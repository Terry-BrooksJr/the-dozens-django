"""
Frontend views for the Dozens application.

This module provides:

- A custom 404 handler that serves an HTML page for browser requests
  and a JSON payload for API-style requests.
- An API endpoint for reporting jokes for review, which validates
  incoming data and creates a corresponding GitHub issue.

The GitHub integration is accessed via ``settings.BASE.get_github_api()``.
"""

from typing import Any

from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from loguru import logger
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from applications.API.errors import StandardErrorResponses
from applications.API.models import Insult, InsultReview
from applications.API.serializers import InsultReviewSerializer
from core.settings import Base


class LandingPageView(TemplateView):
    """Renders the public landing page."""

    template_name = "landing.html"


class PasswordResetPageView(TemplateView):
    """Browser front end for Djoser's JSON password-reset endpoints.

    Without ``uid``/``token`` it asks for an email and POSTs it to
    ``/auth/users/reset_password/``. With them (the link in Djoser's reset
    email, see ``DJOSER["PASSWORD_RESET_CONFIRM_URL"]``) it asks for the new
    password and POSTs it to ``/auth/users/reset_password_confirm/``.
    """

    template_name = "password_reset.html"


class StatusPageView(TemplateView):
    """Renders the service status page."""

    template_name = "status.html"


def page_not_found_view(request, exception):  # pylint: disable=unused-argument
    """Custom 404 handler: serves the image-based 404 page for browser requests,
    falls back to a JSON response for API clients.

    `exception` is unused but required: Django's URL resolver always calls a
    custom 404 handler as `callback(request, exception=exception)`.
    """
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


@extend_schema_view(
    post=extend_schema(
        tags=["Joke Reporting"],
        operation_id="report_joke",
        auth=[],
        summary="Report a joke for review",
        description=(
            "Flag a joke for moderator review. A valid report opens a GitHub issue "
            "for the moderation team; the response links to it.\n\n"
            "`rationale_for_review` must be at least 70 characters. Reports can be "
            "anonymous; otherwise first and last name are required, and an email "
            "is required when `post_review_contact_desired` is true."
        ),
        request=InsultReviewSerializer,
        examples=[
            OpenApiExample(
                "Anonymous report",
                value={
                    "insult_reference_id": "SNORT_MQ==",
                    "review_type": "RE",
                    "anonymous": True,
                    "rationale_for_review": (
                        "This joke is explicit and should be marked NSFW so it does "
                        "not show up in SFW results."
                    ),
                },
                request_only=True,
            )
        ],
        responses={
            201: OpenApiResponse(
                description="Report accepted and a GitHub issue opened.",
                examples=[
                    OpenApiExample(
                        name="Report submitted",
                        value={
                            "status": "SUCCESS",
                            "github_url": "https://github.com/Terry-BrooksJr/the-dozens-django/issues/123",
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(
                description="Invalid report; `errors` lists the problems by field.",
                examples=[
                    OpenApiExample(
                        name="Validation error",
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
                description=(
                    "The report was valid but the GitHub issue couldn't be created "
                    "(e.g. GitHub is unreachable). Retry later."
                ),
                examples=[
                    OpenApiExample(
                        name="Could not forward",
                        value={"status": "FAILED", "errors": {}},
                        response_only=True,
                    )
                ],
            ),
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    )
)
class ReportJokeView(CreateAPIView):
    """API view to handle joke reporting."""

    serializer_class = InsultReviewSerializer
    # Anonymous reporting is supported. Set explicitly: the Base default
    # (DjangoModelPermissionsOrAnonReadOnly) needs a queryset this view lacks.
    permission_classes = [AllowAny]

    def format_issue(self, issue_data: dict[str, Any]) -> dict[str, str]:
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
            TypeError: If ``issue_data`` is not a dictionary.
        """
        if not isinstance(issue_data, dict):
            raise TypeError("issue_data must be a dict.")
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
        logger.bind(request_path=request.path, request_method=request.method).debug(
            "Received request to report joke."
        )
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            vd = dict(serializer.validated_data)
            ref_id = vd.get("insult_reference_id", "unknown")
            review_type = vd.get("review_type", "unknown")
            anonymous = vd.get("anonymous", True)
            try:
                formatted_issue = self.format_issue(vd)
                new_issue = Base.get_github_api().create_issue(
                    formatted_issue.get("issue_title"),
                    body=formatted_issue.get("issue_body"),
                )
                logger.bind(
                    request_path=request.path,
                    request_method=request.method,
                    insult_reference_id=ref_id,
                    review_type=review_type,
                    anonymous=anonymous,
                ).info(
                    f"Joke report submitted and GitHub issue opened. Github URL: {new_issue.html_url}"
                )
                return Response(
                    data={"status": "SUCCESS", "github_url": new_issue.html_url},
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.bind(
                    request_path=request.path,
                    request_method=request.method,
                    insult_reference_id=ref_id,
                    review_type=review_type,
                    anonymous=anonymous,
                    error=str(e),
                ).error(f"Unable to submit {ref_id} for review: {e}")
                return Response(
                    data={"status": "FAILED", "errors": serializer.errors},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        logger.bind(
            request_path=request.path,
            request_method=request.method,
            validation_errors=serializer.errors,
        ).warning("Invalid form submission for joke review.")
        return Response(
            data={"status": "FAILED", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


def get_reference_ids(request):
    """API endpoint to retrieve a list of insult reference IDs for reporting purposes."""
    if request.method == "GET":
        reference_ids = Insult.objects.filter(status=Insult.STATUS.ACTIVE).values_list(
            "reference_id", flat=True
        )
        return JsonResponse({"reference_ids": list(reference_ids)}, status=200)
    return JsonResponse({"detail": "Method not allowed."}, status=405)
