"""Admin registrations for common master entities."""

from django.contrib import admin

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
    CustomerStatutoryDetail,
    Project,
    State,
    Supplier,
    SupplierAddress,
    SupplierBankDetail,
    SupplierContactPerson,
    SupplierDocument,
    SupplierStatutoryDetail,
    Tax,
)


class ReadOnlyUniqueIDAdmin(admin.ModelAdmin):
    readonly_fields = ("unique_id",)


@admin.register(Continent)
class ContinentAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "code", "order_no", "status")
    list_filter = ("status",)
    search_fields = ("name", "code")
    ordering = ("order_no", "name", "id")


@admin.register(Country)
class CountryAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "code", "continent", "status")
    list_filter = ("continent", "status")
    search_fields = ("name", "code", "continent__name")
    autocomplete_fields = ("continent",)


@admin.register(State)
class StateAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "country", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name", "country__name")
    autocomplete_fields = ("country",)


@admin.register(City)
class CityAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "state", "country", "pincode", "is_active")
    list_filter = ("country", "state", "is_active", "city_type")
    search_fields = ("name", "pincode", "state__name", "country__name")
    autocomplete_fields = ("country", "state", "city_type")


@admin.register(Tax)
class TaxAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "country", "value", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name", "country__name")
    autocomplete_fields = ("country",)


@admin.register(Currency)
class CurrencyAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "code", "country", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name", "code", "country__name")
    autocomplete_fields = ("country",)


class CustomerContactInline(admin.TabularInline):
    model = CustomerContactPerson
    extra = 0


class CustomerBankInline(admin.TabularInline):
    model = CustomerBankDetail
    extra = 0


class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0


class CustomerDocumentInline(admin.TabularInline):
    model = CustomerDocument
    extra = 0


class CustomerStatutoryInline(admin.StackedInline):
    model = CustomerStatutoryDetail
    extra = 0
    max_num = 1


@admin.register(Customer)
class CustomerAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("customer_no", "customer_name", "customer_group", "customer_status", "is_active")
    list_filter = ("customer_group", "customer_status", "country", "is_active")
    search_fields = ("customer_no", "customer_name", "email", "mobile_no", "pan_number", "gst_number")
    autocomplete_fields = ("currency", "country", "state", "city")
    inlines = (
        CustomerStatutoryInline,
        CustomerContactInline,
        CustomerBankInline,
        CustomerAddressInline,
        CustomerDocumentInline,
    )


class SupplierContactInline(admin.TabularInline):
    model = SupplierContactPerson
    extra = 0


class SupplierBankInline(admin.TabularInline):
    model = SupplierBankDetail
    extra = 0


class SupplierAddressInline(admin.TabularInline):
    model = SupplierAddress
    extra = 0


class SupplierDocumentInline(admin.TabularInline):
    model = SupplierDocument
    extra = 0


class SupplierStatutoryInline(admin.StackedInline):
    model = SupplierStatutoryDetail
    extra = 0
    max_num = 1


@admin.register(Supplier)
class SupplierAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("supplier_no", "supplier_name", "supplier_group", "gst_status", "is_active")
    list_filter = ("supplier_group", "gst_status", "country", "is_active")
    search_fields = ("supplier_no", "supplier_name", "email", "mobile_no", "pan_number", "gst_number")
    autocomplete_fields = ("currency", "country", "state", "city")
    inlines = (
        SupplierStatutoryInline,
        SupplierContactInline,
        SupplierBankInline,
        SupplierAddressInline,
        SupplierDocumentInline,
    )


@admin.register(Company)
class CompanyAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "code", "country", "state", "city", "is_active")
    list_filter = ("country", "state", "city", "is_active")
    search_fields = ("name", "code")
    autocomplete_fields = ("country", "state", "city")


@admin.register(Project)
class ProjectAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("name", "code", "company", "project_date", "is_active")
    list_filter = ("company", "country", "state", "city", "is_active")
    search_fields = ("name", "code", "client_name", "company__name")
    autocomplete_fields = ("company", "country", "state", "city", "application_type")


@admin.register(CommonMaster)
class CommonMasterAdmin(ReadOnlyUniqueIDAdmin):
    list_display = ("type", "name", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("type", "name")
