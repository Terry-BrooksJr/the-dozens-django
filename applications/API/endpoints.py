from django.views.decorators.cache import never_cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework_extensions.mixins import PaginateByMaxMixin

from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import OptimizedInsultSerializer
from common.preformance import CachedResponseMixin


class InsultDetailsEndpoints(
    PaginateByMaxMixin, CreateModelMixin, RetrieveUpdateDestroyAPIView
):
    lookup_field = "reference_id"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
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
            return [AllowAny]
        else:
            return [IsOwnerOrReadOnly]

    def get_queryset(self):
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .all()
        )


class InsultListEndpoint(CachedResponseMixin, PaginateByMaxMixin, ListAPIView):
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    cache_models = [InsultCategory, InsultReview]
    permission_classes = [IsOwnerOrReadOnly]
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]
    bulk_cache_timeout = 1800
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
            .all()
        )
        # Build cache key with all relevant filters

    def list(self, request, *args, **kwargs):
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


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def random(request):
    """Get a random insult."""
    queryset = (
        Insult.objects.select_related("added_by", "category")
        .prefetch_related("reports")
        .order_by("-added_on")
        .all()
    )

    # Filter by explicity level (NSFW) if provided
    nsfw_param = request.query_params.get("nsfw")
    if nsfw_param is not None:
        nsfw = nsfw_param.lower() in ["true", "1", "yes"]
        queryset = queryset.filter(nsfw=nsfw)
    # Filter by category if provided

    if category := request.query_params.get("category"):
        queryset = queryset.filter(category__category_key=category)

    if not queryset.exists():
        return Response(
            {"detail": "No insults found matching the criteria."}, status=404
        )

    random_insult = queryset.order_by("?").first()
    serializer = OptimizedInsultSerializer(random_insult)
    return Response(serializer.data)
