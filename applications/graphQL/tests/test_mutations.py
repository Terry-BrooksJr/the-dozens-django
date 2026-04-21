# -*- coding: utf-8 -*-
"""
Tests for applications.graphQL.mutations

Covers:
- Mutate is a graphene.Mutation subclass.
- Mutate.mutate() is a no-op that returns None.
"""

from django.test import SimpleTestCase
from graphene import Mutation

from applications.graphQL.mutations import Mutate


class TestMutateStub(SimpleTestCase):
    """The Mutate stub class satisfies its contract as a graphene Mutation."""

    def test_mutate_is_mutation_subclass(self):
        """Mutate inherits from graphene.Mutation."""
        self.assertTrue(issubclass(Mutate, Mutation))

    def test_mutate_method_returns_none(self):
        """Mutate.mutate() returns None (stub implementation)."""
        instance = Mutate()
        result = instance.mutate(info=None)
        self.assertIsNone(result)

    def test_mutate_method_accepts_kwargs(self):
        """Mutate.mutate() accepts arbitrary keyword arguments without error."""
        instance = Mutate()
        result = instance.mutate(info=None, foo="bar", baz=42)
        self.assertIsNone(result)
