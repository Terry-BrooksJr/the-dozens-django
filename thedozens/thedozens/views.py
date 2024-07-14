# -*- coding: utf-8 -*-
"""
Root URL configuration for thedozens project.
"""
import os
from typing import Any

import API.urls
import graphQL.urls
from API.forms import InsultReviewForm
from django.http import HttpRequest, HttpResponse
from django.views.generic import TemplateView
from ghapi.all import GhApi
from loguru import logger
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HomePage(TemplateView):
    template_name = "index.html"
    extra_context = {"title": "The Dozens", "form":InsultReviewForm() }
    # def get_context_data(self, **kwargs) -> dict[str, Any]:
    #     context = super().get_context_data(**kwargs)
    #     context['title'] = "The Dozens"
    #     context['ReportForm'] = InsultReviewForm()

# class GitHubCreateIssueEndPoint(APIView):
#     def post(self, request:HttpRequest, *args, **kwargs) -> HttpResponse:
#         form = InsultReviewForm(request.POST)
#         if form.is_valid():
#             try:
#                 issue_body = form.cleaned_data["rationale_for_review"]
#                 issue_title = f"New Joke Review (Joke Id: {form.cleaned_data['insult_id']}) - {form.cleaned_data['review_type']}"
#                 GITHUB_API = GhApi(
#                     owner="terry-brooks-lrn",
#                     repo="the-dozens-django",
#                     token=os.environ["GITHUB_ACCESS_TOKEN"],
#                 )
#                 GITHUB_API.issue.create(title=issue_title, body=issue_body)
#                 logger.success(
#                     f"successfully submitted Joke: {form.cleaned_data['insult_id']} for review"
#                 )
#                 return Response(data={"status": "OK"}, status=status.HTTP_201_CREATED)
#             except Exception as e:
#                 logger.error(
#                     f"Unable to Submit {form.cleaned_data['insult_id']} For Review: {str(e)}"
#                 )
#                 return Response(
#                     data={"status": "FAILED"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
#                 )
   
