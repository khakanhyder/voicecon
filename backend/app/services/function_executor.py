"""
Function Executor Service.

Handles agent function execution via webhooks with proper
timeout, retry, and error handling.
"""
import logging
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
import httpx
from jsonschema import validate, ValidationError as JSONSchemaError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent import AgentFunction
from app.models.call import CallLog
from app.models.tool import Tool, AgentToolAssignment

logger = logging.getLogger(__name__)


class FunctionExecutionError(Exception):
    """Raised when function execution fails."""
    pass


class FunctionTimeoutError(Exception):
    """Raised when function execution times out."""
    pass


class FunctionValidationError(Exception):
    """Raised when function parameter validation fails."""
    pass


class FunctionExecutor:
    """
    Service for executing agent functions via webhooks.

    Features:
    - Parameter validation (JSON Schema)
    - Webhook HTTP requests with timeout
    - Automatic retries on failure
    - Execution logging
    - Cost tracking
    - Response formatting for LLM
    """

    def __init__(self):
        """Initialize function executor."""
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),  # 30s total, 5s connect
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
        return self.http_client

    async def close(self):
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def validate_parameters(
        self,
        function: AgentFunction,
        parameters: Dict[str, Any]
    ) -> None:
        """
        Validate function parameters against JSON Schema.

        Args:
            function: Agent function with parameter schema
            parameters: Parameters to validate

        Raises:
            FunctionValidationError: If validation fails
        """
        try:
            # Validate against JSON Schema
            validate(instance=parameters, schema=function.parameters)
            logger.info(f"Parameters validated for function: {function.name}")

        except JSONSchemaError as e:
            error_msg = f"Parameter validation failed for {function.name}: {str(e)}"
            logger.error(error_msg)
            raise FunctionValidationError(error_msg)

    async def execute_function(
        self,
        function: AgentFunction,
        parameters: Dict[str, Any],
        call_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Execute a function via webhook.

        Args:
            function: Agent function to execute
            parameters: Function parameters
            call_id: Optional call ID for logging
            db: Optional database session for logging

        Returns:
            Function execution result

        Raises:
            FunctionValidationError: If parameter validation fails
            FunctionTimeoutError: If execution times out
            FunctionExecutionError: If execution fails
        """
        start_time = time.time()

        try:
            # Validate parameters
            self.validate_parameters(function, parameters)

            # Check if function is active
            if not function.is_active:
                raise FunctionExecutionError(f"Function {function.name} is not active")

            # Execute webhook with retries
            result = await self._execute_webhook_with_retry(
                function=function,
                parameters=parameters,
            )

            # Calculate execution time
            execution_time = int((time.time() - start_time) * 1000)  # milliseconds

            # Log execution
            if call_id and db:
                await self._log_execution(
                    function=function,
                    parameters=parameters,
                    result=result,
                    execution_time=execution_time,
                    call_id=call_id,
                    db=db,
                    success=True,
                )

            logger.info(
                f"Function {function.name} executed successfully in {execution_time}ms"
            )

            return {
                "success": True,
                "function_name": function.name,
                "result": result,
                "execution_time_ms": execution_time,
            }

        except (FunctionValidationError, FunctionTimeoutError, FunctionExecutionError) as e:
            execution_time = int((time.time() - start_time) * 1000)

            # Log failed execution
            if call_id and db:
                await self._log_execution(
                    function=function,
                    parameters=parameters,
                    result={"error": str(e)},
                    execution_time=execution_time,
                    call_id=call_id,
                    db=db,
                    success=False,
                    error=str(e),
                )

            logger.error(f"Function {function.name} failed: {str(e)}")

            return {
                "success": False,
                "function_name": function.name,
                "error": str(e),
                "execution_time_ms": execution_time,
            }

    async def _execute_webhook_with_retry(
        self,
        function: AgentFunction,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute webhook with automatic retries.

        Args:
            function: Agent function
            parameters: Function parameters

        Returns:
            Webhook response data

        Raises:
            FunctionTimeoutError: If all retries timeout
            FunctionExecutionError: If all retries fail
        """
        last_error = None
        retry_count = function.retry_count or 3

        for attempt in range(retry_count):
            try:
                result = await self._execute_webhook(function, parameters)
                return result

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"Function {function.name} timeout (attempt {attempt + 1}/{retry_count})"
                )
                if attempt < retry_count - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(2 ** attempt)
                continue

            except httpx.HTTPError as e:
                last_error = e
                logger.warning(
                    f"Function {function.name} HTTP error (attempt {attempt + 1}/{retry_count}): {e}"
                )
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            except Exception as e:
                last_error = e
                logger.error(
                    f"Function {function.name} unexpected error: {e}",
                    exc_info=True
                )
                raise FunctionExecutionError(f"Unexpected error: {str(e)}")

        # All retries failed
        if isinstance(last_error, httpx.TimeoutException):
            raise FunctionTimeoutError(
                f"Function {function.name} timed out after {retry_count} attempts"
            )
        else:
            raise FunctionExecutionError(
                f"Function {function.name} failed after {retry_count} attempts: {str(last_error)}"
            )

    async def _execute_webhook(
        self,
        function: AgentFunction,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute single webhook request.

        Args:
            function: Agent function
            parameters: Function parameters

        Returns:
            Webhook response data

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPError: If HTTP error occurs
        """
        if not function.webhook_url:
            raise FunctionExecutionError(f"Function {function.name} has no webhook URL")

        client = await self._get_http_client()

        # Prepare request
        timeout = (function.timeout or 5000) / 1000.0  # Convert ms to seconds
        headers = function.headers or {}
        headers["Content-Type"] = "application/json"

        # Execute request
        method = (function.http_method or "POST").upper()

        logger.info(
            f"Executing webhook: {method} {function.webhook_url} (timeout: {timeout}s)"
        )

        if method == "GET":
            response = await client.get(
                function.webhook_url,
                params=parameters,
                headers=headers,
                timeout=timeout,
            )
        else:  # POST, PUT, PATCH
            response = await client.request(
                method,
                function.webhook_url,
                json=parameters,
                headers=headers,
                timeout=timeout,
            )

        # Check response status
        response.raise_for_status()

        # Parse response
        try:
            result = response.json()
        except Exception:
            # If not JSON, return text
            result = {"response": response.text}

        return result

    async def _log_execution(
        self,
        function: AgentFunction,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        execution_time: int,
        call_id: str,
        db: AsyncSession,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Log function execution to database.

        Args:
            function: Agent function
            parameters: Function parameters
            result: Execution result
            execution_time: Execution time in milliseconds
            call_id: Call ID
            db: Database session
            success: Whether execution succeeded
            error: Error message if failed
        """
        try:
            # Calculate cost (if applicable)
            # For now, we'll use a simple cost model: $0.001 per function call
            cost = Decimal("0.001")

            call_log = CallLog(
                call_id=call_id,
                log_type="function_call",
                message=f"Function call: {function.name}",
                details={
                    "function_id": str(function.id),
                    "function_name": function.name,
                    "parameters": parameters,
                    "result": result,
                    "success": success,
                    "error": error,
                    "webhook_url": function.webhook_url,
                    "http_method": function.http_method,
                },
                duration_ms=execution_time,
                cost=cost,
                timestamp=datetime.utcnow(),
            )

            db.add(call_log)
            await db.commit()

            logger.info(f"Function execution logged for call {call_id}")

        except Exception as e:
            logger.error(f"Failed to log function execution: {e}", exc_info=True)

    def format_for_llm(
        self,
        function: AgentFunction,
        result: Dict[str, Any],
    ) -> str:
        """
        Format function result for LLM consumption.

        Args:
            function: Agent function
            result: Function execution result

        Returns:
            Formatted string for LLM
        """
        if not result.get("success"):
            return f"Function {function.name} failed: {result.get('error', 'Unknown error')}"

        function_result = result.get("result", {})

        # Format based on result structure
        if isinstance(function_result, dict):
            # Pretty print JSON
            formatted = json.dumps(function_result, indent=2)
            return f"Function {function.name} returned:\n{formatted}"
        elif isinstance(function_result, str):
            return f"Function {function.name} returned: {function_result}"
        else:
            return f"Function {function.name} returned: {str(function_result)}"

    def get_function_definition(self, function: AgentFunction) -> Dict[str, Any]:
        """
        Get function definition in OpenAI function calling format.

        Args:
            function: Agent function

        Returns:
            Function definition for LLM
        """
        return {
            "name": function.name,
            "description": function.description,
            "parameters": function.parameters,
        }

    async def get_agent_functions(
        self,
        agent_id: str,
        db: AsyncSession,
    ) -> List[AgentFunction]:
        """
        Get all active functions for an agent.

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            List of active agent functions
        """
        result = await db.execute(
            select(AgentFunction)
            .where(AgentFunction.agent_id == agent_id)
            .where(AgentFunction.is_active == True)
            .order_by(AgentFunction.execution_order)
        )

        functions = result.scalars().all()
        return functions


    # ── Global Tool support ───────────────────────────────────────────────────

    async def get_agent_assigned_tools(
        self,
        agent_id: str,
        db: AsyncSession,
    ) -> List[Tool]:
        """Fetch all active globally-assigned tools for an agent."""
        result = await db.execute(
            select(AgentToolAssignment)
            .where(AgentToolAssignment.agent_id == agent_id)
        )
        assignments = result.scalars().all()
        tools: List[Tool] = []
        for a in assignments:
            await db.refresh(a, ["tool"])
            if a.tool and a.tool.is_active:
                tools.append(a.tool)
        return tools

    def get_tool_function_definition(self, tool: Tool) -> Dict[str, Any]:
        """Return LLM function-calling definition for a global Tool."""
        cfg = tool.config or {}
        # Build a minimal JSON-schema parameter spec from the tool config
        parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}

        t = tool.tool_type
        if t == "transfer_call":
            parameters["properties"]["destination"] = {"type": "string", "description": "Phone number or SIP URI to transfer to"}
            parameters["required"].append("destination")
        elif t == "hang_up":
            parameters["properties"]["reason"] = {"type": "string", "description": "Reason for ending the call"}
        elif t == "send_sms":
            parameters["properties"]["message"] = {"type": "string", "description": "SMS message to send"}
            parameters["required"].append("message")
        elif t == "leave_voicemail":
            parameters["properties"]["message"] = {"type": "string", "description": "Voicemail message to leave"}
            parameters["required"].append("message")
        elif t == "dtmf":
            parameters["properties"]["digits"] = {"type": "string", "description": "DTMF digits to send"}
            parameters["required"].append("digits")
        elif t == "handoff":
            parameters["properties"]["reason"] = {"type": "string", "description": "Reason for handoff"}
        elif t == "query_knowledge_base":
            parameters["properties"]["query"] = {"type": "string", "description": "Search query for the knowledge base"}
            parameters["required"].append("query")
        elif t in ("api_request", "slack", "mcp", "google_sheets", "google_calendar",
                   "gohighlevel", "custom_tool"):
            parameters["properties"]["message"] = {"type": "string", "description": "Message or payload to send"}
            parameters["properties"]["data"] = {"type": "object", "description": "Additional data"}
        else:
            parameters["properties"]["input"] = {"type": "string", "description": "Input for this tool"}

        # If the tool has a custom parameters schema in config, use it
        if "parameters" in cfg and isinstance(cfg["parameters"], dict):
            parameters = cfg["parameters"]

        return {
            "name": tool.name.replace(" ", "_").lower()[:64],
            "description": tool.description or f"{tool.tool_type} tool",
            "parameters": parameters,
        }

    async def execute_global_tool(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
        call_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Execute a global Tool by its type and config."""
        start_time = time.time()
        cfg = tool.config or {}
        t = tool.tool_type

        try:
            if t == "api_request":
                url = cfg.get("url") or parameters.get("url")
                if not url:
                    raise ValueError("No URL configured for api_request tool")
                method = cfg.get("method", "POST").upper()
                headers = {**cfg.get("headers", {})}
                body = {**cfg.get("body", {}), **parameters}
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.request(method, url, headers=headers, json=body)
                    result = {"status_code": resp.status_code, "body": resp.text[:2000]}

            elif t == "slack":
                webhook_url = cfg.get("webhook_url")
                if not webhook_url:
                    raise ValueError("No webhook_url configured for Slack tool")
                msg = parameters.get("message") or cfg.get("default_message", "Voicecon agent notification")
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(webhook_url, json={"text": msg})
                    result = {"status_code": resp.status_code, "ok": resp.text == "ok"}

            elif t == "mcp":
                server_url = cfg.get("server_url")
                if not server_url:
                    raise ValueError("No server_url configured for MCP tool")
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(server_url, json={"tool": cfg.get("tool_name"), "params": parameters})
                    result = {"status_code": resp.status_code, "body": resp.text[:2000]}

            elif t == "custom_tool":
                url = cfg.get("url")
                if not url:
                    raise ValueError("No URL configured for custom_tool")
                method = cfg.get("method", "POST").upper()
                headers = {**cfg.get("headers", {})}
                if cfg.get("auth_type") == "bearer" and cfg.get("auth_token"):
                    headers["Authorization"] = f"Bearer {cfg['auth_token']}"
                elif cfg.get("auth_type") == "basic" and cfg.get("username") and cfg.get("password"):
                    import base64
                    creds = base64.b64encode(f"{cfg['username']}:{cfg['password']}".encode()).decode()
                    headers["Authorization"] = f"Basic {creds}"
                async with httpx.AsyncClient(timeout=cfg.get("timeout", 30)) as client:
                    resp = await client.request(method, url, headers=headers, json=parameters)
                    result = {"status_code": resp.status_code, "body": resp.text[:2000]}

            elif t in ("transfer_call", "hang_up", "leave_voicemail", "dtmf", "send_sms", "sip_request"):
                # Telephony actions — return structured action for the call handler to interpret
                result = {"action": t, "config": cfg, "parameters": parameters, "requires_telephony": True}

            elif t == "handoff":
                result = {"action": "handoff", "destination": cfg.get("destination"), "message": cfg.get("message")}

            elif t == "query_knowledge_base":
                result = {"action": "query_kb", "knowledge_base_id": cfg.get("knowledge_base_id"), "query": parameters.get("query")}

            elif t in ("google_sheets", "google_calendar", "gohighlevel"):
                result = {"note": f"{t} requires OAuth credentials — configure in Integrations", "config": cfg}

            else:
                result = {"executed": True, "tool_type": t, "parameters": parameters}

            execution_time = int((time.time() - start_time) * 1000)
            logger.info(f"Global tool {tool.name} ({t}) executed in {execution_time}ms")
            return {"success": True, "tool_name": tool.name, "result": result, "execution_time_ms": execution_time}

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Global tool {tool.name} ({t}) failed: {e}")
            return {"success": False, "tool_name": tool.name, "error": str(e), "execution_time_ms": execution_time}


# Global function executor instance
_function_executor: Optional[FunctionExecutor] = None


def get_function_executor() -> FunctionExecutor:
    """
    Get global function executor instance (singleton).

    Returns:
        FunctionExecutor instance
    """
    global _function_executor
    if _function_executor is None:
        _function_executor = FunctionExecutor()
    return _function_executor


# Import asyncio at the end to avoid circular imports
import asyncio
