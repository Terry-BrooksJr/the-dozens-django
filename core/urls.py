# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""

import contextlib
import ipaddress

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseForbidden
from django.urls import include, path, re_path
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


def metrics_view(request):
    """Serve Prometheus metrics only to requests from PROMETHEUS_ALLOWED_HOSTS.

    Each entry can be an exact IP address or a CIDR network (e.g. 172.19.0.0/24).
    """
    allowed = getattr(settings, "PROMETHEUS_ALLOWED_HOSTS", [])
    remote = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ipaddress.ip_address(remote)
    except ValueError:
        return HttpResponseForbidden()

    for entry in allowed:
        try:
            if remote_ip in ipaddress.ip_network(entry, strict=False):
                return ExportToDjangoView(request)
        except ValueError:
            continue

    return HttpResponseForbidden()


urlpatterns = [
    path("", LandingPageView.as_view(), name="landing"),
    path("status/", StatusPageView.as_view(), name="status"),
    path("graphql/", include(GRAPHQL_URL), name="GraphQL"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("metrics", metrics_view, name="prometheus-django-metrics"),
    path("api/", include(API_URLS)),
    path("auth/token/logout/", TokenDestroyView.as_view(), name="token_logout"),
    re_path(r"^auth/", include("djoser.urls")),
    re_path(r"^auth/", include("djoser.urls.authtoken")),
    path("report/", csrf_exempt(ReportJokeView.as_view()), name="report-joke"),
    path(
        "insults/reference-ids/",
        csrf_exempt(get_reference_ids),
        name="insult-reference-ids",
    ),
]

handler404 = page_not_found_view

if settings.DEBUG:
    with contextlib.suppress(ImportError):
        urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")))
