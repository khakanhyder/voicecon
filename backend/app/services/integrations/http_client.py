"""
HTTP Client for Integrations.

Handles HTTP requests with rate limiting, retries, and error handling.
"""
import logging
import time
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
import httpx

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class HTTPRequestError(Exception):
    """Raised when HTTP request fails."""
    pass


class RateLimiter:
    """
    Token bucket rate limiter.

    Implements token bucket algorithm for rate limiting.
    """

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            requests_per_day: Max requests per day
        """
        self.limits = {}

        if requests_per_minute:
            self.limits["minute"] = {
                "max": requests_per_minute,
                "window": 60,
                "requests": [],
            }

        if requests_per_hour:
            self.limits["hour"] = {
                "max": requests_per_hour,
                "window": 3600,
                "requests": [],
            }

        if requests_per_day:
            self.limits["day"] = {
                "max": requests_per_day,
                "window": 86400,
                "requests": [],
            }

        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Blocks if rate limit is exceeded.

        Raises:
            RateLimitExceeded: If rate limit exceeded and cannot wait
        """
        async with self._lock:
            now = time.time()

            # Check each limit window
            for window_name, limit_info in self.limits.items():
                max_requests = limit_info["max"]
                window_seconds = limit_info["window"]
                requests = limit_info["requests"]

                # Remove old requests outside window
                cutoff = now - window_seconds
                limit_info["requests"] = [
                    req_time for req_time in requests if req_time > cutoff
                ]

                # Check if limit exceeded
                if len(limit_info["requests"]) >= max_requests:
                    # Calculate wait time
                    oldest_request = min(limit_info["requests"])
                    wait_time = (oldest_request + window_seconds) - now

                    if wait_time > 0:
                        logger.warning(
                            f"Rate limit exceeded for {window_name}. "
                            f"Waiting {wait_time:.2f} seconds"
                        )
                        await asyncio.sleep(wait_time)

                        # Retry after waiting
                        return await self.acquire()

            # Add current request to all windows
            for limit_info in self.limits.values():
                limit_info["requests"].append(now)

    def get_remaining(self) -> Dict[str, int]:
        """
        Get remaining requests for each window.

        Returns:
            Dictionary with remaining requests per window
        """
        now = time.time()
        remaining = {}

        for window_name, limit_info in self.limits.items():
            max_requests = limit_info["max"]
            window_seconds = limit_info["window"]
            requests = limit_info["requests"]

            # Count requests in current window
            cutoff = now - window_seconds
            current_requests = len([r for r in requests if r > cutoff])

            remaining[window_name] = max(0, max_requests - current_requests)

        return remaining


class RetryConfig:
    """Retry configuration."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retry_on_status_codes: List[int] = None,
    ):
        """
        Initialize retry config.

        Args:
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            retry_on_status_codes: Status codes to retry on
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

        # Default retry on server errors and rate limit
        self.retry_on_status_codes = retry_on_status_codes or [
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]


class IntegrationHTTPClient:
    """
    HTTP client for integration API calls.

    Features:
    - Rate limiting
    - Automatic retries with exponential backoff
    - Request/response logging
    - Error handling
    - Connection pooling
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for API
            rate_limiter: Rate limiter instance
            retry_config: Retry configuration
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=30.0,
                ),
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from endpoint.

        Args:
            endpoint: API endpoint

        Returns:
            Full URL
        """
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint

        if not self.base_url:
            raise ValueError("base_url must be set or endpoint must be full URL")

        return f"{self.base_url}/{endpoint.lstrip('/')}"

    async def _wait_with_backoff(self, attempt: int) -> None:
        """
        Wait with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
        """
        delay = min(
            self.retry_config.initial_delay
            * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay,
        )

        logger.info(f"Waiting {delay:.2f}s before retry (attempt {attempt + 1})")
        await asyncio.sleep(delay)

    async def request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        log_request: bool = True,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and retries.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            headers: Request headers
            params: Query parameters
            json: JSON body
            data: Form data
            log_request: Whether to log request

        Returns:
            Response data

        Raises:
            HTTPRequestError: If request fails after retries
            RateLimitExceeded: If rate limit exceeded
        """
        url = self._build_url(endpoint)
        method = method.upper()

        # Prepare headers
        request_headers = headers or {}
        if "User-Agent" not in request_headers:
            request_headers["User-Agent"] = "Voicecon-Integration/1.0"

        attempt = 0
        last_error = None

        while attempt <= self.retry_config.max_retries:
            try:
                # Apply rate limiting
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                # Get client
                client = await self._get_client()

                # Log request
                if log_request:
                    logger.info(
                        f"{method} {url} (attempt {attempt + 1}/{self.retry_config.max_retries + 1})"
                    )

                # Make request
                start_time = time.time()

                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    data=data,
                )

                duration_ms = int((time.time() - start_time) * 1000)

                # Log response
                if log_request:
                    logger.info(
                        f"{method} {url} -> {response.status_code} ({duration_ms}ms)"
                    )

                # Check if should retry based on status code
                if response.status_code in self.retry_config.retry_on_status_codes:
                    if attempt < self.retry_config.max_retries:
                        logger.warning(
                            f"Got status {response.status_code}, will retry"
                        )
                        await self._wait_with_backoff(attempt)
                        attempt += 1
                        continue
                    else:
                        # No more retries
                        response.raise_for_status()

                # Raise for other error status codes
                response.raise_for_status()

                # Parse response
                try:
                    return response.json()
                except Exception:
                    # If not JSON, return text
                    return {"response": response.text, "status_code": response.status_code}

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Request timeout (attempt {attempt + 1}): {e}")

                if attempt < self.retry_config.max_retries:
                    await self._wait_with_backoff(attempt)
                    attempt += 1
                else:
                    raise HTTPRequestError(f"Request timed out after {attempt + 1} attempts")

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(f"HTTP error {e.response.status_code}: {e}", exc_info=True)

                # Don't retry on client errors (4xx except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise HTTPRequestError(
                        f"HTTP {e.response.status_code}: {e.response.text}"
                    )

                if attempt < self.retry_config.max_retries:
                    await self._wait_with_backoff(attempt)
                    attempt += 1
                else:
                    raise HTTPRequestError(
                        f"HTTP {e.response.status_code} after {attempt + 1} attempts"
                    )

            except httpx.HTTPError as e:
                last_error = e
                logger.error(f"HTTP error (attempt {attempt + 1}): {e}", exc_info=True)

                if attempt < self.retry_config.max_retries:
                    await self._wait_with_backoff(attempt)
                    attempt += 1
                else:
                    raise HTTPRequestError(f"Request failed after {attempt + 1} attempts: {str(e)}")

        # Should not reach here, but just in case
        raise HTTPRequestError(f"Request failed: {str(last_error)}")

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return await self.request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make PUT request."""
        return await self.request("PUT", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make PATCH request."""
        return await self.request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)
