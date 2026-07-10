"""
Onboarding endpoints — company information capture and onboarding status.

Flow: Sign Up -> Company Information -> Pricing -> Billing (or Free Trial) -> Dashboard
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_current_org_id, get_db
from app.models.user import User, Organization
from app.models.company import CompanyProfile
from app.models.subscription import Subscription
from app.schemas.onboarding import (
    CompanyProfileRequest,
    CompanyProfileResponse,
    OnboardingStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Return the current onboarding state so the frontend can route the user."""
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = result.scalar_one_or_none()

    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.organization_id == org_id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
        )
    )
    subscription = result.scalar_one_or_none()

    has_subscription = subscription is not None
    completed = bool(profile and profile.onboarding_completed) or has_subscription
    step = "company"
    if profile:
        step = "done" if completed else profile.onboarding_step

    return OnboardingStatusResponse(
        onboarding_completed=completed,
        step=step,
        has_company_profile=profile is not None,
        has_subscription=has_subscription,
        company=CompanyProfileResponse.model_validate(profile) if profile else None,
    )


@router.post("/company", response_model=CompanyProfileResponse)
async def save_company_profile(
    payload: CompanyProfileRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update the organization's company profile (first onboarding step).

    Also syncs the company name onto the Organization and the user record so the
    information lives alongside the rest of the account data.
    """
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = CompanyProfile(
            organization_id=org_id,
            user_id=current_user.id,
            company_name=payload.company_name,
        )
        db.add(profile)

    # Update all editable fields
    profile.company_name = payload.company_name
    profile.industry_type = payload.industry_type
    profile.company_size = payload.company_size
    profile.company_url = payload.company_url
    profile.assistant_name = payload.assistant_name
    profile.preferred_language = payload.preferred_language
    profile.assistant_instructions = payload.assistant_instructions
    profile.phone_number = payload.phone_number

    # Advance the step only if we haven't already moved further along.
    if profile.onboarding_step in ("company", None):
        profile.onboarding_step = "pricing"

    # Keep Organization + User in sync with the captured company info.
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    organization = result.scalar_one_or_none()
    if organization:
        organization.name = payload.company_name

    current_user.company_name = payload.company_name
    if payload.phone_number:
        current_user.phone_number = payload.phone_number

    await db.commit()
    await db.refresh(profile)

    return CompanyProfileResponse.model_validate(profile)
