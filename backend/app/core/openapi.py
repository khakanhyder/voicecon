"""
OpenAPI/Swagger Configuration for Voicecon API.

Enhanced API documentation with examples, security schemes, and metadata.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.api_keys import API_KEY_HEADER

def custom_openapi(app: FastAPI):
    """
    Generate custom OpenAPI schema with enhanced documentation.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Voicecon API",
        version="1.0.0",
        description="""
# Voicecon Voice AI Platform API

## Overview

Voicecon is a comprehensive Voice AI platform that enables you to:
- Create and manage AI-powered voice agents
- Handle inbound and outbound phone calls
- Integrate with popular CRM and communication tools
- Analyze call performance and metrics
- Automate workflows with integrations

## Authentication

Two credentials are accepted, and every endpoint takes either one.

### Login tokens (for the dashboard)

Short-lived JWTs from `POST /api/v1/auth/login`:

```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

1. **Register an account**: `POST /api/v1/auth/register`
2. **Login**: `POST /api/v1/auth/login` - Returns access_token
3. **Use token**: Include in Authorization header for all requests

### API keys (for servers and integrations)

Create one under **Settings → API Keys** (`POST /api/v1/api-keys`). The secret is
shown exactly once — store it somewhere safe. Send it either way:

```
Authorization: Bearer vcon_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
X-API-Key: vcon_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Keys differ from login tokens in three ways:

- **Workspace-bound.** A key acts only in the workspace it was created in.
  `X-Organization-Id` is rejected if it names any other workspace.
- **Scoped.** A key with `scopes` may do only those things. An empty `scopes`
  list means "everything the creating user's role allows". Either way a key can
  never exceed its creator's role — demote them and the key narrows with them.
- **Never able to escalate.** Minting keys, managing the team, changing billing,
  and deleting or transferring the workspace always require an interactive
  login, so a leaked key can't entrench itself or lock you out. `GET
  /api/v1/api-keys/scopes` lists everything a key *can* be granted.

Revoke a compromised key with `DELETE /api/v1/api-keys/{id}`, or disable it
reversibly with `PATCH /api/v1/api-keys/{id}` `{"is_active": false}`. Either
takes effect on the next request.

## Rate Limiting

API requests are rate-limited to prevent abuse:
- Authentication endpoints: 5 requests/minute
- Write operations: 30 requests/minute
- Read operations: 60 requests/minute
- Voice/LLM operations: 5 requests/minute

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Total requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "details": {}
}
```

Common HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `429`: Too Many Requests
- `500`: Internal Server Error

## Pagination

List endpoints support pagination using query parameters:
- `limit`: Number of items per page (default: 20, max: 100)
- `offset`: Number of items to skip (default: 0)

Response format:
```json
{
  "items": [...],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

## Webhooks

Voicecon can send webhook notifications for events:
- Call completed
- Workflow executed
- Agent status changed

Webhook payloads are signed with HMAC-SHA256 for security verification.

## SDKs and Tools

- Python SDK: `pip install voicecon`
- Node.js SDK: `npm install @voicecon/sdk`
- Postman Collection: [Download](https://docs.voicecon.com/postman)

## Support

- Documentation: https://docs.voicecon.com
- API Status: https://status.voicecon.com
- Support: support@voicecon.com
        """,
        routes=app.routes,
        tags=[
            {
                "name": "Authentication",
                "description": "User registration, login, and token management"
            },
            {
                "name": "Agents",
                "description": "Create and manage AI voice agents"
            },
            {
                "name": "Calls",
                "description": "Manage voice calls and retrieve call history"
            },
            {
                "name": "Integrations",
                "description": "Connect and manage third-party integrations"
            },
            {
                "name": "Workflows",
                "description": "Create and execute automation workflows"
            },
            {
                "name": "Analytics",
                "description": "View call metrics and performance data"
            },
            {
                "name": "Billing",
                "description": "Manage subscriptions, usage, and billing"
            },
            {
                "name": "Marketplace",
                "description": "Browse and install pre-built templates"
            },
            {
                "name": "Knowledge Base",
                "description": "Manage RAG knowledge base for agents"
            },
            {
                "name": "Phone Numbers",
                "description": "Provision and manage phone numbers"
            },
        ]
    )

    # Add security schemes
    openapi_schema.setdefault("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "A login token from POST /api/v1/auth/login, or an API key "
                "(vcon_...) from Settings → API Keys. Both are sent as "
                "`Authorization: Bearer <credential>`."
            ),
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": API_KEY_HEADER,
            "description": (
                "An API key (vcon_...), for clients that reserve the "
                "Authorization header for something else."
            ),
        },
    }

    # Add global security requirement
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []}
    ]

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "https://api.voicecon.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.voicecon.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]

    # Add example responses
    openapi_schema["components"]["examples"] = {
        "AgentExample": {
            "value": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Customer Support Agent",
                "description": "Handles customer inquiries",
                "system_prompt": "You are a helpful customer support agent...",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z"
            }
        },
        "CallExample": {
            "value": {
                "id": "650e8400-e29b-41d4-a716-446655440000",
                "agent_id": "550e8400-e29b-41d4-a716-446655440000",
                "phone_number": "+1234567890",
                "direction": "inbound",
                "status": "completed",
                "duration_seconds": 180,
                "started_at": "2025-01-01T10:00:00Z",
                "ended_at": "2025-01-01T10:03:00Z"
            }
        },
        "ErrorExample": {
            "value": {
                "error": "ValidationError",
                "message": "Invalid input data",
                "details": {
                    "field": "email",
                    "issue": "Invalid email format"
                }
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def setup_openapi(app: FastAPI):
    """
    Setup custom OpenAPI documentation for the application.
    """
    app.openapi = lambda: custom_openapi(app)
