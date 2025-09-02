# -*- coding: utf-8 -*-
from typing import List as ListType

from graphene import Boolean, Int, ObjectType
from graphene_django import DjangoObjectType

from ..API.filters import InsultFilter
from ..API.models import Insult


class InsultType(DjangoObjectType):
    """GraphQL Object Type for the Insult model."""

    class Meta:
        name = "Insult"
        description = """
        Represents an insult entry with its associated metadata.
        Includes content, category, and moderation status.
        """
        model = Insult
        fields = (
            "insult_id",
            "content",
            "category",
            "nsfw",
            "added_on",
            "added_by",
            "last_modified",
            "status",
        )
        filterset_class = InsultFilter

    # Add computed fields if needed
    is_active = Boolean(description="Indicates if the insult is currently active")

    def resolve_is_active(self, info) -> bool:
        """Resolve whether the insult is active."""
        return self.status == "A"


class InsultConnection(ObjectType):
    """Connection type for pagination."""

    def __init__(self, total_count: Int, items: ListType[InsultType]):
        """
        Initialization method ran at instantiation of each instance
        Args:
            items (InsultType): Sequence of the InsultType
        """
        super().__init__()
        self.total_count = Int(description="Total number of insults in the query")
        # noinspection PyTypeChecker
        self.items = list(items)
