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
    render_account_notice_email,
    render_billing_notice_email,
    render_email_changed_notice,
    render_invitation_email,
    render_member_joined_email,
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
        Send a one-time code for sign-up verification, password reset or
        confirming a new email address.

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

    async def send_email_changed_notice(
        self,
        *,
        old_email: str,
        new_email: str,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """
        Tell the previous address that the account has moved to a new one.

        This is how the owner finds out about a change they did not make, so it
        goes to the *old* address. It never raises: the change has already
        happened and must not be reported as failed because a notice bounced.
        """
        html, text, subject = render_email_changed_notice(
            brand=settings.APP_NAME,
            old_email=old_email,
            new_email=new_email,
            support_email=settings.EMAIL_REPLY_TO or "support@voicecon.ai",
            recipient_name=recipient_name,
        )
        message = EmailMessage(
            to=old_email,
            to_name=recipient_name,
            subject=subject,
            html=html,
            text=text,
        )
        return await self.send(message)

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

    async def send_member_joined(
        self,
        *,
        to_email: str,
        recipient_name: Optional[str],
        member_name: str,
        member_email: str,
        organization_name: str,
        role: str,
        team_url: str,
    ) -> bool:
        """Tell a workspace owner that an invitee accepted and joined."""
        html, text, subject = render_member_joined_email(
            brand=settings.APP_NAME,
            member_name=member_name,
            member_email=member_email,
            organization_name=organization_name,
            role=role,
            team_url=team_url,
            recipient_name=recipient_name,
        )
        message = EmailMessage(
            to=to_email, to_name=recipient_name, subject=subject, html=html, text=text
        )
        return await self.send(message)

    async def _send_account_notice(
        self,
        *,
        to_email: str,
        recipient_name: Optional[str],
        subject: str,
        heading: str,
        paragraphs: list[str],
        support_line: str = "",
    ) -> bool:
        """Never raises: these confirm something that has already happened."""
        html, text = render_account_notice_email(
            brand=settings.APP_NAME,
            heading=heading,
            paragraphs=paragraphs,
            support_email=settings.EMAIL_REPLY_TO or "support@voicecon.ai",
            support_line=support_line,
        )
        message = EmailMessage(
            to=to_email, to_name=recipient_name, subject=subject, html=html, text=text
        )
        return await self.send(message)

    async def send_account_deactivated(
        self,
        *,
        to_email: str,
        deletion_date: datetime,
        retention_days: int,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """Confirm a deactivation and say when the account is deleted for good.

        Also how the owner finds out about a deactivation they did not make.
        """
        brand = settings.APP_NAME
        when = f"{deletion_date.strftime('%B')} {deletion_date.day}, {deletion_date.year}"
        greeting = f"Hi {recipient_name}, your" if recipient_name else "Your"
        return await self._send_account_notice(
            to_email=to_email,
            recipient_name=recipient_name,
            subject=f"Your {brand} account has been deactivated",
            heading="Your account has been deactivated",
            paragraphs=[
                f"{greeting} {brand} account has been deactivated. You have been signed out "
                "and can no longer sign in. Your workspaces are switched off and any "
                "subscription on them has been cancelled.",
                f"Your account and its data will be permanently deleted on {when} "
                f"({retention_days} days from now). After that it cannot be recovered.",
                "Our support team reactivates accounts within 2 business days. If you did not "
                "deactivate your account, contact us straight away.",
            ],
            support_line="To reactivate your account before then, contact us at",
        )

    async def send_account_reactivated(
        self,
        *,
        to_email: str,
        login_url: str,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """Tell the owner their account is back and how to get in."""
        brand = settings.APP_NAME
        greeting = f"Hi {recipient_name}, your" if recipient_name else "Your"
        return await self._send_account_notice(
            to_email=to_email,
            recipient_name=recipient_name,
            subject=f"Your {brand} account has been reactivated",
            heading="Your account has been reactivated",
            paragraphs=[
                f"{greeting} {brand} account is active again and is no longer scheduled "
                "for deletion. Your workspaces and everything in them are as you left them.",
                f"Sign in at {login_url} with the same email and password (or Google/Apple) "
                "as before.",
                "Your subscription was cancelled when the account was deactivated, so choose "
                "a plan under Settings, then Billing, to switch your agents back on.",
            ],
            support_line="Questions? Contact us at",
        )

    async def send_account_deleted(
        self,
        *,
        to_email: str,
        recipient_name: Optional[str] = None,
    ) -> bool:
        """Final confirmation, sent to the address just before we forget it."""
        brand = settings.APP_NAME
        greeting = f"Hi {recipient_name}, your" if recipient_name else "Your"
        return await self._send_account_notice(
            to_email=to_email,
            recipient_name=recipient_name,
            subject=f"Your {brand} account has been permanently deleted",
            heading="Your account has been permanently deleted",
            paragraphs=[
                f"{greeting} {brand} account was deactivated and its recovery period has "
                "ended, so the account has now been permanently deleted. It cannot be restored.",
                f"This email address is free to use again: you are welcome to create a new "
                f"{brand} account with it at any time.",
            ],
        )

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

    async def send_affiliate_invite(
        self,
        *,
        to_email: str,
        name: str,
        action_url: str,
        needs_password: bool,
        earning_terms: str,
    ) -> bool:
        """Invite a partner to the affiliate portal. Never raises."""
        brand = settings.APP_NAME
        html, text = render_billing_notice_email(
            brand=brand,
            heading=f"Welcome to the {brand} affiliate program",
            intro=(
                f"Hi {name}, you've been added as a {brand} affiliate partner. "
                "Your portal shows your referral link, coupon code, referred customers and earnings."
            ),
            bullets=[
                earning_terms,
                "Connect your Stripe account in the portal to receive payouts.",
            ],
            action_url=action_url,
            action_label="Set your password" if needs_password else "Open the affiliate portal",
            closing="This link expires in 7 days. If it has expired, ask us to send a new one.",
            footer=f"You received this because {brand} added you to its affiliate program.",
        )
        message = EmailMessage(
            to=to_email, subject=f"You're invited to the {brand} affiliate program", html=html, text=text
        )
        return await self.send(message)

    async def send_affiliate_application_notice(
        self,
        *,
        to_email: str,
        applicant_name: str,
        applicant_email: str,
        company: Optional[str],
        website: Optional[str],
        message: Optional[str],
        action_url: str,
    ) -> bool:
        """Tell a platform admin that someone applied to the affiliate program. Never raises."""
        brand = settings.APP_NAME
        bullets = [f"Name: {applicant_name}", f"Email: {applicant_email}"]
        if company:
            bullets.append(f"Company: {company}")
        if website:
            bullets.append(f"Website or channel: {website}")
        if message:
            # The full text is in the console; the email only needs the gist.
            bullets.append(f"About them: {message[:600]}{'…' if len(message) > 600 else ''}")
        html, text = render_billing_notice_email(
            brand=brand,
            heading="New affiliate request",
            intro=(
                f"{applicant_name} applied to join the {brand} affiliate program. "
                "Review the request in the admin console, then create their affiliate account or reject it."
            ),
            bullets=bullets,
            action_url=action_url,
            action_label="Review the request",
            footer=f"You received this because you are a {brand} platform admin.",
        )
        message_out = EmailMessage(
            to=to_email, subject=f"New affiliate request from {applicant_name}", html=html, text=text
        )
        return await self.send(message_out)

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
