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
        with pytest.raises(ValidationError, match="blank"):
            CompanyProfileRequest(company_name="   ")

    def test_a_name_is_trimmed(self):
        assert CompanyProfileRequest(company_name="  Acme  ").company_name == "Acme"
