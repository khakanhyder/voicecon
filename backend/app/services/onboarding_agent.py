"""
The first agent, created from what the user typed during onboarding.

The Company Information step asks for an assistant's name and what it should
do. Until now those were stored on the company profile and nothing else, so a
person who had just described their assistant landed on an empty Agents page.
Once the workspace has a plan (a trial or a paid subscription — an agent cannot
exist before that), an agent is created from those two answers.

Only when both were actually given: a name with nothing to say, or a
description with nothing to call it, is not an agent worth inventing.
"""
import logging
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.company import CompanyProfile
from app.schemas.agent import AgentCreate, STTConfig
from app.services.agent_service import AgentService
from app.services.voice import languages

logger = logging.getLogger(__name__)

#: The greeting the "New Agent" form pre-fills, so both routes start the same.
DEFAULT_FIRST_MESSAGE = "Hello! How can I help you today?"

#: Onboarding's language names → the speech-recognition codes the agent form uses.
STT_LANGUAGE_CODES = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "arabic": "ar",
    "hindi": "hi",
    "portuguese": "pt",
}


async def create_agent_from_onboarding(
    db: AsyncSession, profile: CompanyProfile
) -> Optional[Agent]:
    """
    Create the workspace's first agent from its company profile.

    Returns the agent, or None when nothing should be created: the user gave no
    assistant details, or the workspace already has an agent (never a second one,
    and never past a plan's agent limit). Does not commit — it runs inside the
    transaction that starts the trial or records the payment — and a failure
    here must never undo that, so errors are logged and swallowed.
    """
    name = (profile.assistant_name or "").strip()
    instructions = (profile.assistant_instructions or "").strip()
    if not name or not instructions:
        return None

    try:
        existing = (
            await db.execute(
                select(func.count(Agent.id)).where(
                    Agent.organization_id == profile.organization_id,
                    Agent.deleted_at.is_(None),
                )
            )
        ).scalar() or 0
        if existing:
            logger.info(
                "Not creating an onboarding agent for %s: it already has %d",
                profile.organization_id, existing,
            )
            return None

        language = STT_LANGUAGE_CODES.get(
            (profile.preferred_language or "").strip().lower(), "en"
        )
        try:
            data = AgentCreate(
                name=name,
                system_prompt=instructions,
                # The form's default greeting, in the language the agent speaks.
                first_message=languages.spoken_greeting(DEFAULT_FIRST_MESSAGE, language),
                stt=STTConfig(language=language),
            )
        except ValidationError as exc:
            logger.warning("Onboarding agent details were not usable: %s", exc)
            return None

        agent = AgentService.build_agent(data, profile.user_id, profile.organization_id)
        # A savepoint: if the insert fails, only the agent is rolled back, not
        # the trial or payment this is part of.
        async with db.begin_nested():
            db.add(agent)
            await db.flush()
        logger.info(
            "Created agent %s (%s) from onboarding for organization %s",
            agent.id, agent.name, profile.organization_id,
        )
        return agent
    except Exception:  # noqa: BLE001 - never let this break the plan activation
        logger.exception(
            "Could not create the onboarding agent for organization %s",
            profile.organization_id,
        )
        return None
