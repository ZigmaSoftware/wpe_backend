from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.http import Http404
from django.utils.dateparse import parse_date
from rest_framework import filters, generics, serializers
from rest_framework.exceptions import ValidationError

from apps.items.models import Item, STOCK_ZERO
from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from .models import StoreStock, StoreTransaction


def serialize_quantity(value: Decimal | None) -> str:
    return f"{(value or STOCK_ZERO):.3f}"


def inventory_stock_queryset(*, warehouse) -> object:
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=warehouse)
        .order_by("item__item_name", "item__item_code", "id")
    )


def inventory_history_queryset(*, warehouse, item_id: int) -> object:
    return (
        StoreTransaction.objects.select_related("item", "warehouse", "created_by")
        .filter(warehouse=warehouse, item_id=item_id)
        .order_by("-transaction_date", "-created_at", "-id")
    )


def inventory_totals_by_item(*, warehouse, item_ids: list[int]) -> dict[int, dict[str, Decimal]]:
    if not item_ids:
        return {}

    totals = (
        StoreTransaction.objects.filter(warehouse=warehouse, item_id__in=item_ids)
        .values("item_id")
        .annotate(total_inward=Sum("inward_qty"), total_outward=Sum("outward_qty"))
    )
    return {
        row["item_id"]: {
            "total_inward": row["total_inward"] or STOCK_ZERO,
            "total_outward": row["total_outward"] or STOCK_ZERO,
        }
        for row in totals
    }


class InventorySummarySerializer(serializers.Serializer):
    item_id = serializers.IntegerField(read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    current_stock = serializers.SerializerMethodField()
    unit = serializers.CharField(source="item.unit", read_only=True)
    last_updated = serializers.DateTimeField(source="updated_at", read_only=True)
    total_inward = serializers.SerializerMethodField()
    total_outward = serializers.SerializerMethodField()

    def _get_totals(self, obj) -> dict[str, Decimal]:
        totals_map = self.context.get("totals_map", {})
        return totals_map.get(obj.item_id, {})

    def get_current_stock(self, obj) -> str:
        return serialize_quantity(obj.available_qty)

    def get_total_inward(self, obj) -> str:
        return serialize_quantity(self._get_totals(obj).get("total_inward"))

    def get_total_outward(self, obj) -> str:
        return serialize_quantity(self._get_totals(obj).get("total_outward"))


class InventoryHistorySerializer(serializers.Serializer):
    datetime = serializers.DateTimeField(source="created_at", read_only=True)
    transaction_type = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    opening_stock = serializers.SerializerMethodField()
    closing_stock = serializers.SerializerMethodField()
    reference_no = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    def get_transaction_type(self, obj) -> str:
        return "INWARD" if obj.inward_qty > STOCK_ZERO else "OUTWARD"

    def get_quantity(self, obj) -> str:
        return serialize_quantity(obj.movement_qty)

    def get_opening_stock(self, obj) -> str:
        opening_stock = (obj.balance_qty or STOCK_ZERO) - (obj.inward_qty or STOCK_ZERO) + (obj.outward_qty or STOCK_ZERO)
        return serialize_quantity(opening_stock)

    def get_closing_stock(self, obj) -> str:
        return serialize_quantity(obj.balance_qty)

    def get_reference_no(self, obj) -> str | None:
        if obj.reference_id:
            return obj.reference_id
        if isinstance(obj.metadata, dict):
            return obj.metadata.get("reference_no") or obj.metadata.get("grn_no")
        return None

    def get_module(self, obj) -> str:
        return str(obj.reference_type or obj.transaction_type)

    def get_created_by(self, obj) -> str:
        return getattr(obj.created_by, "username", None) or "System"


class InventoryWrappedListAPIView(QueryParamFilterMixin, generics.ListAPIView):
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    list_message = "Records fetched successfully."

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        self._current_rows = rows
        serializer = self.get_serializer(rows, many=True)

        if page is not None:
            return success_response(
                message=self.list_message,
                data=self.paginator.get_paginated_data(serializer.data),
            )

        return success_response(
            message=self.list_message,
            data={"count": len(serializer.data), "results": serializer.data},
        )


class BaseInventorySummaryAPIView(InventoryWrappedListAPIView):
    serializer_class = InventorySummarySerializer
    search_fields = ("item__item_code", "item__item_name", "item__external_item_id")
    ordering_fields = ("item__item_name", "item__item_code", "available_qty", "updated_at", "id")
    filterset_map = {
        "item": "item_id",
        "item_id": "item_id",
    }

    def get_warehouse(self):
        raise NotImplementedError

    def get_queryset(self):
        return inventory_stock_queryset(warehouse=self.get_warehouse())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        rows = getattr(self, "_current_rows", [])
        context["totals_map"] = inventory_totals_by_item(
            warehouse=self.get_warehouse(),
            item_ids=[row.item_id for row in rows],
        )
        return context


class BaseInventoryHistoryAPIView(InventoryWrappedListAPIView):
    serializer_class = InventoryHistorySerializer
    search_fields = (
        "transaction_no",
        "reference_id",
        "reference_type",
        "transaction_type",
        "remarks",
        "created_by__username",
    )
    ordering_fields = ("transaction_date", "created_at", "transaction_no", "id")
    list_message = "Inventory history fetched successfully."

    def get_warehouse(self):
        raise NotImplementedError

    def get_item(self) -> Item:
        if not hasattr(self, "_item"):
            item = Item.objects.filter(pk=self.kwargs["item_id"]).only("id").first()
            if item is None:
                raise Http404("Item not found.")
            self._item = item
        return self._item

    def _parse_date_param(self, param_name: str):
        raw_value = (self.request.query_params.get(param_name) or "").strip()
        if not raw_value:
            return None

        parsed_value = parse_date(raw_value)
        if parsed_value is None:
            raise ValidationError({param_name: "Use a valid ISO date."})
        return parsed_value

    def get_queryset(self):
        queryset = inventory_history_queryset(
            warehouse=self.get_warehouse(),
            item_id=self.get_item().id,
        )
        date_from = self._parse_date_param("date_from")
        date_to = self._parse_date_param("date_to")

        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_range": "date_from cannot be after date_to."})
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)
        return queryset
