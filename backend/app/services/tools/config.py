"""
Reading a tool's stored configuration.

A Tool's ``config`` is a free-form JSON column filled in by the builder form,
and the form stores its JSON fields — headers, body, row templates — as the
*text* the user typed. That is the right thing for a textarea: it round-trips
what was written, including formatting, and it lets an invalid draft be saved
and fixed later rather than being rejected mid-edit.

The consumers, though, want real values. Reading ``config["headers"]`` straight
into ``{**headers}`` raised ``TypeError: 'str' object is not a mapping`` for
every tool whose headers had ever been edited, and the failure surfaced only at
call time — the tool saved cleanly, then broke on a live call.

So the coercion belongs here, in one place both the live executor and the
"Test" button go through. A tool created through the API may hold the parsed
object instead, and both spellings are equally valid on the wire, so every
helper accepts either.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

#: Any ``{{reference}}`` inside a larger string.
_TEMPLATE = re.compile(r"\{\{([^}]+)\}\}")

#: A string that is *only* one reference. Surrounding whitespace is tolerated
#: because a form field trivially collects it; anything else around the
#: reference makes it a mixed template whose result can only be text.
_WHOLE_TEMPLATE = re.compile(r"^\s*\{\{([^}]+)\}\}\s*$")

#: Bounds for a user-entered timeout. Zero or negative would mean "never wait";
#: an unbounded value would let one tool pin a worker open indefinitely.
MIN_TIMEOUT = 1.0
MAX_TIMEOUT = 120.0


class ToolConfigError(ValueError):
    """A tool's configuration cannot be used as written.

    Phrased for the person who filled in the form, because that is who sees it
    — in the Test panel, or in a failed call's tool result.
    """


def as_text(value: Any) -> str:
    """Render a resolved value for embedding in text.

    ``str()`` is wrong for containers and booleans: it produces Python
    spellings (``True``, single-quoted dict reprs) that are not valid JSON and
    read as nonsense when spoken back to a caller.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def as_mapping(value: Any, field: str) -> Dict[str, Any]:
    """A config field as a dictionary, however it was stored.

    Args:
        value: The raw config value — a dict, a JSON string, or nothing
        field: Field name, so the error names what the user must fix

    Returns:
        The field as a dict; empty when the field is unset or blank

    Raises:
        ToolConfigError: The field holds text that is not a JSON object
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ToolConfigError(
                f"{field} is not valid JSON: {exc.msg} (line {exc.lineno}, "
                f"column {exc.colno})"
            ) from exc
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ToolConfigError(
                f"{field} must be a JSON object like "
                f'{{"name": "value"}}, not {type(parsed).__name__}'
            )
        return parsed
    raise ToolConfigError(
        f"{field} must be a JSON object, not {type(value).__name__}"
    )


def as_sequence(value: Any, field: str) -> List[Any]:
    """A config field as a list, however it was stored.

    The Google Sheets row template is the case that needs this: the form stores
    ``["{{name}}", "{{phone}}"]`` as text.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ToolConfigError(
                f"{field} is not valid JSON: {exc.msg} (line {exc.lineno}, "
                f"column {exc.colno})"
            ) from exc
        if parsed is None:
            return []
        if not isinstance(parsed, list):
            raise ToolConfigError(
                f"{field} must be a JSON array like "
                f'["first", "second"], not {type(parsed).__name__}'
            )
        return parsed
    raise ToolConfigError(
        f"{field} must be a JSON array, not {type(value).__name__}"
    )


def as_timeout(value: Any, default: float) -> float:
    """A user-entered timeout as a number of seconds.

    The form stores it as text, and an empty box must mean "use the default"
    rather than "wait zero seconds". A value that is not a number at all is
    treated the same way: a mistyped timeout should not stop a tool that would
    otherwise work.

    Args:
        value: The raw config value
        default: Seconds to use when the field is unset or unusable

    Returns:
        Seconds, clamped to a range a phone call can survive
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return default
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return default
    return max(MIN_TIMEOUT, min(MAX_TIMEOUT, seconds))


def as_header_map(value: Any, field: str = "Headers") -> Dict[str, str]:
    """Headers as a dict of strings.

    A header value must be text on the wire, so a number or boolean typed into
    the JSON is rendered rather than rejected — ``{"X-Retries": 3}`` is an
    obvious intent, and failing the call over it helps nobody. A structured
    value is refused, because there is no sensible header spelling for it.
    """
    headers: Dict[str, str] = {}
    for key, raw in as_mapping(value, field).items():
        if isinstance(raw, (dict, list, tuple)):
            raise ToolConfigError(
                f"{field}: '{key}' must be a single value, not a "
                f"{type(raw).__name__}"
            )
        headers[str(key)] = as_text(raw)
    return headers


def resolve(path: str, parameters: Dict[str, Any]) -> Any:
    """Look one ``{{reference}}`` up in the parameters the model extracted.

    Dotted paths reach into a parameter declared as an object, and ``[0]``
    indexes one declared as an array, so a tool taking a structured parameter
    can still template a single field out of it.

    Returns ``None`` for anything that does not resolve — the caller decides
    whether that is an empty string or an absent key.
    """
    current: Any = parameters
    for segment in path.strip().split("."):
        segment = segment.strip()
        if not segment:
            return None
        index: Optional[int] = None
        match = re.match(r"^(.*?)\[(-?\d+)\]$", segment)
        if match:
            segment, index = match.group(1), int(match.group(2))
        if segment:
            if isinstance(current, dict):
                if segment not in current:
                    return None
                current = current[segment]
            else:
                return None
        if index is not None:
            if not isinstance(current, (list, tuple)):
                return None
            try:
                current = current[index]
            except IndexError:
                return None
    return current


def render(value: Any, parameters: Dict[str, Any]) -> Any:
    """Resolve ``{{name}}`` references against a tool's parameters.

    Types are preserved the same way they are in a workflow, because the
    receiving API cares about the difference:

    * **Whole-value** — the string is nothing but one reference, so the
      reference *is* the value and keeps its own type. ``{"amount":
      "{{total}}"}`` posts ``42``, not ``"42"``.
    * **Mixed** — the reference sits inside surrounding text, so the result can
      only be a string: ``"Order {{id}} shipped"``.

    An unresolved reference becomes ``None`` whole-value, or an empty string
    mixed. Leaving a literal ``{{missing}}`` in an outbound payload is never
    what the author meant and cannot be told apart from a real value
    downstream.

    Nested structures are walked, so a body template's inner objects and arrays
    are rendered too.
    """
    if isinstance(value, str):
        whole = _WHOLE_TEMPLATE.match(value)
        if whole:
            return resolve(whole.group(1), parameters)

        matches = _TEMPLATE.findall(value)
        if not matches:
            return value

        rendered = value
        for match in matches:
            rendered = rendered.replace(
                f"{{{{{match}}}}}", as_text(resolve(match, parameters))
            )
        return rendered

    if isinstance(value, dict):
        return {key: render(item, parameters) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [render(item, parameters) for item in value]

    return value


def build_body(
    raw_body: Any,
    parameters: Dict[str, Any],
    field: str = "Body Template",
) -> Dict[str, Any]:
    """The request body for an HTTP tool.

    A body template is a *template*: its ``{{param}}`` placeholders are filled
    from what the model extracted, which is what the form's own hint promises.
    The previous behaviour merged the parameters over the template as extra
    top-level keys, so a template of ``{"email": "{{email}}"}`` posted
    ``{"email": "{{email}}", "email": ...}`` — the placeholder went out
    verbatim and the receiving API saw a literal ``{{email}}``.

    Parameters that the template never mentions are still passed through, so a
    tool with no template at all keeps working as it always has.
    """
    template = as_mapping(raw_body, field)
    rendered = render(template, parameters)

    referenced = {
        match.strip().split(".")[0].split("[")[0]
        for match in _TEMPLATE.findall(json.dumps(template, default=str))
    }
    passthrough = {
        key: value for key, value in parameters.items() if key not in referenced
    }
    return {**rendered, **passthrough}
