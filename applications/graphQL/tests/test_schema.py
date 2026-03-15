# -*- coding: utf-8 -*-
"""
Tests for applications.graphQL.schema

Covers:
- schema is a graphene.Schema instance.
- The root query type is wired up correctly.
- No mutation or subscription type is registered.
- All five public query fields are present in the schema.
- A basic introspection query executes without errors.
"""

from django.test import SimpleTestCase
from graphene import Schema

from applications.graphQL.query import Query
from applications.graphQL.schema import schema

# All query field names as they appear in the GraphQL schema (camelCase).
EXPECTED_QUERY_FIELDS = {
    "randomInsult",
    "insultById",
    "insultsByCategory",
    "insultsByStatus",
    "insultsByClassification",
}


class TestSchemaIsGrapheneSchema(SimpleTestCase):
    """schema module exports a properly configured graphene.Schema instance."""

    def test_schema_is_graphene_schema_instance(self):
        """The exported `schema` object is a graphene.Schema instance."""
        self.assertIsInstance(schema, Schema)

    def test_schema_query_type_is_query_class(self):
        """The schema was built with the Query class as its root query type."""
        self.assertIs(schema.query, Query)

    def test_schema_has_no_mutation_type(self):
        """No Mutation type is registered on the schema."""
        self.assertIsNone(schema.mutation)

    def test_schema_has_no_subscription_type(self):
        """No Subscription type is registered on the schema."""
        self.assertIsNone(schema.subscription)


class TestSchemaIntrospection(SimpleTestCase):
    """Schema introspection confirms the correct query fields are present."""

    @classmethod
    def _execute(cls, query_string: str):
        """Execute a query synchronously and return the ExecutionResult."""
        return schema.execute(query_string)

    def test_introspection_no_errors(self):
        """A basic __typename introspection executes without errors."""
        result = self._execute("{ __typename }")
        self.assertIsNone(result.errors)

    def test_query_type_name_is_query(self):
        """The schema's root query type is named 'Query' in the introspection result."""
        result = self._execute("{ __schema { queryType { name } } }")
        self.assertIsNone(result.errors)
        self.assertEqual(result.data["__schema"]["queryType"]["name"], "Query")

    def test_no_mutation_type_in_introspection(self):
        """introspection confirms mutationType is null."""
        result = self._execute("{ __schema { mutationType { name } } }")
        self.assertIsNone(result.errors)
        self.assertIsNone(result.data["__schema"]["mutationType"])

    def test_all_expected_query_fields_present(self):
        """All five query fields are present in the schema."""
        result = self._execute(
            """
            {
                __schema {
                    queryType {
                        fields {
                            name
                        }
                    }
                }
            }
            """
        )
        self.assertIsNone(result.errors)
        field_names = {
            f["name"]
            for f in result.data["__schema"]["queryType"]["fields"]
        }
        for expected in EXPECTED_QUERY_FIELDS:
            with self.subTest(field=expected):
                self.assertIn(expected, field_names)

    def test_insult_type_is_active_field_in_introspection(self):
        """The Insult type exposes the computed isActive field."""
        result = self._execute(
            """
            {
                __type(name: "Insult") {
                    fields {
                        name
                    }
                }
            }
            """
        )
        self.assertIsNone(result.errors)
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        self.assertIn("isActive", field_names)

    def test_insult_connection_type_in_introspection(self):
        """The InsultConnection type exposes totalCount and items fields."""
        result = self._execute(
            """
            {
                __type(name: "InsultConnection") {
                    fields {
                        name
                    }
                }
            }
            """
        )
        self.assertIsNone(result.errors)
        field_names = {f["name"] for f in result.data["__type"]["fields"]}
        self.assertIn("totalCount", field_names)
        self.assertIn("items", field_names)
