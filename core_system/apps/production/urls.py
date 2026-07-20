from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    BagCreationMasterViewSet,
    BinCreationMasterViewSet,
    BOMCreationMasterViewSet,
    BOMItemCreationMasterViewSet,
    ProductionOrderViewSet,
    MaterialMovementViewSet,
    ProductionTransactionViewSet,
    ProductionSummaryViewSet,
    ColorCreationMasterViewSet,
    PackingMaterialMasterViewSet,
    PackingTypeMasterViewSet,
    ProductionLineMasterViewSet,
    ProductionMachineListAPIView,
    ProductionMachineDetailAPIView,
    ProductionMachineMasterViewSet,
    ProductionLineConnectionConnectAPIView,
    ProductionLineConnectionDisconnectAPIView,
    ProductionLineConnectionListAPIView,
    ProductionLineConnectionScanAPIView,
    ProfileCreationMasterViewSet,
    ProfileSizeMasterViewSet,
    RecipeMasterViewSet,
    WorkCentreCreationMasterViewSet,
    BOMVariantListAPIView,
    BOMVariantDetailAPIView,
    BOMVariantSetPasswordAPIView,
    BOMVariantComponentAPIView,
    BOMVariantVerifyPasswordAPIView,
    BOMVariantRecipeAPIView,
    ProductionBatchListCreateAPIView,
    ProductionBatchDestroyAPIView,
    ProductionStageRecordListAPIView,
    ProductionBatchStartAPIView,
    ProductionBatchConfirmAPIView,
    ProductionOutputCaptureListAPIView,
    ProductionScrapCaptureListAPIView,
    BatchWeightEntryUpdateAPIView,
    RegrindEntryListCreateAPIView,
    RegrindHistoryAPIView,
    ProductionDashboardAPIView,
)

router = DefaultRouter()
router.register(r"production", ProductionOrderViewSet, basename="production-order")
router.register(r"profile-creations", ProfileCreationMasterViewSet, basename="production-profile-creation")
router.register(r"profile-sizes", ProfileSizeMasterViewSet, basename="production-profile-size")
router.register(r"color-creations", ColorCreationMasterViewSet, basename="production-color-creation")
router.register(r"machine-creations", ProductionMachineMasterViewSet, basename="production-machine-creation")
router.register(r"work-centre-creations", WorkCentreCreationMasterViewSet, basename="production-work-centre")
router.register(r"production-lines", ProductionLineMasterViewSet, basename="production-line")
router.register(r"bin-creations", BinCreationMasterViewSet, basename="production-bin")
router.register(r"bag-creations", BagCreationMasterViewSet, basename="production-bag")
router.register(r"packing-types", PackingTypeMasterViewSet, basename="production-packing-type")
router.register(r"packing-materials", PackingMaterialMasterViewSet, basename="production-packing-material")
router.register(r"recipes", RecipeMasterViewSet, basename="production-recipe")
router.register(r"bom-creations", BOMCreationMasterViewSet, basename="production-bom-creation")
router.register(r"bom-item-creations", BOMItemCreationMasterViewSet, basename="production-bom-item-creation")

legacy_router = SimpleRouter()
legacy_router.register(r"material-movements", MaterialMovementViewSet, basename="material-movement")
legacy_router.register(r"production-transactions", ProductionTransactionViewSet, basename="production-transaction")
legacy_router.register(r"production-summaries", ProductionSummaryViewSet, basename="production-summary")

app_name = "production"

urlpatterns = [
    path("", include(router.urls)),
    path("line-connections/", ProductionLineConnectionListAPIView.as_view(), name="line-connections"),
    path("line-connections", ProductionLineConnectionListAPIView.as_view(), name="line-connections-ns"),
    path("line-connections/scan/", ProductionLineConnectionScanAPIView.as_view(), name="line-connections-scan"),
    path("line-connections/scan", ProductionLineConnectionScanAPIView.as_view(), name="line-connections-scan-ns"),
    path("line-connections/lookup/", ProductionLineConnectionScanAPIView.as_view(), name="line-connections-lookup"),
    path("line-connections/lookup", ProductionLineConnectionScanAPIView.as_view(), name="line-connections-lookup-ns"),
    path("line-connections/connect/", ProductionLineConnectionConnectAPIView.as_view(), name="line-connections-connect"),
    path("line-connections/connect", ProductionLineConnectionConnectAPIView.as_view(), name="line-connections-connect-ns"),
    path(
        "line-connections/<int:pk>/disconnect/",
        ProductionLineConnectionDisconnectAPIView.as_view(),
        name="line-connections-disconnect",
    ),
    path(
        "line-connections/<int:pk>/disconnect",
        ProductionLineConnectionDisconnectAPIView.as_view(),
        name="line-connections-disconnect-ns",
    ),
    # Machines
    path("machines/", ProductionMachineListAPIView.as_view(), name="machines"),
    path("machines", ProductionMachineListAPIView.as_view(), name="machines-ns"),
    path("machines/<int:pk>/", ProductionMachineDetailAPIView.as_view(), name="machine-detail"),
    path("machines/<int:pk>", ProductionMachineDetailAPIView.as_view(), name="machine-detail-ns"),
    # Recipe compatibility aliases
    path("bom-variants/", BOMVariantListAPIView.as_view(), name="bom-variants"),
    path("bom-variants", BOMVariantListAPIView.as_view(), name="bom-variants-ns"),
    path("bom-variants/<int:pk>/", BOMVariantDetailAPIView.as_view(), name="bom-variant-detail"),
    path("bom-variants/<int:pk>", BOMVariantDetailAPIView.as_view(), name="bom-variant-detail-ns"),
    path("bom-variants/<int:pk>/set-password/", BOMVariantSetPasswordAPIView.as_view(), name="bom-set-password"),
    path("bom-variants/<int:pk>/verify-password/", BOMVariantVerifyPasswordAPIView.as_view(), name="bom-verify-password"),
    path("bom-variants/<int:pk>/recipe/", BOMVariantRecipeAPIView.as_view(), name="bom-recipe"),
    path("bom-variants/<int:pk>/components/", BOMVariantComponentAPIView.as_view(), name="bom-components"),
    path("bom-variants/<int:pk>/components/<int:comp_id>/", BOMVariantComponentAPIView.as_view(), name="bom-component-detail"),
    path("stage-records/", ProductionStageRecordListAPIView.as_view(), name="stage-records"),
    path("stage-records", ProductionStageRecordListAPIView.as_view(), name="stage-records-ns"),
    # Batches
    path("orders/<int:order_pk>/batches/", ProductionBatchListCreateAPIView.as_view(), name="order-batches"),
    path("orders/<int:order_pk>/batches", ProductionBatchListCreateAPIView.as_view(), name="order-batches-ns"),
    path("orders/<int:order_pk>/batches/<int:pk>/", ProductionBatchDestroyAPIView.as_view(), name="batch-delete"),
    path("orders/<int:order_pk>/batches/<int:pk>", ProductionBatchDestroyAPIView.as_view(), name="batch-delete-ns"),
    path("orders/<int:order_pk>/batches/<int:pk>/start/", ProductionBatchStartAPIView.as_view(), name="batch-start"),
    path("orders/<int:order_pk>/batches/<int:pk>/confirm/", ProductionBatchConfirmAPIView.as_view(), name="batch-confirm"),
    path("orders/<int:order_pk>/output-captures/", ProductionOutputCaptureListAPIView.as_view(), name="output-captures"),
    path("orders/<int:order_pk>/output-captures", ProductionOutputCaptureListAPIView.as_view(), name="output-captures-ns"),
    path("orders/<int:order_pk>/scrap-captures/", ProductionScrapCaptureListAPIView.as_view(), name="scrap-captures"),
    path("orders/<int:order_pk>/scrap-captures", ProductionScrapCaptureListAPIView.as_view(), name="scrap-captures-ns"),
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

# Standalone legacy production APIs remain available behind a feature flag while
# older clients are being retired. The per-order compatibility actions exposed
# by ProductionOrderViewSet are gated inside the view module.
legacy_urlpatterns = [
    path("", include(legacy_router.urls)),
]

if settings.ENABLE_LEGACY_PRODUCTION_API:
    urlpatterns += legacy_urlpatterns
