# -*- coding: utf-8 -*-
"""
module: applications.graphQL.query

Root GraphQL query definitions for the Insults API.

Defines all available read operations — single-item lookups, random
retrieval, and paginated list queries — along with their resolver
implementations. Every public field on the Query type is documented in
the schema and surfaced in the GraphiQL explorer at /graphql/playground/.
"""

from typing import Optional

from graphene import ID, Boolean, Field, Int, NonNull, ObjectType, String
from graphql import GraphQLError

from ..API.models import Insult
from .type import InsultConnection, InsultType


class Query(ObjectType):
    """Root query type providing all read operations for the Insults API.

    ## Available Queries

    ### randomInsult
    Returns a single randomly selected active insult.

    - Optionally scoped to a specific category via the ``category`` argument.
    - Returns ``null`` if no active insults exist (or none match the filter).

    ### insultById
    Returns a specific insult looked up by its integer primary key.

    - Raises a GraphQL error if no insult with the given ID exists.

    ### insultsByCategory
    Returns a paginated list of active insults belonging to a specific category.

    - Only insults with status ``A`` (Active) are included.
    - Supports ``offset`` and ``limit`` for cursor-free pagination.

    ### insultsByStatus
    Returns a paginated list of insults filtered by moderation workflow status.

    - Accepts any valid status code: ``A`` (Active), ``X`` (Removed),
      ``P`` (Pending), ``R`` (Rejected), ``F`` (Flagged).
    - Not restricted to active insults, so administrative consumers can
      inspect insults in any workflow state.

    ### insultsByClassification
    Returns a paginated list of insults filtered by NSFW classification.

    - ``nsfw: true``  → only adult/explicit content.
    - ``nsfw: false`` → only safe-for-work content.
    - Not restricted by status; returns all classification-matching insults.
    """

    # ------------------------------------------------------------------
    # Single-item queries
    # ------------------------------------------------------------------

    random_insult = Field(
        InsultType,
        description=(
            "Return a single randomly selected active insult (status='A'). "
            "Provide the optional `category` argument to restrict the random "
            "draw to insults belonging to that category key (e.g. 'P' for Poor). "
            "Returns `null` when no active insults exist in the requested pool."
        ),
        category=String(
            description=(
                "Optional category key (e.g. 'P') used to narrow the random draw. "
                "When omitted, any active insult is eligible. "
                "Category keys are case-sensitive and must match a valid InsultCategory."
            )
        ),
    )

    insult_by_id = Field(
        InsultType,
        description=(
            "Return the insult with the given integer primary key. "
            "Raises a GraphQL error if no insult with that ID exists."
        ),
        reference_id=NonNull(
            ID,
            description=(
                "The opaque reference ID of the insult to retrieve (e.g. 'GIGGLE_abc123'). "
                "This corresponds to the `referenceId` field on the Insult type."
            ),
        ),
    )

    # ------------------------------------------------------------------
    # Paginated list queries
    # ------------------------------------------------------------------

    insults_by_category = Field(
        InsultConnection,
        description=(
            "Return a paginated list of active insults (status='A') that belong "
            "to the requested category. Use `offset` and `limit` to page through "
            "results; the `totalCount` field on the response reflects all matching "
            "records across every page."
        ),
        category=NonNull(
            String,
            description=(
                "Category key to filter by (e.g. 'P' for Poor, 'F' for Fat). "
                "Must match the `category_key` of a valid InsultCategory. "
                "Case-sensitive."
            ),
        ),
        offset=Int(
            default_value=0,
            description="Number of matching records to skip before returning results. Defaults to 0.",
        ),
        limit=Int(
            default_value=10,
            description="Maximum number of records to return in this page. Defaults to 10.",
        ),
    )

    insults_by_status = Field(
        InsultConnection,
        description=(
            "Return a paginated list of insults filtered by moderation status. "
            "Unlike the category query, this is not restricted to active insults, "
            "allowing administrative consumers to inspect insults in any workflow state. "
            "Use `offset` and `limit` to page through results."
        ),
        status=NonNull(
            String,
            description=(
                "Moderation status code to filter by. "
                "Valid values: 'A' (Active), 'X' (Removed), 'P' (Pending), "
                "'R' (Rejected), 'F' (Flagged for Review)."
            ),
        ),
        offset=Int(
            default_value=0,
            description="Number of matching records to skip before returning results. Defaults to 0.",
        ),
        limit=Int(
            default_value=10,
            description="Maximum number of records to return in this page. Defaults to 10.",
        ),
    )

    insults_by_classification = Field(
        InsultConnection,
        description=(
            "Return a paginated list of insults filtered by NSFW classification. "
            "Pass `nsfw: true` for adult/explicit content, or `nsfw: false` for "
            "safe-for-work content. Results are not restricted by moderation status. "
            "Use `offset` and `limit` to page through results."
        ),
        nsfw=NonNull(
            Boolean,
            description=(
                "NSFW classification to filter by. "
                "`true` returns only adult/explicit insults; "
                "`false` returns only safe-for-work insults."
            ),
        ),
        offset=Int(
            default_value=0,
            description="Number of matching records to skip before returning results. Defaults to 0.",
        ),
        limit=Int(
            default_value=10,
            description="Maximum number of records to return in this page. Defaults to 10.",
        ),
    )

    # ------------------------------------------------------------------
    # Resolvers
    # ------------------------------------------------------------------

    def resolve_random_insult(
        root, info, category: Optional[str] = None
    ) -> Optional[Insult]:
        """Return a randomly selected active insult, optionally scoped to a category.

        Queries active insults (status="A") and uses database-level random
        ordering to select a single result. An optional category key further
        narrows the eligible pool to insults belonging to that category.

        Args:
            root: The root query object (unused).
            info: GraphQL execution context carrying request and schema metadata.
            category: Optional category key (e.g. ``"P"``) to restrict the draw.
                      When omitted or empty, any active insult is eligible.

        Returns:
            Insult: A randomly selected active Insult instance, or ``None`` if no
                    active insults exist in the requested category.
        """
        queryset = Insult.objects.filter(status="A")
        if category:
            queryset = queryset.filter(category=category)
        return queryset.order_by("?").first()

    def resolve_insult_by_id(root, info, reference_id: str) -> Insult:
        """Return the insult with the given primary-key ID.

        Performs a direct primary-key lookup and raises a descriptive
        GraphQL error when the requested insult does not exist, rather
        than returning ``null``, so clients can distinguish a missing
        record from a nullable field.

        Args:
            root: The root query object (unused).
            info: GraphQL execution context carrying request and schema metadata.
            reference_id: The integer primary key of the insult to retrieve.
                          Corresponds to ``Insult.insult_id``.

        Returns:
            Insult: The Insult instance matching the given primary key.

        Raises:
            GraphQLError: If no insult with the given ``reference_id`` exists.
        """
        insult = Insult.get_by_reference_id(reference_id)
        if insult is None:
            raise GraphQLError(f"Insult with ID {reference_id} not found")
        return insult

    def resolve_insults_by_category(
        root, info, category: str, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Return a paginated list of active insults belonging to a specific category.

        Only insults with status ``"A"`` (Active) are included. The
        ``total_count`` on the returned connection reflects all matching rows
        across every page, enabling clients to build accurate pagination
        controls without issuing a separate count query.

        Args:
            root: The root query object (unused).
            info: GraphQL execution context carrying request and schema metadata.
            category: Category key to filter by (e.g. ``"P"`` for Poor).
                      Must match the ``category_key`` of a valid InsultCategory.
            offset: Number of matching records to skip before returning results.
                    Defaults to ``0``.
            limit: Maximum number of records to return in this page.
                   Defaults to ``10``.

        Returns:
            InsultConnection: A connection object containing ``total_count``
                              (all matching records) and the paginated ``items`` list.
        """
        queryset = Insult.objects.filter(status="A", category=category)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)

    def resolve_insults_by_status(
        root, info, status: str, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Return a paginated list of insults filtered by moderation status.

        Unlike the category resolver, this is not restricted to active insults,
        allowing administrative consumers to inspect insults in any moderation
        workflow state. The ``total_count`` on the returned connection reflects
        all matching rows across every page.

        Args:
            root: The root query object (unused).
            info: GraphQL execution context carrying request and schema metadata.
            status: A valid moderation status code — one of ``"A"`` (Active),
                    ``"X"`` (Removed), ``"P"`` (Pending), ``"R"`` (Rejected),
                    or ``"F"`` (Flagged for Review).
            offset: Number of matching records to skip before returning results.
                    Defaults to ``0``.
            limit: Maximum number of records to return in this page.
                   Defaults to ``10``.

        Returns:
            InsultConnection: A connection object containing ``total_count``
                              (all matching records) and the paginated ``items`` list.
        """
        queryset = Insult.objects.filter(status=status)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)

    def resolve_insults_by_classification(
        root, info, nsfw: bool, offset: int = 0, limit: int = 10
    ) -> InsultConnection:
        """Return a paginated list of insults filtered by NSFW classification.

        Does not restrict by moderation status, so results may include insults
        in any workflow state. The ``total_count`` on the returned connection
        reflects all matching rows across every page.

        Args:
            root: The root query object (unused).
            info: GraphQL execution context carrying request and schema metadata.
            nsfw: Pass ``True`` to return only adult/explicit content;
                  pass ``False`` to return only safe-for-work content.
            offset: Number of matching records to skip before returning results.
                    Defaults to ``0``.
            limit: Maximum number of records to return in this page.
                   Defaults to ``10``.

        Returns:
            InsultConnection: A connection object containing ``total_count``
                              (all matching records) and the paginated ``items`` list.
        """
        queryset = Insult.objects.filter(nsfw=nsfw)
        total = queryset.count()
        items = queryset[offset : offset + limit]

        return InsultConnection(total_count=total, items=items)
