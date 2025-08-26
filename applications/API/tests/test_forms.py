# applications/API/tests/test_forms.py
from django.test import TestCase, override_settings
from django.utils import timezone

from applications.API.forms import InsultReviewForm
from applications.API.models import Insult, InsultCategory


@override_settings(ROOT_URLCONF="applications.API.tests.urls")
class InsultReviewFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Category + an active insult we can reference
        cls.cat = InsultCategory.objects.create(category_key="P", name="Poor")
        cls.insult = Insult.objects.create(
            reference_id="TEST_123",
            content="Yo momma is so poor she bought a ticket to nowhere.",
            category=cls.cat,
            nsfw=False,
            status="A",  # ACTIVE
            added_on=timezone.now(),
        )

    def _base_payload(self, **overrides):
        base = {
            "insult_reference_id": self.insult.reference_id,
            "anonymous": "on",  # simulate checked checkbox
            "reporter_first_name": "",
            "reporter_last_name": "",
            "post_review_contact_desired": "",
            "reporter_email": "",
            "rationale_for_review": "x" * 70,  # meets min_length
            "review_type": "R",  # assume e.g. 'R' is a valid choice (Review); adjust if different
        }
        base.update(overrides)
        return base

    def test_valid_when_anonymous_and_refid_ok(self):
        """Anonymous submission is valid with a real insult ref id and sufficient rationale."""
        form = InsultReviewForm(data=self._base_payload())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        # clean() should coerce insult_reference_id to the string ref id
        self.assertEqual(form.cleaned_data["insult_reference_id"], self.insult.reference_id)

    def test_invalid_when_non_anonymous_missing_names(self):
        """Non-anonymous requires first and last name."""
        data = self._base_payload(anonymous="", reporter_first_name="", reporter_last_name="")
        form = InsultReviewForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("First name is required", str(form.errors))
        self.assertIn("Last name is required", str(form.errors))

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
            post_review_contact_desired="on",
            reporter_email="",  # missing
        )
        form = InsultReviewForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("Email address is required", str(form.errors))

    def test_contact_desired_with_email_is_valid(self):
        data = self._base_payload(
            post_review_contact_desired="on",
            reporter_email="me@example.com",
        )
        form = InsultReviewForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_invalid_when_insult_reference_id_not_found(self):
        """Invalid if the ref id doesn't resolve via Insult.get_by_reference_id()."""
        data = self._base_payload(insult_reference_id="NOPE_999")
        form = InsultReviewForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid Insult ID", str(form.errors))

    def test_review_text_min_length_enforced_only_when_provided(self):
        """min_length=70 should fail if provided but too short; empty is allowed."""
        # Too short and provided -> invalid
        data_short = self._base_payload(rationale_for_review="way too short")
        form_short = InsultReviewForm(data=data_short)
        self.assertFalse(form_short.is_valid())
        self.assertIn("Ensure this value has at least 70 characters", str(form_short.errors))

        # Empty is allowed (field is not required)
        data_empty = self._base_payload(rationale_for_review="")
        form_empty = InsultReviewForm(data=data_empty)
        self.assertTrue(form_empty.is_valid(), form_empty.errors.as_json())

    def test_clean_sets_string_ref_id_even_if_whitespace(self):
        """Whitespace should be stripped in clean()."""
        data = self._base_payload(insult_reference_id=f"  {self.insult.reference_id}  ")
        form = InsultReviewForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data["insult_reference_id"], self.insult.reference_id)