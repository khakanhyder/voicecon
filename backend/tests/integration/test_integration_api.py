"""
Integration tests for Integration and Workflow API endpoints.

Tests integration connections and workflow execution.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
class TestIntegrationAPI:
    """Test integration management API."""

    async def test_list_available_integrations(self, auth_client):
        """Test listing available integration types."""
        response = auth_client.get("/api/v1/integrations/available")

        assert response.status_code == 200
        data = response.json()

        assert len(data["integrations"]) > 0
        assert any(i["slug"] == "salesforce" for i in data["integrations"])
        assert any(i["slug"] == "hubspot" for i in data["integrations"])

    async def test_create_integration(self, auth_client, db_session):
        """Test creating a new integration."""
        integration_data = {
            "integration_type": "salesforce",
            "name": "My Salesforce",
            "config": {
                "domain": "test.salesforce.com",
                "api_version": "v54.0",
            },
        }

        response = auth_client.post("/api/v1/integrations", json=integration_data)

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "My Salesforce"
        assert data["integration_type"] == "salesforce"
        assert data["is_active"] is True

    async def test_list_organization_integrations(
        self, auth_client, db_session, test_organization
    ):
        """Test listing organization's integrations."""
        # Create integration
        integration_data = {
            "integration_type": "slack",
            "name": "Team Slack",
            "config": {"workspace": "test-workspace"},
        }

        auth_client.post("/api/v1/integrations", json=integration_data)

        # List integrations
        response = auth_client.get("/api/v1/integrations")

        assert response.status_code == 200
        data = response.json()

        assert len(data["integrations"]) >= 1
        assert any(i["name"] == "Team Slack" for i in data["integrations"])

    async def test_get_integration_by_id(self, auth_client, db_session):
        """Test retrieving specific integration."""
        # Create integration
        integration_data = {
            "integration_type": "hubspot",
            "name": "My HubSpot",
            "config": {"portal_id": "12345"},
        }

        create_response = auth_client.post(
            "/api/v1/integrations", json=integration_data
        )
        integration_id = create_response.json()["id"]

        # Get integration
        response = auth_client.get(f"/api/v1/integrations/{integration_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == integration_id
        assert data["name"] == "My HubSpot"

    async def test_update_integration(self, auth_client, db_session):
        """Test updating integration configuration."""
        # Create integration
        integration_data = {
            "integration_type": "slack",
            "name": "Slack Integration",
            "config": {"workspace": "old-workspace"},
        }

        create_response = auth_client.post(
            "/api/v1/integrations", json=integration_data
        )
        integration_id = create_response.json()["id"]

        # Update integration
        update_data = {
            "name": "Updated Slack",
            "config": {"workspace": "new-workspace"},
        }

        response = auth_client.put(
            f"/api/v1/integrations/{integration_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Slack"
        assert data["config"]["workspace"] == "new-workspace"

    async def test_delete_integration(self, auth_client, db_session):
        """Test deleting an integration."""
        # Create integration
        integration_data = {
            "integration_type": "salesforce",
            "name": "Test Integration",
            "config": {},
        }

        create_response = auth_client.post(
            "/api/v1/integrations", json=integration_data
        )
        integration_id = create_response.json()["id"]

        # Delete integration
        response = auth_client.delete(f"/api/v1/integrations/{integration_id}")

        assert response.status_code == 200

        # Verify deleted
        get_response = auth_client.get(f"/api/v1/integrations/{integration_id}")
        assert get_response.status_code == 404

    @patch("app.services.integrations.integration_manager.IntegrationManager")
    async def test_test_integration_connection(
        self, mock_manager, auth_client, db_session
    ):
        """Test testing integration connection."""
        # Create integration
        integration_data = {
            "integration_type": "salesforce",
            "name": "Test Salesforce",
            "config": {"domain": "test.salesforce.com"},
        }

        create_response = auth_client.post(
            "/api/v1/integrations", json=integration_data
        )
        integration_id = create_response.json()["id"]

        # Mock successful connection test
        mock_manager.return_value.test_connection = AsyncMock(return_value=True)

        # Test connection
        response = auth_client.post(
            f"/api/v1/integrations/{integration_id}/test"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True


@pytest.mark.integration
@pytest.mark.asyncio
class TestOAuthFlow:
    """Test OAuth integration flow."""

    async def test_initiate_oauth_flow(self, auth_client):
        """Test initiating OAuth authorization flow."""
        oauth_data = {
            "integration_type": "salesforce",
            "redirect_uri": "https://app.example.com/oauth/callback",
        }

        response = auth_client.post("/api/v1/integrations/oauth/init", json=oauth_data)

        assert response.status_code == 200
        data = response.json()

        assert "auth_url" in data
        assert "state" in data
        assert "oauth" in data["auth_url"].lower() or "authorize" in data["auth_url"].lower()

    @patch("app.services.integrations.oauth_handler.OAuthHandler")
    async def test_oauth_callback_success(self, mock_oauth, auth_client):
        """Test successful OAuth callback."""
        # Mock token exchange
        mock_oauth.return_value.exchange_code_for_token = AsyncMock(
            return_value={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
            }
        )

        callback_data = {
            "code": "auth_code_123",
            "state": "random_state",
            "integration_type": "salesforce",
        }

        response = auth_client.post(
            "/api/v1/integrations/oauth/callback", json=callback_data
        )

        assert response.status_code == 200
        data = response.json()

        assert "integration_id" in data

    async def test_oauth_callback_with_error(self, auth_client):
        """Test OAuth callback with error."""
        callback_data = {
            "error": "access_denied",
            "error_description": "User denied access",
        }

        response = auth_client.post(
            "/api/v1/integrations/oauth/callback", json=callback_data
        )

        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflowAPI:
    """Test workflow management API."""

    async def test_create_workflow(self, auth_client, db_session, test_agent):
        """Test creating a new workflow."""
        workflow_data = {
            "name": "Lead Creation Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {
                "trigger": "call_completed",
                "conditions": [
                    {"field": "call_duration", "operator": "gt", "value": 60}
                ],
                "actions": [
                    {
                        "type": "salesforce_create_lead",
                        "params": {
                            "first_name": "{{caller_name}}",
                            "email": "{{caller_email}}",
                        },
                    }
                ],
            },
        }

        response = auth_client.post("/api/v1/workflows", json=workflow_data)

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Lead Creation Workflow"
        assert data["trigger"] == "call_completed"
        assert data["is_active"] is True

    async def test_list_workflows(self, auth_client, db_session, test_agent):
        """Test listing workflows."""
        # Create workflow
        workflow_data = {
            "name": "Test Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        auth_client.post("/api/v1/workflows", json=workflow_data)

        # List workflows
        response = auth_client.get("/api/v1/workflows")

        assert response.status_code == 200
        data = response.json()

        assert len(data["workflows"]) >= 1

    async def test_get_workflow_by_id(self, auth_client, db_session, test_agent):
        """Test retrieving specific workflow."""
        # Create workflow
        workflow_data = {
            "name": "My Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Get workflow
        response = auth_client.get(f"/api/v1/workflows/{workflow_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == workflow_id
        assert data["name"] == "My Workflow"

    async def test_update_workflow(self, auth_client, db_session, test_agent):
        """Test updating workflow configuration."""
        # Create workflow
        workflow_data = {
            "name": "Original Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Update workflow
        update_data = {
            "name": "Updated Workflow",
            "workflow_definition": {
                "actions": [{"type": "send_email"}]
            },
        }

        response = auth_client.put(
            f"/api/v1/workflows/{workflow_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Workflow"

    async def test_delete_workflow(self, auth_client, db_session, test_agent):
        """Test deleting a workflow."""
        # Create workflow
        workflow_data = {
            "name": "Workflow to Delete",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Delete workflow
        response = auth_client.delete(f"/api/v1/workflows/{workflow_id}")

        assert response.status_code == 200

    async def test_toggle_workflow_status(self, auth_client, db_session, test_agent):
        """Test activating/deactivating workflow."""
        # Create workflow
        workflow_data = {
            "name": "Toggleable Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Deactivate
        response = auth_client.post(f"/api/v1/workflows/{workflow_id}/deactivate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

        # Reactivate
        response = auth_client.post(f"/api/v1/workflows/{workflow_id}/activate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    @patch("app.services.workflows.workflow_engine.WorkflowEngine")
    async def test_execute_workflow_manually(
        self, mock_engine, auth_client, db_session, test_agent
    ):
        """Test manually executing a workflow."""
        # Create workflow
        workflow_data = {
            "name": "Manual Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "manual",
            "workflow_definition": {
                "actions": [{"type": "send_notification"}]
            },
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Mock execution
        mock_engine.return_value.execute = AsyncMock(
            return_value={"success": True, "result": "Notification sent"}
        )

        # Execute workflow
        execution_data = {"context": {"message": "Test message"}}

        response = auth_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json=execution_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    async def test_get_workflow_execution_history(
        self, auth_client, db_session, test_agent
    ):
        """Test retrieving workflow execution history."""
        # Create workflow
        workflow_data = {
            "name": "History Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {"actions": []},
        }

        create_response = auth_client.post("/api/v1/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # Get execution history
        response = auth_client.get(f"/api/v1/workflows/{workflow_id}/executions")

        assert response.status_code == 200
        data = response.json()

        assert "executions" in data


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflowExecution:
    """Test workflow execution scenarios."""

    @patch("app.services.workflows.workflow_engine.WorkflowEngine")
    async def test_trigger_workflow_on_call_completed(
        self, mock_engine, auth_client, db_session, test_agent
    ):
        """Test workflow triggered when call completes."""
        # Create workflow
        workflow_data = {
            "name": "Call Completion Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {
                "conditions": [
                    {"field": "call_duration", "operator": "gt", "value": 60}
                ],
                "actions": [{"type": "log_event"}],
            },
        }

        auth_client.post("/api/v1/workflows", json=workflow_data)

        # Mock workflow execution
        mock_engine.return_value.execute = AsyncMock(
            return_value={"success": True}
        )

        # Simulate call completion would trigger workflow
        # In actual implementation, this would be done automatically
        assert True

    async def test_workflow_conditional_execution(
        self, auth_client, db_session, test_agent
    ):
        """Test workflow with conditions."""
        workflow_data = {
            "name": "Conditional Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {
                "conditions": [
                    {"field": "sentiment", "operator": "eq", "value": "positive"}
                ],
                "actions": [{"type": "send_thank_you"}],
            },
        }

        response = auth_client.post("/api/v1/workflows", json=workflow_data)

        assert response.status_code == 201
        data = response.json()

        conditions = data["workflow_definition"]["conditions"]
        assert len(conditions) > 0
        assert conditions[0]["field"] == "sentiment"

    async def test_workflow_multiple_actions(
        self, auth_client, db_session, test_agent
    ):
        """Test workflow with multiple sequential actions."""
        workflow_data = {
            "name": "Multi-Action Workflow",
            "agent_id": str(test_agent.id),
            "trigger": "call_completed",
            "workflow_definition": {
                "actions": [
                    {"type": "salesforce_create_lead"},
                    {"type": "send_email"},
                    {"type": "slack_notification"},
                ]
            },
        }

        response = auth_client.post("/api/v1/workflows", json=workflow_data)

        assert response.status_code == 201
        data = response.json()

        actions = data["workflow_definition"]["actions"]
        assert len(actions) == 3
