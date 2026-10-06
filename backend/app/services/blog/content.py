"""
Rules for blog post content.

The body is HTML from the console's rich-text editor and is rendered on the
public website as-is, so it is sanitised here, on the way in, against an
allow-list. Anything the editor cannot produce (scripts, iframes, event
handlers, ``javascript:`` links, inline styles other than text alignment) is
dropped. The browser-side editor is not trusted to have done this: the API can
be called directly.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterable, List, Optional

import nh3

#: Tags the editor produces. No h1: the post title is the page's only h1.
ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4",
    "strong", "b", "em", "i", "u", "s", "code", "pre", "mark", "sub", "sup",
    "blockquote", "ul", "ol", "li",
    "a", "img", "figure", "figcaption",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},  # target: only "_blank", see tag_attribute_values
    "img": {"src", "alt", "title", "width", "height"},
    "ol": {"start"},
    # Text alignment from the editor's toolbar; the style filter below keeps
    # nothing else.
    "p": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
}

MAX_TAGS = 10
MAX_TAG_LENGTH = 40
WORDS_PER_MINUTE = 220

_TAGS_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_H1_RE = re.compile(r"<(/?)h1(?=[\s>])", re.IGNORECASE)


def sanitize_html(html: Optional[str]) -> str:
    """The post body reduced to the allow-listed markup."""
    if not html:
        return ""
    # A heading pasted from elsewhere keeps its weight one level down, rather
    # than being unwrapped into a loose run of text.
    html = _H1_RE.sub(lambda m: f"<{m.group(1)}h2", html)
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        # Removed with their contents, not unwrapped into visible text.
        clean_content_tags={"script", "style", "iframe", "object", "embed", "noscript", "template"},
        url_schemes={"http", "https", "mailto", "tel"},
        tag_attribute_values={"a": {"target": {"_blank"}}},
        filter_style_properties={"text-align"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    # An editor with nothing typed in it still sends "<p></p>".
    return "" if not plain_text(cleaned) and "<img" not in cleaned else cleaned


def plain_text(html: Optional[str]) -> str:
    if not html:
        return ""
    text = _TAGS_RE.sub(" ", html)
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(entity, char)
    return _SPACE_RE.sub(" ", text).strip()


def reading_minutes(html: Optional[str]) -> int:
    words = len(plain_text(html).split())
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def excerpt_from(html: Optional[str], limit: int = 200) -> str:
    """A fallback summary: the opening of the body, cut at a word boundary."""
    text = plain_text(html)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:-")
    return f"{cut}…"


def slugify(value: str, max_length: int = 120) -> str:
    """``"GEO Services: A Guide!"`` → ``"geo-services-a-guide"``."""
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    value = re.sub(r"-{2,}", "-", value)
    return value[:max_length].strip("-")


def normalize_tags(tags: Optional[Iterable[str]]) -> List[str]:
    """Trimmed, de-duplicated (case-insensitively), in the order given."""
    out: List[str] = []
    seen = set()
    for raw in tags or []:
        tag = _SPACE_RE.sub(" ", str(raw or "")).strip()[:MAX_TAG_LENGTH]
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out[:MAX_TAGS]
