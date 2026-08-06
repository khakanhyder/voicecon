"""
Onboarding endpoints — company information capture and onboarding status.

Flow: Sign Up -> Company Information -> Pricing -> Billing (or Free Trial) -> Dashboard

The company step can also claim a phone number. It buys on the same accounts as
the dashboard (Voicecon's shared Twilio by default, or the user's own carrier if
they have already connected one) and attaches the number to the assistant being
described on that screen, so an inbound call works the moment onboarding ends.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perms
from app.core.dependencies import (
    get_current_active_user,
    get_current_org_id,
    get_db,
    require_permission,
)
from app.core.entitlement_guard import require_entitlement
from app.models.agent import Agent
from app.models.user import User, Organization
from app.models.call import PhoneNumber
from app.models.company import CompanyProfile
from app.models.subscription import LIVE_STATUSES, Subscription
from app.schemas.onboarding import (
    ClaimPhoneNumberRequest,
    ClaimPhoneNumberResponse,
    CompanyProfileRequest,
    CompanyProfileResponse,
    OnboardingStatusResponse,
)
from app.services.telephony.number_provisioning import (
    NumberNotRecordedError,
    WebhookUrlNotConfigured,
    purchase_number_for_agent,
)
from app.services.telephony.provider_registry import (
    AmbiguousProviderError,
    NoTelephonyProviderError,
)
from app.services.billing import catalog
from app.services.telephony.providers import NumberProviderError

logger = logging.getLogger(__name__)

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
                Subscription.status.in_(LIVE_STATUSES),
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


@router.post(
    "/company",
    response_model=CompanyProfileResponse,
    dependencies=[Depends(require_permission(perms.WORKSPACE_MANAGE))],
)
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


async def _assistant_agent(
    db: AsyncSession,
    user: User,
    org_id: uuid.UUID,
    assistant_name: str | None,
    assistant_instructions: str | None,
) -> tuple[Agent, bool]:
    """
    The agent that should answer calls on a number claimed during onboarding.

    A number is only reachable through an agent, and a user in onboarding
    usually has none yet — so the assistant they are describing on screen is
    created here. Users who already have an agent (re-running onboarding, or
    invited into an existing account) keep their first one rather than
    accumulating duplicates.
    """
    existing = await db.execute(
        select(Agent)
        .where(Agent.organization_id == org_id, Agent.is_active.is_(True))
        .order_by(Agent.created_at.asc())
        .limit(1)
    )
    agent = existing.scalar_one_or_none()
    if agent:
        return agent, False

    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = result.scalar_one_or_none()

    name = (
        assistant_name
        or (profile.assistant_name if profile else None)
        or (profile.company_name if profile else None)
        or "AI Assistant"
    )
    instructions = assistant_instructions or (
        profile.assistant_instructions if profile else None
    )

    agent = Agent(
        user_id=user.id,
        organization_id=org_id,
        name=name[:255],
        description="Created during onboarding",
        system_prompt=instructions
        or "You are a helpful voice assistant. Answer calls politely and concisely.",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    logger.info(f"Created onboarding assistant {agent.id} for user {user.id}")
    return agent, True


@router.post(
    "/phone-number",
    response_model=ClaimPhoneNumberResponse,
    dependencies=[
        Depends(require_permission(perms.PHONE_NUMBERS_WRITE)),
        # Buying a number costs real money at the carrier, and this endpoint is
        # reachable before onboarding finishes — without a plan or trial behind
        # it, anyone who signs up could provision numbers on our account.
        Depends(require_entitlement(limit=catalog.LIMIT_PHONE_NUMBERS)),
    ],
)
async def claim_phone_number(
    payload: ClaimPhoneNumberRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Buy a phone number during onboarding and attach it to the user's assistant.

    The account is chosen the same way as on the Phone Numbers page: the user's
    own Twilio when they have connected one, otherwise Voicecon's shared Twilio.
    Numbers are searched through `GET /api/v1/phone-numbers/search`, which the
    onboarding screen calls directly.
    """
    existing = await db.execute(
        select(PhoneNumber).where(PhoneNumber.phone_number == payload.phone_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already provisioned")

    agent, agent_created = await _assistant_agent(
        db, current_user, org_id, payload.assistant_name, payload.assistant_instructions
    )

    try:
        record, resolved = await purchase_number_for_agent(
            db,
            current_user,
            agent,
            phone_number=payload.phone_number,
            provider=payload.provider,
            connection_id=payload.connection_id,
            country_code=payload.country_code,
            area_code=payload.area_code,
            monthly_cost=payload.monthly_cost,
        )
    except (NoTelephonyProviderError, AmbiguousProviderError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NumberProviderError as e:
        logger.error(f"Onboarding purchase failed for {payload.phone_number}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except (WebhookUrlNotConfigured, NumberNotRecordedError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error claiming phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to claim phone number: {str(e)}"
        )

    # Show the claimed number back on the company form when it reloads.
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.phone_number = record.phone_number
        await db.commit()

    return ClaimPhoneNumberResponse(
        phone_number_id=record.id,
        phone_number=record.phone_number,
        provider=record.provider,
        source=resolved.option.source,
        account_name=resolved.option.connection_name or resolved.option.name,
        agent_id=agent.id,
        agent_name=agent.name,
        agent_created=agent_created,
    )
