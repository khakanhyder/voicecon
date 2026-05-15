# Security Implementation Guide

**Date:** December 19, 2025
**Status:** Ready for Implementation
**Priority:** CRITICAL - Required before production deployment

---

## Overview

This guide provides step-by-step instructions to implement all critical security fixes identified in the security audit. **All Priority 1 fixes must be completed before production deployment.**

---

## 🔴 Priority 1: Critical Security Fixes (DO FIRST)

### 1. Implement Rate Limiting

**File Created:** `backend/app/middleware/rate_limit.py`

**Steps to Implement:**

1. **Update requirements.txt:**
```bash
cd backend
echo "redis==5.0.1" >> requirements.txt
pip install redis
```

2. **Update main.py to add rate limiting:**
```python
# File: backend/app/main.py
from app.middleware.rate_limit import init_rate_limit_middleware

# After creating app, before routes:
init_rate_limit_middleware(app, redis_url=settings.REDIS_URL)
```

3. **Update .env with Redis URL:**
```bash
# Add to backend/.env
REDIS_URL=redis://localhost:6379/0
```

4. **Test rate limiting:**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:latest

# Run backend
python -m uvicorn app.main:app --reload

# Test with curl (should get 429 after 5 requests)
for i in {1..10}; do curl -X POST http://localhost:8000/api/v1/auth/login; done
```

**Verification:**
- [ ] Rate limit headers present in responses
- [ ] 429 status returned when limit exceeded
- [ ] Different limits for different endpoints work correctly

---

### 2. Implement CSRF Protection

**File Created:** `backend/app/middleware/csrf_protect.py`

**Steps to Implement:**

1. **Update main.py to add CSRF protection:**
```python
# File: backend/app/main.py
from app.middleware.csrf_protect import init_csrf_middleware

# After rate limiting:
init_csrf_middleware(app)
```

2. **Update frontend to include CSRF token:**
```typescript
// File: frontend/src/lib/api.ts
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true, // Important: allows cookies
});

// Add CSRF token to requests
api.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrf_token='))
    ?.split('=')[1];

  if (csrfToken && config.method !== 'get') {
    config.headers['X-CSRF-Token'] = csrfToken;
  }

  return config;
});
```

3. **Add CSRF token endpoint:**
```python
# File: backend/app/api/v1/endpoints/auth.py
from app.middleware.csrf_protect import get_csrf_token

@router.get("/csrf-token")
async def csrf_token(request: Request):
    """Get CSRF token for client."""
    return {"csrf_token": get_csrf_token(request)}
```

**Verification:**
- [ ] POST/PUT/DELETE without X-CSRF-Token header return 403
- [ ] Requests with valid CSRF token succeed
- [ ] CSRF cookie is set on first request

---

### 3. Fix Encryption Salt

**File Created:** `backend/app/core/security_fixed.py`

**Steps to Implement:**

1. **Generate environment-specific salt:**
```bash
# Generate salt for each environment
python -c "import os; print('ENCRYPTION_SALT=' + os.urandom(16).hex())"

# Example output:
# ENCRYPTION_SALT=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

2. **Add to .env for EACH environment:**
```bash
# Development (.env.development)
ENCRYPTION_SALT=<dev-salt-here>

# Staging (.env.staging)
ENCRYPTION_SALT=<staging-salt-here>

# Production (.env.production)
ENCRYPTION_SALT=<prod-salt-here>
```

3. **Update config.py:**
```python
# File: backend/app/core/config.py
class Settings(BaseSettings):
    # ... existing fields ...

    # Encryption
    ENCRYPTION_SALT: str = Field(
        ...,
        description="Hex-encoded salt for encryption key derivation (32 chars min)"
    )

    @field_validator("ENCRYPTION_SALT")
    @classmethod
    def validate_encryption_salt(cls, v: str) -> str:
        try:
            salt_bytes = bytes.fromhex(v)
            if len(salt_bytes) < 16:
                raise ValueError("Salt must be at least 16 bytes (32 hex chars)")
            return v
        except ValueError:
            raise ValueError("ENCRYPTION_SALT must be valid hex string")
```

4. **Replace security.py with security_fixed.py:**
```bash
# Backup original
cp backend/app/core/security.py backend/app/core/security.py.backup

# Replace with fixed version
cp backend/app/core/security_fixed.py backend/app/core/security.py
```

5. **Re-encrypt existing data (if any):**
```python
# Create migration script: backend/scripts/re_encrypt_data.py
import asyncio
from app.database import get_db
from app.core.security import encryption_manager
from sqlalchemy import select

async def re_encrypt_credentials():
    """Re-encrypt all integration credentials with new salt."""
    # Implementation depends on your data structure
    # This is a template
    async with get_db() as db:
        # Get all encrypted data
        credentials = await db.execute(select(IntegrationCredential))

        for cred in credentials.scalars():
            # Decrypt with old manager (using old salt)
            # Encrypt with new manager (using new salt)
            # Save back to database
            pass

if __name__ == "__main__":
    asyncio.run(re_encrypt_credentials())
```

**Verification:**
- [ ] Application starts without warnings about missing ENCRYPTION_SALT
- [ ] Encryption/decryption works correctly
- [ ] Each environment has unique salt

---

### 4. Implement Webhook Signature Verification

**Example for Stripe webhooks:**

```python
# File: backend/app/api/v1/endpoints/webhooks.py
import stripe
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks with signature verification.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verify signature
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process verified webhook
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        # Handle the event
        await handle_payment_success(payment_intent)

    return {"status": "success"}
```

**Add for each webhook integration:**
- [ ] Stripe webhooks
- [ ] Twilio webhooks
- [ ] SendGrid webhooks
- [ ] Any custom webhooks

**Verification:**
- [ ] Webhooks with invalid signatures are rejected
- [ ] Webhooks with valid signatures are processed
- [ ] Replay attacks are prevented (check timestamp)

---

## 🟡 Priority 2: High Security Improvements

### 5. Add Security Headers

**File Created:** `backend/app/middleware/security_headers.py`

**Implementation:**

```python
# File: backend/app/main.py
from app.middleware.security_headers import init_security_headers_middleware

# Add after CSRF middleware:
init_security_headers_middleware(app)
```

**Verification:**
```bash
# Check headers in response
curl -I http://localhost:8000/api/v1/health

# Should include:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Content-Security-Policy: ...
```

---

### 6. Disable API Docs in Production

**Current Issue:** Docs exposed in production

**Fix:**
```python
# File: backend/app/main.py

# Change from:
app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.DEBUG else None,  # Current
    ...
)

# Change to:
app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.is_development else None,  # Fixed
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.is_development else None,
    ...
)
```

**Verification:**
- [ ] Docs accessible in development
- [ ] Docs return 404 in production

---

### 7. Update Dependencies

**Check for vulnerabilities:**

```bash
cd backend

# Install security scanners
pip install safety pip-audit

# Run scans
safety check --json > security-report.json
pip-audit --format json > audit-report.json

# Review reports and update vulnerable packages
```

**Priority packages to update:**
1. `aiohttp` - Update to 3.9.5+ (CVE fixes)
2. `cryptography` - Check for latest patches
3. `sqlalchemy` - Keep updated for security patches

**Update process:**
```bash
# Test in development first
pip install --upgrade aiohttp cryptography sqlalchemy

# Run all tests
pytest

# If tests pass, update requirements.txt
pip freeze | grep -E "(aiohttp|cryptography|sqlalchemy)" >> requirements.txt
```

---

## 🟢 Priority 3: Recommended Improvements

### 8. Implement Security Logging

**Create security audit log:**

```python
# File: backend/app/services/security/audit_log.py
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("security.audit")

class SecurityEvent:
    """Security event types."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    PERMISSION_DENIED = "permission_denied"
    API_KEY_USED = "api_key_used"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CSRF_VIOLATION = "csrf_violation"

async def log_security_event(
    event_type: str,
    user_id: Optional[str],
    ip_address: str,
    details: dict,
    db: AsyncSession
):
    """
    Log security event to database and logging system.
    """
    # Log to application logs
    logger.warning(
        f"Security Event: {event_type}",
        extra={
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    # Store in database for audit trail
    audit_log = AuditLog(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)
    await db.commit()
```

**Add logging to critical operations:**
```python
# In auth endpoints:
from app.services.security.audit_log import log_security_event, SecurityEvent

@router.post("/login")
async def login(credentials: LoginRequest, request: Request, db: AsyncSession):
    user = await authenticate_user(credentials.email, credentials.password, db)

    if not user:
        # Log failed login
        await log_security_event(
            SecurityEvent.LOGIN_FAILURE,
            None,
            request.client.host,
            {"email": credentials.email},
            db
        )
        raise HTTPException(401, "Invalid credentials")

    # Log successful login
    await log_security_event(
        SecurityEvent.LOGIN_SUCCESS,
        str(user.id),
        request.client.host,
        {"email": credentials.email},
        db
    )

    return {"access_token": create_access_token(...)}
```

---

### 9. Add 2FA Support

**Implementation plan:**

1. Add TOTP library:
```bash
pip install pyotp qrcode
```

2. Add 2FA fields to User model:
```python
# File: backend/app/models/user.py
class User(Base):
    # ... existing fields ...

    totp_secret: Mapped[Optional[str]] = mapped_column(String(255))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes: Mapped[Optional[list]] = mapped_column(JSONB)
```

3. Create 2FA endpoints:
```python
# File: backend/app/api/v1/endpoints/two_factor.py
import pyotp
import qrcode

@router.post("/enable")
async def enable_2fa(current_user: User = Depends(get_current_user)):
    """Enable 2FA for user."""
    secret = pyotp.random_base32()
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        current_user.email,
        issuer_name="Voicecon"
    )

    # Generate QR code
    qr = qrcode.make(totp_uri)
    # Return QR code and secret for user to save

    return {"secret": secret, "qr_code": qr}

@router.post("/verify")
async def verify_2fa(code: str, current_user: User = Depends(get_current_user)):
    """Verify 2FA code."""
    totp = pyotp.TOTP(current_user.totp_secret)
    if totp.verify(code):
        current_user.totp_enabled = True
        return {"success": True}
    raise HTTPException(400, "Invalid code")
```

---

## 🔧 Testing Security Implementations

### Automated Security Testing

**Create security test suite:**

```python
# File: backend/tests/security/test_security_measures.py
import pytest
from fastapi.testclient import TestClient

class TestRateLimiting:
    """Test rate limiting implementation."""

    def test_rate_limit_login_endpoint(self, client: TestClient):
        """Test login endpoint rate limiting."""
        # Make 6 requests (limit is 5)
        for i in range(6):
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "wrong"
            })

            if i < 5:
                assert response.status_code in [401, 422]
            else:
                # 6th request should be rate limited
                assert response.status_code == 429

    def test_rate_limit_headers(self, client: TestClient):
        """Test rate limit headers are present."""
        response = client.get("/api/v1/agents")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

class TestCSRFProtection:
    """Test CSRF protection implementation."""

    def test_csrf_required_for_post(self, client: TestClient):
        """Test POST without CSRF token fails."""
        response = client.post("/api/v1/agents", json={
            "name": "Test Agent"
        })
        assert response.status_code == 403

    def test_csrf_with_valid_token(self, auth_client: TestClient):
        """Test POST with valid CSRF token succeeds."""
        # Get CSRF token
        csrf_response = auth_client.get("/api/v1/auth/csrf-token")
        csrf_token = csrf_response.json()["csrf_token"]

        # Make request with token
        response = auth_client.post(
            "/api/v1/agents",
            json={"name": "Test Agent"},
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code in [200, 201]

class TestSecurityHeaders:
    """Test security headers implementation."""

    def test_security_headers_present(self, client: TestClient):
        """Test security headers are in response."""
        response = client.get("/api/v1/health")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers

class TestEncryption:
    """Test encryption implementation."""

    def test_encryption_decryption(self):
        """Test data can be encrypted and decrypted."""
        from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data

        original = "sensitive_api_key_12345"
        encrypted = encrypt_sensitive_data(original)

        assert encrypted != original
        assert decrypt_sensitive_data(encrypted) == original

    def test_encryption_salt_unique(self):
        """Test encryption uses environment-specific salt."""
        from app.core.config import settings

        # Verify ENCRYPTION_SALT is set
        assert hasattr(settings, 'ENCRYPTION_SALT')
        assert len(settings.ENCRYPTION_SALT) >= 32  # At least 16 bytes hex
```

---

## 📋 Pre-Production Security Checklist

Before deploying to production, verify:

### Environment Configuration
- [ ] `SECRET_KEY` is strong (64+ characters) and unique per environment
- [ ] `ENCRYPTION_SALT` is set and unique per environment
- [ ] `STRIPE_WEBHOOK_SECRET` is configured
- [ ] `TWILIO_AUTH_TOKEN` is configured
- [ ] All API keys are stored in environment variables (not in code)
- [ ] `.env` file is in `.gitignore`
- [ ] `ENVIRONMENT=production` is set
- [ ] `DEBUG=false` is set

### Security Middleware
- [ ] Rate limiting is enabled
- [ ] CSRF protection is enabled
- [ ] Security headers are configured
- [ ] CORS is properly configured (not `allow_origins=["*"]`)

### HTTPS/SSL
- [ ] SSL certificate is valid
- [ ] HSTS is enabled
- [ ] All cookies have `Secure` flag
- [ ] Mixed content warnings resolved

### Authentication
- [ ] Password complexity requirements enforced
- [ ] JWT tokens have reasonable expiration times
- [ ] Refresh token rotation implemented
- [ ] Failed login attempts are logged
- [ ] Account lockout after N failed attempts

### Database
- [ ] Database credentials are secure
- [ ] Database is not publicly accessible
- [ ] Backups are encrypted
- [ ] Connection uses SSL

### Monitoring
- [ ] Sentry (or equivalent) is configured
- [ ] Security events are logged
- [ ] Failed authentication attempts are monitored
- [ ] Unusual API usage patterns trigger alerts

### Dependencies
- [ ] All dependencies are up to date
- [ ] No known vulnerabilities (run `safety check`)
- [ ] Automated dependency updates configured

### Testing
- [ ] All security tests pass
- [ ] Penetration testing completed
- [ ] Load testing completed with security measures

---

## 🚀 Deployment Steps

1. **Update .env files for each environment:**
```bash
# Development
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=<dev-secret>
ENCRYPTION_SALT=<dev-salt>

# Staging
ENVIRONMENT=staging
DEBUG=false
SECRET_KEY=<staging-secret>
ENCRYPTION_SALT=<staging-salt>

# Production
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<prod-secret>
ENCRYPTION_SALT=<prod-salt>
```

2. **Deploy security fixes:**
```bash
# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run database migrations (if any)
alembic upgrade head

# Restart application
systemctl restart voicecon-api
```

3. **Verify security measures:**
```bash
# Test rate limiting
curl -I http://your-domain.com/api/v1/health
# Check for X-RateLimit-* headers

# Test security headers
curl -I http://your-domain.com/api/v1/health
# Check for security headers

# Test HTTPS
curl -I https://your-domain.com/api/v1/health
# Verify SSL certificate
```

4. **Monitor for issues:**
- Check application logs for errors
- Monitor Sentry for exceptions
- Watch for rate limit violations
- Monitor authentication failures

---

## 📞 Support

If you encounter issues implementing these security measures:

1. Review the [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md)
2. Check application logs for error messages
3. Verify environment variables are set correctly
4. Run security tests: `pytest backend/tests/security/`

---

**Last Updated:** December 19, 2025
**Review Date:** January 19, 2026
