from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from ldclient import Context


def context_from_request(request, *, anonymous_key_fallback: str = "anon") -> Context:
    user = getattr(request, "user", None)

    if (
        not user
        or isinstance(user, AnonymousUser)
        or not getattr(user, "is_authenticated", False)
    ):
        # Anonymous context
        return Context.builder(anonymous_key_fallback).anonymous(True).build()

    key = str(
        getattr(user, "pk", None) or getattr(user, "id", None) or user.get_username()
    )
    builder = Context.builder(key).name(
        getattr(user, "get_full_name", lambda: "")() or user.get_username()
    )

    # Add useful attributes without leaking secrets
    builder.set("email", getattr(user, "email", None))
    builder.set("is_staff", getattr(user, "is_staff", False))
    builder.set("is_superuser", getattr(user, "is_superuser", False))

    return builder.build()


def browser_context_from_request(request) -> dict | None:
    """Return the logged-in user's context as a plain dict for the browser SDK.

    Returns ``None`` for anonymous requests so the browser falls back to its
    own anonymous key. Deliberately a subset of ``context_from_request``: the
    page source is visible to the user and anything in the context is sent to
    LaunchDarkly from the browser, so email and superuser status are left out.
    """
    ctx = context_from_request(request)
    if ctx.anonymous:
        return None
    return {
        "kind": "user",
        "key": ctx.key,
        "name": ctx.name,
        "is_staff": bool(ctx.get("is_staff")),
    }
