# Twilio Telephony Integration

Complete implementation of Twilio telephony service for real phone call handling.

## Overview

The Voicecon telephony integration enables:
- **Phone Number Management**: Search, provision, and manage Twilio phone numbers
- **Inbound Calls**: Handle incoming calls via webhooks and connect to WebSocket streams
- **Outbound Calls**: Initiate calls programmatically
- **Call Status Tracking**: Real-time call status updates and cost tracking
- **WebSocket Streaming**: Bridge phone calls to WebSocket for real-time AI processing

## Architecture

```
┌─────────────────┐
│  Twilio Cloud   │
│   Phone Network │
└────────┬────────┘
         │
         │ (Webhooks)
         ▼
┌─────────────────────────────────────────┐
│          Voicecon Backend               │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   Telephony Webhooks              │ │
│  │   /api/v1/telephony/              │ │
│  └──────────┬────────────────────────┘ │
│             │                           │
│  ┌──────────▼──────────┐               │
│  │  TwilioService      │               │
│  │  - Provision        │               │
│  │  - TwiML Generation │               │
│  │  - Validation       │               │
│  └──────────┬──────────┘               │
│             │                           │
│  ┌──────────▼──────────┐               │
│  │  Voice CallManager  │               │
│  │  STT → LLM → TTS    │               │
│  └─────────────────────┘               │
│                                         │
└─────────────────────────────────────────┘
         │
         │ (WebSocket)
         ▼
┌─────────────────┐
│   AI Pipeline   │
│  - Deepgram STT │
│  - OpenAI/Claude│
│  - ElevenLabs   │
└─────────────────┘
```

## Components

### 1. TwilioService (`twilio_service.py`)

Core service for interacting with Twilio API.

**Features:**
- Phone number search by country/area code
- Number provisioning with automatic webhook configuration
- TwiML generation for WebSocket streaming
- Webhook signature validation (HMAC)
- Call initiation and status retrieval
- Call recording management
- Number release/deletion

**Key Methods:**

```python
# Search available numbers
numbers = await twilio_service.search_phone_numbers(
    country_code="US",
    area_code="415",
    limit=10
)

# Provision a number
phone_number = await twilio_service.provision_phone_number(
    phone_number="+14155551234",
    agent_id="agent-uuid",
    db=db_session,
    webhook_base_url="https://api.voicecon.com"
)

# Generate TwiML for WebSocket
twiml = twilio_service.generate_twiml_for_websocket(
    websocket_url="wss://api.voicecon.com/voice/stream/call-123",
    agent_name="Customer Support"
)

# Make outbound call
call = await twilio_service.make_outbound_call(
    to_number="+14155559999",
    from_number="+14155551234",
    agent_id="agent-uuid",
    webhook_base_url="https://api.voicecon.com"
)
```

### 2. Telephony Webhooks (`telephony.py`)

FastAPI endpoints for handling Twilio webhooks.

**Endpoints:**

#### `POST /api/v1/telephony/twilio/voice/{agent_id}`
Handles inbound calls from Twilio.

**Flow:**
1. Receive call webhook with CallSid, From, To, CallStatus
2. Validate Twilio signature
3. Fetch agent from database
4. Create Call record
5. Generate TwiML with WebSocket URL
6. Return TwiML response to Twilio

**Example TwiML Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello, connecting you with Customer Support</Say>
    <Connect>
        <Stream url="wss://api.voicecon.com/api/v1/voice/stream/call-123"/>
    </Connect>
</Response>
```

#### `POST /api/v1/telephony/twilio/status`
Handles call status callbacks.

**Status Events:**
- `initiated`: Call has been initiated
- `ringing`: Phone is ringing
- `in-progress`: Call has been answered
- `completed`: Call has ended

**Updates:**
- Call status in database
- Call timing (started_at, answered_at, ended_at)
- Call duration and billable duration
- Telephony costs (Twilio pricing: $0.0085/min inbound, $0.0140/min outbound)

#### `POST /api/v1/telephony/twilio/voice-outbound`
Initiates an outbound call.

**Request:**
```json
{
  "to_number": "+14155559999",
  "agent_id": "agent-uuid",
  "from_number": "+14155551234"  // optional
}
```

**Response:**
```json
{
  "call_id": "uuid",
  "call_sid": "CAxxxx",
  "status": "queued",
  "from": "+14155551234",
  "to": "+14155559999"
}
```

### 3. Phone Number Management (`phone_numbers.py`)

REST API for phone number management.

**Endpoints:**

#### `GET /api/v1/phone-numbers/search`
Search available phone numbers.

**Query Parameters:**
- `country_code`: Country code (US, GB, CA, etc.)
- `area_code`: Optional area code filter
- `contains`: Optional pattern to match
- `limit`: Max results (1-50)

**Response:**
```json
[
  {
    "phone_number": "+14155551234",
    "friendly_name": "(415) 555-1234",
    "locality": "San Francisco",
    "region": "CA",
    "capabilities": {
      "voice": true,
      "SMS": true,
      "MMS": false
    }
  }
]
```

#### `POST /api/v1/phone-numbers/provision`
Purchase and provision a phone number.

**Request:**
```json
{
  "phone_number": "+14155551234",
  "agent_id": "agent-uuid"
}
```

**Response:**
```json
{
  "id": "uuid",
  "phone_number": "+14155551234",
  "provider": "twilio",
  "provider_sid": "PNxxxx",
  "agent_id": "agent-uuid",
  "capabilities": {"voice": true, "sms": true},
  "status": "active",
  "monthly_cost": 1.00,
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### `GET /api/v1/phone-numbers/`
List user's phone numbers.

**Query Parameters:**
- `agent_id`: Filter by agent
- `status`: Filter by status (active, inactive)

#### `PATCH /api/v1/phone-numbers/{id}`
Update phone number configuration.

**Request:**
```json
{
  "agent_id": "new-agent-uuid",  // optional
  "status": "inactive"           // optional
}
```

#### `DELETE /api/v1/phone-numbers/{id}`
Release a phone number.

### 4. Database Models

#### PhoneNumber Model
```python
class PhoneNumber(Base):
    id: UUID
    user_id: UUID
    organization_id: UUID
    agent_id: Optional[UUID]

    phone_number: str  # E.164 format
    country_code: Optional[str]
    area_code: Optional[str]

    provider: str  # "twilio"
    provider_sid: str  # Twilio number SID

    capabilities: dict  # {"voice": True, "sms": True}
    status: str  # "active", "inactive"
    monthly_cost: Optional[Decimal]

    created_at: datetime
    updated_at: datetime
```

#### Call Model
```python
class Call(Base):
    id: UUID
    user_id: UUID
    organization_id: UUID
    agent_id: Optional[UUID]
    phone_number_id: Optional[UUID]

    direction: str  # "inbound", "outbound"
    from_number: str
    to_number: str
    status: str  # "initiated", "ringing", "in-progress", "completed"

    started_at: Optional[datetime]
    answered_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]

    # Costs per service
    cost_stt: Optional[Decimal]
    cost_llm: Optional[Decimal]
    cost_tts: Optional[Decimal]
    cost_telephony: Optional[Decimal]
    cost_total: Optional[Decimal]

    provider: str  # "twilio"
    provider_call_sid: str  # Twilio call SID

    transcript: Optional[str]
    recording_url: Optional[str]

    metadata: dict
    created_at: datetime
```

## Configuration

### Environment Variables

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+14155551234  # Default number (optional)

# API Configuration
API_BASE_URL=https://api.voicecon.com
WEBSOCKET_URL=wss://api.voicecon.com
SERVER_HOST=api.voicecon.com
```

### Twilio Dashboard Setup

1. **Create Account**: Sign up at https://www.twilio.com
2. **Get Credentials**: Copy Account SID and Auth Token from console
3. **Configure Webhooks** (automatic via API):
   - Voice URL: `https://api.voicecon.com/api/v1/telephony/twilio/voice/{agent_id}`
   - Status Callback: `https://api.voicecon.com/api/v1/telephony/twilio/status`
4. **Enable WebSocket Streaming**: Already configured in TwiML generation

## Usage Examples

### Example 1: Provision Phone Number

```python
from app.services.telephony.twilio_service import get_twilio_service

# Search for available numbers
twilio = get_twilio_service()
numbers = await twilio.search_phone_numbers(
    country_code="US",
    area_code="415",
    limit=10
)

# Provision the first available number
phone_number = await twilio.provision_phone_number(
    phone_number=numbers[0]["phone_number"],
    agent_id=str(agent.id),
    db=db_session,
    webhook_base_url="https://api.voicecon.com"
)

print(f"Provisioned: {phone_number.phone_number}")
```

### Example 2: Handle Inbound Call

```python
# Twilio sends webhook to:
# POST /api/v1/telephony/twilio/voice/{agent_id}

# Automatic flow:
# 1. Webhook received
# 2. Call record created
# 3. TwiML generated with WebSocket URL
# 4. Twilio connects call to WebSocket
# 5. Voice pipeline handles audio (STT → LLM → TTS)
```

### Example 3: Make Outbound Call

```python
# Via API:
POST /api/v1/telephony/twilio/voice-outbound
{
  "to_number": "+14155559999",
  "agent_id": "agent-uuid"
}

# Via Python:
from app.services.telephony.twilio_service import get_twilio_service

twilio = get_twilio_service()
call = await twilio.make_outbound_call(
    to_number="+14155559999",
    from_number="+14155551234",
    agent_id=str(agent.id),
    webhook_base_url="https://api.voicecon.com"
)

print(f"Call initiated: {call['call_sid']}")
```

### Example 4: Track Call Costs

```python
# Costs are automatically tracked during call
from sqlalchemy import select
from app.models.call import Call

result = await db.execute(
    select(Call).where(Call.provider_call_sid == "CAxxxx")
)
call = result.scalar_one()

print(f"STT Cost: ${call.cost_stt}")
print(f"LLM Cost: ${call.cost_llm}")
print(f"TTS Cost: ${call.cost_tts}")
print(f"Telephony Cost: ${call.cost_telephony}")
print(f"Total Cost: ${call.cost_total}")
```

## Call Flow

### Inbound Call Flow

```
1. User dials Twilio number: +14155551234
2. Twilio → POST /api/v1/telephony/twilio/voice/{agent_id}
3. Backend creates Call record
4. Backend returns TwiML with WebSocket URL
5. Twilio connects call to WebSocket: wss://api.voicecon.com/api/v1/voice/stream/{call_id}
6. Voice pipeline processes audio:
   - User speaks → Deepgram STT → Text
   - Text → OpenAI/Claude LLM → Response
   - Response → ElevenLabs TTS → Audio
   - Audio → WebSocket → Twilio → User
7. Call status updates sent to: POST /api/v1/telephony/twilio/status
8. Call ends, costs calculated and stored
```

### Outbound Call Flow

```
1. API call: POST /api/v1/telephony/twilio/voice-outbound
2. Backend creates Call record
3. Backend calls Twilio API to initiate call
4. Twilio connects to number
5. On answer, Twilio → POST /api/v1/telephony/twilio/voice/{agent_id}
6. Same as inbound flow from step 4
```

## Cost Tracking

### Twilio Pricing (as of 2025)

**Phone Numbers:**
- US Local: $1.00/month
- US Toll-Free: $2.00/month

**Voice Calls:**
- Inbound: $0.0085/minute
- Outbound: $0.0140/minute

**Automatic Cost Calculation:**

The system automatically calculates telephony costs when a call completes:

```python
# In telephony.py status callback handler
if call.duration_seconds:
    minutes = call.duration_seconds / 60
    if call.direction == "inbound":
        cost = minutes * 0.0085
    else:
        cost = minutes * 0.0140

    call.cost_telephony = round(cost, 4)
    call.cost_total = (
        (call.cost_stt or 0) +
        (call.cost_llm or 0) +
        (call.cost_tts or 0) +
        (call.cost_telephony or 0)
    )
```

### Complete Cost Breakdown

For a 5-minute inbound call:
- Telephony (Twilio): 5 × $0.0085 = $0.0425
- STT (Deepgram): ~$0.0300
- LLM (GPT-4): ~$0.0500
- TTS (ElevenLabs): ~$0.0400
- **Total: ~$0.1625 per call**

## Security

### Webhook Signature Validation

All Twilio webhooks include an `X-Twilio-Signature` header for verification:

```python
def validate_twilio_request(request: Request, url: str) -> bool:
    """Validate Twilio webhook signature using HMAC."""
    twilio_service = get_twilio_service()
    signature = request.headers.get("X-Twilio-Signature", "")

    # Get POST parameters
    post_vars = dict(await request.form())

    # Validate using Twilio's RequestValidator
    return twilio_service.validate_request(url, post_vars, signature)
```

**Note:** Current implementation has simplified validation for development. In production, implement full signature validation on all webhook endpoints.

### Best Practices

1. **Always validate signatures** in production
2. **Use HTTPS** for all webhook URLs
3. **Store credentials** in environment variables, never in code
4. **Rate limit** webhook endpoints to prevent abuse
5. **Log all webhook calls** for debugging
6. **Monitor costs** to detect anomalies

## Error Handling

### Webhook Failures

If a webhook handler fails:
- Return TwiML error message to caller
- Log error with full context
- Don't return 5xx status to avoid Twilio retries

```python
try:
    # Handle webhook
    pass
except Exception as e:
    logger.error(f"Webhook error: {e}")
    twiml = twilio_service.generate_twiml_error(
        "We're sorry, an error occurred."
    )
    return Response(content=twiml, media_type="application/xml")
```

### Call Failures

If outbound call initiation fails:
- Update call status to "failed"
- Store error details in metadata
- Return appropriate HTTP error to client

```python
try:
    call = await twilio.make_outbound_call(...)
except TwilioRestException as e:
    call.status = "failed"
    call.metadata["error"] = str(e)
    await db.commit()
    raise HTTPException(status_code=500, detail=str(e))
```

## Testing

### Manual Testing with Twilio Test Credentials

```bash
# Use Twilio test credentials
export TWILIO_ACCOUNT_SID=ACxxxx (test)
export TWILIO_AUTH_TOKEN=xxxx (test)

# Test webhook with curl
curl -X POST https://api.voicecon.com/api/v1/telephony/twilio/voice/{agent_id} \
  -d "CallSid=CAtest123" \
  -d "From=+15555551234" \
  -d "To=+15555554321" \
  -d "CallStatus=ringing"
```

### Production Deployment Checklist

- [ ] Set production Twilio credentials
- [ ] Configure public webhook URLs with HTTPS
- [ ] Enable webhook signature validation
- [ ] Set up monitoring and alerting
- [ ] Configure rate limiting
- [ ] Test phone number provisioning
- [ ] Test inbound call flow
- [ ] Test outbound call flow
- [ ] Verify cost tracking
- [ ] Test error handling

## Next Steps

1. **Implement signature validation** for production security
2. **Add SMS/MMS support** using Twilio messaging APIs
3. **Add call recording** storage to S3
4. **Implement call transfer** between agents
5. **Add conference calling** support
6. **Create admin dashboard** for call monitoring
7. **Add real-time analytics** with WebSocket updates

## Troubleshooting

### Webhooks Not Receiving Calls

1. Check webhook URL is publicly accessible
2. Verify URL is HTTPS in production
3. Check Twilio phone number configuration
4. Review Twilio debugger logs

### WebSocket Connection Fails

1. Verify WebSocket URL is accessible
2. Check CORS configuration
3. Review WebSocket endpoint implementation
4. Test with wscat: `wscat -c wss://api.voicecon.com/api/v1/voice/stream/{call_id}`

### Calls Not Connecting

1. Verify Twilio credentials are correct
2. Check account balance in Twilio dashboard
3. Review TwiML response format
4. Check agent is active and configured

### Cost Tracking Issues

1. Verify status callbacks are configured
2. Check database call records
3. Review status callback handler logs
4. Ensure duration is being calculated correctly

## Summary

The Twilio telephony integration is now fully implemented with:

✅ **Phone Number Management** - Search, provision, update, release
✅ **Inbound Call Handling** - Webhooks, TwiML generation, WebSocket bridging
✅ **Outbound Call Initiation** - API endpoints, Twilio integration
✅ **Call Status Tracking** - Real-time updates, duration, costs
✅ **Security** - Signature validation (framework ready)
✅ **Error Handling** - Graceful failures, proper logging
✅ **Cost Tracking** - Automatic calculation per service
✅ **Database Models** - Complete schema for calls and numbers
✅ **API Documentation** - Full REST API with examples

The system is production-ready pending webhook signature validation implementation and deployment configuration.
