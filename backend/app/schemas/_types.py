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
import re
import unicodedata
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


#: A person's own name — on sign-up, in the profile, on the affiliate form.
#:
#: Required rather than optional: the name is what the account menu, the "signed
#: in as" line and every invitation email render, so an account without one
#: shows up as a blank row to its own team-mates.
#:
#: What counts as a name is decided by `check_person_name`: letters in any
#: script, spaces, hyphens, apostrophes and periods ("Mary-Jane O'Brien",
#: "Smith Jr.", "J. R. R. Tolkien", "محمد علي"). The earlier rule only asked for
#: one letter somewhere, so "a1b!!" and "12345x" were accepted as people. The
#: same rules are in frontend/src/lib/validation.ts (validatePersonName) and the
#: two share their test cases, so a form never says yes where the API says no.
#: `str.isalpha` is used rather than a regex class because it is Unicode-aware.
PERSON_NAME_MIN = 2
PERSON_NAME_MAX = 100

#: Punctuation a name may contain, besides letters and spaces.
_NAME_PUNCT = "-'\u2019."
_NAME_JOINERS = "-'\u2019"
#: Zero-width joiner and non-joiner: invisible, but part of how Persian, Hindi
#: and other scripts spell ordinary names.
_NAME_JOINING_MARKS = "\u200c\u200d"


def _is_name_mark(ch: str) -> bool:
    """Combining marks: the vowel signs and diacritics of many scripts."""
    return unicodedata.category(ch).startswith("M")


def check_person_name(value: str) -> str:
    """
    The tidied name, or ValueError with a sentence the person can act on.

    Tidying: surrounding whitespace is removed and runs of spaces become one.
    """
    cleaned = " ".join((value or "").split())
    if not cleaned:
        raise ValueError("Enter your name.")

    letters = sum(1 for ch in cleaned if ch.isalpha())
    if any(ch.isdigit() for ch in cleaned):
        raise ValueError("A name can't contain numbers.")
    if len(cleaned) > PERSON_NAME_MAX:
        raise ValueError(f"That name is too long. Use {PERSON_NAME_MAX} characters or fewer.")
    if letters < PERSON_NAME_MIN:
        raise ValueError("That name is too short. Enter at least 2 letters.")
    if any(
        not (
            ch.isalpha()
            or ch == " "
            or ch in _NAME_PUNCT
            or ch in _NAME_JOINING_MARKS
            or _is_name_mark(ch)
        )
        for ch in cleaned
    ):
        raise ValueError("Use letters, spaces, hyphens and apostrophes only.")

    # Punctuation has to sit inside a name, not around or between words alone.
    if cleaned[0] in _NAME_PUNCT or cleaned[-1] in _NAME_JOINERS:
        raise ValueError("That doesn't look like a valid name.")
    for left, right in zip(cleaned, cleaned[1:]):
        if left in _NAME_PUNCT and right in _NAME_PUNCT:
            raise ValueError("That doesn't look like a valid name.")
        if left == " " and right in _NAME_PUNCT:
            raise ValueError("That doesn't look like a valid name.")
    # No name has the same letter four times running ("Aaaaaa", "Zzzzz").
    if re.search(r"(.)\1{3,}", cleaned):
        raise ValueError("That doesn't look like a valid name.")
    return cleaned


def _validate_person_name(value: str) -> str:
    return check_person_name(value)


PersonName = Annotated[str, AfterValidator(_validate_person_name)]


#: The name of a business or of an assistant — "Acme Inc.", "3M", "Studio 54",
#: "Aria", "Sales Assistant". Digits and the punctuation businesses use are
#: fine, but it has to be a *name*: at least one letter and two characters, so
#: "123" and "!!!" are not accepted, nor are the characters that only appear in
#: markup or scripts. Mirrors validateDisplayName in frontend/src/lib/validation.ts.
_DISPLAY_NAME_FORBIDDEN = set('<>{}[]\\|^~`$%*=;"')


def check_display_name(value: str, *, label: str = "name", max_length: int = 100) -> str:
    cleaned = " ".join((value or "").split())
    if not cleaned:
        raise ValueError(f"Enter a {label}.")
    if len(cleaned) > max_length:
        raise ValueError(f"That {label} is too long. Use {max_length} characters or fewer.")
    if len(cleaned) < 2:
        raise ValueError(f"That {label} is too short. Enter at least 2 characters.")
    if not any(ch.isalpha() for ch in cleaned):
        raise ValueError(f"The {label} needs at least one letter.")
    if any(ch in _DISPLAY_NAME_FORBIDDEN or unicodedata.category(ch).startswith("C") for ch in cleaned):
        raise ValueError(f"That {label} contains characters that aren't allowed.")
    return cleaned


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


def _company_name(value: str) -> str:
    return check_display_name(value, label="company name")


def _assistant_name(value: str) -> str:
    return check_display_name(value, label="assistant name", max_length=50)


#: Onboarding's company and assistant names.
CompanyName = Annotated[str, AfterValidator(_company_name)]
AssistantName = Annotated[str, AfterValidator(_assistant_name)]
