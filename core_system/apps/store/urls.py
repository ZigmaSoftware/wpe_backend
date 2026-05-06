from django.urls import path

from .views import (
    ApproveStockRequestAPIView,
    RejectStockRequestAPIView,
    StoreStockListAPIView,
    StoreStockRequestAPIView,
    StoreTransactionListAPIView,
)


urlpatterns = [
    path("request-stock/", StoreStockRequestAPIView.as_view(), name="store-request-stock"),
    path("request-stock", StoreStockRequestAPIView.as_view(), name="store-request-stock-no-slash"),
    path("approve-request/<int:pk>/", ApproveStockRequestAPIView.as_view(), name="store-approve-request"),
    path("approve-request/<int:pk>", ApproveStockRequestAPIView.as_view(), name="store-approve-request-no-slash"),
    path("reject-request/<int:pk>/", RejectStockRequestAPIView.as_view(), name="store-reject-request"),
    path("reject-request/<int:pk>", RejectStockRequestAPIView.as_view(), name="store-reject-request-no-slash"),
    path("stock/", StoreStockListAPIView.as_view(), name="store-stock-list"),
    path("stock", StoreStockListAPIView.as_view(), name="store-stock-list-no-slash"),
    path("transactions/", StoreTransactionListAPIView.as_view(), name="store-transaction-list"),
    path("transactions", StoreTransactionListAPIView.as_view(), name="store-transaction-list-no-slash"),
]

