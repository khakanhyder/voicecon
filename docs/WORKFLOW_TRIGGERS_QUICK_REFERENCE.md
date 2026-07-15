# Workflow Triggers Quick Reference

Quick reference for the Voicecon Workflow Trigger System.

## Trigger Types

```python
TriggerType.MANUAL             # On-demand execution
TriggerType.CALL_STARTED        # When call begins
TriggerType.CALL_COMPLETED      # When call ends
TriggerType.WEBHOOK             # External HTTP trigger
TriggerType.SCHEDULE            # Time-based trigger
TriggerType.INTEGRATION_EVENT   # Integration events
```

---

## Voice Event Triggers

### Basic Configuration

```json
{
  "trigger_type": "call_completed",
  "trigger_config": {}
}
```

### With Filters

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
      "keywords": ["urgent", "help"]
    }
  }
}
```

### Common Patterns

**Long calls only:**
```json
{"filters": {"duration_min": 300}}
```

**Negative sentiment:**
```json
{"filters": {"sentiment": "negative"}}
```

**Specific keywords:**
```json
{"filters": {"keywords": ["cancel", "refund"]}}
```

---

## Webhook Triggers

### Configuration

```json
{
  "trigger_type": "webhook",
  "trigger_config": {
    "webhook_key": "secure-key-min-16-chars",
    "allowed_ips": ["192.168.1.100"]
  }
}
```

### Webhook URL

```
POST /api/v1/workflows/webhook/{webhook_key}
```

### Example Request

```bash
curl -X POST \
  https://api.voicecon.com/api/v1/workflows/webhook/your-key \
  -H 'Content-Type: application/json' \
  -d '{"customer_id": "123"}'
```

---

## Scheduled Triggers

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

**Common Cron Expressions:**

| Expression | Description |
|------------|-------------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Daily at 9 AM |
| `0 9 * * 1` | Every Monday at 9 AM |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 1 * *` | First of month |

### Interval Schedule

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "interval",
    "interval_seconds": 3600
  }
}
```

**Common Intervals:**
- Every minute: `60`
- Every 5 minutes: `300`
- Every hour: `3600`
- Every day: `86400`

### One-Time Schedule

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "one_time",
    "scheduled_at": "2025-12-25T09:00:00Z"
  }
}
```

---

## Integration Event Triggers

### Configuration

```json
{
  "trigger_type": "integration_event",
  "trigger_config": {
    "integration_type": "salesforce",
    "event_type": "lead.created",
    "filters": {
      "LeadSource": "Website"
    }
  }
}
```

### Supported Integrations

| Integration | Example Events |
|-------------|----------------|
| `salesforce` | `lead.created`, `contact.updated` |
| `hubspot` | `contact.created`, `deal.updated` |
| `stripe` | `payment.succeeded`, `subscription.created` |
| `slack` | `message.posted` |

---

## Manual Triggers

### Configuration

```json
{
  "trigger_type": "manual",
  "trigger_config": {}
}
```

### Execution

```bash
POST /api/v1/workflows/{workflow_id}/execute
{
  "trigger_data": {"reason": "manual_test"}
}
```

---

## Filter Reference

### Voice Event Filters

| Filter | Type | Example |
|--------|------|---------|
| `status` | string | `"completed"` |
| `duration_min` | integer | `60` (seconds) |
| `duration_max` | integer | `3600` (seconds) |
| `agent_id` | string | `"agent_123"` |
| `phone_number` | regex | `"\\+1.*"` |
| `sentiment` | string | `"positive"`, `"negative"`, `"neutral"` |
| `intent` | string | `"support"`, `"sales"` |
| `keywords` | array | `["urgent", "help"]` |

---

## API Endpoints

### Test Trigger

```bash
POST /api/v1/workflows/{workflow_id}/test-trigger
Authorization: Bearer {token}

{
  "call_id": "test",
  "duration": 120
}
```

### Trigger Webhook

```bash
POST /api/v1/workflows/webhook/{webhook_key}

{
  "customer_id": "123"
}
```

### Trigger Voice Event

```bash
POST /api/v1/workflows/trigger/voice-event
Authorization: Bearer {token}

{
  "event_type": "call_completed",
  "call_id": "call_123",
  "duration": 180
}
```

### Trigger Integration Event

```bash
POST /api/v1/workflows/trigger/integration-event
Authorization: Bearer {token}

{
  "integration_type": "salesforce",
  "event_type": "lead.created",
  "payload": {}
}
```

---

## Trigger Data Access

Access trigger data in workflow steps using `{{trigger.*}}`:

### Voice Event
```
{{trigger.call_id}}
{{trigger.duration}}
{{trigger.sentiment.label}}
{{trigger.transcript}}
```

### Webhook
```
{{trigger.payload.customer_id}}
{{trigger.payload.order_id}}
```

### Scheduled
```
{{trigger.schedule_type}}
{{trigger.triggered_at}}
```

### Integration Event
```
{{trigger.integration_type}}
{{trigger.payload.LeadId}}
```

---

## Validation

```python
from app.services.workflows import TriggerValidator

# Validate configuration
TriggerValidator.validate_trigger_config(
    trigger_type=TriggerType.SCHEDULE,
    config={
        "schedule_type": "cron",
        "cron_expression": "0 9 * * *"
    }
)
```

**Validates:**
- Required fields
- Cron syntax
- Webhook key length (min 16)
- Future dates for scheduled_at
- Valid integration types

---

## Testing

```python
from app.services.workflows import get_trigger_manager

manager = get_trigger_manager(db)

# Test trigger
result = await manager.test_trigger(
    workflow_id="workflow_uuid",
    test_data={
        "call_id": "test",
        "duration": 120,
        "sentiment": {"label": "positive"}
    }
)

print(result["would_trigger"])  # True/False
```

---

## Complete Examples

### Post-Call Follow-up

```json
{
  "name": "Support Call Follow-up",
  "trigger_type": "call_completed",
  "trigger_config": {
    "filters": {
      "intent": "support",
      "duration_min": 120
    }
  },
  "workflow_steps": [...]
}
```

### Daily Report

```json
{
  "name": "Daily Analytics",
  "trigger_type": "schedule",
  "trigger_config": {
    "schedule_type": "cron",
    "cron_expression": "0 9 * * *"
  },
  "workflow_steps": [...]
}
```

### External Webhook

```json
{
  "name": "Order Processing",
  "trigger_type": "webhook",
  "trigger_config": {
    "webhook_key": "secure-key-123456789012"
  },
  "workflow_steps": [...]
}
```

### CRM Integration

```json
{
  "name": "New Lead Follow-up",
  "trigger_type": "integration_event",
  "trigger_config": {
    "integration_type": "salesforce",
    "event_type": "lead.created",
    "filters": {
      "LeadSource": "Website"
    }
  },
  "workflow_steps": [...]
}
```

---

## Best Practices

### 1. Use Specific Filters
```json
// Good
{"filters": {"duration_min": 60, "sentiment": "negative"}}

// Bad
{"filters": {}}
```

### 2. Secure Webhook Keys
```python
import secrets
webhook_key = secrets.token_urlsafe(32)
```

### 3. Test Before Activating
```bash
POST /api/v1/workflows/{id}/test-trigger
{"call_id": "test", "duration": 100}
```

### 4. Choose Right Schedule Type
- Complex schedules → Cron
- Simple periodic → Interval
- One-time future → One-time

### 5. Monitor Performance
- Track trigger rate
- Monitor match rate
- Review execution success

---

## Troubleshooting

### Trigger Not Firing
1. Check `is_active: true`
2. Verify filters with test endpoint
3. Review logs
4. Validate configuration

### Webhook 404
1. Verify webhook key
2. Check URL format
3. Ensure workflow is active

### Schedule Not Running
1. Verify cron expression
2. Check scheduler is started
3. Review `last_executed_at`

---

## Code Snippets

### Process Event
```python
from app.services.workflows import get_trigger_manager

manager = get_trigger_manager(db)
executions = await manager.process_event(
    event_type=TriggerType.CALL_COMPLETED,
    event_data={"call_id": "123", "duration": 180}
)
```

### Start Scheduler
```python
from app.services.workflows import get_scheduler

scheduler = get_scheduler()
await scheduler.start()
```

### Generate Webhook Key
```python
import secrets
key = secrets.token_urlsafe(32)
```

---

## Resources

- **Full Guide**: [WORKFLOW_TRIGGERS_GUIDE.md](WORKFLOW_TRIGGERS_GUIDE.md)
- **Summary**: [WORKFLOW_TRIGGERS_SUMMARY.md](WORKFLOW_TRIGGERS_SUMMARY.md)
- **Workflow Guide**: [WORKFLOW_SYSTEM_GUIDE.md](WORKFLOW_SYSTEM_GUIDE.md)
