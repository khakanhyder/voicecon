"""
Integration Action Registry.

Defines available actions per connector with their LLM-compatible parameter schemas.
Vapi-style: each action becomes a tool the AI can call during a live conversation.
"""
import inspect
import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Schema: connector_slug -> list of actions the AI can invoke
INTEGRATION_ACTIONS: Dict[str, List[Dict[str, Any]]] = {

    "notion": [
        {
            "action": "search",
            "label": "Search Notion",
            "description": "Search the user's Notion pages and databases",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text"},
                    "object_type": {"type": "string", "description": "Filter: 'page' or 'database'"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "create_page",
            "label": "Create Notion Page",
            "description": "Create a page under a parent page with a title and text",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_page_id": {"type": "string", "description": "Parent page ID",
                                       "title": "Parent page", "x-resource": "pages"},
                    "title": {"type": "string", "description": "Page title"},
                    "content": {"type": "string", "description": "Body text"},
                },
                "required": ["parent_page_id", "title"],
            },
        },
        {
            "action": "append_text",
            "label": "Append Text to Notion Page",
            "description": "Append a paragraph of text to an existing page",
            "parameters": {
                "type": "object",
                "properties": {
                    "block_id": {"type": "string", "description": "Page or block ID",
                                 "title": "Page", "x-resource": "pages"},
                    "text": {"type": "string", "description": "Text to append"},
                },
                "required": ["block_id", "text"],
            },
        },
    ],

    "clickup": [
        {
            "action": "create_task",
            "label": "Create ClickUp Task",
            "description": "Create a task in a ClickUp list",
            "parameters": {
                "type": "object",
                "properties": {
                    # No picker: listing ClickUp lists needs a space id, and the
                    # connector has no get_spaces to populate a space picker
                    # from. The URL mode still resolves it, so the field is
                    # usable — it just cannot offer a dropdown yet.
                    "list_id": {"type": "string", "description": "Target list ID",
                                "title": "List"},
                    "name": {"type": "string", "description": "Task name"},
                    "description": {"type": "string", "description": "Task description"},
                },
                "required": ["list_id", "name"],
            },
        },
        {
            "action": "list_tasks",
            "label": "List ClickUp Tasks",
            "description": "List tasks in a ClickUp list",
            "parameters": {
                "type": "object",
                "properties": {"list_id": {"type": "string", "description": "List ID",
                                           "title": "List"}},
                "required": ["list_id"],
            },
        },
        {
            "action": "add_comment",
            "label": "Comment on ClickUp Task",
            "description": "Add a comment to a ClickUp task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID",
                                "title": "Task", "x-runtime": True},
                    "comment_text": {"type": "string", "description": "Comment text"},
                },
                "required": ["task_id", "comment_text"],
            },
        },
    ],

    "trello": [
        {
            "action": "create_card",
            "label": "Create Trello Card",
            "description": "Create a card in a Trello list",
            "parameters": {
                "type": "object",
                "properties": {
                    # Two-step picker: choosing a board populates the lists on
                    # it. Both are filled from the connection's defaults when
                    # left blank, so the common case needs neither.
                    # UI-only: it exists so the List picker knows which board to
                    # read, and is stripped before the connector is called —
                    # TrelloConnector.create_card takes no board_id.
                    "board_id": {"type": "string", "description": "Board the list belongs to",
                                 "title": "Board", "x-resource": "boards",
                                 "x-ui-only": True},
                    "list_id": {"type": "string", "description": "Target list ID",
                                "title": "List", "x-resource": "lists",
                                "x-depends-on": "board_id"},
                    "name": {"type": "string", "description": "Card title"},
                    "description": {"type": "string", "description": "Card description"},
                },
                "required": ["list_id", "name"],
            },
        },
        {
            "action": "add_comment",
            "label": "Comment on Trello Card",
            "description": "Add a comment to a Trello card",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Card ID",
                                "title": "Card", "x-runtime": True},
                    "text": {"type": "string", "description": "Comment text"},
                },
                "required": ["card_id", "text"],
            },
        },
    ],

    "whatsapp": [
        {
            "action": "send_message",
            "label": "Send WhatsApp Message",
            "description": "Send a WhatsApp text message (within the 24h window)",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient phone (E.164, no '+')"},
                    "message": {"type": "string", "description": "Message text"},
                },
                "required": ["to", "message"],
            },
        },
        {
            "action": "send_template",
            "label": "Send WhatsApp Template",
            "description": "Send an approved WhatsApp template (for first contact)",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient phone (E.164, no '+')"},
                    "template_name": {"type": "string", "description": "Approved template name"},
                    "language_code": {"type": "string", "description": "e.g. en_US"},
                },
                "required": ["to", "template_name"],
            },
        },
    ],

    "hubspot": [
        {
            "action": "create_contact",
            "label": "Create Contact",
            "description": "Create a new contact in HubSpot CRM with the caller's information",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Contact's email address"},
                    "first_name": {"type": "string", "description": "Contact's first name"},
                    "last_name": {"type": "string", "description": "Contact's last name"},
                    "phone": {"type": "string", "description": "Contact's phone number"},
                    "company": {"type": "string", "description": "Company name"},
                },
                "required": ["email"],
            },
        },
        {
            "action": "search_contacts",
            "label": "Search Contacts",
            "description": "Search for existing contacts in HubSpot by name, email, or phone",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (name, email, or phone)"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "create_deal",
            "label": "Create Deal",
            "description": "Create a new deal/opportunity in HubSpot CRM",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_name": {"type": "string", "description": "Name of the deal"},
                    "amount": {"type": "number", "description": "Deal value/amount"},
                    "stage": {"type": "string", "description": "Deal stage (e.g. appointmentscheduled, qualifiedtobuy, closedwon)"},
                    "contact_email": {"type": "string", "description": "Email of the associated contact"},
                },
                "required": ["deal_name"],
            },
        },
        {
            "action": "update_contact",
            "label": "Update Contact",
            "description": "Update an existing HubSpot contact's information",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "HubSpot contact ID",
                                   "title": "Contact", "x-runtime": True},
                    "phone": {"type": "string", "description": "New phone number"},
                    "company": {"type": "string", "description": "New company name"},
                    "additional_properties": {"type": "object", "description": "Additional properties to update"},
                },
                "required": ["contact_id"],
            },
        },
    ],

    "salesforce": [
        {
            "action": "create_contact",
            "label": "Create Contact",
            "description": "Create a new contact record in Salesforce",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string", "description": "Contact's first name"},
                    "last_name": {"type": "string", "description": "Contact's last name"},
                    "email": {"type": "string", "description": "Contact's email address"},
                    "phone": {"type": "string", "description": "Contact's phone number"},
                    "account_name": {"type": "string", "description": "Company/Account name"},
                },
                "required": ["last_name"],
            },
        },
        {
            "action": "create_lead",
            "label": "Create Lead",
            "description": "Create a new lead in Salesforce from caller information",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string", "description": "Lead's first name"},
                    "last_name": {"type": "string", "description": "Lead's last name"},
                    "email": {"type": "string", "description": "Lead's email address"},
                    "phone": {"type": "string", "description": "Lead's phone number"},
                    "company": {"type": "string", "description": "Company name"},
                    "lead_source": {"type": "string", "description": "Lead source (e.g. Phone, Web)"},
                },
                "required": ["last_name", "company"],
            },
        },
        {
            "action": "search_contacts",
            "label": "Search Contacts",
            "description": "Search for contacts in Salesforce by name or email",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name or email to search for"},
                },
                "required": ["query"],
            },
        },
    ],

    "google-calendar": [
        {
            "action": "check_availability",
            "label": "Check Availability",
            "description": "Check calendar availability for a given time range",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "description": "Start time in ISO 8601 format (e.g. 2024-01-15T09:00:00)"},
                    "end_time": {"type": "string", "description": "End time in ISO 8601 format (e.g. 2024-01-15T17:00:00)"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["start_time", "end_time"],
            },
        },
        {
            "action": "find_available_slots",
            "label": "Find Available Slots",
            "description": "Find available time slots in the calendar for booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format"},
                    "duration_minutes": {"type": "integer", "description": "Duration of the meeting in minutes"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["date", "duration_minutes"],
            },
        },
        {
            "action": "create_event",
            "label": "Book Appointment",
            "description": "Book a calendar appointment or meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Meeting/event title"},
                    "start_time": {"type": "string", "description": "Start time in ISO 8601 format"},
                    "end_time": {"type": "string", "description": "End time in ISO 8601 format"},
                    "attendee_email": {"type": "string", "description": "Attendee email address"},
                    "description": {"type": "string", "description": "Meeting description or notes"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["title", "start_time", "end_time"],
            },
        },
        {
            "action": "list_events",
            "label": "List Upcoming Events",
            "description": "List upcoming calendar events for a given date range",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                    "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                    "max_results": {"type": "integer", "description": "Maximum number of events to return"},
                },
                "required": ["start_date"],
            },
        },
    ],

    "slack": [
        {
            "action": "send_message",
            "label": "Send Slack Message",
            "description": "Send a message to a Slack channel or user",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name or ID (e.g. #sales, #support)",
                                "title": "Channel", "x-resource": "channels"},
                    "message": {"type": "string", "description": "Message text to send"},
                    "thread_ts": {"type": "string", "description": "Thread timestamp to reply in a thread (optional)"},
                },
                "required": ["channel", "message"],
            },
        },
    ],

    "sendgrid": [
        {
            "action": "send_email",
            "label": "Send Email",
            "description": "Send an email to the caller or a specified recipient",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body content"},
                    "to_name": {"type": "string", "description": "Recipient's name (optional)"},
                },
                "required": ["to_email", "subject", "body"],
            },
        },
    ],
    "stripe": [
        {
            "action": "create_customer",
            "label": "Create Customer",
            "description": "Create a Stripe customer record for the caller",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer email address"},
                    "name": {"type": "string", "description": "Customer's full name"},
                    "phone": {"type": "string", "description": "Customer phone number"},
                    "description": {"type": "string", "description": "Internal note about this customer"},
                },
                "required": ["email"],
            },
        },
        {
            "action": "create_payment_intent",
            "label": "Take a Payment",
            "description": "Create a payment intent to charge a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    # Stripe is minor-units everywhere. Saying so here is the
                    # difference between charging $10 and charging 10 cents,
                    # and this text is what the agent sees when it fills the
                    # field in.
                    "amount": {
                        "type": "integer",
                        "description": "Amount in the smallest currency unit — cents for USD, so 1000 means $10.00",
                    },
                    "currency": {"type": "string", "description": "Three-letter currency code, e.g. usd"},
                    "customer": {"type": "string", "description": "Stripe customer ID to charge"},
                    "description": {"type": "string", "description": "What the payment is for"},
                },
                "required": ["amount"],
            },
        },
        {
            "action": "create_subscription",
            "label": "Create Subscription",
            "description": "Subscribe a customer to one or more prices",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string", "description": "Stripe customer ID"},
                    "items": {
                        "type": "array",
                        "description": 'Subscription items, e.g. [{"price": "price_xxx"}]',
                        "items": {"type": "object"},
                    },
                    "trial_period_days": {"type": "integer", "description": "Free trial length in days"},
                },
                "required": ["customer", "items"],
            },
        },
        {
            "action": "create_refund",
            "label": "Refund a Payment",
            "description": "Refund a payment, in full or in part",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_intent": {"type": "string", "description": "Payment intent ID to refund"},
                    "amount": {
                        "type": "integer",
                        "description": "Amount to refund in cents; leave empty to refund the full payment",
                    },
                    "reason": {
                        "type": "string",
                        "description": "One of: duplicate, fraudulent, requested_by_customer",
                    },
                },
                "required": ["payment_intent"],
            },
        },
        {
            "action": "get_customer",
            "label": "Look Up Customer",
            "description": "Fetch an existing Stripe customer by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Stripe customer ID"},
                },
                "required": ["customer_id"],
            },
        },
    ],
    "airtable": [
        {
            "action": "create_record",
            "label": "Create Record",
            "description": "Create a new record in an Airtable table",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                    "fields": {"type": "object", "description": "Record fields"},
                },
                "required": ["table_name", "fields"],
            },
        },
    ],
    "gohighlevel": [
        {
            "action": "create_contact",
            "label": "Create Contact",
            "description": "Create a new contact in GoHighLevel",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": [],
            },
        },
    ],
    "twilio": [
        {
            "action": "send_sms",
            "label": "Send SMS",
            "description": "Send an SMS via Twilio",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Destination phone number"},
                    "message": {"type": "string", "description": "SMS content"},
                },
                "required": ["to", "message"],
            },
        },
    ],
    "langfuse": [
        {
            "action": "create_trace",
            "label": "Create Trace",
            "description": "Create a new LLM trace in Langfuse",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Trace name"},
                    "input_data": {"type": "string", "description": "Input payload"},
                },
                "required": ["name"],
            },
        },
    ],
    "calendly": [
        {
            "action": "list_scheduled_events",
            "label": "List Scheduled Events",
            "description": "List the user's scheduled Calendly events",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Event status, e.g., 'active'"},
                    "count": {"type": "integer", "description": "Number of events to list"},
                },
                "required": [],
            },
        },
    ],
    "google-sheets": [
        {
            "action": "append_row",
            "label": "Append Row",
            "description": "Append a row of data to a Google Sheet",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID",
                                       "title": "Spreadsheet", "x-resource": "spreadsheets"},
                    "range_name": {"type": "string", "description": "Range (e.g. Sheet1!A:B)"},
                    "values": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                },
                "required": ["spreadsheet_id", "range_name", "values"],
            },
        },
    ],
    "google-drive": [
        {
            "action": "list_files",
            "label": "List Files",
            "description": "List files in Google Drive",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": [],
            },
        },
    ],
    "cal-com": [
        {
            "action": "list_event_types",
            "label": "List Event Types",
            "description": "List all Cal.com event types",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    ],
    "monday": [
        {
            "action": "list_boards",
            "label": "List Boards",
            "description": "List all Monday.com boards",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    ],
    "vonage": [
        {
            "action": "send_sms",
            "label": "Send SMS via Vonage",
            "description": "Send an SMS using Vonage",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_number": {"type": "string", "description": "Destination number"},
                    "from_name": {"type": "string", "description": "Sender name or number"},
                    "text": {"type": "string", "description": "Message content"},
                },
                "required": ["to_number", "from_name", "text"],
            },
        },
    ],
    "telnyx": [
        {
            "action": "send_message",
            "label": "Send Message via Telnyx",
            "description": "Send a message using Telnyx",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_number": {"type": "string", "description": "Destination number"},
                    "from_number": {"type": "string", "description": "Sender number"},
                    "text": {"type": "string", "description": "Message content"},
                },
                "required": ["to_number", "from_number", "text"],
            },
        },
    ],
    "zapier": [
        {
            "action": "send_webhook",
            "label": "Send to Zapier",
            "description": "Send call data to a Zapier Catch Hook, triggering a Zap",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "JSON payload to send to Zapier"},
                    "event": {"type": "string", "description": "Optional event name, e.g. call_completed"},
                },
                "required": ["data"],
            },
        },
    ],

    "make": [
        {
            "action": "send_webhook",
            "label": "Send to Make",
            "description": "Send call data to a Make scenario's custom webhook",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "JSON payload to send to Make"},
                    "event": {"type": "string", "description": "Optional event name, e.g. call_completed"},
                },
                "required": ["data"],
            },
        },
    ],

    "microsoft-teams": [
        {
            "action": "send_message",
            "label": "Send Teams Message",
            "description": "Post a message to the connected Microsoft Teams channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message text (Markdown supported)"},
                    "title": {"type": "string", "description": "Optional card title"},
                },
                "required": ["message"],
            },
        },
    ],

    "pipedrive": [
        {
            "action": "create_person",
            "label": "Create Person",
            "description": "Create a person (contact) in Pipedrive",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                },
                "required": ["name"],
            },
        },
        {
            "action": "search_persons",
            "label": "Search People",
            "description": "Find people in Pipedrive by name, email or phone",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (name, email, or phone)"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "create_deal",
            "label": "Create Deal",
            "description": "Create a deal in the Pipedrive pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Deal title"},
                    "value": {"type": "number", "description": "Deal value"},
                    "currency": {"type": "string", "description": "Currency code, e.g. USD"},
                    "person_id": {"type": "integer", "description": "ID of the person to attach"},
                },
                "required": ["title"],
            },
        },
        {
            "action": "add_note",
            "label": "Add Note",
            "description": "Attach a note (e.g. the call summary) to a person or deal",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Note text"},
                    "person_id": {"type": "integer", "description": "Person to attach the note to"},
                    "deal_id": {"type": "integer", "description": "Deal to attach the note to"},
                },
                "required": ["content"],
            },
        },
    ],

    "zendesk": [
        {
            "action": "create_ticket",
            "label": "Create Ticket",
            "description": "Raise a Zendesk support ticket from the call",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Ticket subject"},
                    "description": {"type": "string", "description": "Ticket body / call summary"},
                    "requester_email": {"type": "string", "description": "Caller's email, so Zendesk matches an existing user"},
                    "requester_name": {"type": "string", "description": "Caller's name"},
                    "priority": {"type": "string", "description": "urgent, high, normal, or low"},
                },
                "required": ["subject", "description"],
            },
        },
        {
            "action": "add_comment",
            "label": "Comment on Ticket",
            "description": "Add a comment to an existing Zendesk ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "integer", "description": "Ticket ID"},
                    "comment": {"type": "string", "description": "Comment text"},
                    "public": {"type": "boolean", "description": "Visible to the requester (default true)"},
                },
                "required": ["ticket_id", "comment"],
            },
        },
        {
            "action": "search_tickets",
            "label": "Search Tickets",
            "description": "Search Zendesk tickets",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term, e.g. an email address or status:open"},
                },
                "required": ["query"],
            },
        },
    ],

    "intercom": [
        {
            "action": "create_contact",
            "label": "Create Contact",
            "description": "Create a contact or lead in Intercom",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "name": {"type": "string", "description": "Full name"},
                },
                "required": [],
            },
        },
        {
            "action": "search_contacts",
            "label": "Search Contacts",
            "description": "Find Intercom contacts by email, phone or name",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "add_note",
            "label": "Add Note to Contact",
            "description": "Attach a note (e.g. the call summary) to an Intercom contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Intercom contact ID"},
                    "note": {"type": "string", "description": "Note text"},
                },
                "required": ["contact_id", "note"],
            },
        },
        {
            "action": "create_conversation",
            "label": "Start Conversation",
            "description": "Start an Intercom conversation with a contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Intercom contact ID"},
                    "message": {"type": "string", "description": "Message body"},
                },
                "required": ["contact_id", "message"],
            },
        },
    ],

    "supabase": [
        {
            "action": "fetch_table",
            "label": "Fetch Table Data",
            "description": "Fetch rows from a Supabase table",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table name"},
                    "limit": {"type": "integer", "description": "Max rows to fetch"},
                },
                "required": ["table_name"],
            },
        },
    ],
}


def _object_storage_actions(container_word: str) -> List[Dict[str, Any]]:
    """The five actions every object-storage tile exposes.

    S3, R2, GCS and Azure Blob share one connector surface, so they share one
    action definition rather than four copies that would drift. The only
    user-visible difference is vocabulary: Azure calls it a container, the
    S3-compatible three call it a bucket, and the field is named accordingly so
    the form matches the provider's own console.
    """
    return [
        {
            "action": "upload_text",
            "label": "Store Text",
            "description": (
                f"Save a transcript, summary or note as a file in the {container_word}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Object path, e.g. transcripts/call-123.txt"},
                    "content": {"type": "string", "description": "Text to store"},
                    "content_type": {"type": "string", "description": "MIME type (default text/plain)"},
                    container_word: {"type": "string", "description": f"Override the connection's {container_word}"},
                },
                "required": ["key", "content"],
            },
        },
        {
            "action": "upload_from_url",
            "label": "Store File from URL",
            "description": f"Copy a file — usually a call recording — into the {container_word}",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Object path, e.g. recordings/call-123.mp3"},
                    "source_url": {"type": "string", "description": "URL of the file to copy"},
                    container_word: {"type": "string", "description": f"Override the connection's {container_word}"},
                },
                "required": ["key", "source_url"],
            },
        },
        {
            "action": "list_objects",
            "label": "List Files",
            "description": f"List files in the {container_word}, optionally under a prefix",
            "parameters": {
                "type": "object",
                "properties": {
                    "prefix": {"type": "string", "description": "Only list keys starting with this, e.g. recordings/"},
                    "limit": {"type": "integer", "description": "Maximum number of results"},
                    container_word: {"type": "string", "description": f"Override the connection's {container_word}"},
                },
                "required": [],
            },
        },
        {
            "action": "delete_object",
            "label": "Delete File",
            "description": f"Delete a file from the {container_word}",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Object path to delete"},
                    container_word: {"type": "string", "description": f"Override the connection's {container_word}"},
                },
                "required": ["key"],
            },
        },
        {
            "action": "generate_presigned_url",
            "label": "Create Shareable Link",
            "description": (
                "Create a time-limited download link, so a recording can be shared "
                f"without making the {container_word} public"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Object path to share"},
                    "expires_in": {"type": "integer", "description": "Link lifetime in seconds (default 3600, max 7 days)"},
                    container_word: {"type": "string", "description": f"Override the connection's {container_word}"},
                },
                "required": ["key"],
            },
        },
    ]


def _smtp_actions(provider_label: str) -> List[Dict[str, Any]]:
    """Gmail, Outlook and Custom SMTP are one connector with three presets."""
    return [
        {
            "action": "send_email",
            "label": "Send Email",
            "description": f"Send an email via {provider_label}",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "Recipient address (comma-separate for several)"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Plain-text body"},
                    "html_body": {"type": "string", "description": "Optional HTML body"},
                    "cc": {"type": "string", "description": "CC recipients, comma-separated"},
                    "reply_to": {"type": "string", "description": "Reply-To address"},
                },
                "required": ["to_email", "subject", "body"],
            },
        },
    ]


INTEGRATION_ACTIONS.update(
    {
        "aws-s3": _object_storage_actions("bucket"),
        "cloudflare-r2": _object_storage_actions("bucket"),
        "gcs": _object_storage_actions("bucket"),
        "azure-blob": _object_storage_actions("container"),
        "gmail": _smtp_actions("Gmail"),
        "outlook": _smtp_actions("Outlook"),
        "custom-smtp": _smtp_actions("your SMTP server"),
    }
)


# Connector slug → Python class name mapping (mirrors step_handlers.py)
CONNECTOR_CLASS_MAP: Dict[str, str] = {
    "hubspot": "HubSpotConnector",
    "salesforce": "SalesforceConnector",
    "google_calendar": "GoogleCalendarConnector",
    "google-calendar": "GoogleCalendarConnector",
    "slack": "SlackConnector",
    "sendgrid": "SendGridConnector",
    "stripe": "StripeConnector",
    "notion": "NotionConnector",
    "clickup": "ClickUpConnector",
    "trello": "TrelloConnector",
    "whatsapp": "WhatsAppConnector",
    "airtable": "AirtableConnector",
    "gohighlevel": "GoHighLevelConnector",
    "twilio": "TwilioConnector",
    "langfuse": "LangfuseConnector",
    "calendly": "CalendlyConnector",
    "google-sheets": "GoogleSheetsConnector",
    "google-drive": "GoogleDriveConnector",
    "cal-com": "CalComConnector",
    "monday": "MondayConnector",
    "vonage": "VonageConnector",
    "telnyx": "TelnyxConnector",
    "supabase": "SupabaseConnector",
    "aws-s3": "AWSS3Connector",
    "cloudflare-r2": "CloudflareR2Connector",
    "gcs": "GCSConnector",
    "azure-blob": "AzureBlobConnector",
    "zapier": "ZapierConnector",
    "make": "MakeConnector",
    "microsoft-teams": "MicrosoftTeamsConnector",
    "gmail": "GmailSMTPConnector",
    "outlook": "OutlookSMTPConnector",
    "custom-smtp": "CustomSMTPConnector",
    "pipedrive": "PipedriveConnector",
    "zendesk": "ZendeskConnector",
    "intercom": "IntercomConnector",
}


def _as_iso(value: str, *, end_of_day: bool = False) -> str:
    """Widen a plain ``YYYY-MM-DD`` into the ISO timestamp Google expects.

    The action schemas ask for a date because that is what a caller says out
    loud ("anything free on the 14th?"). The Calendar API wants an RFC-3339
    instant. A value that already carries a time is passed through untouched.
    """
    text = str(value).strip()
    if "T" in text:
        return text
    return f"{text}T23:59:59Z" if end_of_day else f"{text}T00:00:00Z"


def _adapt_gcal_create_event(p: Dict[str, Any]) -> Dict[str, Any]:
    if "title" in p:
        p.setdefault("summary", p.pop("title"))
    attendee = p.pop("attendee_email", None)
    if attendee:
        p.setdefault(
            "attendees", [attendee] if isinstance(attendee, str) else list(attendee)
        )
    return p


def _adapt_gcal_list_events(p: Dict[str, Any]) -> Dict[str, Any]:
    if "start_date" in p:
        p.setdefault("time_min", _as_iso(p.pop("start_date")))
    if "end_date" in p:
        p.setdefault("time_max", _as_iso(p.pop("end_date"), end_of_day=True))
    return p


def _adapt_gcal_find_slots(p: Dict[str, Any]) -> Dict[str, Any]:
    day = p.pop("date", None)
    if day:
        p.setdefault("search_start", _as_iso(day))
        p.setdefault("search_end", _as_iso(day, end_of_day=True))
    return p


def _adapt_gcal_check_availability(p: Dict[str, Any]) -> Dict[str, Any]:
    calendar = p.pop("calendar_id", None)
    if calendar:
        p.setdefault("calendar_ids", [calendar])
    return p


def _adapt_hubspot_update_contact(p: Dict[str, Any]) -> Dict[str, Any]:
    """Fold the schema's flat fields into the single ``properties`` dict.

    The schema offers "phone" and "company" because that is what a caller
    actually updates mid-conversation; the method speaks HubSpot's internal
    property bag. Without this the flat fields were dropped and the update
    failed on a missing required ``properties``.
    """
    # Defensive: this value comes from an LLM or a saved form, and a string
    # where a dict belongs must not take the whole tool call down.
    supplied = p.pop("additional_properties", None)
    properties = dict(supplied) if isinstance(supplied, dict) else {}
    for schema_name, hubspot_property in (("phone", "phone"), ("company", "company")):
        if schema_name in p:
            properties[hubspot_property] = p.pop(schema_name)
    if properties:
        p.setdefault("properties", properties)
    return p


def _adapt_hubspot_create_deal(p: Dict[str, Any]) -> Dict[str, Any]:
    if "stage" in p:
        p.setdefault("deal_stage", p.pop("stage"))
    return p


def _adapt_salesforce_create_contact(p: Dict[str, Any]) -> Dict[str, Any]:
    # Account is a lookup relationship, so it cannot be set by name in the
    # same call. Passed through as a custom field, which is where a Salesforce
    # admin would map it, rather than silently dropped.
    account = p.pop("account_name", None)
    if account:
        extra = dict(p.get("additional_fields") or {})
        extra.setdefault("AccountName__c", account)
        p["additional_fields"] = extra
    return p


def _adapt_salesforce_create_lead(p: Dict[str, Any]) -> Dict[str, Any]:
    source = p.pop("lead_source", None)
    if source:
        extra = dict(p.get("additional_fields") or {})
        extra.setdefault("LeadSource", source)
        p["additional_fields"] = extra
    return p


def _adapt_slack_send_message(p: Dict[str, Any]) -> Dict[str, Any]:
    if "message" in p:
        p.setdefault("text", p.pop("message"))
    return p


def _adapt_sendgrid_send_email(p: Dict[str, Any]) -> Dict[str, Any]:
    if "body" in p:
        p.setdefault("text_content", p.pop("body"))
    return p


#: (slug, action) → function mapping the schema's public parameter names onto
#: the connector method's actual arguments.
#:
#: These two vocabularies had silently diverged. The schema is what the builder
#: renders, what a saved workflow stores and what an agent's tool definition
#: advertises — "message", "body", "title", "start_date". The methods were
#: written against the provider's vocabulary — "text", "text_content",
#: "summary", "time_min". Nothing reconciled them, and because
#: ``drop_unsupported_arguments`` quietly discards keys a method cannot take,
#: the mismatch did not raise where it happened: Slack's send_message lost its
#: text and failed on a missing required argument instead.
#:
#: Renaming the schema instead would have been the smaller diff and the wrong
#: fix — it would break every workflow already saved with these keys, and push
#: provider naming into the UI.
ACTION_ADAPTERS: Dict[Tuple[str, str], Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    ("google-calendar", "create_event"): _adapt_gcal_create_event,
    ("google-calendar", "list_events"): _adapt_gcal_list_events,
    ("google-calendar", "find_available_slots"): _adapt_gcal_find_slots,
    ("google_calendar", "create_event"): _adapt_gcal_create_event,
    ("google_calendar", "list_events"): _adapt_gcal_list_events,
    ("google_calendar", "find_available_slots"): _adapt_gcal_find_slots,
    ("google-calendar", "check_availability"): _adapt_gcal_check_availability,
    ("google_calendar", "check_availability"): _adapt_gcal_check_availability,
    ("slack", "send_message"): _adapt_slack_send_message,
    ("sendgrid", "send_email"): _adapt_sendgrid_send_email,
    ("hubspot", "update_contact"): _adapt_hubspot_update_contact,
    ("hubspot", "create_deal"): _adapt_hubspot_create_deal,
    ("salesforce", "create_contact"): _adapt_salesforce_create_contact,
    ("salesforce", "create_lead"): _adapt_salesforce_create_lead,
}


def adapt_parameters(
    connector_slug: str, action: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Translate schema parameter names into connector method arguments.

    Runs at the same choke point as ``strip_ui_only_parameters`` and before
    ``drop_unsupported_arguments``, so a renamed key is translated rather than
    discarded.
    """
    adapter = ACTION_ADAPTERS.get((connector_slug, action))
    if adapter is None:
        return dict(parameters or {})
    return adapter(dict(parameters or {}))


def get_actions_for_connector(connector_slug: str) -> List[Dict[str, Any]]:
    """Return the list of available actions for a given connector."""
    return INTEGRATION_ACTIONS.get(connector_slug, [])


def get_action_schema(connector_slug: str, action: str) -> Dict[str, Any]:
    """Return the parameter schema for a specific connector action.

    Slugs exist in two spellings. ``CONNECTOR_CLASS_MAP`` and ``ACTION_ADAPTERS``
    both carry an underscored alias (``google_calendar``) alongside the
    canonical hyphenated slug (``google-calendar``), but ``INTEGRATION_ACTIONS``
    is keyed only by the canonical one. A connection stored under the alias
    therefore found no schema at all — so ``strip_ui_only_parameters`` removed
    nothing and the schema-derived defaults never applied. Normalising here
    fixes every caller at once, and lets the action allowlist in the workflow
    action step treat this registry as authoritative.
    """
    candidates = [connector_slug]
    if "_" in connector_slug:
        candidates.append(connector_slug.replace("_", "-"))

    for slug in candidates:
        for a in INTEGRATION_ACTIONS.get(slug, []):
            if a["action"] == action:
                return a
    return {}


def strip_ui_only_parameters(
    connector_slug: str, action: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Drop parameters that exist only to drive the builder's UI.

    Some fields are there so a picker knows what to list — Trello's ``board_id``
    tells the List dropdown which board to read — but the connector method has
    no such argument, and passing it raises ``TypeError`` at run time. They are
    marked ``x-ui-only`` in the schema and removed here, at the one point every
    action execution passes through.
    """
    schema = get_action_schema(connector_slug, action)
    properties = (schema.get("parameters") or {}).get("properties") or {}
    ui_only = {
        name
        for name, spec in properties.items()
        if isinstance(spec, dict) and spec.get("x-ui-only")
    }
    if not ui_only:
        return parameters
    return {k: v for k, v in (parameters or {}).items() if k not in ui_only}


def drop_unsupported_arguments(
    method: Any, parameters: Dict[str, Any], *, context: str = ""
) -> Dict[str, Any]:
    """Keep only the arguments ``method`` can actually accept.

    Every dynamic action call ends in ``method(**parameters)``, and one key the
    method does not declare is a hard ``TypeError`` that kills the whole step —
    however correct the rest of the arguments were. Two real sources of stray
    keys, neither of which is the caller doing anything unreasonable:

    * **A saved node whose action was changed.** The builder writes parameters
      into one object per step; switching "Create Trello Card" to "Comment on
      Trello Card" leaves ``board_id`` and ``list_id`` behind, and the run dies
      on ``add_comment() got an unexpected keyword argument 'board_id'``.
    * **An agent calling an integration tool.** The arguments come out of an
      LLM, so an extra plausible-looking key is a matter of time.

    Filtering on the *signature* rather than on the registry schema is
    deliberate: the signature is what actually raises, so this cannot drift from
    the thing it protects. A method taking ``**kwargs`` is left alone — it has
    said it will take anything.

    Dropped keys are logged rather than silently swallowed: if a required
    argument was misspelled, the call still fails on the missing argument, and
    the log says which unknown key was thrown away.
    """
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):  # pragma: no cover - builtins, C functions
        return dict(parameters or {})

    if any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
    ):
        return dict(parameters or {})

    allowed = {
        name
        for name, p in signature.parameters.items()
        if name != "self"
        and p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }

    supplied = dict(parameters or {})
    kept = {k: v for k, v in supplied.items() if k in allowed}
    dropped = sorted(set(supplied) - set(kept))
    if dropped:
        logger.warning(
            "Dropped %s before calling %s%s — the action does not accept %s. "
            "Usually a step whose action was changed after it was configured.",
            ", ".join(repr(k) for k in dropped),
            getattr(method, "__qualname__", str(method)),
            f" ({context})" if context else "",
            "them" if len(dropped) > 1 else "it",
        )
    return kept

def resource_fields(connector_slug: str, action: str) -> Dict[str, Dict[str, Any]]:
    """The pickable fields on an action, for the builder to render."""
    schema = get_action_schema(connector_slug, action)
    properties = (schema.get("parameters") or {}).get("properties") or {}
    return {
        name: spec
        for name, spec in properties.items()
        if isinstance(spec, dict) and spec.get("x-resource")
    }
