
import random

from API.filters import InsultFilter
from API.models import Insult
from API.serializers import (
    AvailableCategoriesSerializer,
    InsultSerializer,
    MyInsultSerializer,
)
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from loguru import logger
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.mixins import DestroyModelMixin, UpdateModelMixin
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, status

from thedozens.utils.category_resolver import Resolver


class MyInsults(UpdateModelMixin, DestroyModelMixin, ListAPIView):
    allowed_methods = ["POST", "PUT", "DELETE"]
    serializer_class = MyInsultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_fields = ('category', 'status', "added_on")

    lookup_field = "pk"

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Insult.objects.filter(added_by=self.request.user.id)
        return Insult.objects.none()

    def list(self, request):
        queryset = self.get_queryset()
        serializer = MyInsultSerializer(queryset, many=True)
        if queryset.exists():
            return Response(data={request.user.username: {'submitted_insults': serializer.data}})
        return Response(data={'results': {
            'error': 'No insults submitted by this user'
        }})
    
    def delete(self, request, pk):
        pass

    def post(self, request):

        if self.request.user.is_anonymous:
            return Response({"error": "You must be logged in to submit an insult"}, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    def put(self, request, pk):
        insult = get_object_or_404(Insult, pk=pk)
        serializer = MyInsultSerializer(insult, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
@extend_schema(
    description="API GET Endpoint returning all the Insults Submitted by the Authenticated User. Will Return ",
    filters=True,
    tags=["Insults"],
    examples=[
        OpenApiExample(
            name="Successful GET Request",
            status_codes=[status.HTTP_200_OK],
            value={"categories": ["poor", "fat", "ugly", "stupid", "snowflake", "old", "old_daddy", "stupid_daddy", "nasty", "tall", '...']}
        ),
        OpenApiExample(
            name="UnSuccessful Request (PUT, POST, PATCH)",
            value={"detail": "Method \"POST\" not allowed."}
        )
    ]
)
class InsultCategories(GenericAPIView):

    permission_classes = [AllowAny]
    allowed_methods = ["GET"]
    serializer_class = AvailableCategoriesSerializer
    queryset = Insult.objects.none()

    def get(self, request):
        categories = [category[1] for category in Insult.CATEGORY.choices if category[0] != "TEST"]
        return Response(categories)


@extend_schema(
    # parameters=[
    #     OpenApiParameter(
    #         name="nfsw",
    #         type=bool,
    #         required=False,
    #         location="query",
    #         default=None,
    #         allow_blank=True,
    #     ),

    #     OpenApiParameter(
    #         name="category",
    #         # type=str,
    #         required=False,
    #         location="object",
    #         default=None,
    #         allow_blank=True,

    #     )
    # ],    
    examples=[
        OpenApiExample(
            "Getting All Jokes In A Category",
            status_codes=[status.HTTP_200_OK,],
            summary="Paginated Listing of all active jokes in  a category",
            description='This endpoint allows API Consumers to get a paginated list of all jokes in a given category i.e. "fat", "poor", "etc.',
            value={
                "count": 401,
                "next": "http://127.0.0.1:8000/api/insults/P?page=2",
                "previous": "null",
                "results": [
                    {
                        "id": 979885544274460700,
                        "content": "Yo mama so bald, you can see what’s on her mind.",
                    },
                    {
                        "id": 979885544274657300,
                        "content": "Yo momma is so bald... you can see what's on her mind.",
                    },
                    {
                        "id": 979885544274690000,
                        "content": "Yo momma is so bald... even a wig wouldn't help!",
                    },
                    {
                        "id": 979885544274722800,
                        "content": "Yo momma is so bald... she had to braids her beard.",
                    },
                ],
            },
            request_only=False,  # signal that example only applies to requests
            response_only=True,  # signal that example only applies to responses
        ),OpenApiExample(
            "Submitting An Invalid Category",
            status_codes=[status.HTTP_404_NOT_FOUND,],
            description='This endpoint allows API Consumers to get a paginated list of all jokes in a given category i.e. "fat", "poor", "etc.',
            value={
                "data": "Invalid Category. Please Make Get Request to '/insults/categories' for a list of available categories"
            },
            request_only=False,  # signal that example only applies to requests
            response_only=True,  # signal that example only applies to responses
        ),
    ]
        
)
class InsultsCategoriesListView(ListAPIView):
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    serializer_class = InsultSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        try:
            category_selection = self.request.query_params.get('category') or self.request.data.get('category')
            available_categories = {y: x for x, y in Insult.CATEGORY.choices}
            if category_selection not in available_categories:
                return Insult.objects.none()
            return Insult.objects.filter(status="A", category=available_categories[category_selection])
        except Exception as e:
            logger.error(f"ERROR: Unable to Get Categories List: {e} ")


    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(data="Invalid Category. Please Make Get Request to '/insults/categories' for a list of available categories", status=status.HTTP_404_NOT_FOUND)
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
    serializer_class =   InsultSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    permission_classes = [AllowAny]


@extend_schema(request=InsultSerializer, responses=InsultSerializer)
class RandomInsultView(RetrieveAPIView):
    queryset = Insult.objects.all()
    serializer_class = InsultSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter  
    permission_classes = [AllowAny]


    def get_queryset(self):
        nsfw_selection = self.request.query_params.get('nsfw') 
        category_selection = self.request.query_params.get('category') or self.request.data.get('category')

        queryset = Insult.objects.all()
        if category_selection:
            resolved_cat = Resolver.resolve(category_selection)
            queryset = queryset.filter(category=resolved_cat)
        if nsfw_selection is not None:
            queryset = queryset.filter(nsfw=nsfw_selection)
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        return random.choice(queryset)
