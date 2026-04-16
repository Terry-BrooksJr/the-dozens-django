from __future__ import annotations

import os
import time
from contextlib import contextmanager
from functools import lru_cache

from prometheus_client import Counter, Histogram

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

# ---- RandomInsultEndpoint metrics ----
RANDOM_INSULT_REQUESTS = Counter(
    "random_insult_requests_total",
    "Total requests to /api/insults/random/",
    ["status", "category_filtered", "nsfw_filtered"],
)
RANDOM_INSULT_STAGE_SECONDS = Histogram(
    "random_insult_stage_seconds",
    "Duration of each processing stage inside RandomInsultEndpoint",
    ["stage"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)
RANDOM_INSULT_QUERYSET_EMPTY = Counter(
    "random_insult_queryset_empty_total",
    "Times the random insult queryset returned no rows after filtering",
)
RANDOM_INSULT_DB_QUERIES = Counter(
    "random_insult_db_queries_total",
    "Total SQL queries executed per random insult request (summed across requests)",
)

# ---- Per-endpoint cache counters ----
ENDPOINT_CACHE_HITS = Counter(
    "endpoint_cache_hits_total",
    "Cache hits keyed by endpoint path",
    ["endpoint"],
)
ENDPOINT_CACHE_MISSES = Counter(
    "endpoint_cache_misses_total",
    "Cache misses keyed by endpoint path",
    ["endpoint"],
)

# ---------------------------------------------------------------------------
# Pre-register known label combinations so they appear in /metrics as zero-
# series from the first scrape, rather than only after the first occurrence.
# Without this, labelled counters are invisible until incremented — which
# makes dashboards and alerts that fire on "rate == 0" unreliable at startup.
# ---------------------------------------------------------------------------
_KNOWN_INVALIDATION_REASONS = (
    "post_save_created",
    "post_save_updated",
    "post_delete",
    "manual",
    "mutation_triggered",
    "pattern_delete",
    "clear_all_utility",
    "manual_clear_all",
    "unknown_signal",
)


def _pre_register_invalidation_labels(prefixes: tuple[str, ...]) -> None:
    """Touch each (prefix, reason) label combo so Prometheus knows they exist."""
    for prefix in prefixes:
        for reason in _KNOWN_INVALIDATION_REASONS:
            CACHE_INVALIDATIONS.labels(prefix, reason)


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

    # ------------------------------------------------------------------ #
    # RandomInsultEndpoint helpers                                         #
    # ------------------------------------------------------------------ #

    @contextmanager
    def time_random_insult_stage(self, stage: str):
        """Time one named phase inside RandomInsultEndpoint."""
        with RANDOM_INSULT_STAGE_SECONDS.labels(stage).time():
            yield

    @contextmanager
    def sql_instrumentation(self):
        """
        Request-scoped SQL counter/timer.

        Wraps Django's execute_wrapper so every SQL statement issued inside
        the block is counted and timed regardless of DEBUG setting.

        Yields a mutable dict::

            {
                "query_count": int,
                "total_ms":    float,
                "slowest_ms":  float,
            }
        """
        from django.db import connection  # local import avoids circular at module load

        stats: dict = {"query_count": 0, "total_ms": 0.0, "slowest_ms": 0.0}

        def _wrapper(execute, sql, params, many, context):
            t0 = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                dur_ms = (time.perf_counter() - t0) * 1000.0
                stats["query_count"] += 1
                stats["total_ms"] += dur_ms
                if dur_ms > stats["slowest_ms"]:
                    stats["slowest_ms"] = dur_ms

        with connection.execute_wrapper(_wrapper):
            yield stats

    def record_random_insult_request(
        self,
        *,
        status: str,
        category_filtered: bool,
        nsfw_filtered: bool,
        db_query_count: int,
    ) -> None:
        """Increment request counter and SQL query accumulator."""
        RANDOM_INSULT_REQUESTS.labels(
            status=status,
            category_filtered=str(category_filtered).lower(),
            nsfw_filtered=str(nsfw_filtered).lower(),
        ).inc()
        RANDOM_INSULT_DB_QUERIES.inc(db_query_count)

    def record_random_insult_empty(self) -> None:
        RANDOM_INSULT_QUERYSET_EMPTY.inc()

    def increment_endpoint_cache(self, endpoint: str, event: str) -> None:
        """
        Record a cache hit or miss for a specific endpoint path.

        ``event`` must be ``"hit"`` or ``"miss"``.
        """
        if event == "hit":
            ENDPOINT_CACHE_HITS.labels(endpoint).inc()
        elif event == "miss":
            ENDPOINT_CACHE_MISSES.labels(endpoint).inc()
        else:
            raise ValueError(f"Unknown cache event '{event}'. Expected hit|miss.")


metrics = _MetricsFacade()
