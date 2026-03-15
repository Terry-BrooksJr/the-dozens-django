# -*- coding: utf-8 -*-
"""
Tests for applications.graphQL.type

Covers:
- InsultType.resolve_is_active for every moderation status code.
- InsultConnection field declarations and instantiation.
- Integration: the isActive field resolves correctly through the full
  GraphQL execution path.
"""

import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from graphene import List, ObjectType
from graphene_django.utils.testing import GraphQLTestCase

from applications.API.models import Insult, InsultCategory, Theme
from applications.graphQL.type import InsultConnection, InsultType

User = get_user_model()

GRAPHQL_ENDPOINT = "/graphql/"


# ---------------------------------------------------------------------------
# Unit tests — resolve_is_active
# ---------------------------------------------------------------------------


class TestInsultTypeResolveIsActive(SimpleTestCase):
    """resolve_is_active(self, info) returns True only for status='A'."""

    # Minimal stand-in: the resolver only reads self.status.
    class _FakeInsult:
        def __init__(self, status: str):
            self.status = status

    def _resolve(self, status: str) -> bool:
        fake = self._FakeInsult(status)
        return InsultType.resolve_is_active(fake, info=None)

    def test_active_returns_true(self):
        """status='A' (Active) → True."""
        self.assertTrue(self._resolve("A"))

    def test_removed_returns_false(self):
        """status='X' (Removed) → False."""
        self.assertFalse(self._resolve("X"))

    def test_pending_returns_false(self):
        """status='P' (Pending) → False."""
        self.assertFalse(self._resolve("P"))

    def test_rejected_returns_false(self):
        """status='R' (Rejected) → False."""
        self.assertFalse(self._resolve("R"))

    def test_flagged_returns_false(self):
        """status='F' (Flagged for Review) → False."""
        self.assertFalse(self._resolve("F"))

    def test_empty_string_returns_false(self):
        """Any unrecognised / empty status string → False."""
        self.assertFalse(self._resolve(""))

    def test_lowercase_a_returns_false(self):
        """Status comparison is case-sensitive; 'a' ≠ 'A'."""
        self.assertFalse(self._resolve("a"))


# ---------------------------------------------------------------------------
# Unit tests — InsultConnection structure
# ---------------------------------------------------------------------------


class TestInsultConnectionStructure(SimpleTestCase):
    """InsultConnection declares the expected fields and can be instantiated."""

    def test_has_total_count_field(self):
        """InsultConnection has a declared total_count field."""
        self.assertIn("total_count", InsultConnection._meta.fields)

    def test_has_items_field(self):
        """InsultConnection has a declared items field."""
        self.assertIn("items", InsultConnection._meta.fields)

    def test_is_objecttype_subclass(self):
        """InsultConnection is a graphene ObjectType subclass."""
        self.assertTrue(issubclass(InsultConnection, ObjectType))

    def test_instantiate_with_keyword_args(self):
        """InsultConnection can be instantiated with total_count and items."""
        conn = InsultConnection(total_count=5, items=[])
        self.assertEqual(conn.total_count, 5)
        self.assertEqual(conn.items, [])

    def test_instantiate_defaults_to_none(self):
        """InsultConnection fields default to None when not supplied."""
        conn = InsultConnection()
        self.assertIsNone(conn.total_count)
        self.assertIsNone(conn.items)


# ---------------------------------------------------------------------------
# Integration test — isActive resolves through the full GraphQL stack
# ---------------------------------------------------------------------------


class TestInsultTypeIsActiveIntegration(GraphQLTestCase):
    """The isActive field resolves correctly end-to-end for each status code."""

    GRAPHQL_URL = GRAPHQL_ENDPOINT

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="type_test_user",
            email="typetestuser@example.com",
            password="pass1234",
        )
        cls.theme = Theme.objects.create(
            theme_key="TT", theme_name="Type Test Theme"
        )
        cls.cat = InsultCategory.objects.create(
            category_key="TTC", name="Type Test Cat", theme=cls.theme
        )

        # One insult per moderation status
        for status_code in ("A", "X", "P", "R", "F"):
            Insult.objects.create(
                content=f"Type test insult [{status_code}]",
                category=cls.cat,
                nsfw=False,
                theme=cls.theme,
                status=status_code,
                added_by=cls.user,
            )

        cls.active = Insult.objects.get(
            content="Type test insult [A]", theme=cls.theme
        )

    def _query_is_active(self, insult_id: int) -> bool | None:
        """Execute insultById and return the isActive value."""
        response = self.query(
            f"""
            query {{
                insultById(referenceId: "{insult_id}") {{
                    isActive
                }}
            }}
            """
        )
        self.assertResponseNoErrors(response)
        return json.loads(response.content)["data"]["insultById"]["isActive"]

    def test_active_insult_is_active_true(self):
        """isActive is True for a status='A' insult."""
        self.assertTrue(self._query_is_active(self.active.insult_id))

    def test_non_active_insults_are_not_active(self):
        """isActive is False for every non-Active status code."""
        for status_code in ("X", "P", "R", "F"):
            insult = Insult.objects.get(
                content=f"Type test insult [{status_code}]", theme=self.theme
            )
            with self.subTest(status=status_code):
                self.assertFalse(self._query_is_active(insult.insult_id))
