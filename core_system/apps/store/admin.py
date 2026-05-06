from django.contrib import admin

from .models import StockRequest, StoreStock, StoreTransaction


@admin.register(StoreStock)
class StoreStockAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "updated_at")
    search_fields = ("item__item_code", "item__item_name")


@admin.register(StoreTransaction)
class StoreTransactionAdmin(admin.ModelAdmin):
    list_display = ("item", "transaction_type", "quantity", "reference_id", "created_at")
    list_filter = ("transaction_type",)
    search_fields = ("item__item_code", "item__item_name", "reference_id")


@admin.register(StockRequest)
class StockRequestAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "status", "requested_by", "approved_by", "requested_at", "approved_at")
    list_filter = ("status",)
    search_fields = ("item__item_code", "item__item_name", "requested_by__username", "approved_by__username")

