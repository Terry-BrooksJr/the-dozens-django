"""Application metrics, exported to Prometheus and LaunchDarkly Observability.

Every metric defined here:

- is named ``dozens_api_<name>`` (the same namespace django_prometheus uses
  via ``PROMETHEUS_METRIC_NAMESPACE``), so all of the service's series share
  one prefix;
- is recorded through the ``metrics`` facade at the bottom of this module,
  whose helpers write to Prometheus and, when LaunchDarkly Observability is
  enabled, send the same name and labels there too.

Label values must come from small, fixed sets (status codes, enum names,
class names). Never use raw request input as a label value.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager, suppress
from functools import lru_cache

from prometheus_client import Counter, Histogram

try:
    from ldobserve import observe
except Exception:  # LaunchDarkly observability plugin is optional
    observe = None

NAMESPACE = "dozens_api"


@lru_cache(maxsize=1)
def _ld_metrics_enabled() -> bool:
    """
    App-level kill switch for LaunchDarkly observability.

    Note: ldobserve is designed to no-op safely when not initialized,
    but this avoids extra work in hot paths when disabled.
    """
    # Same truthy set as settings.LAUNCHDARKLY_OBSERVABILITY_ENABLED, so the
    # plugin and these metrics can't disagree about whether it's on.
    return (
        os.getenv("LAUNCHDARKLY_OBSERVABILITY_ENABLED", "").strip().lower()
        in ("1", "true", "yes", "on")
        and observe is not None
    )


def _as_cache_reason(reason: str | None) -> str:
    """Normalize an invalidation reason, defaulting to ``"unspecified"``."""
    return (reason or "unspecified").strip() or "unspecified"


# ---------------------------------------------------------------------------
# Metric construction and recording helpers
# ---------------------------------------------------------------------------
# Full exported name of each metric, keyed by id(): what LaunchDarkly
# receives, so both backends show the same name.
_EXPORTED_NAMES: dict[int, str] = {}

_FAST_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


def _counter(name: str, documentation: str, labelnames: Iterable[str] = ()):
    """Create a namespaced Counter; ``name`` must end in ``_total``."""
    metric = Counter(name, documentation, list(labelnames), namespace=NAMESPACE)
    _EXPORTED_NAMES[id(metric)] = f"{NAMESPACE}_{name}"
    return metric


def _histogram(
    name: str,
    documentation: str,
    labelnames: Iterable[str] = (),
    buckets: Iterable[float] = Histogram.DEFAULT_BUCKETS,
):
    """Create a namespaced Histogram."""
    metric = Histogram(
        name,
        documentation,
        list(labelnames),
        namespace=NAMESPACE,
        buckets=tuple(buckets),
    )
    _EXPORTED_NAMES[id(metric)] = f"{NAMESPACE}_{name}"
    return metric


def _labelled(metric, labels: Mapping[str, str]):
    """The child series for ``labels``, or the metric itself when unlabelled."""
    return metric.labels(**labels) if labels else metric


def _count(counter, amount: int = 1, **labels: str) -> None:
    """Increment ``counter`` in Prometheus and LaunchDarkly."""
    _labelled(counter, labels).inc(amount)
    if _ld_metrics_enabled():
        observe.record_count(
            _EXPORTED_NAMES[id(counter)], int(amount), attributes=labels or None
        )


def _observe(histogram, value: float, **labels: str) -> None:
    """Record one ``histogram`` observation in Prometheus and LaunchDarkly."""
    _labelled(histogram, labels).observe(value)
    if _ld_metrics_enabled():
        observe.record_histogram(
            _EXPORTED_NAMES[id(histogram)], value, attributes=labels or None
        )


@contextmanager
def _span(name: str, attributes: Mapping[str, str]) -> Iterator[None]:
    """A LaunchDarkly trace span around the block, when observability is on.

    ``observe.start_span`` records an escaping exception on the span and
    marks it failed, so callers don't need to.
    """
    if _ld_metrics_enabled():
        with observe.start_span(name, attributes=dict(attributes)):
            yield
    else:
        yield


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# tier: "local" = this process's in-memory dict (cache managers' first level),
#       "shared" = the Django cache backend (Redis in production).
CACHE_TIERS = ("local", "shared")

CACHE_HITS = _counter("cache_hits_total", "Cache hits", ["cache_prefix", "tier"])
CACHE_MISSES = _counter(
    "cache_misses_total",
    "Cache misses (a miss means every tier missed)",
    ["cache_prefix"],
)
CACHE_INVALIDATIONS = _counter(
    "cache_invalidations_total",
    "Cache invalidations",
    ["cache_prefix", "reason"],
)
CACHE_OP_SECONDS = _histogram(
    "cache_operation_seconds",
    "Duration of cache operations",
    ["cache_prefix", "operation"],
)
DB_QUERY_SECONDS = _histogram(
    "cache_db_query_seconds",
    "DB time while rebuilding cache",
    ["cache_prefix", "status"],  # status: success|error
)

# ---------------------------------------------------------------------------
# RandomInsultEndpoint
# ---------------------------------------------------------------------------
RANDOM_INSULT_REQUESTS = _counter(
    "random_insult_requests_total",
    "Requests to /api/insults/random/, by final HTTP status",
    ["status", "category_filtered", "nsfw_filtered"],
)
RANDOM_INSULT_STAGE_SECONDS = _histogram(
    "random_insult_stage_seconds",
    "Duration of each processing stage inside RandomInsultEndpoint",
    ["stage"],
    buckets=_FAST_BUCKETS,
)
RANDOM_INSULT_QUERYSET_EMPTY = _counter(
    "random_insult_queryset_empty_total",
    "Times the random insult queryset returned no rows after filtering",
)
RANDOM_INSULT_DB_QUERIES = _counter(
    "random_insult_db_queries_total",
    "SQL queries executed by random insult requests (summed across requests)",
)

# ---------------------------------------------------------------------------
# API errors (DRF exception handler)
# ---------------------------------------------------------------------------
_ERROR_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
API_ERRORS = _counter(
    "api_errors_total",
    "Error responses produced by the REST API exception handler",
    ["view", "status", "code"],
)

# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------
GRAPHQL_OPERATIONS = _counter(
    "graphql_operations_total",
    "GraphQL operations, by type and outcome (ok|error|rejected)",
    ["operation_type", "outcome"],
)
GRAPHQL_OPERATION_SECONDS = _histogram(
    "graphql_operation_seconds",
    "GraphQL operation execution time",
    ["operation_type"],
)
GRAPHQL_ROOT_FIELDS = _counter(
    "graphql_root_fields_total",
    "Root fields requested by GraphQL operations (schema fields only)",
    ["operation_type", "field"],
)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAILS = _counter(
    "emails_total",
    "Outgoing emails, by delivery result (sent|unsent; unsent stay queued)",
    ["result"],
)
EMAIL_SEND_SECONDS = _histogram(
    "email_send_seconds", "Time to deliver one batch of emails"
)

# ---------------------------------------------------------------------------
# Joke workflow (business events)
# ---------------------------------------------------------------------------
STATUS_TRANSITIONS = _counter(
    "status_transitions_total",
    "Status changes of insults and reviews (from_status=new on creation)",
    ["model", "from_status", "to_status"],
)
INSULT_REPORTS = _counter(
    "insult_reports_total",
    "Insults reported (flagged) for review, by review type",
    ["review_type"],
)

# ---------------------------------------------------------------------------
# Process / integrations
# ---------------------------------------------------------------------------
LAUNCHDARKLY_INITS = _counter(
    "launchdarkly_init_total",
    "LaunchDarkly client initialization attempts, by outcome",
    ["configured", "reason"],
)
GUNICORN_WORKER_TIMEOUTS = _counter(
    "gunicorn_worker_timeouts_total",
    "Workers killed by gunicorn for exceeding the request timeout",
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


_CACHE_INVALIDATION_STATIC_PREFIXES: tuple[str, ...] = (
    "Insult",
    "InsultCategory",
    "Insult_view",
    "Insult_categories",
)


def init_cache_invalidation_metrics(prefixes: Iterable[str] = ()) -> None:
    """Pre-register cache_invalidations_total label combos at startup.

    ``prefixes`` is supplied by the caller (see ``ApiConfig._init_metrics``)
    rather than read from ``common.cache_managers`` here, since that module
    already imports this one and doing so would create an import cycle.

    Safe to call from AppConfig.ready — failures are suppressed so they
    never block Django startup.
    """
    with suppress(Exception):
        registry_prefixes = set(prefixes)
        registry_prefixes.update(_CACHE_INVALIDATION_STATIC_PREFIXES)
        _pre_register_invalidation_labels(tuple(registry_prefixes))


class _MetricsFacade:
    """Thin facade used throughout the app to record metrics.

    Methods are intentionally minimal and stable so callers aren't tied to
    prometheus_client specifics. Every method records to Prometheus and, when
    enabled, LaunchDarkly Observability.
    """

    # ------------------------------------------------------------------ #
    # Cache                                                                #
    # ------------------------------------------------------------------ #

    def increment_cache(
        self,
        cache_prefix: str,
        event: str,
        reason: str | None = None,
        tier: str = "shared",
    ):
        """
        Record cache events. Supported events:
        - hit (``tier`` says which level answered: local|shared)
        - miss
        - invalidated (requires/uses reason)
        """
        if event == "hit":
            if tier not in CACHE_TIERS:
                raise ValueError(f"Unknown cache tier '{tier}'. Expected local|shared.")
            _count(CACHE_HITS, cache_prefix=cache_prefix, tier=tier)
        elif event == "miss":
            _count(CACHE_MISSES, cache_prefix=cache_prefix)
        elif event == "invalidated":
            _count(
                CACHE_INVALIDATIONS,
                cache_prefix=cache_prefix,
                reason=_as_cache_reason(reason),
            )
        else:
            # Keep callers honest. Silent failures create fake dashboards.
            raise ValueError(
                f"Unknown cache event '{event}'. Expected hit|miss|invalidated."
            )

    @contextmanager
    def time_cache_operation(self, cache_prefix: str, operation: str):
        """Time a cache operation (histogram + LaunchDarkly span)."""
        labels = {"cache_prefix": cache_prefix, "operation": operation}
        start = time.perf_counter()
        try:
            with _span("cache.operation", labels):
                yield
        finally:
            _observe(CACHE_OP_SECONDS, time.perf_counter() - start, **labels)

    @contextmanager
    def time_database_query(self, cache_prefix: str):
        """Time DB work, labelled status=error when an exception escapes."""
        start = time.perf_counter()
        status = "success"
        try:
            with _span("cache.db_query", {"cache_prefix": cache_prefix}):
                yield
        except Exception:
            status = "error"
            raise
        finally:
            _observe(
                DB_QUERY_SECONDS,
                time.perf_counter() - start,
                cache_prefix=cache_prefix,
                status=status,
            )

    def record_database_query_time(
        self, cache_prefix: str, duration: float, status: str = "success"
    ):
        """Manual recording for cases where timing is calculated elsewhere."""
        status_val = (status or "success").strip().lower()
        if status_val not in {"success", "error"}:
            status_val = "success"
        _observe(
            DB_QUERY_SECONDS,
            float(duration),
            cache_prefix=cache_prefix,
            status=status_val,
        )

    # ------------------------------------------------------------------ #
    # RandomInsultEndpoint                                                 #
    # ------------------------------------------------------------------ #

    @contextmanager
    def time_random_insult_stage(self, stage: str):
        """Time one named phase inside RandomInsultEndpoint."""
        start = time.perf_counter()
        try:
            yield
        finally:
            _observe(
                RANDOM_INSULT_STAGE_SECONDS, time.perf_counter() - start, stage=stage
            )

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
            """Time one SQL statement and add it to ``stats``."""
            t0 = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                dur_ms = (time.perf_counter() - t0) * 1000.0
                stats["query_count"] += 1
                stats["total_ms"] += dur_ms
                stats["slowest_ms"] = max(stats["slowest_ms"], dur_ms)

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
        _count(
            RANDOM_INSULT_REQUESTS,
            status=status,
            category_filtered=str(category_filtered).lower(),
            nsfw_filtered=str(nsfw_filtered).lower(),
        )
        if db_query_count:
            _count(RANDOM_INSULT_DB_QUERIES, db_query_count)

    def record_random_insult_empty(self) -> None:
        """Increment the counter for random-insult requests with no matches."""
        _count(RANDOM_INSULT_QUERYSET_EMPTY)

    # ------------------------------------------------------------------ #
    # API errors                                                           #
    # ------------------------------------------------------------------ #

    def record_api_error(self, *, view: str, status: int, code: object) -> None:
        """Count one error response from the REST API exception handler.

        ``code`` can originate in a response body, so anything that isn't a
        short snake_case identifier is recorded as ``other`` to keep the label
        set bounded.
        """
        code_label = (
            code
            if isinstance(code, str) and _ERROR_CODE_RE.fullmatch(code)
            else "other"
        )
        _count(API_ERRORS, view=view, status=str(status), code=code_label)

    # ------------------------------------------------------------------ #
    # GraphQL                                                              #
    # ------------------------------------------------------------------ #

    def record_graphql_operation(
        self,
        *,
        operation_type: str,
        outcome: str,
        duration: float,
        root_fields: Iterable[str] = (),
    ) -> None:
        """Count one GraphQL operation, its execution time and root fields."""
        _count(GRAPHQL_OPERATIONS, operation_type=operation_type, outcome=outcome)
        _observe(GRAPHQL_OPERATION_SECONDS, duration, operation_type=operation_type)
        for field in root_fields:
            _count(GRAPHQL_ROOT_FIELDS, operation_type=operation_type, field=field)

    # ------------------------------------------------------------------ #
    # Email                                                                #
    # ------------------------------------------------------------------ #

    def record_email_delivery(self, *, sent: int, unsent: int, duration: float) -> None:
        """Record the outcome of delivering one batch of emails."""
        if sent:
            _count(EMAILS, sent, result="sent")
        if unsent:
            _count(EMAILS, unsent, result="unsent")
        _observe(EMAIL_SEND_SECONDS, duration)

    # ------------------------------------------------------------------ #
    # Joke workflow                                                        #
    # ------------------------------------------------------------------ #

    def record_status_transition(
        self, *, model: str, from_status: str, to_status: str
    ) -> None:
        """Count a status change (``from_status="new"`` for a new record)."""
        _count(
            STATUS_TRANSITIONS,
            model=model,
            from_status=from_status,
            to_status=to_status,
        )

    def record_insult_report(self, review_type: str) -> None:
        """Count an insult reported for review."""
        _count(INSULT_REPORTS, review_type=review_type)

    # ------------------------------------------------------------------ #
    # Process / integrations                                               #
    # ------------------------------------------------------------------ #

    def record_launchdarkly_init(self, *, configured: bool, reason: str) -> None:
        """Count a LaunchDarkly initialization attempt and its outcome."""
        _count(
            LAUNCHDARKLY_INITS,
            configured=str(bool(configured)).lower(),
            reason=str(reason),
        )

    def record_worker_timeout(self) -> None:
        """Count a gunicorn worker killed for exceeding the request timeout."""
        _count(GUNICORN_WORKER_TIMEOUTS)


metrics = _MetricsFacade()
