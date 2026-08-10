"""
Rate limiting middleware for API protection.

Prevents abuse, scraping and cost exhaustion.

This module was written but never installed — nothing called `setup_rate_limiting`,
so the API ran with no throttling of any kind. Wiring it up surfaced four things
that had to be fixed first, all noted at their sites below:

- raising `HTTPException` from a middleware does not reach FastAPI's handlers,
  so a throttled request answered **500**, not 429;
- the password-reset rules matched `/auth/forgot-password`, but the routes are
  `/auth/password/forgot` and `/auth/password/reset`, so they never fired;
- two separate limit tables disagreed, so `X-RateLimit-Remaining` reported
  against a different limit than the one being enforced;
- the in-memory bucket dict was never pruned, so it grew once per unique
  caller-and-path forever.

Brute-force protection for a *single account* is deliberately not here: this
layer keys unauthenticated traffic by IP, and an office or CI runner shares one.
See `app/api/v1/endpoints/auth.py` for the per-address login throttle.
"""
import re
import time
from typing import Dict, Optional
from collections import defaultdict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from app.core.config import settings


#: Paths that must answer even when a caller is being throttled — health checks
#: are how the platform decides whether to keep the container, and throttling
#: them turns a burst of traffic into a restart loop.
_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
)

#: Endpoints called by *machines*, not people.
#:
#: These are unauthenticated, so the limiter can only key them by IP — and the
#: IP is the provider's egress, shared by every customer on the platform. Twilio
#: POSTs the voice and status callbacks on every single call, so a write ceiling
#: of 60/min is not a safety net here: it is a cap on concurrent calls, and
#: exceeding it drops live ones. Stripe retries a 429'd webhook but treats the
#: endpoint as failing; a workflow's inbound webhook simply loses the event.
#:
#: These paths carry their own authentication — Twilio and Stripe signature
#: validation, and an unguessable key in the URL for the others — so throttling
#: by IP adds nothing they do not already have.
_MACHINE_CALLER_PREFIXES = (
    "/api/v1/telephony/twilio/",
    "/api/v1/telephony/telnyx/",
    "/api/v1/billing/webhooks/",
    "/api/v1/workflows/webhook/",
)

#: Stop tracking a bucket this long after its last request, so an endpoint that
#: is hit once by a million addresses does not retain a million entries.
_BUCKET_TTL_SECONDS = 3600
_PRUNE_EVERY_SECONDS = 300

#: How long to stop calling Redis after it fails. Without this, a Redis that is
#: down (or simply misconfigured — REDIS_URL pointing at a port nothing is
#: listening on is easy to miss) costs every single request a failed connection
#: before the local fallback runs.
_REDIS_COOLDOWN_SECONDS = 60

#: Path segments that are identifiers rather than route structure. Buckets are
#: keyed by route *shape*: keying by the resolved URL gave `/agents/{id}` a
#: fresh allowance per id, so walking ids — the one pattern a scraping limit
#: exists to catch — was effectively unlimited.
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_LONG_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,}$")


def _bucket_path(path: str) -> str:
    """Collapse identifier segments so one route shares one bucket."""
    parts = []
    for segment in path.split("/"):
        if segment.isdigit() or _UUID_RE.match(segment) or _LONG_TOKEN_RE.match(segment):
            parts.append("{id}")
        else:
            parts.append(segment)
    return "/".join(parts)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiting.

    Keyed per user when the request carries a bearer token, per IP otherwise,
    and always per endpoint. Uses Redis when one is configured so the limit
    holds across replicas, and falls back to process-local memory when it is
    not — which is per-replica, and is documented as such rather than pretended
    otherwise.
    """

    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        # In-memory fallback if Redis unavailable
        self.local_buckets: Dict[str, Dict] = defaultdict(dict)
        self._last_prune = time.time()
        #: Timestamp until which Redis is considered down and skipped.
        self._redis_blocked_until = 0.0

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        if any(path.startswith(p) for p in _MACHINE_CALLER_PREFIXES):
            return await call_next(request)

        identifier = await self._get_identifier(request)
        limit, window = self._get_rate_limit(request.url.path, request.method)

        allowed, reset_time = await self._check_rate_limit(
            identifier, limit, window, _bucket_path(path)
        )

        if not allowed:
            retry_after = max(1, int(reset_time - time.time()))
            # Returned, not raised. `HTTPException` raised inside a middleware
            # propagates past FastAPI's exception handlers — they are mounted
            # *inside* the middleware stack — and surfaces as a 500, which is
            # exactly the wrong signal to a client that should back off.
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RateLimitExceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(retry_after),
                },
            )

        response = await call_next(request)

        remaining = await self._get_remaining(identifier, _bucket_path(path), limit, window)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        return response

    async def _get_identifier(self, request: Request) -> str:
        """
        Identify the caller: user id when authenticated, else client IP.

        Keying by user matters — several people behind one office NAT must not
        consume each other's allowance.
        """
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_token

                payload = decode_token(auth_header[7:])
                if payload:
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}"
            except Exception:
                # An unreadable token is not authenticated; fall through to IP
                # so a malformed header cannot buy an unlimited allowance.
                pass

        return f"ip:{self._client_ip(request)}"

    @staticmethod
    def _client_ip(request: Request) -> str:
        """
        The caller's address.

        Deliberately *not* parsed from `X-Forwarded-For` here. Uvicorn runs its
        own proxy-headers middleware ahead of the application and has already
        rewritten `request.client` from that header by the time this runs —
        verified directly: a request to this server carrying
        `X-Forwarded-For: 3.3.3.1` arrives with `request.client.host` equal to
        `3.3.3.1`. Re-reading the header here would be a second, competing
        implementation of a decision that has already been made upstream.

        Which means the trust boundary is **not** in this file. Uvicorn honours
        the header only from peers in `--forwarded-allow-ips`, which defaults to
        `127.0.0.1`. That is right when a reverse proxy sits on the same host,
        and wrong the moment the app is reachable directly — then any client can
        name its own address, land in a fresh bucket per request and walk past
        every IP-keyed limit here. A deployment that exposes this app without a
        proxy in front must pass `--forwarded-allow-ips=""` (or run with
        `proxy_headers=False`); no setting in this module can substitute for it,
        because the rewrite happens before the application is reached.
        """
        return request.client.host if request.client else "unknown"

    def _get_rate_limit(self, path: str, method: str) -> tuple[int, int]:
        """
        The single source of truth for limits: `(requests, window_seconds)`.

        Both enforcement and the `X-RateLimit-*` headers read this. They used to
        consult two different tables that disagreed, so the headers advertised a
        budget the enforcement never honoured.
        """
        # Every anonymous auth route. Note the bucket key includes the path, so
        # this is a budget *per endpoint*, not one shared across sign-in,
        # sign-up and the code endpoints.
        #
        # Deliberately a coarse ceiling rather than a tight one. Anonymous
        # traffic is keyed by IP, and the addresses that share an IP are an
        # office, a university, a mobile carrier's NAT or a CI runner — so a
        # tight per-IP rule mostly punishes bystanders while an attacker just
        # rotates addresses. The rules that actually bite are per-account:
        # 5 sends per address per hour for the one-time codes
        # (services/auth/verification.py) and the failed-login lockout in
        # endpoints/auth.py.
        if "/auth/" in path:
            return (settings.RATE_LIMIT_AUTH_PER_MINUTE, 60)

        # Voice and LLM work costs real money per call.
        if "/voice/" in path or "/llm/" in path:
            return (5, 60)

        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return (settings.RATE_LIMIT_WRITE_PER_MINUTE, 60)

        return (settings.RATE_LIMIT_READ_PER_MINUTE, 60)

    async def _check_rate_limit(
        self, identifier: str, limit: int, window: int, path: str
    ) -> tuple[bool, float]:
        """Record this request and report whether it was within the limit."""
        bucket_key = f"ratelimit:{identifier}:{path}"
        current_time = time.time()

        if self._redis_available(current_time):
            try:
                return await self._check_redis_rate_limit(
                    bucket_key, limit, window, current_time
                )
            except Exception:
                # Redis being down must not take the API down with it; degrade
                # to per-process limiting rather than refusing traffic.
                self._redis_blocked_until = current_time + _REDIS_COOLDOWN_SECONDS

        return self._check_local_rate_limit(bucket_key, limit, window, current_time)

    def _redis_available(self, now: float) -> bool:
        return self.redis_client is not None and now >= self._redis_blocked_until

    async def _check_redis_rate_limit(
        self, key: str, limit: int, window: int, current_time: float
    ) -> tuple[bool, float]:
        """
        Sliding window over a sorted set, shared across replicas.

        The count is read first and the timestamp recorded only if the request
        is allowed. Adding unconditionally — as this did — meant a client that
        kept retrying while blocked pushed its own window forward on every
        attempt and stayed locked out indefinitely, while `Retry-After` kept
        promising a minute. It also disagreed with the in-memory branch, so the
        limiter behaved differently depending on whether Redis happened to be
        reachable.
        """
        pipeline = self.redis_client.pipeline()
        pipeline.zremrangebyscore(key, 0, current_time - window)
        pipeline.zcard(key)
        pipeline.zrange(key, 0, 0, withscores=True)
        results = await pipeline.execute()
        count = results[1]
        oldest = results[2]

        if count >= limit:
            # Reset when the oldest request in the window ages out, matching
            # the local branch rather than always claiming a full window.
            oldest_ts = oldest[0][1] if oldest else current_time
            return (False, oldest_ts + window)

        add = self.redis_client.pipeline()
        add.zadd(key, {str(current_time): current_time})
        add.expire(key, window + 10)
        await add.execute()

        return (True, current_time + window)

    def _check_local_rate_limit(
        self, key: str, limit: int, window: int, current_time: float
    ) -> tuple[bool, float]:
        """Process-local sliding window, used when no Redis is configured."""
        self._prune(current_time)

        bucket = self.local_buckets.setdefault(key, {"requests": []})
        bucket["requests"] = [ts for ts in bucket["requests"] if ts > current_time - window]
        bucket["seen"] = current_time

        if len(bucket["requests"]) >= limit:
            # Reset when the oldest request in the window ages out.
            return (False, bucket["requests"][0] + window)

        bucket["requests"].append(current_time)
        return (True, current_time + window)

    def _prune(self, current_time: float) -> None:
        """
        Drop buckets nothing has touched for an hour.

        Without this the dict gained an entry per unique caller-and-path and
        never gave one back — a slow leak that only showed up under real
        traffic, which is the worst time to find it.
        """
        if current_time - self._last_prune < _PRUNE_EVERY_SECONDS:
            return
        self._last_prune = current_time
        stale = [
            key
            for key, bucket in self.local_buckets.items()
            if current_time - bucket.get("seen", 0) > _BUCKET_TTL_SECONDS
        ]
        for key in stale:
            del self.local_buckets[key]

    async def _get_remaining(
        self, identifier: str, path: str, limit: int, window: int
    ) -> int:
        """Requests left in the current window, for the response headers."""
        bucket_key = f"ratelimit:{identifier}:{path}"
        current_time = time.time()

        if self._redis_available(current_time):
            try:
                count = await self.redis_client.zcount(
                    bucket_key, current_time - window, current_time
                )
                return limit - count
            except Exception:
                self._redis_blocked_until = current_time + _REDIS_COOLDOWN_SECONDS

        bucket = self.local_buckets.get(bucket_key)
        if bucket is None:
            return limit
        fresh = [ts for ts in bucket["requests"] if ts > current_time - window]
        return limit - len(fresh)


def init_rate_limit_middleware(app, redis_url: Optional[str] = None):
    """
    Install the middleware.

    `redis_url` is optional: without it the limiter still works, but per replica
    rather than across the fleet.
    """
    redis_client = None

    if redis_url:
        try:
            redis_client = redis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
        except Exception as e:
            print(f"Failed to connect to Redis for rate limiting: {e}")
            print("Falling back to in-memory rate limiting")

    app.add_middleware(RateLimitMiddleware, redis_client=redis_client)


#: Historical alias — the name the module has always exported.
setup_rate_limiting = init_rate_limit_middleware
