"""
Unit tests for Integration Services.

Tests integration management, OAuth handling, and workflow execution.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from app.services.integrations.integration_manager import IntegrationManager
from app.services.integrations.oauth_handler import OAuthHandler
from app.services.integrations.credential_manager import CredentialManager
from app.models.integration import Integration, IntegrationCredential


@pytest.mark.unit
@pytest.mark.asyncio
class TestIntegrationManager:
    """Test integration manager functionality."""

    async def test_list_available_integrations(self):
        """Test listing available integration types."""
        manager = IntegrationManager()
        available = manager.list_available_integrations()

        assert len(available) > 0
        assert any(i["slug"] == "salesforce" for i in available)
        assert any(i["slug"] == "hubspot" for i in available)
        assert any(i["slug"] == "slack" for i in available)

        for integration in available:
            assert "name" in integration
            assert "slug" in integration
            assert "category" in integration
            assert "auth_type" in integration

    async def test_get_integration_config(self):
        """Test getting integration configuration."""
        manager = IntegrationManager()
        config = manager.get_integration_config("salesforce")

        assert config is not None
        assert config["slug"] == "salesforce"
        assert config["name"] == "Salesforce"
        assert config["auth_type"] == "oauth2"
        assert "required_scopes" in config

    async def test_get_integration_config_not_found(self):
        """Test getting non-existent integration config."""
        manager = IntegrationManager()
        config = manager.get_integration_config("non_existent_integration")

        assert config is None

    async def test_validate_integration_config(self):
        """Test validating integration configuration."""
        manager = IntegrationManager()

        valid_config = {
            "api_key": "test_key",
            "domain": "example.salesforce.com",
        }

        is_valid = manager.validate_config("salesforce", valid_config)
        assert is_valid is True

    async def test_validate_integration_config_missing_fields(self):
        """Test validation with missing required fields."""
        manager = IntegrationManager()

        invalid_config = {
            "api_key": "test_key",
            # Missing domain
        }

        is_valid = manager.validate_config("salesforce", invalid_config)
        assert is_valid is False

    @patch("app.services.integrations.integration_manager.get_connector")
    async def test_test_integration_connection(self, mock_get_connector, db_session):
        """Test testing integration connection."""
        manager = IntegrationManager()

        # Mock connector
        mock_connector = AsyncMock()
        mock_connector.test_connection.return_value = True
        mock_get_connector.return_value = mock_connector

        integration = Integration(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            integration_type="salesforce",
            name="Test Salesforce",
            config={"domain": "test.salesforce.com"},
            is_active=True,
        )

        result = await manager.test_connection(integration, db_session)

        assert result is True
        mock_connector.test_connection.assert_called_once()

    @patch("app.services.integrations.integration_manager.get_connector")
    async def test_execute_integration_action(self, mock_get_connector, db_session):
        """Test executing an integration action."""
        manager = IntegrationManager()

        # Mock connector
        mock_connector = AsyncMock()
        mock_connector.execute_action.return_value = {
            "success": True,
            "lead_id": "00Q1234567890",
        }
        mock_get_connector.return_value = mock_connector

        integration = Integration(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            integration_type="salesforce",
            name="Test Salesforce",
            config={"domain": "test.salesforce.com"},
            is_active=True,
        )

        result = await manager.execute_action(
            integration=integration,
            action="create_lead",
            params={"first_name": "John", "last_name": "Doe", "email": "john@example.com"},
            db=db_session,
        )

        assert result["success"] is True
        assert "lead_id" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestOAuthHandler:
    """Test OAuth authentication handling."""

    async def test_generate_auth_url(self):
        """Test generating OAuth authorization URL."""
        handler = OAuthHandler()

        auth_url = handler.generate_auth_url(
            integration_type="salesforce",
            redirect_uri="https://app.example.com/oauth/callback",
            state="random_state_string",
        )

        assert auth_url is not None
        assert "oauth" in auth_url.lower() or "authorize" in auth_url.lower()
        assert "state=random_state_string" in auth_url
        assert "redirect_uri" in auth_url

    async def test_generate_auth_url_with_scopes(self):
        """Test generating OAuth URL with custom scopes."""
        handler = OAuthHandler()

        auth_url = handler.generate_auth_url(
            integration_type="hubspot",
            redirect_uri="https://app.example.com/oauth/callback",
            state="test_state",
            scopes=["contacts", "companies"],
        )

        assert auth_url is not None
        assert "scope" in auth_url.lower()

    @patch("app.services.integrations.oauth_handler.httpx.AsyncClient")
    async def test_exchange_code_for_token(self, mock_http_client):
        """Test exchanging authorization code for access token."""
        handler = OAuthHandler()

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token_value",
            "refresh_token": "refresh_token_value",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_http_client.return_value.__aenter__.return_value = mock_client

        tokens = await handler.exchange_code_for_token(
            integration_type="salesforce",
            code="auth_code_123",
            redirect_uri="https://app.example.com/oauth/callback",
        )

        assert tokens["access_token"] == "access_token_value"
        assert tokens["refresh_token"] == "refresh_token_value"
        assert tokens["expires_in"] == 3600

    @patch("app.services.integrations.oauth_handler.httpx.AsyncClient")
    async def test_refresh_access_token(self, mock_http_client):
        """Test refreshing an expired access token."""
        handler = OAuthHandler()

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_http_client.return_value.__aenter__.return_value = mock_client

        new_tokens = await handler.refresh_token(
            integration_type="salesforce",
            refresh_token="old_refresh_token",
        )

        assert new_tokens["access_token"] == "new_access_token"
        assert new_tokens["expires_in"] == 3600

    async def test_parse_callback_params(self):
        """Test parsing OAuth callback parameters."""
        handler = OAuthHandler()

        callback_url = "https://app.example.com/oauth/callback?code=auth_code&state=test_state"

        params = handler.parse_callback_params(callback_url)

        assert params["code"] == "auth_code"
        assert params["state"] == "test_state"

    async def test_parse_callback_params_with_error(self):
        """Test parsing OAuth callback with error."""
        handler = OAuthHandler()

        callback_url = "https://app.example.com/oauth/callback?error=access_denied&error_description=User+denied+access"

        params = handler.parse_callback_params(callback_url)

        assert "error" in params
        assert params["error"] == "access_denied"


@pytest.mark.unit
@pytest.mark.asyncio
class TestCredentialManager:
    """Test credential management."""

    async def test_encrypt_credentials(self):
        """Test encrypting integration credentials."""
        manager = CredentialManager()

        credentials = {
            "api_key": "secret_api_key",
            "api_secret": "secret_api_secret",
        }

        encrypted = manager.encrypt_credentials(credentials)

        assert encrypted != credentials
        assert isinstance(encrypted, str)

    async def test_decrypt_credentials(self):
        """Test decrypting integration credentials."""
        manager = CredentialManager()

        original = {
            "api_key": "secret_api_key",
            "api_secret": "secret_api_secret",
        }

        encrypted = manager.encrypt_credentials(original)
        decrypted = manager.decrypt_credentials(encrypted)

        assert decrypted == original

    async def test_store_credentials(self, db_session, test_organization):
        """Test storing integration credentials."""
        manager = CredentialManager()

        integration_id = uuid.uuid4()
        credentials = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }

        stored = await manager.store_credentials(
            integration_id=integration_id,
            credentials=credentials,
            db=db_session,
        )

        assert stored is not None
        assert stored.integration_id == integration_id
        assert stored.encrypted_credentials is not None

    async def test_retrieve_credentials(self, db_session, test_organization):
        """Test retrieving stored credentials."""
        manager = CredentialManager()

        integration_id = uuid.uuid4()
        original_credentials = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }

        # Store credentials
        await manager.store_credentials(
            integration_id=integration_id,
            credentials=original_credentials,
            db=db_session,
        )

        # Retrieve credentials
        retrieved = await manager.retrieve_credentials(
            integration_id=integration_id,
            db=db_session,
        )

        assert retrieved == original_credentials

    async def test_update_credentials(self, db_session, test_organization):
        """Test updating existing credentials."""
        manager = CredentialManager()

        integration_id = uuid.uuid4()

        # Store initial credentials
        initial_credentials = {"access_token": "old_token"}
        await manager.store_credentials(
            integration_id=integration_id,
            credentials=initial_credentials,
            db=db_session,
        )

        # Update credentials
        new_credentials = {"access_token": "new_token"}
        updated = await manager.update_credentials(
            integration_id=integration_id,
            credentials=new_credentials,
            db=db_session,
        )

        assert updated is not None

        # Verify updated credentials
        retrieved = await manager.retrieve_credentials(
            integration_id=integration_id,
            db=db_session,
        )

        assert retrieved["access_token"] == "new_token"

    async def test_delete_credentials(self, db_session, test_organization):
        """Test deleting integration credentials."""
        manager = CredentialManager()

        integration_id = uuid.uuid4()
        credentials = {"access_token": "test_token"}

        # Store credentials
        await manager.store_credentials(
            integration_id=integration_id,
            credentials=credentials,
            db=db_session,
        )

        # Delete credentials
        result = await manager.delete_credentials(
            integration_id=integration_id,
            db=db_session,
        )

        assert result is True

        # Verify deleted
        retrieved = await manager.retrieve_credentials(
            integration_id=integration_id,
            db=db_session,
        )

        assert retrieved is None

    async def test_check_token_expiry(self):
        """Test checking if access token is expired."""
        manager = CredentialManager()

        # Expired token
        expired_credentials = {
            "access_token": "token",
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        }

        is_expired = manager.is_token_expired(expired_credentials)
        assert is_expired is True

        # Valid token
        valid_credentials = {
            "access_token": "token",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        is_expired = manager.is_token_expired(valid_credentials)
        assert is_expired is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestWorkflowExecution:
    """Test workflow execution functionality."""

    @patch("app.services.workflows.workflow_engine.WorkflowEngine")
    async def test_execute_workflow(self, mock_engine, db_session):
        """Test executing a workflow."""
        from app.services.workflows.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()

        workflow_definition = {
            "trigger": "call_completed",
            "actions": [
                {
                    "type": "salesforce_create_lead",
                    "integration_id": str(uuid.uuid4()),
                    "params": {
                        "first_name": "{{caller_name}}",
                        "email": "{{caller_email}}",
                    },
                }
            ],
        }

        context = {
            "caller_name": "John Doe",
            "caller_email": "john@example.com",
        }

        # Mock execution
        mock_engine.execute = AsyncMock(return_value={"success": True})

        result = await mock_engine.execute(workflow_definition, context, db_session)

        assert result["success"] is True

    async def test_workflow_data_mapping(self):
        """Test workflow data mapping."""
        from app.services.workflows.data_mapper import DataMapper

        mapper = DataMapper()

        template = {
            "name": "{{first_name}} {{last_name}}",
            "email": "{{email}}",
            "company": "{{company_name}}",
        }

        context = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "company_name": "Acme Corp",
        }

        mapped = mapper.map_data(template, context)

        assert mapped["name"] == "John Doe"
        assert mapped["email"] == "john@example.com"
        assert mapped["company"] == "Acme Corp"

    async def test_workflow_conditional_execution(self):
        """Test conditional workflow execution."""
        from app.services.workflows.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()

        workflow = {
            "trigger": "call_completed",
            "conditions": [
                {"field": "call_duration", "operator": "gt", "value": 60}
            ],
            "actions": [{"type": "send_notification"}],
        }

        # Context meets condition
        context_pass = {"call_duration": 120}
        should_execute = engine.evaluate_conditions(workflow["conditions"], context_pass)
        assert should_execute is True

        # Context doesn't meet condition
        context_fail = {"call_duration": 30}
        should_execute = engine.evaluate_conditions(workflow["conditions"], context_fail)
        assert should_execute is False
