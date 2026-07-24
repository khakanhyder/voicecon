"""
Telnyx number provider.

Talks to the Telnyx v2 API with the user's API key (Bearer auth), taken from
their Telnyx integration connection.

Buying a number on Telnyx is a two-part flow, unlike Twilio's single call:

1. `POST /v2/number_orders` places the order. The order can settle
   asynchronously, so the number resource may not exist for a moment.
2. Voice webhooks do not live on the number itself — the number is attached to
   an *application*, and the application holds the webhook URL. We use a TeXML
   application because TeXML speaks the same XML dialect as TwiML, so the
   inbound-call handler can reuse the existing `<Connect><Stream>` response.

One TeXML application is created per agent (named `Voicecon Agent <id>`) and
reused for every number pointed at that agent.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.services.telephony.providers.base import (
    AvailableNumber,
    NumberProvider,
    NumberProviderError,
    PurchasedNumber,
)

logger = logging.getLogger(__name__)


class TelnyxNumberProvider(NumberProvider):
    """Buy and configure phone numbers on Telnyx."""

    slug = "telnyx"
    name = "Telnyx"
    base_url = "https://api.telnyx.com"
    credential_hint = "Reconnect Telnyx under Integrations with a valid API key."

    #: How long to wait for an order to settle before giving up on resolving
    #: the number resource (the order still completes — we just record less).
    _ORDER_POLL_ATTEMPTS = 5
    _ORDER_POLL_DELAY_SECONDS = 1.5

    def validate_credentials(self) -> None:
        if not self.credentials.get("api_key"):
            raise NumberProviderError(
                f"Telnyx credentials are incomplete. {self.credential_hint}"
            )

    def auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credentials['api_key']}",
            "Content-Type": "application/json",
        }

    async def search_numbers(
        self,
        country_code: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        limit: int = 10,
    ) -> List[AvailableNumber]:
        params: Dict[str, Any] = {
            "filter[country_code]": country_code,
            "filter[limit]": limit,
            "filter[features][]": "voice",
        }
        if area_code:
            params["filter[national_destination_code]"] = area_code
        if contains:
            params["filter[phone_number][contains]"] = contains

        payload = await self._request("GET", "/v2/available_phone_numbers", params=params)

        results: List[AvailableNumber] = []
        for item in (payload or {}).get("data", []):
            features = {f.get("name") for f in item.get("features") or [] if f}
            cost = item.get("cost_information") or {}
            regions = self._regions(item.get("region_information") or [])

            results.append(
                AvailableNumber(
                    phone_number=item.get("phone_number"),
                    friendly_name=item.get("phone_number"),
                    provider=self.slug,
                    locality=regions.get("rate_center") or regions.get("locality"),
                    region=regions.get("state") or regions.get("country_code"),
                    capabilities={
                        "voice": "voice" in features,
                        "sms": "sms" in features,
                        "mms": "mms" in features,
                    },
                    monthly_cost=self._to_float(cost.get("monthly_cost")),
                    setup_cost=self._to_float(cost.get("upfront_cost")),
                    currency=cost.get("currency"),
                )
            )

        logger.info(f"[telnyx] found {len(results)} numbers in {country_code}")
        return results

    async def purchase_number(
        self,
        phone_number: str,
        voice_url: str,
        status_callback_url: Optional[str] = None,
        label: Optional[str] = None,
    ) -> PurchasedNumber:
        # 1. Make sure the TeXML application that holds the webhook exists, so
        #    the number can be attached to it as soon as the order settles.
        application_id = await self._ensure_texml_application(
            name=label or f"Voicecon {phone_number}",
            voice_url=voice_url,
            status_callback_url=status_callback_url,
        )

        # 2. Place the order.
        order = await self._request(
            "POST",
            "/v2/number_orders",
            json_body={
                "phone_numbers": [{"phone_number": phone_number}],
                "connection_id": application_id,
            },
        )
        order_data = (order or {}).get("data") or {}
        logger.info(
            f"[telnyx] ordered {phone_number} "
            f"(order {order_data.get('id')}, status {order_data.get('status')})"
        )

        # 3. Resolve the number resource so we can store a stable id and make
        #    sure it really is attached to our application.
        number_id = await self._await_number_id(phone_number)
        if number_id:
            await self._attach_application(number_id, application_id)
        else:
            logger.warning(
                f"[telnyx] order for {phone_number} has not settled yet; "
                f"the number id will be resolved on first use"
            )

        return PurchasedNumber(
            phone_number=phone_number,
            provider=self.slug,
            provider_sid=number_id,
            capabilities={"voice": True, "sms": True, "mms": False},
            provider_metadata={
                "order_id": order_data.get("id"),
                "texml_application_id": application_id,
            },
        )

    async def release_number(
        self,
        provider_sid: Optional[str],
        phone_number: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        number_id = provider_sid or await self._lookup_number_id(phone_number)
        if not number_id:
            raise NumberProviderError(
                f"Cannot release {phone_number}: it is not visible on this Telnyx account"
            )

        await self._request("DELETE", f"/v2/phone_numbers/{number_id}", expect_json=False)
        logger.info(f"[telnyx] released {phone_number or number_id}")
        return True

    async def update_voice_webhook(
        self,
        provider_sid: Optional[str],
        voice_url: str,
        phone_number: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        number_id = provider_sid or await self._lookup_number_id(phone_number)
        if not number_id:
            raise NumberProviderError(
                f"Cannot update {phone_number}: it is not visible on this Telnyx account"
            )

        application_id = await self._ensure_texml_application(
            name=f"Voicecon {phone_number or number_id}",
            voice_url=voice_url,
            status_callback_url=status_callback_url,
        )
        await self._attach_application(number_id, application_id)
        logger.info(f"[telnyx] repointed voice webhook for {phone_number or number_id}")

        metadata = dict(provider_metadata or {})
        metadata["texml_application_id"] = application_id
        return metadata

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _regions(region_information: List[Dict[str, Any]]) -> Dict[str, str]:
        """Flatten Telnyx's region list into a {region_type: region_name} map."""
        return {
            entry.get("region_type"): entry.get("region_name")
            for entry in region_information
            if entry and entry.get("region_type")
        }

    async def _lookup_number_id(self, phone_number: Optional[str]) -> Optional[str]:
        """Resolve a number's Telnyx resource id from its E.164 value."""
        if not phone_number:
            return None

        payload = await self._request(
            "GET",
            "/v2/phone_numbers",
            params={"filter[phone_number]": phone_number, "page[size]": 1},
        )
        data = (payload or {}).get("data") or []
        return data[0].get("id") if data else None

    async def _await_number_id(self, phone_number: str) -> Optional[str]:
        """Poll briefly for a freshly ordered number to appear on the account."""
        for attempt in range(self._ORDER_POLL_ATTEMPTS):
            try:
                number_id = await self._lookup_number_id(phone_number)
            except NumberProviderError as e:
                logger.warning(f"[telnyx] lookup of {phone_number} failed: {e}")
                number_id = None

            if number_id:
                return number_id
            if attempt < self._ORDER_POLL_ATTEMPTS - 1:
                await asyncio.sleep(self._ORDER_POLL_DELAY_SECONDS)

        return None

    async def _ensure_texml_application(
        self,
        name: str,
        voice_url: str,
        status_callback_url: Optional[str] = None,
    ) -> str:
        """
        Find (or create) the TeXML application that carries `voice_url`.

        Applications are matched on the webhook URL rather than the name, so a
        renamed agent still reuses its application instead of piling up new ones.
        """
        existing = await self._find_texml_application(voice_url)
        if existing:
            return existing

        body: Dict[str, Any] = {
            "friendly_name": name[:255],
            "voice_url": voice_url,
            "voice_method": "post",
            "active": True,
        }
        if status_callback_url:
            body["status_callback"] = status_callback_url
            body["status_callback_method"] = "post"

        payload = await self._request("POST", "/v2/texml_applications", json_body=body)
        application_id = ((payload or {}).get("data") or {}).get("id")

        if not application_id:
            raise NumberProviderError(
                "Telnyx did not return an application id for the new TeXML application"
            )

        logger.info(f"[telnyx] created TeXML application {application_id} -> {voice_url}")
        return application_id

    async def _find_texml_application(self, voice_url: str) -> Optional[str]:
        """Look for an existing TeXML application already pointed at `voice_url`."""
        payload = await self._request(
            "GET", "/v2/texml_applications", params={"page[size]": 250}
        )
        for app in (payload or {}).get("data", []):
            if (app or {}).get("voice_url") == voice_url:
                return app.get("id")
        return None

    async def _attach_application(self, number_id: str, application_id: str) -> None:
        """Point a number at the application that holds its voice webhook."""
        await self._request(
            "PATCH",
            f"/v2/phone_numbers/{number_id}",
            json_body={"connection_id": application_id},
        )
