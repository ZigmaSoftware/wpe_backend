"""URL configuration for common master APIs."""

from django.urls import path

from .views import (
    CityViewSet,
    CompanyViewSet,
    ContinentViewSet,
    CountryViewSet,
    CurrencyViewSet,
    CustomerDocumentViewSet,
    CustomerViewSet,
    ProjectViewSet,
    StateViewSet,
    SupplierDocumentViewSet,
    SupplierViewSet,
    TaxViewSet,
)


continent_list = ContinentViewSet.as_view({"get": "list", "post": "create"})
continent_create = ContinentViewSet.as_view({"post": "create"})
continent_detail = ContinentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
continent_toggle = ContinentViewSet.as_view({"patch": "toggle_status"})
continent_lookup = ContinentViewSet.as_view({"get": "lookup"})

country_list = CountryViewSet.as_view({"get": "list", "post": "create"})
country_create = CountryViewSet.as_view({"post": "create"})
country_detail = CountryViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
country_toggle = CountryViewSet.as_view({"patch": "toggle_status"})
country_lookup = CountryViewSet.as_view({"get": "lookup"})

state_list = StateViewSet.as_view({"get": "list", "post": "create"})
state_create = StateViewSet.as_view({"post": "create"})
state_detail = StateViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
state_toggle = StateViewSet.as_view({"patch": "toggle_status"})
state_lookup = StateViewSet.as_view({"get": "lookup"})
state_by_country = StateViewSet.as_view({"get": "by_country"})

city_list = CityViewSet.as_view({"get": "list", "post": "create"})
city_create = CityViewSet.as_view({"post": "create"})
city_detail = CityViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
city_toggle = CityViewSet.as_view({"patch": "toggle_status"})
city_lookup = CityViewSet.as_view({"get": "lookup"})
city_types = CityViewSet.as_view({"get": "types"})

tax_list = TaxViewSet.as_view({"get": "list", "post": "create"})
tax_create = TaxViewSet.as_view({"post": "create"})
tax_detail = TaxViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
tax_toggle = TaxViewSet.as_view({"patch": "toggle_status"})
tax_lookup = TaxViewSet.as_view({"get": "lookup"})

currency_list = CurrencyViewSet.as_view({"get": "list", "post": "create"})
currency_create = CurrencyViewSet.as_view({"post": "create"})
currency_detail = CurrencyViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
currency_toggle = CurrencyViewSet.as_view({"patch": "toggle_status"})
currency_lookup = CurrencyViewSet.as_view({"get": "lookup"})

customer_list = CustomerViewSet.as_view({"get": "list", "post": "create"})
customer_create = CustomerViewSet.as_view({"post": "create"})
customer_detail = CustomerViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
customer_toggle = CustomerViewSet.as_view({"patch": "toggle_status"})
customer_lookup = CustomerViewSet.as_view({"get": "lookup"})

customer_document_list = CustomerDocumentViewSet.as_view({"get": "list", "post": "create"})
customer_document_detail = CustomerDocumentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
customer_document_toggle = CustomerDocumentViewSet.as_view({"patch": "toggle_status"})

supplier_list = SupplierViewSet.as_view({"get": "list", "post": "create"})
supplier_create = SupplierViewSet.as_view({"post": "create"})
supplier_detail = SupplierViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
supplier_toggle = SupplierViewSet.as_view({"patch": "toggle_status"})
supplier_lookup = SupplierViewSet.as_view({"get": "lookup"})

supplier_document_list = SupplierDocumentViewSet.as_view({"get": "list", "post": "create"})
supplier_document_detail = SupplierDocumentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
supplier_document_toggle = SupplierDocumentViewSet.as_view({"patch": "toggle_status"})

company_list = CompanyViewSet.as_view({"get": "list", "post": "create"})
company_create = CompanyViewSet.as_view({"post": "create"})
company_detail = CompanyViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
company_toggle = CompanyViewSet.as_view({"patch": "toggle_status"})
company_lookup = CompanyViewSet.as_view({"get": "lookup"})

project_list = ProjectViewSet.as_view({"get": "list", "post": "create"})
project_create = ProjectViewSet.as_view({"post": "create"})
project_detail = ProjectViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})
project_toggle = ProjectViewSet.as_view({"patch": "toggle_status"})
application_types = ProjectViewSet.as_view({"get": "application_types"})


urlpatterns = [
    path("continents/", continent_list, name="continent-list"),
    path("continents/create/", continent_create, name="continent-create"),
    path("continents/lookup/", continent_lookup, name="continent-lookup"),
    path("continents/<int:pk>/", continent_detail, name="continent-detail"),
    path("continents/<int:pk>/toggle/", continent_toggle, name="continent-toggle"),
    path("countries/", country_list, name="country-list"),
    path("countries/create/", country_create, name="country-create"),
    path("countries/dropdown/", country_lookup, name="countries-dropdown"),
    path("countries/lookup/", country_lookup, name="country-lookup"),
    path("countries/<int:pk>/", country_detail, name="country-detail"),
    path("countries/<int:pk>/toggle/", country_toggle, name="country-toggle"),
    path("states/", state_list, name="state-list"),
    path("states/create/", state_create, name="state-create"),
    path("states/lookup/", state_lookup, name="state-lookup"),
    path("states/by-country/<int:country_id>/", state_by_country, name="states-by-country"),
    path("states/<int:pk>/", state_detail, name="state-detail"),
    path("states/<int:pk>/toggle/", state_toggle, name="state-toggle"),
    path("cities/", city_list, name="city-list-rest"),
    path("cities/list/", city_list, name="city-list"),
    path("cities/create/", city_create, name="city-create"),
    path("cities/lookup/", city_lookup, name="city-lookup"),
    path("cities/types/", city_types, name="city-types"),
    path("cities/<int:pk>/", city_detail, name="city-detail"),
    path("cities/<int:pk>/toggle/", city_toggle, name="city-toggle"),
    path("taxes/", tax_list, name="tax-list"),
    path("taxes/create/", tax_create, name="tax-create"),
    path("taxes/lookup/", tax_lookup, name="tax-lookup"),
    path("taxes/<int:pk>/", tax_detail, name="tax-detail"),
    path("taxes/<int:pk>/toggle/", tax_toggle, name="tax-toggle"),
    path("currencies/", currency_list, name="currency-list"),
    path("currencies/create/", currency_create, name="currency-create"),
    path("currencies/lookup/", currency_lookup, name="currency-lookup"),
    path("currencies/<int:pk>/", currency_detail, name="currency-detail"),
    path("currencies/<int:pk>/toggle/", currency_toggle, name="currency-toggle"),
    path("customers/", customer_list, name="customer-list"),
    path("customers/create/", customer_create, name="customer-create"),
    path("customers/lookup/", customer_lookup, name="customer-lookup"),
    path("customers/<int:pk>/", customer_detail, name="customer-detail"),
    path("customers/<int:pk>/toggle/", customer_toggle, name="customer-toggle"),
    path("customer-documents/", customer_document_list, name="customer-document-list"),
    path("customer-documents/<int:pk>/", customer_document_detail, name="customer-document-detail"),
    path("customer-documents/<int:pk>/toggle/", customer_document_toggle, name="customer-document-toggle"),
    path("suppliers/", supplier_list, name="supplier-list"),
    path("suppliers/create/", supplier_create, name="supplier-create"),
    path("suppliers/lookup/", supplier_lookup, name="supplier-lookup"),
    path("suppliers/<int:pk>/", supplier_detail, name="supplier-detail"),
    path("suppliers/<int:pk>/toggle/", supplier_toggle, name="supplier-toggle"),
    path("supplier-documents/", supplier_document_list, name="supplier-document-list"),
    path("supplier-documents/<int:pk>/", supplier_document_detail, name="supplier-document-detail"),
    path("supplier-documents/<int:pk>/toggle/", supplier_document_toggle, name="supplier-document-toggle"),
    path("companies/", company_list, name="company-list-rest"),
    path("company/", company_list, name="company-list"),
    path("company/create/", company_create, name="company-create"),
    path("companies/lookup/", company_lookup, name="company-lookup"),
    path("company/<int:pk>/", company_detail, name="company-detail"),
    path("company/<int:pk>/toggle/", company_toggle, name="company-toggle"),
    path("projects/", project_list, name="project-list"),
    path("projects/create/", project_create, name="project-create"),
    path("projects/application-types/", application_types, name="application-types"),
    path("projects/<int:pk>/", project_detail, name="project-detail"),
    path("projects/<int:pk>/toggle/", project_toggle, name="project-toggle"),
]
