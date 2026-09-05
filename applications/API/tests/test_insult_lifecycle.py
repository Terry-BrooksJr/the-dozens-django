"""
Tests for applications.API.models.Insult lifecycle methods and lookup helpers.

Covers:
- remove_insult / approve_insult / mark_insult_for_review / re_categorize /
  reclassify: each method's happy path (status/field mutation + save), and
  each method's exception branch (a failing save() must be caught and
  logged, never propagated — these are admin-action-safety guarantees).
- Insult.get_by_reference_id:
    * valid reference_id (with and without the "prefix_" underscore
      separator) resolves to the matching instance
    * a reference_id with no recognized prefix returns None
    * a recognized prefix with undecodable base64 returns None
    * a recognized prefix whose decoded payload isn't a valid integer
      returns None
    * a recognized prefix decoding to a PK with no matching row returns None
- Insult.open_report_count only counts PENDING InsultReview rows.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from applications.API.models import (
    Insult,
    InsultCategory,
    InsultReview,
    Theme,
    encode_base64,
)

User = get_user_model()


class _InsultLifecycleBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="lifecycle_user",
            email="lifecycle@example.com",
            password="pw12345",
        )
        cls.theme_a = Theme.objects.create(theme_key="LFA", theme_name="Lifecycle A")
        cls.theme_b = Theme.objects.create(theme_key="LFB", theme_name="Lifecycle B")
        cls.cat_a = InsultCategory.objects.create(
            category_key="LA", name="Lifecycle Cat A", theme=cls.theme_a
        )
        cls.cat_b = InsultCategory.objects.create(
            category_key="LB", name="Lifecycle Cat B", theme=cls.theme_b
        )

    def _create_insult(self, **overrides):
        defaults = dict(
            content="Yo momma is so lifecycle-tested she has 100% coverage.",
            category=self.cat_a,
            nsfw=False,
            added_by=self.user,
            status=Insult.STATUS.ACTIVE,
        )
        defaults.update(overrides)
        return Insult.objects.create(**defaults)


class InsultRemoveApproveReviewTests(_InsultLifecycleBase):
    def test_remove_insult_sets_status_removed(self):
        insult = self._create_insult(status=Insult.STATUS.ACTIVE)

        insult.remove_insult()
        insult.refresh_from_db()

        self.assertEqual(insult.status, Insult.STATUS.REMOVED)

    def test_remove_insult_exception_is_caught_not_raised(self):
        insult = self._create_insult(status=Insult.STATUS.ACTIVE)
        insult.save = MagicMock(side_effect=RuntimeError("db exploded"))

        insult.remove_insult()  # must not raise

        insult.save.assert_called_once_with(update_fields=["status", "last_modified"])

    def test_approve_insult_sets_status_active(self):
        insult = self._create_insult(status=Insult.STATUS.PENDING)

        insult.approve_insult()
        insult.refresh_from_db()

        self.assertEqual(insult.status, Insult.STATUS.ACTIVE)

    def test_approve_insult_exception_is_caught_not_raised(self):
        insult = self._create_insult(status=Insult.STATUS.PENDING)
        insult.save = MagicMock(side_effect=RuntimeError("db exploded"))

        insult.approve_insult()  # must not raise

        insult.save.assert_called_once_with(update_fields=["status", "last_modified"])

    def test_mark_insult_for_review_sets_status_pending(self):
        insult = self._create_insult(status=Insult.STATUS.ACTIVE)

        insult.mark_insult_for_review()
        insult.refresh_from_db()

        self.assertEqual(insult.status, Insult.STATUS.PENDING)

    def test_mark_insult_for_review_exception_is_caught_not_raised(self):
        insult = self._create_insult(status=Insult.STATUS.ACTIVE)
        insult.save = MagicMock(side_effect=RuntimeError("db exploded"))

        insult.mark_insult_for_review()  # must not raise

        insult.save.assert_called_once_with(update_fields=["status", "last_modified"])


class InsultRecategorizeReclassifyTests(_InsultLifecycleBase):
    def test_re_categorize_updates_category_and_theme(self):
        insult = self._create_insult(category=self.cat_a, theme=self.theme_a)

        insult.re_categorize(self.cat_b)
        insult.refresh_from_db()

        self.assertEqual(insult.category, self.cat_b)
        self.assertEqual(insult.theme, self.theme_b)

    def test_re_categorize_exception_is_caught_not_raised(self):
        insult = self._create_insult(category=self.cat_a, theme=self.theme_a)
        insult.save = MagicMock(side_effect=RuntimeError("db exploded"))

        insult.re_categorize(self.cat_b)  # must not raise

        insult.save.assert_called_once_with(
            update_fields=["category", "theme", "last_modified"]
        )

    def test_reclassify_updates_nsfw_flag(self):
        insult = self._create_insult(nsfw=False)

        insult.reclassify(True)
        insult.refresh_from_db()

        self.assertTrue(insult.nsfw)

    def test_reclassify_exception_is_caught_not_raised(self):
        insult = self._create_insult(nsfw=False)
        insult.save = MagicMock(side_effect=RuntimeError("db exploded"))

        insult.reclassify(True)  # must not raise

        insult.save.assert_called_once_with(update_fields=["nsfw", "last_modified"])


class GetByReferenceIdTests(_InsultLifecycleBase):
    def test_valid_reference_id_returns_matching_insult(self):
        insult = self._create_insult()

        found = Insult.get_by_reference_id(insult.reference_id)

        self.assertEqual(found, insult)

    def test_reference_id_without_underscore_separator_still_resolves(self):
        insult = self._create_insult()
        # Build a reference id manually using the same prefix but omitting
        # the "_" separator (exercises the alternate branch in the prefix
        # match — the real generator always includes the underscore).
        no_underscore_ref = f"GIGGLE{encode_base64(insult.insult_id)}"

        found = Insult.get_by_reference_id(no_underscore_ref)

        self.assertEqual(found, insult)

    def test_unrecognized_prefix_returns_none(self):
        self.assertIsNone(Insult.get_by_reference_id("NOTAPREFIX_abc123"))

    def test_undecodable_base64_returns_none(self):
        self.assertIsNone(Insult.get_by_reference_id("GIGGLE_!!!not-valid-base64!!!"))

    def test_decoded_payload_not_an_integer_returns_none(self):
        # base64("hello") decodes cleanly but isn't a valid PK integer.
        self.assertIsNone(Insult.get_by_reference_id("GIGGLE_aGVsbG8="))

    def test_decoded_pk_with_no_matching_row_returns_none(self):
        missing_pk_ref = f"GIGGLE_{encode_base64(999_999_999)}"

        self.assertIsNone(Insult.get_by_reference_id(missing_pk_ref))


class OpenReportCountTests(_InsultLifecycleBase):
    def test_counts_only_pending_reviews(self):
        insult = self._create_insult()

        InsultReview.objects.create(
            insult=insult,
            insult_reference_id=insult.reference_id,
            rationale_for_review="Pending review one",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
            status=InsultReview.STATUS.PENDING,
        )
        InsultReview.objects.create(
            insult=insult,
            insult_reference_id=insult.reference_id,
            rationale_for_review="Pending review two",
            review_type=InsultReview.REVIEW_TYPE.RECLASSIFY,
            status=InsultReview.STATUS.PENDING,
        )
        InsultReview.objects.create(
            insult=insult,
            insult_reference_id=insult.reference_id,
            rationale_for_review="Already resolved review",
            review_type=InsultReview.REVIEW_TYPE.RECATEGORIZE,
            status=InsultReview.STATUS.SAME_CATEGORY,
        )

        self.assertEqual(insult.open_report_count, 2)

    def test_zero_when_no_reviews(self):
        insult = self._create_insult()

        self.assertEqual(insult.open_report_count, 0)
