from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GRNCreateAPIView, GRNViewSet

router = DefaultRouter()
router.register(r"grnview", GRNViewSet, basename="grn-view")

urlpatterns = [
    path("grn/", include(router.urls)),
    path("grn/grncreate/", GRNCreateAPIView.as_view(), name="grn-create"),
]
