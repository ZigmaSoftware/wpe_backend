from django.urls import path
from .views import GRNImportAPIView, GRNListCreateAPIView, GRNMoveToQCRAPIView, QCRListAPIView, QCRStatusUpdateAPIView

urlpatterns = [
    path("grn/", GRNListCreateAPIView.as_view(), name="grn-list-create"),
    path("grn/moved/", GRNListCreateAPIView.as_view(tab_scope="grn"), name="grn-moved-list"),
    path("grn/import/", GRNImportAPIView.as_view(), name="grn-import"),
    path("grn/<int:pk>/move-to-qcr/", GRNMoveToQCRAPIView.as_view(), name="grn-move-to-qcr"),
    path("qcr/", QCRListAPIView.as_view(), name="qcr-list"),
    path("qcr/grn/", QCRListAPIView.as_view(tab_scope="grn"), name="qcr-grn-list"),
    path("qcr/cancelled/", QCRListAPIView.as_view(tab_scope="cancelled"), name="qcr-cancelled-list"),
    path("qcr/<int:pk>/status/", QCRStatusUpdateAPIView.as_view(), name="qcr-status-update"),
]
