"""
Pydantic schemas for the post-signup onboarding flow.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class OnboardingStatusResponse(BaseModel):
    """Aggregate onboarding status for routing decisions."""

    onboarding_completed: bool
    step: str  # company | pricing | billing | done
    has_company_profile: bool
    has_subscription: bool
    company: Optional[CompanyProfileResponse] = None
