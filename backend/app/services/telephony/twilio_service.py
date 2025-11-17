"""
Twilio Telephony Service.

Handles phone number provisioning, inbound/outbound calls, and WebSocket streaming.
"""
import logging
import hmac
import hashlib
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.models.phone_number import PhoneNumber
from app.models.agent import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class TwilioService:
    """
    Twilio telephony service.

    Handles:
    - Phone number search and provisioning
    - Inbound call webhook handling
    - Outbound call initiation
    - TwiML generation for WebSocket streaming
    - Call status tracking
    - Signature validation
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        """
        Initialize Twilio service.

        Args:
            account_sid: Twilio account SID (uses settings if not provided)
            auth_token: Twilio auth token (uses settings if not provided)
            phone_number: Default Twilio phone number (uses settings if not provided)
        """
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.phone_number = phone_number or settings.TWILIO_PHONE_NUMBER

        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials not configured")

        # Initialize Twilio client
        self.client = Client(self.account_sid, self.auth_token)

        # Request validator for webhook signature verification
        self.validator = RequestValidator(self.auth_token)

        logger.info("Initialized Twilio service")

    def validate_request(
        self,
        url: str,
        post_vars: Dict[str, str],
        signature: str
    ) -> bool:
        """
        Validate Twilio webhook request signature.

        Args:
            url: Full URL of the webhook
            post_vars: POST parameters
            signature: X-Twilio-Signature header value

        Returns:
            True if signature is valid
        """
        return self.validator.validate(url, post_vars, signature)

    async def search_phone_numbers(
        self,
        country_code: str = "US",
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search available phone numbers.

        Args:
            country_code: Country code (e.g., US, GB, CA)
            area_code: Specific area code to search
            contains: Pattern the number should contain
            limit: Maximum numbers to return

        Returns:
            List of available phone number dicts
        """
        try:
            search_params = {"limit": limit}

            if area_code:
                search_params["area_code"] = area_code
            if contains:
                search_params["contains"] = contains

            # Search for local numbers
            available_numbers = self.client.available_phone_numbers(country_code).local.list(**search_params)

            results = []
            for number in available_numbers:
                results.append({
                    "phone_number": number.phone_number,
                    "friendly_name": number.friendly_name,
                    "locality": number.locality,
                    "region": number.region,
                    "capabilities": {
                        "voice": number.capabilities.get("voice", False),
                        "SMS": number.capabilities.get("SMS", False),
                        "MMS": number.capabilities.get("MMS", False),
                    },
                })

            logger.info(f"Found {len(results)} available numbers in {country_code}")
            return results

        except TwilioRestException as e:
            logger.error(f"Error searching phone numbers: {e}")
            raise

    async def provision_phone_number(
        self,
        phone_number: str,
        agent_id: str,
        db: AsyncSession,
        webhook_base_url: str,
    ) -> PhoneNumber:
        """
        Purchase and configure a phone number.

        Args:
            phone_number: Phone number to purchase (E.164 format)
            agent_id: Agent ID to associate with number
            db: Database session
            webhook_base_url: Base URL for webhooks

        Returns:
            PhoneNumber model instance

        Raises:
            TwilioRestException: If purchase fails
        """
        try:
            # Configure webhook URLs
            voice_url = urljoin(webhook_base_url, f"/api/v1/telephony/twilio/voice/{agent_id}")
            status_callback_url = urljoin(webhook_base_url, "/api/v1/telephony/twilio/status")

            # Purchase number
            incoming_phone_number = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                voice_url=voice_url,
                voice_method="POST",
                status_callback=status_callback_url,
                status_callback_method="POST",
            )

            logger.info(f"Provisioned phone number: {phone_number} (SID: {incoming_phone_number.sid})")

            # Get agent to populate user_id and organization_id
            agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")

            # Create database record
            phone_number_record = PhoneNumber(
                phone_number=phone_number,
                provider="twilio",
                provider_sid=incoming_phone_number.sid,
                agent_id=agent_id,
                user_id=agent.user_id,
                organization_id=agent.organization_id,
                capabilities={
                    "voice": True,
                    "sms": incoming_phone_number.capabilities.get("sms", False),
                    "mms": incoming_phone_number.capabilities.get("mms", False),
                },
                status="active",
            )

            db.add(phone_number_record)
            await db.commit()
            await db.refresh(phone_number_record)

            return phone_number_record

        except TwilioRestException as e:
            logger.error(f"Error provisioning phone number: {e}")
            await db.rollback()
            raise

    async def release_phone_number(self, phone_number_sid: str) -> bool:
        """
        Release (delete) a phone number.

        Args:
            phone_number_sid: Twilio phone number SID

        Returns:
            True if successful
        """
        try:
            self.client.incoming_phone_numbers(phone_number_sid).delete()
            logger.info(f"Released phone number: {phone_number_sid}")
            return True

        except TwilioRestException as e:
            logger.error(f"Error releasing phone number: {e}")
            raise

    def generate_twiml_for_websocket(
        self,
        websocket_url: str,
        agent_name: Optional[str] = None,
    ) -> str:
        """
        Generate TwiML response for WebSocket streaming.

        Args:
            websocket_url: WebSocket URL for media streaming
            agent_name: Optional agent name for greeting

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Optional greeting
        if agent_name:
            response.say(f"Hello, connecting you with {agent_name}")

        # Start WebSocket stream
        connect = Connect()
        stream = Stream(url=websocket_url)
        connect.append(stream)
        response.append(connect)

        return str(response)

    def generate_twiml_error(self, message: str = "We're sorry, an error occurred") -> str:
        """
        Generate TwiML error response.

        Args:
            message: Error message to speak

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        response.say(message)
        response.hangup()

        return str(response)

    async def make_outbound_call(
        self,
        to_number: str,
        from_number: str,
        agent_id: str,
        webhook_base_url: str,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call.

        Args:
            to_number: Destination phone number
            from_number: Twilio number to call from
            agent_id: Agent ID handling the call
            webhook_base_url: Base URL for webhooks

        Returns:
            Call details dict
        """
        try:
            # Generate TwiML URL for the call
            twiml_url = urljoin(webhook_base_url, f"/api/v1/telephony/twilio/voice/{agent_id}")
            status_callback_url = urljoin(webhook_base_url, "/api/v1/telephony/twilio/status")

            # Make call
            call = self.client.calls.create(
                to=to_number,
                from_=from_number,
                url=twiml_url,
                method="POST",
                status_callback=status_callback_url,
                status_callback_method="POST",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
            )

            logger.info(f"Initiated outbound call: {call.sid} to {to_number}")

            return {
                "call_sid": call.sid,
                "to": call.to,
                "from": call.from_,
                "status": call.status,
                "direction": call.direction,
            }

        except TwilioRestException as e:
            logger.error(f"Error making outbound call: {e}")
            raise

    async def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """
        Get details for a specific call.

        Args:
            call_sid: Twilio call SID

        Returns:
            Call details dict
        """
        try:
            call = self.client.calls(call_sid).fetch()

            return {
                "call_sid": call.sid,
                "from": call.from_,
                "to": call.to,
                "status": call.status,
                "direction": call.direction,
                "start_time": call.start_time,
                "end_time": call.end_time,
                "duration": call.duration,
                "price": float(call.price) if call.price else None,
                "price_unit": call.price_unit,
            }

        except TwilioRestException as e:
            logger.error(f"Error fetching call details: {e}")
            raise

    async def update_phone_number_webhook(
        self,
        phone_number_sid: str,
        voice_url: str,
        status_callback_url: Optional[str] = None,
    ) -> bool:
        """
        Update webhook URLs for a phone number.

        Args:
            phone_number_sid: Twilio phone number SID
            voice_url: New voice webhook URL
            status_callback_url: Optional status callback URL

        Returns:
            True if successful
        """
        try:
            update_params = {
                "voice_url": voice_url,
                "voice_method": "POST",
            }

            if status_callback_url:
                update_params["status_callback"] = status_callback_url
                update_params["status_callback_method"] = "POST"

            self.client.incoming_phone_numbers(phone_number_sid).update(**update_params)

            logger.info(f"Updated webhooks for phone number: {phone_number_sid}")
            return True

        except TwilioRestException as e:
            logger.error(f"Error updating phone number webhook: {e}")
            raise

    async def get_call_recordings(self, call_sid: str) -> List[Dict[str, Any]]:
        """
        Get recordings for a call.

        Args:
            call_sid: Twilio call SID

        Returns:
            List of recording dicts
        """
        try:
            recordings = self.client.recordings.list(call_sid=call_sid)

            results = []
            for recording in recordings:
                results.append({
                    "recording_sid": recording.sid,
                    "duration": recording.duration,
                    "url": f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}",
                    "date_created": recording.date_created,
                })

            return results

        except TwilioRestException as e:
            logger.error(f"Error fetching recordings: {e}")
            raise


# Global Twilio service instance
_twilio_service: Optional[TwilioService] = None


def get_twilio_service() -> TwilioService:
    """
    Get global Twilio service instance (singleton).

    Returns:
        TwilioService instance
    """
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service
