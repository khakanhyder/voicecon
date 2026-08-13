"""
SMTP email connectors.

Gmail, Outlook and Custom SMTP are one implementation with three presets: the
first two only differ from the third by having their host and port filled in
already.

These do not use the shared IntegrationHTTPClient — SMTP is not HTTP. Python's
smtplib is synchronous, so each send runs in a worker thread rather than
blocking the event loop that is also carrying live calls.

A note on credentials: for Gmail and Outlook the password field must be an
**app password**, not the account password. Both providers reject the account
password over SMTP whenever 2FA is on, with an error that says "username and
password not accepted" and sends people hunting for the wrong problem. The
setup steps say this in as many words.
"""
import asyncio
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Any, Dict, List, Optional

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

#: Deliberately permissive — the SMTP server is the real authority on whether an
#: address exists. This only catches "obviously not an address" before we open a
#: connection to find out.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SMTPConnector(BaseConnector):
    """Send mail through any SMTP server."""

    provider_label = "SMTP"

    #: Preset host/port, overridden per provider. None means the user supplies
    #: them (Custom SMTP).
    default_host: Optional[str] = None
    default_port: int = 587
    default_use_tls: bool = True

    def _settings(self) -> Dict[str, Any]:
        auth = self.get_auth_data()
        password = self.credential_manager.decrypt(
            self.connection.api_key_encrypted or ""
        )
        host = auth.get("host") or auth.get("smtp_host") or self.default_host
        if not host:
            raise ConnectorError(
                "No SMTP host configured for this connection."
            )

        username = auth.get("username") or auth.get("email")
        if not username:
            raise ConnectorError("No SMTP username configured for this connection.")

        raw_port = auth.get("port") or auth.get("smtp_port") or self.default_port
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            raise ConnectorError(f"SMTP port '{raw_port}' is not a number.")

        # Port 465 is implicit TLS (SMTPS); 587 and 25 are STARTTLS. Getting
        # this backwards hangs the connection rather than erroring, so it is
        # derived from the port unless the user was explicit.
        explicit = auth.get("use_ssl")
        use_ssl = (
            str(explicit).lower() in ("1", "true", "yes")
            if explicit is not None
            else port == 465
        )

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "use_ssl": use_ssl,
            "use_tls": not use_ssl and self.default_use_tls,
            "from_email": auth.get("from_email") or username,
            "from_name": auth.get("from_name"),
        }

    def _connect(self, settings: Dict[str, Any]):
        """Open an authenticated SMTP session. Runs in a worker thread."""
        context = ssl.create_default_context()
        if settings["use_ssl"]:
            server = smtplib.SMTP_SSL(
                settings["host"], settings["port"], timeout=15, context=context
            )
        else:
            server = smtplib.SMTP(settings["host"], settings["port"], timeout=15)
            if settings["use_tls"]:
                server.starttls(context=context)
        server.login(settings["username"], settings["password"])
        return server

    def _describe(self, exc: Exception) -> str:
        """Turn smtplib's errors into something a user can act on."""
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            return (
                "The server rejected the username or password. If this is Gmail "
                "or Outlook with 2FA enabled, you need an app password rather "
                "than your account password."
            )
        if isinstance(exc, smtplib.SMTPConnectError):
            return "Could not reach the SMTP server — check the host and port."
        if isinstance(exc, ssl.SSLError):
            return (
                "TLS negotiation failed. Port 465 expects implicit SSL; ports "
                "587 and 25 expect STARTTLS."
            )
        if isinstance(exc, (TimeoutError, OSError)):
            return f"Could not connect to the SMTP server: {exc}"
        return str(exc)

    async def test_connection(self) -> Dict[str, Any]:
        try:
            settings = self._settings()
        except ConnectorError as exc:
            return {"success": False, "message": str(exc), "details": {}}

        def _probe():
            server = self._connect(settings)
            try:
                server.noop()
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001 - already done with it
                    pass

        try:
            await asyncio.to_thread(_probe)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {self._describe(exc)}",
                "details": {},
            }

        return {
            "success": True,
            "message": f"{self.provider_label} connection successful",
            "details": {
                "host": settings["host"],
                "port": settings["port"],
                "from_email": settings["from_email"],
            },
        }

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[str] = None,
        reply_to: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email.

        ``to_email`` and ``cc`` accept a comma-separated list, because that is
        what an agent produces when a caller says "send it to me and my
        assistant".
        """
        settings = self._settings()

        recipients = self._parse_addresses(to_email, field="to_email")
        cc_list = self._parse_addresses(cc, field="cc") if cc else []
        if not recipients:
            raise ConnectorError("send_email needs at least one recipient")

        message = EmailMessage()
        message["Subject"] = subject or ""
        message["From"] = formataddr(
            (from_name or settings["from_name"] or "", settings["from_email"])
        )
        message["To"] = ", ".join(recipients)
        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        if reply_to:
            message["Reply-To"] = reply_to

        message.set_content(body or "")
        if html_body:
            message.add_alternative(html_body, subtype="html")

        def _send():
            server = self._connect(settings)
            try:
                server.send_message(message, to_addrs=recipients + cc_list)
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001
                    pass

        try:
            await asyncio.to_thread(_send)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(
                f"Could not send email: {self._describe(exc)}"
            ) from exc

        logger.info(
            f"{self.provider_label}: sent '{subject}' to {len(recipients)} recipient(s)"
        )
        return {
            "success": True,
            "to": recipients,
            "cc": cc_list,
            "subject": subject,
            "from": settings["from_email"],
        }

    @staticmethod
    def _parse_addresses(value: str, *, field: str) -> List[str]:
        addresses = []
        for part in str(value or "").replace(";", ",").split(","):
            candidate = parseaddr(part.strip())[1]
            if not candidate:
                continue
            if not EMAIL_RE.match(candidate):
                raise ConnectorError(f"'{candidate}' in {field} is not a valid email address")
            addresses.append(candidate)
        return addresses


class GmailSMTPConnector(SMTPConnector):
    """Gmail over SMTP. Requires an app password when 2FA is on."""

    provider_label = "Gmail"
    default_host = "smtp.gmail.com"
    default_port = 587


class OutlookSMTPConnector(SMTPConnector):
    """Outlook / Microsoft 365 over SMTP."""

    provider_label = "Outlook"
    default_host = "smtp-mail.outlook.com"
    default_port = 587


class CustomSMTPConnector(SMTPConnector):
    """Any SMTP server — host and port supplied by the user."""

    provider_label = "Custom SMTP"
    default_host = None
    default_port = 587
