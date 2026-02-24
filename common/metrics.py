from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from prometheus_client import Counter, Histogram

import os
import time

try:
    import ldobserve.observe as observe
except Exception:  # LaunchDarkly observability plugin is optional
    observe = None


@lru_cache(maxsize=1)
def _ld_metrics_enabled() -> bool:
    """
    App-level kill switch for LaunchDarkly observability.

    Note: ldobserve is designed to no-op safely when not initialized,
    but this avoids extra work in hot paths when disabled.
    """
    return (
        os.getenv("LAUNCHDARKLY_OBSERVABILITY_ENABLED", "false").strip().lower()
        == "true"
        and observe is not None
    )


def _as_cache_reason(reason: str | None) -> str:
    return (reason or "unspecified").strip() or "unspecified"


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
        """
        Record cache events. Supported events:
        - hit
        - miss
        - invalidated (requires/uses reason)
        """
        ld_enabled = _ld_metrics_enabled()

        if event == "hit":
            CACHE_HITS.labels(cache_prefix).inc()
            if ld_enabled:
                observe.record_incr(
                    "cache_hits_total",
                    attributes={"cache_prefix": cache_prefix},
                )

        elif event == "miss":
            CACHE_MISSES.labels(cache_prefix).inc()
            if ld_enabled:
                observe.record_incr(
                    "cache_misses_total",
                    attributes={"cache_prefix": cache_prefix},
                )

        elif event == "invalidated":
            reason_val = _as_cache_reason(reason)
            CACHE_INVALIDATIONS.labels(cache_prefix, reason_val).inc()
            if ld_enabled:
                observe.record_incr(
                    "cache_invalidations_total",
                    attributes={"cache_prefix": cache_prefix, "reason": reason_val},
                )

        else:
            # Keep callers honest. Silent failures create fake dashboards.
            raise ValueError(
                f"Unknown cache event '{event}'. Expected hit|miss|invalidated."
            )

    @contextmanager
    def time_cache_operation(self, cache_prefix: str, operation: str):
        """
        Times a cache operation and emits:
        - Prometheus histogram timing
        - LaunchDarkly histogram + optional span
        """
        ld_enabled = _ld_metrics_enabled()
        start = time.perf_counter()

        span = None
        if ld_enabled:
            # Optional trace span to correlate performance with other signals
            span = observe.start_span(
                "cache.operation",
                attributes={"cache_prefix": cache_prefix, "operation": operation},
            )
            span.__enter__()

        try:
            with CACHE_OP_SECONDS.labels(cache_prefix, operation).time():
                yield
        except Exception as e:
            if ld_enabled:
                # If the exception escapes, this will be recorded.
                # If you catch exceptions inside the block, call observe.record_exception yourself.
                observe.record_exception(e)
            raise
        finally:
            duration = time.perf_counter() - start

            if ld_enabled:
                observe.record_histogram(
                    "cache_operation_seconds",
                    duration,
                    attributes={"cache_prefix": cache_prefix, "operation": operation},
                )
                if span is not None:
                    span.__exit__(None, None, None)

    @contextmanager
    def time_database_query(self, cache_prefix: str):
        """
        Times DB work and correctly labels status based on whether an exception escapes.
        Emits:
        - Prometheus histogram observation
        - LaunchDarkly histogram + optional span
        """
        ld_enabled = _ld_metrics_enabled()
        start = time.perf_counter()
        status = "success"

        span = None
        if ld_enabled:
            span = observe.start_span(
                "cache.db_query",
                attributes={"cache_prefix": cache_prefix},
            )
            span.__enter__()

        try:
            yield
        except Exception as e:
            status = "error"
            if ld_enabled:
                observe.record_exception(e)
            raise
        finally:
            duration = time.perf_counter() - start

            DB_QUERY_SECONDS.labels(cache_prefix, status).observe(duration)

            if ld_enabled:
                observe.record_histogram(
                    "cache_db_query_seconds",
                    duration,
                    attributes={"cache_prefix": cache_prefix, "status": status},
                )
                if span is not None:
                    span.__exit__(None, None, None)

    def record_database_query_time(
        self, cache_prefix: str, duration: float, status: str = "success"
    ):
        """
        Manual recording for cases where timing is calculated elsewhere.
        """
        duration_f = float(duration)
        status_val = (status or "success").strip().lower()
        if status_val not in {"success", "error"}:
            status_val = "success"

        DB_QUERY_SECONDS.labels(cache_prefix, status_val).observe(duration_f)

        if _ld_metrics_enabled():
            observe.record_histogram(
                "cache_db_query_seconds",
                duration_f,
                attributes={"cache_prefix": cache_prefix, "status": status_val},
            )


metrics = _MetricsFacade()
