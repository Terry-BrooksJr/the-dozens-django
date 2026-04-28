"""
applications.API.tests.test_admin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for InsultAdmin action methods and the view_reports_link helper.

Strategy
--------
* Instantiate InsultAdmin directly (no HTTP round-trip needed for action methods).
* Build fake requests with RequestFactory + FallbackStorage so that
  self.message_user() works without a real session/middleware stack.
* Use @override_settings(ROOT_URLCONF=...) only where reverse() must resolve
  admin URLs (i.e. the view_reports_link test).
* Every test that mutates DB state creates its own Insult to avoid cross-test
  contamination via stale Python objects from setUpTestData.
"""

from unittest.mock import patch

from django.contrib import messages as django_messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase, override_settings

from applications.API.admin import InsultAdmin, RecategorizeForm, UserAdmin
from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()

_ADMIN_URLS = "applications.API.tests.admin_test_urls"


# ---------------------------------------------------------------------------
# Shared test-data mixin
# ---------------------------------------------------------------------------


class _InsultAdminBase(TestCase):
    """Creates the minimum DB objects shared across all admin test classes."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin@example.com",
            password="adminpass",
            first_name="Admin",
            last_name="User",
        )
        cls.theme = Theme.objects.create(theme_key="ATH", theme_name="Admin Test Theme")
        cls.cat_a = InsultCategory.objects.create(
            category_key="AA", name="Alpha", theme=cls.theme
        )
        cls.cat_b = InsultCategory.objects.create(
            category_key="AB", name="Beta", theme=cls.theme
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.ma = InsultAdmin(Insult, self.site)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _request(self, method="get"):
        """Return a fake admin request with the messages framework wired up."""
        request = getattr(self.factory, method)("/admin/API/insult/")
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _post_request(self, data):
        """Return a fake POST request with the messages framework wired up."""
        request = self.factory.post("/admin/API/insult/", data)
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _make_insult(self, **kwargs):
        """Create a fresh Insult, rolled back after each test."""
        defaults = dict(
            content="Test insult content.",
            category=self.cat_a,
            theme=self.theme,
            nsfw=False,
            status=Insult.STATUS.ACTIVE,
            added_by=self.admin_user,
        )
        defaults.update(kwargs)
        return Insult.objects.create(**defaults)

    def _get_messages(self, request):
        return list(request._messages)


# ===========================================================================
# approve_insult
# ===========================================================================


class ApproveInsultActionTests(_InsultAdminBase):

    def test_sets_status_active(self):
        """approve_insult transitions every selected insult to ACTIVE."""
        target = self._make_insult(status=Insult.STATUS.PENDING)
        self.ma.approve_insult(self._request(), Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertEqual(target.status, Insult.STATUS.ACTIVE)

    def test_bulk_applies_to_all_selected(self):
        """approve_insult applies to the entire queryset, not just the first row."""
        targets = [self._make_insult(status=Insult.STATUS.PENDING) for _ in range(3)]
        qs = Insult.objects.filter(pk__in=[t.pk for t in targets])
        self.ma.approve_insult(self._request(), qs)
        for t in targets:
            t.refresh_from_db()
            self.assertEqual(t.status, Insult.STATUS.ACTIVE)

    def test_posts_success_message(self):
        """approve_insult calls message_user with an 'approved' message."""
        target = self._make_insult(status=Insult.STATUS.PENDING)
        request = self._request()
        self.ma.approve_insult(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("approved" in m.message.lower() for m in msgs))

    def test_message_includes_count(self):
        """The success message mentions how many insults were approved."""
        targets = [self._make_insult(status=Insult.STATUS.PENDING) for _ in range(2)]
        request = self._request()
        self.ma.approve_insult(
            request, Insult.objects.filter(pk__in=[t.pk for t in targets])
        )
        msg_text = " ".join(m.message for m in self._get_messages(request))
        self.assertIn("2", msg_text)


# ===========================================================================
# remove_insult
# ===========================================================================


class RemoveInsultActionTests(_InsultAdminBase):

    def test_sets_status_removed(self):
        """remove_insult soft-deletes (sets REMOVED) each selected insult."""
        target = self._make_insult(status=Insult.STATUS.ACTIVE)
        self.ma.remove_insult(self._request(), Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertEqual(target.status, Insult.STATUS.REMOVED)

    def test_bulk_applies_to_all_selected(self):
        targets = [self._make_insult(status=Insult.STATUS.ACTIVE) for _ in range(3)]
        qs = Insult.objects.filter(pk__in=[t.pk for t in targets])
        self.ma.remove_insult(self._request(), qs)
        for t in targets:
            t.refresh_from_db()
            self.assertEqual(t.status, Insult.STATUS.REMOVED)

    def test_posts_success_message(self):
        target = self._make_insult()
        request = self._request()
        self.ma.remove_insult(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("removed" in m.message.lower() for m in msgs))


# ===========================================================================
# mark_insult_for_review
# ===========================================================================


class MarkForReviewActionTests(_InsultAdminBase):

    def test_sets_status_pending(self):
        """mark_insult_for_review transitions each selected insult to PENDING."""
        target = self._make_insult(status=Insult.STATUS.ACTIVE)
        self.ma.mark_insult_for_review(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        target.refresh_from_db()
        self.assertEqual(target.status, Insult.STATUS.PENDING)

    def test_bulk_applies_to_all_selected(self):
        targets = [self._make_insult(status=Insult.STATUS.ACTIVE) for _ in range(2)]
        qs = Insult.objects.filter(pk__in=[t.pk for t in targets])
        self.ma.mark_insult_for_review(self._request(), qs)
        for t in targets:
            t.refresh_from_db()
            self.assertEqual(t.status, Insult.STATUS.PENDING)

    def test_posts_success_message(self):
        target = self._make_insult(status=Insult.STATUS.ACTIVE)
        request = self._request()
        self.ma.mark_insult_for_review(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("review" in m.message.lower() for m in msgs))


# ===========================================================================
# reclassify_as_nsfw / reclassify_as_sfw
# ===========================================================================


class ReclassifyActionTests(_InsultAdminBase):

    def test_reclassify_as_nsfw_sets_flag(self):
        """reclassify_as_nsfw sets nsfw=True on every selected insult."""
        target = self._make_insult(nsfw=False)
        self.ma.reclassify_as_nsfw(self._request(), Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertTrue(target.nsfw)

    def test_reclassify_as_sfw_clears_flag(self):
        """reclassify_as_sfw sets nsfw=False on every selected insult."""
        target = self._make_insult(nsfw=True)
        self.ma.reclassify_as_sfw(self._request(), Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertFalse(target.nsfw)

    def test_nsfw_bulk_applies_to_all_selected(self):
        targets = [self._make_insult(nsfw=False) for _ in range(3)]
        qs = Insult.objects.filter(pk__in=[t.pk for t in targets])
        self.ma.reclassify_as_nsfw(self._request(), qs)
        for t in targets:
            t.refresh_from_db()
            self.assertTrue(t.nsfw)

    def test_sfw_bulk_applies_to_all_selected(self):
        targets = [self._make_insult(nsfw=True) for _ in range(3)]
        qs = Insult.objects.filter(pk__in=[t.pk for t in targets])
        self.ma.reclassify_as_sfw(self._request(), qs)
        for t in targets:
            t.refresh_from_db()
            self.assertFalse(t.nsfw)

    def test_reclassify_as_nsfw_posts_message(self):
        target = self._make_insult(nsfw=False)
        request = self._request()
        self.ma.reclassify_as_nsfw(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("nsfw" in m.message.lower() for m in msgs))

    def test_reclassify_as_sfw_posts_message(self):
        target = self._make_insult(nsfw=True)
        request = self._request()
        self.ma.reclassify_as_sfw(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("sfw" in m.message.lower() for m in msgs))

    def test_reclassify_does_not_change_status(self):
        """Reclassifying NSFW flag must not alter the insult's approval status."""
        target = self._make_insult(nsfw=False, status=Insult.STATUS.ACTIVE)
        self.ma.reclassify_as_nsfw(self._request(), Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertEqual(target.status, Insult.STATUS.ACTIVE)


# ===========================================================================
# re_categorize  (intermediate-form action)
# ===========================================================================


class ReCategorizeActionTests(_InsultAdminBase):

    # --- first pass: renders the intermediate form ---

    def test_returns_template_response_on_first_call(self):
        """A plain GET-style call (no 'apply' in POST) returns a TemplateResponse."""
        target = self._make_insult()
        response = self.ma.re_categorize(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        self.assertIsInstance(response, TemplateResponse)

    def test_uses_correct_template(self):
        target = self._make_insult()
        response = self.ma.re_categorize(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        self.assertEqual(response.template_name, "admin/insult_re_categorize.html")

    def test_context_contains_recategorize_form(self):
        target = self._make_insult()
        response = self.ma.re_categorize(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        self.assertIn("form", response.context_data)
        self.assertIsInstance(response.context_data["form"], RecategorizeForm)

    def test_context_contains_selected_ids(self):
        target = self._make_insult()
        response = self.ma.re_categorize(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        self.assertIn("selected_ids", response.context_data)
        self.assertIn(target.pk, response.context_data["selected_ids"])

    def test_context_contains_insults_queryset(self):
        target = self._make_insult()
        response = self.ma.re_categorize(
            self._request(), Insult.objects.filter(pk=target.pk)
        )
        self.assertIn("insults", response.context_data)

    # --- second pass: applies the re-categorization ---

    def test_applies_new_category_on_post_with_apply(self):
        """Posting 'apply' + a valid category re-categorizes every selected insult."""
        target = self._make_insult(category=self.cat_a)
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": self.cat_b.pk,
                "_selected_ids": [str(target.pk)],
            }
        )
        result = self.ma.re_categorize(request, Insult.objects.filter(pk=target.pk))
        self.assertIsNone(result)  # None = redirect back to changelist
        target.refresh_from_db()
        self.assertEqual(target.category, self.cat_b)

    def test_theme_updated_with_category_on_apply(self):
        """re_categorize also updates the theme to match the new category's theme."""
        target = self._make_insult(category=self.cat_a)
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": self.cat_b.pk,
                "_selected_ids": [str(target.pk)],
            }
        )
        self.ma.re_categorize(request, Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertEqual(target.theme, self.cat_b.theme)

    def test_bulk_re_categorize_applies_to_all_selected(self):
        targets = [self._make_insult(category=self.cat_a) for _ in range(3)]
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": self.cat_b.pk,
                "_selected_ids": [str(t.pk) for t in targets],
            }
        )
        self.ma.re_categorize(
            request, Insult.objects.filter(pk__in=[t.pk for t in targets])
        )
        for t in targets:
            t.refresh_from_db()
            self.assertEqual(t.category, self.cat_b)

    def test_posts_success_message_on_apply(self):
        target = self._make_insult()
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": self.cat_b.pk,
                "_selected_ids": [str(target.pk)],
            }
        )
        self.ma.re_categorize(request, Insult.objects.filter(pk=target.pk))
        msgs = self._get_messages(request)
        self.assertTrue(any("re-categorized" in m.message.lower() for m in msgs))

    def test_invalid_form_redisplays_intermediate_page(self):
        """Posting 'apply' with a blank category redisplays the form (not None)."""
        target = self._make_insult()
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": "",  # intentionally invalid
                "_selected_ids": [str(target.pk)],
            }
        )
        response = self.ma.re_categorize(request, Insult.objects.filter(pk=target.pk))
        self.assertIsInstance(response, TemplateResponse)

    def test_invalid_form_does_not_change_category(self):
        """An invalid re_categorize POST must leave the insult's category unchanged."""
        target = self._make_insult(category=self.cat_a)
        request = self._post_request(
            {
                "apply": "Re-categorize",
                "new_category": "",
                "_selected_ids": [str(target.pk)],
            }
        )
        self.ma.re_categorize(request, Insult.objects.filter(pk=target.pk))
        target.refresh_from_db()
        self.assertEqual(target.category, self.cat_a)


# ===========================================================================
# search_fields — reference_id and added_by
# ===========================================================================


class InsultAdminSearchTests(_InsultAdminBase):
    """Verify that search_fields enables lookups by reference_id and submitter."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_user = User.objects.create_user(
            username="searchable_user",
            email="searchable@example.com",
            password="pass1234",
        )

    def test_search_fields_includes_reference_id(self):
        self.assertIn("reference_id", self.ma.search_fields)

    def test_search_fields_includes_username(self):
        self.assertIn("added_by__username", self.ma.search_fields)

    def test_search_fields_includes_email(self):
        self.assertIn("added_by__email", self.ma.search_fields)

    def test_search_by_reference_id_finds_match(self):
        target = self._make_insult(reference_id="REF_UNIQUE_001")
        other = self._make_insult(reference_id="REF_OTHER_999")
        qs, _ = self.ma.get_search_results(
            self._request(), Insult.objects.all(), "REF_UNIQUE_001"
        )
        self.assertIn(target, qs)
        self.assertNotIn(other, qs)

    def test_search_by_username_finds_match(self):
        target = self._make_insult(added_by=self.other_user, reference_id="REF_U_001")
        self._make_insult(added_by=self.admin_user, reference_id="REF_U_002")
        qs, _ = self.ma.get_search_results(
            self._request(), Insult.objects.all(), "searchable_user"
        )
        self.assertIn(target, qs)

    def test_search_by_email_finds_match(self):
        target = self._make_insult(added_by=self.other_user, reference_id="REF_E_001")
        self._make_insult(added_by=self.admin_user, reference_id="REF_E_002")
        qs, _ = self.ma.get_search_results(
            self._request(), Insult.objects.all(), "searchable@example.com"
        )
        self.assertIn(target, qs)

    def test_search_returns_empty_for_no_match(self):
        self._make_insult(reference_id="REF_NOMATCH_001")
        qs, _ = self.ma.get_search_results(
            self._request(), Insult.objects.all(), "ZZZNOMATCH"
        )
        self.assertEqual(qs.count(), 0)


# ===========================================================================
# view_reports_link  (requires admin URLs to be resolvable)
# ===========================================================================


@override_settings(ROOT_URLCONF=_ADMIN_URLS)
class ViewReportsLinkTests(_InsultAdminBase):

    def test_returns_anchor_tag(self):
        """view_reports_link returns an <a> tag linking to the InsultReview list."""
        target = self._make_insult()
        result = str(self.ma.view_reports_link(target))
        self.assertIn("<a", result)
        self.assertIn("</a>", result)

    def test_link_contains_insult_id_filter(self):
        """The URL in the link filters the changelist by the insult's primary key."""
        target = self._make_insult()
        result = str(self.ma.view_reports_link(target))
        self.assertIn(f"insult__id__exact={target.insult_id}", result)

    def test_link_text_shows_report_count(self):
        """Link label shows the current reports_count value."""
        target = self._make_insult()
        result = str(self.ma.view_reports_link(target))
        self.assertIn(f"View Reports ({target.reports_count})", result)

    def test_link_targets_insult_review_changelist(self):
        """The href points at the InsultReview admin changelist URL."""
        target = self._make_insult()
        result = str(self.ma.view_reports_link(target))
        self.assertIn("/admin/API/insultreview/", result)


# ===========================================================================
# UserAdmin.resend_welcome_email
# ===========================================================================

_PATCH_SEND = "applications.API.admin.WelcomeEmail.send"


class ResendWelcomeEmailActionTests(TestCase):
    """Tests for UserAdmin.resend_welcome_email action."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username="superadmin",
            email="super@example.com",
            password="adminpass",
        )
        cls.user_a = User.objects.create_user(
            username="alpha", email="alpha@example.com", password="pass1234"
        )
        cls.user_b = User.objects.create_user(
            username="beta", email="beta@example.com", password="pass1234"
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.ma = UserAdmin(User, self.site)

    def _request(self):
        request = self.factory.get("/admin/auth/user/")
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _get_messages(self, request):
        return list(request._messages)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    @patch(_PATCH_SEND)
    def test_sends_email_to_each_selected_user(self, mock_send):
        qs = User.objects.filter(pk__in=[self.user_a.pk, self.user_b.pk])
        self.ma.resend_welcome_email(self._request(), qs)
        self.assertEqual(mock_send.call_count, 2)

    @patch(_PATCH_SEND)
    def test_recipient_address_matches_user_email(self, mock_send):
        qs = User.objects.filter(pk=self.user_a.pk)
        self.ma.resend_welcome_email(self._request(), qs)
        mock_send.assert_called_once_with(to=[self.user_a.email])

    @patch(_PATCH_SEND)
    def test_success_message_posted_with_correct_count(self, _mock_send):
        qs = User.objects.filter(pk__in=[self.user_a.pk, self.user_b.pk])
        request = self._request()
        self.ma.resend_welcome_email(request, qs)
        msgs = self._get_messages(request)
        success_msgs = [m for m in msgs if m.level == django_messages.SUCCESS]
        self.assertEqual(len(success_msgs), 1)
        self.assertIn("2", success_msgs[0].message)

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    @patch(_PATCH_SEND, side_effect=RuntimeError("SMTP error"))
    def test_failure_posts_error_message(self, _mock_send):
        qs = User.objects.filter(pk=self.user_a.pk)
        request = self._request()
        self.ma.resend_welcome_email(request, qs)
        msgs = self._get_messages(request)
        error_msgs = [m for m in msgs if m.level == django_messages.ERROR]
        self.assertEqual(len(error_msgs), 1)

    @patch(_PATCH_SEND, side_effect=RuntimeError("SMTP error"))
    def test_failure_does_not_post_success_message(self, _mock_send):
        qs = User.objects.filter(pk=self.user_a.pk)
        request = self._request()
        self.ma.resend_welcome_email(request, qs)
        msgs = self._get_messages(request)
        self.assertFalse(any(m.level == django_messages.SUCCESS for m in msgs))

    @patch(_PATCH_SEND)
    def test_partial_failure_reports_both_counts(self, mock_send):
        mock_send.side_effect = [None, RuntimeError("SMTP error")]
        qs = User.objects.filter(pk__in=[self.user_a.pk, self.user_b.pk])
        request = self._request()
        self.ma.resend_welcome_email(request, qs)
        msgs = self._get_messages(request)
        levels = {m.level for m in msgs}
        self.assertIn(django_messages.SUCCESS, levels)
        self.assertIn(django_messages.ERROR, levels)
