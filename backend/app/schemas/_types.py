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

import phonenumbers
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

#: A phone number a person typed, validated against the real numbering plans
#: and stored in E.164 ("+14155550123").
#:
#: The country picker on the forms always sends the calling code, so a number
#: without a leading "+" is rejected rather than guessed at — guessing a region
#: is how a UK number ends up filed as a US one. Letters, and numbers that no
#: country's plan allows, are rejected too; that is what the earlier length-only
#: check let through. Failures read as a sentence because pydantic would
#: otherwise print the regex.
def _is_a_real_phone_number(value: str) -> str:
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        raise ValueError("Please enter a valid phone number.")
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Please enter a valid phone number.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


PhoneNumberStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
    AfterValidator(_is_a_real_phone_number),
]
