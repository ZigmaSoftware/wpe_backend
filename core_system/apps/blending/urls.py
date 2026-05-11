from django.urls import path

from .views import (
    BlendingRequestableAdditiveStockListAPIView,
    BlendingStockListAPIView,
    BlendingStoreRequestDetailAPIView,
    BlendingStoreRequestListCreateAPIView,
    CancelBlendingStoreRequestAPIView,
    RequestBlendingStockAPIView,
)


urlpatterns = [
    path("request-stock/", RequestBlendingStockAPIView.as_view(), name="blending-request-stock"),
    path("request-stock", RequestBlendingStockAPIView.as_view(), name="blending-request-stock-no-slash"),
    path("store-requests/", BlendingStoreRequestListCreateAPIView.as_view(), name="blending-store-request-list"),
    path("store-requests", BlendingStoreRequestListCreateAPIView.as_view(), name="blending-store-request-list-no-slash"),
    path("store-requests/<int:pk>/", BlendingStoreRequestDetailAPIView.as_view(), name="blending-store-request-detail"),
    path("store-requests/<int:pk>", BlendingStoreRequestDetailAPIView.as_view(), name="blending-store-request-detail-no-slash"),
    path("store-requests/<int:pk>/cancel/", CancelBlendingStoreRequestAPIView.as_view(), name="blending-store-request-cancel"),
    path("store-requests/<int:pk>/cancel", CancelBlendingStoreRequestAPIView.as_view(), name="blending-store-request-cancel-no-slash"),
    path("requestable-additive-stock/", BlendingRequestableAdditiveStockListAPIView.as_view(), name="blending-requestable-additive-stock"),
    path("requestable-additive-stock", BlendingRequestableAdditiveStockListAPIView.as_view(), name="blending-requestable-additive-stock-no-slash"),
    path("stock/", BlendingStockListAPIView.as_view(), name="blending-stock-list"),
    path("stock", BlendingStockListAPIView.as_view(), name="blending-stock-list-no-slash"),
]
