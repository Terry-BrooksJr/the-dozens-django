"""
module: common.preformance

This module provides comprehensive caching and optimization utilities for Django views and models.
It includes mixins for caching API responses, bulk query optimization, cache invalidation,
and specialized managers for category data caching.

Features:
- Response caching for API views
- Bulk query optimization with select_related/prefetch_related
- Automatic cache invalidation on model changes
- Category-specific caching utilities
- Template view caching
- Serializer optimization for bulk operations
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.http.response import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page, never_cache
from django.views.generic import TemplateView
from loguru import logger
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.metrics import metrics


# ===================================================================
# Template View Caching
# ===================================================================


class CachedTemplateView(TemplateView):
    """Template view with automatic caching enabled."""

    @classmethod
    def as_view(cls, **initkwargs):
        """
        Returns a view function for the template view with caching enabled.

        This method wraps the standard Django TemplateView with cache_page,
        using the configured cache timeout to cache the rendered template response.

        Args:
            **initkwargs: Initialization keyword arguments for the view.

        Returns:
            function: A Django view function with caching applied.
        """
        return cache_page(settings.CACHE_TTL)(
            super(CachedTemplateView, cls).as_view(**initkwargs)
        )


class NeverCacheMixin(TemplateView):
    """Mixin class to disable caching for Django views.

    This mixin ensures that responses from views using it are never cached,
    forcing fresh content to be served for every request.
    """

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super(NeverCacheMixin, self).dispatch(*args, **kwargs)


# ===================================================================
# Core Cache Response Mixin
# ===================================================================


class CachedResponseMixin(GenericAPIView):
    """
    Enhanced mixin class to provide comprehensive caching functionality for API responses.
    
    This mixin allows views to cache their responses based on user identity, query parameters,
    and model information, with support for bulk operations and query optimization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bulk optimization settings
        self.bulk_select_related: Union[List[str], None] = getattr(self, "bulk_select_related", None)
        self.bulk_prefetch_related: Union[List[str], None] = getattr(self, "bulk_prefetch_related", None)
        self.bulk_cache_timeout:int = getattr(self, "bulk_cache_timeout", 1800)
        
        # Validate bulk optimization settings
        if (not self.bulk_select_related and self.bulk_select_related is not None) or self.bulk_select_related == []:
            raise AttributeError("Viewset must have a 'bulk_select_related' attribute defined. If No select_related is needed, set it to 'None'")
        if (not self.bulk_prefetch_related and self.bulk_prefetch_related is not None) or self.bulk_prefetch_related == []:
            raise AttributeError("Viewset must have a 'bulk_prefetch_related' attribute defined. If No prefetch_related is needed, set it to 'None'")

    def get_cache_key(self, action_name: str = "default", **kwargs) -> str:
        """
        Generate a unique cache key based on the request and model information.

        This method constructs a cache key that incorporates the user ID, query parameters,
        model names, and action context.

        Args:
            action_name: The action being performed (list, retrieve, bulk, etc.)
            **kwargs: Additional parameters to include in the cache key

        Returns:
            str: A unique cache key for the current request.

        Raises:
            AttributeError: If the view does not have a 'primary_model' attribute.
        """
        user_id = self.request.user.id if self.request.user.is_authenticated else "anon"
        query_params = self.request.GET.urlencode()
        query_params_hash = hashlib.md5(
            query_params.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        # Get the model name(s) associated with the view
        model_names = []

        # Add the primary model name
        primary_model = getattr(self, "primary_model", None)
        if primary_model:
            model_names.append(primary_model.__name__)
        else:
            raise AttributeError("View must have a 'primary_model' attribute.")

        # Add the cache_models names
        cache_models = getattr(self, "cache_models", [])
        model_names.extend(model.__name__ for model in cache_models)
        model_names_str = "_".join(model_names)

        # Build cache key parts
        key_parts = [
            primary_model.__name__,
            self.__class__.__name__,
            action_name,
            model_names_str,
            str(user_id),
            query_params_hash
        ]

        # Add additional parameters
        key_parts.extend(
            f"{key}_{value}"
            for key, value in sorted(kwargs.items())
            if value is not None
        )

        return ":".join(key_parts) + "_cache_key"

    def get_cached_response(self, cache_key: str) -> Union[Response, None]:
        """
        Retrieve cached data using the provided cache key.

        Args:
            cache_key: The cache key to look up.

        Returns:
            Response or None: The cached response if found, otherwise None.
        """
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache Hit for {self.primary_model.__name__} - Cache Key: {cache_key}")
            metrics.increment_cache(model=self.primary_model.__name__, cache_type="hit")
            return Response(cached_data, status=status.HTTP_200_OK)
        else:
            logger.debug(f"Cache Miss for {self.primary_model.__name__} - Cache Key: {cache_key}")
            metrics.increment_cache(model=self.primary_model.__name__, cache_type="miss")
            return None

    def cache_response(self, cache_key: str, data, timeout: Optional[int] = None):
        """
        Store data in the cache with the specified cache key.

        Args:
            cache_key: The cache key under which to store the data.
            data: The data to be cached.
            timeout: Cache timeout in seconds. If None, uses default setting.
        """
        if isinstance(data, TemplateResponse):
            data = data.render()
        elif isinstance(data, JsonResponse):
            data = data.content.decode("utf-8")
        
        cache_timeout = timeout or getattr(settings, 'VIEW_CACHE_TTL', 3600)
        logger.debug(f"New Cache Set {cache_key}: {data}")
        cache.set(cache_key, data, timeout=cache_timeout)

    def get_optimized_queryset(self, base_queryset=None):
        """
        Get queryset optimized for bulk operations with select_related and prefetch_related.

        Args:
            base_queryset: Base queryset to optimize. If None, uses get_queryset().

        Returns:
            Optimized queryset with applied select_related and prefetch_related.
        """
        queryset = self.get_queryset() if base_queryset is None else base_queryset
        
        # Apply select_related for ForeignKey/OneToOne relationships
        if self.bulk_select_related:
            queryset = queryset.select_related(*self.bulk_select_related)

        # Apply prefetch_related for ManyToMany/reverse FK relationships
        if self.bulk_prefetch_related:
            queryset = queryset.prefetch_related(*self.bulk_prefetch_related)

        return queryset

    def get_cached_bulk_data(
        self, cache_key: str, queryset_func, timeout: Optional[int] = None
    ):
        """
        Cache bulk data using object IDs to maintain data freshness.

        Args:
            cache_key: Cache key for storing the data.
            queryset_func: Function that returns the base queryset.
            timeout: Cache timeout in seconds.

        Returns:
            Tuple of (optimized_queryset, extra_metadata).
        """
        # Try to get cached IDs and metadata
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            object_ids, extra_data = cached_data
            logger.debug(f"Bulk Cache Hit - Cache Key: {cache_key}")
            metrics.increment_cache(model=self.primary_model.__name__, cache_type="bulk_hit")
            
            # Return fresh queryset with cached IDs
            fresh_queryset = self.get_optimized_queryset().filter(
                **{f"{self.primary_model._meta.pk.name}__in": object_ids}
            )
            return fresh_queryset, extra_data

        # Cache miss - execute query
        logger.debug(f"Bulk Cache Miss - Cache Key: {cache_key}")
        metrics.increment_cache(model=self.primary_model.__name__, cache_type="bulk_miss")
        
        queryset = queryset_func()
        optimized_queryset = self.get_optimized_queryset(queryset)

        # Extract IDs and any extra metadata
        pk_field = self.primary_model._meta.pk.name
        object_ids = list(optimized_queryset.values_list(pk_field, flat=True))
        extra_data = self._extract_bulk_metadata(optimized_queryset)

        # Cache the IDs and metadata
        cache_timeout = timeout or self.bulk_cache_timeout
        cache.set(cache_key, (object_ids, extra_data), cache_timeout)

        return optimized_queryset, extra_data

    def _extract_bulk_metadata(self, queryset):
        """
        Extract metadata that should be cached alongside object IDs.
        Override in your ViewSet for specific metadata.

        Args:
            queryset: The queryset to extract metadata from.

        Returns:
            Dict containing metadata to be cached.
        """
        return {
            "total_count": queryset.count(),
            "timestamp": timezone.now().isoformat(),
        }

    def list(self, request, *args, **kwargs) -> Response:
        """
        Handle GET requests for listing resources with caching and optimization.

        Args:
            request: The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: The cached or newly generated response.
        """
        # Try bulk optimized approach first
        if hasattr(self, 'bulk_select_related') or hasattr(self, 'bulk_prefetch_related'):
            cache_key = self.get_cache_key(
                "list",
                page=request.GET.get("page", "1"),
                page_size=request.GET.get("page_size", "20"),
            )

            def get_list_queryset():
                return self.filter_queryset(self.get_queryset())

            queryset, extra_data = self.get_cached_bulk_data(cache_key, get_list_queryset)

            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        # Fallback to standard caching approach
        cache_key = self.get_cache_key("list")
        if cached_response := self.get_cached_response(cache_key):
            return cached_response

        # If cache miss, proceed as usual
        queryset = self.filter_queryset(self.get_queryset())

        # Apply pagination if needed
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            self.cache_response(cache_key, data)
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        self.cache_response(cache_key, data)
        return Response(data)

    def retrieve(self, request, *args, **kwargs) -> Response:
        """
        Handle GET requests for retrieving a single resource with caching.

        Args:
            request: The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: The cached or newly generated response.
        """
        cache_key = self.get_cache_key("retrieve", **kwargs)
        if cached_response := self.get_cached_response(cache_key):
            return cached_response

        # If cache miss, proceed as usual
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        self.cache_response(cache_key, data)
        return Response(data)


# ===================================================================
# Cache Invalidation Mixin
# ===================================================================


class CacheInvalidationMixin:
    """
    Mixin to handle cache invalidation for bulk operations and model changes.
    """

    cache_invalidation_patterns = []  # e.g., ['bulk:insult*', 'categories:*']

    def invalidate_bulk_caches(self, patterns: Optional[List[str]] = None):
        """
        Invalidate cached data after mutations.

        Args:
            patterns: List of cache key patterns to invalidate. If None, uses class default.
        """
        if not hasattr(cache, "delete_pattern"):
            logger.warning("Cache backend does not support pattern deletion")
            return

        patterns_to_clear = patterns or self.cache_invalidation_patterns
        for pattern in patterns_to_clear:
            try:
                cache.delete_pattern(pattern)
                logger.debug(f"Invalidated cache pattern: {pattern}")
            except Exception as e:
                logger.warning(f"Failed to clear cache pattern {pattern}: {e}")

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
# Specialized Category Cache Manager
# ===================================================================


class CategoryCacheManager:
    """
    Specialized cache manager for category data with hash table-like operations.
    """

    CACHE_KEY_PREFIX = "categories"
    CACHE_TIMEOUT = 86400  # 1 Day

    @classmethod
    def get_category_name_by_key(cls, category_key: str) -> Optional[str]:
        """Get category name by key with caching."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}:name:{category_key}"
        return cache.get(cache_key)

    @classmethod
    def get_category_key_by_name(cls, category_name: str) -> Optional[str]:
        """Get category key by name with caching."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}:key:{category_name.lower()}"
        return cache.get(cache_key)

    @classmethod
    def set_category_name_mapping(cls, category_key: str, name: str) -> None:
        """Cache category name bidirectionally."""
        cache_key_for_key = f"{cls.CACHE_KEY_PREFIX}:name:{category_key}"
        cache_key_for_name = f"{cls.CACHE_KEY_PREFIX}:key:{name.lower()}"
        cache.set(cache_key_for_name, category_key, cls.CACHE_TIMEOUT)
        cache.set(cache_key_for_key, name.lower(), cls.CACHE_TIMEOUT)

    @classmethod
    def get_all_categories(cls) -> Optional[Dict[str, str]]:
        """Get all categories from cache."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}:all"
        return cache.get(cache_key)

    @classmethod
    def set_all_categories(cls, categories: Dict[str, str]) -> None:
        """Cache all categories and individual mappings."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}:all"
        cache.set(cache_key, categories, cls.CACHE_TIMEOUT)

        # Also set individual category names
        for key, name in categories.items():
            cls.set_category_name_mapping(key, name)

    @classmethod
    def invalidate_category(cls, category_key: str) -> None:
        """Invalidate specific category cache."""
        if category_name := cls.get_category_name_by_key(category_key):
            cache.delete_many([
                f"{cls.CACHE_KEY_PREFIX}:name:{category_key}",
                f"{cls.CACHE_KEY_PREFIX}:all",
                f"{cls.CACHE_KEY_PREFIX}:key:{category_name.lower()}"
            ])
        cache.delete_many([
                f"{cls.CACHE_KEY_PREFIX}:name:{category_key}",
                f"{cls.CACHE_KEY_PREFIX}:all",
            ])

# ===================================================================
# Optimized Serializer Mixins
# ===================================================================


class CachedBulkSerializerMixin:
    """
    Mixin for serializers to provide bulk operation optimizations and field caching.
    """
    
    # Override these in your serializer
    select_related_fields = []
    prefetch_related_fields = []
    cached_fields = []  # Fields to cache expensive computations
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._field_cache = {}
    
    def get_cached_field_value(self, obj, field_name):
        """
        Get cached field value to avoid repeated expensive computations.
        
        Args:
            obj: The model instance
            field_name: Name of the field being computed
            
        Returns:
            Cached value if available, None otherwise
        """
        if field_name not in self.cached_fields:
            return None
            
        cache_key = f"{obj.pk}_{field_name}"
        return self._field_cache.get(cache_key)
    
    def set_cached_field_value(self, obj, field_name, value):
        """
        Cache a computed field value.
        
        Args:
            obj: The model instance
            field_name: Name of the field being computed
            value: The computed value to cache
        """
        if field_name in self.cached_fields:
            cache_key = f"{obj.pk}_{field_name}"
            self._field_cache[cache_key] = value
    
    def to_representation(self, instance):
        """Override to handle bulk optimizations."""
        # Clear field cache for new instance
        if hasattr(instance, 'pk'):
            self._field_cache.clear()
        
        return super().to_representation(instance)


class OptimizedListSerializer(serializers.ListSerializer):
    """
    Optimized list serializer for bulk operations with query optimization.
    """
    
    def to_representation(self, data):
        """
        Override to apply bulk optimizations to the queryset.
        """
        # Apply optimizations if data is a queryset
        if hasattr(data, 'select_related') and hasattr(self.child, 'select_related_fields'):
            if self.child.select_related_fields:
                data = data.select_related(*self.child.select_related_fields)
        
        if hasattr(data, 'prefetch_related') and hasattr(self.child, 'prefetch_related_fields'):
            if self.child.prefetch_related_fields:
                data = data.prefetch_related(*self.child.prefetch_related_fields)
        
        return super().to_representation(data)


# ===================================================================
# Signal Handlers for Cache Invalidation
# ===================================================================


@receiver([post_save, post_delete])
def invalidate_cache(sender, **kwargs):
    """
    Invalidates cache entries related to the given model upon save or delete signals.

    This function listens for post_save and post_delete signals and removes any cache
    keys associated with the affected model, ensuring that stale data is not served.

    Args:
        sender: The model class that triggered the signal.
        **kwargs: Additional keyword arguments provided by the signal.
    """
    model_name = sender.__name__
    logger.debug(f"Signal Received For {model_name}")
    
    # Pattern to match cache keys that include the model name as namespace
    cache_key_pattern = f"{model_name}:*"
    logger.debug(f'Searching For Cache Key Pattern: {cache_key_pattern}')
    
    if cache_keys := cache.keys(cache_key_pattern):
        cache.delete_many(cache_keys)
        metrics.increment_cache(model=model_name, cache_type="eviction")
        logger.info(f"Cache invalidated for model: {model_name}, keys: {len(cache_keys)}")
    else:
        logger.debug(f"No cache keys found for model: {model_name} using {cache_key_pattern}")


# ===================================================================
# Utility Functions
# ===================================================================


def clear_all_cache():
    """Utility function to clear all cache entries."""
    try:
        cache.clear()
        logger.info("All cache entries cleared")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")


def get_cache_stats():
    """Get cache statistics if available."""
    try:
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_stats'):
            return cache._cache.get_stats()
    except Exception as e:
        logger.warning(f"Could not retrieve cache stats: {e}")
    return None