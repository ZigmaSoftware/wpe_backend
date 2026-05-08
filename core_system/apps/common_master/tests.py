from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Currency, Customer, Supplier
from .serializers import CustomerDocumentSerializer
from .models import City, Continent, Country, State


@override_settings(INTERNAL_API_KEY="test-internal-key")
class CommonMasterApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="common-master", password="test-pass-123")
        access_token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        self.continent = Continent.objects.create(name="Asia", status=True)
        self.country = Country.objects.create(continent=self.continent, name="India", code="IN", status=True)
        self.state = State.objects.create(country=self.country, name="Maharashtra", is_active=True)
        self.city = City.objects.create(
            country=self.country,
            state=self.state,
            name="Mumbai",
            pincode="400001",
            is_active=True,
        )
        self.currency = Currency.objects.create(country=self.country, name="Indian Rupee", code="INR", is_active=True)

    def test_create_customer_generates_code_and_copies_shipping_address(self):
        payload = {
            "customer_name": "Acme Industries",
            "customer_group": "domestic",
            "customer_division": "Polymer",
            "currency": self.currency.id,
            "country": self.country.id,
            "state": self.state.id,
            "city": self.city.id,
            "address": "Main office",
            "pincode": "400001",
            "mobile_no": "9876543210",
            "phone_no": "02222000000",
            "email": "accounts@acme.example",
            "pan_number": "ABCDE1234F",
            "gst_number": "27ABCDE1234F1Z5",
            "gst_registered": True,
            "customer_status": "active",
            "billing_address": {
                "name": "Billing HQ",
                "address": "Address 1",
                "country": self.country.id,
                "state": self.state.id,
                "city": self.city.id,
                "pincode": "400001",
                "contact_name": "Accounts",
                "contact_no": "9876543210",
                "gst_number": "27ABCDE1234F1Z5",
                "gst_status": "registered",
                "ecc_no": "ECC-001",
                "is_active": True,
            },
            "shipping_address": {
                "same_as_billing": True,
                "is_active": True,
            },
            "contact_persons": [
                {
                    "contact_person_name": "John Doe",
                    "designation": "Manager",
                    "email": "john@acme.example",
                    "mobile_no": "9876543211",
                    "is_active": True,
                }
            ],
            "bank_details": [
                {
                    "bank_name": "HDFC Bank",
                    "bank_address": "Mumbai",
                    "ifsc_code": "HDFC0001234",
                    "beneficiary_account_name": "Acme Industries",
                    "account_number": "123456789012",
                    "is_primary": True,
                    "is_active": True,
                }
            ],
        }

        response = self.client.post("/api/masters/customers/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["customer_no"], "CUS0001")
        self.assertEqual(response.data["data"]["billing_address"]["name"], "Billing HQ")
        self.assertEqual(response.data["data"]["shipping_address"]["name"], "Billing HQ")
        self.assertEqual(Customer.objects.count(), 1)

    def test_supplier_create_requires_gst_number_for_registered_status(self):
        payload = {
            "supplier_name": "Global Supplies",
            "supplier_group": "Domestic",
            "currency": self.currency.id,
            "country": self.country.id,
            "state": self.state.id,
            "city": self.city.id,
            "pincode": "400001",
            "address": "Supplier address",
            "mobile_no": "9876543210",
            "phone_no": "02222000000",
            "gst_status": "registered",
            "email": "vendor@example.com",
        }

        response = self.client.post("/api/masters/suppliers/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("gst_number", response.data)
        self.assertEqual(Supplier.objects.count(), 0)


class CustomerDocumentSerializerTests(TestCase):
    def test_rejects_unsupported_document_extension(self):
        continent = Continent.objects.create(name="Asia", status=True)
        country = Country.objects.create(continent=continent, name="India", code="IN", status=True)
        currency = Currency.objects.create(country=country, name="Indian Rupee", code="INR", is_active=True)
        customer = Customer.objects.create(
            customer_name="Acme Industries",
            customer_group="domestic",
            country=country,
            currency=currency,
            mobile_no="9876543210",
        )
        document = SimpleUploadedFile("danger.exe", b"binary-content", content_type="application/octet-stream")
        serializer = CustomerDocumentSerializer(
            data={"customer": customer.id, "document_type": "PAN", "file": document}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)
