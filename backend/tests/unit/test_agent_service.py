"""
Unit tests for Agent Service.

Tests agent CRUD operations, configuration, and templates.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.agent_service import get_agent_service, AGENT_TEMPLATES
from app.models.agent import Agent, AgentFunction
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentFunctionCreate,
    AgentFunctionUpdate,
)


@pytest.mark.unit
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentService:
    """Test agent service functionality."""

    async def test_get_agent_service_singleton(self):
        """Test that get_agent_service returns singleton instance."""
        service1 = get_agent_service()
        service2 = get_agent_service()

        assert service1 is service2

    async def test_create_agent(self, db_session, test_user, test_organization):
        """Test creating a new agent."""
        service = get_agent_service()

        agent_data = AgentCreate(
            name="Test Agent",
            description="A test agent",
            system_prompt="You are a helpful assistant.",
            first_message="Hello! How can I help you?",
            llm_provider="openai",
            llm_model="gpt-4",
            temperature=0.7,
            voice_provider="elevenlabs",
            voice_id="rachel",
        )

        agent = await service.create_agent(
            agent_data=agent_data,
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent is not None
        assert agent.name == "Test Agent"
        assert agent.description == "A test agent"
        assert agent.system_prompt == "You are a helpful assistant."
        assert agent.organization_id == test_organization.id
        assert agent.created_by == test_user.id
        assert agent.is_active is True

    async def test_get_agent_by_id(self, db_session, test_agent):
        """Test retrieving agent by ID."""
        service = get_agent_service()

        agent = await service.get_agent(
            agent_id=test_agent.id,
            db=db_session,
        )

        assert agent is not None
        assert agent.id == test_agent.id
        assert agent.name == test_agent.name

    async def test_get_agent_not_found(self, db_session):
        """Test retrieving non-existent agent."""
        service = get_agent_service()
        non_existent_id = uuid.uuid4()

        agent = await service.get_agent(
            agent_id=non_existent_id,
            db=db_session,
        )

        assert agent is None

    async def test_update_agent(self, db_session, test_agent):
        """Test updating agent configuration."""
        service = get_agent_service()

        update_data = AgentUpdate(
            name="Updated Agent Name",
            description="Updated description",
            temperature=0.9,
        )

        updated_agent = await service.update_agent(
            agent_id=test_agent.id,
            update_data=update_data,
            db=db_session,
        )

        assert updated_agent.name == "Updated Agent Name"
        assert updated_agent.description == "Updated description"
        assert updated_agent.temperature == 0.9
        assert updated_agent.system_prompt == test_agent.system_prompt  # Unchanged

    async def test_delete_agent(self, db_session, test_agent):
        """Test deleting an agent (soft delete)."""
        service = get_agent_service()

        result = await service.delete_agent(
            agent_id=test_agent.id,
            db=db_session,
        )

        assert result is True

        # Verify agent is deactivated
        agent = await service.get_agent(
            agent_id=test_agent.id,
            db=db_session,
        )

        assert agent.is_active is False

    async def test_list_agents_by_organization(
        self, db_session, test_organization, test_user
    ):
        """Test listing agents for an organization."""
        service = get_agent_service()

        # Create multiple agents
        for i in range(3):
            agent_data = AgentCreate(
                name=f"Agent {i}",
                description=f"Description {i}",
                system_prompt="You are helpful.",
                llm_provider="openai",
                llm_model="gpt-4",
            )
            await service.create_agent(
                agent_data=agent_data,
                user_id=test_user.id,
                organization_id=test_organization.id,
                db=db_session,
            )

        agents = await service.list_agents(
            organization_id=test_organization.id,
            db=db_session,
        )

        assert len(agents) >= 3
        assert all(a.organization_id == test_organization.id for a in agents)

    async def test_clone_agent(self, db_session, test_agent, test_user):
        """Test cloning an existing agent."""
        service = get_agent_service()

        cloned_agent = await service.clone_agent(
            agent_id=test_agent.id,
            new_name="Cloned Agent",
            user_id=test_user.id,
            db=db_session,
        )

        assert cloned_agent.id != test_agent.id
        assert cloned_agent.name == "Cloned Agent"
        assert cloned_agent.system_prompt == test_agent.system_prompt
        assert cloned_agent.llm_provider == test_agent.llm_provider
        assert cloned_agent.organization_id == test_agent.organization_id

    async def test_toggle_agent_active_status(self, db_session, test_agent):
        """Test toggling agent active status."""
        service = get_agent_service()

        # Deactivate
        await service.set_agent_active(
            agent_id=test_agent.id,
            is_active=False,
            db=db_session,
        )

        agent = await service.get_agent(agent_id=test_agent.id, db=db_session)
        assert agent.is_active is False

        # Reactivate
        await service.set_agent_active(
            agent_id=test_agent.id,
            is_active=True,
            db=db_session,
        )

        agent = await service.get_agent(agent_id=test_agent.id, db=db_session)
        assert agent.is_active is True

    async def test_search_agents_by_name(
        self, db_session, test_organization, test_user
    ):
        """Test searching agents by name."""
        service = get_agent_service()

        # Create agents with specific names
        agent1_data = AgentCreate(
            name="Customer Support Agent",
            description="Handles support",
            system_prompt="You are helpful.",
            llm_provider="openai",
            llm_model="gpt-4",
        )

        agent2_data = AgentCreate(
            name="Sales Agent",
            description="Handles sales",
            system_prompt="You are helpful.",
            llm_provider="openai",
            llm_model="gpt-4",
        )

        await service.create_agent(
            agent_data=agent1_data,
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        await service.create_agent(
            agent_data=agent2_data,
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        # Search for "Support"
        results = await service.search_agents(
            organization_id=test_organization.id,
            query="Support",
            db=db_session,
        )

        assert len(results) >= 1
        assert any("Support" in a.name for a in results)

    async def test_get_agent_statistics(self, db_session, test_agent):
        """Test getting agent statistics."""
        service = get_agent_service()

        stats = await service.get_agent_stats(
            agent_id=test_agent.id,
            db=db_session,
        )

        assert "total_calls" in stats
        assert "total_minutes" in stats
        assert "success_rate" in stats
        assert stats["total_calls"] >= 0


@pytest.mark.unit
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentFunctions:
    """Test agent function management."""

    async def test_add_function_to_agent(self, db_session, test_agent):
        """Test adding a function to an agent."""
        service = get_agent_service()

        function_data = AgentFunctionCreate(
            name="get_weather",
            description="Get current weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        )

        function = await service.add_agent_function(
            agent_id=test_agent.id,
            function_data=function_data,
            db=db_session,
        )

        assert function.name == "get_weather"
        assert function.agent_id == test_agent.id
        assert function.is_active is True

    async def test_update_agent_function(self, db_session, test_agent):
        """Test updating an agent function."""
        service = get_agent_service()

        # Create function
        function_data = AgentFunctionCreate(
            name="send_email",
            description="Send an email",
            parameters={"type": "object", "properties": {}},
        )

        function = await service.add_agent_function(
            agent_id=test_agent.id,
            function_data=function_data,
            db=db_session,
        )

        # Update function
        update_data = AgentFunctionUpdate(
            description="Send an email to a recipient",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject"],
            },
        )

        updated_function = await service.update_agent_function(
            function_id=function.id,
            update_data=update_data,
            db=db_session,
        )

        assert updated_function.description == "Send an email to a recipient"
        assert "to" in updated_function.parameters["properties"]
        assert "subject" in updated_function.parameters["required"]

    async def test_delete_agent_function(self, db_session, test_agent):
        """Test deleting an agent function."""
        service = get_agent_service()

        # Create function
        function_data = AgentFunctionCreate(
            name="test_function",
            description="Test function",
            parameters={"type": "object"},
        )

        function = await service.add_agent_function(
            agent_id=test_agent.id,
            function_data=function_data,
            db=db_session,
        )

        # Delete function
        result = await service.delete_agent_function(
            function_id=function.id,
            db=db_session,
        )

        assert result is True

        # Verify function is deactivated
        function = await service.get_agent_function(
            function_id=function.id,
            db=db_session,
        )

        assert function.is_active is False

    async def test_list_agent_functions(self, db_session, test_agent):
        """Test listing all functions for an agent."""
        service = get_agent_service()

        # Create multiple functions
        functions_data = [
            AgentFunctionCreate(
                name=f"function_{i}",
                description=f"Function {i}",
                parameters={"type": "object"},
            )
            for i in range(3)
        ]

        for func_data in functions_data:
            await service.add_agent_function(
                agent_id=test_agent.id,
                function_data=func_data,
                db=db_session,
            )

        functions = await service.list_agent_functions(
            agent_id=test_agent.id,
            db=db_session,
        )

        assert len(functions) >= 3
        assert all(f.agent_id == test_agent.id for f in functions)


@pytest.mark.unit
@pytest.mark.agents
class TestAgentTemplates:
    """Test agent template functionality."""

    def test_agent_templates_exist(self):
        """Test that agent templates are defined."""
        assert len(AGENT_TEMPLATES) > 0
        assert all("id" in t for t in AGENT_TEMPLATES)
        assert all("name" in t for t in AGENT_TEMPLATES)
        assert all("template_data" in t for t in AGENT_TEMPLATES)

    def test_customer_support_template(self):
        """Test customer support template structure."""
        support_template = next(
            (t for t in AGENT_TEMPLATES if t["id"] == "customer-support"),
            None,
        )

        assert support_template is not None
        assert support_template["name"] == "Customer Support Agent"
        assert "system_prompt" in support_template["template_data"]
        assert "llm" in support_template["template_data"]
        assert "voice" in support_template["template_data"]

    def test_sales_assistant_template(self):
        """Test sales assistant template structure."""
        sales_template = next(
            (t for t in AGENT_TEMPLATES if t["id"] == "sales-assistant"),
            None,
        )

        assert sales_template is not None
        assert sales_template["name"] == "Sales Assistant"
        assert "qualification" in sales_template["description"].lower()

    def test_template_categories(self):
        """Test that templates have valid categories."""
        valid_categories = ["Support", "Sales", "Scheduling", "Healthcare"]

        for template in AGENT_TEMPLATES:
            assert template["category"] in valid_categories

    async def test_create_agent_from_template(
        self, db_session, test_user, test_organization
    ):
        """Test creating agent from a template."""
        service = get_agent_service()

        # Get customer support template
        template = next(
            t for t in AGENT_TEMPLATES if t["id"] == "customer-support"
        )

        template_data = template["template_data"]
        agent_data = AgentCreate(
            name=template_data["name"],
            description=template_data["description"],
            system_prompt=template_data["system_prompt"],
            first_message=template_data["first_message"],
            llm_provider=template_data["llm"]["provider"],
            llm_model=template_data["llm"]["model"],
            temperature=template_data["llm"]["temperature"],
            voice_provider=template_data["voice"]["provider"],
            voice_id=template_data["voice"]["voice_id"],
        )

        agent = await service.create_agent(
            agent_data=agent_data,
            user_id=test_user.id,
            organization_id=test_organization.id,
            db=db_session,
        )

        assert agent.name == "Customer Support"
        assert "customer support" in agent.system_prompt.lower()
        assert agent.llm_provider == "openai"
