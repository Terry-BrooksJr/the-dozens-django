from drf_spectacular.utils import extend_schema, OpenApiParameter
from API.filters import InsultFilter
from API.models import Insult
from API.serializers import (
    InsultsCategorySerializer,
    InsultSerializer,
    MyInsultSerializer,
)
from django_filters import rest_framework as filters
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from rest_framework.views import APIView, status

from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated


class InsultMe(RetrieveAPIView):
    serializer_class = InsultSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        nsfw = self.request.get("")
        category = None

        queryset = queryset  # TODO
        return queryset


class InsultCatergories(APIView):
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        categories = Insult.CATEGORY.choices
        display_name = []
        for category in categories:
            display_name.append(category[1])
        return Response(display_name)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="nfsw",
            type=OpenApiTypes.BOOL,
            description="Allows for the filtering of explicit or content Not Safe For Work(NSFW) Defaults to None, Allowing for All types",
            required=False,
            location="query",
            default=Nonem,
            allow_blank=True,
            many=True,
            enum=[True, False],
        )
    ]
)
class InsultsCatergoriesListView(ListAPIView):
    queryset = Insult.objects.all()
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
        available_categories = [[cat.lower()] for cat in available_categories]
        if category not in available_categories.keys():
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
