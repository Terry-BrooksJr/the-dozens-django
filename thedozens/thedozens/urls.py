# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
from API.forms import InsultReviewForm
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db import IntegrityError, DatabaseError
from django.db.transaction import TransactionManagementError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_page
from logtail import LogtailHandler
from loguru import logger
from rest_framework import status
from rest_framework_swagger.views import get_swagger_view
import API.urls
import graphQL.urls
import os
import json
import requests

PRIMARY_LOG_FILE = os.path.join(settings.BASE_DIR, "standup", "logs", "primary_ops.log")
CRITICAL_LOG_FILE = os.path.join(settings.BASE_DIR, "standup", "logs", "fatal.log")
DEBUG_LOG_FILE = os.path.join(settings.BASE_DIR, "standup", "logs", "utility.log")
LOGTAIL_HANDLER = LogtailHandler(source_token=os.getenv("LOGTAIL_API_KEY"))

logger.add(DEBUG_LOG_FILE, diagnose=True, catch=True, backtrace=True, level="DEBUG")
logger.add(PRIMARY_LOG_FILE, diagnose=False, catch=True, backtrace=False, level="INFO")
logger.add(LOGTAIL_HANDLER, diagnose=False, catch=True, backtrace=False, level="INFO")


def home(request):
    context = dict()
    if request.method == "POST":
        form = InsultReviewForm(request.POST)
        if form.is_valid():
            try:
                logger.success(
                    f'Save Report For Insult Report for  {form.cleaned_data["insult_id"]} to database'
                )

                issue_body = form.cleaned_data["rationale_for_review"]
                issue_title = f"New Joke Review (Joke Id: {form.cleaned_data['insult_id']}) - {form.cleaned_data['review_type']}"
                url = "https://api.github.com/repos/Terry-BrooksJr/the-dozens-django/issues"
                payload = {"title": issue_title, "body": issue_body}
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": os.getenv("GITHUB_ACCESS_TOKEN"),
                    "X-GitHub-Api-Version": "2022-311-28",
                    "Content-Type": "application/json",
                }
                response = requests.post(
                    url=url, headers=headers, data=payload, timeout=30
                )
                logger.debug(response.content)
                logger.debug(response.status_code)
                if response.status_code != 201:
                    logger.error(f"Error Logging to GitHub - {response.status_code}")
                    return HttpResponse(
                        content={"status": "Error Logging Issue to Github"},
                        status=status.HTTP_406_NOT_ACCEPTABLE,
                    )
                else:
                    logger.success(
                        f"Request Status From GitHub: {response.status_code}"
                    )
                    if form.save():
                        logger.success(
                            f"successfully Persisted Report to DB: {form.cleaned_data['insult_id']}"
                        )
                    else:
                        logger.error(
                            f'Unable To Persist {form.cleaned_data["insult_id"]}'
                        )
                    return HttpResponseRedirect(
                        redirect_to=reverse("home-page"),
                        status=status.HTTP_201_CREATED,
                    )
            except (
                IntegrityError,
                DatabaseError,
                TransactionManagementError,
            ) as db_write_error:
                logger.error(
                    f"Unable to Submit {form.cleaned_data['insult_id']} For Review: {db_write_error}"
                )
                return HttpResponseRedirect(
                    redirect_to=reverse("home-page"),
                    status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
                )
            except Exception as other_issue:
                logger.error(f"Some other Bad Shit: {other_issue}")
                return HttpResponseRedirect(
                    redirect_to=reverse("home-page"),
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )
        if not form.is_valid():
            context["form_errors"] = form.errors
            context["ReportForm"] = InsultReviewForm(initial=request.POST)
            messages.error(request, "Please correct the errors below and resubmit.")
            return render(request, "index.html", context)
    else:
        form = InsultReviewForm()
        context["ReportForm"] = form
        return render(request, "index.html", context)


urlpatterns = [
    path(
        "swagger",
        get_swagger_view(
            title="The Yo' Mama Roast API",
        ),
        name="swagger",
    ),
    path("graphql", include("graphQL.urls"), name="graph"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("__debug__/", include("debug_toolbar.urls")),
    path("api/", include(API.urls)),
    path("home", cache_page(timeout=43200, key_prefix="index")(home), name="home-page"),
    path("", include("django_prometheus.urls")),
]
