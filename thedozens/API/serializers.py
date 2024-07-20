# -*- coding: utf-8 -*-
from API.models import Insult, InsultReview
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers
from rest_framework.views import  status

# @extend_schema_serializer(
#     exclude_fields=('single','last_modified'),
#     examples = [
#          OpenApiExample(
#             'Valid example 1',
#             summary='short summary',
#             description='longer description',
#             value={
#                 'songs': {'top10': True},
#                 'single': {'top10': True}
#             },
#             request_only=True, # signal that example only applies to requests
#             response_only=True, # signal that example only applies to responses
#         ),
#     ]
# )

class InsultSerializer(serializers.ModelSerializer):
    """
    Summary:
    Serializer for Insult model to convert model instances to Python data types.

    Explanation:
    This serializer converts Insult model instances to Python data types for serialization. It includes fields like content, category, NSFW, added_on, and added_by. The `to_representation` method customizes the representation of the serialized data.

    Args:
        instance: The Insult model instance to be serialized.

    Returns:
        dict: A dictionary representing the serialized data.

    Examples:
        serializer = InsultSerializer()
        data = serializer.to_representation(instance)
    """

    category = serializers.CharField(source="get_category_display")
    NSFW = serializers.BooleanField(source="explicit")

    class Meta:
        model = Insult
        read_only_fields = [
            "pk",
        ]
        fields = ["content", "category", "NSFW", "added_on", "added_by"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["added_by"] = (
            f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "
        )
        data["added_by"] = (
            f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "
        )
        return data


@extend_schema_serializer(
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
class InsultsListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insult
        fields = ("id", "content")




class MyInsultSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    NSFW = serializers.BooleanField(source="explicit")

    class Meta:
        model = Insult
        fields = "__all__"


class JokeReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsultReview
        fields = "__all__"

@extend_schema_serializer(
    examples=[
        OpenApiExample(
        "Get All Insult Categories Available in the API",
            summary="Get a listing of all insult categories ",
            description="Returns a list of all insult categories available in the API. That can be used a url path parameters in the <pre>/api/insults/categories/{category}</pre> endpoint.",
            value={
                "data": [
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
  "skinny",
  "bald",
  "hairy",
  "lazy",
  "short"
]},status_codes=[status.HTTP_200_OK])])
class AvailableCategoriesSerializer(serializers.Serializer):
    pass