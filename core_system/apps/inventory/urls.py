from django.urls import path

from .views import ProductionInventoryListAPIView

app_name = "inventory"

urlpatterns = [
    path("production-inventory/", ProductionInventoryListAPIView.as_view(), name="production-inventory"),
]
