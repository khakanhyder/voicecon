"""
Unit tests for the shared field types in `app.schemas._types`.

These annotations are the validation boundary for every user-facing name in the
API and for the sign-up form. They exist because `Field(min_length=1)` counts
characters, so a single space satisfied it — producing agents, workflows and
workspaces that occupied a row in the list with nothing to click on. The rules
are checked here directly rather than through each schema that uses them, so a
regression is reported once instead of scattered across every endpoint.
"""
import pytest
from pydantic import BaseModel, ValidationError

from app.schemas._types import (
    NonBlankName,
    NonBlankText,
    PersonName,
    PhoneNumberStr,
)


class Named(BaseModel):
    value: NonBlankName


class Described(BaseModel):
    value: NonBlankText


class Person(BaseModel):
    value: PersonName


class Phone(BaseModel):
    value: PhoneNumberStr


@pytest.mark.unit
class TestNonBlankName:
    def test_an_ordinary_name_passes(self):
        assert Named(value="Support Agent").value == "Support Agent"

    def test_padding_is_trimmed(self):
        """Stored tidy, so the list does not show mysteriously indented rows."""
        assert Named(value="  Support Agent  ").value == "Support Agent"

    @pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n", " \t\n "])
    def test_blank_and_whitespace_only_names_are_refused(self, blank):
        """
        The bug this exists for: trimming happens *before* the length check, so
        a name of pure whitespace is rejected rather than stored.
        """
        with pytest.raises(ValidationError):
            Named(value=blank)

    def test_a_single_character_name_is_allowed(self):
        assert Named(value="A").value == "A"

    def test_names_are_capped_at_the_column_width(self):
        """255 is the column; longer used to overflow and surface as a 500."""
        assert Named(value="x" * 255).value == "x" * 255

        with pytest.raises(ValidationError):
            Named(value="x" * 256)

    def test_the_cap_applies_after_trimming(self):
        """Padding must not count against the limit."""
        assert Named(value="  " + "x" * 255 + "  ").value == "x" * 255


@pytest.mark.unit
class TestNonBlankText:
    def test_long_free_text_is_allowed(self):
        """Descriptions have no 255 ceiling, unlike names."""
        long_text = "y" * 5000

        assert Described(value=long_text).value == long_text

    def test_whitespace_only_text_is_refused(self):
        with pytest.raises(ValidationError):
            Described(value="   ")


@pytest.mark.unit
class TestPersonName:
    def test_an_ordinary_name_passes(self):
        assert Person(value="Ada Lovelace").value == "Ada Lovelace"

    @pytest.mark.parametrize(
        "name",
        ["O'Brien", "Jean-Luc Picard", "Ursula K. Le Guin", "李雷", "Björk Guðmundsdóttir"],
    )
    def test_real_names_are_not_rejected(self, name):
        """
        Deliberately permissive: apostrophes, hyphens and every alphabet there
        is. Anything stricter rejects real people at sign-up.
        """
        assert Person(value=name).value == name

    @pytest.mark.parametrize("not_a_name", ["123", "...", "--", "42 42"])
    def test_a_value_with_no_letters_is_refused(self, not_a_name):
        """"123" and "..." satisfy a length check while naming nobody."""
        with pytest.raises(ValidationError):
            Person(value=not_a_name)

    def test_the_letter_check_is_unicode_aware(self):
        """`str.isalpha`, not a Latin-only character class."""
        assert Person(value="李雷").value == "李雷"

    def test_a_one_character_name_is_refused(self):
        with pytest.raises(ValidationError):
            Person(value="A")

    def test_names_are_capped_at_100(self):
        """The column holds 255; posting 500 used to overflow it into a 500."""
        with pytest.raises(ValidationError):
            Person(value="Ada " * 40)


@pytest.mark.unit
class TestPhoneNumber:
    @pytest.mark.parametrize(
        "number",
        ["+1 555 010 1234", "+44 20 7946 0958", "(555) 010-1234", "555.010.1234"],
    )
    def test_numbers_in_the_shapes_a_country_picker_produces_are_accepted(self, number):
        assert Phone(value=number).value == number

    def test_the_number_is_stored_as_typed(self):
        """No E.164 normalisation here — guessing at it rejects valid numbers."""
        assert Phone(value="+1 (555) 010-1234").value == "+1 (555) 010-1234"

    def test_too_few_digits_is_refused(self):
        with pytest.raises(ValidationError):
            Phone(value="12345")

    def test_too_many_digits_is_refused(self):
        """E.164 tops out at 15 digits."""
        with pytest.raises(ValidationError):
            Phone(value="+1234567890123456")

    def test_letters_are_refused(self):
        with pytest.raises(ValidationError):
            Phone(value="+1 555 CALL NOW")

    def test_the_failure_reads_as_a_sentence(self):
        """
        Written as a validator rather than a `pattern` precisely so the error is
        not a printed regex — nobody filling in a signup form can act on that.
        """
        with pytest.raises(ValidationError) as exc:
            Phone(value="not a phone")

        assert "valid phone number" in str(exc.value)
        assert "^" not in str(exc.value)  # no regex leaked into the message
