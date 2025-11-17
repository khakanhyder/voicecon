# Integration Connectors Guide

Complete guide for using and building integration connectors in the Voicecon platform.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Using Existing Connectors](#using-existing-connectors)
4. [Building Custom Connectors](#building-custom-connectors)
5. [API Reference](#api-reference)
6. [Example Implementations](#example-implementations)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Voicecon integration system provides a robust framework for connecting to third-party services like CRMs, email platforms, calendars, and more.

### Key Features

- **Secure Credential Storage**: All credentials encrypted with Fernet (AES-128 CBC)
- **OAuth2 Support**: Complete OAuth2 authorization code flow
- **Automatic Token Refresh**: OAuth2 tokens refreshed automatically before expiry
- **Rate Limiting**: Token bucket algorithm for API rate limiting
- **Retry Logic**: Exponential backoff for failed requests
- **Request Logging**: All API calls logged to database
- **Connection Testing**: Test connections before activation
- **Multiple Auth Types**: OAuth2, API Key, Basic Auth

### Supported Connectors

- **Salesforce**: CRM integration (contacts, leads, opportunities)
- **SendGrid**: Email sending and contact management
- More connectors coming soon...

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Integration System                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ IntegrationManager│  │  OAuth2Handler  │               │
│  │                  │  │                  │               │
│  │ - Connect        │  │ - State Mgmt    │               │
│  │ - Disconnect     │  │ - Token Exchange│               │
│  │ - Test           │  │ - Token Refresh │               │
│  │ - Refresh Token  │  │                 │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │CredentialManager │  │   BaseConnector  │               │
│  │                  │  │                  │               │
│  │ - Encrypt        │  │ - HTTP Client   │               │
│  │ - Decrypt        │  │ - Auth Headers  │               │
│  │ - PBKDF2 KDF     │  │ - Rate Limiting │               │
│  │                  │  │ - Retry Logic   │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │          Concrete Connectors                 │          │
│  │  ┌──────────────┐  ┌──────────────┐         │          │
│  │  │  Salesforce  │  │   SendGrid   │  ...    │          │
│  │  └──────────────┘  └──────────────┘         │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

#### IntegrationConnector
Defines available integration types (Salesforce, SendGrid, etc.)
- Base URL, API version
- Authentication configuration
- Rate limits
- Feature support flags

#### IntegrationConnection
User's connection to an integration
- Encrypted credentials
- Token expiry tracking
- Usage statistics
- Error tracking

#### IntegrationLog
Audit trail of all API requests
- Request/response details
- Duration metrics
- Success/failure status

---

## Using Existing Connectors

### 1. OAuth2 Flow (e.g., Salesforce)

#### Step 1: Initiate OAuth Flow

```bash
POST /api/v1/integrations/oauth/authorize
Content-Type: application/json

{
  "connector_id": "salesforce-connector-uuid",
  "redirect_uri": "https://your-app.com/oauth/callback",
  "scopes": ["api", "refresh_token"]
}
```

Response:
```json
{
  "authorization_url": "https://login.salesforce.com/services/oauth2/authorize?...",
  "state": "random-state-token"
}
```

#### Step 2: Redirect User

Redirect the user to the `authorization_url`. After authorization, the user will be redirected back to your `redirect_uri` with a `code` parameter.

#### Step 3: Complete OAuth Flow

```bash
POST /api/v1/integrations/oauth/callback?redirect_uri=https://your-app.com/oauth/callback
Content-Type: application/json

{
  "connector_id": "salesforce-connector-uuid",
  "code": "authorization-code-from-callback",
  "state": "random-state-token"
}
```

Response:
```json
{
  "id": "connection-uuid",
  "connector_id": "salesforce-connector-uuid",
  "name": "Salesforce Connection",
  "status": "active",
  "connector": {
    "name": "Salesforce",
    "slug": "salesforce"
  }
}
```

### 2. API Key Authentication (e.g., SendGrid)

```bash
POST /api/v1/integrations/connections
Content-Type: application/json

{
  "connector_id": "sendgrid-connector-uuid",
  "name": "SendGrid Connection",
  "api_key_auth": {
    "api_key": "SG.your-api-key-here",
    "additional_fields": {}
  }
}
```

Response:
```json
{
  "id": "connection-uuid",
  "connector_id": "sendgrid-connector-uuid",
  "name": "SendGrid Connection",
  "status": "active"
}
```

### 3. List Connections

```bash
GET /api/v1/integrations/connections
```

Response:
```json
{
  "connections": [
    {
      "id": "connection-uuid",
      "connector_id": "salesforce-connector-uuid",
      "name": "Salesforce Connection",
      "status": "active",
      "connector": {
        "name": "Salesforce",
        "slug": "salesforce"
      },
      "last_sync_at": "2025-01-15T10:30:00Z",
      "error_count": 0
    }
  ],
  "total": 1
}
```

### 4. Test Connection

```bash
POST /api/v1/integrations/connections/{connection_id}/test
```

Response:
```json
{
  "success": true,
  "message": "Connection test successful",
  "details": {
    "user_id": "005...",
    "organization_id": "00D...",
    "email": "user@example.com"
  },
  "response_time_ms": 234
}
```

### 5. Refresh OAuth Token (Manual)

```bash
POST /api/v1/integrations/oauth/refresh
Content-Type: application/json

{
  "connection_id": "connection-uuid"
}
```

Response:
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "token_expires_at": "2025-01-15T12:00:00Z"
}
```

### 6. Get Connection Statistics

```bash
GET /api/v1/integrations/connections/{connection_id}/stats
```

Response:
```json
{
  "connection_id": "connection-uuid",
  "total_api_calls": 1523,
  "successful_calls": 1501,
  "failed_calls": 22,
  "average_response_time_ms": 245.3,
  "last_24h_calls": 87,
  "error_rate_percent": 1.44
}
```

### 7. Disconnect Integration

```bash
DELETE /api/v1/integrations/connections/{connection_id}
```

---

## Building Custom Connectors

### 1. Create Connector Class

Create a new file in `app/services/integrations/connectors/`:

```python
"""
Custom Connector.

Integration with Custom API.
"""
import logging
from typing import Dict, Any, Optional

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class CustomConnector(BaseConnector):
    """
    Custom API connector.

    Provides methods to interact with Custom API.
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection by calling a simple endpoint.

        Returns:
            Test result dictionary with:
            - success: bool
            - message: str
            - details: dict
        """
        try:
            # Call a simple endpoint to test auth
            user_info = await self.get("/api/v1/user")

            return {
                "success": True,
                "message": "Connection successful",
                "details": {
                    "user_id": user_info.get("id"),
                    "email": user_info.get("email"),
                },
            }

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "details": {},
            }

    # Add your custom methods
    async def create_record(
        self,
        record_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a record in the external system.

        Args:
            record_type: Type of record to create
            data: Record data

        Returns:
            Created record with ID

        Raises:
            ConnectorError: If creation fails
        """
        try:
            response = await self.post(
                f"/api/v1/{record_type}",
                json=data,
            )

            logger.info(f"Record created: {response.get('id')}")
            return response

        except Exception as e:
            logger.error(f"Failed to create record: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create record: {str(e)}")
```

### 2. Register Connector in Database

Create a migration or script to add the connector to the database:

```python
from app.models.integration import IntegrationConnector

connector = IntegrationConnector(
    name="Custom Service",
    slug="custom-service",
    category="crm",  # or "email", "calendar", "storage", etc.
    description="Integration with Custom Service API",
    logo_url="https://example.com/logo.png",

    # API Configuration
    base_url="https://api.customservice.com",
    api_version="v1",

    # Authentication
    auth_type="oauth2",  # or "api_key", "basic"
    auth_config={
        # OAuth2 Configuration
        "authorize_url": "https://api.customservice.com/oauth/authorize",
        "token_url": "https://api.customservice.com/oauth/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret",
        "scopes": ["read", "write"],

        # For API Key auth:
        # "api_key_location": "header",  # or "query"
        # "api_key_name": "X-API-Key",
        # "api_key_format": "{api_key}",  # or "Bearer {api_key}"

        # Test endpoint
        "test_endpoint": "/api/v1/user",
    },

    # Features
    supports_triggers=False,
    supports_actions=True,
    supports_realtime=False,
    supports_webhooks=False,

    # Rate Limits
    rate_limit_per_minute=60,
    rate_limit_per_hour=1000,
    rate_limit_per_day=10000,

    # Documentation
    documentation_url="https://docs.customservice.com/api",
    setup_instructions="1. Create API credentials...",

    is_active=True,
    is_beta=False,
    is_premium=False,
)

db.add(connector)
await db.commit()
```

### 3. Use Your Connector

```python
from sqlalchemy import select
from app.models.integration import IntegrationConnector, IntegrationConnection
from app.services.integrations.connectors.custom_connector import CustomConnector

# Get connector and connection
connector_query = select(IntegrationConnector).where(
    IntegrationConnector.slug == "custom-service"
)
connector = (await db.execute(connector_query)).scalar_one()

connection_query = select(IntegrationConnection).where(
    IntegrationConnection.connector_id == connector.id,
    IntegrationConnection.user_id == user_id,
)
connection = (await db.execute(connection_query)).scalar_one()

# Initialize connector
custom_connector = CustomConnector(
    connection=connection,
    connector=connector,
    db=db,
)

# Use connector methods
try:
    result = await custom_connector.create_record(
        record_type="contacts",
        data={
            "name": "John Doe",
            "email": "john@example.com",
        }
    )
    print(f"Created record: {result}")

finally:
    await custom_connector.close()
```

---

## API Reference

### BaseConnector Methods

#### `async def get_access_token() -> str`
Get access token, handling OAuth2 refresh if needed.

#### `def get_auth_headers(access_token: str) -> Dict[str, str]`
Build authentication headers for requests.

#### `async def make_request(method, endpoint, params, json, data, headers) -> Dict[str, Any]`
Make authenticated API request with logging and error handling.

#### `async def refresh_token() -> None`
Refresh OAuth2 access token (OAuth2 only).

#### `async def test_connection() -> Dict[str, Any]` (Abstract)
Test connection to integration. Must be implemented by subclasses.

#### Convenience Methods
- `async def get(endpoint, **kwargs)`
- `async def post(endpoint, **kwargs)`
- `async def put(endpoint, **kwargs)`
- `async def patch(endpoint, **kwargs)`
- `async def delete(endpoint, **kwargs)`

### IntegrationManager Methods

#### `async def initiate_oauth_flow(connector, user_id, redirect_uri, scopes)`
Initiate OAuth2 authorization flow.

#### `async def complete_oauth_flow(connector, code, state, redirect_uri, user_id, organization_id, db)`
Complete OAuth2 flow and create connection.

#### `async def connect_with_api_key(connector, api_key, user_id, organization_id, db)`
Create connection with API key authentication.

#### `async def test_connection(connection, connector)`
Test an integration connection.

#### `async def refresh_token(connection, connector, db)`
Refresh OAuth2 access token.

#### `async def disconnect_integration(connection, db)`
Disconnect integration.

---

## Example Implementations

### Salesforce Connector Examples

#### Create Contact

```python
from app.services.integrations.connectors import SalesforceConnector

# Initialize connector (see "Use Your Connector" section)
salesforce = SalesforceConnector(connection, connector, db)

try:
    # Create contact
    result = await salesforce.create_contact(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        additional_fields={
            "Title": "Software Engineer",
            "Company": "Acme Inc",
        }
    )

    print(f"Contact created: {result['id']}")

finally:
    await salesforce.close()
```

#### Search Contacts

```python
# Search by email
contacts = await salesforce.search_contacts(
    email="john.doe@example.com"
)

for contact in contacts:
    print(f"{contact['FirstName']} {contact['LastName']}: {contact['Email']}")
```

#### Create Lead

```python
result = await salesforce.create_lead(
    first_name="Jane",
    last_name="Smith",
    company="Tech Corp",
    email="jane@techcorp.com",
    phone="+1987654321",
    status="Open - Not Contacted",
)
```

#### SOQL Query

```python
result = await salesforce.query(
    "SELECT Id, Name, Email FROM Contact WHERE Email LIKE '%@example.com%' LIMIT 10"
)

print(f"Found {result['total_size']} contacts")
for record in result['records']:
    print(f"{record['Name']}: {record['Email']}")
```

### SendGrid Connector Examples

#### Send Email

```python
from app.services.integrations.connectors import SendGridConnector

sendgrid = SendGridConnector(connection, connector, db)

try:
    result = await sendgrid.send_email(
        to_email="recipient@example.com",
        from_email="sender@yourapp.com",
        subject="Welcome to Voicecon!",
        html_content="<h1>Welcome!</h1><p>Thanks for signing up.</p>",
        text_content="Welcome! Thanks for signing up.",
        to_name="John Doe",
        from_name="Voicecon Team",
    )

    print("Email sent successfully")

finally:
    await sendgrid.close()
```

#### Send Template Email

```python
result = await sendgrid.send_template_email(
    to_email="user@example.com",
    from_email="noreply@yourapp.com",
    template_id="d-1234567890abcdef",
    dynamic_template_data={
        "user_name": "John Doe",
        "verification_link": "https://yourapp.com/verify?token=...",
    },
    to_name="John Doe",
)
```

#### Add Contact to List

```python
# Add contact
result = await sendgrid.add_contact(
    email="new.user@example.com",
    first_name="New",
    last_name="User",
    list_ids=["list-id-1", "list-id-2"],
)

print(f"Contact added with job ID: {result['job_id']}")
```

#### Get Email Statistics

```python
stats = await sendgrid.get_stats(
    start_date="2025-01-01",
    end_date="2025-01-31",
    aggregated_by="day",
)

for day_stats in stats['stats']:
    print(f"Date: {day_stats['date']}")
    print(f"Delivered: {day_stats['stats'][0]['metrics']['delivered']}")
    print(f"Opens: {day_stats['stats'][0]['metrics']['unique_opens']}")
```

---

## Best Practices

### 1. Error Handling

Always wrap connector calls in try/except blocks:

```python
try:
    result = await connector.create_contact(...)
except ConnectorError as e:
    logger.error(f"Connector error: {e}")
    # Handle error gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Handle unexpected errors
finally:
    await connector.close()
```

### 2. Rate Limiting

The connector automatically handles rate limiting, but be mindful of your usage:

```python
# Good: Single batch operation
contacts = [...]  # List of 100 contacts
await connector.bulk_create_contacts(contacts)

# Bad: Many individual calls
for contact in contacts:
    await connector.create_contact(contact)  # 100 API calls!
```

### 3. Connection Testing

Always test connections before using them in production:

```python
# Test before use
test_result = await manager.test_connection(connection, connector)
if not test_result["success"]:
    raise Exception(f"Connection test failed: {test_result['message']}")

# Proceed with operations
connector = SalesforceConnector(connection, connector, db)
```

### 4. Token Refresh

OAuth2 tokens are automatically refreshed, but you can manually trigger refresh:

```python
# Manual token refresh
manager = get_integration_manager()
await manager.refresh_token(connection, connector, db)
```

### 5. Logging and Monitoring

All API calls are automatically logged. Monitor your integration health:

```python
# Get connection statistics
stats = await get_connection_stats(connection_id)
print(f"Error rate: {stats['error_rate_percent']}%")
print(f"Avg response time: {stats['average_response_time_ms']}ms")

# Alert if error rate is high
if stats['error_rate_percent'] > 5.0:
    send_alert("High error rate on integration")
```

### 6. Security

- **Never log credentials**: Credentials are automatically redacted in logs
- **Use environment variables**: Store sensitive config in environment variables
- **Rotate keys regularly**: Implement key rotation for API keys
- **Monitor access**: Review integration logs regularly

```python
# Good: Credentials never appear in logs
logger.info(f"Connecting to {connector.name}")

# Bad: Don't log credentials
logger.info(f"API Key: {api_key}")  # DON'T DO THIS!
```

---

## Troubleshooting

### Common Issues

#### 1. OAuth2 State Expired

**Error**: `Invalid or expired state parameter`

**Solution**: OAuth2 state tokens expire after 10 minutes. Complete the flow faster or reinitiate.

```python
# Reinitiate OAuth flow
oauth_data = await manager.initiate_oauth_flow(...)
# Redirect user immediately
```

#### 2. Token Refresh Failed

**Error**: `Token refresh failed: Invalid refresh token`

**Solution**: Refresh token may be revoked. User needs to reconnect.

```python
# Disconnect old connection
await manager.disconnect_integration(connection, db)

# User must reconnect via OAuth flow
```

#### 3. Rate Limit Exceeded

**Error**: `Request failed: 429 Too Many Requests`

**Solution**: The connector will automatically retry with backoff. If persistent, reduce request frequency.

```python
# Configure custom retry settings
retry_config = RetryConfig(
    max_retries=5,
    initial_delay=2.0,
    max_delay=120.0,
)

http_client = IntegrationHTTPClient(
    base_url=connector.base_url,
    retry_config=retry_config,
)
```

#### 4. Connection Test Fails

**Error**: `Connection test failed with status 401`

**Solution**: Credentials may be invalid or expired.

```python
# For API Key: Verify key is correct
# For OAuth2: Refresh token or reconnect

# Test specific endpoint
test_result = await connector.get("/api/v1/user")
```

#### 5. Encryption Key Mismatch

**Error**: `Decryption failed: Invalid token`

**Solution**: `ENCRYPTION_SECRET_KEY` changed. Existing connections need to reconnect.

```python
# Users must reconnect all integrations
# Set ENCRYPTION_SECRET_KEY in environment and don't change it
```

### Debug Mode

Enable debug logging for detailed request/response info:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Connector will log all requests
connector = SalesforceConnector(connection, connector, db)
```

### Support

For additional help:
- Review integration logs in database: `IntegrationLog` table
- Check connection statistics: `/api/v1/integrations/connections/{id}/stats`
- Test connection: `/api/v1/integrations/connections/{id}/test`
- Review connector documentation: `connector.documentation_url`

---

## Summary

The Voicecon integration system provides:

✅ **Secure**: Fernet encryption with PBKDF2 key derivation
✅ **Reliable**: Automatic retry with exponential backoff
✅ **Scalable**: Token bucket rate limiting
✅ **Observable**: Complete request logging and statistics
✅ **Flexible**: Support for OAuth2, API Key, and Basic Auth
✅ **Developer-Friendly**: Simple API and extensible architecture

Start building integrations today! 🚀
