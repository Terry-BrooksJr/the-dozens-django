"""
Tests for applications.ld_integration.flags (bool_flag / json_flag).

Covers:
- LAUNCHDARKLY_ENABLED=False -> both helpers short-circuit to the given default
  without building a context or touching the client
- No request supplied -> falls back to default without touching the client
- Enabled + request supplied -> builds a context via context_from_request and
  delegates evaluation to get_client().variation(flag_key, ctx, default)
- bool_flag coerces the SDK's return value to a bool
- json_flag returns the SDK's raw return value untouched
- LAUNCHDARKLY_ENABLED unset in settings defaults to enabled (True)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings

from applications.ld_integration import flags


class BoolFlagTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_disabled_returns_default_without_touching_client(self):
        with (
            patch.object(flags, "get_client") as mock_get_client,
            patch.object(flags, "context_from_request") as mock_ctx,
        ):
            result = flags.bool_flag("my-flag", self.factory.get("/"), default=True)

        self.assertTrue(result)
        mock_get_client.assert_not_called()
        mock_ctx.assert_not_called()

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_no_request_returns_default(self):
        with patch.object(flags, "get_client") as mock_get_client:
            result = flags.bool_flag("my-flag", None, default=True)

        self.assertTrue(result)
        mock_get_client.assert_not_called()

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_enabled_with_request_delegates_to_client_variation(self):
        request = self.factory.get("/")
        fake_ctx = object()
        mock_client = MagicMock()
        mock_client.variation.return_value = True

        with (
            patch.object(
                flags, "context_from_request", return_value=fake_ctx
            ) as mock_ctx,
            patch.object(flags, "get_client", return_value=mock_client),
        ):
            result = flags.bool_flag("my-flag", request, default=False)

        mock_ctx.assert_called_once_with(request)
        mock_client.variation.assert_called_once_with("my-flag", fake_ctx, False)
        self.assertTrue(result)

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_coerces_truthy_variation_result_to_bool(self):
        request = self.factory.get("/")
        mock_client = MagicMock()
        mock_client.variation.return_value = "truthy-non-bool"

        with (
            patch.object(flags, "context_from_request", return_value=object()),
            patch.object(flags, "get_client", return_value=mock_client),
        ):
            result = flags.bool_flag("my-flag", request, default=False)

        self.assertIs(result, True)

    def test_launchdarkly_enabled_defaults_true_when_setting_absent(self):
        fake_settings = SimpleNamespace()  # deliberately has no LAUNCHDARKLY_ENABLED
        with patch.object(flags, "settings", fake_settings):
            self.assertTrue(flags._enabled())


class JsonFlagTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_disabled_returns_default(self):
        result = flags.json_flag("cfg-flag", self.factory.get("/"), default={"a": 1})
        self.assertEqual(result, {"a": 1})

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_no_request_returns_default(self):
        result = flags.json_flag("cfg-flag", None, default=[1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_returns_raw_variation_result_unmodified(self):
        request = self.factory.get("/")
        fake_ctx = object()
        mock_client = MagicMock()
        mock_client.variation.return_value = {"nested": {"value": 42}}

        with (
            patch.object(
                flags, "context_from_request", return_value=fake_ctx
            ) as mock_ctx,
            patch.object(flags, "get_client", return_value=mock_client),
        ):
            result = flags.json_flag("cfg-flag", request, default=None)

        mock_ctx.assert_called_once_with(request)
        mock_client.variation.assert_called_once_with("cfg-flag", fake_ctx, None)
        self.assertEqual(result, {"nested": {"value": 42}})
