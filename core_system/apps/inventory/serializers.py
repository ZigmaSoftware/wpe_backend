from rest_framework import serializers

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
        return obj.batch_code or ""

    def get_source_stage(self, obj):
        return obj.from_stage or ""

    def get_destination_stage(self, obj):
        return obj.to_stage or ""

    def get_gl_batch_count(self, obj):
        production_order = getattr(obj, "production_order", None)
        if production_order is None:
            return 0
        return production_order.batches.filter(stage="GL").exclude(batch_no__exact="").count()
