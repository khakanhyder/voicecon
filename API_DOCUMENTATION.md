# Voicecon API Documentation

**Version:** 1.0.0
**Base URL:** `https://api.voicecon.com`
**Last Updated:** December 19, 2025

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Rate Limiting](#rate-limiting)
4. [Endpoints](#endpoints)
   - [Authentication](#authentication-endpoints)
   - [Agents](#agents-endpoints)
   - [Calls](#calls-endpoints)
   - [Integrations](#integrations-endpoints)
   - [Workflows](#workflows-endpoints)
   - [Analytics](#analytics-endpoints)
   - [Billing](#billing-endpoints)
   - [Marketplace](#marketplace-endpoints)
5. [Webhooks](#webhooks)
6. [Error Handling](#error-handling)
7. [SDKs & Tools](#sdks--tools)

---

## Quick Start

### 1. Register an Account

```bash
curl -X POST https://api.voicecon.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "full_name": "John Doe",
    "company_name": "Acme Corp"
  }'
```

### 2. Login

```bash
curl -X POST https://api.voicecon.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

### 3. Use the API

```bash
curl https://api.voicecon.com/api/v1/agents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Authentication

Voicecon API uses **JWT (JSON Web Tokens)** for authentication.

### Bearer Token Authentication

Include your access token in the `Authorization` header:

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Token Lifetimes

- **Access Token**: 7 days
- **Refresh Token**: 30 days

### Refreshing Tokens

```bash
curl -X POST https://api.voicecon.com/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

---

## Rate Limiting

API requests are rate-limited per user/IP address:

| Endpoint Type | Limit |
|--------------|-------|
| Authentication | 5 requests/minute |
| Voice/LLM Operations | 5 requests/minute |
| Write Operations (POST/PUT/DELETE) | 30 requests/minute |
| Read Operations (GET) | 60 requests/minute |

### Rate Limit Headers

Every response includes rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1672531200
```

### Rate Limit Exceeded Response

```json
{
  "error": "RateLimitExceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 45
}
```

**HTTP Status:** `429 Too Many Requests`

---

## Endpoints

### Authentication Endpoints

#### Register User

```http
POST /api/v1/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe",
  "company_name": "Acme Corp"
}
```

**Response:** `201 Created`
```json
{
  "message": "User registered successfully",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

---

#### Login

```http
POST /api/v1/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

---

#### Get Current User

```http
GET /api/v1/auth/me
```

**Headers:**
```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "company_name": "Acme Corp",
  "is_verified": true,
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### Agents Endpoints

#### Create Agent

```http
POST /api/v1/agents
```

**Request Body:**
```json
{
  "name": "Customer Support Agent",
  "description": "Handles customer inquiries with empathy",
  "system_prompt": "You are a helpful customer support agent. Be friendly and professional.",
  "first_message": "Hello! How can I help you today?",
  "llm_provider": "openai",
  "llm_model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 500,
  "voice_provider": "elevenlabs",
  "voice_id": "rachel"
}
```

**Response:** `201 Created`
```json
{
  "id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "name": "Customer Support Agent",
  "description": "Handles customer inquiries with empathy",
  "system_prompt": "You are a helpful customer support agent...",
  "is_active": true,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

#### List Agents

```http
GET /api/v1/agents?limit=20&offset=0&search=support&is_active=true
```

**Query Parameters:**
- `limit` (optional): Items per page (default: 20, max: 100)
- `offset` (optional): Number of items to skip (default: 0)
- `search` (optional): Search by name or description
- `is_active` (optional): Filter by active status

**Response:** `200 OK`
```json
{
  "agents": [
    {
      "id": "agent-550e8400-e29b-41d4-a716-446655440000",
      "name": "Customer Support Agent",
      "description": "Handles customer inquiries",
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

#### Get Agent

```http
GET /api/v1/agents/{agent_id}
```

**Response:** `200 OK`
```json
{
  "id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "name": "Customer Support Agent",
  "description": "Handles customer inquiries",
  "system_prompt": "You are a helpful customer support agent...",
  "first_message": "Hello! How can I help you today?",
  "llm_provider": "openai",
  "llm_model": "gpt-4",
  "temperature": 0.7,
  "is_active": true,
  "stats": {
    "total_calls": 150,
    "average_duration": 180,
    "success_rate": 0.95
  },
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

#### Update Agent

```http
PUT /api/v1/agents/{agent_id}
```

**Request Body:**
```json
{
  "name": "Updated Agent Name",
  "description": "Updated description",
  "temperature": 0.8
}
```

**Response:** `200 OK`

---

#### Delete Agent

```http
DELETE /api/v1/agents/{agent_id}
```

**Response:** `200 OK`
```json
{
  "message": "Agent deleted successfully"
}
```

---

#### Test Agent

```http
POST /api/v1/agents/{agent_id}/test
```

**Request Body:**
```json
{
  "message": "Hello, can you help me?"
}
```

**Response:** `200 OK`
```json
{
  "response": "Of course! I'd be happy to help. What can I assist you with today?",
  "tokens_used": 45,
  "latency_ms": 850
}
```

---

### Calls Endpoints

#### List Calls

```http
GET /api/v1/calls?limit=20&status=completed&direction=inbound
```

**Query Parameters:**
- `limit`, `offset`: Pagination
- `status`: Filter by status (initiated, in_progress, completed, failed)
- `direction`: Filter by direction (inbound, outbound)
- `agent_id`: Filter by agent
- `start_date`, `end_date`: Date range filter

**Response:** `200 OK`
```json
{
  "calls": [
    {
      "id": "call-650e8400-e29b-41d4-a716-446655440000",
      "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
      "phone_number": "+1234567890",
      "direction": "inbound",
      "status": "completed",
      "duration_seconds": 180,
      "started_at": "2025-01-01T10:00:00Z",
      "ended_at": "2025-01-01T10:03:00Z"
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

---

#### Get Call Details

```http
GET /api/v1/calls/{call_id}
```

**Response:** `200 OK`
```json
{
  "id": "call-650e8400-e29b-41d4-a716-446655440000",
  "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "phone_number": "+1234567890",
  "direction": "inbound",
  "status": "completed",
  "duration_seconds": 180,
  "recording_url": "https://recordings.voicecon.com/call123.mp3",
  "cost": 0.45,
  "started_at": "2025-01-01T10:00:00Z",
  "ended_at": "2025-01-01T10:03:00Z"
}
```

---

#### Get Call Transcript

```http
GET /api/v1/calls/{call_id}/transcript
```

**Response:** `200 OK`
```json
{
  "call_id": "call-650e8400-e29b-41d4-a716-446655440000",
  "transcript": [
    {
      "speaker": "user",
      "message": "Hello, I need help with my order",
      "timestamp": "2025-01-01T10:00:05Z"
    },
    {
      "speaker": "agent",
      "message": "Of course! I'd be happy to help. Can you provide your order number?",
      "timestamp": "2025-01-01T10:00:10Z"
    }
  ]
}
```

---

#### Create Outbound Call

```http
POST /api/v1/calls
```

**Request Body:**
```json
{
  "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "phone_number": "+1234567890",
  "direction": "outbound"
}
```

**Response:** `201 Created`
```json
{
  "id": "call-750e8400-e29b-41d4-a716-446655440000",
  "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "phone_number": "+1234567890",
  "direction": "outbound",
  "status": "initiated",
  "created_at": "2025-01-01T10:00:00Z"
}
```

---

### Integrations Endpoints

#### List Available Integrations

```http
GET /api/v1/integrations/available
```

**Response:** `200 OK`
```json
{
  "integrations": [
    {
      "slug": "salesforce",
      "name": "Salesforce",
      "category": "crm",
      "auth_type": "oauth2",
      "description": "Connect your Salesforce CRM",
      "logo_url": "https://cdn.voicecon.com/logos/salesforce.svg"
    },
    {
      "slug": "hubspot",
      "name": "HubSpot",
      "category": "crm",
      "auth_type": "oauth2",
      "description": "Connect your HubSpot CRM"
    }
  ]
}
```

---

#### Create Integration

```http
POST /api/v1/integrations
```

**Request Body:**
```json
{
  "integration_type": "salesforce",
  "name": "My Salesforce Integration",
  "config": {
    "domain": "mycompany.salesforce.com",
    "api_version": "v54.0"
  }
}
```

**Response:** `201 Created`

---

#### Test Integration

```http
POST /api/v1/integrations/{integration_id}/test
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Connection successful",
  "details": {
    "connected_at": "2025-01-01T10:00:00Z",
    "api_version": "v54.0"
  }
}
```

---

### Workflows Endpoints

#### Create Workflow

```http
POST /api/v1/workflows
```

**Request Body:**
```json
{
  "name": "Salesforce Lead Creation",
  "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
  "trigger": "call_completed",
  "workflow_definition": {
    "conditions": [
      {
        "field": "call_duration",
        "operator": "gt",
        "value": 60
      }
    ],
    "actions": [
      {
        "type": "salesforce_create_lead",
        "integration_id": "integration-850e8400-e29b-41d4-a716-446655440000",
        "params": {
          "FirstName": "{{caller_name}}",
          "Email": "{{caller_email}}",
          "LeadSource": "Voice Call"
        }
      }
    ]
  }
}
```

**Response:** `201 Created`

---

#### Execute Workflow

```http
POST /api/v1/workflows/{workflow_id}/execute
```

**Request Body:**
```json
{
  "context": {
    "caller_name": "John Doe",
    "caller_email": "john@example.com",
    "call_duration": 180
  }
}
```

**Response:** `200 OK`
```json
{
  "execution_id": "exec-950e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "success": true,
    "lead_id": "00Q1234567890ABC"
  },
  "executed_at": "2025-01-01T10:00:00Z"
}
```

---

### Analytics Endpoints

#### Get Call Metrics

```http
GET /api/v1/analytics/calls/metrics?start_date=2025-01-01&end_date=2025-01-31
```

**Response:** `200 OK`
```json
{
  "total_calls": 500,
  "completed_calls": 475,
  "failed_calls": 25,
  "average_duration": 185,
  "total_minutes": 1462,
  "success_rate": 0.95,
  "total_cost": 219.30
}
```

---

#### Get Agent Performance

```http
GET /api/v1/analytics/agents/metrics
```

**Response:** `200 OK`
```json
{
  "agents": [
    {
      "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
      "agent_name": "Customer Support Agent",
      "total_calls": 150,
      "average_duration": 180,
      "success_rate": 0.96,
      "customer_satisfaction": 4.5
    }
  ]
}
```

---

### Billing Endpoints

#### List Subscription Plans

```http
GET /api/v1/billing/plans
```

**Response:** `200 OK`
```json
{
  "plans": [
    {
      "id": "plan-starter",
      "name": "Starter",
      "price_monthly": 99.00,
      "included_minutes": 1000,
      "included_calls": 500,
      "features": ["5 Agents", "Basic Analytics", "Email Support"]
    },
    {
      "id": "plan-professional",
      "name": "Professional",
      "price_monthly": 299.00,
      "included_minutes": 5000,
      "included_calls": 2000,
      "features": ["Unlimited Agents", "Advanced Analytics", "Priority Support"]
    }
  ]
}
```

---

#### Get Current Usage

```http
GET /api/v1/billing/usage
```

**Response:** `200 OK`
```json
{
  "current_period_start": "2025-01-01T00:00:00Z",
  "current_period_end": "2025-01-31T23:59:59Z",
  "minutes_used": 750,
  "minutes_included": 1000,
  "minutes_remaining": 250,
  "calls_used": 350,
  "calls_included": 500,
  "calls_remaining": 150,
  "overage_charges": 0.00,
  "estimated_total": 99.00
}
```

---

### Marketplace Endpoints

#### List Agent Templates

```http
GET /api/v1/marketplace/templates/agents?category=customer_support&sort_by=popular
```

**Response:** `200 OK`
```json
{
  "templates": [
    {
      "slug": "customer-support-agent",
      "name": "Customer Support Agent",
      "description": "Pre-configured agent for customer support",
      "category": "customer_support",
      "version": "2.1.0",
      "install_count": 1250,
      "average_rating": 4.8,
      "is_official": true
    }
  ]
}
```

---

#### Install Template

```http
POST /api/v1/marketplace/templates/agents/{slug}/install
```

**Request Body:**
```json
{
  "customizations": {
    "company_name": "Acme Corp",
    "support_hours": "9 AM - 5 PM EST"
  }
}
```

**Response:** `201 Created`
```json
{
  "agent_id": "agent-a50e8400-e29b-41d4-a716-446655440000",
  "name": "Customer Support Agent - Acme Corp",
  "installed_at": "2025-01-01T10:00:00Z"
}
```

---

## Webhooks

Voicecon can send webhook notifications to your server for important events.

### Webhook Events

| Event | Description |
|-------|-------------|
| `call.completed` | Call has ended |
| `call.failed` | Call failed to connect |
| `workflow.executed` | Workflow execution completed |
| `agent.status_changed` | Agent activated or deactivated |

### Webhook Payload

```json
{
  "event": "call.completed",
  "timestamp": "2025-01-01T10:00:00Z",
  "data": {
    "call_id": "call-650e8400-e29b-41d4-a716-446655440000",
    "agent_id": "agent-550e8400-e29b-41d4-a716-446655440000",
    "duration_seconds": 180,
    "status": "completed"
  }
}
```

### Webhook Signature Verification

Verify webhook authenticity using HMAC-SHA256:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    computed = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, computed)
```

---

## Error Handling

### Error Response Format

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "details": {
    "field": "email",
    "issue": "Invalid email format"
  }
}
```

### Common Error Codes

| Status Code | Error Type | Description |
|------------|------------|-------------|
| 400 | BadRequest | Invalid request data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | NotFound | Resource not found |
| 422 | ValidationError | Input validation failed |
| 429 | RateLimitExceeded | Too many requests |
| 500 | InternalServerError | Server error |

---

## SDKs & Tools

### Python SDK

```bash
pip install voicecon
```

```python
from voicecon import VoiceconClient

client = VoiceconClient(api_key="YOUR_API_KEY")

# Create an agent
agent = client.agents.create(
    name="Support Agent",
    system_prompt="You are helpful..."
)

# List calls
calls = client.calls.list(limit=10)
```

### Node.js SDK

```bash
npm install @voicecon/sdk
```

```javascript
const Voicecon = require('@voicecon/sdk');

const client = new Voicecon({ apiKey: 'YOUR_API_KEY' });

// Create an agent
const agent = await client.agents.create({
  name: 'Support Agent',
  systemPrompt: 'You are helpful...'
});
```

### Postman Collection

Download our Postman collection: [Voicecon API Collection](https://docs.voicecon.com/postman)

---

## Support

- **Documentation**: https://docs.voicecon.com
- **API Status**: https://status.voicecon.com
- **Support**: support@voicecon.com
- **Discord Community**: https://discord.gg/voicecon

---

**Last Updated:** December 19, 2025
**API Version:** 1.0.0
