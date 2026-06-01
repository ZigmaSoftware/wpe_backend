from django.contrib import admin

from .models import (
    BranchMaster,
    DepartmentMaster,
    DesignationMaster,
    ItemMaster,
    LocationMaster,
    PrinterMaster,
    PriceBookMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    QRLabelTemplateMaster,
    RoleMaster,
    SaleTypeMaster,
    SerialPortConfigurationMaster,
    StoreMaster,
    UnitMaster,
    WarehouseMaster,
    WeighmentScaleMaster,
    WPEUserCreation,
)


class ProductTypeSubtypeInline(admin.TabularInline):
    model = ProductTypeSubtype
    extra = 0
    fields = ("name", "code", "sort_order", "is_active")
    readonly_fields = ("code",)
    ordering = ("sort_order", "name")


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
    list_display = ("code", "name", "warehouse_type", "is_active", "created_at")
    search_fields = ("code", "name", "description")
    list_filter = ("warehouse_type", "is_active")


@admin.register(StoreMaster)
class StoreMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    search_fields = ("code", "name", "description")
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
    list_display = ("code", "name", "designation", "is_active", "created_at")
    search_fields = ("code", "name", "description", "designation__name")
    list_filter = ("is_active",)


@admin.register(DepartmentMaster)
class DepartmentMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department_head", "is_active", "created_at")
    search_fields = ("code", "name", "description", "department_head__full_name")
    list_filter = ("is_active",)


@admin.register(DesignationMaster)
class DesignationMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "is_active", "created_at")
    search_fields = ("code", "name", "description", "department__name")
    list_filter = ("department", "is_active")


@admin.register(UnitMaster)
class UnitMasterAdmin(admin.ModelAdmin):
    list_display = ("uom_code", "name", "decimal_allowed", "decimal_places", "is_active", "created_at")
    search_fields = ("uom_code", "name")
    list_filter = ("decimal_allowed", "is_active")


@admin.register(ProductTypeCategory)
class ProductTypeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_active", "created_at")
    search_fields = ("name", "code", "description")
    list_filter = ("is_active",)
    ordering = ("sort_order", "name")
    inlines = [ProductTypeSubtypeInline]


@admin.register(ProductTypeSubtype)
class ProductTypeSubtypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "code", "sort_order", "is_active", "created_at")
    search_fields = ("name", "code", "description", "category__name")
    list_filter = ("category", "is_active")
    ordering = ("category__sort_order", "category__name", "sort_order", "name")


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


@admin.register(ItemMaster)
class ItemMasterAdmin(admin.ModelAdmin):
    list_display = ("item_code", "item_name", "sub_category", "item_type", "uom", "is_active", "created_at")
    search_fields = ("item_code", "item_name", "sub_category__name", "sub_category__category__name", "uom__uom_code")
    list_filter = ("item_type", "is_active", "uom")


@admin.register(WeighmentScaleMaster)
class WeighmentScaleMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "machine", "connection_type", "is_auto_capture", "is_active", "created_at")
    search_fields = ("code", "name", "department__name", "machine__name", "machine__machine_code", "port_name")
    list_filter = ("department", "connection_type", "is_auto_capture", "is_active")


@admin.register(PrinterMaster)
class PrinterMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "printer_type", "department", "connection_type", "is_active", "created_at")
    search_fields = ("code", "name", "printer_type", "department__name", "ip_address")
    list_filter = ("printer_type", "department", "connection_type", "is_active")


@admin.register(QRLabelTemplateMaster)
class QRLabelTemplateMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "label_type", "printer", "qr_data_format", "is_active", "created_at")
    search_fields = ("code", "name", "label_type", "printer__name", "printer__code")
    list_filter = ("label_type", "qr_data_format", "printer", "is_active")


@admin.register(SerialPortConfigurationMaster)
class SerialPortConfigurationMasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "port_name", "read_format", "is_active", "created_at")
    search_fields = ("code", "name", "port_name")
    list_filter = ("read_format", "is_active")
