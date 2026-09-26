from __future__ import annotations

from .context import browser_context_from_request


def launchdarkly_user(request):
    """Expose ``ld_user`` to templates for the browser SDK's initial context.

    The value is a callable so the session is only touched on templates that
    actually render ``{{ ld_user }}`` (Django calls it on first lookup).
    """
    return {"ld_user": lambda: browser_context_from_request(request)}
