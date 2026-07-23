"""
Concrete email providers: Console (dev), SMTP (stdlib), SendGrid.

SMTP uses the standard library ``smtplib`` run in a worker thread (via
``asyncio.to_thread``) so it never blocks the event loop — no extra async-SMTP
dependency required.
"""
import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings
from app.services.email.base import EmailMessage, EmailProvider

logger = logging.getLogger(__name__)


def _from_header(message: EmailMessage) -> str:
    name = message.from_name or settings.EMAIL_FROM_NAME
    email = message.from_email or settings.EMAIL_FROM
    return formataddr((name, email))


class ConsoleProvider(EmailProvider):
    """Dev fallback: logs the email instead of sending it.

    Used automatically when no SMTP/SendGrid credentials are configured, so the
    invite flow is fully exercisable locally without a mail server.
    """

    name = "console"

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "[email:console] Would send email\n  From: %s\n  To: %s <%s>\n  Subject: %s\n  --- text ---\n%s",
            _from_header(message),
            message.to_name or "",
            message.to,
            message.subject,
            (message.text or message.html)[:2000],
        )


class SMTPProvider(EmailProvider):
    """Generic SMTP transport (stdlib smtplib in a thread)."""

    name = "smtp"

    def _send_sync(self, message: EmailMessage) -> None:
        mime = MIMEMultipart("alternative")
        mime["Subject"] = message.subject
        mime["From"] = _from_header(message)
        mime["To"] = formataddr((message.to_name or "", message.to))
        if message.reply_to:
            mime["Reply-To"] = message.reply_to
        if message.text:
            mime.attach(MIMEText(message.text, "plain", "utf-8"))
        mime.attach(MIMEText(message.html, "html", "utf-8"))

        host, port, timeout = settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_TIMEOUT

        if settings.SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
                self._auth_and_send(server, mime, message)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                self._auth_and_send(server, mime, message)

    def _auth_and_send(self, server: smtplib.SMTP, mime: MIMEMultipart, message: EmailMessage) -> None:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        from_addr = message.from_email or settings.EMAIL_FROM
        server.sendmail(from_addr, [message.to], mime.as_string())

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)
        logger.info("[email:smtp] Sent '%s' to %s", message.subject, message.to)


class SendGridProvider(EmailProvider):
    """SendGrid transport (uses the installed sendgrid SDK)."""

    name = "sendgrid"

    def _send_sync(self, message: EmailMessage) -> None:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content

        from_email = message.from_email or settings.SENDGRID_FROM_EMAIL or settings.EMAIL_FROM
        mail = Mail(
            from_email=Email(from_email, message.from_name or settings.EMAIL_FROM_NAME),
            to_emails=To(message.to, message.to_name),
            subject=message.subject,
        )
        if message.text:
            mail.add_content(Content("text/plain", message.text))
        mail.add_content(Content("text/html", message.html))
        client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        client.send(mail)

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)
        logger.info("[email:sendgrid] Sent '%s' to %s", message.subject, message.to)
