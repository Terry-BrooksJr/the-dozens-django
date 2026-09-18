# -*- coding: utf-8 -*-
"""
Tests for common.helpers.

Covers:
- add_token_auth_scheme: mutates/returns the OpenAPI schema dict, never raises
- _normalize_append_components: coerces APPEND_COMPONENTS to a dict
- log_warning: formats warnings.showwarning args and routes them to loguru
- _insert_after_middleware: inserts items after a marker without mutating input
- _force_utc_time: Loguru patcher converts record["time"] to UTC
- _otel_safe_value: recursively sanitizes values for OTel (depth cap, truncation)
- _safe_get_host: never raises, even when request.get_host() does
- ld_loguru_sink: builds OTel attrs from a Loguru record and forwards to ldobserve
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from common.helpers import (
    _force_utc_time,
    _insert_after_middleware,
    _normalize_append_components,
    _otel_safe_value,
    _safe_get_host,
    add_token_auth_scheme,
    ld_loguru_sink,
    log_warning,
)


class AddTokenAuthSchemeTests(TestCase):
    def test_adds_token_auth_scheme_to_empty_result(self):
        result = add_token_auth_scheme({}, generator=None, request=None, public=True)

        scheme = result["components"]["securitySchemes"]["TokenAuth"]
        self.assertEqual(scheme["type"], "apiKey")
        self.assertEqual(scheme["in"], "header")
        self.assertEqual(scheme["name"], "Authorization")

    def test_preserves_existing_components_and_schemes(self):
        result = {
            "components": {
                "securitySchemes": {"Basic": {"type": "http", "scheme": "basic"}}
            }
        }

        add_token_auth_scheme(result, generator=None, request=None, public=True)

        self.assertIn("Basic", result["components"]["securitySchemes"])
        self.assertIn("TokenAuth", result["components"]["securitySchemes"])

    def test_mutates_and_returns_same_object(self):
        result = {}

        returned = add_token_auth_scheme(
            result, generator=None, request=None, public=True
        )

        self.assertIs(returned, result)

    def test_idempotent_on_repeated_calls(self):
        result = {}
        add_token_auth_scheme(result, generator=None, request=None, public=True)
        first = result["components"]["securitySchemes"]["TokenAuth"]

        add_token_auth_scheme(result, generator=None, request=None, public=True)
        second = result["components"]["securitySchemes"]["TokenAuth"]

        self.assertEqual(first, second)

    def test_non_dict_input_is_returned_unchanged_without_raising(self):
        # None has no .setdefault(); the function must swallow the error and
        # still return the original value rather than raising.
        result = add_token_auth_scheme(None, generator=None, request=None, public=True)

        self.assertIsNone(result)

    def test_non_mutable_input_type_is_returned_unchanged(self):
        result = add_token_auth_scheme(
            "not-a-dict", generator=None, request=None, public=False
        )

        self.assertEqual(result, "not-a-dict")


class NormalizeAppendComponentsTests(TestCase):
    def test_none_becomes_empty_dict(self):
        settings_dict = {"APPEND_COMPONENTS": None}

        result = _normalize_append_components(settings_dict)

        self.assertEqual(result["APPEND_COMPONENTS"], {})

    def test_missing_key_becomes_empty_dict(self):
        settings_dict = {}

        result = _normalize_append_components(settings_dict)

        self.assertEqual(result["APPEND_COMPONENTS"], {})

    def test_valid_json_object_string_is_parsed(self):
        settings_dict = {"APPEND_COMPONENTS": json.dumps({"foo": "bar"})}

        result = _normalize_append_components(settings_dict)

        self.assertEqual(result["APPEND_COMPONENTS"], {"foo": "bar"})

    def test_valid_json_non_object_values_become_empty_dict(self):
        for value in ([1, 2, 3], "not a dictionary", 123, True, None):
            with self.subTest(value=value):
                settings_dict = {"APPEND_COMPONENTS": json.dumps(value)}

                result = _normalize_append_components(settings_dict)

                self.assertEqual(result["APPEND_COMPONENTS"], {})

    def test_invalid_json_string_becomes_empty_dict(self):
        settings_dict = {"APPEND_COMPONENTS": "{not valid json"}

        result = _normalize_append_components(settings_dict)

        self.assertEqual(result["APPEND_COMPONENTS"], {})

    def test_invalid_non_string_value_becomes_empty_dict(self):
        settings_dict = {"APPEND_COMPONENTS": 123}

        result = _normalize_append_components(settings_dict)

        self.assertEqual(result["APPEND_COMPONENTS"], {})

    def test_existing_dict_value_is_left_untouched(self):
        original = {"already": "a-dict"}
        settings_dict = {"APPEND_COMPONENTS": original}

        result = _normalize_append_components(settings_dict)

        self.assertIs(result["APPEND_COMPONENTS"], original)

    def test_returns_same_dict_object(self):
        settings_dict = {"APPEND_COMPONENTS": None}

        result = _normalize_append_components(settings_dict)

        self.assertIs(result, settings_dict)


class LogWarningTests(TestCase):
    def test_formats_and_logs_minimal_warning(self):
        with patch("common.helpers.logger") as mock_logger:
            log_warning("deprecated thing", DeprecationWarning, "mymodule.py", 42)

        mock_logger.warning.assert_called_once_with(
            "mymodule.py:42 - DeprecationWarning: deprecated thing"
        )

    def test_includes_file_name_when_provided(self):
        fake_file = SimpleNamespace(name="/var/log/warnings.log")

        with patch("common.helpers.logger") as mock_logger:
            log_warning("watch out", UserWarning, "mymodule.py", 10, file=fake_file)

        message = mock_logger.warning.call_args[0][0]
        self.assertIn("[/var/log/warnings.log]", message)

    def test_includes_stripped_source_line_when_provided(self):
        with patch("common.helpers.logger") as mock_logger:
            log_warning(
                "watch out",
                UserWarning,
                "mymodule.py",
                10,
                line="  x = 1  \n",
            )

        message = mock_logger.warning.call_args[0][0]
        self.assertIn("| x = 1", message)

    def test_omits_file_and_line_segments_when_absent(self):
        with patch("common.helpers.logger") as mock_logger:
            log_warning("plain", UserWarning, "mymodule.py", 1)

        message = mock_logger.warning.call_args[0][0]
        self.assertNotIn("[", message)
        self.assertNotIn("|", message)


class InsertAfterMiddlewareTests(TestCase):
    def test_inserts_single_item_after_marker(self):
        base = ["a", "b", "c"]

        result = _insert_after_middleware(base, "b", "x")

        self.assertEqual(result, ["a", "b", "x", "c"])

    def test_inserts_multiple_items_in_order(self):
        base = ["a", "b", "c"]

        result = _insert_after_middleware(base, "a", "x", "y", "z")

        self.assertEqual(result, ["a", "x", "y", "z", "b", "c"])

    def test_inserts_after_last_item(self):
        base = ["a", "b", "c"]

        result = _insert_after_middleware(base, "c", "x")

        self.assertEqual(result, ["a", "b", "c", "x"])

    def test_does_not_mutate_original_list(self):
        base = ["a", "b", "c"]

        _insert_after_middleware(base, "b", "x")

        self.assertEqual(base, ["a", "b", "c"])

    def test_missing_marker_raises_value_error(self):
        base = ["a", "b", "c"]

        with self.assertRaises(ValueError) as ctx:
            _insert_after_middleware(base, "missing", "x")

        self.assertIn("missing", str(ctx.exception))

    def test_no_new_items_returns_equivalent_copy(self):
        base = ["a", "b", "c"]

        result = _insert_after_middleware(base, "b")

        self.assertEqual(result, base)
        self.assertIsNot(result, base)


class ForceUtcTimeTests(TestCase):
    def test_converts_aware_non_utc_time_to_utc(self):
        chicago = timezone(timedelta(hours=-5))
        local_time = datetime(2026, 9, 17, 16, 21, 27, tzinfo=chicago)
        record = {"time": local_time}

        _force_utc_time(record)

        self.assertEqual(record["time"].tzinfo, timezone.utc)
        self.assertEqual(record["time"], local_time)  # same instant
        self.assertEqual(record["time"].hour, 21)

    def test_already_utc_time_is_unchanged_in_value(self):
        utc_time = datetime(2026, 9, 17, 21, 21, 27, tzinfo=timezone.utc)
        record = {"time": utc_time}

        _force_utc_time(record)

        self.assertEqual(record["time"], utc_time)
        self.assertEqual(record["time"].tzinfo, timezone.utc)


class OtelSafeValueTests(TestCase):
    def test_primitives_are_returned_unchanged(self):
        for value in (None, True, False, 1, 1.5, "text", b"bytes"):
            with self.subTest(value=value):
                self.assertEqual(_otel_safe_value(value), value)

    def test_list_is_recursively_sanitized(self):
        result = _otel_safe_value([1, "two", 3.0])

        self.assertEqual(result, [1, "two", 3.0])

    def test_tuple_and_set_are_converted_to_list(self):
        self.assertEqual(_otel_safe_value((1, 2)), [1, 2])
        self.assertEqual(sorted(_otel_safe_value({1, 2})), [1, 2])

    def test_dict_keys_are_stringified(self):
        result = _otel_safe_value({1: "one", "two": 2})

        self.assertEqual(result, {"1": "one", "two": 2})

    def test_list_longer_than_50_is_truncated(self):
        result = _otel_safe_value(list(range(60)))

        self.assertEqual(len(result), 50)
        self.assertEqual(result, list(range(50)))

    def test_dict_longer_than_50_is_truncated(self):
        big = {str(i): i for i in range(60)}

        result = _otel_safe_value(big)

        self.assertEqual(len(result), 50)

    def test_unknown_object_is_stringified(self):
        class Thing:
            def __str__(self):
                return "a-thing"

        self.assertEqual(_otel_safe_value(Thing()), "a-thing")

    def test_deep_nesting_is_stringified_past_depth_limit(self):
        # depth 0 -> [depth1 -> [depth2 -> [depth3, stringified here]]]
        nested = [[[[1, 2, 3]]]]

        result = _otel_safe_value(nested)

        self.assertEqual(result, [[["[1, 2, 3]"]]])


class SafeGetHostTests(TestCase):
    def test_returns_host_on_success(self):
        req = SimpleNamespace(get_host=lambda: "example.com")

        self.assertEqual(_safe_get_host(req), "example.com")

    def test_returns_none_when_get_host_raises(self):
        def boom():
            raise Exception("DisallowedHost-like failure")

        req = SimpleNamespace(get_host=boom)

        self.assertIsNone(_safe_get_host(req))

    def test_returns_none_when_get_host_missing(self):
        req = SimpleNamespace()

        self.assertIsNone(_safe_get_host(req))

    def test_returns_none_for_none_request(self):
        self.assertIsNone(_safe_get_host(None))


def _make_record(**overrides):
    record = {
        "level": SimpleNamespace(name="INFO"),
        "name": "myapp.module",
        "file": SimpleNamespace(path="/src/myapp/module.py"),
        "function": "do_thing",
        "line": 123,
        "extra": {},
        "exception": None,
        "message": "hello world",
    }
    record.update(overrides)
    return SimpleNamespace(record=record)


class LdLoguruSinkTests(TestCase):
    def test_noop_when_observe_unavailable(self):
        message = _make_record()

        with patch("common.helpers.observe", None):
            ld_loguru_sink(message)  # must not raise

    def test_forwards_basic_attrs_to_observe(self):
        message = _make_record()

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)

        mock_observe.record_log.assert_called_once()
        text, level_no = mock_observe.record_log.call_args[0]
        attrs = mock_observe.record_log.call_args[1]["attributes"]

        self.assertEqual(text, "hello world")
        self.assertEqual(level_no, 20)  # INFO
        self.assertEqual(attrs["logger.name"], "myapp.module")
        self.assertEqual(attrs["code.filepath"], "/src/myapp/module.py")
        self.assertEqual(attrs["code.function"], "do_thing")
        self.assertEqual(attrs["code.lineno"], 123)

    def test_missing_file_yields_no_filepath_attr(self):
        message = _make_record(file=None)

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)

        attrs = mock_observe.record_log.call_args[1]["attributes"]
        self.assertNotIn("code.filepath", attrs)

    def test_level_name_mapping(self):
        cases = {
            "TRACE": 5,
            "DEBUG": 10,
            "INFO": 20,
            "SUCCESS": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
            "SOMETHING_UNKNOWN": 20,
        }
        for level_name, expected in cases.items():
            with self.subTest(level_name=level_name):
                message = _make_record(level=SimpleNamespace(name=level_name))
                with patch("common.helpers.observe") as mock_observe:
                    ld_loguru_sink(message)
                level_no = mock_observe.record_log.call_args[0][1]
                self.assertEqual(level_no, expected)

    def test_request_extra_is_flattened_into_http_attrs(self):
        req = SimpleNamespace(
            path="/api/insults/",
            method="POST",
            get_host=lambda: "yo-momma.io",
        )
        message = _make_record(extra={"request": req, "custom": "value"})

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)

        attrs = mock_observe.record_log.call_args[1]["attributes"]
        self.assertEqual(attrs["http.target"], "/api/insults/")
        self.assertEqual(attrs["http.method"], "POST")
        self.assertEqual(attrs["http.host"], "yo-momma.io")
        self.assertEqual(attrs["custom"], "value")

    def test_request_with_failing_get_host_does_not_raise_and_omits_host(self):
        def boom():
            raise Exception("bad host header")

        req = SimpleNamespace(path="/x", method="GET", get_host=boom)
        message = _make_record(extra={"request": req})

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)  # must not raise

        attrs = mock_observe.record_log.call_args[1]["attributes"]
        self.assertNotIn("http.host", attrs)

    def test_exception_info_is_attached(self):
        exc = SimpleNamespace(type=ValueError, value=ValueError("bad"), traceback=None)
        message = _make_record(exception=exc)

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)

        attrs = mock_observe.record_log.call_args[1]["attributes"]
        self.assertIn("exception.type", attrs)
        self.assertIn("exception.value", attrs)

    def test_null_attrs_are_stripped(self):
        message = _make_record(file=None)

        with patch("common.helpers.observe") as mock_observe:
            ld_loguru_sink(message)

        attrs = mock_observe.record_log.call_args[1]["attributes"]
        self.assertTrue(all(v is not None for v in attrs.values()))
