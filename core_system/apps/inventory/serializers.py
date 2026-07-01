from decimal import Decimal
import re

from rest_framework import serializers
from django.db.models import Sum
from django.db.models import Q

from .models import ProductionInventoryTransaction


class ProductionInventoryTransactionSerializer(serializers.ModelSerializer):
    stage = serializers.CharField()
    production_order_id = serializers.IntegerField(read_only=True)
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
    status_display = serializers.SerializerMethodField()
    source_stage = serializers.SerializerMethodField()
    destination_stage = serializers.SerializerMethodField()
    gl_batch_count = serializers.SerializerMethodField()
    planned_weight = serializers.SerializerMethodField()
    stage_label = serializers.SerializerMethodField()
    recipe_no = serializers.SerializerMethodField()
    std_batch_size = serializers.SerializerMethodField()
    captured_weight = serializers.SerializerMethodField()
    binlot = serializers.SerializerMethodField()
    baglot = serializers.SerializerMethodField()
    scancode = serializers.SerializerMethodField()
    connected_weight = serializers.SerializerMethodField()
    connected_at = serializers.SerializerMethodField()
    consumed_weight = serializers.SerializerMethodField()
    consumed_at = serializers.SerializerMethodField()
    consumed_bin_name = serializers.SerializerMethodField()
    consumed_scancode = serializers.SerializerMethodField()
    captured_stage_at = serializers.SerializerMethodField()
    captured_bin_name = serializers.SerializerMethodField()
    captured_bin_scancode = serializers.SerializerMethodField()
    captured_stage_weight = serializers.SerializerMethodField()
    scrap = serializers.SerializerMethodField()

    class Meta:
        model = ProductionInventoryTransaction
        fields = [
            "id",
            "stage",
            "stage_label",
            "production_id",
            "production_order_id",
            "production_type",
            "production",
            "batch_no",
            "batch_code",
            "planned_weight",
            "recipe_no",
            "std_batch_size",
            "item_code",
            "item_name",
            "inward_qty",
            "outward_qty",
            "balance_qty",
            "captured_weight",
            "uom",
            "binlot",
            "baglot",
            "scancode",
            "connected_weight",
            "connected_at",
            "consumed_weight",
            "consumed_at",
            "consumed_bin_name",
            "consumed_scancode",
            "captured_stage_at",
            "captured_bin_name",
            "captured_bin_scancode",
            "captured_stage_weight",
            "scrap",
            "source_stage",
            "destination_stage",
            "from_stage",
            "to_stage",
            "reference_no",
            "scan_code",
            "work_center",
            "line",
            "status",
            "status_display",
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
        if obj.stage in {
            ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.BLEND_WIP,
        }:
            return obj.item_code or ""

        finished_goods = self._get_finished_goods(obj)
        if finished_goods:
            return finished_goods.get("item_code") or finished_goods.get("code") or obj.item_code or ""
        return obj.item_code or ""

    def get_item_name(self, obj):
        if obj.item_id:
            return obj.item.item_name
        if obj.stage in {
            ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.BLEND_WIP,
        }:
            return obj.item_name or ""

        finished_goods = self._get_finished_goods(obj)
        if finished_goods:
            return finished_goods.get("item_name") or finished_goods.get("name") or obj.item_name or ""
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

    def get_stage_label(self, obj):
        return ProductionInventoryTransaction.Stage(obj.stage).label if obj.stage else ""

    def get_batch_no(self, obj):
        source_batch = getattr(obj, "source_batch", None)
        if source_batch is not None:
            current_batch_no = str(getattr(source_batch, "batch_no", "") or "").strip()
            if current_batch_no:
                return current_batch_no

            workflow_batch_no = str(getattr(source_batch, "workflow_batch_no", "") or "").strip()
            if workflow_batch_no:
                return workflow_batch_no

        if obj.batch_code:
            return obj.batch_code
        return ""

    def get_planned_weight(self, obj):
        production_order = getattr(obj, "production_order", None)
        if production_order is None:
            return "0.000"
        planned_weight = getattr(production_order, "planned_weight", None)
        if planned_weight and Decimal(str(planned_weight)) > 0:
            return self._fmt(planned_weight)
        planned_quantity = getattr(production_order, "planned_quantity", None)
        if planned_quantity:
            return self._fmt(planned_quantity)
        return "0.000"

    def get_recipe_no(self, obj):
        output_capture = getattr(obj, "output_capture", None)
        if output_capture is not None and str(output_capture.recipe_no or "").strip():
            return str(output_capture.recipe_no or "").strip()

        source_batch = getattr(obj, "source_batch", None)
        bom_variant = getattr(source_batch, "bom_variant", None) if source_batch is not None else None
        if bom_variant is not None:
            return str(getattr(bom_variant, "variant_code", "") or "").strip()
        return ""

    def _get_std_batch_size_value(self, obj):
        output_capture = getattr(obj, "output_capture", None)
        if output_capture is not None and Decimal(str(output_capture.quantity_kg or 0)) > 0:
            return Decimal(str(output_capture.quantity_kg))

        source_batch = getattr(obj, "source_batch", None)
        if source_batch is None:
            return Decimal("0.000")

        prefetched_entries = getattr(source_batch, "_prefetched_objects_cache", {}).get("weight_entries")
        if prefetched_entries is not None:
            total = sum((Decimal(str(getattr(entry, "target_weight_grams", 0) or 0)) for entry in prefetched_entries), Decimal("0.000"))
            return total

        total = source_batch.weight_entries.aggregate(total=Sum("target_weight_grams")).get("total")
        return Decimal(str(total or 0))

    def get_std_batch_size(self, obj):
        return self._fmt(self._get_std_batch_size_value(obj))

    def get_captured_weight(self, obj):
        return self._fmt(obj.inward_qty)

    def _get_capture_lot(self, obj):
        output_capture = getattr(obj, "output_capture", None)
        if output_capture is not None and str(output_capture.binlot or "").strip():
            return str(output_capture.binlot or "").strip()
        return ""

    def get_binlot(self, obj):
        if obj.stage in {
            ProductionInventoryTransaction.Stage.BLEND_STORE,
            ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
        }:
            return self._get_capture_lot(obj)
        return ""

    def get_baglot(self, obj):
        if obj.stage in {
            ProductionInventoryTransaction.Stage.GRANULATION_STORE,
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        }:
            return self._get_capture_lot(obj)
        return ""

    def get_scancode(self, obj):
        output_capture = getattr(obj, "output_capture", None)
        if output_capture is not None and str(output_capture.scancode_id or "").strip():
            return str(output_capture.scancode_id or "").strip()
        return str(obj.scan_code or "").strip()

    def _find_next_stage_row(self, obj, next_stage):
        source_batch = getattr(obj, "source_batch", None)
        queryset = ProductionInventoryTransaction.objects.filter(
            stage=next_stage,
            production_order=obj.production_order,
            created_at__gte=obj.created_at,
        ).order_by("created_at", "id")

        if source_batch is not None:
            child_batch_ids = list(getattr(source_batch, "child_batches", []).values_list("id", flat=True)) if hasattr(getattr(source_batch, "child_batches", None), "values_list") else []
            if child_batch_ids:
                matched = queryset.filter(source_batch_id__in=child_batch_ids).first()
                if matched is not None:
                    return matched

        matched = queryset.filter(item_code=obj.item_code).first()
        if matched is not None:
            return matched
        return queryset.first()

    def _status_from_connection(self, obj):
        balance = Decimal(str(obj.balance_qty or 0))
        outward = Decimal(str(obj.outward_qty or 0))
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_STORE:
            return "Connected" if outward > 0 or obj.to_stage == ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE else "Disconnected"
        if obj.stage in {
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
        }:
            return "Connected" if balance > 0 else "Disconnected"
        if obj.stage == ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE:
            return "Disconnected"
        return obj.status

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

    def get_status_display(self, obj):
        if obj.stage in {
            ProductionInventoryTransaction.Stage.GRANULATION_STORE,
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        }:
            return self._status_from_connection(obj)
        return self.get_status(obj)

    def get_connected_weight(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_STORE:
            return self._fmt(obj.outward_qty)
        if obj.stage in {
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        }:
            return self._fmt(obj.inward_qty)
        return "0.000"

    def get_connected_at(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_STORE:
            next_row = self._find_next_stage_row(obj, ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE)
            return next_row.created_at.isoformat() if next_row is not None and next_row.created_at else None
        if obj.stage in {
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        }:
            return obj.created_at.isoformat() if obj.created_at else None
        return None

    def get_consumed_weight(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            return self._fmt(obj.inward_qty)
        if obj.stage in {
            ProductionInventoryTransaction.Stage.GRANULATION_STORE,
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        }:
            return self._fmt(obj.outward_qty)
        return "0.000"

    def get_consumed_at(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            return obj.created_at.isoformat() if obj.created_at else None
        if obj.stage in {
            ProductionInventoryTransaction.Stage.GRANULATION_STORE,
            ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
            ProductionInventoryTransaction.Stage.DISCONNECTION_FROM_LINE,
        } and Decimal(str(obj.outward_qty or 0)) > 0:
            return obj.updated_at.isoformat() if obj.updated_at else None
        return None

    def get_consumed_bin_name(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            return self.get_binlot(obj)
        return ""

    def get_consumed_scancode(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            return self.get_scancode(obj)
        return ""

    def get_captured_stage_at(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            next_row = self._find_next_stage_row(obj, ProductionInventoryTransaction.Stage.GRANULATION_STORE)
            return next_row.created_at.isoformat() if next_row is not None and next_row.created_at else None
        return None

    def get_captured_bin_name(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            next_row = self._find_next_stage_row(obj, ProductionInventoryTransaction.Stage.GRANULATION_STORE)
            return self.get_baglot(next_row) if next_row is not None else ""
        return ""

    def get_captured_bin_scancode(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            next_row = self._find_next_stage_row(obj, ProductionInventoryTransaction.Stage.GRANULATION_STORE)
            return self.get_scancode(next_row) if next_row is not None else ""
        return ""

    def get_captured_stage_weight(self, obj):
        if obj.stage == ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER:
            next_row = self._find_next_stage_row(obj, ProductionInventoryTransaction.Stage.GRANULATION_STORE)
            return self._fmt(next_row.inward_qty if next_row is not None else 0)
        return "0.000"

    def get_scrap(self, obj):
        return "0.000"

    def get_source_stage(self, obj):
        return obj.from_stage or ""

    def get_destination_stage(self, obj):
        return obj.to_stage or ""

    def get_gl_batch_count(self, obj):
        production_order = getattr(obj, "production_order", None)
        if production_order is None:
            return 0
        return production_order.batches.filter(stage="GL").exclude(batch_no__exact="").count()

    def _get_finished_goods(self, obj):
        production_order = getattr(obj, "production_order", None)
        if production_order is None:
            return None
        extra = getattr(production_order, "extra_form_data", {}) or {}
        finished_goods = extra.get("finished_goods")
        return finished_goods if isinstance(finished_goods, dict) else None
