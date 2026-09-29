"""Middleware that attaches a LaunchDarkly context to each request."""

from __future__ import annotations

from .context import context_from_request


class LaunchDarklyContextMiddleware:
    """
    Attaches request.ld_context so your views can reuse it cheaply.
    """

    def __init__(self, get_response):
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Attach ``request.ld_context`` and continue the chain."""
        request.ld_context = context_from_request(request)
        return self.get_response(request)
