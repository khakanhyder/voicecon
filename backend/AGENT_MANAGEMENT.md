# Agent Management System

Complete agent configuration, CRUD operations, templates, and testing functionality.

## Overview

The agent management system provides a comprehensive interface for creating, configuring, and managing AI voice agents with full control over LLM, TTS, and STT providers.

## Features

### ✅ Complete Agent CRUD
- Create agents with full configuration
- Update any agent settings
- Soft delete with versioning
- Clone existing agents
- Search and filter agents

### ✅ Multi-Provider Support
**LLM Providers:**
- OpenAI (GPT-4, GPT-3.5 Turbo)
- Anthropic (Claude 3 Opus, Sonnet, Haiku)

**TTS Providers:**
- ElevenLabs (9 pre-configured voices)
- Google Cloud TTS
- Azure Speech

**STT Providers:**
- Deepgram (Nova-2, Base)
- Google Cloud Speech
- Azure Speech
- OpenAI Whisper

### ✅ Agent Templates
5 pre-built templates:
1. **Customer Support** - Handles customer inquiries
2. **Sales Assistant** - Lead qualification and demos
3. **Appointment Scheduler** - Books appointments
4. **Technical Support** - IT troubleshooting
5. **Survey Interviewer** - Conducts surveys

### ✅ Agent Testing
- Test with sample messages
- Text or audio mode
- Real-time latency measurement
- Cost tracking per test
- Full response preview

### ✅ Advanced Features
- Conversation settings (interruption, timeout)
- Sentiment analysis
- Emotion detection
- Knowledge base integration
- Custom functions/tools
- Agent versioning

## API Endpoints

### Agent CRUD

#### Create Agent
```bash
POST /api/v1/agents

{
  "name": "Customer Support Agent",
  "description": "Handles customer support inquiries",
  "system_prompt": "You are a helpful customer support agent...",
  "first_message": "Hello! How can I help you today?",
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "voice": {
    "provider": "elevenlabs",
    "voice_id": "rachel",
    "speed": 1.0,
    "pitch": 1.0
  },
  "stt": {
    "provider": "deepgram",
    "language": "en",
    "model": "nova-2"
  },
  "settings": {
    "interrupt_enabled": true,
    "interrupt_sensitivity": 0.5,
    "silence_timeout": 3000,
    "max_call_duration": 1800,
    "end_call_phrases": ["goodbye", "thank you", "end call"]
  },
  "advanced": {
    "sentiment_analysis_enabled": false,
    "emotion_detection_enabled": false,
    "background_noise_reduction": true,
    "knowledge_base_enabled": false
  },
  "tags": ["support", "customer-service"],
  "is_public": false
}

Response: 201 Created
{
  "id": "agent-uuid",
  "name": "Customer Support Agent",
  "version": 1,
  "created_at": "2025-01-15T10:00:00Z",
  ...
}
```

#### List Agents
```bash
GET /api/v1/agents?skip=0&limit=100&search=support&tags=customer-service

Response:
{
  "agents": [...],
  "total": 15,
  "skip": 0,
  "limit": 100
}
```

#### Get Agent
```bash
GET /api/v1/agents/{agent_id}

Response:
{
  "id": "uuid",
  "name": "Customer Support Agent",
  "llm_provider": "openai",
  "llm_model": "gpt-4",
  "tts_provider": "elevenlabs",
  "tts_voice_id": "rachel",
  "version": 2,
  ...
}
```

#### Update Agent
```bash
PATCH /api/v1/agents/{agent_id}

{
  "system_prompt": "Updated prompt...",
  "llm": {
    "temperature": 0.8
  },
  "settings": {
    "max_call_duration": 2400
  }
}

Response: 200 OK
{
  "id": "uuid",
  "version": 3,  // Auto-incremented
  ...
}
```

#### Delete Agent
```bash
DELETE /api/v1/agents/{agent_id}

Response: 204 No Content
```

### Agent Cloning

```bash
POST /api/v1/agents/{agent_id}/clone

{
  "name": "Customer Support Agent V2",
  "include_functions": true,
  "include_knowledge_base": false
}

Response: 201 Created
{
  "id": "new-agent-uuid",
  "description": "Cloned from: Customer Support Agent",
  ...
}
```

### Agent Testing

```bash
POST /api/v1/agents/{agent_id}/test

{
  "test_message": "Hello, I need help with my account",
  "test_mode": "text"
}

Response:
{
  "success": true,
  "test_id": "test-uuid",
  "agent_response": "Hello! I'd be happy to help you with your account. What specific issue are you experiencing?",
  "latency_ms": 450,
  "costs": {
    "llm": 0.002,
    "tts": 0.001,
    "total": 0.003
  },
  "metadata": {
    "agent_id": "uuid",
    "model": "gpt-4",
    "provider": "openai"
  }
}
```

### Agent Templates

#### List Templates
```bash
GET /api/v1/agents/templates/list

Response:
{
  "templates": [
    {
      "id": "customer-support",
      "name": "Customer Support Agent",
      "description": "Handles customer inquiries, complaints...",
      "category": "Support",
      "template_data": {...},
      "use_count": 0
    },
    ...
  ],
  "total": 5
}
```

#### Create from Template
```bash
POST /api/v1/agents/templates/customer-support/create?custom_name=My Support Agent

Response: 201 Created
{
  "id": "new-agent-uuid",
  "name": "My Support Agent",
  "system_prompt": "You are a professional customer support agent...",
  ...
}
```

### Agent Functions

#### Create Function
```bash
POST /api/v1/agents/{agent_id}/functions

{
  "name": "check_order_status",
  "description": "Check the status of a customer order",
  "parameters": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "description": "The order ID"
      }
    },
    "required": ["order_id"]
  },
  "webhook_url": "https://api.example.com/orders/status",
  "http_method": "POST",
  "timeout": 5000,
  "retry_count": 3
}

Response: 201 Created
{
  "id": "function-uuid",
  "agent_id": "agent-uuid",
  "name": "check_order_status",
  ...
}
```

#### List Functions
```bash
GET /api/v1/agents/{agent_id}/functions

Response:
[
  {
    "id": "uuid",
    "name": "check_order_status",
    "description": "Check the status of a customer order",
    "parameters": {...},
    "webhook_url": "https://api.example.com/orders/status",
    "is_active": true,
    "execution_order": 0
  }
]
```

#### Delete Function
```bash
DELETE /api/v1/agents/{agent_id}/functions/{function_id}

Response: 204 No Content
```

## Agent Configuration

### Complete Configuration Schema

```python
{
    # Basic Info
    "name": str,                    # Required
    "description": str,             # Optional
    "type": "assistant" | "squad",  # Default: "assistant"

    # Core Prompts
    "system_prompt": str,           # System instructions
    "first_message": str,           # Greeting message

    # LLM Configuration
    "llm": {
        "provider": "openai" | "anthropic",
        "model": str,               # e.g., "gpt-4", "claude-3-opus"
        "temperature": 0-2,         # Default: 0.7
        "max_tokens": 1-4000,       # Default: 1000
        "api_key": str              # Optional (encrypted)
    },

    # Voice/TTS Configuration
    "voice": {
        "provider": "elevenlabs" | "google" | "azure",
        "voice_id": str,            # Voice name/ID
        "speed": 0.5-2.0,           # Default: 1.0
        "pitch": 0.5-2.0,           # Default: 1.0
        "api_key": str              # Optional (encrypted)
    },

    # Speech-to-Text Configuration
    "stt": {
        "provider": "deepgram" | "google" | "azure" | "whisper",
        "language": str,            # Default: "en"
        "model": str,               # e.g., "nova-2"
        "api_key": str              # Optional (encrypted)
    },

    # Conversation Settings
    "settings": {
        "interrupt_enabled": bool,              # Default: true
        "interrupt_sensitivity": 0-1,           # Default: 0.5
        "silence_timeout": 500-10000,           # Default: 3000 (ms)
        "max_call_duration": 60-7200,           # Default: 1800 (seconds)
        "end_call_phrases": [str]               # Phrases to end call
    },

    # Advanced Features
    "advanced": {
        "sentiment_analysis_enabled": bool,     # Default: false
        "emotion_detection_enabled": bool,      # Default: false
        "background_noise_reduction": bool,     # Default: true
        "knowledge_base_enabled": bool,         # Default: false
        "knowledge_base_config": dict           # RAG configuration
    },

    # Metadata
    "tags": [str],                  # For organization
    "is_public": bool,              # Default: false
    "is_active": bool               # Default: true
}
```

## Agent Templates

### Customer Support Template
```python
{
    "name": "Customer Support",
    "system_prompt": """You are a professional customer support agent. Your role is to:
    - Listen carefully to customer concerns
    - Provide clear and helpful solutions
    - Remain patient and empathetic
    - Escalate to human support when needed
    - Always maintain a positive, professional tone""",
    "llm": {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.7
    },
    "voice": {
        "provider": "elevenlabs",
        "voice_id": "rachel"  // Friendly, professional
    }
}
```

### Sales Assistant Template
```python
{
    "name": "Sales Assistant",
    "system_prompt": """You are a professional sales assistant. Your goals are to:
    - Understand customer needs and pain points
    - Explain product benefits clearly
    - Qualify leads based on BANT
    - Schedule demos or meetings
    - Handle objections professionally""",
    "llm": {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.8  // More creative
    },
    "voice": {
        "provider": "elevenlabs",
        "voice_id": "adam",  // Enthusiastic, engaging
        "speed": 1.1  // Slightly faster
    }
}
```

## Usage Examples

### Create Agent with Python
```python
import httpx

async def create_agent():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "My Support Agent",
                "system_prompt": "You are a helpful assistant.",
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.7
                },
                "voice": {
                    "provider": "elevenlabs",
                    "voice_id": "rachel"
                }
            }
        )

        agent = response.json()
        print(f"Created agent: {agent['id']}")
        return agent
```

### Test Agent
```python
async def test_agent(agent_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/v1/agents/{agent_id}/test",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "test_message": "Hello, I need help",
                "test_mode": "text"
            }
        )

        result = response.json()
        print(f"Response: {result['agent_response']}")
        print(f"Latency: {result['latency_ms']}ms")
        print(f"Cost: ${result['costs']['total']}")
```

### Clone Agent
```python
async def clone_agent(agent_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/v1/agents/{agent_id}/clone",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Cloned Agent",
                "include_functions": True
            }
        )

        cloned = response.json()
        print(f"Cloned: {cloned['id']}")
```

## Agent Versioning

Every update automatically increments the agent version:

```python
# Create agent
agent = create_agent(...)  # version = 1

# Update agent
agent = update_agent(...)  # version = 2

# Update again
agent = update_agent(...)  # version = 3
```

This allows you to:
- Track configuration changes
- Roll back to previous versions
- Audit agent modifications

## Best Practices

### 1. **System Prompts**
```python
# Good
system_prompt = """You are a customer support agent. Your responsibilities:
- Listen carefully
- Provide clear solutions
- Escalate when needed

Guidelines:
- Be concise
- Ask clarifying questions
- Maintain professional tone"""

# Bad
system_prompt = "Help customers"
```

### 2. **Temperature Settings**
- **0.3-0.5**: Factual, consistent responses (support, technical)
- **0.6-0.8**: Balanced creativity (general conversation)
- **0.9-1.2**: Creative, varied responses (sales, marketing)

### 3. **Voice Selection**
- **Rachel**: Friendly, professional (support)
- **Adam**: Enthusiastic, engaging (sales)
- **Josh**: Calm, reassuring (technical)
- **Bella**: Warm, welcoming (reception)

### 4. **Conversation Settings**
```python
# Short, focused calls (appointments)
settings = {
    "max_call_duration": 900,  # 15 minutes
    "silence_timeout": 2000,   # 2 seconds
    "interrupt_enabled": True
}

# Detailed support calls
settings = {
    "max_call_duration": 2400,  # 40 minutes
    "silence_timeout": 4000,    # 4 seconds
    "interrupt_enabled": True
}
```

## Testing

### Manual Testing
1. Create agent via API
2. Test with sample messages
3. Review response and latency
4. Adjust configuration
5. Test again

### Automated Testing
```python
test_cases = [
    "I need help with my order",
    "What are your business hours?",
    "I want to speak to a manager",
]

for test_message in test_cases:
    result = await test_agent(agent_id, test_message)
    assert result["success"]
    assert result["latency_ms"] < 1000
    print(f"✓ {test_message}: {result['latency_ms']}ms")
```

## Production Checklist

- [ ] Create agents with descriptive names
- [ ] Write comprehensive system prompts
- [ ] Configure appropriate temperature
- [ ] Select suitable voice
- [ ] Set realistic call duration limits
- [ ] Test with real-world messages
- [ ] Monitor agent performance
- [ ] Review and update regularly

## Summary

The agent management system provides:

✅ **Complete CRUD operations**
✅ **Multi-provider support** (LLM, TTS, STT)
✅ **5 pre-built templates**
✅ **Real-time testing**
✅ **Agent cloning**
✅ **Function/tool support**
✅ **Version control**
✅ **Custom API keys**
✅ **Advanced features** (sentiment, emotion)

**Total Implementation:**
- Agent models: Already existed (comprehensive)
- Agent schemas: ~500 lines
- Agent service: ~700 lines
- Agent endpoints: ~800 lines
- **Total: ~2,000 lines**

All agent management features are now production-ready! 🎉
