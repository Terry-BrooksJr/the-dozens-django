"""
applications.API.tests.test_signals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for Insult.set_reference_id() admin notification logic.

The notification is triggered directly inside set_reference_id(), which is
itself called from the generate_reference_id post_save signal handler.
There is no separate notification signal — the call lives in the model method
so it always has access to a fully-formed reference_id.

Coverage
--------
Insult._notify_admins_pending() / set_reference_id()
  * Only sends email for PENDING insults — not ACTIVE, REMOVED, REJECTED,
    or FLAGGED.
  * Exactly one email per new pending insult.
  * Email subject contains the reference ID and a "pending" phrase.
  * Email body contains: content, submitter name/username, category,
    NSFW classification, and the admin change-page URL.
  * A plain content-field update on an existing PENDING insult does NOT
    send a second email.
  * Approving (status → ACTIVE) an existing PENDING insult does NOT
    send a second email.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()

# Override both the email backend (so mail.outbox is used) and ADMINS so we
# have a known recipient to assert against.
_EMAIL_OVERRIDES = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "ADMINS": [("Test Admin", "testadmin@example.com")],
    "EMAIL_SUBJECT_PREFIX": "[Django] ",
}


@override_settings(**_EMAIL_OVERRIDES)
class NotifyAdminsPendingInsultSignalTests(TestCase):
    """Tests for the notify_admins_of_pending_insult post_save signal."""

    @classmethod
    def setUpTestData(cls):
        # Only non-Insult objects here — Insult creation triggers the signal,
        # which must run under the locmem backend override (active only during
        # individual test methods, not setUpTestData).
        cls.submitter = User.objects.create_user(
            username="contributor",
            email="contributor@example.com",
            password="pass1234",
            first_name="Terry",
            last_name="Brooks",
        )
        cls.theme = Theme.objects.create(theme_key="SIG", theme_name="Signal Theme")
        cls.cat = InsultCategory.objects.create(
            category_key="SC", name="Signal Cat", theme=cls.theme
        )

    def setUp(self):
        # Guarantee an empty outbox before every test regardless of ordering.
        mail.outbox = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_insult(self, status=Insult.STATUS.PENDING, nsfw=False, **kwargs):
        """Create and return an Insult; the signal fires automatically."""
        defaults = dict(
            content="Yo momma is so lazy she got a remote control to change TV channels on her TV.",
            category=self.cat,
            theme=self.theme,
            nsfw=nsfw,
            added_by=self.submitter,
        )
        defaults.update(kwargs)
        return Insult.objects.create(status=status, **defaults)

    # ------------------------------------------------------------------
    # Fire / no-fire conditions
    # ------------------------------------------------------------------

    def test_email_sent_for_new_pending_insult(self):
        """A newly created PENDING insult triggers exactly one admin email."""
        self._create_insult(status=Insult.STATUS.PENDING)
        self.assertEqual(len(mail.outbox), 1)

    def test_exactly_one_email_per_new_pending_insult(self):
        """Creating one PENDING insult must send exactly one email.

        set_reference_id() is called once per new insult from the
        generate_reference_id signal, and _notify_admins_pending() is
        called at most once inside it, so there should be no duplicates.
        """
        self._create_insult(status=Insult.STATUS.PENDING)
        self.assertEqual(len(mail.outbox), 1)

    def test_notification_sent_from_set_reference_id(self):
        """_notify_admins_pending is called inside set_reference_id, so the
        email reference_id field is always populated (never None)."""
        insult = self._create_insult(status=Insult.STATUS.PENDING)
        self.assertIsNotNone(insult.reference_id)
        self.assertIn(insult.reference_id, mail.outbox[0].body)

    def test_no_email_for_active_insult(self):
        """A newly created ACTIVE insult must NOT trigger a notification."""
        self._create_insult(status=Insult.STATUS.ACTIVE)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_for_removed_insult(self):
        self._create_insult(status=Insult.STATUS.REMOVED)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_for_rejected_insult(self):
        self._create_insult(status=Insult.STATUS.REJECTED)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_for_flagged_insult(self):
        self._create_insult(status=Insult.STATUS.FLAGGED)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_on_content_update_of_pending_insult(self):
        """Updating an existing PENDING insult's content must not resend the email."""
        insult = self._create_insult(status=Insult.STATUS.PENDING)
        mail.outbox = []  # clear the creation email

        insult.content = "Updated content value."
        insult.save(update_fields=["content"])

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_on_status_update_of_existing_insult(self):
        """Approving a PENDING insult (status → ACTIVE) must not resend the email."""
        insult = self._create_insult(status=Insult.STATUS.PENDING)
        mail.outbox = []

        insult.approve_insult()  # calls save(update_fields=["status", "last_modified"])

        self.assertEqual(len(mail.outbox), 0)

    # ------------------------------------------------------------------
    # Email subject
    # ------------------------------------------------------------------

    def test_subject_contains_reference_id(self):
        """The email subject includes the insult's reference ID."""
        insult = self._create_insult()
        self.assertIn(insult.reference_id, mail.outbox[0].subject)

    def test_subject_contains_pending_approval_phrase(self):
        """The subject communicates that the insult needs approval."""
        self._create_insult()
        subject = mail.outbox[0].subject.lower()
        self.assertIn("pending", subject)

    # ------------------------------------------------------------------
    # Email recipients
    # ------------------------------------------------------------------

    def test_email_sent_to_admins(self):
        """The notification is addressed to the configured ADMINS."""
        self._create_insult()
        recipients = mail.outbox[0].to
        self.assertIn("testadmin@example.com", recipients)

    # ------------------------------------------------------------------
    # Email body — content
    # ------------------------------------------------------------------

    def test_body_contains_insult_content(self):
        """Email body reproduces the insult text so admins can review inline."""
        insult = self._create_insult()
        self.assertIn(insult.content, mail.outbox[0].body)

    def test_body_contains_reference_id(self):
        insult = self._create_insult()
        self.assertIn(insult.reference_id, mail.outbox[0].body)

    def test_body_contains_submitter_username(self):
        """Email body includes the submitter's @username."""
        self._create_insult()
        self.assertIn(self.submitter.username, mail.outbox[0].body)

    def test_body_contains_submitter_full_name(self):
        """Email body includes the submitter's full name when set."""
        self._create_insult()
        full_name = self.submitter.get_full_name()
        self.assertIn(full_name, mail.outbox[0].body)

    def test_body_falls_back_to_username_when_no_full_name(self):
        """When first/last name are absent, the username appears in the body."""
        anon = User.objects.create_user(
            username="anon_contrib", email="anon@example.com", password="x"
        )
        insult = self._create_insult(added_by=anon)
        self.assertIn(anon.username, mail.outbox[0].body)

    def test_body_contains_category(self):
        """Email body includes the insult's category."""
        insult = self._create_insult()
        self.assertIn(str(insult.category), mail.outbox[0].body)

    def test_body_nsfw_yes_for_nsfw_insult(self):
        """Body says 'Yes' for the NSFW field when nsfw=True."""
        self._create_insult(nsfw=True)
        self.assertIn("Yes", mail.outbox[0].body)

    def test_body_nsfw_no_for_sfw_insult(self):
        """Body says 'No' for the NSFW field when nsfw=False."""
        self._create_insult(nsfw=False)
        self.assertIn("No", mail.outbox[0].body)

    def test_body_contains_admin_change_url(self):
        """Body includes the relative admin change-page URL for the insult."""
        insult = self._create_insult()
        expected_path = f"/admin/API/insult/{insult.insult_id}/change/"
        self.assertIn(expected_path, mail.outbox[0].body)

    # ------------------------------------------------------------------
    # Multiple insults → one email each
    # ------------------------------------------------------------------

    def test_each_pending_insult_triggers_its_own_email(self):
        """Creating N pending insults must produce exactly N notification emails."""
        for i in range(3):
            self._create_insult(content=f"Unique insult content #{i}")
        self.assertEqual(len(mail.outbox), 3)
