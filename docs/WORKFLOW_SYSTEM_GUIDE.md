# Workflow Automation System - Complete Guide

## Overview

The Voicecon Workflow System enables powerful automation by connecting voice calls, integrations, and business logic through a visual workflow builder. Create sophisticated automation workflows that respond to triggers, execute actions, make decisions, and transform data - all without writing code.

## Table of Contents

1. [Architecture](#architecture)
2. [Workflow Components](#workflow-components)
3. [Creating Workflows](#creating-workflows)
4. [Step Types](#step-types)
5. [Variable Interpolation](#variable-interpolation)
6. [API Reference](#api-reference)
7. [Examples](#examples)
8. [Best Practices](#best-practices)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Workflow System Architecture               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                          │
│  │   Triggers   │                                          │
│  │              │                                          │
│  │ - Manual     │                                          │
│  │ - Schedule   │                                          │
│  │ - Webhook    │                                          │
│  │ - Call Event │                                          │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────┐                                      │
│  │ Workflow Engine  │                                      │
│  │                  │                                      │
│  │ - Load Config    │                                      │
│  │ - Init Context   │                                      │
│  │ - Execute Steps  │                                      │
│  │ - Handle Errors  │                                      │
│  │ - Log Execution  │                                      │
│  └──────┬───────────┘                                      │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────┐                  │
│  │         Step Handlers               │                  │
│  │  ┌────────────┐  ┌──────────────┐  │                  │
│  │  │   Action   │  │  Condition   │  │                  │
│  │  │            │  │              │  │                  │
│  │  │ Call APIs  │  │ If/Else      │  │                  │
│  │  └────────────┘  └──────────────┘  │                  │
│  │  ┌────────────┐  ┌──────────────┐  │                  │
│  │  │    Loop    │  │  Transform   │  │                  │
│  │  │            │  │              │  │                  │
│  │  │ Iterate    │  │ Map Data     │  │                  │
│  │  └────────────┘  └──────────────┘  │                  │
│  │  ┌────────────┐                    │                  │
│  │  │   Delay    │                    │                  │
│  │  │            │                    │                  │
│  │  │ Wait       │                    │                  │
│  │  └────────────┘                    │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Components

### 1. Triggers

Triggers define when a workflow should execute.

#### Trigger Types

**Manual**
- Triggered manually via API call
- Useful for testing and on-demand execution

**Schedule**
- Executes on a cron schedule
- Example: "0 9 * * *" (daily at 9 AM)

**Webhook**
- Triggered by external HTTP requests
- Auto-generates secure webhook URL

**Call Completed**
- Triggers when a call ends
- Access call data in workflow

**Call Started**
- Triggers when a call begins
- Access caller information

**Integration Event**
- Triggers on integration events
- Example: New Salesforce lead

### 2. Steps

Steps are the building blocks of workflows. Each step performs a specific action or makes a decision.

### 3. Context

Workflow context stores variables and data that can be accessed across steps:
- `trigger.*` - Trigger data
- `steps.*` - Results from previous steps
- Custom variables set during execution

---

## Creating Workflows

### Basic Workflow Structure

```json
{
  "name": "Lead Follow-up Automation",
  "description": "Send email and create calendar event for new leads",
  "trigger_type": "call_completed",
  "trigger_config": {
    "duration_min": 60
  },
  "workflow_steps": [
    {
      "id": "step1",
      "name": "Create Salesforce Lead",
      "type": "action",
      "config": {
        "connection_id": "salesforce-connection-id",
        "action": "create_lead",
        "parameters": {
          "first_name": "{{trigger.caller_name}}",
          "last_name": "{{trigger.caller_last}}",
          "company": "{{trigger.company}}",
          "phone": "{{trigger.caller_phone}}"
        }
      }
    },
    {
      "id": "step2",
      "name": "Send Welcome Email",
      "type": "action",
      "config": {
        "connection_id": "sendgrid-connection-id",
        "action": "send_template_email",
        "parameters": {
          "to_email": "{{trigger.caller_email}}",
          "from_email": "sales@company.com",
          "template_id": "welcome-template",
          "dynamic_template_data": {
            "name": "{{trigger.caller_name}}",
            "company": "{{trigger.company}}"
          }
        }
      }
    },
    {
      "id": "step3",
      "name": "Schedule Follow-up",
      "type": "action",
      "config": {
        "connection_id": "google-calendar-id",
        "action": "create_event",
        "parameters": {
          "summary": "Follow up with {{trigger.caller_name}}",
          "start_time": "{{trigger.tomorrow_9am}}",
          "end_time": "{{trigger.tomorrow_930am}}",
          "attendees": ["sales@company.com"]
        }
      }
    }
  ],
  "is_active": true,
  "execution_mode": "async",
  "error_handling": "continue",
  "max_retries": 3,
  "retry_delay": 60
}
```

---

## Step Types

### 1. Action Step

Executes an integration connector action.

```json
{
  "id": "create_contact",
  "name": "Create HubSpot Contact",
  "type": "action",
  "config": {
    "connection_id": "hubspot-connection-uuid",
    "action": "create_contact",
    "parameters": {
      "email": "{{trigger.email}}",
      "first_name": "{{trigger.first_name}}",
      "last_name": "{{trigger.last_name}}",
      "phone": "{{trigger.phone}}"
    },
    "retry_on_failure": true,
    "timeout_seconds": 30
  }
}
```

**Available Actions by Connector:**

**Salesforce:**
- `create_contact`, `update_contact`, `get_contact`, `delete_contact`
- `create_lead`, `update_lead`
- `create_opportunity`
- `query`, `search_contacts`, `search_leads`

**HubSpot:**
- `create_contact`, `update_contact`, `get_contact`, `delete_contact`
- `create_company`, `update_company`
- `create_deal`, `update_deal`
- `search_contacts`, `associate_objects`
- `batch_create_contacts`, `batch_update_contacts`

**SendGrid:**
- `send_email`, `send_template_email`
- `add_contact`, `delete_contact`, `search_contacts`
- `create_list`, `get_lists`, `add_contacts_to_list`
- `get_stats`, `get_bounces`

**Google Calendar:**
- `create_event`, `update_event`, `delete_event`, `get_event`
- `list_events`, `list_calendars`
- `check_availability`, `find_available_slots`
- `quick_add_event`

**Slack:**
- `send_message`, `send_direct_message`, `update_message`, `delete_message`
- `upload_file`
- `create_channel`, `invite_to_channel`, `list_channels`
- `get_user_info`, `list_users`
- `add_reaction`, `post_webhook`

**Stripe:**
- `create_customer`, `get_customer`, `update_customer`, `delete_customer`
- `create_payment_intent`, `confirm_payment_intent`, `cancel_payment_intent`
- `create_subscription`, `cancel_subscription`
- `create_refund`, `create_invoice`, `finalize_invoice`, `pay_invoice`
- `get_balance`, `list_charges`

### 2. Condition Step

Makes decisions based on data.

```json
{
  "id": "check_call_duration",
  "name": "Check if call was long enough",
  "type": "condition",
  "config": {
    "condition": "{{trigger.duration}} >= 60",
    "on_true": ["send_email", "create_lead"],
    "on_false": ["log_short_call"]
  }
}
```

**Supported Operators:**
- `==` - Equals
- `!=` - Not equals
- `<`, `>`, `<=`, `>=` - Comparison
- `contains` - String contains
- `in` - Value in list

**Examples:**
```
"{{trigger.status}} == completed"
"{{trigger.duration}} > 300"
"{{trigger.email}} contains @company.com"
"{{trigger.priority}} in urgent,high"
```

### 3. Loop Step

Iterates over a list of items.

```json
{
  "id": "process_leads",
  "name": "Process each lead",
  "type": "loop",
  "config": {
    "items": "{{trigger.leads}}",
    "steps": ["create_contact", "send_email"],
    "max_iterations": 100
  }
}
```

**Loop Variables:**
- `{{loop.item}}` - Current item
- `{{loop.index}}` - Current index (0-based)

### 4. Transform Step

Transforms and maps data.

```json
{
  "id": "prepare_data",
  "name": "Prepare contact data",
  "type": "transform",
  "config": {
    "transformations": {
      "full_name": "{{trigger.first_name}} {{trigger.last_name}}",
      "email_lower": "{{trigger.email}}.lower()",
      "company_upper": "{{trigger.company}}.upper()"
    }
  }
}
```

**Supported Transformations:**
- `.upper()` - Convert to uppercase
- `.lower()` - Convert to lowercase
- String concatenation with variables

### 5. Delay Step

Pauses execution for a specified duration.

```json
{
  "id": "wait",
  "name": "Wait 1 hour",
  "type": "delay",
  "config": {
    "delay_seconds": 3600
  }
}
```

---

## Variable Interpolation

### Syntax

Variables use double curly braces: `{{variable.path}}`

### Available Variables

**Trigger Data:**
```
{{trigger.call_id}}
{{trigger.duration}}
{{trigger.caller_name}}
{{trigger.caller_phone}}
{{trigger.status}}
{{trigger.transcript}}
{{trigger.sentiment}}
```

**Step Results:**
```
{{steps.step_id.result.field}}
{{steps.create_contact.result.id}}
{{steps.send_email.result.message_id}}
```

**Loop Variables:**
```
{{loop.item}}
{{loop.index}}
```

### Examples

```json
{
  "parameters": {
    "email": "{{trigger.email}}",
    "name": "{{trigger.first_name}} {{trigger.last_name}}",
    "contact_id": "{{steps.create_contact.result.id}}",
    "index": "Item {{loop.index}}"
  }
}
```

---

## API Reference

### Create Workflow

```bash
POST /api/v1/workflows
Content-Type: application/json

{
  "name": "Lead Automation",
  "description": "Automate lead follow-up",
  "trigger_type": "call_completed",
  "trigger_config": {},
  "workflow_steps": [...],
  "is_active": true
}
```

### List Workflows

```bash
GET /api/v1/workflows?is_active=true&page=1&page_size=50
```

### Get Workflow

```bash
GET /api/v1/workflows/{workflow_id}
```

### Update Workflow

```bash
PATCH /api/v1/workflows/{workflow_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "is_active": false
}
```

### Delete Workflow

```bash
DELETE /api/v1/workflows/{workflow_id}
```

### Execute Workflow

```bash
POST /api/v1/workflows/{workflow_id}/execute
Content-Type: application/json

{
  "trigger_data": {
    "caller_name": "John Doe",
    "caller_email": "john@example.com"
  },
  "wait_for_completion": false
}
```

### List Executions

```bash
GET /api/v1/workflows/{workflow_id}/executions?status=completed
```

### Get Execution

```bash
GET /api/v1/workflows/{workflow_id}/executions/{execution_id}
```

### Get Workflow Statistics

```bash
GET /api/v1/workflows/{workflow_id}/stats
```

---

## Examples

### Example 1: Call Follow-up Automation

**Scenario:** After a sales call, create a CRM lead, send a thank-you email, and schedule a follow-up.

```json
{
  "name": "Sales Call Follow-up",
  "trigger_type": "call_completed",
  "trigger_config": {
    "agent_id": "sales-agent-id",
    "duration_min": 120
  },
  "workflow_steps": [
    {
      "id": "create_lead",
      "name": "Create Salesforce Lead",
      "type": "action",
      "config": {
        "connection_id": "salesforce-id",
        "action": "create_lead",
        "parameters": {
          "first_name": "{{trigger.caller_name}}",
          "last_name": "{{trigger.caller_last}}",
          "company": "{{trigger.company}}",
          "phone": "{{trigger.caller_phone}}",
          "status": "New Lead",
          "description": "Call transcript: {{trigger.transcript}}"
        }
      }
    },
    {
      "id": "send_thank_you",
      "name": "Send Thank You Email",
      "type": "action",
      "config": {
        "connection_id": "sendgrid-id",
        "action": "send_template_email",
        "parameters": {
          "to_email": "{{trigger.caller_email}}",
          "from_email": "sales@company.com",
          "template_id": "thank-you-template",
          "dynamic_template_data": {
            "name": "{{trigger.caller_name}}",
            "rep_name": "{{trigger.agent_name}}"
          }
        }
      }
    },
    {
      "id": "schedule_follow_up",
      "name": "Schedule Follow-up Call",
      "type": "action",
      "config": {
        "connection_id": "google-calendar-id",
        "action": "create_event",
        "parameters": {
          "summary": "Follow up: {{trigger.caller_name}}",
          "start_time": "{{trigger.next_week_10am}}",
          "end_time": "{{trigger.next_week_1030am}}",
          "description": "Lead ID: {{steps.create_lead.result.id}}",
          "attendees": ["{{trigger.agent_email}}"]
        }
      }
    },
    {
      "id": "notify_team",
      "name": "Notify Sales Team",
      "type": "action",
      "config": {
        "connection_id": "slack-id",
        "action": "send_message",
        "parameters": {
          "channel": "#sales",
          "text": "New lead from call with {{trigger.caller_name}}",
          "blocks": [
            {
              "type": "section",
              "text": {
                "type": "mrkdwn",
                "text": "*New Sales Lead*\n{{trigger.caller_name}} from {{trigger.company}}"
              }
            },
            {
              "type": "section",
              "fields": [
                {"type": "mrkdwn", "text": "*Duration:*\n{{trigger.duration}}s"},
                {"type": "mrkdwn", "text": "*Sentiment:*\n{{trigger.sentiment}}"}
              ]
            }
          ]
        }
      }
    }
  ],
  "is_active": true,
  "error_handling": "continue",
  "max_retries": 3
}
```

### Example 2: Payment Processing Workflow

**Scenario:** When a payment succeeds, update CRM, send receipt, and upgrade subscription tier.

```json
{
  "name": "Payment Success Automation",
  "trigger_type": "webhook",
  "trigger_config": {},
  "workflow_steps": [
    {
      "id": "check_amount",
      "name": "Check if premium tier",
      "type": "condition",
      "config": {
        "condition": "{{trigger.amount}} >= 9999",
        "on_true": ["upgrade_to_premium"],
        "on_false": ["upgrade_to_basic"]
      }
    },
    {
      "id": "upgrade_to_premium",
      "name": "Update to Premium",
      "type": "action",
      "config": {
        "connection_id": "hubspot-id",
        "action": "update_contact",
        "parameters": {
          "contact_id": "{{trigger.contact_id}}",
          "properties": {
            "subscription_tier": "Premium",
            "subscription_status": "Active"
          }
        }
      }
    },
    {
      "id": "send_receipt",
      "name": "Send Receipt",
      "type": "action",
      "config": {
        "connection_id": "sendgrid-id",
        "action": "send_template_email",
        "parameters": {
          "to_email": "{{trigger.customer_email}}",
          "template_id": "receipt-template",
          "dynamic_template_data": {
            "amount": "{{trigger.amount}}",
            "date": "{{trigger.payment_date}}",
            "invoice_url": "{{trigger.invoice_url}}"
          }
        }
      }
    }
  ]
}
```

### Example 3: Meeting Scheduler

**Scenario:** When someone requests a demo, find an available slot and create a calendar event.

```json
{
  "name": "Demo Scheduler",
  "trigger_type": "webhook",
  "trigger_config": {},
  "workflow_steps": [
    {
      "id": "find_slots",
      "name": "Find Available Slots",
      "type": "action",
      "config": {
        "connection_id": "google-calendar-id",
        "action": "find_available_slots",
        "parameters": {
          "duration_minutes": 30,
          "search_start": "{{trigger.tomorrow_9am}}",
          "search_end": "{{trigger.tomorrow_5pm}}"
        }
      }
    },
    {
      "id": "create_event",
      "name": "Create Calendar Event",
      "type": "action",
      "config": {
        "connection_id": "google-calendar-id",
        "action": "create_event",
        "parameters": {
          "summary": "Demo: {{trigger.company_name}}",
          "start_time": "{{steps.find_slots.result.0.start}}",
          "end_time": "{{steps.find_slots.result.0.end}}",
          "attendees": ["{{trigger.email}}", "sales@company.com"],
          "location": "Zoom"
        }
      }
    },
    {
      "id": "create_deal",
      "name": "Create Deal in HubSpot",
      "type": "action",
      "config": {
        "connection_id": "hubspot-id",
        "action": "create_deal",
        "parameters": {
          "deal_name": "Demo: {{trigger.company_name}}",
          "pipeline": "sales",
          "deal_stage": "demo_scheduled",
          "close_date": "{{trigger.next_month}}"
        }
      }
    },
    {
      "id": "send_confirmation",
      "name": "Send Confirmation",
      "type": "action",
      "config": {
        "connection_id": "sendgrid-id",
        "action": "send_email",
        "parameters": {
          "to_email": "{{trigger.email}}",
          "subject": "Demo Scheduled",
          "html_content": "<p>Your demo is scheduled for {{steps.find_slots.result.0.start}}</p>"
        }
      }
    }
  ]
}
```

---

## Best Practices

### 1. Error Handling

**Use retry logic for flaky APIs:**
```json
{
  "max_retries": 3,
  "retry_delay": 60,
  "error_handling": "continue"
}
```

**Validate data before processing:**
```json
{
  "id": "validate",
  "type": "condition",
  "config": {
    "condition": "{{trigger.email}} contains @",
    "on_true": ["process_email"],
    "on_false": ["log_invalid_email"]
  }
}
```

### 2. Performance

**Use async execution for long workflows:**
```json
{
  "execution_mode": "async",
  "wait_for_completion": false
}
```

**Limit loop iterations:**
```json
{
  "type": "loop",
  "config": {
    "max_iterations": 100
  }
}
```

### 3. Security

**Validate webhook signatures**
**Use secure connection IDs**
**Don't log sensitive data**

### 4. Monitoring

**Check execution statistics:**
```bash
GET /api/v1/workflows/{id}/stats
```

**Monitor execution logs:**
```bash
GET /api/v1/workflows/{id}/executions?status=failed
```

### 5. Testing

**Test with manual trigger first:**
```json
{
  "trigger_type": "manual"
}
```

**Use small datasets in loops**
**Test error scenarios**

---

## Success Metrics

✅ **Powerful Engine**: Async execution with retry logic
✅ **6 Step Types**: Action, Condition, Loop, Transform, Delay
✅ **Variable Interpolation**: Context-aware variable system
✅ **6 Integrations**: Salesforce, HubSpot, SendGrid, Google Calendar, Slack, Stripe
✅ **Comprehensive API**: Full CRUD + execution + statistics
✅ **Production Ready**: Error handling, logging, monitoring

---

## Conclusion

The Voicecon Workflow System provides enterprise-grade automation capabilities with a simple, intuitive API. Build powerful automations that connect voice calls to your entire business ecosystem!

🚀 **Start automating today!**
