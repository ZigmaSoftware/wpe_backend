"""Views for the Extrusion Production / Packing / Weight Verification /
Sticker Generation / Scrap KPI module. Thin views delegate to
`extrusion_services`, mirroring the rest of `apps.production`.
"""

from __future__ import annotations

from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from . import extrusion_services as services
from .extrusion_models import (
    ExtrusionInspection,
    ExtrusionProfileConfig,
    ExtrusionWorkOrder,
    Packet,
    PacketSticker,
    ScrapCategory,
    ScrapReason,
    ScrapTransaction,
)
from .extrusion_permissions import (
    IsExtrusionKPIViewer,
    IsExtrusionPackingOperator,
    IsExtrusionProductionUser,
    IsExtrusionQCApprover,
    IsExtrusionQualityInspector,
    IsExtrusionScrapUser,
    IsExtrusionStickerOperator,
    IsExtrusionSupervisor,
    IsExtrusionUser,
    IsExtrusionWarehouseUser,
    IsExtrusionWeighingOperator,
)
from .extrusion_serializers import (
    ExtrusionInspectionSerializer,
    ExtrusionProfileConfigSerializer,
    ExtrusionWorkOrderCreateUpdateSerializer,
    ExtrusionWorkOrderDetailSerializer,
    ExtrusionWorkOrderListSerializer,
    PacketCreateSerializer,
    PacketSerializer,
    PacketStickerSerializer,
    ReasonInputSerializer,
    ScrapCategorySerializer,
    ScrapReasonSerializer,
    ScrapTransactionCreateSerializer,
    ScrapTransactionSerializer,
    ShiftApprovalBulkInputSerializer,
    StickerReprintSerializer,
    StickerScanInputSerializer,
    WarehouseReceiveInputSerializer,
    WeightCaptureInputSerializer,
)
from .views import ProductionCodeMasterViewSet, ProductionMasterPagination


class ExtrusionProfileConfigViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    queryset = ExtrusionProfileConfig.objects.select_related("profile").all()
    serializer_class = ExtrusionProfileConfigSerializer
    permission_classes = [IsAuthenticated, IsExtrusionProductionUser]
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["profile__name", "profile__code"]
    ordering_fields = ["profile__name", "created_at"]
    ordering = ["profile__name"]
    filterset_map = {"profile": "profile_id", "is_active": "is_active"}


class ScrapCategoryViewSet(ProductionCodeMasterViewSet):
    queryset = ScrapCategory.objects.all()
    serializer_class = ScrapCategorySerializer
    next_code_prefix = "SCRC"
    permission_classes = [IsAuthenticated, IsExtrusionSupervisor]


class ScrapReasonViewSet(ProductionCodeMasterViewSet):
    queryset = ScrapReason.objects.select_related("category").all()
    serializer_class = ScrapReasonSerializer
    search_fields = ["name", "code", "description", "category__name"]
    next_code_prefix = "SCRR"
    filterset_map = {"category": "category_id", "is_active": "is_active"}
    permission_classes = [IsAuthenticated, IsExtrusionSupervisor]


class ExtrusionWorkOrderViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    queryset = ExtrusionWorkOrder.objects.select_related("profile", "extrusion_line", "packing_material").all()
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["work_order_no", "profile__name", "profile__code"]
    ordering_fields = ["production_date", "work_order_no", "status", "created_at"]
    ordering = ["-production_date", "-created_at"]
    filterset_map = {
        "status": "status",
        "extrusion_line": "extrusion_line_id",
        "profile": "profile_id",
        "production_date": "production_date",
    }

    def get_serializer_class(self):
        if self.action == "list":
            return ExtrusionWorkOrderListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ExtrusionWorkOrderCreateUpdateSerializer
        return ExtrusionWorkOrderDetailSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "release"):
            return [IsAuthenticated(), IsExtrusionProductionUser()]
        return [IsAuthenticated(), IsExtrusionUser()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != ExtrusionWorkOrder.Status.DRAFT:
            return Response(
                {"detail": "Only draft work orders can be deleted."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete: this work order is referenced by other data."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        work_order = self.get_object()
        services.release_work_order(work_order, user=request.user)
        return success_response(
            message="Work order released.", data=ExtrusionWorkOrderDetailSerializer(work_order).data
        )


class ExtrusionInspectionViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    queryset = ExtrusionInspection.objects.select_related("work_order", "inspected_by").all()
    serializer_class = ExtrusionInspectionSerializer
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["work_order__work_order_no", "batch_reference"]
    ordering_fields = ["inspected_at", "created_at"]
    ordering = ["-inspected_at"]
    filterset_map = {"work_order": "work_order_id", "overall_result": "overall_result"}

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsExtrusionQualityInspector()]
        return [IsAuthenticated(), IsExtrusionUser()]

    def perform_create(self, serializer):
        instance = serializer.save()
        services.create_or_update_inspection(instance, user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        services.create_or_update_inspection(instance, user=self.request.user)


class PacketViewSet(QueryParamFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Packet.objects.select_related(
        "work_order", "work_order__profile", "packing_material", "inspection"
    ).prefetch_related("weight_attempts").all()
    serializer_class = PacketSerializer
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["packet_no", "work_order__work_order_no"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]
    filterset_map = {
        "work_order": "work_order_id",
        "status": "status",
        "inspection": "inspection_id",
    }

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsExtrusionPackingOperator()]
        if self.action == "weigh":
            return [IsAuthenticated(), IsExtrusionWeighingOperator()]
        if self.action == "generate_sticker":
            return [IsAuthenticated(), IsExtrusionStickerOperator()]
        if self.action == "reverse_qc_approval":
            return [IsAuthenticated(), IsExtrusionSupervisor()]
        if self.action == "receive_warehouse":
            return [IsAuthenticated(), IsExtrusionWarehouseUser()]
        return [IsAuthenticated(), IsExtrusionUser()]

    def create(self, request, *args, **kwargs):
        input_serializer = PacketCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        packet = services.create_packet(
            work_order=data["work_order"],
            inspection=data["inspection"],
            pieces=data["pieces"],
            length_per_piece=data["length_per_piece"],
            packing_material=data["packing_material"],
            tare_weight=data.get("tare_weight"),
            user=request.user,
        )
        return Response(PacketSerializer(packet).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def weigh(self, request, pk=None):
        packet = self.get_object()
        input_serializer = WeightCaptureInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        if data["is_override"] and not IsExtrusionSupervisor().has_permission(request, self):
            raise DRFValidationError("Manual weight override requires supervisor authorization.")
        attempt = services.record_weight_attempt(
            packet=packet,
            actual_gross_weight=data["actual_gross_weight"],
            user=request.user,
            source=data["source"],
            device_id=data["device_id"],
            workstation_id=data["workstation_id"],
            bridge_client_id=data["bridge_client_id"],
            is_override=data["is_override"],
            override_reason=data["override_reason"],
        )
        packet.refresh_from_db()
        return success_response(
            message=f"Weight recorded — {attempt.result}.", data=PacketSerializer(packet).data
        )

    @action(detail=True, methods=["post"], url_path="generate-sticker")
    def generate_sticker(self, request, pk=None):
        packet = self.get_object()
        sticker = services.generate_sticker(packet, user=request.user)
        return success_response(message="Sticker generated.", data=PacketStickerSerializer(sticker).data)

    @action(detail=True, methods=["post"], url_path="reverse-qc-approval")
    def reverse_qc_approval(self, request, pk=None):
        packet = self.get_object()
        input_serializer = ReasonInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        services.reverse_qc_approval(packet, user=request.user, reason=input_serializer.validated_data["reason"])
        packet.refresh_from_db()
        return success_response(message="QC approval reversed.", data=PacketSerializer(packet).data)

    @action(detail=True, methods=["post"], url_path="receive-warehouse")
    def receive_warehouse(self, request, pk=None):
        packet = self.get_object()
        input_serializer = WarehouseReceiveInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        services.receive_at_warehouse(
            packet, user=request.user, warehouse_id=input_serializer.validated_data.get("warehouse")
        )
        packet.refresh_from_db()
        return success_response(message="Packet received into warehouse.", data=PacketSerializer(packet).data)


class ShiftEndApprovalAPIView(APIView):
    permission_classes = [IsAuthenticated, IsExtrusionQCApprover]

    def get(self, request):
        queryset = services.eligible_packets_for_approval(
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
            shift=request.query_params.get("shift"),
            line=request.query_params.get("line"),
            work_order=request.query_params.get("work_order"),
            profile=request.query_params.get("profile"),
        ).select_related("work_order", "work_order__profile")
        return Response(PacketSerializer(queryset, many=True).data)

    def post(self, request):
        input_serializer = ShiftApprovalBulkInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        if data["packet_ids"]:
            packets = Packet.objects.filter(pk__in=data["packet_ids"])
        else:
            packets = services.eligible_packets_for_approval(
                date_from=data["date_from"], date_to=data["date_to"], shift=data["shift"] or None,
                line=data["line"], work_order=data["work_order"], profile=data["profile"],
            )
        approved = services.approve_packets(packets, user=request.user, remarks=data["remarks"])
        return success_response(
            message=f"{len(approved)} packet(s) approved.",
            data=PacketSerializer(approved, many=True).data,
        )


class StickerViewSet(QueryParamFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PacketSticker.objects.select_related("packet", "packet__work_order").all()
    serializer_class = PacketStickerSerializer
    pagination_class = ProductionMasterPagination
    permission_classes = [IsAuthenticated, IsExtrusionUser]
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["sticker_no", "packet__packet_no"]
    filterset_map = {"packet": "packet_id", "status": "status"}

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsExtrusionStickerOperator])
    def reprint(self, request, pk=None):
        sticker = self.get_object()
        input_serializer = StickerReprintSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        services.reprint_sticker(sticker, user=request.user, reason=input_serializer.validated_data["reason"])
        sticker.refresh_from_db()
        return success_response(message="Sticker reprinted.", data=PacketStickerSerializer(sticker).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsExtrusionStickerOperator])
    def scan(self, request):
        input_serializer = StickerScanInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        try:
            sticker = PacketSticker.objects.select_related("packet").get(sticker_no=data["sticker_no"])
        except PacketSticker.DoesNotExist:
            raise DRFValidationError("Sticker not found.")
        services.scan_sticker(sticker, packet=data.get("packet"), user=request.user)
        sticker.refresh_from_db()
        return success_response(message="Sticker scanned.", data=PacketStickerSerializer(sticker).data)


class ScrapTransactionViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    queryset = ScrapTransaction.objects.select_related(
        "work_order", "profile", "scrap_category", "scrap_reason", "packet", "inspection"
    ).all()
    serializer_class = ScrapTransactionSerializer
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ["work_order__work_order_no", "packet__packet_no", "remarks"]
    ordering_fields = ["created_at", "production_date"]
    ordering = ["-created_at"]
    filterset_map = {
        "work_order": "work_order_id",
        "packet": "packet_id",
        "source_stage": "source_stage",
        "status": "status",
        "scrap_category": "scrap_category_id",
        "scrap_reason": "scrap_reason_id",
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "approve", "reverse"):
            if self.action in ("approve", "reverse"):
                return [IsAuthenticated(), IsExtrusionSupervisor()]
            return [IsAuthenticated(), IsExtrusionScrapUser()]
        return [IsAuthenticated(), IsExtrusionUser()]

    def create(self, request, *args, **kwargs):
        input_serializer = ScrapTransactionCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        scrap = services.create_scrap_transaction(
            source_stage=data["source_stage"],
            work_order=data["work_order"],
            inspection=data.get("inspection"),
            packet=data.get("packet"),
            scrap_category=data["scrap_category"],
            scrap_reason=data["scrap_reason"],
            actual_scrap_weight=data["actual_scrap_weight"],
            remarks=data["remarks"],
            production_date=data["production_date"],
            shift=data["shift"],
            user=request.user,
        )
        return Response(ScrapTransactionSerializer(scrap).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        scrap = self.get_object()
        services.approve_scrap_transaction(scrap, user=request.user)
        scrap.refresh_from_db()
        return success_response(message="Scrap transaction approved.", data=ScrapTransactionSerializer(scrap).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        scrap = self.get_object()
        input_serializer = ReasonInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        services.reverse_scrap_transaction(scrap, user=request.user, reason=input_serializer.validated_data["reason"])
        scrap.refresh_from_db()
        return success_response(message="Scrap transaction reversed.", data=ScrapTransactionSerializer(scrap).data)


class ExtrusionKPIDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsExtrusionKPIViewer]

    def get(self, request):
        params = request.query_params
        filters = {
            "date_from": params.get("date_from") or None,
            "date_to": params.get("date_to") or None,
            "work_order": params.get("work_order") or None,
            "profile": params.get("profile") or None,
            "shift": params.get("shift") or None,
            "line": params.get("line") or None,
            "scrap_stage": params.get("scrap_stage") or None,
            "scrap_category": params.get("scrap_category") or None,
            "scrap_reason": params.get("scrap_reason") or None,
            "cost_per_kg": params.get("cost_per_kg") or None,
        }
        data = services.compute_scrap_kpis(filters)
        return Response(data)
