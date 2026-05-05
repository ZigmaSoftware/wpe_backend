from django.urls import path

from .views import BlendingStockListAPIView, RequestBlendingStockAPIView


urlpatterns = [
    path("request-stock/", RequestBlendingStockAPIView.as_view(), name="blending-request-stock"),
    path("request-stock", RequestBlendingStockAPIView.as_view(), name="blending-request-stock-no-slash"),
    path("stock/", BlendingStockListAPIView.as_view(), name="blending-stock-list"),
    path("stock", BlendingStockListAPIView.as_view(), name="blending-stock-list-no-slash"),
]
