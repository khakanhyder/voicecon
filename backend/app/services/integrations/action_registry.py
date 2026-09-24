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
        {
            "action": "find_database_items",
            "label": "Find Database Rows",
            "description": "Find rows in a Notion database with the given text in any column (name, email, phone, status...). Returns each row's id, which Update and Archive need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database to search (defaults to the connection's database)",
                                    "title": "Database", "x-resource": "databases"},
                    "query": {"type": "string", "description": "Text to look for, e.g. the caller's name or email"},
                },
                "required": ["database_id", "query"],
            },
        },
        {
            "action": "update_database_item",
            "label": "Update Database Row",
            "description": "Change columns of a database row using plain values, e.g. {\"Status\": \"Done\", \"Due\": \"2026-10-02\"}. Get the row id from Find Database Rows first.",
            "x-snapshot": {"method": "get_page_summary", "args": ["page_id"]},
            "x-scope": [{"param": "database_id", "field": "database_id", "label": "database"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Row id, from Find Database Rows",
                                "title": "Row", "x-runtime": True},
                    "database_id": {"type": "string", "description": "Database the row must be in (defaults to the connection's database)",
                                    "title": "Database", "x-resource": "databases", "x-ui-only": True},
                    "values": {"type": "object", "description": "Columns to change by name, with plain values"},
                },
                "required": ["page_id", "values"],
            },
        },
        {
            "action": "update_page_title",
            "label": "Rename Page",
            "description": "Change the title of a page or database row.",
            "x-snapshot": {"method": "get_page_summary", "args": ["page_id"]},
            "x-scope": [{"param": "database_id", "field": "database_id", "label": "database"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page or row id",
                                "title": "Page", "x-runtime": True},
                    "database_id": {"type": "string", "description": "Database the row must be in (defaults to the connection's database)",
                                    "title": "Database", "x-resource": "databases", "x-ui-only": True},
                    "title": {"type": "string", "description": "New title"},
                },
                "required": ["page_id", "title"],
            },
        },
        {
            "action": "archive_page",
            "label": "Archive Page",
            "description": "Archive (delete) a page or database row. It can be restored from Notion's Trash. Get the id from Find Database Rows or Search first.",
            "x-snapshot": {"method": "get_page_summary", "args": ["page_id"]},
            "x-scope": [{"param": "database_id", "field": "database_id", "label": "database"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page or row id",
                                "title": "Page", "x-runtime": True},
                    "database_id": {"type": "string", "description": "Database the row must be in (defaults to the connection's database)",
                                    "title": "Database", "x-resource": "databases", "x-ui-only": True},
                },
                "required": ["page_id"],
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
        {
            "action": "find_tasks",
            "label": "Find ClickUp Tasks",
            "description": "Find tasks in a list by words in their name or description. Returns each task's id, which Update ClickUp Task needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_id": {"type": "string", "description": "List to search (defaults to the connection's list)",
                                "title": "List"},
                    "query": {"type": "string", "description": "Words to look for, e.g. the caller's name or order number"},
                },
                "required": ["list_id"],
            },
        },
        {
            "action": "update_task",
            "label": "Update ClickUp Task",
            "description": "Change a task's name, description, status, priority or due date. Get the task id from Find ClickUp Tasks first.",
            "x-snapshot": {"method": "get_task", "args": ["task_id"]},
            "x-scope": [{"param": "list_id", "field": "list.id", "label": "list"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Id of the task, from Find ClickUp Tasks",
                                "title": "Task", "x-runtime": True},
                    # Not passed to ClickUp: the task must be on this list.
                    "list_id": {"type": "string", "description": "List the task must be on (defaults to the connection's list)",
                                "title": "List", "x-ui-only": True},
                    "name": {"type": "string", "description": "New task name"},
                    "description": {"type": "string", "description": "New description"},
                    "status": {"type": "string", "description": "New status, exactly as named in ClickUp (e.g. 'in progress', 'complete')"},
                    "priority": {"type": "string", "description": "urgent, high, normal or low"},
                    "due_date": {"type": "string", "description": "New due date, YYYY-MM-DD or ISO 8601"},
                },
                "required": ["task_id"],
            },
        },
        {
            "action": "delete_task",
            "label": "Delete ClickUp Task",
            "description": "Delete a task (ClickUp keeps it in Trash for 30 days). Get the task id from Find ClickUp Tasks first.",
            "x-snapshot": {"method": "get_task", "args": ["task_id"]},
            "x-scope": [{"param": "list_id", "field": "list.id", "label": "list"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Id of the task, from Find ClickUp Tasks",
                                "title": "Task", "x-runtime": True},
                    "list_id": {"type": "string", "description": "List the task must be on (defaults to the connection's list)",
                                "title": "List", "x-ui-only": True},
                },
                "required": ["task_id"],
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
        {
            "action": "find_cards",
            "label": "Find Trello Cards",
            "description": "Find open cards on a board by words in their title or description. Returns each card's id, which Update Trello Card needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "Board to search (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards"},
                    "query": {"type": "string", "description": "Words to look for, e.g. the caller's name"},
                },
                "required": ["board_id"],
            },
        },
        {
            "action": "update_card",
            "label": "Update Trello Card",
            "description": "Rename a card, change its description or due date, or move it to another list. Get the card id from Find Trello Cards first.",
            "x-snapshot": {"method": "get_card", "args": ["card_id"]},
            "x-scope": [{"param": "board_id", "field": "board_id", "label": "board"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Id of the card, from Find Trello Cards",
                                "title": "Card", "x-runtime": True},
                    # Not passed to Trello: the card must be on this board.
                    "board_id": {"type": "string", "description": "Board the card must be on (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards", "x-ui-only": True},
                    "name": {"type": "string", "description": "New card title"},
                    "description": {"type": "string", "description": "New description"},
                    "due": {"type": "string", "description": "New due date, ISO 8601"},
                    "move_to_list_id": {"type": "string", "description": "Id of the list to move the card to (from the card's board)"},
                },
                "required": ["card_id"],
            },
        },
        {
            "action": "archive_card",
            "label": "Archive Trello Card",
            "description": "Archive a card; it can be restored from the board's archive. Get the card id from Find Trello Cards first.",
            "x-snapshot": {"method": "get_card", "args": ["card_id"]},
            "x-scope": [{"param": "board_id", "field": "board_id", "label": "board"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "Id of the card, from Find Trello Cards",
                                "title": "Card", "x-runtime": True},
                    "board_id": {"type": "string", "description": "Board the card must be on (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards", "x-ui-only": True},
                },
                "required": ["card_id"],
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
            "description": "Update an existing HubSpot contact's details. Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "HubSpot contact ID, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                    "email": {"type": "string", "description": "New email address"},
                    "first_name": {"type": "string", "description": "New first name"},
                    "last_name": {"type": "string", "description": "New last name"},
                    "phone": {"type": "string", "description": "New phone number"},
                    "company": {"type": "string", "description": "New company name"},
                    "additional_properties": {"type": "object", "description": "Other HubSpot properties to update, by internal name"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "delete_contact",
            "label": "Delete Contact",
            "description": "Delete a HubSpot contact (HubSpot keeps it restorable for 90 days). Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "HubSpot contact ID, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "search_deals",
            "label": "Find Deals",
            "description": "Find deals by name or other text. Returns each deal's id, which Update Deal needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for, e.g. the deal or company name"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "update_deal",
            "label": "Update Deal",
            "description": "Change a deal's name, stage, amount or close date. Get the deal id from Find Deals first.",
            "x-snapshot": {"method": "get_deal", "args": ["deal_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "HubSpot deal ID, from Find Deals",
                                "title": "Deal", "x-runtime": True},
                    "deal_name": {"type": "string", "description": "New deal name"},
                    "stage": {"type": "string", "description": "New deal stage id (e.g. appointmentscheduled, qualifiedtobuy, closedwon)"},
                    "amount": {"type": "number", "description": "New deal amount"},
                    "close_date": {"type": "string", "description": "New expected close date, YYYY-MM-DD"},
                    "additional_properties": {"type": "object", "description": "Other HubSpot deal properties, by internal name"},
                },
                "required": ["deal_id"],
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
        {
            "action": "search_leads",
            "label": "Search Leads",
            "description": "Find leads by name, email, phone or company. Returns each lead's Id, which Update Lead needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name, email, phone or company to search for"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "update_contact",
            "label": "Update Contact",
            "description": "Change an existing contact's details. Get the contact Id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Salesforce contact Id, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                    "first_name": {"type": "string", "description": "New first name"},
                    "last_name": {"type": "string", "description": "New last name"},
                    "email": {"type": "string", "description": "New email address"},
                    "phone": {"type": "string", "description": "New phone number"},
                    "title": {"type": "string", "description": "New job title"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "update_lead",
            "label": "Update Lead",
            "description": "Change an existing lead's details or status. Get the lead Id from Search Leads first.",
            "x-snapshot": {"method": "get_lead", "args": ["lead_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "Salesforce lead Id, from Search Leads",
                                "title": "Lead", "x-runtime": True},
                    "first_name": {"type": "string", "description": "New first name"},
                    "last_name": {"type": "string", "description": "New last name"},
                    "email": {"type": "string", "description": "New email address"},
                    "phone": {"type": "string", "description": "New phone number"},
                    "company": {"type": "string", "description": "New company name"},
                    "status": {"type": "string", "description": "New lead status, exactly as named in Salesforce (e.g. 'Working - Contacted')"},
                },
                "required": ["lead_id"],
            },
        },
        {
            "action": "delete_contact",
            "label": "Delete Contact",
            "description": "Delete a Salesforce contact (it goes to the Recycle Bin). Get the contact Id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Salesforce contact Id, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                },
                "required": ["contact_id"],
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
                    "time_zone": {"type": "string", "description": "Business time zone, e.g. Asia/Karachi. Opening hours and returned times use it"},
                    "day_start": {"type": "string", "description": "Opening time, HH:MM in the business time zone (default 00:00)"},
                    "day_end": {"type": "string", "description": "Closing time, HH:MM; the last slot ends by then (default 23:59)"},
                    "step_minutes": {"type": "integer", "description": "Gap between slot start times in minutes (default 30; 60 gives on-the-hour slots)"},
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
                    "time_zone": {"type": "string", "description": "Time zone for the returned times, e.g. Asia/Karachi (defaults to the calendar's zone)"},
                    # Declared so the connection's default calendar applies here
                    # too. Without it, bookings went to the default calendar
                    # while availability read "primary", so a slot that had
                    # just been booked still showed as free.
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to the connection's calendar)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["start_date"],
            },
        },
        {
            # The lookup half of reschedule/cancel: those need an event id, and
            # the agent must get it from here rather than guess one.
            "action": "find_events",
            "label": "Find Appointments",
            "description": (
                "Find existing appointments that mention the caller, e.g. by their email, "
                "phone number or name. Returns each event's id, which Reschedule Appointment "
                "and Cancel Appointment need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for: the caller's email, phone number or name"},
                    "start_date": {"type": "string", "description": "Search from this date, YYYY-MM-DD (default: today)"},
                    "end_date": {"type": "string", "description": "Search up to this date, YYYY-MM-DD (default: 90 days ahead)"},
                    "time_zone": {"type": "string", "description": "Time zone for the returned times, e.g. Asia/Karachi"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to the connection's calendar)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "update_event",
            "operation": "update",
            "label": "Reschedule Appointment",
            "description": (
                "Move an existing appointment to a new time, or change its title or notes. "
                "Get the event id from Find Appointments first. Attendees, location and the "
                "meeting link are kept."
            ),
            # Loaded before the change so the audit log records what it was.
            "x-snapshot": {"method": "get_event", "args": ["event_id", "calendar_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Id of the appointment, from Find Appointments"},
                    "start_time": {"type": "string", "description": "New start time in ISO 8601 format"},
                    "end_time": {"type": "string", "description": "New end time in ISO 8601 format (default: keeps the current length)"},
                    "time_zone": {"type": "string", "description": "Time zone of the new times if they carry no offset, e.g. Asia/Karachi (default: the appointment's own)"},
                    "title": {"type": "string", "description": "New title (leave out to keep it)"},
                    "description": {"type": "string", "description": "New notes (leave out to keep them)"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to the connection's calendar)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["event_id"],
            },
        },
        {
            "action": "delete_event",
            "operation": "delete",
            "label": "Cancel Appointment",
            "description": (
                "Cancel an existing appointment. Get the event id from Find Appointments first. "
                "Attendees are emailed the cancellation."
            ),
            "x-snapshot": {"method": "get_event", "args": ["event_id", "calendar_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Id of the appointment, from Find Appointments"},
                    "calendar_id": {"type": "string", "description": "Calendar ID (defaults to the connection's calendar)",
                                    "title": "Calendar", "x-resource": "calendars"},
                },
                "required": ["event_id"],
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
        {
            "action": "update_message",
            "label": "Edit Message",
            "description": "Edit a message this agent posted earlier in the call (Slack only allows editing the app's own messages). Use the ts returned by Send Message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel the message is in (defaults to the connection's channel)",
                                "title": "Channel", "x-resource": "channels"},
                    "ts": {"type": "string", "description": "The message's ts, from Send Message"},
                    "message": {"type": "string", "description": "New message text"},
                },
                "required": ["channel", "ts", "message"],
            },
        },
        {
            "action": "delete_message",
            "label": "Delete Message",
            "description": "Delete a message this agent posted earlier in the call. Use the ts returned by Send Message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel the message is in (defaults to the connection's channel)",
                                "title": "Channel", "x-resource": "channels"},
                    "ts": {"type": "string", "description": "The message's ts, from Send Message"},
                },
                "required": ["channel", "ts"],
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
        {
            "action": "find_contact",
            "label": "Find Contact",
            "description": "Look up a marketing contact by email. Returns the contact id, which the other contact actions need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Contact's email address"},
                },
                "required": ["email"],
            },
        },
        {
            "action": "add_contact",
            "operation": "update",
            "label": "Add or Update Contact",
            "description": "Add a contact to your marketing contacts, or update their name if the email already exists, and optionally put them on a list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Contact's email address"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "list_id": {"type": "string", "description": "List to add them to (defaults to the connection's list)",
                                "title": "Contact list", "x-resource": "lists"},
                },
                "required": ["email"],
            },
        },
        {
            "action": "remove_contact_from_list",
            "label": "Remove From List",
            "description": "Take a contact off a list, e.g. a caller who no longer wants those emails. The contact is kept. Get the contact id from Find Contact first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "list_id": {"type": "string", "description": "List (defaults to the connection's list)",
                                "title": "Contact list", "x-resource": "lists"},
                    "contact_id": {"type": "string", "description": "SendGrid contact id, from Find Contact"},
                },
                "required": ["list_id", "contact_id"],
            },
        },
        {
            "action": "delete_contact",
            "label": "Delete Contact",
            "description": "Delete a marketing contact entirely. Get the contact id from Find Contact first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "SendGrid contact id, from Find Contact"},
                },
                "required": ["contact_id"],
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
        {
            "action": "find_customers",
            "label": "Find Customer",
            "description": "Find Stripe customers by email. Returns each customer's id, which the other Stripe actions need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer's email address"},
                },
                "required": ["email"],
            },
        },
        {
            "action": "update_customer",
            "label": "Update Customer",
            "description": "Change a customer's name, email, phone or description. Get the customer id from Find Customer first.",
            "x-snapshot": {"method": "get_customer", "args": ["customer_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Stripe customer id (cus_...), from Find Customer"},
                    "name": {"type": "string", "description": "New name"},
                    "email": {"type": "string", "description": "New email address"},
                    "phone": {"type": "string", "description": "New phone number"},
                    "description": {"type": "string", "description": "New description"},
                },
                "required": ["customer_id"],
            },
        },
        {
            "action": "list_subscriptions",
            "label": "List Subscriptions",
            "description": "List a customer's subscriptions. Returns each subscription's id, which Cancel Subscription needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Stripe customer id (cus_...), from Find Customer"},
                    "status": {"type": "string", "enum": ["active", "trialing", "past_due", "all"], "description": "Which subscriptions to list (default active)"},
                },
                "required": ["customer_id"],
            },
        },
        {
            "action": "cancel_subscription",
            "label": "Cancel Subscription",
            "description": "Cancel a customer's subscription, by default at the end of the period they have paid for. Get the subscription id from List Subscriptions first.",
            "x-snapshot": {"method": "get_subscription", "args": ["subscription_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string", "description": "Stripe subscription id (sub_...), from List Subscriptions"},
                    "immediately": {"type": "boolean", "description": "End it now instead of at the end of the paid period (default false)"},
                },
                "required": ["subscription_id"],
            },
        },
        {
            "action": "cancel_payment_intent",
            "label": "Cancel Payment",
            "description": "Cancel a payment that has not been captured yet, e.g. one created earlier in this call.",
            "x-snapshot": {"method": "get_payment_intent", "args": ["intent_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "intent_id": {"type": "string", "description": "Payment intent id (pi_...)"},
                },
                "required": ["intent_id"],
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
        {
            "action": "find_records",
            "label": "Find Records",
            "description": "Find records in a table where a field matches a value, e.g. Email is the caller's email. Returns each record's id, which Update Record needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                    "field": {"type": "string", "description": "Field (column) to search, e.g. Email or Phone"},
                    "value": {"type": "string", "description": "Value to look for"},
                    "match": {"type": "string", "enum": ["exact", "contains"], "description": "exact (default, ignores case) or contains"},
                },
                "required": ["table_name", "field", "value"],
            },
        },
        {
            "action": "update_record",
            "label": "Update Record",
            "description": "Change fields on an existing record. Only the fields given are changed. Get the record id from Find Records first.",
            "x-snapshot": {"method": "get_record", "args": ["table_name", "record_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                    "record_id": {"type": "string", "description": "Id of the record (starts with 'rec'), from Find Records"},
                    "fields": {"type": "object", "description": "Fields to change, e.g. {\"Status\": \"Booked\"}"},
                },
                "required": ["table_name", "record_id", "fields"],
            },
        },
        {
            "action": "delete_record",
            "label": "Delete Record",
            "description": "Delete a record. Get the record id from Find Records first.",
            "x-snapshot": {"method": "get_record", "args": ["table_name", "record_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                    "record_id": {"type": "string", "description": "Id of the record (starts with 'rec'), from Find Records"},
                },
                "required": ["table_name", "record_id"],
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
        {
            "action": "search_contacts",
            "label": "Search Contacts",
            "description": "Find contacts by name, email or phone. Returns each contact's id, which the other GoHighLevel actions need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name, email or phone to search for"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "update_contact",
            "label": "Update Contact",
            "description": "Change an existing contact's name, email, phone or company. Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "GoHighLevel contact id, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                    "first_name": {"type": "string", "description": "New first name"},
                    "last_name": {"type": "string", "description": "New last name"},
                    "email": {"type": "string", "description": "New email address"},
                    "phone": {"type": "string", "description": "New phone number"},
                    "company_name": {"type": "string", "description": "New company name"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "book_appointment",
            "label": "Book Appointment",
            "description": "Book an appointment on a GoHighLevel calendar for a contact. Get the contact id from Search Contacts (or Create Contact) first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "description": "Calendar to book on",
                                    "title": "Calendar", "x-resource": "calendars"},
                    "contact_id": {"type": "string", "description": "Contact id the appointment is for"},
                    "start_time": {"type": "string", "description": "Start time in ISO 8601 format"},
                    "end_time": {"type": "string", "description": "End time in ISO 8601 format"},
                    "title": {"type": "string", "description": "Appointment title"},
                },
                "required": ["calendar_id", "contact_id", "start_time", "end_time"],
            },
        },
        {
            "action": "create_opportunity",
            "label": "Create Opportunity",
            "description": "Add an opportunity to a pipeline for a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "Pipeline (defaults to the connection's pipeline)",
                                    "title": "Pipeline", "x-resource": "pipelines"},
                    "title": {"type": "string", "description": "Opportunity title"},
                    "stage": {"type": "string", "description": "Stage name, e.g. 'New Lead' (default: the pipeline's first stage)"},
                    "contact_id": {"type": "string", "description": "Contact id the opportunity is for"},
                    "monetary_value": {"type": "number", "description": "Value of the opportunity"},
                },
                "required": ["pipeline_id", "title"],
            },
        },
        {
            "action": "delete_contact",
            "label": "Delete Contact",
            "description": "Delete a contact. Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "GoHighLevel contact id, from Search Contacts",
                                   "title": "Contact", "x-runtime": True},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "find_appointments",
            "label": "Find Appointments",
            "description": "List a contact's appointments. Returns each appointment's id, which Reschedule and Cancel Appointment need. Get the contact id from Search Contacts first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "GoHighLevel contact id, from Search Contacts"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "reschedule_appointment",
            "operation": "update",
            "label": "Reschedule Appointment",
            "description": "Move an appointment to a new start time; it keeps its length. Get the appointment id from Find Appointments first.",
            "x-snapshot": {"method": "get_appointment", "args": ["appointment_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment id, from Find Appointments"},
                    "start_time": {"type": "string", "description": "New start time in ISO 8601 format"},
                    "time_zone": {"type": "string", "description": "Time zone of the new time, e.g. America/New_York"},
                },
                "required": ["appointment_id", "start_time"],
            },
        },
        {
            "action": "cancel_appointment",
            "label": "Cancel Appointment",
            "description": "Mark an appointment as cancelled. Get the appointment id from Find Appointments first.",
            "x-snapshot": {"method": "get_appointment", "args": ["appointment_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment id, from Find Appointments"},
                },
                "required": ["appointment_id"],
            },
        },
        {
            "action": "find_opportunities",
            "label": "Find Opportunities",
            "description": "Find opportunities in a pipeline by contact name, email or phone. Returns each opportunity's id, which Update Opportunity needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "Pipeline (defaults to the connection's pipeline)",
                                    "title": "Pipeline", "x-resource": "pipelines"},
                    "query": {"type": "string", "description": "Name, email or phone to search for"},
                },
                "required": ["pipeline_id", "query"],
            },
        },
        {
            "action": "update_opportunity",
            "label": "Update Opportunity",
            "description": "Move an opportunity to another stage (by name), mark it won or lost, or change its title or value. Get the opportunity id from Find Opportunities first.",
            "x-snapshot": {"method": "get_opportunity", "args": ["pipeline_id", "opportunity_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string", "description": "Pipeline (defaults to the connection's pipeline)",
                                    "title": "Pipeline", "x-resource": "pipelines"},
                    "opportunity_id": {"type": "string", "description": "Opportunity id, from Find Opportunities"},
                    "stage": {"type": "string", "description": "New stage name, e.g. 'Booked'"},
                    "status": {"type": "string", "enum": ["open", "won", "lost", "abandoned"], "description": "New status"},
                    "title": {"type": "string", "description": "New title"},
                    "monetary_value": {"type": "number", "description": "New value"},
                },
                "required": ["pipeline_id", "opportunity_id"],
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
        {
            "action": "find_events",
            "label": "Find Caller's Bookings",
            "description": "Find the caller's upcoming Calendly bookings by their email. Each result has the event id Cancel Booking needs, and a reschedule link you can offer the caller (Calendly cannot move a booking directly).",
            "parameters": {
                "type": "object",
                "properties": {
                    "invitee_email": {"type": "string", "description": "The caller's email address"},
                },
                "required": ["invitee_email"],
            },
        },
        {
            "action": "cancel_event",
            "label": "Cancel Booking",
            "description": "Cancel a Calendly booking; Calendly notifies the invitee. Get the event id from Find Caller's Bookings first.",
            "x-snapshot": {"method": "get_event_details", "args": ["event_uuid"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "event_uuid": {"type": "string", "description": "Event id, from Find Caller's Bookings"},
                    "reason": {"type": "string", "description": "Reason, shared with the invitee"},
                },
                "required": ["event_uuid"],
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
        {
            "action": "find_rows",
            "label": "Find Rows",
            "description": "Find rows where a column matches a value, e.g. Phone is the caller's number. The first row of the sheet must hold the column names. Phone numbers match however they are formatted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet (defaults to the connection's spreadsheet)",
                                       "title": "Spreadsheet", "x-resource": "spreadsheets"},
                    "sheet": {"type": "string", "description": "Tab name (default: the first tab)"},
                    "column": {"type": "string", "description": "Column to search, by its header, e.g. Phone or Email"},
                    "value": {"type": "string", "description": "Value to look for"},
                    "match": {"type": "string", "enum": ["exact", "contains"], "description": "exact (default, ignores case) or contains"},
                },
                "required": ["spreadsheet_id", "column", "value"],
            },
        },
        {
            "action": "update_row",
            "label": "Update Row",
            "description": "Change cells in the row where a column matches a value (e.g. set Status to Cancelled where Phone is the caller's number). Other cells are kept. If several rows match, give the row number from Find Rows.",
            "x-snapshot": {"method": "get_row", "args": ["spreadsheet_id", "sheet", "row_number", "column", "value"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet (defaults to the connection's spreadsheet)",
                                       "title": "Spreadsheet", "x-resource": "spreadsheets"},
                    "sheet": {"type": "string", "description": "Tab name (default: the first tab)"},
                    "column": {"type": "string", "description": "Column to match on, by its header, e.g. Phone or Email"},
                    "value": {"type": "string", "description": "Value that identifies the row, e.g. the caller's phone number"},
                    "row_number": {"type": "integer", "description": "Row number from Find Rows, if several rows match (checked against the column and value)"},
                    "values": {"type": "object", "description": "Cells to change by column name, e.g. {\"Status\": \"Cancelled\"}"},
                },
                "required": ["spreadsheet_id", "column", "value", "values"],
            },
        },
        {
            "action": "upsert_row",
            "operation": "update",
            "label": "Add or Update Row",
            "description": "Update the row where a column matches a value, or add a new row if there is none. Use for 'save this caller's details' when they may already be in the sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet (defaults to the connection's spreadsheet)",
                                       "title": "Spreadsheet", "x-resource": "spreadsheets"},
                    "sheet": {"type": "string", "description": "Tab name (default: the first tab)"},
                    "column": {"type": "string", "description": "Column that identifies the row, e.g. Phone or Email"},
                    "value": {"type": "string", "description": "Value that identifies the row"},
                    "values": {"type": "object", "description": "Cells to set by column name, e.g. {\"Name\": \"Sara\", \"Status\": \"Booked\"}"},
                },
                "required": ["spreadsheet_id", "column", "value", "values"],
            },
        },
        {
            "action": "delete_row",
            "label": "Delete Row",
            "description": "Delete the row where a column matches a value. The rows below move up. If several rows match, give the row number from Find Rows.",
            "x-snapshot": {"method": "get_row", "args": ["spreadsheet_id", "sheet", "row_number", "column", "value"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet (defaults to the connection's spreadsheet)",
                                       "title": "Spreadsheet", "x-resource": "spreadsheets"},
                    "sheet": {"type": "string", "description": "Tab name (default: the first tab)"},
                    "column": {"type": "string", "description": "Column to match on, by its header, e.g. Phone or Email"},
                    "value": {"type": "string", "description": "Value that identifies the row, e.g. the caller's phone number"},
                    "row_number": {"type": "integer", "description": "Row number from Find Rows, if several rows match (checked against the column and value)"},
                },
                "required": ["spreadsheet_id", "column", "value"],
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
        {
            "action": "find_bookings",
            "label": "Find Bookings",
            "description": "Find the caller's upcoming bookings by their email or name. Returns each booking's id, which Reschedule and Cancel Booking need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attendee": {"type": "string", "description": "The caller's email address or name"},
                },
                "required": ["attendee"],
            },
        },
        {
            "action": "reschedule_booking",
            "operation": "update",
            "label": "Reschedule Booking",
            "description": "Move a booking to a new time; without an end time it keeps its length. Get the booking id from Find Bookings first.",
            "x-snapshot": {"method": "get_booking", "args": ["booking_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer", "description": "Booking id, from Find Bookings"},
                    "start_time": {"type": "string", "description": "New start time in ISO 8601 format"},
                    "end_time": {"type": "string", "description": "New end time (default: keeps the current length)"},
                },
                "required": ["booking_id", "start_time"],
            },
        },
        {
            "action": "cancel_booking",
            "label": "Cancel Booking",
            "description": "Cancel a booking; Cal.com emails the attendees. Get the booking id from Find Bookings first.",
            "x-snapshot": {"method": "get_booking", "args": ["booking_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer", "description": "Booking id, from Find Bookings"},
                    "reason": {"type": "string", "description": "Reason, shared with the attendees"},
                },
                "required": ["booking_id"],
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
        {
            "action": "find_items",
            "label": "Find Items",
            "description": "Find items on a board with the given text in their name or any column. Returns each item's id, which Update and Archive Item need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "Board (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards"},
                    "query": {"type": "string", "description": "Text to look for, e.g. the caller's name or phone"},
                },
                "required": ["board_id", "query"],
            },
        },
        {
            "action": "create_item",
            "label": "Create Item",
            "description": "Add an item to a board, filling columns by their titles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "Board (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards"},
                    "item_name": {"type": "string", "description": "Item name"},
                    "values": {"type": "object", "description": "Columns by title, e.g. {\"Status\": \"New\", \"Phone\": \"+923001234567\"}"},
                },
                "required": ["board_id", "item_name"],
            },
        },
        {
            "action": "update_item",
            "label": "Update Item",
            "description": "Change an item's columns (by title) or its name. Get the item id from Find Items first.",
            "x-snapshot": {"method": "get_item", "args": ["item_id"]},
            "x-scope": [{"param": "board_id", "field": "board_id", "label": "board"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "Board (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards"},
                    "item_id": {"type": "string", "description": "Item id, from Find Items"},
                    "values": {"type": "object", "description": "Columns to change by title, e.g. {\"Status\": \"Done\"}"},
                    "item_name": {"type": "string", "description": "New item name"},
                },
                "required": ["board_id", "item_id"],
            },
        },
        {
            "action": "archive_item",
            "label": "Archive Item",
            "description": "Archive an item (restorable from the board's archive for 30 days). Get the item id from Find Items first.",
            "x-snapshot": {"method": "get_item", "args": ["item_id"]},
            "x-scope": [{"param": "board_id", "field": "board_id", "label": "board"}],
            "parameters": {
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "Board the item must be on (defaults to the connection's board)",
                                 "title": "Board", "x-resource": "boards", "x-ui-only": True},
                    "item_id": {"type": "string", "description": "Item id, from Find Items"},
                },
                "required": ["item_id"],
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
        {
            "action": "update_person",
            "label": "Update Person",
            "description": "Change a person's name, email or phone. Get the person id from Search Persons first.",
            "x-snapshot": {"method": "get_person", "args": ["person_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "integer", "description": "Person id, from Search Persons"},
                    "name": {"type": "string", "description": "New name"},
                    "email": {"type": "string", "description": "New email (becomes the primary email)"},
                    "phone": {"type": "string", "description": "New phone (becomes the primary phone)"},
                },
                "required": ["person_id"],
            },
        },
        {
            "action": "delete_person",
            "label": "Delete Person",
            "description": "Delete a person (restorable in Pipedrive for 30 days). Get the person id from Search Persons first.",
            "x-snapshot": {"method": "get_person", "args": ["person_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "integer", "description": "Person id, from Search Persons"},
                },
                "required": ["person_id"],
            },
        },
        {
            "action": "search_deals",
            "label": "Find Deals",
            "description": "Find deals by title, person or organisation. Returns each deal's id, which Update and Delete Deal need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for"},
                },
                "required": ["query"],
            },
        },
        {
            "action": "update_deal",
            "label": "Update Deal",
            "description": "Change a deal's title or value, move it to a stage (by name), or mark it won or lost. Get the deal id from Find Deals first.",
            "x-snapshot": {"method": "get_deal", "args": ["deal_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "integer", "description": "Deal id, from Find Deals"},
                    "title": {"type": "string", "description": "New title"},
                    "value": {"type": "number", "description": "New value"},
                    "stage": {"type": "string", "description": "Stage name to move the deal to, e.g. 'Proposal Made'"},
                    "status": {"type": "string", "enum": ["open", "won", "lost"], "description": "New status"},
                    "lost_reason": {"type": "string", "description": "Why the deal was lost (with status lost)"},
                },
                "required": ["deal_id"],
            },
        },
        {
            "action": "delete_deal",
            "label": "Delete Deal",
            "description": "Delete a deal (restorable in Pipedrive for 30 days). Get the deal id from Find Deals first.",
            "x-snapshot": {"method": "get_deal", "args": ["deal_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "integer", "description": "Deal id, from Find Deals"},
                },
                "required": ["deal_id"],
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
        {
            "action": "update_ticket",
            "label": "Update Ticket",
            "description": "Change a ticket's status (open, pending, hold, solved), priority or subject, add tags, and optionally leave a note. Get the ticket id from Search Tickets first.",
            "x-snapshot": {"method": "get_ticket", "args": ["ticket_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "integer", "description": "Ticket number, from Search Tickets"},
                    "status": {"type": "string", "enum": ["open", "pending", "hold", "solved"], "description": "New status"},
                    "priority": {"type": "string", "enum": ["urgent", "high", "normal", "low"], "description": "New priority"},
                    "subject": {"type": "string", "description": "New subject"},
                    "add_tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to add"},
                    "comment": {"type": "string", "description": "Note explaining the change"},
                    "public": {"type": "boolean", "description": "Show the note to the customer (default: internal only)"},
                },
                "required": ["ticket_id"],
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
        {
            "action": "update_contact",
            "label": "Update Contact",
            "description": "Change a contact's name, email or phone. Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Intercom contact id, from Search Contacts"},
                    "name": {"type": "string", "description": "New name"},
                    "email": {"type": "string", "description": "New email address"},
                    "phone": {"type": "string", "description": "New phone number"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "archive_contact",
            "label": "Archive Contact",
            "description": "Archive a contact (Intercom can unarchive it). Get the contact id from Search Contacts first.",
            "x-snapshot": {"method": "get_contact", "args": ["contact_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Intercom contact id, from Search Contacts"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "find_conversations",
            "label": "Find Conversations",
            "description": "List a contact's conversations (open ones by default). Returns each conversation's id, which Close Conversation needs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Intercom contact id, from Search Contacts"},
                    "state": {"type": "string", "enum": ["open", "closed", "snoozed", "all"], "description": "Which conversations (default open)"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "action": "close_conversation",
            "operation": "update",
            "label": "Close Conversation",
            "description": "Close a conversation, e.g. once the caller's issue is resolved on the call. Get the conversation id from Find Conversations first.",
            "x-snapshot": {"method": "get_conversation", "args": ["conversation_id"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string", "description": "Conversation id, from Find Conversations"},
                    "note": {"type": "string", "description": "Closing note"},
                },
                "required": ["conversation_id"],
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
                    "table_name": {"type": "string", "description": "Table name (defaults to the connection's table)",
                                   "title": "Table", "x-resource": "tables"},
                    "limit": {"type": "integer", "description": "Max rows to fetch"},
                },
                "required": ["table_name"],
            },
        },
        {
            "action": "find_rows",
            "label": "Find Rows",
            "description": "Find rows where a column equals a value, e.g. phone is the caller's number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table (defaults to the connection's table)",
                                   "title": "Table", "x-resource": "tables"},
                    "column": {"type": "string", "description": "Column to match, e.g. phone or email"},
                    "value": {"type": "string", "description": "Value to look for"},
                },
                "required": ["table_name", "column", "value"],
            },
        },
        {
            "action": "insert_row",
            "label": "Insert Row",
            "description": "Add a row to the table.",
            "x-requires-default": ["table_name"],
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table (defaults to the connection's table)",
                                   "title": "Table", "x-resource": "tables"},
                    "values": {"type": "object", "description": "Columns to set, e.g. {\"name\": \"Sara\"}"},
                },
                "required": ["table_name", "values"],
            },
        },
        {
            "action": "update_row",
            "label": "Update Row",
            "description": "Change columns of the one row where a column equals a value. Refused if more than one row matches.",
            "x-requires-default": ["table_name"],
            "x-snapshot": {"method": "get_row", "args": ["table_name", "column", "value"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table (defaults to the connection's table)",
                                   "title": "Table", "x-resource": "tables"},
                    "column": {"type": "string", "description": "Column that identifies the row, ideally a unique one such as id, email or phone"},
                    "value": {"type": "string", "description": "Value of that column for the row"},
                    "values": {"type": "object", "description": "Columns to change, e.g. {\"status\": \"cancelled\"}"},
                },
                "required": ["table_name", "column", "value", "values"],
            },
        },
        {
            "action": "delete_row",
            "label": "Delete Row",
            "description": "Delete the one row where a column equals a value. Refused if more than one row matches.",
            "x-requires-default": ["table_name"],
            "x-snapshot": {"method": "get_row", "args": ["table_name", "column", "value"]},
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table (defaults to the connection's table)",
                                   "title": "Table", "x-resource": "tables"},
                    "column": {"type": "string", "description": "Column that identifies the row, ideally a unique one such as id, email or phone"},
                    "value": {"type": "string", "description": "Value of that column for the row"},
                },
                "required": ["table_name", "column", "value"],
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
    if day and any(p.get(k) for k in ("time_zone", "day_start", "day_end")):
        # Opening hours are local to the business, so the connector builds the
        # window in its zone — and can report a mistyped zone clearly, which
        # an exception raised here could not.
        date_part = str(day).strip()[:10]
        p.setdefault("search_start", date_part)
        p.setdefault("search_end", date_part)
    elif day:
        p.setdefault("search_start", _as_iso(day))
        p.setdefault("search_end", _as_iso(day, end_of_day=True))
    return p


def _adapt_gcal_find_events(p: Dict[str, Any]) -> Dict[str, Any]:
    if "start_date" in p:
        p.setdefault("time_min", _as_iso(p.pop("start_date")))
    if "end_date" in p:
        p.setdefault("time_max", _as_iso(p.pop("end_date"), end_of_day=True))
    return p


def _adapt_gcal_update_event(p: Dict[str, Any]) -> Dict[str, Any]:
    if "title" in p:
        p.setdefault("summary", p.pop("title"))
    if "time_zone" in p:
        p.setdefault("timezone", p.pop("time_zone"))
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
    for schema_name, hubspot_property in (
        ("phone", "phone"), ("company", "company"), ("email", "email"),
        ("first_name", "firstname"), ("last_name", "lastname"),
    ):
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


def _adapt_hubspot_update_deal(p: Dict[str, Any]) -> Dict[str, Any]:
    """Fold the flat deal fields into HubSpot's property bag."""
    supplied = p.pop("additional_properties", None)
    properties = dict(supplied) if isinstance(supplied, dict) else {}
    for schema_name, hubspot_property in (
        ("deal_name", "dealname"), ("stage", "dealstage"), ("amount", "amount"), ("close_date", "closedate"),
    ):
        if p.get(schema_name) not in (None, ""):
            properties[hubspot_property] = p.pop(schema_name)
        else:
            p.pop(schema_name, None)
    p["properties"] = properties
    return p


def _salesforce_fields(p: Dict[str, Any], mapping) -> Dict[str, Any]:
    fields = {}
    for schema_name, sf_field in mapping:
        value = p.pop(schema_name, None)
        if value not in (None, ""):
            fields[sf_field] = value
    p["fields"] = fields
    return p


def _adapt_salesforce_update_contact(p: Dict[str, Any]) -> Dict[str, Any]:
    return _salesforce_fields(p, (("first_name", "FirstName"), ("last_name", "LastName"), ("email", "Email"),
                                  ("phone", "Phone"), ("title", "Title")))


def _adapt_salesforce_update_lead(p: Dict[str, Any]) -> Dict[str, Any]:
    return _salesforce_fields(p, (("first_name", "FirstName"), ("last_name", "LastName"), ("email", "Email"),
                                  ("phone", "Phone"), ("company", "Company"), ("status", "Status")))


def _adapt_ghl_create_opportunity(p: Dict[str, Any]) -> Dict[str, Any]:
    if "stage" in p:
        p.setdefault("stage_id", p.pop("stage"))
    return p


def _adapt_slack_update_message(p: Dict[str, Any]) -> Dict[str, Any]:
    if "message" in p:
        p.setdefault("text", p.pop("message"))
    return p


def _adapt_sendgrid_add_contact(p: Dict[str, Any]) -> Dict[str, Any]:
    list_id = p.pop("list_id", None)
    if list_id:
        p.setdefault("list_ids", [list_id])
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
    ("google-calendar", "find_events"): _adapt_gcal_find_events,
    ("google_calendar", "find_events"): _adapt_gcal_find_events,
    ("google-calendar", "update_event"): _adapt_gcal_update_event,
    ("google_calendar", "update_event"): _adapt_gcal_update_event,
    ("slack", "send_message"): _adapt_slack_send_message,
    ("sendgrid", "send_email"): _adapt_sendgrid_send_email,
    ("hubspot", "update_contact"): _adapt_hubspot_update_contact,
    ("hubspot", "create_deal"): _adapt_hubspot_create_deal,
    ("salesforce", "create_contact"): _adapt_salesforce_create_contact,
    ("salesforce", "create_lead"): _adapt_salesforce_create_lead,
    ("hubspot", "update_deal"): _adapt_hubspot_update_deal,
    ("salesforce", "update_contact"): _adapt_salesforce_update_contact,
    ("salesforce", "update_lead"): _adapt_salesforce_update_lead,
    ("gohighlevel", "create_opportunity"): _adapt_ghl_create_opportunity,
    ("slack", "update_message"): _adapt_slack_update_message,
    ("sendgrid", "add_contact"): _adapt_sendgrid_add_contact,
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
    """Return the list of available actions for a given connector.

    Each carries its ``operation`` and ``destructive`` flag, so the Tools page
    and the workflow builder can group actions and warn before a delete.
    """
    return [
        {**a, "operation": operation_of(a), "destructive": is_destructive(a)}
        for a in INTEGRATION_ACTIONS.get(connector_slug, [])
    ]


# ---- What an action does to the data in the connected app ----
#
# Agents may create and read freely. Changing or removing a record that already
# exists is different: it happens mid-call on the strength of what an LLM heard,
# so update and delete actions carry extra rules (see action_runner). The
# operation is declared on the action where it matters and otherwise inferred
# from the method name, which is consistent across the connectors.

OP_CREATE = "create"
OP_READ = "read"
OP_UPDATE = "update"
OP_DELETE = "delete"

_READ_PREFIXES = ("search", "list_", "get_", "find_", "check_", "fetch_", "query", "lookup", "generate_presigned")
_UPDATE_PREFIXES = ("update_",)
_DELETE_PREFIXES = ("delete_", "cancel_", "archive_", "remove_")


def operation_of(action_def: Dict[str, Any]) -> str:
    """``create``, ``read``, ``update`` or ``delete`` for a registry entry."""
    declared = action_def.get("operation")
    if declared in (OP_CREATE, OP_READ, OP_UPDATE, OP_DELETE):
        return declared
    name = str(action_def.get("action") or "")
    if name.startswith(_DELETE_PREFIXES):
        return OP_DELETE
    if name.startswith(_UPDATE_PREFIXES):
        return OP_UPDATE
    if name.startswith(_READ_PREFIXES):
        return OP_READ
    return OP_CREATE


def is_destructive(action_def: Dict[str, Any]) -> bool:
    """Deletes, and anything explicitly marked ``destructive``."""
    return bool(action_def.get("destructive")) or operation_of(action_def) == OP_DELETE


def changes_existing_data(action_def: Dict[str, Any]) -> bool:
    """Update and delete: the actions an agent must confirm with the caller."""
    return operation_of(action_def) in (OP_UPDATE, OP_DELETE)


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
