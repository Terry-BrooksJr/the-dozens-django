# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from API.forms import InsultReviewForm
from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path
from django.utils.decorators import method_decorator

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from django.views.generic import TemplateView
from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import API.urls
import graphQL.urls
from thedozens.views import HomePage 
import os



urlpatterns = [
    path("graphql", include(graphQL.urls), name="GraphQL"),
    path("admin/", admin.site.urls),
    re_path(r'^auth/', include('djoser.urls')),
    path("api-auth/", include("rest_framework.urls")),
    path('', include('django_prometheus.urls')),
    path("__debug__/", include("debug_toolbar.urls")),
    path("api/", include(API.urls)),
    re_path(r"$^", HomePage.as_view(), name="home-page"),
    # path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
]
