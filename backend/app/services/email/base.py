"""
Email provider abstraction.

Adding a new transport = implement ``EmailProvider.send`` and wire it into
``service.EmailService._build_provider``. Every provider receives the same
normalized ``EmailMessage``.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailMessage:
    """A single outbound email, transport-agnostic."""

    to: str
    subject: str
    html: str
    text: Optional[str] = None
    to_name: Optional[str] = None
    # Optional overrides; default to settings.EMAIL_FROM / EMAIL_FROM_NAME.
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None


class EmailProvider(ABC):
    """Transport that actually delivers an EmailMessage."""

    name: str = "base"

    @abstractmethod
    async def send(self, message: EmailMessage) -> None:
        """Deliver the message. Should raise on hard failure."""
        raise NotImplementedError
