"""URL routing for WPE master APIs."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BranchMasterViewSet,
    DepartmentMasterViewSet,
    LocationMasterViewSet,
    PriceBookMasterViewSet,
    ProductionTypeMasterViewSet,
    PurchaseTypeMasterViewSet,
    RolePermissionMatrixView,
    RoleMasterViewSet,
    SaleTypeMasterViewSet,
    UserScreenPermMatrixView,
    WarehouseMasterViewSet,
    WPEUserCreationViewSet,
)


router = DefaultRouter()
router.register(r"locations", LocationMasterViewSet, basename="wpe-location")
router.register(r"branches", BranchMasterViewSet, basename="wpe-branch")
router.register(r"price-books", PriceBookMasterViewSet, basename="wpe-price-book")
router.register(r"warehouses", WarehouseMasterViewSet, basename="wpe-warehouse")
router.register(r"production-types", ProductionTypeMasterViewSet, basename="wpe-production-type")
router.register(r"sale-types", SaleTypeMasterViewSet, basename="wpe-sale-type")
router.register(r"purchase-types", PurchaseTypeMasterViewSet, basename="wpe-purchase-type")
router.register(r"roles", RoleMasterViewSet, basename="wpe-role")
router.register(r"departments", DepartmentMasterViewSet, basename="wpe-department")
router.register(r"users", WPEUserCreationViewSet, basename="wpe-user")
router.register(r"role-permissions", RolePermissionMatrixView, basename="wpe-role-perm")
router.register(r"user-screen-permissions", UserScreenPermMatrixView, basename="wpe-user-screen-perm")

urlpatterns = [
    path("", include(router.urls)),
]
