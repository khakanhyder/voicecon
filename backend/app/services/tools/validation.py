"""
What a tool needs before it may be saved.

The builder form marks fields as required, but nothing enforced it: the API
stored any config it was given, so a Transfer Call with no destination or an
API Request with no URL saved cleanly and only failed on a live call, after the
agent had already told the caller it was transferring them. This module is the
gate, and ``frontend/src/lib/toolValidation.ts`` mirrors it so the form can
point at the field before the request is sent. Keep the two in step.

Errors are keyed by the config field they belong to, so the form can show each
one under its own input. Values may arrive as the text the form stores or as
the parsed JSON an API client sends, and both spellings are accepted — the
executors read either (see :mod:`app.services.tools.config`).
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tools.config import ToolConfigError, as_header_map, as_mapping

#: Tool types that can be created. ``integration`` is the older spelling of
#: ``connected_integration`` and executes identically.
CREATABLE_TOOL_TYPES = frozenset({
    "workflow",
    "transfer_call", "hang_up", "leave_voicemail", "dtmf", "send_sms", "sip_request",
    "handoff", "query_knowledge_base",
    "connected_integration", "integration",
    "api_request", "mcp", "slack", "custom_tool",
})

#: Types the executor refuses outright — they need a connection's credentials,
#: which only a Connected Integration tool carries. Creating one produced a tool
#: that could never run, so they are rejected with the way forward instead.
RETIRED_TOOL_TYPES = {
    "google_sheets": "Google Sheets",
    "google_calendar": "Google Calendar",
    "gohighlevel": "GoHighLevel",
}

HTTP_METHODS = {
    "api_request": {"GET", "POST", "PUT", "PATCH", "DELETE"},
    "custom_tool": {"GET", "POST", "PUT", "PATCH"},
}
SIP_METHODS = {"INVITE", "BYE", "REFER"}
AUTH_TYPES = {"none", "bearer", "basic", "custom_header"}

MIN_TIMEOUT = 1
MAX_TIMEOUT = 120

#: A dialable number: a leading +, then 7–15 digits, with the separators people
#: paste in. The + is required because the carrier dials it as E.164 — a
#: national number without its country code is not reachable.
_PHONE = re.compile(r"^\+[\d\s().-]+$")
_SIP_URI = re.compile(r"^sips?:[^\s@]+@[^\s@]+$|^sips?:[^\s@]+\.[^\s@]+$", re.IGNORECASE)
#: A value filled in during the call, such as ``{{caller_number}}``.
_TEMPLATE = re.compile(r"^\{\{\s*[A-Za-z_][\w.]*\s*\}\}$")
_DTMF = re.compile(r"^[0-9A-Da-d*#wW]+$")
#: A header name per RFC 7230 ``token``.
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
#: A parameter name the model can emit as a JSON key and a template can reference.
_PARAM_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARAM_TYPES = {"string", "number", "integer", "boolean", "object", "array"}


def _text(config: Dict[str, Any], key: str) -> str:
    value = config.get(key)
    return value.strip() if isinstance(value, str) else ("" if value is None else str(value).strip())


def _is_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return bool(_PHONE.match(value)) and 7 <= len(digits) <= 15


def _is_http_url(value: str) -> bool:
    """A full http(s) URL with a real host — ``https://api`` is a typo, not a server.

    Reachability (public address, no internal targets) is decided at request
    time by :func:`app.core.egress.assert_safe_url`, because DNS can change.
    """
    if re.search(r"\s", value):
        return False
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and ("." in host or ":" in host)


def _require(errors: Dict[str, str], config: Dict[str, Any], key: str, label: str) -> str:
    value = _text(config, key)
    if not value:
        errors[key] = f"{label} is required."
    return value


def _check_url(errors: Dict[str, str], config: Dict[str, Any], key: str, label: str, https_only: bool = False) -> None:
    value = _require(errors, config, key, label)
    if not value:
        return
    if not _is_http_url(value):
        errors[key] = f"{label} must be a full URL starting with http:// or https://."
    elif https_only and not value.lower().startswith("https://"):
        errors[key] = f"{label} must start with https://."


def _check_method(errors: Dict[str, str], config: Dict[str, Any], allowed: set) -> None:
    value = _text(config, "method")
    if value and value.upper() not in allowed:
        errors["method"] = f"Method must be one of {', '.join(sorted(allowed))}."


def _check_timeout(errors: Dict[str, str], config: Dict[str, Any]) -> None:
    value = _text(config, "timeout")
    if not value:
        return
    try:
        seconds = float(value)
    except ValueError:
        errors["timeout"] = "Timeout must be a number of seconds."
        return
    if not MIN_TIMEOUT <= seconds <= MAX_TIMEOUT:
        errors["timeout"] = f"Timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds."


def _check_json_object(errors: Dict[str, str], config: Dict[str, Any], key: str, label: str, headers: bool = False) -> None:
    try:
        if headers:
            as_header_map(config.get(key), label)
        else:
            as_mapping(config.get(key), label)
    except ToolConfigError as exc:
        errors[key] = str(exc)


def _check_parameters(errors: Dict[str, str], config: Dict[str, Any]) -> None:
    """The parameter schema the builder writes under ``config.parameters``."""
    schema = config.get("parameters")
    if schema is None:
        return
    if not isinstance(schema, dict):
        errors["parameters"] = "Parameters must be a JSON schema object."
        return
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        errors["parameters"] = "Parameters must list their properties as an object."
        return
    for name, definition in properties.items():
        if not _PARAM_NAME.match(str(name)):
            errors["parameters"] = (
                f"Parameter name '{name}' may only use letters, numbers and "
                f"underscores, and cannot start with a number."
            )
            return
        kind = definition.get("type") if isinstance(definition, dict) else None
        if kind not in _PARAM_TYPES:
            errors["parameters"] = f"Parameter '{name}' needs a valid type."
            return
    required = schema.get("required") or []
    if not isinstance(required, list) or any(r not in properties for r in required):
        errors["parameters"] = "Required parameters must all be defined."


def validate_tool_config(tool_type: str, config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Field-level problems with a tool's configuration.

    Checks only what can be decided from the values themselves; whether a
    referenced workflow, knowledge base or connection exists is
    :func:`check_tool_references`, which needs the database.

    Args:
        tool_type: The tool's type
        config: The tool's configuration as submitted

    Returns:
        ``{field: message}``; empty when the configuration is usable
    """
    cfg = config or {}
    errors: Dict[str, str] = {}

    if tool_type in RETIRED_TOOL_TYPES:
        app_name = RETIRED_TOOL_TYPES[tool_type]
        return {"tool_type": (
            f"{app_name} tools run through a connected integration. Connect "
            f"{app_name} under Integrations, then create a Connected "
            f"Integration tool instead."
        )}
    if tool_type not in CREATABLE_TOOL_TYPES:
        return {"tool_type": f"'{tool_type}' is not a supported tool type."}

    if tool_type == "workflow":
        _require(errors, cfg, "workflow_id", "Workflow")

    elif tool_type in ("connected_integration", "integration"):
        _require(errors, cfg, "connection_id", "Connected integration")
        _require(errors, cfg, "action", "Action")

    elif tool_type == "transfer_call":
        destination = _require(errors, cfg, "destination", "Transfer destination")
        if destination and not (_is_phone(destination) or _SIP_URI.match(destination) or _TEMPLATE.match(destination)):
            errors["destination"] = (
                "Enter a phone number with country code (e.g. +15551234567) "
                "or a SIP URI (e.g. sip:agent@example.com)."
            )

    elif tool_type == "leave_voicemail":
        _require(errors, cfg, "message", "Voicemail message")

    elif tool_type == "send_sms":
        to = _require(errors, cfg, "to", "Recipient number")
        if to and not (_is_phone(to) or _TEMPLATE.match(to)):
            errors["to"] = (
                "Enter a phone number with country code (e.g. +15551234567) "
                "or {{caller_number}}."
            )
        _require(errors, cfg, "message", "Message template")

    elif tool_type == "dtmf":
        digits = _require(errors, cfg, "digits", "DTMF digits")
        if digits and not _DTMF.match(digits):
            errors["digits"] = "Use only 0-9, *, #, A-D, and w for a pause."
        elif len(digits) > 64:
            errors["digits"] = "DTMF digits cannot be longer than 64 characters."

    elif tool_type == "sip_request":
        sip_uri = _require(errors, cfg, "sip_uri", "SIP URI")
        if sip_uri and not _SIP_URI.match(sip_uri):
            errors["sip_uri"] = "Enter a SIP URI such as sip:user@example.com."
        _check_method(errors, cfg, SIP_METHODS)

    elif tool_type == "handoff":
        _require(errors, cfg, "destination", "Destination queue / agent")

    elif tool_type == "query_knowledge_base":
        _require(errors, cfg, "knowledge_base_id", "Knowledge base")

    elif tool_type == "api_request":
        _check_url(errors, cfg, "url", "Server URL")
        _check_method(errors, cfg, HTTP_METHODS["api_request"])
        _check_timeout(errors, cfg)
        _check_json_object(errors, cfg, "headers", "Headers", headers=True)
        _check_json_object(errors, cfg, "body", "Body template")

    elif tool_type == "mcp":
        _check_url(errors, cfg, "server_url", "MCP server URL")
        tool_name = _require(errors, cfg, "tool_name", "Tool name")
        if tool_name and re.search(r"\s", tool_name):
            errors["tool_name"] = "Tool name cannot contain spaces."
        _check_timeout(errors, cfg)

    elif tool_type == "slack":
        _check_url(errors, cfg, "webhook_url", "Slack webhook URL", https_only=True)
        _require(errors, cfg, "message", "Message template")

    elif tool_type == "custom_tool":
        _check_url(errors, cfg, "url", "Server URL")
        _check_method(errors, cfg, HTTP_METHODS["custom_tool"])
        _check_timeout(errors, cfg)
        auth = (_text(cfg, "auth_type") or "none").lower()
        if auth not in AUTH_TYPES:
            errors["auth_type"] = "Choose a valid authentication type."
        elif auth == "bearer":
            _require(errors, cfg, "auth_token", "Bearer token")
        elif auth == "basic":
            _require(errors, cfg, "auth_user", "Username")
            _require(errors, cfg, "auth_pass", "Password")
        elif auth == "custom_header":
            header = _require(errors, cfg, "auth_header", "Header name")
            if header and not _HEADER_NAME.match(header):
                errors["auth_header"] = "Header name cannot contain spaces or special characters."
            _require(errors, cfg, "auth_value", "Header value")
        _check_json_object(errors, cfg, "headers", "Extra headers", headers=True)

    _check_parameters(errors, cfg)
    return errors


async def check_tool_references(
    tool_type: str,
    config: Optional[Dict[str, Any]],
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Dict[str, str]:
    """Problems with what a tool points at: it must exist in this workspace.

    A tool naming another workspace's workflow or connection must not save — the
    executor loads those by id, so it is also a cross-tenant boundary.
    """
    from app.models.integration import IntegrationConnection, IntegrationConnector, Workflow
    from app.models.knowledge_base import KnowledgeBase
    from app.services.integrations.action_registry import get_action_schema

    cfg = config or {}
    errors: Dict[str, str] = {}

    def _uuid(key: str) -> Optional[uuid.UUID]:
        try:
            return uuid.UUID(_text(cfg, key))
        except ValueError:
            return None

    if tool_type == "workflow" and _text(cfg, "workflow_id"):
        workflow_id = _uuid("workflow_id")
        found = workflow_id and (await db.execute(
            select(Workflow.id).where(and_(Workflow.id == workflow_id, Workflow.organization_id == org_id))
        )).scalar_one_or_none()
        if not found:
            errors["workflow_id"] = "That workflow no longer exists. Choose another."

    elif tool_type == "query_knowledge_base" and _text(cfg, "knowledge_base_id"):
        kb_id = _uuid("knowledge_base_id")
        found = kb_id and (await db.execute(
            select(KnowledgeBase.id).where(and_(KnowledgeBase.id == kb_id, KnowledgeBase.organization_id == org_id))
        )).scalar_one_or_none()
        if not found:
            errors["knowledge_base_id"] = "That knowledge base no longer exists. Choose another."

    elif tool_type in ("connected_integration", "integration") and _text(cfg, "connection_id"):
        connection_id = _uuid("connection_id")
        row = connection_id and (await db.execute(
            select(IntegrationConnector.slug)
            .join(IntegrationConnection, IntegrationConnection.connector_id == IntegrationConnector.id)
            .where(and_(
                IntegrationConnection.id == connection_id,
                IntegrationConnection.organization_id == org_id,
                IntegrationConnection.is_active == True,  # noqa: E712
            ))
        )).scalar_one_or_none()
        if not row:
            errors["connection_id"] = "That integration is no longer connected. Choose another."
        elif _text(cfg, "action") and not get_action_schema(row, _text(cfg, "action")):
            errors["action"] = "That action is not available for this integration."

    return errors
