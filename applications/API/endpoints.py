from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.mixins import CreateModelMixin
from transformers import Owlv2Config
import applications.API.models import Insult
from applications.API.serializers import OptimizedInsultSerializer
from rest_framework_extensions.mixins import PaginateByMaxMixin

from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import (
    CategorySerializer,
    OptimizedInsultSerializer,
    CreateInsultSerializer
)
from common.preformance import CachedResponseMixin, CacheInvalidationMixin, CategoryCacheManager
from common.utils.helpers import _check_ownership


from rest_framework_extensions.mixins import PaginateByMaxMixin
from applications.API.filters import InsultFilter
from applications.API.models import Insult, InsultCategory, InsultReview
from applications.API.permissions import IsOwnerOrReadOnly
from applications.API.serializers import (
    CategorySerializer,
    OptimizedInsultSerializer,
    CreateInsultSerializer
)
from common.preformance import CachedResponseMixin, CacheInvalidationMixin, CategoryCacheManager
from common.utils.helpers import _check_ownership
from django_filters.rest_framework import DjangoFilterBackend
import typing

class InsultDetailsEndpoints(PaginateByMaxMixin,CreateModelMixin, RetrieveUpdateDestroyAPIView):
    lookup_field = "reference_id"
    serializer_class = OptimizedInsultSerializer
    primary_model = Insult
    cache_models = [InsultCategory, InsultReview]  
    permission_classes = [IsOwnerOrReadOnly]
    lookup_field = "insult_id"
    bulk_select_related = ["added_by", "category"]
    bulk_prefetch_related = ["reports"]
    bulk_cache_timeout = 1800  
    cache_invalidation_patterns = [  "Insult:*",
        "bulk:insult*", 
        "categories:*",
        "users:*:insults*"]
    filter_backends = (DjangoFilterBackend,)  #pyrefly: ignore
    filterset_class = InsultFilter
    
    def get_queryset(self):
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .all()
        )
        
        
        
class InsultListEndpoint(ListView):
        
    
    def get_queryset(self):
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .all()
        )
            # Build cache key with all relevant filters
        
        
    def list(self, request, *args, **kwargs):
        filters = { 
            "category": request.GET.get("category"),
            "status": request.GET.get("status"),
            "nsfw": request.GET.get("nsfw"),
            "page": request.GET.get("page", "1"),
            "page_size": request.GET.get("page_size", "20"),
            "user": User.objects.get(id=request.user.username.id) if request.user.is_authenticated else None
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
                nsfw_bool = filters["nsfw"].lower() in ('true', '1', 'yes')
                queryset = queryset.filter(nsfw=nsfw_bool)
            if self.action == "list" and filters["user"]:
                status_agnostic_queryset = queryset.filter(added_by=filters["user"])
                return status_agnostic_queryset.union(
                    queryset.filter(status=Insult.STATUS.ACTIVE)
                ).order_by("-added_on")
            return queryset.filter(status=Insult.STATUS.ACTIVE).order_by('-added_on')
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
        return Response({
            "count": len(serializer.data),
            "results": serializer.data
            **extra_data
        })