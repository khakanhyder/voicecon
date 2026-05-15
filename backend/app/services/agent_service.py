"""
Agent Service.

Handles agent creation, configuration, testing, and templates.
"""
import logging
import uuid
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.agent import Agent, AgentFunction
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentFunctionCreate,
    AgentFunctionUpdate,
    AgentTemplate,
)
from app.core.security_fixed import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)


# Predefined agent templates
AGENT_TEMPLATES = [
    {
        "id": "customer-support",
        "name": "Customer Support Agent",
        "description": "Handles customer inquiries, complaints, and general support",
        "category": "Support",
        "thumbnail_url": None,
        "use_count": 0,
        "template_data": {
            "name": "Customer Support",
            "description": "Friendly and helpful customer support agent",
            "system_prompt": """You are a professional customer support agent. Your role is to:
- Listen carefully to customer concerns
- Provide clear and helpful solutions
- Remain patient and empathetic
- Escalate to human support when needed
- Always maintain a positive, professional tone

Guidelines:
- Be concise but thorough
- Ask clarifying questions
- Confirm understanding before providing solutions
- Thank customers for their patience""",
            "first_message": "Hello! Thank you for contacting support. How can I help you today?",
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "rachel",
                "speed": 1.0
            },
            "settings": {
                "interrupt_enabled": True,
                "max_call_duration": 1800
            }
        }
    },
    {
        "id": "sales-assistant",
        "name": "Sales Assistant",
        "description": "Engages prospects, qualifies leads, and schedules demos",
        "category": "Sales",
        "thumbnail_url": None,
        "use_count": 0,
        "template_data": {
            "name": "Sales Assistant",
            "description": "Engaging sales assistant for lead qualification",
            "system_prompt": """You are a professional sales assistant. Your goals are to:
- Understand customer needs and pain points
- Explain product benefits clearly
- Qualify leads based on budget, authority, need, timeline
- Schedule demos or meetings
- Handle objections professionally

Guidelines:
- Build rapport quickly
- Listen more than you talk
- Use open-ended questions
- Focus on value, not features
- Be enthusiastic but not pushy""",
            "first_message": "Hi there! Thanks for your interest. I'd love to learn more about your needs. What brings you here today?",
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.8,
                "max_tokens": 600
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "adam",
                "speed": 1.1
            },
            "settings": {
                "interrupt_enabled": True,
                "max_call_duration": 2400
            }
        }
    },
    {
        "id": "appointment-scheduler",
        "name": "Appointment Scheduler",
        "description": "Books appointments, manages calendar, sends reminders",
        "category": "Scheduling",
        "thumbnail_url": None,
        "use_count": 0,
        "template_data": {
            "name": "Appointment Scheduler",
            "description": "Efficient appointment booking assistant",
            "system_prompt": """You are an appointment scheduling assistant. Your tasks:
- Collect necessary information (name, contact, reason)
- Check availability
- Book appointments in the calendar
- Confirm details
- Send confirmation and reminders

Guidelines:
- Be efficient and clear
- Double-check all details
- Offer alternative times if needed
- Explain the booking process
- Confirm via phone and email""",
            "first_message": "Hello! I can help you schedule an appointment. May I have your name please?",
            "llm": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "temperature": 0.5,
                "max_tokens": 400
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "bella",
                "speed": 1.0
            },
            "settings": {
                "interrupt_enabled": True,
                "max_call_duration": 900
            }
        }
    },
    {
        "id": "technical-support",
        "name": "Technical Support Agent",
        "description": "Provides technical troubleshooting and IT support",
        "category": "Support",
        "thumbnail_url": None,
        "use_count": 0,
        "template_data": {
            "name": "Technical Support",
            "description": "Expert technical support for troubleshooting",
            "system_prompt": """You are a technical support specialist. Your responsibilities:
- Diagnose technical issues systematically
- Provide step-by-step troubleshooting
- Explain technical concepts clearly
- Document solutions
- Escalate complex issues when needed

Guidelines:
- Ask diagnostic questions
- Use simple, non-technical language
- Confirm each step is completed
- Be patient with non-technical users
- Provide clear next steps""",
            "first_message": "Hello! I'm here to help with your technical issue. Can you describe what's happening?",
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.6,
                "max_tokens": 800
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "josh",
                "speed": 0.95
            },
            "settings": {
                "interrupt_enabled": True,
                "max_call_duration": 2400
            }
        }
    },
    {
        "id": "survey-interviewer",
        "name": "Survey Interviewer",
        "description": "Conducts surveys, collects feedback, gathers data",
        "category": "Research",
        "thumbnail_url": None,
        "use_count": 0,
        "template_data": {
            "name": "Survey Interviewer",
            "description": "Professional survey and feedback collector",
            "system_prompt": """You are a survey interviewer. Your role:
- Ask survey questions clearly
- Record responses accurately
- Stay neutral and unbiased
- Encourage honest feedback
- Thank participants

Guidelines:
- Read questions exactly as written
- Don't lead or influence answers
- Be patient with responses
- Clarify questions if needed
- Keep surveys on track""",
            "first_message": "Hello! Thank you for participating in our survey. This will take about 5 minutes. Shall we begin?",
            "llm": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "temperature": 0.4,
                "max_tokens": 300
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "elli",
                "speed": 1.0
            },
            "settings": {
                "interrupt_enabled": False,
                "max_call_duration": 600
            }
        }
    }
]


class AgentService:
    """
    Service for agent management.

    Features:
    - Create/update/delete agents
    - Agent versioning
    - Agent testing
    - Template management
    - Configuration validation
    """

    async def create_agent(
        self,
        agent_data: AgentCreate,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
    ) -> Agent:
        """
        Create a new agent.

        Args:
            agent_data: Agent creation data
            user_id: User ID
            organization_id: Organization ID
            db: Database session

        Returns:
            Created agent
        """
        try:
            # Create agent record
            agent = Agent(
                user_id=user_id,
                organization_id=organization_id,
                name=agent_data.name,
                description=agent_data.description,
                type=agent_data.type,
                system_prompt=agent_data.system_prompt,
                first_message=agent_data.first_message,
                # LLM config
                llm_provider=agent_data.llm.provider,
                llm_model=agent_data.llm.model,
                llm_temperature=agent_data.llm.temperature,
                llm_max_tokens=agent_data.llm.max_tokens,
                # Voice config
                tts_provider=agent_data.voice.provider,
                tts_voice_id=agent_data.voice.voice_id,
                tts_speed=agent_data.voice.speed,
                tts_pitch=agent_data.voice.pitch,
                # STT config
                stt_provider=agent_data.stt.provider,
                stt_language=agent_data.stt.language,
                stt_model=agent_data.stt.model,
                # Conversation settings
                interrupt_enabled=agent_data.settings.interrupt_enabled,
                interrupt_sensitivity=agent_data.settings.interrupt_sensitivity,
                silence_timeout=agent_data.settings.silence_timeout,
                max_call_duration=agent_data.settings.max_call_duration,
                end_call_phrases=agent_data.settings.end_call_phrases,
                # Advanced features
                sentiment_analysis_enabled=agent_data.advanced.sentiment_analysis_enabled,
                emotion_detection_enabled=agent_data.advanced.emotion_detection_enabled,
                background_noise_reduction=agent_data.advanced.background_noise_reduction,
                knowledge_base_enabled=agent_data.advanced.knowledge_base_enabled,
                knowledge_base_config=agent_data.advanced.knowledge_base_config,
                # Metadata
                tags=agent_data.tags,
                is_public=agent_data.is_public,
            )

            # Encrypt API keys if provided
            if agent_data.llm.api_key:
                agent.llm_api_key_encrypted = encrypt_value(agent_data.llm.api_key)

            if agent_data.voice.api_key:
                agent.tts_api_key_encrypted = encrypt_value(agent_data.voice.api_key)

            if agent_data.stt.api_key:
                agent.stt_api_key_encrypted = encrypt_value(agent_data.stt.api_key)

            db.add(agent)
            await db.commit()
            await db.refresh(agent)

            logger.info(f"Created agent: {agent.id} - {agent.name}")

            return agent

        except Exception as e:
            logger.error(f"Error creating agent: {e}", exc_info=True)
            await db.rollback()
            raise

    async def update_agent(
        self,
        agent_id: uuid.UUID,
        agent_data: AgentUpdate,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[Agent]:
        """
        Update an existing agent.

        Args:
            agent_id: Agent ID
            agent_data: Update data
            user_id: User ID
            db: Database session

        Returns:
            Updated agent or None
        """
        try:
            # Get agent
            result = await db.execute(
                select(Agent).where(
                    and_(
                        Agent.id == agent_id,
                        Agent.user_id == user_id,
                    )
                )
            )
            agent = result.scalar_one_or_none()

            if not agent:
                return None

            # Update fields
            if agent_data.name is not None:
                agent.name = agent_data.name

            if agent_data.description is not None:
                agent.description = agent_data.description

            if agent_data.system_prompt is not None:
                agent.system_prompt = agent_data.system_prompt

            if agent_data.first_message is not None:
                agent.first_message = agent_data.first_message

            if agent_data.llm:
                agent.llm_provider = agent_data.llm.provider
                agent.llm_model = agent_data.llm.model
                agent.llm_temperature = agent_data.llm.temperature
                agent.llm_max_tokens = agent_data.llm.max_tokens
                if agent_data.llm.api_key:
                    agent.llm_api_key_encrypted = encrypt_value(agent_data.llm.api_key)

            if agent_data.voice:
                agent.tts_provider = agent_data.voice.provider
                agent.tts_voice_id = agent_data.voice.voice_id
                agent.tts_speed = agent_data.voice.speed
                agent.tts_pitch = agent_data.voice.pitch
                if agent_data.voice.api_key:
                    agent.tts_api_key_encrypted = encrypt_value(agent_data.voice.api_key)

            if agent_data.stt:
                agent.stt_provider = agent_data.stt.provider
                agent.stt_language = agent_data.stt.language
                agent.stt_model = agent_data.stt.model
                if agent_data.stt.api_key:
                    agent.stt_api_key_encrypted = encrypt_value(agent_data.stt.api_key)

            if agent_data.settings:
                agent.interrupt_enabled = agent_data.settings.interrupt_enabled
                agent.interrupt_sensitivity = agent_data.settings.interrupt_sensitivity
                agent.silence_timeout = agent_data.settings.silence_timeout
                agent.max_call_duration = agent_data.settings.max_call_duration
                agent.end_call_phrases = agent_data.settings.end_call_phrases

            if agent_data.advanced:
                agent.sentiment_analysis_enabled = agent_data.advanced.sentiment_analysis_enabled
                agent.emotion_detection_enabled = agent_data.advanced.emotion_detection_enabled
                agent.background_noise_reduction = agent_data.advanced.background_noise_reduction
                agent.knowledge_base_enabled = agent_data.advanced.knowledge_base_enabled
                agent.knowledge_base_config = agent_data.advanced.knowledge_base_config

            if agent_data.tags is not None:
                agent.tags = agent_data.tags

            if agent_data.is_active is not None:
                agent.is_active = agent_data.is_active

            if agent_data.is_public is not None:
                agent.is_public = agent_data.is_public

            # Increment version
            agent.version += 1

            await db.commit()
            await db.refresh(agent)

            logger.info(f"Updated agent: {agent.id} (version {agent.version})")

            return agent

        except Exception as e:
            logger.error(f"Error updating agent: {e}", exc_info=True)
            await db.rollback()
            raise

    async def delete_agent(
        self,
        agent_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete an agent.

        Args:
            agent_id: Agent ID
            user_id: User ID
            db: Database session
            soft_delete: Use soft delete (set deleted_at)

        Returns:
            True if deleted
        """
        try:
            result = await db.execute(
                select(Agent).where(
                    and_(
                        Agent.id == agent_id,
                        Agent.user_id == user_id,
                    )
                )
            )
            agent = result.scalar_one_or_none()

            if not agent:
                return False

            if soft_delete:
                agent.deleted_at = datetime.utcnow()
                agent.is_active = False
            else:
                await db.delete(agent)

            await db.commit()

            logger.info(f"Deleted agent: {agent_id} (soft={soft_delete})")

            return True

        except Exception as e:
            logger.error(f"Error deleting agent: {e}", exc_info=True)
            await db.rollback()
            raise

    async def clone_agent(
        self,
        agent_id: uuid.UUID,
        new_name: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        include_functions: bool = True,
    ) -> Optional[Agent]:
        """
        Clone an existing agent.

        Args:
            agent_id: Source agent ID
            new_name: Name for cloned agent
            user_id: User ID
            organization_id: Organization ID
            db: Database session
            include_functions: Clone functions too

        Returns:
            Cloned agent or None
        """
        try:
            # Get source agent
            result = await db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            source = result.scalar_one_or_none()

            if not source:
                return None

            # Create clone
            clone = Agent(
                user_id=user_id,
                organization_id=organization_id,
                name=new_name,
                description=f"Cloned from: {source.name}",
                type=source.type,
                system_prompt=source.system_prompt,
                first_message=source.first_message,
                llm_provider=source.llm_provider,
                llm_model=source.llm_model,
                llm_temperature=source.llm_temperature,
                llm_max_tokens=source.llm_max_tokens,
                tts_provider=source.tts_provider,
                tts_voice_id=source.tts_voice_id,
                tts_speed=source.tts_speed,
                tts_pitch=source.tts_pitch,
                stt_provider=source.stt_provider,
                stt_language=source.stt_language,
                stt_model=source.stt_model,
                interrupt_enabled=source.interrupt_enabled,
                interrupt_sensitivity=source.interrupt_sensitivity,
                silence_timeout=source.silence_timeout,
                max_call_duration=source.max_call_duration,
                end_call_phrases=source.end_call_phrases,
                sentiment_analysis_enabled=source.sentiment_analysis_enabled,
                emotion_detection_enabled=source.emotion_detection_enabled,
                background_noise_reduction=source.background_noise_reduction,
                knowledge_base_enabled=source.knowledge_base_enabled,
                knowledge_base_config=source.knowledge_base_config,
                tags=source.tags,
            )

            db.add(clone)
            await db.commit()
            await db.refresh(clone)

            # Clone functions if requested
            if include_functions:
                for func in source.functions:
                    cloned_func = AgentFunction(
                        agent_id=clone.id,
                        name=func.name,
                        description=func.description,
                        parameters=func.parameters,
                        webhook_url=func.webhook_url,
                        http_method=func.http_method,
                        headers=func.headers,
                        timeout=func.timeout,
                        retry_count=func.retry_count,
                        is_active=func.is_active,
                        execution_order=func.execution_order,
                    )
                    db.add(cloned_func)

                await db.commit()

            logger.info(f"Cloned agent: {source.id} -> {clone.id}")

            return clone

        except Exception as e:
            logger.error(f"Error cloning agent: {e}", exc_info=True)
            await db.rollback()
            raise

    def get_templates(self) -> List[AgentTemplate]:
        """
        Get all agent templates.

        Returns:
            List of templates
        """
        return [AgentTemplate(**t) for t in AGENT_TEMPLATES]

    async def create_from_template(
        self,
        template_id: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        db: AsyncSession,
        custom_name: Optional[str] = None,
    ) -> Optional[Agent]:
        """
        Create agent from template.

        Args:
            template_id: Template ID
            user_id: User ID
            organization_id: Organization ID
            db: Database session
            custom_name: Optional custom name

        Returns:
            Created agent or None
        """
        # Find template
        template = next((t for t in AGENT_TEMPLATES if t["id"] == template_id), None)

        if not template:
            return None

        # Create agent from template
        agent_data = AgentCreate(**template["template_data"])

        if custom_name:
            agent_data.name = custom_name

        agent = await self.create_agent(
            agent_data=agent_data,
            user_id=user_id,
            organization_id=organization_id,
            db=db,
        )

        logger.info(f"Created agent from template: {template_id} -> {agent.id}")

        return agent


# Global agent service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """
    Get global agent service instance (singleton).

    Returns:
        AgentService instance
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
