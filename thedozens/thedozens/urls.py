# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
import API.urls
import certbot_django.server.urls
import graphQL.urls
from django.contrib import admin
from django.urls import include, path, re_path

from thedozens.views import HomePage  # ,  GitHubCreateIssueEndPoint

urlpatterns = [
    re_path(r"^\.well-known/", include(certbot_django.server.urls)),
    path("graphql", include("graphQL.urls"), name="graph"),
    path("admin/", admin.site.urls),
    re_path(r'^auth/', include('djoser.urls')),
    path("api-auth/", include("rest_framework.urls")),
    path("__debug__/", include("debug_toolbar.urls")),
    re_path("^auth/webauthn/", include("djoser.webauthn.urls")),
    path("api/", include(API.urls)),
    re_path(r"$^", cache_page(HomePage.as_view()), name="home-page"),
    path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
    re_path(r"$^", HomePage.as_view(), name="home-page"),
    # path("report", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
]
