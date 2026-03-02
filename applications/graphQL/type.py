# -*- coding: utf-8 -*-
"""
module: applications.graphQL.type

GraphQL object types and connection types for the Insults API.

This module defines the GraphQL type system used by the schema, including
the primary Insult object type exposed to consumers and the InsultConnection
wrapper used by all paginated list responses. Types declared here are
registered automatically by graphene-django and surfaced in the interactive
schema explorer at /graphql/playground/.
"""

from graphene import Boolean, Int, List, ObjectType
from graphene_django import DjangoObjectType

from ..API.filters import InsultFilter
from ..API.models import Insult


class InsultType(DjangoObjectType):
    """GraphQL object type representing a single Insult resource.

    Exposes the core fields of the Insult model to GraphQL consumers.
    Category and user relationships are surfaced as their respective
    foreign-key representations. The computed ``isActive`` field provides
    a convenience boolean derived from the ``status`` field without
    requiring a separate query.

    Exposed Fields:
        insultId     — Auto-incremented primary key.
        content      — The full text body of the insult.
        category     — The InsultCategory this insult belongs to.
        nsfw         — Whether the insult contains adult or explicit content.
        addedOn      — Date the insult was first submitted to the platform.
        addedBy      — The user who submitted the insult.
        lastModified — Timestamp of the most recent change to this record.
        status       — Moderation workflow state.
                       Valid codes: A (Active), X (Removed), P (Pending),
                       R (Rejected), F (Flagged for Review).
        isActive     — Computed field; ``true`` when ``status`` is Active.
    """

    class Meta:
        name = "Insult"
        description = (
            "A single insult entry with its full metadata. "
            "The `status` field reflects the moderation workflow state "
            "(A=Active, X=Removed, P=Pending, R=Rejected, F=Flagged). "
            "The computed `isActive` field is a convenience boolean that is "
            "`true` when `status` equals Active."
        )
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

    is_active = Boolean(
        description=(
            "Convenience field derived from `status`. "
            "Returns `true` when the insult is Active (status='A'), "
            "`false` for any other moderation state."
        )
    )

    def resolve_is_active(self, info) -> bool:
        """Resolve the computed ``isActive`` convenience field.

        Derives the boolean active state directly from the ``status`` field
        without requiring an additional database query.

        Args:
            info: GraphQL execution context (unused).

        Returns:
            bool: ``True`` if the insult's status is ``"A"`` (Active),
                  ``False`` for any other moderation state.
        """
        return self.status == "A"


class InsultConnection(ObjectType):
    """Paginated wrapper for lists of Insult results.

    Returned by all list-based queries in place of a bare list so that
    consumers receive both the current page of results and the total
    number of matching records. This allows clients to implement accurate
    offset/limit pagination controls without issuing a separate count query.

    Fields:
        totalCount — Total number of records matching the query across all pages.
        items      — The Insult records for the current page.
    """

    total_count = Int(
        description=(
            "Total number of insults that match the query filters, "
            "across all pages. Use this together with `offset` and `limit` "
            "to implement pagination controls."
        )
    )
    items = List(
        InsultType,
        description=(
            "The current page of Insult records. "
            "The number of items returned is bounded by the `limit` argument "
            "supplied to the parent query."
        ),
    )
