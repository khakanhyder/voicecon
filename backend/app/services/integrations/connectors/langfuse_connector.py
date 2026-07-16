"""
Langfuse Connector.

Integrates with the Langfuse REST API for LLM observability.
Auth uses HTTP Basic where the username is the Public Key and the
password is the Secret Key. The user supplies these as a Base64-encoded
"public_key:secret_key" string in the api_key field.
"""
import base64
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class LangfuseConnector(BaseConnector):
    """
    Langfuse connector.

    Actions:
    - test_connection: verify credentials via /api/public/health
    - create_trace: create a new trace
    - create_generation: create a generation (LLM call log)
    - create_span: create a span (sub-operation)
    - create_score: score a trace or observation
    - list_traces: list recent traces
    """

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """Langfuse uses HTTP Basic auth with public_key:secret_key."""
        return {"Authorization": f"Basic {access_token}"}

    def _get_keys(self) -> Dict[str, str]:
        """Return public and secret keys from auth data."""
        data = self.get_auth_data()
        return {
            "public_key": data.get("public_key", ""),
            "secret_key": data.get("secret_key", ""),
            "host": data.get("host", "https://cloud.langfuse.com"),
        }

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/api/public/health")
            return {
                "success": True,
                "message": "Langfuse connection successful",
                "details": {"status": res.get("status", "ok")},
            }
        except Exception as e:
            logger.error(f"Langfuse connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Langfuse connection test failed: {e}", "details": {}}

    async def create_trace(self, name: str, input_data: Optional[str] = None,
                           output_data: Optional[str] = None,
                           user_id: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None,
                           session_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new trace for an LLM operation."""
        try:
            body: Dict[str, Any] = {"name": name}
            if input_data: body["input"] = input_data
            if output_data: body["output"] = output_data
            if user_id: body["userId"] = user_id
            if metadata: body["metadata"] = metadata
            if session_id: body["sessionId"] = session_id

            res = await self.post("/api/public/traces", json=body)
            logger.info(f"Langfuse trace created: {res.get('id')}")
            return {"id": res.get("id"), "name": name, "success": True}
        except Exception as e:
            logger.error(f"Langfuse create_trace failed: {e}", exc_info=True)
            raise ConnectorError(f"Langfuse create_trace failed: {e}")

    async def create_generation(self, trace_id: str, name: str,
                                model: Optional[str] = None,
                                input_data: Optional[str] = None,
                                output_data: Optional[str] = None,
                                usage: Optional[Dict[str, Any]] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Log an LLM generation (model call)."""
        try:
            body: Dict[str, Any] = {
                "traceId": trace_id,
                "name": name,
                "type": "GENERATION",
            }
            if model: body["model"] = model
            if input_data: body["input"] = input_data
            if output_data: body["output"] = output_data
            if usage: body["usage"] = usage
            if metadata: body["metadata"] = metadata

            res = await self.post("/api/public/generations", json=body)
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"Langfuse create_generation failed: {e}")

    async def create_span(self, trace_id: str, name: str,
                          input_data: Optional[str] = None,
                          output_data: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a span (sub-operation within a trace)."""
        try:
            body: Dict[str, Any] = {
                "traceId": trace_id,
                "name": name,
            }
            if input_data: body["input"] = input_data
            if output_data: body["output"] = output_data
            if metadata: body["metadata"] = metadata

            res = await self.post("/api/public/spans", json=body)
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"Langfuse create_span failed: {e}")

    async def create_score(self, trace_id: str, name: str, value: float,
                           observation_id: Optional[str] = None,
                           comment: Optional[str] = None) -> Dict[str, Any]:
        """Score a trace or observation."""
        try:
            body: Dict[str, Any] = {
                "traceId": trace_id,
                "name": name,
                "value": value,
            }
            if observation_id: body["observationId"] = observation_id
            if comment: body["comment"] = comment

            res = await self.post("/api/public/scores", json=body)
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"Langfuse create_score failed: {e}")

    async def list_traces(self, limit: int = 20, page: int = 1) -> Dict[str, Any]:
        """List recent traces."""
        try:
            res = await self.get(
                "/api/public/traces",
                params={"limit": limit, "page": page},
            )
            traces = [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "user_id": t.get("userId"),
                    "timestamp": t.get("timestamp"),
                }
                for t in res.get("data", [])
            ]
            return {"traces": traces, "count": len(traces)}
        except Exception as e:
            raise ConnectorError(f"Langfuse list_traces failed: {e}")
