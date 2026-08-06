"""
Pickable resources inside a connected integration.

An action almost always needs to be pointed at *something* — a Trello list, a
Slack channel, a Google Sheet. Until now the only way to say which was to type
the provider's internal id into a text box, which meant every workflow author
had to go and find an opaque string like ``66f0a1c3d9e4b2001f5c7a91`` before
they could create a card. That is a fine ask for an integrator and an
impossible one for the person who actually bought the product.

This module is the missing half of the picture. Connectors already know how to
enumerate their own resources — :meth:`TrelloConnector.get_boards`,
:meth:`SlackConnector.list_channels` and five others were written long ago and
never reachable from outside. Here they are declared once, normalised into a
single ``{id, name}`` shape, and exposed so the builder can render a dropdown
of names while continuing to store ids.

Three ways to name a resource, which is what makes this usable by everyone:

* **From a list** — the default. Pick "To Do" from a dropdown.
* **From a URL** — paste the link to the board you already have open. No
  dropdown, no waiting on an API call, and no hunting: the id is extracted from
  the address bar. For a lot of people this is the fastest route.
* **By id** — the escape hatch, for expressions and power users.

Adding a connector to this file is a few lines and needs no endpoint, no
frontend change and no migration.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceSpec:
    """How to list one kind of resource on one connector."""

    #: Method on the connector instance that fetches them.
    method: str
    #: Human label, singular — what the field is called in the UI ("List").
    label: str
    #: Where the items live in the connector's return value. Connectors were
    #: written independently and disagree: some return a bare list, some wrap it
    #: in ``{"boards": [...]}``, Google uses ``items``, SendGrid uses ``result``.
    #: Candidates are tried in order and the first list wins.
    result_keys: tuple = ("items", "result", "results", "data")
    #: Resource kind this one lives inside, if any. ``lists`` belong to a
    #: ``board``, so the board must be chosen first.
    parent_kind: Optional[str] = None
    #: The keyword argument the parent's id is passed as.
    parent_arg: Optional[str] = None
    #: Extra keyword arguments always passed to the method.
    fixed_args: Dict[str, Any] = field(default_factory=dict)
    #: Hint shown under the picker when the list is empty.
    empty_hint: str = ""


#: connector slug -> resource kind -> how to fetch it.
#:
#: Only connectors whose listing method genuinely exists are declared. A kind
#: that is missing simply falls back to the URL and id modes, which is a
#: perfectly usable field — never a broken one.
RESOURCE_PROVIDERS: Dict[str, Dict[str, ResourceSpec]] = {
    "trello": {
        "boards": ResourceSpec(
            method="get_boards",
            label="Board",
            result_keys=("boards",),
            empty_hint="No boards found on this Trello account.",
        ),
        "lists": ResourceSpec(
            method="get_lists",
            label="List",
            result_keys=("lists",),
            parent_kind="boards",
            parent_arg="board_id",
            empty_hint="This board has no lists yet.",
        ),
    },
    "slack": {
        "channels": ResourceSpec(
            method="list_channels",
            label="Channel",
            result_keys=("channels",),
            empty_hint="No channels visible to this Slack app. Invite it to a channel first.",
        ),
    },
    "google-calendar": {
        "calendars": ResourceSpec(
            method="list_calendars",
            label="Calendar",
            result_keys=("items", "calendars"),
        ),
    },
    "google_calendar": {
        "calendars": ResourceSpec(
            method="list_calendars",
            label="Calendar",
            result_keys=("items", "calendars"),
        ),
    },
    "monday": {
        "boards": ResourceSpec(
            method="list_boards",
            label="Board",
            result_keys=("boards",),
        ),
    },
    "clickup": {
        "lists": ResourceSpec(
            method="get_lists",
            label="List",
            result_keys=("lists",),
            parent_kind="spaces",
            parent_arg="space_id",
            empty_hint="This space has no lists yet.",
        ),
    },
    "sendgrid": {
        "lists": ResourceSpec(
            method="get_lists",
            label="Contact list",
            result_keys=("result", "lists"),
        ),
    },
    "gohighlevel": {
        "pipelines": ResourceSpec(
            method="list_pipelines",
            label="Pipeline",
            result_keys=("pipelines",),
        ),
        "calendars": ResourceSpec(
            method="list_calendars",
            label="Calendar",
            result_keys=("calendars",),
        ),
    },
}


# ---------------------------------------------------------------- URL parsing

#: connector slug -> resource kind -> pattern whose first group is the id.
#:
#: Pasting a link is often quicker than a dropdown, because the user already has
#: the thing open in another tab. Trello and Notion embed a short id that their
#: own API accepts in place of the canonical one, so no extra lookup is needed.
URL_PATTERNS: Dict[str, Dict[str, Pattern]] = {
    "trello": {
        "boards": re.compile(r"trello\.com/b/([a-zA-Z0-9]+)"),
        "cards": re.compile(r"trello\.com/c/([a-zA-Z0-9]+)"),
    },
    "slack": {
        # https://acme.slack.com/archives/C01234ABCDE
        "channels": re.compile(r"/archives/([A-Z0-9]{8,})"),
    },
    "google-sheets": {
        "spreadsheets": re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})"),
    },
    "google-drive": {
        "files": re.compile(r"/(?:file/d|open\?id=)/?([a-zA-Z0-9_-]{20,})"),
    },
    "notion": {
        # A Notion URL ends with a 32-character hex id, optionally hyphenated.
        "pages": re.compile(r"([0-9a-fA-F]{32})(?:\?|$|#)"),
        "databases": re.compile(r"([0-9a-fA-F]{32})(?:\?|$|#)"),
    },
    "airtable": {
        "bases": re.compile(r"airtable\.com/(app[a-zA-Z0-9]+)"),
        "tables": re.compile(r"airtable\.com/app[a-zA-Z0-9]+/(tbl[a-zA-Z0-9]+)"),
    },
    "monday": {
        "boards": re.compile(r"/boards/(\d+)"),
    },
    "clickup": {
        "lists": re.compile(r"/v/l[i]?/(\d+)"),
    },
}


def parse_resource_url(connector_slug: str, kind: str, url: str) -> Optional[str]:
    """Pull a resource id out of a pasted link.

    Returns ``None`` when the link does not look like the expected kind, which
    the caller should surface as "that doesn't look like a Trello board link"
    rather than silently storing rubbish that fails at 2am mid-run.
    """
    if not url or not url.strip():
        return None

    pattern = (URL_PATTERNS.get(connector_slug) or {}).get(kind)
    if pattern is None:
        return None

    match = pattern.search(url.strip())
    return match.group(1) if match else None


def supports_url(connector_slug: str, kind: str) -> bool:
    """Whether the "paste a link" mode is offered for this field."""
    return (URL_PATTERNS.get(connector_slug) or {}).get(kind) is not None


# ---------------------------------------------------------------- normalising

#: Keys a provider might call the identifier, most specific first.
_ID_KEYS = ("id", "gid", "value", "list_id", "board_id", "channel_id", "_id")
#: Keys a provider might call the display name.
_NAME_KEYS = ("name", "title", "summary", "label", "displayName", "display_name")


def _extract_items(raw: Any, result_keys: tuple) -> List[Dict[str, Any]]:
    """Find the list of resources inside whatever the connector returned."""
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if not isinstance(raw, dict):
        return []

    # Declared keys first, then the generic ones, then any single list value —
    # enough to cover connectors that were written before this existed.
    for key in tuple(result_keys) + ("items", "result", "results", "data"):
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        # Monday returns GraphQL-shaped {"data": {"boards": [...]}}
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]

    lists = [v for v in raw.values() if isinstance(v, list)]
    if len(lists) == 1:
        return [item for item in lists[0] if isinstance(item, dict)]
    return []


def _pick(item: Dict[str, Any], keys) -> Optional[str]:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def normalize_resources(raw: Any, spec: ResourceSpec) -> List[Dict[str, str]]:
    """Turn a connector's response into ``[{"id", "name"}]``.

    Items without an id are dropped — an option that cannot be selected is
    worse than one that is absent. Items without a name fall back to the id, so
    a resource is always reachable even if the provider omits a label.
    """
    normalized: List[Dict[str, str]] = []
    for item in _extract_items(raw, spec.result_keys):
        identifier = _pick(item, _ID_KEYS)
        if not identifier:
            continue
        entry = {
            "id": identifier,
            "name": _pick(item, _NAME_KEYS) or identifier,
        }
        # Carried through for the UI only: archived Slack channels and closed
        # Trello boards are still selectable but should look different.
        for flag in ("archived", "closed", "is_archived", "state"):
            if flag in item:
                entry["state"] = str(item[flag])
                break
        if item.get("url"):
            entry["url"] = str(item["url"])
        normalized.append(entry)

    # Deliberately *not* sorted. Providers return these in an order that
    # usually means something — Trello lists come back in board order, so
    # "To Do, Doing, Done" stays readable instead of being alphabetised into
    # "Doing, Done, To Do". Long lists are handled by the search box, which is
    # a better answer than reordering someone's board for them.
    return normalized


def search_resources(
    resources: List[Dict[str, str]], query: Optional[str]
) -> List[Dict[str, str]]:
    """Filter by name, case-insensitively.

    Applied here rather than at the provider because almost none of these APIs
    accept a search term for these endpoints, and the lists are small enough
    that fetching once and filtering locally is both simpler and faster than a
    round trip per keystroke.
    """
    if not query or not query.strip():
        return resources
    needle = query.strip().lower()
    return [r for r in resources if needle in r["name"].lower()]


# ---------------------------------------------------------------- lookups

def get_spec(connector_slug: str, kind: str) -> Optional[ResourceSpec]:
    return (RESOURCE_PROVIDERS.get(connector_slug) or {}).get(kind)


def kinds_for_connector(connector_slug: str) -> Dict[str, ResourceSpec]:
    return RESOURCE_PROVIDERS.get(connector_slug) or {}


def describe_kinds(connector_slug: str) -> List[Dict[str, Any]]:
    """What this connector can offer a picker for — used by the setup screen."""
    described = []
    for kind, spec in kinds_for_connector(connector_slug).items():
        described.append(
            {
                "kind": kind,
                "label": spec.label,
                "parent_kind": spec.parent_kind,
                "supports_url": supports_url(connector_slug, kind),
                "empty_hint": spec.empty_hint,
            }
        )
    return described


# ---------------------------------------------------------------- defaults

#: Which resource each connector should ask about once, at connect time.
#:
#: This is the part that makes the picker invisible for most people: someone
#: with a single Trello board answers "where should cards go?" once and never
#: sees a list field again, because every action falls back to this.
#: ``(kind, config key the action parameter is named after)``.
CONNECTION_DEFAULTS: Dict[str, List[Dict[str, str]]] = {
    "trello": [
        {"kind": "boards", "key": "board_id", "prompt": "Which board should cards go to?"},
        {"kind": "lists", "key": "list_id", "prompt": "And which list?"},
    ],
    "slack": [
        {"kind": "channels", "key": "channel", "prompt": "Which channel should messages go to?"},
    ],
    "google-calendar": [
        {"kind": "calendars", "key": "calendar_id", "prompt": "Which calendar should bookings use?"},
    ],
    "google_calendar": [
        {"kind": "calendars", "key": "calendar_id", "prompt": "Which calendar should bookings use?"},
    ],
    "clickup": [
        {"kind": "lists", "key": "list_id", "prompt": "Which list should tasks go to?"},
    ],
    "monday": [
        {"kind": "boards", "key": "board_id", "prompt": "Which board should items go to?"},
    ],
    "sendgrid": [
        {"kind": "lists", "key": "list_id", "prompt": "Which contact list should contacts be added to?"},
    ],
    "gohighlevel": [
        {"kind": "pipelines", "key": "pipeline_id", "prompt": "Which pipeline should opportunities go to?"},
    ],
}


def defaults_for_connector(connector_slug: str) -> List[Dict[str, str]]:
    return CONNECTION_DEFAULTS.get(connector_slug) or []


def apply_connection_defaults(
    parameters: Dict[str, Any], connection_config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Fill in parameters the author left blank from the connection's defaults.

    Only ever *fills a gap*. An explicit value — including one that came from a
    ``{{template}}`` — always wins, because a default silently overriding what
    someone typed is far worse than a missing value they can see.
    """
    if not connection_config:
        return parameters

    defaults = (connection_config or {}).get("defaults") or {}
    if not isinstance(defaults, dict) or not defaults:
        return parameters

    filled = dict(parameters or {})
    for key, value in defaults.items():
        current = filled.get(key)
        if value in (None, "") :
            continue
        if current in (None, ""):
            filled[key] = value
            logger.debug(f"Filled '{key}' from the connection default")
    return filled
