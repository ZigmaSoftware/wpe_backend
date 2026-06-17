from decimal import Decimal
import re

from rest_framework import serializers
from django.db.models import Sum
from django.db.models import Q

from .models import ProductionInventoryTransaction


class ProductionInventoryTransactionSerializer(serializers.ModelSerializer):
    stage = serializers.CharField()
    item_code = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    uom = serializers.SerializerMethodField()
    inward_qty = serializers.SerializerMethodField()
    outward_qty = serializers.SerializerMethodField()
    balance_qty = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    production = serializers.SerializerMethodField()
    batch_no = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    source_stage = serializers.SerializerMethodField()
    destination_stage = serializers.SerializerMethodField()
    gl_batch_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductionInventoryTransaction
        fields = [
            "id",
            "stage",
            "production_id",
            "production_type",
            "production",
            "batch_no",
            "batch_code",
            "item_code",
            "item_name",
            "inward_qty",
            "outward_qty",
            "balance_qty",
            "uom",
            "source_stage",
            "destination_stage",
            "from_stage",
            "to_stage",
            "reference_no",
            "scan_code",
            "work_center",
            "line",
            "status",
            "gl_batch_count",
            "created_by",
            "created_at",
        ]

    def _fmt(self, value):
        if value is None:
            return "0.000"
        try:
            from decimal import Decimal
            return f"{Decimal(value):.3f}"
        except Exception:
            return str(value)

    def _extract_workflow_suffix(self, value):
        text = str(value or "").strip().upper()
        if not text:
            return ""
        match = re.search(r"(-\d+)$", text)
        if match:
            return match.group(1)
        return text

    def get_item_code(self, obj):
        if obj.item_id:
            return obj.item.item_code
        return obj.item_code or ""

    def get_item_name(self, obj):
        if obj.item_id:
            return obj.item.item_name
        return obj.item_name or ""

    def get_uom(self, obj):
        if obj.item_id:
            return obj.item.unit
        return obj.uom or ""

    def get_inward_qty(self, obj):
        return self._fmt(obj.inward_qty)

    def get_outward_qty(self, obj):
        return self._fmt(obj.outward_qty)

    def get_balance_qty(self, obj):
        return self._fmt(obj.balance_qty)

    def get_created_by(self, obj):
        return getattr(obj.created_by, "username", None) or "System"

    def get_production(self, obj):
        return obj.production_type or ""

    def get_batch_no(self, obj):
        if obj.batch_code:
            return obj.batch_code
        if obj.stage == ProductionInventoryTransaction.Stage.BLEND_WIP:
            source_batch = getattr(obj, "source_batch", None)
            if source_batch is not None:
                return str(getattr(source_batch, "batch_no", "") or "").strip()
        return ""

    def _get_moved_quantity_to_next_stage(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.BLEND_WIP:
            next_stage = ProductionInventoryTransaction.Stage.BLEND_STORE
        elif obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            next_stage = ProductionInventoryTransaction.Stage.GRANULATION_STORE
        else:
            return Decimal("0.000")

        source_batch = getattr(obj, "source_batch", None)
        direct_filter = Q()
        if source_batch is not None:
            direct_filter |= Q(source_batch__parent_batch_id=source_batch.id)

        lineage_suffix = self._extract_workflow_suffix(
            obj.batch_code or obj.reference_no or getattr(source_batch, "batch_no", None)
        )
        suffix_filter = Q()
        if lineage_suffix:
            suffix_filter |= Q(batch_code__iendswith=lineage_suffix)
            suffix_filter |= Q(reference_no__iendswith=lineage_suffix)

        if not direct_filter and not suffix_filter:
            return Decimal("0.000")

        total = ProductionInventoryTransaction.objects.filter(
            stage=next_stage,
            production_order=obj.production_order,
            item_code=obj.item_code,
            created_at__gte=obj.created_at,
        ).filter(
            direct_filter | suffix_filter
        ).aggregate(total=Sum("inward_qty"))
        return Decimal(str(total.get("total") or 0))

    def get_status(self, obj):
        if obj.stage not in {
            ProductionInventoryTransaction.Stage.BLEND_WIP,
            ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
        }:
            return obj.status

        if Decimal(str(obj.balance_qty or 0)) <= 0:
            return ProductionInventoryTransaction.Status.COMPLETED

        moved_qty = self._get_moved_quantity_to_next_stage(obj)
        return (
            ProductionInventoryTransaction.Status.COMPLETED
            if moved_qty > 0
            else obj.status
        )

    def get_source_stage(self, obj):
        return obj.from_stage or ""

    def get_destination_stage(self, obj):
        return obj.to_stage or ""

    def get_gl_batch_count(self, obj):
        production_order = getattr(obj, "production_order", None)
        if production_order is None:
            return 0
        return production_order.batches.filter(stage="GL").exclude(batch_no__exact="").count()
