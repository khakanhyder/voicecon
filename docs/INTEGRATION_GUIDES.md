# Voicecon Integration Guides

**Complete step-by-step guides for connecting Voicecon with your favorite tools**

Version 1.0.0 | Last Updated: December 19, 2025

---

## Table of Contents

### CRM Integrations
1. [Salesforce](#salesforce-integration)
2. [HubSpot](#hubspot-integration)
3. [Pipedrive](#pipedrive-integration)
4. [Zoho CRM](#zoho-crm-integration)

### Communication Tools
5. [Slack](#slack-integration)
6. [Microsoft Teams](#microsoft-teams-integration)
7. [Discord](#discord-integration)

### Calendar & Scheduling
8. [Google Calendar](#google-calendar-integration)
9. [Calendly](#calendly-integration)
10. [Microsoft Outlook Calendar](#microsoft-outlook-integration)

### Marketing & Email
11. [Mailchimp](#mailchimp-integration)
12. [SendGrid](#sendgrid-integration)
13. [ActiveCampaign](#activecampaign-integration)

### Database & Storage
14. [Google Sheets](#google-sheets-integration)
15. [Airtable](#airtable-integration)

### Custom Integrations
16. [Webhook Integration](#webhook-integration)
17. [REST API Integration](#rest-api-integration)

---

## Salesforce Integration

### Overview

Connect Voicecon to Salesforce to automatically:
- Create and update Leads, Contacts, Accounts, Opportunities
- Log call activities and notes
- Update opportunity stages
- Sync customer data bidirectionally

**Authentication**: OAuth 2.0

**Supported Editions**:
- Salesforce Professional
- Salesforce Enterprise
- Salesforce Unlimited

---

### Prerequisites

Before connecting Salesforce:

1. **Salesforce Admin Access** - You need System Administrator or equivalent permissions
2. **Connected App** - Create a Connected App in Salesforce (we'll guide you)
3. **API Enabled** - Ensure API access is enabled for your org

---

### Step 1: Create Connected App in Salesforce

#### 1.1. Navigate to Setup

1. Log in to Salesforce
2. Click the gear icon (⚙️) → **Setup**
3. In Quick Find, search for **App Manager**
4. Click **App Manager**

#### 1.2. Create New Connected App

1. Click **New Connected App** button
2. Fill in Basic Information:
   - **Connected App Name**: `Voicecon Integration`
   - **API Name**: `Voicecon_Integration` (auto-filled)
   - **Contact Email**: Your email

#### 1.3. Enable OAuth Settings

1. Check **Enable OAuth Settings**
2. **Callback URL**: `https://app.voicecon.com/oauth/callback/salesforce`
3. **Selected OAuth Scopes**: Add these scopes:
   - `Access and manage your data (api)`
   - `Perform requests on your behalf at any time (refresh_token, offline_access)`
   - `Access your basic information (id, profile, email, address, phone)`

4. Click **Save**
5. Click **Continue**

#### 1.4. Retrieve Credentials

After saving, you'll see:
- **Consumer Key** (this is your Client ID)
- **Consumer Secret** (click to reveal)

**IMPORTANT**: Copy both values. You'll need them in Step 2.

---

### Step 2: Connect in Voicecon

#### 2.1. Navigate to Integrations

1. Log in to Voicecon
2. Go to **Integrations** in sidebar
3. Find **Salesforce** card
4. Click **Connect**

#### 2.2. Enter Salesforce Details

1. **Salesforce Domain**: Enter your domain
   - Example: `mycompany.salesforce.com`
   - For sandboxes: `mycompany--sandbox.sandbox.my.salesforce.com`

2. **Client ID**: Paste Consumer Key from Step 1.4
3. **Client Secret**: Paste Consumer Secret from Step 1.4

4. Click **Authorize**

#### 2.3. Grant Permissions

1. You'll be redirected to Salesforce login
2. Log in with your credentials
3. Review requested permissions
4. Click **Allow**
5. You'll be redirected back to Voicecon

**Success!** You should see "Salesforce Connected" ✅

---

### Step 3: Configure Data Mapping

Map Voicecon call data to Salesforce fields:

#### 3.1. Lead Mapping

Navigate to: **Integrations → Salesforce → Field Mapping → Leads**

| Voicecon Field | Salesforce Field | Notes |
|----------------|------------------|-------|
| `caller_first_name` | `FirstName` | Required |
| `caller_last_name` | `LastName` | Required |
| `caller_email` | `Email` | |
| `caller_phone` | `Phone` | |
| `caller_company` | `Company` | Required |
| `call_summary` | `Description` | |
| Fixed: "Voice Call" | `LeadSource` | |
| `detected_intent` | `Lead_Intent__c` | Custom field |
| `call_duration` | `Call_Duration__c` | Custom field |

**To add custom fields:**
1. Click **Add Custom Field**
2. Select Voicecon field
3. Enter Salesforce field API name
4. Click **Save**

#### 3.2. Activity Mapping

Map call activities:

| Voicecon Field | Salesforce Activity Field |
|----------------|---------------------------|
| `call_id` | `Subject` (prefix: "Call:") |
| `call_transcript` | `Description` |
| `call_duration` | `DurationInMinutes` |
| `call_start_time` | `ActivityDate` |
| Fixed: "Call" | `Type` |
| Fixed: "Completed" | `Status` |

---

### Step 4: Test the Integration

#### 4.1. Test Connection

1. In Voicecon, go to **Integrations → Salesforce**
2. Click **Test Connection**
3. Verify success message: "Connection successful. API Version: v58.0"

#### 4.2. Test Lead Creation

1. Click **Test Action** → **Create Lead**
2. Enter test data:
```json
{
  "FirstName": "John",
  "LastName": "Doe",
  "Company": "Test Company",
  "Email": "john@testcompany.com",
  "Phone": "+1234567890",
  "LeadSource": "Voice Call",
  "Description": "Test lead created via Voicecon integration"
}
```
3. Click **Run Test**
4. Check Salesforce to verify lead was created

---

### Step 5: Create Workflows

#### Example Workflow 1: Create Lead After Qualified Call

**Trigger**: Call Completed

**Conditions**:
- Call duration > 60 seconds
- Intent = "purchase_interest" OR "demo_request"

**Actions**:
1. **Salesforce: Create Lead**
   ```json
   {
     "FirstName": "{{caller_first_name}}",
     "LastName": "{{caller_last_name}}",
     "Company": "{{caller_company}}",
     "Email": "{{caller_email}}",
     "Phone": "{{caller_phone}}",
     "LeadSource": "Voice Call - {{agent_name}}",
     "Description": "{{call_summary}}",
     "Lead_Intent__c": "{{detected_intent}}",
     "Call_Duration__c": "{{call_duration}}"
   }
   ```

2. **Salesforce: Create Task**
   ```json
   {
     "Subject": "Follow up on voice call",
     "Description": "Lead called about {{detected_intent}}. Listen to call: {{call_recording_url}}",
     "Status": "Not Started",
     "Priority": "High",
     "ActivityDate": "{{tomorrow}}"
   }
   ```

#### Example Workflow 2: Update Opportunity Stage

**Trigger**: Call Completed

**Conditions**:
- Call tags contain "contract_discussion"
- Salesforce Opportunity exists for contact

**Actions**:
1. **Salesforce: Update Opportunity**
   ```json
   {
     "Id": "{{salesforce_opportunity_id}}",
     "StageName": "Negotiation/Review",
     "Next_Step__c": "Awaiting signed contract",
     "Description": "Contract discussed on call {{call_date}}. Recording: {{call_recording_url}}"
   }
   ```

---

### Common Use Cases

#### Use Case 1: Inbound Lead Capture

**Scenario**: Customer calls your support number expressing interest in your product.

**Workflow**:
1. Agent identifies purchase intent during call
2. Agent asks qualifying questions (captured in transcript)
3. On call completion → Create Lead in Salesforce
4. Assign to sales team based on territory
5. Create follow-up task for sales rep

#### Use Case 2: Customer Support Ticket Creation

**Scenario**: Customer calls with a technical issue.

**Workflow**:
1. Agent gathers issue details
2. On call completion → Create Case in Salesforce
3. Link Case to Contact (via phone number lookup)
4. Set Case Priority based on issue severity
5. Attach call recording and transcript to Case

#### Use Case 3: Appointment Scheduling

**Scenario**: Prospect wants to schedule a demo.

**Workflow**:
1. Agent checks calendar availability (via function)
2. Books demo appointment
3. Create Salesforce Event linked to Lead/Contact
4. Send calendar invitation
5. Create reminder task 24 hours before demo

---

### Troubleshooting

#### Error: "OAuth token expired"

**Cause**: Salesforce access token expired (typically after 2 hours)

**Solution**:
1. Voicecon automatically refreshes tokens
2. If issue persists, click **Reconnect** in Integrations page
3. Re-authorize the connection

#### Error: "Insufficient privileges"

**Cause**: Connected user doesn't have permission to create/edit records

**Solution**:
1. In Salesforce, verify user has:
   - Create/Edit permissions on Leads, Contacts, etc.
   - API Enabled permission
   - Connected App access
2. Check Profile permissions
3. Verify Permission Sets

#### Error: "Required field missing: Company"

**Cause**: Lead creation requires Company field

**Solution**:
1. Update field mapping to ensure Company is populated
2. Options:
   - Extract from conversation
   - Use default value: "Unknown"
   - Make field optional in Salesforce validation rules

#### Leads Not Syncing

**Troubleshooting Steps**:
1. Check workflow execution logs: **Workflows → [Workflow Name] → Execution History**
2. Verify integration status: **Integrations → Salesforce** (should show green checkmark)
3. Test connection: Click **Test Connection**
4. Review field mappings: Ensure all required fields are mapped
5. Check Salesforce validation rules: May be blocking creation

---

### Advanced Configuration

#### Custom Object Support

To create records on custom objects:

1. **Identify Object API Name**: In Salesforce Setup → Object Manager
   - Example: `Custom_Lead_Type__c`

2. **Create Custom Workflow Action**:
   - Integration: Salesforce
   - Action: Create Record
   - Object: Enter API name (`Custom_Lead_Type__c`)
   - Field Mapping: Map as needed

3. **Test with sample data**

#### Relationship Mapping

Link related records:

**Example: Link Contact to Account**
```json
{
  "FirstName": "{{caller_first_name}}",
  "LastName": "{{caller_last_name}}",
  "AccountId": "{{salesforce_account_id}}",
  "Email": "{{caller_email}}"
}
```

Use lookup functions to find AccountId:
1. Add function: **Salesforce Lookup Account**
2. Search by: Company Name
3. Return: Account ID

#### Bulk Operations

For high-volume operations:

1. Enable **Bulk API** in integration settings
2. Set batch size (default: 200 records)
3. Configure retry logic
4. Monitor bulk job status in Salesforce Setup → Bulk Data Load Jobs

---

## HubSpot Integration

### Overview

Connect Voicecon to HubSpot to:
- Create and update Contacts, Companies, Deals
- Log call activities in timeline
- Update deal stages automatically
- Sync contact properties

**Authentication**: OAuth 2.0

**Supported Plans**:
- HubSpot Starter
- HubSpot Professional
- HubSpot Enterprise

---

### Step 1: Connect HubSpot

#### 1.1. Navigate to Integrations

1. Log in to Voicecon
2. Go to **Integrations**
3. Find **HubSpot** card
4. Click **Connect**

#### 1.2. Authorize HubSpot

1. Click **Authorize with HubSpot**
2. Log in to HubSpot
3. Select your HubSpot account (if you have multiple)
4. Review permissions:
   - Read/Write Contacts
   - Read/Write Companies
   - Read/Write Deals
   - Read/Write Calls (Timeline)
5. Click **Authorize**

**Success!** You'll be redirected back to Voicecon.

---

### Step 2: Configure Field Mapping

#### 2.1. Contact Properties

| Voicecon Field | HubSpot Property | Type |
|----------------|------------------|------|
| `caller_first_name` | `firstname` | Text |
| `caller_last_name` | `lastname` | Text |
| `caller_email` | `email` | Email |
| `caller_phone` | `phone` | Phone |
| `caller_company` | `company` | Text |
| `detected_intent` | `call_intent` | Dropdown (custom) |
| `call_quality_score` | `last_call_quality` | Number (custom) |

#### 2.2. Deal Properties

| Voicecon Field | HubSpot Property |
|----------------|------------------|
| `detected_intent` | `dealname` |
| `call_summary` | `description` |
| Fixed: "Voice Call" | `leadsource` |
| `call_value_estimate` | `amount` |

---

### Step 3: Create Custom Properties (Optional)

To track call-specific data in HubSpot:

#### 3.1. Create Custom Contact Property

1. In HubSpot, go to **Settings** → **Properties** → **Contact Properties**
2. Click **Create Property**
3. Configure:
   - **Label**: "Last Call Intent"
   - **Field Type**: "Dropdown select"
   - **Options**:
     - Purchase Interest
     - Demo Request
     - Support Issue
     - General Inquiry
   - **Internal Name**: `last_call_intent`
4. Click **Create**

#### 3.2. Create Custom Call Property

1. Go to **Settings** → **Properties** → **Call Properties**
2. Click **Create Property**
3. Configure:
   - **Label**: "Call Duration (seconds)"
   - **Field Type**: "Number"
   - **Internal Name**: `call_duration_seconds`
4. Click **Create**

---

### Step 4: Create Workflows

#### Example Workflow 1: Create Contact & Deal

**Trigger**: Call Completed

**Conditions**:
- Call duration > 90 seconds
- Intent = "purchase_interest"

**Actions**:

1. **HubSpot: Create or Update Contact**
   ```json
   {
     "properties": {
       "email": "{{caller_email}}",
       "firstname": "{{caller_first_name}}",
       "lastname": "{{caller_last_name}}",
       "phone": "{{caller_phone}}",
       "last_call_intent": "{{detected_intent}}",
       "lifecyclestage": "lead"
     }
   }
   ```

2. **HubSpot: Create Deal**
   ```json
   {
     "properties": {
       "dealname": "Voice Call Lead - {{caller_name}}",
       "dealstage": "appointmentscheduled",
       "amount": "{{estimated_deal_value}}",
       "pipeline": "default",
       "leadsource": "Voice Call",
       "description": "{{call_summary}}"
     },
     "associations": [
       {
         "to": "{{hubspot_contact_id}}",
         "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
       }
     ]
   }
   ```

3. **HubSpot: Log Call Activity**
   ```json
   {
     "properties": {
       "hs_timestamp": "{{call_start_time}}",
       "hs_call_title": "Inbound Call - {{agent_name}}",
       "hs_call_body": "{{call_transcript}}",
       "hs_call_duration": "{{call_duration}}",
       "hs_call_recording_url": "{{call_recording_url}}",
       "hs_call_status": "COMPLETED"
     },
     "associations": [
       {
         "to": "{{hubspot_contact_id}}",
         "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 194}]
       }
     ]
   }
   ```

#### Example Workflow 2: Update Deal Stage

**Trigger**: Call Completed

**Conditions**:
- Call tags contain "demo_completed"
- HubSpot Deal exists

**Actions**:

1. **HubSpot: Update Deal**
   ```json
   {
     "id": "{{hubspot_deal_id}}",
     "properties": {
       "dealstage": "presentationscheduled",
       "notes_last_updated": "Demo completed via voice call",
       "closedate": "{{estimated_close_date}}"
     }
   }
   ```

2. **HubSpot: Create Task**
   ```json
   {
     "properties": {
       "hs_task_subject": "Follow up after demo call",
       "hs_task_body": "Review call recording and send proposal",
       "hs_task_status": "NOT_STARTED",
       "hs_task_priority": "HIGH",
       "hs_timestamp": "{{tomorrow}}"
     },
     "associations": [
       {
         "to": "{{hubspot_deal_id}}",
         "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]
       }
     ]
   }
   ```

---

### Common Use Cases

#### Use Case 1: Lead Qualification

**Scenario**: Qualify leads from calls and route to sales

**Implementation**:
1. Agent asks qualification questions
2. Extracts: Budget, Authority, Need, Timeline (BANT)
3. Creates Contact with custom properties:
   - `budget_range`
   - `decision_maker`
   - `timeline_to_purchase`
4. Sets lifecycle stage based on qualification
5. Assigns to sales rep based on territory

#### Use Case 2: Customer Onboarding

**Scenario**: Track onboarding calls in customer timeline

**Implementation**:
1. Create Contact (if not exists)
2. Log call in timeline
3. Update custom property: `onboarding_status`
4. Create task for next onboarding step
5. Send follow-up email via HubSpot workflow

---

### Troubleshooting

#### Error: "Contact already exists with this email"

**Solution**: Use "Create or Update" action instead of "Create"

**Configuration**:
```json
{
  "action": "upsert",
  "identifier": "email",
  "properties": {...}
}
```

#### Call Not Appearing in Timeline

**Checklist**:
1. Verify Call logging is enabled in integration settings
2. Check association is correctly set to Contact ID
3. Ensure `hs_timestamp` is in correct format (Unix timestamp in milliseconds)
4. HubSpot timeline may take 5-10 minutes to update

---

## Slack Integration

### Overview

Send real-time notifications to Slack:
- New qualified leads
- Missed calls
- High-priority support issues
- Daily call summaries

**Authentication**: OAuth 2.0

---

### Step 1: Connect Slack

1. Go to **Integrations** → **Slack**
2. Click **Add to Slack**
3. Select your Slack workspace
4. Choose channels Voicecon can access
5. Click **Allow**

---

### Step 2: Configure Notifications

#### Example Notification 1: New Qualified Lead

**Trigger**: Call Completed
**Condition**: Intent = "purchase_interest"
**Channel**: `#sales-leads`

**Message Template**:
```
🎯 *New Qualified Lead from Voice Call*

*Contact*: {{caller_name}}
*Email*: {{caller_email}}
*Phone*: {{caller_phone}}
*Company*: {{caller_company}}

*Call Summary*:
{{call_summary}}

*Intent*: {{detected_intent}}
*Duration*: {{call_duration_formatted}}

<{{call_recording_url}}|🎧 Listen to Call>
<{{crm_lead_url}}|📋 View in CRM>
```

**Result**:
![Slack notification example with formatted message and action buttons]

#### Example Notification 2: Missed Call Alert

**Trigger**: Call Failed
**Condition**: Status = "no_answer"
**Channel**: `#support-alerts`

**Message**:
```
⚠️ *Missed Call Alert*

*Caller*: {{caller_phone}}
*Time*: {{call_time}}
*Agent*: {{agent_name}}

*Action Required*: Call back customer
```

---

### Advanced Features

#### Interactive Buttons

Add action buttons to Slack messages:

```json
{
  "text": "New lead from call",
  "attachments": [
    {
      "text": "{{caller_name}} called about {{intent}}",
      "callback_id": "lead_action",
      "actions": [
        {
          "name": "claim",
          "text": "Claim Lead",
          "type": "button",
          "value": "{{lead_id}}"
        },
        {
          "name": "snooze",
          "text": "Snooze 1hr",
          "type": "button",
          "value": "{{lead_id}}"
        }
      ]
    }
  ]
}
```

#### Thread Replies

Post follow-up messages as thread replies:

1. Initial message: "New call from {{caller_name}}"
2. Thread reply 1: "CRM record created: {{crm_url}}"
3. Thread reply 2: "Follow-up email sent"

---

## Google Calendar Integration

### Overview

Enable agents to:
- Check calendar availability
- Schedule appointments
- Send meeting invitations
- Handle reschedule requests

**Authentication**: OAuth 2.0

---

### Step 1: Connect Google Calendar

1. Go to **Integrations** → **Google Calendar**
2. Click **Connect with Google**
3. Select Google account
4. Grant calendar permissions
5. Select calendars to sync

---

### Step 2: Configure Agent Function

Add "Schedule Appointment" function to your agent:

#### Function Definition

```json
{
  "name": "schedule_appointment",
  "description": "Schedule a meeting on the calendar",
  "parameters": {
    "type": "object",
    "properties": {
      "date": {
        "type": "string",
        "description": "Meeting date (YYYY-MM-DD)"
      },
      "time": {
        "type": "string",
        "description": "Meeting time (HH:MM)"
      },
      "duration": {
        "type": "number",
        "description": "Duration in minutes"
      },
      "attendee_email": {
        "type": "string",
        "description": "Attendee email address"
      },
      "meeting_type": {
        "type": "string",
        "enum": ["demo", "consultation", "follow-up"]
      }
    },
    "required": ["date", "time", "duration", "attendee_email"]
  }
}
```

#### Function Implementation

```python
def schedule_appointment(date, time, duration, attendee_email, meeting_type="demo"):
    """
    Schedule appointment on Google Calendar
    """
    # Check availability first
    is_available = check_calendar_availability(date, time, duration)

    if not is_available:
        # Find next available slot
        next_slot = find_next_available_slot(date, duration)
        return {
            "success": False,
            "message": f"That time is not available. Next available: {next_slot}"
        }

    # Create calendar event
    event = {
        "summary": f"{meeting_type.capitalize()} - {attendee_email}",
        "start": {
            "dateTime": f"{date}T{time}:00",
            "timeZone": "America/New_York"
        },
        "end": {
            "dateTime": calculate_end_time(date, time, duration),
            "timeZone": "America/New_York"
        },
        "attendees": [
            {"email": attendee_email}
        ],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30}
            ]
        }
    }

    # Insert event
    calendar_service.events().insert(
        calendarId='primary',
        body=event,
        sendUpdates='all'
    ).execute()

    return {
        "success": True,
        "message": f"Appointment scheduled for {date} at {time}",
        "event_id": event['id']
    }
```

---

### Step 3: Update Agent System Prompt

Add scheduling instructions to your agent:

```
When a customer wants to schedule an appointment:

1. Ask for their preferred date and time
2. Use the schedule_appointment function to check availability
3. If not available, suggest the next available slot
4. Confirm the appointment details
5. Get their email address for calendar invitation

Example conversation:
Customer: "I'd like to schedule a demo"
You: "I'd be happy to help! What day works best for you?"
Customer: "How about tomorrow at 2 PM?"
You: [Call schedule_appointment function]
You: "Great! I've scheduled a demo for tomorrow at 2 PM. You'll receive a calendar invitation at your email."
```

---

## Webhook Integration

### Overview

Connect any service with webhook support:
- Custom internal systems
- Third-party apps without native integration
- Legacy systems with APIs
- Microservices architecture

---

### Step 1: Create Webhook Integration

1. Go to **Integrations** → **Create Custom Integration**
2. Select **Webhook**
3. Configure:
   - **Name**: "My Custom System"
   - **Webhook URL**: `https://your-api.com/webhook/voicecon`
   - **Method**: POST
   - **Headers**: Add authentication headers
   - **Payload Format**: JSON

---

### Step 2: Configure Webhook Payload

#### Payload Template

```json
{
  "event": "call.completed",
  "timestamp": "{{call_end_time}}",
  "call": {
    "id": "{{call_id}}",
    "direction": "{{call_direction}}",
    "duration": {{call_duration}},
    "status": "{{call_status}}"
  },
  "caller": {
    "phone": "{{caller_phone}}",
    "name": "{{caller_name}}",
    "email": "{{caller_email}}"
  },
  "agent": {
    "id": "{{agent_id}}",
    "name": "{{agent_name}}"
  },
  "transcript": "{{call_transcript}}",
  "intent": "{{detected_intent}}",
  "recording_url": "{{call_recording_url}}"
}
```

---

### Step 3: Handle Webhook on Your Server

#### Example: Node.js Express Server

```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();
app.use(express.json());

// Verify webhook signature
function verifySignature(req) {
  const signature = req.headers['x-voicecon-signature'];
  const payload = JSON.stringify(req.body);
  const secret = process.env.VOICECON_WEBHOOK_SECRET;

  const computed = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(computed)
  );
}

// Webhook endpoint
app.post('/webhook/voicecon', (req, res) => {
  // Verify signature
  if (!verifySignature(req)) {
    return res.status(401).send('Invalid signature');
  }

  const { event, call, caller, agent } = req.body;

  // Process event
  switch (event) {
    case 'call.completed':
      handleCallCompleted(call, caller, agent);
      break;

    case 'call.failed':
      handleCallFailed(call);
      break;

    default:
      console.log(`Unknown event: ${event}`);
  }

  res.status(200).send('OK');
});

function handleCallCompleted(call, caller, agent) {
  console.log(`Call ${call.id} completed`);

  // Your custom logic here
  // - Store in database
  // - Send notifications
  // - Trigger workflows
  // - Update CRM
}

app.listen(3000, () => {
  console.log('Webhook server running on port 3000');
});
```

#### Example: Python Flask Server

```python
from flask import Flask, request, jsonify
import hmac
import hashlib
import os

app = Flask(__name__)

def verify_signature(request):
    """Verify webhook signature"""
    signature = request.headers.get('X-Voicecon-Signature')
    payload = request.get_data()
    secret = os.environ['VOICECON_WEBHOOK_SECRET'].encode()

    computed = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, computed)

@app.route('/webhook/voicecon', methods=['POST'])
def voicecon_webhook():
    # Verify signature
    if not verify_signature(request):
        return jsonify({'error': 'Invalid signature'}), 401

    data = request.get_json()
    event = data['event']

    # Process event
    if event == 'call.completed':
        handle_call_completed(data)
    elif event == 'call.failed':
        handle_call_failed(data)

    return jsonify({'status': 'success'}), 200

def handle_call_completed(data):
    call = data['call']
    caller = data['caller']

    # Your custom logic
    print(f"Call {call['id']} completed with {caller['name']}")

    # Examples:
    # - Insert into database
    # - Send to message queue
    # - Trigger automation
    # - Update analytics

if __name__ == '__main__':
    app.run(port=3000)
```

---

### Security Best Practices

#### 1. Always Verify Signatures

**Never trust webhook data without verification**:
- Use HMAC-SHA256 signature verification
- Compare signatures using constant-time comparison
- Reject requests with invalid signatures

#### 2. Use HTTPS Only

- Configure webhook URL with `https://`
- Use valid SSL certificate
- Reject non-HTTPS requests

#### 3. Implement Idempotency

Handle duplicate webhook deliveries:

```python
import redis

redis_client = redis.Redis()

@app.route('/webhook/voicecon', methods=['POST'])
def webhook():
    data = request.get_json()
    event_id = data['call']['id']

    # Check if already processed
    if redis_client.exists(f'processed:{event_id}'):
        return jsonify({'status': 'already processed'}), 200

    # Process event
    handle_event(data)

    # Mark as processed (expire after 24 hours)
    redis_client.setex(f'processed:{event_id}', 86400, '1')

    return jsonify({'status': 'success'}), 200
```

#### 4. Rate Limiting

Protect your webhook endpoint:

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.headers.get('X-Voicecon-Signature'))

@app.route('/webhook/voicecon', methods=['POST'])
@limiter.limit("100 per minute")
def webhook():
    # Handle webhook
    pass
```

---

## Best Practices Across All Integrations

### 1. Error Handling

Always implement retry logic:

```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
def create_crm_record(data):
    try:
        response = requests.post(crm_api_url, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log error
        logger.error(f"CRM API error: {e}")
        # Re-raise to trigger retry
        raise
```

### 2. Logging and Monitoring

Track integration performance:

**Key Metrics to Monitor**:
- Success rate
- Response time
- Error rate
- Retry attempts
- Data throughput

**Implementation**:
```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def log_integration_call(integration, action, success, duration_ms, error=None):
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "integration": integration,
        "action": action,
        "success": success,
        "duration_ms": duration_ms,
        "error": str(error) if error else None
    }

    if success:
        logger.info(f"Integration call succeeded", extra=log_data)
    else:
        logger.error(f"Integration call failed", extra=log_data)
```

### 3. Data Validation

Validate before sending to integrations:

```python
from pydantic import BaseModel, validator, EmailStr

class CRMContact(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    company: str

    @validator('phone')
    def validate_phone(cls, v):
        # Ensure E.164 format
        if not v.startswith('+'):
            raise ValueError('Phone must be in E.164 format')
        return v

    @validator('company')
    def validate_company(cls, v):
        if len(v) < 2:
            raise ValueError('Company name too short')
        return v

# Usage
try:
    contact = CRMContact(
        first_name=caller_first_name,
        last_name=caller_last_name,
        email=caller_email,
        phone=caller_phone,
        company=caller_company
    )
    create_crm_contact(contact.dict())
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
```

### 4. Testing Integrations

Test before production:

**Test Checklist**:
- ✅ Test with sample data
- ✅ Verify field mapping
- ✅ Test error scenarios
- ✅ Verify authentication refresh
- ✅ Test rate limiting
- ✅ Validate data in target system

**Use Test Mode**:
1. Enable test mode in integration settings
2. Test data is tagged as "test"
3. Can be easily deleted
4. No impact on production

---

## Integration Templates

### Template: Lead Capture and Nurture

**Integrations Used**:
- Salesforce (CRM)
- SendGrid (Email)
- Slack (Notifications)

**Workflow**:
1. Call completed with purchase intent
2. Create Lead in Salesforce
3. Send welcome email via SendGrid
4. Notify sales team in Slack
5. Schedule follow-up task

**ROI**: 45% increase in lead response time

---

### Template: Customer Support Automation

**Integrations Used**:
- HubSpot (CRM)
- Slack (Notifications)
- Google Sheets (Reporting)

**Workflow**:
1. Support call completed
2. Create ticket in HubSpot
3. Alert support team in Slack
4. Log call metrics in Google Sheets
5. Send CSAT survey email

**ROI**: 60% reduction in ticket response time

---

### Template: Event Registration

**Integrations Used**:
- Google Calendar (Scheduling)
- Mailchimp (Email Marketing)
- Airtable (Database)

**Workflow**:
1. Caller wants to register for event
2. Check event capacity in Airtable
3. Register attendee
4. Add to Google Calendar
5. Add to Mailchimp list for event reminders
6. Send confirmation email

**ROI**: 3x increase in event registrations

---

## Support and Resources

### Documentation
- API Reference: https://docs.voicecon.com/integrations
- Video Tutorials: https://learn.voicecon.com/integrations
- Code Examples: https://github.com/voicecon/integration-examples

### Getting Help
- Email: integrations@voicecon.com
- Chat: In-app support widget
- Discord: https://discord.gg/voicecon

### Request New Integration
Can't find the integration you need?
1. Go to **Integrations** → **Request Integration**
2. Describe your use case
3. We prioritize based on demand

---

*Last Updated: December 19, 2025*
*Version: 1.0.0*
