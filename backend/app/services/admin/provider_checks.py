"""
"Test connection" for the platform credentials managed in the admin dashboard.

Each check makes the cheapest authenticated read the provider offers, using the
values currently in effect on ``settings`` (database override or environment),
and reports one of:

* ``ok``           — the credential authenticated.
* ``invalid``      — the provider rejected it (401/403).
* ``not_configured`` — a required value is missing.
* ``error``        — anything else (network, 5xx, unexpected response). The
  credential may be fine; the check could not tell.

Nothing here returns or logs a secret.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
import time
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0


@dataclass
class CheckResult:
    status: str
    message: str
    latency_ms: Optional[int] = None

    def as_dict(self) -> dict:
        return asdict(self)


def _missing(*names: str) -> CheckResult:
    return CheckResult("not_configured", f"Missing: {', '.join(names)}")


async def _http_check(
    method: str,
    url: str,
    *,
    ok_message: str,
    headers: Optional[dict] = None,
    auth: Optional[tuple] = None,
) -> CheckResult:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.request(method, url, headers=headers, auth=auth)
    except httpx.HTTPError as exc:
        return CheckResult("error", f"Could not reach the provider: {type(exc).__name__}")
    latency = int((time.monotonic() - started) * 1000)

    if response.status_code < 300:
        return CheckResult("ok", ok_message, latency)
    if response.status_code in (401, 403):
        return CheckResult("invalid", f"Rejected by the provider (HTTP {response.status_code}).", latency)
    return CheckResult("error", f"Unexpected response (HTTP {response.status_code}).", latency)


async def check_openai() -> CheckResult:
    key = settings.OPENAI_API_KEY
    if not key:
        return _missing("OPENAI_API_KEY")
    base = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {key}"}
    if settings.OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = settings.OPENAI_ORG_ID
    return await _http_check("GET", f"{base}/models", headers=headers, ok_message="Key accepted; models listed.")


async def check_anthropic() -> CheckResult:
    key = settings.ANTHROPIC_API_KEY
    if not key:
        return _missing("ANTHROPIC_API_KEY")
    return await _http_check(
        "GET",
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        ok_message="Key accepted; models listed.",
    )


async def check_deepgram() -> CheckResult:
    key = settings.DEEPGRAM_API_KEY
    if not key:
        return _missing("DEEPGRAM_API_KEY")
    return await _http_check(
        "GET",
        "https://api.deepgram.com/v1/projects",
        headers={"Authorization": f"Token {key}"},
        ok_message="Key accepted.",
    )


async def check_elevenlabs() -> CheckResult:
    key = settings.ELEVENLABS_API_KEY
    if not key:
        return _missing("ELEVENLABS_API_KEY")
    # /v1/models needs no special scope, so a restricted key still passes.
    return await _http_check(
        "GET",
        "https://api.elevenlabs.io/v1/models",
        headers={"xi-api-key": key},
        ok_message="Key accepted.",
    )


async def check_twilio() -> CheckResult:
    sid, token = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    missing = [n for n, v in (("TWILIO_ACCOUNT_SID", sid), ("TWILIO_AUTH_TOKEN", token)) if not v]
    if missing:
        return _missing(*missing)
    return await _http_check(
        "GET",
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
        auth=(sid, token),
        ok_message="Account SID and auth token accepted.",
    )


async def check_stripe() -> CheckResult:
    key = settings.stripe_secret_key
    if not key:
        return _missing("STRIPE_SECRET_KEY")
    result = await _http_check(
        "GET", "https://api.stripe.com/v1/balance", auth=(key, ""), ok_message="Secret key accepted."
    )
    if result.status == "ok":
        mode = "live" if key.startswith(("sk_live_", "rk_live_")) else "test"
        result.message = f"Secret key accepted ({mode} mode)."
        if not settings.STRIPE_WEBHOOK_SECRET:
            result.message += " Webhook signing secret is not set, so billing webhooks will be rejected."
    return result


async def check_polar() -> CheckResult:
    token = settings.POLAR_ACCESS_TOKEN
    if not token:
        return _missing("POLAR_ACCESS_TOKEN")
    env = "production" if settings.polar_api_base == "https://api.polar.sh" else "sandbox"
    result = await _http_check(
        "GET",
        f"{settings.polar_api_base}/v1/products/?limit=1",
        headers={"Authorization": f"Bearer {token}"},
        ok_message="Access token accepted.",
    )
    if result.status == "ok":
        result.message = f"Access token accepted ({env})."
        if not settings.POLAR_WEBHOOK_SECRET:
            result.message += " Webhook signing secret is not set, so Polar webhooks will be rejected."
    elif result.status == "invalid":
        result.message += f" Check the token belongs to the {env} environment and has the products:read scope."
    return result


def _smtp_login() -> str:
    host, port = settings.SMTP_HOST, int(settings.SMTP_PORT or 587)
    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_SECONDS, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS)
    try:
        server.ehlo()
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            server.starttls(context=context)
            server.ehlo()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            return "Connected and signed in."
        return "Connected (no username set, so sign-in was not tested)."
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def check_email() -> CheckResult:
    provider = settings.resolved_email_provider
    if provider == "console":
        return CheckResult(
            "not_configured",
            "No email provider configured: emails are only written to the server log.",
        )
    if provider == "sendgrid":
        if not settings.SENDGRID_API_KEY:
            return _missing("SENDGRID_API_KEY")
        return await _http_check(
            "GET",
            "https://api.sendgrid.com/v3/scopes",
            headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
            ok_message="SendGrid key accepted.",
        )
    if not settings.SMTP_HOST:
        return _missing("SMTP_HOST")
    started = time.monotonic()
    try:
        message = await asyncio.to_thread(_smtp_login)
    except smtplib.SMTPAuthenticationError:
        return CheckResult("invalid", "SMTP server rejected the username or password.")
    except Exception as exc:
        return CheckResult("error", f"Could not connect to the SMTP server: {type(exc).__name__}")
    return CheckResult("ok", message, int((time.monotonic() - started) * 1000))


def _s3_head_bucket() -> None:
    import boto3

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        endpoint_url=settings.AWS_ENDPOINT_URL or None,
    )
    client.head_bucket(Bucket=settings.AWS_S3_BUCKET)


async def check_storage() -> CheckResult:
    missing = [
        n
        for n in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET")
        if not getattr(settings, n, None)
    ]
    if missing:
        return CheckResult(
            "not_configured",
            f"Missing: {', '.join(missing)}. Files are stored on the server's local disk.",
        )
    started = time.monotonic()
    try:
        await asyncio.to_thread(_s3_head_bucket)
    except Exception as exc:
        text = str(exc)
        if any(code in text for code in ("403", "InvalidAccessKeyId", "SignatureDoesNotMatch", "AccessDenied")):
            return CheckResult("invalid", "Credentials were rejected or lack access to the bucket.")
        if "404" in text or "NoSuchBucket" in text:
            return CheckResult("invalid", "The bucket does not exist.")
        return CheckResult("error", f"Could not reach the bucket: {type(exc).__name__}")
    return CheckResult("ok", "Bucket reachable with these credentials.", int((time.monotonic() - started) * 1000))


CHECKS: Dict[str, Callable[[], Awaitable[CheckResult]]] = {
    "openai": check_openai,
    "anthropic": check_anthropic,
    "deepgram": check_deepgram,
    "elevenlabs": check_elevenlabs,
    "twilio": check_twilio,
    "stripe": check_stripe,
    "polar": check_polar,
    "email": check_email,
    "storage": check_storage,
}


async def run_check(provider: str) -> CheckResult:
    check = CHECKS.get(provider)
    if check is None:
        return CheckResult("error", f"No connection test for '{provider}'.")
    try:
        return await check()
    except Exception as exc:  # a check must never 500 the admin page
        logger.warning(f"Provider check {provider} failed unexpectedly: {exc}")
        return CheckResult("error", f"Check failed: {type(exc).__name__}")
