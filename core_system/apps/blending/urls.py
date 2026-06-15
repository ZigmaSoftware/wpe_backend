from django.urls import path

from .views import (
    BlendingInventoryHistoryAPIView,
    BlendingInventorySummaryAPIView,
    BlendingHeadApprovalListAPIView,
    BlendingRequestableAdditiveStockListAPIView,
    BlendingStockListAPIView,
    BlendingStoreRequestDetailAPIView,
    BlendingStoreRequestListCreateAPIView,
    CancelBlendingStoreRequestAPIView,
    ApproveBlendingHeadRequestAPIView,
    RejectBlendingHeadRequestAPIView,
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
    path("head-approvals/", BlendingHeadApprovalListAPIView.as_view(), name="blending-head-approval-list"),
    path("head-approvals", BlendingHeadApprovalListAPIView.as_view(), name="blending-head-approval-list-no-slash"),
    path("head-approvals/<int:pk>/approve/", ApproveBlendingHeadRequestAPIView.as_view(), name="blending-head-approval-approve"),
    path("head-approvals/<int:pk>/approve", ApproveBlendingHeadRequestAPIView.as_view(), name="blending-head-approval-approve-no-slash"),
    path("head-approvals/<int:pk>/reject/", RejectBlendingHeadRequestAPIView.as_view(), name="blending-head-approval-reject"),
    path("head-approvals/<int:pk>/reject", RejectBlendingHeadRequestAPIView.as_view(), name="blending-head-approval-reject-no-slash"),
    path("requestable-additive-stock/", BlendingRequestableAdditiveStockListAPIView.as_view(), name="blending-requestable-additive-stock"),
    path("requestable-additive-stock", BlendingRequestableAdditiveStockListAPIView.as_view(), name="blending-requestable-additive-stock-no-slash"),
    path("inventory/summary/", BlendingInventorySummaryAPIView.as_view(), name="blending-inventory-summary"),
    path("inventory/summary", BlendingInventorySummaryAPIView.as_view(), name="blending-inventory-summary-no-slash"),
    path("inventory/<int:item_id>/history/", BlendingInventoryHistoryAPIView.as_view(), name="blending-inventory-history"),
    path("inventory/<int:item_id>/history", BlendingInventoryHistoryAPIView.as_view(), name="blending-inventory-history-no-slash"),
    path("stock/", BlendingStockListAPIView.as_view(), name="blending-stock-list"),
    path("stock", BlendingStockListAPIView.as_view(), name="blending-stock-list-no-slash"),
]
