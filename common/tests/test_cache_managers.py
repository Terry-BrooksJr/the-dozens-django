"""
Tests for common.cache_managers.

Covers:
CacheManagerRegistry
  - register / get / names / count / all / items / values
  - invalidate_all: calls each manager's invalidate_cache
  - invalidate_all: continues past a manager that raises
  - get_all_stats: returns stats dict; skips managers without get_cache_stats
  - get returns None for unknown name

CategoryCacheManager
  - get_cache_keys: returns expected key structure
  - build_data_from_db: maps key_field → name_field correctly
  - build_data_from_db: returns empty dict on exception
  - get_all_categories: populates from DB on cache miss; returns cached value on hit
  - get_category_name_by_key: Redis hit path / fallback to all_categories
  - get_category_key_by_name: Redis hit path / fallback (case-insensitive)
  - set_category_name_mapping: writes both directions into cache
  - invalidate_category: deletes correct cache keys

GenericDataCacheManager
  - get_cache_keys returns expected key
  - get_cached_data: module-level cache hit (no Django cache call)
  - get_cached_data: Redis hit populates module cache
  - get_cached_data: cache miss calls data builder and stores result
  - get_cached_data: invalid cache_key name returns None
  - get_cached_data: DB ProgrammingError returns None gracefully
  - invalidate_cache: clears both caches
  - get_cache_stats: returns a dict with expected keys

FormChoicesCacheManager
  - get_form_choices: returns cached choices list
  - get_queryset_json: returns cached JSON string
  - get_choices_and_queryset: returns both together
  - _build_form_choices_data: builds (value, display) tuples from queryset

Factory functions
  - create_form_choices_manager: creates and auto-registers manager
  - create_category_manager: creates and auto-registers manager
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from common.cache_managers import (
    BaseCacheManager,
    CacheManagerRegistry,
    CategoryCacheManager,
    FormChoicesCacheManager,
    GenericDataCacheManager,
    create_category_manager,
    create_form_choices_manager,
)

# ---------------------------------------------------------------------------
# Shared helpers / fake model
# ---------------------------------------------------------------------------


def _make_model_class(name="FakeModel", objects=None):
    """Return a minimal model-class-like object."""
    m = MagicMock()
    m.__name__ = name
    m.objects = objects or MagicMock()
    return m


def _make_generic_manager(model_class=None, prefix="test", builder=None, timeout=60):
    mc = model_class or _make_model_class()
    return GenericDataCacheManager(
        model_class=mc,
        cache_prefix=prefix,
        data_builder=builder,
        cache_timeout=timeout,
    )


# ---------------------------------------------------------------------------
# CacheManagerRegistry
# ---------------------------------------------------------------------------


class CacheManagerRegistryTests(TestCase):
    """Tests the behavior of the CacheManagerRegistry utility class. These tests verify that cache managers can be registered, queried, invalidated, and inspected for statistics."""
    def test_names_returns_registered_names(self):
        """Registered cache manager names are exposed via names() The method should return all manager identifiers that have been added to the registry."""
        reg = self._fresh_registry()
        reg.register("alpha", MagicMock())
        reg.register("beta", MagicMock())
        self.assertIn("alpha", reg.names())
        self.assertIn("beta", reg.names())

    def _fresh_registry(self):
        return CacheManagerRegistry()

    def test_register_and_get(self):
        """Registering a manager makes it retrievable by its name. The registry should return the same manager instance that was originally registered."""
        reg = self._fresh_registry()
        mgr = MagicMock(spec=BaseCacheManager)
        reg.register("my_manager", mgr)
        self.assertIs(reg.get("my_manager"), mgr)

    def test_get_unknown_returns_none(self):
        reg = self._fresh_registry()
        self.assertIsNone(reg.get("does_not_exist"))

    def test_count(self):
        reg = self._fresh_registry()
        self.assertEqual(reg.count(), 0)
        reg.register("one", MagicMock())
        self.assertEqual(reg.count(), 1)

    def test_all_returns_shallow_copy(self):
        reg = self._fresh_registry()
        mgr = MagicMock()
        reg.register("x", mgr)
        snapshot = reg.all()
        self.assertIsInstance(snapshot, dict)
        self.assertIs(snapshot["x"], mgr)
        # Mutating the snapshot doesn't affect the registry
        del snapshot["x"]
        self.assertIsNotNone(reg.get("x"))

    def test_items_and_values_iteration(self):
        reg = self._fresh_registry()
        mgr = MagicMock()
        reg.register("z", mgr)
        pairs = list(reg.items())
        self.assertEqual(pairs, [("z", mgr)])
        vals = list(reg.values())
        self.assertEqual(vals, [mgr])

    def test_invalidate_all_calls_each_manager(self):
        """Invalidate all propagates the request to every registered manager. Each manager should receive a single invalidate_cache call with the given reason."""
        """Invalidate all propagates the request to every registered manager. Each manager should receive a single invalidate_cache call with the given reason."""
        reg = self._fresh_registry()
        m1, m2 = MagicMock(), MagicMock()
        reg.register("m1", m1)
        reg.register("m2", m2)
        reg.invalidate_all("test_reason")
        m1.invalidate_cache.assert_called_once_with("test_reason")
        m2.invalidate_cache.assert_called_once_with("test_reason")

    def test_invalidate_all_continues_past_exception(self):
        """A manager that raises must not prevent others from being invalidated."""
        reg = self._fresh_registry()
        bad = MagicMock()
        bad.invalidate_cache.side_effect = RuntimeError("oops")
        good = MagicMock()
        reg.register("bad", bad)
        reg.register("good", good)
        reg.invalidate_all("reason")  # must not raise
        good.invalidate_cache.assert_called_once()

    def test_get_all_stats_includes_managers_with_stats(self):
        reg = self._fresh_registry()
        mgr = MagicMock()
        mgr.get_cache_stats.return_value = {"hits": 5}
        reg.register("stats_mgr", mgr)
        stats = reg.get_all_stats()
        self.assertIn("stats_mgr", stats)
        self.assertEqual(stats["stats_mgr"]["hits"], 5)

    def test_get_all_stats_skips_managers_without_method(self):
        reg = self._fresh_registry()
        mgr = MagicMock(spec=[])  # no get_cache_stats
        reg.register("no_stats", mgr)
        stats = reg.get_all_stats()
        self.assertNotIn("no_stats", stats)


# ---------------------------------------------------------------------------
# CategoryCacheManager
# ---------------------------------------------------------------------------


class CategoryCacheManagerTests(TestCase):
    """Tests the behavior of the CategoryCacheManager class. These tests verify that category data is cached, retrieved, invalidated, and mapped between keys and names correctly."""
    def _make_obj(self, key, name):
        obj = MagicMock()
        obj.key = key
        obj.name = name
        return obj

    def test_get_cache_keys_structure(self):
        model = _make_model_class()
        mgr = CategoryCacheManager(model)
        keys = mgr.get_cache_keys()
        self.assertIn("all", keys)
        self.assertIn("name_prefix", keys)
        self.assertIn("key_prefix", keys)

    def test_build_data_from_db_maps_correctly(self):
        obj1 = self._make_obj("P", "Poor")
        obj2 = self._make_obj("D", "Dark")
        model = _make_model_class()
        model.objects.all.return_value = [obj1, obj2]
        mgr = CategoryCacheManager(model)
        result = mgr.build_data_from_db()
        self.assertEqual(result["all"], {"P": "Poor", "D": "Dark"})

    def test_build_data_from_db_returns_empty_on_exception(self):
        model = _make_model_class()
        model.objects.all.side_effect = Exception("db down")
        mgr = CategoryCacheManager(model)
        result = mgr.build_data_from_db()
        self.assertEqual(result["all"], {})

    def test_get_all_categories_populates_from_db_on_cache_miss(self):
        obj = self._make_obj("P", "Poor")
        model = _make_model_class()
        model.objects.all.return_value = [obj]
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None  # cache miss
            mock_cache.set = MagicMock()
            result = mgr.get_all_categories()

        self.assertEqual(result, {"P": "Poor"})
        mock_cache.set.assert_called()

    def test_get_all_categories_returns_cached_value(self):
        model = _make_model_class()
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = {"X": "Extreme"}
            result = mgr.get_all_categories()

        model.objects.all.assert_not_called()
        self.assertEqual(result, {"X": "Extreme"})

    def test_get_category_name_by_key_redis_hit(self):
        model = _make_model_class()
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = "Poor"
            name = mgr.get_category_name_by_key("P")

        self.assertEqual(name, "Poor")

    def test_get_category_name_by_key_falls_back_to_all(self):
        obj = self._make_obj("P", "Poor")
        model = _make_model_class()
        model.objects.all.return_value = [obj]
        mgr = CategoryCacheManager(model)

        # First get() call (individual key) misses; second (all:) also misses → build from DB
        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            name = mgr.get_category_name_by_key("P")

        self.assertEqual(name, "Poor")

    def test_get_category_key_by_name_case_insensitive(self):
        obj = self._make_obj("P", "Poor")
        model = _make_model_class()
        model.objects.all.return_value = [obj]
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            key = mgr.get_category_key_by_name("POOR")

        self.assertEqual(key, "P")

    def test_get_category_key_by_name_returns_none_when_missing(self):
        model = _make_model_class()
        model.objects.all.return_value = []
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            key = mgr.get_category_key_by_name("nonexistent")

        self.assertIsNone(key)

    def test_set_category_name_mapping_writes_both_directions(self):
        model = _make_model_class()
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.set = MagicMock()
            mgr.set_category_name_mapping("P", "Poor")

        calls = mock_cache.set.call_args_list
        set_keys = [c.args[0] for c in calls]
        # Should have written name→key and key→name entries
        self.assertEqual(len(calls), 2)
        self.assertTrue(any("P" in k for k in set_keys))
        self.assertTrue(any("poor" in k for k in set_keys))

    def test_invalidate_category_deletes_correct_keys(self):
        model = _make_model_class()
        mgr = CategoryCacheManager(model)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = "Poor"  # name lookup
            mock_cache.delete_many = MagicMock()
            mgr.invalidate_category("P")

        deleted = mock_cache.delete_many.call_args.args[0]
        self.assertTrue(any("P" in k for k in deleted))


# ---------------------------------------------------------------------------
# GenericDataCacheManager
# ---------------------------------------------------------------------------


class GenericDataCacheManagerTests(TestCase):
    """Tests the behavior of the GenericDataCacheManager class. These tests verify that generic data is cached, retrieved, invalidated, and reported on consistently across different backends."""
    def test_get_cache_keys_returns_data_key(self):
        mgr = _make_generic_manager(prefix="myprefix")
        keys = mgr.get_cache_keys()
        self.assertIn("data", keys)
        self.assertIn("myprefix", keys["data"])

    def test_get_cached_data_module_cache_hit(self):
        """If data is in module-level cache, Django cache is never consulted."""
        mgr = _make_generic_manager(prefix="modcache")
        mgr._module_cache["data"] = ["item1", "item2"]

        with patch("common.cache_managers.cache") as mock_cache:
            result = mgr.get_cached_data("data")

        mock_cache.get.assert_not_called()
        self.assertEqual(result, ["item1", "item2"])

    def test_get_cached_data_redis_hit_populates_module_cache(self):
        mgr = _make_generic_manager(prefix="rediscache")

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = ["redis_item"]
            mock_cache.set = MagicMock()
            result = mgr.get_cached_data("data")

        self.assertEqual(result, ["redis_item"])
        self.assertEqual(mgr._module_cache.get("data"), ["redis_item"])

    def test_get_cached_data_miss_calls_builder_and_caches(self):
        builder = MagicMock(return_value={"data": ["fresh"]})
        mgr = _make_generic_manager(prefix="dbmiss", builder=builder)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            result = mgr.get_cached_data("data")

        builder.assert_called_once()
        mock_cache.set.assert_called_once()
        self.assertEqual(result, ["fresh"])

    def test_get_cached_data_invalid_key_returns_none(self):
        mgr = _make_generic_manager()
        result = mgr.get_cached_data("this_key_does_not_exist")
        self.assertIsNone(result)

    def test_get_cached_data_programming_error_returns_none(self):
        from django.db.utils import ProgrammingError

        builder = MagicMock(side_effect=ProgrammingError("table missing"))
        mgr = _make_generic_manager(prefix="dberr", builder=builder)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = mgr.get_cached_data("data")

        self.assertIsNone(result)

    def test_get_cached_data_generic_exception_returns_none(self):
        builder = MagicMock(side_effect=RuntimeError("unexpected"))
        mgr = _make_generic_manager(prefix="unexpecterr", builder=builder)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = mgr.get_cached_data("data")

        self.assertIsNone(result)

    def test_invalidate_cache_clears_both_levels(self):
        mgr = _make_generic_manager(prefix="inv_test")
        mgr._module_cache["data"] = ["stale"]

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.delete_many = MagicMock()
            mgr.invalidate_cache("test")

        mock_cache.delete_many.assert_called_once()
        self.assertEqual(mgr._module_cache, {})

    def test_get_cache_stats_keys(self):
        mgr = _make_generic_manager(prefix="stats_test", timeout=120)

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get_many.return_value = {}
            stats = mgr.get_cache_stats()

        for key in (
            "cache_prefix",
            "redis_keys",
            "redis_keys_count",
            "module_cache_count",
            "cache_timeout",
            "timestamp",
        ):
            self.assertIn(key, stats)

        self.assertEqual(stats["cache_prefix"], "stats_test")
        self.assertEqual(stats["cache_timeout"], 120)


# ---------------------------------------------------------------------------
# FormChoicesCacheManager
# ---------------------------------------------------------------------------


class FormChoicesCacheManagerTests(TestCase):
    """Tests the behavior of the FormChoicesCacheManager class. These tests verify that form choice data and related querysets are built, cached, retrieved, and invalidated correctly."""

    def _make_manager(self, choice_data=None, prefix="form_test"):
        """Return a FormChoicesCacheManager with mocked model."""
        model = _make_model_class()
        choice_data = choice_data or [{"color": "red"}, {"color": "blue"}]
        model.objects.filter.return_value.values.return_value = choice_data
        return FormChoicesCacheManager(
            model_class=model,
            choice_field="color",
            cache_prefix=prefix,
        )

    def test_get_form_choices_returns_list(self):
        mgr = self._make_manager()

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            choices = mgr.get_form_choices()

        self.assertIsInstance(choices, list)

    def test_get_queryset_json_returns_json_string(self):
        mgr = self._make_manager()

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            qs_json = mgr.get_queryset_json()

        # Should be valid JSON
        parsed = json.loads(qs_json)
        self.assertIsInstance(parsed, list)

    def test_get_choices_and_queryset_returns_tuple(self):
        mgr = self._make_manager()

        with patch("common.cache_managers.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            choices, qs_json = mgr.get_choices_and_queryset()

        self.assertIsInstance(choices, list)
        self.assertIsInstance(qs_json, str)

    def test_build_form_choices_data_structure(self):
        mgr = self._make_manager(choice_data=[{"color": "red"}])
        result = mgr._build_form_choices_data()
        self.assertIn("choices", result)
        self.assertIn("queryset", result)
        # choices should be list of (value, display) tuples
        choices = result["choices"]
        self.assertEqual(len(choices), 1)
        value, display = choices[0]
        self.assertEqual(value, "red")

    def test_build_form_choices_handles_attribute_error(self):
        """Attribute/value errors during build return empty defaults."""
        model = _make_model_class()
        model.objects.filter.side_effect = AttributeError("no field")
        mgr = FormChoicesCacheManager(
            model_class=model,
            choice_field="color",
            cache_prefix="err_test",
        )
        result = mgr._build_form_choices_data()
        self.assertEqual(result["choices"], [])
        self.assertEqual(result["queryset"], "[]")

    def test_get_cache_keys_has_choices_and_queryset(self):
        mgr = self._make_manager()
        keys = mgr.get_cache_keys()
        self.assertIn("choices", keys)
        self.assertIn("queryset", keys)


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class FactoryFunctionTests(TestCase):
    """Tests the behavior of cache manager factory functions. These tests verify that factory helpers create the correct manager instances and automatically register them in the shared cache registry."""

    def test_create_form_choices_manager_returns_instance(self):
        from common.cache_managers import cache_registry

        model = _make_model_class("FactoryModel")
        model.objects.filter.return_value.values.return_value = []

        mgr = create_form_choices_manager(
            model_class=model,
            choice_field="name",
            cache_prefix="factory_choices_test",
        )

        self.assertIsInstance(mgr, FormChoicesCacheManager)
        self.assertIsNotNone(cache_registry.get("factory_choices_test"))

    def test_create_category_manager_returns_instance(self):
        from common.cache_managers import cache_registry

        model = _make_model_class("FactoryCatModel")
        model.objects.all.return_value = []

        mgr = create_category_manager(model_class=model)

        self.assertIsInstance(mgr, CategoryCacheManager)
        self.assertIsNotNone(cache_registry.get("FactoryCatModel_categories"))
