"""
What counts as a name, on every form that asks for one.

The cases live in frontend/src/lib/__fixtures__/name-cases.json and are also run
by the frontend's validation.test.ts, so the form and the API cannot disagree
about whether "a1b" is a person.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.affiliate_portal import ApplicationRequest
from app.api.v1.endpoints.waitlist import WaitlistSignup
from app.schemas.auth import RegisterRequest
from app.schemas._types import check_display_name, check_person_name
from app.schemas.onboarding import CompanyProfileRequest
from app.schemas.user import UserUpdate

CASES = json.loads(
    (Path(__file__).resolve().parents[3] / "frontend/src/lib/__fixtures__/name-cases.json").read_text()
)
PERSON = CASES["person"]
DISPLAY = CASES["display"]


class TestPersonName:
    @pytest.mark.parametrize("typed,tidy", PERSON["valid"])
    def test_accepts_real_names_and_tidies_them(self, typed, tidy):
        assert check_person_name(typed) == tidy

    @pytest.mark.parametrize("typed", PERSON["invalid"])
    def test_rejects_what_is_not_a_name(self, typed):
        with pytest.raises(ValueError):
            check_person_name(typed)

    def test_the_length_limit_is_enforced_with_a_sentence(self):
        with pytest.raises(ValueError, match="too long"):
            check_person_name("Ab" * PERSON["too_long"])
        assert len(check_person_name("Abc" * 33 + "A")) == 100   # exactly the limit is fine

    def test_each_mistake_has_its_own_message(self):
        for typed, message in [
            ("", "Enter your name."),
            ("123", "can't contain numbers"),
            ("A", "too short"),
            ("John!", "letters, spaces, hyphens and apostrophes"),
            ("-John", "valid name"),
        ]:
            with pytest.raises(ValueError, match=message):
                check_person_name(typed)

    def test_persian_and_hindi_joiners_are_part_of_real_names(self):
        assert check_person_name("می‌خواهم") == "می‌خواهم"


class TestDisplayName:
    @pytest.mark.parametrize("typed,tidy", DISPLAY["valid"])
    def test_accepts_business_and_assistant_names(self, typed, tidy):
        assert check_display_name(typed) == tidy

    @pytest.mark.parametrize("typed", DISPLAY["invalid"])
    def test_rejects_what_is_not_a_name(self, typed):
        with pytest.raises(ValueError):
            check_display_name(typed)

    def test_the_label_and_limit_are_the_callers(self):
        with pytest.raises(ValueError, match="assistant name is too long"):
            check_display_name("A" * 51, label="assistant name", max_length=50)


class TestEveryFormThatTakesAName:
    """The same rule, reached through each schema, so none is left behind."""

    def test_sign_up(self):
        base = dict(email="a@example.com", password="Tr1cky-horse-staple", email_verification_token="t")
        assert RegisterRequest(full_name="  Ali   Khan ", **base).full_name == "Ali Khan"
        with pytest.raises(ValidationError, match="can't contain numbers"):
            RegisterRequest(full_name="123", **base)
        with pytest.raises(ValidationError):
            RegisterRequest(full_name="!!!", **base)

    def test_profile_edit(self):
        assert UserUpdate(full_name=" Sara  Malik ").full_name == "Sara Malik"
        assert UserUpdate().full_name is None   # omitted stays omitted
        with pytest.raises(ValidationError, match="can't contain numbers"):
            UserUpdate(full_name="Sara 2")

    def test_onboarding_company_and_assistant(self):
        profile = CompanyProfileRequest(company_name=" 3M ", assistant_name=" Aria ")
        assert (profile.company_name, profile.assistant_name) == ("3M", "Aria")
        with pytest.raises(ValidationError, match="company name needs at least one letter"):
            CompanyProfileRequest(company_name="123")
        with pytest.raises(ValidationError, match="Enter a company name"):
            CompanyProfileRequest(company_name="   ")
        with pytest.raises(ValidationError, match="assistant name"):
            CompanyProfileRequest(company_name="Acme", assistant_name="!!!")

    def test_onboarding_assistant_stays_optional(self):
        assert CompanyProfileRequest(company_name="Acme").assistant_name is None
        assert CompanyProfileRequest(company_name="Acme", assistant_name="  ").assistant_name is None

    def test_affiliate_application(self):
        ok = ApplicationRequest(name="Sara  Malik", email="a@example.com", message="x" * 12)
        assert ok.name == "Sara Malik"
        with pytest.raises(ValidationError, match="can't contain numbers"):
            ApplicationRequest(name="1234", email="a@example.com", message="x" * 12)

    def test_waitlist(self):
        assert WaitlistSignup(email="a@example.com", first_name="").first_name is None
        assert WaitlistSignup(email="a@example.com", first_name=" Ali ").first_name == "Ali"
        with pytest.raises(ValidationError):
            WaitlistSignup(email="a@example.com", last_name="12")
