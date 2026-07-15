# Workflow Triggers Guide

Complete guide to the Voicecon Workflow Trigger System.

## Table of Contents

1. [Overview](#overview)
2. [Trigger Types](#trigger-types)
3. [Voice Event Triggers](#voice-event-triggers)
4. [Webhook Triggers](#webhook-triggers)
5. [Scheduled Triggers](#scheduled-triggers)
6. [Integration Event Triggers](#integration-event-triggers)
7. [Manual Triggers](#manual-triggers)
8. [Trigger Configuration](#trigger-configuration)
9. [Trigger Testing](#trigger-testing)
10. [API Reference](#api-reference)
11. [Best Practices](#best-practices)

---

## Overview

The Workflow Trigger System automatically starts workflows in response to various events:

- **Voice Events**: Call started, call completed, intent detected, etc.
- **Webhooks**: External systems trigger workflows via HTTP POST
- **Scheduled**: Run workflows on a schedule (cron, interval, one-time)
- **Integration Events**: Events from connected integrations (new lead in CRM, etc.)
- **Manual**: Manually execute workflows via API or UI

### Key Features

- **Flexible Filtering**: Filter which events trigger workflows
- **High Performance**: Async event processing with minimal latency
- **Rate Limiting**: Prevent trigger abuse
- **Trigger Testing**: Test triggers with sample data before going live
- **Validation**: Comprehensive configuration validation
- **Monitoring**: Track trigger execution and performance

---

## Trigger Types

### Available Trigger Types

```python
class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    CALL_COMPLETED = "call_completed"
    CALL_STARTED = "call_started"
    INTEGRATION_EVENT = "integration_event"
```

### Trigger Selection Guide

| Use Case | Trigger Type | Example |
|----------|--------------|---------|
| Run workflow on demand | `manual` | Testing, ad-hoc executions |
| After call ends | `call_completed` | Post-call follow-up, CRM updates |
| When call starts | `call_started` | Real-time notifications |
| External system integration | `webhook` | Zapier, Make.com, custom apps |
| Daily reports | `schedule` (cron) | Analytics, summaries |
| Periodic tasks | `schedule` (interval) | Health checks, sync jobs |
| One-time future task | `schedule` (one-time) | Reminder, delayed action |
| CRM event | `integration_event` | New lead, updated contact |

---

## Voice Event Triggers

Trigger workflows based on call events.

### Supported Events

1. **call_started**: Triggered when a call begins
2. **call_completed**: Triggered when a call ends

### Basic Configuration

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {}
}
```

### With Filters

Filter calls by various criteria:

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "status": "completed",
      "duration_min": 60,
      "duration_max": 3600,
      "agent_id": "agent_123",
      "phone_number": "\\+1.*",
      "sentiment": "positive",
      "intent": "support",
      "keywords": ["urgent", "escalate"]
    }
  }
}
```

### Filter Options

| Filter | Type | Description | Example |
|--------|------|-------------|---------|
| `status` | string | Call status | `"completed"`, `"failed"` |
| `duration_min` | integer | Minimum duration (seconds) | `60` |
| `duration_max` | integer | Maximum duration (seconds) | `3600` |
| `agent_id` | string | Specific agent | `"agent_123"` |
| `phone_number` | regex | Phone number pattern | `"\\+1.*"` (US numbers) |
| `sentiment` | string | Call sentiment | `"positive"`, `"negative"`, `"neutral"` |
| `intent` | string | Detected intent | `"support"`, `"sales"` |
| `keywords` | array | Keywords in transcript | `["urgent", "cancel"]` |

### Examples

#### Trigger on Long Calls

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "duration_min": 600
    }
  }
}
```

#### Trigger on Negative Sentiment

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "sentiment": "negative"
    }
  }
}
```

#### Trigger on Specific Keywords

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "keywords": ["cancel", "refund", "complaint"]
    }
  }
}
```

### Trigger Data Structure

When a voice event triggers a workflow, the following data is available:

```json
{
  "event_type": "voice_event",
  "call_id": "uuid",
  "call_sid": "twilio_call_sid",
  "status": "completed",
  "duration": 120,
  "agent_id": "agent_123",
  "phone_number": "+1234567890",
  "transcript": "Full call transcript...",
  "intent": "support",
  "sentiment": {
    "label": "positive",
    "score": 0.85
  },
  "metadata": {},
  "triggered_at": "2025-11-16T10:00:00Z"
}
```

---

## Webhook Triggers

Allow external systems to trigger workflows via HTTP POST.

### Basic Configuration

```json
{
  "trigger_type": "webhook",
  "trigger_config": {
    "webhook_key": "your-secure-key-min-16-chars"
  }
}
```

### With Security Options

```json
{
  "trigger_type": "webhook",
  "trigger_config": {
    "webhook_key": "super-secure-webhook-key-123",
    "allowed_ips": ["192.168.1.100", "10.0.0.50"]
  }
}
```

### Webhook URL Format

```
POST https://api.voicecon.com/api/v1/workflows/webhook/{webhook_key}
```

### Example Request

```bash
curl -X POST \
  https://api.voicecon.com/api/v1/workflows/webhook/super-secure-webhook-key-123 \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": "cust_123",
    "order_id": "ord_456",
    "total": 99.99
  }'
```

### Response

```json
{
  "success": true,
  "execution_ids": ["exec_uuid_1", "exec_uuid_2"],
  "count": 2
}
```

### Trigger Data Structure

```json
{
  "event_type": "webhook",
  "payload": {
    "customer_id": "cust_123",
    "order_id": "ord_456",
    "total": 99.99
  },
  "headers": {},
  "source_ip": "192.168.1.100",
  "triggered_at": "2025-11-16T10:00:00Z"
}
```

### Security Best Practices

1. **Use Long, Random Webhook Keys**: Minimum 16 characters, use UUID or random string
2. **IP Whitelisting**: Restrict to known IPs when possible
3. **Rotate Keys**: Periodically rotate webhook keys
4. **Monitor Usage**: Track webhook calls for suspicious activity
5. **Rate Limiting**: Configure rate limits to prevent abuse

---

## Scheduled Triggers

Run workflows on a schedule.

### Schedule Types

1. **Cron**: Unix cron expressions for complex schedules
2. **Interval**: Run every N seconds
3. **One-time**: Execute once at specific time

### Cron Schedule

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "cron",
    "cron_expression": "0 9 * * *"
  }
}
```

#### Common Cron Expressions

| Expression | Description |
|------------|-------------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1` | Every Monday at 9:00 AM |
| `0 0 1 * *` | First day of every month |
| `0 0 * * 0` | Every Sunday at midnight |
| `*/15 * * * *` | Every 15 minutes |
| `0 9,17 * * *` | Daily at 9:00 AM and 5:00 PM |
| `0 9-17 * * *` | Every hour from 9 AM to 5 PM |

#### Cron Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
* * * * *
```

### Interval Schedule

Run every N seconds:

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "interval",
    "interval_seconds": 3600
  }
}
```

**Examples:**
- Every minute: `"interval_seconds": 60`
- Every 5 minutes: `"interval_seconds": 300`
- Every hour: `"interval_seconds": 3600`
- Every day: `"interval_seconds": 86400`

### One-Time Schedule

Execute once at specific time:

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "one_time",
    "scheduled_at": "2025-12-25T09:00:00Z"
  }
}
```

**Note:** Workflow will be automatically deactivated after execution.

### Scheduler Operation

The scheduler:
- Checks for due workflows every 30 seconds
- Runs workflows asynchronously (non-blocking)
- Updates `last_executed_at` after each run
- Automatically deactivates one-time schedules after execution

### Trigger Data Structure

```json
{
  "event_type": "scheduled",
  "schedule_type": "cron",
  "triggered_at": "2025-11-16T09:00:00Z"
}
```

---

## Integration Event Triggers

Trigger workflows when integration events occur.

### Configuration

```json
{
  "trigger_type": "integration_event",
  "trigger_config": {
    "integration_type": "salesforce",
    "event_type": "lead.created"
  }
}
```

### With Filters

Filter events by payload fields:

```json
{
  "trigger_type": "integration_event",
  "trigger_config": {
    "integration_type": "salesforce",
    "event_type": "lead.created",
    "filters": {
      "LeadSource": "Website",
      "Status": "New"
    }
  }
}
```

### Supported Integrations

| Integration | Event Types |
|-------------|-------------|
| `salesforce` | `lead.created`, `contact.updated`, `opportunity.closed` |
| `hubspot` | `contact.created`, `deal.updated`, `company.created` |
| `stripe` | `payment.succeeded`, `subscription.created`, `invoice.paid` |
| `slack` | `message.posted`, `reaction.added` |

### Trigger Data Structure

```json
{
  "event_type": "integration_event",
  "integration_type": "salesforce",
  "integration_event_type": "lead.created",
  "payload": {
    "LeadId": "00Q...",
    "Email": "john@example.com",
    "Company": "Acme Corp",
    "LeadSource": "Website"
  },
  "metadata": {},
  "triggered_at": "2025-11-16T10:00:00Z"
}
```

---

## Manual Triggers

Execute workflows on demand via API or UI.

### Configuration

```json
{
  "trigger_type": "manual",
  "trigger_config": {}
}
```

### Execution via API

```bash
POST /api/v1/workflows/{workflow_id}/execute
```

```json
{
  "trigger_data": {
    "customer_id": "cust_123",
    "reason": "manual_test"
  },
  "wait_for_completion": false
}
```

### Use Cases

- Testing workflows
- Ad-hoc execution
- Admin tasks
- Troubleshooting
- Re-running failed workflows

---

## Trigger Configuration

### Complete Workflow Example

```json
{
  "name": "Post-Call Follow-up",
  "description": "Send follow-up email after support calls",
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "intent": "support",
      "duration_min": 120,
      "sentiment": "positive"
    }
  },
  "workflow_steps": [
    {
      "id": "get_customer",
      "type": "action",
      "config": {
        "connection_id": "{{connections.salesforce}}",
        "action": "get_contact",
        "parameters": {
          "phone": "{{trigger.phone_number}}"
        }
      }
    },
    {
      "id": "send_email",
      "type": "action",
      "config": {
        "connection_id": "{{connections.sendgrid}}",
        "action": "send_email",
        "parameters": {
          "to": "{{steps.get_customer.result.email}}",
          "subject": "Thank you for calling!",
          "body": "Thanks for your call. Here's a summary..."
        }
      }
    }
  ],
  "is_active": true
}
```

### Validation

All trigger configurations are validated when creating/updating workflows:

```python
from app.services.workflows import TriggerValidator

TriggerValidator.validate_trigger_config(trigger_type, trigger_config)
```

**Validates:**
- Required fields are present
- Cron expressions are valid
- Webhook keys are secure (min 16 chars)
- Schedule times are in the future
- Integration types are supported

---

## Trigger Testing

Test triggers before activating workflows.

### Test Trigger API

```bash
POST /api/v1/workflows/{workflow_id}/test-trigger
```

```json
{
  "call_id": "test_call_123",
  "status": "completed",
  "duration": 180,
  "sentiment": {"label": "positive", "score": 0.9},
  "transcript": "Customer was very satisfied..."
}
```

### Response

```json
{
  "workflow_id": "workflow_uuid",
  "trigger_type": "call_completed",
  "would_trigger": true,
  "prepared_data": {
    "event_type": "voice_event",
    "call_id": "test_call_123",
    "status": "completed",
    "duration": 180,
    "sentiment": {"label": "positive", "score": 0.9}
  },
  "test_data": {
    "call_id": "test_call_123",
    "status": "completed",
    "duration": 180
  }
}
```

### Test Scenarios

#### Test Voice Event Filter

```json
{
  "test_data": {
    "status": "completed",
    "duration": 45,
    "sentiment": {"label": "negative"}
  }
}
```

Expected: `"would_trigger": false` (duration too short)

#### Test Webhook Trigger

```json
{
  "test_data": {
    "webhook_key": "correct-key",
    "payload": {"order_id": "123"}
  }
}
```

Expected: `"would_trigger": true`

---

## API Reference

### Trigger Workflow Endpoints

#### Test Trigger
```
POST /api/v1/workflows/{workflow_id}/test-trigger
```

**Request:**
```json
{
  "call_id": "test_123",
  "duration": 120
}
```

**Response:**
```json
{
  "would_trigger": true,
  "prepared_data": {...}
}
```

#### Webhook Trigger
```
POST /api/v1/workflows/webhook/{webhook_key}
```

**Public endpoint** - no authentication required

**Request:**
```json
{
  "customer_id": "cust_123",
  "action": "order_placed"
}
```

**Response:**
```json
{
  "success": true,
  "execution_ids": ["exec_1", "exec_2"],
  "count": 2
}
```

#### Voice Event Trigger
```
POST /api/v1/workflows/trigger/voice-event
```

**Request:**
```json
{
  "event_type": "call_completed",
  "call_id": "call_123",
  "duration": 180
}
```

**Response:**
```json
{
  "success": true,
  "event_type": "call_completed",
  "execution_ids": ["exec_1"],
  "count": 1
}
```

#### Integration Event Trigger
```
POST /api/v1/workflows/trigger/integration-event
```

**Request:**
```json
{
  "integration_type": "salesforce",
  "event_type": "lead.created",
  "payload": {
    "LeadId": "00Q123",
    "Email": "john@example.com"
  }
}
```

**Response:**
```json
{
  "success": true,
  "integration_type": "salesforce",
  "event_type": "lead.created",
  "execution_ids": ["exec_1"],
  "count": 1
}
```

---

## Best Practices

### 1. Use Filters Wisely

**Good:**
```json
{
  "filters": {
    "duration_min": 60,
    "sentiment": "negative"
  }
}
```

**Bad:**
```json
{
  "filters": {}
}
```

Empty filters trigger on ALL events, which may be too broad.

### 2. Test Before Activating

Always test triggers with sample data:

```bash
curl -X POST /api/v1/workflows/{id}/test-trigger \
  -d '{"call_id": "test", "duration": 100}'
```

### 3. Secure Webhook Keys

```python
import secrets

# Generate secure webhook key
webhook_key = secrets.token_urlsafe(32)
```

### 4. Monitor Trigger Performance

Track metrics:
- Trigger rate (events/minute)
- Match rate (triggers/events)
- Execution success rate
- Average latency

### 5. Use Appropriate Schedule Types

| Need | Use |
|------|-----|
| Complex schedule | Cron |
| Simple periodic | Interval |
| One-time future | One-time |

### 6. Handle High-Volume Triggers

For high-volume events:
- Use specific filters to reduce triggers
- Consider rate limiting
- Use batch processing where possible
- Monitor execution costs

### 7. Error Handling

Configure workflows to handle trigger failures:

```json
{
  "error_handling": "continue",
  "max_retries": 3,
  "retry_delay": 60
}
```

### 8. Documentation

Document trigger configurations:

```json
{
  "name": "Support Call Follow-up",
  "description": "Triggers on completed support calls over 2 minutes with negative sentiment to escalate to manager",
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "intent": "support",
      "duration_min": 120,
      "sentiment": "negative"
    }
  }
}
```

---

## Advanced Examples

### Multi-Condition Voice Trigger

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "duration_min": 300,
      "sentiment": "negative",
      "keywords": ["cancel", "refund", "angry"],
      "agent_id": "agent_support_123"
    }
  }
}
```

### Scheduled Daily Report

```json
{
  "name": "Daily Call Analytics Report",
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "cron",
    "cron_expression": "0 9 * * *"
  },
  "workflow_steps": [
    {
      "id": "get_analytics",
      "type": "action",
      "config": {
        "connection_id": "{{connections.analytics}}",
        "action": "get_daily_stats"
      }
    },
    {
      "id": "send_report",
      "type": "action",
      "config": {
        "connection_id": "{{connections.slack}}",
        "action": "send_message",
        "parameters": {
          "channel": "#reports",
          "text": "Daily Report: {{steps.get_analytics.result}}"
        }
      }
    }
  ]
}
```

### Webhook with Validation

```json
{
  "trigger_type": "webhook",
  "trigger_config": {
    "webhook_key": "secure-key-min-16-chars",
    "allowed_ips": ["192.168.1.100"]
  },
  "workflow_steps": [
    {
      "id": "validate_payload",
      "type": "condition",
      "config": {
        "condition": "{{trigger.payload.order_id}} != null"
      }
    },
    {
      "id": "process_order",
      "type": "action",
      "config": {
        "connection_id": "{{connections.stripe}}",
        "action": "get_payment_intent",
        "parameters": {
          "payment_intent_id": "{{trigger.payload.order_id}}"
        }
      }
    }
  ]
}
```

---

## Troubleshooting

### Trigger Not Firing

1. **Check workflow is active**: `is_active: true`
2. **Verify filters**: Test with `test-trigger` endpoint
3. **Check logs**: Review execution logs
4. **Validate config**: Ensure trigger_config is valid

### Webhook 404

1. **Verify webhook key**: Must match exactly
2. **Check URL**: Ensure correct endpoint
3. **Review active workflows**: At least one must match the key

### Schedule Not Running

1. **Verify cron expression**: Test with croniter
2. **Check scheduler is running**: Scheduler must be started
3. **Review last_executed_at**: Ensure not executed recently for interval

### Too Many Triggers

1. **Add filters**: Narrow down trigger conditions
2. **Increase thresholds**: Adjust duration_min, etc.
3. **Rate limiting**: Implement rate limits
4. **Review logs**: Identify trigger sources

---

## See Also

- [Workflow System Guide](./WORKFLOW_SYSTEM_GUIDE.md)
- [Data Mapper Guide](./DATA_MAPPER_GUIDE.md)
- [Integration Connectors](./NEW_CONNECTORS_SUMMARY.md)
