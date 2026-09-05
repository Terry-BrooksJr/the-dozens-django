"""
Tests for applications.ld_integration.client.

Covers:
- _should_init_in_this_process: RUN_MAIN=true, RUN_MAIN unset + DJANGO_SETTINGS_MODULE set/unset
- configure_launchdarkly:
    * ldclient not installed -> disabled, not configured
    * enabled=False -> disabled, not configured
    * missing sdk_key -> disabled, not configured
    * not the "app" process (per _should_init_in_this_process) -> disabled, not configured
    * already configured -> short-circuits without re-initializing the SDK
    * success path without observability plugin
    * success path with observability plugin available and obs_enabled=True
    * observability plugin available but obs_enabled=False -> plugin not attached
- get_client: returns None when ldclient isn't installed, otherwise delegates to ld_client.get()
- postfork_reinit: calls postfork() on the client and swallows any exception
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

from django.test import TestCase

from applications.ld_integration import client as ld_client_module


@contextlib.contextmanager
def _unset_env(*names):
    """Temporarily remove specific env vars (rather than wiping os.environ)."""
    sentinel = object()
    originals = {
        name: ld_client_module.os.environ.pop(name, sentinel) for name in names
    }
    try:
        yield
    finally:
        for name, value in originals.items():
            if value is not sentinel:
                ld_client_module.os.environ[name] = value


class ResetConfiguredStateMixin:
    """Ensure the module-level `_configured` singleton flag doesn't leak between tests."""

    def setUp(self):
        super().setUp()
        self._original_configured = ld_client_module._configured
        ld_client_module._configured = False

    def tearDown(self):
        ld_client_module._configured = self._original_configured
        super().tearDown()


class ShouldInitInThisProcessTests(TestCase):
    def test_run_main_true_returns_true(self):
        with patch.dict(ld_client_module.os.environ, {"RUN_MAIN": "true"}):
            self.assertTrue(ld_client_module._should_init_in_this_process())

    def test_no_run_main_but_django_settings_module_set_returns_true(self):
        with (
            _unset_env("RUN_MAIN"),
            patch.dict(
                ld_client_module.os.environ,
                {"DJANGO_SETTINGS_MODULE": "core.settings"},
            ),
        ):
            self.assertTrue(ld_client_module._should_init_in_this_process())

    def test_neither_run_main_nor_django_settings_module_returns_false(self):
        with _unset_env("RUN_MAIN", "DJANGO_SETTINGS_MODULE"):
            self.assertFalse(ld_client_module._should_init_in_this_process())


class ConfigureLaunchdarklyNotAvailableTests(ResetConfiguredStateMixin, TestCase):
    @patch.object(ld_client_module, "LDCLIENT_AVAILABLE", False)
    def test_sdk_not_installed_returns_disabled_result(self):
        result = ld_client_module.configure_launchdarkly(
            sdk_key="sdk-123",
            enabled=True,
            obs_enabled=False,
            service_name="svc",
            service_version="1.0",
        )

        self.assertFalse(result.enabled)
        self.assertFalse(result.configured)
        self.assertIn("not installed", result.reason)


class ConfigureLaunchdarklyGuardClauseTests(ResetConfiguredStateMixin, TestCase):
    def test_enabled_false_returns_disabled_result(self):
        result = ld_client_module.configure_launchdarkly(
            sdk_key="sdk-123",
            enabled=False,
            obs_enabled=False,
            service_name="svc",
            service_version="1.0",
        )

        self.assertFalse(result.enabled)
        self.assertFalse(result.configured)
        self.assertIn("disabled", result.reason.lower())

    def test_missing_sdk_key_returns_disabled_result(self):
        result = ld_client_module.configure_launchdarkly(
            sdk_key="",
            enabled=True,
            obs_enabled=False,
            service_name="svc",
            service_version="1.0",
        )

        self.assertFalse(result.enabled)
        self.assertFalse(result.configured)
        self.assertIn("LAUNCHDARKLY_SDK_KEY", result.reason)

    @patch.object(ld_client_module, "_should_init_in_this_process", return_value=False)
    def test_wrong_process_returns_disabled_result(self, _mock_should_init):
        result = ld_client_module.configure_launchdarkly(
            sdk_key="sdk-123",
            enabled=True,
            obs_enabled=False,
            service_name="svc",
            service_version="1.0",
        )

        self.assertFalse(result.enabled)
        self.assertFalse(result.configured)
        self.assertIn("non-app process", result.reason)


class ConfigureLaunchdarklySuccessTests(ResetConfiguredStateMixin, TestCase):
    @patch.object(ld_client_module, "_should_init_in_this_process", return_value=True)
    @patch.object(ld_client_module, "ld_client")
    @patch.object(ld_client_module, "Config")
    def test_success_without_observability(
        self, mock_config_cls, mock_ld_client, _mock_should_init
    ):
        with (
            patch.object(ld_client_module, "OBSERVABILITY_PLUGIN", None),
            patch.object(ld_client_module, "OBSERVABILITY_CONFIG", None),
        ):
            result = ld_client_module.configure_launchdarkly(
                sdk_key="sdk-123",
                enabled=True,
                obs_enabled=True,
                service_name="svc",
                service_version="1.0",
            )

        self.assertTrue(result.enabled)
        self.assertTrue(result.configured)
        self.assertEqual(result.reason, "Configured successfully")

        mock_config_cls.assert_called_once_with(sdk_key="sdk-123", plugins=[])
        mock_ld_client.set_config.assert_called_once()
        mock_ld_client.get.assert_called_once()
        self.assertTrue(ld_client_module._configured)

    @patch.object(ld_client_module, "_should_init_in_this_process", return_value=True)
    @patch.object(ld_client_module, "ld_client")
    @patch.object(ld_client_module, "Config")
    def test_success_with_observability_plugin_attached(
        self, mock_config_cls, mock_ld_client, _mock_should_init
    ):
        mock_obs_plugin_cls = MagicMock()
        mock_obs_config_cls = MagicMock()
        mock_obs_config_instance = mock_obs_config_cls.return_value
        mock_obs_plugin_instance = mock_obs_plugin_cls.return_value

        with (
            patch.object(ld_client_module, "OBSERVABILITY_PLUGIN", mock_obs_plugin_cls),
            patch.object(ld_client_module, "OBSERVABILITY_CONFIG", mock_obs_config_cls),
        ):
            result = ld_client_module.configure_launchdarkly(
                sdk_key="sdk-123",
                enabled=True,
                obs_enabled=True,
                service_name="my-service",
                service_version="2.3.4",
            )

        self.assertTrue(result.configured)
        mock_obs_config_cls.assert_called_once_with(
            service_name="my-service", service_version="2.3.4"
        )
        mock_obs_plugin_cls.assert_called_once_with(mock_obs_config_instance)
        mock_config_cls.assert_called_once_with(
            sdk_key="sdk-123", plugins=[mock_obs_plugin_instance]
        )

    @patch.object(ld_client_module, "_should_init_in_this_process", return_value=True)
    @patch.object(ld_client_module, "ld_client")
    @patch.object(ld_client_module, "Config")
    def test_obs_enabled_false_does_not_attach_plugin(
        self, mock_config_cls, mock_ld_client, _mock_should_init
    ):
        mock_obs_plugin_cls = MagicMock()
        mock_obs_config_cls = MagicMock()

        with (
            patch.object(ld_client_module, "OBSERVABILITY_PLUGIN", mock_obs_plugin_cls),
            patch.object(ld_client_module, "OBSERVABILITY_CONFIG", mock_obs_config_cls),
        ):
            ld_client_module.configure_launchdarkly(
                sdk_key="sdk-123",
                enabled=True,
                obs_enabled=False,
                service_name="svc",
                service_version="1.0",
            )

        mock_obs_plugin_cls.assert_not_called()
        mock_config_cls.assert_called_once_with(sdk_key="sdk-123", plugins=[])

    @patch.object(ld_client_module, "_should_init_in_this_process", return_value=True)
    @patch.object(ld_client_module, "ld_client")
    @patch.object(ld_client_module, "Config")
    def test_already_configured_short_circuits(
        self, mock_config_cls, mock_ld_client, _mock_should_init
    ):
        ld_client_module._configured = True

        result = ld_client_module.configure_launchdarkly(
            sdk_key="sdk-123",
            enabled=True,
            obs_enabled=False,
            service_name="svc",
            service_version="1.0",
        )

        self.assertTrue(result.enabled)
        self.assertTrue(result.configured)
        self.assertEqual(result.reason, "Already configured")
        mock_config_cls.assert_not_called()
        mock_ld_client.set_config.assert_not_called()


class GetClientTests(TestCase):
    @patch.object(ld_client_module, "LDCLIENT_AVAILABLE", False)
    def test_returns_none_when_sdk_not_installed(self):
        self.assertIsNone(ld_client_module.get_client())

    @patch.object(ld_client_module, "LDCLIENT_AVAILABLE", True)
    @patch.object(ld_client_module, "ld_client")
    def test_delegates_to_ld_client_get(self, mock_ld_client):
        sentinel = object()
        mock_ld_client.get.return_value = sentinel

        result = ld_client_module.get_client()

        self.assertIs(result, sentinel)
        mock_ld_client.get.assert_called_once_with()


class PostforkReinitTests(TestCase):
    @patch.object(ld_client_module, "ld_client")
    def test_calls_postfork_on_client(self, mock_ld_client):
        mock_client = MagicMock()
        mock_ld_client.get.return_value = mock_client

        ld_client_module.postfork_reinit()

        mock_client.postfork.assert_called_once_with()

    @patch.object(ld_client_module, "ld_client")
    def test_swallows_exceptions(self, mock_ld_client):
        mock_ld_client.get.side_effect = RuntimeError("boom")

        # Must not raise.
        ld_client_module.postfork_reinit()
