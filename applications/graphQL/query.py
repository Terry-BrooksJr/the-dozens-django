from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from graphene import ID, Boolean, Field, Int, NonNull, ObjectType, String
from graphql import GraphQLError

from ..API.models import Insult
from .type import InsultConnection, InsultType


class Query(ObjectType):
    """Root query type for the Insults API."""

    # Single insult queries
    random_insult = Field(
        InsultType,
        description="Get a random active insult",
        category=String(description="Optional category filter for random insult"),
    )

    insult_by_id = Field(
        InsultType,
        reference_id=NonNull(ID, description="Unique identifier of the insult"),
        description="Get a specific insult by its ID",
    )

    # List queries with pagination
    insults_by_category = Field(
        InsultConnection,
        category=NonNull(String, description="Category to filter insults by"),
        offset=Int(default_value=0, description="Number of items to skip"),
        limit=Int(default_value=10, description="Maximum number of items to return"),
        description="Get paginated list of insults by category",
    )

    insults_by_status = Field(
        InsultConnection,
        status=NonNull(String, description="Status to filter insults by"),
        offset=Int(default_value=0),
        limit=Int(default_value=10),
        description="Get paginated list of insults by status",
    )

    insults_by_classification = Field(
        InsultConnection,
        nsfw=NonNull(Boolean, description="NSFW classification to filter by"),
        offset=Int(default_value=0),
        limit=Int(default_value=10),
        description="Get paginated list of insults by NSFW classification",
    )

    def resolve_random_insult(
        root, info, category: Optional[str] = None
    ) -> Optional[Insult]:
        """Resolve a random active insult, optionally filtered by category."""
        queryset = Insult.objects.filter(status="A")
        if category:
            queryset = queryset.filter(category=category)
        return queryset.order_by("?").first()

    def resolve_insult_by_id(root, info, id: str) -> Insult:
        """Resolve an insult by its ID."""
        try:
            return Insult.objects.get(id=id)
        except ObjectDoesNotExist:
            raise GraphQLError(f"Insult with ID {id} not found")

    def resolve_insults_by_category(
        root, info, category: str, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Resolve paginated insults by category."""
        queryset = Insult.objects.filter(status="A", category=category)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)

    def resolve_insults_by_status(
        root, info, status: str, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Resolve paginated insults by status."""
        queryset = Insult.objects.filter(status=status)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)

    def resolve_insults_by_classification(
        root, info, nsfw: bool, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Resolve paginated insults by NSFW classification."""
        queryset = Insult.objects.filter(nsfw=nsfw)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)
