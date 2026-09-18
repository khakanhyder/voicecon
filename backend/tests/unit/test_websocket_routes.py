"""
WebSocket routes must not sit under the router-wide workspace guard.

The guard's OAuth2 dependency needs an HTTP Request; on a WebSocket it raised
before the handshake, so the browser test call's Deepgram STT socket and the
workflow run stream both failed with a 500 and the UI silently fell back.
"""
from fastapi.routing import APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest

from app.main import app

BROWSER_SOCKETS = [
    "/api/v1/agents/00000000-0000-0000-0000-000000000000/stt",
    "/api/v1/workflows/00000000-0000-0000-0000-000000000000/executions/stream",
]


def _all_dependency_calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _all_dependency_calls(dep)


def test_browser_websockets_carry_no_http_only_dependencies():
    from fastapi.security import OAuth2PasswordBearer

    routes = {
        r.path: r for r in app.routes if isinstance(r, APIWebSocketRoute)
    }
    for path in ("/api/v1/agents/{agent_id}/stt", "/api/v1/workflows/{workflow_id}/executions/stream"):
        assert path in routes, path
        calls = list(_all_dependency_calls(routes[path].dependant))
        assert not any(isinstance(c, OAuth2PasswordBearer) for c in calls), path


@pytest.mark.parametrize("path", BROWSER_SOCKETS)
def test_bad_token_is_rejected_after_handshake(path):
    client = TestClient(app)
    with client.websocket_connect(f"{path}?token=not-a-jwt") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 4001
