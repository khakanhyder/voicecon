"""
Pre-built workflow templates for the marketplace.
"""

from datetime import datetime
from decimal import Decimal

# Workflow Templates Data
WORKFLOW_TEMPLATES = [
    {
        "name": "Salesforce Lead Creation",
        "slug": "salesforce-lead-creation",
        "description": "Automatically create leads in Salesforce from calls",
        "long_description": """
Automatically capture lead information from phone calls and create new leads in Salesforce.
Maps call data to Salesforce fields and assigns leads based on your routing rules.

Features:
- Automatic lead creation from call transcripts
- Custom field mapping
- Lead assignment rules
- Duplicate detection
- Lead source tracking
        """.strip(),
        "category": "lead_capture",
        "tags": ["salesforce", "crm", "leads", "sales"],
        "version": "2.0.0",
        "icon": "☁️",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": True,
        "is_free": True,
        "workflow_definition": {
            "trigger": "call_completed",
            "conditions": [
                {
                    "type": "contains_intent",
                    "value": "lead_information"
                }
            ],
            "actions": [
                {
                    "type": "extract_data",
                    "fields": ["name", "email", "phone", "company", "interest"]
                },
                {
                    "type": "salesforce_create_lead",
                    "mapping": {
                        "FirstName": "{{name.first}}",
                        "LastName": "{{name.last}}",
                        "Email": "{{email}}",
                        "Phone": "{{phone}}",
                        "Company": "{{company}}",
                        "LeadSource": "Voice Call",
                        "Description": "{{call.transcript}}"
                    }
                },
                {
                    "type": "notify",
                    "channel": "email",
                    "message": "New lead created: {{lead.name}}"
                }
            ]
        },
        "trigger_config": {
            "event": "call.completed",
            "filters": {
                "min_duration": 30,
                "must_contain_keywords": ["interested", "information", "pricing"]
            }
        },
        "setup_guide": """
# Salesforce Lead Creation Workflow Setup

## Prerequisites
- Salesforce account with API access
- Salesforce connected app credentials
- Lead creation permissions

## Setup Steps

1. **Connect Salesforce**
   - Go to Integrations → Salesforce
   - Click "Connect Salesforce"
   - Authorize Voicecon app
   - Test connection

2. **Install Workflow Template**
   - Navigate to Marketplace
   - Find "Salesforce Lead Creation"
   - Click Install

3. **Configure Field Mapping**
   - Map call data to Salesforce fields
   - Set default values for required fields
   - Configure lead source tracking

4. **Set Up Lead Assignment**
   - Choose assignment method:
     - Default owner
     - Round-robin
     - Territory rules
     - Salesforce assignment rules

5. **Enable Duplicate Detection**
   - Configure matching rules
   - Set duplicate handling (update/skip/create)

6. **Test the Workflow**
   - Make a test call
   - Verify lead creation in Salesforce
   - Check field mapping accuracy

## Field Mapping Options
- First Name → FirstName (required)
- Last Name → LastName (required)
- Email → Email
- Phone → Phone
- Company → Company (required for B2B)
- Lead Source → LeadSource
- Call Transcript → Description
- Custom Fields → Map as needed

## Best Practices
- Review lead quality regularly
- Update field mappings based on feedback
- Set up lead scoring rules
- Configure email alerts for new leads
        """.strip(),
        "use_cases": [
            {
                "title": "Inbound Lead Capture",
                "description": "Automatically create leads from inbound calls"
            },
            {
                "title": "Lead Enrichment",
                "description": "Enhance existing leads with call data"
            }
        ],
        "required_integrations": ["salesforce"],
        "compatible_agents": ["sales-qualification-agent", "lead-capture-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "HubSpot Deal Update",
        "slug": "hubspot-deal-update",
        "description": "Update deal stages in HubSpot based on call outcomes",
        "long_description": """
Automatically move deals through your HubSpot pipeline based on call conversations and outcomes.
Adds notes, updates properties, and keeps your CRM always up-to-date.

Features:
- Automatic deal stage progression
- Call notes attached to deals
- Property updates based on conversation
- Activity logging
- Next action setting
        """.strip(),
        "category": "data_sync",
        "tags": ["hubspot", "crm", "sales", "pipeline"],
        "version": "1.8.5",
        "icon": "🔄",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": True,
        "is_free": True,
        "workflow_definition": {
            "trigger": "call_completed",
            "conditions": [
                {
                    "type": "contact_has_deal",
                    "value": True
                }
            ],
            "actions": [
                {
                    "type": "hubspot_find_deal",
                    "by": "contact_email"
                },
                {
                    "type": "hubspot_update_deal",
                    "updates": {
                        "dealstage": "{{determined_stage}}",
                        "last_contact_date": "{{call.date}}",
                        "notes_last_updated": "{{call.date}}"
                    }
                },
                {
                    "type": "hubspot_add_note",
                    "content": "Call Summary: {{call.summary}}\\n\\nKey Points: {{call.key_points}}"
                },
                {
                    "type": "hubspot_create_task",
                    "task": {
                        "title": "Follow up on {{call.date}}",
                        "due_date": "{{next_business_day}}",
                        "description": "Next steps: {{call.next_actions}}"
                    }
                }
            ]
        },
        "trigger_config": {
            "event": "call.completed",
            "filters": {
                "has_hubspot_contact": True
            }
        },
        "setup_guide": """
# HubSpot Deal Update Workflow Setup

## Prerequisites
- HubSpot Sales Hub (Starter or higher)
- Deal pipeline configured
- HubSpot API key

## Setup Steps

1. **Connect HubSpot**
   - Go to Integrations → HubSpot
   - Enter API key or OAuth connect
   - Grant required permissions
   - Test connection

2. **Install Workflow**
   - Install from Marketplace
   - Select target pipeline

3. **Configure Stage Mapping**
   - Map call outcomes to deal stages:
     - Interested → Qualified
     - Needs more info → Presentation Scheduled
     - Ready to buy → Proposal Sent
     - Not interested → Closed Lost

4. **Set Up Note Templates**
   - Customize call summary format
   - Define key information to capture
   - Set note visibility

5. **Configure Task Creation**
   - Set default task type
   - Configure due date rules
   - Assign task owners

6. **Test the Workflow**
   - Make a test call with deal contact
   - Verify deal stage update
   - Check note attachment
   - Confirm task creation

## Stage Progression Rules
Define rules for automatic stage changes:
- Demo completed → "Proposal Sent"
- Price accepted → "Contract Sent"
- Contract signed → "Closed Won"
- Not interested → "Closed Lost"

## Best Practices
- Review stage changes weekly
- Keep notes concise and actionable
- Set realistic follow-up dates
- Use deal properties for automation
- Track conversion rates by stage
        """.strip(),
        "use_cases": [
            {
                "title": "Sales Pipeline Management",
                "description": "Keep deals moving through pipeline automatically"
            },
            {
                "title": "Call Documentation",
                "description": "Ensure every call is logged and summarized"
            }
        ],
        "required_integrations": ["hubspot"],
        "compatible_agents": ["sales-qualification-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Google Calendar Booking",
        "slug": "google-calendar-booking",
        "description": "Create calendar events from appointment bookings",
        "long_description": """
Automatically create Google Calendar events when appointments are booked via phone.
Sends invites, sets reminders, and handles rescheduling seamlessly.

Features:
- Automatic event creation
- Calendar availability checking
- Email invitations
- SMS reminders
- Timezone handling
- Reschedule and cancel support
        """.strip(),
        "category": "notifications",
        "tags": ["calendar", "scheduling", "google", "appointments"],
        "version": "3.1.0",
        "icon": "📅",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "intent_detected",
            "conditions": [
                {
                    "type": "intent",
                    "value": "book_appointment"
                }
            ],
            "actions": [
                {
                    "type": "extract_datetime",
                    "field": "appointment_time"
                },
                {
                    "type": "check_availability",
                    "calendar_id": "{{calendar_id}}",
                    "duration_minutes": "{{appointment_duration}}"
                },
                {
                    "type": "create_calendar_event",
                    "calendar": "google",
                    "event": {
                        "summary": "{{appointment_type}} with {{customer_name}}",
                        "description": "{{appointment_notes}}",
                        "start": "{{appointment_time}}",
                        "duration": "{{appointment_duration}}",
                        "attendees": ["{{customer_email}}"],
                        "reminders": [
                            {"method": "email", "minutes": 1440},
                            {"method": "sms", "minutes": 60}
                        ]
                    }
                },
                {
                    "type": "send_confirmation",
                    "channel": "sms",
                    "message": "Your appointment is confirmed for {{formatted_time}}. You'll receive a reminder 1 hour before."
                }
            ]
        },
        "trigger_config": {
            "event": "intent.detected",
            "intent_name": "book_appointment"
        },
        "setup_guide": """
# Google Calendar Booking Workflow Setup

## Prerequisites
- Google Workspace or personal Google account
- Calendar API enabled
- Service account or OAuth credentials

## Setup Steps

1. **Connect Google Calendar**
   - Go to Integrations → Google
   - Click "Connect Google Calendar"
   - Authorize access
   - Select default calendar

2. **Install Workflow**
   - Install from Marketplace
   - Configure appointment types

3. **Set Availability Rules**
   - Define business hours
   - Set buffer time between appointments
   - Configure blackout dates

4. **Configure Appointment Types**
   - Define each appointment type:
     - Name
     - Duration
     - Description
     - Required information

5. **Set Up Reminders**
   - Email reminder (24 hours)
   - SMS reminder (1 hour)
   - Custom reminder messages

6. **Test Booking Flow**
   - Book test appointment
   - Verify calendar event creation
   - Check reminder delivery
   - Test rescheduling

## Availability Configuration
Set when appointments can be booked:
- Monday-Friday: 9 AM - 5 PM
- Buffer time: 15 minutes
- Min advance notice: 2 hours
- Max advance booking: 30 days

## Best Practices
- Keep calendar always up-to-date
- Set realistic buffer times
- Send confirmation immediately
- Enable automatic reminders
- Handle timezone differences
- Provide easy rescheduling options
        """.strip(),
        "use_cases": [
            {
                "title": "Medical Appointments",
                "description": "Schedule and confirm patient appointments"
            },
            {
                "title": "Consultations",
                "description": "Book professional service consultations"
            },
            {
                "title": "Sales Demos",
                "description": "Schedule product demonstrations"
            }
        ],
        "required_integrations": ["google-calendar"],
        "compatible_agents": ["appointment-scheduler"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Slack Notification",
        "slug": "slack-notification",
        "description": "Send real-time call notifications to Slack",
        "long_description": """
Get instant Slack notifications for important calls, leads, and customer interactions.
Customize notifications by type, urgency, and team channel.

Features:
- Real-time call alerts
- Customizable notification format
- Team-specific channels
- Priority routing
- Rich message formatting
- Action buttons
        """.strip(),
        "category": "notifications",
        "tags": ["slack", "notifications", "alerts", "team"],
        "version": "2.5.0",
        "icon": "💬",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "call_completed",
            "conditions": [
                {
                    "type": "call_outcome",
                    "value": ["lead", "urgent", "escalation"]
                }
            ],
            "actions": [
                {
                    "type": "slack_send_message",
                    "channel": "{{slack_channel}}",
                    "message": {
                        "blocks": [
                            {
                                "type": "header",
                                "text": "🎯 New {{call_type}}"
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {"type": "mrkdwn", "text": "*From:*\\n{{caller_name}}"},
                                    {"type": "mrkdwn", "text": "*Phone:*\\n{{caller_phone}}"},
                                    {"type": "mrkdwn", "text": "*Duration:*\\n{{call_duration}}"},
                                    {"type": "mrkdwn", "text": "*Agent:*\\n{{agent_name}}"}
                                ]
                            },
                            {
                                "type": "section",
                                "text": "*Summary:*\\n{{call_summary}}"
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": "View Call",
                                        "url": "{{call_url}}"
                                    },
                                    {
                                        "type": "button",
                                        "text": "Listen to Recording",
                                        "url": "{{recording_url}}"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        },
        "trigger_config": {
            "event": "call.completed",
            "filters": {
                "min_priority": "medium"
            }
        },
        "setup_guide": """
# Slack Notification Workflow Setup

## Prerequisites
- Slack workspace admin access
- Slack app or webhook URL
- Dedicated channels created

## Setup Steps

1. **Connect Slack**
   - Go to Integrations → Slack
   - Click "Add to Slack"
   - Authorize workspace access
   - Grant required permissions

2. **Create Channels** (Recommended)
   - #leads - For new leads
   - #urgent-calls - For urgent issues
   - #sales-calls - For sales interactions

3. **Install Workflow**
   - Install from Marketplace
   - Select notification channel

4. **Configure Notification Rules**
   - Set priority levels:
     - High priority → #urgent-calls
     - Medium priority → #leads
     - Low priority → #sales-calls
   - Define trigger conditions

5. **Customize Message Format**
   - Choose information to include
   - Set up action buttons
   - Configure mention rules (@mentions)

6. **Test Notifications**
   - Make test calls
   - Verify message delivery
   - Check formatting
   - Test action buttons

## Notification Types
- **New Lead**: When qualified lead is captured
- **Urgent Call**: Customer reports critical issue
- **High-Value Call**: Large deal opportunity
- **Escalation**: Customer requests manager

## Best Practices
- Don't over-notify (causes alert fatigue)
- Use mentions strategically
- Include relevant context
- Add actionable buttons
- Use different channels by priority
- Set up Do Not Disturb hours
        """.strip(),
        "use_cases": [
            {
                "title": "Lead Alerts",
                "description": "Notify sales team of new qualified leads"
            },
            {
                "title": "Urgent Issues",
                "description": "Alert support team of critical customer issues"
            },
            {
                "title": "Team Coordination",
                "description": "Keep team informed of important calls"
            }
        ],
        "required_integrations": ["slack"],
        "compatible_agents": ["customer-support-agent", "sales-qualification-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Email Follow-up",
        "slug": "email-follow-up",
        "description": "Send automated follow-up emails after calls",
        "long_description": """
Automatically send personalized follow-up emails after phone calls. Includes call summary,
next steps, and relevant resources. Integrates with major email platforms.

Features:
- Customizable email templates
- Call summary inclusion
- Resource attachments
- Tracking and analytics
- A/B testing support
- Unsubscribe handling
        """.strip(),
        "category": "notifications",
        "tags": ["email", "follow-up", "automation", "nurture"],
        "version": "2.3.1",
        "icon": "📧",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "call_completed",
            "conditions": [
                {
                    "type": "email_provided",
                    "value": True
                }
            ],
            "actions": [
                {
                    "type": "send_email",
                    "template": "call_followup",
                    "to": "{{customer_email}}",
                    "subject": "Thanks for your call - {{company_name}}",
                    "body": """
Hi {{customer_name}},

Thank you for speaking with us today about {{topic_discussed}}. Here's a quick summary of our conversation:

{{call_summary}}

Next Steps:
{{next_steps}}

{{#if resources}}
I've attached some resources that might be helpful:
{{resources}}
{{/if}}

If you have any questions, feel free to reply to this email or call us at {{phone_number}}.

Best regards,
{{agent_name}}
{{company_name}}
                    """,
                    "track_opens": True,
                    "track_clicks": True
                }
            ]
        },
        "trigger_config": {
            "event": "call.completed",
            "filters": {
                "email_captured": True
            }
        },
        "setup_guide": """
# Email Follow-up Workflow Setup

## Prerequisites
- Email service provider (SendGrid, Mailgun, etc.)
- Email templates designed
- Sending domain configured

## Setup Steps

1. **Connect Email Provider**
   - Go to Integrations → Email
   - Connect SendGrid or Mailgun
   - Verify sending domain
   - Configure DKIM/SPF

2. **Install Workflow**
   - Install from Marketplace
   - Select email template

3. **Customize Email Template**
   - Edit subject line
   - Customize email body
   - Add company branding
   - Include signature

4. **Configure Variables**
   - Map call data to email fields
   - Set default values
   - Configure conditional sections

5. **Set Up Tracking**
   - Enable open tracking
   - Enable click tracking
   - Configure analytics

6. **Test Email Delivery**
   - Send test emails
   - Check formatting
   - Verify links work
   - Test on mobile devices

## Email Template Variables
- {{customer_name}}
- {{customer_email}}
- {{call_date}}
- {{call_summary}}
- {{next_steps}}
- {{agent_name}}
- {{company_name}}
- {{resources}}

## Best Practices
- Send within 5 minutes of call end
- Keep emails concise
- Include clear next steps
- Make it easy to respond
- Personalize beyond name
- Track engagement metrics
- A/B test subject lines
- Respect unsubscribe requests
        """.strip(),
        "use_cases": [
            {
                "title": "Sales Follow-up",
                "description": "Send proposals and next steps after sales calls"
            },
            {
                "title": "Support Resolution",
                "description": "Confirm issue resolution and provide resources"
            },
            {
                "title": "Lead Nurturing",
                "description": "Keep leads engaged with relevant content"
            }
        ],
        "required_integrations": ["sendgrid", "mailgun"],
        "compatible_agents": ["sales-qualification-agent", "customer-support-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "SMS Confirmation",
        "slug": "sms-confirmation",
        "description": "Send SMS confirmations and reminders",
        "long_description": """
Send automated SMS messages for bookings, confirmations, and reminders. High delivery rates
and instant notifications keep customers informed.

Features:
- Instant SMS delivery
- Custom message templates
- Two-way SMS support
- Link shortening
- Delivery tracking
- Opt-out handling
        """.strip(),
        "category": "notifications",
        "tags": ["sms", "text", "notifications", "reminders"],
        "version": "1.9.2",
        "icon": "📱",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "appointment_booked",
            "conditions": [
                {
                    "type": "phone_provided",
                    "value": True
                }
            ],
            "actions": [
                {
                    "type": "send_sms",
                    "to": "{{customer_phone}}",
                    "message": "Hi {{customer_name}}, your {{appointment_type}} is confirmed for {{appointment_date}} at {{appointment_time}}. Reply CONFIRM to acknowledge or RESCHEDULE to change. - {{business_name}}"
                },
                {
                    "type": "schedule_reminder",
                    "delay_minutes": 1440,
                    "action": {
                        "type": "send_sms",
                        "to": "{{customer_phone}}",
                        "message": "Reminder: You have a {{appointment_type}} tomorrow at {{appointment_time}} with {{business_name}}. Reply CONFIRM or call {{phone_number}} to reschedule."
                    }
                }
            ]
        },
        "trigger_config": {
            "event": "appointment.booked",
            "filters": {
                "phone_number_provided": True
            }
        },
        "setup_guide": """
# SMS Confirmation Workflow Setup

## Prerequisites
- SMS provider account (Twilio recommended)
- SMS-enabled phone number
- Compliance with SMS regulations

## Setup Steps

1. **Connect SMS Provider**
   - Go to Integrations → SMS
   - Connect Twilio account
   - Verify phone number
   - Test SMS delivery

2. **Install Workflow**
   - Install from Marketplace
   - Configure message templates

3. **Customize Messages**
   - Confirmation message
   - Reminder message (24hr before)
   - Second reminder (1hr before)
   - Add business name and contact info

4. **Set Up Two-Way SMS** (Optional)
   - Configure keyword responses
   - CONFIRM → Acknowledge
   - RESCHEDULE → Offer alternatives
   - CANCEL → Process cancellation
   - STOP → Opt-out

5. **Configure Reminders**
   - Set reminder timing
   - Customize reminder messages
   - Configure frequency

6. **Test the Flow**
   - Book test appointment
   - Verify confirmation SMS
   - Check reminder delivery
   - Test reply keywords

## SMS Compliance
- Always include business name
- Provide opt-out option
- Honor opt-out requests immediately
- Only send to opted-in numbers
- Respect quiet hours (9 AM - 9 PM)

## Message Templates
**Confirmation:**
"Hi {{name}}, your {{type}} is confirmed for {{date}} at {{time}}. Reply CONFIRM to acknowledge. - {{business}}"

**24hr Reminder:**
"Reminder: You have a {{type}} tomorrow at {{time}} with {{business}}. Reply CONFIRM or call to reschedule."

**1hr Reminder:**
"Your appointment starts in 1 hour at {{location}}. See you soon! - {{business}}"

## Best Practices
- Keep messages under 160 characters
- Include clear call-to-action
- Use link shortening for URLs
- Time reminders appropriately
- Make it easy to reschedule
- Track delivery and engagement
        """.strip(),
        "use_cases": [
            {
                "title": "Appointment Reminders",
                "description": "Reduce no-shows with automated reminders"
            },
            {
                "title": "Booking Confirmations",
                "description": "Instant confirmation of reservations"
            },
            {
                "title": "Status Updates",
                "description": "Keep customers informed of order/delivery status"
            }
        ],
        "required_integrations": ["twilio"],
        "compatible_agents": ["appointment-scheduler"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Zendesk Ticket Creation",
        "slug": "zendesk-ticket-creation",
        "description": "Create support tickets in Zendesk from calls",
        "long_description": """
Automatically create Zendesk tickets from customer support calls. Includes call transcript,
customer information, and intelligent priority assignment.

Features:
- Automatic ticket creation
- Smart priority detection
- Call transcript attachment
- Customer profile linking
- Tag assignment
- SLA tracking
        """.strip(),
        "category": "data_sync",
        "tags": ["zendesk", "support", "ticketing", "help-desk"],
        "version": "2.1.3",
        "icon": "🎫",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "call_completed",
            "conditions": [
                {
                    "type": "requires_followup",
                    "value": True
                }
            ],
            "actions": [
                {
                    "type": "zendesk_create_ticket",
                    "ticket": {
                        "subject": "Call follow-up: {{issue_summary}}",
                        "description": "{{call_transcript}}",
                        "requester": {
                            "name": "{{customer_name}}",
                            "email": "{{customer_email}}",
                            "phone": "{{customer_phone}}"
                        },
                        "priority": "{{detected_priority}}",
                        "type": "{{ticket_type}}",
                        "tags": ["voice-call", "{{call_category}}"],
                        "custom_fields": {
                            "call_id": "{{call_id}}",
                            "call_duration": "{{call_duration}}",
                            "agent_name": "{{agent_name}}"
                        }
                    }
                },
                {
                    "type": "notify",
                    "message": "Ticket {{ticket_id}} created for {{customer_name}}"
                }
            ]
        },
        "trigger_config": {
            "event": "call.completed",
            "filters": {
                "category": "support"
            }
        },
        "setup_guide": """
# Zendesk Ticket Creation Workflow Setup

## Prerequisites
- Zendesk account (any plan)
- API token or OAuth credentials
- Ticket form configured

## Setup Steps

1. **Connect Zendesk**
   - Go to Integrations → Zendesk
   - Enter subdomain and API token
   - Test connection
   - Verify permissions

2. **Install Workflow**
   - Install from Marketplace
   - Map to ticket form

3. **Configure Ticket Mapping**
   - Map call data to ticket fields
   - Set default assignee/group
   - Configure custom fields

4. **Set Up Priority Detection**
   - Define priority keywords:
     - Urgent: "emergency", "critical", "down"
     - High: "problem", "issue", "broken"
     - Normal: "question", "how to"
     - Low: "feedback", "suggestion"

5. **Configure Tags**
   - Auto-tag by call category
   - Add source tag: "voice-call"
   - Include product/service tags

6. **Test Ticket Creation**
   - Make test support call
   - Verify ticket creation
   - Check field mapping
   - Confirm priority assignment

## Field Mapping
- Subject → Ticket subject
- Description → Call transcript
- Requester → Customer info
- Priority → Auto-detected or default
- Type → Question/Problem/Incident
- Tags → voice-call, category
- Custom Fields → Call metadata

## Priority Assignment Rules
**Urgent:**
- Keywords: emergency, critical, down, outage
- Customer tier: Premium/Enterprise
- Impact: Multiple users affected

**High:**
- Keywords: problem, issue, broken, not working
- Repeat caller
- SLA approaching

**Normal:**
- General questions
- "How to" inquiries
- Feature requests

**Low:**
- Feedback
- Suggestions
- General inquiries

## Best Practices
- Review ticket quality weekly
- Update priority rules based on patterns
- Train team on voice ticket handling
- Set up SLA tracking
- Use macros for common responses
- Link related tickets
        """.strip(),
        "use_cases": [
            {
                "title": "Support Call Documentation",
                "description": "Create tickets for all support calls requiring follow-up"
            },
            {
                "title": "Issue Tracking",
                "description": "Track and resolve customer issues systematically"
            },
            {
                "title": "SLA Management",
                "description": "Ensure timely responses with automatic ticketing"
            }
        ],
        "required_integrations": ["zendesk"],
        "compatible_agents": ["customer-support-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Shopify Order Check",
        "slug": "shopify-order-check",
        "description": "Look up and provide Shopify order status",
        "long_description": """
Enable customers to check their Shopify order status via phone. Provides real-time order information,
tracking details, and estimated delivery dates.

Features:
- Order lookup by number or email
- Real-time order status
- Tracking number retrieval
- Delivery estimates
- Order history access
- Refund status checking
        """.strip(),
        "category": "data_sync",
        "tags": ["shopify", "ecommerce", "orders", "tracking"],
        "version": "1.7.4",
        "icon": "🛍️",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "intent_detected",
            "conditions": [
                {
                    "type": "intent",
                    "value": "check_order_status"
                }
            ],
            "actions": [
                {
                    "type": "extract_data",
                    "fields": ["order_number", "email"]
                },
                {
                    "type": "shopify_find_order",
                    "by": "order_number",
                    "value": "{{order_number}}"
                },
                {
                    "type": "format_response",
                    "template": "Your order #{{order_number}} is {{fulfillment_status}}. {{#if tracking_number}}Tracking number: {{tracking_number}}. {{/if}}Estimated delivery: {{estimated_delivery}}."
                },
                {
                    "type": "send_response",
                    "message": "{{formatted_response}}"
                }
            ]
        },
        "trigger_config": {
            "event": "intent.detected",
            "intent_name": "check_order_status"
        },
        "setup_guide": """
# Shopify Order Check Workflow Setup

## Prerequisites
- Shopify store
- Shopify Admin API access
- Private app or OAuth credentials

## Setup Steps

1. **Connect Shopify**
   - Go to Integrations → Shopify
   - Enter store URL
   - Provide API credentials
   - Test connection

2. **Install Workflow**
   - Install from Marketplace
   - Configure lookup methods

3. **Configure Lookup Options**
   - Order number lookup
   - Email address lookup
   - Phone number lookup
   - Set security verification level

4. **Customize Response Templates**
   - Order found response
   - Order not found response
   - Multiple orders response
   - Shipping delay notification

5. **Set Up Order Status Mapping**
   - Map Shopify status to customer-friendly language:
     - unfulfilled → "being prepared"
     - fulfilled → "shipped"
     - delivered → "delivered"

6. **Test Order Lookup**
   - Test with valid order number
   - Test with email lookup
   - Test order not found scenario
   - Verify tracking info delivery

## Order Status Translations
Make status customer-friendly:
- "unfulfilled" → "Your order is being prepared"
- "partial" → "Part of your order has shipped"
- "fulfilled" → "Your order is on its way"
- "delivered" → "Your order has been delivered"

## Security Considerations
- Verify customer identity
- Don't share full payment details
- Mask email addresses
- Ask for order number + last 4 of phone
- Log all order inquiries

## Response Templates
**Order Found:**
"Great! I found your order #{{number}}. It's currently {{status}}. {{#if tracking}}Your tracking number is {{tracking}}.{{/if}} {{#if estimate}}Expected delivery: {{estimate}}.{{/if}}"

**Order Not Found:**
"I'm sorry, I couldn't find an order with that number. Please verify the order number or email address. Would you like me to look it up a different way?"

**Multiple Orders:**
"I found {{count}} orders for that email. Let me start with your most recent order from {{date}}..."

## Best Practices
- Verify customer identity first
- Provide proactive updates
- Offer assistance with issues
- Track common inquiries
- Update shipping estimates regularly
        """.strip(),
        "use_cases": [
            {
                "title": "Order Status Inquiries",
                "description": "Let customers check their order status by phone"
            },
            {
                "title": "Delivery Tracking",
                "description": "Provide real-time tracking information"
            },
            {
                "title": "Order History",
                "description": "Help customers review past orders"
            }
        ],
        "required_integrations": ["shopify"],
        "compatible_agents": ["order-status-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Stripe Payment Link",
        "slug": "stripe-payment-link",
        "description": "Generate and send Stripe payment links",
        "long_description": """
Automatically generate Stripe payment links during calls and send them via SMS or email.
Perfect for collecting payments over the phone without handling card details.

Features:
- Secure payment link generation
- Custom amount and description
- SMS/Email delivery
- Payment status tracking
- Receipt automation
- Refund handling
        """.strip(),
        "category": "data_sync",
        "tags": ["stripe", "payments", "checkout", "billing"],
        "version": "2.0.1",
        "icon": "💳",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "workflow_definition": {
            "trigger": "intent_detected",
            "conditions": [
                {
                    "type": "intent",
                    "value": "make_payment"
                }
            ],
            "actions": [
                {
                    "type": "extract_data",
                    "fields": ["amount", "description", "customer_email"]
                },
                {
                    "type": "stripe_create_payment_link",
                    "amount": "{{amount}}",
                    "description": "{{description}}",
                    "success_url": "{{success_url}}",
                    "cancel_url": "{{cancel_url}}"
                },
                {
                    "type": "send_sms",
                    "to": "{{customer_phone}}",
                    "message": "Here's your payment link for {{description}} ({{amount}}): {{payment_link}}. This link expires in 24 hours. - {{business_name}}"
                },
                {
                    "type": "send_email",
                    "to": "{{customer_email}}",
                    "subject": "Payment link from {{business_name}}",
                    "body": "Click here to complete your payment: {{payment_link}}"
                }
            ]
        },
        "trigger_config": {
            "event": "intent.detected",
            "intent_name": "make_payment"
        },
        "setup_guide": """
# Stripe Payment Link Workflow Setup

## Prerequisites
- Stripe account
- Stripe API keys
- PCI compliance understanding

## Setup Steps

1. **Connect Stripe**
   - Go to Integrations → Stripe
   - Enter API keys (publishable and secret)
   - Configure webhook endpoint
   - Test connection

2. **Install Workflow**
   - Install from Marketplace
   - Configure payment settings

3. **Configure Payment Links**
   - Set default currency
   - Configure success/cancel URLs
   - Set link expiration (default: 24 hours)
   - Enable email receipts

4. **Set Up Notifications**
   - Payment successful → Confirmation
   - Payment failed → Retry instructions
   - Link expired → New link generation

5. **Configure Security**
   - Enable payment verification
   - Set maximum payment amount
   - Configure refund policy
   - Add terms and conditions link

6. **Test Payment Flow**
   - Generate test payment link
   - Complete test payment
   - Verify webhook reception
   - Check receipt delivery

## Payment Link Configuration
- Currency: USD (or your default)
- Expiration: 24 hours
- Allow promotion codes: Yes/No
- Collect billing address: Yes/No
- Collect shipping address: Yes/No

## Security Best Practices
- Never handle card details over phone
- Always use Stripe's secure checkout
- Verify customer identity
- Send links only to verified contact info
- Set reasonable payment limits
- Monitor for fraud
- Enable 3D Secure for high-value payments

## Delivery Options
**SMS:**
"Hi {{name}}, here's your secure payment link for {{item}} ({{amount}}): {{link}}. Expires in 24hrs. - {{business}}"

**Email:**
Subject: "Complete your payment - {{business}}"
Body: Professional email template with payment button

## Payment Status Handling
- Pending → Send reminder after 2 hours
- Successful → Send receipt and thank you
- Failed → Offer assistance, send new link
- Expired → Generate new link if requested

## Best Practices
- Set clear expiration times
- Provide clear payment description
- Send receipt immediately after payment
- Monitor abandoned payments
- Follow up on expired links
- Keep payment amounts accurate
- Test regularly
        """.strip(),
        "use_cases": [
            {
                "title": "Phone Order Payments",
                "description": "Collect payments for phone orders securely"
            },
            {
                "title": "Service Payments",
                "description": "Get paid for consultations and services"
            },
            {
                "title": "Invoice Payments",
                "description": "Send payment links for outstanding invoices"
            }
        ],
        "required_integrations": ["stripe"],
        "compatible_agents": ["customer-support-agent", "order-status-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Multi-step Lead Nurture",
        "slug": "multi-step-lead-nurture",
        "description": "Automated multi-touch lead nurturing sequence",
        "long_description": """
Create sophisticated lead nurturing campaigns triggered by phone calls. Combines email, SMS,
and task creation to keep leads engaged until they're ready to buy.

Features:
- Multi-channel sequences
- Behavior-based triggers
- Dynamic content
- Lead scoring integration
- A/B testing
- Performance analytics
        """.strip(),
        "category": "lead_capture",
        "tags": ["nurture", "marketing", "automation", "leads"],
        "version": "1.6.0",
        "icon": "🌱",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": True,
        "is_free": True,
        "workflow_definition": {
            "trigger": "lead_captured",
            "conditions": [
                {
                    "type": "lead_status",
                    "value": ["new", "warm"]
                }
            ],
            "actions": [
                {
                    "type": "wait",
                    "duration_hours": 1
                },
                {
                    "type": "send_email",
                    "template": "welcome_sequence_1",
                    "subject": "Thanks for your interest in {{product_name}}"
                },
                {
                    "type": "wait",
                    "duration_days": 2
                },
                {
                    "type": "send_email",
                    "template": "case_study",
                    "subject": "How {{customer_company}} achieved {{result}}"
                },
                {
                    "type": "wait",
                    "duration_days": 3
                },
                {
                    "type": "create_task",
                    "assignee": "{{sales_rep}}",
                    "title": "Follow up with {{lead_name}}",
                    "due_date": "today"
                },
                {
                    "type": "send_sms",
                    "message": "Hi {{name}}, {{sales_rep}} from {{company}} here. I wanted to follow up on {{topic}}. Got time for a quick call? - Text YES to schedule."
                }
            ]
        },
        "trigger_config": {
            "event": "lead.captured",
            "filters": {
                "lead_score": {
                    "min": 30
                }
            }
        },
        "setup_guide": """
# Multi-step Lead Nurture Setup Guide

## Prerequisites
- Email marketing platform
- CRM with lead scoring
- SMS capability
- Content library prepared

## Setup Steps

1. **Install Workflow**
   - Install from Marketplace
   - Review default sequence

2. **Configure Sequence Steps**
   - Day 0: Call follow-up email
   - Day 2: Value proposition email
   - Day 5: Case study email
   - Day 7: Personal outreach (task + SMS)
   - Day 14: Final touch (offer/discount)

3. **Create Email Templates**
   - Welcome email
   - Educational content
   - Case studies
   - Product information
   - Call-to-action emails

4. **Set Up Lead Scoring**
   - Email opens: +5 points
   - Link clicks: +10 points
   - Reply: +25 points
   - Multiple visits: +15 points

5. **Configure Exit Criteria**
   - Lead becomes customer → Exit
   - Lead requests removal → Exit
   - Lead score drops below threshold → Pause
   - No engagement after 30 days → Archive

6. **Test the Sequence**
   - Add test lead
   - Verify timing
   - Check email delivery
   - Test task creation
   - Confirm SMS delivery

## Sequence Structure
**Touch 1 (Hour 1):**
- Channel: Email
- Purpose: Thank you + set expectations
- CTA: Download resource

**Touch 2 (Day 2):**
- Channel: Email
- Purpose: Education + value prop
- CTA: Watch demo video

**Touch 3 (Day 5):**
- Channel: Email
- Purpose: Social proof (case study)
- CTA: Request consultation

**Touch 4 (Day 7):**
- Channel: Task + SMS
- Purpose: Personal outreach
- CTA: Schedule call

**Touch 5 (Day 14):**
- Channel: Email
- Purpose: Special offer
- CTA: Sign up / Buy now

## Personalization Variables
- {{lead_name}}
- {{company_name}}
- {{product_interest}}
- {{call_topic}}
- {{pain_point}}
- {{industry}}
- {{lead_source}}

## Success Metrics
- Open rates by email
- Click-through rates
- Response rates
- Conversion to opportunity
- Time to conversion
- ROI by sequence

## Optimization Tips
- A/B test subject lines
- Test send times
- Vary content by industry
- Adjust timing based on engagement
- Personalize beyond name
- Use dynamic content
- Remove non-responders
- Re-engage cold leads with different sequence

## Best Practices
- Don't over-email
- Provide clear value in each touch
- Make unsubscribe easy
- Honor preferences
- Track engagement
- Update based on behavior
- Use multiple channels strategically
- Keep content relevant
        """.strip(),
        "use_cases": [
            {
                "title": "Lead Warming",
                "description": "Nurture cold leads until they're sales-ready"
            },
            {
                "title": "Post-Demo Follow-up",
                "description": "Keep demo attendees engaged"
            },
            {
                "title": "Re-engagement",
                "description": "Win back dormant leads"
            }
        ],
        "required_integrations": ["hubspot", "salesforce", "sendgrid"],
        "compatible_agents": ["sales-qualification-agent", "lead-capture-agent"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },
]
