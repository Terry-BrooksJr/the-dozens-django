"""
Root URL configuration for thedozens project.
"""

import contextlib
import hmac

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseForbidden
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django_prometheus.exports import ExportToDjangoView

import applications.API.urls as API_URLS
import applications.graphQL.urls as GRAPHQL_URL
from applications.API.auth.auth_endpoints import TokenDestroyView
from applications.frontend.views import (
    LandingPageView,
    ReportJokeView,
    StatusPageView,
    get_reference_ids,
    page_not_found_view,
)
from common.deprecation import deprecated_route
from core.admin_view import grafana_dashboard_view


@csrf_exempt
def metrics_view(request):
    """Serve Prometheus metrics only to requests bearing the correct scrape token.

    Prometheus must send:
        Authorization: Bearer <METRICS_SCRAPE_TOKEN>

    The token is compared with hmac.compare_digest to prevent timing attacks.
    Set METRICS_SCRAPE_TOKEN in Doppler; if unset the endpoint is always denied.
    CSRF-exempt because auth is header-only (no cookies), so CSRF doesn't apply.
    """
    expected = getattr(settings, "METRICS_SCRAPE_TOKEN", "")
    if not expected:
        return HttpResponseForbidden()

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, provided = auth_header.partition(" ")

    if scheme.lower() != "bearer" or not provided:
        return HttpResponseForbidden()

    if not hmac.compare_digest(provided.strip(), expected):
        return HttpResponseForbidden()

    return ExportToDjangoView(request)


urlpatterns = [
    path("", LandingPageView.as_view(), name="landing"),
    path("status/", StatusPageView.as_view(), name="status"),
    path("graphql/", include(GRAPHQL_URL)),
    # Exact "/graphql" too: APPEND_SLASH can't redirect a POST without losing its body.
    path("graphql", GRAPHQL_URL.graphql_api_view),
    path(
        "ops-gateway/observability/",
        admin.site.admin_view(grafana_dashboard_view),
        name="admin-grafana-dashboard",
    ),
    path("ops-gateway/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("metrics", metrics_view, name="prometheus-django-metrics"),
    path("api/", include(API_URLS)),
    path("auth/token/logout/", TokenDestroyView.as_view(), name="token_logout"),
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.authtoken")),
    # Deprecated aliases for routes that now live under /api/v2.0.0/.
    path(
        "report/",
        deprecated_route(ReportJokeView.as_view(), "/api/v2.0.0/reports/"),
        name="report-joke",
    ),
    path(
        "insults/reference-ids/",
        deprecated_route(
            csrf_exempt(get_reference_ids), "/api/v2.0.0/insults/reference-ids/"
        ),
        name="insult-reference-ids",
    ),
]

handler404 = page_not_found_view

if settings.DEBUG:
    with contextlib.suppress(ImportError):
        urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")))
