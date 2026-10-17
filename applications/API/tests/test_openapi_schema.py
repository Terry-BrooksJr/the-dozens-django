"""
Tests for the generated OpenAPI schema.

Covers:
- the schema generates and validates with no drf-spectacular warnings
- every operation has a summary, a description and a tag declared in
  SPECTACULAR_SETTINGS["TAGS"]
- documented responses match what selected endpoints actually return
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class OpenApiSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "schema.yaml"
            # --fail-on-warn turns any drf-spectacular warning into an error.
            call_command(
                "spectacular", "--validate", "--fail-on-warn", "--file", str(out)
            )
            cls.schema = yaml.safe_load(out.read_text())
        cls.operations = {
            (method.upper(), path): op
            for path, ops in cls.schema["paths"].items()
            for method, op in ops.items()
        }

    def test_every_operation_is_documented(self):
        declared = {t["name"] for t in settings.SPECTACULAR_SETTINGS["TAGS"]}
        for key, op in self.operations.items():
            with self.subTest(operation=key):
                self.assertTrue(op.get("summary"), "missing summary")
                self.assertTrue(op.get("description"), "missing description")
                self.assertTrue(op.get("tags"), "missing tag")
                self.assertLessEqual(set(op["tags"]), declared)

    def test_updates_document_200_with_the_insult(self):
        for method in ("PUT", "PATCH"):
            with self.subTest(method=method):
                op = self.operations[(method, "/api/v2.0.0/insults/{reference_id}/")]
                self.assertIn("200", op["responses"])
                self.assertNotIn("204", op["responses"])

    def test_djoser_post_actions_document_204(self):
        for path in (
            "/auth/users/set_password/",
            "/auth/users/reset_password/",
            "/auth/users/activation/",
        ):
            with self.subTest(path=path):
                responses = self.operations[("POST", path)]["responses"]
                self.assertIn("204", responses)
                self.assertNotIn("200", responses)

    def test_unknown_category_is_documented_as_400(self):
        for path in (
            "/api/v2.0.0/insults/",
            "/api/v2.0.0/insults/random/",
            "/api/v2.0.0/categories/{category_name}/insults/",
        ):
            with self.subTest(path=path):
                self.assertIn("400", self.operations[("GET", path)]["responses"])


class DocsRoutesNotCachedTests(SimpleTestCase):
    """The schema and docs pages are rebuilt on every request, never page-cached."""

    def test_schema_and_docs_pages_are_never_cached(self):
        from django.core.cache import cache
        from django.test import Client

        cache.clear()
        client = Client()
        for path in ("/api/schema/", "/api/swagger/", "/api/redoc/"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response["Cache-Control"])


class DocsRoutesNotThrottledTests(SimpleTestCase):
    """Each docs page load is two requests, so the docs routes are never throttled."""

    def test_schema_and_docs_routes_have_no_throttles(self):
        from django.urls import resolve

        for path in ("/api/schema/", "/api/swagger/", "/api/redoc/"):
            with self.subTest(path=path):
                func = resolve(path).func
                view = func.view_class(**func.view_initkwargs)
                self.assertEqual(view.get_throttles(), [])
