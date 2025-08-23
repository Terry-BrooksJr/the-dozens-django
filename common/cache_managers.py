"""
module: common.cache_managers

Generalized caching framework for Django applications with comprehensive
data type support, multi-level caching, and automatic invalidation.

This module provides:
- Generic cache manager for any data type
- Form choices caching
- Multi-level caching (module-level + Redis)
- Automatic cache invalidation
- Performance metrics integration
- Thread-safe operations
"""

from __future__ import annotations

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.db.utils import ProgrammingError
from loguru import logger

from common.metrics import metrics


class BaseCacheManager(ABC):
    """
    Abstract base class for cache managers with standardized interface.
    """

    def __init__(self, model_class: Type[models.Model], cache_prefix: str = None):
        self.model_class = model_class
        self.cache_prefix = cache_prefix or model_class.__name__
        self.cache_timeout = getattr(self, "CACHE_TIMEOUT", 86400)  # 24 hours default
        self._cache_lock = threading.Lock()

    @abstractmethod
    def get_cache_keys(self) -> Dict[str, str]:
        """Return dictionary of cache key names and their full cache keys."""

    @abstractmethod
    def build_data_from_db(self) -> Dict[str, Any]:
        """Build data from database. Should return dict with cache key names as keys."""

    def invalidate_cache(self, reason: str = "manual") -> None:
        """Invalidate all cache entries for this manager."""
        logger.info(f"Invalidating {self.cache_prefix} cache (reason: {reason})")

        with metrics.time_cache_operation(self.cache_prefix, "invalidate"):
            cache_keys = list(self.get_cache_keys().values())
            cache.delete_many(cache_keys)
            metrics.increment_cache(self.cache_prefix, "invalidated", reason)


class GenericDataCacheManager(BaseCacheManager):
    """
    Generic cache manager for any data type with configurable data building.

    Supports:
    - Multi-level caching (module-level + Redis)
    - Automatic invalidation on model changes
    - Performance metrics
    - Thread-safe operations
    """

    # Default cache timeout (24 hours)
    CACHE_TIMEOUT = int(os.environ["CACHE_TTL"])

    def __init__(
        self,
        model_class: Type[models.Model],
        cache_prefix: str = None,
        data_builder: Callable = None,
        cache_timeout: int = int(os.environ["CACHE_TTL"]),
    ):
        super().__init__(model_class, cache_prefix)

        self.data_builder = data_builder or self._default_data_builder
        self.cache_timeout = cache_timeout or self.CACHE_TIMEOUT

        # Module-level cache storage
        self._module_cache: Dict[str, Any] = {}

        # Register signal handlers
        self._register_signals()

    def get_cache_keys(self) -> Dict[str, str]:
        """Get cache keys for this manager."""
        return {
            "data": f"{self.cache_prefix}:generic_data_v1",
        }

    def _default_data_builder(self) -> Dict[str, Any]:
        """Default data builder - returns all model instances as dict."""
        try:
            queryset = self.model_class.objects.all()
            data = list(queryset.values())
            return {"data": data}
        except Exception as e:
            logger.error(f"Error in default data builder for {self.cache_prefix}: {e}")
            return {"data": []}

    def build_data_from_db(self) -> Dict[str, Any]:
        """Build data using the configured data builder."""
        return self.data_builder()

    def get_cached_data(self, cache_key: str = "data") -> Any:
        """
        Get cached data with multi-level caching strategy.

        Args:
            cache_key: Which cache key to retrieve (defaults to "data")

        Returns:
            Cached data or None if not found
        """
        cache_keys = self.get_cache_keys()
        full_cache_key = cache_keys.get(cache_key)

        if not full_cache_key:
            logger.warning(f"Invalid cache key: {cache_key}")
            return None

        with self._cache_lock:
            # Level 1: Module-level cache
            if cache_key in self._module_cache:
                logger.debug(
                    f"Module-level cache hit for {self.cache_prefix}:{cache_key}"
                )
                metrics.increment_cache(self.cache_prefix, "hit")
                return self._module_cache[cache_key]

            # Level 2: Redis cache
            cached_data = cache.get(full_cache_key)
            if cached_data is not None:
                logger.debug(f"Redis cache hit for {self.cache_prefix}:{cache_key}")
                metrics.increment_cache(self.cache_prefix, "hit")
                self._module_cache[cache_key] = cached_data
                return cached_data

            # Level 3: Database query (cache miss)
            return self._build_and_cache_data(cache_key, full_cache_key)

    def _build_and_cache_data(self, cache_key: str, full_cache_key: str) -> Any:
        """Build data from database and cache it."""
        logger.info(
            f"Cache miss - querying database for {self.cache_prefix}:{cache_key}"
        )
        metrics.increment_cache(self.cache_prefix, "miss")

        db_start_time = time.time()

        try:
            with metrics.time_database_query(self.cache_prefix, "success"):
                built_data = self.build_data_from_db()
                data = built_data.get(cache_key)

                if data is not None:
                    # Cache in both levels
                    self._module_cache[cache_key] = data
                    cache.set(full_cache_key, data, timeout=self.cache_timeout)

                    db_duration = time.time() - db_start_time
                    logger.info(
                        f"Successfully cached {self.cache_prefix}:{cache_key} in {db_duration:.2f}s"
                    )
                    return data
                else:
                    logger.warning(f"No data returned for cache key: {cache_key}")
                    return None

        except ProgrammingError as e:
            logger.error(f"Database not ready for {self.cache_prefix}: {e}")
            return None
        except Exception as e:
            db_duration = time.time() - db_start_time
            logger.error(f"Unexpected error caching {self.cache_prefix} data: {e}")
            metrics.record_database_query_time(self.cache_prefix, db_duration, "error")
            return None

    def invalidate_cache(self, reason: str = "manual") -> None:
        """Invalidate both module-level and Redis cache."""
        with self._cache_lock:
            super().invalidate_cache(reason)
            self._module_cache.clear()

    def _register_signals(self):
        """Register signal handlers for automatic cache invalidation."""

        def handle_model_change(sender, instance, **kwargs):
            if kwargs.get("created"):
                reason = "post_save_created"
            elif "post_save" in str(kwargs):
                reason = "post_save_updated"
            else:
                reason = "post_delete"

            logger.debug(
                f"{self.cache_prefix} {instance.pk} modified ({reason}), invalidating cache"
            )
            self.invalidate_cache(reason)

        post_save.connect(
            handle_model_change,
            sender=self.model_class,
            dispatch_uid=f"{self.__class__.__name__}_{self.model_class.__name__}_post_save",
        )
        post_delete.connect(
            handle_model_change,
            sender=self.model_class,
            dispatch_uid=f"{self.__class__.__name__}_{self.model_class.__name__}_post_delete",
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        cache_keys = self.get_cache_keys()
        redis_data = cache.get_many(list(cache_keys.values()))

        return {
            "cache_prefix": self.cache_prefix,
            "redis_keys": list(cache_keys.keys()),
            "redis_keys_count": len(redis_data),
            "module_cache_count": len(self._module_cache),
            "cache_timeout": self.cache_timeout,
            "timestamp": time.time(),
        }


class FormChoicesCacheManager(GenericDataCacheManager):
    """
    Specialized cache manager for Django form choices.

    Provides optimized caching for form choice fields with support for:
    - Choice tuples generation
    - Custom display formatting
    - Queryset JSON serialization
    """

    def __init__(
        self,
        model_class: Type[models.Model],
        choice_field: str,
        display_formatter: Callable[[Any], str] = None,
        filter_kwargs: Dict[str, Any] = None,
        cache_prefix: str = None,
    ):

        self.choice_field = choice_field
        self.display_formatter = display_formatter or self._default_display_formatter
        self.filter_kwargs = filter_kwargs or {}

        # Build data builder function
        data_builder = self._build_form_choices_data
        super().__init__(model_class, cache_prefix, data_builder)

    def get_cache_keys(self) -> Dict[str, str]:
        """Get cache keys for form choices."""
        return {
            "choices": f"{self.cache_prefix}:form_choices_v2",
            "queryset": f"{self.cache_prefix}:form_queryset_v2",
        }

    def _default_display_formatter(self, obj: Any) -> str:
        """Default formatter for choice display text."""
        if hasattr(obj, self.choice_field):
            value = getattr(obj, self.choice_field)
            return f"{self.choice_field.replace('_', ' ').title()}: {value}"
        return str(obj)

    def _build_form_choices_data(self) -> Dict[str, Any]:
        """Build form choices and queryset data from database."""
        try:
            # Build queryset with filters
            queryset = self.model_class.objects.filter(**self.filter_kwargs)

            # Get values for choices
            choice_data = list(queryset.values(self.choice_field))

            # Build choices list (value, display_text) tuples
            choices = []
            for item in choice_data:
                value = item[self.choice_field]
                display_text = self.display_formatter(item)
                choices.append((value, display_text))

            # Serialize queryset as JSON
            queryset_json = json.dumps(choice_data, cls=DjangoJSONEncoder)

            return {
                "choices": choices,
                "queryset": queryset_json,
            }

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Error building form choices for {self.cache_prefix}: {e}")
            return {
                "choices": [],
                "queryset": "[]",
            }

    def get_form_choices(self) -> List[Tuple[Any, str]]:
        """Get cached form choices."""
        return self.get_cached_data("choices") or []

    def get_queryset_json(self) -> str:
        """Get cached queryset as JSON string."""
        return self.get_cached_data("queryset") or "[]"

    def get_choices_and_queryset(self) -> Tuple[List[Tuple[Any, str]], str]:
        """Get both choices and queryset in one call - matches your original API."""
        with self._cache_lock:
            choices = self.get_cached_data("choices") or []
            queryset_json = self.get_cached_data("queryset") or "[]"
            return choices, queryset_json


class CategoryCacheManager(BaseCacheManager):
    """
    Manages caching for category data, providing efficient retrieval and bidirectional mapping
    between category keys and names. This class supports cache invalidation, cache population,
    and lookup operations for category data.

    The manager caches all categories, individual key-to-name and name-to-key mappings, and
    provides methods for cache invalidation and population from the database.
    """

    CACHE_TIMEOUT = 86400  # 1 Day

    def __init__(
        self,
        model_class: Type[models.Model],
        key_field: str = "key",
        name_field: str = "name",
    ):
        super().__init__(model_class, "categories")
        self.key_field = key_field
        self.name_field = name_field

    def get_cache_keys(self) -> Dict[str, str]:
        """Get all cache keys used by category manager."""
        return {
            "all": f"{self.cache_prefix}:all",
            "name_prefix": f"{self.cache_prefix}:name:",
            "key_prefix": f"{self.cache_prefix}:key:",
        }

    def build_data_from_db(self) -> Dict[str, Any]:
        """Build category mappings from database."""
        try:
            queryset = self.model_class.objects.all()
            categories = {}

            for obj in queryset:
                key = getattr(obj, self.key_field)
                name = getattr(obj, self.name_field)
                categories[key] = name

            return {"all": categories}
        except Exception as e:
            logger.error(f"Error building category data: {e}")
            return {"all": {}}

    def get_category_name_by_key(self, category_key: str) -> Optional[str]:
        """Get category name by key with caching."""
        cache_keys = self.get_cache_keys()
        cache_key = f"{cache_keys['name_prefix']}{category_key}"

        if cached_name := cache.get(cache_key):
            return cached_name

        # Fallback to all categories
        all_categories = self.get_all_categories()
        return all_categories.get(category_key)

    def get_category_key_by_name(self, category_name: str) -> Optional[str]:
        """Get category key by name with caching."""
        cache_keys = self.get_cache_keys()
        cache_key = f"{cache_keys['key_prefix']}{category_name.lower()}"

        if cached_key := cache.get(cache_key):
            return cached_key

        # Fallback to all categories
        all_categories = self.get_all_categories()
        return next(
            (
                key
                for key, name in all_categories.items()
                if name.lower() == category_name.lower()
            ),
            None,
        )

    def set_category_name_mapping(self, category_key: str, name: str) -> None:
        """Cache category name bidirectionally."""
        cache_keys = self.get_cache_keys()
        cache_key_for_key = f"{cache_keys['key_prefix']}{category_key}"
        cache_key_for_name = f"{cache_keys['name_prefix']}{name.lower()}"

        cache.set(cache_key_for_name, category_key, self.cache_timeout)
        cache.set(cache_key_for_key, name, self.cache_timeout)

    def get_all_categories(self) -> Dict[str, str]:
        """Get all categories from cache."""
        cache_keys = self.get_cache_keys()
        cached_data = cache.get(cache_keys["all"])

        if cached_data is not None:
            return cached_data

        # Build from database
        built_data = self.build_data_from_db()
        categories = built_data["all"]

        # Cache the result
        cache.set(cache_keys["all"], categories, self.cache_timeout)

        # Also set individual mappings
        for key, name in categories.items():
            self.set_category_name_mapping(key, name)

        return categories

    def invalidate_category(self, category_key: str) -> None:
        """Invalidate specific category cache."""
        cache_keys = self.get_cache_keys()

        # Get name before invalidation
        category_name = self.get_category_name_by_key(category_key)

        keys_to_delete = [
            f"{cache_keys['name_prefix']}{category_key}",
            cache_keys["all"],
        ]

        if category_name:
            keys_to_delete.append(f"{cache_keys['key_prefix']}{category_name.lower()}")

        cache.delete_many(keys_to_delete)


# ===================================================================
# Cache Manager Registry
# ===================================================================


class CacheManagerRegistry:
    """
    Registry for managing multiple cache managers across the application.
    """

    def __init__(self):
        self._managers: Dict[str, BaseCacheManager] = {}

    def names(self) -> List[str]:
        """Return a list of registered cache manager names (read-only)."""
        return list(self._managers.keys())

    def items(self):
        """Iterate (name, manager) pairs for registered managers (read-only)."""
        return self._managers.items()

    def values(self):
        """Iterate managers (read-only)."""
        return self._managers.values()

    def all(self) -> Dict[str, BaseCacheManager]:
        """Return a shallow copy mapping of all registered managers (read-only)."""
        return dict(self._managers)

    def count(self) -> int:
        """Return number of registered managers."""
        return len(self._managers)

    def register(self, name: str, manager: BaseCacheManager) -> None:
        """Register a cache manager."""
        self._managers[name] = manager
        logger.info(f"Registered cache manager: {name}")

    def get(self, name: str) -> Optional[BaseCacheManager]:
        """Get a registered cache manager."""
        return self._managers.get(name)

    def invalidate_all(self, reason: str = "manual") -> None:
        """Invalidate all registered cache managers."""
        for name, manager in self._managers.items():
            try:
                manager.invalidate_cache(reason)
                logger.info(f"Invalidated cache manager: {name}")
            except Exception as e:
                logger.error(f"Error invalidating cache manager {name}: {e}")

    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats from all registered cache managers."""
        stats = {}
        for name, manager in self._managers.items():
            try:
                if hasattr(manager, "get_cache_stats"):
                    stats[name] = manager.get_cache_stats()
            except Exception as e:
                logger.error(f"Error getting stats for cache manager {name}: {e}")
                stats[name] = {"error": str(e)}
        return stats


# Global registry instance
cache_registry = CacheManagerRegistry()


# ===================================================================
# Utility Functions
# ===================================================================


def create_form_choices_manager(
    model_class: Type[models.Model],
    choice_field: str,
    display_formatter: Callable[[Any], str] = None,
    filter_kwargs: Dict[str, Any] = None,
    cache_prefix: str = None,
) -> FormChoicesCacheManager:
    """
    Factory function to create and register a form choices cache manager.
    """
    manager = FormChoicesCacheManager(
        model_class=model_class,
        choice_field=choice_field,
        display_formatter=display_formatter,
        filter_kwargs=filter_kwargs,
        cache_prefix=cache_prefix,
    )

    # Auto-register with a sensible name
    registry_name = cache_prefix or f"{model_class.__name__}_choices"
    cache_registry.register(registry_name, manager)

    return manager


def create_category_manager(
    model_class: Type[models.Model], key_field: str = "key", name_field: str = "name"
) -> CategoryCacheManager:
    """
    Factory function to create and register a category cache manager.
    """
    manager = CategoryCacheManager(model_class, key_field, name_field)
    cache_registry.register(f"{model_class.__name__}_categories", manager)
    return manager


def get_cache_performance_summary() -> Dict[str, Any]:
    """
    Get performance summary for all registered cache managers.
    """
    return {
        "managers": cache_registry.get_all_stats(),
        "timestamp": time.time(),
    }


def clear_all_caches() -> None:
    """Clear all registered cache managers."""
    cache_registry.invalidate_all("manual_clear_all")
