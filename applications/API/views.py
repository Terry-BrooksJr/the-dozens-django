import django.utils.decorators
import django.views.decorators.cache
import random

from django.db.models import Q
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from django.views.decorators.cache import never_cache
from rest_framework import viewsets, status
from django.utils.decorators import method_decorator
from rest_framework.exceptions import PermissionDenied

from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
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
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value=[
                            {
                                "reference_id": 1,
                                "content": "Yo momma is so ugly... when they took her to the beautician it took 12 hours for a quote!",
                                "category": "Ugly",
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
    create=extend_schema(
        tags=["Insults"],
        operation_id="create_insult",
        description="Create a new insult. Authentication required.",
        request=CreateInsultSerializer,
        responses={
            201: OpenApiResponse(
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Created Response",
                        value={
                            "id": 1,
                            "content": "Yo momma is so old... her birth certificate says expired on it.",
                            "category": "Unique\One-Off",
                            "status": "Active",
                            "nsfw": False,
                            "added_by": "Mariyln Q.",
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
        request=OptimizedInsultSerializer,
        responses={
            200: OptimizedInsultSerializer,
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
class InsultViewSet(PaginateByMaxMixin,
                    CachedResponseMixin,
                    CacheInvalidationMixin,
                    viewsets.ModelViewSet):
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
    primary_model = Insult
    cache_models = [InsultCategory, InsultReview]  
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
    
    @action(detail=False, methods=['get'])
    def cache_stats(self, request):
        """Get cache performance statistics."""
        return Response({
            'cache_backend': cache.__class__.__name__,
            'bulk_cache_timeout': self.bulk_cache_timeout,
            'invalidation_patterns': self.cache_invalidation_patterns
        })
        
    def get_serializer_class(self):
        """Return the appropriate serializer class based on the action."""
        return OptimizedInsultSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "random"]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]
    

    def get_queryset(self):
        return (
            Insult.objects.select_related("added_by", "category")
            .prefetch_related("reports")
            .order_by("-added_on")
            .all()
        )
    # # Filter by status if authenticated user to return all insults regardless of status they created and all active insults created by others
    #     if self.action == "list" and self.request.user.is_authenticated:
    #         return base_queryset.filter(added_by=self.request.user)

    #     if self.request.user.is_authenticated:
    #         return base_queryset.filter(
    #             Q(added_by=self.request.user) | Q(status=Insult.STATUS.ACTIVE)
    #         )

    #     return base_queryset.filter(status=Insult.STATUS.ACTIVE)
    
    def perform_update(self, serializer):
        obj = self.get_object()
        _check_ownership(obj=obj, user=self.request.user)
        serializer.save()
    @extend_schema(
        tags=["Insults"],
        operation_id="create_insult",
        description="Create a new insult. Authentication required.",
        request=CreateInsultSerializer,
        responses={
            201: OpenApiResponse(
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Created Response",
                        response_only=True,
                        value={
                            "reference_id": 1,
                            "content": "Your code has more bugs than a roach motel",
                            "category": "Programming",
                            "status": "Pending",
                            "nsfw": False,
                            "added_by": "John D.",
                            "added_on": "just now",
                        },
                    ),
                    OpenApiExample( "Create Request",
                        request_only=True,
                        value={
                            "content": "Your code has more bugs than a roach motel",
                            "category": "Programming",
                            "nsfw": False,
                        }
                        ), 
                ],
            ),
            400: OpenApiResponse(description="Invalid input"),
            401: OpenApiResponse(description="Authentication required",
                examples=[
                    OpenApiExample(
                        "Authentication Required",
                        value={
                            "detail": "Authentication credentials were not provided."
                        },  
                        ) 
                    ]
            ),
        },  
    )
    def preform_create(self, serializer):
        """
        Custom create method to handle ownership and additional logic.
        
        This method checks if the user is authenticated and sets the added_by field.
        """
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required to create insults.")
        serializer.save(added_by=self.request.user)
    def perform_destroy(self, instance):
        _check_ownership(instance, self.request.user)
        instance.delete()
        
    @action(detail=False, methods=["get"])
    def bulk_list(self, request):
        """
        Optimized bulk listing with comprehensive caching and filtering.
        
        This endpoint demonstrates:
        - Bulk query optimization
        - Cache key generation with filters
        - Cached bulk data retrieval
        - Pagination support
        """
        # Build cache key with all relevant filters
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
            "results": serializer.data,
            **extra_data
        })
    @action(detail=False, methods=["get"])
    def my_insults(self, request):
        """
        Get current user's insults with optimization.
        
        Demonstrates user-specific caching and authentication handling.
        """
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        cache_key = self.get_cache_key("my_insults", user_id=request.user.id)
        
        def get_user_queryset():
            return self.get_queryset().filter(added_by=request.user).order_by('-added_on')
        
        queryset, extra_data = self.get_cached_bulk_data(
            cache_key, get_user_queryset, timeout=1800  # 30 minutes for user data
        )
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
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
                enum=["active", "pending", "rejected", ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OptimizedInsultSerializer,
                examples=[
                    OpenApiExample(
                        "Category Insults",
                        value=[
{
  "count": 116,
  "next": "http://127.0.0.1:8888/api/insults/?category=F&page=2",
  "previous": None ,
  "results": [
    {
      "reference_id": "GIGGLE_OTc3",
      "content": "“Yo Momma’s so fat that when she walked past the TV, I missed three episodes.",
      "category": "fat",
      "status": "Active",
      "nsfw": False,
      "added_by": "terry-brooks.",
      "added_on": "2 years ago"
    },
    {
      "reference_id": "GIGGLE_MTAxOA==",
      "content": "Yo Momma’s so fat, when she stepped on the scale it said, ‘To be continued.’",
      "category": "fat",
      "status": "Active",
      "nsfw": False,
      "added_by": "terry-brooks.",
      "added_on": "2 years ago"
    },
    {
      "reference_id": "SNORT_OTE5",
      "content": "Yo Momma so fat, she left in high heels and came back in flip flops.",
      "category": "fat",
      "status": "Active",
      "nsfw": False,
      "added_by": "terry-brooks.",
      "added_on": "2 years ago"
    }
  ]
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
    @permission_classes(AllowAny)
    @action(detail=True, methods=["get"])
    def by_category(self, request):
        """
        Get insults by category using specialized category caching.
        
        Demonstrates integration with CategoryCacheManager.
        """
        category_name = request.GET.get('category')
        if not category_name:
            return Response(
                {"detail": "Category parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use specialized category cache
        category_key = CategoryCacheManager.get_category_key_by_name(category_name)
        
        if not category_key:
            # Category not found in cache, might not exist
            return Response(
                {"detail": "Category not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        cache_key = self.get_cache_key("by_category", category_key=category_key)
        
        def get_category_queryset():
            return self.get_queryset().filter(
                category__category_key=category_key
            ).order_by('-added_on')
        
        queryset, extra_data = self.get_cached_bulk_data(cache_key, get_category_queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
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
 OptimizedInsultSerializer,
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
    @method_decorator(never_cache)
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
        }))
class CategoryViewSet(
    CachedResponseMi xin, PaginateByMaxMixin, viewsets.ReadOnlyModelViewSet
):
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
            cat["category_key"]: cat["name"]
            for cat in self.get_queryset().values("category_key", "name")
        }

        return Response(
            {
                "help_text": "Available categories",
                "available_cate gories": available_categories,
            }
        )