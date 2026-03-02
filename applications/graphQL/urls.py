# -*- coding: utf-8 -*-
"""
module: applications.graphQL.urls

URL configuration for the GraphQL API.

Registers two distinct endpoints under the /graphql/ prefix declared in
core.urls:

- ``/graphql/``             → GraphQL API endpoint. Accepts POST requests
                              carrying a JSON body with a ``query`` field.
                              CSRF-exempt so external API clients can POST
                              without a browser cookie. Responds with
                              explicit Content-Type, Cache-Control, and
                              X-Content-Type-Options headers.

- ``/graphql/playground/``  → Interactive GraphiQL explorer. Renders the
                              in-browser IDE pre-loaded with example headers
                              (Authorization), variables (category, offset,
                              limit, nsfw, status, referenceId), and a
                              welcome query showcasing all five operations.
                              CSRF is active on this endpoint.

Both paths share the same compiled schema (applications.graphQL.schema).
"""

from django.urls import path

from applications.graphQL.schema import schema
from applications.graphQL.views import DozenGraphQLView

urlpatterns = [
    # Machine-facing API endpoint — CSRF-exempt, JSON headers enforced
    path("", DozenGraphQLView.as_api_view(schema=schema)),
    # Interactive GraphiQL playground — pre-loaded with example headers/variables
    path("playground/", DozenGraphQLView.as_playground_view(schema=schema)),
]
