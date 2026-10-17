"""
# applications.API.endpoints

API endpoints for managing insults, categories, and themes.

- Provides CRUD operations for insults and categories
- Supports filtering, random retrieval, and category/theme discovery
"""

import random
import time

from django.contrib.auth import get_user_model
from django.core.exceptions import EmptyResultSet
from django.db import connection
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from loguru import logger
from rest_framework import serializers
from rest_framework.generics import (
    CreateAPIView,
    GenericAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response

from applications.API import openapi
from applications.API.authentication import FlexibleTokenAuthentication
from applications.API.errors import (
    StandardErrorResponses,
)
from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview, Theme
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import (
    BaseInsultSerializer,
    CategorySerializer,
    CreateInsultSerializer,
    MyInsultSerializer,
    OptimizedInsultSerializer,
)
from common.metrics import metrics
from common.performance import CachedResponseMixin

User = get_user_model()


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        operation_id="list_insults_by_category",
        auth=[],
        summary="List insults in a category",
        description=(
            "A page of insults in one category, in random order. Anonymous callers "
            "see active insults; an authenticated caller also sees their own "
            "submissions in the category, whatever their status. The page also "
            "carries `total_count` and `timestamp`."
        ),
        parameters=[openapi.CATEGORY_NAME_PARAM, openapi.NSFW_QUERY_PARAM],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="A page of insults.",
                examples=[openapi.insult_page_example(openapi.INSULT)],
            ),
            **openapi.public_list_responses(),
        },
    )
)
class InsultByCategoryEndpoint(CachedResponseMixin, ListAPIView):
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
    # The serializer never reads ``reports``; prefetching it cost a query per request.
    bulk_prefetch_related = None
    bulk_cache_timeout = 1800
    cache_invalidation_patterns = [
        "Insult:*",
        "bulk:insult*",
        "categories:*",
        "users:*:insults*",
    ]

    def get_queryset(self) -> QuerySet | None:  # pyrefly: ignore
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
        if category := self._requested_category():
            return self._get_categorized_queryset(category)
        return (
            Insult.objects.filter(added_by=self.request.user).union(Insult.public.all())
            if self.request.user.is_authenticated
            else Insult.public.all().prefetch_related("reports").order_by("?")
        )

    def _requested_category(self) -> str | None:
        """Return the category from the URL path or the ``category`` query param.

        The path form serves ``/api/v2.0.0/categories/{category_name}/insults/``
        (and the deprecated ``/api/insults/category/{category_name}/``); the
        query-param form serves the ``/api/v2.0.0/insults/?category=`` collection.
        ``category_name`` is still accepted as a query-param alias.
        """
        return (
            self.kwargs.get("category_name")
            or self.request.query_params.get("category")
            or self.request.query_params.get("category_name")
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
            .order_by("?")
            .exclude(category__category_key__in=["TEST", "X"])
            .union(
                # Joins User Submission with All other Matching Insults that are active
                Insult.public.filter(
                    category=normalized_category["category_key"],
                ).order_by("?")
            )
            if self.request.user.is_authenticated
            else Insult.public.filter(
                category=normalized_category["category_key"],
            ).order_by("?")
        )

    def list(self, request, *args, **kwargs):
        """List active insults, optionally narrowed to a category.

        The category comes from the URL path or the ``category`` query
        parameter. Results are filtered by ``status``/``nsfw``, served from
        the bulk cache, and paginated.
        """
        filters = {
            "status": request.GET.get("status"),
            "nsfw": request.GET.get("nsfw"),
            "category": self._requested_category(),
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
        tags=["Insults"],
        operation_id="list_insults",
        auth=[],
        summary="List insults",
        description=(
            "A page of insults in random order, optionally filtered by `category` "
            "and `nsfw`. Anonymous callers see active insults; an authenticated "
            "caller also sees all of their own submissions. The page also carries "
            "`total_count` and `timestamp`."
        ),
        parameters=[openapi.CATEGORY_QUERY_PARAM, openapi.NSFW_QUERY_PARAM],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="A page of insults.",
                examples=[
                    openapi.insult_page_example(openapi.INSULT, openapi.INSULT_POOR)
                ],
            ),
            **openapi.public_list_responses(),
        },
    ),
    post=extend_schema(
        tags=["Insults"],
        operation_id="create_insult",
        auth=[{"TokenAuth": []}],
        summary="Create an insult",
        description=(
            "Submit a new insult as the authenticated user. `category` takes a key "
            "or name. The insult starts as `Pending - New` and stays out of public "
            "listings until a moderator approves it; its owner can still retrieve it."
        ),
        request=CreateInsultSerializer,
        examples=[openapi.CREATE_INSULT_REQUEST_EXAMPLE],
        responses={
            201: OpenApiResponse(
                response=CreateInsultSerializer,
                description="The created insult.",
                examples=[openapi.CREATED_INSULT_EXAMPLE],
            ),
            400: openapi.INVALID_INSULT,
            401: StandardErrorResponses.UNAUTHORIZED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    ),
)
class InsultCollectionEndpoint(CreateModelMixin, InsultByCategoryEndpoint):
    """
    # Insult Collection

    - `GET /api/v2.0.0/insults/`: list active insults (supports `?category=`)
    - `POST /api/v2.0.0/insults/`: create an insult (token authentication required)
    """

    authentication_classes = [FlexibleTokenAuthentication]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateInsultSerializer
        return super().get_serializer_class()

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Set the authenticated user as the insult owner."""
        serializer.save(added_by=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        auth=[],
        operation_id="retrieve_insult",
        summary="Retrieve an insult",
        description=(
            "One insult by reference ID. Active insults are public; an "
            "authenticated owner can also retrieve their own pending or rejected "
            "submissions. Anything else returns `404`."
        ),
        parameters=[openapi.REFERENCE_ID_PARAM],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="The insult.",
                examples=[openapi.INSULT_EXAMPLE],
            ),
            404: StandardErrorResponses.INSULT_NOT_FOUND,
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    ),
    put=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="update_insult",
        summary="Replace an insult",
        description="Replace an insult's editable fields. Only its owner may do this.",
        parameters=[openapi.REFERENCE_ID_PARAM],
        request=OptimizedInsultSerializer,
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="The updated insult.",
                examples=[openapi.INSULT_EXAMPLE],
            ),
            400: StandardErrorResponses.BAD_REQUEST,
            401: StandardErrorResponses.UNAUTHORIZED,
            403: StandardErrorResponses.OWNER_ONLY_ACCESS,
            404: StandardErrorResponses.INSULT_NOT_FOUND,
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    ),
    patch=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="partial_update_insult",
        summary="Update part of an insult",
        description=(
            'Update only the fields sent, e.g. `{"nsfw": true}`. Only the '
            "insult's owner may do this."
        ),
        parameters=[openapi.REFERENCE_ID_PARAM],
        request=OptimizedInsultSerializer,
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="The updated insult.",
                examples=[openapi.INSULT_EXAMPLE],
            ),
            400: StandardErrorResponses.BAD_REQUEST,
            401: StandardErrorResponses.UNAUTHORIZED,
            403: StandardErrorResponses.OWNER_ONLY_ACCESS,
            404: StandardErrorResponses.INSULT_NOT_FOUND,
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    ),
    delete=extend_schema(
        tags=["Insults"],
        auth=[{"TokenAuth": []}],
        operation_id="delete_insult",
        summary="Delete an insult",
        description="Permanently delete an insult. Only its owner may do this.",
        parameters=[openapi.REFERENCE_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Deleted; no response body."),
            401: StandardErrorResponses.UNAUTHORIZED,
            403: StandardErrorResponses.OWNER_ONLY_ACCESS,
            404: StandardErrorResponses.INSULT_NOT_FOUND,
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    ),
)
class InsultDetailsEndpoint(CreateModelMixin, RetrieveUpdateDestroyAPIView):
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
    # The serializer never reads ``reports``; prefetching it cost a query per request.
    bulk_prefetch_related = None

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
        """Allow anyone to read; restrict writes to the insult's owner."""
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        else:
            return [IsOwnerOrReadOnly()]

    def get_queryset(self):
        """Return public insults and the authenticated user's submissions."""
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        visibility = Q(status=Insult.STATUS.ACTIVE)
        if self.request.user.is_authenticated:
            visibility |= Q(added_by=self.request.user)
        return (
            Insult.objects.select_related("added_by", "category")
            .filter(visibility)
            .order_by("-added_on")
        )

    def get(self, request, reference_id, *args, **kwargs):
        """Retrieve a specific insult by reference_id."""
        insult = get_object_or_404(
            self.get_queryset(),
            reference_id=reference_id,
        )
        serializer = self.get_serializer(insult)
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        operation_id="get_random_insult",
        auth=[],
        summary="Get a random insult",
        description=(
            "One random active insult, optionally limited by `category` and "
            "`nsfw`. Never cached: every call can return a different insult. "
            "Not rate limited."
        ),
        parameters=[openapi.CATEGORY_QUERY_PARAM, openapi.NSFW_QUERY_PARAM],
        request=None,
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                description="A random insult.",
                examples=[openapi.INSULT_EXAMPLE],
            ),
            400: openapi.UNKNOWN_CATEGORY,
            401: StandardErrorResponses.UNAUTHORIZED,
            404: StandardErrorResponses.NO_RESULTS_FOUND,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    )
)
class RandomInsultEndpoint(GenericAPIView):
    """Serves a single random active insult, instrumented per query phase."""

    serializer_class = OptimizedInsultSerializer
    permission_classes = [AllowAny]
    throttle_classes = []

    def dispatch(self, request, *args, **kwargs):
        """Count every request to this endpoint, under its final status.

        Counted here rather than in ``get()`` because DRF authenticates,
        checks permissions and throttles in ``initial()``, before ``get()``
        runs: a bad token is turned into a 401/403 response inside
        ``super().dispatch()`` and would otherwise never be counted. An
        unhandled exception propagates out of ``super().dispatch()`` and is
        counted as a 500 in ``finally``.
        """
        self._sql_stats = {"query_count": 0, "total_ms": 0.0, "slowest_ms": 0.0}
        status_label = "500"
        try:
            response = super().dispatch(request, *args, **kwargs)
            status_label = str(response.status_code)
            return response
        finally:
            metrics.record_random_insult_request(
                status=status_label,
                category_filtered="category" in request.GET,
                nsfw_filtered="nsfw" in request.GET,
                db_query_count=self._sql_stats["query_count"],
            )

    @method_decorator(never_cache)
    def get(self, request):
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
        request_id = getattr(request, "request_id", "unknown")
        t_start = time.perf_counter()

        nsfw_param = request.query_params.get("nsfw")
        category_param = request.query_params.get("category")
        resolved_category_key: str | None = None

        # Request counting (by final status) happens in dispatch(); the SQL
        # stats are shared with it through self._sql_stats.
        with metrics.sql_instrumentation() as sql_stats:
            self._sql_stats = sql_stats
            # Phase 1: queryset build. Lazy - no SQL runs here, so the base
            # queryset and the NSFW filter share one stage.
            with metrics.time_random_insult_stage("queryset_build"):
                queryset = Insult.public.select_related("added_by", "category").all()
                if nsfw_param is not None:
                    nsfw = nsfw_param.lower() in ["true", "1", "yes"]
                    queryset = queryset.filter(nsfw=nsfw)

            # Phase 2: category resolution (may hit cache/DB)
            with metrics.time_random_insult_stage("category_resolution"):
                if category_param:
                    resolved = BaseInsultSerializer.resolve_category(
                        category_param.upper()
                    )
                    resolved_category_key = resolved.get("category_key")
                    queryset = queryset.filter(
                        category__category_key=resolved_category_key
                    )

            # Phase 3: count serves double duty — emptiness check + random
            # offset bound. First SQL query of the request.
            with metrics.time_random_insult_stage("emptiness_check"):
                count = queryset.count()

            if count == 0:
                duration_ms = (time.perf_counter() - t_start) * 1000.0
                metrics.record_random_insult_empty()
                logger.bind(
                    request_id=request_id,
                    path=request.path,
                    nsfw_param=nsfw_param,
                    category_param=category_param,
                    resolved_category_key=resolved_category_key,
                    duration_ms=round(duration_ms, 2),
                    db_query_count=sql_stats["query_count"],
                    db_total_ms=round(sql_stats["total_ms"], 2),
                    db_slowest_ms=round(sql_stats["slowest_ms"], 2),
                    empty_result=True,
                ).info("random_insult | no results found after filtering")
                return Response(
                    {"detail": "No insults found matching the criteria."},
                    status=404,
                )

            # Phase 4: offset-based random selection.
            # ORDER BY insult_id uses the PK index (O(log n) + offset).
            # Replaces ORDER BY RANDOM() which was a full-table sort (O(n log n)).
            with metrics.time_random_insult_stage("random_selection"):
                random_insult = queryset.order_by("insult_id")[
                    random.randint(0, count - 1)
                ]

            # Phase 5: serialization
            with metrics.time_random_insult_stage("serialization"):
                serializer = OptimizedInsultSerializer(random_insult)
                data = serializer.data

        duration_ms = (time.perf_counter() - t_start) * 1000.0
        logger.bind(
            request_id=request_id,
            path=request.path,
            nsfw_param=nsfw_param,
            category_param=category_param,
            resolved_category_key=resolved_category_key,
            selected_insult_id=random_insult.insult_id if random_insult else None,
            duration_ms=round(duration_ms, 2),
            db_query_count=sql_stats["query_count"],
            db_total_ms=round(sql_stats["total_ms"], 2),
            db_slowest_ms=round(sql_stats["slowest_ms"], 2),
            empty_result=False,
        ).info("random_insult | success")
        return Response(data)


@extend_schema_view(
    get=extend_schema(
        tags=["Insult Categories"],
        auth=[],
        operation_id="list_categories",
        summary="List categories by theme",
        description=(
            "Every public category, grouped by theme and keyed by category key, "
            "with its name, description and number of active insults. Use either "
            "the key or the name wherever the API takes a category."
        ),
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Categories grouped by theme.",
                examples=[
                    OpenApiExample(
                        "Categories",
                        value={
                            "help_text": (
                                "Here is a list of all available Insult Categories. "
                                "The API will accept either values and is case "
                                "insensitive. Ex: `/api/insults/p` and "
                                "`api/insults/POOR` will yield the same result"
                            ),
                            "results": {
                                "Yo Momma": {
                                    "theme_description": "Classic yo momma jokes.",
                                    "categories": {
                                        "F": {
                                            "name": "Fat",
                                            "description": "",
                                            "count": 80,
                                        },
                                        "P": {
                                            "name": "Poor",
                                            "description": "",
                                            "count": 134,
                                        },
                                    },
                                }
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            429: StandardErrorResponses.RATE_LIMIT_EXCEEDED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    )
)
class ListThemesAndCategoryEndpoint(CachedResponseMixin, GenericAPIView):
    """Lists public insult categories grouped under their themes."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Build the base queryset of public insult categories.

        **Returns**

        - `QuerySet`: Categories excluding test and internal categories
        """
        return InsultCategory.public.annotate(
            active_insult_count=Count(
                "insult", filter=Q(insult__status=Insult.STATUS.ACTIVE)
            )
        )

    def get(self, request):
        """

          # Categories & Themes

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
        deprecated=True,
        summary="Create an insult (deprecated)",
        description=(
            "Deprecated alias served only at `POST /api/insults/new`; use "
            "`POST /api/v2.0.0/insults/`, which behaves the same."
        ),
        request=CreateInsultSerializer,
        examples=[openapi.CREATE_INSULT_REQUEST_EXAMPLE],
        responses={
            201: OpenApiResponse(
                response=CreateInsultSerializer,
                description="The created insult.",
                examples=[openapi.CREATED_INSULT_EXAMPLE],
            ),
            400: openapi.INVALID_INSULT,
            401: StandardErrorResponses.UNAUTHORIZED,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
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
          content (str): Insult content (Must be in a 'Yo Momma So...' format. i.e. Yo Momma So Ugly... or Yo Daddy So Dumb...;  UTF-8)
          nsfw (bool): Explicit content flag
          category (str): Category key or name
    """

    serializer_class = CreateInsultSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [FlexibleTokenAuthentication]

    def perform_create(self, serializer):
        """Set the authenticated user as the insult owner."""
        serializer.save(added_by=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["Insults"],
        auth=[],
        operation_id="list_reference_ids",
        summary="List active insult reference IDs",
        description=(
            "A page of the reference IDs of every active insult, sorted so paging "
            "is stable. Pass an ID to `GET /api/v2.0.0/insults/{reference_id}/` "
            "for the full insult. Not rate limited."
        ),
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="A page of reference IDs.",
                examples=[
                    OpenApiExample(
                        "Reference IDs",
                        value={
                            "count": 214,
                            "next": "https://api.yo-momma.io/api/v2.0.0/insults/reference-ids/?page=2",
                            "previous": None,
                            "results": ["CACKLE_NDQ5", "CHUCKLE_NDUz", "GIGGLE_Mg=="],
                        },
                        response_only=True,
                    )
                ],
            ),
            404: openapi.INVALID_PAGE,
            500: StandardErrorResponses.INTERNAL_SERVER_ERROR,
        },
    )
)
class ListReferenceIdsEndpoint(ListAPIView):
    """
    # List Active Insult Reference IDs

    Returns a paginated list of reference IDs for all active (status=``A``) insults.

    ## Endpoint

    - ``GET /api/v2.0.0/insults/reference-ids/``

    ## Query Parameters

    - ``page`` *(int, optional)*: Page number
    - ``page_size`` *(int, optional)*: Results per page (``max`` for the maximum allowed)

    ## Notes

    - No authentication required
    - Only active, public insults are included (same visibility as ``/api/v2.0.0/insults/random/``)
    - Results are ordered alphabetically by reference ID for stable pagination
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []
    # Required by ListAPIView / drf-spectacular; the actual list() override
    # returns plain strings so the serializer is never instantiated at runtime.
    serializer_class = OptimizedInsultSerializer

    def get_queryset(self):
        """Return reference IDs of all public insults, ordered for stable paging."""
        if getattr(self, "swagger_fake_view", False):
            return Insult.objects.none()
        return Insult.public.values_list("reference_id", flat=True).order_by(
            "reference_id"
        )

    def list(self, request, *args, **kwargs):
        """Return reference IDs as plain strings, paginated when requested."""
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(list(page))
        return Response({"count": qs.count(), "results": list(qs)})


class UserContentManagementEndpoint(ListAPIView):
    permission_classes = []
    authentication_classes = []
    serializer_class = MyInsultSerializer


_HEALTH_RESPONSE = inline_serializer(
    name="HealthResponse",
    fields={
        "status": serializers.ChoiceField(choices=["ok", "degraded"]),
        "database": serializers.ChoiceField(choices=["ok", "unavailable"]),
        "graphql": serializers.ChoiceField(choices=["ok", "error"]),
        "launchdarkly": serializers.ChoiceField(
            choices=["ok", "disabled", "not_initialized", "unavailable"]
        ),
        "loki": serializers.ChoiceField(
            choices=["Actively Forwarded", "Configured - Not Forwarding", "Disabled"]
        ),
        "timestamp": serializers.DateTimeField(),
    },
)


@extend_schema_view(
    get=extend_schema(
        tags=["Health & Status Check"],
        auth=[],
        operation_id="service_heartbeat",
        summary="Service health heartbeat",
        description=(
            "Checks the service's dependencies. Responds `503` with "
            "`status: degraded` when the database, GraphQL or (if enabled) "
            "LaunchDarkly is unhealthy, otherwise `200`.\n\n"
            "`loki` reports log forwarding for the worker that answered: "
            "`Actively Forwarded` (configured and the latest push succeeded), "
            "`Configured - Not Forwarding` (configured but nothing delivered yet, "
            "or the latest push failed) or `Disabled` (not configured). It is "
            "informational and never makes the service degraded.\n\n"
            "Never cached and not rate limited."
        ),
        responses={
            200: OpenApiResponse(
                response=_HEALTH_RESPONSE,
                description="All checks healthy.",
                examples=[
                    OpenApiExample(
                        "Healthy",
                        value={
                            "status": "ok",
                            "database": "ok",
                            "graphql": "ok",
                            "launchdarkly": "ok",
                            "loki": "Actively Forwarded",
                            "timestamp": "2026-10-16T10:04:41.581040+00:00",
                        },
                        response_only=True,
                    )
                ],
            ),
            503: OpenApiResponse(
                response=_HEALTH_RESPONSE,
                description="One or more checks degraded.",
                examples=[
                    OpenApiExample(
                        "Degraded",
                        value={
                            "status": "degraded",
                            "database": "unavailable",
                            "graphql": "ok",
                            "launchdarkly": "not_initialized",
                            "loki": "Configured - Not Forwarding",
                            "timestamp": "2026-10-16T10:04:41.581040+00:00",
                        },
                        response_only=True,
                    )
                ],
            ),
        },
    )
)
class HealthEndpoint(GenericAPIView):
    """Deep readiness check covering the database, GraphQL, and LaunchDarkly,
    plus the Loki log-forwarding status (informational only)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []
    serializer_class = None

    def _check_database(self) -> str:
        """Return ``"ok"`` if a database connection can be established."""
        try:
            connection.ensure_connection()
            return "ok"
        except Exception:
            return "unavailable"

    def _check_graphql(self) -> str:
        """Return ``"ok"`` if the GraphQL schema can execute a trivial query."""
        try:
            from applications.graphQL.schema import schema

            result = schema.execute("{ __typename }")
            return "error" if result.errors else "ok"
        except Exception:
            return "error"

    def _check_launchdarkly(self) -> str:
        """Report the LaunchDarkly client state.

        Returns:
            str: ``"ok"``, ``"disabled"``, ``"not_initialized"``, or
            ``"unavailable"``.
        """
        from django.conf import settings

        if not getattr(settings, "LAUNCHDARKLY_ENABLED", False):
            return "disabled"
        try:
            from applications.ld_integration.client import get_client

            client = get_client()
            return "ok" if (client and client.is_initialized()) else "not_initialized"
        except Exception:
            return "unavailable"

    def _check_loki(self) -> str:
        """Report Loki log forwarding for this worker process.

        Returns:
            str: ``"Actively Forwarded"``, ``"Configured - Not Forwarding"``
            or ``"Disabled"`` (see ``common.loki``).
        """
        from common.loki import forwarding_status

        return forwarding_status()

    # never_cache: UpdateCacheMiddleware would otherwise store a healthy
    # response for CACHE_MIDDLEWARE_SECONDS and replay it, hiding an outage.
    @method_decorator(never_cache)
    def get(self, request):
        """Run every health check; respond 503 if any check is degraded."""
        checks = {
            "database": self._check_database(),
            "graphql": self._check_graphql(),
            "launchdarkly": self._check_launchdarkly(),
        }
        degraded = any(v not in ("ok", "disabled") for v in checks.values())
        return Response(
            {
                "status": "degraded" if degraded else "ok",
                **checks,
                # Informational: a log-shipping outage must not take the API
                # out of rotation, so it's excluded from `degraded`.
                "loki": self._check_loki(),
                "timestamp": timezone.now().isoformat(),
            },
            status=503 if degraded else 200,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Health & Status Check"],
        auth=[],
        operation_id="ping",
        summary="Liveness probe",
        description=(
            'Returns `{"status": "ok"}` whenever the server can answer '
            "requests. It checks nothing else; use `GET /api/health/` for "
            "dependency checks. Never cached and not rate limited."
        ),
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="PingResponse", fields={"status": serializers.CharField()}
                ),
                description="The server is up.",
                examples=[
                    OpenApiExample("Alive", value={"status": "ok"}, response_only=True)
                ],
            )
        },
    )
)
class PingEndpoint(GenericAPIView):
    """Lightweight liveness probe used by Traefik health checks.

    Intentionally skips DB/GraphQL/LD checks — those run under /api/health/.
    This just confirms Gunicorn is alive and able to accept requests.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []
    serializer_class = None

    @method_decorator(never_cache)
    def get(self, request):
        """Return a static ``ok`` payload."""
        return Response({"status": "ok"})
