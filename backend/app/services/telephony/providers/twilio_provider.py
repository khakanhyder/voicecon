"""
Twilio number provider.

Talks to the Twilio REST API (2010-04-01) over HTTP Basic auth, where the
username is the Account SID and the password is the Auth Token. Credentials
come from the user's Twilio integration connection, so different users can buy
numbers on their own Twilio accounts.
"""
import base64
import logging
from typing import Any, Dict, List, Optional

from app.services.telephony.providers.base import (
    AvailableNumber,
    NumberProvider,
    NumberProviderError,
    PurchasedNumber,
)

logger = logging.getLogger(__name__)


class TwilioNumberProvider(NumberProvider):
    """Buy and configure phone numbers on Twilio."""

    slug = "twilio"
    name = "Twilio"
    base_url = "https://api.twilio.com"
    credential_hint = (
        "Reconnect Twilio under Integrations with your Account SID and Auth Token."
    )

    def validate_credentials(self) -> None:
        if not self.credentials.get("account_sid") or not self.credentials.get("auth_token"):
            raise NumberProviderError(
                f"Twilio credentials are incomplete. {self.credential_hint}"
            )

    @property
    def account_sid(self) -> str:
        return self.credentials["account_sid"]

    def auth_headers(self) -> Dict[str, str]:
        pair = f"{self.account_sid}:{self.credentials['auth_token']}"
        encoded = base64.b64encode(pair.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    async def search_numbers(
        self,
        country_code: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        limit: int = 10,
    ) -> List[AvailableNumber]:
        params: Dict[str, Any] = {"PageSize": limit, "VoiceEnabled": "true"}
        if area_code:
            params["AreaCode"] = area_code
        if contains:
            params["Contains"] = contains

        payload = await self._request(
            "GET",
            f"/2010-04-01/Accounts/{self.account_sid}"
            f"/AvailablePhoneNumbers/{country_code}/Local.json",
            params=params,
        )

        results: List[AvailableNumber] = []
        for item in (payload or {}).get("available_phone_numbers", []):
            caps = item.get("capabilities") or {}
            results.append(
                AvailableNumber(
                    phone_number=item.get("phone_number"),
                    friendly_name=item.get("friendly_name") or item.get("phone_number"),
                    provider=self.slug,
                    locality=item.get("locality"),
                    region=item.get("region"),
                    capabilities={
                        "voice": bool(caps.get("voice")),
                        "sms": bool(caps.get("SMS") or caps.get("sms")),
                        "mms": bool(caps.get("MMS") or caps.get("mms")),
                    },
                    currency="USD",
                )
            )

        logger.info(f"[twilio] found {len(results)} numbers in {country_code}")
        return results

    async def purchase_number(
        self,
        phone_number: str,
        voice_url: str,
        status_callback_url: Optional[str] = None,
        label: Optional[str] = None,
    ) -> PurchasedNumber:
        form: Dict[str, Any] = {
            "PhoneNumber": phone_number,
            "VoiceUrl": voice_url,
            "VoiceMethod": "POST",
        }
        if status_callback_url:
            form["StatusCallback"] = status_callback_url
            form["StatusCallbackMethod"] = "POST"
        if label:
            form["FriendlyName"] = label

        payload = await self._request(
            "POST",
            f"/2010-04-01/Accounts/{self.account_sid}/IncomingPhoneNumbers.json",
            form=form,
        )

        caps = (payload or {}).get("capabilities") or {}
        logger.info(f"[twilio] purchased {phone_number} (SID {payload.get('sid')})")

        return PurchasedNumber(
            phone_number=payload.get("phone_number") or phone_number,
            provider=self.slug,
            provider_sid=payload.get("sid"),
            capabilities={
                "voice": bool(caps.get("voice", True)),
                "sms": bool(caps.get("sms") or caps.get("SMS")),
                "mms": bool(caps.get("mms") or caps.get("MMS")),
            },
        )

    async def release_number(
        self,
        provider_sid: Optional[str],
        phone_number: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        sid = provider_sid or await self._lookup_sid(phone_number)
        if not sid:
            raise NumberProviderError(
                f"Cannot release {phone_number}: no Twilio SID on record"
            )

        await self._request(
            "DELETE",
            f"/2010-04-01/Accounts/{self.account_sid}/IncomingPhoneNumbers/{sid}.json",
            expect_json=False,
        )
        logger.info(f"[twilio] released {phone_number or sid}")
        return True

    async def update_voice_webhook(
        self,
        provider_sid: Optional[str],
        voice_url: str,
        phone_number: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sid = provider_sid or await self._lookup_sid(phone_number)
        if not sid:
            raise NumberProviderError(
                f"Cannot update {phone_number}: no Twilio SID on record"
            )

        form: Dict[str, Any] = {"VoiceUrl": voice_url, "VoiceMethod": "POST"}
        if status_callback_url:
            form["StatusCallback"] = status_callback_url
            form["StatusCallbackMethod"] = "POST"

        await self._request(
            "POST",
            f"/2010-04-01/Accounts/{self.account_sid}/IncomingPhoneNumbers/{sid}.json",
            form=form,
        )
        logger.info(f"[twilio] repointed voice webhook for {phone_number or sid}")
        return provider_metadata or {}

    async def _lookup_sid(self, phone_number: Optional[str]) -> Optional[str]:
        """Find a number's SID by its E.164 value (fallback for older rows)."""
        if not phone_number:
            return None

        payload = await self._request(
            "GET",
            f"/2010-04-01/Accounts/{self.account_sid}/IncomingPhoneNumbers.json",
            params={"PhoneNumber": phone_number, "PageSize": 1},
        )
        numbers = (payload or {}).get("incoming_phone_numbers") or []
        return numbers[0].get("sid") if numbers else None
