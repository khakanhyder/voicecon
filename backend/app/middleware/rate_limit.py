"""
Rate Limiting Middleware for API Protection.

Prevents abuse, brute force attacks, and cost exhaustion.
"""
import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
import json

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm.

    Supports:
    - Per-IP rate limiting
    - Per-user rate limiting (for authenticated requests)
    - Per-endpoint rate limits
    - Distributed rate limiting via Redis
    """

    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        # In-memory fallback if Redis unavailable
        self.local_buckets: Dict[str, Dict] = defaultdict(dict)

    async def dispatch(self, request: Request, call_next):
        """
        Check rate limit before processing request.
        """
        # Get identifier (IP or user ID)
        identifier = await self._get_identifier(request)

        # Get rate limit for this endpoint
        limit, window = self._get_rate_limit(request)

        # Check rate limit
        allowed, reset_time = await self._check_rate_limit(
            identifier,
            limit,
            window,
            request.url.path
        )

        if not allowed:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RateLimitExceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": int(reset_time - time.time())
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time - time.time()))
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = await self._get_remaining(identifier, request.url.path, window)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        return response

    async def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.

        Priority:
        1. User ID (if authenticated)
        2. API key (if present)
        3. Client IP address
        """
        # Try to get user ID from token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                token = auth_header[7:]
                payload = decode_token(token)
                if payload:
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}"
            except Exception:
                pass

        # Fallback to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    def _get_rate_limit(self, request: Request) -> tuple[int, int]:
        """
        Get rate limit for the endpoint.

        Returns:
            (requests_per_window, window_in_seconds)
        """
        path = request.url.path
        method = request.method

        # Authentication endpoints - very strict
        if "/auth/login" in path or "/auth/register" in path:
            return (5, 60)  # 5 requests per minute

        # Password reset - strict
        if "/auth/forgot-password" in path or "/auth/reset-password" in path:
            return (3, 300)  # 3 requests per 5 minutes

        # Expensive operations - strict
        if method == "POST" and any(x in path for x in ["/calls", "/agents"]):
            return (10, 60)  # 10 per minute

        # Voice/LLM operations - very strict (cost control)
        if "/voice/" in path or "/llm/" in path:
            return (5, 60)  # 5 per minute

        # Write operations - moderate
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            return (30, 60)  # 30 per minute

        # Read operations - lenient
        return (60, 60)  # 60 per minute

    async def _check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
        path: str
    ) -> tuple[bool, float]:
        """
        Check if request is within rate limit.

        Returns:
            (allowed: bool, reset_time: float)
        """
        bucket_key = f"ratelimit:{identifier}:{path}"
        current_time = time.time()
        reset_time = current_time + window

        if self.redis_client:
            try:
                return await self._check_redis_rate_limit(
                    bucket_key, limit, window, current_time
                )
            except Exception:
                # Fallback to local if Redis fails
                pass

        # Local rate limiting (in-memory)
        return await self._check_local_rate_limit(
            bucket_key, limit, window, current_time
        )

    async def _check_redis_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: float
    ) -> tuple[bool, float]:
        """
        Check rate limit using Redis (distributed).
        """
        # Use sorted set to store timestamps
        pipeline = self.redis_client.pipeline()

        # Remove old entries
        pipeline.zremrangebyscore(key, 0, current_time - window)

        # Count requests in window
        pipeline.zcard(key)

        # Add current request
        pipeline.zadd(key, {str(current_time): current_time})

        # Set expiration
        pipeline.expire(key, window + 10)

        results = await pipeline.execute()
        count = results[1]

        reset_time = current_time + window
        allowed = count < limit

        return (allowed, reset_time)

    async def _check_local_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: float
    ) -> tuple[bool, float]:
        """
        Check rate limit using local memory.
        """
        if key not in self.local_buckets:
            self.local_buckets[key] = {
                "requests": [],
                "reset_time": current_time + window
            }

        bucket = self.local_buckets[key]

        # Remove old requests
        bucket["requests"] = [
            ts for ts in bucket["requests"]
            if ts > current_time - window
        ]

        # Check if within limit
        if len(bucket["requests"]) >= limit:
            return (False, bucket["reset_time"])

        # Add current request
        bucket["requests"].append(current_time)

        # Update reset time
        if current_time >= bucket["reset_time"]:
            bucket["reset_time"] = current_time + window

        return (True, bucket["reset_time"])

    async def _get_remaining(
        self,
        identifier: str,
        path: str,
        window: int
    ) -> int:
        """
        Get remaining requests in current window.
        """
        bucket_key = f"ratelimit:{identifier}:{path}"
        current_time = time.time()

        if self.redis_client:
            try:
                count = await self.redis_client.zcount(
                    bucket_key,
                    current_time - window,
                    current_time
                )
                limit, _ = self._get_rate_limit_by_path(path)
                return limit - count
            except Exception:
                pass

        # Local fallback
        if bucket_key in self.local_buckets:
            bucket = self.local_buckets[bucket_key]
            bucket["requests"] = [
                ts for ts in bucket["requests"]
                if ts > current_time - window
            ]
            limit, _ = self._get_rate_limit_by_path(path)
            return limit - len(bucket["requests"])

        return 0

    def _get_rate_limit_by_path(self, path: str) -> tuple[int, int]:
        """Helper to get rate limit by path only."""
        # Simplified version for remaining count
        if "/auth/" in path:
            return (5, 60)
        if "/calls" in path or "/agents" in path:
            return (10, 60)
        return (60, 60)


def init_rate_limit_middleware(app, redis_url: Optional[str] = None):
    """
    Initialize rate limiting middleware.

    Args:
        app: FastAPI application
        redis_url: Redis connection URL (optional)
    """
    redis_client = None

    if redis_url:
        try:
            redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            print(f"Failed to connect to Redis for rate limiting: {e}")
            print("Falling back to in-memory rate limiting")

    app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
