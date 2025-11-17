"""
Integration Schemas.

Pydantic schemas for integration API validation.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# Connector Schemas
class IntegrationConnectorBase(BaseModel):
    """Base integration connector schema."""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    logo_url: Optional[str] = None

    base_url: Optional[str] = None
    api_version: Optional[str] = Field(None, max_length=50)
    auth_type: str = Field(..., description="oauth2, api_key, basic, jwt")
    auth_config: Dict[str, Any] = Field(default_factory=dict)

    supports_triggers: bool = False
    supports_actions: bool = True
    supports_realtime: bool = False
    supports_webhooks: bool = False

    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None

    documentation_url: Optional[str] = None
    setup_instructions: Optional[str] = None


class IntegrationConnectorCreate(IntegrationConnectorBase):
    """Create integration connector schema."""
    pass


class IntegrationConnectorUpdate(BaseModel):
    """Update integration connector schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_beta: Optional[bool] = None
    is_premium: Optional[bool] = None


class IntegrationConnectorResponse(IntegrationConnectorBase):
    """Integration connector response schema."""
    id: str
    is_active: bool
    is_beta: bool
    is_premium: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationConnectorListResponse(BaseModel):
    """List of integration connectors."""
    connectors: List[IntegrationConnectorResponse]
    total: int
    page: int
    page_size: int


# Connection Schemas
class OAuth2AuthData(BaseModel):
    """OAuth2 authentication data."""
    code: str = Field(..., description="Authorization code from OAuth callback")
    redirect_uri: str = Field(..., description="Redirect URI used in OAuth flow")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection")


class APIKeyAuthData(BaseModel):
    """API key authentication data."""
    api_key: str = Field(..., description="API key for authentication")
    additional_fields: Dict[str, str] = Field(default_factory=dict, description="Additional auth fields")


class BasicAuthData(BaseModel):
    """Basic authentication data."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class IntegrationConnectionCreate(BaseModel):
    """Create integration connection schema."""
    connector_id: str = Field(..., description="Integration connector ID")
    name: Optional[str] = Field(None, max_length=255, description="User-defined name for connection")

    # Authentication data (one of these based on auth_type)
    oauth2_auth: Optional[OAuth2AuthData] = None
    api_key_auth: Optional[APIKeyAuthData] = None
    basic_auth: Optional[BasicAuthData] = None

    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Connection-specific configuration")

    @validator('name')
    def validate_name(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        return v


class IntegrationConnectionUpdate(BaseModel):
    """Update integration connection schema."""
    name: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class IntegrationConnectionResponse(BaseModel):
    """Integration connection response schema."""
    id: str
    user_id: str
    organization_id: str
    connector_id: str
    name: Optional[str]
    status: str

    # Connector info (nested)
    connector: IntegrationConnectorResponse

    # Metadata (no sensitive data)
    config: Dict[str, Any]
    metadata: Dict[str, Any]

    # Status
    is_active: bool
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    error_count: int

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationConnectionListResponse(BaseModel):
    """List of integration connections."""
    connections: List[IntegrationConnectionResponse]
    total: int


# OAuth2 Flow Schemas
class OAuth2AuthorizationRequest(BaseModel):
    """OAuth2 authorization request."""
    connector_id: str = Field(..., description="Integration connector ID")
    redirect_uri: str = Field(..., description="Redirect URI for OAuth callback")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection")
    scopes: List[str] = Field(default_factory=list, description="OAuth scopes to request")


class OAuth2AuthorizationResponse(BaseModel):
    """OAuth2 authorization response."""
    authorization_url: str = Field(..., description="URL to redirect user for authorization")
    state: str = Field(..., description="State parameter for verification")


class OAuth2CallbackRequest(BaseModel):
    """OAuth2 callback request."""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for verification")
    connector_id: str = Field(..., description="Integration connector ID")


class OAuth2TokenRefreshRequest(BaseModel):
    """OAuth2 token refresh request."""
    connection_id: str = Field(..., description="Integration connection ID")


class OAuth2TokenRefreshResponse(BaseModel):
    """OAuth2 token refresh response."""
    success: bool
    message: str
    token_expires_at: Optional[datetime] = None


# Connection Test Schemas
class ConnectionTestRequest(BaseModel):
    """Connection test request."""
    connection_id: Optional[str] = Field(None, description="Existing connection ID to test")
    connector_id: Optional[str] = Field(None, description="Connector ID for new connection test")
    auth_data: Optional[Dict[str, Any]] = Field(None, description="Authentication data for test")


class ConnectionTestResponse(BaseModel):
    """Connection test response."""
    success: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    response_time_ms: Optional[int] = None


# Webhook Schemas
class WebhookEventRequest(BaseModel):
    """Incoming webhook event."""
    connection_id: str
    event_type: str
    payload: Dict[str, Any]
    signature: Optional[str] = None


# Integration Action Schemas
class IntegrationActionRequest(BaseModel):
    """Execute an integration action."""
    connection_id: str = Field(..., description="Integration connection ID")
    action: str = Field(..., description="Action to execute (e.g., 'create_contact', 'send_email')")
    parameters: Dict[str, Any] = Field(..., description="Action parameters")


class IntegrationActionResponse(BaseModel):
    """Integration action response."""
    success: bool
    message: str
    result: Optional[Dict[str, Any]] = None
    execution_time_ms: int


# Sync Schemas
class SyncRequest(BaseModel):
    """Manual sync request."""
    connection_id: str
    sync_type: str = Field(..., description="Type of sync (full, incremental)")


class SyncResponse(BaseModel):
    """Sync response."""
    success: bool
    message: str
    records_synced: int
    sync_started_at: datetime
    sync_completed_at: Optional[datetime] = None


# Statistics Schemas
class ConnectionStatsResponse(BaseModel):
    """Connection statistics."""
    connection_id: str
    total_api_calls: int
    successful_calls: int
    failed_calls: int
    average_response_time_ms: float
    last_24h_calls: int
    error_rate_percent: float


class IntegrationUsageResponse(BaseModel):
    """Integration usage statistics."""
    total_connections: int
    active_connections: int
    total_api_calls_today: int
    total_api_calls_month: int
    most_used_connectors: List[Dict[str, Any]]
