"""URL routing for WPE master APIs."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BranchMasterViewSet,
    DepartmentMasterViewSet,
    DesignationMasterViewSet,
    ItemMasterViewSet,
    LocationMasterViewSet,
    PrinterMasterViewSet,
    PriceBookMasterViewSet,
    ProductTypeCategoryViewSet,
    ProductTypeSubtypeViewSet,
    ProductionTypeMasterViewSet,
    PurchaseTypeMasterViewSet,
    QRLabelTemplateMasterViewSet,
    RolePermissionMatrixView,
    RoleMasterViewSet,
    SaleTypeMasterViewSet,
    SerialPortConfigurationMasterViewSet,
    StoreMasterViewSet,
    UnitMasterViewSet,
    UserScreenPermMatrixView,
    WarehouseMasterViewSet,
    WeighmentScaleMasterViewSet,
    WPEUserCreationViewSet,
)


router = DefaultRouter()
router.register(r"locations", LocationMasterViewSet, basename="wpe-location")
router.register(r"branches", BranchMasterViewSet, basename="wpe-branch")
router.register(r"price-books", PriceBookMasterViewSet, basename="wpe-price-book")
router.register(r"warehouses", WarehouseMasterViewSet, basename="wpe-warehouse")
router.register(r"stores", StoreMasterViewSet, basename="wpe-store")
router.register(r"units", UnitMasterViewSet, basename="wpe-unit")
router.register(r"item-creations", ItemMasterViewSet, basename="wpe-item")
router.register(r"item-variants", ItemMasterViewSet, basename="wpe-item-variant")
router.register(r"weighment-scale-creations", WeighmentScaleMasterViewSet, basename="wpe-weighment-scale")
router.register(r"printer-creations", PrinterMasterViewSet, basename="wpe-printer")
router.register(r"qr-label-templates", QRLabelTemplateMasterViewSet, basename="wpe-qr-label-template")
router.register(r"serial-port-configurations", SerialPortConfigurationMasterViewSet, basename="wpe-serial-port-configuration")
router.register(r"production-types", ProductionTypeMasterViewSet, basename="wpe-production-type")
router.register(r"product-type-categories", ProductTypeCategoryViewSet, basename="wpe-product-type-category")
router.register(r"product-type-subtypes", ProductTypeSubtypeViewSet, basename="wpe-product-type-subtype")
router.register(r"sale-types", SaleTypeMasterViewSet, basename="wpe-sale-type")
router.register(r"purchase-types", PurchaseTypeMasterViewSet, basename="wpe-purchase-type")
router.register(r"roles", RoleMasterViewSet, basename="wpe-role")
router.register(r"departments", DepartmentMasterViewSet, basename="wpe-department")
router.register(r"designations", DesignationMasterViewSet, basename="wpe-designation")
router.register(r"users", WPEUserCreationViewSet, basename="wpe-user")
router.register(r"role-permissions", RolePermissionMatrixView, basename="wpe-role-perm")
router.register(r"user-screen-permissions", UserScreenPermMatrixView, basename="wpe-user-screen-perm")

urlpatterns = [
    path("", include(router.urls)),
]
