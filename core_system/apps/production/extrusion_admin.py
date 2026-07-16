from django.contrib import admin

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


class ExtrusionWorkOrderConsumableInline(admin.TabularInline):
    model = ExtrusionWorkOrderConsumable
    extra = 0


@admin.register(ExtrusionWorkOrder)
class ExtrusionWorkOrderAdmin(admin.ModelAdmin):
    list_display = ["work_order_no", "profile", "extrusion_line", "production_date", "shift", "status"]
    list_filter = ["status", "extrusion_line", "production_date"]
    search_fields = ["work_order_no", "profile__name", "profile__code"]
    readonly_fields = ["work_order_no", "created_at", "updated_at"]
    inlines = [ExtrusionWorkOrderConsumableInline]


@admin.register(ExtrusionProfileConfig)
class ExtrusionProfileConfigAdmin(admin.ModelAdmin):
    list_display = ["profile", "section_weight_per_meter", "tolerance_type", "tolerance_value", "is_active"]
    search_fields = ["profile__name", "profile__code"]


@admin.register(ExtrusionInspection)
class ExtrusionInspectionAdmin(admin.ModelAdmin):
    list_display = ["work_order", "overall_result", "rejection_decision", "inspected_by", "inspected_at"]
    list_filter = ["overall_result", "rejection_decision"]
    search_fields = ["work_order__work_order_no", "batch_reference"]


class PacketWeightAttemptInline(admin.TabularInline):
    model = PacketWeightAttempt
    extra = 0
    readonly_fields = [f.name for f in PacketWeightAttempt._meta.fields]
    can_delete = False


@admin.register(Packet)
class PacketAdmin(admin.ModelAdmin):
    list_display = ["packet_no", "work_order", "status", "expected_gross_weight", "actual_gross_weight"]
    list_filter = ["status"]
    search_fields = ["packet_no", "work_order__work_order_no"]
    readonly_fields = ["packet_no", "created_at", "updated_at"]
    inlines = [PacketWeightAttemptInline]


@admin.register(PacketSticker)
class PacketStickerAdmin(admin.ModelAdmin):
    list_display = ["sticker_no", "packet", "status", "reprint_count", "generated_at", "scanned_at"]
    list_filter = ["status"]
    search_fields = ["sticker_no", "packet__packet_no"]


@admin.register(StickerScanLog)
class StickerScanLogAdmin(admin.ModelAdmin):
    list_display = ["sticker", "packet", "result", "scanned_by", "scanned_at"]
    list_filter = ["result"]


@admin.register(ScrapCategory)
class ScrapCategoryAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]
    search_fields = ["code", "name"]


@admin.register(ScrapReason)
class ScrapReasonAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "category", "is_active"]
    list_filter = ["category"]
    search_fields = ["code", "name"]


@admin.register(ScrapTransaction)
class ScrapTransactionAdmin(admin.ModelAdmin):
    list_display = ["work_order", "source_stage", "scrap_category", "scrap_reason", "actual_scrap_weight", "status"]
    list_filter = ["source_stage", "status", "scrap_category"]
    search_fields = ["work_order__work_order_no", "packet__packet_no"]


@admin.register(ExtrusionAuditLog)
class ExtrusionAuditLogAdmin(admin.ModelAdmin):
    list_display = ["entity_type", "entity_id", "action", "actor", "created_at"]
    list_filter = ["entity_type", "action"]
    search_fields = ["entity_id", "reason"]
    readonly_fields = [f.name for f in ExtrusionAuditLog._meta.fields]
