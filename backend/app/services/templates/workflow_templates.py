"""
Pre-built workflow templates.

Each template's ``workflow_definition`` is a real v2 graph — the same
``{schema_version, nodes, edges}`` shape the visual builder saves and
``WorkflowExecutor`` runs. Installing one produces a workflow that opens in the
builder and executes, rather than a description of one.

That is a deliberate constraint, and the reason this file is short. An earlier
version carried ten templates written in an invented schema
(``{trigger, conditions, actions}`` with step types like ``extract_data`` and
``salesforce_create_lead``) that no handler implemented, alongside triggers
(``intent.detected``, ``lead.captured``) that are not trigger types and
integrations (Zendesk, Shopify, Twilio, Mailgun) the platform has no connector
for. None of it could run; none of it could even load into the builder.

Four remain, chosen to cover distinct *shapes* rather than distinct vendors —
what a person learns from one transfers to the workflow they go on to build:

  1. event in -> enrich -> notify an app        (call summary to Slack)
  2. event in -> qualify -> write to a system   (qualified call to HubSpot)
  3. time in  -> assemble -> send               (daily digest)
  4. request in -> route -> act per branch      (inbound webhook router)

Two need no integration at all, so they run the moment they are installed.

Placeholders
------------
``connection_id`` is per-workspace and cannot be baked in, so integration steps
ship with it blank and the template declares ``required_integrations``. The
install endpoint creates the workflow inactive, and the builder's validator
already reports a blank required field as an error against the exact node — so
the gap is visible where it has to be fixed.
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# Graph helpers
#
# Written as small builders rather than literal dicts: a hand-written graph is
# where a typo becomes a template that installs and then fails at run time, and
# these keep ids, handles and positions consistent by construction.
# ---------------------------------------------------------------------------

#: Vertical spacing between stacked nodes, matching the builder's auto-layout.
_ROW = 160


def _node(node_id, node_type, name, config, row, column=0):
    """One graph node, positioned on a simple grid."""
    return {
        "id": node_id,
        "type": node_type,
        "name": name,
        "position": {"x": 320 + column * 340, "y": row * _ROW},
        "config": config,
        "settings": {},
    }


def _edge(source, target, source_handle="out"):
    """One graph edge. Ids are derived so they cannot collide."""
    return {
        "id": f"e_{source}_{source_handle}_{target}",
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": "in",
    }


def _graph(nodes, edges):
    return {"schema_version": 2, "nodes": nodes, "edges": edges}


_PUBLISHED = {
    "status": "published",
    "published_at": datetime(2026, 8, 21),
    "author_name": "Voicecon",
    "is_official": True,
    "is_free": True,
    "version": "3.0.0",
}


# ---------------------------------------------------------------------------
# 1. Call summary to Slack
# ---------------------------------------------------------------------------

_CALL_SUMMARY_TO_SLACK = {
    **_PUBLISHED,
    "name": "Post a call summary to Slack",
    "slug": "call-summary-to-slack",
    "description": "After every call, send a short summary to a Slack channel",
    "long_description": (
        "When a call ends, this builds a one-line summary from the call's own "
        "data and posts it to Slack.\n\n"
        "Shape: event in -> enrich -> notify. The Set Fields step is where you "
        "decide what the message says; swap Slack for any other connected app "
        "and the rest of the workflow is unchanged."
    ),
    "category": "notifications",
    "tags": ["slack", "notifications", "calls"],
    "icon": "💬",
    "is_featured": True,
    "required_integrations": ["slack"],
    "trigger_type": "call_completed",
    "trigger_config": {"filters": {}},
    "setup_guide": (
        "1. Connect Slack under Integrations.\n"
        "2. Open the workflow's 'Post to Slack' step and pick that connection.\n"
        "3. Set the channel you want the summary in.\n"
        "4. Activate the workflow."
    ),
    "use_cases": [
        "Keep a sales channel aware of inbound calls as they happen",
        "Give a support team a running log without opening the dashboard",
    ],
    "workflow_definition": _graph(
        nodes=[
            _node("trigger", "trigger", "When a call ends", {"inputs": []}, row=0),
            _node(
                "summary",
                "transform",
                "Build the summary",
                {
                    "transformations": {
                        "call_summary": (
                            "Call with {{trigger.phone_number}} ended after "
                            "{{trigger.duration}}s."
                        ),
                        "call_notes": "{{trigger.transcript}}",
                    }
                },
                row=1,
            ),
            _node(
                "notify",
                "action",
                "Post to Slack",
                {
                    # Blank on purpose: connections are per-workspace. The
                    # builder flags this as a required field, which is how the
                    # user is told to pick one.
                    "connection_id": "",
                    "action": "send_message",
                    "parameters": {
                        "channel": "#general",
                        "text": "{{call_summary}}",
                    },
                },
                row=2,
            ),
        ],
        edges=[_edge("trigger", "summary"), _edge("summary", "notify")],
    ),
}


# ---------------------------------------------------------------------------
# 2. Qualified call to HubSpot
# ---------------------------------------------------------------------------

_QUALIFIED_CALL_TO_HUBSPOT = {
    **_PUBLISHED,
    "name": "Send qualified calls to HubSpot",
    "slug": "qualified-call-to-hubspot",
    "description": "Create a HubSpot contact when a call looks like a real lead",
    "long_description": (
        "Not every call is worth a CRM record. This one checks the call "
        "against a rule first and only writes the ones that pass.\n\n"
        "Shape: event in -> qualify -> write. The Branch step is the part to "
        "make your own — length is only a starting proxy for interest; "
        "{{trigger.intent}} and {{trigger.sentiment}} are available too."
    ),
    "category": "lead_capture",
    "tags": ["hubspot", "crm", "leads"],
    "icon": "🎯",
    "is_featured": True,
    "required_integrations": ["hubspot"],
    "trigger_type": "call_completed",
    "trigger_config": {"filters": {}},
    "setup_guide": (
        "1. Connect HubSpot under Integrations.\n"
        "2. Open 'Create the contact' and pick that connection, then choose "
        "the action and map the fields.\n"
        "3. Adjust the Branch rule to match how you qualify a lead.\n"
        "4. Activate the workflow."
    ),
    "use_cases": [
        "Capture inbound leads without manual CRM entry",
        "Keep short or misdialled calls out of the CRM",
    ],
    "workflow_definition": _graph(
        nodes=[
            _node("trigger", "trigger", "When a call ends", {"inputs": []}, row=0),
            _node(
                "details",
                "transform",
                "Collect the details",
                {
                    "transformations": {
                        "contact_phone": "{{trigger.phone_number}}",
                        "call_notes": "{{trigger.transcript}}",
                        "call_length": "{{trigger.duration}}",
                    }
                },
                row=1,
            ),
            _node(
                "qualified",
                "condition",
                "Long enough to be a lead?",
                {
                    "variable": "trigger.duration",
                    "operator": "greater_than",
                    "value": "60",
                },
                row=2,
            ),
            _node(
                "create",
                "action",
                "Create the contact",
                {
                    "connection_id": "",
                    "action": "create_contact",
                    "parameters": {
                        "phone": "{{contact_phone}}",
                        "notes": "{{call_notes}}",
                    },
                },
                row=3,
            ),
            _node(
                "skipped",
                "transform",
                "Note that it was skipped",
                {"transformations": {"outcome": "Call too short to qualify"}},
                row=3,
                column=1,
            ),
        ],
        edges=[
            _edge("trigger", "details"),
            _edge("details", "qualified"),
            _edge("qualified", "create", source_handle="true"),
            _edge("qualified", "skipped", source_handle="false"),
        ],
    ),
}


# ---------------------------------------------------------------------------
# 3. Daily digest (no integration required)
# ---------------------------------------------------------------------------

_DAILY_DIGEST = {
    **_PUBLISHED,
    "name": "Send a daily digest",
    "slug": "daily-digest",
    "description": "On a schedule, assemble a message and POST it anywhere",
    "long_description": (
        "Runs every weekday morning, builds a payload, and posts it to a URL "
        "you choose.\n\n"
        "Shape: time in -> assemble -> send. Nothing here needs a connected "
        "app, so it runs as soon as you set the URL — which makes it the "
        "easiest template to start from when you want to see a workflow work "
        "end to end."
    ),
    "category": "notifications",
    "tags": ["schedule", "digest", "http"],
    "icon": "📅",
    "is_featured": True,
    "required_integrations": [],
    "trigger_type": "schedule",
    "trigger_config": {
        "schedule_type": "cron",
        # Weekday mornings. Reopens in the builder as a custom cron, since
        # "weekdays only" is not one of the simple presets.
        "cron_expression": "0 9 * * 1-5",
        "timezone": "UTC",
    },
    "setup_guide": (
        "1. Open the 'Send it' step and replace the URL with your own "
        "endpoint — a Slack incoming webhook, an internal API, anything that "
        "accepts a POST.\n"
        "2. Adjust the time and time zone on the trigger step.\n"
        "3. Use 'Test run' to check it, then activate."
    ),
    "use_cases": [
        "A morning summary posted into a chat tool",
        "A scheduled ping to an internal reporting service",
    ],
    "workflow_definition": _graph(
        nodes=[
            _node(
                "trigger",
                "trigger",
                "Every weekday at 09:00",
                {"inputs": []},
                row=0,
            ),
            _node(
                "compose",
                "transform",
                "Compose the message",
                {
                    "transformations": {
                        "title": "Daily digest",
                        # The scheduler stamps every run with `triggered_at`.
                        # There is no `{{now}}` — an unresolved reference
                        # interpolates to its own literal text rather than
                        # failing, so it would ship a payload reading "{{now}}".
                        "sent_at": "{{trigger.triggered_at}}",
                    }
                },
                row=1,
            ),
            _node(
                "send",
                "webhook",
                "Send it",
                {
                    # A placeholder the user must replace. Deliberately a
                    # documentation domain rather than a real endpoint, so a
                    # forgotten edit fails loudly instead of posting somewhere.
                    "url": "https://example.com/replace-with-your-endpoint",
                    "method": "POST",
                    "headers": {},
                    "body": {"title": "{{title}}", "sent_at": "{{sent_at}}"},
                },
                row=2,
            ),
        ],
        edges=[_edge("trigger", "compose"), _edge("compose", "send")],
    ),
}


# ---------------------------------------------------------------------------
# 4. Inbound webhook router (no integration required)
# ---------------------------------------------------------------------------

_WEBHOOK_ROUTER = {
    **_PUBLISHED,
    "name": "Route an incoming webhook",
    "slug": "webhook-router",
    "description": "Take a POST from any system and branch on what it contains",
    "long_description": (
        "Gives the workflow its own URL, then sends each request down a "
        "different path depending on a field in the body.\n\n"
        "Shape: request in -> route -> act per branch. This is the pattern "
        "behind most integrations with systems that have no connector: they "
        "POST, you decide what happens. The Switch step's rules are matched in "
        "order, and anything unmatched takes 'else'."
    ),
    "category": "data_sync",
    "tags": ["webhook", "routing", "http"],
    "icon": "🔀",
    "is_featured": False,
    "required_integrations": [],
    "trigger_type": "webhook",
    # The key is generated on save; shipping one would hand every install the
    # same URL.
    "trigger_config": {},
    "setup_guide": (
        "1. Open the trigger step and copy the webhook URL.\n"
        "2. Adjust the Switch rules to match the field your system sends — "
        "the whole body is available as {{trigger.payload}}.\n"
        "3. Point each branch at what should happen.\n"
        "4. Activate, then POST to the URL to try it."
    ),
    "use_cases": [
        "Accept events from a system with no built-in connector",
        "Fan one endpoint out to different handling per event type",
    ],
    "workflow_definition": _graph(
        nodes=[
            _node(
                "trigger", "trigger", "When the webhook is called", {"inputs": []}, row=0
            ),
            _node(
                "route",
                "switch",
                "What kind of event?",
                {
                    "rules": [
                        {
                            "label": "New lead",
                            "variable": "trigger.payload.type",
                            "operator": "equals",
                            "value": "lead",
                        },
                        {
                            "label": "Support request",
                            "variable": "trigger.payload.type",
                            "operator": "equals",
                            "value": "support",
                        },
                    ]
                },
                row=1,
            ),
            _node(
                "lead",
                "transform",
                "Handle the lead",
                {
                    "transformations": {
                        "handled_as": "lead",
                        "who": "{{trigger.payload.email}}",
                    }
                },
                row=2,
            ),
            _node(
                "support",
                "transform",
                "Handle the support request",
                {
                    "transformations": {
                        "handled_as": "support",
                        "who": "{{trigger.payload.email}}",
                    }
                },
                row=2,
                column=1,
            ),
            _node(
                "other",
                "transform",
                "Anything else",
                {"transformations": {"handled_as": "unrecognised"}},
                row=2,
                column=2,
            ),
        ],
        edges=[
            _edge("trigger", "route"),
            _edge("route", "lead", source_handle="branch-0"),
            _edge("route", "support", source_handle="branch-1"),
            _edge("route", "other", source_handle="fallback"),
        ],
    ),
}


WORKFLOW_TEMPLATES = [
    _CALL_SUMMARY_TO_SLACK,
    _QUALIFIED_CALL_TO_HUBSPOT,
    _DAILY_DIGEST,
    _WEBHOOK_ROUTER,
]
