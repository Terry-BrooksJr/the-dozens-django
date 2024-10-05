import random
from enum import Enum

from API.filters import InsultFilter
from API.models import Insult
from API.serializers import CategorySerializer, InsultSerializer, MyInsultSerializer
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import status
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from thedozens.utils.category_resolver import Resolver


class MyInsultsViewSet(ModelViewSet):
    """
    MyInsultsViewSet is a viewset for managing insults submitted by authenticated users. It provides functionality to retrieve, update, and delete insults while enforcing user permissions.

    This viewset allows authenticated users to interact with their own submitted insults. It includes methods for retrieving the user's insults, updating an insult, and deleting an insult, ensuring that users can only modify their own submissions.

    Args:
        request: The HTTP request object.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.

    Returns:
        Response: A response object containing the result of the operation.

    Raises:
        PermissionDenied: If a user attempts to update or delete an insult they did not submit.

    Examples:
        To retrieve insults for the authenticated user:
            GET /api/insults/

        To update an insult:
            PATCH /api/insults/{id}/

        To delete an insult:
            DELETE /api/insults/{id}/
    """

    serializer_class = MyInsultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ("category", "status", "added_on")

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Insult.objects.filter(added_by=self.request.user.id)
        return Insult.objects.none()

    def destroy(self, request, *args, **kwargs):
        insult = self.get_object()
        if insult.added_by != request.user:
            return Response(
                {"error": "You cannot delete insults that you did not submit"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        insult = self.get_object()
        if insult.added_by != request.user:
            return Response(
                {"error": "You cannot update insults that you did not submit"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class InsultsCategoriesViewSet(ReadOnlyModelViewSet):
    """
    InsultsCategoriesViewSet is a read-only viewset for retrieving insults based on selected categories. It filters insults by their status and category, ensuring that only active insults in the specified category are returned.

    This viewset allows users to query insults by providing a category parameter. If the specified category is not valid, it returns an empty queryset, ensuring that only relevant insults are accessible.

    Args:
        request: The HTTP request object.

    Returns:
        QuerySet: A queryset of active insults filtered by the specified category, or an empty queryset if the category is invalid.

    Examples:
        To retrieve insults in a specific category:
            GET /api/insults/categories/?category=funny
    """

    available_categories = {y: x for x, y in Insult.CATEGORY.choices}
    serializer_class = InsultSerializer
    filterset_class = InsultFilter

    @extend_schema(
        responses={
            200: inline_serializer(
                name="Available Joke categories",
                fields={
                    "help_text": OpenApiTypes.STR,
                    "available_categories": OpenApiTypes.OBJECT,
                },
            ),
        }
    )
    @action(
        detail=False,
        methods=["GET"],
    )
    def list_available_categories(self, request):
        resp = {
            "help_text": "Please pass the values of the keys to filterable API endpoint",
            "available_categories": self.available_categories,
        }
        return Response(resp, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="category",
                description="Category of the insult",
                required=False,
                type=OpenApiTypes.STR,
                enum=[x for x, y in Insult.CATEGORY.choices],
                location="query",
            ),
            OpenApiParameter(
                name="nsfw",
                description="Explicity content filter to out mature, graphic or violence themed content. <sub>NOTE: While all efforts to eswure this is as accurate as possible, this is an API that con have content contributed that are inaccurate. If this occurs, please report the joke/",
                required=False,
                type=OpenApiTypes.BOOL,
                location="query",
            ),
        ],
        methods=["GET"],
        responses={200: CategorySerializer},
        examples=[
            OpenApiExample(
                "Getting All Jokes In A Category",
                status_codes=[
                    status.HTTP_200_OK,
                ],
                summary="Paginated Listing of all active jokes in  a category",
                description='This endpoint allows API Consumers to get a paginated list of all jokes in a given category i.e. "fat", "poor", "etc.',
                value={
                    "count": 401,
                    "category": "Bald",
                    "results": [
                        {
                            "id": 979885544274460700,
                            "nsfw": False,
                            "content": "Yo mama so bald, you can see what’s on her mind.",
                        },
                        {
                            "id": 979885544274657300,
                            "nsfw": False,
                            "content": "Yo momma is so bald... you can see what's on her mind.",
                        },
                        {
                            "id": 979885544274690000,
                            "nsfw": False,
                            "content": "Yo momma is so bald... even a wig wouldn't help!",
                        },
                        {
                            "id": 979885544274722800,
                            "nsfw": False,
                            "content": "Yo momma is so bald... she had to braids her beard.",
                        },
                    ],
                },
                request_only=False,  # signal that example only applies to requests
                response_only=True,  # signal that example only applies to responses
            ),
            OpenApiExample(
                "Submitting An Invalid Category",
                status_codes=[
                    status.HTTP_404_NOT_FOUND,
                ],
                description='This endpoint allows API Consumers to get a paginated list of all jokes in a given category i.e. "fat", "poor", "etc.',
                value={
                    "data": "Invalid Category. Please Make Get Request to '/insults/categories' for a list of available categories"
                },
                request_only=False,  # signal that example only applies to requests
                response_only=True,  # signal that example only applies to responses
            ),
        ],
    )
    def get_queryset(self):
        category_selection = self.request.query_params.get(
            "category"
        ) or self.request.data.get("category")
        available_categories = {y: x for x, y in Insult.CATEGORY.choices}
        if category_selection not in available_categories:
            return Insult.objects.none()
        return Insult.objects.filter(
            status="A", category=available_categories[category_selection]
        )


class RandomInsultViewSet(ReadOnlyModelViewSet):
    """
    RandomInsultViewSet is a viewset for retrieving a random insult from a collection of available insults. It allows users to filter insults based on categories and NSFW (not safe for work) content.

    This viewset provides a method to fetch a random insult and handles cases where no insults are available. It also includes a method to retrieve a queryset of insults, applying filters based on user-specified parameters for category and NSFW content.

    Args:
        request: The HTTP request object.

    Returns:
        Response: A response object containing the serialized random insult data or an error message if no insults are available.

    Examples:
        To retrieve a random insult:
            GET /api/insults/random/

        To retrieve a random insult in a specific category:
            GET /api/insults/random/?category=funny

        To retrieve a random insult with NSFW content:
            GET /api/insults/random/?nsfw=true`
    """

    serializer_class = InsultSerializer

    @action(detail=False, methods=["get"])
    def random(self, request):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {"error": "No insults available"}, status=status.HTTP_404_NOT_FOUND
            )
        random_insult = random.choice(queryset)
        serializer = self.get_serializer(random_insult)
        return Response(serializer.data)

    def get_queryset(self):
        nsfw_selection = self.request.query_params.get("nsfw")
        category_selection = self.request.query_params.get("category")

        queryset = Insult.objects.all()
        if category_selection:
            resolved_cat = Resolver.resolve(category_selection)
            queryset = queryset.filter(category=resolved_cat)
        if nsfw_selection is not None:
            queryset = queryset.filter(nsfw=nsfw_selection)
        return queryset


# class InsultsCategoriesListView(ListAPIView):
#     filterset_class = InsultFilter
#     serializer_class = InsultSerializer

#     def get_queryset(self):
#         try:
#             category_selection = self.request.query_params.get('category') or self.request.data.get('category')
#             available_categories = {y: x for x, y in Insult.CATEGORY.choices}
#             if category_selection not in available_categories:
#                 return Insult.objects.none()
#             return Insult.objects.filter(status="A", category=available_categories[category_selection])
#         except Exception as e:
#             logger.error(f"ERROR: Unable to Get Categories List: {e} ")


#     def list(self, request, *args, **kwargs):
#         queryset = self.filter_queryset(self.get_queryset())
#         if not queryset.exists():
#             return Response(data="Invalid Category. Please Make Get Request to '/insults/categories' for a list of available categories", status=status.HTTP_404_NOT_FOUND)
#         page = self.paginate_queryset(queryset)
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#         serializer = self.get_serializer(queryset, many=True)
#         return Response(serializer.data)

# @extend_schema(request=InsultSerializer, responses=InsultSerializer)
# class InsultSingleItem(RetrieveAPIView):
#     queryset = Insult.objects.all()
#     lookup_field = "id"
#     serializer_class =   InsultSerializer
#     filterset_class = InsultFilter
#     permission_classes = [AllowAny]


# @extend_schema(request=InsultSerializer, responses=InsultSerializer)
# class RandomInsultView(RetrieveAPIView):
#     queryset = Insult.objects.all()
#     serializer_class = InsultSerializer
#     filterset_class = InsultFilter
#     permission_classes = [AllowAny]


#     def get_queryset(self):
#         nsfw_selection = self.request.query_params.get('nsfw')
#         category_selection = self.request.query_params.get('category') or self.request.data.get('category')

#         queryset = Insult.objects.all()
#         if category_selection:
#             resolved_cat = Resolver.resolve(category_selection)
#             queryset = queryset.filter(category=resolved_cat)
#         if nsfw_selection is not None:
#             queryset = queryset.filter(nsfw=nsfw_selection)
#         return queryset

#     def get_object(self):
#         queryset = self.filter_queryset(self.get_queryset())
#         return random.choice(queryset)
