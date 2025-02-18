
from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory
from applications.API.serializers import (
    CategorySerializer,
    InsultSerializer,
    MyInsultSerializer,
    serializers,
)
from common.cache import CachedResponseMixin
from common.utils.helpers import _check_ownership
from django.db.models import Q
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import permissions
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import status
from rest_framework_extensions.mixins import PaginateByMaxMixin


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an insult to edit/delete it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        return obj.added_by == request.user


@extend_schema_view(
    retrieve=extend_schema(
        tags=["Insults"],
        operation_id="retrieve_user_submitted_insults",
        description="Retrieve a list of insults added by the authenticated user.",
        responses={
            200: OpenApiResponse(
                description="A list of insults contributed by the user.",
                examples=[
                    OpenApiExample(
                        name="Successful Response",
                        value={
                            "jokester": "johndoe",
                            "jokes_contributed": 3,
                            "jokes": [
                                {"id": 1, "content": "Your code looks like spaghetti."},
                                {
                                    "id": 2,
                                    "content": "You're debugging your own mess again?",
                                },
                                {
                                    "id": 3,
                                    "content": "Your CSS skills are truly groundbreaking—breaking everything!",
                                },
                            ],
                        },
                    )
                ],
            ),
            401: OpenApiResponse(
                response={"detail": "Authentication credentials were not provided."},
                description="User is not authenticated.",
            ),
        },
    )
)
class MyInsultsViewSet(CachedResponseMixin, RetrieveUpdateDestroyAPIView):
    """
    MyInsultsViewSet is a viewset for managing insults submitted by authenticated users. It provides functionality to retrieve, update, and delete insults while enforcing user permissions.

    This viewset allows authenticated users to interact with their own submitted insults. It includes methods for retrieving the user's insults, updating an insult, and deleting an insult, ensuring that users can only modify their own submissions.

    Args:
        request: The HTTP request object.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.

    Returns:
        Response: A response object containing the result of the operation.

    Raises:
        PermissionDenied: If a user attempts to update or delete an insult they did not submit.

    Examples:
        To retrieve insults for the authenticated user:
            GET /api/insults/

        To update an insult:
            PATCH /api/insults/{id}/

        To delete an insult:
            DELETE /api/insults/{id}/
    """

    serializer_class = MyInsultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("category", "status", "added_on")

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Insult.objects.filter(added_by=self.request.user.id)
        return Insult.objects.none()

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _check_ownership(obj, request.user)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        insult = self.get_object()
        _check_ownership(insult, request.user)
        return super().update(request, *args, **kwargs)


@extend_schema(
    tags=["Insults"],
    operation_id="list_available_insult_categories",
    description="Endpoint to retrieve all available insult categories in the system",
    responses={
        200: inline_serializer(
            name="InsultCategoriesResponse",
            fields={
                "help_text": OpenApiTypes.STR,
                "available_categories": serializers.DictField(
                    child=serializers.CharField(),
                    help_text="Dictionary mapping category keys to their display names",
                ),
            },
        ),
        401: OpenApiResponse(
            description="Authentication credentials were not provided"
        ),
        403: OpenApiResponse(description="Permission denied"),
    },
    examples=[
        OpenApiExample(
            "Success Response",
            value={
                "help_text": "Available categories",
                "available_categories": {"P": "Poor", "F": "Fat"},
            },
        )
    ],
)
class AvailableInsultsCategoriesListView(PaginateByMaxMixin, ListAPIView):
    """
    API endpoint that provides a list of all available insult categories.

    This viewset is read-only and requires no authentication. It returns a mapping
    of category keys to their display names, making it useful for populating
    dropdown menus or filter options in client applications.

    Technical Details:
    -----------------
    - Endpoint: GET /api/insults/categories/
    - Authentication: None required
    - Permissions: AllowAny
    - Response Format: JSON

    Response Structure:
    ------------------
    {
        "help_text": str,
        "available_categories": {
            "category_key": "category_display_name",
            ...
        }
    }

    Example Usage:
    -------------
    ```http
    GET /api/insults/categories/

    Response:
    {
        "help_text": "Available categories",
        "available_categories": {
            "funny": "Funny Insults",
            "savage": "Savage Comebacks"
        }
    }
    ```

    Notes:
    ------
    - The endpoint always returns all active categories in the system
    - Category keys are unique identifiers used in other API endpoints
    - Display names are human-readable versions of the categories

    Related Models:
    --------------
    - InsultCategory: Stores category information including key and display name
    """

    queryset = InsultCategory.objects.all()
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        """
        Retrieve all available insult categories.

        Transforms the queryset into a dictionary mapping category keys to their
        display names for easier consumption by client applications.

        Returns:
            Response: JSON object containing help text and available categories
        """
        super().list(request, *args, **kwargs)
        available_categories = {
            cat.key: cat.name
            for cat in InsultCategory.objects.all().values("key", "name")
        }

        return Response(
            {
                "help_text": "Available categories",
                "available_categories": available_categories,
            }
        )


@extend_schema(
    tags=["Insults"],
    operation_id="list_insults_by_category",
    description="Retrieve a list of insults filtered by category. Each category corresponds to a predefined list of available insults.",
    parameters=[
        OpenApiParameter(
            name="category",
            description="The category code to filter insults by. Should match one of the available categories.",
            required=True,
            type=str,
            examples=[
                OpenApiExample(
                    name="Example Category",
                    value="fat",
                    description="Filter insults under the 'fat' category.",
                )
            ],
        ),
    ],
    responses={
        200: CategorySerializer(many=True),
        404: {
            "description": "Category not found or no insults available in the specified category."
        },
    },
)
class InsultsCategoriesListView(PaginateByMaxMixin, ListAPIView):
    """
    Retrieve insults filtered by category.

    This view provides insults that belong to a specific category, filtered by the
    `category` path parameter. If the category is invalid or no insults exist in the
    specified category, an empty result set is returned.
    """

    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "category"
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]
    max_paginate_by = 100

    def get_queryset(self):
        category = self.kwargs.get("category", "").lower()
        available_categories = {y.lower(): x for x, y in Insult.CATEGORY.choices}

        if category not in available_categories:
            return Insult.objects.none()

        return Insult.objects.filter(
            status="A", category=available_categories[category]
        )


# @extend_schema_view(
#     retrieve=extend_schema(
#         tags=["Insults"],
#         operation_id="retrieve_specific_insult",
#         description="Retrieve a specific insult created by the authenticated user.",
#         responses={
#             200: InsultSerializer,
#             404: OpenApiResponse(
#                 description="The requested insult does not exist."
#             ),
#         },
#     ),
#     update=extend_schema(
#         tags=["Insults"],
#         description="Update a specific insult created by the authenticated user.",
#         responses={
#             200: InsultSerializer,
#             400: OpenApiResponse(
#                 description="Bad request. The provided data is invalid."
#             ),
#             403: OpenApiResponse(
#                 description="The requested insult does not exist or does not belong to the user."
#             ),
#         },
#     ),
#     partial_update=extend_schema(
#         tags=["Insults"],
#         description="Partially update a specific insult created by the authenticated user.",
#         responses={
#             200: InsultSerializer,
#             400: OpenApiResponse(
#                 description="Bad request. The provided data is invalid."
#             ),
#             403: OpenApiResponse(
#                 description="The requested insult does not exist or does not belong to the user."
#             ),
#         },
#     ),
#     destroy=extend_schema(
#         tags=["Insults"],
#         description="Delete a specific insult created by the authenticated user.",
#         responses={
#             204: OpenApiResponse(description="The insult was successfully deleted."),
#             403: OpenApiResponse(
#                 description="The requested insult does not exist or does not belong to the user."
#             ),
#         },
#     )
# )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an insult to edit/delete it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.added_by == request.user


class InsultSingleItem(RetrieveUpdateDestroyAPIView):
    serializer_class = InsultSerializer
    lookup_field = "id"
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter

    def get_permissions(self):
        if self.request.method == "GET":
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Filter queryset based on user authentication and ownership:
        - Authenticated owners can see their insults in any status
        - Others can only see active status insults
        """
        base_queryset = Insult.objects.all()

        if self.request.user.is_authenticated:
            # Show all statuses for owner's insults, only active for others
            return base_queryset.filter(
                Q(added_by=self.request.user)  # All statuses for owner
                | Q(status=Insult.STATUS.ACTIVE)  # Only active for others
            )

        # Unauthenticated users only see active insults
        return base_queryset.filter(status=Insult.STATUS.ACTIVE)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Insult ID",
            )
        ],
        tags=["insults"],
        description="Retrieve an insult. Returns active insults for all users, owners can see their insults in any status.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Insult ID",
            )
        ],
        tags=["insults"],
        description="Update an insult. Only the owner can perform this action.",
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="Insult ID",
            )
        ],
        tags=["insults"],
        description="Delete an insult. Only the owner can perform this action.",
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def handle_exception(self, exc):
        """
        Custom exception handling to provide better error messages
        """
        if isinstance(exc, Http404):
            if self.request.user.is_authenticated:
                detail = "Insult not found or you don't have permission to view it"
            else:
                detail = "Insult not found or is not currently active"
            return Response({"detail": detail}, status=status.HTTP_404_NOT_FOUND)
        return super().handle_exception(exc)
