# Voicecon Monitoring & Observability Guide

**Complete guide for monitoring, logging, and error tracking**

Version 1.0.0 | Last Updated: December 19, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Sentry Error Tracking](#sentry-error-tracking)
3. [DataDog Monitoring](#datadog-monitoring)
4. [Application Metrics](#application-metrics)
5. [Logging Strategy](#logging-strategy)
6. [Health Checks](#health-checks)
7. [Alerting](#alerting)
8. [Dashboards](#dashboards)
9. [Performance Monitoring](#performance-monitoring)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Monitoring Stack

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  ┌──────────┐  ┌──────────┐            │
│  │ Backend  │  │ Frontend │            │
│  │ FastAPI  │  │ Next.js  │            │
│  └────┬─────┘  └────┬─────┘            │
│       │             │                   │
└───────┼─────────────┼───────────────────┘
        │             │
┌───────▼─────────────▼───────────────────┐
│      Instrumentation Layer              │
│  ┌──────────┐  ┌──────────┐            │
│  │  Sentry  │  │ OpenTel  │            │
│  │ (Errors) │  │ (Traces) │            │
│  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼───────────────────┘
        │             │
┌───────▼─────────────▼───────────────────┐
│      Observability Platform             │
│  ┌──────────┐  ┌──────────┐            │
│  │ DataDog  │  │Prometheus│            │
│  │ (Metrics)│  │ (Metrics)│            │
│  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼───────────────────┘
        │             │
┌───────▼─────────────▼───────────────────┐
│      Alerting & Dashboards              │
│  ┌──────────┐  ┌──────────┐            │
│  │PagerDuty │  │  Slack   │            │
│  │ (On-call)│  │ (Alerts) │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
```

### Key Metrics to Track

**Application Metrics**:
- Request rate (requests/second)
- Error rate (4xx, 5xx errors)
- Response time (p50, p95, p99)
- Throughput (bytes/second)

**Business Metrics**:
- Active calls (concurrent)
- Call duration (average, max)
- Agent response time
- Integration success rate
- Customer satisfaction

**Infrastructure Metrics**:
- CPU utilization
- Memory usage
- Disk I/O
- Network traffic
- Database connections

---

## Sentry Error Tracking

### Backend Setup (FastAPI)

#### 1. Install Sentry SDK

```bash
pip install sentry-sdk[fastapi]
```

#### 2. Configure Sentry in `backend/app/core/sentry.py`

```python
"""
Sentry configuration for error tracking and performance monitoring.
"""
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from app.core.config import settings


def init_sentry():
    """Initialize Sentry SDK for error tracking."""
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"voicecon-backend@{settings.APP_VERSION}",

        # Performance monitoring
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,  # 10% profiling

        # Integrations
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[500, 599],
            ),
            SqlalchemyIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],

        # PII handling
        send_default_pii=False,

        # Performance
        enable_tracing=True,

        # Error filtering
        before_send=before_send_filter,
    )


def before_send_filter(event, hint):
    """
    Filter events before sending to Sentry.

    Use this to:
    - Remove sensitive data
    - Skip certain errors
    - Add custom context
    """
    # Skip health check errors
    if event.get('request', {}).get('url', '').endswith('/health'):
        return None

    # Skip rate limit errors (they're expected)
    if 'RateLimitExceeded' in str(event.get('exception', {})):
        return None

    # Add custom tags
    if 'user' in event:
        event['tags'] = event.get('tags', {})
        event['tags']['user_type'] = 'authenticated'

    return event


def capture_exception(error: Exception, context: dict = None):
    """
    Capture exception with additional context.

    Usage:
        try:
            risky_operation()
        except Exception as e:
            capture_exception(e, {
                'user_id': user.id,
                'operation': 'create_agent'
            })
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)
        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", context: dict = None):
    """
    Capture informational message.

    Usage:
        capture_message(
            "Unusual activity detected",
            level="warning",
            context={'user_id': user.id}
        )
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)
        sentry_sdk.capture_message(message, level=level)
```

#### 3. Initialize in `backend/app/main.py`

```python
from app.core.sentry import init_sentry

# Initialize Sentry
init_sentry()

app = FastAPI(title="Voicecon API")
```

#### 4. Add Request Context Middleware

```python
"""
Middleware to add request context to Sentry.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import sentry_sdk


class SentryContextMiddleware(BaseHTTPMiddleware):
    """Add request context to Sentry events."""

    async def dispatch(self, request: Request, call_next):
        # Set user context if authenticated
        if hasattr(request.state, 'user'):
            user = request.state.user
            sentry_sdk.set_user({
                "id": str(user.id),
                "email": user.email,
                "username": user.full_name,
            })

        # Set request context
        sentry_sdk.set_context("request", {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
        })

        # Process request
        response = await call_next(request)

        return response


# Add to app
app.add_middleware(SentryContextMiddleware)
```

### Frontend Setup (Next.js)

#### 1. Install Sentry SDK

```bash
npm install @sentry/nextjs
```

#### 2. Configure Sentry

Create `frontend/sentry.client.config.ts`:

```typescript
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
  release: `voicecon-frontend@${process.env.NEXT_PUBLIC_APP_VERSION}`,

  // Performance monitoring
  tracesSampleRate: 0.1, // 10% of transactions

  // Session replay
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  integrations: [
    new Sentry.BrowserTracing({
      tracePropagationTargets: [
        'localhost',
        'voicecon.com',
        'api.voicecon.com',
      ],
    }),
    new Sentry.Replay({
      maskAllText: false,
      blockAllMedia: false,
    }),
  ],

  // Error filtering
  beforeSend(event, hint) {
    // Filter out certain errors
    if (event.exception?.values?.[0]?.type === 'ChunkLoadError') {
      return null; // Skip chunk load errors
    }

    return event;
  },
});
```

Create `frontend/sentry.server.config.ts`:

```typescript
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
  tracesSampleRate: 0.1,
});
```

#### 3. Add Error Boundary

Create `frontend/src/components/ErrorBoundary.tsx`:

```typescript
'use client';

import React from 'react';
import * as Sentry from '@sentry/nextjs';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to Sentry
    Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo.componentStack,
        },
      },
    });
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-red-600">
              Something went wrong
            </h1>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="mt-4 rounded bg-blue-500 px-4 py-2 text-white"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

## DataDog Monitoring

### Backend Instrumentation

#### 1. Install DataDog APM

```bash
pip install ddtrace
```

#### 2. Configure DataDog in `backend/app/core/datadog.py`

```python
"""
DataDog APM and metrics configuration.
"""
from ddtrace import tracer, patch_all
from ddtrace.runtime import RuntimeMetrics
from datadog import initialize, statsd
from app.core.config import settings


def init_datadog():
    """Initialize DataDog APM and metrics."""
    if not settings.DATADOG_API_KEY:
        return

    # Initialize DataDog client
    options = {
        'api_key': settings.DATADOG_API_KEY,
        'app_key': settings.DATADOG_APP_KEY,
    }
    initialize(**options)

    # Configure tracer
    tracer.configure(
        hostname='voicecon-backend',
        service_name='voicecon-api',
        env=settings.ENVIRONMENT,
    )

    # Patch libraries for automatic instrumentation
    patch_all()

    # Enable runtime metrics
    RuntimeMetrics.enable()


def record_metric(metric_name: str, value: float, tags: list = None):
    """
    Record custom metric to DataDog.

    Usage:
        record_metric('voicecon.calls.duration', call_duration, tags=['agent:support'])
    """
    statsd.gauge(metric_name, value, tags=tags or [])


def increment_counter(metric_name: str, value: int = 1, tags: list = None):
    """
    Increment counter metric.

    Usage:
        increment_counter('voicecon.calls.total', tags=['direction:inbound'])
    """
    statsd.increment(metric_name, value, tags=tags or [])


def record_histogram(metric_name: str, value: float, tags: list = None):
    """
    Record histogram metric (for distributions).

    Usage:
        record_histogram('voicecon.api.response_time', response_time_ms)
    """
    statsd.histogram(metric_name, value, tags=tags or [])
```

#### 3. Add Metrics to Call Manager

Update `backend/app/services/voice/call_manager.py`:

```python
from app.core.datadog import increment_counter, record_histogram
import time


class CallManager:
    async def create_call(self, agent_id, phone_number, ...):
        start_time = time.time()

        try:
            # Create call
            session = await self._create_session(...)

            # Record metrics
            increment_counter(
                'voicecon.calls.created',
                tags=[
                    f'agent:{agent_id}',
                    f'direction:{direction}',
                    f'status:success'
                ]
            )

            return session

        except Exception as e:
            increment_counter(
                'voicecon.calls.created',
                tags=[
                    f'agent:{agent_id}',
                    f'status:error',
                    f'error:{type(e).__name__}'
                ]
            )
            raise

        finally:
            duration_ms = (time.time() - start_time) * 1000
            record_histogram(
                'voicecon.calls.creation_time',
                duration_ms,
                tags=[f'agent:{agent_id}']
            )

    async def end_call(self, call_id):
        session = self._sessions.get(call_id)
        if not session:
            return

        # Record call duration
        record_histogram(
            'voicecon.calls.duration',
            session.duration_seconds,
            tags=[
                f'agent:{session.agent_id}',
                f'direction:{session.direction}',
                f'status:{session.status}'
            ]
        )

        # Record call cost
        record_metric(
            'voicecon.calls.cost',
            session.cost,
            tags=[f'agent:{session.agent_id}']
        )
```

### Custom Metrics Examples

```python
# Track integration health
increment_counter(
    'voicecon.integrations.api_call',
    tags=[
        'integration:salesforce',
        'action:create_lead',
        'status:success'
    ]
)

# Track workflow execution
record_histogram(
    'voicecon.workflows.execution_time',
    execution_time_ms,
    tags=[
        f'workflow:{workflow_id}',
        f'trigger:{trigger_type}'
    ]
)

# Track LLM usage
increment_counter(
    'voicecon.llm.tokens_used',
    value=tokens_used,
    tags=[
        'provider:openai',
        'model:gpt-4',
        f'agent:{agent_id}'
    ]
)

# Track database query performance
record_histogram(
    'voicecon.database.query_time',
    query_time_ms,
    tags=[
        'table:calls',
        'operation:select'
    ]
)
```

---

## Application Metrics

### Prometheus Metrics Export

#### 1. Install Prometheus Client

```bash
pip install prometheus-client
```

#### 2. Configure Metrics Endpoint

Create `backend/app/core/metrics.py`:

```python
"""
Prometheus metrics for Voicecon.
"""
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    REGISTRY
)

# Application info
app_info = Info('voicecon_app', 'Application information')
app_info.info({
    'version': '1.0.0',
    'environment': 'production'
})

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Call metrics
calls_total = Counter(
    'voicecon_calls_total',
    'Total calls',
    ['agent', 'direction', 'status']
)

calls_active = Gauge(
    'voicecon_calls_active',
    'Currently active calls'
)

call_duration_seconds = Histogram(
    'voicecon_call_duration_seconds',
    'Call duration in seconds',
    ['agent', 'direction'],
    buckets=[30, 60, 120, 300, 600, 1200, 1800, 3600]
)

# Agent metrics
agents_active = Gauge(
    'voicecon_agents_active',
    'Number of active agents'
)

# Integration metrics
integration_calls_total = Counter(
    'voicecon_integration_calls_total',
    'Total integration API calls',
    ['integration', 'action', 'status']
)

integration_call_duration_seconds = Histogram(
    'voicecon_integration_call_duration_seconds',
    'Integration API call duration',
    ['integration', 'action']
)

# Database metrics
db_connections = Gauge(
    'voicecon_db_connections',
    'Database connections',
    ['state']
)

db_query_duration_seconds = Histogram(
    'voicecon_db_query_duration_seconds',
    'Database query duration',
    ['operation']
)

# LLM metrics
llm_requests_total = Counter(
    'voicecon_llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'status']
)

llm_tokens_total = Counter(
    'voicecon_llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model', 'type']
)

llm_cost_total = Counter(
    'voicecon_llm_cost_total',
    'Total LLM cost in USD',
    ['provider', 'model']
)
```

#### 3. Add Metrics Endpoint

In `backend/app/api/v1/api.py`:

```python
from fastapi import Response
from app.core.metrics import generate_latest


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

#### 4. Add Metrics Middleware

```python
"""
Middleware to record HTTP metrics.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from app.core.metrics import (
    http_requests_total,
    http_request_duration_seconds
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time

        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response
```

---

## Logging Strategy

### Structured Logging Setup

Create `backend/app/core/logging.py`:

```python
"""
Structured logging configuration.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "call_id"):
            log_data["call_id"] = record.call_id

        return json.dumps(log_data)


def setup_logging():
    """Configure application logging."""
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Create logger for use in application
logger = logging.getLogger("voicecon")
```

### Usage in Application

```python
from app.core.logging import logger

# Basic logging
logger.info("User logged in", extra={"user_id": user.id})
logger.warning("Rate limit approaching", extra={"user_id": user.id, "requests": 95})
logger.error("Failed to create call", extra={"agent_id": agent.id, "error": str(e)})

# With context manager
import contextvars

request_id_var = contextvars.ContextVar("request_id")

# In middleware
request_id = str(uuid.uuid4())
request_id_var.set(request_id)

# In handler
logger.info("Processing request", extra={"request_id": request_id_var.get()})
```

---

*This guide continues with sections on Health Checks, Alerting, Dashboards, Performance Monitoring, and Troubleshooting. Would you like me to continue with the complete monitoring guide?*

---

*Last Updated: December 19, 2025*
*Version: 1.0.0*
