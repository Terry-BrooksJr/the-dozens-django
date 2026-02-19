from __future__ import annotations

from contextlib import contextmanager

from prometheus_client import Counter, Histogram

# ---- Prometheus metrics ----
CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_prefix"],
)
CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_prefix"],
)
CACHE_INVALIDATIONS = Counter(
    "cache_invalidations_total",
    "Total cache invalidations",
    ["cache_prefix", "reason"],
)
CACHE_OP_SECONDS = Histogram(
    "cache_operation_seconds",
    "Duration of cache operations",
    ["cache_prefix", "operation"],
)
DB_QUERY_SECONDS = Histogram(
    "cache_db_query_seconds",
    "DB time while rebuilding cache",
    ["cache_prefix", "status"],  # status: success|error
)


class _MetricsFacade:
    """Thin facade used throughout the app to record cache metrics.

    Methods are intentionally minimal and stable so callers aren't tied to
    prometheus_client specifics.
    """

    def increment_cache(self, cache_prefix: str, event: str, reason: str | None = None):
        if event == "hit":
            CACHE_HITS.labels(cache_prefix).inc()
        elif event == "invalidated":
            CACHE_INVALIDATIONS.labels(cache_prefix, reason or "unspecified").inc()
        elif event == "miss":
            CACHE_MISSES.labels(cache_prefix).inc()

    @contextmanager
    def time_cache_operation(self, cache_prefix: str, operation: str):
        with CACHE_OP_SECONDS.labels(cache_prefix, operation).time():
            yield

    @contextmanager
    def time_database_query(self, cache_prefix: str, status: str = "success"):
        with DB_QUERY_SECONDS.labels(cache_prefix, status).time():
            yield

    def record_database_query_time(
        self, cache_prefix: str, duration: float, status: str = "success"
    ):
        DB_QUERY_SECONDS.labels(cache_prefix, status).observe(duration)


metrics = _MetricsFacade()
