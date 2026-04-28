"""
applications.API.tests.test_emails
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for WelcomeEmail context building and dispatch logging.

Coverage
--------
WelcomeEmail.get_context_data()
  * All required context keys are present.
  * A new Token is created when the user has none.
  * An existing Token is reused (no duplicate created).
  * site_url / docs_url / swagger_url / graphql_url are derived from protocol+domain.

WelcomeEmail.send()
  * Delegates to the parent send() with the correct recipients.
  * Logs an attempt and a success entry on a clean send.
  * Logs an error entry and re-raises when parent send() raises.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.authtoken.models import Token

from applications.API.emails import WelcomeEmail

User = get_user_model()

_EMAIL_OVERRIDES = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "noreply@test.example.com",
}

# Super-class whose send() we stub out to avoid template-rendering overhead.
_PARENT_SEND = "djoser.email.ConfirmationEmail.send"


def _request(factory):
    req = factory.get("/")
    req.META.setdefault("SERVER_NAME", "testserver")
    req.META.setdefault("SERVER_PORT", "80")
    return req


@override_settings(**_EMAIL_OVERRIDES)
class WelcomeEmailContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.factory = RequestFactory()
        cls.user = User.objects.create_user(
            username="ctxuser",
            email="ctxuser@example.com",
            password="securepass123",
        )

    def _email(self, user=None):
        return WelcomeEmail(
            request=_request(self.factory),
            context={"user": user or self.user},
        )

    def test_all_required_context_keys_present(self):
        ctx = self._email().get_context_data()
        for key in (
            "api_key",
            "site_url",
            "site_domain",
            "docs_url",
            "swagger_url",
            "graphql_url",
        ):
            with self.subTest(key=key):
                self.assertIn(key, ctx)

    def test_token_created_when_none_exists(self):
        user = User.objects.create_user(
            username="notokenuser",
            email="notoken@example.com",
            password="securepass123",
        )
        Token.objects.filter(user=user).delete()

        ctx = self._email(user=user).get_context_data()

        token = Token.objects.get(user=user)
        self.assertEqual(ctx["api_key"], token.key)

    def test_existing_token_reused_no_duplicate(self):
        token, _ = Token.objects.get_or_create(user=self.user)

        ctx = self._email().get_context_data()

        self.assertEqual(ctx["api_key"], token.key)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 1)

    def test_url_fields_derived_from_protocol_and_domain(self):
        ctx = self._email().get_context_data()
        base = f"{ctx['protocol']}://{ctx['domain']}"

        self.assertEqual(ctx["site_url"], base)
        self.assertEqual(ctx["docs_url"], f"{base}/api/redoc")
        self.assertEqual(ctx["swagger_url"], f"{base}/api/swagger/")
        self.assertEqual(ctx["graphql_url"], f"{base}/graphql/playground")


@override_settings(**_EMAIL_OVERRIDES)
class WelcomeEmailSendTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="senduser",
            email="senduser@example.com",
            password="securepass123",
        )
        Token.objects.get_or_create(user=self.user)

    def _email(self):
        return WelcomeEmail(
            request=_request(self.factory),
            context={"user": self.user},
        )

    @patch(_PARENT_SEND)
    def test_delegates_to_parent_with_correct_recipients(self, mock_send):
        self._email().send(to=[self.user.email])

        mock_send.assert_called_once_with([self.user.email])

    @patch(_PARENT_SEND)
    def test_logs_attempt_and_success_on_clean_send(self, _mock_send):
        with patch("applications.API.emails.logger") as mock_logger:
            self._email().send(to=[self.user.email])

        self.assertEqual(mock_logger.info.call_count, 2)
        # First call should mention the recipient
        first_args = str(mock_logger.info.call_args_list[0])
        self.assertIn(self.user.email, first_args)

    @patch(_PARENT_SEND, side_effect=RuntimeError("SMTP refused"))
    def test_logs_error_and_reraises_on_failure(self, _mock_send):
        with patch("applications.API.emails.logger") as mock_logger:
            with self.assertRaises(RuntimeError, msg="SMTP refused"):
                self._email().send(to=[self.user.email])

        mock_logger.error.assert_called_once()
        error_args = str(mock_logger.error.call_args_list[0])
        self.assertIn(self.user.email, error_args)

    @patch(_PARENT_SEND, side_effect=RuntimeError("SMTP refused"))
    def test_exception_not_swallowed(self, _mock_send):
        with self.assertRaises(RuntimeError):
            self._email().send(to=[self.user.email])
