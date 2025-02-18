import pytest
from applications.API.models import Insult, InsultCategory
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


@pytest.mark.django_db
class TestMyInsultsViewSet(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass123"
        )
        self.category = InsultCategory.objects.create(
            category_key="funny", name="Funny Insults"
        )
        self.insult = Insult.objects.create(
            content="Your code has more bugs than features",
            category=self.category,
            added_by=self.user,
            status="A",
        )
        self.other_insult = Insult.objects.create(
            content="Your documentation is as clear as mud",
            category=self.category,
            added_by=self.other_user,
            status="A",
        )
        self.url = reverse("my-insults-detail", kwargs={"pk": self.insult.pk})

    def test_get_own_insults_authenticated(self):
        """Test that authenticated users can retrieve their own insults"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], self.insult.content)

    def test_get_insults_unauthenticated(self):
        """Test that unauthenticated users cannot access insults"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_own_insult(self):
        """Test that users can update their own insults"""
        self.client.force_authenticate(user=self.user)
        updated_data = {
            "content": "Updated insult content",
            "category": self.category.id,
        }
        response = self.client.patch(self.url, updated_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], updated_data["content"])

    def test_update_other_user_insult(self):
        """Test that users cannot update other users' insults"""
        self.client.force_authenticate(user=self.other_user)
        updated_data = {"content": "Trying to update someone else's insult"}
        response = self.client.patch(self.url, updated_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_own_insult(self):
        """Test that users can delete their own insults"""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Insult.objects.filter(pk=self.insult.pk).exists())


@pytest.mark.django_db
class TestInsultsCategoriesViewSet(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.category1 = InsultCategory.objects.create(
            category_key="funny", category_name="Funny Insults"
        )
        self.category2 = InsultCategory.objects.create(
            key="savage", name="Savage Comebacks"
        )
        self.url = reverse("insult-categories-list")

    def test_list_categories(self):
        """Test retrieving all categories"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["available_categories"]), 2)
        self.assertEqual(
            response.data["available_categories"],
            {"funny": "Funny Insults", "savage": "Savage Comebacks"},
        )


@pytest.mark.django_db
class TestInsultsCategoriesListView(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = InsultCategory.objects.create(key="funny", name="Funny Insults")
        self.insult = Insult.objects.create(
            content="Test insult", category=self.category, status="A"
        )
        self.url = reverse("insult-categories", kwargs={"category": "funny"})

    def test_list_insults_by_valid_category(self):
        """Test retrieving insults for a valid category"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_insults_invalid_category(self):
        """Test retrieving insults for an invalid category"""
        url = reverse("insult-categories", kwargs={"category": "invalid"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_pagination(self):
        """Test that pagination works correctly"""
        # Create 10 more insults
        for i in range(10):
            Insult.objects.create(
                content=f"Test insult {i}", category=self.category, status="A"
            )

        response = self.client.get(f"{self.url}?page_size=5")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)


@pytest.mark.django_db
class TestInsultSingleItem(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = InsultCategory.objects.create(key="funny", name="Funny Insults")
        self.insult = Insult.objects.create(
            content="Test insult", category=self.category, status="A"
        )
        self.url = reverse("Single_View", kwargs={"id": self.insult.pk})

    def test_retrieve_single_insult(self):
        """Test retrieving a single insult"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], self.insult.content)

    def test_retrieve_nonexistent_insult(self):
        """Test retrieving a nonexistent insult"""
        url = reverse("Single_View", kwargs={"id": 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
