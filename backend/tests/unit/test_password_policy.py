"""
Unit tests for the sign-up / reset password policy.

The policy is deliberately NIST-shaped: a length floor, a byte ceiling that
matches what bcrypt can actually read, a common-password blocklist, and a check
that the password is not the user's own name or address. These tests pin both
halves of that — what must be refused, and just as importantly the strong
passphrases that must NOT be refused, since an over-strict rule pushes people
back towards `Password1!`.
"""
import pytest

from app.core.passwords import (
    MAX_BYTES,
    MIN_LENGTH,
    PasswordPolicyError,
    validate_password,
)


@pytest.mark.unit
@pytest.mark.auth
class TestLength:
    def test_password_at_the_minimum_is_accepted(self):
        password = "z" * (MIN_LENGTH - 1) + "q"

        assert validate_password(password) == password

    @pytest.mark.parametrize("length", [0, 1, 7])
    def test_short_passwords_are_refused(self, length):
        with pytest.raises(PasswordPolicyError, match="at least"):
            validate_password("aB3$x" [:1] * length if length else "")

    def test_the_message_names_the_minimum(self):
        """The user has to be told what to change, not just that it failed."""
        with pytest.raises(PasswordPolicyError, match=str(MIN_LENGTH)):
            validate_password("short")

    def test_password_at_the_byte_ceiling_is_accepted(self):
        password = "u" * (MAX_BYTES - 1) + "v"

        assert validate_password(password) == password

    def test_password_past_the_byte_ceiling_is_refused(self):
        """
        bcrypt reads 72 bytes and silently ignores the rest, so two long
        passwords sharing a prefix would authenticate each other. Refusing here
        is what lets the limit be explained instead of hidden.
        """
        with pytest.raises(PasswordPolicyError, match="too long"):
            validate_password("v" * (MAX_BYTES + 1))

    def test_the_ceiling_counts_bytes_not_characters(self):
        """
        A multi-byte passphrase can be well under 72 *characters* and still
        overflow bcrypt's 72-byte window.
        """
        password = "密" * 25  # 3 bytes each → 75 bytes

        assert len(password) < MAX_BYTES
        with pytest.raises(PasswordPolicyError, match="too long"):
            validate_password(password)


@pytest.mark.unit
@pytest.mark.auth
class TestWeakPasswords:
    @pytest.mark.parametrize(
        "password", ["password", "12345678", "qwertyuiop", "iloveyou", "p@ssw0rd"]
    )
    def test_common_passwords_are_refused(self, password):
        with pytest.raises(PasswordPolicyError, match="commonly used"):
            validate_password(password)

    def test_the_blocklist_ignores_case(self):
        with pytest.raises(PasswordPolicyError, match="commonly used"):
            validate_password("PASSWORD")

    def test_the_blocklist_ignores_accents(self):
        """`Pässwörd` is `password` to anyone running a dictionary attack."""
        with pytest.raises(PasswordPolicyError, match="commonly used"):
            validate_password("Pässwörd")

    def test_a_repeated_character_is_refused(self):
        """"aaaaaaaa" clears the length check and nothing else."""
        with pytest.raises(PasswordPolicyError, match="same character"):
            validate_password("aaaaaaaaaa")

    @pytest.mark.parametrize("password", ["12345678", "abcdefgh", "hgfedcba"])
    def test_keyboard_and_alphabet_runs_are_refused(self, password):
        with pytest.raises(PasswordPolicyError):
            validate_password(password)

    def test_only_spaces_is_refused(self):
        with pytest.raises(PasswordPolicyError, match="spaces"):
            validate_password(" " * 12)


@pytest.mark.unit
@pytest.mark.auth
class TestPersonalInformation:
    def test_the_email_local_part_cannot_be_the_password(self):
        with pytest.raises(PasswordPolicyError, match="name or your email"):
            validate_password("johnsmith", email="johnsmith@example.com")

    def test_a_dotted_local_part_is_split_into_its_names(self):
        """
        `alexander.hamilton@` must rule out "hamilton" on its own, not just the
        whole local part. (The surname has to clear the length floor to reach
        this check at all — a short one is refused for being short.)
        """
        with pytest.raises(PasswordPolicyError, match="name or your email"):
            validate_password("hamilton", email="alexander.hamilton@example.com")

    def test_the_full_name_cannot_be_the_password(self):
        with pytest.raises(PasswordPolicyError, match="name or your email"):
            validate_password("johnsmith", full_name="John Smith")

    def test_the_check_ignores_case_and_accents(self):
        with pytest.raises(PasswordPolicyError, match="name or your email"):
            validate_password("JOHNSMITH", full_name="Jöhn Smith")

    def test_a_password_merely_containing_the_name_is_allowed(self):
        """
        The rule is "is your name", not "contains it" — a passphrase built
        around your own name is still a passphrase, and rejecting it would push
        people towards something shorter.
        """
        password = "johnsmith-rides-a-red-bicycle"

        assert validate_password(password, full_name="John Smith") == password

    def test_without_context_the_personal_check_is_skipped(self):
        """Password reset flows may not know who the user is yet."""
        assert validate_password("johnsmith") == "johnsmith"


@pytest.mark.unit
@pytest.mark.auth
class TestStrongPasswordsAreAccepted:
    @pytest.mark.parametrize(
        "password",
        [
            "correct-horse-battery",       # a passphrase, no composition rules met
            "tR0ub4dor&3",                 # the classic composed password
            "my dog has fleas 42",         # spaces are legal inside a password
            "ᚠᚢᚦᚨᚱᚲ-runes-ftw",            # non-Latin script
            "🔐🔐 keys and more keys",      # emoji
        ],
    )
    def test_reasonable_passwords_pass(self, password):
        assert validate_password(password) == password

    def test_the_password_is_returned_unchanged(self):
        """
        The policy must not silently rewrite the password — trimming it here
        would hash something different from what the user typed at login.
        """
        password = "  spaces kept inside  "

        assert validate_password(password) == password
