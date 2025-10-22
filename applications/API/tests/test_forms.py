"""
module: applications.API.tests.test_forms
TODO: Complete Summary 
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from applications.API.forms import InsultReviewForm
from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()


@override_settings(ROOT_URLCONF="applications.API.tests.urls")
class InsultReviewFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username="owner", email="owner@example.com", password="pass1234"
        )
        cls.theme = Theme.objects.create(theme_name="Test Theme", theme_key="TEST")
        cls.cat = InsultCategory.objects.create(
            category_key="P", name="Poor", theme=cls.theme
        )
        cls.insult = Insult.objects.create(
            content="Yo momma is so poor she bought a ticket to nowhere.",
            category=cls.cat,
            theme=cls.theme,
            nsfw=False,
            status="A",  # ACTIVE
            added_on=timezone.now(),
            added_by=cls.user,
        )

    def _base_payload(self, **overrides):
        base = {
            "insult_reference_id": self.insult.reference_id,
            "anonymous": "true",  # simulate checked checkbox
            "reporter_first_name": "Dummy",
            "reporter_last_name": "Reporter",
            "post_review_contact_desired": "false",
            "reporter_email": "",
            "rationale_for_review": "x" * 70,  # meets min_length
            "review_type": "RE",
        }
        base.update(overrides)
        return base

    def test_valid_when_anonymous_and_refid_ok(self):
        """Anonymous submission is valid with a real insult ref id and sufficient rationale."""
        form = InsultReviewForm(data=self._base_payload())
        self.assertTrue(form.is_valid())
        # clean() should coerce insult_reference_id to the string ref id
        self.assertEqual(
            form.cleaned_data["insult_reference_id"], self.insult.reference_id
        )

    def test_invalid_when_non_anonymous_missing_names(self):
        """Non-anonymous requires first and last name."""
        data = self._base_payload(
            anonymous="", reporter_first_name="", reporter_last_name=""
        )
        self.assert_form_invalid_and_error_present(  # noqa
            data, "First name is required when not submitting anonymously"
        )

    def test_valid_when_non_anonymous_with_names(self):
        """Non-anonymous becomes valid once names are provided."""
        data = self._base_payload(
            anonymous="",
            reporter_first_name="Terry",
            reporter_last_name="B.",
        )
        form = InsultReviewForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_contact_desired_requires_email(self):
        """If user wants follow-up contact, email is required."""
        data = self._base_payload(
            post_review_contact_desired="true",
            reporter_email="",  # missing
        )
        self.assert_form_invalid_and_error_present(data, "Email address is required")

    def test_contact_desired_with_email_is_valid(self):
        data = self._base_payload(
            post_review_contact_desired="true",
            reporter_email="me@example.com",
        )
        form = InsultReviewForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_invalid_when_insult_reference_id_not_found(self):
        """Invalid if the ref id doesn't resolve via Insult.get_by_reference_id()."""
        data = self._base_payload(insult_reference_id="NOPE_999")
        self.assert_form_invalid_and_error_present(data, "Invalid Insult ID")

    def test_review_text_min_length_enforced_only_when_provided(self):
        """min_length=70 should fail if provided but too short; empty is allowed."""
        # Too short and provided -> invalid
        data_short = self._base_payload(rationale_for_review="way too short")
        form_short = self.assert_form_invalid_and_error_present(
            data_short,
            "Please Ensure The Basis of your review request is 70 characters or more.",
        )
        # Empty is allowed (field is not required)
        data_empty = self._base_payload(rationale_for_review="")
        form_empty = InsultReviewForm(data=data_empty)
        # form_short = InsultReviewForm(data=form_short)
        self.assertFalse(form_empty.is_valid(), form_empty.errors.as_json())
        # self.assertFalse(form_short.is_valid(), form_short.errors.as_json())

    def assert_form_invalid_and_error_present(self, form_data, expected_error):
        """
        Helper method to test that the InsultReviewForm is invalid and contains the expected error message.

        Args:
            form_data (dict): The form data to be validated.
            expected_error (str): The expected error message or key to be found in the form errors.

        Returns:
            InsultReviewForm: The form instance after validation.
        """
        result = InsultReviewForm(data=form_data)
        self.assertFalse(result.is_valid())
        errors = dict(result.errors)
        self.assertIn(expected_error, errors["__all__"])
        return result

    def test_clean_sets_string_ref_id_even_if_whitespace(self):
        """Whitespace should be stripped in clean()."""
        data = self._base_payload(insult_reference_id=f"  {self.insult.reference_id}  ")
        form = InsultReviewForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(
            form.cleaned_data["insult_reference_id"], self.insult.reference_id
        )
