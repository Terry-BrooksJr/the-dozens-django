from API.filters import InsultFilter
from API.models import Insult
from API.serializers import (
    InsultsCategorySerializer,
    InsultSerializer,
    MyInsultSerializer,
)
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, status

class InsultMe(RetrieveAPIView):
    """
    A view to retrieve insults submitted by the authenticated use.
    """
    serializer_class = InsultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Get the queryset of insults added by the authenticated user.
        """
        nsfw = self.request.get("")
        category = None
        if self.request.user.is_authenticated:
            queryset = Insult.objects.filter(added_by=self.request.user)

        return queryset


class InsultCategories(APIView):    
    """
    A view to retrieve available insult categories.
    """
    permission_classes = [AllowAny]
    allowed_methods = ['GET']
    
    def get(self, request):
        categories = Insult.CATEGORY.choices
        display_name = []
        for category in categories:
            display_name.append(category[1])
        return Response(display_name)


@extend_schema(
    description="API Get Only Endpoint to provide a list of available insult categories",
    parameters=[
        OpenApiParameter(
            name="nfsw",
            type=OpenApiTypes.BOOL,
            description="Allows for the filtering of explicit or content Not Safe For Work(NSFW) Defaults to None, Allowing for All types",
            required=False,
            location="query",
            default=None,
            allow_blank=True,
            many=True,
            enum=[True, False],
        )
    ]
)
class InsultsCategoriesListView(ListAPIView):
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "category"
    serializer_class = InsultsCategorySerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        category = self.kwargs["category"]
        category = category.lower()
        available_categories = dict((y, x) for x, y in Insult.CATEGORY.choices)
        available_categories_list = [[cat.lower()] for cat in Insult.CATEGORY.choices]
        if category not in available_categories_list:
            return Insult.objects.none()
        else:
            for key, value in available_categories.items():
                if key == category:
                    request_cat_code = available_categories[key]
                return Insult.objects.filter(status="A").filter(
                    category=request_cat_code
                )


@extend_schema(request=InsultSerializer, responses=InsultSerializer)
class InsultSingleItem(RetrieveAPIView):
    queryset = Insult.objects.all()
    lookup_field = "id"
    serializer_class = InsultSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    permission_classes = [AllowAny]


@extend_schema(request=InsultSerializer, responses=MyInsultSerializer)
class MyInsultsView(RetrieveUpdateDestroyAPIView):
    serializer_class = InsultSerializer
    filterset_class = InsultFilter
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        """
        This view returns a list of all insults created by the currently
        authenticated user.

        Returns empty list if user Anonymous
        """
        user = self.request.user

        if not user.is_anonymous:
            return Insult.objects.filter(added_by=user)

        return Insult.objects.none()
