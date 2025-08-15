# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

import applications.API.urls as API_URLS
import applications.graphQL.urls as GRAPHQL_URL
from applications.frontend.views import GitHubCreateIssueEndPoint, HomePage

urlpatterns = [
    path("graphql", include(GRAPHQL_URL), name="GraphQL"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("django_prometheus.urls")),
    path("api/", include(API_URLS)),
    re_path(r"^$", HomePage.as_view(), name="home-page"),
    re_path(r"^auth/", include("djoser.urls")),
    re_path(r"^auth/", include("djoser.urls.authtoken")),
    path("select2/", include("django_select2.urls")),
    path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="report-joke"),
]

if settings.DEBUG:
    urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")))
