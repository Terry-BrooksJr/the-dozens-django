"""
Tests for applications.ld_integration.apps.LDIntegrationConfig.

Covers:
- ready() forwards each relevant setting (with correct defaults when unset)
  straight through to configure_launchdarkly as the matching keyword argument.
"""

from __future__ import annotations

from types import SimpleNamespace
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
        # A bare object with none of the LAUNCHDARKLY_* attributes — unlike
        # override_settings, this can actually represent "unset" rather than
        # whatever the real project settings happen to define (which would
        # make this test pass regardless of ready()'s fallback values).
        fake_settings = SimpleNamespace()
        config = _make_config()

        with (
            patch("applications.ld_integration.apps.settings", fake_settings),
            patch(
                "applications.ld_integration.apps.configure_launchdarkly"
            ) as mock_configure,
        ):
            config.ready()

        mock_configure.assert_called_once_with(
            sdk_key="",
            enabled=True,
            obs_enabled=False,
            service_name="django-service",
            service_version="dev",
        )
