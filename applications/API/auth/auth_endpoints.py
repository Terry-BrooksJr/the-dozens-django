"""Authentication API Endpoints

Provides authentication endpoints with enhanced documentation.

Extends Djoser authentication views with proper OpenAPI schemas
and documentation for token-based authentication.
"""

from djoser.views import TokenDestroyView as DjoserTokenDestroyView
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_token_destroy",
        summary="Logout user and destroy token",
        description="Destroys the authentication token, effectively logging out the user.",
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
