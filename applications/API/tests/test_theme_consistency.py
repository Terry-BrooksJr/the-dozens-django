"""
Tests for Insult model theme consistency enforcement.

This module tests that insults always have themes that match their category's theme.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()


class InsultThemeConsistencyTests(TestCase):
    """Test suite for ensuring theme consistency between Insult and InsultCategory."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for theme consistency tests."""
        # Create users
        cls.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create themes
        cls.theme1 = Theme.objects.create(theme_name="Theme 1", theme_key="T1")
        cls.theme2 = Theme.objects.create(theme_name="Theme 2", theme_key="T2")

        # Create categories
        cls.category_theme1 = InsultCategory.objects.create(
            category_key="C1",
            name="Category 1",
            description="Category in Theme 1",
            theme=cls.theme1,
        )
        cls.category_theme2 = InsultCategory.objects.create(
            category_key="C2",
            name="Category 2",
            description="Category in Theme 2",
            theme=cls.theme2,
        )

    def test_create_insult_without_theme_auto_sets_from_category(self):
        """Test that creating an insult without theme automatically sets it from category."""
        insult = Insult.objects.create(
            content="Test insult without explicit theme",
            category=self.category_theme1,
            # Note: theme is NOT set explicitly
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        # Theme should be automatically set from category
        self.assertEqual(insult.theme, self.theme1)
        self.assertEqual(insult.theme, insult.category.theme)

    def test_create_insult_with_matching_theme_succeeds(self):
        """Test that creating an insult with correct theme works."""
        insult = Insult.objects.create(
            content="Test insult with matching theme",
            category=self.category_theme1,
            theme=self.theme1,
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        self.assertEqual(insult.theme, self.theme1)
        self.assertEqual(insult.theme, insult.category.theme)

    def test_create_insult_with_mismatched_theme_corrects_automatically(self):
        """Test that creating an insult with wrong theme auto-corrects it."""
        insult = Insult.objects.create(
            content="Test insult with mismatched theme",
            category=self.category_theme1,  # Theme 1
            theme=self.theme2,  # Wrong theme!
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        # Theme should be auto-corrected to match category's theme
        self.assertEqual(insult.theme, self.theme1)
        self.assertNotEqual(insult.theme, self.theme2)

    def test_clean_validates_theme_category_consistency(self):
        """Test that full_clean() validates theme matches category."""
        insult = Insult(
            content="Test insult for validation",
            category=self.category_theme1,  # Theme 1
            theme=self.theme2,  # Wrong theme!
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        # full_clean() should raise ValidationError for mismatched theme
        with self.assertRaises(ValidationError) as cm:
            insult.full_clean()

        # Check that the error is about theme mismatch
        self.assertIn("theme", cm.exception.error_dict)

    def test_re_categorize_updates_theme(self):
        """Test that re_categorize() also updates the theme."""
        # Create insult in category with theme1
        insult = Insult.objects.create(
            content="Test insult for re-categorization",
            category=self.category_theme1,
            theme=self.theme1,
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        # Verify initial state
        self.assertEqual(insult.theme, self.theme1)

        # Re-categorize to category with theme2
        insult.re_categorize(self.category_theme2)

        # Refresh from database
        insult.refresh_from_db()

        # Theme should be updated to match new category's theme
        self.assertEqual(insult.category, self.category_theme2)
        self.assertEqual(insult.theme, self.theme2)
        self.assertEqual(insult.theme, insult.category.theme)

    def test_update_category_updates_theme(self):
        """Test that updating category field also updates theme via save()."""
        insult = Insult.objects.create(
            content="Test insult for category update",
            category=self.category_theme1,
            theme=self.theme1,
            nsfw=False,
            added_by=self.user,
            added_on=timezone.now(),
        )

        # Update category directly
        insult.category = self.category_theme2
        insult.save()

        # Refresh from database
        insult.refresh_from_db()

        # Theme should be updated automatically
        self.assertEqual(insult.theme, self.theme2)
        self.assertEqual(insult.theme, insult.category.theme)

    def test_bulk_create_consistency(self):
        """Test that bulk creation doesn't bypass theme consistency."""
        # Bulk create with mismatched themes
        insults = Insult.objects.bulk_create(
            [
                Insult(
                    content=f"Bulk insult {i}",
                    category=self.category_theme1,
                    theme=self.theme2 if i % 2 else self.theme1,  # Mixed themes
                    nsfw=False,
                    added_by=self.user,
                    added_on=timezone.now(),
                )
                for i in range(3)
            ]
        )
