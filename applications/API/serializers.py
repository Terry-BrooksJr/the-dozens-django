# from rest_framework import serializers
# from drf_spectacular.utils import (
#     OpenApiExample,
#     extend_schema_field,
#     extend_schema_serializer,
#     OpenApiParameter,
# )
# from humanize import naturaltime
# from rest_framework.views import status
# from django.utils.text import capfirst

# from applications.API.models import Insult, InsultReview, InsultCategory


# class BaseInsultSerializer(serializers.ModelSerializer):
#     """
#     Base serializer for Insult model containing common functionality.
#     """
#     category = serializers.CharField(source="get_category_display")

#     def format_date(self, date):
#         """Format date using humanize library."""
#         return naturaltime(date).humanize(
#             granularity=["month", "day", "hour", "minute"]
#         )

#     def format_category(self, category):
#         """Ensure consistent category formatting."""
#         return capfirst(category)


# @extend_schema_serializer(
#     examples=[
#         OpenApiExample(
#             name="NSFW Insult Example",
#             value={
#                 "id": 10000987765,
#                 "content": "Yo Mama's so Dumb, She thought a quarterback was a refund",
#                 "category": "Poor",
#                 "status": "Active",
#                 "nsfw": True,
#                 "added_by": "John D.",
#                 "added_on": "2 months ago"
#             },
#             description="Example of an NSFW humorous insult that has been approved.",
#             response_only=True
#         ),
#         OpenApiExample(
#             name="Safe Insult Example",
#             value={
#                 "id": 678867900002,
#                 "content": "Yo Mama's coding style is like a Picasso painting—hard to interpret!",
#                 "category": "Stupid",
#                 "status": "Pending",
#                 "nsfw": False,
#                 "added_by": "Jane S.",
#                 "added_on": "5 days ago"
#             },
#             description="Example of a safe sarcastic insult pending approval.",
#             response_only=True
#         ),
#         OpenApiExample(
#             name="Create Insult Request",
#             value={
#                 "content": "Your code has more bugs than a roach motel!",
#                 "category": "Programming",
#                 "nsfw": False
#             },
#             description="Example request body for creating a new insult.",
#             request_only=True
#         )
#     ],
#     # parameters=[
#     #     OpenApiParameter(
#     #         name="content",
#     #         description="The actual text content of the insult",
#     #         required=True,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="category",
#     #         description="The category the insult belongs to (e.g., 'Programming', 'Poor', 'Stupid')",
#     #         required=True,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="nsfw",
#     #         description="Flag indicating if the content is Not Safe For Work",
#     #         required=True,
#     #         type=bool
#     #     ),
#     #     OpenApiParameter(
#     #         name="status",
#     #         description="Current status of the insult (read-only)",
#     #         required=False,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="added_by",
#     #         description="Username of the person who added the insult (read-only)",
#     #         required=False,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="added_on",
#     #         description="Timestamp when the insult was added (read-only)",
#     #         required=False,
#     #         type=str
#     #     )
#     # ]
# )
# class InsultSerializer(BaseInsultSerializer):
#     """
#     Main serializer for the Insult model with full field representation.
#     Handles both creation and retrieval of insults with proper field validation.
#     """
#     status = serializers.CharField(source="get_status_display", read_only=True)
#     nsfw = serializers.BooleanField(source="explicit")
#     id = serializers.ReadOnlyField()
#     added_by = serializers.SerializerMethodField()

#     class Meta:
#         model = Insult
#         fields = [
#             'id', 'content', 'category', 'status',
#             'nsfw', 'added_by', 'added_on'
#         ]
#         read_only_fields = ['id', 'status', 'added_by', 'added_on']

#     def get_added_by(self, obj):
#         if not obj.added_by:
#             return None
#         return f"{obj.added_by.first_name} {obj.added_by.last_name[0]}."

#     def to_representation(self, instance):
#         representation = super().to_representation(instance)
#         representation['added_on'] = self.format_date(instance.added_on)
#         representation['category'] = self.format_category(representation['category'])
#         return representation


# @extend_schema_serializer(
#     examples=[
#         OpenApiExample(
#             "My Insults List Example",
#             summary="List of User's Insults",
#             description="Shows a simplified list of insults created by the user",
#             value=[{
#                 "category": "Poor",
#                 "content": "Your code runs slower than a turtle in molasses",
#                 "status": "Active",
#                 "added_by": "John D."
#             }, {
#                 "category": "Stupid",
#                 "content": "You bring everyone so much joy when you leave the room",
#                 "status": "Pending",
#                 "added_by": "John D."
#             }],
#             response_only=True
#         ),
#         OpenApiExample(
#             "Create My Insult Example",
#             summary="Create New Insult",
#             description="Example request for creating a new insult",
#             value={
#                 "category": "Poor",
#                 "content": "Your code is like a maze - confusing and full of dead ends"
#             },
#             request_only=True
#         )
#     ]
#     # parameters=[
#     #     OpenApiParameter(
#     #         name="category",
#     #         description="Category of the insult",
#     #         required=True,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="content",
#     #         description="The insult text content",
#     #         required=True,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="status",
#     #         description="Current status (read-only)",
#     #         required=False,
#     #         type=str
#     #     )
#     # ]
# )
# class MyInsultSerializer(BaseInsultSerializer):
#     """
#     Simplified serializer for user's own insults.
#     Provides a streamlined view for insult creation and listing.
#     """
#     status = serializers.CharField(source="get_status_display", read_only=True)
#     added_by = serializers.SerializerMethodField()

#     class Meta:
#         model = Insult
#         fields = ['category', 'content', 'status', 'added_by']
#         read_only_fields = ['status', 'added_by']

#     def get_added_by(self, obj):
#         if not obj.added_by:
#             return None
#         return f"{obj.added_by.first_name} {obj.added_by.last_name[0]}."

#     def to_representation(self, instance):
#         representation = super().to_representation(instance)
#         representation['category'] = self.format_category(representation['category'])
#         return representation


# @extend_schema_serializer(
#     examples=[
#         OpenApiExample(
#             "Category List Example",
#             summary="Available Categories",
#             description="List of all available insult categories",
#             value=[{
#                 "key": "P",
#                 "name": "Poor"
#             }, {
#                 "key": "S",
#                 "name": "Stupid"
#             }],
#             response_only=True
#         )
#     ],
#     # parameters=[
#     #     OpenApiParameter(
#     #         name="key",
#     #         description="Unique identifier for the category",
#     #         required=True,
#     #         type=str
#     #     ),
#     #     OpenApiParameter(
#     #         name="name",
#     #         description="Display name of the category",
#     #         required=True,
#     #         type=str
#     #     )
#     # ]
# )
# class CategorySerializer(serializers.ModelSerializer):
#     """
#     Serializer for InsultCategory model.
#     Handles the listing and retrieval of insult categories.
#     """
#     class Meta:
#         model = InsultCategory
#         fields = ['key', 'name']

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema_field,
    extend_schema_serializer,
)
from humanize import naturaltime
from rest_framework import serializers

from applications.API.models import Insult, InsultCategory


class BaseInsultSerializer(serializers.ModelSerializer):
    """
    Base serializer for Insult model containing common functionality.
    """

    category = serializers.PrimaryKeyRelatedField(
        queryset=InsultCategory.objects.all(), pk_field=serializers.CharField()
    )

    def format_date(self, date):
        """Format date using humanize library."""
        # Use caching to prevent repeated calculations
        if not hasattr(self, "_formatted_dates"):
            self._formatted_dates = {}

        cache_key = date.isoformat() if date else None
        if cache_key and cache_key in self._formatted_dates:
            return self._formatted_dates[cache_key]

        formatted = naturaltime(date, future=False, minimum_unit="minutes", months=True)

        if cache_key:
            self._formatted_dates[cache_key] = formatted

        return formatted


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            name="NSFW Insult Example",
            value={
                "id": 10000987765,
                "content": "Yo Mama's so Dumb, She thought a quarterback was a refund",
                "category": "Poor",
                "status": "Active",
                "nsfw": True,
                "added_by": "John D.",
                "added_on": "2 months ago",
            },
            description="Example of an NSFW humorous insult that has been approved.",
            response_only=True,
        ),
        OpenApiExample(
            name="Safe Insult Example",
            value={
                "id": 678867900002,
                "content": "Yo Mama's coding style is like a Picasso painting—hard to interpret!",
                "category": "Stupid",
                "status": "Pending",
                "nsfw": False,
                "added_by": "Jane S.",
                "added_on": "5 days ago",
            },
            description="Example of a safe sarcastic insult pending approval.",
            response_only=True,
        ),
        OpenApiExample(
            name="Create Insult Request",
            value={
                "content": "Your code has more bugs than a roach motel!",
                "category": "Programming",
                "nsfw": False,
            },
            description="Example request body for creating a new insult.",
            request_only=True,
        ),
    ]
)
class InsultSerializer(BaseInsultSerializer):
    """
    Main serializer for the Insult model with full field representation.

    Handles both creation and retrieval of insults with proper field validation.
    Provides comprehensive information about each insult including metadata.

    Attributes:
        id (int): Unique identifier for the insult (read-only)
        content (str): The actual text content of the insult
        category (str): The category the insult belongs to (formatted display name)
        status (str): Current status of the insult (e.g., 'Active', 'Pending')
        nsfw (bool): Flag indicating if the content is Not Safe For Work
        added_by (str): Username of the person who added the insult
        added_on (str): Humanized timestamp when the insult was added
    """

    status = serializers.CharField(source="get_status_display", read_only=True)
    nsfw = serializers.BooleanField()
    id = serializers.ReadOnlyField()
    added_by = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_added_by(self, obj):
        """Format the added_by field to protect user privacy."""
        try:
            if not obj.added_by:
                return None
            elif obj.added_by.first_name and not obj.added_by.last_name:
                return f"{obj.added_by.first_name}"
            elif not obj.added_by.first_name or not obj.added_by.last_name:
                return f"{obj.added_by.username}"
            return f"{obj.added_by.first_name} {obj.added_by.last_name[0]}."
        except IndexError:
            return "Unknown User."

    class Meta:
        model = Insult
        fields = ["id", "content", "category", "status", "nsfw", "added_by", "added_on"]
        read_only_fields = ["id", "status", "added_by", "added_on"]

    def to_representation(self, instance):
        """
        Transform the outgoing data to desired format.
        Applies date formatting and ensures proper category display.
        """
        representation = super().to_representation(instance)
        representation["added_on"] = self.format_date(instance.added_on)
        representation["category"] = representation["category"].title()
        return representation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "My Insults List Example",
            summary="List of User's Insults",
            description="Shows a simplified list of insults created by the user",
            value=[
                {
                    "category": "Poor",
                    "content": "Your code runs slower than a turtle in molasses",
                    "status": "Active",
                    "added_by": "John D.",
                },
                {
                    "category": "Stupid",
                    "content": "You bring everyone so much joy when you leave the room",
                    "status": "Pending",
                    "added_by": "John D.",
                },
            ],
            response_only=True,
        ),
        OpenApiExample(
            "Create My Insult Example",
            summary="Create New Insult",
            description="Example request for creating a new insult",
            value={
                "category": "Poor",
                "content": "Your code is like a maze - confusing and full of dead ends",
            },
            request_only=True,
        ),
    ]
)
class MyInsultSerializer(BaseInsultSerializer):
    """
    Simplified serializer for user's own insults.

    Provides a streamlined view for insult creation and listing.
    Focused on the most relevant fields for user-created content.

    Attributes:
        category (str): Category of the insult (formatted display name)
        content (str): The actual text content of the insult
        status (str): Current status of the insult (read-only)
        added_by (str): Username of the person who added the insult (read-only)
    """

    status = serializers.CharField(source="get_status_display", read_only=True)
    added_by = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_added_by(self, obj):
        """Format the added_by field to protect user privacy."""
        if not obj.added_by:
            return None
        return f"{obj.added_by.first_name} {obj.added_by.last_name[0]}."

    class Meta:
        model = Insult
        fields = ["category", "content", "status", "added_by"]
        read_only_fields = ["status", "added_by"]

    def to_representation(self, instance):
        """Apply proper formatting to category names."""
        representation = super().to_representation(instance)
        representation["category"] = self.format_category(representation["category"])
        return representation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Category List Example",
            summary="Available Categories",
            description="List of all available insult categories",
            value=[
                {"category_key": "P", "name": "Poor"},
                {"category_key": "S", "name": "Stupid"},
                {"category_key": "F", "name": "Fat"},
            ],
            response_only=True,
        )
    ]
)
class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for InsultCategory model.

    Handles the listing and retrieval of insult categories.

    Attributes:
        category_key (str): Unique identifier for the category
        name (str): Display name of the category
    """

    class Meta:
        model = InsultCategory
        fields = ["category_key", "name"]
