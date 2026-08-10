"""
Shared field types.

`Field(..., min_length=1)` counts characters, so a single space satisfies it.
Every user-facing name in this API was declared that way, which meant a name of
pure whitespace was accepted and stored — producing an agent, workflow, tool or
workspace that occupies a row in the list with nothing to click on and no way
to tell one from another. The forms trimmed before checking, so only a direct
API call or a pasted value reached it.

`strip_whitespace=True` fixes both halves at once: the value is trimmed before
`min_length` is applied, so blank input is rejected *and* a padded name is
stored tidy.
"""
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

#: A required, human-visible name. Trimmed, and must survive trimming.
NonBlankName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

#: Same rules, for a longer free-text field with no 255 ceiling.
NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


#: A person's own name, as typed on sign-up.
#:
#: Required rather than optional: the name is what the account menu, the "signed
#: in as" line and every invitation email render, so an account without one
#: shows up as a blank row to its own team-mates. 100 is comfortably inside the
#: 255-char column — posting 500 characters used to overflow it and surface as
#: a 500 rather than a validation message.
#:
#: At least one letter is required somewhere in the value. Without that, "123",
#: "..." and "--" all satisfy a length check while naming nobody. Beyond that it
#: is deliberately permissive: names legitimately contain spaces, apostrophes,
#: hyphens and every alphabet there is, so anything stricter would reject real
#: people. `str.isalpha` is used rather than a regex character class because it
#: is Unicode-aware — it accepts a name written in any script.
def _must_contain_a_letter(value: str) -> str:
    if not any(ch.isalpha() for ch in value):
        raise ValueError("Please enter your name.")
    return value


PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(_must_contain_a_letter),
]

#: A phone number, in whatever shape the country picker produced ("+1 555 010
#: 1234"). Stored as typed, so this only rejects values that cannot be a phone
#: number at all — letters, or too few digits to dial. Full E.164 parsing needs
#: a library that knows every national numbering plan; guessing at it here
#: would reject valid numbers, which is the worse failure for a signup form.
def _looks_like_a_phone_number(value: str) -> str:
    """
    Written as a function rather than a `pattern` so the failure reads as a
    sentence. Pydantic reports a failed pattern by printing the regex, and
    "String should match pattern '^\\+?[0-9][0-9\\s().\\-]{5,}$'" is not
    something to show someone filling in a signup form.
    """
    digits = [c for c in value if c.isdigit()]
    if len(digits) < 7 or len(digits) > 15:
        raise ValueError("Please enter a valid phone number.")
    if any(c.isalpha() for c in value):
        raise ValueError("Please enter a valid phone number.")
    return value


PhoneNumberStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=7, max_length=50),
    AfterValidator(_looks_like_a_phone_number),
]
