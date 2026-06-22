"""
Agent schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from uuid import UUID


# LLM Configuration
class LLMConfig(BaseModel):
    """LLM configuration schema."""
    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-5.4-nano", description="Model name")
    temperature: Decimal = Field(default=Decimal("0.7"), ge=0, le=2, description="Temperature (0-2)")
    max_tokens: int = Field(default=1000, ge=1, le=4000, description="Max tokens")
    api_key: Optional[str] = Field(default=None, description="Custom API key (will be encrypted)")


# Voice/TTS Configuration
class VoiceConfig(BaseModel):
    """Voice/TTS configuration schema."""
    provider: str = Field(default="elevenlabs", description="TTS provider")
    voice_id: Optional[str] = Field(default="21m00Tcm4TlvDq8ikWAM", description="Voice ID or name")
    speed: Decimal = Field(default=Decimal("1.0"), ge=0.5, le=2.0, description="Speech speed")
    pitch: Decimal = Field(default=Decimal("1.0"), ge=0.5, le=2.0, description="Speech pitch")
    api_key: Optional[str] = Field(default=None, description="Custom API key")


# STT Configuration
class STTConfig(BaseModel):
    """STT configuration schema."""
    provider: str = Field(default="deepgram", description="STT provider")
    language: str = Field(default="en", description="Language code")
    model: Optional[str] = Field(default="nova-2", description="Model name")
    api_key: Optional[str] = Field(default=None, description="Custom API key")


# Conversation Settings
class ConversationSettings(BaseModel):
    """Conversation settings schema."""
    interrupt_enabled: bool = Field(default=True, description="Allow user interruptions")
    interrupt_sensitivity: Decimal = Field(default=Decimal("0.5"), ge=0, le=1, description="Interrupt sensitivity")
    silence_timeout: int = Field(default=3000, ge=500, le=10000, description="Silence timeout (ms)")
    max_call_duration: int = Field(default=1800, ge=60, le=7200, description="Max call duration (seconds)")
    end_call_phrases: List[str] = Field(default_factory=list, description="Phrases that end the call")


# Advanced Features
class AdvancedFeatures(BaseModel):
    """Advanced features schema."""
    sentiment_analysis_enabled: bool = Field(default=False)
    emotion_detection_enabled: bool = Field(default=False)
    background_noise_reduction: bool = Field(default=True)
    knowledge_base_enabled: bool = Field(default=False)
    knowledge_base_config: dict = Field(default_factory=dict)


# Agent Create Schema
class AgentCreate(BaseModel):
    """Schema for creating an agent."""
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(default=None, description="Agent description")
    type: str = Field(default="assistant", description="Agent type")

    # Core prompts
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    first_message: Optional[str] = Field(default=None, description="First message to caller")

    # Service configurations
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    voice: VoiceConfig = Field(default_factory=VoiceConfig, description="Voice configuration")
    stt: STTConfig = Field(default_factory=STTConfig, description="STT configuration")

    # Settings
    settings: ConversationSettings = Field(default_factory=ConversationSettings, description="Conversation settings")
    advanced: AdvancedFeatures = Field(default_factory=AdvancedFeatures, description="Advanced features")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for organization")
    is_public: bool = Field(default=False, description="Make agent publicly available")

    @validator("type")
    def validate_type(cls, v):
        """Validate agent type."""
        allowed = ["assistant", "squad"]
        if v not in allowed:
            raise ValueError(f"Type must be one of: {allowed}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Customer Support Agent",
                "description": "Handles customer support inquiries",
                "system_prompt": "You are a helpful customer support agent...",
                "first_message": "Hello! How can I help you today?",
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.7
                },
                "voice": {
                    "provider": "elevenlabs",
                    "voice_id": "rachel",
                    "speed": 1.0
                },
                "settings": {
                    "interrupt_enabled": True,
                    "max_call_duration": 1800
                }
            }
        }


# Agent Update Schema
class AgentUpdate(BaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None

    llm: Optional[LLMConfig] = None
    voice: Optional[VoiceConfig] = None
    stt: Optional[STTConfig] = None
    settings: Optional[ConversationSettings] = None
    advanced: Optional[AdvancedFeatures] = None

    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


# Agent Response Schema
class AgentResponse(BaseModel):
    """Schema for agent response."""
    id: UUID
    user_id: UUID
    organization_id: UUID

    name: str
    description: Optional[str]
    type: str

    system_prompt: Optional[str]
    first_message: Optional[str]

    # LLM config
    llm_provider: str
    llm_model: str
    llm_temperature: Decimal
    llm_max_tokens: int

    # Voice config
    tts_provider: str
    tts_voice_id: Optional[str]
    tts_speed: Decimal
    tts_pitch: Decimal

    # STT config
    stt_provider: str
    stt_language: str
    stt_model: Optional[str]

    # Conversation settings
    interrupt_enabled: bool
    interrupt_sensitivity: Decimal
    silence_timeout: int
    max_call_duration: int
    end_call_phrases: List[str]

    # Advanced features
    sentiment_analysis_enabled: bool
    emotion_detection_enabled: bool
    background_noise_reduction: bool
    knowledge_base_enabled: bool

    # Metadata
    is_active: bool
    is_public: bool
    tags: List[str]
    version: int

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Agent List Response
class AgentListResponse(BaseModel):
    """Schema for list of agents."""
    agents: List[AgentResponse]
    total: int
    skip: int
    limit: int


# Agent Function Schema
class AgentFunctionCreate(BaseModel):
    """Schema for creating an agent function."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    parameters: dict = Field(..., description="JSON Schema for parameters")

    webhook_url: Optional[str] = None
    http_method: str = Field(default="POST")
    headers: dict = Field(default_factory=dict)
    timeout: int = Field(default=5000, ge=1000, le=30000)
    retry_count: int = Field(default=3, ge=0, le=5)

    is_active: bool = Field(default=True)
    execution_order: int = Field(default=0)


class AgentFunctionUpdate(BaseModel):
    """Schema for updating an agent function."""
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    webhook_url: Optional[str] = None
    http_method: Optional[str] = None
    headers: Optional[dict] = None
    timeout: Optional[int] = None
    retry_count: Optional[int] = None
    is_active: Optional[bool] = None


class AgentFunctionResponse(BaseModel):
    """Schema for agent function response."""
    id: UUID
    agent_id: UUID
    name: str
    description: str
    parameters: dict
    webhook_url: Optional[str]
    http_method: str
    headers: dict
    timeout: int
    retry_count: int
    is_active: bool
    execution_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Agent Test Request
class AgentTestRequest(BaseModel):
    """Schema for testing an agent."""
    test_message: str = Field(..., description="Test message to send to agent")
    test_mode: str = Field(default="text", description="Test mode (text, audio)")
    phone_number: Optional[str] = Field(default=None, description="Phone number for audio test")


# Agent Test Response
class AgentTestResponse(BaseModel):
    """Schema for agent test response."""
    success: bool
    test_id: UUID
    agent_response: str
    latency_ms: int
    costs: dict
    metadata: dict


# Agent Template
class AgentTemplate(BaseModel):
    """Predefined agent template."""
    id: str
    name: str
    description: str
    category: str
    template_data: AgentCreate
    thumbnail_url: Optional[str] = None
    use_count: int = 0


# Agent Clone Request
class AgentCloneRequest(BaseModel):
    """Schema for cloning an agent."""
    name: str = Field(..., description="Name for cloned agent")
    include_functions: bool = Field(default=True, description="Clone functions")
    include_knowledge_base: bool = Field(default=False, description="Clone knowledge base")
