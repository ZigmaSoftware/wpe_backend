from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GRNCreateAPIView, GRNViewSet

router = DefaultRouter()
router.register(r"view", GRNViewSet, basename="grn-view")

urlpatterns = [
    path("grn", include(router.urls)),
    path('grn/', GRNCreateAPIView.as_view(), name='grn-create'),
]
