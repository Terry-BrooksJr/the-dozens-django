# -*- coding: utf-8 -*-
from applications.API.models import Insult, InsultReview
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema_field,
    extend_schema_serializer,
)
from humanize import naturaltime as get_natural_time
from rest_framework import serializers
from rest_framework.views import status


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
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            name="NSFW Insult",
            value={
                "pk": 1,
                "content": "Yo Mama so Dumb, She thought a quarterback was a refund",
                "category": "Poor",
                "status": "Approved",
                "NSFW": True,
                "added_by": "love_laughing23",
            },
            description="Example of an NSFW humorous insult approved for use.",
        ),
        OpenApiExample(
            name="Safe Insult",
            value={
                "pk": 2,
                "content": "Your coding style is like a Picasso painting—hard to interpret!",
                "category": "Fat",
                "status": "Pending",
                "NSFW": False,
                "added_by": "Jane S.",
            },
            description="Example of a safe sarcastic insult pending approval.",
        ),
    ]
)
class InsultSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    NSFW = serializers.BooleanField(source="explicit")
    pk = serializers.ReadOnlyField()

    class Meta:
        model = Insult
        fields = "__all__"

    @extend_schema_field(str)  # Add type hint for _get_pk_val
    def _get_pk_val(self):
        return self.pk

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        category = instance.get_category_display()
        dated = get_natural_time(instance.added_on)
        representation["added_on"] = dated.humanize(
            granularity=["month", "day", "hour", "minute"]
        )
        representation["category"] = category.capitalize()
        return representation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Simplified Insult Example",
            summary="Simplified Insult Serializer Example",
            description="This example represents a simplified version of an insult for specific API views.",
            value={
                "category": "stupid",
                "content": "You bring everyone so much joy, when you leave the room.",
                "status": "approved",
            },
            status_codes=[status.HTTP_200_OK],
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
        get(instance.added_on)
        category = instance.get_category_display
        representation["category"] = category.capitalize()
        representation["added_by"] = (
            f"{instance.added_by.first_name} {instance.added_by.last_name[0]}"
        )
        return representation


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Insult
        fields = ["category", "content", "pk", "nsfw"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Joke Report Example",
            summary="Joke Report Serializer Example",
            description="An example report for an insult that was reviewed.",
            value={
                "id": 1,
                "insult": 5,
                "reviewer": "admin",
                "review_comment": "This insult is a bit too harsh.",
                "reviewed_on": "2024-09-27",
            },
            status_codes=[status.HTTP_200_OK],
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
