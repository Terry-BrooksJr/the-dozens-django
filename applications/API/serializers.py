"""
module: applications.API.serializers
# TODO: Write Module Summary 
"""
import contextlib
from asyncio.log import logger
from datetime import datetime
from functools import lru_cache
from typing import Any, ClassVar, Dict, Optional, Union

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
from common.cache_managers import CategoryCacheManager, create_category_manager


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


class CachedBulkSerializer(serializers.ModelSerializer):
    """
    Base serializer with caching capabilities for bulk operations.
    """

    # Default cache settings (subclasses can override)
    CACHE_TIMEOUT: ClassVar[int] = 300
    CACHE_VERSION: ClassVar[int] = 1

    # Define these in your concrete serializer
    select_related_fields = []  # e.g., ['added_by', 'category']
    prefetch_related_fields = []  # e.g., ['reviews']
    cached_fields = []  # Fields to cache individually

    def get_cache_key(self, obj, field_name: str) -> str:
        """
        Build a stable cache key for a computed field value.
        If the class defines a `cacher` with `get_cache_key`, delegate to it.
        Otherwise, fall back to a deterministic string using class name, model name,
        object primary key, field name, and a version number.
        """
        # Prefer a class-provided cacher if available
        cacher = getattr(type(self), "cacher", None)
        if cacher is not None and hasattr(cacher, "get_cache_key"):
            with contextlib.suppress(Exception):
                return cacher.get_cache_key(obj, field_name)

        model_name = obj.__class__.__name__
        obj_pk = getattr(obj, "pk", None) or getattr(obj, "id", None) or ""
        return f"field:{self.__class__.__name__}:{model_name}:{obj_pk}:{field_name}:v{type(self).CACHE_VERSION}"

    def set_cached_field_value(
        self, obj, field_name: str, value, cache_timeout: int = 300
    ):
        """
        Set a cached value for an expensive field computation.
        """
        if field_name not in self.cached_fields:
            return
        cache_key = self.get_cache_key(obj, field_name)
        cache.set(cache_key, value, cache_timeout)

    def get_cached_field_value(self, obj, field_name: str, compute_method_name: str):
        """
        Retrieve a cached value for a computed field, or compute and cache it if not present.
        This method ensures efficient access to expensive field computations by leveraging caching.

        Args:
            obj: The object for which the field value is being retrieved.
            field_name: The name of the field to cache.
            compute_method_name: The name of the method used to compute the field value.

        Returns:
            The cached or newly computed value for the specified field.
        """
        cache_key = self.get_cache_key(obj, field_name)
        try:
            cached_value = cache.get(cache_key)
        except Exception as e:  # Dragonfly/Redis flakiness => fail open
            logger.warning("Cache backend unavailable while getting %s: %s", field_name, e)
            cached_value = None
        if cached_value is not None:
            return cached_value

        compute = getattr(self, compute_method_name)
        value = compute(obj)
        try:
            cache.set(cache_key, value, timeout=self.CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Cache backend unavailable while setting {field_name}: {e}")
        return value


class BaseInsultSerializer(CachedBulkSerializer):
    cacher: ClassVar[CategoryCacheManager] = create_category_manager(
        model_class=InsultCategory, key_field="category_key", name_field="name"
    )
    category = serializers.SlugRelatedField(
    slug_field="category_key",  # or "name"
    queryset=InsultCategory.objects.all()
)

    @staticmethod
    def _normalize_category_input(value: str) -> str:
        """
        Normalize the input value for a category key or name.
        Returns the category key if a model instance is provided, or a cleaned string otherwise.

        Args:
            value: The category key, name, or model instance.

        Returns:
            str: The normalized category key or name.
        """
        # If a model instance is passed (e.g., during serialization), use its key
        with contextlib.suppress(Exception):

            if isinstance(value, InsultCategory):
                return value.category_key
        if not isinstance(value, str):
            return value
        v = value.strip()
        # Try common separators first
        for sep in (" - ", "–", "-"):
            if sep in v:
                if left := v.split(sep, 1)[0].strip():
                    return left
        return v

    def get_category_by_key(self, category_key: str) -> Dict[str, str]:
        """
        Retrieve category information by its key, using cache for efficiency.
        Returns a dictionary containing the category key and name, or raises a validation error if not found.

        Args:
            category_key: The key of the category to look up.

        Returns:
            Dict[str, str]: A dictionary with 'category_key' and 'category_name'.

        Raises:
            serializers.ValidationError: If the category key does not exist.
        """
        if not category_key:
            return {"category_key": "", "category_name": "Uncategorized"}

        key = self._normalize_category_input(category_key)

        if category_name := type(self).cacher.get_category_name_by_key(key):
            return {"category_key": key, "category_name": category_name}

        # Fallback to database
        try:
            category = InsultCategory.objects.get(category_key=key)
            # Update cache for future requests (targeted update)
            type(self).cacher.set_category_name_mapping(
                category.category_key, category.name
            )
            return {"category_key": key, "category_name": category.name}
        except InsultCategory.DoesNotExist as e:
            raise serializers.ValidationError(
                f"Category with key '{key}' does not exist."
            ) from e

    def _compute_added_on_display(self, obj) -> str:
        """
        Generate a formatted string representation of the 'added_on' datetime for the given object.
        Returns a formatted date string or an empty string if the date is not available.

        Args:
            obj: The object containing the 'added_on' attribute.

        Returns:
            str: The formatted date string or an empty string if not available.
        """
        dt = getattr(obj, "added_on", None)
        if not dt:
            return ""
        try:
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            return str(dt)

    def _compute_added_by_display(self, obj) -> str:
        """
        Generate a display string for the user who added the insult.
        Returns a formatted name, username, or a default string if the user is anonymous.

        Args:
            obj: The object containing the 'added_by' user attribute.

        Returns:
            str: The display name for the user who added the insult.
        """
        user = getattr(obj, "added_by", None)
        if user is None:
            return "Anon Jokester"

        if not user.first_name:
            return user.username
        return (
            f"{user.first_name} {user.last_name[0]}."
            if user.last_name
            else user.first_name
        )

    def get_category_by_name(self, category_name: str) -> Dict[str, str]:
        """
        Retrieve category information by its name.
        Returns a dictionary containing the category key and name, or raises a validation error if not found.

        Args:
            category_name: The name of the category to look up.

        Returns:
            Dict[str, str]: A dictionary with 'category_key' and 'category_name'.

        Raises:
            serializers.ValidationError: If the category name is not a string or does not exist.
        """
        if not category_name:
            return {"category_key": "", "category_name": "Uncategorized"}

        if isinstance(category_name, str):
            normalized_name = category_name.strip()
        else:
            # If a model instance or other type is passed in by mistake, fail fast here
            raise serializers.ValidationError("Category name must be a string.")

        if category_key := type(self).cacher.get_category_key_by_name(normalized_name):
            return {"category_key": category_key, "category_name": normalized_name}

        # Fallback to database
        try:
            category = InsultCategory.objects.get(name__iexact=normalized_name)
            type(self).cacher.set_category_name_mapping(
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
    @classmethod
    def resolve_category(cls, value: str) -> Dict[str, Union[None, str]]:
        """
        Validate and resolve a category by key or name.

        This method checks if the provided value is a valid category key, name, or model instance,
        and returns a dictionary with the resolved category key and name. If the category cannot be
        resolved, a validation error is raised.

        Args:
            value: The category key, name, or InsultCategory instance to validate.

        Returns:
            Dict[str, str]: A dictionary containing 'category_key' and 'category_name'.

        Raises:
            serializers.ValidationError: If the category cannot be resolved by key or name.
        """
        if not value:
            return {"category_key": "", "category_name": "Uncategorized"}



        if isinstance(value, InsultCategory):
            validated = {"category_key": value.category_key, "category_name": value.name}
            logger.debug(f"Serializer Resolved {value} to {validated}")
            return validated
        
        if isinstance(value, str):
            value = cls._normalize_category_input(value)

        # First try as category key
        try:
            validated = {
                "category_key": cls.cacher.get_category_key_by_name(value),
                "category_name": value,
            }
            logger.debug(f'Serializer Resolved {value} to {validated}')
            return validated
        except serializers.ValidationError:
            try:
                validated = {
                    "category_key": value,
                    "category_name": type(self).cacher.get_category_name_by_key(value).lower(),
                }
                logger.debug(f'Serializer Resolved {value} to {validated}')
                return validated
            except serializers.ValidationError as e:
                raise serializers.ValidationError(
                    f"Category '{value}' not found. Please provide a valid category key or name."
                ) from e

    # If you need just the name (for backward compatibility):
    def get_category_name_by_key(self, category_key: str) -> str:
        """
        Retrieve and format the category name for a given category key.
        Returns a consistently formatted category name string.

        Args:
            category_key: The key of the category to look up.

        Returns:
            str: The formatted category name.
        """
        category_info = type(self).cacher.get_category_by_key(category_key)
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

    @extend_schema_field(serializers.CharField())
    def get_added_on_display(self, obj) -> str:
        return self.get_cached_field_value(
            obj,
            "added_on",
            compute_method_name="_compute_added_on_display",
        )

    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_category = None
        if "category" in data:
            raw_category = data["category"]
        elif "category_name" in data:
            raw_category = data["category_name"]
            
        if raw_category is not None and isinstance(raw_category, str):
            category = type(self).resolve_category(raw_category)

            data["category"] = InsultCategory.objects.get(category_key=category["category_key"])

        return super().to_internal_value(data)

    def to_representation(self, instance) -> Dict[str, Any]:  # pyrefly: ignore

        representation = super().to_representation(instance)

        # Use cached category lookup instead of additional DB query
        validated_category = type(self).resolve_category(representation['category'])
        representation["category"] = validated_category["category_name"]

        return representation

    @extend_schema_field(serializers.CharField())
    def get_added_by_display(self, obj) -> Optional[str]:
        return self.get_cached_field_value(
            obj, "added_by", compute_method_name="_compute_added_by_display"
        )


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
                {"category_key": "P", "name": "Poor", "count": 120},
                {"category_key": "S", "name": "Stupid", "count": 33},
                {"category_key": "F", "name": "Fat", "count": 30},
                {"category_key": "L", "name": "Lazy", "count": 10},
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

    category_key = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    count = serializers.ReadOnlyField()
    description = serializers.ReadOnlyField()
    class Meta:
        model = InsultCategory
        fields = ["category_key", "name", "count", "description"]

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
    cached_fields = ["added_by", "added_on"]

    # nsfw = serializers.BooleanField()
    # reference_id = serializers.ReadOnlyField()
    added_by = serializers.SerializerMethodField(method_name="get_added_by_display")
    added_on = serializers.SerializerMethodField(method_name="get_added_on_display")
    # category = serializers.CharField()
    # content = serializers.CharField()

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
    content = serializers.CharField(min_length=60)

    class Meta:
        model = Insult
        fields = ["category", "content", "nsfw"]
        extra_kwargs = {
            "content": {"required": True, "allow_blank": False},
        }
        
    
