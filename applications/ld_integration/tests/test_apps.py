"""
Tests for applications.ld_integration.apps.LDIntegrationConfig.

Covers:
- ready() forwards each relevant setting (with correct defaults when unset)
  straight through to configure_launchdarkly as the matching keyword argument.
- ready() installs InterceptHandler as the sole root logger handler, even
  when something else (Django's LOGGING_CONFIG, pytest's log capture) has
  already attached a handler before it runs.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from applications.ld_integration.apps import LDIntegrationConfig
from common.helpers import InterceptHandler


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


class LDIntegrationConfigRootLoggerTests(TestCase):
    """ready() must own the root logger's handler list unconditionally.

    logging.basicConfig() only touches the root logger when it has *no*
    handlers yet - a no-op otherwise. Django's own LOGGING_CONFIG or
    pytest's logging capture can easily have attached one before ready()
    runs, which would silently skip installing InterceptHandler and leave
    stdlib logs unbridged. ready() must replace the handler list directly
    so it always wins.
    """

    def setUp(self):
        super().setUp()
        root_logger = logging.getLogger()
        self._original_handlers = list(root_logger.handlers)
        self._original_level = root_logger.level
        self.addCleanup(self._restore_root_logger)

    def _restore_root_logger(self):
        root_logger = logging.getLogger()
        root_logger.handlers = self._original_handlers
        root_logger.setLevel(self._original_level)

    def test_installs_intercept_handler_even_when_root_already_has_one(self):
        root_logger = logging.getLogger()
        root_logger.handlers = [logging.NullHandler()]

        config = _make_config()
        with patch("applications.ld_integration.apps.configure_launchdarkly"):
            config.ready()

        self.assertEqual(len(root_logger.handlers), 1)
        self.assertIsInstance(root_logger.handlers[0], InterceptHandler)

    def test_installs_intercept_handler_when_root_has_no_handlers(self):
        root_logger = logging.getLogger()
        root_logger.handlers = []

        config = _make_config()
        with patch("applications.ld_integration.apps.configure_launchdarkly"):
            config.ready()

        self.assertEqual(len(root_logger.handlers), 1)
        self.assertIsInstance(root_logger.handlers[0], InterceptHandler)
