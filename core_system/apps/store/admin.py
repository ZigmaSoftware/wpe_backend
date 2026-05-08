from django.contrib import admin

from .models import StockRequest, StockRequestItem, StoreStock, StoreTransaction, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "warehouse_type", "is_active", "is_system")
    list_filter = ("warehouse_type", "is_active", "is_system")
    search_fields = ("code", "name")


@admin.register(StoreStock)
class StoreStockAdmin(admin.ModelAdmin):
    list_display = ("item", "warehouse", "available_qty", "reserved_qty", "updated_at")
    list_filter = ("warehouse",)
    search_fields = ("item__item_code", "item__item_name", "warehouse__code", "warehouse__name")


@admin.register(StoreTransaction)
class StoreTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_no",
        "transaction_date",
        "item",
        "warehouse",
        "transaction_type",
        "reference_type",
        "reference_id",
        "inward_qty",
        "outward_qty",
        "balance_qty",
    )
    list_filter = ("transaction_type", "reference_type", "warehouse")
    search_fields = ("transaction_no", "item__item_code", "item__item_name", "reference_id")


class StockRequestItemInline(admin.TabularInline):
    model = StockRequestItem
    extra = 0


@admin.register(StockRequest)
class StockRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_no",
        "status",
        "requesting_warehouse",
        "issuing_warehouse",
        "requested_by",
        "action_by",
        "requested_at",
        "action_at",
        "cancelled_at",
    )
    list_filter = ("status", "requesting_warehouse", "issuing_warehouse")
    search_fields = ("request_no", "requested_by__username", "action_by__username")
    inlines = [StockRequestItemInline]
