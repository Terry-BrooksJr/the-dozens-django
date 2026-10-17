"""Authentication API Endpoints

Provides authentication endpoints with enhanced documentation.

Extends Djoser authentication views with proper OpenAPI schemas
and documentation for token-based authentication.
"""

from djoser.views import TokenDestroyView as DjoserTokenDestroyView
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        operation_id="auth_token_destroy",
        summary="Log out (delete my token)",
        description=(
            "Delete the caller's API token, logging them out everywhere it was "
            "used. Log in again for a new one."
        ),
        responses={
            204: OpenApiResponse(
                description="Token successfully deleted and user logged out"
            )
        },
        auth=[{"TokenAuth": []}],
    )
)
class TokenDestroyView(DjoserTokenDestroyView):
    """API endpoint for user logout via token destruction.

    Provides secure logout functionality by destroying the user's
    authentication token.
    """
