"""
Password policy for sign-up, password reset and password change.

The rules follow NIST SP 800-63B, which is what most current guidance settled
on, and they are deliberately *not* the older "one upper, one digit, one
symbol" recipe. Composition rules push people towards `Password1!` — which
satisfies every one of them and is among the first things any attacker tries —
while blocking passphrases that are genuinely far stronger. What actually
correlates with a password surviving an attack is length, and not being a
password everybody else already uses.

So: a floor on length, a ceiling that matches what bcrypt can actually read,
a blocklist of the passwords that turn up first in every credential dump, and
a check that the password is not simply the user's own name or address.

If a compliance regime requires character-class rules, `_COMPOSITION_RULES` at
the bottom is the hook — it is off by default, and turning it on is a one-line
change rather than a rewrite.
"""
import re
import unicodedata

#: Shortest allowed. NIST's floor is 8; longer is better but this is the point
#: below which a password is not worth calling one.
MIN_LENGTH = 8

#: bcrypt reads at most 72 *bytes* and ignores everything after. The hashing
#: helper truncates silently, which means two different long passwords sharing
#: a 72-byte prefix authenticate each other — so the limit is enforced here
#: instead, where it can be explained to the user rather than hidden.
MAX_BYTES = 72

#: The passwords that appear at the top of every leaked-credential list. This
#: is a floor, not a substitute for a real breach corpus: wiring in a service
#: like Pwned Passwords (k-anonymity range query, so no password leaves the
#: server) would catch orders of magnitude more, and is the natural upgrade.
_COMMON_PASSWORDS = frozenset(
    """
    123456 12345678 123456789 1234567890 12345 1234567 password password1
    password123 qwerty qwerty123 qwertyuiop abc123 111111 123123 000000
    iloveyou admin admin123 welcome welcome1 welcome123 monkey dragon
    letmein login princess solo starwars master hello freedom whatever
    trustno1 sunshine ashley bailey shadow superman qazwsx michael football
    baseball jennifer jordan hunter harley ranger buster soccer batman
    andrew tigger charlie robert thomas hockey killer george sexy andrea
    changeme default secret passw0rd p@ssw0rd p@ssword letmein123
    """.split()
)

#: Runs of the same character, or trivial sequences. "aaaaaaaa" clears a length
#: check and nothing else.
_REPEATED = re.compile(r"^(.)\1+$")
_SEQUENCES = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop")


class PasswordPolicyError(ValueError):
    """A password was refused. The message is shown to the user verbatim."""


def _normalize(value: str) -> str:
    """Casefold and strip accents, so `Pässwörd` is recognised as `password`."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )
    return stripped.casefold()


def _is_sequence(normalized: str) -> bool:
    if len(normalized) < MIN_LENGTH:
        return False
    return any(normalized in seq or normalized in seq[::-1] for seq in _SEQUENCES)


def _personal_tokens(email: str | None, full_name: str | None) -> list[str]:
    """The parts of a person's own identity that must not *be* the password."""
    tokens: list[str] = []
    if email:
        local = email.split("@")[0]
        tokens.append(local)
        # `john.smith@` gives "john" and "smith" as well as the whole local part.
        tokens.extend(part for part in re.split(r"[._\-+]", local) if len(part) >= 3)
    if full_name:
        tokens.append(full_name.replace(" ", ""))
        tokens.extend(part for part in full_name.split() if len(part) >= 3)
    return [_normalize(t) for t in tokens if t]


def validate_password(
    password: str,
    *,
    email: str | None = None,
    full_name: str | None = None,
) -> str:
    """
    Check a password, returning it unchanged, or raise `PasswordPolicyError`.

    `email` and `full_name` are optional context: when the caller knows who the
    password belongs to, a password that is simply their own name or address is
    refused. Passing neither still applies every other rule.
    """
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_LENGTH} characters."
        )

    if len(password.encode("utf-8")) > MAX_BYTES:
        # Explained in terms of length rather than bytes, which would mean
        # nothing to the person typing it.
        raise PasswordPolicyError(
            f"Password is too long. Please use {MAX_BYTES} characters or fewer."
        )

    if password.strip() != password.strip(" ") or not password.strip():
        raise PasswordPolicyError("Password cannot be only spaces.")

    normalized = _normalize(password)

    if normalized in _COMMON_PASSWORDS:
        raise PasswordPolicyError(
            "That password is one of the most commonly used ones. Please choose another."
        )

    if _REPEATED.match(password):
        raise PasswordPolicyError("Password cannot be the same character repeated.")

    if _is_sequence(normalized):
        raise PasswordPolicyError("Password cannot be a simple sequence of keys.")

    for token in _personal_tokens(email, full_name):
        if token and token == normalized:
            raise PasswordPolicyError(
                "Password cannot be your name or your email address."
            )

    if _COMPOSITION_RULES:
        _enforce_composition(password)

    return password


#: Off by default — see the module docstring. Set to True only if a compliance
#: requirement demands character-class rules; it makes passwords predictably
#: worse, not better.
_COMPOSITION_RULES = False


def _enforce_composition(password: str) -> None:
    missing = []
    if not any(c.islower() for c in password):
        missing.append("a lowercase letter")
    if not any(c.isupper() for c in password):
        missing.append("an uppercase letter")
    if not any(c.isdigit() for c in password):
        missing.append("a number")
    if missing:
        raise PasswordPolicyError("Password must contain " + ", ".join(missing) + ".")
