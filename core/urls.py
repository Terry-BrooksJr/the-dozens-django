# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt

import applications.API.urls as API_URLS
import applications.frontend.urls as FRONTEND_URLS
import applications.graphQL.urls as GRAPHQL_URL
from applications.API.auth.auth_endpoints import TokenDestroyView
from applications.frontend.views import ReportJokeView, page_not_found_view

urlpatterns = [
    path("graphql", include(GRAPHQL_URL), name="GraphQL"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("django_prometheus.urls")),
    path("api/", include(API_URLS)),
    path("report/", include(FRONTEND_URLS)),
    path("auth/token/logout/", TokenDestroyView.as_view(), name="token_logout"),
    re_path(r"^auth/", include("djoser.urls")),
    re_path(r"^auth/", include("djoser.urls.authtoken")),
    path("report-joke/", csrf_exempt(ReportJokeView.as_view()), name="report-joke"),
]

handler404 = page_not_found_view

if settings.DEBUG:
    try:
        urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")))
    except ImportError:
        pass
