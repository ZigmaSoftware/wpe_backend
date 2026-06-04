import re
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    ProductionOrder,
    MaterialMovement,
    ProductionTransaction,
    ProductionSummary,
)
from .serializers import (
    ProductionOrderListSerializer,
    ProductionOrderDetailSerializer,
    ProductionOrderCreateUpdateSerializer,
    MaterialMovementSerializer,
    ProductionTransactionSerializer,
    ProductionSummarySerializer,
)


class ProductionOrderViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Production Orders.

    Endpoints:
    - GET /api/production/ - List all production orders
    - POST /api/production/ - Create new production order
    - GET /api/production/{id}/ - Get production order details
    - PATCH /api/production/{id}/ - Update production order
    - DELETE /api/production/{id}/ - Delete production order
    - GET /api/production/{id}/material-movements/ - Get material movements
    - GET /api/production/{id}/transactions/ - Get production transactions
    - GET /api/production/{id}/summary/ - Get production summary
    """

    queryset = ProductionOrder.objects.select_related('summary').prefetch_related(
        'material_movements',
        'material_plans',
        'transactions'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'production_type', 'batch_number', 'production_date']
    search_fields = ['production_id', 'production_for', 'batch_number', 'plan_id', 'line_name']
    ordering_fields = ['production_date', 'created_at', 'total_cost']
    ordering = ['-production_date', '-created_at']

    def get_serializer_class(self):
        """Choose serializer based on action"""
        if self.action == 'retrieve':
            return ProductionOrderDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductionOrderCreateUpdateSerializer
        return ProductionOrderListSerializer

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        """Return the next available production order ID (e.g. 005, 006)."""
        ids = ProductionOrder.objects.values_list("production_id", flat=True)
        numeric_pattern = re.compile(r"^(\d+)$")
        highest = 0
        for pid in ids:
            match = numeric_pattern.match(str(pid or "").strip())
            if match:
                highest = max(highest, int(match.group(1)))
        return Response({"code": f"{highest + 1:03d}"})

    @action(detail=True, methods=['get'])
    def material_movements(self, request, pk=None):
        """Get all material movements for a production order"""
        production_order = self.get_object()
        movements = production_order.material_movements.all()
        serializer = MaterialMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get all transactions for a production order"""
        production_order = self.get_object()
        transactions = production_order.transactions.all()
        serializer = ProductionTransactionSerializer(transactions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get summary for a production order"""
        production_order = self.get_object()
        try:
            summary = production_order.summary
            serializer = ProductionSummarySerializer(summary)
            return Response(serializer.data)
        except ProductionSummary.DoesNotExist:
            return Response(
                {"detail": "Summary not found for this production order."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a production order (change status to CLOSED)"""
        production_order = self.get_object()
        production_order.status = 'CLOSED'
        production_order.save()
        serializer = self.get_serializer(production_order)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def cost_breakdown(self, request, pk=None):
        """Get cost breakdown for a production order"""
        production_order = self.get_object()

        return Response({
            "production_id": production_order.production_id,
            "total_quantity": str(production_order.total_quantity),
            "material_cost": str(production_order.material_cost),
            "other_cost": str(production_order.other_cost),
            "total_cost": str(production_order.total_cost),
            "cost_per_unit": str(production_order.cost_per_unit),
        })


class MaterialMovementViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Material Movements.

    Endpoints:
    - GET /api/material-movements/ - List all material movements
    - POST /api/material-movements/ - Create new material movement
    - GET /api/material-movements/{id}/ - Get material movement details
    - PATCH /api/material-movements/{id}/ - Update material movement
    """

    queryset = MaterialMovement.objects.select_related('production_order')
    serializer_class = MaterialMovementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['movement_type', 'status', 'production_order']
    search_fields = ['item_name', 'item_code', 'warehouse']
    ordering_fields = ['movement_date', 'created_at']
    ordering = ['-movement_date']


class ProductionTransactionViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Production Transactions.

    Endpoints:
    - GET /api/production-transactions/ - List all transactions
    - POST /api/production-transactions/ - Create new transaction
    - GET /api/production-transactions/{id}/ - Get transaction details
    - PATCH /api/production-transactions/{id}/ - Update transaction
    """

    queryset = ProductionTransaction.objects.select_related('production_order')
    serializer_class = ProductionTransactionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['transaction_type', 'transaction_date', 'production_order']
    search_fields = ['transaction_id', 'item_name', 'item_code', 'warehouse']
    ordering_fields = ['transaction_date', 'created_at']
    ordering = ['-transaction_date', '-created_at']


class ProductionSummaryViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Production Summaries.

    Endpoints:
    - GET /api/production-summaries/ - List all summaries
    - GET /api/production-summaries/{id}/ - Get summary details
    - PATCH /api/production-summaries/{id}/ - Update summary
    """

    queryset = ProductionSummary.objects.select_related('production_order')
    serializer_class = ProductionSummarySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_finalized', 'production_order']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        """Finalize a production summary (lock it from edits)"""
        summary = self.get_object()
        summary.finalize()
        serializer = self.get_serializer(summary)
        return Response(serializer.data)


# ===== RECIPE / BOM AND PRODUCTION MASTER VIEWS =====

import re
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework import status as drf_status
from rest_framework.permissions import IsAuthenticated

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from .models import (
    BagCreationMaster,
    BinCreationMaster,
    BOMCreationMaster,
    BOMItemCreationMaster,
    BOMVariant,
    BOMVariantComponent,
    BatchWeightEntry,
    ColorCreationMaster,
    PackingMaterialMaster,
    PackingTypeMaster,
    ProductionBatch,
    ProductionOutputCapture,
    ProductionLineMaster,
    ProductionMachine,
    ProfileCreationMaster,
    ProfileSizeMaster,
    RegrindMaterialEntry,
    WorkCentreCreationMaster,
    WEIGHT_MIN_GRAMS, WEIGHT_MAX_GRAMS,
    build_alpha_running_code,
    build_prefixed_running_number,
    resolve_workflow_batch_no,
)
from .serializers import (
    BagCreationMasterSerializer,
    BinCreationMasterSerializer,
    BOMCreationMasterSerializer,
    BOMItemCreationMasterSerializer,
    ProductionMachineSerializer,
    BOMVariantComponentSerializer,
    BOMVariantListSerializer,
    BOMVariantDetailSerializer,
    RecipeMasterSerializer,
    RecipeMasterDetailSerializer,
    ProductionBatchSerializer,
    ProductionOutputCaptureSerializer,
    BatchWeightEntrySerializer,
    ColorCreationMasterSerializer,
    PackingMaterialMasterSerializer,
    PackingTypeMasterSerializer,
    ProductionLineMasterSerializer,
    ProfileCreationMasterSerializer,
    ProfileSizeMasterSerializer,
    ProductionStageRecordSerializer,
    RegrindMaterialEntrySerializer,
    WorkCentreCreationMasterSerializer,
)


def _next_code_response(model_cls, *, field_name: str, prefix: str, width: int = 3, alpha: bool = False):
    with transaction.atomic():
        if alpha:
            code = build_alpha_running_code(model_cls, field_name=field_name, prefix=prefix)
        else:
            code = build_prefixed_running_number(model_cls, field_name=field_name, prefix=prefix, width=width)
    return Response({"code": code})


class ProductionMasterPagination(StandardResultsSetPagination):
    page_size = 25
    max_page_size = 500


class ProductionBaseMasterViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = ProductionMasterPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "is_active"]
    ordering = ["name"]
    filterset_map = {
        "is_active": "is_active",
    }
    lookup_code_attr: str | None = None

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.get_queryset().filter(is_active=True).order_by("name")
        rows: list[dict[str, object]] = []
        for instance in queryset:
            row: dict[str, object] = {
                "id": instance.pk,
                "name": getattr(instance, "name", str(instance)),
            }
            if self.lookup_code_attr:
                code_value = getattr(instance, self.lookup_code_attr, None)
                if code_value:
                    row["code"] = code_value
            rows.append(row)
        return Response(rows)

    @action(detail=True, methods=["patch"], url_path="toggle")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        instance.is_active = not instance.is_active
        instance.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
            return Response(status=drf_status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete: this record is referenced by other data."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )


class ProductionCodeMasterViewSet(ProductionBaseMasterViewSet):
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at", "is_active"]
    next_code_prefix: str | None = None
    next_code_width = 3
    lookup_code_attr = "code"

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        if not self.next_code_prefix:
            return Response({"detail": "Next code preview is not configured for this resource."}, status=drf_status.HTTP_404_NOT_FOUND)
        return _next_code_response(
            self.get_queryset().model,
            field_name="code",
            prefix=self.next_code_prefix,
            width=self.next_code_width,
        )


class ProfileCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = ProfileCreationMaster.objects.select_related(
        "profile_type",
        "profile_size",
        "color",
        "packing_type",
    ).all()
    serializer_class = ProfileCreationMasterSerializer
    search_fields = ["name", "code", "profile_type__name", "profile_size__name", "color__name", "packing_type__name"]
    ordering_fields = ["name", "code", "profile_type__name", "created_at", "is_active"]
    filterset_map = {
        "profile_type": "profile_type_id",
        "profile_size": "profile_size_id",
        "color": "color_id",
        "packing_type": "packing_type_id",
        "is_active": "is_active",
    }
    next_code_prefix = "PRD"


class ProfileSizeMasterViewSet(ProductionCodeMasterViewSet):
    queryset = ProfileSizeMaster.objects.all()
    serializer_class = ProfileSizeMasterSerializer
    search_fields = ["name", "code", "description", "uom"]
    next_code_prefix = "SIZE"


class ColorCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = ColorCreationMaster.objects.all()
    serializer_class = ColorCreationMasterSerializer
    search_fields = ["name", "code", "color_group"]
    next_code_prefix = "COLR"


class ProductionMachineMasterViewSet(ProductionBaseMasterViewSet):
    queryset = ProductionMachine.objects.select_related("department").all()
    serializer_class = ProductionMachineSerializer
    search_fields = ["name", "machine_code", "machine_type", "serial_no", "manufacturer", "department__name"]
    ordering_fields = ["machine_code", "name", "machine_type", "status", "created_at", "is_active"]
    ordering = ["machine_code"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "machine_type": "machine_type",
        "status": "status",
        "is_active": "is_active",
    }
    lookup_code_attr = "machine_code"

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(
            self.get_queryset().model,
            field_name="machine_code",
            prefix="MCH",
            width=3,
        )


class WorkCentreCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = WorkCentreCreationMaster.objects.select_related("department").all()
    serializer_class = WorkCentreCreationMasterSerializer
    search_fields = ["name", "code", "description", "department__name"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "is_active": "is_active",
    }
    next_code_prefix = "WC"


class ProductionLineMasterViewSet(ProductionCodeMasterViewSet):
    queryset = ProductionLineMaster.objects.select_related("department", "machine").all()
    serializer_class = ProductionLineMasterSerializer
    search_fields = ["name", "code", "department__name", "machine__name", "machine__machine_code", "status"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "machine": "machine_id",
        "machine_id": "machine_id",
        "status": "status",
        "is_active": "is_active",
    }
    next_code_prefix = "LINE"
    next_code_width = 2


class BinCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = BinCreationMaster.objects.select_related("department").all()
    serializer_class = BinCreationMasterSerializer
    search_fields = ["name", "code", "department__name", "current_material"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "current_status": "current_status",
        "is_active": "is_active",
    }
    next_code_prefix = "BIN"

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(
            self.get_queryset().model,
            field_name="code",
            prefix="BIN",
            alpha=True,
        )


class BagCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = BagCreationMaster.objects.select_related("department").all()
    serializer_class = BagCreationMasterSerializer
    search_fields = ["name", "code", "department__name", "current_status"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "current_status": "current_status",
        "is_active": "is_active",
    }
    next_code_prefix = "BAG"


class PackingTypeMasterViewSet(ProductionCodeMasterViewSet):
    queryset = PackingTypeMaster.objects.all()
    serializer_class = PackingTypeMasterSerializer
    search_fields = ["name", "code", "description", "uom"]
    next_code_prefix = "PACK"


class PackingMaterialMasterViewSet(ProductionCodeMasterViewSet):
    queryset = PackingMaterialMaster.objects.select_related("item").all()
    serializer_class = PackingMaterialMasterSerializer
    search_fields = ["name", "code", "item__item_name", "item__item_code"]
    filterset_map = {
        "item": "item_id",
        "item_id": "item_id",
        "is_active": "is_active",
    }
    next_code_prefix = "PM"


def bom_component_queryset():
    return BOMVariantComponent.objects.select_related(
        "item",
        "product_subtype__category",
    ).order_by("sequence", "id")


def bom_variant_queryset():
    return BOMVariant.objects.select_related("product_item", "approved_by").prefetch_related(
        Prefetch("components", queryset=bom_component_queryset())
    )


def resolve_bom_component_source(component_data):
    from apps.items.models import Item
    from apps.wpe_masters.models import ProductTypeSubtype

    item_id = component_data.get("item")
    product_subtype_id = component_data.get("product_subtype")

    if item_id and product_subtype_id:
        return None, None, "Provide either item or product_subtype, not both."
    if not item_id and not product_subtype_id:
        return None, None, "item or product_subtype is required."

    item = get_object_or_404(Item, pk=item_id) if item_id else None
    product_subtype = (
        get_object_or_404(ProductTypeSubtype.objects.select_related("category"), pk=product_subtype_id)
        if product_subtype_id
        else None
    )
    return item, product_subtype, None


def validate_bom_component_payload(component_data, fallback_sequence):
    item, product_subtype, error = resolve_bom_component_source(component_data)
    if error:
        return None, error

    target_weight_grams = component_data.get("target_weight_grams")
    if target_weight_grams in (None, ""):
        return None, "target_weight_grams is required."

    unit = str(component_data.get("unit", "g")).strip() or "g"
    payload = {
        "item": item,
        "product_subtype": product_subtype,
        "target_weight_grams": target_weight_grams,
        "min_weight_grams": component_data.get("min_weight_grams", 195),
        "max_weight_grams": component_data.get("max_weight_grams", 9205),
        "sequence": component_data.get("sequence", fallback_sequence),
        "is_regrind": component_data.get("is_regrind", False),
        "unit": unit,
        "is_active": component_data.get("is_active", True),
    }

    try:
        target_weight = Decimal(str(payload["target_weight_grams"]))
        min_weight = Decimal(str(payload["min_weight_grams"]))
        max_weight = Decimal(str(payload["max_weight_grams"]))
    except Exception:
        return None, "Weight values must be numeric."

    if target_weight <= Decimal("0"):
        return None, "target_weight_grams must be greater than zero."
    if min_weight < Decimal("0"):
        return None, "min_weight_grams must be zero or greater."
    if max_weight < Decimal("0"):
        return None, "max_weight_grams must be zero or greater."
    if min_weight > target_weight:
        return None, "min_weight_grams cannot exceed target_weight_grams."
    if max_weight < target_weight:
        return None, "max_weight_grams cannot be less than target_weight_grams."
    if min_weight > max_weight:
        return None, "min_weight_grams cannot exceed max_weight_grams."

    return payload, None


class RecipeMasterViewSet(ProductionBaseMasterViewSet):
    queryset = bom_variant_queryset().annotate(component_count=Count("components", distinct=True))
    serializer_class = RecipeMasterSerializer
    search_fields = ["variant_code", "name", "revision", "status", "batch_uom"]
    ordering_fields = ["variant_code", "name", "revision", "status", "created_at", "updated_at"]
    ordering = ["variant_code"]
    filterset_map = {
        "status": "status",
        "approved_by": "approved_by_id",
        "approved_by_id": "approved_by_id",
        "is_active": "is_active",
    }
    lookup_code_attr = "variant_code"

    def get_serializer_class(self):
        if self.action in {"retrieve", "items"}:
            return RecipeMasterDetailSerializer
        return RecipeMasterSerializer

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(
            self.get_queryset().model,
            field_name="variant_code",
            prefix="REC",
            width=3,
        )

    @action(detail=False, methods=["get"], url_path="approver-options")
    def approver_options(self, request):
        from apps.admin_master.models import UserCreation

        queryset = (
            UserCreation.objects.select_related("user", "staff")
            .filter(is_active=True, user__isnull=False)
            .order_by("staff__name", "user__username", "id")
        )
        rows = []
        for user_creation in queryset:
            display_name = (
                getattr(user_creation.staff, "name", "")
                or getattr(user_creation.user, "get_full_name", lambda: "")()
                or getattr(user_creation.user, "username", "")
            )
            rows.append(
                {
                    "id": user_creation.user_id,
                    "name": display_name,
                    "code": getattr(user_creation.staff, "staff_code", None),
                }
            )
        return Response(rows)

    @action(detail=True, methods=["get", "put"], url_path="items")
    def items(self, request, pk=None):
        recipe = get_object_or_404(bom_variant_queryset(), pk=pk)

        if request.method.lower() == "get":
            return Response(RecipeMasterDetailSerializer(recipe).data)

        components = request.data.get("components", [])
        if not isinstance(components, list):
            return Response({"detail": "components must be a list."}, status=drf_status.HTTP_400_BAD_REQUEST)

        seen_keys = set()
        new_components = []
        for index, comp_data in enumerate(components, start=1):
            payload, error = validate_bom_component_payload(comp_data, index)
            if error:
                return Response({"detail": f"Component {index}: {error}"}, status=drf_status.HTTP_400_BAD_REQUEST)

            duplicate_key = (
                ("product_subtype", payload["product_subtype"].pk)
                if payload["product_subtype"] is not None
                else ("item", payload["item"].pk)
            )
            if duplicate_key in seen_keys:
                return Response(
                    {"detail": f"Component {index}: duplicate component selection is not allowed."},
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )
            seen_keys.add(duplicate_key)
            new_components.append(BOMVariantComponent(bom_variant=recipe, **payload))

        with transaction.atomic():
            recipe.components.all().delete()
            if new_components:
                BOMVariantComponent.objects.bulk_create(new_components)

        refreshed = bom_variant_queryset().annotate(component_count=Count("components", distinct=True)).get(pk=recipe.pk)
        return Response(RecipeMasterDetailSerializer(refreshed).data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        recipe = self.get_object()
        recipe.is_active = False
        recipe.status = BOMVariant.RecipeStatus.INACTIVE
        recipe.save(update_fields=["is_active", "status", "updated_at"])
        return Response(status=drf_status.HTTP_204_NO_CONTENT)


class BOMCreationMasterViewSet(ProductionCodeMasterViewSet):
    queryset = BOMCreationMaster.objects.select_related("product").all()
    serializer_class = BOMCreationMasterSerializer
    search_fields = ["name", "code", "product__name", "product__code", "bom_version", "status"]
    ordering_fields = ["code", "name", "product__name", "created_at", "is_active"]
    ordering = ["code"]
    filterset_map = {
        "product": "product_id",
        "product_id": "product_id",
        "status": "status",
        "is_active": "is_active",
    }
    next_code_prefix = "BOM"


class BOMItemCreationMasterViewSet(ProductionBaseMasterViewSet):
    queryset = BOMItemCreationMaster.objects.select_related("bom", "item").all()
    serializer_class = BOMItemCreationMasterSerializer
    search_fields = ["bom__code", "bom__name", "item__item_code", "item__item_name", "item_type", "uom"]
    ordering_fields = ["bom__code", "item__item_code", "created_at", "is_active"]
    ordering = ["bom__code", "item__item_code"]
    filterset_map = {
        "bom": "bom_id",
        "bom_id": "bom_id",
        "item": "item_id",
        "item_id": "item_id",
        "item_type": "item_type",
        "is_active": "is_active",
    }


class ProductionMachineListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionMachineSerializer

    def get_queryset(self):
        qs = ProductionMachine.objects.all()
        show_all = self.request.query_params.get("show_all", "false").lower() == "true"
        if not show_all:
            qs = qs.filter(is_active=True)
        stage = self.request.query_params.get("stage")
        if stage:
            qs = qs.filter(applicable_stages__icontains=stage)
        return qs.order_by("machine_code")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return success_response(message="Machines fetched.", data=list(ProductionMachineSerializer(qs, many=True).data))

    def post(self, request, *args, **kwargs):
        data = request.data
        required = ("machine_code", "name", "machine_type")
        for field in required:
            if not data.get(field):
                return success_response(message=f"{field} is required.", data={}, status_code=400)
        if ProductionMachine.objects.filter(machine_code=data["machine_code"]).exists():
            return success_response(message="Machine code already exists.", data={}, status_code=400)
        machine = ProductionMachine.objects.create(
            machine_code=data["machine_code"].strip().upper(),
            name=data["name"].strip(),
            machine_type=data["machine_type"],
            applicable_stages=data.get("applicable_stages", "AD,BL"),
            location=data.get("location", ""),
            notes=data.get("notes", ""),
            is_active=data.get("is_active", True),
        )
        return success_response(message="Machine created.", data=ProductionMachineSerializer(machine).data, status_code=201)


class ProductionMachineDetailAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(ProductionMachine, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        machine = self.get_object(pk)
        return success_response(message="Machine fetched.", data=ProductionMachineSerializer(machine).data)

    def patch(self, request, pk, *args, **kwargs):
        machine = self.get_object(pk)
        data = request.data
        updatable = ("name", "machine_type", "applicable_stages", "location", "notes", "is_active")
        for field in updatable:
            if field in data:
                setattr(machine, field, data[field])
        machine.save()
        return success_response(message="Machine updated.", data=ProductionMachineSerializer(machine).data)

    def delete(self, request, pk, *args, **kwargs):
        machine = self.get_object(pk)
        machine.is_active = False
        machine.save()
        return success_response(message="Machine deactivated.", data={})


class BOMVariantListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BOMVariantListSerializer

    def get_queryset(self):
        qs = bom_variant_queryset().annotate(component_count=Count("components", distinct=True))
        show_all = self.request.query_params.get("show_all", "false").lower() == "true"
        if not show_all:
            qs = qs.filter(is_active=True)
        product_item = self.request.query_params.get("product_item")
        if product_item:
            qs = qs.filter(product_item_id=product_item)
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(variant_code__icontains=search) | Q(name__icontains=search))
        return qs.order_by("variant_code")

    def list(self, request, *args, **kwargs):
        return success_response(message="Recipes fetched.", data=list(BOMVariantListSerializer(self.get_queryset(), many=True).data))

    def post(self, request, *args, **kwargs):
        data = request.data
        required = ("variant_code", "name")
        for field in required:
            if not data.get(field):
                return success_response(message=f"{field} is required.", data={}, status_code=400)
        if BOMVariant.objects.filter(variant_code=data["variant_code"]).exists():
            return success_response(message="Variant code already exists.", data={}, status_code=400)

        from apps.items.models import Item
        product_item = None
        if data.get("product_item"):
            product_item = get_object_or_404(Item, pk=data["product_item"])

        with transaction.atomic():
            bom = BOMVariant(
                variant_code=data["variant_code"].strip().upper(),
                name=data["name"].strip(),
                product_item=product_item,
                revision=data.get("revision", "v1"),
                batch_size=data.get("batch_size") or None,
                batch_uom=data.get("batch_uom", ""),
                status=data.get("status", BOMVariant.RecipeStatus.DRAFT),
                approved_by_id=data.get("approved_by") or None,
                approved_at=data.get("approved_at") or None,
                notes=data.get("notes", ""),
                is_active=True,
                created_by=request.user,
            )
            if data.get("password"):
                bom.set_password(str(data["password"]))
            else:
                bom.access_password_hash = ""
            bom.save()

            seen_keys = set()
            components = data.get("components", [])
            for index, comp_data in enumerate(components, start=1):
                payload, error = validate_bom_component_payload(comp_data, index)
                if error:
                    return success_response(
                        message=f"Component {index}: {error}",
                        data={},
                        status_code=400,
                    )

                duplicate_key = (
                    ("product_subtype", payload["product_subtype"].pk)
                    if payload["product_subtype"] is not None
                    else ("item", payload["item"].pk)
                )
                if duplicate_key in seen_keys:
                    return success_response(
                        message=f"Component {index}: duplicate component selection is not allowed.",
                        data={},
                        status_code=400,
                    )
                seen_keys.add(duplicate_key)
                BOMVariantComponent.objects.create(bom_variant=bom, **payload)

        full_bom = bom_variant_queryset().get(pk=bom.pk)
        return success_response(message="Recipe created.", data=BOMVariantDetailSerializer(full_bom).data, status_code=201)


class BOMVariantDetailAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(bom_variant_queryset(), pk=pk)

    def get(self, request, pk, *args, **kwargs):
        bom = self.get_object(pk)
        return success_response(message="Recipe fetched.", data=BOMVariantDetailSerializer(bom).data)

    def patch(self, request, pk, *args, **kwargs):
        bom = self.get_object(pk)
        data = request.data
        for field in ("name", "revision", "notes", "is_active", "batch_size", "batch_uom", "status", "approved_at"):
            if field in data:
                setattr(bom, field, data[field])
        if "approved_by" in data:
            bom.approved_by_id = data.get("approved_by") or None
        if data.get("product_item"):
            from apps.items.models import Item
            bom.product_item = get_object_or_404(Item, pk=data["product_item"])
        bom.save()
        refreshed = bom_variant_queryset().annotate(component_count=Count("components", distinct=True)).get(pk=bom.pk)
        return success_response(message="Recipe updated.", data=BOMVariantListSerializer(refreshed).data)

    def delete(self, request, pk, *args, **kwargs):
        bom = self.get_object(pk)
        bom.is_active = False
        bom.status = BOMVariant.RecipeStatus.INACTIVE
        bom.save()
        return success_response(message="Recipe deactivated.", data={})


class BOMVariantSetPasswordAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk)
        password = request.data.get("password", "")
        if not password:
            return success_response(message="Password is required.", data={}, status_code=400)
        bom.set_password(str(password))
        bom.save()
        return success_response(message="Password updated successfully.", data={})


class BOMVariantComponentAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk, is_active=True)
        data = request.data
        payload, error = validate_bom_component_payload(data, bom.components.count() + 1)
        if error:
            return success_response(message=error, data={}, status_code=400)

        duplicate_filter = {"product_subtype": payload["product_subtype"]} if payload["product_subtype"] else {"item": payload["item"]}
        if BOMVariantComponent.objects.filter(bom_variant=bom, **duplicate_filter).exists():
            return success_response(message="This item is already mapped to this recipe.", data={}, status_code=400)

        comp = BOMVariantComponent.objects.create(bom_variant=bom, **payload)
        comp = bom_component_queryset().get(pk=comp.pk)
        return success_response(message="Recipe item added.", data=BOMVariantComponentSerializer(comp).data, status_code=201)

    def put(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk, is_active=True)
        components = request.data.get("components", [])
        if not isinstance(components, list):
            return success_response(message="components must be a list.", data={}, status_code=400)

        seen_keys = set()
        new_components = []
        for index, comp_data in enumerate(components, start=1):
            payload, error = validate_bom_component_payload(comp_data, index)
            if error:
                return success_response(
                    message=f"Component {index}: {error}",
                    data={},
                    status_code=400,
                )

            duplicate_key = (
                ("product_subtype", payload["product_subtype"].pk)
                if payload["product_subtype"] is not None
                else ("item", payload["item"].pk)
            )
            if duplicate_key in seen_keys:
                return success_response(
                    message=f"Component {index}: duplicate component selection is not allowed.",
                    data={},
                    status_code=400,
                )
            seen_keys.add(duplicate_key)
            new_components.append(BOMVariantComponent(bom_variant=bom, **payload))

        with transaction.atomic():
            bom.components.all().delete()
            if new_components:
                BOMVariantComponent.objects.bulk_create(new_components)

        refreshed = bom_variant_queryset().get(pk=bom.pk)
        return success_response(
            message="Recipe items saved.",
            data=BOMVariantDetailSerializer(refreshed).data,
        )

    def delete(self, request, pk, comp_id, *args, **kwargs):
        comp = get_object_or_404(BOMVariantComponent, pk=comp_id, bom_variant_id=pk)
        comp.delete()
        return success_response(message="Recipe item removed.", data={})


class BOMVariantVerifyPasswordAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk, is_active=True)
        if not bom.access_password_hash:
            return success_response(message="Recipe has no password configured.", data={"verified": True})
        password = request.data.get("password", "")
        if not password:
            return success_response(message="Password is required.", data={"verified": False}, status_code=400)
        if bom.check_password(str(password)):
            return success_response(message="Password verified. Recipe access granted.", data={"verified": True})
        return success_response(message="Invalid password. Recipe access denied.", data={"verified": False}, status_code=403)


class BOMVariantRecipeAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(bom_variant_queryset(), pk=pk, is_active=True)
        if not bom.access_password_hash:
            return success_response(message="Recipe fetched.", data=BOMVariantDetailSerializer(bom).data)
        password = request.data.get("password", "")
        if not bom.check_password(str(password)):
            return success_response(message="Invalid password.", data={}, status_code=403)
        return success_response(message="Recipe fetched.", data=BOMVariantDetailSerializer(bom).data)


class ProductionStageRecordListAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionStageRecordSerializer
    pagination_class = StandardResultsSetPagination
    AD_PRODUCTION_TYPE = "WPE Additive Production"
    STAGE_PRODUCTION_TYPE_BY_STAGE = {
        ProductionBatch.Stage.AD: "WPE Additive Production",
        ProductionBatch.Stage.BL: "WPE Blend Production",
        ProductionBatch.Stage.GL: "WPE Granulated Blend Production",
    }
    BATCH_STATUS_PRIORITY = {
        ProductionBatch.BatchStatus.IN_PROGRESS: 0,
        ProductionBatch.BatchStatus.PENDING: 1,
        ProductionBatch.BatchStatus.COMPLETED: 2,
        ProductionBatch.BatchStatus.FAILED: 3,
    }
    NEXT_WORKFLOW_STATUS_BY_STAGE = {
        ProductionBatch.Stage.AD: ProductionBatch.Stage.BL,
        ProductionBatch.Stage.BL: ProductionBatch.Stage.GL,
        ProductionBatch.Stage.GL: "PR",
    }

    def get(self, request, *args, **kwargs):
        stage = str(request.query_params.get("stage", "")).upper().strip()
        if stage not in {"AD", "BL", "GL", "PR"}:
            return success_response(
                message="stage is required and must be one of: AD, BL, GL, PR.",
                data={},
                status_code=400,
            )

        queryset = self._build_queryset(stage)
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        serializer = self.get_serializer(self._build_records(stage, rows), many=True)

        if page is not None:
            return success_response(
                message="Production stage records fetched.",
                data=self.paginator.get_paginated_data(serializer.data),
            )

        return success_response(
            message="Production stage records fetched.",
            data={"count": len(serializer.data), "results": serializer.data},
        )

    def _build_queryset(self, stage: str):
        search = str(self.request.query_params.get("search", "")).strip()
        status = str(self.request.query_params.get("status", "")).strip()
        date_from = str(self.request.query_params.get("date_from", "")).strip()
        date_to = str(self.request.query_params.get("date_to", "")).strip()

        batch_prefetch = Prefetch(
            "batches",
            queryset=ProductionBatch.objects.select_related("machine").order_by("-created_at"),
        )
        queryset = ProductionOrder.objects.prefetch_related(batch_prefetch).order_by("-production_date", "-created_at")
        if stage == ProductionBatch.Stage.AD:
            queryset = queryset.filter(
                Q(production_type=self.AD_PRODUCTION_TYPE) | Q(batches__stage=ProductionBatch.Stage.AD)
            ).distinct()
        elif stage in {ProductionBatch.Stage.BL, ProductionBatch.Stage.GL}:
            queryset = queryset.filter(batches__stage=stage).distinct()
        elif stage == "PR":
            queryset = queryset.filter(
                batches__stage=ProductionBatch.Stage.GL,
                batches__status=ProductionBatch.BatchStatus.COMPLETED,
            ).distinct()
        if status:
            if stage in {ProductionBatch.Stage.BL, ProductionBatch.Stage.GL}:
                queryset = queryset.filter(batches__stage=stage, batches__status=status).distinct()
            elif stage == "PR":
                if status != "IN_PROGRESS":
                    queryset = queryset.none()
            else:
                queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(production_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(production_date__lte=date_to)
        if search:
            queryset = queryset.filter(
                Q(production_id__icontains=search)
                | Q(production_type__icontains=search)
                | Q(batch_number__icontains=search)
                | Q(plan_id__icontains=search)
                | Q(line_name__icontains=search)
                | Q(line_number__icontains=search)
                | Q(batches__machine__name__icontains=search)
                | Q(batches__workflow_batch_no__icontains=search)
                | Q(batches__batch_no__icontains=search)
            ).distinct()
        return queryset

    def _build_records(self, stage: str, rows: list[ProductionOrder]):
        return [self._build_order_record(order, stage=stage) for order in rows]

    def _build_order_record(self, order: ProductionOrder, stage: str = "PR"):
        stage_batches = self._get_stage_batches(order, stage) if stage in {"AD", "BL", "GL"} else self._get_order_batches(order)
        preferred_batch = self._get_preferred_stage_batch(stage_batches)
        display_batch_no = self._resolve_batch_display_no(preferred_batch)
        return {
            "id": order.id,
            "order_id": order.id,
            "production_id": order.production_id,
            "stage": stage,
            "production_type": self._resolve_stage_production_type(order, stage),
            "batch_no": display_batch_no,
            "display_batch_no": display_batch_no,
            "batch_count": len(stage_batches) if stage in {"AD", "BL", "GL"} else len(self._get_order_batches(order)),
            "production_date": order.production_date,
            "shift": order.shift,
            "line_no": self._format_order_line(order, preferred_batch),
            "start_date_time": preferred_batch.started_at if preferred_batch and preferred_batch.started_at else order.start_date_time,
            "end_date_time": self._resolve_stage_end_time(order, stage, stage_batches, preferred_batch),
            "plan_id": self._format_plan_id(order.plan_id),
            "status": self._resolve_stage_status(order, stage, stage_batches, preferred_batch),
            "workflow_status": self._get_stage_workflow_status(order, stage, stage_batches),
        }

    def _format_plan_id(self, value):
        text = str(value or "").strip()
        return text or "0"

    def _format_batch_line(self, batch: ProductionBatch):
        machine_name = str(getattr(batch.machine, "name", "") or "").strip()
        if machine_name:
            return machine_name

        order_line = self._format_order_line(batch.production_order)
        if order_line != "-":
            return order_line

        if batch.stage == ProductionBatch.Stage.BL:
            return "Line: Blending"
        if batch.stage == ProductionBatch.Stage.GL:
            return "Line: Granulation"
        return "-"

    def _format_order_line(self, order: ProductionOrder, preferred_batch: ProductionBatch | None = None):
        line_number = str(order.line_number or "").strip()
        line_name = str(order.line_name or "").strip()
        if line_number and line_name:
            prefix = line_number if line_number.lower().startswith("line") else f"Line {line_number}"
            return f"{prefix}: {line_name}"
        if line_name:
            return line_name
        if line_number:
            return line_number if line_number.lower().startswith("line") else f"Line {line_number}"
        if preferred_batch and preferred_batch.machine_id and preferred_batch.machine:
            return preferred_batch.machine.name
        return "-"

    def _get_order_batches(self, order: ProductionOrder):
        prefetched_batches = getattr(order, "_prefetched_objects_cache", {}).get("batches")
        if prefetched_batches is not None:
            return list(prefetched_batches)
        return list(order.batches.all())

    def _get_stage_batches(self, order: ProductionOrder, stage: str):
        return [batch for batch in self._get_order_batches(order) if batch.stage == stage]

    def _get_preferred_stage_batch(self, batches: list[ProductionBatch]):
        if not batches:
            return None
        return sorted(
            batches,
            key=lambda batch: (
                self.BATCH_STATUS_PRIORITY.get(batch.status, 99),
                -(batch.id or 0),
            ),
        )[0]

    def _get_stage_workflow_status(self, order: ProductionOrder, stage: str, stage_batches: list[ProductionBatch]):
        if stage != "PR" and order.status in {"PLAN_COMPLETED", "CLOSED"}:
            return "COMPLETED"

        if stage == "PR":
            return "PR"

        if stage == ProductionBatch.Stage.AD and not stage_batches:
            return ProductionBatch.Stage.AD
        if any(batch.status in {ProductionBatch.BatchStatus.IN_PROGRESS, ProductionBatch.BatchStatus.PENDING} for batch in stage_batches):
            return stage
        if stage_batches and all(batch.status == ProductionBatch.BatchStatus.COMPLETED for batch in stage_batches):
            next_stage = self.NEXT_WORKFLOW_STATUS_BY_STAGE.get(stage, stage)
            if next_stage == "PR":
                return "PR"
            if next_stage == "COMPLETED":
                return "COMPLETED"
            if self._get_stage_batches(order, next_stage):
                return next_stage
        return stage

    def _resolve_stage_end_time(
        self,
        order: ProductionOrder,
        stage: str,
        stage_batches: list[ProductionBatch],
        preferred_batch: ProductionBatch | None = None,
    ):
        if stage == "PR":
            return order.end_date_time or (preferred_batch.completed_at if preferred_batch else None)
        if any(batch.status in {ProductionBatch.BatchStatus.IN_PROGRESS, ProductionBatch.BatchStatus.PENDING} for batch in stage_batches):
            return None
        completed_times = [batch.completed_at for batch in stage_batches if batch.completed_at is not None]
        return max(completed_times) if completed_times else None

    def _resolve_stage_status(
        self,
        order: ProductionOrder,
        stage: str,
        stage_batches: list[ProductionBatch],
        preferred_batch: ProductionBatch | None = None,
    ):
        if stage == "PR":
            return "IN_PROGRESS"
        if stage == ProductionBatch.Stage.AD:
            return order.status
        return preferred_batch.status if preferred_batch is not None else order.status

    def _resolve_stage_production_type(self, order: ProductionOrder, stage: str):
        if stage in self.STAGE_PRODUCTION_TYPE_BY_STAGE:
            return self.STAGE_PRODUCTION_TYPE_BY_STAGE[stage]
        return order.production_type

    def _resolve_batch_display_no(self, preferred_batch: ProductionBatch | None = None):
        if preferred_batch is None:
            return None
        return resolve_workflow_batch_no(preferred_batch)


class ProductionBatchListCreateAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionBatchSerializer
    filterset_map = {"stage": "stage", "status": "status"}

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["requested_stage"] = self.request.query_params.get("stage")
        return context

    def get_queryset(self):
        order_batch_prefetch = Prefetch(
            "production_order__batches",
            queryset=ProductionBatch.objects.select_related("machine", "output_capture").order_by("-created_at"),
        )
        return ProductionBatch.objects.filter(
            production_order_id=self.kwargs["order_pk"]
        ).select_related("production_order", "machine", "bom_variant", "operator", "output_capture").prefetch_related(
            order_batch_prefetch,
            "weight_entries__item",
            "weight_entries__bom_component__item",
            "weight_entries__bom_component__product_subtype__category",
            "regrind_entries__item",
        ).order_by("stage", "-created_at")

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return success_response(message="Batches fetched.", data=list(serializer.data))

    def post(self, request, *args, **kwargs):
        stage = request.data.get("stage")
        valid_stages = [s[0] for s in ProductionBatch.Stage.choices]
        if stage not in valid_stages:
            return success_response(message=f"Invalid stage. Must be one of: {', '.join(valid_stages)}", data={}, status_code=400)

        bom_variant_id = request.data.get("bom_variant") or None
        machine_id = request.data.get("machine") or None
        notes = request.data.get("notes", "")

        with transaction.atomic():
            order = get_object_or_404(
                ProductionOrder.objects.select_for_update(),
                pk=self.kwargs["order_pk"],
            )

            batch = ProductionBatch.objects.create(
                production_order=order,
                stage=stage,
                bom_variant_id=bom_variant_id,
                machine_id=machine_id,
                notes=notes,
                operator=request.user,
                status=ProductionBatch.BatchStatus.PENDING,
            )

            workflow_batch_no = str(order.batch_number or "").strip()
            if not workflow_batch_no and batch.batch_no:
                ProductionOrder.objects.filter(pk=order.pk).update(batch_number=batch.batch_no)

            if bom_variant_id:
                bom = bom_variant_queryset().get(pk=bom_variant_id)
                for component in bom.components.filter(is_active=True):
                    BatchWeightEntry.objects.get_or_create(
                        batch=batch,
                        bom_component=component,
                        defaults={
                            "item": component.item,
                            "target_weight_grams": component.target_weight_grams,
                            "entered_by": request.user,
                        }
                    )

        batch.refresh_from_db()
        full_batch = ProductionBatch.objects.select_related(
            "production_order", "machine", "bom_variant", "operator", "output_capture"
        ).prefetch_related(
            Prefetch(
                "production_order__batches",
                queryset=ProductionBatch.objects.select_related("machine", "output_capture").order_by("-created_at"),
            ),
            "weight_entries__item",
            "weight_entries__bom_component__item",
            "weight_entries__bom_component__product_subtype__category",
            "regrind_entries__item"
        ).get(pk=batch.pk)
        return success_response(message="Batch created.", data=ProductionBatchSerializer(full_batch).data, status_code=201)


class ProductionBatchDestroyAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _get_batch_capture(batch: ProductionBatch):
        try:
            return batch.output_capture
        except ProductionOutputCapture.DoesNotExist:
            return None

    def delete(self, request, order_pk, pk, *args, **kwargs):
        order = get_object_or_404(ProductionOrder, pk=order_pk)
        target_batch = get_object_or_404(
            ProductionBatch.objects.select_related("production_order"),
            pk=pk,
            production_order_id=order_pk,
        )

        with transaction.atomic():
            order_batches = list(
                order.batches.select_related("machine", "output_capture").order_by("-created_at", "-id")
            )
            workflow_batch_no = resolve_workflow_batch_no(target_batch, sibling_batches=order_batches) or str(
                target_batch.batch_no or ""
            )
            related_batches = [
                batch
                for batch in order_batches
                if resolve_workflow_batch_no(batch, sibling_batches=order_batches) == workflow_batch_no
            ]
            related_batch_ids = [batch.id for batch in related_batches]

            for batch in related_batches:
                capture = self._get_batch_capture(batch)
                if batch.stage == ProductionBatch.Stage.BL:
                    ProductionBatchConfirmAPIView._release_assigned_bin(capture)
                elif batch.stage == ProductionBatch.Stage.GL:
                    ProductionBatchConfirmAPIView._release_assigned_bag(capture)

            ProductionBatch.objects.filter(production_order_id=order_pk, id__in=related_batch_ids).delete()

            remaining_batches = list(
                order.batches.select_related("machine").exclude(id__in=related_batch_ids).order_by("-created_at", "-id")
            )
            next_batch_number = (
                resolve_workflow_batch_no(remaining_batches[0], sibling_batches=remaining_batches)
                if remaining_batches
                else ""
            )
            ProductionOrder.objects.filter(pk=order.pk).update(batch_number=next_batch_number or None)

        return success_response(
            message="Batch deleted.",
            data={
                "workflow_batch_no": workflow_batch_no,
                "deleted_batch_ids": related_batch_ids,
            },
        )


class ProductionBatchStartAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_pk, pk, *args, **kwargs):
        batch = get_object_or_404(ProductionBatch, pk=pk, production_order_id=order_pk)
        if batch.status != ProductionBatch.BatchStatus.PENDING:
            return success_response(message="Only PENDING batches can be started.", data={}, status_code=400)
        batch.status = ProductionBatch.BatchStatus.IN_PROGRESS
        batch.started_at = timezone.now()
        batch.save()
        return success_response(message="Batch started.", data=ProductionBatchSerializer(batch).data)


class ProductionBatchConfirmAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    NEXT_STAGE_BY_STAGE = {
        ProductionBatch.Stage.AD: ProductionBatch.Stage.BL,
        ProductionBatch.Stage.BL: ProductionBatch.Stage.GL,
    }

    @staticmethod
    def _sanitize_scancode_token(value: str) -> str:
        token = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        return token or "NA"

    def _get_required_weight_entries(self, batch: ProductionBatch):
        entries = list(
            batch.weight_entries.select_related(
                "bom_component__item",
                "bom_component__product_subtype__category",
            ).all()
        )
        entries.sort(key=lambda entry: (getattr(entry.bom_component, "sequence", 0), entry.id))
        positive_entries = [entry for entry in entries if float(entry.target_weight_grams or 0) > 0]
        return positive_entries or entries

    def _build_output_session_key(self, entries: list[BatchWeightEntry]) -> str:
        return "|".join(
            f"{entry.bom_component_id}:{Decimal(entry.entered_weight_grams or 0):.3f}:{entry.entered_at.isoformat()}"
            for entry in entries
        )

    def _build_output_scancode(self, batch: ProductionBatch, sequence: int, captured_at):
        return ProductionOutputCaptureListAPIView._build_stage_output_scancode(
            batch,
            sequence,
            captured_at,
        )

    def _seed_batch_weight_entries(self, batch: ProductionBatch, entered_by):
        if not batch.bom_variant_id:
            return

        for component in batch.bom_variant.components.filter(is_active=True):
            BatchWeightEntry.objects.get_or_create(
                batch=batch,
                bom_component=component,
                defaults={
                    "item": component.item,
                    "target_weight_grams": component.target_weight_grams,
                    "entered_by": entered_by,
                }
            )

    def _create_stage_handoff_batch(
        self,
        source_batch: ProductionBatch,
        next_stage: str,
        transitioned_at,
    ):
        workflow_batch_no = resolve_workflow_batch_no(source_batch)
        existing_batch = ProductionBatch.objects.filter(
            production_order=source_batch.production_order,
            stage=next_stage,
            workflow_batch_no=workflow_batch_no,
        ).order_by("-created_at").first()
        if existing_batch is not None:
            return existing_batch

        next_batch = ProductionBatch.objects.create(
            production_order=source_batch.production_order,
            bom_variant=source_batch.bom_variant,
            stage=next_stage,
            machine=source_batch.machine,
            workflow_batch_no=workflow_batch_no or None,
            status=ProductionBatch.BatchStatus.IN_PROGRESS,
            started_at=transitioned_at,
            operator=self.request.user,
            notes=f"Moved from {source_batch.stage} batch {source_batch.batch_no}.",
        )
        self._seed_batch_weight_entries(next_batch, self.request.user)
        return next_batch

    def _create_output_capture(self, batch: ProductionBatch):
        if batch.stage != ProductionBatch.Stage.AD:
            return None

        existing_capture = getattr(batch, "output_capture", None)
        if existing_capture is not None:
            return ProductionOutputCaptureListAPIView._ensure_capture_scancode_format(existing_capture)

        entries = self._get_required_weight_entries(batch)
        captured_at = batch.completed_at or timezone.now()
        total_weight = sum(((entry.entered_weight_grams or Decimal("0.000")) for entry in entries), Decimal("0.000"))
        existing_sequences = ProductionOutputCapture.objects.select_for_update().filter(
            production_order=batch.production_order
        ).values_list("sequence", flat=True)
        next_sequence = max(existing_sequences, default=0) + 1

        capture, _ = ProductionOutputCapture.objects.get_or_create(
            source_batch=batch,
            defaults={
                "production_order": batch.production_order,
                "sequence": next_sequence,
                "scancode_id": self._build_output_scancode(batch, next_sequence, captured_at),
                "recipe_no": str(getattr(batch.bom_variant, "variant_code", "") or batch.production_order.production_id or ""),
                "quantity_kg": total_weight,
                "weight_kg": total_weight,
                "binlot": str(batch.batch_no or ""),
                "session_key": self._build_output_session_key(entries),
                "captured_at": captured_at,
            },
        )
        return capture

    @staticmethod
    def _release_assigned_bin(capture: ProductionOutputCapture | None):
        if capture is None:
            return None

        assigned_bin_code = str(capture.binlot or "").strip()
        source_batch_code = str(getattr(capture.source_batch, "batch_no", "") or "").strip()
        if not assigned_bin_code or assigned_bin_code == source_batch_code:
            return None

        assigned_bin = (
            BinCreationMaster.objects.select_for_update()
            .filter(code__iexact=assigned_bin_code)
            .first()
        )
        if assigned_bin is None:
            return None

        assigned_bin.current_status = BinCreationMaster.BinStatus.FREE
        assigned_bin.current_material = ""
        assigned_bin.save(update_fields=["current_status", "current_material", "updated_at"])
        return assigned_bin

    @staticmethod
    def _release_assigned_bag(capture: ProductionOutputCapture | None):
        if capture is None:
            return None

        assigned_bag_code = str(capture.binlot or "").strip()
        source_batch_code = str(getattr(capture.source_batch, "batch_no", "") or "").strip()
        if not assigned_bag_code or assigned_bag_code == source_batch_code:
            return None

        assigned_bag = (
            BagCreationMaster.objects.select_for_update()
            .filter(code__iexact=assigned_bag_code)
            .first()
        )
        if assigned_bag is None:
            return None

        assigned_bag.current_status = BagCreationMaster.BagStatus.FREE
        assigned_bag.save(update_fields=["current_status", "updated_at"])
        return assigned_bag

    def post(self, request, order_pk, pk, *args, **kwargs):
        batch = get_object_or_404(
            ProductionBatch.objects.select_related("output_capture").prefetch_related("weight_entries"),
            pk=pk, production_order_id=order_pk
        )
        if batch.status != ProductionBatch.BatchStatus.IN_PROGRESS:
            return success_response(message="Only IN_PROGRESS batches can be confirmed.", data={}, status_code=400)

        if batch.stage in {ProductionBatch.Stage.BL, ProductionBatch.Stage.GL}:
            if getattr(batch, "output_capture", None) is None:
                return success_response(
                    message=(
                        "Create the BL captured output list before confirming this batch."
                        if batch.stage == ProductionBatch.Stage.BL
                        else "Create the GL captured output list before confirming this batch."
                    ),
                    data={},
                    status_code=400,
                )
        else:
            entries = list(batch.weight_entries.all())
            missing = [e for e in entries if e.entered_weight_grams is None]
            invalid = [e for e in entries if e.is_valid is False]

            if missing:
                return success_response(message=f"{len(missing)} component(s) have no weight entered yet.", data={"missing_count": len(missing)}, status_code=400)
            if invalid:
                return success_response(message=f"{len(invalid)} weight entry(ies) are out of valid range.", data={"invalid_count": len(invalid)}, status_code=400)

        with transaction.atomic():
            transitioned_at = timezone.now()
            bl_capture = None
            gl_capture = None
            if batch.stage == ProductionBatch.Stage.BL:
                bl_capture = (
                    ProductionOutputCapture.objects.select_for_update()
                    .filter(source_batch=batch)
                    .first()
                )
                bl_capture = ProductionOutputCaptureListAPIView._ensure_bl_capture_bin_assignment(bl_capture, batch)
                if bl_capture is None:
                    return success_response(
                        message="No free bin is available for assignment.",
                        data={},
                        status_code=400,
                    )
            elif batch.stage == ProductionBatch.Stage.GL:
                gl_capture = (
                    ProductionOutputCapture.objects.select_for_update()
                    .filter(source_batch=batch)
                    .first()
                )
                gl_capture = ProductionOutputCaptureListAPIView._ensure_gl_capture_bag_assignment(gl_capture, batch)
                if gl_capture is None:
                    return success_response(
                        message="No free bag is available for assignment.",
                        data={},
                        status_code=400,
                    )
            batch.status = ProductionBatch.BatchStatus.COMPLETED
            batch.completed_at = transitioned_at
            batch.save(update_fields=["status", "completed_at", "updated_at"])
            self._create_output_capture(batch)
            next_stage = self.NEXT_STAGE_BY_STAGE.get(batch.stage)
            if next_stage:
                self._create_stage_handoff_batch(batch, next_stage=next_stage, transitioned_at=transitioned_at)
            if batch.stage == ProductionBatch.Stage.BL:
                self._release_assigned_bin(bl_capture)
            elif batch.stage == ProductionBatch.Stage.GL:
                self._release_assigned_bag(gl_capture)

        return success_response(message="Batch confirmed and completed.", data=ProductionBatchSerializer(batch).data)


class ProductionOutputCaptureListAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _get_capture_queryset(order_pk, *, source_batch_id=None):
        queryset = (
            ProductionOutputCapture.objects.filter(production_order_id=order_pk)
            .select_related("production_order", "source_batch", "source_batch__bom_variant")
            .prefetch_related(
                Prefetch(
                    "source_batch__weight_entries",
                    queryset=BatchWeightEntry.objects.select_related(
                        "bom_component__item",
                        "bom_component__product_subtype__category",
                    ).order_by("bom_component__sequence", "id"),
                )
            )
            .order_by("-captured_at", "-id")
        )
        if source_batch_id is not None:
            queryset = queryset.filter(source_batch_id=source_batch_id)
        return queryset

    @staticmethod
    def _build_manual_output_session_key(batch: ProductionBatch, weight_kg: Decimal, captured_at):
        return f"{batch.stage}:{batch.id}:{weight_kg:.3f}:{captured_at.strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def _sanitize_scancode_token(value: str) -> str:
        token = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        return token or "NA"

    @staticmethod
    def _resolve_workflow_batch_suffix(batch: ProductionBatch) -> str:
        workflow_batch_no = resolve_workflow_batch_no(batch) or str(batch.batch_no or "")
        match = re.search(r"(\d+)(?!.*\d)", workflow_batch_no)
        if match:
            return match.group(1)[-2:].zfill(2)
        return "00"

    @classmethod
    def _build_stage_output_scancode(cls, batch: ProductionBatch, _sequence: int, captured_at):
        production_token = cls._sanitize_scancode_token(batch.production_order.production_id or "PRD")
        stage_token = cls._sanitize_scancode_token(batch.stage or "ST")
        localized_captured_at = timezone.localtime(captured_at) if timezone.is_aware(captured_at) else captured_at
        batch_suffix = cls._resolve_workflow_batch_suffix(batch)
        return f"{production_token}{stage_token}{localized_captured_at.strftime('%d%m%Y%H%M')}{batch_suffix}"

    @classmethod
    def _ensure_capture_scancode_format(cls, capture: ProductionOutputCapture):
        source_batch = getattr(capture, "source_batch", None)
        if source_batch is None:
            return capture

        expected_scancode = cls._build_stage_output_scancode(
            source_batch,
            capture.sequence,
            capture.captured_at,
        )
        if capture.scancode_id != expected_scancode:
            capture.scancode_id = expected_scancode
            capture.save(update_fields=["scancode_id", "updated_at"])
        return capture

    @staticmethod
    def _reserve_free_bin():
        reserved_bin = (
            BinCreationMaster.objects.select_for_update()
            .filter(
                is_active=True,
                current_status=BinCreationMaster.BinStatus.FREE,
            )
            .order_by("created_at", "id")
            .first()
        )
        if reserved_bin is None:
            return None

        reserved_bin.current_status = BinCreationMaster.BinStatus.OCCUPIED
        reserved_bin.save(update_fields=["current_status", "updated_at"])
        return reserved_bin

    @staticmethod
    def _reserve_free_bag():
        reserved_bag = (
            BagCreationMaster.objects.select_for_update()
            .filter(
                is_active=True,
                current_status=BagCreationMaster.BagStatus.FREE,
            )
            .order_by("created_at", "id")
            .first()
        )
        if reserved_bag is None:
            return None

        reserved_bag.current_status = BagCreationMaster.BagStatus.OCCUPIED
        reserved_bag.save(update_fields=["current_status", "updated_at"])
        return reserved_bag

    @staticmethod
    def _ensure_bl_capture_bin_assignment(capture: ProductionOutputCapture, batch: ProductionBatch):
        if batch.stage != ProductionBatch.Stage.BL:
            return capture

        current_binlot = str(capture.binlot or "").strip()
        matched_bin = None
        if current_binlot:
            matched_bin = (
                BinCreationMaster.objects.select_for_update()
                .filter(
                    is_active=True,
                    code__iexact=current_binlot,
                )
                .first()
            )

        if matched_bin is not None and matched_bin.current_status != BinCreationMaster.BinStatus.HOLD:
            if matched_bin.current_status == BinCreationMaster.BinStatus.FREE:
                matched_bin.current_status = BinCreationMaster.BinStatus.OCCUPIED
                matched_bin.save(update_fields=["current_status", "updated_at"])
            return capture

        reserved_bin = ProductionOutputCaptureListAPIView._reserve_free_bin()
        if reserved_bin is None:
            return None

        capture.binlot = str(reserved_bin.code or "")
        capture.save(update_fields=["binlot", "updated_at"])
        return capture

    @staticmethod
    def _ensure_gl_capture_bag_assignment(capture: ProductionOutputCapture, batch: ProductionBatch):
        if batch.stage != ProductionBatch.Stage.GL:
            return capture

        current_baglot = str(capture.binlot or "").strip()
        matched_bag = None
        if current_baglot:
            matched_bag = (
                BagCreationMaster.objects.select_for_update()
                .filter(
                    is_active=True,
                    code__iexact=current_baglot,
                )
                .first()
            )

        if matched_bag is not None and matched_bag.current_status != BagCreationMaster.BagStatus.USED:
            if matched_bag.current_status == BagCreationMaster.BagStatus.FREE:
                matched_bag.current_status = BagCreationMaster.BagStatus.OCCUPIED
                matched_bag.save(update_fields=["current_status", "updated_at"])
            return capture

        reserved_bag = ProductionOutputCaptureListAPIView._reserve_free_bag()
        if reserved_bag is None:
            return None

        capture.binlot = str(reserved_bag.code or "")
        capture.save(update_fields=["binlot", "updated_at"])
        return capture

    @staticmethod
    def _parse_source_batch_id(value):
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return "invalid"
        return parsed if parsed > 0 else "invalid"

    def get(self, request, order_pk, *args, **kwargs):
        get_object_or_404(ProductionOrder, pk=order_pk)
        source_batch_id = self._parse_source_batch_id(request.query_params.get("source_batch"))
        if source_batch_id == "invalid":
            return success_response(message="source_batch must be a valid batch identifier.", data={}, status_code=400)

        captures = list(self._get_capture_queryset(order_pk, source_batch_id=source_batch_id))
        for capture in captures:
            self._ensure_capture_scancode_format(capture)
        return success_response(
            message="Output captures fetched.",
            data=list(ProductionOutputCaptureSerializer(captures, many=True).data),
        )

    def post(self, request, order_pk, *args, **kwargs):
        order = get_object_or_404(ProductionOrder, pk=order_pk)
        source_batch_id = self._parse_source_batch_id(request.data.get("source_batch"))
        if source_batch_id is None:
            return success_response(message="source_batch is required.", data={}, status_code=400)
        if source_batch_id == "invalid":
            return success_response(message="source_batch must be a valid batch identifier.", data={}, status_code=400)

        batch = get_object_or_404(
            ProductionBatch.objects.select_related("production_order", "bom_variant"),
            pk=source_batch_id,
            production_order_id=order_pk,
        )
        if batch.stage == ProductionBatch.Stage.AD:
            return success_response(message="AD output captures are created from final capture only.", data={}, status_code=400)
        if batch.status == ProductionBatch.BatchStatus.FAILED:
            return success_response(message="Cannot capture output for a failed batch.", data={}, status_code=400)

        raw_weight = request.data.get("weight_kg")
        if raw_weight in (None, ""):
            return success_response(message="weight_kg is required.", data={}, status_code=400)

        try:
            weight_kg = Decimal(str(raw_weight)).quantize(Decimal("0.001"))
        except Exception:
            return success_response(message="weight_kg must be a valid decimal value.", data={}, status_code=400)

        if weight_kg <= 0:
            return success_response(message="weight_kg must be greater than zero.", data={}, status_code=400)

        captured_at = timezone.now()

        with transaction.atomic():
            existing_capture = (
                ProductionOutputCapture.objects.select_for_update()
                .filter(source_batch=batch)
                .first()
            )
            if existing_capture is None:
                if batch.status == ProductionBatch.BatchStatus.COMPLETED:
                    return success_response(
                        message="Cannot create a captured output list for a completed batch.",
                        data={},
                        status_code=400,
                    )
                assigned_binlot = str(batch.batch_no or "")
                if batch.stage == ProductionBatch.Stage.BL:
                    assigned_bin = self._reserve_free_bin()
                    if assigned_bin is None:
                        return success_response(
                            message="No free bin is available for assignment.",
                            data={},
                            status_code=400,
                        )
                    assigned_binlot = str(assigned_bin.code or "")
                elif batch.stage == ProductionBatch.Stage.GL:
                    assigned_bag = self._reserve_free_bag()
                    if assigned_bag is None:
                        return success_response(
                            message="No free bag is available for assignment.",
                            data={},
                            status_code=400,
                        )
                    assigned_binlot = str(assigned_bag.code or "")
                existing_sequences = ProductionOutputCapture.objects.select_for_update().filter(
                    production_order=order
                ).values_list("sequence", flat=True)
                sequence = max(existing_sequences, default=0) + 1
                capture = ProductionOutputCapture.objects.create(
                    production_order=order,
                    source_batch=batch,
                    sequence=sequence,
                    scancode_id=self._build_stage_output_scancode(batch, sequence, captured_at),
                    recipe_no=str(getattr(batch.bom_variant, "variant_code", "") or order.production_id or ""),
                    quantity_kg=weight_kg,
                    weight_kg=weight_kg,
                    binlot=assigned_binlot,
                    session_key=self._build_manual_output_session_key(batch, weight_kg, captured_at),
                    captured_at=captured_at,
                )
                created = True
            else:
                capture = existing_capture
                created = False
                if batch.stage == ProductionBatch.Stage.BL:
                    capture = self._ensure_bl_capture_bin_assignment(capture, batch)
                    if capture is None:
                        return success_response(
                            message="No free bin is available for assignment.",
                            data={},
                            status_code=400,
                        )
                elif batch.stage == ProductionBatch.Stage.GL:
                    capture = self._ensure_gl_capture_bag_assignment(capture, batch)
                    if capture is None:
                        return success_response(
                            message="No free bag is available for assignment.",
                            data={},
                            status_code=400,
                        )
                capture = self._ensure_capture_scancode_format(capture)

        capture = self._get_capture_queryset(order_pk, source_batch_id=source_batch_id).get(pk=capture.pk)
        return success_response(
            message="Output capture saved." if created else "Output capture already exists for this batch.",
            data=ProductionOutputCaptureSerializer(capture).data,
            status_code=201 if created else 200,
        )


class BatchWeightEntryUpdateAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_pk, batch_pk, pk, *args, **kwargs):
        entry = get_object_or_404(BatchWeightEntry, pk=pk, batch_id=batch_pk, batch__production_order_id=order_pk)
        if entry.batch.status == ProductionBatch.BatchStatus.COMPLETED:
            return success_response(message="Cannot edit weight entries on a completed batch.", data={}, status_code=400)

        weight_raw = request.data.get("entered_weight_grams")
        if weight_raw is None:
            return success_response(message="entered_weight_grams is required.", data={}, status_code=400)
        try:
            weight = Decimal(str(weight_raw))
        except Exception:
            return success_response(message="entered_weight_grams must be a valid number.", data={}, status_code=400)

        entry.entered_weight_grams = weight
        entry.entered_by = request.user
        entry.validate_weight()
        entry.save()

        return success_response(
            message="Weight saved." if entry.is_valid else "Weight saved but is out of valid range.",
            data=BatchWeightEntrySerializer(entry).data,
            status_code=200 if entry.is_valid else 422,
        )


class RegrindEntryListCreateAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_pk, batch_pk, *args, **kwargs):
        entries = RegrindMaterialEntry.objects.filter(batch_id=batch_pk, production_order_id=order_pk).select_related("item", "added_by")
        return success_response(message="Regrind entries fetched.", data=list(RegrindMaterialEntrySerializer(entries, many=True).data))

    def post(self, request, order_pk, batch_pk, *args, **kwargs):
        batch = get_object_or_404(ProductionBatch, pk=batch_pk, production_order_id=order_pk)
        if batch.status == ProductionBatch.BatchStatus.COMPLETED:
            return success_response(message="Cannot add regrind to a completed batch.", data={}, status_code=400)

        item_id = request.data.get("item_id")
        qty_raw = request.data.get("quantity_grams")
        source_lot = request.data.get("source_lot_no", "")
        notes = request.data.get("notes", "")
        stage = request.data.get("stage", batch.stage)

        if not item_id:
            return success_response(message="item_id is required.", data={}, status_code=400)
        if qty_raw is None:
            return success_response(message="quantity_grams is required.", data={}, status_code=400)
        try:
            qty = Decimal(str(qty_raw))
        except Exception:
            return success_response(message="quantity_grams must be a valid number.", data={}, status_code=400)

        from apps.items.models import Item
        item = get_object_or_404(Item, pk=item_id)

        errors = []
        if qty <= 0:
            errors.append("Quantity must be greater than zero.")
        if float(qty) < WEIGHT_MIN_GRAMS:
            errors.append(f"Below global minimum {WEIGHT_MIN_GRAMS}g.")
        if float(qty) > WEIGHT_MAX_GRAMS:
            errors.append(f"Exceeds global maximum {WEIGHT_MAX_GRAMS}g.")

        is_valid = len(errors) == 0
        entry = RegrindMaterialEntry.objects.create(
            production_order_id=order_pk, batch=batch, stage=stage, item=item,
            quantity_grams=qty, source_lot_no=source_lot,
            is_valid=is_valid, validation_notes=" ".join(errors),
            notes=notes, added_by=request.user,
        )
        return success_response(
            message="Regrind added." if is_valid else "Regrind added but has validation issues.",
            data=RegrindMaterialEntrySerializer(entry).data,
            status_code=201 if is_valid else 422,
        )


class RegrindHistoryAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def list(self, request, *args, **kwargs):
        qs = RegrindMaterialEntry.objects.select_related("item", "production_order", "batch", "added_by").order_by("-added_at")
        if request.query_params.get("item_id"):
            qs = qs.filter(item_id=request.query_params["item_id"])
        if request.query_params.get("order_id"):
            qs = qs.filter(production_order_id=request.query_params["order_id"])
        page = self.paginate_queryset(qs)
        if page is not None:
            return success_response(message="Regrind history fetched.", data=self.paginator.get_paginated_data(RegrindMaterialEntrySerializer(page, many=True).data))
        return success_response(message="Regrind history fetched.", data=list(RegrindMaterialEntrySerializer(qs, many=True).data))


class ProductionDashboardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return success_response(message="Production dashboard fetched.", data={
            "planned": ProductionOrder.objects.filter(status="PLANNED").count(),
            "in_progress": ProductionOrder.objects.filter(status="IN_PROGRESS").count(),
            "completed": ProductionOrder.objects.filter(status="PLAN_COMPLETED").count(),
            "closed": ProductionOrder.objects.filter(status="CLOSED").count(),
            "total_machines": ProductionMachine.objects.filter(is_active=True).count(),
            "total_bom_variants": BOMVariant.objects.filter(is_active=True).count(),
        })
