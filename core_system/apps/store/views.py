from __future__ import annotations

from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from .inventory_monitoring import BaseInventoryHistoryAPIView, BaseInventorySummaryAPIView
from .models import StockRequest, StoreStock, StoreTransaction
from .permissions import IsStoreUser
from .selectors import (
    availability_map_for_requests,
    current_stock_queryset,
    stock_source_map_for_stock_rows,
    stock_dashboard_summary,
    stock_ledger_queryset,
    store_request_queryset,
)
from .serializers import (
    LegacyStockRequestCreateSerializer,
    StockMovementSerializer,
    StockRequestApproveSerializer,
    StockRequestRejectSerializer,
    StockRequestSerializer,
    StoreStockSerializer,
    StoreTransactionSerializer,
)
from .services import (
    add_stock_from_grn,
    apply_inward_stock,
    apply_outward_stock,
    approve_stock_request,
    get_store_warehouse,
    reject_stock_request,
    request_stock,
)


class WrappedListAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    list_message = "Records fetched successfully."

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            self._serializer_rows = list(page)
            serializer = self.get_serializer(page, many=True)
            return success_response(
                message=self.list_message,
                data=self.paginator.get_paginated_data(serializer.data),
            )

        self._serializer_rows = list(queryset)
        serializer = self.get_serializer(self._serializer_rows, many=True)
        return success_response(
            message=self.list_message,
            data={"count": len(serializer.data), "results": serializer.data},
        )


class StoreStockRequestAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LegacyStockRequestCreateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_request = request_stock(
            item=serializer.validated_data["item"],
            quantity=serializer.validated_data["quantity"],
            user=request.user,
            request_type=serializer.validated_data.get("request_type", StockRequest.RequestType.GENERAL),
            department=serializer.validated_data.get("department", "BLENDING"),
            request_date=serializer.validated_data.get("request_date"),
            require_date=serializer.validated_data.get("require_date"),
            require_time=serializer.validated_data.get("require_time"),
            requested_for_name=serializer.validated_data.get("requested_for_name", ""),
            request_reason=serializer.validated_data.get("request_reason", ""),
        )
        return Response(
            {
                "detail": "Stock request submitted to store.",
                "request": StockRequestSerializer(
                    stock_request,
                    context={"availability_map": availability_map_for_requests([stock_request])},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class StoreRequestApprovalListAPIView(WrappedListAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockRequestSerializer
    search_fields = ("request_no", "requested_by__username", "items__item__item_name", "items__item__item_code")
    ordering_fields = ("requested_at", "request_no", "status", "id")
    filterset_map = {
        "status": "status",
        "requested_by": "requested_by_id",
        "requesting_warehouse": "requesting_warehouse_id",
        "issuing_warehouse": "issuing_warehouse_id",
        "request_type": "request_type",
        "department": "department__iexact",
    }
    list_message = "Store request queue fetched successfully."

    def get_queryset(self):
        queryset = store_request_queryset().filter(status=StockRequest.Status.PENDING_STORE_ISSUE)
        request_no = self.request.query_params.get("request_no")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if request_no:
            queryset = queryset.filter(request_no__icontains=request_no)
        if date_from:
            queryset = queryset.filter(requested_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(requested_at__date__lte=date_to)
        return queryset.distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self, "paginator") and getattr(self, "paginator", None) and getattr(self.paginator, "page", None):
            request_rows = list(self.paginator.page.object_list)
        else:
            request_rows = list(self.filter_queryset(self.get_queryset()))
        context["availability_map"] = availability_map_for_requests(request_rows)
        return context


class StoreRequestDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockRequestSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return store_request_queryset().filter(status=StockRequest.Status.PENDING_STORE_ISSUE)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            context={
                **self.get_serializer_context(),
                "availability_map": availability_map_for_requests([instance]),
            },
        )
        return success_response(
            message="Store request fetched successfully.",
            data=serializer.data,
        )


class ApproveStockRequestAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockRequestApproveSerializer

    def post(self, request, pk: int, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval_result = approve_stock_request(
            pk,
            request.user,
            approval_remarks=serializer.validated_data.get("approval_remarks"),
            approval_lines=serializer.validated_data.get("items"),
        )
        stock_request = approval_result["stock_request"]
        availability_map = availability_map_for_requests([stock_request])

        return success_response(
            message="Store request reviewed successfully",
            data={
                "request": StockRequestSerializer(
                    stock_request,
                    context={"availability_map": availability_map},
                ).data,
                "source_stocks": StoreStockSerializer(approval_result["source_stocks"], many=True).data,
                "destination_stocks": StoreStockSerializer(approval_result["destination_stocks"], many=True).data,
                "issue_transactions": StoreTransactionSerializer(
                    approval_result["issue_transactions"],
                    many=True,
                ).data,
                "receipt_transactions": StoreTransactionSerializer(
                    approval_result["receipt_transactions"],
                    many=True,
                ).data,
            },
        )


class RejectStockRequestAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockRequestRejectSerializer

    def post(self, request, pk: int, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_request = reject_stock_request(
            pk,
            request.user,
            approval_remarks=serializer.validated_data.get("approval_remarks"),
        )
        return success_response(
            message="Store request rejected successfully",
            data={
                "request": StockRequestSerializer(
                    stock_request,
                    context={"availability_map": availability_map_for_requests([stock_request])},
                ).data
            },
        )


class StoreStockListAPIView(WrappedListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StoreStockSerializer
    search_fields = (
        "item__item_code",
        "item__item_name",
        "warehouse__code",
        "warehouse__name",
        "item__category",
        "item__group",
        "item__sub_group",
    )
    ordering_fields = (
        "available_qty",
        "reserved_qty",
        "updated_at",
        "warehouse__name",
        "item__item_name",
        "id",
    )
    filterset_map = {
        "warehouse": "warehouse_id",
        "warehouse_id": "warehouse_id",
        "item": "item_id",
        "item_id": "item_id",
    }
    list_message = "Current stock fetched successfully."

    def get_queryset(self):
        queryset = current_stock_queryset()
        warehouse_code = self.request.query_params.get("warehouse_code")
        if warehouse_code:
            queryset = queryset.filter(warehouse__code__iexact=warehouse_code)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        rows = getattr(self, "_serializer_rows", None)
        if rows is not None:
            context["stock_source_map"] = stock_source_map_for_stock_rows(rows)
        return context


class StoreTransactionListAPIView(WrappedListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StoreTransactionSerializer
    search_fields = (
        "transaction_no",
        "reference_id",
        "item__item_code",
        "item__item_name",
        "warehouse__code",
        "warehouse__name",
        "remarks",
    )
    ordering_fields = ("transaction_date", "created_at", "transaction_no", "id")
    filterset_map = {
        "warehouse": "warehouse_id",
        "warehouse_id": "warehouse_id",
        "item": "item_id",
        "item_id": "item_id",
        "transaction_type": "transaction_type",
        "reference_type": "reference_type",
    }
    list_message = "Stock ledger fetched successfully."

    def get_queryset(self):
        queryset = stock_ledger_queryset()
        reference_id = self.request.query_params.get("reference_id")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if reference_id:
            queryset = queryset.filter(reference_id__icontains=reference_id)
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)
        return queryset


class StockDashboardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]

    def get(self, request, *args, **kwargs):
        data = {
            "warehouse_summary": stock_dashboard_summary(),
            "pending_store_requests": StockRequest.objects.filter(status=StockRequest.Status.PENDING_STORE_ISSUE).count(),
            "approved_store_requests": StockRequest.objects.filter(status=StockRequest.Status.APPROVED).count(),
            "stock_ledger_entries": StoreTransaction.objects.count(),
            "warehouses": StoreStock.objects.values("warehouse_id").distinct().count(),
        }
        return success_response(message="Stock dashboard fetched successfully.", data=data)


class StoreInventorySummaryAPIView(BaseInventorySummaryAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    list_message = "Store inventory summary fetched successfully."

    def get_warehouse(self):
        return get_store_warehouse()


class StoreInventoryHistoryAPIView(BaseInventoryHistoryAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    list_message = "Store inventory history fetched successfully."

    def get_warehouse(self):
        return get_store_warehouse()


class StockInwardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockMovementSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_row, stock_transaction = apply_inward_stock(
            item=serializer.validated_data["item"],
            warehouse=serializer.validated_data["warehouse"],
            quantity=serializer.validated_data["quantity"],
            transaction_type=serializer.validated_data["transaction_type"],
            reference_type=serializer.validated_data["reference_type"],
            reference_id=serializer.validated_data.get("reference_id"),
            remarks=serializer.validated_data.get("remarks"),
            created_by=request.user,
            transaction_date=serializer.validated_data.get("transaction_date"),
        )
        return success_response(
            message="Stock inward recorded successfully.",
            data={
                "current_stock": StoreStockSerializer(stock_row).data,
                "transaction": StoreTransactionSerializer(stock_transaction).data,
            },
            status_code=status.HTTP_201_CREATED,
        )


class StockOutwardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]
    serializer_class = StockMovementSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_row, stock_transaction = apply_outward_stock(
            item=serializer.validated_data["item"],
            warehouse=serializer.validated_data["warehouse"],
            quantity=serializer.validated_data["quantity"],
            transaction_type=serializer.validated_data["transaction_type"],
            reference_type=serializer.validated_data["reference_type"],
            reference_id=serializer.validated_data.get("reference_id"),
            remarks=serializer.validated_data.get("remarks"),
            created_by=request.user,
            transaction_date=serializer.validated_data.get("transaction_date"),
        )
        return success_response(
            message="Stock outward recorded successfully.",
            data={
                "current_stock": StoreStockSerializer(stock_row).data,
                "transaction": StoreTransactionSerializer(stock_transaction).data,
            },
            status_code=status.HTTP_201_CREATED,
        )


class GRNStockInwardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsStoreUser]

    def post(self, request, *args, **kwargs):
        result = add_stock_from_grn(request.data, created_by=request.user)
        return success_response(
            message="GRN stock inward processed successfully.",
            data=result,
            status_code=status.HTTP_201_CREATED,
        )
