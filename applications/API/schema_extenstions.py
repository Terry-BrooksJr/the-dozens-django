# api/schema_extensions.py
from rest_framework import serializers
from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse

class DjoserUserDeleteExtension(OpenApiViewExtension):
    # Target the Djoser view (import path can vary by version)
    # target_class = "djoser.views.UserViewSet"SA

    def view_replacement(self):
        from djoser.views import UserViewSet

        class PatchedUserViewset(UserViewSet):
            @extend_schema(
                summary="Delete the current user (requires current_password).",
                request=inline_serializer(
                    name="UserDeleteRequest",
                    fields={"current_password": serializers.CharField()}
                ),
                responses={204: OpenApiResponse(description="Deleted")},
            )
            def destroy(self, request, *args, **kwargs):
                return super().perform_destroy(request, *args, **kwargs)
            @extend_schema(
                summary="Create a New User. (Required to Contribute)",
                request=inline_serializer(
                    name="UserCreateRequest",
                    fields={"username": serializers.CharField(), "password": serializers.CharField(), "first_name": serializers.CharField(), "last_name": serializers.CharField, "email": serializers.EmailField()}
                ),
                responses={204: OpenApiResponse(description="Deleted")},
            )
            def create(self, request, *args, **kwargs):
                return super().perform_create(request, *args, **kwargs)