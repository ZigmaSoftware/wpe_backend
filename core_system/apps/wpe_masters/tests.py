from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ProductTypeCategory, ProductTypeSubtype


UserModel = get_user_model()


class ProductTypesApiTests(APITestCase):
    def setUp(self):
        self.superuser = UserModel.objects.create_superuser(
            username="product-admin",
            email="product-admin@example.com",
            password="password123",
        )
        self.regular_user = UserModel.objects.create_user(
            username="product-user",
            email="product-user@example.com",
            password="password123",
        )
        self.category_list_url = "/api/wpe-masters/product-type-categories/"
        self.subtype_list_url = "/api/wpe-masters/product-type-subtypes/"
        self.category_tree_url = "/api/wpe-masters/product-type-categories/tree/"
        self.subtype_lookup_url = "/api/wpe-masters/product-type-subtypes/lookup/"

    def authenticate(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_superuser_can_list_seeded_product_type_categories(self):
        self.authenticate(self.superuser)

        response = self.client.get(self.category_list_url, {"page_size": 100})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 40)
        category_names = {row["name"] for row in response.data["results"]}
        self.assertIn("Blend", category_names)
        self.assertIn("LUMBER", category_names)
        self.assertIn("Lumber", category_names)

    def test_regular_user_without_permission_cannot_list_product_type_categories(self):
        self.authenticate(self.regular_user)

        response = self.client.get(self.category_list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_create_subtype_and_lookup_by_category(self):
        self.authenticate(self.superuser)
        category = ProductTypeCategory.objects.get(name="Blend")

        create_response = self.client.post(
            self.subtype_list_url,
            {
                "category": category.id,
                "name": "Blend QA Sample",
                "description": "Temporary verification subtype",
                "sort_order": 9990,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["category_name"], "Blend")
        self.assertTrue(
            ProductTypeSubtype.objects.filter(category=category, name="Blend QA Sample").exists()
        )

        lookup_response = self.client.get(self.subtype_lookup_url, {"category_id": category.id})

        self.assertEqual(lookup_response.status_code, status.HTTP_200_OK)
        lookup_names = {row["name"] for row in lookup_response.data}
        self.assertIn("Blend QA Sample", lookup_names)
        self.assertIn("WPE", lookup_names)

    def test_duplicate_subtype_in_same_category_is_rejected(self):
        self.authenticate(self.superuser)
        category = ProductTypeCategory.objects.get(name="Blend")

        response = self.client.post(
            self.subtype_list_url,
            {
                "category": category.id,
                "name": "WPE",
                "description": "",
                "sort_order": 9999,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_tree_action_returns_nested_subtypes(self):
        self.authenticate(self.superuser)

        response = self.client.get(self.category_tree_url, {"search": "Blend"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        blend_record = next((row for row in response.data if row["name"] == "Blend"), None)
        self.assertIsNotNone(blend_record)
        self.assertEqual([entry["name"] for entry in blend_record["subtypes"]], ["WPE", "Lumber"])
