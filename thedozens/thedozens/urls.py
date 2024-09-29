# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
import API.urls
import graphQL.urls
from thedozens.views import HomePage, GitHubCreateIssueEndPoint
from django.conf import settings

urlpatterns = [
    path("graphql", include(graphQL.urls), name="GraphQL"),
    path("admin/", admin.site.urls),
    re_path(r'^auth/', include('djoser.urls')),
    path("api-auth/", include("rest_framework.urls")),
    path('', include('django_prometheus.urls')),
    path("api/", include(API.urls)),
    re_path(r"^$", HomePage.as_view(), name="home-page"),
    path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
]

if settings.DEBUG:
    urlpatterns.insert(3, path("__debug__/", include("debug_toolbar.urls")) )