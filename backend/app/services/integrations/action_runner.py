"""
Run one action on a connected integration: the single path both agent tools
and workflow action steps go through.

It used to be two copies, and they had drifted. The workflow step checked the
action against the registry, scoped the connection to the workspace, applied
the connection's saved defaults and closed the connector; the agent tool path
did none of that, so an agent could be pointed at any method on a connector
and always booked into "primary" instead of the calendar chosen at connect time.

Actions that change or remove existing data carry extra rules when an **agent**
calls them, because the arguments come from an LLM mid-conversation:

* **Delete is opt-in.** A tool must have ``allow_destructive`` switched on, or a
  delete action is refused, both when the tool is saved and when it runs.
* **Confirm first.** Update and delete calls must carry ``confirmed: true``.
  Without it nothing is changed and the agent is told to read the change back
  and ask. The flag is added to the tool's schema at definition time (see
  ``confirmation_parameter``), so tools saved earlier get it too.
* **Pinned targets.** Resource fields (the calendar, the list) come from the
  connection's defaults and cannot be overridden by the model.
* **Record scope.** An update or delete by record id checks the record really
  belongs to that pinned board or list (``x-scope`` on the action), so an agent
  set up for one Trello board cannot edit cards on another by naming their id.
* **Audit.** Every update or delete, successful or not, is written to
  ``integration_changes`` with a snapshot of the record from just before.

Workflow steps are designed by a person rather than improvised by a model, so
they skip the confirm and opt-in rules but are audited the same way.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.integrations.action_registry import (
    CONNECTOR_CLASS_MAP,
    OP_DELETE,
    adapt_parameters,
    changes_existing_data,
    drop_unsupported_arguments,
    get_action_schema,
    is_destructive,
    operation_of,
    strip_ui_only_parameters,
)
from app.services.integrations.resource_registry import apply_connection_defaults

logger = logging.getLogger(__name__)

SOURCE_AGENT = "agent"
SOURCE_WORKFLOW = "workflow"

#: The argument an agent must set to true on an update or delete.
CONFIRM_KEY = "confirmed"

#: Longest one action may take, lookup-before-change included. An agent is on a
#: live call; a stuck provider or database must end in a sentence it can say,
#: not a silence that outlasts the caller's patience.
ACTION_TIMEOUT_SECONDS = 60


class IntegrationActionError(Exception):
    """The action could not run. The message is safe to show the user or agent."""


def is_enabled(value: Any) -> bool:
    """A tool config flag. The Tools form stores every value as a string."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("true", "1", "yes", "on")


def confirmation_parameter() -> Dict[str, Any]:
    """The schema property added to every update/delete tool an agent sees."""
    return {
        "type": "boolean",
        "description": (
            "Set to true only after you have read the exact change back to the "
            "caller (which record, and what it becomes) and they clearly said yes. "
            "If you call without it, nothing is changed."
        ),
    }


def with_confirmation(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Add the required ``confirmed`` flag to an update/delete tool's schema."""
    schema = dict(parameters or {})
    properties = dict(schema.get("properties") or {})
    properties[CONFIRM_KEY] = confirmation_parameter()
    required = [r for r in (schema.get("required") or []) if r != CONFIRM_KEY] + [CONFIRM_KEY]
    schema.update({"type": "object", "properties": properties, "required": required})
    return schema


def confirmation_instructions(action_def: Dict[str, Any]) -> str:
    """Sentence appended to an update/delete tool's description for the agent."""
    verb = "delete" if operation_of(action_def) == OP_DELETE else "change"
    return (
        f" This will {verb} existing data. First look the record up, read back "
        f"exactly what will {verb} and wait for the caller to say yes, then call "
        f"with confirmed=true."
    )


async def run_integration_action(
    db: AsyncSession,
    *,
    organization_id: Optional[uuid.UUID],
    connection_id: Any,
    action: str,
    parameters: Optional[Dict[str, Any]],
    source: str,
    tool_config: Optional[Dict[str, Any]] = None,
    tool_id: Optional[uuid.UUID] = None,
    call_id: Optional[str] = None,
) -> Any:
    """Run ``action`` on the connection and return the connector's result.

    Raises:
        IntegrationActionError: the action is not allowed or could not run.
            When an agent has not confirmed an update/delete, returns a
            ``needs_confirmation`` result instead of raising, so the model gets
            a plain instruction rather than an error to apologise for.
    """
    from app.models.integration import IntegrationConnection, IntegrationConnector
    from app.services.integrations import connectors as connector_module

    if organization_id is None:
        raise IntegrationActionError("This action cannot run without a workspace.")
    if not connection_id:
        raise IntegrationActionError("No connected integration is set for this action.")
    if not action:
        raise IntegrationActionError("No action is set.")

    try:
        conn_uuid = connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id))
    except ValueError:
        raise IntegrationActionError(f"Connection {connection_id} not found")

    # Scoped to the workspace: the id comes from saved config, and without this
    # it could name another workspace's connection and run with its tokens.
    connection = (
        await db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.id == conn_uuid,
                IntegrationConnection.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        # Same message as a missing one, so a probe learns nothing.
        raise IntegrationActionError(f"Connection {connection_id} not found")

    connector = await db.get(IntegrationConnector, connection.connector_id)
    if connector is None:
        raise IntegrationActionError("Connector not found")

    slug = connector.slug
    class_name = CONNECTOR_CLASS_MAP.get(slug)
    if not class_name:
        raise IntegrationActionError(f"Unsupported connector: {slug}")

    # The registry is the allowlist. Without this check any method on the
    # connector could be named, including internal helpers and update/delete
    # methods that were never exposed.
    action_def = get_action_schema(slug, action)
    if not action_def:
        raise IntegrationActionError(f"Action '{action}' is not available on {slug}")

    operation = operation_of(action_def)
    changes_data = changes_existing_data(action_def)
    supplied = dict(parameters or {})
    confirmed = is_enabled(supplied.pop(CONFIRM_KEY, None))

    if source == SOURCE_AGENT:
        if is_destructive(action_def) and not is_enabled((tool_config or {}).get("allow_destructive")):
            raise IntegrationActionError(
                f"Deleting is turned off for this tool, so '{action_def.get('label') or action}' "
                f"was not run. Turn on \"Allow deleting\" in the tool's settings to use it."
            )
        if changes_data and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "message": (
                    "Nothing was changed. Read the change back to the caller: which record, "
                    "and exactly what will change. If they say yes, call this tool again "
                    "with the same details and confirmed=true."
                ),
            }

    # Some writes are only allowed on a target chosen for the connection, never
    # on one the model names: Supabase's key usually bypasses row-level
    # security, so an agent could otherwise write to any table in the project.
    if source == SOURCE_AGENT:
        chosen = ((connection.config or {}).get("defaults")) or {}
        for key in action_def.get("x-requires-default") or []:
            if chosen.get(key) in (None, ""):
                raise IntegrationActionError(
                    f"Choose which {key.replace('_name', '').replace('_id', '').replace('_', ' ')} agents may change "
                    f"on this integration's page (\"Where things go by default\") before an agent can use "
                    f"'{action_def.get('label') or action}'."
                )

    properties = (action_def.get("parameters") or {}).get("properties") or {}
    accepted = set(properties) or None
    scopes = [s for s in action_def.get("x-scope") or [] if s.get("param")]
    # For agents, resource fields (and any field a scope check relies on) are
    # pinned to the connection's choice.
    pinned = (
        {name for name, spec in properties.items() if isinstance(spec, dict) and spec.get("x-resource")}
        | {s["param"] for s in scopes}
        if source == SOURCE_AGENT
        else None
    )
    params = apply_connection_defaults(supplied, connection.config, accepted_keys=accepted, pin_keys=pinned)
    # Read before strip_ui_only_parameters: a scope field is often UI-only
    # (Trello's board_id), so the connector method never sees it.
    expected_scope = {s["param"]: params.get(s["param"]) for s in scopes} if source == SOURCE_AGENT else {}
    params = strip_ui_only_parameters(slug, action, params)
    # Keep the schema-named values for the audit row, before renaming.
    audited_params = dict(params)
    try:
        params = adapt_parameters(slug, action, params)
    except ValueError as exc:  # e.g. "Nothing to change"
        raise IntegrationActionError(str(exc))

    instance = getattr(connector_module, class_name)(connection=connection, connector=connector, db=db)
    try:
        if not hasattr(instance, action):
            raise IntegrationActionError(f"Action '{action}' not found on {class_name}")
        method = getattr(instance, action)
        params = drop_unsupported_arguments(method, params, context=f"{slug}.{action}")

        label = action_def.get("label") or action
        try:
            async with asyncio.timeout(ACTION_TIMEOUT_SECONDS):
                before = await _snapshot(instance, action_def, params) if changes_data else None
        except TimeoutError:
            raise _too_slow(label, writes=False)
        _check_scope(action_def, scopes, expected_scope, before)

        try:
            try:
                async with asyncio.timeout(ACTION_TIMEOUT_SECONDS):
                    result = await method(**params)
            except TimeoutError:
                raise _too_slow(label, writes=operation != "read")
        except Exception as exc:
            if changes_data:
                await _audit(
                    db, organization_id=organization_id, connection_id=connection.id, slug=slug,
                    action=action, operation=operation, params=audited_params, before=before,
                    result=None, error=str(exc), source=source, tool_id=tool_id, call_id=call_id,
                )
            raise

        if changes_data:
            await _audit(
                db, organization_id=organization_id, connection_id=connection.id, slug=slug,
                action=action, operation=operation, params=audited_params, before=before,
                result=result, error=None, source=source, tool_id=tool_id, call_id=call_id,
            )
        return result
    finally:
        close = getattr(instance, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:  # noqa: BLE001 - cleanup must not mask the result
                pass


def _too_slow(label: str, writes: bool) -> IntegrationActionError:
    """What the agent hears when an action runs past ``ACTION_TIMEOUT_SECONDS``."""
    tail = (
        " It may still have gone through, so check the app before trying again."
        if writes
        else " Try again in a moment."
    )
    return IntegrationActionError(
        f"'{label}' took longer than {ACTION_TIMEOUT_SECONDS} seconds and was stopped.{tail}"
    )


def _dig(record: Optional[Dict[str, Any]], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _same_id(value: Any) -> str:
    """Ids compared loosely: Notion writes the same id with and without dashes."""
    return str(value or "").replace("-", "").strip().lower()


def _check_scope(
    action_def: Dict[str, Any],
    scopes: list,
    expected: Dict[str, Any],
    before: Optional[Dict[str, Any]],
) -> None:
    """Refuse to change a record outside the board/list this tool is set to."""
    for scope in scopes:
        want = expected.get(scope["param"])
        if not want:
            continue  # No board/list chosen for this connection: nothing to hold it to.
        label = scope.get("label") or scope["param"].replace("_id", "")
        if before is None:
            raise IntegrationActionError(
                f"Could not check that record is on the {label} this tool manages, so nothing was changed. "
                f"Look it up again and use the id from the results."
            )
        got = _dig(before, scope.get("field") or scope["param"])
        if _same_id(got) != _same_id(want):
            raise IntegrationActionError(
                f"That record is not on the {label} this tool manages, so nothing was changed."
            )


async def _snapshot(instance: Any, action_def: Dict[str, Any], params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The record as it was before the change, for the audit log. Best effort."""
    spec = action_def.get("x-snapshot") or {}
    method = getattr(instance, spec.get("method") or "", None)
    if method is None:
        return None
    args = {k: params[k] for k in spec.get("args") or [] if params.get(k) not in (None, "")}
    try:
        found = await method(**args)
        return found if isinstance(found, dict) else {"value": found}
    except Exception as exc:  # noqa: BLE001 - the change itself reports the real error
        logger.info(f"No snapshot before {action_def.get('action')}: {exc}")
        return None


def _record_id(params: Dict[str, Any], result: Any) -> Optional[str]:
    for key in ("event_id", "record_id", "task_id", "card_id", "contact_id", "deal_id", "id", "key", "object_key"):
        if params.get(key):
            return str(params[key])[:255]
    if isinstance(result, dict) and result.get("id"):
        return str(result["id"])[:255]
    return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, dict):
        return value
    return {"value": value if isinstance(value, (str, int, float, bool, list)) else str(value)}


async def _audit(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    slug: str,
    action: str,
    operation: str,
    params: Dict[str, Any],
    before: Optional[Dict[str, Any]],
    result: Any,
    error: Optional[str],
    source: str,
    tool_id: Optional[uuid.UUID],
    call_id: Optional[str],
) -> None:
    """Write one ``integration_changes`` row. Never fails the action itself."""
    from app.models.integration import IntegrationChange

    try:
        db.add(
            IntegrationChange(
                organization_id=organization_id,
                connection_id=connection_id,
                connector_slug=slug,
                action=action,
                operation=operation,
                record_id=_record_id(params, result),
                source=source,
                tool_id=tool_id,
                call_id=str(call_id)[:255] if call_id else None,
                parameters=_jsonable(params),
                before=_jsonable(before),
                result=_jsonable(result),
                success=error is None,
                error_message=error,
            )
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Could not record the {slug}.{action} change: {exc}", exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
