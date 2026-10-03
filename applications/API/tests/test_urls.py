"""
Routing tests for the REST API URL layout.

Covers:
- Canonical /api/v1/ routes reverse to the expected paths and resolve to the
  expected views.
- Fixed insult sub-paths (random, reference-ids) win over the
  ``{reference_id}`` catch-all.
- Deprecated pre-v1 aliases still resolve, respond, and carry the
  ``Deprecation`` and ``Link: rel="successor-version"`` headers.
- ``/graphql`` matching is anchored.
- Deprecated aliases are left out of the OpenAPI schema.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from applications.API.endpoints import (
    InsultByCategoryEndpoint,
    InsultCollectionEndpoint,
    InsultDetailsEndpoint,
    ListReferenceIdsEndpoint,
    ListThemesAndCategoryEndpoint,
    RandomInsultEndpoint,
)
from applications.API.models import Insult, InsultCategory, Theme
from applications.frontend.views import ReportJokeView

User = get_user_model()


class CanonicalRouteTests(TestCase):
    """Canonical /api/v1/ names map to RESTful paths and the right views."""

    ROUTES = [
        ("category-list", {}, "/api/v1/categories/", ListThemesAndCategoryEndpoint),
        (
            "category-insult-list",
            {"category_name": "poor"},
            "/api/v1/categories/poor/insults/",
            InsultByCategoryEndpoint,
        ),
        ("insult-list", {}, "/api/v1/insults/", InsultCollectionEndpoint),
        ("insult-random", {}, "/api/v1/insults/random/", RandomInsultEndpoint),
        (
            "insult-reference-id-list",
            {},
            "/api/v1/insults/reference-ids/",
            ListReferenceIdsEndpoint,
        ),
        (
            "insult-detail",
            {"reference_id": "GIGGLE_ABC123"},
            "/api/v1/insults/GIGGLE_ABC123/",
            InsultDetailsEndpoint,
        ),
        ("report-list", {}, "/api/v1/reports/", ReportJokeView),
    ]

    def test_reverse_and_resolve(self):
        for name, kwargs, expected_path, view_cls in self.ROUTES:
            with self.subTest(name=name):
                self.assertEqual(reverse(name, kwargs=kwargs), expected_path)
                self.assertIs(resolve(expected_path).func.cls, view_cls)

    def test_fixed_sub_paths_are_not_captured_as_reference_ids(self):
        self.assertEqual(resolve("/api/v1/insults/random/").url_name, "insult-random")
        self.assertEqual(
            resolve("/api/v1/insults/reference-ids/").url_name,
            "insult-reference-id-list",
        )

    def test_no_verbs_in_canonical_paths(self):
        with self.assertRaises(Resolver404):
            resolve("/api/v1/insults/new")


class InsultCollectionTests(TestCase):
    """GET lists and POST creates on the same /api/v1/insults/ collection."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="collection_user", email="collection@example.com", password="pw"
        )
        self.token = Token.objects.create(user=self.user)
        theme = Theme.objects.create(theme_key="COL", theme_name="Collection Theme")
        self.category = InsultCategory.objects.create(
            category_key="CL", name="Collection", theme=theme
        )
        Insult.objects.create(
            content="Yo momma is so collected she lists herself.",
            category=self.category,
            nsfw=False,
            added_by=self.user,
            status=Insult.STATUS.ACTIVE,
            added_on=timezone.now(),
        )

    def test_get_lists_insults(self):
        response = self.client.get("/api/v1/insults/?category=CL")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertNotIn("Deprecation", response.headers)

    def test_post_requires_authentication(self):
        response = self.client.post(
            "/api/v1/insults/",
            {"content": "Yo momma so anonymous...", "category": "CL", "nsfw": False},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_post_creates_pending_insult_owned_by_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            "/api/v1/insults/",
            {
                "content": "Yo momma so restful she only responds to POST.",
                "category": "CL",
                "nsfw": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = Insult.objects.get(
            content="Yo momma so restful she only responds to POST."
        )
        self.assertEqual(created.added_by, self.user)
        self.assertEqual(created.status, Insult.STATUS.PENDING)


class DeprecatedAliasTests(TestCase):
    """Pre-v1 routes keep working but advertise their successors."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        user = User.objects.create_user(
            username="legacy_user", email="legacy@example.com", password="pw"
        )
        theme = Theme.objects.create(theme_key="LEG", theme_name="Legacy Theme")
        category = InsultCategory.objects.create(
            category_key="LG", name="Legacy", theme=theme
        )
        self.insult = Insult.objects.create(
            content="Yo momma is so legacy she still uses the old URLs.",
            category=category,
            nsfw=False,
            added_by=user,
            status=Insult.STATUS.ACTIVE,
            added_on=timezone.now(),
        )

    def assertDeprecated(self, response, successor):
        self.assertEqual(response.headers.get("Deprecation"), "true")
        self.assertEqual(
            response.headers.get("Link"), f'<{successor}>; rel="successor-version"'
        )

    def test_legacy_get_routes_still_respond_with_deprecation_headers(self):
        ref = self.insult.reference_id
        cases = [
            ("/api/categories/", "/api/v1/categories/"),
            ("/api/insults/random/", "/api/v1/insults/random/"),
            ("/api/insults/category/LG/", "/api/v1/categories/LG/insults/"),
            (f"/api/insults/{ref}/", f"/api/v1/insults/{ref}/"),
            ("/insults/reference-ids/", "/api/v1/insults/reference-ids/"),
        ]
        for legacy, successor in cases:
            with self.subTest(path=legacy):
                response = self.client.get(legacy)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertDeprecated(response, successor)

    def test_legacy_create_route_is_deprecated(self):
        response = self.client.post("/api/insults/new", {}, format="json")

        self.assertDeprecated(response, "/api/v1/insults/")

    def test_legacy_report_route_is_deprecated(self):
        response = self.client.post("/report/", {}, format="json")

        self.assertDeprecated(response, "/api/v1/reports/")

    def test_legacy_url_names_still_reverse(self):
        self.assertEqual(reverse("random_insult"), "/api/insults/random/")
        self.assertEqual(reverse("create_insult"), "/api/insults/new")
        self.assertEqual(reverse("report-joke"), "/report/")


class GraphQLRouteTests(TestCase):
    def test_graphql_prefix_is_anchored(self):
        resolve("/graphql")
        resolve("/graphql/")
        resolve("/graphql/playground/")
        with self.assertRaises(Resolver404):
            resolve("/graphqlplayground/")


class SchemaTests(TestCase):
    def test_schema_documents_v1_and_omits_deprecated_aliases(self):
        response = self.client.get("/api/schema/?format=json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        paths = response.json()["paths"]
        self.assertIn("/api/v1/insults/", paths)
        self.assertEqual(set(paths["/api/v1/insults/"]), {"get", "post"})
        self.assertIn("/api/v1/reports/", paths)
        for legacy in (
            "/api/insults/new",
            "/api/insults/random/",
            "/api/categories/",
            "/report/",
        ):
            self.assertNotIn(legacy, paths)
