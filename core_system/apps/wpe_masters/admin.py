from django.contrib import admin

from .models import (
    BranchMaster,
    DepartmentMaster,
    LocationMaster,
    PriceBookMaster,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    RoleMaster,
    SaleTypeMaster,
    WarehouseMaster,
    WPEUserCreation,
)


@admin.register(LocationMaster)
class LocationMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(BranchMaster)
class BranchMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(PriceBookMaster)
class PriceBookMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(WarehouseMaster)
class WarehouseMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(ProductionTypeMaster)
class ProductionTypeMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(SaleTypeMaster)
class SaleTypeMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(PurchaseTypeMaster)
class PurchaseTypeMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(RoleMaster)
class RoleMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(DepartmentMaster)
class DepartmentMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(WPEUserCreation)
class WPEUserCreationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone_no", "role", "is_active", "created_at")
    search_fields = ("full_name", "email", "user__username")
    list_filter = ("is_active", "role")
    filter_horizontal = (
        "authorized_branches",
        "authorized_price_books",
        "authorized_warehouses",
        "authorized_production_types",
        "authorized_sale_types",
        "authorized_purchase_types",
    )
