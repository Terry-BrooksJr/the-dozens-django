from API.models import Insult, InsultReview
from API.dataclasses import InsultDataType
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers
from rest_framework.views import  status
from django.contrib.auth.models import User
from rest_framework_dataclasses.fields import EnumField
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
    content = serializers.CharField()
    added_on = serializers.DateField()
    added_by = serializers.PrimaryKeyRelatedField(read_only=True, many=False)
    category = serializers.ChoiceField(choices=Insult.CATEGORY.choices)
    NSFW = serializers.BooleanField(source="explicit" )

    class Meta:
        dataclass = InsultDataType
        model = Insult
        read_only_fields = [
            "pk",
        ]
        fields = ["pk","content", "category", "NSFW", "added_on", "added_by"]
    def get_category_display(self):
        return self.get_category(self.instance.category)
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["category"] = instance.get_category_display()
        if instance.added_by.first_name and instance.added_by.last_name:
            representation["added_by"] = f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "
        elif instance.added_by.first_name: 
            representation["added_by"] = f"{instance.added_by.first_name}. "
        else:
            representation["added_by"] = instance.added_by.username
        return representation


@extend_schema_serializer(

)
        # class InsultsListSerializer(serializers.ModelSerializer):
        #     category = serializers.CharField(source="get_category_display")
        #     NSFW = serializers.BooleanField(source="explicit" )

        #     class Meta:
        #         model = Insult
        #         fields = ("content", "category", "NSFW", "added_on", "added_by")

        #     def to_representation(self, instance):
        #         representation = super().to_representation(instance)
        #         representation["added_by"] = (
        #             f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "
        #         )
        #         representation["added_by"] = (
        #             f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}. "
        #         )
        #         return representation



class MyInsultSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    status = serializers.CharField(source="get_status_display")
    NSFW = serializers.BooleanField(source="explicit")

    class Meta:
        model = Insult
        fields = "__all__"
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["category"] = representation["category"].capitalize()
        representation["added_by"] = f"{ instance.added_by.first_name} {instance.added_by.last_name[0]}"
        
    

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
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["available_categories"] = []
        for category in instance:
            representation["available_categories"].append(category)
        return representation

class InsultReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsultReview