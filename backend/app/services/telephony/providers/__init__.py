"""
Telephony number providers.

Carrier-specific implementations of `NumberProvider`, used by the phone-number
endpoints to search, buy, configure and release numbers without caring which
carrier a given number came from.
"""
from app.services.telephony.providers.base import (
    AvailableNumber,
    NumberProvider,
    NumberProviderError,
    PurchasedNumber,
)
from app.services.telephony.providers.telnyx_provider import TelnyxNumberProvider
from app.services.telephony.providers.twilio_provider import TwilioNumberProvider

#: Carrier slug -> provider class. The slugs match the integration connector
#: slugs in `integration_connectors`, which is how a connected integration is
#: mapped onto the carrier that can serve it.
PROVIDER_CLASSES = {
    TwilioNumberProvider.slug: TwilioNumberProvider,
    TelnyxNumberProvider.slug: TelnyxNumberProvider,
}

#: Connector slugs that can sell phone numbers.
TELEPHONY_PROVIDER_SLUGS = tuple(PROVIDER_CLASSES.keys())

__all__ = [
    "AvailableNumber",
    "NumberProvider",
    "NumberProviderError",
    "PurchasedNumber",
    "TwilioNumberProvider",
    "TelnyxNumberProvider",
    "PROVIDER_CLASSES",
    "TELEPHONY_PROVIDER_SLUGS",
]
