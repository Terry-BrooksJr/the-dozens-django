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
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
import rest_framework.decorators
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    CreateAPIView,
)
from django.contrib.auth import get_user_model

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

User = get_user_model()


@extend_schema_view(
    get=extend_schema(
        operation_id="list_insults_by_cat",
        tags=["Insult Categories"],
        auth=[],
        summary=(
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
    """
    ## List Insults by Category

    ### URL
       <pre> GET /api/insults/<category_name> </pre>

   ### Description
   
      > Returns a list of insults for a given category. Unauthenticated callers receive only
      > ACTIVE insults. If authenticated, the caller also sees their own insults in the same
      >  category regardless of status. Category can be provided as a key (e.g., "P") or a
      >  name (e.g., "poor").

    ### Authentication
    
       > Optional for reads. Authentication expands visibility to include the caller's own
        non‑ACTIVE items.

    ### Path Parameters
    
       * __category_name__ (string):   
            > Category key or name. Case‑insensitive.   
            > Examples: "P",
            > "Poor".

    ### Query Parameters
    
       >  Standard list pagination parameters are supported via the global pagination settings.

    ### Responses
    
       *  200 OK: JSON array of insult objects.
       *  404 Not Found: No insults found for the specified category.

    ### Example
        GET /api/insults/poor

        {
            "count": 2,
            "results": [
                {
                    "reference_id": "SNICKER_NDc4",
                    "content": "Yo momma is so poor…",
                    "category": "Poor",
                    "nsfw": false,
                    "added_by": "John D.",
                    "added_on": "2 days ago"
                }
            ]
        }
    """
    lookup_field = "category"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    filter_backends = [DjangoFilterBackend]
    cache_models = [InsultCategory]
    bulk_select_related = ["added_by", "category"]

    def get_queryset(self):
        # Prevent schema generation from evaluating real queries
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        logger.debug(f"kwargs seen by view: {self.kwargs}")
        category = self.kwargs["category_name"]
        user_content = None
        normalized_category = BaseInsultSerializer.resolve_category(category)
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
        tags=["Insults "],
        auth=[],
        operation_id="retrieve_insult",
        summary="Retrieve a specific insult by ID.",
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
        summary="Update an existing insult. Only the owner can perform this action.",
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
        summary="Partial Update to existing insult. Only the owner can perform this action.",
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
        summary="Delete an existing insult. Only the owner can perform this action.",
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
class InsultDetailsEndpoint(
    PaginateByMaxMixin, CreateModelMixin, RetrieveUpdateDestroyAPIView
):
    """
    Consumer API: Retrieve / Update / Delete a Single Insult

    URLs
        GET    /api/insult/<reference_id>
        PUT    /api/insult/<reference_id>
        PATCH  /api/insult/<reference_id>
        DELETE /api/insult/<reference_id>

    Description
        Retrieves a single insult by its `reference_id`. Owners may update or delete their
        own insults. Non‑owners can only read.

    Authentication
        Required for PUT, PATCH, DELETE via Token.
        Optional for GET.

    Path Parameters
        reference_id (string): Prefixed Base64 identifier, for example
            "SNICKER_NDc4".

    Responses
        200 OK: Insult object (for GET/PUT/PATCH).
        204 No Content: Successful deletion.
        401 Unauthorized / 403 Forbidden: Missing or insufficient permissions.
        404 Not Found: No insult with the given `reference_id`.

    Notes
        The serializer optimizes related fields and prefetches reports. List endpoints are
        better for bulk access; this route is for single‑item CRUD.
    """
    lookup_field = "reference_id"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    authentication_classes = [TokenAuthentication]
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
        summary="List all insults. Returns active insults for all users, authenticated users can see their own insults in any status.",
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
class InsultListEndpoint(CachedResponseMixin, PaginateByMaxMixin, ListAPIView):
    """
    Consumer API: List All Insults

    URL
        GET /api/insults

    Description
        Returns a paginated list of ACTIVE insults across all categories. If the caller is
        authenticated, their own insults are included regardless of status. Categories with
        keys `TEST` and `X` are excluded from public listing.

    Authentication
        Optional. Authentication broadens visibility to include the caller's own items.

    Query Parameters
        nsfw (bool, optional): Filter by explicit content. `true` returns only NSFW; `false`
            returns only SFW. Omit to return both.
        page (int, optional): Page number (default 1).
        page_size (int, optional): Items per page (default 20 unless configured otherwise).

    Responses
        200 OK: Paginated list with `count` and `results`.
        400 Bad Request: If a category is passed here (use /api/insults/<category> instead).

    Example
        GET /api/insults?nsfw=false&page=1&page_size=20

        {
            "count": 133,
            "results": [ { "reference_id": "…", "content": "…", "category": "Ugly", … } ]
        }
    """
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


class RandomInsultEndpoint(GenericAPIView):
    """
    Consumer API: Get a Random Insult

    URL
        GET /api/insults/random

    Description
        Returns a single random insult. Supports optional filtering by NSFW status and
        category.

    Query Parameters
        nsfw (bool, optional): Filter for explicit content (`true` or `false`).
        category (string, optional): Category key or name (e.g., "P", "poor").

    Responses
        200 OK: Insult object.
        404 Not Found: No insults match the provided filters.

    Example
        GET /api/insults/random?nsfw=false&category=ugly
    """
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
            category = BaseInsultSerializer.resolve_category(category)
            queryset = queryset.filter(category=category["category_key"])

        if not queryset.exists():
            return Response(
                {"detail": "No insults found matching the criteria."}, status=404
            )

        random_insult = queryset.order_by("?").first()
        serializer = OptimizedInsultSerializer(random_insult)
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        tags=["Insult Categories"],
        auth=[],
        operation_id="list_categories",
        summary="List all available insult categories",
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
class ListCategoryEndpoint(CachedResponseMixin, GenericAPIView):
    """
    Consumer API: List All Categories

    URL
        GET /api/categories

    Description
        Returns all available insult categories intended for public use. Internal or excluded
        categories (e.g., keys `TEST` and `X`) are omitted. Each category includes a human‑
        readable name, description, and a count of ACTIVE insults currently assigned.

    Authentication
        Not required.

    Responses
        200 OK: JSON object with a `help_text` string and a `categories` mapping keyed by
            `category_key`. Each entry contains `name`, `description`, and `count`.

    Example
        {
            "help_text": "Here is a list of all available Insult Categories…",
            "categories": {
                "SRT": {"name": "Short", "description": "Height jokes …", "count": 13},
                "P":   {"name": "Poor",  "description": "Money/means jokes …", "count": 42}
            }
        }

    Notes
        The API accepts either the category key or name (case‑insensitive) in endpoints that
        filter by category.
    """

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """Retrieve all insult categories except for test and excluded categories.

        Returns a queryset of insult categories, omitting those with keys 'TEST' and 'X'.

        Returns:
            QuerySet: A queryset of insult categories excluding 'TEST' and 'X'.
        """
        return InsultCategory.objects.exclude(category_key__in=["TEST", "X"])

    def get(self, request):
        """Return a list of all available insult categories.

        Provides a response containing all insult categories, including a help text for API usage.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: A response object containing the list of categories and help text.
        """
        qs = self.get_queryset()
        serializer = CategorySerializer(qs, many=True)
        logger.debug(serializer.data)
        data = {
            row["category_key"]: {
                "name": row["name"],
                "description": row["description"],
                "count": row["count"],
            }
            for row in serializer.data
        }
        return Response(
            {
                "help_text": "Here is a list of all available Insult Categories. The API will accept either values and is case insensitive. Ex: `/api/insults/p` and `api/insults/POOR` will yield the same result",
                "categories": data,
            }
        )


@extend_schema_view(
    post=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="create-insult",
        request=CreateInsultSerializer,
        summary="Create New Insult",
        responses={
            201: OpenApiResponse(
                description="Successful POST request",
                examples=[
                    OpenApiExample(
                        "Categories List",
                        value={
                            "help_text": "Here is a list of all available Insult Categories. The API will accept either values and is case insensitive. Ex: `/api/insults/p` and `api/insults/POOR` will yield the same result",
                            "categories": {
                                "SRT": {
                                    "name": "Short",
                                    "description": "Height jokes about being unusually small, undersized, or comically tiny.",
                                    "count": 13,
                                },
                                "DO": {
                                    "name": "daddy - old",
                                    "description": "Insults aimed at a father figure’s age or being past one’s prime.",
                                    "count": 1,
                                },
                                "DS": {
                                    "name": "daddy - stupid",
                                    "description": "Insults aimed at a father figure’s intellect or clueless behavior.",
                                    "count": 2,
                                },
                                # ...
                            },
                        },
                    )
                ],
            )
        },
    )
)
class CreateInsultEndpoint(CreateAPIView):
    """
    Consumer API: Create a New Insult

    URL
        POST /api/insults

    Description
        Creates a new insult owned by the authenticated caller. Newly created insults default
        to `Pending` status until approved. The `reference_id` is generated automatically.

    Authentication
        Required via Token.

    Request Body
        JSON matching the `CreateInsultSerializer` fields (content, category, nsfw, etc.).

    Responses
        201 Created: Insult object, including generated `reference_id`.
        400 Bad Request: Invalid input.
        401 Unauthorized: Missing/invalid token.

    Notes
        The endpoint records the submitting user as `added_by`.
    """
    serializer_class = CreateInsultSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Populate owner from the authenticated user and let CreateAPIView handle the rest."""
        serializer.save(added_by=self.request.user)
