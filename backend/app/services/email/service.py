"""
EmailService — the high-level API the rest of the app uses.

It lazily selects a provider based on ``settings.resolved_email_provider`` and
exposes both a generic ``send`` and purpose-built helpers (e.g.
``send_invitation``). Sending never raises into the caller by default: delivery
failures are logged and swallowed so a flaky mail server can't break the invite
API. Pass ``raise_on_error=True`` when the caller wants to know.
"""
import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.services.email.base import EmailMessage, EmailProvider
from app.services.email.providers import ConsoleProvider, SMTPProvider, SendGridProvider
from app.services.email.templates import (
    render_billing_notice_email,
    render_invitation_email,
    render_verification_code_email,
)

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self._provider: Optional[EmailProvider] = None
        self._provider_name: Optional[str] = None

    def _build_provider(self) -> EmailProvider:
        choice = settings.resolved_email_provider
        if choice == "smtp":
            return SMTPProvider()
        if choice == "sendgrid":
            return SendGridProvider()
        return ConsoleProvider()

    @property
    def provider(self) -> EmailProvider:
        # Rebuild if the resolved provider changed (e.g. tests toggling config).
        resolved = settings.resolved_email_provider
        if self._provider is None or self._provider_name != resolved:
            self._provider = self._build_provider()
            self._provider_name = resolved
            logger.info("Email provider initialized: %s", self._provider.name)
        return self._provider

    @property
    def delivery_enabled(self) -> bool:
        """True when a real transport (not the log-only console) is configured."""
        return settings.resolved_email_provider != "console"

    async def send(self, message: EmailMessage, *, raise_on_error: bool = False) -> bool:
        """Send an email. Returns True on success; logs + returns False on failure."""
        try:
            await self.provider.send(message)
            return True
        except Exception as exc:  # noqa: BLE001 — deliberately broad; email must not break callers
            logger.error("Email send failed (to=%s, subject=%s): %s", message.to, message.subject, exc)
            if raise_on_error:
                raise
            return False

    async def send_verification_code(
        self,
        *,
        to_email: str,
        code: str,
        expires_minutes: int,
        purpose: str = "signup",
        recipient_name: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Send a one-time code for sign-up verification or password reset.

        Unlike an invitation, the user is waiting on this email, so callers pass
        ``raise_on_error=True`` to surface a dead mail server rather than
        leaving them staring at a code that never arrives.
        """
        html, text, subject = render_verification_code_email(
            brand=settings.APP_NAME,
            code=code,
            expires_minutes=expires_minutes,
            purpose=purpose,
            recipient_name=recipient_name,
        )
        message = EmailMessage(
            to=to_email,
            to_name=recipient_name,
            subject=subject,
            html=html,
            text=text,
        )
        return await self.send(message, raise_on_error=raise_on_error)

    async def send_invitation(
        self,
        *,
        to_email: str,
        organization_name: str,
        inviter_name: Optional[str],
        role: str,
        accept_url: str,
        reject_url: str,
        expires_at: datetime,
        raise_on_error: bool = False,
    ) -> bool:
        """Render and send a team-invitation email."""
        html, text = render_invitation_email(
            brand=settings.APP_NAME,
            organization_name=organization_name,
            inviter_name=inviter_name,
            role=role,
            accept_url=accept_url,
            reject_url=reject_url,
            expires_human=expires_at.strftime("%B %d, %Y"),
        )
        message = EmailMessage(
            to=to_email,
            subject=f"You're invited to join {organization_name} on {settings.APP_NAME}",
            html=html,
            text=text,
        )
        return await self.send(message, raise_on_error=raise_on_error)

    async def send_billing_notice(
        self,
        *,
        to_email: str,
        subject: str,
        heading: str,
        intro: str,
        action_url: str,
        action_label: str = "Choose a plan",
        bullets: Optional[list[str]] = None,
        closing: str = "",
    ) -> bool:
        """Send a trial or subscription lifecycle notice.

        Never raises: the reconciler that calls this is mid-transition, and a
        dead mail server must not roll back a subscription state change.
        """
        html, text = render_billing_notice_email(
            brand=settings.APP_NAME,
            heading=heading,
            intro=intro,
            action_url=action_url,
            action_label=action_label,
            bullets=bullets,
            closing=closing,
        )
        message = EmailMessage(to=to_email, subject=subject, html=html, text=text)
        return await self.send(message)

    async def send_subscription_confirmation(
        self,
        *,
        to_email: str,
        plan_name: str,
        action_url: str,
    ) -> bool:
        """Send a confirmation email when a user subscribes to a paid plan."""
        subject = f"{plan_name} Subscription is Active"
        heading = f"Welcome to {plan_name}"
        intro = (
            f"Your subscription to the {plan_name} plan is now active. "
            "You can now access all features included in your plan."
        )
        bullets = [
            "Your agents and workflows are fully enabled.",
            "You can manage your subscription at any time from your dashboard."
        ]
        html, text = render_billing_notice_email(
            brand=settings.APP_NAME,
            heading=heading,
            intro=intro,
            action_url=action_url,
            action_label="Go to Dashboard",
            bullets=bullets,
        )
        message = EmailMessage(to=to_email, subject=subject, html=html, text=text)
        return await self.send(message)


# Process-wide singleton.
email_service = EmailService()
