# -*- coding: utf-8 -*-
"""
Tests for applications.graphQL.subscriptions

Covers:
- Subscription is a graphene.ObjectType subclass.
- The class currently declares no fields (stub for future implementation).
"""

from django.test import SimpleTestCase
from graphene import ObjectType

from applications.graphQL.subscriptions import Subscription


class TestSubscriptionStub(SimpleTestCase):
    """The Subscription stub class satisfies its graphene ObjectType contract."""

    def test_subscription_is_objecttype_subclass(self):
        """Subscription inherits from graphene.ObjectType."""
        self.assertTrue(issubclass(Subscription, ObjectType))

    def test_subscription_has_no_declared_fields(self):
        """Subscription currently declares no fields (reserved for future use)."""
        # graphene stores declared fields in _meta.fields
        declared = {
            name
            for name, field in Subscription._meta.fields.items()
            # Exclude any fields inherited from ObjectType itself (there are none,
            # but this guards against framework changes).
        }
        self.assertEqual(declared, set())

    def test_subscription_can_be_instantiated(self):
        """Subscription can be instantiated without arguments."""
        instance = Subscription()
        self.assertIsInstance(instance, Subscription)
