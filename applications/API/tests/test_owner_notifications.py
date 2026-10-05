"""
applications.API.tests.test_owner_notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for emailing a joke's submitter the outcome of a moderator review.

Coverage
--------
Insult._notify_owner_joke_status_change()
  * Sends one email per outcome to the submitter, with the outcome's subject.
  * Skips submitters without an email address.
  * Skips "modified" outcomes that have no reviewer notes.
  * "modified" emails quote the original and the published edit plus notes.
  * Later reviews of an admin-modified joke quote the published edit and
    never leak the old reviewer notes.
  * Greets the submitter by first name, falling back to username.
  * Send failures, empty sends and unknown outcomes are logged, never raised.

InsultAdmin review views
  * Every review button notifies the owner with the matching outcome.
  * No notification when the insult is no longer in the required status.
  * No notification when the model method fails to change the status.
  * The notification is deferred until the review transaction commits, and
    only the first of two conflicting reviews sends one.
"""

from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from applications.API.admin import InsultAdmin
from applications.API.emails import REVIEW_OUTCOMES
from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()

_EMAIL_OVERRIDES = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "noreply@test.example.com",
    "ADMINS": ["testadmin@example.com"],
}
_ADMIN_URLS = "applications.API.tests.admin_test_urls"
_NOTIFY = "applications.API.models.Insult._notify_owner_joke_status_change"


class _OwnerNotificationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.submitter = User.objects.create_user(
            username="joke_owner",
            email="owner@example.com",
            password="pass1234",  # nosec B106
            first_name="Pat",
        )
        cls.theme = Theme.objects.create(theme_key="ONT", theme_name="Owner Theme")
        cls.cat_a = InsultCategory.objects.create(
            category_key="OA", name="Owner Cat A", theme=cls.theme
        )
        cls.cat_b = InsultCategory.objects.create(
            category_key="OB", name="Owner Cat B", theme=cls.theme
        )

    def _make_insult(self, **overrides):
        """Create an insult and clear any admin "pending" email it triggered."""
        defaults = {
            "content": "Yo momma so old her birth certificate says expired.",
            "category": self.cat_a,
            "theme": self.theme,
            "nsfw": False,
            "status": Insult.STATUS.ACTIVE,
            "added_by": self.submitter,
        }
        defaults.update(overrides)
        insult = Insult.objects.create(**defaults)
        mail.outbox = []
        return insult


# ===========================================================================
# Insult._notify_owner_joke_status_change
# ===========================================================================


@override_settings(**_EMAIL_OVERRIDES)
class NotifyOwnerJokeStatusChangeTests(_OwnerNotificationBase):
    def test_sends_one_email_per_outcome_with_outcome_subject(self):
        for outcome, config in REVIEW_OUTCOMES.items():
            with self.subTest(outcome=outcome):
                insult = self._make_insult(reviewer_notes="Tightened the punchline.")

                insult._notify_owner_joke_status_change(outcome=outcome)

                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].subject, config["subject"])
                self.assertEqual(mail.outbox[0].to, ["owner@example.com"])

    def test_email_has_html_alternative_and_reference_id(self):
        insult = self._make_insult()

        insult._notify_owner_joke_status_change(outcome="approved")

        message = mail.outbox[0]
        self.assertIn(insult.reference_id, message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(insult.reference_id, html)

    def test_no_email_when_submitter_has_no_address(self):
        no_email = User.objects.create_user(
            username="ghost", password="pass1234"
        )  # nosec B106
        insult = self._make_insult(added_by=no_email)

        insult._notify_owner_joke_status_change(outcome="approved")

        self.assertEqual(mail.outbox, [])

    def test_modified_without_reviewer_notes_is_not_sent(self):
        insult = self._make_insult(
            is_admin_modified=True, modified_content="Edited joke.", reviewer_notes=""
        )

        insult._notify_owner_joke_status_change(outcome="modified")

        self.assertEqual(mail.outbox, [])

    def test_modified_quotes_original_edit_and_notes(self):
        insult = self._make_insult(
            content="Original joke.",
            is_admin_modified=True,
            modified_content="Edited joke.",
            reviewer_notes="Fixed the grammar.",
        )

        insult._notify_owner_joke_status_change(outcome="modified")

        body = mail.outbox[0].body
        self.assertIn('"Original joke."', body)
        self.assertIn('"Edited joke."', body)
        self.assertIn("Fixed the grammar.", body)

    def test_later_review_of_modified_joke_quotes_edit_without_old_notes(self):
        insult = self._make_insult(
            content="Original joke.",
            is_admin_modified=True,
            modified_content="Edited joke.",
            reviewer_notes="Old notes that must not leak.",
        )

        insult._notify_owner_joke_status_change(outcome="kept")

        body = mail.outbox[0].body
        self.assertIn('"Edited joke."', body)
        self.assertNotIn("Original joke.", body)
        self.assertNotIn("Old notes that must not leak.", body)

    def test_greets_by_first_name(self):
        insult = self._make_insult()

        insult._notify_owner_joke_status_change(outcome="approved")

        self.assertIn("Pat", mail.outbox[0].body)

    def test_greets_by_username_without_first_name(self):
        nameless = User.objects.create_user(
            username="nameless_owner",
            email="nameless@example.com",
            password="pw",  # nosec B106
        )
        insult = self._make_insult(added_by=nameless)

        insult._notify_owner_joke_status_change(outcome="approved")

        self.assertIn("nameless_owner", mail.outbox[0].body)

    @patch("applications.API.models.logger")
    def test_send_exception_is_logged_not_raised(self, mock_logger):
        insult = self._make_insult()

        with patch(
            "applications.API.emails.SubmissionReviewEmail.send",
            side_effect=RuntimeError("smtp down"),
        ):
            insult._notify_owner_joke_status_change(outcome="approved")  # no raise

        mock_logger.error.assert_called_once()
        self.assertIn("smtp down", mock_logger.error.call_args.args[0])
        mock_logger.success.assert_not_called()

    @patch("applications.API.models.logger")
    def test_nothing_sent_is_logged_as_error(self, mock_logger):
        insult = self._make_insult()

        with patch(
            "applications.API.emails.SubmissionReviewEmail.send", return_value=0
        ):
            insult._notify_owner_joke_status_change(outcome="approved")

        mock_logger.error.assert_called_once()
        mock_logger.success.assert_not_called()

    @patch("applications.API.models.logger")
    def test_unknown_outcome_is_logged_not_raised(self, mock_logger):
        insult = self._make_insult()

        insult._notify_owner_joke_status_change(outcome="not-a-real-outcome")

        self.assertEqual(mail.outbox, [])
        mock_logger.error.assert_called_once()


# ===========================================================================
# InsultAdmin review views -> owner notification
# ===========================================================================


@override_settings(ROOT_URLCONF=_ADMIN_URLS, **_EMAIL_OVERRIDES)
@patch(_NOTIFY)
class ReviewViewsNotifyOwnerTests(_OwnerNotificationBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            username="notify_admin",
            email="admin@example.com",
            password="adminpass",  # nosec B106
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.ma = InsultAdmin(Insult, AdminSite())

    def _request(self, method="post", data=None):
        request = getattr(self.factory, method)("/admin/API/insult/", data or {})
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _run(self, view, *args):
        """Call a review view and run its on_commit callbacks, as a real commit would."""
        with self.captureOnCommitCallbacks(execute=True):
            return view(*args)

    def _assert_notified(self, mock_notify, outcome):
        mock_notify.assert_called_once_with(outcome=outcome)

    # -- Pending - New --------------------------------------------------

    def test_approve_notifies_approved(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(self.ma.approve_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "approved")

    def test_reject_notifies_rejected(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(self.ma.reject_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "rejected")

    def test_modify_post_notifies_modified(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(
            self.ma.modify_view,
            self._request(
                data={"modified_content": "Edited.", "reviewer_notes": "Why."}
            ),
            insult.insult_id,
        )
        self._assert_notified(mock_notify, "modified")

    def test_modify_get_does_not_notify(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(self.ma.modify_view, self._request(method="get"), insult.insult_id)
        mock_notify.assert_not_called()

    def test_modify_invalid_form_does_not_notify(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(
            self.ma.modify_view,
            self._request(data={"modified_content": "Edited."}),
            insult.insult_id,
        )
        mock_notify.assert_not_called()

    # -- Flagged for Review ---------------------------------------------

    def test_flagged_reclassify_notifies_reclassified(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.FLAGGED)
        self._run(self.ma.flagged_reclassify_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "reclassified")

    def test_flagged_recategorize_post_notifies_recategorized(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.FLAGGED)
        self._run(
            self.ma.flagged_recategorize_view,
            self._request(data={"new_category": self.cat_b.pk}),
            insult.insult_id,
        )
        self._assert_notified(mock_notify, "recategorized")

    def test_flagged_remove_notifies_removed(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.FLAGGED)
        self._run(self.ma.flagged_remove_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "removed")

    def test_flagged_keep_notifies_kept(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.FLAGGED)
        self._run(self.ma.flagged_keep_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "kept")

    # -- No notification paths ------------------------------------------

    def test_wrong_status_does_not_notify(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.ACTIVE)
        self._run(self.ma.approve_view, self._request(), insult.insult_id)
        self._run(self.ma.flagged_keep_view, self._request(), insult.insult_id)
        mock_notify.assert_not_called()

    def test_failed_status_change_does_not_notify(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        with patch.object(Insult, "approve_insult", autospec=True):  # no-op
            self._run(self.ma.approve_view, self._request(), insult.insult_id)
        mock_notify.assert_not_called()

    def test_failed_recategorize_does_not_notify(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.FLAGGED)
        with patch.object(Insult, "re_categorize", autospec=True):  # no-op
            self._run(
                self.ma.flagged_recategorize_view,
                self._request(data={"new_category": self.cat_b.pk}),
                insult.insult_id,
            )
        mock_notify.assert_not_called()

    def test_notification_waits_for_commit(self, mock_notify):
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        with self.captureOnCommitCallbacks() as callbacks:
            self.ma.approve_view(self._request(), insult.insult_id)
            mock_notify.assert_not_called()
        for callback in callbacks:
            callback()
        self._assert_notified(mock_notify, "approved")

    def test_second_review_of_same_insult_does_not_notify(self, mock_notify):
        """The moderator who loses the race is turned away without an email."""
        insult = self._make_insult(status=Insult.STATUS.PENDING)
        self._run(self.ma.approve_view, self._request(), insult.insult_id)
        self._run(self.ma.reject_view, self._request(), insult.insult_id)
        self._assert_notified(mock_notify, "approved")
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
