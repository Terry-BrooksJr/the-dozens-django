from applications.API.models import Insult, InsultCategory
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory


def _check_ownership(self, obj, user):
    """Helper method to verify object ownership."""
    if obj.added_by != user:
        raise PermissionDenied(
            f"Object {obj.id} does not belong to user {user.username}"
        )


class BaseTestCase(TestCase):
    """Base test class with common setup and helper methods."""

    def setUp(self):
        """Common test setup."""
        self.factory = APIRequestFactory()
        self.user1 = User.objects.create_user(username="user1", id=1)
        self.user2 = User.objects.create_user(username="user2", id=2)
        self.test_category = InsultCategory.objects.create(
            category_key="TEST", name="Base Test Class Category"
        )

    def create_insult(self, **kwargs):
        """Helper method to create test insults."""
        defaults = {
            "content": "Test insult",
            "category": self.test_category,
            "status": "A",
            "nsfw": False,
            "added_by": self.user1,
        } | kwargs
        return Insult.objects.create(**defaults)
