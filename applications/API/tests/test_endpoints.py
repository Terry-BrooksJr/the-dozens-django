from applications.API.models import Insult, InsultCategory
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from nose.tools import assert_equal, assert_in
from rest_framework import status
from rest_framework.test import APIClient


class BaseTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass123"
        )

        # Create test category
        self.category = InsultCategory.objects.create(
            category_key="TST", name="Test Category"
        )

        # Create test insults
        self.active_insult = Insult.objects.create(
            content="Test active insult",
            category=self.category,
            added_by=self.user,
            status="A",
        )

        self.pending_insult = Insult.objects.create(
            content="Test pending insult",
            category=self.category,
            added_by=self.user,
            status="P",
        )

        # Setup API client
        self.client = APIClient()


class TestInsultSingleItem(BaseTestCase):
    def test_get_active_insult_unauthenticated(self):
        """Test that unauthenticated users can retrieve active insults"""
        url = reverse("insult-detail", kwargs={"id": self.active_insult.id})
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(response.data["content"], self.active_insult.content)

    def test_get_pending_insult_unauthenticated(self):
        """Test that unauthenticated users cannot retrieve pending insults"""
        url = reverse("insult-detail", kwargs={"id": self.pending_insult.id})
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_own_pending_insult(self):
        """Test that users can retrieve their own pending insults"""
        self.client.force_authenticate(user=self.user)
        url = reverse("insult-detail", kwargs={"id": self.pending_insult.id})
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(response.data["content"], self.pending_insult.content)

    def test_update_own_insult(self):
        """Test that users can update their own insults"""
        self.client.force_authenticate(user=self.user)
        url = reverse("insult-detail", kwargs={"id": self.active_insult.id})
        updated_content = "Updated content"
        response = self.client.patch(url, {"content": updated_content})

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(response.data["content"], updated_content)

    def test_update_others_insult(self):
        """Test that users cannot update others' insults"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("insult-detail", kwargs={"id": self.active_insult.id})
        response = self.client.patch(url, {"content": "Updated content"})

        assert_equal(response.status_code, status.HTTP_403_FORBIDDEN)


class TestMyInsultsViewSet(BaseTestCase):
    def test_list_own_insults(self):
        """Test that users can list all their insults regardless of status"""
        self.client.force_authenticate(user=self.user)
        url = reverse("my-insults-list")
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(len(response.data), 2)

    def test_list_insults_unauthenticated(self):
        """Test that unauthenticated users get empty list"""
        url = reverse("my-insults-list")
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(len(response.data), 0)


class TestAvailableInsultsCategoriesListView(BaseTestCase):
    def test_list_categories(self):
        """Test that anyone can list categories"""
        url = reverse("available-categories")
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_in("available_categories", response.data)
        assert_equal(
            response.data["available_categories"][self.category.category_key],
            self.category.name,
        )


class TestInsultsCategoriesListView(BaseTestCase):
    def test_list_insults_by_category(self):
        """Test listing active insults in a category"""
        url = reverse(
            "category-insults", kwargs={"category": self.category.category_key}
        )
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(len(response.data), 1)
        assert_equal(response.data[0]["id"], self.active_insult.id)

    def test_invalid_category(self):
        """Test that invalid category returns empty list"""
        url = reverse("category-insults", kwargs={"category": "INVALID"})
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(len(response.data), 0)

    def test_pagination(self):
        """Test that pagination works correctly"""
        # Create more than max_paginate_by insults
        for i in range(101):  # max_paginate_by is 100
            Insult.objects.create(
                content=f"Test insult {i}",
                category=self.category,
                added_by=self.user,
                status="A",
            )

        url = reverse(
            "category-insults", kwargs={"category": self.category.category_key}
        )
        response = self.client.get(url)

        assert_equal(response.status_code, status.HTTP_200_OK)
        assert_equal(len(response.data), 100)  # Should be limited by max_paginate_by
