from rest_framework import filters, generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.store.inventory_monitoring import BaseInventorySummaryAPIView
from apps.store.services import get_warehouse_by_name
from common.drf import StandardResultsSetPagination, success_response

from .models import ProductionInventoryTransaction
from .serializers import ProductionInventoryTransactionSerializer

VALID_STAGES = {choice[0] for choice in ProductionInventoryTransaction.Stage.choices}


class ProductionInventoryListAPIView(generics.ListAPIView):
    serializer_class = ProductionInventoryTransactionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "batch_code",
        "item_code",
        "item_name",
        "item__item_code",
        "item__item_name",
        "reference_no",
        "scan_code",
        "work_center",
        "line",
        "status",
        "created_by__username",
    ]
    ordering_fields = ["created_at", "batch_code", "stage", "status", "id"]

    def get_queryset(self):
        params = self.request.query_params

        stage = (params.get("stage") or "").strip().upper()
        if not stage:
            raise ValidationError({"stage": "The 'stage' query parameter is required."})
        if stage not in VALID_STAGES:
            raise ValidationError({"stage": f"Invalid stage. Valid choices: {', '.join(sorted(VALID_STAGES))}"})

        queryset = (
            ProductionInventoryTransaction.objects.select_related("item", "created_by")
            .filter(stage=stage)
            .order_by("-created_at", "-id")
        )

        work_center = (params.get("work_center") or "").strip()
        if work_center:
            queryset = queryset.filter(work_center=work_center)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        serializer = self.get_serializer(rows, many=True)

        if page is not None:
            return success_response(
                message="Production inventory fetched successfully.",
                data=self.paginator.get_paginated_data(serializer.data),
            )

        return success_response(
            message="Production inventory fetched successfully.",
            data={"count": len(serializer.data), "results": serializer.data},
        )


class WarehouseInventorySummaryAPIView(BaseInventorySummaryAPIView):
    permission_classes = [IsAuthenticated]
    list_message = "Warehouse inventory summary fetched successfully."

    def get_warehouse_name(self) -> str:
        warehouse_name = (self.request.query_params.get("warehouse_name") or "").strip()
        if not warehouse_name:
            raise ValidationError({"warehouse_name": "The 'warehouse_name' query parameter is required."})
        return warehouse_name

    def get_warehouse(self):
        if not hasattr(self, "_warehouse"):
            self._warehouse = get_warehouse_by_name(self.get_warehouse_name())
        return self._warehouse
