"""API Schema Extensions Module

Provides DRF Spectacular extensions for enhanced API documentation.

Contains custom schema extensions for third-party packages like Djoser
to provide better OpenAPI documentation and examples.
"""

from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers


class DjoserUserDeleteExtension(OpenApiViewExtension):
    """Schema extension for Djoser UserViewSet endpoints.

    Enhances API documentation for user management endpoints
    with proper request/response schemas and descriptions.
    """

    # Target the Djoser view (import path can vary by version)
    # target_class = "djoser.views.UserViewSet"

    def view_replacement(self):
        from djoser.views import UserViewSet

        class PatchedUserViewset(UserViewSet):
            @extend_schema(
                summary="Delete the current user account",
                description="Permanently delete the authenticated user's account. Requires current password for confirmation.",
                request=inline_serializer(
                    name="UserDeleteRequest",
                    fields={
                        "current_password": serializers.CharField(
                            help_text="Current account password for verification"
                        )
                    },
                ),
                responses={
                    204: OpenApiResponse(
                        description="User account deleted successfully"
                    )
                },
            )
            def destroy(self, request, *args, **kwargs):
                return super().perform_destroy(request, *args, **kwargs)

            @extend_schema(
                summary="Create a new user account",
                description="Register a new user account. Required for contributing insults to the platform.",
                request=inline_serializer(
                    name="UserCreateRequest",
                    fields={
                        "username": serializers.CharField(
                            help_text="Unique username for the account"
                        ),
                        "password": serializers.CharField(help_text="Account password"),
                        "first_name": serializers.CharField(
                            help_text="User's first name"
                        ),
                        "last_name": serializers.CharField(
                            help_text="User's last name"
                        ),
                        "email": serializers.EmailField(
                            help_text="Valid email address"
                        ),
                    },
                ),
                responses={
                    201: OpenApiResponse(
                        description="User account created successfully"
                    )
                },
            )
            def create(self, request, *args, **kwargs):
                return super().perform_create(request, *args, **kwargs)
