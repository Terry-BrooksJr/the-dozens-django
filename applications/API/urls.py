"""URL routes for the REST API.

Canonical resource routes are versioned (``/api/v2.0.0/``) and follow REST
conventions: plural nouns, HTTP methods as verbs, filters as query params.
Health probes and schema docs stay unversioned under ``/api/``.

The pre-v2.0.0 routes are kept as deprecated aliases (see ``legacy_urlpatterns``)
so existing clients keep working; their responses carry ``Deprecation`` and
``Link: rel="successor-version"`` headers, and they are excluded from the
OpenAPI schema.
"""

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from applications.API.endpoints import (
    CreateInsultEndpoint,
    HealthEndpoint,
    InsultByCategoryEndpoint,
    InsultCollectionEndpoint,
    InsultDetailsEndpoint,
    ListReferenceIdsEndpoint,
    ListThemesAndCategoryEndpoint,
    PingEndpoint,
    RandomInsultEndpoint,
)
from applications.frontend.views import ReportJokeView
from common.deprecation import deprecated_route

v2_urlpatterns = [
    # Categories
    path("categories/", ListThemesAndCategoryEndpoint.as_view(), name="category-list"),
    path(
        "categories/<str:category_name>/insults/",
        InsultByCategoryEndpoint.as_view(),
        name="category-insult-list",
    ),
    # Insults – collection and fixed sub-paths first
    path("insults/", InsultCollectionEndpoint.as_view(), name="insult-list"),
    path("insults/random/", RandomInsultEndpoint.as_view(), name="insult-random"),
    path(
        "insults/reference-ids/",
        ListReferenceIdsEndpoint.as_view(),
        name="insult-reference-id-list",
    ),
    # Insults – member route (catch-all; keep last among insult routes)
    path(
        "insults/<str:reference_id>/",
        InsultDetailsEndpoint.as_view(),
        name="insult-detail",
    ),
    # Reports (moderation flags raised against an insult)
    path("reports/", ReportJokeView.as_view(), name="report-list"),
]

# Deprecated pre-v2.0.0 aliases. Remove once clients have migrated.
legacy_urlpatterns = [
    path(
        "categories/",
        deprecated_route(
            ListThemesAndCategoryEndpoint.as_view(), "/api/v2.0.0/categories/"
        ),
        name="list_categories",
    ),
    path(
        "insults/new",
        deprecated_route(CreateInsultEndpoint.as_view(), "/api/v2.0.0/insults/"),
        name="create_insult",
    ),
    path(
        "insults/random/",
        deprecated_route(RandomInsultEndpoint.as_view(), "/api/v2.0.0/insults/random/"),
        name="random_insult",
    ),
    path(
        "insults/category/<str:category_name>/",
        deprecated_route(
            InsultByCategoryEndpoint.as_view(),
            "/api/v2.0.0/categories/{category_name}/insults/",
        ),
        name="insults_by_category",
    ),
    path(
        "insults/<str:reference_id>/",
        deprecated_route(
            InsultDetailsEndpoint.as_view(), "/api/v2.0.0/insults/{reference_id}/"
        ),
        name="insult_detail",
    ),
]

urlpatterns = [
    # Health / liveness
    path("ping/", PingEndpoint.as_view(), name="ping"),  # Traefik liveness probe
    path("health/", HealthEndpoint.as_view(), name="health"),  # deep readiness check
    # API documentation/schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(), name="redoc"),
    # Versioned resources
    path("v2.0.0/", include(v2_urlpatterns)),
    *legacy_urlpatterns,
]
