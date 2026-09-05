"""
Tests for applications.API.permissions.IsOwnerOrReadOnly.

Covers:
- SAFE_METHODS (GET/HEAD/OPTIONS) are always allowed, regardless of ownership.
- A write method (POST/PUT/PATCH/DELETE) is allowed for the object's owner.
- A write method is denied for a non-owner, non-staff user.
- A write method is allowed for a staff user editing someone else's object —
  the staff bypass branch, previously untested.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from applications.API.permissions import IsOwnerOrReadOnly

User = get_user_model()


class IsOwnerOrReadOnlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pw"
        )
        cls.other = User.objects.create_user(
            username="other", email="other@example.com", password="pw"
        )
        cls.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw", is_staff=True
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOwnerOrReadOnly()
        self.obj = SimpleNamespace(added_by=self.owner)

    def _request(self, method, user):
        request = getattr(self.factory, method.lower())("/")
        request.user = user
        return request

    def test_safe_method_allowed_for_non_owner(self):
        request = self._request("get", self.other)

        self.assertTrue(self.permission.has_object_permission(request, None, self.obj))

    def test_safe_method_allowed_for_anonymous_style_non_owner(self):
        request = self._request("head", self.other)

        self.assertTrue(self.permission.has_object_permission(request, None, self.obj))

    def test_write_method_allowed_for_owner(self):
        request = self._request("put", self.owner)

        self.assertTrue(self.permission.has_object_permission(request, None, self.obj))

    def test_write_method_denied_for_non_owner_non_staff(self):
        request = self._request("delete", self.other)

        self.assertFalse(self.permission.has_object_permission(request, None, self.obj))

    def test_write_method_allowed_for_staff_non_owner(self):
        """Staff users may edit/delete objects they don't own."""
        request = self._request("patch", self.staff)

        self.assertTrue(self.permission.has_object_permission(request, None, self.obj))
