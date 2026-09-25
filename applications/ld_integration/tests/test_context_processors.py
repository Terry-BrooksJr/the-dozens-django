"""
Tests for applications.ld_integration.context_processors.launchdarkly_user.

Covers:
- The processor defers work until the template looks up ``ld_user``
- Rendering ``ld_user|json_script`` emits the user's context when logged in
- Rendering emits ``null`` for anonymous visitors
"""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import engines
from django.test import RequestFactory, TestCase

from applications.ld_integration.context_processors import launchdarkly_user

User = get_user_model()

TEMPLATE = '{{ ld_user|json_script:"ld-user" }}'


def _render(request) -> dict | None:
    html = engines["django"].from_string(TEMPLATE).render(request=request)
    payload = html.split(">", 1)[1].rsplit("<", 1)[0]
    return json.loads(payload)


class LaunchDarklyUserContextProcessorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_context_is_not_built_until_template_uses_it(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        with mock.patch(
            "applications.ld_integration.context_processors.browser_context_from_request"
        ) as build:
            launchdarkly_user(request)

        build.assert_not_called()

    def test_renders_logged_in_user_context(self):
        user = User.objects.create_user(
            username="rendered", email="rendered@example.com", password="pw"
        )
        request = self.factory.get("/")
        request.user = user

        self.assertEqual(
            _render(request),
            {
                "kind": "user",
                "key": str(user.pk),
                "name": "rendered",
                "is_staff": False,
            },
        )

    def test_renders_null_for_anonymous_visitor(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        self.assertIsNone(_render(request))
