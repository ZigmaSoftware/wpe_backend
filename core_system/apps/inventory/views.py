from django.db import models
from django.db.models import Q
from decimal import Decimal
from django.utils.dateparse import parse_date
from rest_framework import filters, generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.store.inventory_monitoring import BaseInventorySummaryAPIView
from apps.store.services import get_warehouse_by_name
from common.drf import StandardResultsSetPagination, success_response

from .models import ProductionInventoryTransaction
from .serializers import ProductionInventoryTransactionSerializer

VALID_STAGES = {choice[0] for choice in ProductionInventoryTransaction.Stage.choices}
ACTIVE_PRODUCTION_INVENTORY_STAGES = [
    ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
    ProductionInventoryTransaction.Stage.BLEND_WIP,
    ProductionInventoryTransaction.Stage.BLEND_STORE,
    ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
    ProductionInventoryTransaction.Stage.GRANULATION_STORE,
    ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
    ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
    ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
]


class ProductionInventoryListAPIView(generics.ListAPIView):
    serializer_class = ProductionInventoryTransactionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "batch_code",
        "production_id",
        "production_type",
        "item_code",
        "item_name",
        "item__item_code",
        "item__item_name",
        "output_capture__recipe_no",
        "output_capture__binlot",
        "output_capture__scancode_id",
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
        if stage != "ALL" and stage not in VALID_STAGES:
            raise ValidationError({"stage": f"Invalid stage. Valid choices: {', '.join(sorted(VALID_STAGES))}"})

        include_history = str(params.get("include_history") or "").strip().lower() in {"1", "true", "yes"}

        queryset = (
            ProductionInventoryTransaction.objects.select_related(
                "item",
                "created_by",
                "production_order",
                "source_batch",
                "source_batch__bom_variant",
                "output_capture",
            ).prefetch_related("source_batch__child_batches")
            .order_by("-created_at", "-id")
        )

        if stage == "ALL":
            queryset = queryset.filter(stage__in=ACTIVE_PRODUCTION_INVENTORY_STAGES)
        else:
            queryset = queryset.filter(stage=stage)

        if include_history:
            queryset = queryset.filter(Q(balance_qty__gt=0) | Q(inward_qty__gt=0))
        else:
            queryset = queryset.filter(balance_qty__gt=0)

        work_center = (params.get("work_center") or "").strip()
        if work_center:
            queryset = queryset.filter(work_center=work_center)

        from_date_raw = (params.get("from_date") or "").strip()
        to_date_raw = (params.get("to_date") or "").strip()
        from_date = parse_date(from_date_raw) if from_date_raw else None
        to_date = parse_date(to_date_raw) if to_date_raw else None

        if from_date_raw and from_date is None:
            raise ValidationError({"from_date": "Invalid from_date. Use YYYY-MM-DD."})
        if to_date_raw and to_date is None:
            raise ValidationError({"to_date": "Invalid to_date. Use YYYY-MM-DD."})
        if from_date and to_date and from_date > to_date:
            raise ValidationError({"to_date": "To date must be on or after from date."})

        if from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)

        return queryset

    def _build_totals(self, queryset):
        totals = queryset.aggregate(
            total_inward=models.Sum("inward_qty"),
            total_outward=models.Sum("outward_qty"),
            total_current=models.Sum("balance_qty"),
        )
        total_inward = Decimal(str(totals.get("total_inward") or 0))
        total_outward = Decimal(str(totals.get("total_outward") or 0))
        total_current = Decimal(str(totals.get("total_current") or 0))

        planned_weight_total = Decimal("0.000")
        production_orders = {}
        for order in queryset.select_related("production_order"):
            production_order = getattr(order, "production_order", None)
            if production_order is None or production_order.pk in production_orders:
                continue
            production_orders[production_order.pk] = production_order

        for production_order in production_orders.values():
            planned_weight = Decimal(str(getattr(production_order, "planned_weight", 0) or 0))
            if planned_weight <= 0:
                planned_weight = Decimal(str(getattr(production_order, "planned_quantity", 0) or 0))
            planned_weight_total += planned_weight

        return {
            "total_inward_weight": f"{total_inward:.3f}",
            "total_current_weight": f"{total_current:.3f}",
            "total_outward_weight": f"{total_outward:.3f}",
            "planned_weight": f"{planned_weight_total:.3f}",
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        totals = self._build_totals(queryset)
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        serializer = self.get_serializer(rows, many=True)

        if page is not None:
            paginated_data = self.paginator.get_paginated_data(serializer.data)
            paginated_data["totals"] = totals
            return success_response(
                message="Production inventory fetched successfully.",
                data=paginated_data,
            )

        return success_response(
            message="Production inventory fetched successfully.",
            data={"count": len(serializer.data), "results": serializer.data, "totals": totals},
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
