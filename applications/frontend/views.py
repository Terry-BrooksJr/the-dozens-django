# -*- coding: utf-8 -*-

import os

from django.http import HttpRequest
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from loguru import logger
from rest_framework import status
from rest_framework.response import Response
from django.conf import settings
from applications.API.forms import InsultReviewForm
from typing import Dict, Any
from applications.API.serializers import InsultReviewSerializer



class ReportJokeView(CreateAPIView):
    """API view to handle joke reporting."""

    serializer_class = InsultReviewSerializer

    def format_issue(self, issue_data:Dict[str, Any]) -> Dict[str,str]:
        """Creates a dictionary containing the title and body for a joke review issue.
        
        This function extracts relevant information from a validated form to format an issue for review.

        Args:
            form: A validated Django form containing joke review data.

        Returns:
            Dict[str, str]: A dictionary with 'issue_title' and 'issue_body' keys.
        """
        if not isinstance(issue_data, dict):
            raise ValueError("issue_data must be an instance of InsultReviewForm.")
        issue_body = issue_data["rationale_for_review"]
        issue_title = f"New Joke Review (Joke Id: {issue_data['insult_reference_id']}) - {issue_data['review_type']}"

        return {"issue_title": issue_title, "issue_body": issue_body}

    def post(self, request: Request, *_args, **_kwargs) -> Response:
        """Handle POST requests to report a joke for review.

            This view processes a joke report form, creates a GitHub issue for review, and returns an appropriate HTTP response.

        Args:
            request: The HTTP request object containing POST data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response | None: A DRF Response object indicating the result of the operation.
        """
        logger.debug("Received request to report joke.")
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                formatted_issue = self.format_issue(dict(serializer.validated_data))
                settings.BASE.get_github_api().create_issue(formatted_issue.get("issue_title"), body=formatted_issue.get("issue_body"))
                return Response(
                    data={"status": "SUCCESS"},
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.error(
                    f"Unable to Submit {serializer.data.get('reference_id','Unknown Reference_ID')} For Review: {str(e)}"
                )
                return Response(
                    data={"status": f"FAILED - {str(e)}",  "errors": serializer.errors},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        logger.warning("Invalid form submission for joke review.")
        return Response(
            data={"status": "FAILED", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
