"""Send a real test email through the app's configured provider.

Usage (from backend/, with the venv active):
    python scripts/test_smtp.py you@example.com

Verifies host/port/TLS/credentials end-to-end using the same EmailService the
signup, invite and password-reset flows use. Exit code 0 = delivered.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.services.email.base import EmailMessage  # noqa: E402
from app.services.email.service import EmailService  # noqa: E402


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/test_smtp.py <recipient@example.com>")
        return 2
    recipient = sys.argv[1]

    print(f"provider : {settings.resolved_email_provider}")
    print(f"host     : {settings.SMTP_HOST}:{settings.SMTP_PORT} "
          f"(tls={settings.SMTP_USE_TLS} ssl={settings.SMTP_USE_SSL})")
    print(f"username : {settings.SMTP_USERNAME}")
    print(f"from     : {settings.email_from_full}")
    print(f"to       : {recipient}\n")

    if settings.resolved_email_provider == "console":
        print("!! console provider — nothing will actually be delivered.")

    ok = await EmailService().send(
        EmailMessage(
            to=recipient,
            subject="Voicecon SMTP test",
            html="<p>SMTP is configured correctly. This is a test from Voicecon.</p>",
            text="SMTP is configured correctly. This is a test from Voicecon.",
        ),
        raise_on_error=True,
    )
    print("DELIVERED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
