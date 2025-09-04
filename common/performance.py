"""
module: common.performance

Enhanced performance module integrating with the generalized caching framework.
This replaces the specialized caching in your original module with the new
generalized approach while maintaining all existing functionality.

Features:
- Integration with generalized cache managers
- Backward compatibility with existing code
- Enhanced metrics and monitoring
- Simplified cache invalidation
"""

import hashlib
import os
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.http import HttpResponse
from django.http.response import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page, never_cache
from django.views.generic import TemplateView
from loguru import logger
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from common.cache_managers import (
    GenericDataCacheManager,
    cache_registry,
    get_cache_performance_summary,
)
from common.metrics import metrics

# ===================================================================
# Template View Caching (unchanged)
# ===================================================================


class CachedTemplateView(TemplateView):
    """Template view with automatic caching enabled."""

    @classmethod
    def as_view(cls, **initkwargs) -> Callable[..., HttpResponse]:
        """
        Returns a view function for the template view with caching enabled.
        """
        return cache_page(int(os.environ["CACHE_TTL"]))(
            super(CachedTemplateView, cls).as_view(**initkwargs)
        )


class NeverCacheMixin(TemplateView):
    """Mixin class to disable caching for Django views."""

    @method_decorator(never_cache)
    def dispatch(self, *args: Any, **kwargs: Any) -> HttpResponse:
        return super(NeverCacheMixin, self).dispatch(*args, **kwargs)


# ===================================================================
# Enhanced Cache Response Mixin with Generalized Cache Integration
# ===================================================================


class CachedResponseMixin(GenericAPIView):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bulk optimization settings (unchanged)
        self.bulk_select_related: Optional[List[str]] = getattr(
            self, "bulk_select_related", None
        )
        self.bulk_prefetch_related: Optional[List[str]] = getattr(
            self, "bulk_prefetch_related", None
        )
        self.bulk_cache_timeout: int = int(getattr(self, "bulk_cache_timeout", 1800))

        # Validate bulk optimization settings (unchanged)
        if (
            not self.bulk_select_related and self.bulk_select_related is not None
        ) or self.bulk_select_related == []:
            raise AttributeError(
                "Viewset must have a 'bulk_select_related' attribute defined."
            )
        if (
            not self.bulk_prefetch_related and self.bulk_prefetch_related is not None
        ) or self.bulk_prefetch_related == []:
            raise AttributeError(
                "Viewset must have a 'bulk_prefetch_related' attribute defined."
            )

        # Initialize cache manager if needed
        self._init_cache_manager()

    def _init_cache_manager(self):
        """Initialize cache manager for this view if not already registered."""
        primary_model = getattr(self, "primary_model", None)
        if primary_model:
            manager_name = f"{primary_model.__name__}_view_cache"

            if not cache_registry.get(manager_name):
                # Create a generic cache manager for this view
                def view_data_builder():
                    """Data builder for view caching."""
                    try:
                        queryset = self.get_queryset()
                        optimized_queryset = self.get_optimized_queryset(queryset)

                        # Extract basic data that can be cached
                        data = list(optimized_queryset.values())
                        return {"view_data": data}
                    except Exception as e:
                        logger.error(f"Error in view data builder: {e}")
                        return {"view_data": []}

                cache_manager = GenericDataCacheManager(
                    model_class=primary_model,
                    cache_prefix=f"{primary_model.__name__}_view",
                    data_builder=view_data_builder,
                    cache_timeout=getattr(settings, "VIEW_CACHE_TTL", 3600),
                )

                cache_registry.register(manager_name, cache_manager)
                self._cache_manager = cache_manager
            else:
                self._cache_manager = cache_registry.get(manager_name)

    def get_cache_key(self, action_name: str = "default", **kwargs: Any) -> str:
        """Generate a unique cache key based on the request and model information."""
        user_id: Union[int, str] = (
            self.request.user.pk if self.request.user.is_authenticated else "anon"
        )
        query_params: str = self.request.GET.urlencode()
        query_params_hash: str = hashlib.md5(
            query_params.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        model_names: List[str] = []
        primary_model: Optional[Model] = getattr(self, "primary_model", None)
        if primary_model:
            model_names.append(primary_model.__name__)
        else:
            raise AttributeError("View must have a 'primary_model' attribute.")

        cache_models: List[Model] = getattr(self, "cache_models", [])
        model_names.extend(model.__name__ for model in cache_models)
        model_names_str: str = "_".join(model_names)

        key_parts: List[str] = [
            primary_model.__name__,
            self.__class__.__name__,
            action_name,
            model_names_str,
            str(user_id),
            query_params_hash,
        ]

        key_parts.extend(
            f"{key}_{value}"
            for key, value in sorted(kwargs.items())
            if value is not None
        )

        return ":".join(key_parts) + "_cache_key"

    def get_cached_response(self, cache_key: str) -> Optional[Response]:
        """
        Retrieve cached data using the provided cache key.
        Now integrates with the generalized caching metrics.
        """
        cached_data: Any = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(
                f"Cache Hit for {self.primary_model.__name__} - Cache Key: {cache_key}"
            )
            metrics.increment_cache(self.primary_model.__name__, "hit")
            return Response(cached_data, status=status.HTTP_200_OK)
        else:
            logger.debug(
                f"Cache Miss for {self.primary_model.__name__} - Cache Key: {cache_key}"
            )
            metrics.increment_cache(self.primary_model.__name__, "miss")
            return None

    def cache_response(
        self, cache_key: str, data: Any, timeout: Optional[int] = None
    ) -> None:
        """Store data in the cache with the specified cache key."""
        if isinstance(data, TemplateResponse):
            data = data.render()
        elif isinstance(data, JsonResponse):
            data = data.content.decode("utf-8")

        cache_timeout = timeout or getattr(settings, "VIEW_CACHE_TTL", 3600)
        logger.debug(f"New Cache Set {cache_key}: {data}")
        cache.set(cache_key, data, timeout=cache_timeout)

    def get_optimized_queryset(
        self, base_queryset: Optional[QuerySet] = None
    ) -> QuerySet:
        """Get queryset optimized for bulk operations."""
        queryset: QuerySet = (
            self.get_queryset() if base_queryset is None else base_queryset
        )

        if self.bulk_select_related:
            queryset = queryset.select_related(*self.bulk_select_related)

        if self.bulk_prefetch_related:
            queryset = queryset.prefetch_related(*self.bulk_prefetch_related)

        return queryset

    def get_cached_bulk_data(
        self,
        cache_key: str,
        queryset_func: Callable[[], QuerySet],
        timeout: Optional[int] = None,
    ) -> Tuple[QuerySet, Dict[str, Any]]:
        """
        Cache bulk data using the cache manager if available.
        Falls back to original implementation if no manager is set up.
        """
        # Try using the cache manager if available
        if hasattr(self, "_cache_manager") and self._cache_manager:
            try:
                cached_data = self._cache_manager.get_cached_data("view_data")
                if cached_data:
                    logger.debug(f"Bulk Cache Hit via manager - Cache Key: {cache_key}")
                    metrics.increment_cache(self.primary_model.__name__, "hit")

                    # Build fresh queryset from cached IDs if they exist
                if cached_data and isinstance(cached_data, list)and len(cached_data)>0:
                    pk_field = self.primary_model._meta.pk.name
                    
                    if pk_field in cached_data[0]:
                        object_ids = [item[pk_field] for item in cached_data]
                        fresh_queryset = self.get_optimized_queryset().filter(
                            **{f"{pk_field}__in": object_ids}
                        )
                        extra_data = {
                            "total_count": len(object_ids),
                            "timestamp": timezone.now().isoformat(),
                        }
                        return fresh_queryset, extra_data
            except Exception as e:
                logger.warning(f"Error using cache manager, falling back: {e}")

        # Fallback to original implementation
        cached_data: Optional[Tuple[List[Any], Dict[str, Any]]] = cache.get(cache_key)
        if cached_data is not None:
            object_ids, extra_data = cached_data
            logger.debug(f"Bulk Cache Hit - Cache Key: {cache_key}")
            metrics.increment_cache(self.primary_model.__name__, "hit")

            fresh_queryset: QuerySet = self.get_optimized_queryset().filter(
                **{f"{self.primary_model._meta.pk.name}__in": object_ids}
            )
            return fresh_queryset, extra_data

        # Cache miss - execute query
        logger.debug(f"Bulk Cache Miss - Cache Key: {cache_key}")
        metrics.increment_cache(self.primary_model.__name__, "miss")

        queryset: QuerySet = queryset_func()
        optimized_queryset: QuerySet = self.get_optimized_queryset(queryset)

        pk_field: str = self.primary_model._meta.pk.name
        object_ids: List[Any] = list(
            optimized_queryset.values_list(pk_field, flat=True)
        )
        extra_data: Dict[str, Any] = self._extract_bulk_metadata(optimized_queryset)

        cache_timeout: int = timeout or self.bulk_cache_timeout
        cache.set(cache_key, (object_ids, extra_data), cache_timeout)

        return optimized_queryset, extra_data

    def _extract_bulk_metadata(self, queryset: QuerySet) -> Dict[str, Any]:
        """Extract metadata that should be cached alongside object IDs."""
        return {
            "total_count": queryset.count(),
            "timestamp": timezone.now().isoformat(),
        }

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle GET requests for listing resources with caching and optimization."""
        # Try bulk optimized approach first
        if hasattr(self, "bulk_select_related") or hasattr(
            self, "bulk_prefetch_related"
        ):
            cache_key: str = self.get_cache_key(
                "list",
                page=request.GET.get("page", "1"),
                page_size=request.GET.get("page_size", "20"),
            )

            def get_list_queryset():
                return self.filter_queryset(self.get_queryset())

            queryset, extra_data = self.get_cached_bulk_data(
                cache_key, get_list_queryset
            )

            # Apply pagination
            page: Optional[List[Any]] = self.paginate_queryset(queryset)
            if page is not None:
                serializer: serializers.BaseSerializer = self.get_serializer(
                    page, many=True
                )
                return self.get_paginated_response(serializer.data)

            serializer: serializers.BaseSerializer = self.get_serializer(
                queryset, many=True
            )
            return Response(serializer.data)

        # Fallback to standard caching approach
        cache_key: str = self.get_cache_key("list")
        if cached_response := self.get_cached_response(cache_key):
            return cached_response

        queryset: QuerySet = self.filter_queryset(self.get_queryset())
        page: Optional[List[Any]] = self.paginate_queryset(queryset)
        if page is not None:
            serializer: serializers.BaseSerializer = self.get_serializer(
                page, many=True
            )
            data: Any = serializer.data
            self.cache_response(cache_key, data)
            return self.get_paginated_response(data)

        serializer: serializers.BaseSerializer = self.get_serializer(
            queryset, many=True
        )
        data: Any = serializer.data
        self.cache_response(cache_key, data)
        return Response(data)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle GET requests for retrieving a single resource with caching."""
        cache_key: str = self.get_cache_key("retrieve", **kwargs)
        if cached_response := self.get_cached_response(cache_key):
            return cached_response

        instance: Any = self.get_object()
        serializer: serializers.BaseSerializer = self.get_serializer(instance)
        data: Any = serializer.data
        self.cache_response(cache_key, data)
        return Response(data)


# ===================================================================
# Enhanced Cache Invalidation Mixin
# ===================================================================


class CacheInvalidationMixin:
    """
    Enhanced mixin to handle cache invalidation using the generalized cache framework.
    """

    cache_invalidation_patterns: ClassVar[List[str]] = []
    cache_manager_names: ClassVar[List[str]] = (
        []
    )  # Names of cache managers to invalidate

    def invalidate_bulk_caches(self, patterns: Optional[List[str]] = None) -> None:
        """
        Invalidate cached data after mutations using both patterns and managers.
        """
        # Invalidate specific cache managers
        manager_names = self.cache_manager_names or []
        for manager_name in manager_names:
            if manager := cache_registry.get(manager_name):
                try:
                    manager.invalidate_cache("mutation_triggered")
                    logger.debug(f"Invalidated cache manager: {manager_name}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate manager {manager_name}: {e}")

        # Fallback to pattern-based invalidation
        if hasattr(cache, "delete_pattern"):
            patterns_to_clear: List[str] = patterns or self.cache_invalidation_patterns
            for pattern in patterns_to_clear:
                try:
                    cache.delete_pattern(pattern)
                    logger.debug(f"Invalidated cache pattern: {pattern}")
                except Exception as e:
                    logger.warning(f"Failed to clear cache pattern {pattern}: {e}")
        else:
            logger.warning("Cache backend does not support pattern deletion")

    def perform_create(self, serializer):
        """Override to invalidate caches after creation."""
        result = super().perform_create(serializer)
        self.invalidate_bulk_caches()
        return result

    def perform_update(self, serializer):
        """Override to invalidate caches after update."""
        result = super().perform_update(serializer)
        self.invalidate_bulk_caches()
        return result

    def perform_destroy(self, instance):
        """Override to invalidate caches after deletion."""
        result = super().perform_destroy(instance)
        self.invalidate_bulk_caches()
        return result


# ===================================================================
# Enhanced Category Cache Manager (now using the generalized framework)
# ===================================================================


def create_category_cache_manager(model_class, key_field="key", name_field="name"):
    """
    Factory function to create a category cache manager using the generalized framework.

    Args:
        model_class: The Django model class for categories
        key_field: Field name containing the category key
        name_field: Field name containing the category name

    Returns:
        GenericDataCacheManager configured for category operations
    """

    def category_data_builder():
        """Build category data with bidirectional lookup support."""
        try:
            queryset = model_class.objects.all()
            categories = {}
            key_to_name = {}
            name_to_key = {}

            for obj in queryset:
                key = getattr(obj, key_field)
                name = getattr(obj, name_field)
                categories[key] = name
                key_to_name[key] = name
                name_to_key[name.lower()] = key

            return {
                "categories": categories,
                "key_to_name": key_to_name,
                "name_to_key": name_to_key,
            }
        except Exception as e:
            logger.error(f"Error building category data: {e}")
            return {
                "categories": {},
                "key_to_name": {},
                "name_to_key": {},
            }

    manager = GenericDataCacheManager(
        model_class=model_class,
        cache_prefix=f"{model_class.__name__}_categories",
        data_builder=category_data_builder,
        cache_timeout=86400,  # 1 day
    )

    # Add convenience methods
    def get_category_name_by_key(key: str) -> Optional[str]:
        key_to_name = manager.get_cached_data("key_to_name") or {}
        return key_to_name.get(key)

    def get_category_key_by_name(name: str) -> Optional[str]:
        name_to_key = manager.get_cached_data("name_to_key") or {}
        return name_to_key.get(name.lower())

    def get_all_categories() -> Dict[str, str]:
        return manager.get_cached_data("categories") or {}

    # Bind methods to manager
    manager.get_category_name_by_key = get_category_name_by_key
    manager.get_category_key_by_name = get_category_key_by_name
    manager.get_all_categories = get_all_categories

    return manager


# ===================================================================
# Optimized Serializer Mixins (enhanced)
# ===================================================================


class CachedBulkSerializerMixin:
    """
    Enhanced mixin for serializers with bulk operation optimizations and field caching.
    """

    select_related_fields = []
    prefetch_related_fields = []
    cached_fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._field_cache = {}

    def get_cached_field_value(self, obj, field_name):
        """Get cached field value to avoid repeated expensive computations."""
        if field_name not in self.cached_fields:
            return None

        cache_key = f"{obj.pk}_{field_name}"
        return self._field_cache.get(cache_key)

    def set_cached_field_value(self, obj, field_name, value):
        """Cache a computed field value."""
        if field_name in self.cached_fields:
            cache_key = f"{obj.pk}_{field_name}"
            self._field_cache[cache_key] = value

    def to_representation(self, instance):
        """Override to handle bulk optimizations."""
        if hasattr(instance, "pk"):
            self._field_cache.clear()
        return super().to_representation(instance)


class OptimizedListSerializer(serializers.ListSerializer):
    """
    Optimized list serializer for bulk operations with query optimization.
    """

    def to_representation(self, data):
        """Override to apply bulk optimizations to the queryset."""
        if (
            hasattr(data, "select_related")
            and hasattr(self.child, "select_related_fields")
            and self.child.select_related_fields
        ):
            data = data.select_related(*self.child.select_related_fields)

        if (
            hasattr(data, "prefetch_related")
            and hasattr(self.child, "prefetch_related_fields")
            and self.child.prefetch_related_fields
        ):
            data = data.prefetch_related(*self.child.prefetch_related_fields)

        return super().to_representation(data)


# ===================================================================
# Enhanced Signal Handlers
# ===================================================================


@receiver([post_save, post_delete])
def invalidate_cache(sender: Model, **kwargs: Any) -> None:
    """
    Enhanced cache invalidation that works with the generalized cache framework.
    """
    model_name: str = sender.__name__
    logger.debug(f"Signal Received For {model_name}")

    # First, try to invalidate any registered cache managers for this model
    managers_invalidated = False
    for manager_name, manager in cache_registry.items():
        if hasattr(manager, "model_class") and manager.model_class == sender:
            try:
                if kwargs.get("created"):
                    reason = "post_save_created"
                elif "post_save" in str(kwargs):
                    reason = "post_save_updated"
                else:
                    reason = "post_delete"

                manager.invalidate_cache(reason)
                managers_invalidated = True
                logger.debug(f"Invalidated manager {manager_name} for {model_name}")
            except Exception as e:
                logger.warning(f"Error invalidating manager {manager_name}: {e}")

    # Fallback to pattern-based cache invalidation
    if not managers_invalidated:
        cache_key_pattern: str = f"{model_name}:*"
        logger.debug(f"Fallback: Searching For Cache Key Pattern: {cache_key_pattern}")

        if hasattr(cache, "keys"):
            try:
                if cache_keys := cache.keys(cache_key_pattern):
                    cache.delete_many(cache_keys)
                    metrics.increment_cache(
                        model_name, "invalidated", reason="pattern_delete"
                    )
                    logger.info(
                        f"Cache invalidated for model: {model_name}, keys: {len(cache_keys)}"
                    )
                else:
                    logger.debug(
                        f"No cache keys found for pattern: {cache_key_pattern}"
                    )
            except Exception as e:
                logger.warning(f"Error with pattern-based invalidation: {e}")


# ===================================================================
# Enhanced Utility Functions
# ===================================================================


def clear_all_cache() -> None:
    """Utility function to clear all cache entries using the registry."""
    try:
        # Clear all registered cache managers first
        cache_registry.invalidate_all("clear_all_utility")

        # Then clear the entire cache as fallback
        cache.clear()
        logger.info("All cache entries cleared")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")


def get_cache_stats() -> Dict[str, Any]:
    """Get comprehensive cache statistics."""
    try:
        # Get stats from the generalized framework
        performance_summary = get_cache_performance_summary()

        # Add legacy cache stats if available
        legacy_stats = None
        if hasattr(cache, "_cache") and hasattr(cache._cache, "get_stats"):
            legacy_stats = cache._cache.get_stats()

        return {
            "generalized_framework": performance_summary,
            "legacy_cache_stats": legacy_stats,
            "registry_stats": cache_registry.get_all_stats(),
        }
    except Exception as e:
        logger.warning(f"Could not retrieve comprehensive cache stats: {e}")
        return {"error": str(e)}


def warm_critical_caches() -> Dict[str, Any]:
    """Warm up critical cache managers on application startup."""
    results = {}
    critical_managers = []  # Define which managers are critical

    for manager_name in critical_managers:
        manager = cache_registry.get(manager_name)
        if manager:
            try:
                if hasattr(manager, "get_cached_data"):
                    manager.get_cached_data()
                elif hasattr(manager, "get_all_categories"):
                    manager.get_all_categories()
                elif hasattr(manager, "get_form_choices"):
                    manager.get_form_choices()

                results[manager_name] = "success"
                logger.info(f"Warmed critical cache: {manager_name}")

            except Exception as e:
                results[manager_name] = f"error: {str(e)}"
                logger.error(f"Error warming critical cache {manager_name}: {e}")
        else:
            results[manager_name] = "manager_not_found"

    return results


def register_common_cache_managers():
    """
    Register common cache managers that are used across the application.
    Call this during Django app initialization.
    """
    # This function should be called in your Django app's ready() method
    # to set up commonly used cache managers

    # Example registrations (uncomment and modify as needed):

    # Register insult choices manager (if not already registered in forms.py)
    # from applications.API.models import Insult
    # if not cache_registry.get("Insult_choices"):
    #     create_form_choices_manager(
    #         model_class=Insult,
    #         choice_field="reference_id",
    #         filter_kwargs={"status": "A"},
    #         cache_prefix="Insult"
    #     )

    pass  # Replace with actual registrations


# ===================================================================
# Integration with Django Apps
# ===================================================================


def setup_performance_caching():
    """
    Setup function to be called during Django app initialization.
    This ensures all cache managers are properly registered.
    """
    try:
        register_common_cache_managers()
        logger.info("Performance caching setup completed")
    except Exception as e:
        logger.error(f"Error setting up performance caching: {e}")
