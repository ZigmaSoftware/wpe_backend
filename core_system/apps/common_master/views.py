"""DRF viewsets for common masters and ERP partner APIs."""

from __future__ import annotations

from django.db.models import Prefetch, ProtectedError, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.admin_master.pagination import AdminMasterPagination
from common.drf import (
    EnvelopedMutationMixin,
    LookupQuerysetMixin,
    ProtectedDestroyMixin,
    QueryParamFilterMixin,
    ResponseSerializerMixin,
    StandardizedListMixin,
    ToggleStatusMixin,
)

from .models import (
    City,
    CommonMaster,
    Company,
    Continent,
    Country,
    Currency,
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContactPerson,
    CustomerDocument,
    Project,
    State,
    Supplier,
    SupplierAddress,
    SupplierBankDetail,
    SupplierContactPerson,
    SupplierDocument,
    Tax,
)
from .serializers import (
    CitySerializer,
    CompanySerializer,
    ContinentSerializer,
    CountrySerializer,
    CurrencySerializer,
    CustomerDocumentSerializer,
    CustomerReadSerializer,
    CustomerWriteSerializer,
    ProjectSerializer,
    StateSerializer,
    SupplierDocumentSerializer,
    SupplierReadSerializer,
    SupplierWriteSerializer,
    TaxSerializer,
)

class CommonMasterViewSet(
    StandardizedListMixin,
    EnvelopedMutationMixin,
    ProtectedDestroyMixin,
    ToggleStatusMixin,
    LookupQuerysetMixin,
    QueryParamFilterMixin,
    ResponseSerializerMixin,
    viewsets.ModelViewSet,
):
    permission_classes = [IsAuthenticated]
    pagination_class = AdminMasterPagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    resource_name = "Record"
    status_field = "is_active"
    protected_error_as_validation_error = True

    @property
    def protected_error_message(self):
        return f"{self.resource_name} cannot be deleted because dependent records exist."

    def build_destroy_success_response(self):
        return Response({"message": f"{self.resource_name} deleted successfully."})

    @action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        return self.perform_toggle_status()


class ContinentViewSet(CommonMasterViewSet):
    queryset = Continent.objects.all().order_by("order_no", "name", "id")
    serializer_class = ContinentSerializer
    resource_name = "Continent"
    status_field = "status"
    search_fields = ("name", "code")
    ordering_fields = ("order_no", "name", "id")
    filterset_map = {
        "is_active": "status",
        "status": "status",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.get_queryset().filter(status=True).values("id", "name", "code", "order_no")
        return Response(list(queryset))


class CountryViewSet(CommonMasterViewSet):
    queryset = Country.objects.select_related("continent").all().order_by("name", "id")
    serializer_class = CountrySerializer
    resource_name = "Country"
    status_field = "status"
    search_fields = ("name", "code", "continent__name")
    ordering_fields = ("name", "code", "continent__name", "id")
    filterset_map = {
        "continent": "continent_id",
        "continent_id": "continent_id",
        "is_active": "status",
        "status": "status",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(status=True).values("id", "name", "code")
        return Response(list(queryset))


class StateViewSet(CommonMasterViewSet):
    queryset = State.objects.select_related("country").all().order_by("name", "id")
    serializer_class = StateSerializer
    resource_name = "State"
    search_fields = ("name", "country__name")
    ordering_fields = ("name", "country__name", "id")
    filterset_map = {
        "country": "country_id",
        "country_id": "country_id",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name", "country_id")
        return Response(list(queryset))

    @action(detail=False, methods=["get"], url_path="by-country/(?P<country_id>[^/.]+)")
    def by_country(self, request, country_id=None):
        queryset = self.get_queryset().filter(country_id=country_id, is_active=True).values("id", "name")
        return Response(list(queryset))


class CityViewSet(CommonMasterViewSet):
    queryset = City.objects.select_related("country", "state", "city_type").all().order_by("name", "id")
    serializer_class = CitySerializer
    resource_name = "City"
    search_fields = ("name", "pincode", "state__name", "country__name")
    ordering_fields = ("name", "pincode", "state__name", "country__name", "id")
    filterset_map = {
        "country": "country_id",
        "country_id": "country_id",
        "state": "state_id",
        "state_id": "state_id",
        "city_type": "city_type_id",
        "city_type_id": "city_type_id",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name", "state_id")
        return Response(list(queryset))

    @action(detail=False, methods=["get"], url_path="types")
    def types(self, request):
        queryset = CommonMaster.objects.filter(type="CITY_TYPE", is_active=True).values("id", "name")
        return Response(list(queryset))


class TaxViewSet(CommonMasterViewSet):
    queryset = Tax.objects.select_related("country").all().order_by("name", "id")
    serializer_class = TaxSerializer
    resource_name = "Tax"
    search_fields = ("name", "country__name", "value")
    ordering_fields = ("name", "value", "country__name", "id")
    filterset_map = {
        "country": "country_id",
        "country_id": "country_id",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name", "value")
        return Response(list(queryset))


class CurrencyViewSet(CommonMasterViewSet):
    queryset = Currency.objects.select_related("country").all().order_by("name", "code", "id")
    serializer_class = CurrencySerializer
    resource_name = "Currency"
    search_fields = ("name", "code", "country__name")
    ordering_fields = ("name", "code", "country__name", "id")
    filterset_map = {
        "country": "country_id",
        "country_id": "country_id",
        "is_active": "is_active",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name", "code")
        return Response(list(queryset))


class CustomerViewSet(CommonMasterViewSet):
    serializer_class = CustomerWriteSerializer
    response_serializer_class = CustomerReadSerializer
    resource_name = "Customer"
    search_fields = (
        "customer_no",
        "customer_name",
        "email",
        "mobile_no",
        "pan_number",
        "gst_number",
    )
    ordering_fields = ("customer_no", "customer_name", "customer_since", "created_at", "id")
    filterset_map = {
        "customer_group": "customer_group",
        "customer_status": "customer_status",
        "currency": "currency_id",
        "currency_id": "currency_id",
        "country": "country_id",
        "country_id": "country_id",
        "state": "state_id",
        "state_id": "state_id",
        "city": "city_id",
        "city_id": "city_id",
        "is_active": "is_active",
    }

    def get_queryset(self):
        address_queryset = CustomerAddress.objects.select_related("country", "state", "city").all()
        return (
            Customer.objects.select_related("currency", "country", "state", "city", "statutory_detail")
            .prefetch_related(
                "contact_persons",
                "bank_details",
                "documents",
                Prefetch("addresses", queryset=address_queryset),
            )
            .all()
            .order_by("customer_name", "customer_no", "id")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return CustomerReadSerializer
        return CustomerWriteSerializer

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values(
            "id",
            "customer_no",
            "customer_name",
        )
        return Response(list(queryset))

    @action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        if instance.customer_status == Customer.CustomerStatus.BLOCKED:
            raise ValidationError({"detail": "Blocked customers cannot be toggled. Update the customer status explicitly."})

        instance.customer_status = (
            Customer.CustomerStatus.INACTIVE
            if instance.customer_status == Customer.CustomerStatus.ACTIVE
            else Customer.CustomerStatus.ACTIVE
        )
        instance.is_active = instance.customer_status == Customer.CustomerStatus.ACTIVE
        instance.save(update_fields=["customer_status", "is_active", "updated_at"])
        return Response(
            {
                "message": "Customer status updated.",
                "status": instance.customer_status,
                "is_active": instance.is_active,
            }
        )


class SupplierViewSet(CommonMasterViewSet):
    serializer_class = SupplierWriteSerializer
    response_serializer_class = SupplierReadSerializer
    resource_name = "Supplier"
    search_fields = (
        "supplier_no",
        "supplier_name",
        "email",
        "mobile_no",
        "pan_number",
        "gst_number",
    )
    ordering_fields = ("supplier_no", "supplier_name", "created_at", "id")
    filterset_map = {
        "supplier_group": "supplier_group",
        "currency": "currency_id",
        "currency_id": "currency_id",
        "country": "country_id",
        "country_id": "country_id",
        "state": "state_id",
        "state_id": "state_id",
        "city": "city_id",
        "city_id": "city_id",
        "gst_status": "gst_status",
        "is_active": "is_active",
        "msme_type": "msme_type",
    }

    def get_queryset(self):
        address_queryset = SupplierAddress.objects.select_related("country", "state", "city").all()
        return (
            Supplier.objects.select_related("currency", "country", "state", "city", "statutory_detail")
            .prefetch_related(
                "contact_persons",
                "bank_details",
                "documents",
                Prefetch("addresses", queryset=address_queryset),
            )
            .all()
            .order_by("supplier_name", "supplier_no", "id")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return SupplierReadSerializer
        return SupplierWriteSerializer

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values(
            "id",
            "supplier_no",
            "supplier_name",
        )
        return Response(list(queryset))


class CustomerDocumentViewSet(CommonMasterViewSet):
    queryset = CustomerDocument.objects.select_related("customer").all().order_by("-created_at", "-id")
    serializer_class = CustomerDocumentSerializer
    resource_name = "Customer document"
    search_fields = ("document_type", "remarks", "customer__customer_no", "customer__customer_name")
    ordering_fields = ("created_at", "document_type", "customer__customer_no", "id")
    filterset_map = {
        "customer": "customer_id",
        "customer_id": "customer_id",
        "document_type": "document_type",
        "is_active": "is_active",
    }


class SupplierDocumentViewSet(CommonMasterViewSet):
    queryset = SupplierDocument.objects.select_related("supplier").all().order_by("-created_at", "-id")
    serializer_class = SupplierDocumentSerializer
    resource_name = "Supplier document"
    search_fields = ("document_type", "remarks", "supplier__supplier_no", "supplier__supplier_name")
    ordering_fields = ("created_at", "document_type", "supplier__supplier_no", "id")
    filterset_map = {
        "supplier": "supplier_id",
        "supplier_id": "supplier_id",
        "document_type": "document_type",
        "is_active": "is_active",
    }


class CompanyViewSet(CommonMasterViewSet):
    queryset = Company.objects.select_related("country", "state", "city").all().order_by("-id")
    serializer_class = CompanySerializer
    resource_name = "Company"
    search_fields = ("name", "code", "city__name", "state__name")
    ordering_fields = ("name", "code", "created_at", "id")
    filterset_map = {
        "country": "country_id",
        "country_id": "country_id",
        "state": "state_id",
        "state_id": "state_id",
        "city": "city_id",
        "city_id": "city_id",
        "is_active": "is_active",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name", "code")
        return Response(list(queryset))


class ProjectViewSet(CommonMasterViewSet):
    queryset = Project.objects.select_related(
        "company",
        "country",
        "state",
        "city",
        "application_type",
    ).all().order_by("-id")
    serializer_class = ProjectSerializer
    resource_name = "Project"
    search_fields = ("name", "code", "company__name", "client_name")
    ordering_fields = ("project_date", "name", "code", "created_at", "id")
    filterset_map = {
        "company": "company_id",
        "company_id": "company_id",
        "country": "country_id",
        "country_id": "country_id",
        "state": "state_id",
        "state_id": "state_id",
        "city": "city_id",
        "city_id": "city_id",
        "application_type": "application_type_id",
        "application_type_id": "application_type_id",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"], url_path="application-types")
    def application_types(self, request):
        queryset = CommonMaster.objects.filter(type="APPLICATION_TYPE", is_active=True).values("id", "name")
        return Response(list(queryset))
