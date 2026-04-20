from __future__ import annotations

import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.http import JsonResponse
from django.test import override_settings
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.response import Response

from applications.API.models import Insult, InsultCategory, Theme
from common import performance

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


class MetricsSpy:
    def __init__(self):
        self.increment_cache = MagicMock()
        self.record_database_query_time = MagicMock()
        self.time_cache_operation = MagicMock(side_effect=lambda *a, **k: nullcontext())
        self.time_database_query = MagicMock(side_effect=lambda *a, **k: nullcontext())


class FakeRegistry:
    def __init__(self):
        self._managers = {}

    def register(self, name, manager):
        self._managers[name] = manager

    def get(self, name):
        return self._managers.get(name)

    def items(self):
        return self._managers.items()

    def invalidate_all(self, reason="manual"):
        for manager in self._managers.values():
            manager.invalidate_cache(reason)

    def get_all_stats(self):
        return {
            name: manager.get_cache_stats()
            for name, manager in self._managers.items()
            if hasattr(manager, "get_cache_stats")
        }


class FakeManager:
    def __init__(self, model_class=None, cached_data=None):
        self.model_class = model_class
        self.cached_data = cached_data
        self.invalidate_cache = MagicMock()
        self.get_cached_data = MagicMock(return_value=cached_data)
        self.get_cache_stats = MagicMock(return_value={"ok": True})


class FakeGenericDataCacheManager:
    def __init__(self, model_class, cache_prefix, data_builder, cache_timeout):
        self.model_class = model_class
        self.cache_prefix = cache_prefix
        self.data_builder = data_builder
        self.cache_timeout = cache_timeout
        self.invalidate_cache = MagicMock()
        self.get_cached_data = MagicMock(return_value=None)

    def get_cache_stats(self):
        return {
            "cache_prefix": self.cache_prefix,
            "cache_timeout": self.cache_timeout,
        }


class InsultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insult
        fields = ("insult_id", "content", "reference_id", "status")


class CachedInsultListView(performance.CachedResponseMixin):
    primary_model = Insult
    cache_models = [Theme, InsultCategory]
    bulk_select_related = ["theme", "category", "added_by"]
    bulk_prefetch_related = None
    serializer_class = InsultSerializer

    def __init__(self, queryset=None, obj=None, *args, **kwargs):
        self._queryset = queryset if queryset is not None else Insult.objects.all()
        self._object = obj
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        return self._queryset

    def filter_queryset(self, queryset):
        return queryset

    def paginate_queryset(self, queryset):
        return None

    def get_serializer(self, instance, many=False):
        return self.serializer_class(instance, many=many)

    def get_paginated_response(self, data):
        return Response({"results": data})

    def get_object(self):
        return self._object or self._queryset.first()


class DummyMutationBase:
    def perform_create(self, serializer):
        return "created"

    def perform_update(self, serializer):
        return "updated"

    def perform_destroy(self, instance):
        return "destroyed"


class MutationView(performance.CacheInvalidationMixin, DummyMutationBase):
    cache_manager_names = ["insult_view_cache"]
    cache_invalidation_patterns = ["Insult:*"]


class CachedFieldSerializer(
    performance.CachedBulkSerializerMixin, serializers.Serializer
):
    insult_id = serializers.IntegerField()
    content = serializers.CharField()
    cached_fields = ["expensive_value"]


class ChildSerializer(serializers.Serializer):
    insult_id = serializers.IntegerField()
    content = serializers.CharField()
    select_related_fields = ["category"]
    prefetch_related_fields = []


class FakeOptimizableSequence(list):
    def __init__(self, iterable):
        super().__init__(iterable)
        self.select_related_calls = []
        self.prefetch_related_calls = []

    def select_related(self, *args):
        self.select_related_calls.append(args)
        return self

    def prefetch_related(self, *args):
        self.prefetch_related_calls.append(args)
        return self


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture
def metrics_spy(monkeypatch):
    spy = MetricsSpy()
    monkeypatch.setattr(performance, "metrics", spy)
    return spy


@pytest.fixture
def api_rf():
    return APIRequestFactory()


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        username="terry",
        email="terry@example.com",
        password="not-a-good-password-but-here-we-are",
    )


@pytest.fixture
def theme():
    return Theme.objects.create(
        theme_key="TECH1",
        theme_name="Tech Theme",
        description="Theme for testing",
    )


@pytest.fixture
def category(theme):
    return InsultCategory.objects.create(
        category_key="TST1",
        name="Testing",
        description="Testing category",
        theme=theme,
    )


@pytest.fixture
def second_category(theme):
    return InsultCategory.objects.create(
        category_key="TST2",
        name="Debugging",
        description="Debugging category",
        theme=theme,
    )


@pytest.fixture
def insults(user, theme, category):
    insult_1 = Insult.objects.create(
        content="First insult",
        theme=theme,
        category=category,
        nsfw=False,
        added_by=user,
        status=Insult.STATUS.ACTIVE,
    )
    insult_2 = Insult.objects.create(
        content="Second insult",
        theme=theme,
        category=category,
        nsfw=True,
        added_by=user,
        status=Insult.STATUS.ACTIVE,
    )
    return [insult_1, insult_2]


@pytest.fixture(autouse=True)
def clear_redis_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------
# CachedResponseMixin
# ---------------------------------------------------------------------


def test_get_cache_key_includes_expected_components(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/?page=2&search=fire")
    force_authenticate(request, user=insults[0].added_by)

    view = CachedInsultListView(
        queryset=Insult.objects.filter(pk__in=[i.pk for i in insults])
    )
    view.request = Request(request)

    key = view.get_cache_key("list", page=2, page_size=20)

    expected_hash = hashlib.md5(
        "page=2&search=fire".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()

    assert key.startswith(
        "Insult:CachedInsultListView:list:Insult_Theme_InsultCategory:"
    )
    assert f":{insults[0].added_by.pk}:" in key
    assert expected_hash in key
    assert key.endswith("page_2:page_size_20_cache_key")


def test_get_cache_key_uses_anon_for_unauthenticated_user(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/")
    request.user = SimpleNamespace(is_authenticated=False, pk=None)

    view = CachedInsultListView(queryset=Insult.objects.all())
    view.request = Request(request)

    key = view.get_cache_key("list")

    assert ":anon:" in key


def test_get_cached_response_returns_response_and_increments_hit(
    api_rf, insults, metrics_spy
):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    view = CachedInsultListView(queryset=Insult.objects.all())
    view.request = Request(request)

    payload = [{"insult_id": insults[0].insult_id, "content": insults[0].content}]
    cache.set("cached-key", payload, timeout=300)

    response = view.get_cached_response("cached-key")

    assert response is not None
    assert response.status_code == 200
    assert response.data == payload
    metrics_spy.increment_cache.assert_called_once_with("Insult", "hit")


def test_get_cached_response_returns_none_and_increments_miss(
    api_rf, insults, metrics_spy
):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    view = CachedInsultListView(queryset=Insult.objects.all())
    view.request = Request(request)

    response = view.get_cached_response("missing-key")

    assert response is None
    metrics_spy.increment_cache.assert_called_once_with("Insult", "miss")


@override_settings(VIEW_CACHE_TTL=777)
def test_cache_response_stores_json_response_as_string(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    view = CachedInsultListView(queryset=Insult.objects.all())
    view.request = Request(request)

    response = JsonResponse({"ok": True})
    view.cache_response("json-key", response)

    cached_value = cache.get("json-key")
    assert cached_value == '{"ok": true}'


def test_get_optimized_queryset_applies_select_related(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    base_queryset = Insult.objects.all()
    view = CachedInsultListView(queryset=base_queryset)
    view.request = Request(request)

    optimized = view.get_optimized_queryset()

    assert "theme" in optimized.query.select_related
    assert "category" in optimized.query.select_related
    assert "added_by" in optimized.query.select_related


def test_get_cached_bulk_data_uses_manager_cache_hit(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    queryset = Insult.objects.filter(
        insult_id__in=[i.insult_id for i in insults]
    ).order_by("insult_id")
    view = CachedInsultListView(queryset=queryset)
    view.request = Request(request)

    cached_rows = [
        {"insult_id": insults[0].insult_id},
        {"insult_id": insults[1].insult_id},
    ]
    view._cache_manager = FakeManager(model_class=Insult, cached_data=cached_rows)

    fresh_queryset, extra_data = view.get_cached_bulk_data(
        "bulk-key",
        queryset_func=lambda: queryset,
    )

    assert list(fresh_queryset.values_list("insult_id", flat=True)) == [
        insults[0].insult_id,
        insults[1].insult_id,
    ]
    assert extra_data["total_count"] == 2
    assert "timestamp" in extra_data
    metrics_spy.increment_cache.assert_called_once_with("Insult", "hit")


def test_get_cached_bulk_data_uses_redis_fallback_hit(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    queryset = Insult.objects.filter(
        insult_id__in=[i.insult_id for i in insults]
    ).order_by("insult_id")
    view = CachedInsultListView(queryset=queryset)
    view.request = Request(request)
    view._cache_manager = None

    extra_data = {"total_count": 2, "timestamp": "2026-01-01T00:00:00"}
    cache.set(
        "bulk-key",
        ([insults[0].insult_id, insults[1].insult_id], extra_data),
        timeout=300,
    )

    fresh_queryset, returned_extra = view.get_cached_bulk_data(
        "bulk-key",
        queryset_func=lambda: queryset,
    )

    assert list(fresh_queryset.values_list("insult_id", flat=True)) == [
        insults[0].insult_id,
        insults[1].insult_id,
    ]
    assert returned_extra == extra_data
    metrics_spy.increment_cache.assert_called_once_with("Insult", "hit")


def test_get_cached_bulk_data_builds_from_db_and_caches_result(
    api_rf, insults, metrics_spy
):
    request = api_rf.get("/api/insults/")
    request.user = insults[0].added_by

    queryset = Insult.objects.filter(
        insult_id__in=[i.insult_id for i in insults]
    ).order_by("insult_id")
    view = CachedInsultListView(queryset=queryset)
    view.request = Request(request)
    view._cache_manager = None

    returned_queryset, extra_data = view.get_cached_bulk_data(
        "bulk-build-key",
        queryset_func=lambda: queryset,
        timeout=222,
    )

    assert list(returned_queryset.values_list("insult_id", flat=True)) == [
        insults[0].insult_id,
        insults[1].insult_id,
    ]
    assert extra_data["total_count"] == 2
    assert "timestamp" in extra_data

    cached_value = cache.get("bulk-build-key")
    assert cached_value[0] == [insults[0].insult_id, insults[1].insult_id]
    assert cached_value[1]["total_count"] == 2

    metrics_spy.increment_cache.assert_called_once_with("Insult", "miss")


def test_list_returns_serialized_results_via_bulk_path(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/?page=1&page_size=20")
    request.user = insults[0].added_by

    queryset = Insult.objects.filter(
        insult_id__in=[i.insult_id for i in insults]
    ).order_by("insult_id")
    view = CachedInsultListView(queryset=queryset)
    drf_request = Request(request)
    view.request = drf_request

    response = view.list(drf_request)

    assert response.status_code == 200
    assert len(response.data) == 2
    assert response.data[0]["insult_id"] == insults[0].insult_id
    assert response.data[1]["insult_id"] == insults[1].insult_id


def test_retrieve_caches_and_returns_single_object(api_rf, insults, metrics_spy):
    request = api_rf.get("/api/insults/1/")
    request.user = insults[0].added_by

    view = CachedInsultListView(queryset=Insult.objects.all(), obj=insults[0])
    drf_request = Request(request)
    view.request = drf_request

    response = view.retrieve(drf_request, insult_id=insults[0].insult_id)

    assert response.status_code == 200
    assert response.data["insult_id"] == insults[0].insult_id

    cached_keys = (
        [k for k in cache.iter_keys("*")] if hasattr(cache, "iter_keys") else []
    )
    if cached_keys:
        assert any("retrieve" in str(key) for key in cached_keys)


# ---------------------------------------------------------------------
# _init_cache_manager / registry interaction
# ---------------------------------------------------------------------


def test_init_cache_manager_registers_manager_when_missing(
    monkeypatch, api_rf, insults
):
    fake_registry = FakeRegistry()
    monkeypatch.setattr(performance, "cache_registry", fake_registry)
    monkeypatch.setattr(
        performance, "GenericDataCacheManager", FakeGenericDataCacheManager
    )

    view = CachedInsultListView(queryset=Insult.objects.all())

    manager = fake_registry.get("Insult_view_cache")
    assert manager is not None
    assert manager.model_class is Insult
    assert manager.cache_prefix == "Insult_view"
    assert view._cache_manager is manager


def test_init_cache_manager_reuses_existing_manager(monkeypatch):
    fake_registry = FakeRegistry()
    existing = FakeManager(model_class=Insult)
    fake_registry.register("Insult_view_cache", existing)

    monkeypatch.setattr(performance, "cache_registry", fake_registry)

    view = CachedInsultListView(queryset=Insult.objects.all())

    assert view._cache_manager is existing


# ---------------------------------------------------------------------
# CacheInvalidationMixin
# ---------------------------------------------------------------------


def test_invalidate_bulk_caches_invalidates_managers_and_patterns(monkeypatch):
    fake_registry = FakeRegistry()
    fake_manager = FakeManager(model_class=Insult)
    fake_registry.register("insult_view_cache", fake_manager)

    delete_pattern_spy = MagicMock()
    mock_cache = MagicMock()
    mock_cache.delete_pattern = delete_pattern_spy
    monkeypatch.setattr(performance, "cache_registry", fake_registry)
    monkeypatch.setattr(performance, "cache", mock_cache)

    view = MutationView()
    view.invalidate_bulk_caches()

    fake_manager.invalidate_cache.assert_called_once_with("mutation_triggered")
    delete_pattern_spy.assert_called_once_with("Insult:*")


def test_perform_create_update_destroy_trigger_invalidation(monkeypatch):
    invalidate_spy = MagicMock()
    monkeypatch.setattr(MutationView, "invalidate_bulk_caches", invalidate_spy)

    view = MutationView()

    assert view.perform_create(serializer=MagicMock()) == "created"
    assert view.perform_update(serializer=MagicMock()) == "updated"
    assert view.perform_destroy(instance=MagicMock()) == "destroyed"
    assert invalidate_spy.call_count == 3


# ---------------------------------------------------------------------
# Signal invalidation helpers
# ---------------------------------------------------------------------


def test_invalidation_reason_post_save_created():
    reason = performance._invalidation_reason(post_save, {"created": True})
    assert reason == "post_save_created"


def test_invalidation_reason_post_save_updated():
    reason = performance._invalidation_reason(post_save, {"created": False})
    assert reason == "post_save_updated"


def test_invalidation_reason_post_delete():
    reason = performance._invalidation_reason(post_delete, {})
    assert reason == "post_delete"


def test_invalidate_cache_uses_registered_manager(monkeypatch, metrics_spy):
    fake_registry = FakeRegistry()
    fake_manager = FakeManager(model_class=Insult)
    fake_registry.register("insult_manager", fake_manager)

    monkeypatch.setattr(performance, "cache_registry", fake_registry)

    performance.invalidate_cache(sender=Insult, signal=post_save, created=True)

    fake_manager.invalidate_cache.assert_called_once_with("post_save_created")
    metrics_spy.increment_cache.assert_not_called()


def test_invalidate_cache_falls_back_to_pattern_delete(monkeypatch, metrics_spy):
    fake_registry = FakeRegistry()
    monkeypatch.setattr(performance, "cache_registry", fake_registry)

    keys_spy = MagicMock(return_value=["Insult:a", "Insult:b"])
    delete_many_spy = MagicMock()
    mock_cache = MagicMock()
    mock_cache.keys = keys_spy
    mock_cache.delete_many = delete_many_spy

    monkeypatch.setattr(performance, "cache", mock_cache)

    performance.invalidate_cache(sender=Insult, signal=post_delete)

    keys_spy.assert_called_once_with("Insult:*")
    delete_many_spy.assert_called_once_with(["Insult:a", "Insult:b"])
    metrics_spy.increment_cache.assert_called_once_with(
        "Insult", "invalidated", reason="pattern_delete"
    )


# ---------------------------------------------------------------------
# Category cache manager factory
# ---------------------------------------------------------------------


def test_create_category_cache_manager_builder_returns_expected_maps(
    category, second_category
):
    manager = performance.create_category_cache_manager(
        InsultCategory,
        key_field="category_key",
        name_field="name",
    )

    built = manager.data_builder()

    assert built["categories"] == {
        category.category_key: category.name,
        second_category.category_key: second_category.name,
    }
    assert built["key_to_name"][category.category_key] == category.name
    assert built["name_to_key"][category.name.lower()] == category.category_key


@pytest.mark.xfail(
    reason=(
        "create_category_cache_manager binds convenience methods that call "
        "GenericDataCacheManager.get_cached_data() with unsupported keys "
        "('categories', 'key_to_name', 'name_to_key')."
    ),
    strict=True,
)
def test_create_category_cache_manager_convenience_methods(category, second_category):
    manager = performance.create_category_cache_manager(
        InsultCategory,
        key_field="category_key",
        name_field="name",
    )

    assert manager.get_category_name_by_key(category.category_key) == category.name
    assert (
        manager.get_category_key_by_name(second_category.name)
        == second_category.category_key
    )
    assert manager.get_all_categories()[category.category_key] == category.name


# ---------------------------------------------------------------------
# Serializer mixins
# ---------------------------------------------------------------------


def test_cached_bulk_serializer_mixin_caches_only_configured_fields(insults):
    serializer = CachedFieldSerializer()

    serializer.set_cached_field_value(insults[0], "expensive_value", 123)
    serializer.set_cached_field_value(insults[0], "not_cached", 999)

    assert serializer.get_cached_field_value(insults[0], "expensive_value") == 123
    assert serializer.get_cached_field_value(insults[0], "not_cached") is None


def test_cached_bulk_serializer_to_representation_clears_field_cache(insults):
    serializer = CachedFieldSerializer()
    serializer.set_cached_field_value(insults[0], "expensive_value", 123)

    assert serializer._field_cache

    data = serializer.to_representation(
        {"insult_id": insults[0].insult_id, "content": insults[0].content}
    )

    assert data["insult_id"] == insults[0].insult_id
    assert serializer._field_cache == {}


def test_optimized_list_serializer_applies_queryset_optimizations(insults):
    data = FakeOptimizableSequence(
        [
            {"insult_id": insults[0].insult_id, "content": insults[0].content},
            {"insult_id": insults[1].insult_id, "content": insults[1].content},
        ]
    )

    serializer = performance.OptimizedListSerializer(child=ChildSerializer())
    result = serializer.to_representation(data)

    assert len(result) == 2
    assert data.select_related_calls == [("category",)]
    assert data.prefetch_related_calls == []


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------


def test_clear_all_cache_invalidates_registry_and_clears_cache(monkeypatch):
    fake_registry = FakeRegistry()
    fake_manager = FakeManager(model_class=Insult)
    fake_registry.register("insult_cache", fake_manager)

    monkeypatch.setattr(performance, "cache_registry", fake_registry)

    cache.set("temp-key", {"ok": True}, timeout=30)
    assert cache.get("temp-key") == {"ok": True}

    performance.clear_all_cache()

    fake_manager.invalidate_cache.assert_called_once_with("clear_all_utility")
    assert cache.get("temp-key") is None


def test_get_cache_stats_returns_framework_registry_and_legacy_stats(monkeypatch):
    fake_registry = FakeRegistry()
    fake_manager = FakeManager(model_class=Insult)
    fake_registry.register("insult_cache", fake_manager)

    monkeypatch.setattr(performance, "cache_registry", fake_registry)
    monkeypatch.setattr(
        performance,
        "get_cache_performance_summary",
        MagicMock(return_value={"summary": "ok"}),
    )

    fake_internal_cache = SimpleNamespace(get_stats=MagicMock(return_value={"hits": 5}))
    mock_cache = MagicMock()
    mock_cache._cache = fake_internal_cache
    monkeypatch.setattr(performance, "cache", mock_cache)

    stats = performance.get_cache_stats()

    assert stats["generalized_framework"] == {"summary": "ok"}
    assert stats["legacy_cache_stats"] == {"hits": 5}
    assert stats["registry_stats"] == {"insult_cache": {"ok": True}}


def test_warm_critical_caches_returns_empty_when_no_critical_managers():
    result = performance.warm_critical_caches()
    assert result == {}


def test_setup_performance_caching_calls_register_common_cache_managers(monkeypatch):
    register_spy = MagicMock()
    monkeypatch.setattr(performance, "register_common_cache_managers", register_spy)

    performance.setup_performance_caching()

    register_spy.assert_called_once_with()
