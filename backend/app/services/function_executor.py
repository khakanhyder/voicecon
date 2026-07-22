"""
Function Executor Service.

Handles agent function execution via webhooks with proper
timeout, retry, and error handling.
"""
import logging
import re
import json
import time
import uuid
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

# OpenAI requires tool function names to match ^[a-zA-Z0-9_-]+$. Anything else
# (spaces, brackets, punctuation) gets a 400 that fails the whole turn.
_INVALID_FN_CHARS = re.compile(r"[^a-zA-Z0-9_-]+")


def _as_uuid_arg(value):
    """Coerce an id to UUID, leaving unparseable input as-is.

    Ids arrive as strings while the columns are UUID typed. asyncpg coerces
    them; SQLite (used in tests) does not, so do it here for robustness.
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return value


def sanitize_function_name(name: str) -> str:
    """
    Turn a human tool name into a valid OpenAI function name.

    Lowercases, replaces every run of disallowed characters with a single
    underscore, trims stray underscores, and caps the length. A name like
    "[demo] Get weather" becomes "demo_get_weather".

    Args:
        name: The tool's display name

    Returns:
        A name matching ^[a-zA-Z0-9_-]+$, never empty
    """
    cleaned = _INVALID_FN_CHARS.sub("_", (name or "").lower()).strip("_")
    return (cleaned or "tool")[:64]


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
            .where(AgentFunction.agent_id == _as_uuid_arg(agent_id))
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
            .where(AgentToolAssignment.agent_id == _as_uuid_arg(agent_id))
        )
        assignments = result.scalars().all()
        tools: List[Tool] = []
        for a in assignments:
            await db.refresh(a, ["tool"])
            if a.tool and a.tool.is_active:
                tools.append(a.tool)
        return tools

    async def _execute_workflow_tool(
        self,
        cfg: Dict[str, Any],
        parameters: Dict[str, Any],
        db: Optional[AsyncSession],
        channel: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Run a workflow as a tool and return its outcome to the conversation.

        The parameters the LLM extracted become the workflow's trigger data, so
        a caller saying "book me in for Tuesday at 3" ends up as
        ``{"date": "Tuesday", "time": "15:00"}`` in ``{{trigger.*}}``.

        Runs synchronously: the agent needs the result before it can reply.

        Args:
            cfg: Tool config, carrying ``workflow_id``
            parameters: Parameters extracted by the LLM
            db: Database session
            channel: Live voice channel, passed through so speak/ask steps
                inside the workflow talk to the caller directly

        Returns:
            A summary of the run, including its output
        """
        from app.models.integration import Workflow
        from app.services.workflows.graph import input_schema, load_graph
        from app.services.workflows.workflow_engine import get_workflow_engine

        workflow_id = cfg.get("workflow_id")
        if not workflow_id:
            return {"error": "This tool is not linked to a workflow."}
        if db is None:
            return {"error": "No database session available to run the workflow."}

        # Validate the LLM's parameters against the workflow's declared inputs
        # BEFORE running. A model can omit or mistype a required field; without
        # this the workflow would run with missing trigger data. A validation
        # failure is returned as a tool error so the agent asks the caller for
        # the missing detail rather than producing a wrong result.
        try:
            workflow = await db.get(Workflow, uuid.UUID(str(workflow_id)))
        except (ValueError, AttributeError, TypeError):
            workflow = None

        if not workflow:
            return {"error": "The linked workflow no longer exists."}

        schema = input_schema(load_graph(workflow.workflow_steps))
        missing = [
            field
            for field in schema.get("required", [])
            if not str((parameters or {}).get(field, "")).strip()
        ]
        if missing:
            return {
                "error": "missing_parameters",
                "missing": missing,
                "message": (
                    "Ask the caller for: " + ", ".join(missing) + ", then try again."
                ),
            }

        engine = get_workflow_engine(db)

        try:
            execution = await engine.execute_workflow(
                workflow_id=str(workflow_id),
                trigger_data=parameters or {},
                wait_for_completion=True,
                channel=channel,
            )
        except Exception as e:
            # An inactive or deleted workflow raises. Report it as a tool
            # failure so the agent can apologise rather than dropping the turn.
            logger.error(f"Workflow tool failed to start: {e}", exc_info=True)
            return {"error": f"The workflow could not be started: {e}"}

        await db.refresh(execution)

        result_data = execution.result_data or {}
        steps = result_data.get("steps") or []

        # Surface the last successful step's output as "the answer", which is
        # what the agent will paraphrase back to the caller.
        output = None
        for step in reversed(steps):
            if step.get("status") == "success" and step.get("result") is not None:
                output = step["result"]
                break

        # Variables published by ask/ai/transform steps, minus the internal
        # namespaces, so the agent sees plain names it can talk about.
        context = result_data.get("final_context") or {}
        variables = {
            key: value
            for key, value in context.items()
            if key not in ("steps", "trigger")
        }

        succeeded = execution.status == "completed"

        return {
            "success": succeeded,
            "status": execution.status,
            "output": output,
            "variables": variables,
            "error": execution.error_message if not succeeded else None,
        }

    async def build_tool_definitions(
        self,
        tools: List[Tool],
        db: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build LLM function definitions for a set of tools.

        Workflow-backed tools need a database read to derive their parameter
        schema from the workflow's declared inputs, which the synchronous
        builder cannot do — so they are resolved here first.

        Args:
            tools: Tools assigned to the agent
            db: Database session

        Returns:
            One function-calling definition per tool
        """
        definitions = []

        for tool in tools:
            schema = None
            if tool.tool_type == "workflow" and db is not None:
                schema = await self._workflow_input_schema(tool, db)
            definitions.append(self.get_tool_function_definition(tool, schema))

        return definitions

    async def _workflow_input_schema(
        self,
        tool: Tool,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Derive a tool parameter schema from the workflow's declared inputs.

        Args:
            tool: A tool whose config names a workflow
            db: Database session

        Returns:
            JSON Schema, or None when the workflow cannot be loaded
        """
        from app.models.integration import Workflow
        from app.services.workflows.graph import input_schema, load_graph

        workflow_id = (tool.config or {}).get("workflow_id")
        if not workflow_id:
            return None

        try:
            workflow = await db.get(Workflow, uuid.UUID(str(workflow_id)))
        except (ValueError, AttributeError, TypeError):
            return None

        if not workflow:
            logger.warning(f"Tool {tool.name} references missing workflow {workflow_id}")
            return None

        return input_schema(load_graph(workflow.workflow_steps))

    def get_tool_function_definition(
        self,
        tool: Tool,
        workflow_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Return LLM function-calling definition for a global Tool.

        Args:
            tool: The tool
            workflow_schema: Pre-resolved schema for workflow-backed tools,
                since deriving it requires an async database read

        Returns:
            A function-calling definition
        """
        from app.services.integrations.action_registry import get_action_schema

        cfg = tool.config or {}
        parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}

        t = tool.tool_type

        if t == "workflow":
            # Inputs declared on the workflow's trigger node become the tool's
            # parameters, so the LLM knows what to extract from the caller.
            parameters = workflow_schema or parameters

        # Integration tool: use action registry schema
        elif t in ("integration", "connected_integration"):
            connector_slug = cfg.get("connector_slug", "")
            action = cfg.get("action", "")
            action_def = get_action_schema(connector_slug, action)
            if action_def:
                parameters = action_def.get("parameters", parameters)
        elif t == "transfer_call":
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
        elif t in ("api_request", "slack", "mcp", "custom_tool"):
            parameters["properties"]["message"] = {"type": "string", "description": "Message or payload to send"}
            parameters["properties"]["data"] = {"type": "object", "description": "Additional data"}
        else:
            parameters["properties"]["input"] = {"type": "string", "description": "Input for this tool"}

        # Override with explicit parameters schema in config if present
        if "parameters" in cfg and isinstance(cfg["parameters"], dict):
            parameters = cfg["parameters"]

        return {
            "name": sanitize_function_name(tool.name),
            "description": tool.description or f"{tool.tool_type} tool",
            "parameters": parameters,
        }

    async def execute_global_tool(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
        call_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        channel: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a global Tool by its type and config.

        Args:
            tool: Tool to execute
            parameters: Parameters the LLM extracted
            call_id: Live call id, when invoked mid-conversation
            db: Database session
            channel: Live voice channel, so a workflow-backed tool's speak/ask
                steps can reach the caller instead of being simulated
        """
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
                from app.services.knowledge_base.rag_service import search_knowledge_base_db
                from app.core.config import settings as _settings
                kb_id = cfg.get("knowledge_base_id") or cfg.get("kb_id")
                query = parameters.get("query") or parameters.get("q") or ""
                if not kb_id:
                    result = {"error": "No knowledge base is configured for this tool."}
                elif db is None:
                    result = {"error": "Knowledge base search is unavailable in this context."}
                elif not query:
                    result = {"error": "No search query was provided."}
                else:
                    try:
                        hits = await search_knowledge_base_db(
                            db=db,
                            knowledge_base_id=kb_id,
                            query=query,
                            api_key=_settings.OPENAI_API_KEY,
                            top_k=cfg.get("top_k", 4),
                        )
                        if hits:
                            result = {
                                "query": query,
                                "results": [
                                    {"content": h["content"], "source": h["document_title"], "score": h["score"]}
                                    for h in hits
                                ],
                            }
                        else:
                            result = {"query": query, "results": [],
                                      "note": "No relevant information found in the knowledge base."}
                    except Exception as e:
                        logger.error(f"Knowledge base search failed: {e}", exc_info=True)
                        result = {"error": f"Knowledge base search failed: {e}"}

            elif t in ("integration", "connected_integration"):
                result = await self._execute_integration_tool(cfg, parameters, db)

            elif t == "workflow":
                result = await self._execute_workflow_tool(
                    cfg, parameters, db, channel=channel
                )

            else:
                result = {"executed": True, "tool_type": t, "parameters": parameters}

            execution_time = int((time.time() - start_time) * 1000)
            logger.info(f"Global tool {tool.name} ({t}) executed in {execution_time}ms")
            return {"success": True, "tool_name": tool.name, "result": result, "execution_time_ms": execution_time}

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Global tool {tool.name} ({t}) failed: {e}")
            return {"success": False, "tool_name": tool.name, "error": str(e), "execution_time_ms": execution_time}


    async def _execute_integration_tool(
        self,
        cfg: Dict[str, Any],
        parameters: Dict[str, Any],
        db: Optional[AsyncSession],
    ) -> Dict[str, Any]:
        """
        Execute a connected integration tool by loading the user's
        OAuth/API-key connection and calling the specified action.

        cfg must contain:
          - connection_id: UUID of the IntegrationConnection row
          - connector_slug: e.g. "hubspot", "google_calendar"
          - action: method name on the connector, e.g. "create_contact"
        """
        if db is None:
            raise ValueError("Database session required for integration tools")

        from app.models.integration import IntegrationConnection, IntegrationConnector
        from app.services.integrations import connectors as connector_module
        from app.services.integrations.action_registry import CONNECTOR_CLASS_MAP

        connection_id = cfg.get("connection_id")
        connector_slug = cfg.get("connector_slug")
        action = cfg.get("action")

        if not connection_id:
            raise ValueError("integration tool missing connection_id in config")
        if not action:
            raise ValueError("integration tool missing action in config")

        # Load the user's connection (has encrypted credentials)
        conn_result = await db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.id == connection_id
            )
        )
        connection = conn_result.scalar_one_or_none()
        if not connection:
            raise ValueError(f"IntegrationConnection {connection_id} not found")

        # Load the connector definition
        connector_result = await db.execute(
            select(IntegrationConnector).where(
                IntegrationConnector.id == connection.connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()
        if not connector:
            raise ValueError(f"IntegrationConnector not found for connection {connection_id}")

        slug = connector_slug or connector.slug
        class_name = CONNECTOR_CLASS_MAP.get(slug)
        if not class_name:
            raise ValueError(f"No connector class for slug '{slug}'")

        # Instantiate the connector (handles auth, rate limiting, etc.)
        connector_class = getattr(connector_module, class_name)
        instance = connector_class(connection=connection, connector=connector, db=db)

        # Call the action method dynamically
        if not hasattr(instance, action):
            raise ValueError(f"Action '{action}' not found on {class_name}")

        method = getattr(instance, action)
        result = await method(**parameters)
        return result if isinstance(result, dict) else {"result": result}


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
