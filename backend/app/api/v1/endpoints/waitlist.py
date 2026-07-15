"""
Waitlist Endpoints.

Public "Launching Soon" waitlist sign-up. Submitted emails are pushed into a
Mailchimp Audience (List) so the marketing team can notify sign-ups at launch.

No authentication is required — this is called from the public landing page.
"""
import hashlib
import logging

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class WaitlistSignup(BaseModel):
    """Payload for a waitlist sign-up."""

    email: EmailStr
    # Optional — captured if the form ever collects a name; harmless when empty.
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class WaitlistResponse(BaseModel):
    success: bool
    message: str


def _subscriber_hash(email: str) -> str:
    """Mailchimp subscriber hash: MD5 of the lowercased email address."""
    return hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()


@router.post("/subscribe", response_model=WaitlistResponse, status_code=status.HTTP_200_OK)
async def subscribe_to_waitlist(payload: WaitlistSignup) -> WaitlistResponse:
    """
    Add an email address to the Voicecon waitlist Mailchimp Audience.

    Uses an upsert (PUT) keyed on the subscriber hash, so submitting the same
    email twice is idempotent and never returns an error to the visitor.
    """
    if not settings.mailchimp_configured:
        logger.error(
            "Waitlist sign-up attempted but Mailchimp is not configured "
            "(need MAILCHIMP_API_KEY, MAILCHIMP_AUDIENCE_ID, and a server prefix)."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The waitlist is not available right now. Please try again later.",
        )

    dc = settings.mailchimp_server_prefix
    list_id = settings.MAILCHIMP_AUDIENCE_ID
    email = str(payload.email)
    url = (
        f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}"
        f"/members/{_subscriber_hash(email)}"
    )

    merge_fields = {}
    if payload.first_name:
        merge_fields["FNAME"] = payload.first_name
    if payload.last_name:
        merge_fields["LNAME"] = payload.last_name

    body = {
        "email_address": email,
        # Only sets status on brand-new contacts; won't re-subscribe someone
        # who previously unsubscribed (Mailchimp compliance).
        "status_if_new": "subscribed",
    }
    if merge_fields:
        body["merge_fields"] = merge_fields

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Mailchimp accepts HTTP basic auth with any username + the API key.
            resp = await client.put(
                url,
                json=body,
                auth=("voicecon", settings.MAILCHIMP_API_KEY),
            )
    except httpx.HTTPError as exc:
        logger.exception("Mailchimp request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't reach the waitlist service. Please try again in a moment.",
        )

    if resp.status_code in (200, 201):
        return WaitlistResponse(
            success=True,
            message="You're on the list! We'll email you the moment Voicecon launches.",
        )

    # Surface Mailchimp's error for logs, but keep the visitor-facing message clean.
    detail = {}
    try:
        detail = resp.json()
    except Exception:  # noqa: BLE001 - non-JSON error body
        detail = {"raw": resp.text}

    logger.error(
        "Mailchimp rejected waitlist sign-up (status=%s): %s",
        resp.status_code,
        detail,
    )

    # A previously-unsubscribed/cleaned contact returns 400; treat gracefully.
    title = (detail or {}).get("title", "")
    if resp.status_code == 400 and title in (
        "Member In Compliance State",
        "Forgotten Email Not Subscribed",
    ):
        return WaitlistResponse(
            success=True,
            message="You're already on our list — we'll be in touch at launch.",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="We couldn't add you to the waitlist. Please check your email and try again.",
    )
