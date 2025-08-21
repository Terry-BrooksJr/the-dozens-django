from asyncio.log import logger
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.utils.text import capfirst
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiTypes,
    extend_schema_field,
    extend_schema_serializer,
)
from humanize import naturaltime
from rest_framework import serializers, status
from rest_framework.response import Response

from applications.API.models import Insult, InsultCategory
from common.preformance import CategoryCacheManager


class BulkSerializationMixin:
    """
    Mixin to handle bulk serialization with optimized ListSerializer.
    """

    def get_bulk_serializer_class(self):
        """
        Return the serializer class optimized for bulk operations.
        Override this method to return your optimized serializer.
        """
        return getattr(self, "bulk_serializer_class", self.get_serializer_class())

    def get_bulk_serializer(self, *args, **kwargs):
        """
        Return a serializer instance optimized for bulk operations.
        """
        serializer_class = self.get_bulk_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    def bulk_serialize_response(self, queryset, extra_data: Optional[Dict] = None):
        """
        Serialize bulk data with additional metadata.
        """
        serializer = self.get_bulk_serializer(queryset, many=True)
        response_data = {"results": serializer.data, "count": len(serializer.data)}

        # Add extra metadata if provided
        if extra_data:
            response_data |= extra_data

        return Response(response_data, status=status.HTTP_200_OK)


class OptimizedListSerializer(serializers.ListSerializer):
    """
    Enhanced ListSerializer with better bulk optimization.
    """

    def to_representation(self, data):
        """
        Optimized bulk serialization with caching and prefetching.
        """
        # Optimize queryset if it's not already optimized
        if hasattr(data, "select_related") and not getattr(
            data, "_prefetch_done", False
        ):
            # Get related fields from child serializer
            child_class = self.child.__class__
            select_related = getattr(child_class, "select_related_fields", [])
            prefetch_related = getattr(child_class, "prefetch_related_fields", [])

            if select_related:
                data = data.select_related(*select_related)
            if prefetch_related:
                data = data.prefetch_related(*prefetch_related)

            # Mark as optimized to avoid double optimization
            data._prefetch_done = True

        # Cache serialization context for reuse
        if not hasattr(self, "_cached_context"):
            self._cached_context = self.child.context

        return super().to_representation(data)

    def create(self, validated_data):
        """Optimized bulk create operation."""
        # Use bulk_create for better performance
        ModelClass = self.child.Meta.model
        instances = [ModelClass(**attrs) for attrs in validated_data]

        # Bulk create with ignore_conflicts for better performance
        try:
            return ModelClass.objects.bulk_create(instances, ignore_conflicts=False)
        except Exception:
            # Fallback to individual creation if bulk fails
            return [self.child.create(attrs) for attrs in validated_data]

    def update(self, instance, validated_data):
        """Optimized bulk update operation."""
        # This is more complex and usually handled at the ViewSet level
        # For now, fallback to individual updates
        return super().update(instance, validated_data)


class CachedBulkSerializer(serializers.ModelSerializer):
    """
    Base serializer with caching capabilities for bulk operations.
    """

    # Define these in your concrete serializer
    select_related_fields = []  # e.g., ['added_by', 'category']
    prefetch_related_fields = []  # e.g., ['reviews']
    cached_fields = []  # Fields to cache individually

    def set_cached_field_value(
        self, obj, field_name: str, value, cache_timeout: int = 300
    ):
        """
        Set a cached value for an expensive field computation.
        """
        if field_name not in self.cached_fields:
            return
        cache_key = f"field:{self.__class__.__name__}:{field_name}:{obj.pk}"
        cache.set(cache_key, value, cache_timeout)

    class Meta:
        list_serializer_class = OptimizedListSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._field_cache = {}

    def get_cached_field_value(self, obj, field_name: str, cache_timeout: int = 300):
        """
        Get field value with caching for expensive computations.
        """
        if field_name not in self.cached_fields:
            return None

        cache_key = f"field:{self.__class__.__name__}:{field_name}:{obj.pk}"
        cached_value = cache.get(cache_key)

        if cached_value is None:
            # Field not cached, compute and cache
            method_name = f"get_{field_name}"
            if hasattr(self, method_name):
                cached_value = getattr(self, method_name)(obj)
                cache.set(cache_key, cached_value, cache_timeout)

        return cached_value


class BaseInsultSerializer(CachedBulkSerializer):
    """
    Base serializer for Insult model containing common functionality.
    """

    def get_category_by_key(self, category_key: str) -> Dict[str, str]:
        """
        Get category info by key with caching.
        Returns dict with category_key and category_name.
        """
        if not category_key:
            return {"category_key": "", "category_name": "Uncategorized"}

        if category_name := CategoryCacheManager.get_category_name_by_key(category_key):
            return {
                "category_key": category_key,
                "category_name": category_name,
            }

        # Fallback to database
        try:
            category = InsultCategory.objects.get(category_key=category_key)
            # Update cache for future requests
            CategoryCacheManager.set_category_name_mapping(category_key, category.name)
            return {
                "category_key": category_key,
                "category_name": category.name,
            }
        except InsultCategory.DoesNotExist as e:
            raise serializers.ValidationError(
                f"Category with key '{category_key}' does not exist."
            ) from e

    def get_category_by_name(self, category_name: str) -> Dict[str, str]:
        """
        Get category info by name with caching.
        Returns dict with category_key and category_name.
        """
        if not category_name:
            return {"category_key": "", "category_name": "Uncategorized"}

        normalized_name = category_name.lower()

        if category_key := CategoryCacheManager.get_category_key_by_name(
            normalized_name
        ):
            return {
                "category_key": category_key,
                "category_name": normalized_name,
            }

        # Fallback to database
        try:
            category = InsultCategory.objects.get(name__iexact=normalized_name)
            # Update cache for future requests
            CategoryCacheManager.set_category_name_mapping(
                category.category_key, category.name
            )
            return {
                "category_key": category.category_key,
                "category_name": category.name,
            }
        except InsultCategory.DoesNotExist as e:
            logger.error(f'Category "{category_name}" does not exist.')
            raise serializers.ValidationError(
                f"Category '{category_name}' does not exist."
            ) from e

    def validate_category(self, value: str) -> Dict[str, str]:
        """
        Validate category by key or name and return complete category info.
        Auto-detects whether input is a key or name and resolves the missing value.
        """
        if not value:
            return {"category_key": "", "category_name": "Uncategorized"}

        # First try as category key (keys are typically hyphenated/underscored)
        try:
            return self.get_category_by_key(value)
        except serializers.ValidationError:
            # If key lookup fails, try as category name
            try:
                return self.get_category_by_name(value)
            except serializers.ValidationError as e:
                # Neither key nor name found
                raise serializers.ValidationError(
                    f"Category '{value}' not found. Please provide a valid category key or name."
                ) from e

    # If you need just the name (for backward compatibility):
    def get_category_name_by_key(self, category_key: str) -> str:
        """Get formatted category name by key."""
        category_info = self.get_category_by_key(category_key)
        return BaseInsultSerializer.format_category(category_info["category_name"])

    @staticmethod
    @lru_cache(maxsize=128)
    def _format_date(date_iso: str) -> str:
        """
        Format date using humanize library with caching.
        Uses ISO string for hashable cache key.
        """

        date = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
        return naturaltime(date, future=False, minimum_unit="seconds", months=True)

    @staticmethod
    @lru_cache(maxsize=64)
    def format_category(category: str) -> str:
        """Ensure consistent category formatting with caching."""
        return capfirst(category) if category else "Uncategorized"

    def get_added_on_display(self, obj):
        """Cached date formatting."""
        cached_value = self.get_cached_field_value(obj, "added_on_display")
        if cached_value is not None:
            return cached_value

        if not obj.added_on:
            display_date = ""
        else:
            display_date = self._format_date(obj.added_on.isoformat())

        self.set_cached_field_value(obj, "added_on_display", display_date)
        return display_date

    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override to handle category name to key conversion.
        This allows users to submit category names directly.
        """
        if "category" in data and isinstance(data["category"], str):
            category_name = data["category"].lower()
            category_key = self.validate_category(category_name)["category_key"]
            data["category"] = category_key

        return super().to_internal_value(data)

    def to_representation(self, instance) -> Dict[str, Any]:  # pyrefly: ignore
        """
        Transform the outgoing data with optimized category lookup.
        """
        representation = super().to_representation(instance)

        # Use cached category lookup instead of additional DB query
        if representation.get("category"):
            representation["category"] = self.validate_category(
                representation["category"]
            )["category_name"]

        return representation

    @extend_schema_field(serializers.CharField())
    def get_added_by(self, obj) -> Optional[str]:
        """Optimized added_by formatter matching InsultSerializer logic."""
        cached_value = self.get_cached_field_value(obj, "added_by_name")
        if cached_value is not None:
            return cached_value

        if not obj.added_by:
            return None

        user = obj.added_by

        if user.first_name:
            if user.last_name:
                return f"{user.first_name} {user.last_name[0]}."
            else:
                return user.first_name
        return user.username or "Unknown User"


class MyInsultSerializer(BaseInsultSerializer):
    """
    Simplified serializer for user's own insults.
    Optimized for common user operations.
    """

    status = serializers.CharField(source="get_status_display", read_only=True)
    added_by = serializers.SerializerMethodField()

    class Meta:
        model = Insult
        fields = ["reference_id", "category", "content", "status", "reports_count"]
        read_only_fields = ["reference_id", "status", "added_by", "reports_count"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Category List Example",
            summary="Available Categories",
            description="List of all available insult categories, and the number of jokes",
            value=[
                {"category_key": "P", "name": "Poor", "insult_count": 120},
                {"category_key": "S", "name": "Stupid", "insult_count": 33},
                {"category_key": "F", "name": "Fat", "insult_count": 30},
                {"category_key": "L", "name": "Lazy", "insult_count": 10},
            ],
            response_only=True,
        )
    ]
)
class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for InsultCategory model.
    Simple and efficient category representation.
    """

    category_key = serializers.ReadOnlyField(source="category_key")
    name = serializers.ReadOnlyField(source="name")
    insult_count = serializers.SerializerMethodField(method_name="get_count")

    class Meta:
        model = InsultCategory
        fields = ["category_key","name", "insult_count"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_count(self, instance):
        return Insult.objects.filter(
            category_key=instance.category_key, status=Insult.STATUS.ACTIVE
        ).count()


# Bulk operations serializer for better performance with multiple insults
class BulkInsultSerializer(serializers.ListSerializer):
    """
    Custom ListSerializer for bulk operations.
    Optimizes database queries when handling multiple insults.
    """

    def to_representation(self, data):
        """
        Optimize bulk serialization by prefetching related data.
        """
        # Prefetch related data to avoid N+1 queries
        if hasattr(data, "select_related"):
            data = data.select_related("added_by", "category")
        elif hasattr(data, "__iter__"):
            # For querysets, prefetch related objects
            [obj.insult_id for obj in data if hasattr(obj, "insult_id")]
        return super().to_representation(data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "My Insults List Example",
            summary="List of User's Insults",
            description="Shows a simplified list of insults created by the user",
            value=[
                {
                    "reference_id": "GIGGLE_Nzk1",
                    "category": "One-Off/Unique",
                    "content": "Yo momma is so bald... you can see what''s on her mind.",
                    "status": "Active",
                    "reports_count": 0,
                },
                {
                    "reference_id": "GIGGLE_Nzk1",
                    "category": "Stupid",
                    "content": "Yo momma so stupid, she went to the dentist to get Bluetooth.",
                    "status": "Pending",
                    "reports_count": 2,
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
                "nsfw": False,
            },
            request_only=True,
        ),
    ]
)
class OptimizedInsultSerializer(BaseInsultSerializer):
    """
    Version of InsultSerializer optimized for bulk operations.
    """

    # Optimization settings
    select_related_fields = ["added_by", "category"]
    prefetch_related_fields = ["reviews"]
    cached_fields = ["added_by", "added_on"]  # Cache expensive fields

    status = serializers.CharField(source="get_status_display", read_only=True)
    nsfw = serializers.BooleanField()
    reference_id = serializers.ReadOnlyField()
    added_by = serializers.SerializerMethodField(method_name="get_added_by")
    added_on = serializers.SerializerMethodField(method_name="get_added_on_display")
    category = serializers.SerializerMethodField(method_name="find_category")

    class Meta:
        list_serializer_class = BulkInsultSerializer
        model = Insult
        fields = [
            "reference_id",
            "content",
            "category",
            "status",
            "nsfw",
            "added_by",
            "added_on",
        ]
        read_only_fields = ["reference_id", "status", "added_by", "added_on"]

    def find_category(self, obj) -> str:
        """
        Use cached category name for performance.
        """
        try:
            category = self.validate_category(obj.category)
            return self.format_category(category["category_name"])

        except serializers.ValidationError:
            logger.error(
                f"Invalid category key '{obj.category}' for Insult ID {obj.insult_id}"
            )
            # Fallback to default category if validation fails
            return "Uncategorized"


class CreateInsultSerializer(BaseInsultSerializer):
    """
    Serializer for creating new insults.
    Handles category validation and formatting.
    """

    category = serializers.CharField(
        help_text="Category key or name for the insult.",
        required=True,
        allow_blank=False,
    )
    nsfw = serializers.BooleanField(
        default=False, help_text="Indicates if the insult is NSFW (Not Safe For Work)."
    )

    def validate_category(self, value: str) -> Dict[str, str]:
        """
        Validate category by key or name and return complete category info.
        Auto-detects whether input is a key or name and resolves the missing value.
        """
        return super().validate_category(value)

    class Meta:
        model = Insult
        fields = ["category", "content", "nsfw"]
        extra_kwargs = {
            "content": {"required": True, "allow_blank": False},
        }
