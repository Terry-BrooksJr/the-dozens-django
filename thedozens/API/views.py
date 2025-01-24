import random
from enum import Enum

from API.filters import InsultFilter

from API.models import Insult
from API.serializers import (
    InsultsCategorySerializer,
    InsultSerializer,
    MyInsultSerializer,
    serializers
)
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer, OpenApiResponse, extend_schema_view, OpenApiExample
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, status
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

@extend_schema_view(
    retrieve=extend_schema(
        tags=["Insults"],
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
                                {"id": 2, "content": "You're debugging your own mess again?"},
                                {"id": 3, "content": "Your CSS skills are truly groundbreaking—breaking everything!"},
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

class MyInsultsViewSet(ModelViewSet):
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
        insult = self.get_object()
        if insult.added_by != request.user:
            return Response(
                {"error": "You cannot delete insults that you did not submit"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        insult = self.get_object()
        if insult.added_by != request.user:
            return Response(
                {"error": "You cannot update insults that you did not submit"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class InsultsCategoriesViewSet(ReadOnlyModelViewSet):
    """
    InsultsCategoriesViewSet is a read-only viewset for retrieving insults based on selected categories. It filters insults by their status and category, ensuring that only active insults in the specified category are returned.

    This viewset allows users to query insults by providing a category parameter. If the specified category is not valid, it returns an empty queryset, ensuring that only relevant insults are accessible.

    Args:
        request: The HTTP request object.

    Returns:
        QuerySet: A queryset of active insults filtered by the specified category, or an empty queryset if the category is invalid.

    Examples:
        To retrieve insults in a specific category:
            GET /api/insults/categories/?category=funny
    """

    available_categories = {y: x for x, y in Insult.CATEGORY.choices}
    serializer_class = InsultSerializer
    filterset_class = InsultFilter

    @extend_schema(
        responses={
            200: inline_serializer(
                name="Available Joke categories",
                fields={
                    "help_text": OpenApiTypes.STR,
                    "available_categories": OpenApiTypes.OBJECT,
                },
            ),
        }
    )
    @action(
        detail=False,
        methods=["GET"],
    )
    def list_available_categories(self, request):
        resp = {
            "help_text": "Please pass the values of the keys to filterable API endpoint",
            "available_categories": self.available_categories,
        }
        return Response(resp, status=status.HTTP_200_OK)

@extend_schema(
    tags=["Insults"],
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
                    description="Filter insults under the 'fat' category."
                )
            ]
        ),
    ],
    responses={
        200: InsultsCategorySerializer(many=True),
        404: {"description": "Category not found or no insults available in the specified category."},
    }
)
class InsultsCategoriesListView(ListAPIView):
    """
    Retrieve insults filtered by category.

    This view provides insults that belong to a specific category, filtered by the
    `category` path parameter. If the category is invalid or no insults exist in the
    specified category, an empty result set is returned.
    """

    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "category"
    serializer_class = InsultsCategorySerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        category = self.kwargs.get("category", "").lower()
        available_categories = {y.lower(): x for x, y in Insult.CATEGORY.choices}

        if category not in available_categories:
            return Insult.objects.none()

        return Insult.objects.filter(
            status="A",
            category=available_categories[category]
        )
    
class InsultSingleItem(RetrieveAPIView):
    queryset = Insult.objects.all()
    lookup_field = "id"
    serializer_class = InsultSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    permission_classes = [AllowAny]


@extend_schema_view(
    retrieve=extend_schema(
        tags=["My Insults"],
        description="Retrieve a specific insult created by the authenticated user.",
        responses={
            200: InsultSerializer,
            403: OpenApiResponse(
                description="The requested insult does not exist or does not belong to the user."
            ),
        },
    ),
    update=extend_schema(
        tags=["My Insults"],
        description="Update a specific insult created by the authenticated user.",
        responses={
            200: InsultSerializer,
            400: OpenApiResponse(
                description="Bad request. The provided data is invalid."
            ),
            403: OpenApiResponse(
                description="The requested insult does not exist or does not belong to the user."
            ),
        },
    ),
    partial_update=extend_schema(
        tags=["My Insults"],
        description="Partially update a specific insult created by the authenticated user.",
        responses={
            200: InsultSerializer,
            400: OpenApiResponse(
                description="Bad request. The provided data is invalid."
            ),
            403: OpenApiResponse(
                description= "The requested insult does not exist or does not belong to the user."
            ),
        },
    ),
    destroy=extend_schema(
        tags=["My Insults"],
        description="Delete a specific insult created by the authenticated user.",
        responses={
            204: OpenApiResponse(
                description="The insult was successfully deleted."
            ),
            403: OpenApiResponse(
                description="The requested insult does not exist or does not belong to the user."
            ),
        },
    ),
)
class MyInsultsView(RetrieveUpdateDestroyAPIView):
    """
    Manage insults created by the currently authenticated user.

    Allows retrieving, updating, partially updating, or deleting a specific insult.
    """

    serializer_class = InsultSerializer
    filterset_class = InsultFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Returns a queryset of insults created by the authenticated user.

        If the user is anonymous, returns an empty queryset.
        """
        user = self.request.user
        if not user.is_anonymous:
            return Insult.objects.filter(added_by=user)
        return Insult.objects.none()
    
    def update(self, request, *args, **kwargs):
        user = self.request.user
        joke = self.get_object()
        if user != joke.added_by:
            return Response(data=f"Insult {joke.insult_id} does not belong to user {user.username},",. status=40344444O444)