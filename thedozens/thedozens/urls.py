# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from API.forms import InsultReviewForm
from django.contrib import admin
from django.urls import include, path, re_path
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from django.views.generic import TemplateView
from ghapi.all import GhApi
from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import API.urls
import graphQL.urls
import os
from rest_framework.decorators import api_view, renderer_classes, permission_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.permissions import AllowAny
from API.models import InsultReview


class HomePage(TemplateView):
    template_name = "index.html"
    # extra_context = {"title": "The Dozens", "form":InsultReviewForm() }


class GitHubCreateIssueEndPoint(APIView):
    def post(self, request, *args, **kwargs):
        form = InsultReviewForm(**request.POST)
        if form.is_valid():
            try:
                logger.success(
                    f'Save Report For Insult Report for  {form.cleaned_data["insult_id"]} to database'
                )

                issue_body = form.cleaned_data["rationale_for_review"]
                issue_title = f"New Joke Review (Joke Id: {form.cleaned_data['insult_id']}) - {form.cleaned_data['review_type']}"
                GITHUB_API = GhApi(
                    owner="terry-brooks-lrn",
                    repo="the-dozens-django",
                    token=os.environ["GITHUB_ACCESS_TOKEN"],
                )
                GITHUB_API.issue.create(title=issue_title, body=issue_body)
                form.save()
                logger.success(
                    f"successfully submitted Joke: {form.cleaned_data['insult_id']} for review"
                )
                return HttpResponse(
                    data={"status": "OK"},
                    template_name="index.html",
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.error(
                    f"Unable to Submit {form.cleaned_data['insult_id']} For Review: {db_write_error}"
                )
                return Response(
                    data={"status": "FAILED"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
   

urlpatterns = [
    path("graphql", include(graphQL.urls), name="GraphQL"),
    path("admin/", admin.site.urls),
    re_path(r'^auth/', include('djoser.urls')),
    path("api-auth/", include("rest_framework.urls")),
    path("__debug__/", include("debug_toolbar.urls")),
    path("api/", include(API.urls)),
    re_path(r"$^", cache_page(HomePage.as_view()), name="home-page"),
    path("report-joke", GitHubCreateIssueEndPoint.as_view(), name="Report-Joke"),
]
