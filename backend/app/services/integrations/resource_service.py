"""
Fetches the pickable resources inside a connection.

Sits between the HTTP layer and the connectors: resolves the connection, builds
the right connector, calls its listing method and normalises the result. The
cache matters more than it looks — a picker fires on open and on every
keystroke, and Trello starts returning 429 well before a user notices they are
being rate limited.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConnection, IntegrationConnector
from app.services.integrations.action_registry import CONNECTOR_CLASS_MAP
from app.services.integrations.resource_registry import (
    ResourceSpec,
    get_spec,
    normalize_resources,
    search_resources,
)

logger = logging.getLogger(__name__)

#: Long enough that typing in the search box costs nothing, short enough that a
#: list created seconds ago in another tab shows up when the user looks for it.
CACHE_TTL_SECONDS = 60


class ResourceError(Exception):
    """A resource listing failed for a reason worth showing the user."""

    def __init__(self, message: str, *, code: str = "resource_error"):
        super().__init__(message)
        self.code = code


#: (connection_id, kind, parent_id) -> (expires_at, resources)
_cache: Dict[Tuple[str, str, str], Tuple[float, List[Dict[str, str]]]] = {}


def invalidate_connection(connection_id: uuid.UUID | str) -> None:
    """Drop every cached kind for a connection.

    Called when a connection is reconnected or its defaults change, so a
    freshly re-authorised account never serves a list fetched with the old
    token's permissions.
    """
    key = str(connection_id)
    for cached in [k for k in _cache if k[0] == key]:
        _cache.pop(cached, None)


async def _load_connection(
    db: AsyncSession, connection_id: uuid.UUID, organization_id: uuid.UUID
) -> Tuple[IntegrationConnection, IntegrationConnector]:
    result = await db.execute(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise ResourceError("Connection not found", code="not_found")

    result = await db.execute(
        select(IntegrationConnector).where(
            IntegrationConnector.id == connection.connector_id
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise ResourceError("Connector not found", code="not_found")

    return connection, connector


async def list_resources(
    db: AsyncSession,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    kind: str,
    *,
    parent: Optional[str] = None,
    query: Optional[str] = None,
    refresh: bool = False,
) -> Dict[str, Any]:
    """List one kind of resource inside a connection.

    Returns ``{"resources": [{"id", "name"}], "label": str, "cached": bool}``.

    Raises :class:`ResourceError` with a code the frontend switches on, so a
    disconnected integration renders a "Reconnect" button rather than an empty
    dropdown that looks like the account has nothing in it.
    """
    connection, connector = await _load_connection(db, connection_id, organization_id)
    slug = connector.slug

    spec: Optional[ResourceSpec] = get_spec(slug, kind)
    if spec is None:
        raise ResourceError(
            f"{connector.name} cannot list '{kind}'.", code="unsupported_kind"
        )

    if spec.parent_kind and not parent:
        # Not an error: the builder shows the child picker disabled until the
        # parent is chosen, and asks again once it is.
        return {
            "resources": [],
            "label": spec.label,
            "needs_parent": spec.parent_kind,
            "cached": False,
        }

    if not connection.is_active or connection.status != "active":
        raise ResourceError(
            f"{connector.name} is disconnected. Reconnect it to choose a {spec.label.lower()}.",
            code="disconnected",
        )

    cache_key = (str(connection_id), kind, parent or "")
    if not refresh:
        cached = _cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return {
                "resources": search_resources(cached[1], query),
                "label": spec.label,
                "empty_hint": spec.empty_hint,
                "cached": True,
            }

    class_name = CONNECTOR_CLASS_MAP.get(slug)
    if not class_name:
        raise ResourceError(
            f"No connector implementation for '{slug}'.", code="unsupported_connector"
        )

    from app.services.integrations import connectors as connector_module

    connector_class = getattr(connector_module, class_name, None)
    if connector_class is None:
        raise ResourceError(
            f"Connector class {class_name} is not available.",
            code="unsupported_connector",
        )

    instance = connector_class(connection=connection, connector=connector, db=db)
    try:
        method = getattr(instance, spec.method, None)
        if method is None:
            raise ResourceError(
                f"{connector.name} cannot list {spec.label.lower()}s.",
                code="unsupported_kind",
            )

        kwargs: Dict[str, Any] = dict(spec.fixed_args)
        if spec.parent_arg and parent:
            kwargs[spec.parent_arg] = parent

        try:
            raw = await method(**kwargs)
        except Exception as exc:  # noqa: BLE001 — provider errors are user-facing
            logger.warning(
                f"Listing {kind} on {slug} connection {connection_id} failed: {exc}"
            )
            raise ResourceError(
                f"Could not reach {connector.name}. It may need reconnecting.",
                code="provider_error",
            )
    finally:
        try:
            await instance.close()
        except Exception:  # noqa: BLE001 — closing must not mask the real error
            pass

    resources = normalize_resources(raw, spec)
    _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, resources)

    return {
        "resources": search_resources(resources, query),
        "label": spec.label,
        "empty_hint": spec.empty_hint,
        "cached": False,
    }


async def resolve_names(
    db: AsyncSession,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    kind: str,
    ids: List[str],
    *,
    parent: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Map stored ids back to display names.

    A workflow saved last month holds ids, but the builder must show names when
    it reopens. An id that no longer resolves maps to ``None`` so the field can
    say "no longer available" instead of rendering a raw string the user has no
    way to interpret.
    """
    if not ids:
        return {}
    try:
        listed = await list_resources(
            db, organization_id, connection_id, kind, parent=parent
        )
    except ResourceError:
        return {identifier: None for identifier in ids}

    by_id = {r["id"]: r["name"] for r in listed.get("resources", [])}
    return {identifier: by_id.get(identifier) for identifier in ids}
