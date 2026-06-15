from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    DepartmentMaster,
    DesignationMaster,
    ItemMaster,
    LocationMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    RoleMaster,
    UnitMaster,
)


UserModel = get_user_model()


class LocationMasterApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="location-user",
            email="location@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.list_url = "/api/wpe-masters/locations/"
        self.lookup_url = "/api/wpe-masters/locations/lookup/"

    def test_seeded_locations_default_to_blending_center(self):
        seeded_location = LocationMaster.objects.get(name="Blend WIP")

        self.assertEqual(seeded_location.center_type, LocationMaster.CenterType.BLENDING_CENTER)

    def test_create_location_persists_selected_center_type(self):
        response = self.client.post(
            self.list_url,
            {
                "name": "QA GRN Dock",
                "center_type": LocationMaster.CenterType.GRN_CENTER,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["center_type"], LocationMaster.CenterType.GRN_CENTER)
        self.assertTrue(
            LocationMaster.objects.filter(
                name="QA GRN Dock",
                center_type=LocationMaster.CenterType.GRN_CENTER,
            ).exists()
        )

    def test_location_list_can_be_filtered_by_center_type(self):
        LocationMaster.objects.create(
            name="QA Shared Location GRN",
            center_type=LocationMaster.CenterType.GRN_CENTER,
        )
        LocationMaster.objects.create(
            name="QA Shared Location Warehouse",
            center_type=LocationMaster.CenterType.WAREHOUSE_CENTER,
        )

        response = self.client.get(
            self.list_url,
            {
                "search": "QA Shared Location",
                "center_type": LocationMaster.CenterType.GRN_CENTER,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "QA Shared Location GRN")
        self.assertEqual(response.data["results"][0]["center_type"], LocationMaster.CenterType.GRN_CENTER)

    def test_location_lookup_can_be_filtered_by_center_type(self):
        grn_location = LocationMaster.objects.create(
            name="QA Lookup GRN",
            center_type=LocationMaster.CenterType.GRN_CENTER,
        )
        LocationMaster.objects.create(
            name="QA Lookup Blending",
            center_type=LocationMaster.CenterType.BLENDING_CENTER,
        )

        response = self.client.get(
            self.lookup_url,
            {"center_type": LocationMaster.CenterType.GRN_CENTER},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        matched = next((row for row in response.data if row["id"] == grn_location.id), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["name"], "QA Lookup GRN")
        self.assertFalse(any(row["name"] == "QA Lookup Blending" for row in response.data))


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

    def test_subtype_list_includes_variant_count(self):
        self.authenticate(self.superuser)
        category = ProductTypeCategory.objects.get(name="Blend")
        subtype = ProductTypeSubtype.objects.create(
            category=category,
            name="QA Variant Count Subtype",
            description="",
            sort_order=10001,
            is_active=True,
        )
        unit = UnitMaster.objects.create(uom_code="KG", name="Kilogram", decimal_allowed=True, decimal_places=3)
        ItemMaster.objects.create(
            item_name="QA Variant Alpha",
            sub_category=subtype,
            description="Alpha specification",
            item_type=ItemMaster.ItemType.RM,
            uom=unit,
        )
        ItemMaster.objects.create(
            item_name="QA Variant Beta",
            sub_category=subtype,
            description="Beta specification",
            item_type=ItemMaster.ItemType.RM,
            uom=unit,
        )

        response = self.client.get(self.subtype_list_url, {"category_id": category.id, "search": "QA Variant Count"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record = next((row for row in response.data["results"] if row["id"] == subtype.id), None)
        self.assertIsNotNone(record)
        self.assertEqual(record["variant_count"], 2)


class DesignationLookupApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="designation-lookup-user",
            email="designation-lookup@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_lookup_includes_department_context(self):
        department = DepartmentMaster.objects.create(name="Administration")
        designation = DesignationMaster.objects.create(name="Supervisor", department=department)

        response = self.client.get("/api/wpe-masters/designations/lookup/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        matched = next((row for row in response.data if row["id"] == designation.id), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["name"], "Supervisor")
        self.assertEqual(matched["department_id"], department.id)
        self.assertEqual(matched["department_name"], "Administration")


class RoleLookupApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="role-lookup-user",
            email="role-lookup@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_lookup_includes_designation_and_department_context(self):
        department = DepartmentMaster.objects.create(name="Administration")
        designation = DesignationMaster.objects.create(name="Supervisor", department=department)
        role = RoleMaster.objects.create(name="Store Supervisor", designation=designation)

        response = self.client.get("/api/wpe-masters/roles/lookup/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        matched = next((row for row in response.data if row["id"] == role.id), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched["name"], "Store Supervisor")
        self.assertEqual(matched["designation_id"], designation.id)
        self.assertEqual(matched["designation_name"], "Supervisor")
        self.assertEqual(matched["department_id"], department.id)
        self.assertEqual(matched["department_name"], "Administration")


class ItemVariantApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="item-variant-user",
            email="item-variant@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_item_variants_alias_exposes_description_field(self):
        category = ProductTypeCategory.objects.create(name="QA Electrical Category")
        subtype = ProductTypeSubtype.objects.create(name="QA Cable", category=category)
        unit = UnitMaster.objects.create(uom_code="MTR", name="Meter", decimal_allowed=True, decimal_places=2)
        item = ItemMaster.objects.create(
            item_name="2.5 sq.mm Copper Cable",
            sub_category=subtype,
            description="FRLS electrical cable",
            item_type=ItemMaster.ItemType.RM,
            uom=unit,
        )

        response = self.client.get("/api/wpe-masters/item-variants/", {"search": "Copper"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record = next((row for row in response.data["results"] if row["id"] == item.id), None)
        self.assertIsNotNone(record)
        self.assertEqual(record["description"], "FRLS electrical cable")
        self.assertEqual(record["sub_category_name"], "QA Cable")
        self.assertEqual(record["category_name"], "QA Electrical Category")

    def test_duplicate_variant_name_is_blocked_only_within_same_sub_category(self):
        category = ProductTypeCategory.objects.create(name="QA Blending Category")
        first_subtype = ProductTypeSubtype.objects.create(name="QA Wood Powder", category=category)
        second_subtype = ProductTypeSubtype.objects.create(name="QA HDPE Chips", category=category)
        unit = UnitMaster.objects.create(uom_code="KG", name="Kilogram", decimal_allowed=True, decimal_places=3)

        ItemMaster.objects.create(
            item_name="White Grade",
            sub_category=first_subtype,
            description="Existing first variant",
            item_type=ItemMaster.ItemType.RM,
            uom=unit,
        )

        duplicate_response = self.client.post(
            "/api/wpe-masters/item-variants/",
            {
                "item_name": "White Grade",
                "sub_category": first_subtype.id,
                "description": "Duplicate in same sub category",
                "item_type": ItemMaster.ItemType.RM,
                "uom": unit.id,
                "gst_percentage": "0.00",
                "minimum_stock": "0.000",
                "maximum_stock": "0.000",
                "reorder_level": "0.000",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", duplicate_response.data)

        allowed_response = self.client.post(
            "/api/wpe-masters/item-variants/",
            {
                "item_name": "White Grade",
                "sub_category": second_subtype.id,
                "description": "Allowed in a different sub category",
                "item_type": ItemMaster.ItemType.RM,
                "uom": unit.id,
                "gst_percentage": "0.00",
                "minimum_stock": "0.000",
                "maximum_stock": "0.000",
                "reorder_level": "0.000",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(allowed_response.status_code, status.HTTP_201_CREATED)
