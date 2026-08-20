"""
Pydantic schemas for the post-signup onboarding flow.
"""
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: A hostname label: alphanumeric, inner hyphens allowed.
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
#: A public TLD is alphabetic — this is what rules out "acme.123" and bare words.
_TLD = re.compile(r"^[a-z]{2,}$")


class CompanyProfileRequest(BaseModel):
    """Company Information form payload (Figma "Company Information" screen)."""

    company_name: str = Field(..., min_length=1, max_length=255)
    industry_type: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    company_url: Optional[str] = Field(None, max_length=255)
    assistant_name: Optional[str] = Field(None, max_length=255)
    preferred_language: str = Field("English", max_length=50)
    assistant_instructions: Optional[str] = None
    phone_number: Optional[str] = Field(None, max_length=50)

    @field_validator("company_name")
    @classmethod
    def _company_name_is_not_blank(cls, value: str) -> str:
        """
        Reject a name that is only whitespace.

        `min_length=1` counts characters, so a single space satisfied it. That
        mattered more than it looks: this endpoint copies the value onto the
        Organization, so a spacebar in the company field renamed the whole
        workspace to nothing and left the switcher and page headers blank. The
        form already trimmed before checking, so only a direct API call — or a
        pasted value — could reach it.
        """
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company name cannot be blank.")
        return cleaned

    @field_validator(
        "industry_type",
        "company_size",
        "company_url",
        "assistant_name",
        "phone_number",
        mode="before",
    )
    @classmethod
    def _blank_optional_is_none(cls, value):
        """
        Store an omitted optional field as NULL rather than "".

        An untouched input posts an empty string, which otherwise reads back as
        a value that is present but empty — so the UI shows a filled-in field
        containing nothing instead of its placeholder.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("company_url")
    @classmethod
    def _company_url_is_a_website(cls, value: Optional[str]) -> Optional[str]:
        """
        Reject a "website" that is not one, and store it with a scheme.

        The field is optional, but when it is filled in it ends up on the
        company profile and is rendered as a link. Without this, a bare word
        typed into the onboarding form ("dcsdcs") saved happily and only turned
        up later as a link that goes nowhere. Accepts what people type —
        ``acme.com``, ``www.acme.com`` — and normalizes to ``https://acme.com``.
        Only http(s) is allowed, so a stored ``javascript:`` URL can never be
        rendered into an href.
        """
        if value is None:
            return None

        candidate = value if "://" in value else f"https://{value}"
        parsed = urlparse(candidate)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("Website must start with http:// or https://")

        host = (parsed.hostname or "").lower()
        labels = host.split(".")
        if (
            len(labels) < 2
            or not all(_HOST_LABEL.match(label) for label in labels)
            or not _TLD.match(labels[-1])
        ):
            raise ValueError("Enter a valid website, e.g. www.acme.com")

        # A trailing slash on a bare domain is noise in a field the user reads back.
        path = "" if parsed.path == "/" else parsed.path
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        rebuilt = f"{parsed.scheme}://{netloc}{path}"
        if parsed.query:
            rebuilt += f"?{parsed.query}"
        if parsed.fragment:
            rebuilt += f"#{parsed.fragment}"
        return rebuilt


class CompanyProfileResponse(BaseModel):
    """Company profile as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    company_name: str
    industry_type: Optional[str] = None
    company_size: Optional[str] = None
    company_url: Optional[str] = None
    assistant_name: Optional[str] = None
    preferred_language: str
    assistant_instructions: Optional[str] = None
    phone_number: Optional[str] = None
    onboarding_completed: bool
    onboarding_step: str
    created_at: datetime
    updated_at: datetime


class ClaimPhoneNumberRequest(BaseModel):
    """Claim one of the numbers returned by ``/phone-numbers/search``."""

    phone_number: str = Field(..., max_length=50, description="E.164 number to buy")
    provider: Optional[str] = Field(
        None, description="Carrier to buy from. Defaults to Twilio."
    )
    connection_id: Optional[str] = Field(
        None,
        description=(
            "Account to buy on — a carrier connection id, or 'platform:twilio' "
            "for Voicecon's shared account. Defaults to the user's own Twilio "
            "when connected, otherwise the shared account."
        ),
    )
    country_code: Optional[str] = Field(None, max_length=10)
    area_code: Optional[str] = Field(None, max_length=10)
    monthly_cost: Optional[float] = Field(None, ge=0)
    # Taken from the on-screen form: the profile is not saved until the user
    # presses Continue, so the assistant details are not in the database yet.
    assistant_name: Optional[str] = Field(None, max_length=255)
    assistant_instructions: Optional[str] = None


class ClaimPhoneNumberResponse(BaseModel):
    """The number that was bought and the agent that will answer it."""

    phone_number_id: UUID
    phone_number: str
    provider: str
    source: str = Field(description="'platform' (Voicecon's account) or 'integration'")
    account_name: str
    agent_id: UUID
    agent_name: str
    agent_created: bool


class OnboardingStatusResponse(BaseModel):
    """Aggregate onboarding status for routing decisions."""

    onboarding_completed: bool
    step: str  # company | pricing | billing | done
    has_company_profile: bool
    has_subscription: bool
    company: Optional[CompanyProfileResponse] = None
