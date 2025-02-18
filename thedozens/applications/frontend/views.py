# -*- coding: utf-8 -*-

import os

from applications.API.forms import InsultReviewForm
from django.http import HttpRequest, HttpResponse
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from ghapi.all import GhApi
from loguru import logger
from rest_framework import status
from rest_framework.response import Response


class HomePage(TemplateView):
    template_name = "index.html"
    extra_context = {"title": "The Dozens"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = InsultReviewForm()
        return context


class GitHubCreateIssueEndPoint(FormView):
    form_class = InsultReviewForm

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = InsultReviewForm(request.POST)
        if form.is_valid():
            try:
                return self.format_issue(form)
            except Exception as e:
                logger.error(
                    f"Unable to Submit {form.cleaned_data['insult_id']} For Review: {str(e)}"
                )
                return Response(
                    data={"status": "FAILED"},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

    def format_issue(self, form):
        issue_body = form.cleaned_data["rationale_for_review"]
        issue_title = f"New Joke Review (Joke Id: {form.cleaned_data['insult_id']}) - {form.cleaned_data['review_type']}"
        GITHUB_API = GhApi(
            owner="terry-brooks-lrn",
            repo="the-dozens-django",
            token=os.environ["GITHUB_ACCESS_TOKEN"],
        )
        GITHUB_API.issue.create(title=issue_title, body=issue_body)
        logger.success(
            f"Successfully Submitted Joke: {form.cleaned_data['insult_id']} for review"
        )
        return Response(data={"status": "OK"}, status=status.HTTP_201_CREATED)
