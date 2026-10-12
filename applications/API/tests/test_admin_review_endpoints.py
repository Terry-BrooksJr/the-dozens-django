"""
applications.API.tests.test_admin_review_endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request-level tests for the InsultAdmin single-insult review endpoints.

Unlike test_admin.py (which calls ModelAdmin methods directly), these go
through the Django test client, so URL routing, ``admin_view`` login checks,
``require_POST`` and the full middleware stack are exercised.

Coverage
--------
Method and permission enforcement
  * POST-only endpoints reject GET with 405 and change nothing.
  * Anonymous users are redirected to the admin login.
  * Staff without ``change_insult`` get 403; staff with it can review.
  * Unknown insult IDs return 404.

State transitions (Pending - New)
  * Approve: P -> A.  Reject: P -> R.
  * Modify: GET shows the form; POST publishes the edit (P -> A) and keeps
    the original ``content``; an invalid POST re-renders and changes nothing.

State transitions (Flagged for Review), with mixed report types
  * Reclassify: flips NSFW, F -> A; RE -> NCE, RC -> SJC, removal -> SJC.
  * Recategorize: moves category and theme, F -> A; RC -> NJC, RE -> SCE,
    removal -> SJC.
  * Remove: F -> X; every report -> X.
  * Do Nothing: F -> A unchanged; RE -> SCE, RC/removal -> SJC.
  * Already-resolved reports are never touched.

Failures and duplicate submissions
  * A model method that fails to change state reports an error, sends no
    notification, skips cache invalidation and leaves reports pending.
  * A second submission of the same review is a no-op with a warning.
  * An endpoint for the wrong status (e.g. approving a flagged insult) is a
    no-op with a warning.
  * A failing owner email never breaks the review.

Cache invalidation and notifications
  * Every successful review invalidates the insult cache once with
    ``reason="admin_<outcome>"``.
  * Every successful review emails the owner exactly once with the
    outcome's subject, regardless of how many reports were resolved.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import constants as message_levels
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.API.emails import REVIEW_OUTCOMES
from applications.API.models import Insult, InsultCategory, InsultReview, Theme

User = get_user_model()

_OVERRIDES = {
    "ROOT_URLCONF": "applications.API.tests.admin_test_urls",
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "noreply@test.example.com",
    "ADMINS": ["testadmin@example.com"],
    # Keep hero-image URLs independent of the environment's static storage.
    "EMAIL_ASSET_BASE_URL": "https://cdn.example.com/static",
}
_OWNER_EMAIL = "owner@example.com"
_INVALIDATE = "applications.API.admin.invalidate_insult_cache"
_SEND = "applications.API.emails.SubmissionReviewEmail.send"

RT = InsultReview.REVIEW_TYPE
RS = InsultReview.STATUS


@override_settings(**_OVERRIDES)
class _ReviewEndpointBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username="review_admin",
            email="admin@example.com",
            password="adminpass",  # nosec B106
        )
        cls.owner = User.objects.create_user(
            username="joke_owner",
            email=_OWNER_EMAIL,
            password="pass1234",  # nosec B106
            first_name="Pat",
        )
        cls.theme_a = Theme.objects.create(theme_key="RVA", theme_name="Review A")
        cls.theme_b = Theme.objects.create(theme_key="RVB", theme_name="Review B")
        cls.cat_a = InsultCategory.objects.create(
            category_key="RA", name="Review Cat A", theme=cls.theme_a
        )
        cls.cat_b = InsultCategory.objects.create(
            category_key="RB", name="Review Cat B", theme=cls.theme_b
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_insult(self, **overrides):
        """Create an insult; clears the admin "pending" email creation sends."""
        defaults = {
            "content": "Yo momma so old her social security number is 1.",
            "category": self.cat_a,
            "theme": self.theme_a,
            "nsfw": False,
            "status": Insult.STATUS.ACTIVE,
            "added_by": self.owner,
        }
        defaults.update(overrides)
        insult = Insult.objects.create(**defaults)
        mail.outbox = []
        return insult

    def _pending_insult(self, **overrides):
        return self._make_insult(status=Insult.STATUS.PENDING, **overrides)

    def _report(self, insult, review_type):
        return InsultReview.objects.create(
            insult=insult,
            insult_reference_id=insult.reference_id,
            review_type=review_type,
            rationale_for_review="Please review this joke.",
        )

    def _flagged_insult(self, *review_types, **overrides):
        """Create an active insult, then flag it by filing one report per type."""
        insult = self._make_insult(**overrides)
        reports = [self._report(insult, review_type) for review_type in review_types]
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.FLAGGED)
        mail.outbox = []
        return insult, reports

    def _post(self, url_name, insult_id, data=None):
        # Run the review's on_commit callbacks (owner email, cache
        # invalidation) as the real transaction commit would.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse(f"admin:{url_name}", args=[insult_id]), data
            )

    def _get(self, url_name, insult_id):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.get(reverse(f"admin:{url_name}", args=[insult_id]))

    def _owner_emails(self):
        return [m for m in mail.outbox if m.to == [_OWNER_EMAIL]]

    def _assert_owner_notified_once(self, outcome):
        emails = self._owner_emails()
        self.assertEqual(len(emails), 1, f"expected one {outcome!r} email")
        self.assertEqual(emails[0].subject, REVIEW_OUTCOMES[outcome]["subject"])

    def _messages(self, response):
        return [(m.level, str(m)) for m in get_messages(response.wsgi_request)]

    def _assert_message(self, response, level, fragment):
        self.assertTrue(
            any(
                lvl == level and fragment in text
                for lvl, text in self._messages(response)
            ),
            f"no level-{level} message containing {fragment!r}: "
            f"{self._messages(response)}",
        )

    def _statuses(self, reports):
        for report in reports:
            report.refresh_from_db()
        return [report.status for report in reports]


# ===========================================================================
# Method and permission enforcement
# ===========================================================================


class ReviewEndpointMethodTests(_ReviewEndpointBase):
    POST_ONLY_PENDING = ("API_insult_approve", "API_insult_reject")
    POST_ONLY_FLAGGED = (
        "API_insult_flagged_reclassify",
        "API_insult_flagged_remove",
        "API_insult_flagged_keep",
    )

    def test_post_only_endpoints_reject_get(self):
        for url_name in self.POST_ONLY_PENDING + self.POST_ONLY_FLAGGED:
            with self.subTest(url_name=url_name):
                if url_name in self.POST_ONLY_PENDING:
                    insult = self._pending_insult()
                    expected_status = Insult.STATUS.PENDING
                else:
                    insult, _ = self._flagged_insult(RT.RECLASSIFY)
                    expected_status = Insult.STATUS.FLAGGED

                response = self._get(url_name, insult.insult_id)

                self.assertEqual(response.status_code, 405)
                insult.refresh_from_db()
                self.assertEqual(insult.status, expected_status)
                self.assertEqual(self._owner_emails(), [])

    def test_modify_get_renders_form_prefilled_with_content(self):
        insult = self._pending_insult(content="Original joke.")

        response = self._get("API_insult_modify", insult.insult_id)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/insult_modify.html")
        self.assertEqual(
            response.context["form"].initial["modified_content"], "Original joke."
        )

    def test_recategorize_get_renders_form_with_open_reports(self):
        insult, reports = self._flagged_insult(RT.RECATEGORIZE, RT.REMOVAL)

        response = self._get("API_insult_flagged_recategorize", insult.insult_id)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/insult_flagged_recategorize.html")
        self.assertCountEqual(
            [r.pk for r in response.context["open_reports"]], [r.pk for r in reports]
        )

    def test_unknown_insult_returns_404(self):
        self.assertEqual(self._post("API_insult_approve", 999_999).status_code, 404)


class ReviewEndpointPermissionTests(_ReviewEndpointBase):
    def setUp(self):
        # No default login; each test picks its user.
        pass

    def test_anonymous_redirected_to_login(self):
        insult = self._pending_insult()

        response = self._post("API_insult_approve", insult.insult_id)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.PENDING)

    def test_non_staff_redirected_to_login(self):
        self.client.force_login(self.owner)
        insult = self._pending_insult()

        response = self._post("API_insult_approve", insult.insult_id)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.PENDING)

    def test_staff_without_change_permission_forbidden(self):
        staff = User.objects.create_user(
            username="view_only_staff", password="pw", is_staff=True  # nosec B106
        )
        self.client.force_login(staff)
        pending = self._pending_insult()
        flagged, reports = self._flagged_insult(RT.REMOVAL)

        responses = [
            self._post("API_insult_approve", pending.insult_id),
            self._post("API_insult_flagged_remove", flagged.insult_id),
            self._get("API_insult_modify", pending.insult_id),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 403)
        pending.refresh_from_db()
        flagged.refresh_from_db()
        self.assertEqual(pending.status, Insult.STATUS.PENDING)
        self.assertEqual(flagged.status, Insult.STATUS.FLAGGED)
        self.assertEqual(self._statuses(reports), [RS.PENDING])
        self.assertEqual(self._owner_emails(), [])

    def test_staff_with_change_permission_can_review(self):
        staff = User.objects.create_user(
            username="moderator_staff", password="pw", is_staff=True  # nosec B106
        )
        staff.user_permissions.add(
            Permission.objects.get(
                codename="change_insult",
                content_type=ContentType.objects.get_for_model(Insult),
            )
        )
        self.client.force_login(staff)
        insult = self._pending_insult()

        response = self._post("API_insult_approve", insult.insult_id)

        self.assertEqual(response.status_code, 302)
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self._assert_owner_notified_once("approved")


# ===========================================================================
# Pending - New transitions
# ===========================================================================


@patch(_INVALIDATE)
class PendingReviewTransitionTests(_ReviewEndpointBase):
    def test_approve(self, mock_invalidate):
        insult = self._pending_insult()

        response = self._post("API_insult_approve", insult.insult_id)

        self.assertRedirects(
            response,
            reverse("admin:API_insult_change", args=[insult.insult_id]),
            fetch_redirect_response=False,
        )
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self._assert_message(response, message_levels.SUCCESS, "approved")
        mock_invalidate.assert_called_once_with(reason="admin_approved")
        self._assert_owner_notified_once("approved")

    def test_approve_redirects_to_same_host_referer(self, _mock_invalidate):
        insult = self._pending_insult()
        referer = "http://testserver" + reverse("admin:API_insult_changelist")

        response = self.client.post(
            reverse("admin:API_insult_approve", args=[insult.insult_id]),
            HTTP_REFERER=referer,
        )

        self.assertEqual(response["Location"], referer)

    def test_approve_ignores_foreign_referer(self, _mock_invalidate):
        insult = self._pending_insult()

        response = self.client.post(
            reverse("admin:API_insult_approve", args=[insult.insult_id]),
            HTTP_REFERER="https://evil.example.com/phish",
        )

        self.assertEqual(
            response["Location"],
            reverse("admin:API_insult_change", args=[insult.insult_id]),
        )

    def test_reject(self, mock_invalidate):
        insult = self._pending_insult()

        response = self._post("API_insult_reject", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.REJECTED)
        self._assert_message(response, message_levels.SUCCESS, "rejected")
        mock_invalidate.assert_called_once_with(reason="admin_rejected")
        self._assert_owner_notified_once("rejected")

    def test_modify_publishes_edit_and_keeps_original(self, mock_invalidate):
        insult = self._pending_insult(content="Original joke.")

        response = self._post(
            "API_insult_modify",
            insult.insult_id,
            {"modified_content": "Edited joke.", "reviewer_notes": "Tightened it."},
        )

        self.assertRedirects(
            response,
            reverse("admin:API_insult_changelist"),
            fetch_redirect_response=False,
        )
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self.assertTrue(insult.is_admin_modified)
        self.assertEqual(insult.content, "Original joke.")
        self.assertEqual(insult.modified_content, "Edited joke.")
        self.assertEqual(insult.reviewer_notes, "Tightened it.")
        mock_invalidate.assert_called_once_with(reason="admin_modified")
        self._assert_owner_notified_once("modified")
        body = self._owner_emails()[0].body
        self.assertIn("Edited joke.", body)
        self.assertIn("Tightened it.", body)

    def test_modify_invalid_post_rerenders_and_changes_nothing(self, mock_invalidate):
        insult = self._pending_insult()

        response = self._post(
            "API_insult_modify", insult.insult_id, {"modified_content": "Edited."}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reviewer_notes", response.context["form"].errors)
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.PENDING)
        self.assertFalse(insult.is_admin_modified)
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])


# ===========================================================================
# Flagged for Review transitions (mixed report types)
# ===========================================================================


@patch(_INVALIDATE)
class FlaggedReviewTransitionTests(_ReviewEndpointBase):
    MIXED = (RT.RECLASSIFY, RT.RECATEGORIZE, RT.REMOVAL, RT.DUPLICATE, RT.MALICIOUS)

    def test_reclassify_flips_nsfw_and_resolves_each_report_by_type(
        self, mock_invalidate
    ):
        insult, reports = self._flagged_insult(*self.MIXED, nsfw=False)

        response = self._post("API_insult_flagged_reclassify", insult.insult_id)

        self.assertEqual(response.status_code, 302)
        insult.refresh_from_db()
        self.assertTrue(insult.nsfw)
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self.assertEqual(
            self._statuses(reports),
            [
                RS.NEW_CLASSIFICATION,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
            ],
        )
        mock_invalidate.assert_called_once_with(reason="admin_reclassified")
        self._assert_owner_notified_once("reclassified")

    def test_reclassify_nsfw_to_sfw(self, _mock_invalidate):
        insult, _ = self._flagged_insult(RT.RECLASSIFY, nsfw=True)

        self._post("API_insult_flagged_reclassify", insult.insult_id)

        insult.refresh_from_db()
        self.assertFalse(insult.nsfw)

    def test_recategorize_moves_category_and_theme_and_resolves_by_type(
        self, mock_invalidate
    ):
        insult, reports = self._flagged_insult(*self.MIXED)

        response = self._post(
            "API_insult_flagged_recategorize",
            insult.insult_id,
            {"new_category": self.cat_b.pk},
        )

        self.assertRedirects(
            response,
            reverse("admin:API_insult_changelist"),
            fetch_redirect_response=False,
        )
        insult.refresh_from_db()
        self.assertEqual(insult.category, self.cat_b)
        self.assertEqual(insult.theme, self.theme_b)
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self.assertEqual(
            self._statuses(reports),
            [
                RS.SAME_CLASSIFICATION,
                RS.NEW_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
            ],
        )
        mock_invalidate.assert_called_once_with(reason="admin_recategorized")
        self._assert_owner_notified_once("recategorized")

    def test_recategorize_invalid_post_changes_nothing(self, mock_invalidate):
        insult, reports = self._flagged_insult(RT.RECATEGORIZE)

        response = self._post(
            "API_insult_flagged_recategorize", insult.insult_id, {"new_category": ""}
        )

        self.assertEqual(response.status_code, 200)
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.FLAGGED)
        self.assertEqual(insult.category, self.cat_a)
        self.assertEqual(self._statuses(reports), [RS.PENDING])
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_remove_soft_deletes_and_closes_every_report(self, mock_invalidate):
        insult, reports = self._flagged_insult(*self.MIXED)

        self._post("API_insult_flagged_remove", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.REMOVED)
        self.assertEqual(self._statuses(reports), [RS.REMOVED] * len(self.MIXED))
        mock_invalidate.assert_called_once_with(reason="admin_removed")
        self._assert_owner_notified_once("removed")

    def test_keep_restores_unchanged_and_dismisses_by_type(self, mock_invalidate):
        insult, reports = self._flagged_insult(*self.MIXED, nsfw=False)

        self._post("API_insult_flagged_keep", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self.assertFalse(insult.nsfw)
        self.assertEqual(insult.category, self.cat_a)
        self.assertEqual(
            self._statuses(reports),
            [
                RS.SAME_CLASSIFICATION,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
                RS.SAME_CATEGORY,
            ],
        )
        mock_invalidate.assert_called_once_with(reason="admin_kept")
        self._assert_owner_notified_once("kept")

    def test_resolved_reports_record_reviewer_and_date(self, _mock_invalidate):
        insult, reports = self._flagged_insult(RT.RECLASSIFY, RT.REMOVAL)

        self._post("API_insult_flagged_keep", insult.insult_id)

        for report in reports:
            report.refresh_from_db()
            self.assertEqual(report.reviewer, self.admin_user)
            self.assertIsNotNone(report.date_reviewed)

    def test_already_resolved_reports_are_untouched(self, _mock_invalidate):
        insult, (open_report, closed_report) = self._flagged_insult(
            RT.RECLASSIFY, RT.RECLASSIFY
        )
        InsultReview.objects.filter(pk=closed_report.pk).update(
            status=RS.NEW_CLASSIFICATION
        )

        self._post("API_insult_flagged_remove", insult.insult_id)

        self.assertEqual(
            self._statuses([open_report, closed_report]),
            [RS.REMOVED, RS.NEW_CLASSIFICATION],
        )

    def test_many_reports_still_notify_owner_once(self, _mock_invalidate):
        insult, _ = self._flagged_insult(*(RT.REMOVAL,) * 4)

        self._post("API_insult_flagged_remove", insult.insult_id)

        self._assert_owner_notified_once("removed")


# ===========================================================================
# Failures, wrong-status and duplicate submissions
# ===========================================================================


@patch(_INVALIDATE)
class ReviewFailureAndDuplicateTests(_ReviewEndpointBase):
    def test_failed_approve_reports_error_and_skips_side_effects(self, mock_invalidate):
        insult = self._pending_insult()

        with patch.object(Insult, "approve_insult", autospec=True):  # no-op
            response = self._post("API_insult_approve", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.PENDING)
        self._assert_message(response, message_levels.ERROR, "Could not update")
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_failed_keep_leaves_reports_pending(self, mock_invalidate):
        insult, reports = self._flagged_insult(RT.RECLASSIFY, RT.REMOVAL)

        with patch.object(Insult, "approve_insult", autospec=True):  # no-op
            response = self._post("API_insult_flagged_keep", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.FLAGGED)
        self.assertEqual(self._statuses(reports), [RS.PENDING, RS.PENDING])
        self._assert_message(response, message_levels.ERROR, "Could not update")
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_failed_reclassify_leaves_insult_flagged(self, mock_invalidate):
        insult, reports = self._flagged_insult(RT.RECLASSIFY, nsfw=False)

        with patch.object(Insult, "reclassify", autospec=True):  # no-op
            response = self._post("API_insult_flagged_reclassify", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.FLAGGED)
        self.assertFalse(insult.nsfw)
        self.assertEqual(self._statuses(reports), [RS.PENDING])
        self._assert_message(response, message_levels.ERROR, "Could not reclassify")
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_failed_recategorize_leaves_insult_flagged(self, mock_invalidate):
        insult, reports = self._flagged_insult(RT.RECATEGORIZE)

        with patch.object(Insult, "re_categorize", autospec=True):  # no-op
            response = self._post(
                "API_insult_flagged_recategorize",
                insult.insult_id,
                {"new_category": self.cat_b.pk},
            )

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.FLAGGED)
        self.assertEqual(insult.category, self.cat_a)
        self.assertEqual(self._statuses(reports), [RS.PENDING])
        self._assert_message(response, message_levels.ERROR, "Could not recategorize")
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_owner_email_failure_does_not_break_review(self, mock_invalidate):
        insult, reports = self._flagged_insult(RT.REMOVAL)

        with patch(_SEND, side_effect=RuntimeError("smtp down")):
            response = self._post("API_insult_flagged_remove", insult.insult_id)

        self.assertEqual(response.status_code, 302)
        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.REMOVED)
        self.assertEqual(self._statuses(reports), [RS.REMOVED])
        mock_invalidate.assert_called_once_with(reason="admin_removed")

    def test_wrong_status_is_noop_with_warning(self, mock_invalidate):
        pending = self._pending_insult()
        flagged, reports = self._flagged_insult(RT.REMOVAL)

        cases = [
            ("API_insult_flagged_remove", pending, Insult.STATUS.PENDING),
            ("API_insult_flagged_keep", pending, Insult.STATUS.PENDING),
            ("API_insult_approve", flagged, Insult.STATUS.FLAGGED),
            ("API_insult_reject", flagged, Insult.STATUS.FLAGGED),
        ]
        for url_name, insult, expected_status in cases:
            with self.subTest(url_name=url_name):
                response = self._post(url_name, insult.insult_id)

                self.assertEqual(response.status_code, 302)
                self._assert_message(
                    response, message_levels.WARNING, "nothing was changed"
                )
                insult.refresh_from_db()
                self.assertEqual(insult.status, expected_status)

        self.assertEqual(self._statuses(reports), [RS.PENDING])
        mock_invalidate.assert_not_called()
        self.assertEqual(self._owner_emails(), [])

    def test_duplicate_approve_notifies_once(self, mock_invalidate):
        insult = self._pending_insult()

        self._post("API_insult_approve", insult.insult_id)
        second = self._post("API_insult_approve", insult.insult_id)

        self._assert_message(second, message_levels.WARNING, "nothing was changed")
        mock_invalidate.assert_called_once_with(reason="admin_approved")
        self._assert_owner_notified_once("approved")

    def test_approve_then_reject_does_not_reject(self, _mock_invalidate):
        insult = self._pending_insult()

        self._post("API_insult_approve", insult.insult_id)
        self._post("API_insult_reject", insult.insult_id)

        insult.refresh_from_db()
        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)
        self._assert_owner_notified_once("approved")

    def test_duplicate_modify_keeps_first_edit(self, mock_invalidate):
        insult = self._pending_insult()

        self._post(
            "API_insult_modify",
            insult.insult_id,
            {"modified_content": "First edit.", "reviewer_notes": "First."},
        )
        second = self._post(
            "API_insult_modify",
            insult.insult_id,
            {"modified_content": "Second edit.", "reviewer_notes": "Second."},
        )

        self.assertEqual(second.status_code, 302)
        insult.refresh_from_db()
        self.assertEqual(insult.modified_content, "First edit.")
        self.assertEqual(insult.reviewer_notes, "First.")
        mock_invalidate.assert_called_once_with(reason="admin_modified")
        self._assert_owner_notified_once("modified")

    def test_duplicate_flagged_submissions_notify_once(self, mock_invalidate):
        for url_name, outcome, needs_category in [
            ("API_insult_flagged_reclassify", "reclassified", False),
            ("API_insult_flagged_recategorize", "recategorized", True),
            ("API_insult_flagged_remove", "removed", False),
            ("API_insult_flagged_keep", "kept", False),
        ]:
            with self.subTest(url_name=url_name):
                mail.outbox = []
                mock_invalidate.reset_mock()
                insult, reports = self._flagged_insult(RT.RECLASSIFY, nsfw=False)
                payload = {"new_category": self.cat_b.pk} if needs_category else None

                self._post(url_name, insult.insult_id, payload)
                insult.refresh_from_db()
                after_first = (insult.status, insult.nsfw, insult.category_id)
                self._post(url_name, insult.insult_id, payload)

                insult.refresh_from_db()
                self.assertEqual(
                    (insult.status, insult.nsfw, insult.category_id), after_first
                )
                self.assertNotEqual(self._statuses(reports), [RS.PENDING])
                mock_invalidate.assert_called_once_with(reason=f"admin_{outcome}")
                self._assert_owner_notified_once(outcome)
