# -*- coding: utf-8 -*-
"""
Edge-case and supplemental tests for applications.graphQL.query

These tests complement the happy-path coverage in test_query.py and focus on:
- randomInsult returns null when the active-insult pool is empty.
- insultsByStatus for the Removed, Rejected, and Flagged status codes.
- insultsByCategory excludes pending/non-active insults.
- insultsByClassification pagination (offset/limit).
- insultsByStatus pagination (offset/limit).
- insultById raises a GraphQL error for every non-existent lookup.
"""

import json

from django.contrib.auth import get_user_model
from graphene_django.utils.testing import GraphQLTestCase

from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()
GRAPHQL_ENDPOINT = "/graphql/"


class GraphQLInsultQueryEdgeCaseTests(GraphQLTestCase):
    """Edge cases for all five query resolvers."""

    GRAPHQL_URL = GRAPHQL_ENDPOINT

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="edge_user",
            email="edge@example.com",
            password="pass1234",
        )
        cls.theme = Theme.objects.create(theme_key="EC", theme_name="Edge Case Theme")
        cls.cat_a = InsultCategory.objects.create(
            category_key="ECA", name="Edge Cat A", theme=cls.theme
        )
        cls.cat_b = InsultCategory.objects.create(
            category_key="ECB", name="Edge Cat B", theme=cls.theme
        )

        # One insult per non-Active status so we can query each independently
        for status_code in ("X", "P", "R", "F"):
            Insult.objects.create(
                content=f"Edge insult status {status_code}",
                category=cls.cat_a,
                nsfw=False,
                theme=cls.theme,
                status=status_code,
                added_by=cls.user,
            )

        # Several active insults for pagination tests
        for i in range(5):
            Insult.objects.create(
                content=f"Edge active insult {i}",
                category=cls.cat_b,
                nsfw=(i % 2 == 0),  # alternate NSFW flag
                theme=cls.theme,
                status=Insult.STATUS.ACTIVE,
                added_by=cls.user,
            )

    # -------------------------------------------------------------------------
    # randomInsult — empty pool
    # -------------------------------------------------------------------------

    def test_random_insult_empty_category_returns_null(self):
        """randomInsult(category) returns null when pool has no active insults."""
        # cat_a has only non-Active insults.
        response = self.query("""
            query {
                randomInsult(category: "ECA") {
                    referenceId
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["randomInsult"]
        self.assertIsNone(data)

    def test_random_insult_nonexistent_category_returns_null(self):
        """randomInsult returns null when the category key doesn't exist at all."""
        response = self.query("""
            query {
                randomInsult(category: "XXXXXX") {
                    referenceId
                }
            }
            """)
        self.assertResponseNoErrors(response)
        self.assertIsNone(json.loads(response.content)["data"]["randomInsult"])

    # -------------------------------------------------------------------------
    # insultById — non-existent IDs
    # -------------------------------------------------------------------------

    def test_insult_by_id_zero_returns_error(self):
        """insultById(referenceId: "0") raises a GraphQL error."""
        response = self.query("""
            query {
                insultById(referenceId: "0") {
                    referenceId
                }
            }
            """)
        self.assertResponseHasErrors(response)

    def test_insult_by_id_very_large_id_returns_error(self):
        """insultById raises a GraphQL error for an unreachable ID."""
        response = self.query("""
            query {
                insultById(referenceId: "2147483647") {
                    referenceId
                }
            }
            """)
        self.assertResponseHasErrors(response)

    def test_insult_by_id_error_message_contains_id(self):
        """GraphQL error message for a missing insult mentions the requested ID."""
        response = self.query("""
            query {
                insultById(referenceId: "99999999") {
                    referenceId
                }
            }
            """)
        body = json.loads(response.content)
        errors = body.get("errors", [])
        self.assertTrue(any("99999999" in e.get("message", "") for e in errors))

    # -------------------------------------------------------------------------
    # insultsByStatus — non-Active status codes
    # -------------------------------------------------------------------------

    def test_insults_by_status_removed(self):
        """insultsByStatus(status: 'X') returns insults with Removed status."""
        response = self.query("""
            query {
                insultsByStatus(status: "X") {
                    totalCount
                    items { status }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertGreaterEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertEqual(item["status"], "X")

    def test_insults_by_status_rejected(self):
        """insultsByStatus(status: 'R') returns insults with Rejected status."""
        response = self.query("""
            query {
                insultsByStatus(status: "R") {
                    totalCount
                    items { status }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertGreaterEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertEqual(item["status"], "R")

    def test_insults_by_status_flagged(self):
        """insultsByStatus(status: 'F') returns insults with Flagged status."""
        response = self.query("""
            query {
                insultsByStatus(status: "F") {
                    totalCount
                    items { status }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertGreaterEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertEqual(item["status"], "F")

    def test_insults_by_status_unknown_returns_empty(self):
        """insultsByStatus for an unknown status code returns zero results."""
        response = self.query("""
            query {
                insultsByStatus(status: "Z") {
                    totalCount
                    items { referenceId }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertEqual(data["totalCount"], 0)
        self.assertEqual(len(data["items"]), 0)

    # -------------------------------------------------------------------------
    # insultsByStatus — pagination
    # -------------------------------------------------------------------------

    def test_insults_by_status_pagination_offset(self):
        """insultsByStatus respects offset — skips the first N results."""
        # All 5 active insults from cat_b
        resp_all = self.query("""
            query {
                insultsByStatus(status: "A", offset: 0, limit: 100) {
                    totalCount
                    items { referenceId }
                }
            }
            """)
        self.assertResponseNoErrors(resp_all)
        total = json.loads(resp_all.content)["data"]["insultsByStatus"]["totalCount"]

        resp_offset = self.query(f"""
            query {{
                insultsByStatus(status: "A", offset: {total}, limit: 10) {{
                    totalCount
                    items {{ referenceId }}
                }}
            }}
            """)
        self.assertResponseNoErrors(resp_offset)
        data = json.loads(resp_offset.content)["data"]["insultsByStatus"]
        self.assertEqual(data["totalCount"], total)
        self.assertEqual(len(data["items"]), 0)

    def test_insults_by_status_pagination_limit(self):
        """insultsByStatus(limit: 2) returns at most 2 items."""
        response = self.query("""
            query {
                insultsByStatus(status: "A", offset: 0, limit: 2) {
                    totalCount
                    items { referenceId }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertLessEqual(len(data["items"]), 2)

    # -------------------------------------------------------------------------
    # insultsByCategory — excludes non-Active insults
    # -------------------------------------------------------------------------

    def test_insults_by_category_excludes_non_active(self):
        """insultsByCategory never returns non-Active insults."""
        # cat_a has Removed, Pending, Rejected, Flagged — all non-Active.
        response = self.query("""
            query {
                insultsByCategory(category: "ECA") {
                    totalCount
                    items { referenceId status }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByCategory"]
        self.assertEqual(data["totalCount"], 0)
        self.assertEqual(len(data["items"]), 0)

    def test_insults_by_category_returns_only_active_items(self):
        """insultsByCategory items all have status 'A'."""
        response = self.query("""
            query {
                insultsByCategory(category: "ECB") {
                    totalCount
                    items { status }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByCategory"]
        self.assertGreaterEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertEqual(item["status"], "A")

    # -------------------------------------------------------------------------
    # insultsByClassification — pagination
    # -------------------------------------------------------------------------

    def test_insults_by_classification_limit_zero_returns_empty_items(self):
        """insultsByClassification(limit: 0) returns totalCount but no items."""
        response = self.query("""
            query {
                insultsByClassification(nsfw: false, offset: 0, limit: 0) {
                    totalCount
                    items { referenceId }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByClassification"]
        self.assertGreaterEqual(data["totalCount"], 0)
        self.assertEqual(len(data["items"]), 0)

    def test_insults_by_classification_offset_beyond_total(self):
        """insultsByClassification with offset > total returns empty items list."""
        resp_count = self.query("""
            query {
                insultsByClassification(nsfw: true, offset: 0, limit: 1) {
                    totalCount
                }
            }
            """)
        self.assertResponseNoErrors(resp_count)
        total = json.loads(resp_count.content)["data"]["insultsByClassification"][
            "totalCount"
        ]

        response = self.query(f"""
            query {{
                insultsByClassification(nsfw: true, offset: {total + 100}, limit: 10) {{
                    totalCount
                    items {{ referenceId }}
                }}
            }}
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByClassification"]
        self.assertEqual(data["totalCount"], total)
        self.assertEqual(len(data["items"]), 0)

    def test_insults_by_classification_includes_all_statuses(self):
        """insultsByClassification is not restricted to Active status."""
        # All insults in cat_a have nsfw=False regardless of status.
        resp_sfw = self.query("""
            query {
                insultsByClassification(nsfw: false, offset: 0, limit: 100) {
                    totalCount
                }
            }
            """)
        self.assertResponseNoErrors(resp_sfw)
        total = json.loads(resp_sfw.content)["data"]["insultsByClassification"][
            "totalCount"
        ]
        # cat_a has 4 SFW insults in non-Active states; they must be counted.
        self.assertGreaterEqual(total, 4)
