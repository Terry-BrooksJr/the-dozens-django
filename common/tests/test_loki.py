"""
Tests for common.loki (Loki sink installation and forwarding status).

Covers:
- Disabled: LOKI_URL / LOKI_PASSWORD unset, or LOKI_URL not a valid http(s) URL
- Configured - Not Forwarding: valid config but no sink in this process, no
  successful push yet, or the latest push failed
- Actively Forwarded: valid config and the latest push succeeded
- install_loki_sink: labels/auth passed through; nothing installed when disabled
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from common import loki

VALID_ENV = {
    "LOKI_URL": "https://logs.example.com/loki/api/v1/push",
    "LOKI_PASSWORD": "secret",  # nosec B105
}
PUSH_TARGET = "loki_logger_handler.loki_request.LokiRequest.send"


class _LokiTestCase(SimpleTestCase):
    def setUp(self):
        # No real Loguru sink and no real network; reset the per-process handler.
        for p in (
            patch.object(loki, "logger"),
            patch.object(loki, "_handler", None),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.push = MagicMock()
        push_patch = patch(PUSH_TARGET, self.push)
        push_patch.start()
        self.addCleanup(push_patch.stop)

    def env(self, **values):
        """Patch os.environ to exactly the LOKI_* values given."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOKI_")}
        env.update(values)
        p = patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)


class DisabledTests(_LokiTestCase):
    def test_unset_is_disabled_and_installs_nothing(self):
        self.env()
        self.assertIsNone(loki.install_loki_sink("Production"))
        loki.logger.add.assert_not_called()
        self.assertEqual(loki.forwarding_status(), loki.DISABLED)

    def test_password_missing_is_disabled(self):
        self.env(LOKI_URL=VALID_ENV["LOKI_URL"])
        self.assertEqual(loki.forwarding_status(), loki.DISABLED)

    def test_invalid_url_is_disabled_and_warns(self):
        for url in ("logs.example.com/push", "ftp://logs.example.com", "https://"):
            with self.subTest(url=url):
                self.env(LOKI_URL=url, LOKI_PASSWORD="secret")  # nosec B106
                self.assertIsNone(loki.install_loki_sink("Production"))
                self.assertEqual(loki.forwarding_status(), loki.DISABLED)
        loki.logger.add.assert_not_called()
        loki.logger.warning.assert_called()


class ConfiguredStatusTests(_LokiTestCase):
    def setUp(self):
        super().setUp()
        self.env(**VALID_ENV)

    def test_valid_config_without_a_sink_is_not_forwarding(self):
        # e.g. Staging/Offline: env set, but the settings class adds no sink.
        self.assertEqual(loki.forwarding_status(), loki.CONFIGURED_NOT_FORWARDING)

    def test_installed_sink_with_no_push_yet_is_not_forwarding(self):
        loki.install_loki_sink("Production")
        self.assertEqual(loki.forwarding_status(), loki.CONFIGURED_NOT_FORWARDING)

    def test_successful_push_is_actively_forwarded(self):
        handler = loki.install_loki_sink("Production")
        handler.request.send("{}")
        self.push.assert_called_once_with("{}")
        self.assertEqual(loki.forwarding_status(), loki.ACTIVELY_FORWARDED)

    def test_failed_push_after_success_is_not_forwarding_until_recovery(self):
        handler = loki.install_loki_sink("Production")
        handler.request.send("{}")

        self.push.side_effect = OSError("loki down")
        with self.assertRaises(OSError):
            handler.request.send("{}")
        self.assertEqual(loki.forwarding_status(), loki.CONFIGURED_NOT_FORWARDING)

        self.push.side_effect = None
        handler.request.send("{}")
        self.assertEqual(loki.forwarding_status(), loki.ACTIVELY_FORWARDED)

    def test_background_flush_path_is_tracked(self):
        """The handler's own flush (_send) goes through the tracked push."""
        handler = loki.install_loki_sink("Production")
        handler.buffer.put(MagicMock(key="k", labels={}, line="hi", loki_metadata=None))
        with (
            patch("loki_logger_handler.loki_logger_handler.Stream"),
            patch("loki_logger_handler.loki_logger_handler.Streams") as streams,
        ):
            streams.return_value.serialize.return_value = "{}"
            handler._send()

        self.push.assert_called_once_with("{}")
        self.assertEqual(loki.forwarding_status(), loki.ACTIVELY_FORWARDED)

    def test_install_passes_labels_auth_and_adds_serialized_sink(self):
        with patch.object(loki, "MonitoredLokiHandler") as handler_cls:
            loki.install_loki_sink("Development")
        kwargs = handler_cls.call_args.kwargs
        self.assertEqual(kwargs["url"], VALID_ENV["LOKI_URL"])
        self.assertEqual(kwargs["auth"], ("lokiadmin", "secret"))
        self.assertEqual(
            kwargs["labels"], {"application": "dozen_api", "environment": "Development"}
        )
        loki.logger.add.assert_called_once_with(
            handler_cls.return_value, serialize=True
        )
