from API.filters import InsultFilter
from API.models import Insult
from API.serializers import (
    InsultsListSerializer,
    InsultSerializer,
    MyInsultSerializer,
    AvailableCategoriesSerializer
)
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, OpenApiExample
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
    GenericAPIView
    )
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, status
import random
from thedozens.utils.category_resolver import Resolver
from rest_framework.parsers import JSONParser

class MyInsults(ListAPIView):
    """
    A view to retrieve insults submitted by the authenticated use.
    """

    serializer_class = MyInsultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get the queryset of insults added by the authenticated user.
        """
        return (
            Insult.objects.filter(added_by=self.request.user)
            if self.request.user.is_authenticated
            else Insult.objects.none()
        )
    def list(self, request):
        queryset = self.get_queryset()
        serializer = MyInsultSerializer(queryset, many=True)
        return Response(data=f"'{str(request.user.username)}':{ 'submitted_insults': [{serializer.data}]}")

@extend_schema(
        description="API Get Only Endpoint to provide a list of available insult categories",
    filters=True,
    tags=["Insults"],
    examples=[
        OpenApiExample(name="Successful GET Request",
        status_codes=[status.HTTP_200_OK],
        value={
        "categories" :[ 
            "poor",
            "fat",
            "ugly",
            "stupid",
            "snowflake",
            "old",
            "old_daddy",
            "stupid_daddy",
            "nasty",
            "tall",
            '...'
         ]
        }), OpenApiExample(
            name="UnSuccessful Request (PUT, POST, PATCH)",
            value={    "detail": "Method \"POST\" not allowed."

            }
        )
    ]
)
class InsultCategories(GenericAPIView):
    """
    A view to retrieve available insult categories.
    """

    permission_classes = [AllowAny]
    allowed_methods = ["GET"]
    serializer_class = AvailableCategoriesSerializer()


    def get_queryset(self):
        categories = Insult.CATEGORY.choices
        display_name = [
            category[1] for category in categories if category[0] != "TEST"
        ]
        return Response(display_name)
    
    def get(self, request):
        return self.get_queryset()


@extend_schema(


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
        ), OpenApiParameter(
            name="category",
            type=OpenApiTypes.STR ,
            description="Allows for the filtering of jokes based on their category. Use the `insults/categories` endpoint for a list of acceptable values. Defaults to None Allowing for All categories ",
            required=False,
            location="object",
            default=None,
            allow_blank=True,
            many=True,
            enum=[True, False],
        )
    ],
)
class InsultsCategoriesListView(ListAPIView):
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    serializer_class = InsultsListSerializer(many=True)
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def get_queryset(self, **kwargs):
        category = self.kwargs['category']
        available_categories = {y: x for x, y in Insult.CATEGORY.choices}
        available_categories_list = tuple(sum(available_categories, []))
        logger.debug(available_categories_list)
        if category not in available_categories_list:
            return Insult.objects.none()
        for request_cat_code in available_categories.values():
            return Insult.objects.filter(status="A").filter(
                category=request_cat_code
            )
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if len(queryset) <= 0 :
            return Response(data="Invalid Category. Please Make Get Request to '/insults/categories' for a list of available categories ", status=status.HTTP_404_NOT_FOUND)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema(request=InsultSerializer, responses=InsultSerializer)
class InsultSingleItem(RetrieveAPIView):
    queryset = Insult.objects.all()
    lookup_field = "id"
    serializer_class = InsultSerializer(many=False)
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    permission_classes = [AllowAny]


@extend_schema(request=InsultSerializer, responses=InsultSerializer)
class RandomInsultView(RetrieveAPIView):
    queryset = Insult.objects.all()
    serializer_class = InsultSerializer(many=False)
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    permission_classes = [AllowAny]
    
    def get_queryset(self):
            """
            Optionally restricts the returned purchases to a given user,
            by filtering against a `username` query parameter in the URL.
            """
            queryset = Insult.objects.all()
            nsfw_selection = self.request.query_params.get('nsfw') if self.request.query_params.get('nsfw') is not None else (self.request.data['nsfw'] if self.request.data['nsfw'] is not None else None )
            category_selection = self.request.query_params.get('category') if self.request.query_params.get('category') is not None else (self.request.data['category'] if self.request.data['category'] is not None else None )

            if category is not None:
                resolved_cat = Resolver.resolve(category_selection)
                queryset = queryset.filter(category=resolved_cat)

            if nsfw_selection is not None:
                queryset = queryset.filter(explicit=nsfw_selection)

            return queryset
    def get_object(self):
        """
        Returns the object the view is displaying.

        You may want to override this if you need to provide non-standard
        queryset lookups.  Eg if objects are referenced using multiple
        keyword arguments in the url conf.
        """
        queryset = self.filter_queryset(self.get_queryset())
        return random.choice(queryset)
