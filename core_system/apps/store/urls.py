from django.urls import path

from .views import (
    ApproveStockRequestAPIView,
    GRNStockInwardAPIView,
    RejectStockRequestAPIView,
    StockDashboardAPIView,
    StockInwardAPIView,
    StockOutwardAPIView,
    StoreRequestApprovalListAPIView,
    StoreRequestDetailAPIView,
    StoreStockListAPIView,
    StoreTransactionListAPIView,
)


urlpatterns = [
    path("requests/", StoreRequestApprovalListAPIView.as_view(), name="store-request-list"),
    path("requests", StoreRequestApprovalListAPIView.as_view(), name="store-request-list-no-slash"),
    path("requests/<int:pk>/", StoreRequestDetailAPIView.as_view(), name="store-request-detail"),
    path("requests/<int:pk>", StoreRequestDetailAPIView.as_view(), name="store-request-detail-no-slash"),
    path("requests/<int:pk>/approve/", ApproveStockRequestAPIView.as_view(), name="store-request-approve"),
    path("requests/<int:pk>/approve", ApproveStockRequestAPIView.as_view(), name="store-request-approve-no-slash"),
    path("requests/<int:pk>/reject/", RejectStockRequestAPIView.as_view(), name="store-request-reject"),
    path("requests/<int:pk>/reject", RejectStockRequestAPIView.as_view(), name="store-request-reject-no-slash"),
    path("dashboard/", StockDashboardAPIView.as_view(), name="store-dashboard"),
    path("dashboard", StockDashboardAPIView.as_view(), name="store-dashboard-no-slash"),
    path("stock/current/", StoreStockListAPIView.as_view(), name="store-current-stock"),
    path("stock/current", StoreStockListAPIView.as_view(), name="store-current-stock-no-slash"),
    path("stock/ledger/", StoreTransactionListAPIView.as_view(), name="store-stock-ledger"),
    path("stock/ledger", StoreTransactionListAPIView.as_view(), name="store-stock-ledger-no-slash"),
    path("stock/inward/", StockInwardAPIView.as_view(), name="store-stock-inward"),
    path("stock/inward", StockInwardAPIView.as_view(), name="store-stock-inward-no-slash"),
    path("stock/outward/", StockOutwardAPIView.as_view(), name="store-stock-outward"),
    path("stock/outward", StockOutwardAPIView.as_view(), name="store-stock-outward-no-slash"),
    path("stock/grn-inward/", GRNStockInwardAPIView.as_view(), name="store-grn-inward"),
    path("stock/grn-inward", GRNStockInwardAPIView.as_view(), name="store-grn-inward-no-slash"),
]
