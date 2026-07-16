"""
Integration Action Registry.

Defines available actions per connector with their LLM-compatible parameter schemas.
Vapi-style: each action becomes a tool the AI can call during a live conversation.
"""
from typing import Dict, Any, List

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
                    "parent_page_id": {"type": "string", "description": "Parent page ID"},
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
                    "block_id": {"type": "string", "description": "Page or block ID"},
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
                    "list_id": {"type": "string", "description": "Target list ID"},
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
                "properties": {"list_id": {"type": "string", "description": "List ID"}},
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
                    "task_id": {"type": "string", "description": "Task ID"},
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
                    "list_id": {"type": "string", "description": "Target list ID"},
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
                    "card_id": {"type": "string", "description": "Card ID"},
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
                    "contact_id": {"type": "string", "description": "HubSpot contact ID"},
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

    "google_calendar": [
        {
            "action": "check_availability",
            "label": "Check Availability",
            "description": "Check calendar availability for a given time range",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "description": "Start time in ISO 8601 format (e.g. 2024-01-15T09:00:00)"},
                    "end_time": {"type": "string", "description": "End time in ISO 8601 format (e.g. 2024-01-15T17:00:00)"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)"},
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
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)"},
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
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to primary)"},
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
                    "channel": {"type": "string", "description": "Channel name or ID (e.g. #sales, #support)"},
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
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID"},
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
}


def get_actions_for_connector(connector_slug: str) -> List[Dict[str, Any]]:
    """Return the list of available actions for a given connector."""
    return INTEGRATION_ACTIONS.get(connector_slug, [])


def get_action_schema(connector_slug: str, action: str) -> Dict[str, Any]:
    """Return the parameter schema for a specific connector action."""
    for a in INTEGRATION_ACTIONS.get(connector_slug, []):
        if a["action"] == action:
            return a
    return {}
