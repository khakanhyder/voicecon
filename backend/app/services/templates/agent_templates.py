"""
Pre-built agent templates for the marketplace.
"""

from datetime import datetime
from decimal import Decimal

# Agent Templates Data
AGENT_TEMPLATES = [
    {
        "name": "Customer Support Agent",
        "slug": "customer-support-agent",
        "description": "Handle customer inquiries with empathy and efficiency",
        "long_description": """
A comprehensive customer support agent that can handle common customer inquiries, troubleshoot issues,
and escalate to human agents when necessary. Perfect for businesses looking to provide 24/7 support
without overwhelming their support team.

This agent is trained to:
- Answer frequently asked questions
- Troubleshoot common technical issues
- Process refund and return requests
- Escalate complex issues appropriately
- Maintain a friendly, helpful tone
        """.strip(),
        "category": "customer_support",
        "tags": ["support", "help-desk", "ticketing", "customer-service"],
        "version": "2.1.0",
        "icon": "🎧",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": True,
        "is_free": True,
        "agent_config": {
            "name": "Customer Support Agent",
            "voice_id": "en-US-Neural2-F",
            "language": "en-US",
            "temperature": 0.7,
            "max_tokens": 150,
        },
        "system_prompt": """You are a friendly and professional customer support agent for {company_name}.
Your goal is to help customers resolve their issues quickly and effectively.

Guidelines:
- Always greet customers warmly
- Listen carefully to their concerns
- Ask clarifying questions when needed
- Provide clear, step-by-step solutions
- Be patient and empathetic
- If you cannot solve an issue, escalate to a human agent
- End calls on a positive note

Remember: Customer satisfaction is your top priority.""",
        "first_message": "Hello! Thank you for contacting {company_name} support. My name is {agent_name}, and I'm here to help you today. How can I assist you?",
        "customizable_fields": [
            {
                "name": "company_name",
                "label": "Company Name",
                "type": "text",
                "required": True,
                "default": "Your Company",
                "description": "The name of your company"
            },
            {
                "name": "agent_name",
                "label": "Agent Name",
                "type": "text",
                "required": False,
                "default": "Alex",
                "description": "The name your agent will use"
            },
            {
                "name": "escalation_keywords",
                "label": "Escalation Keywords",
                "type": "text",
                "required": False,
                "default": "speak to manager, human agent, escalate",
                "description": "Keywords that trigger escalation to human agent"
            }
        ],
        "setup_guide": """
# Customer Support Agent Setup Guide

## Prerequisites
- Active Voicecon account
- Phone number provisioned
- (Optional) Integration with your ticketing system

## Setup Steps

1. **Install the Template**
   - Click "Install" button
   - Customize company name and agent name
   - Review escalation keywords

2. **Assign Phone Number**
   - Go to Phone Numbers page
   - Assign your support line to this agent

3. **Configure Integrations** (Optional)
   - Connect to Zendesk, Freshdesk, or your ticketing system
   - Set up automatic ticket creation workflow

4. **Test the Agent**
   - Call your support line
   - Test various scenarios (FAQs, escalations, etc.)
   - Refine responses as needed

5. **Go Live**
   - Update your support hours
   - Train your team on escalation handling
   - Monitor call quality and customer satisfaction

## Best Practices
- Review call transcripts weekly
- Update FAQs based on common questions
- Set clear escalation criteria
- Provide fallback to human agents for complex issues
        """.strip(),
        "use_cases": [
            {
                "title": "24/7 Customer Support",
                "description": "Provide round-the-clock support for common inquiries"
            },
            {
                "title": "First-Level Triage",
                "description": "Filter and route calls before reaching human agents"
            },
            {
                "title": "After-Hours Support",
                "description": "Handle calls outside business hours"
            }
        ],
        "required_integrations": None,
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Sales Qualification Agent",
        "slug": "sales-qualification-agent",
        "description": "Qualify leads and schedule sales calls automatically",
        "long_description": """
An intelligent sales qualification agent that identifies high-quality leads and books meetings with your
sales team. Uses proven BANT (Budget, Authority, Need, Timeline) methodology to qualify prospects.

Key capabilities:
- Qualify leads using BANT framework
- Capture contact information
- Schedule sales appointments
- CRM integration for automatic lead creation
- Real-time lead scoring
        """.strip(),
        "category": "sales",
        "tags": ["sales", "lead-gen", "crm", "qualification", "bant"],
        "version": "1.5.2",
        "icon": "💼",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": True,
        "is_free": True,
        "agent_config": {
            "name": "Sales Qualifier",
            "voice_id": "en-US-Neural2-D",
            "language": "en-US",
            "temperature": 0.7,
            "max_tokens": 150,
        },
        "system_prompt": """You are a professional sales development representative for {company_name}.
Your goal is to qualify leads and schedule meetings with the sales team.

Qualification Framework (BANT):
1. Budget: Does the prospect have budget allocated?
2. Authority: Are they a decision-maker?
3. Need: Do they have a clear business need?
4. Timeline: When do they plan to make a decision?

Process:
1. Introduce yourself and the company
2. Ask qualifying questions naturally
3. Determine lead quality (Hot/Warm/Cold)
4. For qualified leads, offer to schedule a meeting
5. Capture contact information
6. Confirm next steps

Remember: Be consultative, not pushy. Focus on understanding their needs.""",
        "first_message": "Hi, this is {sales_rep_name} from {company_name}. Thanks for your interest in our {product_name}. I'd love to learn more about your needs and see if we're a good fit. Do you have a few minutes to chat?",
        "customizable_fields": [
            {
                "name": "company_name",
                "label": "Company Name",
                "type": "text",
                "required": True,
                "default": "Your Company"
            },
            {
                "name": "sales_rep_name",
                "label": "Sales Rep Name",
                "type": "text",
                "required": True,
                "default": "Jordan"
            },
            {
                "name": "product_name",
                "label": "Product/Service Name",
                "type": "text",
                "required": True,
                "default": "our solution"
            }
        ],
        "setup_guide": """
# Sales Qualification Agent Setup Guide

## Prerequisites
- CRM system (Salesforce, HubSpot, or similar)
- Calendar integration for booking meetings
- Define your ideal customer profile (ICP)

## Setup Steps

1. **Install & Customize**
   - Install template
   - Set company name and product details
   - Configure qualification criteria

2. **Connect CRM**
   - Integrate with Salesforce or HubSpot
   - Set up automatic lead creation workflow
   - Configure lead scoring rules

3. **Calendar Integration**
   - Connect Google Calendar or Calendly
   - Set sales team availability
   - Configure booking workflow

4. **Define Qualification Criteria**
   - Set minimum budget requirements
   - Define decision-maker titles
   - List key pain points/needs

5. **Test & Refine**
   - Role-play different scenarios
   - Test lead scoring accuracy
   - Verify CRM synchronization

## Tips for Success
- Keep qualification questions natural and conversational
- Use lead scoring to prioritize follow-ups
- Review calls to improve qualification accuracy
- A/B test different approaches
        """.strip(),
        "use_cases": [
            {
                "title": "Inbound Lead Qualification",
                "description": "Qualify leads from your website or marketing campaigns"
            },
            {
                "title": "Outbound Lead Screening",
                "description": "Pre-qualify cold leads before sales rep contact"
            },
            {
                "title": "Meeting Scheduling",
                "description": "Book qualified prospects directly into sales calendars"
            }
        ],
        "required_integrations": ["salesforce", "hubspot", "calendar"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Appointment Scheduler",
        "slug": "appointment-scheduler",
        "description": "Book and manage appointments with calendar integration",
        "long_description": """
A smart appointment scheduling agent that handles booking, rescheduling, and cancellations automatically.
Integrates seamlessly with Google Calendar, Outlook, and popular scheduling tools.

Features:
- Real-time calendar availability checking
- Automatic appointment confirmation
- Reminder system integration
- Rescheduling and cancellation handling
- Multi-timezone support
- Buffer time management
        """.strip(),
        "category": "scheduling",
        "tags": ["calendar", "booking", "scheduling", "appointments"],
        "version": "3.0.1",
        "icon": "📅",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "agent_config": {
            "name": "Appointment Scheduler",
            "voice_id": "en-US-Neural2-F",
            "language": "en-US",
            "temperature": 0.6,
            "max_tokens": 150,
        },
        "system_prompt": """You are a professional appointment scheduler for {business_name}.
Your role is to help customers book, reschedule, or cancel appointments efficiently.

Process:
1. Greet the customer and ask if they want to book, reschedule, or cancel
2. For new bookings:
   - Ask for preferred date and time
   - Check calendar availability
   - Confirm appointment type and duration
   - Collect contact information
   - Send confirmation
3. For rescheduling:
   - Verify existing appointment
   - Offer new available slots
   - Update and confirm
4. For cancellations:
   - Verify appointment
   - Process cancellation
   - Offer to reschedule if appropriate

Always confirm details before finalizing any booking.""",
        "first_message": "Hello! Thank you for calling {business_name}. I'm here to help you schedule an appointment. Would you like to book a new appointment, reschedule, or cancel an existing one?",
        "customizable_fields": [
            {
                "name": "business_name",
                "label": "Business Name",
                "type": "text",
                "required": True,
                "default": "Your Business"
            },
            {
                "name": "appointment_types",
                "label": "Appointment Types",
                "type": "text",
                "required": True,
                "default": "Consultation, Follow-up, New Patient",
                "description": "Comma-separated list of appointment types"
            },
            {
                "name": "business_hours",
                "label": "Business Hours",
                "type": "text",
                "required": True,
                "default": "9 AM - 5 PM",
                "description": "Your operating hours"
            }
        ],
        "setup_guide": """
# Appointment Scheduler Setup Guide

## Prerequisites
- Google Calendar, Outlook, or Calendly account
- Business hours defined
- Appointment types configured

## Setup Steps

1. **Install Template**
   - Customize business name and hours
   - Define appointment types and durations

2. **Connect Calendar**
   - Integrate with Google Calendar
   - Set up calendar synchronization
   - Configure availability rules

3. **Configure Appointment Types**
   - Define appointment durations
   - Set buffer times between appointments
   - Configure any special requirements

4. **Set Up Reminders**
   - Enable SMS/Email reminders
   - Configure reminder timing (24hr, 1hr before, etc.)
   - Customize reminder messages

5. **Test the System**
   - Book a test appointment
   - Verify calendar sync
   - Test rescheduling and cancellation
   - Check reminder delivery

## Best Practices
- Keep calendar always up-to-date
- Set realistic buffer times
- Enable double-booking prevention
- Regularly review no-show rates
- Collect feedback on booking experience
        """.strip(),
        "use_cases": [
            {
                "title": "Medical Practice",
                "description": "Schedule patient appointments automatically"
            },
            {
                "title": "Professional Services",
                "description": "Book consultations and meetings"
            },
            {
                "title": "Salon/Spa",
                "description": "Manage beauty and wellness appointments"
            }
        ],
        "required_integrations": ["calendar"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Order Status Agent",
        "slug": "order-status-agent",
        "description": "Check order status and provide shipping updates",
        "long_description": """
An e-commerce agent that handles order status inquiries, tracking updates, and delivery issues.
Integrates with major e-commerce platforms and shipping carriers.

Capabilities:
- Order status lookup by order number
- Real-time tracking information
- Estimated delivery dates
- Address change requests
- Return and exchange initiation
- Missing package investigations
        """.strip(),
        "category": "ecommerce",
        "tags": ["ecommerce", "orders", "tracking", "shipping"],
        "version": "2.0.3",
        "icon": "📦",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "agent_config": {
            "name": "Order Status Agent",
            "voice_id": "en-US-Neural2-F",
            "language": "en-US",
            "temperature": 0.6,
            "max_tokens": 150,
        },
        "system_prompt": """You are a helpful order status agent for {store_name}.
Your role is to help customers track their orders and resolve delivery issues.

Process:
1. Ask for order number or customer email
2. Look up order in the system
3. Provide current status and tracking information
4. Answer questions about delivery
5. Handle issues like:
   - Missing packages
   - Delivery delays
   - Address changes
   - Returns and exchanges

Always be proactive in offering solutions. If there's an issue, explain what happened
and what steps are being taken to resolve it.""",
        "first_message": "Hello! Thank you for contacting {store_name}. I can help you check your order status. May I have your order number or the email address you used for your purchase?",
        "customizable_fields": [
            {
                "name": "store_name",
                "label": "Store Name",
                "type": "text",
                "required": True,
                "default": "Your Store"
            },
            {
                "name": "return_window_days",
                "label": "Return Window (Days)",
                "type": "number",
                "required": True,
                "default": "30"
            }
        ],
        "setup_guide": """
# Order Status Agent Setup Guide

## Prerequisites
- E-commerce platform (Shopify, WooCommerce, etc.)
- Shipping carrier accounts
- Order management system access

## Setup Steps

1. **Install & Configure**
   - Install template
   - Customize store name and policies
   - Set return window

2. **Connect E-commerce Platform**
   - Integrate with Shopify or WooCommerce
   - Configure order lookup API
   - Test order retrieval

3. **Integrate Shipping Carriers**
   - Connect to UPS, FedEx, USPS APIs
   - Enable real-time tracking
   - Configure tracking number format

4. **Set Up Return Workflows**
   - Define return eligibility rules
   - Configure return label generation
   - Set up refund processing

5. **Test Scenarios**
   - Order lookup by number
   - Order lookup by email
   - Tracking number retrieval
   - Return initiation

## Common Use Cases
- "Where's my order?"
- "When will my package arrive?"
- "I need to return something"
- "My tracking isn't updating"
        """.strip(),
        "use_cases": [
            {
                "title": "Order Tracking",
                "description": "Provide real-time order and shipping updates"
            },
            {
                "title": "Delivery Issues",
                "description": "Handle missing packages and delays"
            },
            {
                "title": "Returns & Exchanges",
                "description": "Process return requests automatically"
            }
        ],
        "required_integrations": ["shopify", "woocommerce"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },

    {
        "name": "Lead Capture Agent",
        "slug": "lead-capture-agent",
        "description": "Capture and qualify inbound leads automatically",
        "long_description": """
A high-converting lead capture agent that collects contact information and qualifying details from
interested prospects. Perfect for capturing leads from ads, landing pages, and marketing campaigns.

Features:
- Natural conversation flow
- Smart information collection
- Lead scoring and qualification
- Instant CRM synchronization
- Follow-up scheduling
- Multi-channel lead routing
        """.strip(),
        "category": "sales",
        "tags": ["lead-gen", "marketing", "crm", "conversions"],
        "version": "2.2.1",
        "icon": "🎯",
        "author_name": "Voicecon",
        "is_official": True,
        "is_featured": False,
        "is_free": True,
        "agent_config": {
            "name": "Lead Capture Agent",
            "voice_id": "en-US-Neural2-D",
            "language": "en-US",
            "temperature": 0.7,
            "max_tokens": 150,
        },
        "system_prompt": """You are a friendly lead capture specialist for {company_name}.
Your goal is to collect contact information and understand the prospect's needs.

Information to Collect:
1. Full name
2. Email address
3. Phone number (if comfortable sharing)
4. Company name (for B2B)
5. Primary interest/need
6. Best time to follow up

Process:
1. Warmly greet the caller
2. Confirm their interest in {offering}
3. Collect information conversationally (don't interrogate)
4. Ask about their specific needs
5. Set expectations for follow-up
6. Thank them and confirm next steps

Remember: Build rapport before asking for information. Make it feel like a conversation, not a form.""",
        "first_message": "Hi there! Thanks so much for your interest in {offering} from {company_name}. I'd love to learn more about what you're looking for and see how we can help. First, may I get your name?",
        "customizable_fields": [
            {
                "name": "company_name",
                "label": "Company Name",
                "type": "text",
                "required": True,
                "default": "Your Company"
            },
            {
                "name": "offering",
                "label": "Product/Service Offering",
                "type": "text",
                "required": True,
                "default": "our services"
            },
            {
                "name": "lead_source",
                "label": "Lead Source",
                "type": "text",
                "required": False,
                "default": "website"
            }
        ],
        "setup_guide": """
# Lead Capture Agent Setup Guide

## Prerequisites
- CRM system (HubSpot, Salesforce, etc.)
- Lead routing rules defined
- Follow-up workflows configured

## Setup Steps

1. **Install Template**
   - Customize company and offering details
   - Set lead source tracking

2. **Connect CRM**
   - Integrate with your CRM
   - Map fields (name, email, phone, etc.)
   - Test lead creation

3. **Configure Lead Routing**
   - Set up territory rules
   - Assign lead owners
   - Configure round-robin if needed

4. **Set Up Notifications**
   - Email alerts for new leads
   - Slack notifications
   - SMS alerts for hot leads

5. **Create Follow-up Workflows**
   - Immediate email response
   - Schedule follow-up calls
   - Nurture sequence enrollment

## Optimization Tips
- A/B test different opening scripts
- Track conversion rates
- Monitor call quality
- Optimize qualifying questions
- Reduce friction in information collection
        """.strip(),
        "use_cases": [
            {
                "title": "Ad Campaign Leads",
                "description": "Capture leads from Google Ads and Facebook campaigns"
            },
            {
                "title": "Website Inquiries",
                "description": "Convert website visitors into qualified leads"
            },
            {
                "title": "Event Follow-up",
                "description": "Capture attendee information from events and webinars"
            }
        ],
        "required_integrations": ["hubspot", "salesforce"],
        "status": "published",
        "published_at": datetime.utcnow(),
    },
]
