from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductionOrderViewSet,
    MaterialMovementViewSet,
    ProductionTransactionViewSet,
    ProductionSummaryViewSet,
)

router = DefaultRouter()
router.register(r'production', ProductionOrderViewSet, basename='production-order')
router.register(r'material-movements', MaterialMovementViewSet, basename='material-movement')
router.register(r'production-transactions', ProductionTransactionViewSet, basename='production-transaction')
router.register(r'production-summaries', ProductionSummaryViewSet, basename='production-summary')

app_name = 'production'

urlpatterns = [
    path('', include(router.urls)),
]
