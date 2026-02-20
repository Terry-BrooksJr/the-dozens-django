# -*- coding: utf-8 -*-
"""
Frontend views for the Dozens application.

This module provides:

- A custom 404 handler that serves an HTML page for browser requests
  and a JSON payload for API-style requests.
- An API endpoint for reporting jokes for review, which validates
  incoming data and creates a corresponding GitHub issue.

The GitHub integration is accessed via ``settings.BASE.get_github_api()``.
"""


from django.http import JsonResponse
from django.shortcuts import render
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from loguru import logger
from rest_framework import status
from rest_framework.response import Response
from django.conf import settings
from typing import Dict, Any
from applications.API.serializers import InsultReviewSerializer
from applications.API.errors import StandardErrorResponses


def page_not_found_view(request, exception):
    """Custom 404 handler: serves the image-based 404 page for browser requests,
    falls back to a JSON response for API clients."""
    if request.content_type == "application/json" or request.path.startswith(
        ("/api/", "/auth/", "/graphql")
    ):
        return JsonResponse(
            {
                "detail": "Yo momma so lost, she tried to route to this page with Apple Maps.",
                "code": "not_found",
                "status_code": 404,
            },
            status=404,
        )
    return render(request, "404.html", status=404)


class ReportJokeView(CreateAPIView):
    """API view to handle joke reporting."""

    serializer_class = InsultReviewSerializer

    def format_issue(self, issue_data: Dict[str, Any]) -> Dict[str, str]:
        """Build the GitHub issue payload for a joke review.

        Takes validated serializer data for an insult review and converts it
        into the title/body pair expected by the GitHub issues API.

        Args:
            issue_data: A dictionary of validated insult review fields,
                typically from ``serializer.validated_data``. Must include:
                - "rationale_for_review"
                - "insult_reference_id"
                - "review_type"

        Returns:
            A dictionary with:
            - "issue_title": A short, human-readable summary of the review.
            - "issue_body": The full rationale text for the review.

        Raises:
            ValueError: If ``issue_data`` is not a dictionary.
        """
        if not isinstance(issue_data, dict):
            raise ValueError("issue_data must be an instance of InsultReviewForm.")
        issue_body = issue_data["rationale_for_review"]
        issue_title = f"New Joke Review (Joke Id: {issue_data['insult_reference_id']}) - {issue_data['review_type']}"

        return {"issue_title": issue_title, "issue_body": issue_body}

    @extend_schema(
        tags=["Joke Reporting"],
        operation_id="report_joke",
        auth=[],
        summary="Report a joke for review",
        description=(
            "Submit a report for a joke that may violate community guidelines. "
            "The report is validated and forwarded to the moderation team via a GitHub issue. "
            "Anonymous submissions are supported; non-anonymous submissions require a first and last name. "
            "If post-review contact is desired, a valid email address must be provided."
        ),
        request=InsultReviewSerializer,
        responses={
            201: OpenApiResponse(
                description="Report submitted successfully",
                examples=[
                    OpenApiExample(
                        name="Report Submitted",
                        summary="Joke report created and forwarded for review",
                        description="Returned when the joke report is valid and has been successfully submitted.",
                        value={"status": "SUCCESS"},
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Invalid report payload",
                examples=[
                    OpenApiExample(
                        name="Validation Error",
                        summary="One or more required fields are missing or invalid",
                        description="Returned when the submitted data fails serializer validation.",
                        value={
                            "status": "FAILED",
                            "errors": {
                                "rationale_for_review": [
                                    "Ensure this field has at least 70 characters."
                                ]
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            422: OpenApiResponse(
                description="Report could not be processed",
                examples=[
                    OpenApiExample(
                        name="Processing Error",
                        summary="Report was valid but could not be forwarded",
                        description=(
                            "Returned when the report payload is valid but an upstream error "
                            "(e.g. GitHub API failure) prevented the issue from being created."
                        ),
                        value={
                            "status": "FAILED - GitHub API connection error",
                            "errors": {},
                        },
                        response_only=True,
                    )
                ],
            ),
            **StandardErrorResponses.get_common_error_responses(),
        },
    )
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
                settings.BASE.get_github_api().create_issue(
                    formatted_issue.get("issue_title"),
                    body=formatted_issue.get("issue_body"),
                )
                return Response(
                    data={"status": "SUCCESS"},
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.error(
                    f"Unable to Submit {serializer.data.get('reference_id','Unknown Reference_ID')} For Review: {str(e)}"
                )
                return Response(
                    data={"status": f"FAILED - {str(e)}", "errors": serializer.errors},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        logger.warning("Invalid form submission for joke review.")
        return Response(
            data={"status": "FAILED", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
