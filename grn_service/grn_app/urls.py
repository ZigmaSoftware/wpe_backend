from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GRNAuditLogAPIView,
    GRNCreateAPIView,
    GRNDetailAPIView,
    GRNImportAPIView,
    GRNMoveToQCRAPIView,
    GRNPendingToQCRAPIView,
    GRNReceiverCreateAPIView,
    GRNViewSet,
    QCRListAPIView,
    QCRStatusUpdateAPIView,
    WarehouseInventoryListAPIView,
)

router = DefaultRouter()
router.register(r"grnview", GRNViewSet, basename="grn-view")

urlpatterns = [
    path("grn/grncreate/", GRNReceiverCreateAPIView.as_view(), name="grn-receiver-create"),
    path("grn/", GRNCreateAPIView.as_view(), name="grn-create"),
    path("grn/<int:pk>/", GRNDetailAPIView.as_view(), name="grn-detail"),
    path("grnview/", include(router.urls)),
    path("grn/moved/", GRNCreateAPIView.as_view(tab_scope="grn"), name="grn-moved-list"),
    path("grn/pending/", GRNCreateAPIView.as_view(tab_scope="pending"), name="grn-pending-list"),
    path("grn/import/", GRNImportAPIView.as_view(), name="grn-import"),
    path("grn/<int:pk>/move-to-qcr/", GRNMoveToQCRAPIView.as_view(), name="grn-move-to-qcr"),
    path("grn/<int:pk>/move-pending-to-qcr/", GRNPendingToQCRAPIView.as_view(), name="grn-pending-to-qcr"),
    path("qcr/", QCRListAPIView.as_view(), name="qcr-list"),
    path("qcr/grn/", QCRListAPIView.as_view(tab_scope="grn"), name="qcr-grn-list"),
    path("qcr/cancelled/", QCRListAPIView.as_view(tab_scope="cancelled"), name="qcr-cancelled-list"),
    path("qcr/<int:pk>/status/", QCRStatusUpdateAPIView.as_view(), name="qcr-status-update"),
    path("warehouse-inventory/", WarehouseInventoryListAPIView.as_view(), name="warehouse-inventory-list"),
    path("grn/<int:pk>/audit-log/", GRNAuditLogAPIView.as_view(), name="grn-audit-log"),
]
