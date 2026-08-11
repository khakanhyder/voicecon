"""
Unit tests for AgentService.

Two things carry most of the weight here:

1. **Workspace isolation.** `update`, `delete` and `clone` all scope their lookup
   by `organization_id`. If any of them stopped doing that, a bare agent id —
   which the API takes straight from the URL — would be enough to read, edit or
   copy another tenant's agent. Each of those methods therefore has a
   cross-workspace test alongside its happy path.
2. **Config mapping.** `AgentCreate` nests config under `llm`/`voice`/`stt`/
   `settings`/`advanced`, while the table stores flat `llm_*`/`tts_*`/`stt_*`
   columns. That hand-written mapping is easy to get wrong and silently drops
   settings, so it is asserted field by field.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.agent import Agent, AgentFunction
from app.schemas.agent import (
    AdvancedFeatures,
    AgentCreate,
    AgentUpdate,
    ConversationSettings,
    LLMConfig,
    STTConfig,
    VoiceConfig,
)
from app.services.agent_service import AGENT_TEMPLATES, get_agent_service


def _agent_create(**overrides) -> AgentCreate:
    """An AgentCreate with every nested section populated."""
    payload = {
        "name": "Test Agent",
        "description": "A test agent",
        "system_prompt": "You are a helpful assistant.",
        "first_message": "Hello! How can I help you?",
        "llm": LLMConfig(provider="openai", model="gpt-4", temperature=0.5, max_tokens=800),
        "voice": VoiceConfig(provider="elevenlabs", voice_id="rachel", speed=1.2, pitch=0.9),
        "stt": STTConfig(provider="deepgram", language="en", model="nova-2"),
        "settings": ConversationSettings(
            interrupt_enabled=False,
            silence_timeout=2000,
            max_call_duration=600,
            end_call_phrases=["goodbye"],
        ),
        "advanced": AdvancedFeatures(sentiment_analysis_enabled=True),
        "tags": ["support", "tier-1"],
    }
    payload.update(overrides)
    return AgentCreate(**payload)


@pytest.fixture
def service():
    return get_agent_service()


@pytest.mark.unit
@pytest.mark.agents
class TestServiceSingleton:
    def test_get_agent_service_is_a_singleton(self):
        assert get_agent_service() is get_agent_service()


@pytest.mark.unit
@pytest.mark.agents
class TestCreateAgent:
    async def test_create_agent_persists_the_core_fields(
        self, service, db_session, test_user, test_organization
    ):
        agent = await service.create_agent(
            agent_data=_agent_create(),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.system_prompt == "You are a helpful assistant."
        assert agent.user_id == test_user.id
        assert agent.organization_id == test_organization.id
        assert agent.is_active is True

    async def test_nested_config_maps_onto_the_flat_columns(
        self, service, db_session, test_user, test_organization
    ):
        """The `llm`/`voice`/`stt` sections must land in the `*_provider` columns."""
        agent = await service.create_agent(
            agent_data=_agent_create(),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert (agent.llm_provider, agent.llm_model) == ("openai", "gpt-4")
        assert float(agent.llm_temperature) == 0.5
        assert agent.llm_max_tokens == 800

        assert (agent.tts_provider, agent.tts_voice_id) == ("elevenlabs", "rachel")
        assert float(agent.tts_speed) == 1.2
        assert float(agent.tts_pitch) == 0.9

        assert (agent.stt_provider, agent.stt_language, agent.stt_model) == (
            "deepgram",
            "en",
            "nova-2",
        )

    async def test_conversation_and_advanced_settings_are_stored(
        self, service, db_session, test_user, test_organization
    ):
        agent = await service.create_agent(
            agent_data=_agent_create(),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent.interrupt_enabled is False
        assert agent.silence_timeout == 2000
        assert agent.max_call_duration == 600
        assert agent.end_call_phrases == ["goodbye"]
        assert agent.sentiment_analysis_enabled is True
        assert agent.tags == ["support", "tier-1"]

    async def test_customer_api_keys_are_encrypted_at_rest(
        self, service, db_session, test_user, test_organization
    ):
        """
        These are the customer's own provider keys. Storing them in plaintext
        would put live OpenAI/ElevenLabs credentials in the agents table.
        """
        agent = await service.create_agent(
            agent_data=_agent_create(
                llm=LLMConfig(api_key="sk-live-secret-llm"),
                voice=VoiceConfig(api_key="el-secret-voice"),
                stt=STTConfig(api_key="dg-secret-stt"),
            ),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert "sk-live-secret-llm" not in (agent.llm_api_key_encrypted or "")
        assert "el-secret-voice" not in (agent.tts_api_key_encrypted or "")
        assert "dg-secret-stt" not in (agent.stt_api_key_encrypted or "")

    async def test_no_api_key_leaves_the_column_empty(
        self, service, db_session, test_user, test_organization
    ):
        """Most agents use the platform keys; those must not get a bogus blob."""
        agent = await service.create_agent(
            agent_data=_agent_create(),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent.llm_api_key_encrypted is None

    async def test_defaults_apply_when_only_a_name_is_given(
        self, service, db_session, test_user, test_organization
    ):
        """The create form can post just a name; the rest must fall back sanely."""
        agent = await service.create_agent(
            agent_data=AgentCreate(name="Minimal"),
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent.name == "Minimal"
        assert agent.llm_provider == "openai"
        assert agent.tts_provider == "elevenlabs"
        assert agent.stt_provider == "deepgram"

    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    async def test_blank_names_are_rejected_before_reaching_the_database(self, blank):
        """
        A whitespace-only name produces a row that renders as an unclickable blank
        in the agent list, so it is rejected at the schema boundary.
        """
        with pytest.raises(ValueError):
            AgentCreate(name=blank)

    async def test_name_is_trimmed(self):
        assert AgentCreate(name="  Padded  ").name == "Padded"


@pytest.mark.unit
@pytest.mark.agents
class TestUpdateAgent:
    async def test_update_changes_only_the_supplied_fields(
        self, service, db_session, test_agent, test_organization
    ):
        original_prompt = test_agent.system_prompt

        updated = await service.update_agent(
            agent_id=test_agent.id,
            agent_data=AgentUpdate(name="Renamed"),
            organization_id=test_organization.id,
            db=db_session,
        )

        assert updated.name == "Renamed"
        assert updated.system_prompt == original_prompt

    async def test_update_bumps_the_version(
        self, service, db_session, test_agent, test_organization
    ):
        """Version is what lets a stale editor detect it is overwriting someone."""
        before = test_agent.version

        updated = await service.update_agent(
            agent_id=test_agent.id,
            agent_data=AgentUpdate(description="new"),
            organization_id=test_organization.id,
            db=db_session,
        )

        assert updated.version == before + 1

    async def test_update_can_deactivate_an_agent(
        self, service, db_session, test_agent, test_organization
    ):
        updated = await service.update_agent(
            agent_id=test_agent.id,
            agent_data=AgentUpdate(is_active=False),
            organization_id=test_organization.id,
            db=db_session,
        )

        assert updated.is_active is False

    async def test_update_rewrites_nested_config(
        self, service, db_session, test_agent, test_organization
    ):
        updated = await service.update_agent(
            agent_id=test_agent.id,
            agent_data=AgentUpdate(llm=LLMConfig(provider="anthropic", model="claude-opus-5")),
            organization_id=test_organization.id,
            db=db_session,
        )

        assert (updated.llm_provider, updated.llm_model) == ("anthropic", "claude-opus-5")

    async def test_updating_an_agent_in_another_workspace_is_refused(
        self, service, db_session, test_agent, other_organization
    ):
        """
        Tenant isolation. The agent id comes straight from the URL, so scoping the
        lookup by organization is the only thing stopping cross-tenant edits.
        """
        result = await service.update_agent(
            agent_id=test_agent.id,
            agent_data=AgentUpdate(name="Hijacked"),
            organization_id=other_organization.id,
            db=db_session,
        )

        assert result is None
        await db_session.refresh(test_agent)
        assert test_agent.name == "Test Agent"

    async def test_updating_an_unknown_agent_returns_none(
        self, service, db_session, test_organization
    ):
        result = await service.update_agent(
            agent_id=uuid.uuid4(),
            agent_data=AgentUpdate(name="Ghost"),
            organization_id=test_organization.id,
            db=db_session,
        )

        assert result is None


@pytest.mark.unit
@pytest.mark.agents
class TestDeleteAgent:
    async def test_soft_delete_keeps_the_row_but_deactivates_it(
        self, service, db_session, test_agent, test_organization
    ):
        """
        Calls reference their agent, so the row has to survive. Soft delete is
        what keeps historical call logs readable after an agent is removed.
        """
        assert await service.delete_agent(
            agent_id=test_agent.id, organization_id=test_organization.id, db=db_session
        ) is True

        await db_session.refresh(test_agent)
        assert test_agent.deleted_at is not None
        assert test_agent.is_active is False

    async def test_hard_delete_removes_the_row(
        self, service, db_session, test_agent, test_organization
    ):
        agent_id = test_agent.id

        assert await service.delete_agent(
            agent_id=agent_id,
            organization_id=test_organization.id,
            db=db_session,
            soft_delete=False,
        ) is True

        found = await db_session.execute(select(Agent).where(Agent.id == agent_id))
        assert found.scalar_one_or_none() is None

    async def test_deleting_an_agent_in_another_workspace_is_refused(
        self, service, db_session, test_agent, other_organization
    ):
        result = await service.delete_agent(
            agent_id=test_agent.id,
            organization_id=other_organization.id,
            db=db_session,
        )

        assert result is False
        await db_session.refresh(test_agent)
        assert test_agent.deleted_at is None

    async def test_deleting_an_unknown_agent_returns_false(
        self, service, db_session, test_organization
    ):
        assert await service.delete_agent(
            agent_id=uuid.uuid4(),
            organization_id=test_organization.id,
            db=db_session,
        ) is False


@pytest.mark.unit
@pytest.mark.agents
class TestCloneAgent:
    async def test_clone_copies_the_configuration_under_a_new_name(
        self, service, db_session, test_agent, test_user, test_organization
    ):
        clone = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Cloned Agent",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert clone.id != test_agent.id
        assert clone.name == "Cloned Agent"
        assert clone.system_prompt == test_agent.system_prompt
        assert clone.llm_provider == test_agent.llm_provider
        assert clone.organization_id == test_organization.id

    async def test_clone_records_where_it_came_from(
        self, service, db_session, test_agent, test_user, test_organization
    ):
        clone = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Cloned Agent",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert test_agent.name in clone.description

    async def test_clone_copies_functions_by_default(
        self, service, db_session, test_agent, test_user, test_organization
    ):
        """
        Regression: `functions` is lazy, and reading it after a commit raised
        "greenlet_spawn has not been called" — a 500 on every clone the UI sent.
        """
        db_session.add(
            AgentFunction(
                agent_id=test_agent.id,
                name="lookup_order",
                description="Look up an order",
                parameters={"type": "object", "properties": {}},
                webhook_url="https://example.test/hook",
            )
        )
        await db_session.commit()

        clone = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Cloned Agent",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        copied = await db_session.execute(
            select(AgentFunction).where(AgentFunction.agent_id == clone.id)
        )
        functions = copied.scalars().all()
        assert [f.name for f in functions] == ["lookup_order"]
        assert functions[0].webhook_url == "https://example.test/hook"

    async def test_clone_can_skip_functions(
        self, service, db_session, test_agent, test_user, test_organization
    ):
        db_session.add(
            AgentFunction(
                agent_id=test_agent.id,
                name="lookup_order",
                description="Look up an order",
                parameters={},
            )
        )
        await db_session.commit()

        clone = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Bare Clone",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
            include_functions=False,
        )

        copied = await db_session.execute(
            select(AgentFunction).where(AgentFunction.agent_id == clone.id)
        )
        assert copied.scalars().all() == []

    async def test_cloning_an_agent_from_another_workspace_is_refused(
        self, service, db_session, test_agent, test_user, other_organization
    ):
        """Otherwise a bare agent id would copy a competitor's prompt wholesale."""
        result = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Stolen",
            user_id=test_user.id,
            organization_id=other_organization.id,
            db=db_session,
        )

        assert result is None

    async def test_cloning_an_unknown_agent_returns_none(
        self, service, db_session, test_user, test_organization
    ):
        assert await service.clone_agent(
            agent_id=uuid.uuid4(),
            new_name="Ghost",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        ) is None


@pytest.mark.unit
@pytest.mark.agents
@pytest.mark.templates
class TestAgentTemplates:
    def test_every_template_is_returned(self, service):
        assert len(service.get_templates()) == len(AGENT_TEMPLATES)

    def test_template_ids_are_unique(self, service):
        """Ids address templates, so a duplicate would shadow one permanently."""
        ids = [t.id for t in service.get_templates()]

        assert len(ids) == len(set(ids))

    def test_templates_expose_the_fields_the_gallery_renders(self, service):
        for template in service.get_templates():
            assert template.id and template.name
            assert template.description
            assert template.category

    @pytest.mark.parametrize("template", AGENT_TEMPLATES, ids=lambda t: t["id"])
    def test_each_template_builds_a_valid_agent(self, template):
        """
        Templates are hand-written dicts that bypass the API's validation until
        someone installs one. A typo here is a 500 at install time, not at boot.
        """
        agent_data = AgentCreate(**template["template_data"])

        assert agent_data.name
        assert agent_data.system_prompt
        assert agent_data.first_message

    async def test_create_from_template_builds_a_configured_agent(
        self, service, db_session, test_user, test_organization
    ):
        agent = await service.create_from_template(
            template_id="customer-support",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent is not None
        assert agent.organization_id == test_organization.id
        assert agent.system_prompt
        assert agent.first_message

    async def test_create_from_template_honours_a_custom_name(
        self, service, db_session, test_user, test_organization
    ):
        agent = await service.create_from_template(
            template_id="sales-assistant",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
            custom_name="My Sales Bot",
        )

        assert agent.name == "My Sales Bot"

    async def test_unknown_template_returns_none(
        self, service, db_session, test_user, test_organization
    ):
        """Must be None, not a half-built agent from an empty template dict."""
        assert await service.create_from_template(
            template_id="no-such-template",
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        ) is None
