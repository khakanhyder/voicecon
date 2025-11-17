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
