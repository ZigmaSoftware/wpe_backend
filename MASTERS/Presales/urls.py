
from rest_framework.routers import DefaultRouter
from .views import PreSalesViewSet
from django.urls import path
from django.urls import include

router = DefaultRouter()
router.register(r'', PreSalesViewSet)

urlpatterns = [
    path('presales/', include(router.urls)),
]