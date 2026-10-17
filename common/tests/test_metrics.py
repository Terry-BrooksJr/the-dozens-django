"""
Tests for common.metrics._MetricsFacade (exposed as the module-level `metrics` singleton).

Covers:
- increment_cache: hit / miss / invalidated (with and without reason) / unknown event raises
- time_cache_operation: context manager records histogram and exits cleanly
- time_cache_operation: exception propagates and re-raises
- time_database_query: success path labels status="success"
- time_database_query: exception path labels status="error" and re-raises
- record_database_query_time: valid statuses accepted; invalid normalised to "success"
- time_random_insult_stage: context manager exits cleanly
- sql_instrumentation: counts queries and tracks timing
- record_random_insult_request: increments RANDOM_INSULT_REQUESTS counter
- record_random_insult_empty: increments RANDOM_INSULT_QUERYSET_EMPTY counter
"""

from __future__ import annotations

from django.test import TestCase

from common.metrics import metrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _counter_value(counter, *label_values):
    """Read the current value of a labelled prometheus Counter."""
    return counter.labels(*label_values)._value.get()


def _histogram_count(histogram, *label_values):
    """Read the observation count of a labelled prometheus Histogram."""
    return histogram.labels(*label_values)._sum.get()


# ---------------------------------------------------------------------------
# increment_cache
# ---------------------------------------------------------------------------


class IncrementCacheTests(TestCase):
    def test_hit_increments_cache_hits_counter(self):
        from common.metrics import CACHE_HITS

        before = _counter_value(CACHE_HITS, "test_prefix_hit", "shared")
        metrics.increment_cache("test_prefix_hit", "hit")
        self.assertEqual(
            _counter_value(CACHE_HITS, "test_prefix_hit", "shared"), before + 1
        )

    def test_miss_increments_cache_misses_counter(self):
        from common.metrics import CACHE_MISSES

        before = _counter_value(CACHE_MISSES, "test_prefix_miss")
        metrics.increment_cache("test_prefix_miss", "miss")
        self.assertEqual(_counter_value(CACHE_MISSES, "test_prefix_miss"), before + 1)

    def test_invalidated_increments_invalidations_counter(self):
        from common.metrics import CACHE_INVALIDATIONS

        before = _counter_value(CACHE_INVALIDATIONS, "test_prefix_inv", "signal")
        metrics.increment_cache("test_prefix_inv", "invalidated", reason="signal")
        self.assertEqual(
            _counter_value(CACHE_INVALIDATIONS, "test_prefix_inv", "signal"),
            before + 1,
        )

    def test_invalidated_without_reason_uses_unspecified(self):
        from common.metrics import CACHE_INVALIDATIONS

        before = _counter_value(
            CACHE_INVALIDATIONS, "test_prefix_noreason", "unspecified"
        )
        metrics.increment_cache("test_prefix_noreason", "invalidated")
        self.assertEqual(
            _counter_value(CACHE_INVALIDATIONS, "test_prefix_noreason", "unspecified"),
            before + 1,
        )

    def test_invalidated_empty_reason_uses_unspecified(self):
        from common.metrics import CACHE_INVALIDATIONS

        before = _counter_value(
            CACHE_INVALIDATIONS, "test_prefix_empty_r", "unspecified"
        )
        metrics.increment_cache("test_prefix_empty_r", "invalidated", reason="   ")
        self.assertEqual(
            _counter_value(CACHE_INVALIDATIONS, "test_prefix_empty_r", "unspecified"),
            before + 1,
        )

    def test_unknown_event_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            metrics.increment_cache("any", "bogus_event")
        self.assertIn("bogus_event", str(ctx.exception))
        self.assertIn("hit|miss|invalidated", str(ctx.exception))


# ---------------------------------------------------------------------------
# time_cache_operation
# ---------------------------------------------------------------------------


class TimeCacheOperationTests(TestCase):
    def test_context_manager_exits_without_exception(self):
        """Should not raise and should record an observation."""
        from common.metrics import CACHE_OP_SECONDS

        before = CACHE_OP_SECONDS.labels("op_prefix", "read")._sum.get()
        with metrics.time_cache_operation("op_prefix", "read"):
            pass  # simulate fast operation
        # At least one observation was added
        self.assertGreaterEqual(
            CACHE_OP_SECONDS.labels("op_prefix", "read")._sum.get(), before
        )

    def test_exception_propagates(self):
        """Exceptions inside the block must not be swallowed."""
        with (
            self.assertRaises(RuntimeError),
            metrics.time_cache_operation("op_prefix", "write"),
        ):
            raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# time_database_query
# ---------------------------------------------------------------------------


class TimeDatabaseQueryTests(TestCase):
    def test_success_path_records_observation(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("db_prefix", "success")._sum.get()
        with metrics.time_database_query("db_prefix"):
            pass
        self.assertGreaterEqual(
            DB_QUERY_SECONDS.labels("db_prefix", "success")._sum.get(), before
        )

    def test_exception_path_labels_error_and_reraises(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("db_prefix_err", "error")._sum.get()
        with (
            self.assertRaises(ValueError),
            metrics.time_database_query("db_prefix_err"),
        ):
            raise ValueError("db exploded")
        self.assertGreaterEqual(
            DB_QUERY_SECONDS.labels("db_prefix_err", "error")._sum.get(), before
        )


# ---------------------------------------------------------------------------
# record_database_query_time
# ---------------------------------------------------------------------------


class RecordDatabaseQueryTimeTests(TestCase):
    def test_success_status_records_observation(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("manual_prefix", "success")._sum.get()
        metrics.record_database_query_time("manual_prefix", 0.042, "success")
        after = DB_QUERY_SECONDS.labels("manual_prefix", "success")._sum.get()
        self.assertAlmostEqual(after - before, 0.042, places=5)

    def test_error_status_records_observation(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("manual_prefix_e", "error")._sum.get()
        metrics.record_database_query_time("manual_prefix_e", 0.1, "error")
        after = DB_QUERY_SECONDS.labels("manual_prefix_e", "error")._sum.get()
        self.assertAlmostEqual(after - before, 0.1, places=5)

    def test_invalid_status_normalised_to_success(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("manual_prefix_bad", "success")._sum.get()
        metrics.record_database_query_time("manual_prefix_bad", 0.01, "unknown_status")
        after = DB_QUERY_SECONDS.labels("manual_prefix_bad", "success")._sum.get()
        self.assertAlmostEqual(after - before, 0.01, places=5)

    def test_none_status_normalised_to_success(self):
        from common.metrics import DB_QUERY_SECONDS

        before = DB_QUERY_SECONDS.labels("manual_prefix_none", "success")._sum.get()
        metrics.record_database_query_time("manual_prefix_none", 0.005, None)
        after = DB_QUERY_SECONDS.labels("manual_prefix_none", "success")._sum.get()
        self.assertAlmostEqual(after - before, 0.005, places=5)


# ---------------------------------------------------------------------------
# time_random_insult_stage
# ---------------------------------------------------------------------------


class TimeRandomInsultStageTests(TestCase):
    def test_context_manager_exits_cleanly(self):
        from common.metrics import RANDOM_INSULT_STAGE_SECONDS

        before = RANDOM_INSULT_STAGE_SECONDS.labels("queryset_build")._sum.get()
        with metrics.time_random_insult_stage("queryset_build"):
            pass
        self.assertGreaterEqual(
            RANDOM_INSULT_STAGE_SECONDS.labels("queryset_build")._sum.get(), before
        )

    def test_exception_propagates(self):
        with (
            self.assertRaises(KeyError),
            metrics.time_random_insult_stage("serialization"),
        ):
            raise KeyError("missing")


# ---------------------------------------------------------------------------
# sql_instrumentation
# ---------------------------------------------------------------------------


class SqlInstrumentationTests(TestCase):
    databases = ["default"]

    def test_counts_queries_executed_inside_block(self):
        """Each SQL statement issued inside the block increments query_count."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with metrics.sql_instrumentation() as stats:
            list(User.objects.all())  # forces at least one SQL hit

        self.assertGreaterEqual(stats["query_count"], 1)

    def test_total_ms_is_positive_after_query(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with metrics.sql_instrumentation() as stats:
            list(User.objects.all())

        self.assertGreater(stats["total_ms"], 0)

    def test_slowest_ms_gte_zero_with_no_queries(self):
        """Block with no SQL → all stats remain at zero."""
        with metrics.sql_instrumentation() as stats:
            pass

        self.assertEqual(stats["query_count"], 0)
        self.assertEqual(stats["total_ms"], 0.0)
        self.assertEqual(stats["slowest_ms"], 0.0)

    def test_slowest_ms_tracks_max(self):
        """slowest_ms should reflect the maximum single-query duration."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with metrics.sql_instrumentation() as stats:
            list(User.objects.all())
            list(User.objects.all())

        self.assertGreaterEqual(stats["slowest_ms"], 0)
        self.assertLessEqual(stats["slowest_ms"], stats["total_ms"])


# ---------------------------------------------------------------------------
# record_random_insult_request / record_random_insult_empty
# ---------------------------------------------------------------------------


class RecordRandomInsultRequestTests(TestCase):
    def test_increments_request_counter(self):
        from common.metrics import RANDOM_INSULT_REQUESTS

        before = _counter_value(RANDOM_INSULT_REQUESTS, "200", "false", "false")
        metrics.record_random_insult_request(
            status="200",
            category_filtered=False,
            nsfw_filtered=False,
            db_query_count=3,
        )
        self.assertEqual(
            _counter_value(RANDOM_INSULT_REQUESTS, "200", "false", "false"),
            before + 1,
        )

    def test_increments_db_queries_counter_by_count(self):
        from common.metrics import RANDOM_INSULT_DB_QUERIES

        before = RANDOM_INSULT_DB_QUERIES._value.get()
        metrics.record_random_insult_request(
            status="200",
            category_filtered=True,
            nsfw_filtered=True,
            db_query_count=5,
        )
        self.assertEqual(RANDOM_INSULT_DB_QUERIES._value.get(), before + 5)

    def test_record_random_insult_empty_increments_counter(self):
        from common.metrics import RANDOM_INSULT_QUERYSET_EMPTY

        before = RANDOM_INSULT_QUERYSET_EMPTY._value.get()
        metrics.record_random_insult_empty()
        self.assertEqual(RANDOM_INSULT_QUERYSET_EMPTY._value.get(), before + 1)


# ---------------------------------------------------------------------------
# Naming, cache tiers, LaunchDarkly forwarding, new recorders
# ---------------------------------------------------------------------------


class MetricNamingTests(TestCase):
    def test_every_metric_uses_the_service_namespace(self):
        from common.metrics import _EXPORTED_NAMES

        self.assertTrue(_EXPORTED_NAMES)
        for name in _EXPORTED_NAMES.values():
            self.assertTrue(name.startswith("dozens_api_"), name)


class CacheTierTests(TestCase):
    def test_hits_are_counted_per_tier(self):
        from common.metrics import CACHE_HITS

        local = _counter_value(CACHE_HITS, "tier_prefix", "local")
        shared = _counter_value(CACHE_HITS, "tier_prefix", "shared")
        metrics.increment_cache("tier_prefix", "hit", tier="local")
        self.assertEqual(_counter_value(CACHE_HITS, "tier_prefix", "local"), local + 1)
        self.assertEqual(_counter_value(CACHE_HITS, "tier_prefix", "shared"), shared)

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            metrics.increment_cache("tier_prefix", "hit", tier="disk")


class LaunchDarklyForwardingTests(TestCase):
    """With observability on, each recording also goes to LaunchDarkly."""

    def setUp(self):
        from unittest.mock import MagicMock, patch

        self.observe = MagicMock()
        patches = [
            patch("common.metrics._ld_metrics_enabled", return_value=True),
            patch("common.metrics.observe", self.observe),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_counter_forwarded_with_same_name_and_labels(self):
        metrics.increment_cache("ld_prefix", "hit", tier="local")
        self.observe.record_count.assert_called_once_with(
            "dozens_api_cache_hits_total",
            1,
            attributes={"cache_prefix": "ld_prefix", "tier": "local"},
        )

    def test_endpoint_metrics_are_forwarded_too(self):
        with metrics.time_random_insult_stage("serialization"):
            pass
        name = self.observe.record_histogram.call_args.args[0]
        self.assertEqual(name, "dozens_api_random_insult_stage_seconds")

    def test_failed_db_query_uses_span_context_and_records_error(self):
        with self.assertRaises(RuntimeError), metrics.time_database_query("ld_db"):
            raise RuntimeError("boom")
        # The span is entered and exited as a context manager, so the
        # exception reaches it (it records it and marks the span failed).
        span_cm = self.observe.start_span.return_value
        span_cm.__enter__.assert_called_once()
        exc_type = span_cm.__exit__.call_args.args[0]
        self.assertIs(exc_type, RuntimeError)
        _, kwargs = self.observe.record_histogram.call_args
        self.assertEqual(
            kwargs["attributes"], {"cache_prefix": "ld_db", "status": "error"}
        )


class ApiErrorMetricTests(TestCase):
    def _value(self, view, status, code):
        from common.metrics import API_ERRORS

        return _counter_value(API_ERRORS, view, status, code)

    def test_known_code_is_kept(self):
        before = self._value("V", "401", "not_authenticated")
        metrics.record_api_error(view="V", status=401, code="not_authenticated")
        self.assertEqual(self._value("V", "401", "not_authenticated"), before + 1)

    def test_free_form_codes_are_bucketed_as_other(self):
        before = self._value("V", "400", "other")
        for code in (["list"], "Has Spaces", "x" * 200, None):
            metrics.record_api_error(view="V", status=400, code=code)
        self.assertEqual(self._value("V", "400", "other"), before + 4)


class NewRecorderTests(TestCase):
    def test_graphql_operation(self):
        from common.metrics import GRAPHQL_OPERATIONS, GRAPHQL_ROOT_FIELDS

        ops = _counter_value(GRAPHQL_OPERATIONS, "query", "ok")
        field = _counter_value(GRAPHQL_ROOT_FIELDS, "query", "allInsults")
        metrics.record_graphql_operation(
            operation_type="query",
            outcome="ok",
            duration=0.01,
            root_fields=["allInsults"],
        )
        self.assertEqual(_counter_value(GRAPHQL_OPERATIONS, "query", "ok"), ops + 1)
        self.assertEqual(
            _counter_value(GRAPHQL_ROOT_FIELDS, "query", "allInsults"), field + 1
        )

    def test_email_delivery(self):
        from common.metrics import EMAILS

        sent = _counter_value(EMAILS, "sent")
        unsent = _counter_value(EMAILS, "unsent")
        metrics.record_email_delivery(sent=2, unsent=1, duration=0.2)
        self.assertEqual(_counter_value(EMAILS, "sent"), sent + 2)
        self.assertEqual(_counter_value(EMAILS, "unsent"), unsent + 1)

    def test_launchdarkly_init_labels_are_strings(self):
        from common.metrics import LAUNCHDARKLY_INITS

        before = _counter_value(LAUNCHDARKLY_INITS, "false", "Missing key")
        metrics.record_launchdarkly_init(configured=False, reason="Missing key")
        self.assertEqual(
            _counter_value(LAUNCHDARKLY_INITS, "false", "Missing key"), before + 1
        )

    def test_worker_timeout(self):
        from common.metrics import GUNICORN_WORKER_TIMEOUTS

        before = GUNICORN_WORKER_TIMEOUTS._value.get()
        metrics.record_worker_timeout()
        self.assertEqual(GUNICORN_WORKER_TIMEOUTS._value.get(), before + 1)
