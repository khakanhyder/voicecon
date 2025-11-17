# 🚀 Voicecon Backend - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/voicecon
SECRET_KEY=your-secret-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
DEEPGRAM_API_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
ELEVENLABS_API_KEY=your-elevenlabs-key
```

### 3. Run Database Migrations
```bash
alembic upgrade head
```

### 4. Start Server
```bash
uvicorn app.main:app --reload
```

Server runs at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

---

## Common Operations

### Register & Login
```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword",
    "full_name": "John Doe"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "securepassword"
  }'

# Save the access_token from response
export TOKEN="your-access-token-here"
```

### Create Agent from Template
```bash
curl -X POST "http://localhost:8000/api/v1/agents/templates/customer-support/create?custom_name=My Support Agent" \
  -H "Authorization: Bearer $TOKEN"
```

### Test Agent
```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_message": "Hello, I need help with my account",
    "test_mode": "text"
  }'
```

### Make Phone Call
```bash
# First, purchase a phone number
curl -X POST http://localhost:8000/api/v1/phone-numbers/purchase \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+14155551234",
    "friendly_name": "Main Line"
  }'

# Make outbound call
curl -X POST http://localhost:8000/api/v1/telephony/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "to_number": "+14155559999",
    "agent_id": "your-agent-id"
  }'
```

### View Analytics
```bash
# Dashboard summary
curl -X GET http://localhost:8000/api/v1/analytics/dashboard \
  -H "Authorization: Bearer $TOKEN"

# Call metrics
curl -X GET "http://localhost:8000/api/v1/analytics/metrics?start_date=2025-01-01" \
  -H "Authorization: Bearer $TOKEN"

# Cost metrics
curl -X GET http://localhost:8000/api/v1/analytics/costs \
  -H "Authorization: Bearer $TOKEN"
```

---

## Testing Locally with Real Calls

### Setup ngrok
```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# Expose local server
ngrok http 8000

# Note the HTTPS URL (e.g., https://abc123.ngrok.io)
```

### Configure Twilio
1. Go to Twilio Console → Phone Numbers
2. Select your phone number
3. Set "A CALL COMES IN" webhook to:
   ```
   https://your-ngrok-url.ngrok.io/api/v1/telephony/webhook
   ```
4. Set HTTP method to `POST`

### Make Test Call
```bash
# Option 1: Call your Twilio number from your phone
# Your agent will answer!

# Option 2: Make outbound call via API
curl -X POST http://localhost:8000/api/v1/telephony/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "to_number": "+1YOUR_PHONE_NUMBER",
    "agent_id": "your-agent-id"
  }'
```

---

## Available Templates

### 1. Customer Support
```bash
POST /api/v1/agents/templates/customer-support/create
```
- Handles customer inquiries and complaints
- Professional, empathetic tone
- GPT-4 + Rachel (ElevenLabs)

### 2. Sales Assistant
```bash
POST /api/v1/agents/templates/sales-assistant/create
```
- Lead qualification
- BANT framework
- GPT-4 + Adam (ElevenLabs)

### 3. Appointment Scheduler
```bash
POST /api/v1/agents/templates/appointment-scheduler/create
```
- Books appointments
- Calendar integration ready
- GPT-4 + Bella (ElevenLabs)

### 4. Technical Support
```bash
POST /api/v1/agents/templates/technical-support/create
```
- IT troubleshooting
- Step-by-step guidance
- GPT-4 + Josh (ElevenLabs)

### 5. Survey Interviewer
```bash
POST /api/v1/agents/templates/survey-interviewer/create
```
- Conducts surveys
- Collects feedback
- GPT-3.5 + Elli (ElevenLabs)

---

## API Endpoint Reference

### Authentication
- `POST /api/v1/auth/register` - Register user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get current user

### Agents
- `POST /api/v1/agents` - Create agent
- `GET /api/v1/agents` - List agents
- `GET /api/v1/agents/{id}` - Get agent
- `PATCH /api/v1/agents/{id}` - Update agent
- `DELETE /api/v1/agents/{id}` - Delete agent
- `POST /api/v1/agents/{id}/clone` - Clone agent
- `POST /api/v1/agents/{id}/test` - Test agent
- `GET /api/v1/agents/templates/list` - List templates
- `POST /api/v1/agents/templates/{id}/create` - Create from template

### Telephony
- `POST /api/v1/telephony/call` - Make call
- `POST /api/v1/telephony/webhook` - Twilio webhook
- `POST /api/v1/telephony/transfer` - Transfer call
- `POST /api/v1/telephony/hangup` - Hang up call

### Phone Numbers
- `GET /api/v1/phone-numbers` - List owned numbers
- `GET /api/v1/phone-numbers/available` - Search available
- `POST /api/v1/phone-numbers/purchase` - Purchase number
- `DELETE /api/v1/phone-numbers/{id}` - Release number

### Calls
- `GET /api/v1/calls` - List calls
- `GET /api/v1/calls/{id}` - Get call details
- `GET /api/v1/calls/{id}/transcript` - Get transcript
- `GET /api/v1/calls/{id}/recording` - Get recording

### Analytics
- `GET /api/v1/analytics/metrics` - Call metrics
- `GET /api/v1/analytics/costs` - Cost metrics
- `GET /api/v1/analytics/dashboard` - Dashboard summary
- `GET /api/v1/analytics/agents/{id}/metrics` - Agent metrics
- `GET /api/v1/analytics/transcripts/search` - Search transcripts
- `GET /api/v1/analytics/export` - Export data

### WebSocket
- `WS /api/v1/voice/stream/{call_id}` - Voice streaming

---

## Configuration Options

### Agent Configuration

**LLM Settings:**
```json
{
  "llm": {
    "provider": "openai",      // openai, anthropic
    "model": "gpt-4",          // gpt-4, gpt-3.5-turbo, claude-3-opus, etc.
    "temperature": 0.7,        // 0-2 (lower = consistent, higher = creative)
    "max_tokens": 1000         // 1-4000
  }
}
```

**Voice Settings:**
```json
{
  "voice": {
    "provider": "elevenlabs",  // elevenlabs, google, azure
    "voice_id": "rachel",      // rachel, adam, josh, bella, etc.
    "speed": 1.0,              // 0.5-2.0
    "pitch": 1.0               // 0.5-2.0
  }
}
```

**STT Settings:**
```json
{
  "stt": {
    "provider": "deepgram",    // deepgram, google, azure, whisper
    "language": "en",          // en, es, fr, etc.
    "model": "nova-2"          // nova-2, base
  }
}
```

**Conversation Settings:**
```json
{
  "settings": {
    "interrupt_enabled": true,
    "interrupt_sensitivity": 0.5,       // 0-1
    "silence_timeout": 3000,            // ms
    "max_call_duration": 1800,          // seconds
    "end_call_phrases": ["goodbye", "end call"]
  }
}
```

---

## Cost Breakdown

### Per Call (5 minutes)
- **STT (Deepgram):** $0.024
- **LLM (GPT-4):** $0.025
- **TTS (ElevenLabs):** $0.048
- **Telephony (Twilio):** $0.070
- **Total:** ~$0.167

### Cost Optimization Tips
1. Use GPT-3.5 for simple tasks ($0.002 vs $0.025)
2. Use Google TTS for basic voices ($0.016 vs $0.048)
3. Shorter conversations = lower costs
4. Cache common responses

---

## Troubleshooting

### Issue: "Database connection failed"
```bash
# Check PostgreSQL is running
psql -U postgres

# Verify DATABASE_URL in .env
echo $DATABASE_URL
```

### Issue: "Twilio webhook not working"
```bash
# Check ngrok is running
curl https://your-ngrok-url.ngrok.io/health

# Verify webhook URL in Twilio console
# Make sure it's HTTPS (not HTTP)
```

### Issue: "API key invalid"
```bash
# Verify environment variables
echo $OPENAI_API_KEY
echo $DEEPGRAM_API_KEY
echo $ELEVENLABS_API_KEY

# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Issue: "WebSocket connection failed"
```bash
# Check server logs for errors
tail -f logs/app.log

# Test WebSocket connection
wscat -c ws://localhost:8000/api/v1/voice/stream/test-call-id
```

---

## Next Steps

1. **Test the API** - Use Swagger UI at http://localhost:8000/docs
2. **Create an agent** - Use templates or custom configuration
3. **Make a test call** - Try outbound or inbound calls
4. **View analytics** - Check dashboard for metrics
5. **Build frontend** - Connect React/Next.js app to API

---

## Documentation

- **[BACKEND_COMPLETE.md](BACKEND_COMPLETE.md)** - Complete feature overview
- **[AGENT_MANAGEMENT.md](AGENT_MANAGEMENT.md)** - Agent system guide
- **[CALL_MANAGEMENT.md](CALL_MANAGEMENT.md)** - Call & analytics guide
- **[VOICE_STREAMING.md](VOICE_STREAMING.md)** - WebSocket streaming
- **[TELEPHONY_INTEGRATION.md](TELEPHONY_INTEGRATION.md)** - Twilio integration
- **[LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)** - Testing procedures

---

## Support

**API Documentation:** http://localhost:8000/docs
**Interactive Testing:** http://localhost:8000/docs#/

---

**Happy Building! 🚀**
