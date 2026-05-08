from collections import OrderedDict
from django.urls import include, path

from core_system.api_router import ExtendedDefaultRouter

from . import views

# Initialize router for ViewSets
router = ExtendedDefaultRouter()
router.register(r'continents-list', views.ContinentViewSet)
router.extra_api_root_dict = OrderedDict ({
    "countries": "country-list",
    "countries-create": "country-create",
    "continents": "continent-list",
    "continents-create": "continent-create",
    "states": "state-list",
    "states-create": "state-create",
    "cities": "city-list",
    "city-types": "city-types",
    "cities-create": "city-create",
    "taxes": "tax-list",
    "taxes-create": "tax-create",
    "companies": "company-list",
    "companies-create": "company-create",
    "projects": "project-list",
    "projects-create": "project-create",
    "countries-dropdown": "countries-dropdown",
})


# Country endpoints
country_patterns = [
    path('countries/', views.country_list, name='country-list'),
    path('countries/create/', views.create_country, name='country-create'),
    path('countries/<int:pk>/', views.update_country, name='country-update'),
    path('countries/<int:pk>/toggle/', views.toggle_country, name='country-toggle'),
]

# Continent endpoints
continent_patterns = [
    path('continents/', views.continent_list, name='continent-list'),
    path('continents/create/', views.create_continent, name='continent-create'),
    path('continents/<int:pk>/', views.update_continent, name='continent-update'),
    path('continents/<int:pk>/toggle/', views.toggle_continent, name='continent-toggle'),
]

# State endpoints
state_patterns = [
    path('states/', views.list_states, name='state-list'),
    path('states/create/', views.create_state, name='state-create'),
    path('states/toggle/<int:pk>/', views.toggle_state, name='state-toggle'),
]

# City endpoints
city_patterns = [
    path('cities/types/', views.get_city_types, name='city-types'),
    path('cities/list/', views.list_city, name='city-list'),
    path('cities/create/', views.create_city, name='city-create'),
    path('cities/toggle/<int:pk>/', views.toggle_city, name='city-toggle'),
    path('cities/<int:pk>/', views.get_city, name='city-detail'),
]

# Tax endpoints
tax_patterns = [
    path('taxes/', views.list_tax, name='tax-list'),
    path('taxes/create/', views.create_tax, name='tax-create'),
    path('taxes/<int:pk>/', views.get_tax, name='tax-detail'),
    path('taxes/<int:pk>/toggle/', views.toggle_tax, name='tax-toggle'),
]

#Company Creation
company_patterns = [
    path('company/', views.list_company, name='company-list'),
    path('company/create/', views.create_company, name='company-create'),
    # path('company/<int:pk>/', views.update_company),
    path('company/<int:pk>/toggle/', views.toggle_company, name='company-toggle'),
]

# Project Creation
project_patterns = [
    path('projects/', views.list_project, name='project-list'),
    path('projects/create/', views.create_project, name='project-create'),
    # path('projects/<int:pk>/', views.update_project),
    path('projects/<int:pk>/toggle/', views.toggle_project, name='project-toggle'),
]

# Dropdown endpoints (placed at end for lower priority)
dropdown_patterns = [
    path('countries/dropdown/', views.get_countries, name='countries-dropdown'),
    path('states/by-country/<int:country_id>/', views.get_states_by_country, name='states-by-country'),
]

# Combine all patterns
urlpatterns = [
    path('', include(router.urls)),
] + country_patterns + continent_patterns + state_patterns + city_patterns + tax_patterns + dropdown_patterns + company_patterns + project_patterns
