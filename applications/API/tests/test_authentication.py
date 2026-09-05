"""
Tests for applications.API.authentication.FlexibleTokenAuthentication.

Covers:
- Standard ``Authorization: Token <key>`` header still authenticates (regression
  guard on the super().authenticate() delegation).
- Bare ``Authorization: <key>`` (no "Token" keyword) authenticates via the
  fallback path — this is the entire reason the subclass exists.
- A bare, unregistered token raises AuthenticationFailed.
- A bare token belonging to an inactive user raises AuthenticationFailed.
- No Authorization header at all returns None (unauthenticated, not an error).
- A two-part header using an unrecognized scheme (e.g. "Bearer <key>") returns
  None rather than falling into the bare-token fallback.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed

from applications.API.authentication import FlexibleTokenAuthentication

User = get_user_model()


class FlexibleTokenAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tokenuser", email="tokenuser@example.com", password="pw12345"
        )
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self):
        self.factory = RequestFactory()
        self.auth = FlexibleTokenAuthentication()

    def test_standard_token_prefix_still_authenticates(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Token {self.token.key}")

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        user, token = result
        self.assertEqual(user, self.user)
        self.assertEqual(token, self.token)

    def test_bare_token_authenticates_via_fallback(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION=self.token.key)

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        user, token = result
        self.assertEqual(user, self.user)
        self.assertEqual(token, self.token)

    def test_bare_unregistered_token_raises_authentication_failed(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION="not-a-real-token")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_bare_token_for_inactive_user_raises_authentication_failed(self):
        inactive_user = User.objects.create_user(
            username="inactive", email="inactive@example.com", password="pw"
        )
        inactive_user.is_active = False
        inactive_user.save(update_fields=["is_active"])
        inactive_token = Token.objects.create(user=inactive_user)

        request = self.factory.get("/", HTTP_AUTHORIZATION=inactive_token.key)

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_missing_authorization_header_returns_none(self):
        request = self.factory.get("/")

        self.assertIsNone(self.auth.authenticate(request))

    def test_unrecognized_two_part_scheme_returns_none(self):
        """A "Bearer <token>" style header must not fall into the bare-token path."""
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {self.token.key}")

        self.assertIsNone(self.auth.authenticate(request))
