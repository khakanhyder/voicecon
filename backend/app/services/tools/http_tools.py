"""
The tool types that are, underneath, one outbound HTTP request.

``api_request``, ``custom_tool``, ``mcp`` and ``slack`` differ only in where
their URL is configured, how they authenticate, and what shape the payload
takes. They were implemented twice — once in the live executor and once in the
endpoint behind the builder's "Test" button — and the two copies drifted, which
is how the test path kept an SSRF hole that the executor had already closed and
how both kept reading config keys the form does not write.

One implementation, both callers. A tool that passes Test now runs the same
request on a live call, which is the only thing that makes Test worth pressing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.services.tools.config import (
    ToolConfigError,
    as_header_map,
    as_text,
    as_timeout,
    build_body,
    render,
)

logger = logging.getLogger(__name__)

#: Tool types this module executes.
HTTP_TOOL_TYPES = frozenset({"api_request", "custom_tool", "mcp", "slack"})

#: How much of a response body to keep. Enough for an agent to answer from, or
#: for a developer to see what went wrong, without putting a large document
#: into a call log or an LLM context window.
_MAX_BODY = 2000


def require_safe_url(raw: Any, label: str) -> str:
    """A configured destination URL, checked before anything connects to it.

    The URL is author-supplied and the response body comes back in the tool
    result, so an unrestricted fetch is a read primitive against the cloud
    metadata endpoint and every internal service this container can route to.
    Every caller here disables redirects for the same reason — a public URL can
    302 to a private one after this check passes.
    """
    url = str(raw or "").strip()
    if not url:
        raise ToolConfigError(f"No URL configured for the {label} tool")

    from app.core.egress import UnsafeURLError, assert_safe_url

    try:
        assert_safe_url(url)
    except UnsafeURLError as exc:
        raise ToolConfigError(f"{label} url rejected: {exc}") from exc
    return url


def auth_headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    """The Authorization (or custom) header a custom tool's auth mode implies.

    The field names here are the ones the builder form actually writes. Bearer
    auth read the right key, but basic auth looked for ``username`` and
    ``password`` while the form stores ``auth_user`` and ``auth_pass``, so the
    header was silently never added and every request went out unauthenticated
    — a 401 nobody could explain from the configuration in front of them. The
    ``custom_header`` mode was offered by the form and not implemented at all.

    Both spellings are accepted so a tool saved against the older code keeps
    working.
    """
    mode = str(cfg.get("auth_type") or "none").strip().lower()

    if mode == "bearer":
        token = str(cfg.get("auth_token") or "").strip()
        if not token:
            raise ToolConfigError(
                "Bearer authentication is selected but no token is set"
            )
        return {"Authorization": f"Bearer {token}"}

    if mode == "basic":
        user = str(cfg.get("auth_user") or cfg.get("username") or "")
        password = str(cfg.get("auth_pass") or cfg.get("password") or "")
        if not user and not password:
            raise ToolConfigError(
                "Basic authentication is selected but no username or password "
                "is set"
            )
        import base64

        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    if mode == "custom_header":
        name = str(cfg.get("auth_header") or "").strip()
        if not name:
            raise ToolConfigError(
                "Custom header authentication is selected but no header name "
                "is set"
            )
        return {name: as_text(cfg.get("auth_value"))}

    return {}


async def run_http_tool(
    tool_type: str,
    cfg: Dict[str, Any],
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute one HTTP-shaped tool and return its result.

    Args:
        tool_type: One of :data:`HTTP_TOOL_TYPES`
        cfg: The tool's stored configuration
        parameters: What the model extracted, or what a test run supplied

    Returns:
        A result dict for the tool log and the agent

    Raises:
        ToolConfigError: The configuration cannot be used as written
        httpx.HTTPError: The request itself failed
    """
    parameters = parameters or {}

    if tool_type == "api_request":
        return await _api_request(cfg, parameters)
    if tool_type == "custom_tool":
        return await _custom_tool(cfg, parameters)
    if tool_type == "mcp":
        return await _mcp(cfg, parameters)
    if tool_type == "slack":
        return await _slack(cfg, parameters)

    raise ToolConfigError(f"'{tool_type}' is not an HTTP tool type")


async def _api_request(
    cfg: Dict[str, Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """A configured request to an arbitrary endpoint.

    The target comes from the tool's *configuration* only. It used to fall back
    to ``parameters["url"]``, and those parameters are what the model extracted
    from a conversation — so a caller who could steer the agent could choose the
    address this server connects to, with the tool's own headers attached.
    Where a request goes is a configuration decision, not something to infer
    from speech.
    """
    url = require_safe_url(cfg.get("url"), "api_request")
    method = str(cfg.get("method") or "POST").upper()
    headers = as_header_map(cfg.get("headers"))
    body = build_body(cfg.get("body"), parameters)

    async with httpx.AsyncClient(
        timeout=as_timeout(cfg.get("timeout"), 20.0), follow_redirects=False
    ) as client:
        resp = await client.request(
            method,
            url,
            headers=headers or None,
            # A GET carries no body; sending one makes some servers reject the
            # request outright, so the values go in the query string instead.
            json=body if method != "GET" and body else None,
            params=body if method == "GET" and body else None,
        )
        return _response(resp)


async def _custom_tool(
    cfg: Dict[str, Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """A webhook to the author's own server, with first-class auth handling."""
    url = require_safe_url(cfg.get("url"), "custom_tool")
    method = str(cfg.get("method") or "POST").upper()
    headers = as_header_map(cfg.get("headers"), "Extra Headers")
    headers.update(auth_headers(cfg))

    async with httpx.AsyncClient(
        timeout=as_timeout(cfg.get("timeout"), 20.0), follow_redirects=False
    ) as client:
        resp = await client.request(
            method,
            url,
            headers=headers or None,
            json=parameters if method != "GET" and parameters else None,
            params=parameters if method == "GET" and parameters else None,
        )
        return _response(resp)


async def _mcp(cfg: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke one tool on a Model Context Protocol server."""
    server_url = require_safe_url(cfg.get("server_url"), "MCP")
    tool_name = str(cfg.get("tool_name") or "").strip()
    if not tool_name:
        raise ToolConfigError("No tool name configured for the MCP tool")

    async with httpx.AsyncClient(
        timeout=as_timeout(cfg.get("timeout"), 15.0), follow_redirects=False
    ) as client:
        resp = await client.post(
            server_url, json={"tool": tool_name, "params": parameters}
        )
        return _response(resp)


async def _slack(cfg: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Post the configured message template to an incoming webhook.

    The form's field is "Message Template" and stores ``message``. This used to
    read ``default_message``, a key the form never writes, so every configured
    template was ignored and every notification arrived as the same placeholder
    line.
    """
    webhook_url = require_safe_url(cfg.get("webhook_url"), "Slack")

    template = (
        cfg.get("message")
        or cfg.get("default_message")
        or "Voicecon agent notification"
    )
    text = as_text(render(template, parameters))
    # A template whose references all resolve to nothing would post an empty
    # message, which Slack rejects and which tells nobody anything.
    if not text.strip():
        text = as_text(parameters.get("message")) or "Voicecon agent notification"

    payload: Dict[str, Any] = {"text": text}
    channel = str(cfg.get("channel") or "").strip()
    if channel:
        payload["channel"] = channel

    async with httpx.AsyncClient(
        timeout=as_timeout(cfg.get("timeout"), 10.0), follow_redirects=False
    ) as client:
        resp = await client.post(webhook_url, json=payload)
        return {
            "status_code": resp.status_code,
            "ok": resp.text.strip() == "ok",
            "message": text,
            "response": resp.text[:500],
        }


def _response(resp: httpx.Response) -> Dict[str, Any]:
    """A response rendered for a tool result.

    The parsed body is included when the endpoint returned JSON, because that
    is what an agent or a later workflow step actually wants to read; the raw
    text is kept alongside it so a non-JSON error page is still visible.
    """
    result: Dict[str, Any] = {
        "status_code": resp.status_code,
        "ok": resp.is_success,
        "body": resp.text[:_MAX_BODY],
    }
    try:
        result["json"] = resp.json()
    except (ValueError, UnicodeDecodeError):
        pass
    return result
