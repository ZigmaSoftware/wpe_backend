"""Purchase master URL configuration with a browsable DRF index."""

from collections import OrderedDict
from django.urls import include, path

from core_system.api_router import ExtendedDefaultRouter

from . import views


router = ExtendedDefaultRouter()
router.extra_api_root_dict = OrderedDict ({
    "units": "unit-list",
    "units-create": "unit-create",
    "item-groups": "item-group-list",
    "item-groups-create": "item-group-create",
    "sub-groups": "sub-group-list",
    "sub-groups-create": "sub-group-create",
    "sub-groups-group-dropdown": "sub-group-group-dropdown",
    "categories": "category-list",
    "categories-create": "category-create",
    "categories-group-dropdown": "category-group-dropdown",
    "categories-sub-group-dropdown": "category-sub-group-dropdown",
    "items": "item-list",
    "items-create": "item-create",
    "items-group-dropdown": "item-group-dropdown",
    "items-sub-group-dropdown": "item-sub-group-dropdown",
    "products": "product-list",
    "products-create": "product-create",
    "products-company-dropdown": "product-company-dropdown",
    "products-group-dropdown": "product-group-dropdown",
    "products-sub-group-dropdown": "product-sub-group-dropdown",
    "boms": "bom-list",
    "boms-create": "bom-create",
    "products-dropdown": "product-dropdown",
    "items-dropdown": "item-dropdown",
})

# Unit endpoints
unit_patterns = [
    path('units/', views.unit_list, name='unit-list'),
    path('units/create/', views.create_unit, name='unit-create'),
    path('units/<int:pk>/', views.update_unit, name='unit-update'),
    path('units/<int:pk>/toggle/', views.toggle_unit, name='unit-toggle'),
]

# Item Group endpoints
item_group_patterns = [
    path('item-groups/', views.item_group_list, name='item-group-list'),
    path('item-groups/create/', views.create_item_group, name='item-group-create'),
    path('item-groups/<int:pk>/', views.update_item_group, name='item-group-update'),
    path('item-groups/<int:pk>/toggle/', views.toggle_item_group, name='item-group-toggle'),
]

# Item Sub Group endpoints
sub_group_patterns = [
    path('sub-groups/', views.sub_group_list, name='sub-group-list'),
    path('sub-groups/create/', views.create_sub_group, name='sub-group-create'),
    path('sub-groups/<int:pk>/', views.update_sub_group, name='sub-group-update'),
    path('sub-groups/<int:pk>/toggle/', views.toggle_sub_group, name='sub-group-toggle'),
    path('sub-groups/group-dropdown/', views.group_dropdown, name='sub-group-group-dropdown'),
]

# Category endpoints
category_patterns = [
    path('categories/', views.category_list, name='category-list'),
    path('categories/create/', views.create_category, name='category-create'),
    path('categories/<int:pk>/', views.update_category, name='category-update'),
    path('categories/<int:pk>/toggle/', views.toggle_category, name='category-toggle'),
    path('categories/group-dropdown/', views.group_dropdown, name='category-group-dropdown'),
    path('categories/sub-group-dropdown/', views.sub_group_dropdown, name='category-sub-group-dropdown'),
]

# Item Names/codes endpoints
item_patterns = [
    path('items/', views.item_list, name='item-list'),
    path('items/create/', views.create_item, name='item-create'),
    path('items/<int:pk>/toggle/', views.toggle_item, name='item-toggle'),
    path('items/group-dropdown/', views.group_dropdown, name='item-group-dropdown'),
    path('items/sub-group-dropdown/', views.sub_group_dropdown, name='item-sub-group-dropdown'),
]

# Product endpoints
product_patterns = [
    path('products/', views.product_list, name='product-list'),
    path('products/create/', views.create_product, name='product-create'),
    path('products/<int:pk>/', views.update_product, name='product-update'),
    path('products/<int:pk>/toggle/', views.toggle_product, name='product-toggle'),
    path('products/company-dropdown/', views.company_dropdown, name='product-company-dropdown'),
    path('products/group-dropdown/', views.group_dropdown, name='product-group-dropdown'),
    path('products/sub-group-dropdown/', views.sub_group_dropdown, name='product-sub-group-dropdown'),
]

# BOM endpoints
bom_patterns = [
    path('boms/', views.bom_list, name='bom-list'),
    path('boms/create/', views.create_bom, name='bom-create'),
    path('boms/<int:pk>/view/', views.view_bom, name='bom-view'),
    path('boms/<int:pk>/update/', views.update_bom, name='bom-update'),
    path('boms/<int:pk>/delete/', views.delete_bom, name='bom-delete'),
    path('products-dropdown/', views.product_dropdown, name='product-dropdown'),
    path('items-dropdown/', views.item_dropdown, name='item-dropdown'),
]

# Combine all patterns
urlpatterns = [path("", include(router.urls))] + [
    *unit_patterns,
    *item_group_patterns,
    *sub_group_patterns,
    *category_patterns,
    *item_patterns,
    *product_patterns,
    *bom_patterns,
]
