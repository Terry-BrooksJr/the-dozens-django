import django_filters
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from loguru import logger
from rest_framework import status
import rest_framework.decorators
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    CreateAPIView,
)
from django.core.cache import cache

from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import PaginateByMaxMixin

from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import (
    BaseInsultSerializer,
    CategorySerializer,
    CreateInsultSerializer,
    OptimizedInsultSerializer,
)
from common.performance import CachedResponseMixin


@extend_schema_view(
    get=extend_schema(
        operation_id="list_insults_by_cat",
        tags=["Insults"],
        auth=[],
        description=(
            "List insults for a specific category. Returns active insults for all users; "
            "if authenticated, the user also sees their own insults regardless of status."
        ),
        parameters=[
            OpenApiParameter(
                name="category_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Category key or name (e.g., 'P' or 'Poor').",
            )
        ],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="Successful response returning insults for the requested category.",
            ),
            404: OpenApiResponse(
                description="No insults found for the given category."
            ),
        },
    )
)
class InsultByCategoryEndpoint(
    CachedResponseMixin, PaginateByMaxMixin, RetrieveModelMixin, ListAPIView
):
    lookup_field = "category"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    cache_models = [InsultCategory]
    bulk_select_related = ["added_by", "category"]

    def get_queryset(self):
        # Prevent schema generation from evaluating real queries
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        logger.debug(f"kwargs seen by view: {self.kwargs}")
        category = self.kwargs["category_name"]
        user_content = None
        normalized_category = BaseInsultSerializer.validate_category(category)
        logger.debug(normalized_category)
        if self.request.user.is_authenticated:
            user_content = Insult.objects.filter(
                category=normalized_category["category_key"], added_by=self.request.user
            )
        queryset = Insult.objects.filter(
            status=Insult.STATUS.ACTIVE, category=normalized_category["category_key"]
        )
        return queryset.union(user_content) if user_content is not None else queryset


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        auth=[],
        operation_id="retrieve_insult",
        description="Retrieve a specific insult by ID.",
        parameters=[
            OpenApiParameter(
                name="reference_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "reference_id": 1,
                            "content": "Yo momma is so fat... she rolled over 4 quarters and made a dollar!'",
                            "category": "Fat",
                            "status": "Active",
                            "nsfw": False,
                            "added_by": "Mike R.",
                            "added_on": "2 years ago",
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
    put=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="update_insult",
        description="Update an existing insult. Only the owner can perform this action.",
        parameters=[
            OpenApiParameter(
                name="reference_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        request=OptimizedInsultSerializer,
        responses={
            200: OptimizedInsultSerializer,
            400: OpenApiResponse(description="Invalid input"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied - not the owner"),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
    patch=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="partial_update_insult",
        description="Partial Update to existing insult. Only the owner can perform this action.",
        parameters=[
            OpenApiParameter(
                name="reference_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="A unique integer value identifying this insult",
            )
        ],
        request=OptimizedInsultSerializer,
        responses={
            200: OptimizedInsultSerializer,
            400: OpenApiResponse(description="Invalid input"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied - not the owner"),
            404: OpenApiResponse(description="Insult not found"),
        },
    ),
    delete=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="delete_insult",
        description="Delete an existing insult. Only the owner can perform this action.",
        parameters=[
            OpenApiParameter(
                name="reference_id",
                type=OpenApiTypes.STR,
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
class InsultDetailsEndpoints(
    PaginateByMaxMixin, CreateModelMixin, RetrieveUpdateDestroyAPIView
):
    lookup_field = "reference_id"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    cache_models = [InsultCategory, InsultReview]
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]
    filter_backends = [DjangoFilterBackend]

    bulk_cache_timeout = 1800
    cache_invalidation_patterns = [
        "Insult:*",
        "bulk:insult*",
        "categories:*",
        "users:*:insults*",
    ]
    filter_backends = (DjangoFilterBackend,)  # pyrefly: ignore
    filterset_class = InsultFilter

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        else:
            return [IsOwnerOrReadOnly()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .all()
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        operation_id="list_insults",
        auth=[],
        description="List all insults. Returns active insults for all users, authenticated users can see their own insults in any status.",
        parameters=[
            OpenApiParameter(
                name="nsfw",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter explicit content. `true` returns only NSFW insults; `false` returns only SFW. If omitted, both are returned.",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Successful 200 response returning a paginated list of insults. The payload includes a top‑level `count` and a `results` array of insult objects. Supports optional filtering via `category` and `nsfw` query parameters.",
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        name="Success Response - Unfiltered (NSFW) and Uncategorized (Category)",
                        description="Example 200 response payload showing a list of insults without NSFW filtering applied and without any category restrictions. This represents the default unfiltered response.",
                        value={
                            "count": 133,
                            "results": [
                                {
                                    "reference_id": "SNICKER_NDc4",
                                    "content": "Yo momma is so ugly... when they took her to the beautician it took 12 hours for a quote!",
                                    "category": "Ugly",
                                    "nsfw": False,
                                    "added_by": "John D.",
                                    "added_on": "2 days ago",
                                },
                                {
                                    "reference_id": "CACKLE_NDQ5",
                                    "content": "Yo momma is so fat... when she dives into the ocean, there is a tsunami-warning!'",
                                    "category": "Fat",
                                    "nsfw": False,
                                    "added_by": "Linda p.",
                                    "added_on": "12 days ago",
                                },
                                {
                                    "reference_id": "CHUCKLE_NDUz",
                                    "content": "Yo momma is so old her driver's license is written with Roman numerals.",
                                    "category": "Old",
                                    "nsfw": False,
                                    "added_by": "John D.",
                                    "added_on": "4 Weeks Ago",
                                },
                            ],
                        },
                    ),
                    OpenApiExample(
                        name="Success Response - categorized (Category) & filtered(NSFW)",
                        description="Example 200 response payload filtered to show only NSFW insults in the 'Poor' category. Demonstrates combined filtering via `category=P` and `nsfw=true`.",
                        value={
                            "count": 1,
                            "results": [
                                {
                                    "reference_id": "CACKLE_NDY2",
                                    "content": "Yo momma is so poor... she accepts food stamps for sex!",
                                    "category": "Poor",
                                    "nsfw": True,
                                    "added_by": "John D.",
                                    "added_on": "2 days ago",
                                }
                            ],
                        },
                    ),
                ],
            ),
            404: OpenApiResponse(
                description="No insults found matching the provided filters or resource not available.",
                examples=[
                    OpenApiExample(
                        name="No Insults Found",
                        description="Example 404 response when no insults match the provided filters (e.g., `category=XYZ` with `nsfw=true`).",
                        value={
                            "detail": "No insults found matching the provided filters or resource not available."
                        },
                    )
                ],
            ),
        },
    )
)
class InsultListView(CachedResponseMixin, PaginateByMaxMixin, ListAPIView):
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    cache_models = [InsultCategory, InsultReview]
    permission_classes = [AllowAny]
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]
    bulk_cache_timeout = 1800
    filter_backends = [DjangoFilterBackend]
    cache_invalidation_patterns = [
        "Insult:*",
        "bulk:insult*",
        "categories:*",
        "users:*:insults*",
    ]

    def get_queryset(self):
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .exclude(category__category_key__in=["TEST", "X"])
        )
        # Build cache key with all relevant filters

    def list(self, request, *args, **kwargs):
        # Check for category query parameter early and reject with 400
        if request.GET.get("category_name") or request.GET.get("category"):
            return Response(
                {"Error": "Please Use the `api/insults/<category>` endpoint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user if request.user.is_authenticated else None
        filters = {
            "category": request.GET.get("category"),
            "status": request.GET.get("status"),
            "nsfw": request.GET.get("nsfw"),
            "page": request.GET.get("page", "1"),
            "page_size": request.GET.get("page_size", "20"),
            "user_id": getattr(user, "id", None),
        }

        cache_key = self.get_cache_key("bulk_list", **filters)

        def get_filtered_queryset():
            """Build the filtered queryset."""
            queryset = self.get_queryset()

            # Apply filters
            if filters["category"]:
                queryset = queryset.filter(category__category_key=filters["category"])
            if filters["status"]:
                queryset = queryset.filter(status=filters["status"])
            if filters["nsfw"] is not None:
                nsfw_bool = filters["nsfw"].lower() in ("true", "1", "yes")
                queryset = queryset.filter(nsfw=nsfw_bool)
            if filters["user_id"]:
                user_qs = queryset.filter(
                    added_by_id=filters["user_id"]
                )  # include user's own regardless of status
                active_qs = queryset.filter(status=Insult.STATUS.ACTIVE)
                return user_qs.union(active_qs).order_by("-added_on")
            return queryset.filter(status=Insult.STATUS.ACTIVE).order_by("-added_on")
            # Get cached or fresh data with optimizations

        queryset, extra_data = self.get_cached_bulk_data(
            cache_key, get_filtered_queryset, timeout=self.bulk_cache_timeout
        )
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data)
            response_data.data.update(extra_data)  # Add metadata
            return response_data

        # Non-paginated response
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {"count": len(serializer.data), "results": serializer.data, **extra_data}
        )


class RandomInsultView(GenericAPIView):
    serializer_class = OptimizedInsultSerializer
    permission_classes = [AllowAny]

    @method_decorator(never_cache)
    @extend_schema(
        tags=["Insults"],
        operation_id="get_random_insult",
        auth=[],
        responses=OptimizedInsultSerializer,
        request=None,
        parameters=[
            OpenApiParameter(
                name="nsfw",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter explicit content. `true` returns only NSFW insults; `false` returns only SFW. If omitted, both are returned.",
                required=False,
            ),
            OpenApiParameter(
                name="category_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter insult to a category such as fat, poor, etc. ",
                required=False,
            ),
        ],
    )
    def get(self, request):
        """Get a random insult."""
        queryset = (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("?")
            .all()
        )

        # Filter by explicity level (NSFW) if provided
        nsfw_param = request.query_params.get("nsfw")
        if nsfw_param is not None:
            nsfw = nsfw_param.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(nsfw=nsfw)
        # Filter by category if provided

        if category := request.query_params.get("category"):
            category = BaseInsultSerializer.validate_category(category)
            queryset = queryset.filter(category=category["category_key"])

        if not queryset.exists():
            return Response(
                {"detail": "No insults found matching the criteria."}, status=404
            )

        random_insult = queryset.order_by("?").first()
        serializer = OptimizedInsultSerializer(random_insult)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Insults"],
        auth=[],
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
                            "available_categories": [
                                {"p": {"category_name": "poor", "insult_count": 134}},
                                {"f": {"category_name": "fat", "insult_count": 80}},
                                # ...
                            ],
                        },
                    )
                ],
            )
        },
    )
)
class ListCategoryView(CachedResponseMixin, GenericAPIView):
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return InsultCategory.objects.exclude(category_key__in=["TEST", "X"]).values()

    def get(self, request):
        qs = self.get_queryset()
        serializer = CategorySerializer(qs)
        return Response(
            {
                "help_text": "Here is a list of all available Insult Categories. The API will accept either values and is case insensitive. Ex: `/api/insults/p` and `api/insults/POOR` will yield the same result",
                "catergories": serializer.data,
            }
        )


class CreateInsultView(CreateAPIView):
    serializer_class = CreateInsultSerializer
    permission_classes = [IsAuthenticated]
