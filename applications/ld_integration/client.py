"""
Client utilities for integrating LaunchDarkly feature flags into the application.

This module centralizes initialization, configuration, and safe access to the shared LaunchDarkly client,
including optional observability plugins and post-fork reinitialization for worker-based servers.
"""

from __future__ import annotations

import contextlib
import os
import threading
from dataclasses import dataclass

import ldclient as ld_client
from ldclient.config import Config

try:
    from ldobserve import (
        ObservabilityConfig as OBSERVABILITY_CONFIG,
        ObservabilityPlugin as OBSERVABILITY_PLUGIN,
    )
except ImportError:
    OBSERVABILITY_CONFIG = None
    OBSERVABILITY_PLUGIN = None


_lock = threading.Lock()
_configured = False


@dataclass(frozen=True)
class LDInitResult:
    enabled: bool
    configured: bool
    reason: str


def _should_init_in_this_process() -> bool:
    """
    Django dev server uses an autoreloader that imports twice.
    RUN_MAIN is set in the reloader child process.
    """
    if os.getenv(
        "DJANGO_ALLOW_ASYNC_UNSAFE"
    ):  # not related, but shows you're doing weird dev stuff
        pass
    if os.getenv("RUN_MAIN") == "true":
        return True
    # In production (gunicorn/uwsgi), RUN_MAIN usually isn't set.
    return os.getenv("DJANGO_SETTINGS_MODULE") is not None


def configure_launchdarkly(
    *,
    sdk_key: str,
    enabled: bool,
    obs_enabled: bool,
    service_name: str,
    service_version: str,
) -> LDInitResult:
    """
    Initialize and configure the shared LaunchDarkly client for this process. This function coordinates basic enablement checks, process safety, and optional observability integration before creating the SDK singleton.

    The function returns a structured result indicating whether LaunchDarkly is enabled, whether configuration actually occurred in this call, and the reason for that outcome. It is safe to call multiple times; subsequent calls will report that configuration has already been performed without reinitializing the client.

    Args:
        sdk_key: The LaunchDarkly SDK key used to authenticate the client.
        enabled: A feature flag indicating whether LaunchDarkly should be used at all.
        obs_enabled: Whether observability plugins should be attached to the client if available.
        service_name: Logical service identifier used for observability metadata.
        service_version: Version string for the running service used in observability metadata.

    Returns:
        An LDInitResult describing the final enabled state, whether configuration occurred, and a human-readable reason.
    """
    global _configured

    if not enabled:
        return LDInitResult(
            enabled=False,
            configured=False,
            reason="LaunchDarkly disabled via settings/env",
        )

    if not sdk_key:
        return LDInitResult(
            enabled=False, configured=False, reason="Missing LAUNCHDARKLY_SDK_KEY"
        )

    if not _should_init_in_this_process():
        return LDInitResult(
            enabled=False, configured=False, reason="Skipped init in non-app process"
        )

    with _lock:
        if _configured:
            return LDInitResult(
                enabled=True, configured=True, reason="Already configured"
            )

        plugins = []
        if obs_enabled and OBSERVABILITY_PLUGIN and OBSERVABILITY_CONFIG:
            # Observability plugin init pattern  [oai_citation:5‡LaunchDarkly](https://launchdarkly.com/docs/eu-docs/sdk/observability/python)
            obs_cfg = OBSERVABILITY_CONFIG(
                service_name=service_name,
                service_version=service_version,
            )
            plugins.append(OBSERVABILITY_PLUGIN(obs_cfg))

        ld_client.set_config(Config(sdk_key=sdk_key, plugins=plugins))
        _ = ld_client.get()

        _configured = True
        return LDInitResult(
            enabled=True, configured=True, reason="Configured successfully"
        )


def get_client():
    """
    Assumes configure_launchdarkly() already ran via AppConfig.ready().
    """
    return ld_client.get()


def postfork_reinit():
    """
    Call this inside each worker process after fork.
    This is the official fix for worker-based servers.
    """
    with contextlib.suppress(Exception):
        ld_client.get().postfork()
