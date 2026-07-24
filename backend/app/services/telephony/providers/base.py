"""
Telephony number-provider abstraction.

Phone numbers can be bought from more than one carrier (Twilio, Telnyx, ...).
Each carrier is wrapped in a `NumberProvider` so the phone-number endpoints stay
carrier-agnostic: they resolve a provider from the user's connected integration
and then call the same handful of operations no matter who the carrier is.

Credentials are always passed in by the resolver (decrypted from the user's
`IntegrationConnection`) — a provider never reads global settings itself.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class NumberProviderError(Exception):
    """Raised when a carrier operation fails."""


@dataclass
class AvailableNumber:
    """A number offered for sale by a carrier."""

    phone_number: str
    friendly_name: str
    provider: str
    locality: Optional[str] = None
    region: Optional[str] = None
    capabilities: Dict[str, bool] = field(default_factory=dict)
    monthly_cost: Optional[float] = None
    setup_cost: Optional[float] = None
    currency: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "phone_number": self.phone_number,
            "friendly_name": self.friendly_name,
            "provider": self.provider,
            "locality": self.locality,
            "region": self.region,
            "capabilities": self.capabilities,
            "monthly_cost": self.monthly_cost,
            "setup_cost": self.setup_cost,
            "currency": self.currency,
        }


@dataclass
class PurchasedNumber:
    """The result of buying a number from a carrier."""

    phone_number: str
    provider: str
    provider_sid: str
    capabilities: Dict[str, bool] = field(default_factory=dict)
    monthly_cost: Optional[float] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)


class NumberProvider(ABC):
    """
    Base class for a carrier that can sell and configure phone numbers.

    Subclasses talk to their carrier over HTTP and translate results into the
    shared `AvailableNumber` / `PurchasedNumber` shapes.
    """

    slug: str = ""
    name: str = ""
    base_url: str = ""

    #: Human-readable hint shown when credentials are missing/incomplete.
    credential_hint: str = ""

    def __init__(self, credentials: Dict[str, Any]):
        """
        Args:
            credentials: Decrypted credentials for this carrier, resolved from
                the user's integration connection.
        """
        self.credentials = credentials or {}
        self.validate_credentials()

    # ── to implement ────────────────────────────────────────────────────────

    def validate_credentials(self) -> None:
        """Raise `NumberProviderError` if the credentials are unusable."""

    @abstractmethod
    def auth_headers(self) -> Dict[str, str]:
        """Authentication headers for carrier API calls."""

    @abstractmethod
    async def search_numbers(
        self,
        country_code: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        limit: int = 10,
    ) -> List[AvailableNumber]:
        """Search the carrier's inventory for buyable numbers."""

    @abstractmethod
    async def purchase_number(
        self,
        phone_number: str,
        voice_url: str,
        status_callback_url: Optional[str] = None,
        label: Optional[str] = None,
    ) -> PurchasedNumber:
        """Buy `phone_number` and point its voice webhook at `voice_url`."""

    @abstractmethod
    async def release_number(
        self,
        provider_sid: Optional[str],
        phone_number: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Give the number back to the carrier."""

    @abstractmethod
    async def update_voice_webhook(
        self,
        provider_sid: Optional[str],
        voice_url: str,
        phone_number: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Re-point the number's voice webhook (used when a number is reassigned
        to a different agent). Returns provider metadata to persist.
        """

    # ── shared HTTP plumbing ────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        form: Optional[Dict[str, Any]] = None,
        expect_json: bool = True,
    ) -> Any:
        """
        Make an authenticated call to the carrier API.

        Raises:
            NumberProviderError: on transport failure or a non-2xx response.
        """
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self.auth_headers(),
                    params=params,
                    json=json_body,
                    data=form,
                )
        except httpx.HTTPError as e:
            logger.error(f"[{self.slug}] transport error on {method} {url}: {e}")
            raise NumberProviderError(f"{self.name} is unreachable: {e}")

        if response.status_code >= 400:
            detail = self._extract_error(response)
            logger.error(
                f"[{self.slug}] {method} {url} failed "
                f"({response.status_code}): {detail}"
            )
            raise NumberProviderError(f"{self.name}: {detail}")

        if not expect_json or not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            raise NumberProviderError(f"{self.name} returned a non-JSON response")

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        """Pull the most useful message out of a carrier error response."""
        try:
            payload = response.json()
        except ValueError:
            return (response.text or "")[:300] or f"HTTP {response.status_code}"

        # Telnyx: {"errors": [{"detail": "...", "title": "..."}]}
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if isinstance(errors, list) and errors:
            first = errors[0] or {}
            return first.get("detail") or first.get("title") or str(first)

        # Twilio: {"message": "...", "code": 20003}
        if isinstance(payload, dict):
            for key in ("message", "detail", "error", "error_message"):
                if payload.get(key):
                    return str(payload[key])

        return str(payload)[:300] or f"HTTP {response.status_code}"

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """Carriers return costs as strings; normalise to float or None."""
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
