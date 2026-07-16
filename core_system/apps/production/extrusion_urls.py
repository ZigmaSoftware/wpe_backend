from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .extrusion_views import (
    ExtrusionInspectionViewSet,
    ExtrusionKPIDashboardAPIView,
    ExtrusionProfileConfigViewSet,
    ExtrusionWorkOrderViewSet,
    PacketViewSet,
    ScrapCategoryViewSet,
    ScrapReasonViewSet,
    ScrapTransactionViewSet,
    ShiftEndApprovalAPIView,
    StickerViewSet,
)

router = DefaultRouter()
router.register(r"profile-configs", ExtrusionProfileConfigViewSet, basename="extrusion-profile-config")
router.register(r"scrap-categories", ScrapCategoryViewSet, basename="extrusion-scrap-category")
router.register(r"scrap-reasons", ScrapReasonViewSet, basename="extrusion-scrap-reason")
router.register(r"work-orders", ExtrusionWorkOrderViewSet, basename="extrusion-work-order")
router.register(r"inspections", ExtrusionInspectionViewSet, basename="extrusion-inspection")
router.register(r"packets", PacketViewSet, basename="extrusion-packet")
router.register(r"stickers", StickerViewSet, basename="extrusion-sticker")
router.register(r"scrap-transactions", ScrapTransactionViewSet, basename="extrusion-scrap-transaction")

app_name = "extrusion"

urlpatterns = [
    path("", include(router.urls)),
    path("shift-approval/", ShiftEndApprovalAPIView.as_view(), name="shift-approval"),
    path("shift-approval", ShiftEndApprovalAPIView.as_view(), name="shift-approval-ns"),
    path("kpi-dashboard/", ExtrusionKPIDashboardAPIView.as_view(), name="kpi-dashboard"),
    path("kpi-dashboard", ExtrusionKPIDashboardAPIView.as_view(), name="kpi-dashboard-ns"),
]
