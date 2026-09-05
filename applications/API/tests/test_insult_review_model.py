"""
Tests for applications.API.models.InsultReview: set_insult(), the
mark_review_* state-transition methods, and the flag_insult /
decrement_report_count model signals.

None of these were previously exercised directly — only indirectly, and only
along the single "everything succeeds" path, via admin-action tests. This
file targets the methods and signals themselves, including their error
branches.

Covers:
- set_insult():
    * missing insult_reference_id raises IntegrityError
    * a reference_id matching no real Insult is a silent no-op
    * a reference_id matching a real Insult sets self.insult and persists it
    * Insult.DoesNotExist bubbling out of get_by_reference_id is wrapped in
      IntegrityError (defensive branch — get_by_reference_id currently never
      raises this itself, but the except clause exists and must behave)
    * Base64DecoderException is wrapped in IntegrityError (same defensive
      situation)
    * any other exception is wrapped in a generic IntegrityError
- mark_review_not_reclassified / mark_review_recategorized /
  mark_review_not_recatagoized / mark_review_removed / mark_review_reclassified:
    * happy path sets status/reviewer/date_reviewed and saves
    * a failing save() is caught and logged, never propagated
- flag_insult signal: creating an InsultReview against a real Insult's
  reference_id flags that Insult and increments its reports_count.
- decrement_report_count signal: deleting an InsultReview decrements the
  related Insult's reports_count.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from applications.API.models import (
    Base64DecoderException,
    Insult,
    InsultCategory,
    InsultReview,
    Theme,
)

User = get_user_model()


class _InsultReviewBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="review_user", email="review@example.com", password="pw12345"
        )
        cls.reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@example.com", password="pw12345"
        )
        cls.theme = Theme.objects.create(theme_key="RVT", theme_name="Review Theme")
        cls.cat = InsultCategory.objects.create(
            category_key="RV", name="Review Cat", theme=cls.theme
        )
        cls.insult = Insult.objects.create(
            content="Yo momma is so reviewable she has her own InsultReview.",
            category=cls.cat,
            nsfw=False,
            added_by=cls.user,
            status=Insult.STATUS.ACTIVE,
        )

    def _unsaved_review(self, **overrides):
        defaults = dict(
            insult_reference_id="",
            rationale_for_review="Some rationale for review.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )
        defaults.update(overrides)
        return InsultReview(**defaults)


class SetInsultTests(_InsultReviewBase):
    def test_missing_reference_id_raises_integrity_error(self):
        review = self._unsaved_review(insult_reference_id="")

        with self.assertRaises(IntegrityError) as ctx:
            review.set_insult()

        self.assertIn("Insult Reference ID must be provided", str(ctx.exception))

    def test_unmatched_reference_id_is_a_noop(self):
        review = self._unsaved_review(insult_reference_id="GIGGLE_doesnotexist")

        review.set_insult()  # must not raise

        self.assertIsNone(review.insult)

    def test_matching_reference_id_sets_insult(self):
        # Persist first so self.save(update_fields=["insult"]) can UPDATE it.
        review = InsultReview.objects.create(
            insult_reference_id=self.insult.reference_id,
            rationale_for_review="Matches a real insult.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )

        review.refresh_from_db()

        self.assertEqual(review.insult_id, self.insult.insult_id)

    @patch("applications.API.models.Insult.get_by_reference_id")
    def test_insult_does_not_exist_is_wrapped_in_integrity_error(self, mock_lookup):
        mock_lookup.side_effect = Insult.DoesNotExist
        review = self._unsaved_review(insult_reference_id="GIGGLE_whatever")

        with self.assertRaises(IntegrityError) as ctx:
            review.set_insult()

        self.assertIn("does not exist", str(ctx.exception))

    @patch("applications.API.models.Insult.get_by_reference_id")
    def test_base64_decoder_exception_is_wrapped_in_integrity_error(self, mock_lookup):
        mock_lookup.side_effect = Base64DecoderException("bad payload")
        review = self._unsaved_review(insult_reference_id="GIGGLE_whatever")

        with self.assertRaises(IntegrityError) as ctx:
            review.set_insult()

        self.assertIn("Base64 format", str(ctx.exception))

    @patch("applications.API.models.Insult.get_by_reference_id")
    def test_generic_exception_is_wrapped_in_integrity_error(self, mock_lookup):
        mock_lookup.side_effect = RuntimeError("boom")
        review = self._unsaved_review(insult_reference_id="GIGGLE_whatever")

        with self.assertRaises(IntegrityError) as ctx:
            review.set_insult()

        self.assertIn("Generalized Insult Setting Error", str(ctx.exception))
        self.assertIn("boom", str(ctx.exception))


class MarkReviewMethodsHappyPathTests(_InsultReviewBase):
    def _saved_review(self):
        return InsultReview.objects.create(
            insult=self.insult,
            insult_reference_id=self.insult.reference_id,
            rationale_for_review="Needs a decision.",
            review_type=InsultReview.REVIEW_TYPE.RECLASSIFY,
        )

    def test_mark_review_not_reclassified(self):
        review = self._saved_review()

        review.mark_review_not_reclassified(self.reviewer)
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.SAME_CLASSIFICATION)
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertIsNotNone(review.date_reviewed)

    def test_mark_review_recategorized(self):
        review = self._saved_review()

        review.mark_review_recategorized(self.reviewer)
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.NEW_CATEGORY)
        self.assertEqual(review.reviewer, self.reviewer)

    def test_mark_review_not_recatagoized_with_reviewer(self):
        review = self._saved_review()

        review.mark_review_not_recatagoized(self.reviewer)
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.SAME_CATEGORY)
        self.assertEqual(review.reviewer, self.reviewer)

    def test_mark_review_not_recatagoized_without_reviewer(self):
        review = self._saved_review()

        review.mark_review_not_recatagoized()
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.SAME_CATEGORY)
        self.assertIsNone(review.reviewer)

    def test_mark_review_removed_with_reviewer(self):
        review = self._saved_review()

        review.mark_review_removed(self.reviewer)
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.REMOVED)
        self.assertEqual(review.reviewer, self.reviewer)

    def test_mark_review_removed_without_reviewer(self):
        review = self._saved_review()

        review.mark_review_removed()
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.REMOVED)
        self.assertIsNone(review.reviewer)

    def test_mark_review_reclassified(self):
        review = self._saved_review()

        review.mark_review_reclassified(self.reviewer)
        review.refresh_from_db()

        self.assertEqual(review.status, InsultReview.STATUS.NEW_CLASSIFICATION)
        self.assertEqual(review.reviewer, self.reviewer)


class MarkReviewMethodsExceptionTests(_InsultReviewBase):
    def _saved_review(self):
        return InsultReview.objects.create(
            insult=self.insult,
            insult_reference_id=self.insult.reference_id,
            rationale_for_review="Needs a decision.",
            review_type=InsultReview.REVIEW_TYPE.RECLASSIFY,
        )

    def test_mark_review_not_reclassified_exception_is_caught(self):
        review = self._saved_review()
        review.save = MagicMock(side_effect=RuntimeError("boom"))

        review.mark_review_not_reclassified(self.reviewer)  # must not raise

        review.save.assert_called_once()

    def test_mark_review_recategorized_exception_is_caught(self):
        review = self._saved_review()
        review.save = MagicMock(side_effect=RuntimeError("boom"))

        review.mark_review_recategorized(self.reviewer)  # must not raise

        review.save.assert_called_once()

    def test_mark_review_not_recatagoized_exception_is_caught(self):
        review = self._saved_review()
        review.save = MagicMock(side_effect=RuntimeError("boom"))

        review.mark_review_not_recatagoized(self.reviewer)  # must not raise

        review.save.assert_called_once()

    def test_mark_review_removed_exception_is_caught(self):
        review = self._saved_review()
        review.save = MagicMock(side_effect=RuntimeError("boom"))

        review.mark_review_removed(self.reviewer)  # must not raise

        review.save.assert_called_once()

    def test_mark_review_reclassified_exception_is_caught(self):
        review = self._saved_review()
        review.save = MagicMock(side_effect=RuntimeError("boom"))

        review.mark_review_reclassified(self.reviewer)  # must not raise

        review.save.assert_called_once()


class FlagInsultSignalTests(_InsultReviewBase):
    def test_creating_review_flags_insult_and_increments_reports_count(self):
        self.assertEqual(self.insult.reports_count, 0)

        InsultReview.objects.create(
            insult_reference_id=self.insult.reference_id,
            rationale_for_review="This joke needs review.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )

        self.insult.refresh_from_db()
        self.assertEqual(self.insult.status, Insult.STATUS.FLAGGED)
        self.assertEqual(self.insult.reports_count, 1)

    def test_second_review_increments_reports_count_again(self):
        for i in range(2):
            InsultReview.objects.create(
                insult_reference_id=self.insult.reference_id,
                rationale_for_review=f"Review number {i}.",
                review_type=InsultReview.REVIEW_TYPE.REMOVAL,
            )

        self.insult.refresh_from_db()
        self.assertEqual(self.insult.reports_count, 2)

    def test_review_with_unresolvable_reference_id_does_not_error(self):
        """Creating a review that can't be matched to an Insult must not raise."""
        InsultReview.objects.create(
            insult_reference_id="GIGGLE_doesnotexist",
            rationale_for_review="Orphaned review.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )  # must not raise


class DecrementReportCountSignalTests(_InsultReviewBase):
    def test_deleting_review_decrements_reports_count(self):
        review = InsultReview.objects.create(
            insult_reference_id=self.insult.reference_id,
            rationale_for_review="Will be deleted.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )
        self.insult.refresh_from_db()
        self.assertEqual(self.insult.reports_count, 1)

        review.delete()

        self.insult.refresh_from_db()
        self.assertEqual(self.insult.reports_count, 0)

    def test_deleting_review_without_insult_does_not_error(self):
        review = InsultReview.objects.create(
            insult_reference_id="GIGGLE_doesnotexist",
            rationale_for_review="No related insult.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )

        review.delete()  # must not raise
