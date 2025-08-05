# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from applications.API.forms import InsultReviewForm
from applications.API.models import Insult, InsultCategory


class InsultReviewFormTest(TestCase):
    """Test suite for InsultReviewForm validation."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.insult_category = InsultCategory.objects.create(
            category_key="TEST", name="Test Category"
        )
        self.admin_user = User.objects.create_user(
            username="admin_testuser",
            password="testpass123",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        # Create test insults
        self.insult1 = Insult.objects.create(
            content="Test insult 1",
            category="TEST",
            nsfw=False,
            added_on=settings.GLOBAL_NOW,
            reports_count=14,
            added_by=1,
            status=Insult.STATUS.ACTIVE,
        )
        self.insult2 = Insult.objects.create(
            content="Test insult 2",
            category="TEST",
            nsfw=False,
            added_on=settings.GLOBAL_NOW,
            reports_count=14,
            added_by=1,
            status=Insult.STATUS.ACTIVE,
        )
        self.insult3 = Insult.objects.create(
            content="Test insult 3",
            category="TEST",
            nsfw=False,
            added_on=settings.GLOBAL_NOW,
            reports_count=14,
            added_by=1,
            status=Insult.STATUS.ACTIVE,
        )

        # Base form data template
        self.base_form_data = {
            "anonymous": True,
            "reporter_first_name": None,
            "reporter_last_name": None,
            "post_review_contact_desired": False,
            "reporter_email": None,
            "insult_id": self.insult1.id,
        }

    def tearDown(self):
        """Clean up after each test method."""
        # Optional: Clean up any created objects if needed
        # Usually Django handles this automatically in tests

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures (run once for entire test class)."""
        super().setUpClass()
        # Add any class-level setup here if needed

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures."""
        super().tearDownClass()
        # Add any class-level cleanup here if needed

    def test_clean_anonymous_submission_valid(self):
        """Test valid anonymous submission."""
        form_data = self.base_form_data.copy()
        form = InsultReviewForm(data=form_data)

        self.assertTrue(form.is_valid())
        cleaned_data = form.clean()
        self.assertEqual(cleaned_data["anonymous"], True)
        self.assertIsNone(cleaned_data["reporter_first_name"])
        self.assertIsNone(cleaned_data["reporter_last_name"])

    def test_clean_non_anonymous_submission_valid(self):
        """Test valid non-anonymous submission."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "John",
                "reporter_last_name": "Doe",
                "insult_id": self.insult2.id,
            }
        )
        form = InsultReviewForm(data=form_data)

        self.assertTrue(form.is_valid())
        cleaned_data = form.clean()
        self.assertEqual(cleaned_data["reporter_first_name"], "John")
        self.assertEqual(cleaned_data["reporter_last_name"], "Doe")

    def test_clean_contact_desired_valid(self):
        """Test valid submission with contact desired."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "Jane",
                "reporter_last_name": "Smith",
                "post_review_contact_desired": True,
                "reporter_email": "jane@example.com",
                "insult_id": self.insult3.id,
            }
        )
        form = InsultReviewForm(data=form_data)

        self.assertTrue(form.is_valid())
        cleaned_data = form.clean()
        self.assertEqual(cleaned_data["reporter_email"], "jane@example.com")
        self.assertTrue(cleaned_data["post_review_contact_desired"])

    def test_clean_blank_first_name_raises_validation_error(self):
        """Test that blank first name for non-anonymous raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": " ",  # Blank space
                "reporter_last_name": "Doe",
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Name Not Provided - You have selected that you do not wish submit this report "
            "anonymously, but have not provided a first name. Please change your anonymity "
            "preference or enter a first name"
        )
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_blank_last_name_raises_validation_error(self):
        """Test that blank last name for non-anonymous raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "John",
                "reporter_last_name": " ",  # Blank space
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Name Not Provided - You have selected that you do not wish submit this report "
            "anonymously, but have not provided a last name, or last initial. Please change "
            "your anonymity preference or enter a last name"
        )
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_blank_email_with_contact_desired_raises_validation_error(self):
        """Test that blank email with contact desired raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "John",
                "reporter_last_name": "Doe",
                "post_review_contact_desired": True,
                "reporter_email": " ",  # Blank space
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Email Not Provided - You have selected that you wish to be contacted to know "
            "the desired outcome of the review, but have not provided an email address. "
            "Please change your results contact preference or enter a vaild email addrwss"
        )
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_invalid_insult_id_raises_validation_error(self):
        """Test that invalid insult ID raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "insult_id": 999,  # Non-existent ID
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = "Invaild Insult ID - Please confirm Insult ID"
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_missing_first_name_raises_validation_error(self):
        """Test that missing first name for non-anonymous raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": None,
                "reporter_last_name": "Doe",
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Name Not Provided - You have selected that you do not wish submit this report "
            "anonymously, but have not provided a first name. Please change your anonymity "
            "preference or enter a first name"
        )
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_missing_last_name_raises_validation_error(self):
        """Test that missing last name for non-anonymous raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "John",
                "reporter_last_name": None,
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Name Not Provided - You have selected that you do not wish submit this report "
            "anonymously, but have not provided a last name, or last initial. Please change "
            "your anonymity preference or enter a last name"
        )
        self.assertEqual(str(context.exception), expected_message)

    def test_clean_missing_email_with_contact_desired_raises_validation_error(self):
        """Test that missing email with contact desired raises ValidationError."""
        form_data = self.base_form_data.copy()
        form_data.update(
            {
                "anonymous": False,
                "reporter_first_name": "John",
                "reporter_last_name": "Doe",
                "post_review_contact_desired": True,
                "reporter_email": None,
            }
        )
        form = InsultReviewForm(data=form_data)

        with self.assertRaises(ValidationError) as context:
            form.clean()

        expected_message = (
            "Email Not Provided - You have selected that you wish to be contacted to know "
            "the desired outcome of the review, but have not provided an email address. "
            "Please change your results contact preference or enter a vaild email addrwss"
        )
        self.assertEqual(str(context.exception), expected_message)
