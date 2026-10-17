"""
applications.API.openapi
~~~~~~~~~~~~~~~~~~~~~~~~

Shared OpenAPI building blocks (parameters and example payloads) for the
``@extend_schema_view`` declarations on the API views.

Examples mirror real responses: list/detail/random insults are serialized by
``OptimizedInsultSerializer`` (``added``/``by`` and a status code), while
create responses come from ``CreateInsultSerializer`` (``added_by``/
``added_on`` and a status label). Keep them in sync with the serializers.
"""

from __future__ import annotations

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
)
from rest_framework import status

from applications.API.errors import StandardErrorResponses

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
REFERENCE_ID_PARAM = OpenApiParameter(
    name="reference_id",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    description=(
        "The insult's public reference ID: a prefix (`GIGGLE`, `CHUCKLE`, "
        "`SNORT`, `SNICKER` or `CACKLE`), an underscore and an encoded number, "
        "e.g. `SNORT_MQ==`."
    ),
)

CATEGORY_NAME_PARAM = OpenApiParameter(
    name="category_name",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    description="Category key (e.g. `P`) or name (e.g. `Poor`); case-insensitive.",
)

CATEGORY_QUERY_PARAM = OpenApiParameter(
    name="category",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Category key (e.g. `P`) or name (e.g. `Poor`), case-insensitive. "
        "An unknown category returns `400`."
    ),
)

NSFW_QUERY_PARAM = OpenApiParameter(
    name="nsfw",
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Filter explicit content: `true` returns only NSFW insults, `false` only "
        "SFW ones. Omit it to include both."
    ),
)

# ---------------------------------------------------------------------------
# Example payloads
# ---------------------------------------------------------------------------
INSULT = {
    "content": "Yo momma is so fat she needs two time zones.",
    "reference_id": "SNORT_MQ==",
    "category": "Fat",
    "nsfw": False,
    "status": "A",
    "added": "2 days ago",
    "by": "Mike R.",
}

INSULT_POOR = {
    "content": "Yo momma is so poor she can't even pay attention.",
    "reference_id": "GIGGLE_Mg==",
    "category": "Poor",
    "nsfw": False,
    "status": "A",
    "added": "3 weeks ago",
    "by": "Linda P.",
}

CREATED_INSULT = {
    "reference_id": "GIGGLE_Mw==",
    "category": "Fat",
    "content": "Yo momma is so slow she got a speeding ticket in 2031.",
    "nsfw": False,
    "status": "Pending - New",
    "added_by": "Mike R.",
    "added_on": "just now",
}


def insult_page_example(
    *insults: dict, name: str = "Page of insults"
) -> OpenApiExample:
    """A paginated insult list response, as returned by the list endpoints."""
    return OpenApiExample(
        name,
        value={
            "count": len(insults),
            "next": None,
            "previous": None,
            "results": list(insults),
            "total_count": len(insults),
            "timestamp": "2026-10-16T10:04:39.652156+00:00",
        },
        response_only=True,
    )


INSULT_EXAMPLE = OpenApiExample("Insult", value=INSULT, response_only=True)

CREATED_INSULT_EXAMPLE = OpenApiExample(
    "Created insult", value=CREATED_INSULT, response_only=True
)

CREATE_INSULT_REQUEST_EXAMPLE = OpenApiExample(
    "New insult",
    value={
        "content": "Yo momma is so slow she got a speeding ticket in 2031.",
        "category": "F",
        "nsfw": False,
    },
    request_only=True,
)

# Error bodies below are what the Production exception handler
# (applications.API.errors.yo_momma_exception_handler) returns.
UNKNOWN_CATEGORY_EXAMPLE = OpenApiExample(
    "Unknown category",
    value={
        "detail": (
            "Yo momma sent a request so messy neither server nor Jerry Springer "
            "would touch it."
        ),
        "code": "bad_request",
        "status_code": 400,
        "errors": [
            "Category 'NOPE' not found. Please provide a valid category key or name."
        ],
    },
    response_only=True,
)

INSULT_VALIDATION_ERROR_EXAMPLE = OpenApiExample(
    "Invalid insult",
    value={
        "detail": (
            "Yo momma sent a request so messy neither server nor Jerry Springer "
            "would touch it."
        ),
        "code": "bad_request",
        "status_code": 400,
        "errors": {
            "category": ["This field is required."],
            "content": ["This field may not be blank."],
        },
    },
    response_only=True,
)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
UNKNOWN_CATEGORY = OpenApiResponse(
    description="Unknown category key or name.",
    examples=[UNKNOWN_CATEGORY_EXAMPLE],
)

INVALID_PAGE = OpenApiResponse(
    description="`page` is past the last page (filters that match nothing return `200` with no results)."
)

INVALID_INSULT = OpenApiResponse(
    description="Invalid or missing insult fields.",
    examples=[INSULT_VALIDATION_ERROR_EXAMPLE],
)


def public_list_responses(*, throttled: bool = True) -> dict:
    """Error responses of the public, paginated insult list endpoints."""
    responses = {
        status.HTTP_400_BAD_REQUEST: UNKNOWN_CATEGORY,
        status.HTTP_404_NOT_FOUND: INVALID_PAGE,
        status.HTTP_500_INTERNAL_SERVER_ERROR: StandardErrorResponses.INTERNAL_SERVER_ERROR,
    }
    if throttled:
        responses[status.HTTP_429_TOO_MANY_REQUESTS] = (
            StandardErrorResponses.RATE_LIMIT_EXCEEDED
        )
    return responses
