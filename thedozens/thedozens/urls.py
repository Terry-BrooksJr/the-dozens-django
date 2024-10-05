# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
import API.urls
import graphQL.urls
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from thedozens.views import GitHubCreateIssueEndPoint, HomePage

urlpatterns = [
    path("graphql", include(graphQL.urls), name="GraphQL"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("django_prometheus.urls")),
    path("api/", include(API.urls)),
    re_path(r"^$", HomePage.as_view(), name="home-page"),
    re_path(r"^auth/", include("djoser.urls")),
    re_path(r"^auth/", include("djoser.urls.authtoken")),
    path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
]

if settings.DEBUG:
    urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")))
