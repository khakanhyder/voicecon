"""
Integration tests for Agent API endpoints.

Tests complete agent CRUD operations and deployment.
"""
import pytest
import uuid
from datetime import datetime


@pytest.mark.integration
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentAPI:
    """Test agent API endpoints."""

    async def test_create_agent(self, auth_client, db_session):
        """Test creating a new agent."""
        agent_data = {
            "name": "Test Agent",
            "description": "A test agent for automated testing",
            "system_prompt": "You are a helpful test assistant.",
            "first_message": "Hello! How can I test your system today?",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "temperature": 0.7,
            "voice_provider": "elevenlabs",
            "voice_id": "rachel",
        }

        response = auth_client.post("/api/v1/agents", json=agent_data)

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Test Agent"
        assert data["description"] == agent_data["description"]
        assert data["system_prompt"] == agent_data["system_prompt"]
        assert data["is_active"] is True

    async def test_create_agent_minimal_data(self, auth_client):
        """Test creating agent with minimal required data."""
        agent_data = {
            "name": "Minimal Agent",
            "system_prompt": "You are helpful.",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
        }

        response = auth_client.post("/api/v1/agents", json=agent_data)

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Minimal Agent"
        assert data["llm_provider"] == "openai"

    async def test_create_agent_validation_error(self, auth_client):
        """Test creating agent with invalid data."""
        agent_data = {
            "name": "",  # Empty name should fail
            "system_prompt": "Test",
        }

        response = auth_client.post("/api/v1/agents", json=agent_data)

        assert response.status_code == 422

    async def test_list_agents(self, auth_client, db_session, test_agent):
        """Test listing agents."""
        response = auth_client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()

        assert "agents" in data
        assert len(data["agents"]) >= 1
        assert any(a["id"] == str(test_agent.id) for a in data["agents"])

    async def test_list_agents_with_search(self, auth_client, db_session):
        """Test listing agents with search filter."""
        # Create agents with specific names
        agent_data1 = {
            "name": "Customer Support Agent",
            "system_prompt": "Support agent",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
        }

        agent_data2 = {
            "name": "Sales Agent",
            "system_prompt": "Sales agent",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
        }

        auth_client.post("/api/v1/agents", json=agent_data1)
        auth_client.post("/api/v1/agents", json=agent_data2)

        # Search for "Support"
        response = auth_client.get("/api/v1/agents?search=Support")

        assert response.status_code == 200
        data = response.json()

        assert len(data["agents"]) >= 1
        assert any("Support" in a["name"] for a in data["agents"])

    async def test_list_agents_filter_by_status(self, auth_client, test_agent):
        """Test filtering agents by active status."""
        # List active agents
        response = auth_client.get("/api/v1/agents?is_active=true")

        assert response.status_code == 200
        data = response.json()

        assert all(a["is_active"] is True for a in data["agents"])

    async def test_get_agent_by_id(self, auth_client, test_agent):
        """Test retrieving specific agent by ID."""
        response = auth_client.get(f"/api/v1/agents/{test_agent.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(test_agent.id)
        assert data["name"] == test_agent.name

    async def test_get_agent_not_found(self, auth_client):
        """Test retrieving non-existent agent."""
        non_existent_id = uuid.uuid4()

        response = auth_client.get(f"/api/v1/agents/{non_existent_id}")

        assert response.status_code == 404

    async def test_update_agent(self, auth_client, test_agent):
        """Test updating agent configuration."""
        update_data = {
            "name": "Updated Agent Name",
            "description": "Updated description",
            "temperature": 0.9,
        }

        response = auth_client.put(
            f"/api/v1/agents/{test_agent.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Agent Name"
        assert data["description"] == "Updated description"
        assert data["temperature"] == 0.9

    async def test_update_agent_partial(self, auth_client, test_agent):
        """Test partial agent update."""
        update_data = {"name": "New Name Only"}

        response = auth_client.patch(
            f"/api/v1/agents/{test_agent.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "New Name Only"
        # Other fields should remain unchanged
        assert data["system_prompt"] == test_agent.system_prompt

    async def test_delete_agent(self, auth_client, test_agent):
        """Test deleting an agent (soft delete)."""
        response = auth_client.delete(f"/api/v1/agents/{test_agent.id}")

        assert response.status_code == 200

        # Verify agent is deactivated
        get_response = auth_client.get(f"/api/v1/agents/{test_agent.id}")
        data = get_response.json()

        assert data["is_active"] is False

    async def test_clone_agent(self, auth_client, test_agent):
        """Test cloning an existing agent."""
        clone_data = {"new_name": "Cloned Agent"}

        response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/clone",
            json=clone_data,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Cloned Agent"
        assert data["id"] != str(test_agent.id)
        assert data["system_prompt"] == test_agent.system_prompt

    async def test_toggle_agent_status(self, auth_client, test_agent):
        """Test toggling agent active status."""
        # Deactivate
        response = auth_client.post(f"/api/v1/agents/{test_agent.id}/deactivate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

        # Reactivate
        response = auth_client.post(f"/api/v1/agents/{test_agent.id}/activate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    async def test_get_agent_statistics(self, auth_client, test_agent):
        """Test retrieving agent statistics."""
        response = auth_client.get(f"/api/v1/agents/{test_agent.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert "total_calls" in data
        assert "total_minutes" in data
        assert "success_rate" in data
        assert "average_duration" in data


@pytest.mark.integration
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentFunctionsAPI:
    """Test agent function management API."""

    async def test_add_function_to_agent(self, auth_client, test_agent):
        """Test adding a function to an agent."""
        function_data = {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                    },
                },
                "required": ["location"],
            },
        }

        response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/functions",
            json=function_data,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "get_weather"
        assert data["agent_id"] == str(test_agent.id)
        assert "location" in data["parameters"]["properties"]

    async def test_list_agent_functions(self, auth_client, test_agent):
        """Test listing all functions for an agent."""
        # Add functions
        functions_data = [
            {
                "name": f"function_{i}",
                "description": f"Function {i}",
                "parameters": {"type": "object"},
            }
            for i in range(3)
        ]

        for func_data in functions_data:
            auth_client.post(
                f"/api/v1/agents/{test_agent.id}/functions",
                json=func_data,
            )

        # List functions
        response = auth_client.get(f"/api/v1/agents/{test_agent.id}/functions")

        assert response.status_code == 200
        data = response.json()

        assert len(data["functions"]) >= 3

    async def test_update_agent_function(self, auth_client, test_agent):
        """Test updating an agent function."""
        # Create function
        function_data = {
            "name": "send_email",
            "description": "Send an email",
            "parameters": {"type": "object"},
        }

        create_response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/functions",
            json=function_data,
        )
        function_id = create_response.json()["id"]

        # Update function
        update_data = {
            "description": "Send an email to a recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                },
            },
        }

        response = auth_client.put(
            f"/api/v1/agents/{test_agent.id}/functions/{function_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["description"] == "Send an email to a recipient"
        assert "to" in data["parameters"]["properties"]

    async def test_delete_agent_function(self, auth_client, test_agent):
        """Test deleting an agent function."""
        # Create function
        function_data = {
            "name": "test_function",
            "description": "Test",
            "parameters": {"type": "object"},
        }

        create_response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/functions",
            json=function_data,
        )
        function_id = create_response.json()["id"]

        # Delete function
        response = auth_client.delete(
            f"/api/v1/agents/{test_agent.id}/functions/{function_id}"
        )

        assert response.status_code == 200

        # Verify function is deactivated
        get_response = auth_client.get(
            f"/api/v1/agents/{test_agent.id}/functions/{function_id}"
        )
        data = get_response.json()

        assert data["is_active"] is False


@pytest.mark.integration
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentTestingAPI:
    """Test agent testing and validation API."""

    async def test_test_agent_prompt(self, auth_client, test_agent):
        """Test testing agent with a prompt."""
        test_data = {
            "message": "Hello, can you help me?",
        }

        response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/test",
            json=test_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert "response" in data
        assert isinstance(data["response"], str)
        assert len(data["response"]) > 0

    async def test_validate_agent_config(self, auth_client, test_agent):
        """Test validating agent configuration."""
        response = auth_client.post(f"/api/v1/agents/{test_agent.id}/validate")

        assert response.status_code == 200
        data = response.json()

        assert "is_valid" in data
        assert data["is_valid"] is True
        assert "errors" in data

    async def test_validate_agent_with_errors(self, auth_client):
        """Test validation catches configuration errors."""
        # Create agent with invalid config
        agent_data = {
            "name": "Invalid Agent",
            "system_prompt": "",  # Empty prompt
            "llm_provider": "openai",
            "llm_model": "gpt-4",
        }

        create_response = auth_client.post("/api/v1/agents", json=agent_data)
        agent_id = create_response.json()["id"]

        # Validate
        response = auth_client.post(f"/api/v1/agents/{agent_id}/validate")

        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is False
        assert len(data["errors"]) > 0


@pytest.mark.integration
@pytest.mark.agents
@pytest.mark.asyncio
class TestAgentDeployment:
    """Test agent deployment and phone number assignment."""

    async def test_assign_phone_number_to_agent(self, auth_client, test_agent):
        """Test assigning phone number to agent."""
        phone_data = {"phone_number": "+15555551234"}

        response = auth_client.post(
            f"/api/v1/agents/{test_agent.id}/phone-number",
            json=phone_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert "phone_number" in data

    async def test_unassign_phone_number(self, auth_client, test_agent):
        """Test unassigning phone number from agent."""
        # First assign
        phone_data = {"phone_number": "+15555551234"}
        auth_client.post(
            f"/api/v1/agents/{test_agent.id}/phone-number",
            json=phone_data,
        )

        # Then unassign
        response = auth_client.delete(
            f"/api/v1/agents/{test_agent.id}/phone-number"
        )

        assert response.status_code == 200

    async def test_deploy_agent(self, auth_client, test_agent):
        """Test deploying agent to production."""
        response = auth_client.post(f"/api/v1/agents/{test_agent.id}/deploy")

        assert response.status_code == 200
        data = response.json()

        assert data["is_active"] is True
        assert "deployed_at" in data

    async def test_undeploy_agent(self, auth_client, test_agent):
        """Test undeploying agent from production."""
        # First deploy
        auth_client.post(f"/api/v1/agents/{test_agent.id}/deploy")

        # Then undeploy
        response = auth_client.post(f"/api/v1/agents/{test_agent.id}/undeploy")

        assert response.status_code == 200
        data = response.json()

        assert data["is_active"] is False
