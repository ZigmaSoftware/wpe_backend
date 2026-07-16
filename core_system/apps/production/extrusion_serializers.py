"""Serializers for the Extrusion Production / Packing / Weight Verification /
Sticker Generation / Scrap KPI module.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import PackingMaterialMaster
from .extrusion_models import (
    ExtrusionAuditLog,
    ExtrusionInspection,
    ExtrusionProfileConfig,
    ExtrusionWorkOrder,
    ExtrusionWorkOrderConsumable,
    Packet,
    PacketSticker,
    PacketWeightAttempt,
    ScrapCategory,
    ScrapReason,
    ScrapTransaction,
    StickerScanLog,
)


class ExtrusionProfileConfigSerializer(serializers.ModelSerializer):
    profile_code = serializers.CharField(source="profile.code", read_only=True)
    profile_name = serializers.CharField(source="profile.name", read_only=True)

    class Meta:
        model = ExtrusionProfileConfig
        fields = [
            "id", "profile", "profile_code", "profile_name",
            "section_weight_per_meter", "standard_length_per_piece", "default_pieces_per_packet",
            "default_tare_weight", "tolerance_type", "tolerance_value", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExtrusionWorkOrderConsumableSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = ExtrusionWorkOrderConsumable
        fields = ["id", "item", "item_name", "item_code", "quantity", "uom"]
        read_only_fields = ["id"]


class ExtrusionWorkOrderListSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    profile_code = serializers.CharField(source="profile.code", read_only=True)
    extrusion_line_name = serializers.CharField(source="extrusion_line.name", read_only=True)
    packet_count = serializers.IntegerField(source="packets.count", read_only=True)

    class Meta:
        model = ExtrusionWorkOrder
        fields = [
            "id", "work_order_no", "profile", "profile_name", "profile_code",
            "extrusion_line", "extrusion_line_name", "production_date", "shift",
            "planned_pieces", "planned_meters", "status", "packet_count", "created_at",
        ]
        read_only_fields = ["id", "work_order_no", "created_at"]


class ExtrusionWorkOrderDetailSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    profile_code = serializers.CharField(source="profile.code", read_only=True)
    extrusion_line_name = serializers.CharField(source="extrusion_line.name", read_only=True)
    packing_material_name = serializers.CharField(source="packing_material.name", read_only=True)
    consumables = ExtrusionWorkOrderConsumableSerializer(many=True, read_only=True)

    class Meta:
        model = ExtrusionWorkOrder
        fields = [
            "id", "work_order_no", "profile", "profile_name", "profile_code",
            "extrusion_line", "extrusion_line_name", "production_date", "shift",
            "planned_pieces", "planned_meters", "packing_material", "packing_material_name",
            "expected_tare_weight", "expected_section_weight_per_meter",
            "tolerance_type", "tolerance_value", "status", "released_by", "released_at",
            "notes", "consumables", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "work_order_no", "status", "released_by", "released_at", "created_at", "updated_at"]


class ExtrusionWorkOrderCreateUpdateSerializer(serializers.ModelSerializer):
    consumables = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = ExtrusionWorkOrder
        fields = [
            "id", "work_order_no", "status",
            "profile", "extrusion_line", "production_date", "shift", "planned_pieces", "planned_meters",
            "packing_material", "expected_tare_weight", "expected_section_weight_per_meter",
            "tolerance_type", "tolerance_value", "notes", "consumables",
        ]
        read_only_fields = ["id", "work_order_no", "status"]

    def validate(self, data):
        work_order = self.instance
        if work_order is not None:
            critical_fields = {"profile", "extrusion_line", "packing_material"}
            if work_order.is_locked_for_critical_edits and critical_fields & set(data.keys()):
                raise serializers.ValidationError(
                    "Profile, line and packing material cannot be changed once the work order has "
                    "downstream transactions."
                )
        return data

    def create(self, validated_data):
        consumables = validated_data.pop("consumables", [])
        work_order = ExtrusionWorkOrder.objects.create(
            created_by=self.context["request"].user, **validated_data
        )
        self._sync_consumables(work_order, consumables)
        return work_order

    def update(self, instance, validated_data):
        consumables = validated_data.pop("consumables", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if consumables is not None:
            instance.consumables.all().delete()
            self._sync_consumables(instance, consumables)
        return instance

    @staticmethod
    def _sync_consumables(work_order, consumables):
        for row in consumables:
            ExtrusionWorkOrderConsumable.objects.create(
                work_order=work_order,
                item_id=row.get("item"),
                quantity=row.get("quantity") or 0,
                uom=row.get("uom", ""),
            )


class ExtrusionInspectionSerializer(serializers.ModelSerializer):
    work_order_no = serializers.CharField(source="work_order.work_order_no", read_only=True)
    inspected_by_name = serializers.CharField(source="inspected_by.get_full_name", read_only=True)

    class Meta:
        model = ExtrusionInspection
        fields = [
            "id", "work_order", "work_order_no", "batch_reference", "inspected_pieces",
            "straightness_result", "flatness_result", "section_weight_result", "length_result",
            "visual_result", "dimensional_result", "overall_result", "rejection_decision",
            "rejection_reason", "remarks", "inspected_by", "inspected_by_name", "inspected_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "overall_result", "inspected_by", "created_at", "updated_at"]


class PacketWeightAttemptSerializer(serializers.ModelSerializer):
    weighed_by_name = serializers.CharField(source="weighed_by.get_full_name", read_only=True)

    class Meta:
        model = PacketWeightAttempt
        fields = [
            "id", "attempt_no", "actual_gross_weight", "result", "weight_deviation", "deviation_percentage",
            "source", "device_id", "workstation_id", "bridge_client_id", "is_override", "override_reason",
            "weighed_by", "weighed_by_name", "weighed_at",
        ]
        read_only_fields = fields


class WeightCaptureInputSerializer(serializers.Serializer):
    actual_gross_weight = serializers.DecimalField(max_digits=14, decimal_places=3)
    source = serializers.ChoiceField(choices=PacketWeightAttempt.Source.choices, default=PacketWeightAttempt.Source.SCALE)
    device_id = serializers.CharField(required=False, allow_blank=True, default="")
    workstation_id = serializers.CharField(required=False, allow_blank=True, default="")
    bridge_client_id = serializers.CharField(required=False, allow_blank=True, default="")
    is_override = serializers.BooleanField(required=False, default=False)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class PacketSerializer(serializers.ModelSerializer):
    work_order_no = serializers.CharField(source="work_order.work_order_no", read_only=True)
    profile_name = serializers.CharField(source="work_order.profile.name", read_only=True)
    packing_material_name = serializers.CharField(source="packing_material.name", read_only=True)
    weight_attempts = PacketWeightAttemptSerializer(many=True, read_only=True)
    has_sticker = serializers.SerializerMethodField()

    class Meta:
        model = Packet
        fields = [
            "id", "work_order", "work_order_no", "profile_name", "inspection", "packet_no",
            "pieces", "length_per_piece", "total_meters", "packing_material", "packing_material_name",
            "tare_weight", "section_weight_per_meter", "tolerance_type", "tolerance_value",
            "expected_net_weight", "expected_gross_weight", "tolerance_amount",
            "min_permissible_weight", "max_permissible_weight",
            "actual_gross_weight", "weight_deviation", "deviation_percentage", "status",
            "qc_approved_by", "qc_approved_at", "qc_approval_remarks",
            "warehouse", "warehouse_received_by", "warehouse_received_at",
            "weight_attempts", "has_sticker", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "packet_no", "total_meters", "expected_net_weight", "expected_gross_weight",
            "tolerance_amount", "min_permissible_weight", "max_permissible_weight",
            "actual_gross_weight", "weight_deviation", "deviation_percentage", "status",
            "qc_approved_by", "qc_approved_at", "warehouse_received_by", "warehouse_received_at",
            "created_at", "updated_at",
        ]

    def get_has_sticker(self, instance) -> bool:
        return PacketSticker.objects.filter(packet=instance).exists()


class PacketCreateSerializer(serializers.Serializer):
    work_order = serializers.PrimaryKeyRelatedField(queryset=ExtrusionWorkOrder.objects.all())
    inspection = serializers.PrimaryKeyRelatedField(queryset=ExtrusionInspection.objects.all())
    pieces = serializers.IntegerField(min_value=1)
    length_per_piece = serializers.DecimalField(max_digits=12, decimal_places=3)
    packing_material = serializers.PrimaryKeyRelatedField(queryset=PackingMaterialMaster.objects.all())
    tare_weight = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True, default=None)


class PacketStickerSerializer(serializers.ModelSerializer):
    packet_no = serializers.CharField(source="packet.packet_no", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.get_full_name", read_only=True)
    scanned_by_name = serializers.CharField(source="scanned_by.get_full_name", read_only=True)

    class Meta:
        model = PacketSticker
        fields = [
            "id", "packet", "packet_no", "sticker_no", "qr_payload", "status",
            "reprint_count", "last_reprint_reason", "last_reprint_by", "last_reprint_at",
            "generated_by", "generated_by_name", "generated_at",
            "scanned_by", "scanned_by_name", "scanned_at",
            "cancelled_by", "cancelled_at", "cancellation_reason",
        ]
        read_only_fields = fields


class StickerReprintSerializer(serializers.Serializer):
    reason = serializers.CharField()


class StickerScanInputSerializer(serializers.Serializer):
    sticker_no = serializers.CharField()
    packet = serializers.PrimaryKeyRelatedField(queryset=Packet.objects.all(), required=False, allow_null=True)


class StickerScanLogSerializer(serializers.ModelSerializer):
    scanned_by_name = serializers.CharField(source="scanned_by.get_full_name", read_only=True)

    class Meta:
        model = StickerScanLog
        fields = ["id", "sticker", "packet", "result", "scanned_by", "scanned_by_name", "scanned_at", "remarks"]
        read_only_fields = fields


class ShiftApprovalBulkInputSerializer(serializers.Serializer):
    packet_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to = serializers.DateField(required=False, allow_null=True, default=None)
    shift = serializers.CharField(required=False, allow_blank=True, default="")
    line = serializers.IntegerField(required=False, allow_null=True, default=None)
    work_order = serializers.IntegerField(required=False, allow_null=True, default=None)
    profile = serializers.IntegerField(required=False, allow_null=True, default=None)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class ReasonInputSerializer(serializers.Serializer):
    reason = serializers.CharField()


class WarehouseReceiveInputSerializer(serializers.Serializer):
    warehouse = serializers.IntegerField(required=False, allow_null=True, default=None)


class ScrapCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapCategory
        fields = ["id", "code", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "code", "created_at", "updated_at"]


class ScrapReasonSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ScrapReason
        fields = ["id", "code", "name", "description", "category", "category_name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "code", "created_at", "updated_at"]


class ScrapTransactionSerializer(serializers.ModelSerializer):
    work_order_no = serializers.CharField(source="work_order.work_order_no", read_only=True)
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    scrap_category_name = serializers.CharField(source="scrap_category.name", read_only=True)
    scrap_reason_name = serializers.CharField(source="scrap_reason.name", read_only=True)
    packet_no = serializers.CharField(source="packet.packet_no", read_only=True)

    class Meta:
        model = ScrapTransaction
        fields = [
            "id", "source_stage", "work_order", "work_order_no", "profile", "profile_name",
            "inspection", "packet", "packet_no", "production_date", "shift",
            "scrap_category", "scrap_category_name", "scrap_reason", "scrap_reason_name",
            "actual_scrap_weight", "remarks", "status", "created_by", "approved_by", "approved_at",
            "reversed_by", "reversed_at", "reversal_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "profile", "status", "created_by", "approved_by", "approved_at",
            "reversed_by", "reversed_at", "reversal_reason", "created_at", "updated_at",
        ]


class ScrapTransactionCreateSerializer(serializers.Serializer):
    source_stage = serializers.ChoiceField(choices=ScrapTransaction.SourceStage.choices)
    work_order = serializers.PrimaryKeyRelatedField(queryset=ExtrusionWorkOrder.objects.all())
    inspection = serializers.PrimaryKeyRelatedField(
        queryset=ExtrusionInspection.objects.all(), required=False, allow_null=True, default=None
    )
    packet = serializers.PrimaryKeyRelatedField(
        queryset=Packet.objects.all(), required=False, allow_null=True, default=None
    )
    production_date = serializers.DateField()
    shift = serializers.CharField(required=False, allow_blank=True, default="")
    scrap_category = serializers.PrimaryKeyRelatedField(queryset=ScrapCategory.objects.all())
    scrap_reason = serializers.PrimaryKeyRelatedField(queryset=ScrapReason.objects.all())
    actual_scrap_weight = serializers.DecimalField(max_digits=14, decimal_places=3)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class ExtrusionAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True)

    class Meta:
        model = ExtrusionAuditLog
        fields = [
            "id", "entity_type", "entity_id", "action", "actor", "actor_name", "reason", "remarks",
            "old_value", "new_value", "source", "created_at",
        ]
        read_only_fields = fields
