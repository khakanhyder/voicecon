"""
Validation rules on the onboarding Company Information payload.

The form checks these too, but the API is the gate: a direct POST — or a form
build that predates the check — must not be able to store a "website" that is
not one.
"""
import pytest
from pydantic import ValidationError

from app.schemas.onboarding import CompanyProfileRequest


def _profile(**overrides):
    return CompanyProfileRequest(company_name="Acme Inc.", **overrides)


class TestCompanyUrl:
    @pytest.mark.parametrize(
        "typed,stored",
        [
            ("acme.com", "https://acme.com"),
            ("www.acme.com", "https://www.acme.com"),
            ("  Acme.COM  ", "https://acme.com"),
            ("http://acme.com", "http://acme.com"),
            ("https://acme.com/careers", "https://acme.com/careers"),
            ("https://acme.co.uk/a?b=1", "https://acme.co.uk/a?b=1"),
            ("https://acme.com/", "https://acme.com"),
            ("voicecon.ai", "https://voicecon.ai"),
            ("acme.com.pk", "https://acme.com.pk"),
            ("acme.technology", "https://acme.technology"),
        ],
    )
    def test_accepts_what_people_type_and_adds_a_scheme(self, typed, stored):
        assert _profile(company_url=typed).company_url == stored

    def test_the_field_stays_optional(self):
        assert _profile().company_url is None
        assert _profile(company_url="").company_url is None
        assert _profile(company_url="   ").company_url is None

    @pytest.mark.parametrize(
        "typed",
        [
            "dcsdcs",      # the bug this was written for: a bare word saved fine
            "localhost",
            "acme.",
            ".com",
            "acme..com",
            "acme.c",      # a one-letter TLD does not exist
            "acme.123",    # a numeric TLD does not exist
            "acme .com",
            "as.asdfdsf",  # reported from onboarding: letters, but not a TLD that exists
            "acme.comm",
            "acme.local",
        ],
    )
    def test_rejects_anything_that_is_not_a_domain(self, typed):
        with pytest.raises(ValidationError, match="valid website"):
            _profile(company_url=typed)

    @pytest.mark.parametrize("typed", ["javascript://acme.com", "ftp://acme.com"])
    def test_refuses_any_scheme_that_is_not_http(self, typed):
        """A stored javascript: URL must never reach an href."""
        with pytest.raises(ValidationError, match="http"):
            _profile(company_url=typed)


class TestCompanyName:
    def test_a_blank_name_is_rejected(self):
        with pytest.raises(ValidationError, match="Enter a company name"):
            CompanyProfileRequest(company_name="   ")

    def test_a_name_is_trimmed(self):
        assert CompanyProfileRequest(company_name="  Acme  ").company_name == "Acme"


class TestPhoneNumberValidation:
    """Phone numbers are checked against real numbering plans and stored as E.164."""

    def _company(self, phone):
        from app.schemas.onboarding import CompanyProfileRequest

        return CompanyProfileRequest(company_name="Acme", phone_number=phone)

    def test_valid_number_is_normalised_to_e164(self):
        assert self._company("+92 300 1234567").phone_number == "+923001234567"
        assert self._company("+44 20 7946 0958").phone_number == "+442079460958"

    def test_blank_is_none(self):
        assert self._company("  ").phone_number is None
        assert self._company(None).phone_number is None

    @pytest.mark.parametrize("bad", ["abc", "+1 555", "3001234567", "+999 123456"])
    def test_invalid_numbers_are_rejected(self, bad):
        with pytest.raises(ValidationError):
            self._company(bad)

    def test_user_update_applies_same_rule(self):
        from app.schemas.user import UserUpdate

        assert UserUpdate(phone_number="+14155552671").phone_number == "+14155552671"
        assert UserUpdate(phone_number=None).phone_number is None
        with pytest.raises(ValidationError):
            UserUpdate(phone_number="hello")
