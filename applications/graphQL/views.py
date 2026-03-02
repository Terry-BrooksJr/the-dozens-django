# -*- coding: utf-8 -*-
"""
module: applications.graphQL.views

Custom GraphQL view for the Dozens API.

Provides two distinct view entry-points built on top of graphene-django's
GraphQLView:

- ``DozenGraphQLView.as_api_view()``
      CSRF-exempt view used for the machine-facing API endpoint
      (POST /graphql/). Attaches lean, explicit response headers
      (Content-Type, Cache-Control, X-Content-Type-Options) on every
      non-playground response.

- ``DozenGraphQLView.as_playground_view()``
      Standard view used for the interactive GraphiQL explorer
      (GET /graphql/playground/). Inherits the custom graphiql.html
      template that pre-populates headers, variables, and a welcome query
      for new visitors.
"""

from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView


class DozenGraphQLView(GraphQLView):
    """Custom GraphQL view for the Dozens API.

    Extends the stock graphene-django ``GraphQLView`` with two additions:

    1. **Response headers** — Non-playground responses receive explicit
       ``Content-Type``, ``Cache-Control``, and ``X-Content-Type-Options``
       headers so clients always receive well-typed, non-cached JSON.

    2. **CSRF exemption** — The API endpoint must accept POST requests from
       external clients that have no CSRF cookie. ``as_api_view()`` wraps
       the view with ``@csrf_exempt`` while the playground remains protected
       by the standard Django CSRF middleware.

    The interactive GraphiQL template is overridden at
    ``templates/graphene/graphiql.html`` and pre-populates the Headers,
    Variables, and Query panels with sensible defaults on first visit.
    """

    def dispatch(self, request, *args, **kwargs):
        """Process the request and attach appropriate response headers.

        Delegates all execution to the parent ``GraphQLView.dispatch()``,
        then adds headers that signal the content type and caching policy
        to API clients. Headers are only added to API responses; the
        playground response is left untouched so the browser can render
        the HTML page normally.

        Args:
            request: The incoming HTTP request.
            *args: Positional arguments forwarded to the parent view.
            **kwargs: Keyword arguments forwarded to the parent view.

        Returns:
            HttpResponse: The GraphQL response with API headers attached,
                          or the GraphiQL HTML page for playground requests.
        """
        response = super().dispatch(request, *args, **kwargs)

        # Only add API-specific headers on non-playground (JSON) responses.
        if not self.graphiql:
            # Ensure clients always parse the body as JSON.
            response["Content-Type"] = "application/json"
            # Prevent proxies and browsers from caching query responses.
            # GraphQL responses often contain user-specific or time-sensitive
            # data that must not be served stale.
            response["Cache-Control"] = "no-store"
            # Instruct browsers not to sniff the content type.
            response["X-Content-Type-Options"] = "nosniff"

        return response

    @classmethod
    def as_api_view(cls, schema, **kwargs):
        """Return a CSRF-exempt view for the machine-facing API endpoint.

        External API clients (mobile apps, server-to-server calls, OpenAPI
        clients) send POST requests without a Django CSRF cookie, so the
        endpoint must be exempt from CSRF verification. Authentication is
        enforced at the resolver or middleware level instead.

        Args:
            schema: The compiled Graphene Schema to execute queries against.
            **kwargs: Additional keyword arguments forwarded to
                      ``GraphQLView.as_view()``.

        Returns:
            Callable: A CSRF-exempt Django view function.
        """
        return csrf_exempt(cls.as_view(schema=schema, graphiql=False, **kwargs))

    @classmethod
    def as_playground_view(cls, schema, **kwargs):
        """Return the GraphiQL playground view.

        Renders the interactive GraphiQL IDE at ``/graphql/playground/``.
        CSRF is intentionally left active so the playground can only be
        used from a browser session with a valid CSRF cookie, reducing the
        risk of cross-site request forgery against the schema explorer.

        The custom ``templates/graphene/graphiql.html`` template pre-populates
        the Headers, Variables, and Query panels with sensible defaults on a
        first visit and respects whatever the user has previously saved.

        Args:
            schema: The compiled Graphene Schema to execute queries against.
            **kwargs: Additional keyword arguments forwarded to
                      ``GraphQLView.as_view()``.

        Returns:
            Callable: A standard Django view function rendering GraphiQL.
        """
        return cls.as_view(schema=schema, graphiql=True, **kwargs)
