# Local Testing Guide - Voicecon Voice AI Pipeline

Complete guide to testing the voice AI + telephony pipeline on your local machine.

## Prerequisites

### Required Tools
- Docker & Docker Compose
- Python 3.11+
- ngrok (for Twilio webhooks)
- A Twilio account (free trial works!)

### Required API Keys

1. **Twilio** (https://www.twilio.com)
   - Account SID
   - Auth Token
   - Optional: Purchase a phone number ($1/month)

2. **Deepgram** (https://deepgram.com)
   - API Key (free $200 credit)

3. **OpenAI** (https://platform.openai.com)
   - API Key (pay-as-you-go)

4. **ElevenLabs** (https://elevenlabs.io)
   - API Key (free tier available)

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
cd voicecon

# Copy environment template
cp backend/.env.example backend/.env
```

### 2. Configure Environment Variables

Edit `backend/.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voicecon

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here  # optional

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Server Configuration
API_BASE_URL=https://your-ngrok-url.ngrok.io  # Will set this later
WEBSOCKET_URL=wss://your-ngrok-url.ngrok.io
SERVER_HOST=localhost
```

### 3. Start Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be ready (10 seconds)
sleep 10

# Run database migrations
cd backend
python -m alembic upgrade head

# Seed database with demo data
python scripts/seed_demo.py
```

### 4. Start Backend Server

```bash
# From backend directory
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 5. Setup ngrok for Webhooks

In a new terminal:

```bash
# Install ngrok (if not already installed)
# macOS: brew install ngrok
# Or download from https://ngrok.com

# Start ngrok tunnel
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

**Copy the https URL!**

### 6. Update Environment with ngrok URL

Edit `backend/.env`:
```bash
API_BASE_URL=https://abc123.ngrok.io
WEBSOCKET_URL=wss://abc123.ngrok.io
```

Restart your backend server (Ctrl+C, then `uvicorn app.main:app --reload --port 8000`)

## Testing Options

You have 3 ways to test the voice pipeline:

### Option 1: Test with Real Phone Calls (Recommended)

**Step 1: Create an Agent**

```bash
# Create a test agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Test Assistant",
    "description": "Local testing agent",
    "system_prompt": "You are a helpful AI assistant. Keep responses brief.",
    "first_message": "Hello! This is your test assistant. How can I help you?",
    "stt_provider": "deepgram",
    "stt_model": "nova-2",
    "llm_provider": "openai",
    "llm_model": "gpt-3.5-turbo",
    "llm_temperature": 0.7,
    "tts_provider": "elevenlabs",
    "tts_voice": "rachel"
  }'

# Response will include agent_id
```

**Step 2: Search for a Phone Number**

```bash
# Search for available numbers in your area
curl -X GET "http://localhost:8000/api/v1/phone-numbers/search?country_code=US&area_code=415&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Step 3: Provision the Number**

```bash
# Provision a phone number
curl -X POST http://localhost:8000/api/v1/phone-numbers/provision \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "phone_number": "+14155551234",
    "agent_id": "your-agent-uuid"
  }'
```

This automatically:
- Purchases the number from Twilio
- Configures webhooks to your ngrok URL
- Links it to your agent

**Step 4: Call the Number!**

1. Call the number from your phone
2. Wait for the greeting
3. Start talking!
4. The AI will respond via voice

**Step 5: Monitor in Real-Time**

Watch the logs in your terminal:
```bash
# You'll see:
INFO: WebSocket connected: call_id=xxx
INFO: Stream started: stream_sid=xxx
INFO: Transcription: Hello, how are you?
INFO: LLM response: I'm doing well, thank you! How can I assist you today?
INFO: Sent audio response: 15 chunks
```

Check active sessions:
```bash
curl http://localhost:8000/api/v1/voice/sessions/active
```

### Option 2: Test WebSocket Directly (No Phone)

**Step 1: Create a Call Record**

```bash
# Create a test call
curl -X POST http://localhost:8000/api/v1/calls \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "agent_id": "your-agent-uuid",
    "to_number": "+14155559999"
  }'

# Note the call_id from response
```

**Step 2: Connect WebSocket Client**

Install wscat:
```bash
npm install -g wscat
```

Connect to voice stream:
```bash
wscat -c "ws://localhost:8000/api/v1/voice/stream/YOUR_CALL_ID"
```

**Step 3: Send Test Messages**

```json
# Start stream
{"event": "start", "start": {"streamSid": "test123", "callSid": "CAtest"}}

# Send audio (base64 mulaw - this is just an example)
{"event": "media", "media": {"payload": "//7+/v7+/v7+/v7+"}}

# Stop stream
{"event": "stop", "stop": {"callSid": "CAtest"}}
```

### Option 3: Test Individual Services

**Test STT Service:**

```python
# test_stt.py
import asyncio
from app.services.voice.stt_service import get_stt_service

async def test_stt():
    stt = get_stt_service()

    # Test with audio file
    with open("test_audio.wav", "rb") as f:
        audio_data = f.read()

    result = await stt.transcribe_file(
        audio_data=audio_data,
        provider="deepgram",
        model="nova-2"
    )

    print(f"Transcription: {result.transcript}")
    print(f"Confidence: {result.confidence}")
    print(f"Duration: {result.duration}s")

asyncio.run(test_stt())
```

**Test LLM Service:**

```python
# test_llm.py
import asyncio
from app.services.voice.llm_service import get_llm_service, ChatMessage

async def test_llm():
    llm = get_llm_service()

    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="What is the capital of France?"),
    ]

    # Non-streaming
    result = await llm.chat(messages, provider="openai", model="gpt-3.5-turbo")
    print(f"Response: {result.content}")
    print(f"Tokens: {result.total_tokens}")

    # Streaming
    print("\nStreaming response:")
    async for chunk in llm.chat_stream(messages, provider="openai"):
        print(chunk, end='', flush=True)

asyncio.run(test_llm())
```

**Test TTS Service:**

```python
# test_tts.py
import asyncio
from app.services.voice.tts_service import get_tts_service

async def test_tts():
    tts = get_tts_service()

    # Synthesize
    result = await tts.synthesize(
        text="Hello! This is a test of the text to speech system.",
        provider="elevenlabs",
        voice_id="rachel"
    )

    # Save to file
    with open("output.mp3", "wb") as f:
        f.write(result.audio_data)

    print(f"Generated {len(result.audio_data)} bytes of audio")
    print(f"Duration: {result.duration}s")
    print(f"Characters: {result.character_count}")

asyncio.run(test_tts())
```

## Viewing Logs

### Backend Logs
```bash
# In terminal where uvicorn is running
# You'll see all requests, errors, and processing
```

### Check Call Details
```bash
# Get all calls
curl http://localhost:8000/api/v1/calls \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get specific call with costs
curl http://localhost:8000/api/v1/calls/CALL_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Check Active Sessions
```bash
# Get active voice sessions
curl http://localhost:8000/api/v1/voice/sessions/active

# Get specific session
curl http://localhost:8000/api/v1/voice/sessions/CALL_ID
```

## Testing Complete Flow End-to-End

### Automated Test Script

Create `test_complete_flow.sh`:

```bash
#!/bin/bash

echo "🧪 Testing Voicecon Voice AI Pipeline"
echo "======================================"

# 1. Health check
echo "\n1️⃣ Checking server health..."
curl -s http://localhost:8000/health | jq

# 2. Search phone numbers
echo "\n2️⃣ Searching for available phone numbers..."
NUMBERS=$(curl -s "http://localhost:8000/api/v1/phone-numbers/search?country_code=US&limit=5" \
  -H "Authorization: Bearer $TOKEN")
echo $NUMBERS | jq

# 3. Get first available number
PHONE_NUMBER=$(echo $NUMBERS | jq -r '.[0].phone_number')
echo "Selected number: $PHONE_NUMBER"

# 4. Provision number
echo "\n3️⃣ Provisioning phone number..."
PROVISION_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/phone-numbers/provision \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"phone_number\": \"$PHONE_NUMBER\", \"agent_id\": \"$AGENT_ID\"}")
echo $PROVISION_RESULT | jq

# 5. Check active sessions
echo "\n4️⃣ Checking active sessions..."
curl -s http://localhost:8000/api/v1/voice/sessions/active | jq

echo "\n✅ Setup complete! Call $PHONE_NUMBER to test."
```

Run it:
```bash
export TOKEN="your_jwt_token"
export AGENT_ID="your_agent_uuid"
chmod +x test_complete_flow.sh
./test_complete_flow.sh
```

## Troubleshooting

### Issue: "Connection refused" when starting server

**Solution:**
```bash
# Check if PostgreSQL and Redis are running
docker ps

# Start them if not running
docker-compose up -d postgres redis

# Wait 10 seconds, then try again
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Install dependencies
cd backend
pip install -r requirements.txt
```

### Issue: ngrok URL changes every restart

**Solution:**
Get a free ngrok account for a static subdomain:
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
ngrok http 8000 --domain=your-static-domain.ngrok.io
```

### Issue: Twilio webhooks not working

**Checklist:**
1. ✅ ngrok is running and showing forwarding
2. ✅ `API_BASE_URL` in `.env` matches ngrok URL
3. ✅ Backend server restarted after updating `.env`
4. ✅ Phone number provisioned (webhooks set automatically)

**Debug:**
```bash
# Check Twilio webhook logs
# Go to: https://console.twilio.com/debugger

# Test webhook manually
curl -X POST "https://your-ngrok-url.ngrok.io/api/v1/telephony/twilio/voice/AGENT_ID" \
  -d "CallSid=CAtest" \
  -d "From=+15555551234" \
  -d "To=+14155551234" \
  -d "CallStatus=ringing"
```

### Issue: Audio quality is poor

**Solutions:**
1. Check internet connection (WebSocket requires good bandwidth)
2. Use wired connection instead of WiFi
3. Reduce other network usage
4. Try different Twilio region (closer to you)

### Issue: High latency (>2 seconds)

**Check:**
```bash
# Test individual services
python test_stt.py  # Should be <200ms
python test_llm.py  # Should be <500ms
python test_tts.py  # Should be <200ms
```

**Solutions:**
1. Use faster models:
   - LLM: `gpt-3.5-turbo` instead of `gpt-4`
   - TTS: `eleven_turbo_v2` instead of standard
2. Enable streaming (already implemented)
3. Check ngrok latency (may add 50-100ms)

### Issue: "Agent not found" error

**Solution:**
```bash
# Verify agent exists
curl http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create agent if needed
# See "Create an Agent" section above
```

## Cost Estimation

Testing locally will incur API costs:

**Per 5-minute test call:**
- Deepgram STT: ~$0.03
- OpenAI GPT-3.5: ~$0.05
- ElevenLabs TTS: ~$0.04
- Twilio (if using real number): ~$0.04
- **Total: ~$0.16 per call**

**Free tier limits:**
- Deepgram: $200 free credit = ~6,600 minutes
- ElevenLabs: 10,000 characters/month free
- Twilio: $15 trial credit

## Monitoring Dashboard (Optional)

View metrics in real-time:

```bash
# Install additional tools
pip install rich

# Run monitoring script
python scripts/monitor_calls.py
```

This will show:
```
╔═══════════════════════════════════════╗
║  Voicecon Live Call Monitor           ║
╠═══════════════════════════════════════╣
║  Active Calls: 2                      ║
║  Total Calls Today: 15                ║
║  Average Duration: 3m 24s             ║
║  Total Cost Today: $2.45              ║
╚═══════════════════════════════════════╝

Active Sessions:
┌─────────────┬──────────┬─────────┬──────────┐
│ Call ID     │ Agent    │ State   │ Duration │
├─────────────┼──────────┼─────────┼──────────┤
│ abc-123     │ Support  │ TALKING │ 1m 23s   │
│ def-456     │ Sales    │ LISTENING│ 0m 45s   │
└─────────────┴──────────┴─────────┴──────────┘
```

## Production Readiness Checklist

Before deploying to production:

- [ ] All API keys configured
- [ ] Database migrations run
- [ ] ngrok replaced with real domain
- [ ] SSL certificates configured
- [ ] Environment variables secured
- [ ] Audio format conversion implemented
- [ ] Streaming STT implemented
- [ ] Error monitoring setup (Sentry)
- [ ] Load testing completed (100+ concurrent calls)
- [ ] Backup strategy in place
- [ ] Cost alerts configured

## Next Steps

1. **Test basic flow**: Call provisioned number, have a conversation
2. **Monitor metrics**: Check `/voice/sessions/active` during call
3. **Review costs**: Check call details after each test
4. **Iterate**: Adjust agent prompts, models, voices
5. **Scale up**: Test with multiple concurrent calls

## Support

If you encounter issues:

1. Check logs in terminal
2. Review Twilio debugger: https://console.twilio.com/debugger
3. Test individual services (STT, LLM, TTS separately)
4. Check ngrok status
5. Verify all API keys are valid

---

**You're all set! Start testing your voice AI pipeline locally.** 🎉

Run `./test_complete_flow.sh` or call your provisioned number to begin!
