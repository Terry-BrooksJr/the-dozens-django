"""
common.loki
~~~~~~~~~~~

Loki log forwarding: installs the Loguru → Loki sink and reports whether it
is actually delivering, for the ``loki`` entry of ``/api/health/``.

Status values (see ``forwarding_status``):

- ``Actively Forwarded``: Loki is configured with a valid URL, this process
  installed the sink, and its most recent push to Loki succeeded.
- ``Configured - Not Forwarding``: the configuration is valid, but this
  process isn't delivering: the active settings class doesn't install the
  sink (Staging, Offline), no push has succeeded yet, or the latest push
  failed.
- ``Disabled``: Loki isn't configured (``LOKI_URL`` or ``LOKI_PASSWORD``
  unset), or ``LOKI_URL`` isn't a valid http(s) URL; no sink is installed.

Each gunicorn worker has its own sink, so the status describes the worker
that answered the health request.
"""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlsplit

from loguru import logger
from loki_logger_handler.loki_logger_handler import LokiLoggerHandler

from common.helpers import SanitizingLoguruFormatter

ACTIVELY_FORWARDED = "Actively Forwarded"
CONFIGURED_NOT_FORWARDING = "Configured - Not Forwarding"
DISABLED = "Disabled"

_LOKI_USER = "lokiadmin"
_FLUSH_INTERVAL_SECONDS = 10

# The sink installed in this process, if any (one per process).
_handler: MonitoredLokiHandler | None = None


class MonitoredLokiHandler(LokiLoggerHandler):
    """``LokiLoggerHandler`` that records when its pushes succeed or fail.

    The library's own ``error`` flag is set on the first failure and never
    cleared, so it can't tell "recovered" from "still failing", nor "sending
    fine" from "never sent". This wraps the push itself instead.
    """

    def __init__(self, *args, **kwargs):
        """Create the handler, then wrap its push to record each outcome."""
        self._outcome_lock = threading.Lock()
        self.last_success_at: float | None = None
        self.last_failure_at: float | None = None
        super().__init__(*args, **kwargs)

        push = self.request.send

        def _tracked_push(data):
            try:
                push(data)
            except Exception:
                self._record(success=False)
                raise
            self._record(success=True)

        self.request.send = _tracked_push

    def _record(self, *, success: bool) -> None:
        """Note the time of a push outcome."""
        with self._outcome_lock:
            if success:
                self.last_success_at = time.monotonic()
            else:
                self.last_failure_at = time.monotonic()

    @property
    def is_forwarding(self) -> bool:
        """Whether a push has succeeded and nothing has failed since."""
        with self._outcome_lock:
            return self.last_success_at is not None and (
                self.last_failure_at is None
                or self.last_success_at >= self.last_failure_at
            )


def _configured() -> tuple[str, str] | None:
    """``(url, password)`` when both are set, else None."""
    url = os.getenv("LOKI_URL", "").strip()
    password = os.getenv("LOKI_PASSWORD", "")
    return (url, password) if url and password else None


def _is_valid_url(url: str) -> bool:
    """Whether ``url`` is an absolute http(s) URL with a host."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def install_loki_sink(environment: str) -> MonitoredLokiHandler | None:
    """Add a Loki sink to Loguru when Loki is configured with a valid URL.

    Args:
        environment: Value of the ``environment`` label on every log line.

    Returns:
        The installed handler, or None when Loki is disabled or ``LOKI_URL``
        is invalid (which is logged).
    """
    global _handler
    config = _configured()
    if config is None:
        return None
    url, password = config
    if not _is_valid_url(url):
        logger.warning("LOKI_URL is not a valid http(s) URL; Loki forwarding is off")
        return None

    handler = MonitoredLokiHandler(
        url=url,
        auth=(_LOKI_USER, password),
        labels={"application": "dozen_api", "environment": environment},
        label_keys={},
        timeout=_FLUSH_INTERVAL_SECONDS,
        default_formatter=SanitizingLoguruFormatter(),
    )
    logger.add(handler, serialize=True)
    _handler = handler
    return handler


def forwarding_status() -> str:
    """Loki forwarding status for this process (see the module docstring)."""
    config = _configured()
    if config is None or not _is_valid_url(config[0]):
        return DISABLED
    if _handler is not None and _handler.is_forwarding:
        return ACTIVELY_FORWARDED
    return CONFIGURED_NOT_FORWARDING
