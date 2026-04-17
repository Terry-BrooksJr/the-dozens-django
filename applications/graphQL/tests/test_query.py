# -*- coding: utf-8 -*-
import json

from django.contrib.auth import get_user_model
from graphene_django.utils.testing import GraphQLTestCase

from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()

GRAPHQL_ENDPOINT = "/graphql/"


class GraphQLInsultQueryTests(GraphQLTestCase):
    """Tests for the GraphQL insult query resolvers."""

    GRAPHQL_URL = GRAPHQL_ENDPOINT

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="gql_owner", email="gql@example.com", password="pass1234"
        )
        cls.theme = Theme.objects.create(theme_key="GT", theme_name="GraphQL Theme")
        cls.cat_poor = InsultCategory.objects.create(
            category_key="GP", name="GQL Poor", theme=cls.theme
        )
        cls.cat_fat = InsultCategory.objects.create(
            category_key="GF", name="GQL Fat", theme=cls.theme
        )

        # Active SFW insult in cat_poor
        cls.active_sfw = Insult.objects.create(
            content="Yo momma is so poor, she can't afford a free sample.",
            category=cls.cat_poor,
            nsfw=False,
            theme=cls.theme,
            status=Insult.STATUS.ACTIVE,
            added_by=cls.user,
        )
        # Active NSFW insult in cat_fat
        cls.active_nsfw = Insult.objects.create(
            content="Yo momma is so fat she sat on a rainbow and skittles fell out.",
            category=cls.cat_fat,
            nsfw=True,
            theme=cls.theme,
            status=Insult.STATUS.ACTIVE,
            added_by=cls.user,
        )
        # Pending insult — should not appear in active queries
        cls.pending = Insult.objects.create(
            content="This one is pending review.",
            category=cls.cat_poor,
            nsfw=False,
            theme=cls.theme,
            status=Insult.STATUS.PENDING,
            added_by=cls.user,
        )

    # -------------------------------------------------------------------------
    # randomInsult
    # -------------------------------------------------------------------------

    def test_random_insult_returns_active(self):
        """randomInsult returns a non-null active insult."""
        response = self.query("""
            query {
                randomInsult {
                    referenceId
                    content
                    isActive
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["randomInsult"]
        self.assertIsNotNone(data)
        self.assertTrue(data["isActive"])

    def test_random_insult_with_valid_category(self):
        """randomInsult(category:) returns an insult from the requested category."""
        response = self.query("""
            query {
                randomInsult(category: "GP") {
                    referenceId
                    content
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["randomInsult"]
        self.assertIsNotNone(data)
        self.assertEqual(data["referenceId"], self.active_sfw.reference_id)

    def test_random_insult_with_empty_category_returns_null(self):
        """randomInsult(category:) returns null when no active insults exist for that category."""
        response = self.query("""
            query {
                randomInsult(category: "NOTEXIST") {
                    referenceId
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["randomInsult"]
        self.assertIsNone(data)

    # -------------------------------------------------------------------------
    # insultById
    # -------------------------------------------------------------------------

    def test_insult_by_id_returns_correct_insult(self):
        """insultById returns the correct insult for a known ID."""
        response = self.query(f"""
            query {{
                insultById(referenceId: "{self.active_sfw.reference_id}") {{
                    referenceId
                    content
                }}
            }}
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultById"]
        self.assertIsNotNone(data)
        self.assertEqual(data["referenceId"], self.active_sfw.reference_id)

    def test_insult_by_id_not_found_returns_error(self):
        """insultById raises a GraphQL error for a non-existent ID."""
        response = self.query("""
            query {
                insultById(referenceId: "99999999") {
                    referenceId
                }
            }
            """)
        self.assertResponseHasErrors(response)

    # -------------------------------------------------------------------------
    # insultsByCategory
    # -------------------------------------------------------------------------

    def test_insults_by_category_returns_paginated_results(self):
        """insultsByCategory returns total count and items for a valid category."""
        response = self.query("""
            query {
                insultsByCategory(category: "GP", offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                        content
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByCategory"]
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(len(data["items"]), 1)

    def test_insults_by_category_pagination(self):
        """insultsByCategory respects limit and offset."""
        response = self.query("""
            query {
                insultsByCategory(category: "GP", offset: 0, limit: 0) {
                    totalCount
                    items {
                        referenceId
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByCategory"]
        self.assertEqual(data["totalCount"], 1)
        self.assertEqual(len(data["items"]), 0)

    def test_insults_by_category_no_results(self):
        """insultsByCategory returns zero items for a category with no active insults."""
        response = self.query("""
            query {
                insultsByCategory(category: "NOTEXIST", offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByCategory"]
        self.assertEqual(data["totalCount"], 0)
        self.assertEqual(len(data["items"]), 0)

    # -------------------------------------------------------------------------
    # insultsByStatus
    # -------------------------------------------------------------------------

    def test_insults_by_status_active(self):
        """insultsByStatus returns only active insults when status=A."""
        response = self.query("""
            query {
                insultsByStatus(status: "A", offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                        status
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertEqual(data["totalCount"], 2)
        for item in data["items"]:
            self.assertEqual(item["status"], "A")

    def test_insults_by_status_pending(self):
        """insultsByStatus returns pending insults when status=P."""
        response = self.query("""
            query {
                insultsByStatus(status: "P", offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByStatus"]
        self.assertGreaterEqual(data["totalCount"], 1)

    # -------------------------------------------------------------------------
    # insultsByClassification
    # -------------------------------------------------------------------------

    def test_insults_by_classification_sfw(self):
        """insultsByClassification(nsfw: false) returns only SFW insults."""
        response = self.query("""
            query {
                insultsByClassification(nsfw: false, offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                        nsfw
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByClassification"]
        self.assertGreaterEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertFalse(item["nsfw"])

    def test_insults_by_classification_nsfw(self):
        """insultsByClassification(nsfw: true) returns only NSFW insults."""
        response = self.query("""
            query {
                insultsByClassification(nsfw: true, offset: 0, limit: 10) {
                    totalCount
                    items {
                        referenceId
                        nsfw
                    }
                }
            }
            """)
        self.assertResponseNoErrors(response)
        data = json.loads(response.content)["data"]["insultsByClassification"]
        self.assertEqual(data["totalCount"], 1)
        for item in data["items"]:
            self.assertTrue(item["nsfw"])
