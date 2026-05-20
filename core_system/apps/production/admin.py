from django.contrib import admin
from .models import (
    ProductionOrder,
    MaterialMovement,
    ProductionTransaction,
    ProductionSummary,
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
