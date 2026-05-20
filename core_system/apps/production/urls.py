from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProductionOrderViewSet,
    MaterialMovementViewSet,
    ProductionTransactionViewSet,
    ProductionSummaryViewSet,
    ProductionMachineListAPIView,
    ProductionMachineDetailAPIView,
    BOMVariantListAPIView,
    BOMVariantDetailAPIView,
    BOMVariantSetPasswordAPIView,
    BOMVariantComponentAPIView,
    BOMVariantVerifyPasswordAPIView,
    BOMVariantRecipeAPIView,
    ProductionBatchListCreateAPIView,
    ProductionBatchStartAPIView,
    ProductionBatchConfirmAPIView,
    BatchWeightEntryUpdateAPIView,
    RegrindEntryListCreateAPIView,
    RegrindHistoryAPIView,
    ProductionDashboardAPIView,
)

router = DefaultRouter()
router.register(r"production", ProductionOrderViewSet, basename="production-order")
router.register(r"material-movements", MaterialMovementViewSet, basename="material-movement")
router.register(r"production-transactions", ProductionTransactionViewSet, basename="production-transaction")
router.register(r"production-summaries", ProductionSummaryViewSet, basename="production-summary")

app_name = "production"

urlpatterns = [
    path("", include(router.urls)),
    # Machines
    path("machines/", ProductionMachineListAPIView.as_view(), name="machines"),
    path("machines", ProductionMachineListAPIView.as_view(), name="machines-ns"),
    path("machines/<int:pk>/", ProductionMachineDetailAPIView.as_view(), name="machine-detail"),
    path("machines/<int:pk>", ProductionMachineDetailAPIView.as_view(), name="machine-detail-ns"),
    # BOM Variants
    path("bom-variants/", BOMVariantListAPIView.as_view(), name="bom-variants"),
    path("bom-variants", BOMVariantListAPIView.as_view(), name="bom-variants-ns"),
    path("bom-variants/<int:pk>/", BOMVariantDetailAPIView.as_view(), name="bom-variant-detail"),
    path("bom-variants/<int:pk>", BOMVariantDetailAPIView.as_view(), name="bom-variant-detail-ns"),
    path("bom-variants/<int:pk>/set-password/", BOMVariantSetPasswordAPIView.as_view(), name="bom-set-password"),
    path("bom-variants/<int:pk>/verify-password/", BOMVariantVerifyPasswordAPIView.as_view(), name="bom-verify-password"),
    path("bom-variants/<int:pk>/recipe/", BOMVariantRecipeAPIView.as_view(), name="bom-recipe"),
    path("bom-variants/<int:pk>/components/", BOMVariantComponentAPIView.as_view(), name="bom-components"),
    path("bom-variants/<int:pk>/components/<int:comp_id>/", BOMVariantComponentAPIView.as_view(), name="bom-component-detail"),
    # Batches
    path("orders/<int:order_pk>/batches/", ProductionBatchListCreateAPIView.as_view(), name="order-batches"),
    path("orders/<int:order_pk>/batches", ProductionBatchListCreateAPIView.as_view(), name="order-batches-ns"),
    path("orders/<int:order_pk>/batches/<int:pk>/start/", ProductionBatchStartAPIView.as_view(), name="batch-start"),
    path("orders/<int:order_pk>/batches/<int:pk>/confirm/", ProductionBatchConfirmAPIView.as_view(), name="batch-confirm"),
    path("orders/<int:order_pk>/batches/<int:batch_pk>/weights/<int:pk>/", BatchWeightEntryUpdateAPIView.as_view(), name="weight-entry-update"),
    path("orders/<int:order_pk>/batches/<int:batch_pk>/regrind/", RegrindEntryListCreateAPIView.as_view(), name="regrind-entries"),
    path("orders/<int:order_pk>/batches/<int:batch_pk>/regrind", RegrindEntryListCreateAPIView.as_view(), name="regrind-entries-ns"),
    # Regrind history
    path("regrind/history/", RegrindHistoryAPIView.as_view(), name="regrind-history"),
    path("regrind/history", RegrindHistoryAPIView.as_view(), name="regrind-history-ns"),
    # Dashboard
    path("dashboard/", ProductionDashboardAPIView.as_view(), name="production-dashboard"),
    path("dashboard", ProductionDashboardAPIView.as_view(), name="production-dashboard-ns"),
]
