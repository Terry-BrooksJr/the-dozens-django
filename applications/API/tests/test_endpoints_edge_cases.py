"""
Edge-case tests for applications.API.endpoints that aren't covered by
test_endpoints.py's happy-path CRUD/list suite.

Covers:
- InsultByCategoryEndpoint.list(): the early `?category=`/`?category_name=`
  query-param redirect branch (bare and with extra query params preserved).
- RandomInsultEndpoint: the empty-result 404 branch (deterministic, via a
  filter combination that is guaranteed to match nothing).
- ListThemesAndCategoryEndpoint.get(): grouping of categories under their
  themes, exclusion of the "INTL" theme, and exclusion of
  IGNORED_INSULT_CATEGORIES from the results — this view had zero direct
  test coverage previously.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from applications.API.endpoints import (
    InsultByCategoryEndpoint,
    ListThemesAndCategoryEndpoint,
    RandomInsultEndpoint,
)
from applications.API.models import Insult, InsultCategory, Theme

User = get_user_model()


def open_view(view_cls):
    """Bypass project-specific permission wiring so we can test list() logic
    in isolation, matching the pattern used in test_endpoints.py."""

    class OpenView(view_cls):  # type: ignore
        permission_classes = [AllowAny]

        def check_permissions(self, request):
            return None

    return OpenView


class InsultByCategoryRedirectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = open_view(InsultByCategoryEndpoint).as_view()

    def test_category_query_param_redirects_to_path_form(self):
        request = self.factory.get("/api/insults/?category=poor")

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.url, "/api/insults/poor")

    def test_category_name_query_param_redirects_to_path_form(self):
        request = self.factory.get("/api/insults/?category_name=Fat")

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response.url, "/api/insults/Fat")

    def test_redirect_preserves_other_query_params(self):
        request = self.factory.get("/api/insults/?category=poor&nsfw=true")

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("/api/insults/poor?", response.url)
        self.assertIn("nsfw=true", response.url)


class RandomInsultEmptyResultTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = RandomInsultEndpoint.as_view()
        self.user = User.objects.create_user(
            username="random_edge_user", email="random_edge@example.com", password="pw"
        )
        self.theme = Theme.objects.create(theme_key="RND", theme_name="Random Theme")
        self.cat = InsultCategory.objects.create(
            category_key="RD", name="Random Cat", theme=self.theme
        )
        # Only an SFW active insult exists — filtering for NSFW must match nothing.
        Insult.objects.create(
            content="Yo momma is so random this is the only insult in the DB.",
            category=self.cat,
            nsfw=False,
            added_by=self.user,
            status=Insult.STATUS.ACTIVE,
            added_on=timezone.now(),
        )

    def test_no_matching_results_returns_404_with_detail(self):
        request = self.factory.get("/api/insults/random/?nsfw=true")

        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("No insults found", response.data["detail"])


class ListThemesAndCategoryEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = ListThemesAndCategoryEndpoint.as_view()

    def _get(self):
        request = self.factory.get("/api/categories/")
        return self.view(request)

    def test_categories_grouped_under_their_theme(self):
        theme = Theme.objects.create(theme_key="GRP", theme_name="Grouping Theme")
        InsultCategory.objects.create(
            category_key="G1", name="Group Cat One", description="d1", theme=theme
        )
        InsultCategory.objects.create(
            category_key="G2", name="Group Cat Two", description="d2", theme=theme
        )

        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertIn("Grouping Theme", results)
        categories = results["Grouping Theme"]["categories"]
        self.assertIn("G1", categories)
        self.assertIn("G2", categories)
        self.assertEqual(categories["G1"]["name"], "Group Cat One")

    def test_intl_theme_categories_are_excluded_from_results(self):
        intl_theme = Theme.objects.create(theme_key="INTL", theme_name="International")
        InsultCategory.objects.create(
            category_key="IN", name="Intl Cat", description="d", theme=intl_theme
        )

        response = self._get()

        self.assertNotIn("International", response.data["results"])

    def test_ignored_category_keys_are_excluded(self):
        """Categories in settings.IGNORED_INSULT_CATEGORIES (TEST, X) never appear."""
        theme = Theme.objects.create(theme_key="IGN", theme_name="Ignored Theme")
        InsultCategory.objects.create(
            category_key="TEST", name="Test Category", description="d", theme=theme
        )

        response = self._get()

        if "Ignored Theme" in response.data["results"]:
            self.assertNotIn(
                "TEST", response.data["results"]["Ignored Theme"]["categories"]
            )

    def test_help_text_present_in_response(self):
        response = self._get()

        self.assertIn("help_text", response.data)
