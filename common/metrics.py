from typing import Any, ContextManager, Dict, TypeVar, Union

from prometheus_client import Counter, Gauge, Histogram

DozensMetricsType = TypeVar("DozensMetricsType", bound="DozensMetrics")


class DozensMetrics:
    """Manages metrics tracking for the Dozens jokes API application.

    This class provides a comprehensive metrics tracking system for monitoring various
    application events and performance indicators. It uses Prometheus-style counters,
    gauges, and histograms to record submission attempts, cache interactions, and
    document processing metrics.

    Attributes:
        NAMESPACE (str): The base namespace for all metrics in the web application.
        cached_queryset_hit (Counter): Counter for requests served by a cached Queryset.
        cache_stats_* (Gauge): Various gauges for real-time cache statistics.
    """

    _instance: Union[None, DozensMetricsType] = None

    # Existing cache counters
    cached_queryset_hit = Counter(
        "cached_queryset_hit",
        "Number of requests served by a cached Queryset",
        ["model"],
    )
    cached_queryset_miss = Counter(
        "cached_queryset_miss",
        "Number of requests not served by a cached Queryset",
        ["model"],
    )
    cached_queryset_evicted = Counter(
        "cached_queryset_evicted", "Number of cached Querysets evicted", ["model"]
    )

    # New cache invalidation counter
    cached_queryset_invalidated = Counter(
        "cached_queryset_invalidated",
        "Number of times cache was invalidated",
        ["model", "reason"],  # reason could be 'post_save', 'post_delete', 'manual'
    )

    # Cache statistics gauges (real-time values)
    cache_module_loaded = Gauge(
        "cache_module_loaded_status",
        "Whether module-level cache is loaded (1=loaded, 0=not loaded)",
        ["model", "cache_type"],
    )

    cache_choices_count = Gauge(
        "cache_choices_count", "Number of choices currently in cache", ["model"]
    )

    cache_redis_keys_count = Gauge(
        "cache_redis_keys_present", "Number of Redis cache keys present", ["model"]
    )

    # Cache operation timing
    cache_operation_duration = Histogram(
        "cache_operation_duration_seconds",
        "Time spent on cache operations",
        ["model", "operation"],  # operation: 'load', 'invalidate', 'query_db'
        buckets=[
            0.1,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            15.0,
            30.0,
        ],  # Include 15s for your slow query
    )

    # Database query performance
    database_query_duration = Histogram(
        "database_query_duration_seconds",
        "Time spent querying database for cache data",
        ["model", "status"],  # status: 'success', 'error'
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 15.0, 30.0, 60.0],
    )

    def __new__(cls):
        """Ensures that only one instance of DozensMetrics is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.cache_operation_duration = cls.cache_operation_duration
            cls._instance.database_query_duration = cls.database_query_duration
        return cls._instance

    @classmethod
    def increment_cache(cls, model: str, cache_type: str, reason: Union[None,str] = None) -> None:
        """Tracks cache performance metrics for different database models.

        This method increments the appropriate counter based on the cache interaction type,
        providing insights into cache hit, miss, and eviction rates for specific models.

        Args:
            model: The name of the database model being cached.
            cache_type: The type of cache interaction ('hit', 'miss', 'eviction', 'invalidated').
            reason: Optional reason for invalidation ('post_save', 'post_delete', 'manual').

        Returns:
            None
        """
        if cache_type == "hit":
            cls.cached_queryset_hit.labels(model=model).inc()
        elif cache_type == "miss":
            cls.cached_queryset_miss.labels(model=model).inc()
        elif cache_type == "eviction":
            cls.cached_queryset_evicted.labels(model=model).inc()
        elif cache_type == "invalidated":
            cls.cached_queryset_invalidated.labels(
                model=model, reason=reason or "unknown"
            ).inc()

    @classmethod
    def update_cache_stats(cls, model: str, stats: Dict[str, Any]) -> None:
        """Updates cache statistics gauges with current cache state.

            Args:
                model: The name of the database model.
        def update_cache_stats(cls, model: str, stats: dict[str, Any]) -> None:
                    Expected keys:
                    - 'module_cache_loaded': bool
                    - 'choices_count': int
                    - 'redis_keys': dict (from cache.get_many result)

            Example usage:
                stats = get_cache_stats()
                metrics.update_cache_stats('Insult', stats)
        """
        # Update module cache loaded status
        module_loaded = 1 if stats.get("module_cache_loaded", False) else 0
        cls.cache_module_loaded.labels(model=model, cache_type="module").set(
            module_loaded
        )

        # Update choices count
        choices_count = stats.get("choices_count", 0)
        cls.cache_choices_count.labels(model=model).set(choices_count)

        # Update Redis keys count
        redis_keys = stats.get("redis_keys", {})
        redis_keys_count = len(redis_keys) if redis_keys else 0
        cls.cache_redis_keys_count.labels(model=model).set(redis_keys_count)

    @classmethod
    def time_cache_operation(cls, model: str, operation: str) -> ContextManager:
        """Context manager for timing cache operations.

        Usage:
            with metrics.time_cache_operation('Insult', 'load'):
                # Your cache operation here
                pass
        """
        return cls.cache_operation_duration.labels(
            model=model, operation=operation
        ).time()

    @classmethod
    def time_database_query(cls, model: str, status: str = "success"):
        """Context manager for timing database queries.

        Usage:
            with metrics.time_database_query('Insult', 'success'):
                # Your database query here
                pass
        """
        return cls.database_query_duration.labels(model=model, status=status).time()

    @classmethod
    def record_database_query_time(
        cls, model: str, duration: float, status: str = "success"
    ) -> None:
        """Record database query duration manually.

        Args:
            model: The database model name.
            duration: Query duration in seconds.
            status: Query status ('success' or 'error').
        """
        cls.database_query_duration.labels(model=model, status=status).observe(duration)

    @classmethod
    def get_cache_hit_rate(cls, model: str) -> float:
        """Calculate cache hit rate for a model (for debugging/monitoring).

        Args:
            model: The database model name.

        Returns:
            Hit rate as a percentage (0.0 to 100.0), or 0.0 if no data.
        """
        try:
            # Note: Accessing internal Prometheus client attributes
            # This may break with future prometheus_client versions
            hits_metric = cls.cached_queryset_hit.labels(model=model)
            misses_metric = cls.cached_queryset_miss.labels(model=model)

            hits = getattr(hits_metric, "_value", None)
            misses = getattr(misses_metric, "_value", None)

            if hits is None or misses is None:
                return 0.0

            hits_value = getattr(hits, "_value", 0)
            misses_value = getattr(misses, "_value", 0)
            total = hits_value + misses_value

            if total == 0:
                return 0.0

            return (hits_value / total) * 100.0
        except Exception:
            return 0.0


# Create a singleton instance for global use
metrics = DozensMetrics()
