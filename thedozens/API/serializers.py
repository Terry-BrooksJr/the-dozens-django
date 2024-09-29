from API.dataclasses import InsultDataType
from API.models import Insult, InsultReview
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers
from rest_framework.views import status
from arrow import get

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Example Insult',
            summary='Example of an Insult',
            description='This example represents an insult, categorized and created by a user.',
            value={
                "pk": 1,
                "content": "You're so slow, it takes you an hour to cook minute rice.",
                "category": "stupid",
                "NSFW": False,
                "added_on": "2024-09-25",
                "added_by": "john_doe"
            },
            status_codes=[status.HTTP_200_OK]
        )
    ]
)
class InsultSerializer(serializers.ModelSerializer):
    """
    Serializer for Insult model to convert model instances to Python data types.
    """
    content = serializers.CharField()
    added_on = serializers.DateField()
    added_by = serializers.SerializerMethodField()
    category = serializers.ChoiceField(choices=Insult.CATEGORY.choices)
    NSFW = serializers.BooleanField(source="nsfw")

    class Meta:
        model = Insult
        read_only_fields = ["pk"]
        fields = ["pk", "content", "category", "NSFW", "added_on", "added_by"]

    def get_added_by(self, instance) -> str:
        if instance.added_by.first_name:
            if instance.added_by.last_name:
                return f"{instance.added_by.first_name} {instance.added_by.last_name[0]}."
            else:
                return f"{instance.added_by.first_name}."
        return instance.added_by.username

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        category = instance.get_category_display
        dated = get(instance.added_on)
        representation["added_on"] = dated.humanize(granularity=["month", "day", "hour", "minute"])
        representation["category"] = category.capitalize()
        return representation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Simplified Insult Example',
            summary='Simplified Insult Serializer Example',
            description='This example represents a simplified version of an insult for specific API views.',
            value={
                "category": "stupid",
                "content": "You bring everyone so much joy, when you leave the room.",
                "status": "approved"
            },
            status_codes=[status.HTTP_200_OK]
        )
    ]
)
class MyInsultSerializer(serializers.ModelSerializer):
    """
    Serializer for simplified Insult representation.
    """
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Insult
        fields = ["category", "content", "status"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        dated = get(instance.added_on)
        category = instance.get_category_display
        representation["category"] = category.capitalize()
        representation["added_by"] = f"{instance.added_by.first_name} {instance.added_by.last_name[0]}"
        return representation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Joke Report Example',
            summary='Joke Report Serializer Example',
            description='An example report for an insult that was reviewed.',
            value={
                "id": 1,
                "insult": 5,
                "reviewer": "admin",
                "review_comment": "This insult is a bit too harsh.",
                "reviewed_on": "2024-09-27"
            },
            status_codes=[status.HTTP_200_OK]
        )
    ]
)
class JokeReportSerializer(serializers.ModelSerializer):
    """
    Serializer for InsultReview model.
    """
    class Meta:
        model = InsultReview
        fields = "__all__"


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Available Insult Categories",
            summary="Available Insult Categories",
            description="Returns a list of all available insult categories.",
            value={
                "available_categories": [
                    "poor", "fat", "ugly", "stupid", "snowflake", "old", 
                    "old_daddy", "stupid_daddy", "nasty", "tall", "skinny", 
                    "bald", "hairy", "lazy", "short"
                ]
            },
            status_codes=[status.HTTP_200_OK]
        )
    ]
)
class AvailableCategoriesSerializer(serializers.Serializer):
    """
    Serializer to represent available insult categories.
    """
    def to_representation(self, instance):
        return {"available_categories": list(instance)}



