"""
Tests for applications.ld_integration.context.context_from_request.

Covers:
- No `request.user` attribute at all -> anonymous context
- AnonymousUser -> anonymous context
- A user object with is_authenticated=False -> anonymous context
- Authenticated user -> keyed context built from pk, with name/email/is_staff/is_superuser set
- Authenticated user with no get_full_name() result falls back to username
- Custom anonymous_key_fallback is honored
"""

from __future__ import annotations

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from applications.ld_integration.context import context_from_request


class ContextFromRequestAnonymousTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_missing_user_attribute_yields_anonymous_context(self):
        request = self.factory.get("/")
        # RequestFactory does not attach .user by default.
        self.assertFalse(hasattr(request, "user"))

        ctx = context_from_request(request)

        self.assertTrue(ctx.anonymous)
        self.assertEqual(ctx.key, "anon")

    def test_anonymous_user_yields_anonymous_context(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        ctx = context_from_request(request)

        self.assertTrue(ctx.anonymous)
        self.assertEqual(ctx.key, "anon")

    def test_user_with_is_authenticated_false_yields_anonymous_context(self):
        request = self.factory.get("/")
        request.user = SimpleNamespace(is_authenticated=False)

        ctx = context_from_request(request)

        self.assertTrue(ctx.anonymous)

    def test_custom_anonymous_key_fallback_is_used(self):
        request = self.factory.get("/")
        request.user = None

        ctx = context_from_request(request, anonymous_key_fallback="guest-123")

        self.assertTrue(ctx.anonymous)
        self.assertEqual(ctx.key, "guest-123")


class ContextFromRequestAuthenticatedTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_authenticated_user_uses_pk_as_key(self):
        user = User.objects.create_user(
            username="jdoe", email="jdoe@example.com", password="pw"
        )
        request = self.factory.get("/")
        request.user = user

        ctx = context_from_request(request)

        self.assertFalse(ctx.anonymous)
        self.assertEqual(ctx.key, str(user.pk))

    def test_authenticated_user_sets_email_is_staff_is_superuser(self):
        user = User.objects.create_user(
            username="jdoe2",
            email="jdoe2@example.com",
            password="pw",
            is_staff=True,
            is_superuser=True,
        )
        request = self.factory.get("/")
        request.user = user

        ctx = context_from_request(request)

        self.assertEqual(ctx.get("email"), "jdoe2@example.com")
        self.assertTrue(ctx.get("is_staff"))
        self.assertTrue(ctx.get("is_superuser"))

    def test_authenticated_user_defaults_is_staff_is_superuser_false(self):
        user = User.objects.create_user(
            username="jdoe3", email="jdoe3@example.com", password="pw"
        )
        request = self.factory.get("/")
        request.user = user

        ctx = context_from_request(request)

        self.assertFalse(ctx.get("is_staff"))
        self.assertFalse(ctx.get("is_superuser"))

    def test_full_name_used_as_context_name_when_present(self):
        user = User.objects.create_user(
            username="jdoe4",
            email="jdoe4@example.com",
            password="pw",
            first_name="Jane",
            last_name="Doe",
        )
        request = self.factory.get("/")
        request.user = user

        ctx = context_from_request(request)

        self.assertEqual(ctx.name, "Jane Doe")

    def test_username_used_as_context_name_when_full_name_blank(self):
        user = User.objects.create_user(
            username="nofullname", email="nofullname@example.com", password="pw"
        )
        request = self.factory.get("/")
        request.user = user

        ctx = context_from_request(request)

        self.assertEqual(ctx.name, "nofullname")

    def test_falls_back_to_username_when_pk_and_id_are_absent(self):
        # A user-like object without pk/id must key off get_username().
        fake_user = SimpleNamespace(
            is_authenticated=True,
            pk=None,
            id=None,
            get_username=lambda: "fallback-username",
            get_full_name=lambda: "",
            email="fallback@example.com",
            is_staff=False,
            is_superuser=False,
        )
        request = self.factory.get("/")
        request.user = fake_user

        ctx = context_from_request(request)

        self.assertEqual(ctx.key, "fallback-username")
