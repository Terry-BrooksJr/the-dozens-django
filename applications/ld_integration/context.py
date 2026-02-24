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
