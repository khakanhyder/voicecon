"""
Concrete email providers: Console (dev), SMTP (stdlib), SendGrid.

SMTP uses the standard library ``smtplib`` run in a worker thread (via
``asyncio.to_thread``) so it never blocks the event loop — no extra async-SMTP
dependency required.
"""
import asyncio
import html as html_lib
import logging
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from app.core.config import settings
from app.services.email.base import EmailMessage, EmailProvider

logger = logging.getLogger(__name__)


def _from_header(message: EmailMessage) -> str:
    name = message.from_name or settings.EMAIL_FROM_NAME
    email = message.from_email or settings.EMAIL_FROM
    return formataddr((name, email))


def _from_address(message: EmailMessage) -> str:
    return message.from_email or settings.EMAIL_FROM


def _sender_domain(message: EmailMessage) -> str:
    """The From address's domain — what SPF, DKIM and DMARC are judged on."""
    address = _from_address(message)
    return address.rsplit("@", 1)[-1].lower() if "@" in address else "voicecon.ai"


def _reply_to(message: EmailMessage) -> str | None:
    return message.reply_to or settings.EMAIL_REPLY_TO or None


def _plain_text(message: EmailMessage) -> str:
    """The text/plain part. HTML-only mail scores worse with spam filters, so
    derive one from the HTML when a caller didn't write it."""
    if message.text:
        return message.text
    text = re.sub(r"(?is)<(style|script|head).*?</\1>", "", message.html)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</h[1-6]>|</tr>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


#: Headers every transactional email carries. Auto-Submitted marks it as
#: machine-sent (RFC 3834) so auto-responders don't reply to noreply, and the
#: Microsoft header stops Outlook/Exchange out-of-office bounces.
TRANSACTIONAL_HEADERS = {
    "Auto-Submitted": "auto-generated",
    "X-Auto-Response-Suppress": "OOF, AutoReply",
}


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
        mime["Date"] = formatdate(usegmt=True)
        # The Message-ID's domain should be the sending domain. It used to be
        # SERVER_HOST — an API host or bare IP — which filters read as a
        # mismatch between who claims to send the mail and who generated it.
        mime["Message-ID"] = make_msgid(domain=_sender_domain(message))
        reply_to = _reply_to(message)
        if reply_to:
            mime["Reply-To"] = reply_to
        for name, value in TRANSACTIONAL_HEADERS.items():
            mime[name] = value
        # Plain text first, HTML last: clients show the last part they support.
        mime.attach(MIMEText(_plain_text(message), "plain", "utf-8"))
        mime.attach(MIMEText(message.html, "html", "utf-8"))

        host, port, timeout = settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_TIMEOUT
        # EHLO with a real name instead of the container's random hostname,
        # which ends up in the Received header.
        helo = settings.SMTP_HELO_NAME or _sender_domain(message)

        if settings.SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                host, port, timeout=timeout, context=context, local_hostname=helo
            ) as server:
                self._auth_and_send(server, mime, message)
        else:
            with smtplib.SMTP(host, port, timeout=timeout, local_hostname=helo) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                self._auth_and_send(server, mime, message)

    def _auth_and_send(self, server: smtplib.SMTP, mime: MIMEMultipart, message: EmailMessage) -> None:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        # Envelope sender = From address, so SPF is checked against the same
        # domain the recipient sees (DMARC alignment).
        server.sendmail(_from_address(message), [message.to], mime.as_string())

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)
        logger.info("[email:smtp] Sent '%s' to %s", message.subject, message.to)


class SendGridProvider(EmailProvider):
    """SendGrid transport (uses the installed sendgrid SDK)."""

    name = "sendgrid"

    def _send_sync(self, message: EmailMessage) -> None:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Content, Email, Header, Mail, ReplyTo, To

        from_email = message.from_email or settings.SENDGRID_FROM_EMAIL or settings.EMAIL_FROM
        mail = Mail(
            from_email=Email(from_email, message.from_name or settings.EMAIL_FROM_NAME),
            to_emails=To(message.to, message.to_name),
            subject=message.subject,
        )
        mail.add_content(Content("text/plain", _plain_text(message)))
        mail.add_content(Content("text/html", message.html))
        reply_to = _reply_to(message)
        if reply_to:
            mail.reply_to = ReplyTo(reply_to)
        for name, value in TRANSACTIONAL_HEADERS.items():
            mail.add_header(Header(name, value))
        client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        client.send(mail)

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)
        logger.info("[email:sendgrid] Sent '%s' to %s", message.subject, message.to)
