from __future__ import annotations

from typing import Any
from django.conf import settings

from .client import get_client
from .context import context_from_request


def _enabled() -> bool:
    return getattr(settings, "LAUNCHDARKLY_ENABLED", True)


def bool_flag(flag_key: str, request=None, *, default: bool = False) -> bool:
    if not _enabled():
        return default

    ctx = context_from_request(request) if request is not None else None
    if ctx is None:
        return default

    return bool(get_client().variation(flag_key, ctx, default))


def json_flag(flag_key: str, request=None, *, default: Any = None) -> Any:
    if not _enabled():
        return default

    ctx = context_from_request(request) if request is not None else None
    if ctx is None:
        return default

    return get_client().variation(flag_key, ctx, default)
