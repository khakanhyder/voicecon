# Template Marketplace Guide

Complete guide for using and managing templates in the Voicecon marketplace.

## Table of Contents

1. [Overview](#overview)
2. [Available Templates](#available-templates)
3. [Installation Guide](#installation-guide)
4. [Template Customization](#template-customization)
5. [Seeding Templates](#seeding-templates)
6. [Creating Custom Templates](#creating-custom-templates)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

The Voicecon Template Marketplace provides 15 pre-built templates (5 agents + 10 workflows) that you can install and customize for your business needs.

### Benefits

- **Faster Setup**: Get started in minutes, not hours
- **Best Practices**: Templates follow proven patterns
- **Customizable**: Adapt templates to your specific needs
- **Professional**: Created and maintained by Voicecon
- **Free**: All templates are available at no cost

## Available Templates

### Agent Templates (5)

#### 1. Customer Support Agent 🎧
**Best For**: Businesses providing customer support
- **Category**: Customer Support
- **Version**: 2.1.0
- **Features**:
  - 24/7 availability
  - FAQ handling
  - Issue escalation
  - Empathetic responses

**Use Cases**:
- After-hours support
- First-level triage
- Common inquiry handling

**Setup Time**: ~10 minutes

---

#### 2. Sales Qualification Agent 💼
**Best For**: B2B sales teams
- **Category**: Sales
- **Version**: 1.5.2
- **Features**:
  - BANT qualification
  - Meeting scheduling
  - CRM integration
  - Lead scoring

**Use Cases**:
- Inbound lead qualification
- Demo scheduling
- Lead prioritization

**Setup Time**: ~15 minutes

---

#### 3. Appointment Scheduler ��
**Best For**: Service businesses
- **Category**: Scheduling
- **Version**: 3.0.1
- **Features**:
  - Calendar integration
  - Availability checking
  - Confirmation/reminders
  - Rescheduling handling

**Use Cases**:
- Medical appointments
- Consultations
- Service bookings

**Setup Time**: ~10 minutes

---

#### 4. Order Status Agent 📦
**Best For**: E-commerce businesses
- **Category**: E-commerce
- **Version**: 2.0.3
- **Features**:
  - Order lookup
  - Tracking info
  - Return processing
  - Delivery estimates

**Use Cases**:
- Order inquiries
- Shipping updates
- Return requests

**Setup Time**: ~15 minutes

---

#### 5. Lead Capture Agent 🎯
**Best For**: Marketing teams
- **Category**: Sales
- **Version**: 2.2.1
- **Features**:
  - Contact collection
  - Interest qualification
  - CRM sync
  - Follow-up scheduling

**Use Cases**:
- Ad campaign leads
- Website inquiries
- Event follow-up

**Setup Time**: ~10 minutes

---

### Workflow Templates (10)

#### 1. Salesforce Lead Creation ☁️
Automatically create Salesforce leads from phone calls.

**Features**:
- Auto-create leads
- Field mapping
- Duplicate detection
- Lead routing

**Required Integration**: Salesforce
**Compatible Agents**: Sales Qualification, Lead Capture

---

#### 2. HubSpot Deal Update 🔄
Update HubSpot deals based on call outcomes.

**Features**:
- Stage progression
- Note attachment
- Property updates
- Task creation

**Required Integration**: HubSpot
**Compatible Agents**: Sales Qualification

---

#### 3. Google Calendar Booking 📅
Create calendar events from appointment bookings.

**Features**:
- Event creation
- Availability checking
- Email invites
- SMS reminders

**Required Integration**: Google Calendar
**Compatible Agents**: Appointment Scheduler

---

#### 4. Slack Notification 💬
Send real-time call notifications to Slack.

**Features**:
- Instant alerts
- Rich formatting
- Channel routing
- Action buttons

**Required Integration**: Slack
**Compatible Agents**: All agents

---

#### 5. Email Follow-up 📧
Send automated follow-up emails after calls.

**Features**:
- Custom templates
- Call summary inclusion
- Resource attachments
- Tracking analytics

**Required Integration**: SendGrid/Mailgun
**Compatible Agents**: All agents

---

#### 6. SMS Confirmation 📱
Send SMS confirmations and reminders.

**Features**:
- Instant delivery
- Two-way SMS
- Reminder scheduling
- Opt-out handling

**Required Integration**: Twilio
**Compatible Agents**: Appointment Scheduler

---

#### 7. Zendesk Ticket Creation 🎫
Create support tickets from calls automatically.

**Features**:
- Auto ticket creation
- Priority detection
- Transcript attachment
- Tag assignment

**Required Integration**: Zendesk
**Compatible Agents**: Customer Support

---

#### 8. Shopify Order Check 🛍️
Look up Shopify order status during calls.

**Features**:
- Order lookup
- Tracking retrieval
- Status updates
- Return initiation

**Required Integration**: Shopify
**Compatible Agents**: Order Status

---

#### 9. Stripe Payment Link 💳
Generate and send Stripe payment links.

**Features**:
- Secure link generation
- SMS/Email delivery
- Payment tracking
- Receipt automation

**Required Integration**: Stripe
**Compatible Agents**: Customer Support, Order Status

---

#### 10. Multi-step Lead Nurture 🌱
Automated multi-touch lead nurturing.

**Features**:
- Multi-channel sequences
- Behavior triggers
- Lead scoring
- A/B testing

**Required Integration**: HubSpot/Salesforce, SendGrid
**Compatible Agents**: Sales Qualification, Lead Capture

---

## Installation Guide

### Step 1: Browse Marketplace

1. Navigate to **Marketplace** in dashboard
2. Browse by category or search
3. Click template to view details

### Step 2: Review Template Details

Before installing, review:
- Description and features
- Required integrations
- Customization options
- Setup guide
- User reviews and ratings

### Step 3: Install Template

1. Click **Install** button
2. Review customization options
3. Fill in required fields:
   - Company name
   - Agent name
   - Business-specific details
4. Click **Complete Installation**

### Step 4: Post-Installation Setup

1. **Assign Resources**:
   - For agents: Assign phone number
   - For workflows: Configure triggers

2. **Connect Integrations**:
   - Navigate to Integrations page
   - Connect required services
   - Test connections

3. **Test Template**:
   - Make test call (agents)
   - Trigger test event (workflows)
   - Verify functionality

4. **Refine & Go Live**:
   - Adjust responses
   - Update configurations
   - Enable for production

## Template Customization

### Customizable Fields

Most templates support customization:

#### Agent Templates
- **Company Name**: Your business name
- **Agent Name**: Personality name
- **Voice**: Select voice type
- **Language**: Primary language
- **Temperature**: Response creativity (0.0-1.0)
- **Custom Prompts**: Modify system prompt

#### Workflow Templates
- **Field Mapping**: Map data to integrations
- **Conditions**: Set trigger conditions
- **Actions**: Add/remove workflow steps
- **Notifications**: Configure alerts

### Advanced Customization

For deeper customization:

1. **Clone Template**:
   - Install template
   - Go to agent/workflow editor
   - Modify as needed
   - Save as custom version

2. **Edit System Prompt**:
   ```
   Go to Agents → [Agent Name] → Edit
   Modify "System Prompt" section
   Add your specific guidelines
   Save changes
   ```

3. **Add Functions**:
   ```
   Go to Agents → [Agent Name] → Functions
   Add custom functions
   Configure API calls
   Test thoroughly
   ```

## Seeding Templates

To populate your database with all pre-built templates:

### Prerequisites

1. Database running and migrated:
   ```bash
   cd backend
   alembic upgrade head
   ```

2. Environment variables set:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/voicecon
   ```

### Run Seeder

```bash
cd backend
python -m scripts.seed_templates
```

### Expected Output

```
================================================================================
VOICECON TEMPLATE SEEDER
================================================================================

This script will seed the database with pre-built templates.
Existing templates will be skipped.

================================================================================
SEEDING AGENT TEMPLATES
================================================================================

✅ Created agent template: Customer Support Agent (customer-support-agent)
✅ Created agent template: Sales Qualification Agent (sales-qualification-agent)
✅ Created agent template: Appointment Scheduler (appointment-scheduler)
✅ Created agent template: Order Status Agent (order-status-agent)
✅ Created agent template: Lead Capture Agent (lead-capture-agent)

✅ Successfully seeded 5 agent templates!

================================================================================
SEEDING WORKFLOW TEMPLATES
================================================================================

✅ Created workflow template: Salesforce Lead Creation (salesforce-lead-creation)
✅ Created workflow template: HubSpot Deal Update (hubspot-deal-update)
...

✅ Successfully seeded 10 workflow templates!

================================================================================
SEEDING SUMMARY
================================================================================
✅ Agent Templates: 5
✅ Workflow Templates: 10
✅ Total Templates: 15
================================================================================

🎉 Template seeding completed successfully!
```

### Verify Installation

1. Navigate to marketplace: `http://localhost:3000/marketplace`
2. Verify all templates appear
3. Check template details
4. Test installation flow

## Creating Custom Templates

You can create and publish your own templates to the marketplace.

### Agent Template Structure

```python
{
    "name": "My Custom Agent",
    "slug": "my-custom-agent",
    "description": "Short description",
    "long_description": "Detailed description...",
    "category": "customer_support",  # or sales, scheduling, etc.
    "tags": ["tag1", "tag2"],
    "version": "1.0.0",
    "icon": "🤖",
    "author_name": "Your Company",
    "is_official": False,  # True only for Voicecon templates
    "is_featured": False,
    "is_free": True,
    "agent_config": {
        "name": "Agent Name",
        "voice_id": "en-US-Neural2-F",
        "language": "en-US",
        "temperature": 0.7,
        "max_tokens": 150,
    },
    "system_prompt": "Your system prompt with {{variables}}...",
    "first_message": "Hello! I'm {{agent_name}}...",
    "customizable_fields": [
        {
            "name": "field_name",
            "label": "Field Label",
            "type": "text",  # or number, select, etc.
            "required": True,
            "default": "default value",
            "description": "Help text"
        }
    ],
    "setup_guide": "# Markdown setup instructions...",
    "use_cases": [
        {
            "title": "Use Case Title",
            "description": "Description"
        }
    ],
    "required_integrations": ["integration-name"],
    "status": "published",
    "published_at": datetime.utcnow(),
}
```

### Workflow Template Structure

```python
{
    "name": "My Custom Workflow",
    "slug": "my-custom-workflow",
    "description": "Short description",
    "long_description": "Detailed description...",
    "category": "lead_capture",  # or notifications, data_sync
    "tags": ["tag1", "tag2"],
    "version": "1.0.0",
    "icon": "⚡",
    "workflow_definition": {
        "trigger": "call_completed",
        "conditions": [...],
        "actions": [...]
    },
    "trigger_config": {
        "event": "call.completed",
        "filters": {...}
    },
    "setup_guide": "# Markdown instructions...",
    "required_integrations": ["integration-name"],
    "compatible_agents": ["agent-slug-1", "agent-slug-2"],
    "status": "published",
    "published_at": datetime.utcnow(),
}
```

### Publishing Process

1. **Create Template**: Define structure above
2. **Add to Seed File**: Add to appropriate templates file
3. **Test Thoroughly**: Install and test all features
4. **Write Documentation**: Complete setup guide
5. **Submit for Review**: Contact Voicecon team
6. **Publication**: Approved templates go live

## Best Practices

### For Template Users

1. **Start with Official Templates**: They're tested and maintained
2. **Read Setup Guides**: Follow instructions carefully
3. **Test Before Production**: Always test in staging first
4. **Monitor Performance**: Track metrics and adjust
5. **Keep Updated**: Check for template updates regularly
6. **Provide Feedback**: Rate and review templates

### For Template Creators

1. **Clear Documentation**: Write thorough setup guides
2. **Sensible Defaults**: Provide good default values
3. **Error Handling**: Handle edge cases gracefully
4. **Versioning**: Use semantic versioning
5. **Testing**: Test all scenarios thoroughly
6. **Support**: Provide support channels
7. **Updates**: Keep templates current

### Integration Best Practices

1. **Test Connections**: Always verify integrations work
2. **Handle Failures**: Gracefully handle API failures
3. **Rate Limits**: Respect API rate limits
4. **Security**: Store credentials securely
5. **Logging**: Log important events
6. **Monitoring**: Monitor integration health

## Troubleshooting

### Template Installation Issues

**Problem**: Template fails to install

**Solutions**:
1. Check database connection
2. Verify you have permissions
3. Check for conflicting templates
4. Review error logs

---

**Problem**: Missing customization fields

**Solutions**:
1. Refresh page
2. Clear browser cache
3. Check template definition
4. Update template version

---

### Integration Issues

**Problem**: Integration not connecting

**Solutions**:
1. Verify API credentials
2. Check API key permissions
3. Test connection manually
4. Review integration docs

---

**Problem**: Workflow not triggering

**Solutions**:
1. Check trigger conditions
2. Verify event is firing
3. Review workflow logs
4. Test with manual trigger

---

### Performance Issues

**Problem**: Slow template responses

**Solutions**:
1. Review system prompt length
2. Reduce max_tokens if needed
3. Check API response times
4. Optimize function calls

---

## Support

### Getting Help

1. **Documentation**: Check this guide first
2. **Community**: Join Voicecon community forum
3. **Support**: Contact support@voicecon.ai
4. **GitHub**: Report issues on GitHub

### Contributing

Want to contribute templates?

1. Fork the repository
2. Create your template
3. Write documentation
4. Submit pull request
5. Await review

### Feedback

We value your feedback:
- Rate templates after using them
- Write reviews with specific feedback
- Report bugs and issues
- Suggest improvements
- Share success stories

---

**Last Updated**: January 2024
**Version**: 1.0.0
**Templates Available**: 15 (5 agents + 10 workflows)
