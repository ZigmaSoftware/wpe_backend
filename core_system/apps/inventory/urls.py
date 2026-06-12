from django.urls import path

from .views import ProductionInventoryListAPIView, WarehouseInventorySummaryAPIView

app_name = "inventory"

urlpatterns = [
    path("production-inventory/", ProductionInventoryListAPIView.as_view(), name="production-inventory"),
    path("warehouse-inventory/", WarehouseInventorySummaryAPIView.as_view(), name="warehouse-inventory"),
    path("warehouse-inventory", WarehouseInventorySummaryAPIView.as_view(), name="warehouse-inventory-no-slash"),
]
