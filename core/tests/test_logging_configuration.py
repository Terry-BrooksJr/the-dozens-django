# -*- coding: utf-8 -*-
"""
Tests for the Loguru logging configuration lifecycle in core.settings.

Covers:
- Base.configure_logging_common(): runs exactly once per class, even under
  concurrent callers, and reports whether it performed setup.
- Offline/Development/Production/Staging.configure_logging(): the sinks each
  environment installs, including the optional Loki and LaunchDarkly sinks.
"""

from __future__ import annotations

import os
import threading
from unittest.mock import patch

from django.test import SimpleTestCase

from core.settings import Base, Development, Offline, Production, Staging


class _ResetsLoggingConfigured(SimpleTestCase):
    """Resets the shared, process-wide logging guard around each test.

    `configure_logging_common` deliberately checks and sets the guard via
    `Base.is_logging_configured()`/`Base.set_logging_configured_state()`
    (not `cls.`) so that the guard is shared across every environment
    subclass - so tests must reset it on `Base` regardless of which
    subclass's `configure_logging()` they exercise, or a prior test
    configuring any subclass would make this one's call a silent no-op.
    """

    def setUp(self):
        super().setUp()
        original = Base.is_logging_configured()
        self.addCleanup(Base.set_logging_configured_state, original)
        Base.set_logging_configured_state(False)


class ConfigureLoggingCommonTests(_ResetsLoggingConfigured):
    """Tests for `Base.configure_logging_common`, the shared once-per-process setup guard."""

    @patch("core.settings.logger")
    def test_first_call_performs_setup_and_sets_flag(self, mock_logger):
        """The first call performs setup, returns True, and flips the shared guard."""
        performed = Base.configure_logging_common()

        self.assertTrue(performed)
        self.assertTrue(Base.is_logging_configured())
        mock_logger.remove.assert_called_once()
        mock_logger.configure.assert_called_once()

    @patch("core.settings.logger")
    def test_second_call_is_a_no_op(self, mock_logger):
        """A second call returns False and performs no further logger setup."""
        Base.configure_logging_common()
        mock_logger.reset_mock()

        performed_again = Base.configure_logging_common()

        self.assertFalse(performed_again)
        mock_logger.remove.assert_not_called()
        mock_logger.configure.assert_not_called()

    @patch("core.settings.logger")
    def test_concurrent_callers_configure_exactly_once(self, mock_logger):
        """Under concurrent callers, exactly one performs setup and the rest no-op."""
        results = []
        barrier = threading.Barrier(8)

        def call():
            barrier.wait()
            results.append(Base.configure_logging_common())

        threads = [threading.Thread(target=call) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 7)
        mock_logger.remove.assert_called_once()


class PostSetupTests(_ResetsLoggingConfigured):
    """Tests for `Base.post_setup`, the django-configurations lifecycle hook.

    django-configurations calls `post_setup()` once Value()s resolve, only
    on the concrete class DJANGO_CONFIGURATION selects. This guards against
    a regression where settings finish resolving without ever installing
    the selected environment's logging sinks - either because the parent
    hook stopped running, or configure_logging() stopped being called from
    it (or got called more than once).
    """

    @patch("core.settings.Base.configure_logging")
    @patch("configurations.base.Configuration.post_setup")
    def test_calls_parent_first_then_configures_logging_once(
        self, mock_parent_post_setup, mock_configure_logging
    ):
        call_order = []
        mock_parent_post_setup.side_effect = lambda: call_order.append("parent")
        mock_configure_logging.side_effect = lambda: call_order.append(
            "configure_logging"
        )

        Base.post_setup()

        self.assertEqual(call_order, ["parent", "configure_logging"])
        mock_parent_post_setup.assert_called_once()
        mock_configure_logging.assert_called_once()


class OfflineLoggingTests(_ResetsLoggingConfigured):
    """Tests for `Offline.configure_logging`."""

    @patch("core.settings.logger")
    def test_adds_single_debug_console_sink(self, mock_logger):
        """Offline adds exactly one sink: the console at DEBUG level."""
        Offline.configure_logging()

        mock_logger.add.assert_called_once()
        _, kwargs = mock_logger.add.call_args
        self.assertEqual(kwargs["level"], "DEBUG")

    @patch("core.settings.logger")
    def test_skips_sinks_when_already_configured(self, mock_logger):
        """No sinks are added when the shared `Base.is_logging_configured()` guard is already set."""
        # The guard lives on Base, shared across every environment subclass -
        # setting it on Offline alone would not stop configure_logging().
        Base.set_logging_configured_state(True)

        Offline.configure_logging()

        mock_logger.add.assert_not_called()


class DevelopmentLoggingTests(_ResetsLoggingConfigured):
    """Tests for `Development.configure_logging`."""

    @patch("core.settings.logger")
    def test_no_loki_sink_when_loki_url_unset(self, mock_logger):
        """Without LOKI_URL set, only the console sink is added."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOKI_URL", None)
            Development.configure_logging()

        self.assertEqual(mock_logger.add.call_count, 1)

    @patch("core.settings.LokiLoggerHandler")
    @patch("core.settings.logger")
    def test_adds_loki_sink_when_loki_url_set(self, mock_logger, mock_loki_handler):
        """With LOKI_URL and LOKI_PASSWORD set, a Loki handler sink is added alongside the console sink."""
        with patch.dict(
            os.environ,
            {"LOKI_URL": "http://loki.example.com", "LOKI_PASSWORD": "secret"},
        ):
            Development.configure_logging()

        mock_loki_handler.assert_called_once()
        self.assertEqual(
            mock_loki_handler.call_args.kwargs["url"], "http://loki.example.com"
        )
        self.assertEqual(
            mock_loki_handler.call_args.kwargs["auth"], ("lokiadmin", "secret")
        )
        self.assertEqual(mock_logger.add.call_count, 2)


class ProductionLoggingTests(_ResetsLoggingConfigured):
    """Tests for `Production.configure_logging`."""

    @patch("core.settings.logger")
    def test_stdout_only_when_loki_and_ld_disabled(self, mock_logger):
        """With Loki and LaunchDarkly Observability both disabled, only stdout gets a sink."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOKI_URL", None)
            with patch.object(Production, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", False):
                Production.configure_logging()

        self.assertEqual(mock_logger.add.call_count, 1)

    @patch("core.settings.LokiLoggerHandler")
    @patch("core.settings.logger")
    def test_adds_loki_and_launchdarkly_sinks_when_enabled(
        self, mock_logger, mock_loki_handler
    ):
        """With LOKI_URL set and LaunchDarkly Observability enabled, stdout, Loki, and LD all get sinks."""
        with patch.dict(
            os.environ,
            {"LOKI_URL": "http://loki.example.com", "LOKI_PASSWORD": "secret"},
        ):
            with patch.object(Production, "LAUNCHDARKLY_OBSERVABILITY_ENABLED", True):
                Production.configure_logging()

        mock_loki_handler.assert_called_once()
        # stdout + Loki + LaunchDarkly
        self.assertEqual(mock_logger.add.call_count, 3)


class StagingLoggingTests(_ResetsLoggingConfigured):
    """Tests for `Staging.configure_logging`."""

    @patch("core.settings.LokiLoggerHandler")
    @patch("core.settings.logger")
    def test_ignores_loki_url_and_adds_single_warning_sink(
        self, mock_logger, mock_loki_handler
    ):
        """Staging never adds a Loki sink even if LOKI_URL is set, and adds one WARNING-level console sink."""
        with patch.dict(
            os.environ,
            {"LOKI_URL": "http://loki.example.com", "LOKI_PASSWORD": "secret"},
        ):
            Staging.configure_logging()

        mock_loki_handler.assert_not_called()
        mock_logger.add.assert_called_once()
        _, kwargs = mock_logger.add.call_args
        self.assertEqual(kwargs["level"], "WARNING")
