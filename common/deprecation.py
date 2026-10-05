"""
module: common.deprecation

Helpers for keeping legacy URL routes alive while steering clients to their
replacements.

``deprecated_route`` wraps a view so every response carries the IETF
``Deprecation`` header (RFC 9745) and a ``Link`` header pointing at the
successor URL (``rel="successor-version"``). Clients and API gateways can
detect both without parsing the body.

The wrapper is a plain function with no ``cls`` attribute, so drf-spectacular
leaves deprecated aliases out of the OpenAPI schema; only the canonical
routes are documented.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


def deprecated_route(view: Callable, successor: str) -> Callable:
    """Wrap ``view`` so its responses advertise deprecation and a successor.

    Args:
        view: The view callable (e.g. ``SomeView.as_view()``).
        successor: Path of the replacement route. May contain ``str.format``
            fields named after the URL kwargs, e.g.
            ``"/api/v2.0.0/insults/{reference_id}/"``.

    Returns:
        A view callable with the same behaviour plus the deprecation headers.
    """

    def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = view(request, *args, **kwargs)
        response["Deprecation"] = "true"
        response["Link"] = f'<{successor.format(**kwargs)}>; rel="successor-version"'
        return response

    # DRF views are csrf_exempt; keep that marker on the wrapper.
    wrapped.csrf_exempt = getattr(view, "csrf_exempt", False)  # type: ignore[attr-defined]
    return wrapped
