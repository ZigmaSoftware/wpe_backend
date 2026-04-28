from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GRNCreateAPIView,
    GRNImportAPIView,
    GRNMoveToQCRAPIView,
    GRNViewSet,
    QCRListAPIView,
    QCRStatusUpdateAPIView,
)

router = DefaultRouter()
router.register(r"view", GRNViewSet, basename="grn-view")

urlpatterns = [
    path("grn", include(router.urls)),
    path("grn/", GRNCreateAPIView.as_view(), name="grn-create"),
    path("grn/moved/", GRNCreateAPIView.as_view(tab_scope="grn"), name="grn-moved-list"),
    path("grn/import/", GRNImportAPIView.as_view(), name="grn-import"),
    path("grn/<int:pk>/move-to-qcr/", GRNMoveToQCRAPIView.as_view(), name="grn-move-to-qcr"),
    path("qcr/", QCRListAPIView.as_view(), name="qcr-list"),
    path("qcr/grn/", QCRListAPIView.as_view(tab_scope="grn"), name="qcr-grn-list"),
    path("qcr/cancelled/", QCRListAPIView.as_view(tab_scope="cancelled"), name="qcr-cancelled-list"),
    path("qcr/<int:pk>/status/", QCRStatusUpdateAPIView.as_view(), name="qcr-status-update"),
]
