"""
core.tests.test_mailer_backends
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for ImmediateDbBackend — the custom django-mailer backend that queues
and drains a message in the same call, so delivery doesn't depend on a
scheduled `manage.py send_mail` process (nothing in this deploy runs one).

Coverage
--------
* A message is delivered immediately — it lands in the real backend's
  outbox, and no row is left behind in the mailer queue.
* A successful send is recorded in mailer.MessageLog with RESULT_SUCCESS.
* send_messages() returns the number of messages sent, matching Django's
  EmailBackend contract.
* A transient SMTP-style failure is deferred and logged as a failure —
  not lost, not raised.
* A non-transient error is not swallowed by the deferral path; it
  propagates, and the message is left in the queue exactly as queued
  (not deferred, not deleted, not falsely logged) for the next send to
  pick back up.
* Base.EMAIL_BACKEND is wired to ImmediateDbBackend, guarding against a
  silent regression to plain (queue-only, never-drained) DbBackend.
"""

import ast
import inspect
import smtplib
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from mailer.models import (
    PRIORITY_DEFERRED,
    RESULT_FAILURE,
    RESULT_SUCCESS,
    Message,
    MessageLog,
)

from core.settings import Base, Development, Offline, Production, Staging


def _class_body_assigns(cls, name):
    """True if `name` is assigned directly in cls's own class body.

    django-configurations' metaclass flattens every resolved setting
    (including inherited ones) into each class's __dict__, so a plain
    `name in vars(cls)` can't tell "defined here" from "inherited from
    Base" — every environment class appears to have every setting. Reading
    the class body's own AST is the only reliable way to check that.
    """
    tree = ast.parse(inspect.getsource(cls))
    (class_node,) = tree.body
    for node in class_node.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return True
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return True
    return False


_BACKEND_OVERRIDES = {
    "EMAIL_BACKEND": "core.mailer_backends.ImmediateDbBackend",
    "MAILER_EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "MAILER_USE_FILE_LOCK": False,
}

_LOCMEM_SEND = "django.core.mail.backends.locmem.EmailBackend.send_messages"


@override_settings(**_BACKEND_OVERRIDES)
class ImmediateDbBackendDeliveryTests(TestCase):
    def test_send_mail_delivers_immediately(self):
        mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Subject")

    def test_successful_send_leaves_no_queued_message(self):
        mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        self.assertEqual(Message.objects.count(), 0)

    def test_successful_send_is_logged(self):
        mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        self.assertEqual(MessageLog.objects.count(), 1)
        self.assertEqual(MessageLog.objects.get().result, RESULT_SUCCESS)

    def test_send_messages_returns_count_sent(self):
        connection = mail.get_connection()
        sent = connection.send_messages(
            [
                mail.EmailMessage("A", "a", "from@example.com", ["to@example.com"]),
                mail.EmailMessage("B", "b", "from@example.com", ["to2@example.com"]),
            ]
        )

        self.assertEqual(sent, 2)
        self.assertEqual(len(mail.outbox), 2)


@override_settings(**_BACKEND_OVERRIDES)
class ImmediateDbBackendFailureTests(TestCase):
    @patch(
        _LOCMEM_SEND,
        side_effect=smtplib.SMTPRecipientsRefused(
            {"to@example.com": (550, b"no such user")}
        ),
    )
    def test_transient_failure_is_deferred_not_lost(self, _mock_send):
        mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.get().priority, PRIORITY_DEFERRED)

    @patch(
        _LOCMEM_SEND,
        side_effect=smtplib.SMTPRecipientsRefused(
            {"to@example.com": (550, b"no such user")}
        ),
    )
    def test_transient_failure_is_logged_as_failure(self, _mock_send):
        mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        self.assertEqual(MessageLog.objects.filter(result=RESULT_FAILURE).count(), 1)

    @patch(_LOCMEM_SEND, side_effect=RuntimeError("totally unexpected"))
    def test_unrecoverable_error_is_not_swallowed(self, _mock_send):
        with self.assertRaises(RuntimeError):
            mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

    @patch(_LOCMEM_SEND, side_effect=RuntimeError("totally unexpected"))
    def test_unrecoverable_error_leaves_message_queued_for_retry(self, _mock_send):
        with self.assertRaises(RuntimeError):
            mail.send_mail("Subject", "Body", "from@example.com", ["to@example.com"])

        # Deliberately not deferred/deleted/logged: an error outside
        # django-mailer's known-transient SMTP exceptions isn't assumed
        # recoverable by retry, so the message is left exactly as queued
        # for a human to notice, rather than silently marked handled.
        self.assertEqual(Message.objects.count(), 1)
        self.assertNotEqual(Message.objects.get().priority, PRIORITY_DEFERRED)
        self.assertEqual(MessageLog.objects.count(), 0)


class MailerSettingsWiringTests(TestCase):
    # Django's test runner forces EMAIL_BACKEND to locmem for the whole test
    # session, so these check the settings classes directly rather than the
    # runtime `django.conf.settings` object.

    def test_base_email_backend_is_immediate_db_backend(self):
        self.assertEqual(Base.EMAIL_BACKEND, "core.mailer_backends.ImmediateDbBackend")

    def test_environments_do_not_shadow_base_email_backend(self):
        for configuration in (Production, Offline, Development, Staging):
            with self.subTest(configuration=configuration.__name__):
                self.assertFalse(_class_body_assigns(configuration, "EMAIL_BACKEND"))
