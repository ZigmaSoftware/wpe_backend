from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PreSalesViewSet,
    PresalesRequestListCreateAPIView,
    PresalesRequestDetailAPIView,
    PresalesRequestSubmitAPIView,
    PresalesRequestApproveAPIView,
    PresalesRequestRejectAPIView,
    PresalesRequestSendToProductionAPIView,
    PresalesRequestAuditLogAPIView,
    PresalesDashboardAPIView,
)

router = DefaultRouter()
router.register(r"legacy", PreSalesViewSet, basename="presales-legacy")

urlpatterns = [
    path("", include(router.urls)),
    path("requests/", PresalesRequestListCreateAPIView.as_view(), name="presales-requests"),
    path("requests", PresalesRequestListCreateAPIView.as_view(), name="presales-requests-ns"),
    path("requests/<int:pk>/", PresalesRequestDetailAPIView.as_view(), name="presales-request-detail"),
    path("requests/<int:pk>", PresalesRequestDetailAPIView.as_view(), name="presales-request-detail-ns"),
    path("requests/<int:pk>/submit/", PresalesRequestSubmitAPIView.as_view(), name="presales-request-submit"),
    path("requests/<int:pk>/approve/", PresalesRequestApproveAPIView.as_view(), name="presales-request-approve"),
    path("requests/<int:pk>/reject/", PresalesRequestRejectAPIView.as_view(), name="presales-request-reject"),
    path("requests/<int:pk>/send-to-production/", PresalesRequestSendToProductionAPIView.as_view(), name="presales-request-send-to-production"),
    path("requests/<int:pk>/audit-log/", PresalesRequestAuditLogAPIView.as_view(), name="presales-request-audit-log"),
    path("dashboard/", PresalesDashboardAPIView.as_view(), name="presales-dashboard"),
    path("dashboard", PresalesDashboardAPIView.as_view(), name="presales-dashboard-ns"),
]
