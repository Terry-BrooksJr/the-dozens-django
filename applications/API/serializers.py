"""API Serializers Module

Provides Django REST Framework serializers for the insults API.

This module contains optimized serializers for handling insult data, categories,
and bulk operations with built-in caching capabilities for improved performance.
Includes base classes with common functionality and specialized serializers
for different use cases.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from functools import lru_cache
from typing import Any, ClassVar, Dict, Optional

from django.core.cache import cache
from django.conf import settings
from django.utils.text import capfirst
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema_field,
    extend_schema_serializer,
)
from humanize import naturaltime
from django.utils.translation import gettext_lazy as _
from loguru import logger
from rest_framework import serializers, status
from rest_framework.response import Response
import arrow
from applications.API.models import Insult, InsultCategory, InsultReview
from common.cache_managers import CategoryCacheManager, create_category_manager


class BulkSerializationMixin:
    """Mixin for handling bulk serialization operations.

    Provides optimized methods for bulk serialization with enhanced
    ListSerializer support and metadata handling.
    """

    def get_bulk_serializer_class(self):
        """Get the serializer class optimized for bulk operations.

        Returns:
            class: The serializer class configured for bulk operations.
        """
        return getattr(self, "bulk_serializer_class", self.get_serializer_class())

    def get_bulk_serializer(self, *args, **kwargs):
        """Get a serializer instance configured for bulk operations.

        Returns:
            Serializer: A serializer instance optimized for bulk data.
        """
        serializer_class = self.get_bulk_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    def bulk_serialize_response(self, queryset, extra_data: Optional[Dict] = None):
        """Serialize bulk data with optional metadata.

        Args:
            queryset: The data to serialize
            extra_data: Optional metadata to include in response

        Returns:
            Response: Serialized data with count and metadata
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
        """Store a computed field value in cache.

        Args:
            obj: The model instance
            field_name: Name of the field being cached
            value: The computed value to cache
            cache_timeout: Cache expiration time in seconds
        """
        if field_name not in self.cached_fields:
            return
        cache_key = self.get_cache_key(obj, field_name)
        cache.set(cache_key, value, cache_timeout)

    def get_cached_field_value(self, obj, field_name: str, compute_method_name: str):
        """Retrieve or compute a cached field value.

        Retrieves a cached value for expensive field computations, or computes
        and caches it if not present.

        Args:
            obj: The model instance
            field_name: Name of the field to cache
            compute_method_name: Method name for computing the field value

        Returns:
            The cached or newly computed field value
        """
        cache_key = self.get_cache_key(obj, field_name)
        try:
            cached_value = cache.get(cache_key)
        except Exception as e:  # Dragonfly/Redis flakiness => fail open
            logger.warning(
                "Cache backend unavailable while getting %s: %s", field_name, e
            )
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
    """Base serializer for insult data with category management.

    Provides common functionality for insult serialization including
    category resolution, caching, and field formatting.
    """

    cacher: ClassVar[CategoryCacheManager] = create_category_manager(
        model_class=InsultCategory, key_field="category_key", name_field="name"
    )
    category = serializers.SlugRelatedField(
        slug_field="category_key", queryset=InsultCategory.objects.all()
    )

    @staticmethod
    def _normalize_category_input(value: str) -> str:
        """Normalize category input values.

        Args:
            value: Category key, name, or model instance

        Returns:
            str: Normalized category key or name
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
        """Retrieve category information by key.

        Args:
            category_key: Category key to look up

        Returns:
            Dict containing category_key and category_name

        Raises:
            ValidationError: If category key does not exist
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
            formatted_dt = arrow.get(dt)
            return formatted_dt.humanize(settings.GLOBAL_NOW)
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

        if category_key := type(self).cacher.get_category_key_by_name(
            normalized_name.title()
        ):
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
    def resolve_category(cls, value: str) -> Dict[str, str]:
        """
        Validate and resolve a category by key or name.

        This method checks if the provided value is a valid category key, name, or model instance,
        and returns a dictionary with the resolved category key and name. If the category cannot be
        resolved, a validation error is raised. Supports case-insensitive matching for both keys and names.

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
            validated = {
                "category_key": value.category_key,
                "category_name": value.name,
            }
            if value.category_key is not None and value.name is not None:
                logger.debug(f"Path A: Serializer Resolved {value} to {validated}")
                return validated

        if isinstance(value, str):
            value = cls._normalize_category_input(value)

        # Try case-sensitive category key lookup first (cached)
        if category_name := cls.cacher.get_category_name_by_key(value):
            validated = {
                "category_key": value,
                "category_name": category_name,
            }
            logger.debug(f"Path B: Serializer Resolved {value} to {validated}")
            return validated

        # Try case-sensitive category name lookup (cached)
        if category_key := cls.cacher.get_category_key_by_name(value):
            validated = {
                "category_key": category_key,
                "category_name": value,
            }
            logger.debug(f"Path C:  Serializer Resolved {value} to {validated}")
            return validated

        # Try case-insensitive key lookup via database
        with contextlib.suppress(InsultCategory.DoesNotExist):
            category = InsultCategory.objects.get(category_key__iexact=value)
            validated = {
                "category_key": category.category_key,
                "category_name": category.name,
            }
            logger.debug(
                f"Serializer Resolved {value} to {validated} (case-insensitive key)"
            )
            return validated
        # Try case-insensitive name lookup via database
        with contextlib.suppress(InsultCategory.DoesNotExist):
            category = InsultCategory.objects.get(name__iexact=value)
            validated = {
                "category_key": category.category_key,
                "category_name": category.name,
            }
            logger.debug(
                f"Serializer Resolved {value} to {validated} (case-insensitive name)"
            )
            return validated
        # If all lookups fail, raise validation error
        raise serializers.ValidationError(
            f"Category '{value}' not found. Please provide a valid category key or name."
        )

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
        if category_name := type(self).cacher.get_category_name_by_key(category_key):
            return BaseInsultSerializer.format_category(category_name)
        else:
            raise serializers.ValidationError(
                f"Category key '{category_key}' not found."
            )

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
        """Return a formatted display string for the 'added_on' datetime of an object.

        This method retrieves a cached, human-readable representation of the object's 'added_on' field.

        Args:
            obj: The object containing the 'added_on' attribute.

        Returns:
            str: The formatted date string for display.
        """
        return self.get_cached_field_value(
            obj,
            "added_on",
            compute_method_name="_compute_added_on_display",
        )

    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert input data to native Python objects for validation and deserialization.

        This method processes the input data, resolves the insult category, and prepares the data for further validation.
        Normalizes category input (key or name) to the canonical category_key string so downstream
        CharField / SlugRelatedField validation receives a value of the expected type.

        Args:
            data: The input data dictionary to be deserialized.

        Returns:
            Dict[str, Any]: The validated and deserialized data dictionary.
        """
        raw_category = None
        if "category" in data:
            raw_category = data["category"]
        elif "category_name" in data:
            raw_category = data["category_name"]

        if raw_category is not None and isinstance(raw_category, str):
            resolved = type(self).resolve_category(raw_category)
            # Store the resolved key string — not a model instance — so that
            # DRF field-level validation (CharField / SlugRelatedField) receives
            # a type it can process. The model lookup happens later in
            # validate_category() or via SlugRelatedField's queryset.
            data["category"] = resolved["category_key"]

        return super().to_internal_value(data)

    def to_representation(self, instance) -> Dict[str, Any]:  # type: ignore
        """Convert a model instance to its serialized representation.

        This method returns a dictionary representation of the instance, replacing the category field with its display name using cached lookup.

        Args:
            instance: The model instance to serialize.

        Returns:
            Dict[str, Any]: The serialized representation of the instance.
        """
        representation = super().to_representation(instance)

        # Use cached category lookup instead of additional DB query
        validated_category = type(self).resolve_category(representation["category"])
        representation["category"] = validated_category["category_name"]

        return representation

    @extend_schema_field(serializers.CharField())
    def get_added_by_display(self, obj) -> Optional[str]:
        """Return a formatted display string for the user who added the insult.

        This method retrieves a cached, human-readable representation of the object's 'added_by' field.

        Args:
            obj: The object containing the 'added_by' attribute.

        Returns:
            Optional[str]: The formatted display name for the user who added the insult.
        """
        return self.get_cached_field_value(
            obj, "added_by", compute_method_name="_compute_added_by_display"
        )


class MyInsultSerializer(BaseInsultSerializer):
    """Serializer for user's personal insults.

    Simplified serializer optimized for displaying a user's own insults
    with essential fields and status information.
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
    """Serializer for insult categories.

    Provides read-only access to category information including
    key, name, count, and description.
    """

    category_key = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    count = serializers.ReadOnlyField()
    description = serializers.ReadOnlyField()

    class Meta:
        model = InsultCategory
        fields = ["category_key", "name", "count", "description", "theme_id"]


# Bulk operations serializer for better performance with multiple insults
class BulkInsultSerializer(serializers.ListSerializer):
    """Optimized list serializer for bulk insult operations.

    Provides query optimization for handling multiple insults efficiently
    with proper prefetching of related data.
    """

    def to_representation(self, data):
        """Optimize bulk serialization with prefetching.

        Args:
            data: Queryset or data to serialize

        Returns:
            Serialized representation of the data
        """
        if hasattr(data, "select_related"):
            data = data.select_related("added_by", "category")
        # Note: Django automatically handles prefetching for querysets
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
                    "reference_id": "CACKLE_Xy12",
                    "category": "Stupid",
                    "content": "Yo momma so stupid, she went to the dentist to get Bluetooth.",
                    "status": "Pending",
                    "reports_count": 2,
                },
            ],
            response_only=True,
        ),
        OpenApiExample(
            "Create or Modify an Insult Example",
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
    """Performance-optimized insult serializer.

    Enhanced serializer for bulk operations with caching,
    prefetching, and optimized field selection.
    """

    # Optimization settings
    select_related_fields = ["added_by", "category"]
    prefetch_related_fields = ["reviews"]
    cached_fields = ["added_by", "added_on"]

    # nsfw = serializers.BooleanField()
    # reference_id = serializers.ReadOnlyField()
    by = serializers.SerializerMethodField(method_name="get_added_by_display")
    added = serializers.SerializerMethodField(method_name="get_added_on_display")
    # category = serializers.CharField()
    # content = serializers.CharField()

    class Meta:
        list_serializer_class = BulkInsultSerializer
        model = Insult
        fields = [
            "content",
            "reference_id",
            "category",
            "nsfw",
            "status",
            "added",
            "by",
        ]
        read_only_fields = ["reference_id", "status", "added_by", "added_on"]


class CreateInsultSerializer(BaseInsultSerializer):
    """Serializer for creating new insults.

    Handles insult creation with category validation,
    content requirements, and NSFW classification.
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

    # Read-only response fields
    reference_id = serializers.CharField(read_only=True)
    status = serializers.CharField(source="get_status_display", read_only=True)
    added_by = serializers.SerializerMethodField(method_name="get_added_by_display")
    added_on = serializers.SerializerMethodField(method_name="get_added_on_display")

    class Meta:
        model = Insult
        fields = [
            "reference_id",
            "category",
            "content",
            "nsfw",
            "status",
            "added_by",
            "added_on",
        ]
        extra_kwargs = {
            "content": {"required": True, "allow_blank": False},
        }

    def validate_category(self, value):
        """Resolve a category key or name string to an InsultCategory instance."""
        resolved = self.resolve_category(value)
        try:
            return InsultCategory.objects.get(category_key=resolved["category_key"])
        except InsultCategory.DoesNotExist:
            raise serializers.ValidationError(f"Category '{value}' not found.")

    def create(self, validated_data):
        """Create an Insult, deriving the theme from the resolved category."""
        category = validated_data["category"]
        validated_data["theme"] = category.theme
        return super().create(validated_data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Submit Anonymous Insult Review",
            summary="Submit an anonymous review for an insult",
            description=(
                "Example request payload for submitting an anonymous review using "
                "a known insult reference ID. Since this review is anonymous, no "
                "reporter name or email details are required."
            ),
            value={
                "insult_reference_id": "BURN_1234AB",
                "anonymous": True,
                "review_type": "FLAG_FOR_REVIEW",
                "rationale_for_review": (
                    "The insult targets a protected characteristic and may violate "
                    "community guidelines. Please review and consider removing it "
                    "from public listings based on the platform's content standards."
                ),
                "post_review_contact_desired": False,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Submit Contactable Insult Review",
            summary="Submit a non-anonymous review with contact details",
            description=(
                "Example request payload for a reviewer who is willing to be contacted "
                "about their report. When 'anonymous' is false, first and last name "
                "are required. If 'post_review_contact_desired' is true, an email "
                "address must also be supplied."
            ),
            value={
                "insult_reference_id": "SNAP_9XZ21",
                "anonymous": False,
                "review_type": "Joke Reclassification",
                "rationale_for_review": (
                    "This insult includes personally identifying information and could "
                    "lead to targeted harassment. I am requesting that it be removed "
                    "or restricted, in line with your moderation and safety policies."
                ),
                "reporter_first_name": "Jordan",
                "reporter_last_name": "Brooks",
                "reporter_email": "jordan.brooks@example.com",
                "post_review_contact_desired": True,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Insult Review Response",
            summary="Serialized insult review after successful submission",
            description=(
                "Example of the data structure returned by the API once an insult "
                "review has been successfully created and stored."
            ),
            value={
                "id": 42,
                "insult_reference_id": "SNAP_9XZ21",
                "anonymous": False,
                "review_type": "Joke Removal",
                "rationale_for_review": (
                    "This insult includes personally identifying information and could "
                    "lead to targeted harassment. I am requesting that it be removed "
                    "or restricted, in line with your moderation and safety policies."
                ),
                "reporter_first_name": "Jordan",
                "reporter_last_name": "Brooks",
                "reporter_email": "jordan.brooks@example.com",
                "post_review_contact_desired": True,
            },
            response_only=True,
        ),
    ]
)
class InsultReviewSerializer(serializers.ModelSerializer):
    """Serializer for submitting insult reviews.

    Validates review submissions including insult reference,
    review type, and rationale.
    """

    insult_reference_id = serializers.CharField(
        help_text="Reference ID of the insult being reviewed.",
        required=True,
    )

    anonymous = serializers.BooleanField(
        required=False,
        help_text="Check if you want to remain anonymous",
    )

    review_type = serializers.ChoiceField(
        choices=InsultReview.REVIEW_TYPE.choices,
        help_text="Type of review being submitted.",
        required=True,
    )
    rationale_for_review = serializers.CharField(
        help_text="Detailed rationale for the review. (Minimum 70 characters.)",
        required=True,
        min_length=70,
    )

    class Meta:
        model = InsultReview
        exclude = ["date_submitted", "status", "insult", "reviewer"]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Custom validation with improved error handling.
        """
        cleaned_data = super().validate(attrs)
        logger.debug(f"Type: {type(cleaned_data)} | Value: {cleaned_data}")

        # Normalize and coerce incoming values
        anonymous = bool(cleaned_data.get("anonymous", False))
        reporter_first_name = (cleaned_data.get("reporter_first_name") or "").strip()
        reporter_last_name = (cleaned_data.get("reporter_last_name") or "").strip()
        post_review_contact_desired = bool(
            cleaned_data.get("post_review_contact_desired", False)
        )
        reporter_email = (cleaned_data.get("reporter_email") or "").strip()
        insult_obj_or_value = cleaned_data.get("insult_reference_id")
        review_basis = (cleaned_data.get("rationale_for_review") or "").strip()
        # Support both ModelChoiceField (object) and pre-populated string values
        if hasattr(insult_obj_or_value, "reference_id"):
            ref_id = insult_obj_or_value.reference_id
        else:
            ref_id = str(insult_obj_or_value or "").strip()

        if not ref_id or Insult.get_by_reference_id(ref_id) is None:
            raise serializers.ValidationError(
                _("Invalid Insult ID"),
                code="invalid-insult-id",
            )

        # Ensure downstream code receives the reference-id string
        cleaned_data["insult_reference_id"] = ref_id
        cleaned_data["anonymous"] = anonymous
        cleaned_data["reporter_first_name"] = reporter_first_name
        cleaned_data["reporter_last_name"] = reporter_last_name
        # Validate non-anonymous submissions
        if not anonymous:
            if not reporter_first_name:
                raise serializers.ValidationError(
                    _("First name is required when not submitting anonymously"),
                    code="first-name-required",
                )
            if not reporter_last_name:
                raise serializers.ValidationError(
                    _("Last name is required when not submitting anonymously"),
                    code="last-name-required",
                )

        # Validate contact preference
        if post_review_contact_desired and not reporter_email:
            raise serializers.ValidationError(
                _("Email address is required"),
                code="email-required-for-contact",
            )

        # Validate Min Char Length only when provided
        if review_basis and len(review_basis) < 70:
            raise serializers.ValidationError(
                _(
                    "Please Ensure The Basis of your review request is 70 characters or more."
                )
            )
        return cleaned_data
