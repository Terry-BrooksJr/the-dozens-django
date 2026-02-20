"""
Unified error handling & documentation for The Dozens API.

This module:
- Defines a single source of truth for error payload templates.
- Exposes standardized OpenAPI error responses for DRF Spectacular.
- Provides the custom 'yo_momma_exception_handler' for runtime errors.
"""

from typing import Any, Dict

from drf_spectacular.utils import OpenApiResponse, OpenApiExample
from loguru import logger
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


# ---------------------------------------------------------------------------
# Core templates: single source of truth for error payloads
# ---------------------------------------------------------------------------

ERROR_TEMPLATES: Dict[int, Dict[str, str]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "detail": "Yo momma so unknown, the server said 'New phone, who this?'",
        "code": "authentication_failed",
    },
    status.HTTP_403_FORBIDDEN: {
        "detail": "Yo momma so restricted, even admin don’t have clearance.",
        "code": "permission_denied",
    },
    status.HTTP_404_NOT_FOUND: {
        "detail": "Yo momma so lost, she tried to route to this page with Apple Maps.",
        "code": "not_found",
    },
    status.HTTP_400_BAD_REQUEST: {
        "detail": "Yo momma sent a request so messy neither server nor Jerry Springer would touch it.",
        "code": "bad_request",
    },
    status.HTTP_405_METHOD_NOT_ALLOWED: {
        "detail": "Just like yo momma at every all-you-can-eat buffet: NOT ALLOWED.",
        "code": "method_not_allowed",
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "detail": "Request was throttled. Expected available in 60 seconds.",
        "code": "throttled",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "detail": "Yo momma broke the server just by showing up.",
        "code": "server_error",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "detail": "Service temporarily unavailable.",
        "code": "service_unavailable",
    },
}


def _build_payload(
    *,
    status_code: int,
    detail: str,
    code: str = "error",
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build a standardized error payload matching The Dozens API format.
    """
    payload: Dict[str, Any] = {
        "detail": detail,
        "code": code,
        "status_code": status_code,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# OpenAPI / DRF Spectacular standard error responses
# ---------------------------------------------------------------------------


class StandardErrorResponses:
    """
    Centralized error response definitions for consistent API documentation.
    Uses ERROR_TEMPLATES for the canonical detail+code values so schema
    examples match runtime behavior.
    """

    # 401 Unauthorized - Authentication required
    UNAUTHORIZED = OpenApiResponse(
        description="Authentication credentials required",
        examples=[
            OpenApiExample(
                name="Authentication Required",
                summary="Missing or invalid authentication credentials",
                description=(
                    "This endpoint requires valid authentication. "
                    "Provide a valid token in the Authorization header."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_401_UNAUTHORIZED],
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
                response_only=True,
            )
        ],
    )

    # 403 Forbidden - Permission denied (generic)
    PERMISSION_DENIED = OpenApiResponse(
        description="Insufficient permissions to access this resource",
        examples=[
            OpenApiExample(
                name="Permission Denied",
                summary="User lacks required permissions",
                description=(
                    "The authenticated user does not have permission "
                    "to perform this action on the requested resource."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_403_FORBIDDEN],
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
                response_only=True,
            )
        ],
    )

    # 403 Forbidden - Owner only access
    OWNER_ONLY_ACCESS = OpenApiResponse(
        description="Resource access restricted to owner only",
        examples=[
            OpenApiExample(
                name="Owner Only Access",
                summary="Only resource owner can modify",
                description=(
                    "This resource can only be modified by its owner. "
                    "You can only modify insults that you created."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_403_FORBIDDEN],
                    "detail": "You can only modify resources that you own.",
                    "status_code": status.HTTP_403_FORBIDDEN,
                },
                response_only=True,
            )
        ],
    )

    # 404 Not Found - Generic resource
    RESOURCE_NOT_FOUND = OpenApiResponse(
        description="The requested resource could not be found",
        examples=[
            OpenApiExample(
                name="Resource Not Found",
                summary="Requested resource does not exist",
                description=(
                    "The resource with the specified identifier was not "
                    "found or may have been removed."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND],
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                response_only=True,
            )
        ],
    )

    # 404 Not Found - Insult specific
    INSULT_NOT_FOUND = OpenApiResponse(
        description="The requested insult could not be found",
        examples=[
            OpenApiExample(
                name="Insult Not Found",
                summary="Insult with specified ID does not exist",
                description=(
                    "The insult with the provided reference_id was not "
                    "found in our database."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND],
                    "detail": "Insult not found.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                response_only=True,
            )
        ],
    )

    # 404 Not Found - Category specific
    CATEGORY_NOT_FOUND = OpenApiResponse(
        description="The requested category could not be found",
        examples=[
            OpenApiExample(
                name="Category Not Found",
                summary="Category with specified key/name does not exist",
                description=(
                    "The category with the provided key or name was not found. "
                    "Check available categories using the /api/categories endpoint."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND],
                    "detail": "Category not found.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                response_only=True,
            )
        ],
    )

    # 404 Not Found - No matching results
    NO_RESULTS_FOUND = OpenApiResponse(
        description="No resources found matching the provided criteria",
        examples=[
            OpenApiExample(
                name="No Results Found",
                summary="No resources match the specified filters",
                description=(
                    "No resources were found that match your search criteria. "
                    "Try adjusting your filters or search parameters."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND],
                    "detail": "No results found matching the provided criteria.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                },
                response_only=True,
            )
        ],
    )

    # 405 Method Not Allowed
    METHOD_NOT_ALLOWED = OpenApiResponse(
        description="HTTP method not allowed for this endpoint",
        examples=[
            OpenApiExample(
                name="Method Not Allowed",
                summary="HTTP method not supported",
                description=(
                    "The HTTP method used is not supported for this endpoint. "
                    "Check the allowed methods in the response headers."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_405_METHOD_NOT_ALLOWED],
                    "status_code": status.HTTP_405_METHOD_NOT_ALLOWED,
                },
                response_only=True,
            )
        ],
    )

    # 400 Bad Request
    BAD_REQUEST = OpenApiResponse(
        description="The request was malformed or invalid",
        examples=[
            OpenApiExample(
                name="Bad Request",
                summary="Malformed or invalid request",
                description=(
                    "Your request could not be processed due to invalid syntax "
                    "or missing required data. "
                    "Double check your payload and try again."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_400_BAD_REQUEST],
                    "status_code": status.HTTP_400_BAD_REQUEST,
                },
                response_only=True,
            )
        ],
    )

    # 429 Rate Limit Exceeded
    RATE_LIMIT_EXCEEDED = OpenApiResponse(
        description="API rate limit exceeded",
        examples=[
            OpenApiExample(
                name="Rate Limit Exceeded",
                summary="Too many requests in given time period",
                description=(
                    "You have exceeded the API rate limit. "
                    "Please wait before making additional requests."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_429_TOO_MANY_REQUESTS],
                    "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
                },
                response_only=True,
            )
        ],
    )

    # 500 Internal Server Error
    INTERNAL_SERVER_ERROR = OpenApiResponse(
        description="Internal server error occurred",
        examples=[
            OpenApiExample(
                name="Internal Server Error",
                summary="Unexpected server error",
                description=(
                    "An unexpected error occurred on the server. "
                    "Please try again later or contact support if the problem persists."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_500_INTERNAL_SERVER_ERROR],
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
                response_only=True,
            )
        ],
    )

    # 503 Service Unavailable
    SERVICE_UNAVAILABLE = OpenApiResponse(
        description="Service temporarily unavailable",
        examples=[
            OpenApiExample(
                name="Service Unavailable",
                summary="Service is temporarily down",
                description=(
                    "The service is temporarily unavailable due to maintenance "
                    "or high load. Please try again later."
                ),
                value={
                    **ERROR_TEMPLATES[status.HTTP_503_SERVICE_UNAVAILABLE],
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                },
                response_only=True,
            )
        ],
    )

    # ---- Common sets -----------------------------------------------------

    @classmethod
    def get_common_error_responses(cls) -> Dict[int, OpenApiResponse]:
        """
        Get commonly used error responses for most endpoints.
        """
        return {
            status.HTTP_500_INTERNAL_SERVER_ERROR: cls.INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE: cls.SERVICE_UNAVAILABLE,
        }

    @classmethod
    def get_authenticated_endpoint_responses(cls) -> Dict[int, OpenApiResponse]:
        """
        Get error responses for endpoints requiring authentication.
        """
        return {
            status.HTTP_401_UNAUTHORIZED: cls.UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN: cls.PERMISSION_DENIED,
            **cls.get_common_error_responses(),
        }

    @classmethod
    def get_crud_endpoint_responses(cls) -> Dict[int, OpenApiResponse]:
        """
        Get error responses for CRUD endpoints with resource ownership.
        """
        return {
            status.HTTP_401_UNAUTHORIZED: cls.UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN: cls.OWNER_ONLY_ACCESS,
            status.HTTP_404_NOT_FOUND: cls.RESOURCE_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST: cls.BAD_REQUEST,
            status.HTTP_405_METHOD_NOT_ALLOWED: cls.METHOD_NOT_ALLOWED,
            **cls.get_common_error_responses(),
        }

    @classmethod
    def get_list_endpoint_responses(cls) -> Dict[int, OpenApiResponse]:
        """
        Get error responses for list/search endpoints.
        """
        return {
            status.HTTP_400_BAD_REQUEST: cls.BAD_REQUEST,
            status.HTTP_404_NOT_FOUND: cls.NO_RESULTS_FOUND,
            status.HTTP_429_TOO_MANY_REQUESTS: cls.RATE_LIMIT_EXCEEDED,
            **cls.get_common_error_responses(),
        }


# Convenience functions for specific endpoint types used in @extend_schema
def get_insult_crud_responses() -> Dict[int, OpenApiResponse]:
    """Get standardized error responses for insult CRUD operations."""
    return {
        status.HTTP_401_UNAUTHORIZED: StandardErrorResponses.UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: StandardErrorResponses.OWNER_ONLY_ACCESS,
        status.HTTP_404_NOT_FOUND: StandardErrorResponses.INSULT_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED: StandardErrorResponses.METHOD_NOT_ALLOWED,
        status.HTTP_429_TOO_MANY_REQUESTS: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
        status.HTTP_500_INTERNAL_SERVER_ERROR: StandardErrorResponses.INTERNAL_SERVER_ERROR,
    }


def get_category_list_responses() -> Dict[int, OpenApiResponse]:
    """Get standardized error responses for category listing operations."""
    return {
        status.HTTP_404_NOT_FOUND: StandardErrorResponses.CATEGORY_NOT_FOUND,
        status.HTTP_429_TOO_MANY_REQUESTS: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
        status.HTTP_500_INTERNAL_SERVER_ERROR: StandardErrorResponses.INTERNAL_SERVER_ERROR,
    }


def get_public_list_responses() -> Dict[int, OpenApiResponse]:
    """Get standardized error responses for public list endpoints."""
    return {
        status.HTTP_404_NOT_FOUND: StandardErrorResponses.NO_RESULTS_FOUND,
        status.HTTP_429_TOO_MANY_REQUESTS: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
        status.HTTP_500_INTERNAL_SERVER_ERROR: StandardErrorResponses.INTERNAL_SERVER_ERROR,
    }


# ---------------------------------------------------------------------------
# Runtime exception handler (yo momma flavor)
# ---------------------------------------------------------------------------

# Which statuses get the yo momma overlay instead of raw DRF messages
YO_MOMMA_OVERRIDES: Dict[int, Dict[str, str]] = {
    status.HTTP_401_UNAUTHORIZED: ERROR_TEMPLATES[status.HTTP_401_UNAUTHORIZED],
    status.HTTP_403_FORBIDDEN: ERROR_TEMPLATES[status.HTTP_403_FORBIDDEN],
    status.HTTP_404_NOT_FOUND: ERROR_TEMPLATES[status.HTTP_404_NOT_FOUND],
    status.HTTP_400_BAD_REQUEST: ERROR_TEMPLATES[status.HTTP_400_BAD_REQUEST],
    status.HTTP_500_INTERNAL_SERVER_ERROR: ERROR_TEMPLATES[
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ],
}


def yo_momma_exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """
    Reusable exception handler for The Dozens API.

    - Delegates to DRF's default exception handler first.
    - Normalizes the response body shape into {detail, code, status_code, ...}.
    - Injects Yo Momma–style messages for selected HTTP status codes.
    - Uses ERROR_TEMPLATES as the single source of truth for detail/code pairs.
    """

    # Let DRF do its default handling (validation, auth, etc.)
    response = drf_exception_handler(exc, context)

    # If DRF didn't handle it, treat as 500
    if response is None:
        view = context.get("view")
        request = context.get("request")
        logger.error(
            "Unhandled exception in {view} [{method} {path}]: {exc_type}: {exc}",
            view=view.__class__.__name__ if view else "unknown",
            method=getattr(request, "method", "?"),
            path=getattr(request, "path", "?"),
            exc_type=type(exc).__name__,
            exc=exc,
        )
        base = ERROR_TEMPLATES[status.HTTP_500_INTERNAL_SERVER_ERROR]
        return Response(
            _build_payload(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=base["detail"],
                code=base["code"],
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    status_code = response.status_code
    data = response.data or {}

    # Try to pull an error code from DRF/APIException if present
    default_code = getattr(exc, "default_code", None)
    if isinstance(exc, APIException) and hasattr(exc, "get_codes"):
        try:
            codes = exc.get_codes()
            if isinstance(codes, str):
                default_code = codes
        except Exception:
            # Don't let broken get_codes() kill the handler
            pass

    current_code = data.get("code", default_code or "error")

    # Extract request context for structured logging
    view = context.get("view")
    request = context.get("request")
    log_context = {
        "view": view.__class__.__name__ if view else "unknown",
        "method": getattr(request, "method", "?"),
        "path": getattr(request, "path", "?"),
        "status_code": status_code,
        "exc_type": type(exc).__name__,
        "raw_detail": data,
    }

    # Yo Momma overlays for specific status codes
    if status_code in YO_MOMMA_OVERRIDES:
        base = YO_MOMMA_OVERRIDES[status_code]
        # Preserve original validation errors alongside the themed message
        original_detail = data.get("detail", data)
        extra = None
        if isinstance(original_detail, (dict, list)):
            extra = {"errors": original_detail}
        elif isinstance(original_detail, str) and original_detail != base["detail"]:
            extra = {"errors": original_detail}
        payload = _build_payload(
            status_code=status_code,
            detail=base["detail"],
            code=base["code"],
            extra=extra,
        )
    else:
        # Normalize everything else into your standard shape
        original_detail = data.get("detail", data)

        if isinstance(original_detail, (dict, list)):
            # Validation errors & field errors
            payload = _build_payload(
                status_code=status_code,
                detail="Request could not be processed due to validation errors.",
                code=current_code,
                extra={"errors": original_detail},
            )
        else:
            payload = _build_payload(
                status_code=status_code,
                detail=str(original_detail),
                code=current_code,
            )

    # Log the error with full context at the appropriate level
    if status_code >= 500:
        logger.error(
            "API Error {status_code} in {view} [{method} {path}]: {exc_type} - {raw_detail}",
            **log_context,
        )
    elif status_code >= 400:
        logger.warning(
            "API Error {status_code} in {view} [{method} {path}]: {exc_type} - {raw_detail}",
            **log_context,
        )

    response.data = payload
    return response
