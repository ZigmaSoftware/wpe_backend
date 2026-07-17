from django.contrib import admin
from .models import (
    BagCreationMaster,
    BinCreationMaster,
    ColorCreationMaster,
    PackingMaterialMaster,
    PackingTypeMaster,
    ProductionBatch,
    ProductionLineMaster,
    ProductionMachine,
    ProductionOrder,
    ProfileCreationMaster,
    ProfileSizeMaster,
    MaterialMovement,
    RegrindMaterialEntry,
    ProductionTransaction,
    ProductionSummary,
    WorkCentreCreationMaster,
    BOMVariant,
)


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = [
        "production_id",
        "status",
        "production_type",
        "batch_number",
        "production_date",
        "total_quantity",
        "total_cost",
        "created_at",
    ]
    list_filter = ["status", "production_type", "production_date", "created_at"]
    search_fields = ["production_id", "batch_number", "plan_id"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {
            "fields": ("production_id", "production_type", "status")
        }),
        ("Batch Information", {
            "fields": ("batch_number", "batch_date")
        }),
        ("Production Details", {
            "fields": ("production_date", "shift", "line_number", "line_name")
        }),
        ("Planning", {
            "fields": ("plan_id", "planned_quantity", "planned_weight")
        }),
        ("Costs", {
            "fields": ("total_quantity", "other_cost", "material_cost", "total_cost")
        }),
        ("Timeline", {
            "fields": ("start_date_time", "end_date_time")
        }),
        ("Audit", {
            "fields": ("created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(MaterialMovement)
class MaterialMovementAdmin(admin.ModelAdmin):
    list_display = [
        "production_order",
        "movement_type",
        "item_name",
        "quantity",
        "source_location",
        "destination_location",
        "status",
        "movement_date",
    ]
    list_filter = ["movement_type", "status", "movement_date"]
    search_fields = ["production_order__production_id", "item_name", "item_code"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Production Order", {
            "fields": ("production_order",)
        }),
        ("Movement Information", {
            "fields": ("movement_type", "movement_date", "status")
        }),
        ("Material Details", {
            "fields": ("item_id", "item_name", "item_code", "quantity", "unit")
        }),
        ("Location", {
            "fields": ("source_location", "destination_location", "warehouse", "bin_number")
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ProductionTransaction)
class ProductionTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "transaction_id",
        "production_order",
        "transaction_type",
        "item_name",
        "quantity_in",
        "quantity_out",
        "transaction_date",
        "warehouse",
    ]
    list_filter = ["transaction_type", "transaction_date", "created_at"]
    search_fields = ["transaction_id", "production_order__production_id", "item_name", "item_code"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Transaction Information", {
            "fields": ("transaction_id", "production_order", "transaction_type", "transaction_date", "transaction_time")
        }),
        ("Item Details", {
            "fields": ("item_id", "item_number", "item_name", "item_code")
        }),
        ("Quantity", {
            "fields": ("quantity_in", "quantity_out", "unit")
        }),
        ("Warehouse", {
            "fields": ("warehouse", "bin_location")
        }),
        ("References", {
            "fields": ("reference_id", "remarks")
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ProductionSummary)
class ProductionSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "production_order",
        "total_production_cost",
        "total_output_quantity",
        "cost_per_unit",
        "is_finalized",
        "updated_at",
    ]
    list_filter = ["is_finalized", "created_at", "updated_at"]
    search_fields = ["production_order__production_id"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Production Order", {
            "fields": ("production_order", "is_finalized")
        }),
        ("Cost Summary", {
            "fields": ("total_raw_material_cost", "total_other_cost", "total_production_cost", "cost_per_unit")
        }),
        ("Quantity Summary", {
            "fields": ("total_input_quantity", "total_output_quantity", "total_waste_quantity")
        }),
        ("Efficiency", {
            "fields": ("yield_percentage",)
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ProductionMachine)
class ProductionMachineAdmin(admin.ModelAdmin):
    list_display = ["machine_code", "name", "machine_type", "department", "status", "is_active", "updated_at"]
    list_filter = ["machine_type", "status", "is_active", "department"]
    search_fields = ["machine_code", "name", "serial_no", "manufacturer"]


class ProductionCodeMasterAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active", "updated_at"]
    list_filter = ["is_active", "created_at", "updated_at"]
    search_fields = ["code", "name", "description"]


@admin.register(ProfileCreationMaster)
class ProfileCreationMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "profile_type", "profile_size", "color", "is_active", "updated_at"]
    list_filter = ["is_active", "profile_type", "color", "packing_type"]


@admin.register(ProfileSizeMaster)
class ProfileSizeMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "width", "thickness", "length", "uom", "is_active"]


@admin.register(ColorCreationMaster)
class ColorCreationMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "color_group", "is_active", "updated_at"]
    list_filter = ["color_group", "is_active"]


@admin.register(WorkCentreCreationMaster)
class WorkCentreCreationMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "department", "capacity", "is_active", "updated_at"]
    list_filter = ["department", "is_active"]


@admin.register(ProductionLineMaster)
class ProductionLineMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "department", "machine", "status", "is_active", "updated_at"]
    list_filter = ["department", "status", "is_active"]


@admin.register(BinCreationMaster)
class BinCreationMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "department", "capacity", "capacity_uom", "current_status", "is_active"]
    list_filter = ["department", "current_status", "is_active"]


@admin.register(BagCreationMaster)
class BagCreationMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "department", "standard_weight", "current_status", "is_active"]
    list_filter = ["department", "current_status", "is_active"]


@admin.register(PackingTypeMaster)
class PackingTypeMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "standard_pcs", "standard_weight", "uom", "is_active"]


@admin.register(PackingMaterialMaster)
class PackingMaterialMasterAdmin(ProductionCodeMasterAdmin):
    list_display = ["code", "name", "item", "uom", "standard_consumption", "is_active"]


@admin.register(BOMVariant)
class BOMVariantAdmin(admin.ModelAdmin):
    list_display = ["variant_code", "name", "revision", "is_active", "updated_at"]
    list_filter = ["is_active", "created_at", "updated_at"]
    search_fields = ["variant_code", "name"]


@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display = ["batch_no", "production_order", "stage", "machine", "status", "started_at", "completed_at"]
    list_filter = ["stage", "status", "machine"]
    search_fields = ["batch_no", "production_order__production_id"]


@admin.register(RegrindMaterialEntry)
class RegrindMaterialEntryAdmin(admin.ModelAdmin):
    list_display = ["production_order", "batch", "stage", "item", "quantity_grams", "is_valid", "added_at"]
    list_filter = ["stage", "is_valid", "added_at"]
