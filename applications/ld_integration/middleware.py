from __future__ import annotations

from .context import context_from_request


class LaunchDarklyContextMiddleware:
    """
    Attaches request.ld_context so your views can reuse it cheaply.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.ld_context = context_from_request(request)
        return self.get_response(request)
