"""
Application configuration management using Pydantic Settings.
"""
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    # Application
    APP_NAME: str = "Voicecon"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Debug mode")
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production-use-a-long-random-string", description="Secret key for JWT tokens")
    # Salt for deriving the credential-encryption key. MUST be stable across
    # restarts, or previously-encrypted stored credentials become undecryptable.
    ENCRYPTION_SALT: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # Database
    DATABASE_URL: str = Field(default="mysql+aiomysql://root:password@localhost:3306/voicecon", description="Database URL")
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    # CORS — stored as raw string; parse via cors_origins property
    BACKEND_CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Allowed CORS origins (comma-separated or JSON array)"
    )

    # Public URLs Twilio's servers use to reach this backend. Twilio calls these
    # from the internet, so they must be a PUBLIC https/wss address (a deployed
    # domain or an ngrok tunnel) — never localhost.
    #   API_BASE_URL   e.g. https://your-app.onrender.com   (used to build voice/status webhook URLs)
    #   WEBSOCKET_URL  e.g. wss://your-app.onrender.com     (Twilio Media Streams socket)
    #   SERVER_HOST    host only, e.g. your-app.onrender.com (fallback if API_BASE_URL is unset)
    # If left unset, the code falls back to the inbound request's Host header.
    API_BASE_URL: Optional[str] = None
    WEBSOCKET_URL: Optional[str] = None
    SERVER_HOST: Optional[str] = None

    # API Keys - External Services
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    # Point the OpenAI client at an OpenAI-compatible gateway, e.g. OpenRouter
    # (https://openrouter.ai/api/v1). Unset means api.openai.com.
    OPENAI_BASE_URL: Optional[str] = None

    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None

    # Deepgram (STT)
    DEEPGRAM_API_KEY: Optional[str] = None

    # ElevenLabs (TTS)
    ELEVENLABS_API_KEY: Optional[str] = None

    # Twilio (Telephony)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    # Verify the X-Twilio-Signature on inbound webhooks. Auto-skips when no auth
    # token is configured (nothing to validate against), so local/dev without
    # Twilio creds is unaffected.
    TWILIO_VALIDATE_WEBHOOKS: bool = True
    # Public base URL Twilio calls (e.g. https://api.example.com). Used to
    # reconstruct the exact signed URL behind a TLS-terminating proxy.
    TWILIO_PUBLIC_BASE_URL: Optional[str] = None

    # Stripe (Payments)
    STRIPE_API_KEY: Optional[str] = None  # legacy alias for STRIPE_SECRET_KEY
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    @property
    def stripe_secret_key(self) -> Optional[str]:
        """Resolve the Stripe secret key (prefers STRIPE_SECRET_KEY, falls back to legacy)."""
        return self.STRIPE_SECRET_KEY or self.STRIPE_API_KEY

    # ---- Social login (Google / Apple "Sign in with") ----
    # Public URL of the frontend — used as the OAuth origin/redirect base.
    FRONTEND_URL: str = Field(default="http://localhost:3000")

    # Google OAuth 2.0 — from Google Cloud Console → APIs & Services → Credentials
    # (OAuth 2.0 Client ID of type "Web application").
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Apple "Sign in with Apple" — from the Apple Developer portal.
    #   APPLE_CLIENT_ID: the Services ID (e.g. com.voicecon.web), used as the token audience
    #   APPLE_TEAM_ID / APPLE_KEY_ID / APPLE_PRIVATE_KEY: only needed for the
    #     authorization-code exchange (refresh tokens); pure sign-in verifies the
    #     id_token and needs just APPLE_CLIENT_ID.
    APPLE_CLIENT_ID: Optional[str] = None
    APPLE_TEAM_ID: Optional[str] = None
    APPLE_KEY_ID: Optional[str] = None
    APPLE_PRIVATE_KEY: Optional[str] = None

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def apple_oauth_enabled(self) -> bool:
        return bool(self.APPLE_CLIENT_ID)

    @property
    def stripe_configured(self) -> bool:
        """True when a real (non-placeholder) Stripe secret key is set."""
        key = self.stripe_secret_key
        return bool(key) and key.startswith("sk_") and "..." not in key

    # Mailchimp (Waitlist / marketing audience)
    #   MAILCHIMP_API_KEY        e.g. abc123def456...-us21  (the -us21 suffix is the data center)
    #   MAILCHIMP_AUDIENCE_ID    the target Audience (List) ID
    #   MAILCHIMP_SERVER_PREFIX  optional override for the data center (e.g. us21); derived
    #                            from the API key suffix when left unset.
    MAILCHIMP_API_KEY: Optional[str] = None
    MAILCHIMP_AUDIENCE_ID: Optional[str] = None
    MAILCHIMP_SERVER_PREFIX: Optional[str] = None

    @property
    def mailchimp_server_prefix(self) -> Optional[str]:
        """Data center prefix for Mailchimp API calls (e.g. 'us21').

        Prefers the explicit override, otherwise reads the '-us21' suffix that
        Mailchimp appends to every API key.
        """
        if self.MAILCHIMP_SERVER_PREFIX:
            return self.MAILCHIMP_SERVER_PREFIX
        if self.MAILCHIMP_API_KEY and "-" in self.MAILCHIMP_API_KEY:
            return self.MAILCHIMP_API_KEY.rsplit("-", 1)[-1]
        return None

    @property
    def mailchimp_configured(self) -> bool:
        """True when Mailchimp is fully configured for waitlist sign-ups."""
        return bool(
            self.MAILCHIMP_API_KEY
            and self.MAILCHIMP_AUDIENCE_ID
            and self.mailchimp_server_prefix
        )

    # SendGrid (Email)
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None

    # ---- Email / SMTP ----
    # Generic SMTP transport. Fill these in to enable real email delivery; when
    # unset (and SendGrid is also unset) the app falls back to a console provider
    # that logs emails instead of sending them, so dev works with no credentials.
    #   EMAIL_PROVIDER: "auto" | "smtp" | "sendgrid" | "console"
    EMAIL_PROVIDER: str = Field(default="auto", description="Email provider selection")
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True   # STARTTLS on a plaintext port (587)
    SMTP_USE_SSL: bool = False  # implicit TLS (465); mutually exclusive with STARTTLS
    SMTP_TIMEOUT: int = 15
    # Default From identity for all outbound mail.
    EMAIL_FROM: str = Field(default="no-reply@voicecon.app", description="Default From address")
    EMAIL_FROM_NAME: str = Field(default="Voicecon", description="Default From display name")

    @property
    def smtp_configured(self) -> bool:
        """SMTP is usable when at least a host is set."""
        return bool(self.SMTP_HOST)

    @property
    def sendgrid_configured(self) -> bool:
        return bool(self.SENDGRID_API_KEY)

    @property
    def resolved_email_provider(self) -> str:
        """The provider actually used given config and the EMAIL_PROVIDER hint."""
        choice = (self.EMAIL_PROVIDER or "auto").lower()
        if choice in ("smtp", "sendgrid", "console"):
            return choice
        # auto: prefer SMTP, then SendGrid, else console (log-only)
        if self.smtp_configured:
            return "smtp"
        if self.sendgrid_configured:
            return "sendgrid"
        return "console"

    @property
    def email_from_full(self) -> str:
        """RFC 5322 From header, e.g. 'Voicecon <no-reply@voicecon.app>'."""
        return f"{self.EMAIL_FROM_NAME} <{self.EMAIL_FROM}>"

    # AWS (Storage)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # Sentry (Error Tracking)
    SENTRY_DSN: Optional[str] = None

    # WebSocket
    WS_MESSAGE_QUEUE_SIZE: int = 100
    WS_HEARTBEAT_INTERVAL: int = 30

    @property
    def cors_origins(self) -> List[str]:
        v = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not v:
            return ["http://localhost:3000"]
        if v.startswith("["):
            import json
            try:
                return json.loads(v)
            except Exception:
                pass
        origins = [o.strip() for o in v.split(",") if o.strip()]
        return origins or ["http://localhost:3000"]

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def assemble_celery_broker(cls, v: Optional[str], info) -> str:
        if v:
            return v
        # Default to REDIS_URL if not provided
        redis_url = info.data.get("REDIS_URL", "redis://localhost:6379/0")
        return redis_url

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def assemble_celery_backend(cls, v: Optional[str], info) -> str:
        if v:
            return v
        # Default to REDIS_URL if not provided
        redis_url = info.data.get("REDIS_URL", "redis://localhost:6379/0")
        return redis_url

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


# Create global settings instance
settings = Settings()
