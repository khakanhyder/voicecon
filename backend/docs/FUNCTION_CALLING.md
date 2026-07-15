# Agent Function Calling System

## Overview

The function calling system enables AI agents to execute external functions via webhooks during conversations. This allows agents to:
- Query external APIs and databases
- Book appointments and reservations
- Check order status, inventory levels
- Perform calculations and transformations
- Integrate with third-party services

**Features:**
- ✅ JSON Schema parameter validation
- ✅ HTTP webhook execution (GET, POST, PUT, PATCH)
- ✅ Automatic retry with exponential backoff
- ✅ Configurable timeout handling
- ✅ Execution logging and cost tracking
- ✅ Real-time function calling during voice conversations
- ✅ OpenAI function calling format support

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Voice Conversation                      │
│                                                          │
│  User: "What's the status of order #12345?"            │
│    │                                                     │
│    ├─> STT (Deepgram)                                   │
│    │                                                     │
│    ├─> LLM (GPT-4) with functions                       │
│    │     ├─> Detects function call needed               │
│    │     └─> Calls: check_order_status(order_id="12345")│
│    │                                                     │
│    ├─> FunctionExecutor                                 │
│    │     ├─> Validates parameters (JSON Schema)         │
│    │     ├─> HTTP POST to webhook                       │
│    │     ├─> Receives: {"status": "shipped", ...}       │
│    │     └─> Logs execution + costs                     │
│    │                                                     │
│    ├─> LLM (GPT-4) with function result                 │
│    │     └─> Generates: "Order #12345 has been shipped!"│
│    │                                                     │
│    └─> TTS (ElevenLabs)                                 │
│          └─> Speaks response to user                    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Database Schema

### AgentFunction Model

```python
class AgentFunction(Base):
    """Agent function/tool configuration."""
    __tablename__ = "agent_functions"

    id: UUID                           # Primary key
    agent_id: UUID                     # Foreign key to agent

    # Function definition
    name: str                          # Function name (e.g., "check_order_status")
    description: str                   # What the function does
    parameters: dict                   # JSON Schema for parameters

    # Webhook configuration
    webhook_url: str                   # URL to call
    http_method: str                   # GET, POST, PUT, PATCH (default: POST)
    headers: dict                      # Custom HTTP headers
    timeout: int                       # Timeout in milliseconds (default: 5000)
    retry_count: int                   # Number of retries (default: 3)

    # Settings
    is_active: bool                    # Enable/disable function
    execution_order: int               # Order of execution (if multiple)

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

---

## Creating Functions

### API Endpoint

```bash
POST /api/v1/agents/{agent_id}/functions
```

### Example: Order Status Function

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/functions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "check_order_status",
    "description": "Check the status of a customer order by order ID",
    "parameters": {
      "type": "object",
      "properties": {
        "order_id": {
          "type": "string",
          "description": "The order ID to check"
        }
      },
      "required": ["order_id"]
    },
    "webhook_url": "https://api.example.com/orders/status",
    "http_method": "POST",
    "headers": {
      "X-API-Key": "your-api-key"
    },
    "timeout": 5000,
    "retry_count": 3
  }'
```

### Example: Calendar Availability

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/functions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "check_availability",
    "description": "Check available appointment slots for a given date",
    "parameters": {
      "type": "object",
      "properties": {
        "date": {
          "type": "string",
          "format": "date",
          "description": "Date to check (YYYY-MM-DD)"
        },
        "duration_minutes": {
          "type": "integer",
          "description": "Appointment duration in minutes",
          "default": 30
        }
      },
      "required": ["date"]
    },
    "webhook_url": "https://api.example.com/calendar/availability",
    "http_method": "GET",
    "timeout": 3000
  }'
```

### Example: Customer Lookup

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/functions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_customer_info",
    "description": "Retrieve customer information by phone number or email",
    "parameters": {
      "type": "object",
      "properties": {
        "phone": {
          "type": "string",
          "description": "Customer phone number"
        },
        "email": {
          "type": "string",
          "format": "email",
          "description": "Customer email"
        }
      },
      "oneOf": [
        {"required": ["phone"]},
        {"required": ["email"]}
      ]
    },
    "webhook_url": "https://api.example.com/customers/lookup",
    "http_method": "POST",
    "timeout": 4000
  }'
```

---

## Function Execution Flow

### 1. Parameter Validation

The function executor validates parameters against the JSON Schema:

```python
# Function definition
{
  "parameters": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "pattern": "^[A-Z0-9]{8}$"
      }
    },
    "required": ["order_id"]
  }
}

# Valid call
{"order_id": "ABC12345"}  # ✅ Passes validation

# Invalid calls
{"order_id": "123"}       # ❌ Too short
{"order_id": 12345}       # ❌ Wrong type (number instead of string)
{}                        # ❌ Missing required field
```

### 2. HTTP Request

The executor makes an HTTP request to the webhook URL:

**Request:**
```http
POST https://api.example.com/orders/status
Content-Type: application/json
X-API-Key: your-api-key

{
  "order_id": "ABC12345"
}
```

**Response:**
```json
{
  "order_id": "ABC12345",
  "status": "shipped",
  "tracking_number": "1Z999AA1234567890",
  "estimated_delivery": "2025-11-20"
}
```

### 3. Retry Logic

If the request fails, the executor automatically retries with exponential backoff:

```python
# Retry schedule (3 attempts):
Attempt 1: Immediate
Attempt 2: Wait 1 second (2^0)
Attempt 3: Wait 2 seconds (2^1)
Attempt 4: Wait 4 seconds (2^2)

# Total time before giving up: ~7 seconds + 3x request time
```

### 4. Response Formatting

The executor formats the response for the LLM:

```python
# Raw response
{
  "status": "shipped",
  "tracking_number": "1Z999AA1234567890"
}

# Formatted for LLM
"""
Function check_order_status returned:
{
  "status": "shipped",
  "tracking_number": "1Z999AA1234567890",
  "estimated_delivery": "2025-11-20"
}
"""

# LLM uses this to generate natural response:
"Great news! Your order has been shipped. The tracking number is
1Z999AA1234567890, and it should arrive by November 20th."
```

---

## Testing Functions

### API Endpoint

```bash
POST /api/v1/agents/{agent_id}/functions/{function_id}/test
```

### Test Request

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/functions/{function_id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "order_id": "ABC12345"
    }
  }'
```

### Test Response

```json
{
  "success": true,
  "function_name": "check_order_status",
  "result": {
    "order_id": "ABC12345",
    "status": "shipped",
    "tracking_number": "1Z999AA1234567890"
  },
  "error": null,
  "execution_time_ms": 245,
  "formatted_result": "Function check_order_status returned:\n{\n  \"order_id\": \"ABC12345\",\n  \"status\": \"shipped\",\n  \"tracking_number\": \"1Z999AA1234567890\"\n}"
}
```

---

## Webhook Implementation Guide

### Webhook Requirements

1. **Accept JSON payload** with function parameters
2. **Return JSON response** with results
3. **Respond within timeout** (default: 5 seconds)
4. **Use standard HTTP status codes**

### Example Webhook (Express.js)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

// Order status webhook
app.post('/orders/status', async (req, res) => {
  try {
    const { order_id } = req.body;

    // Validate order ID
    if (!order_id) {
      return res.status(400).json({ error: 'Missing order_id' });
    }

    // Query database
    const order = await db.orders.findOne({ id: order_id });

    if (!order) {
      return res.status(404).json({ error: 'Order not found' });
    }

    // Return order data
    res.json({
      order_id: order.id,
      status: order.status,
      tracking_number: order.tracking_number,
      estimated_delivery: order.estimated_delivery
    });

  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.listen(3000);
```

### Example Webhook (Python/FastAPI)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class OrderStatusRequest(BaseModel):
    order_id: str

class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    tracking_number: str
    estimated_delivery: str

@app.post("/orders/status", response_model=OrderStatusResponse)
async def check_order_status(request: OrderStatusRequest):
    # Query database
    order = await db.orders.get(request.order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderStatusResponse(
        order_id=order.id,
        status=order.status,
        tracking_number=order.tracking_number,
        estimated_delivery=order.estimated_delivery
    )
```

---

## Error Handling

### Validation Errors

```json
{
  "success": false,
  "function_name": "check_order_status",
  "error": "Parameter validation failed: 'order_id' is a required property",
  "execution_time_ms": 2
}
```

### Timeout Errors

```json
{
  "success": false,
  "function_name": "check_order_status",
  "error": "Function check_order_status timed out after 3 attempts",
  "execution_time_ms": 15234
}
```

### HTTP Errors

```json
{
  "success": false,
  "function_name": "check_order_status",
  "error": "Function check_order_status failed after 3 attempts: 404 Not Found",
  "execution_time_ms": 3456
}
```

---

## Execution Logging

Every function call is logged to the `call_logs` table:

```python
CallLog(
    call_id="call-uuid",
    log_type="function_call",
    message="Function call: check_order_status",
    details={
        "function_id": "func-uuid",
        "function_name": "check_order_status",
        "parameters": {"order_id": "ABC12345"},
        "result": {"status": "shipped", ...},
        "success": true,
        "webhook_url": "https://api.example.com/orders/status",
        "http_method": "POST"
    },
    duration_ms=245,
    cost=0.001,  # $0.001 per function call
    timestamp="2025-11-16T10:30:00Z"
)
```

---

## Cost Tracking

Function calls are tracked with a flat cost of **$0.001 per execution**.

### Per-Call Breakdown

```
STT:      $0.024
LLM:      $0.025
Function: $0.001  ← Function execution
TTS:      $0.048
Telephony:$0.070
───────────────
Total:    $0.168
```

### Analytics

View function execution costs:

```bash
GET /api/v1/analytics/costs?start_date=2025-11-01
```

Response includes function costs:

```json
{
  "total_cost": 24.50,
  "function_cost": 0.50,  // 500 function calls
  "cost_breakdown": {
    "stt": 4.50,
    "llm": 7.50,
    "tts": 6.00,
    "telephony": 6.50,
    "functions": 0.50
  }
}
```

---

## Real-Time Function Calling

During voice conversations, functions are called automatically when the LLM detects the need:

### Example Conversation

```
User: "What's the status of my order ABC12345?"
  ↓
STT: Transcribes speech
  ↓
LLM: Detects need to call check_order_status
  ↓
FunctionExecutor: Calls webhook
  webhook_url: https://api.example.com/orders/status
  parameters: {"order_id": "ABC12345"}
  ↓
Webhook Response: {"status": "shipped", "tracking": "1Z999AA..."}
  ↓
LLM: Generates natural response with function result
  "Your order has been shipped! Tracking number: 1Z999AA..."
  ↓
TTS: Synthesizes speech
  ↓
User: Hears response
```

### Function Call Limits

To prevent infinite loops, a maximum of **5 function calls** per LLM response is enforced:

```python
max_function_calls = 5  # Per conversation turn

# Example chain:
1. check_customer_info() → customer data
2. check_order_history() → past orders
3. calculate_discount() → discount amount
4. create_quote() → quote details
5. send_email() → confirmation
```

---

## Advanced Features

### Custom Headers

Add authentication or custom headers:

```json
{
  "headers": {
    "Authorization": "Bearer your-token",
    "X-API-Key": "your-api-key",
    "X-Custom-Header": "custom-value"
  }
}
```

### HTTP Methods

Support for multiple HTTP methods:

```json
// GET request (parameters as query string)
{
  "http_method": "GET",
  "webhook_url": "https://api.example.com/data"
}

// POST request (parameters as JSON body)
{
  "http_method": "POST",
  "webhook_url": "https://api.example.com/data"
}

// PUT/PATCH for updates
{
  "http_method": "PUT",
  "webhook_url": "https://api.example.com/resource/{id}"
}
```

### Complex Parameters

JSON Schema supports complex validation:

```json
{
  "parameters": {
    "type": "object",
    "properties": {
      "date_range": {
        "type": "object",
        "properties": {
          "start": {"type": "string", "format": "date"},
          "end": {"type": "string", "format": "date"}
        },
        "required": ["start", "end"]
      },
      "filters": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "field": {"type": "string"},
            "operator": {"enum": ["=", "!=", ">", "<", ">=", "<="]},
            "value": {}
          }
        }
      }
    }
  }
}
```

---

## Best Practices

### 1. Function Design

**✅ Good:**
```json
{
  "name": "check_order_status",
  "description": "Check the status of a customer order by order ID. Returns order status, tracking number, and estimated delivery date."
}
```

**❌ Bad:**
```json
{
  "name": "check",
  "description": "Check stuff"
}
```

### 2. Parameter Validation

**✅ Good:**
```json
{
  "parameters": {
    "type": "object",
    "properties": {
      "phone": {
        "type": "string",
        "pattern": "^\\+?[1-9]\\d{1,14}$",
        "description": "Customer phone number in E.164 format"
      }
    },
    "required": ["phone"]
  }
}
```

**❌ Bad:**
```json
{
  "parameters": {
    "type": "object",
    "properties": {
      "phone": {"type": "string"}
    }
  }
}
```

### 3. Error Handling

**Webhook should return clear errors:**

```json
// Good error response
{
  "error": "Order ABC12345 not found",
  "error_code": "ORDER_NOT_FOUND",
  "details": {
    "order_id": "ABC12345",
    "suggestion": "Please verify the order ID"
  }
}

// Bad error response
{
  "error": "Error"
}
```

### 4. Timeout Configuration

Set appropriate timeouts based on webhook complexity:

```python
# Quick lookups: 2-3 seconds
{"timeout": 3000}

# API calls: 5 seconds (default)
{"timeout": 5000}

# Complex operations: 8-10 seconds
{"timeout": 10000}

# Maximum allowed: 30 seconds
{"timeout": 30000}
```

### 5. Security

**Never expose sensitive data in function responses:**

```json
// ✅ Good - Masked sensitive data
{
  "card_number": "****1234",
  "expiry": "12/25"
}

// ❌ Bad - Full sensitive data
{
  "card_number": "4532123456781234",
  "cvv": "123"
}
```

---

## Use Cases

### 1. E-commerce

- Check order status
- Calculate shipping costs
- Check inventory availability
- Apply discount codes
- Process returns

### 2. Appointment Booking

- Check calendar availability
- Book appointments
- Reschedule appointments
- Send confirmations
- Check-in patients

### 3. Customer Support

- Look up customer information
- Check account status
- Reset passwords
- Create support tickets
- Escalate to human agent

### 4. Sales

- Check product availability
- Calculate quotes
- Apply discounts
- Create orders
- Send proposals

### 5. Banking/Finance

- Check account balance
- Transfer funds
- Check transaction history
- Pay bills
- Report card lost/stolen

---

## Troubleshooting

### Function Not Being Called

**Check:**
1. Function is `is_active = true`
2. Agent's LLM provider is "openai" (required for function calling)
3. Function description clearly describes when to use it
4. Parameters are well-defined in JSON Schema

### Timeout Issues

**Solutions:**
1. Increase timeout: `{"timeout": 10000}`
2. Increase retry count: `{"retry_count": 5}`
3. Optimize webhook performance
4. Use async processing with callback

### Validation Errors

**Debug:**
1. Test function with `/agents/{id}/functions/{func_id}/test`
2. Check JSON Schema syntax
3. Verify parameter types match schema
4. Review error message for specific validation failure

---

## API Reference

### Create Function

```
POST /api/v1/agents/{agent_id}/functions
```

### List Functions

```
GET /api/v1/agents/{agent_id}/functions
```

### Delete Function

```
DELETE /api/v1/agents/{agent_id}/functions/{function_id}
```

### Test Function

```
POST /api/v1/agents/{agent_id}/functions/{function_id}/test
```

---

## Summary

The function calling system enables powerful integrations with external services:

✅ **JSON Schema validation** - Type-safe parameter validation
✅ **Automatic retries** - Exponential backoff for reliability
✅ **Timeout handling** - Configurable timeouts per function
✅ **Real-time execution** - Functions called during live conversations
✅ **Cost tracking** - $0.001 per execution logged
✅ **Error handling** - Comprehensive error reporting
✅ **Testing interface** - Test functions before deploying
✅ **OpenAI integration** - Native function calling support

**Ready to build intelligent agents that can take actions!** 🚀

---

**See also:**
- [Agent Management](AGENT_MANAGEMENT.md)
- [Voice Streaming](VOICE_STREAMING.md)
- [Call Management](CALL_MANAGEMENT.md)
