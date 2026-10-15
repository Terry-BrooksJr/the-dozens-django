"""
Tests for the joke-workflow metrics recorded by model signals.

Covers:
- creating an insult counts new -> <status>
- a status change through save() counts old -> new; a save without a change
  counts nothing
- reporting an insult counts the report by review type, and the review's own
  new -> pending transition
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from applications.API.models import Insult, InsultCategory, InsultReview, Theme
from common.metrics import INSULT_REPORTS, STATUS_TRANSITIONS

User = get_user_model()


def _transitions(model, from_status, to_status):
    return STATUS_TRANSITIONS.labels(model, from_status, to_status)._value.get()


class StatusTransitionMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="metrics_user",
            email="metrics@example.com",
            password="pw12345",  # nosec B106
        )
        theme = Theme.objects.create(theme_key="MET", theme_name="Metrics")
        cls.category = InsultCategory.objects.create(
            category_key="MT", name="Metrics Cat", theme=theme
        )

    def _create_insult(self, status):
        return Insult.objects.create(
            content="Yo momma is so measured she has her own histogram.",
            category=self.category,
            nsfw=False,
            added_by=self.user,
            status=status,
        )

    def test_creation_counts_new_to_status(self):
        before = _transitions("insult", "new", "active")
        self._create_insult(Insult.STATUS.ACTIVE)
        self.assertEqual(_transitions("insult", "new", "active"), before + 1)

    def test_status_change_counts_old_to_new(self):
        insult = Insult.objects.get(pk=self._create_insult(Insult.STATUS.PENDING).pk)
        before = _transitions("insult", "pending", "active")

        insult.approve_insult()

        self.assertEqual(_transitions("insult", "pending", "active"), before + 1)

    def test_save_without_status_change_counts_nothing(self):
        insult = Insult.objects.get(pk=self._create_insult(Insult.STATUS.ACTIVE).pk)
        before = _transitions("insult", "active", "active")

        insult.content = "Yo momma is so unchanged her status stayed put."
        insult.save()

        self.assertEqual(_transitions("insult", "active", "active"), before)

    def test_report_counts_review_type_and_review_creation(self):
        insult = self._create_insult(Insult.STATUS.ACTIVE)
        reports = INSULT_REPORTS.labels("removal")._value.get()
        reviews = _transitions("insult_review", "new", "pending")

        InsultReview.objects.create(
            insult_reference_id=insult.reference_id,
            rationale_for_review="Not funny.",
            review_type=InsultReview.REVIEW_TYPE.REMOVAL,
        )

        self.assertEqual(INSULT_REPORTS.labels("removal")._value.get(), reports + 1)
        self.assertEqual(_transitions("insult_review", "new", "pending"), reviews + 1)
