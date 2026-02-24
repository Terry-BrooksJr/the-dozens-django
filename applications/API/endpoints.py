"""
# applications.API.endpoints

API endpoints for managing insults, categories, and themes.

- Provides CRUD operations for insults and categories  
- Supports filtering, random retrieval, and category/theme discovery
"""

from urllib.parse import urlencode
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import EmptyResultSet
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.db.models import QuerySet
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
from applications.API.authentication import FlexibleTokenAuthentication
from rest_framework.generics import (
    CreateAPIView,
    GenericAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import PaginateByMaxMixin

from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview, Theme
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import (
    BaseInsultSerializer,
    CategorySerializer,
    CreateInsultSerializer,
    OptimizedInsultSerializer,
)
from applications.API.errors import (
    StandardErrorResponses,
    get_insult_crud_responses,
    get_category_list_responses,
    get_public_list_responses,
)
from common.performance import CachedResponseMixin

User = get_user_model()


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        operation_id="list_insults_by_category",
        auth=[],
        summary="List insults by category",
        description="Retrieve paginated insults filtered by category. Authenticated users see their own insults plus all active insults; unauthenticated users see only active insults. Supports both category keys (e.g., 'P') and names (e.g., 'Poor').",
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
                description="Successfully retrieved paginated list of category-filtered insults",
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
            **get_public_list_responses(),
        },
    )
)
class InsultByCategoryEndpoint(CachedResponseMixin, PaginateByMaxMixin, ListAPIView):
    """
    # Insults by Category

    API endpoint for retrieving insults filtered by category.

    - Supports category keys (e.g., `P`) and names (e.g., `Poor`) in a case‑insensitive manner
    - Authenticated users see **their own insults** plus all active insults
    - Unauthenticated users see **only active insults**

    ## Endpoint

    - `GET /api/insults/<category_name>`

    ## Query Parameters

    - `nsfw` *(bool, optional)*: Filter explicit content.
      - `true` → only NSFW insults
      - `false` → only SFW insults
      - omitted → both are returned
    - `page` *(int, optional)*: Page number for pagination
    - `page_size` *(int, optional)*: Number of items per page
    """

    lookup_field = "category"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    filter_backends = [DjangoFilterBackend]  # pyrefly: ignore
    cache_models = [InsultCategory]
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]
    bulk_cache_timeout = 1800
    cache_invalidation_patterns = [
        "Insult:*",
        "bulk:insult*",
        "categories:*",
        "users:*:insults*",
    ]

    def get_queryset(self) -> Optional[QuerySet]:  # pyrefly: ignore
        """
        Build the base queryset for this view.

        - If `category_name` is provided in the URL, returns the category‑filtered queryset
        - If the user is authenticated, includes their insults plus all active insults
        - If unauthenticated, returns only active insults

        **Returns**

        - `QuerySet`: Filtered insults based on category and authentication
        """
        # Prevent schema generation from evaluating real queries
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        if self.kwargs:
            logger.debug(f"kwargs seen by view: {self.kwargs}")
            if category := self.kwargs["category_name"]:
                return self._get_categorized_queryset(category)
        return (
            Insult.objects.filter(added_by=self.request.user).union(Insult.public.all())
            if self.request.user.is_authenticated
            else Insult.public.all().prefetch_related("reports").order_by("?")
        )

    def _get_categorized_queryset(self, category):
        """
        Helper to build the category‑filtered queryset.

        - Includes the requesting user's insults for the category (if authenticated)
        - Always merges in active public insults for the same category

        **Args**

        - `category`: Category key or name to filter by

        **Returns**

        - `QuerySet`: Category‑filtered insults with user‑specific visibility
        """
        normalized_category = BaseInsultSerializer.resolve_category(category)
        logger.debug(normalized_category)
        return (
            # Gets All User's Submission Regardless of Status
            Insult.objects.filter(
                category=normalized_category["category_key"], added_by=self.request.user
            )
            .prefetch_related("reports")
            .order_by("?")
            .exclude(category__category_key__in=["TEST", "X"])
            .union(
                # Joins User Submission with All other Matching Insults that are active
                Insult.public.filter(
                    category=normalized_category["category_key"],
                )
                .prefetch_related("reports")
                .order_by("?")
            )
            if self.request.user.is_authenticated
            else Insult.public.filter(
                category=normalized_category["category_key"],
            )
            .prefetch_related("reports")
            .order_by("?")
        )

    def list(self, request, *args, **kwargs):
        # Check for category query parameter early and reject with 400
        if category := request.GET.get("category_name") or request.GET.get("category"):
            # Build new query params without the category fields
            params = request.GET.copy()
            params.pop("category", None)
            params.pop("category_name", None)
            querystring = f"?{urlencode(params)}" if params else ""

            return redirect(f"/api/insults/{category}{querystring}")

        filters = {
            "status": request.GET.get("status"),
            "nsfw": request.GET.get("nsfw"),
        }

        cache_key = self.get_cache_key("bulk_list", **filters)

        def get_filtered_queryset():
            """Build the filtered queryset."""
            queryset = self.get_queryset()

            # Apply filters
            try:
                if filters["status"]:
                    queryset = queryset.filter(status=filters["status"])
                if filters["nsfw"] is not None:
                    nsfw_bool = filters["nsfw"].lower() in ("true", "1", "yes")
                    queryset = queryset.filter(nsfw=nsfw_bool)
                return queryset.filter(status=Insult.STATUS.ACTIVE).order_by(
                    "-added_on"
                )
            except EmptyResultSet:
                return Insult.objects.none()
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
            {"count": queryset.count(), "results": serializer.data, **extra_data}
        )


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
            404: StandardErrorResponses.INSULT_NOT_FOUND,
            **StandardErrorResponses.get_common_error_responses(),
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
            204: OpenApiResponse(description="Insult updated successfully"),
            400: OpenApiResponse(description="Invalid input data provided"),
            **get_insult_crud_responses(),
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
            204: OpenApiResponse(description="Insult partially updated successfully"),
            400: OpenApiResponse(description="Invalid input data provided"),
            **get_insult_crud_responses(),
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
            **get_insult_crud_responses(),
        },
    ),
)
class InsultDetailsEndpoint(
    PaginateByMaxMixin, CreateModelMixin, RetrieveUpdateDestroyAPIView
):
    """
    # Insult Details

    API endpoint for CRUD operations on a single insult.

    - All users can read insults
    - Only the owner can update or delete their insult

    ## Endpoints

    - `GET /api/insult/<reference_id>`: Retrieve insult
    - `PUT /api/insult/<reference_id>`: Update insult *(owner only)*
    - `PATCH /api/insult/<reference_id>`: Partially update insult *(owner only)*
    - `DELETE /api/insult/<reference_id>`: Delete insult *(owner only)*

    ## Authentication

    - Token authentication required for **PUT**, **PATCH**, and **DELETE**
    - Optional for **GET**
    """

    lookup_field = "reference_id"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    authentication_classes = [FlexibleTokenAuthentication]
    cache_models = [InsultCategory, InsultReview]
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]

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

    def get(self, request, reference_id, *args, **kwargs):
        """Retrieve a specific insult by reference_id."""
        # if not (ref_id := kwargs.get("reference_id")):
        #     return Response(
        #         {"detail": "Reference ID is required."}, status=400
        #     )
        insult = Insult.get_by_reference_id(reference_id)
        serializer = self.get_serializer(insult)
        return Response(serializer.data)


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
# class InsultListEndpoint(CachedResponseMixin, PaginateByMaxMixin, ListAPIView):
#     """
#     List All Insults

#     URL
#         GET /api/insults

#     Description
#         Returns a paginated list of ACTIVE insults across all categories. If the caller is
#         authenticated, their own insults are included regardless of status. Categories with
#         keys `TEST` and `X` are excluded from public listing.

#     Authentication
#         Optional. Authentication broadens visibility to include the caller's own items.

#     Query Parameters
#         nsfw (bool, optional): Filter by explicit content. `true` returns only NSFW; `false`
#             returns only SFW. Omit to return both.
#         page (int, optional): Page number (default 1).
#         page_size (int, optional): Items per page (default 20 unless configured otherwise).


#     """

#     serializer_class = OptimizedInsultSerializer
#     primary_model = Insult
#     cache_models = [InsultCategory, InsultReview]
#     permission_classes = [AllowAny]

#     def get_queryset(self):
#         return (
#             Insult.objects.select_related("added_by", "category")
#             .prefetch_related("reports")
#             .order_by("-added_on")
#             .exclude(category__category_key__in=["TEST", "X"])
#         )
#         # Build cache key with all relevant filters

#     def list(self, request, *args, **kwargs):
#         # Check for category query parameter early and reject with 400
#         if request.GET.get("category_name") or request.GET.get("category"):
#             return Response(
#                 {"Error": "Please Use the `api/insults/<category>` endpoint"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         user = request.user if request.user.is_authenticated else None
#         filters = {
#             "category": request.GET.get("category"),
#             "status": request.GET.get("status"),
#             "nsfw": request.GET.get("nsfw"),
#             "page": request.GET.get("page", "1"),
#             "page_size": request.GET.get("page_size", "20"),
#             "user_id": getattr(user, "id", None),
#         }

#         cache_key = self.get_cache_key("bulk_list", **filters)

#         def get_filtered_queryset():
#             """Build the filtered queryset."""
#             queryset = self.get_queryset()

#             # Apply filters
#             if filters["category"]:
#                 queryset = queryset.filter(category__category_key=filters["category"])
#             if filters["status"]:
#                 queryset = queryset.filter(status=filters["status"])
#             if filters["nsfw"] is not None:
#                 nsfw_bool = filters["nsfw"].lower() in ("true", "1", "yes")
#                 queryset = queryset.filter(nsfw=nsfw_bool)
#             if filters["user_id"]:
#                 user_qs = queryset.filter(
#                     added_by_id=filters["user_id"]
#                 )  # include user's own regardless of status
#                 active_qs = queryset.filter(status=Insult.STATUS.ACTIVE)
#                 return user_qs.union(active_qs).order_by("-added_on")
#             return queryset.filter(status=Insult.STATUS.ACTIVE).order_by("-added_on")
#             # Get cached or fresh data with optimizations

#         queryset, extra_data = self.get_cached_bulk_data(
#             cache_key, get_filtered_queryset, timeout=self.bulk_cache_timeout
#         )
#         # Apply pagination
#         page = self.paginate_queryset(queryset)
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             response_data = self.get_paginated_response(serializer.data)
#             response_data.data.update(extra_data)  # Add metadata
#             return response_data

#         # Non-paginated response
#         serializer = self.get_serializer(queryset, many=True)
#         return Response(
#             {"count": len(serializer.data), "results": serializer.data, **extra_data}
#         )


class RandomInsultEndpoint(GenericAPIView):
    """
    # Random Insult

    API endpoint for retrieving a single random insult.

    - By default returns from the active public insults
    - Can be filtered by NSFW status and category

    ## Endpoint

    - `GET /api/insults/random`

    ## Query Parameters

    - `nsfw` *(bool, optional)*: Filter explicit content (`true` / `false`)
    - `category` *(str, optional)*: Category key or name to filter by
    """

    serializer_class = OptimizedInsultSerializer
    permission_classes = [AllowAny]
    throttle_classes = []

    @method_decorator(never_cache)
    @extend_schema(
        tags=["Insults"],
        operation_id="get_random_insult",
        auth=[],
        summary="Get a random insult",
        description="Returns a single random insult from the active collection. Supports optional filtering by NSFW status and category for more targeted results.",
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="Random insult retrieved successfully",
            ),
            404: StandardErrorResponses.NO_RESULTS_FOUND,
            **StandardErrorResponses.get_common_error_responses(),
        },
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
        """
        Retrieve a random insult with optional filters.

        **Args**

        - `request`: HTTP request with optional query parameters

        **Returns**

        - `Response`: Random insult data or `404` if no matches are found
        """
        queryset = (
            Insult.public.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("?")
            .all()
        )

        # Filter by explicitly level (NSFW) if provided
        nsfw_param = request.query_params.get("nsfw")
        if nsfw_param is not None:
            logger.debug(f"Filtering random insult by NSFW={nsfw_param}")
            nsfw = nsfw_param.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(nsfw=nsfw)
        # Filter by category if provided

        if category := request.query_params.get("category_name"):
            logger.debug(f"Filtering random insult by category: {category}")
            category = BaseInsultSerializer.resolve_category(category.upper())
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
            ),
            **get_category_list_responses(),
        },
    )
)
class ListThemesAndCategoryEndpoint(CachedResponseMixin, GenericAPIView):
    """
    # Categories &amp; Themes

    API endpoint for listing insult categories organized by theme.

    - Returns all public insult categories, grouped under their themes
    - Includes metadata such as insult counts and descriptions

    ## Endpoint

    - `GET /api/categories`

    ## Features

    - No authentication required
    - Cached responses for performance
    - Case‑insensitive category matching support
    """

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Build the base queryset of public insult categories.

        **Returns**

        - `QuerySet`: Categories excluding test and internal categories
        """
        return InsultCategory.public.all().prefetch_related("theme")

    def get(self, request):
        """
        Return a list of insult categories grouped by theme.

        **Args**

        - `request`: HTTP request object

        **Returns**

        - `Response`: JSON payload containing a `help_text` and a `results` mapping
        """
        qs = self.get_queryset()
        theme_qs = Theme.objects.all().exclude(theme_key="INTL")
        serializer = CategorySerializer(qs, many=True)
        logger.debug(serializer.data)
        output = {}
        for row in serializer.data:
            # Find the matching theme by primary key instead of theme_key comparison
            theme = next((t for t in theme_qs if t.theme_key == row["theme_id"]), None)
            if not theme:
                continue

            # Initialize theme entry if it doesn't exist yet
            if theme.theme_name not in output:
                output[theme.theme_name] = {
                    "theme_description": theme.description,
                    "categories": {},
                }

            # Always add/update the category entry for this theme
            output[theme.theme_name]["categories"][row["category_key"]] = {
                "name": row["name"],
                "description": row["description"],
                "count": row["count"],
            }

        return Response(
            {
                "help_text": "Here is a list of all available Insult Categories. The API will accept either values and is case insensitive. Ex: `/api/insults/p` and `api/insults/POOR` will yield the same result",
                "results": output,
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
                description="Insult created successfully",
                response=CreateInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Successful Creation",
                        summary="New insult created successfully",
                        description="Example response when a new insult is successfully created",
                        value={
                            "reference_id": "GIGGLE_ABC123",
                            "category": "Poor",
                            "content": "Your code is so poor, it makes welfare look like a luxury lifestyle.",
                            "nsfw": False,
                            "status": "Pending",
                            "added_by": "DevJoker",
                            "added_on": "2 minutes ago",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="Invalid input data provided"),
            **StandardErrorResponses.get_authenticated_endpoint_responses(),
        },
    )
)
class CreateInsultEndpoint(CreateAPIView):
    """
      # Create New Insult (Must Be Registered User)

      Creates new insults owned by authenticated users. New insults
      default to 'Pending' status pending approval.

     ## Endpoints:
          POST /api/insults/new

     ## Authentication:
          Token authentication required

    ##  Request Body:
          content (str): Insult content (minimum 60 characters, UTF-8)
          nsfw (bool): Explicit content flag
          category (str): Category key or name
    """

    serializer_class = CreateInsultSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [FlexibleTokenAuthentication]

    def perform_create(self, serializer):
        """Set the authenticated user as the insult owner."""
        serializer.save(added_by=self.request.user)
