"""Tests for applications.API.serializers

Covers every serializer class and the shared helper methods on
BaseInsultSerializer / CachedBulkSerializer.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import serializers

from applications.API.models import Insult, InsultCategory, InsultReview, Theme
from applications.API.serializers import (
    BaseInsultSerializer,
    BulkInsultSerializer,
    CachedBulkSerializer,
    CategorySerializer,
    CreateInsultSerializer,
    InsultReviewSerializer,
    MyInsultSerializer,
    OptimizedInsultSerializer,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared base test case
# ---------------------------------------------------------------------------


class SerializerTestCase(TestCase):
    """Base case with shared DB fixtures and cache reset before each test."""

    @classmethod
    def setUpTestData(cls):
        cls.theme = Theme.objects.create(
            theme_key="TST", theme_name="Test Theme", description=""
        )
        cls.category = InsultCategory.objects.create(
            category_key="P", name="Poor", theme=cls.theme, description=""
        )
        cls.category2 = InsultCategory.objects.create(
            category_key="F", name="Fat", theme=cls.theme, description=""
        )
        cls.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            first_name="Terry",
            last_name="Brooks",
            password="pass1234",
        )
        cls.anon_user = User.objects.create_user(
            username="anon",
            email="anon@example.com",
            password="pass1234",
        )
        cls.insult = Insult.objects.create(
            content="Yo momma is so poor she runs after the garbage truck with a shopping list.",
            category=cls.category,
            nsfw=False,
            theme=cls.theme,
            status=Insult.STATUS.ACTIVE,
            added_by=cls.user,
        )

    def setUp(self):
        cache.clear()


# ===========================================================================
# CachedBulkSerializer
# ===========================================================================


class TestCachedBulkSerializer(SerializerTestCase):
    """Unit tests for the caching helpers on CachedBulkSerializer."""

    def _make_serializer(self, extra_cls_attrs=None):
        """Return an instance of a minimal, concrete CachedBulkSerializer subclass."""
        attrs = {
            "Meta": type("Meta", (), {"model": Insult, "fields": ["content"]}),
        }
        if extra_cls_attrs:
            attrs.update(extra_cls_attrs)
        cls = type("_TestCachedSerializer", (CachedBulkSerializer,), attrs)
        return cls()

    # ── get_cache_key ────────────────────────────────────────────────────────

    def test_get_cache_key_default_contains_expected_parts(self):
        s = self._make_serializer()
        key = s.get_cache_key(self.insult, "content")
        self.assertIn("_TestCachedSerializer", key)
        self.assertIn("Insult", key)
        self.assertIn(str(self.insult.pk), key)
        self.assertIn("content", key)
        self.assertIn(":v1", key)

    def test_get_cache_key_delegates_to_cacher(self):
        mock_cacher = MagicMock()
        mock_cacher.get_cache_key.return_value = "cacher_provided_key"
        s = self._make_serializer({"cacher": mock_cacher})
        key = s.get_cache_key(self.insult, "content")
        self.assertEqual(key, "cacher_provided_key")

    def test_get_cache_key_falls_back_when_cacher_raises(self):
        mock_cacher = MagicMock()
        mock_cacher.get_cache_key.side_effect = RuntimeError("redis down")
        s = self._make_serializer({"cacher": mock_cacher})
        # contextlib.suppress in the implementation eats the error and falls back
        key = s.get_cache_key(self.insult, "content")
        self.assertIn("content", key)

    # ── set_cached_field_value ───────────────────────────────────────────────

    def test_set_cached_field_value_no_op_when_field_not_in_cached_fields(self):
        s = self._make_serializer({"cached_fields": []})
        s.set_cached_field_value(self.insult, "content", "some_value")
        cache_key = s.get_cache_key(self.insult, "content")
        self.assertIsNone(cache.get(cache_key))

    def test_set_cached_field_value_stores_when_field_in_cached_fields(self):
        s = self._make_serializer({"cached_fields": ["content"]})
        s.set_cached_field_value(self.insult, "content", "stored_value")
        cache_key = s.get_cache_key(self.insult, "content")
        self.assertEqual(cache.get(cache_key), "stored_value")

    # ── get_cached_field_value ───────────────────────────────────────────────

    def test_get_cached_field_value_returns_pre_cached_value(self):
        s = self._make_serializer()
        cache_key = s.get_cache_key(self.insult, "content")
        cache.set(cache_key, "pre_cached", 300)
        result = s.get_cached_field_value(self.insult, "content", "_compute_content")
        self.assertEqual(result, "pre_cached")

    def test_get_cached_field_value_computes_on_cache_miss(self):
        s = self._make_serializer()
        s._compute_content = lambda obj: "computed_value"
        result = s.get_cached_field_value(self.insult, "content", "_compute_content")
        self.assertEqual(result, "computed_value")

    def test_get_cached_field_value_caches_computed_value(self):
        s = self._make_serializer()
        s._compute_content = lambda obj: "computed_and_cached"
        s.get_cached_field_value(self.insult, "content", "_compute_content")
        cache_key = s.get_cache_key(self.insult, "content")
        self.assertEqual(cache.get(cache_key), "computed_and_cached")

    def test_get_cached_field_value_handles_cache_backend_error_on_get(self):
        """A failing cache.get should fall through to the compute method."""
        s = self._make_serializer()
        s._compute_content = lambda obj: "fallback"
        with patch("applications.API.serializers.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Redis unavailable")
            mock_cache.set.side_effect = Exception("Redis unavailable")
            result = s.get_cached_field_value(
                self.insult, "content", "_compute_content"
            )
        self.assertEqual(result, "fallback")


# ===========================================================================
# BaseInsultSerializer – static / class helpers
# ===========================================================================


class TestBaseInsultSerializerNormalize(SerializerTestCase):
    """Tests for _normalize_category_input."""

    def test_normalizes_insult_category_instance_to_key(self):
        result = BaseInsultSerializer._normalize_category_input(self.category)
        self.assertEqual(result, "P")

    def test_normalizes_string_with_space_dash_separator(self):
        result = BaseInsultSerializer._normalize_category_input("P - Poor")
        self.assertEqual(result, "P")

    def test_normalizes_string_with_em_dash_separator(self):
        result = BaseInsultSerializer._normalize_category_input("P–Poor")
        self.assertEqual(result, "P")

    def test_normalizes_string_with_plain_dash_separator(self):
        result = BaseInsultSerializer._normalize_category_input("P-Poor")
        self.assertEqual(result, "P")

    def test_normalizes_plain_string_strips_whitespace(self):
        result = BaseInsultSerializer._normalize_category_input("  Poor  ")
        self.assertEqual(result, "Poor")

    def test_returns_non_string_non_instance_unchanged(self):
        result = BaseInsultSerializer._normalize_category_input(42)
        self.assertEqual(result, 42)


class TestBaseInsultSerializerFormatHelpers(SerializerTestCase):
    """Tests for format_category and _format_date."""

    def test_format_category_capitalizes_lowercase_input(self):
        result = BaseInsultSerializer.format_category("poor")
        self.assertEqual(result, "Poor")

    def test_format_category_empty_string_returns_uncategorized(self):
        result = BaseInsultSerializer.format_category("")
        self.assertEqual(result, "Uncategorized")

    def test_format_category_none_returns_uncategorized(self):
        result = BaseInsultSerializer.format_category(None)
        self.assertEqual(result, "Uncategorized")

    def test_format_date_returns_non_empty_string(self):
        iso = "2024-01-01T00:00:00+00:00"
        result = BaseInsultSerializer._format_date(iso)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestBaseInsultSerializerResolveCategory(SerializerTestCase):
    """Tests for the resolve_category classmethod."""

    def test_empty_string_returns_uncategorized(self):
        result = BaseInsultSerializer.resolve_category("")
        self.assertEqual(result, {"category_key": "", "category_name": "Uncategorized"})

    def test_none_returns_uncategorized(self):
        result = BaseInsultSerializer.resolve_category(None)
        self.assertEqual(result, {"category_key": "", "category_name": "Uncategorized"})

    def test_insult_category_instance_resolves_directly(self):
        result = BaseInsultSerializer.resolve_category(self.category)
        self.assertEqual(result["category_key"], "P")
        self.assertEqual(result["category_name"], "Poor")

    def test_resolves_by_key_via_db(self):
        result = BaseInsultSerializer.resolve_category("P")
        self.assertEqual(result["category_key"], "P")
        self.assertEqual(result["category_name"], "Poor")

    def test_resolves_by_name_via_db(self):
        result = BaseInsultSerializer.resolve_category("Poor")
        self.assertEqual(result["category_key"], "P")

    def test_resolves_by_key_case_insensitive(self):
        result = BaseInsultSerializer.resolve_category("p")
        self.assertEqual(result["category_key"], "P")

    def test_resolves_by_name_case_insensitive(self):
        result = BaseInsultSerializer.resolve_category("poor")
        self.assertEqual(result["category_key"], "P")

    def test_unknown_category_raises_validation_error(self):
        with self.assertRaises(serializers.ValidationError):
            BaseInsultSerializer.resolve_category("COMPLETELY_NONEXISTENT_XYZ")


class TestBaseInsultSerializerComputeMethods(SerializerTestCase):
    """Tests for _compute_added_by_display and _compute_added_on_display."""

    def _serializer(self):
        return OptimizedInsultSerializer()

    def test_compute_added_by_display_none_user_returns_anon_jokester(self):
        class FakeObj:
            added_by = None

        self.assertEqual(
            self._serializer()._compute_added_by_display(FakeObj()), "Anon Jokester"
        )

    def test_compute_added_by_display_no_first_name_returns_username(self):
        class FakeObj:
            added_by = self.anon_user  # anon_user has no first_name

        result = self._serializer()._compute_added_by_display(FakeObj())
        self.assertEqual(result, "anon")

    def test_compute_added_by_display_first_and_last_name(self):
        class FakeObj:
            added_by = self.user  # first_name="Terry", last_name="Brooks"

        result = self._serializer()._compute_added_by_display(FakeObj())
        self.assertEqual(result, "Terry B.")

    def test_compute_added_by_display_first_name_only(self):
        user = User.objects.create_user(
            username="firstonly",
            email="fo@example.com",
            first_name="Jordan",
            last_name="",
            password="pass",
        )

        class FakeObj:
            added_by = user

        result = self._serializer()._compute_added_by_display(FakeObj())
        self.assertEqual(result, "Jordan")

    def test_compute_added_on_display_no_date_returns_empty_string(self):
        class FakeObj:
            added_on = None

        result = self._serializer()._compute_added_on_display(FakeObj())
        self.assertEqual(result, "")

    def test_compute_added_on_display_with_date_returns_non_empty_string(self):
        result = self._serializer()._compute_added_on_display(self.insult)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


# ===========================================================================
# CategorySerializer
# ===========================================================================


class TestCategorySerializer(SerializerTestCase):

    def test_serializes_all_expected_fields(self):
        data = CategorySerializer(self.category).data
        for field in ("category_key", "name", "count", "description", "theme_id"):
            self.assertIn(field, data)

    def test_category_key_and_name_match_instance(self):
        data = CategorySerializer(self.category).data
        self.assertEqual(data["category_key"], "P")
        self.assertEqual(data["name"], "Poor")

    def test_count_reflects_active_insults_in_category(self):
        data = CategorySerializer(self.category).data
        # At least the one insult from setUpTestData
        self.assertGreaterEqual(data["count"], 1)

    def test_all_fields_are_read_only(self):
        """No data should leak into validated_data from the read-only fields."""
        s = CategorySerializer(data={"category_key": "X", "name": "New"})
        s.is_valid()
        self.assertNotIn("category_key", s.validated_data)
        self.assertNotIn("name", s.validated_data)


# ===========================================================================
# MyInsultSerializer
# ===========================================================================


class TestMyInsultSerializer(SerializerTestCase):

    def test_serializes_expected_fields(self):
        data = MyInsultSerializer(self.insult).data
        for field in ("reference_id", "category", "content", "status", "reports_count"):
            self.assertIn(field, data)

    def test_status_is_display_label_not_code(self):
        data = MyInsultSerializer(self.insult).data
        self.assertEqual(data["status"], "Active")

    def test_category_shows_display_name(self):
        data = MyInsultSerializer(self.insult).data
        self.assertEqual(data["category"], "Poor")

    def test_reference_id_is_read_only(self):
        payload = {
            "reference_id": "FAKE_REF",
            "content": "Yo momma is so poor she uses newspaper coupons for luxuries like salt.",
            "category": "P",
            "status": "Active",
            "reports_count": 0,
        }
        s = MyInsultSerializer(data=payload)
        s.is_valid()
        self.assertNotIn("reference_id", s.validated_data)

    def test_status_is_read_only(self):
        payload = {
            "content": "Yo momma is so poor she uses newspaper coupons for luxuries like salt.",
            "category": "P",
            "status": "Pending - New",
        }
        s = MyInsultSerializer(data=payload)
        s.is_valid()
        self.assertNotIn("status", s.validated_data)


# ===========================================================================
# OptimizedInsultSerializer
# ===========================================================================


class TestOptimizedInsultSerializer(SerializerTestCase):

    def test_serializes_all_expected_fields(self):
        data = OptimizedInsultSerializer(self.insult).data
        for field in (
            "content",
            "reference_id",
            "category",
            "nsfw",
            "status",
            "added",
            "by",
        ):
            self.assertIn(field, data)

    def test_by_field_is_string(self):
        data = OptimizedInsultSerializer(self.insult).data
        self.assertIsInstance(data["by"], str)

    def test_added_field_is_string(self):
        data = OptimizedInsultSerializer(self.insult).data
        self.assertIsInstance(data["added"], str)

    def test_category_field_shows_name_not_key(self):
        """to_representation must replace the key with the category display name."""
        data = OptimizedInsultSerializer(self.insult).data
        self.assertEqual(data["category"], "Poor")

    def test_reference_id_is_read_only(self):
        payload = {
            "content": "Yo momma is so poor the ducks throw bread at her.",
            "category": "P",
            "nsfw": False,
        }
        s = OptimizedInsultSerializer(data=payload)
        s.is_valid()
        self.assertNotIn("reference_id", s.validated_data)


# ===========================================================================
# BulkInsultSerializer
# ===========================================================================


class TestBulkInsultSerializer(SerializerTestCase):

    def test_many_true_uses_bulk_list_serializer(self):
        """many=True on OptimizedInsultSerializer should produce a BulkInsultSerializer."""
        s = OptimizedInsultSerializer(
            Insult.objects.filter(pk=self.insult.pk), many=True
        )
        self.assertIsInstance(s, BulkInsultSerializer)

    def test_bulk_serializes_queryset(self):
        data = OptimizedInsultSerializer(
            Insult.objects.filter(pk=self.insult.pk), many=True
        ).data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["reference_id"], self.insult.reference_id)

    def test_to_representation_calls_select_related_on_queryset(self):
        """BulkInsultSerializer.to_representation exercises the select_related branch."""
        qs = Insult.objects.filter(pk=self.insult.pk)
        list_s = BulkInsultSerializer(child=OptimizedInsultSerializer())
        result = list_s.to_representation(qs)
        self.assertIsInstance(result, list)

    def test_to_representation_handles_plain_list(self):
        """Passing a plain list (no select_related) should not raise."""
        list_s = BulkInsultSerializer(child=OptimizedInsultSerializer())
        result = list_s.to_representation([self.insult])
        self.assertIsInstance(result, list)


# ===========================================================================
# CreateInsultSerializer
# ===========================================================================


class TestCreateInsultSerializer(SerializerTestCase):

    # 70-char minimum for a valid content string
    _VALID_CONTENT = (
        "Yo momma is so poor she can't afford a free sample at the grocery store today."
    )

    def _payload(self, **overrides):
        base = {"category": "P", "content": self._VALID_CONTENT, "nsfw": False}
        base.update(overrides)
        return base

    # ── validate_category ────────────────────────────────────────────────────

    def test_validate_category_resolves_key_to_instance(self):
        s = CreateInsultSerializer(data=self._payload(category="P"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsInstance(s.validated_data["category"], InsultCategory)
        self.assertEqual(s.validated_data["category"].category_key, "P")

    def test_validate_category_resolves_name_to_instance(self):
        s = CreateInsultSerializer(data=self._payload(category="Poor"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["category"].category_key, "P")

    def test_validate_category_nonexistent_raises_validation_error(self):
        s = CreateInsultSerializer(data=self._payload(category="NONEXISTENT_99"))
        self.assertFalse(s.is_valid())
        self.assertIn("category", s.errors)

    # ── content validation ───────────────────────────────────────────────────

    def test_content_shorter_than_60_chars_fails(self):
        s = CreateInsultSerializer(data=self._payload(content="Too short."))
        self.assertFalse(s.is_valid())
        self.assertIn("content", s.errors)

    def test_content_exactly_60_chars_passes(self):
        content = "x" * 60
        s = CreateInsultSerializer(data=self._payload(content=content))
        self.assertTrue(s.is_valid(), s.errors)

    def test_content_blank_fails(self):
        s = CreateInsultSerializer(data=self._payload(content=""))
        self.assertFalse(s.is_valid())
        self.assertIn("content", s.errors)

    # ── nsfw default ─────────────────────────────────────────────────────────

    def test_nsfw_defaults_to_false_when_omitted(self):
        payload = {"category": "P", "content": self._VALID_CONTENT}
        s = CreateInsultSerializer(data=payload)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertFalse(s.validated_data.get("nsfw", True))

    # ── create ───────────────────────────────────────────────────────────────

    def test_create_sets_theme_from_category(self):
        s = CreateInsultSerializer(data=self._payload())
        self.assertTrue(s.is_valid(), s.errors)
        insult = s.save(added_by=self.user)
        try:
            self.assertEqual(insult.theme, self.category.theme)
        finally:
            insult.delete()

    def test_create_returns_insult_instance(self):
        s = CreateInsultSerializer(data=self._payload())
        self.assertTrue(s.is_valid(), s.errors)
        insult = s.save(added_by=self.user)
        try:
            self.assertIsInstance(insult, Insult)
            self.assertIsNotNone(insult.pk)
        finally:
            insult.delete()


# ===========================================================================
# InsultReviewSerializer
# ===========================================================================


class TestInsultReviewSerializer(SerializerTestCase):

    # Meets the 70-character minimum
    _RATIONALE = (
        "This insult is deeply offensive, targeting a protected characteristic "
        "in a way that violates community guidelines and must be removed promptly."
    )

    def _anon_payload(self, **overrides):
        base = {
            "insult_reference_id": self.insult.reference_id,
            "anonymous": True,
            "review_type": InsultReview.REVIEW_TYPE.REMOVAL,
            "rationale_for_review": self._RATIONALE,
            "post_review_contact_desired": False,
        }
        base.update(overrides)
        return base

    def _non_anon_payload(self, **overrides):
        base = self._anon_payload(
            anonymous=False,
            reporter_first_name="Jordan",
            reporter_last_name="Brooks",
        )
        base.update(overrides)
        return base

    # ── happy paths ──────────────────────────────────────────────────────────

    def test_valid_anonymous_review_passes(self):
        s = InsultReviewSerializer(data=self._anon_payload())
        self.assertTrue(s.is_valid(), s.errors)

    def test_valid_non_anonymous_review_with_names_passes(self):
        s = InsultReviewSerializer(data=self._non_anon_payload())
        self.assertTrue(s.is_valid(), s.errors)

    def test_valid_non_anonymous_with_contact_info_passes(self):
        payload = self._non_anon_payload(
            post_review_contact_desired=True,
            reporter_email="jordan@example.com",
        )
        s = InsultReviewSerializer(data=payload)
        self.assertTrue(s.is_valid(), s.errors)

    def test_all_review_type_choices_are_accepted(self):
        for review_type in InsultReview.REVIEW_TYPE.values:
            s = InsultReviewSerializer(data=self._anon_payload(review_type=review_type))
            self.assertTrue(
                s.is_valid(),
                f"review_type={review_type!r} unexpectedly invalid: {s.errors}",
            )

    # ── reference ID validation ──────────────────────────────────────────────

    def test_invalid_insult_reference_id_raises(self):
        s = InsultReviewSerializer(
            data=self._anon_payload(insult_reference_id="INVALID_REF_99999")
        )
        self.assertFalse(s.is_valid())
        non_field = " ".join(str(e) for e in s.errors.get("non_field_errors", []))
        self.assertIn("Invalid Insult ID", non_field)

    def test_empty_insult_reference_id_is_rejected(self):
        s = InsultReviewSerializer(data=self._anon_payload(insult_reference_id=""))
        self.assertFalse(s.is_valid())

    # ── non-anonymous name requirements ─────────────────────────────────────

    def test_non_anonymous_missing_first_name_raises(self):
        s = InsultReviewSerializer(data=self._non_anon_payload(reporter_first_name=""))
        self.assertFalse(s.is_valid())
        self.assertIn("First name is required", str(s.errors))

    def test_non_anonymous_missing_last_name_raises(self):
        s = InsultReviewSerializer(data=self._non_anon_payload(reporter_last_name=""))
        self.assertFalse(s.is_valid())
        self.assertIn("Last name is required", str(s.errors))

    # ── contact-preference email requirement ─────────────────────────────────

    def test_contact_desired_without_email_raises(self):
        payload = self._non_anon_payload(
            post_review_contact_desired=True,
            reporter_email="",
        )
        s = InsultReviewSerializer(data=payload)
        self.assertFalse(s.is_valid())
        self.assertIn("Email address is required", str(s.errors))

    # ── rationale length ─────────────────────────────────────────────────────

    def test_rationale_shorter_than_70_chars_fails(self):
        s = InsultReviewSerializer(
            data=self._anon_payload(rationale_for_review="Way too short.")
        )
        self.assertFalse(s.is_valid())
        self.assertIn("rationale_for_review", s.errors)

    # ── review_type validation ───────────────────────────────────────────────

    def test_missing_review_type_fails(self):
        payload = self._anon_payload()
        del payload["review_type"]
        s = InsultReviewSerializer(data=payload)
        self.assertFalse(s.is_valid())
        self.assertIn("review_type", s.errors)

    def test_invalid_review_type_value_fails(self):
        s = InsultReviewSerializer(data=self._anon_payload(review_type="BOGUS"))
        self.assertFalse(s.is_valid())
        self.assertIn("review_type", s.errors)

    # ── validated_data normalisation ─────────────────────────────────────────

    def test_validate_normalises_reference_id_to_string(self):
        s = InsultReviewSerializer(data=self._anon_payload())
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(
            s.validated_data["insult_reference_id"], self.insult.reference_id
        )

    def test_validate_coerces_anonymous_to_bool(self):
        s = InsultReviewSerializer(data=self._anon_payload(anonymous=True))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIs(s.validated_data["anonymous"], True)

    def test_validate_strips_reporter_name_whitespace(self):
        payload = self._non_anon_payload(
            reporter_first_name="  Jordan  ", reporter_last_name="  Brooks  "
        )
        s = InsultReviewSerializer(data=payload)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["reporter_first_name"], "Jordan")
        self.assertEqual(s.validated_data["reporter_last_name"], "Brooks")
