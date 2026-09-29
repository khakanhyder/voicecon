"""Decide what failure text is fit to show a customer.

Messages we write for people ("That number is no longer available") and text
that leaks out of a library or a provider ("HTTPSConnectionPool(host=...)",
"'NoneType' object has no attribute ...", a raw JSON body) travel down the
same fields. The customer dashboard renders those fields, so anything that
reads like the second kind is logged here and replaced with a plain sentence.

The frontend applies the same test in `lib/api.ts` (`getErrorMessage`) as a
second line of defence; keep the two roughly in step.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Anything this long is a dump, not a sentence someone wrote for a user.
MAX_PUBLIC_LENGTH = 240

_TECHNICAL = re.compile(
    r"traceback|exception|errno|stack ?trace|"
    r"\b[A-Z][A-Za-z]+(Error|Exception)\b|"  # ValueError, ClientResponseError, ...
    r"nonetype|object has no attribute|not subscriptable|unexpected keyword|"
    r"sqlalchemy|psycopg|asyncpg|integrityerror|duplicate key|violates|"
    r"httpx|aiohttp|urllib|connectionpool|max retries|ssl|certificate|"
    r"\bstatus code \d{3}\b|\bfor url\b|https?://|"
    r"object at 0x|<[a-z!/]|^\s*[\[{]",
    re.IGNORECASE,
)


def looks_technical(text: Any) -> bool:
    """True when ``text`` is not a short, plain, human sentence."""
    if not isinstance(text, str) or not text.strip():
        return True
    return len(text) > MAX_PUBLIC_LENGTH or bool(_TECHNICAL.search(text))


def public_message(text: Any, fallback: str, *, context: str = "") -> str:
    """``text`` if it is fit for a customer, else ``fallback`` (and log it)."""
    if not looks_technical(text):
        return text
    if text:
        logger.warning(f"Hid technical message from customer{f' ({context})' if context else ''}: {text}")
    return fallback


_CREDENTIAL_HINT = re.compile(
    r"\b(401|403)\b|unauthori[sz]ed|forbidden|invalid[_ ](api[_ ])?(key|token|credential)|"
    r"authenticat|permission|access denied",
    re.IGNORECASE,
)


def public_test_result(result: Dict[str, Any], integration_name: str) -> Dict[str, Any]:
    """A connection-test result with its message and details made customer-safe.

    Connector tests put ``f"... failed: {exc}"`` and up to 500 characters of the
    provider's response body into the result. The full result is logged; the
    customer gets a sentence that says what to check.
    """
    if result.get("success"):
        return result

    raw = result.get("message")
    logger.warning(
        f"{integration_name} connection test failed: {raw} details={result.get('details')}"
    )
    if not looks_technical(raw) and not str(raw).lower().startswith(
        ("connection test failed", "connection test error")
    ):
        message = raw
    elif _CREDENTIAL_HINT.search(f"{raw} {result.get('details')}"):
        message = f"{integration_name} rejected these credentials. Check them and try again."
    else:
        message = f"We couldn't connect to {integration_name}. Check your details and try again."
    return {**result, "message": message, "details": {}}
