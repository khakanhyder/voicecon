"""
Integration Action Registry.

Defines available actions per connector with their LLM-compatible parameter schemas.
Vapi-style: each action becomes a tool the AI can call during a live conversation.
"""
from typing import Dict, Any, List

# Schema: connector_slug -> list of actions the AI can invoke
INTEGRATION_ACTIONS: Dict[str, List[Dict[str, Any]]] = {

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
}

# Connector slug → Python class name mapping (mirrors step_handlers.py)
CONNECTOR_CLASS_MAP: Dict[str, str] = {
    "hubspot": "HubSpotConnector",
    "salesforce": "SalesforceConnector",
    "google_calendar": "GoogleCalendarConnector",
    "slack": "SlackConnector",
    "sendgrid": "SendgridConnector",
    "stripe": "StripeConnector",
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
