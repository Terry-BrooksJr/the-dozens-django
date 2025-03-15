import random

from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import CategorySerializer, InsultSerializer
from common.cache import CachedResponseMixin
from common.utils.helpers import _check_ownership
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import PaginateByMaxMixin


@extend_schema_view(
    list=extend_schema(
        tags=["Insults"],
        operation_id="list_insults",
        description="List all insults. Returns active insults for all users, authenticated users can see their own insults in any status.",
        parameters=[
            OpenApiParameter(
                name="category",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter insults by category",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by insult status (authenticated users only)",
                required=False,
                enum=["active", "pending", "rejected"],
            ),
            OpenApiParameter(
                name="added_on",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by date added (YYYY-MM-DD)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=InsultSerializer(many=True),
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value=[
                            {
                                "id": 1,
                                "content": "Your code runs slower than a turtle in molasses",
                                "category": "Programming",
                                "status": "Active",
                                "nsfw": False,
                                "added_by": "John D.",
                                "added_on": "2 days ago",
                            }
                        ],
                    )
                ],
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided"
            ),
        },
    ),
    retrieve=extend_schema(
        tags=["Insults"],
        operation_id="retrieve_insult",
        description="Retrieve a specific insult by ID.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        responses={
            200: OpenApiResponse(
                response=InsultSerializer,
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "id": 1,
                            "content": "Your code runs slower than a turtle in molasses",
                            "category": "Programming",
                            "status": "Active",
                            "nsfw": False,
                            "added_by": "John D.",
                            "added_on": "2 days ago",
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
    create=extend_schema(
        tags=["Insults"],
        operation_id="create_insult",
        description="Create a new insult. Authentication required.",
        request=InsultSerializer,
        responses={
            201: OpenApiResponse(
                response=InsultSerializer,
                examples=[
                    OpenApiExample(
                        "Created Response",
                        value={
                            "id": 1,
                            "content": "Your code has more bugs than a roach motel",
                            "category": "Programming",
                            "status": "Pending",
                            "nsfw": False,
                            "added_by": "John D.",
                            "added_on": "just now",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid input"),
            401: OpenApiResponse(description="Authentication required"),
        },
    ),
    update=extend_schema(
        tags=["Insults"],
        operation_id="update_insult",
        description="Update an existing insult. Only the owner can perform this action.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        request=InsultSerializer,
        responses={
            200: InsultSerializer,
            400: OpenApiResponse(description="Invalid input"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied - not the owner"),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
    destroy=extend_schema(
        tags=["Insults"],
        operation_id="delete_insult",
        description="Delete an existing insult. Only the owner can perform this action.",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        responses={
            204: OpenApiResponse(description="Insult deleted successfully"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied - not the owner"),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
)
class InsultViewSet(PaginateByMaxMixin, CachedResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing insults. Provides CRUD operations and additional actions.

    Endpoints:
    - GET /api/insults/ - List all insults (filtered by user if authenticated)
    - POST /api/insults/ - Create a new insult
    - GET /api/insults/{id}/ - Retrieve a specific insult
    - PUT /api/insults/{id}/ - Update an insult (owner only)
    - DELETE /api/insults/{id}/ - Delete an insult (owner only)
    - GET /api/insults/random/ - Get a random insult
    """

    serializer_class = InsultSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "id"
    primary_model = Insult

    def get_permissions(self):
        if self.action in ["list", "retrieve", "random"]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        base_queryset = Insult.objects.all()

        if self.action == "list" and self.request.user.is_authenticated:
            return base_queryset.filter(added_by=self.request.user)

        if self.request.user.is_authenticated:
            return base_queryset.filter(
                Q(added_by=self.request.user) | Q(status=Insult.STATUS.ACTIVE)
            )

        return base_queryset.filter(status=Insult.STATUS.ACTIVE)

    def perform_update(self, serializer):
        obj = self.get_object()
        _check_ownership(obj, self.request.user)
        serializer.save()

    def perform_destroy(self, instance):
        _check_ownership(instance, self.request.user)
        instance.delete()

    @extend_schema(
        tags=["Insults"],
        operation_id="get_random_insult",
        description="Retrieve a random insult from the database.",
        parameters=[
            OpenApiParameter(
                name="nsfw",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Whether to include NSFW insults",
                required=False,
            ),
            OpenApiParameter(
                name="category",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Category to filter insults by",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=InsultSerializer,
                examples=[
                    OpenApiExample(
                        "Random Insult",
                        value={
                            "id": 42,
                            "content": "Your code documentation is like a unicorn - mythical and non-existent",
                            "category": "Programming",
                            "status": "Active",
                            "nsfw": False,
                            "added_by": "Jane D.",
                            "added_on": "1 month ago",
                        },
                    )
                ],
            ),
            404: OpenApiResponse(
                description="No insults found matching the criteria.",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={"detail": "No insults found matching the criteria."},
                    )
                ],
            ),
        },
    )
    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def random(self, request):
        """Get a random insult."""
        queryset = self.get_queryset()
    
    # Filter by explicity level (NSFW) if provided
        nsfw_param = request.query_params.get("nsfw")
        if nsfw_param is not None:
            nsfw = nsfw_param.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(nsfw=nsfw)
        # Filter by category if provided

        if category := request.query_params.get("category"):
            queryset = queryset.filter(category=category)

        if not queryset.exists():
            return Response(
                {"detail": "No insults found matching the criteria."}, status=404
            )

        random_insult = random.choice(queryset)
        serializer = self.get_serializer(random_insult)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Insults"],
        operation_id="list_categories",
        description="List all available insult categories",
        responses={
            200: OpenApiResponse(
                description="List of available categories",
                examples=[
                    OpenApiExample(
                        "Categories List",
                        value={
                            "help_text": "Available categories",
                            "available_categories": {
                                "F": "Fat",
                                "S": "Stupid",
                                "P": "Poor",
                            },
                        },
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["Categories"],
        operation_id="retrieve_category",
        description="Retrieve a specific category by key",
        parameters=[
            OpenApiParameter(
                name="category_key",
                type=str,
                location=OpenApiParameter.PATH,
                description="Category key",
            )
        ],
        responses={
            200: CategorySerializer,
        },
    ),
)
class CategoryViewSet(CachedResponseMixin, PaginateByMaxMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing insult categories. Provides read-only operations.

    Endpoints:
    - GET /api/categories/ - List all categories
    - GET /api/categories/{category_key}/ - Retrieve a specific category
    - GET /api/categories/{category_key}/insults/ - List all insults in a category
    """

    queryset = InsultCategory.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    primary_model = InsultCategory
    max_paginate_by = 100

    def list(self, request, *args, **kwargs):
        """Override list to return categories in the desired format."""
        available_categories = {
            cat['category_key']: cat['name'] for cat in self.get_queryset().values("category_key", "name")
        }

        return Response(
            {
                "help_text": "Available categories",
                "available_categories": available_categories,
            }
        )

    @extend_schema(
        tags=["Insults"],
        operation_id="list_category_insults",
        description="Retrieve insults for a specific category",
        parameters=[
            OpenApiParameter(
                name="category",
                type=str,
                location=OpenApiParameter.PATH,
                description="Category key to filter insults by",
                required=True,
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by status (authenticated users only)",
                required=False,
                enum=["active", "pending", "rejected"],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=InsultSerializer(many=True),
                examples=[
                    OpenApiExample(
                        "Category Insults",
                        value=[
                            {
                                "id": 1,
                                "content": "Your code is like a black hole - it sucks up resources and nothing escapes",
                                "category": "Programming",
                                "status": "Active",
                                "nsfw": False,
                                "added_by": "John D.",
                                "added_on": "3 days ago",
                            }
                        ],
                    )
                ],
            ),
            404: OpenApiResponse(
                description="Category not found",
                examples=[
                    OpenApiExample("Not Found", value={"detail": "Category not found"})
                ],
            ),
        },
    )
    @action(detail=True, methods=["get"])
    def insults(self, request, pk=None):
        """Get all insults for a specific category."""
        category = self.get_object()

        if request.user.is_authenticated:
            user_insults = Insult.objects.filter(
                added_by=request.user, category=category
            )
            other_insults = Insult.objects.exclude(added_by=request.user).filter(
                status=Insult.STATUS.ACTIVE, category=category
            )
            queryset = user_insults.union(other_insults)
        else:
            queryset = Insult.objects.filter(
                status=Insult.STATUS.ACTIVE, category=category
            )

        serializer = InsultSerializer(queryset, many=True)
        return Response(serializer.data)
