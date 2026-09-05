"""
Tests for applications.ld_integration.apps.LDIntegrationConfig.

Covers:
- ready() forwards each relevant setting (with correct defaults when unset)
  straight through to configure_launchdarkly as the matching keyword argument.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from applications.ld_integration.apps import LDIntegrationConfig


def _make_config():
    # AppConfig.__init__ needs (app_name, app_module); avoid Django's app
    # registry entirely since we only care about the .ready() method body.
    return LDIntegrationConfig.__new__(LDIntegrationConfig)


class LDIntegrationConfigReadyTests(TestCase):
    @override_settings(
        LAUNCHDARKLY_SDK_KEY="sdk-abc",
        LAUNCHDARKLY_ENABLED=True,
        LAUNCHDARKLY_OBSERVABILITY_ENABLED=True,
        LAUNCHDARKLY_SERVICE_NAME="my-service",
        LAUNCHDARKLY_SERVICE_VERSION="9.9.9",
    )
    def test_ready_forwards_settings_to_configure_launchdarkly(self):
        config = _make_config()

        with patch(
            "applications.ld_integration.apps.configure_launchdarkly"
        ) as mock_configure:
            config.ready()

        mock_configure.assert_called_once_with(
            sdk_key="sdk-abc",
            enabled=True,
            obs_enabled=True,
            service_name="my-service",
            service_version="9.9.9",
        )

    def test_ready_uses_defaults_when_settings_are_absent(self):
        from django.conf import settings

        config = _make_config()

        with patch(
            "applications.ld_integration.apps.configure_launchdarkly"
        ) as mock_configure:
            config.ready()

        _, kwargs = mock_configure.call_args
        self.assertEqual(
            kwargs["sdk_key"], getattr(settings, "LAUNCHDARKLY_SDK_KEY", "")
        )
        self.assertEqual(
            kwargs["enabled"], getattr(settings, "LAUNCHDARKLY_ENABLED", True)
        )
        self.assertEqual(
            kwargs["obs_enabled"],
            getattr(settings, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", False),
        )
        self.assertEqual(
            kwargs["service_name"],
            getattr(settings, "LAUNCHDARKLY_SERVICE_NAME", "django-service"),
        )
        self.assertEqual(
            kwargs["service_version"],
            getattr(settings, "LAUNCHDARKLY_SERVICE_VERSION", "dev"),
        )
