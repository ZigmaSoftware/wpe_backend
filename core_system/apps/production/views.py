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

        if stage in {ProductionBatch.Stage.AD, ProductionBatch.Stage.BL, ProductionBatch.Stage.GL}:
            queryset = (
                ProductionBatch.objects.filter(stage=stage)
                .select_related("production_order", "machine")
                .order_by("-started_at", "-created_at")
            )
            if status:
                queryset = queryset.filter(status=status)
            if date_from:
                queryset = queryset.filter(production_order__production_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(production_order__production_date__lte=date_to)
            if search:
                queryset = queryset.filter(
                    Q(batch_no__icontains=search)
                    | Q(production_order__production_id__icontains=search)
                    | Q(production_order__production_type__icontains=search)
                    | Q(production_order__plan_id__icontains=search)
                    | Q(machine__name__icontains=search)
                    | Q(production_order__line_name__icontains=search)
                )
            return queryset

        batch_prefetch = Prefetch(
            "batches",
            queryset=ProductionBatch.objects.select_related("machine").order_by("-created_at"),
        )
        queryset = ProductionOrder.objects.prefetch_related(batch_prefetch).order_by("-production_date", "-created_at")
        if status:
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
                | Q(batches__batch_no__icontains=search)
            ).distinct()
        return queryset

    def _build_records(self, stage: str, rows: list[ProductionBatch] | list[ProductionOrder]):
        if stage == "PR":
            return [self._build_order_record(order) for order in rows]
        return [self._build_batch_record(batch) for batch in rows]  # AD, BL, GL all use batch records

    def _build_batch_record(self, batch: ProductionBatch):
        order = batch.production_order
        return {
            "id": batch.id,
            "order_id": order.id,
            "production_id": order.production_id,
            "stage": batch.stage,
            "production_type": order.production_type,
            "batch_no": batch.batch_no,
            "production_date": order.production_date,
            "shift": order.shift,
            "line_no": self._format_batch_line(batch),
            "start_date_time": batch.started_at,
            "end_date_time": batch.completed_at,
            "plan_id": self._format_plan_id(order.plan_id),
            "status": batch.status,
        }

    def _build_order_record(self, order: ProductionOrder):
        preferred_batch = self._get_preferred_batch(order)
        return {
            "id": order.id,
            "order_id": order.id,
            "production_id": order.production_id,
            "stage": "PR",
            "production_type": order.production_type,
            "batch_no": self._resolve_order_batch_no(order, preferred_batch),
            "production_date": order.production_date,
            "shift": order.shift,
            "line_no": self._format_order_line(order, preferred_batch),
            "start_date_time": order.start_date_time,
            "end_date_time": order.end_date_time,
            "plan_id": self._format_plan_id(order.plan_id),
            "status": order.status,
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

    def _get_preferred_batch(self, order: ProductionOrder):
        stage_priority = {
            ProductionBatch.Stage.GL: 0,
            ProductionBatch.Stage.BL: 1,
            ProductionBatch.Stage.AD: 2,
        }
        batches = list(order.batches.all())
        if not batches:
            return None
        batches.sort(key=lambda batch: (stage_priority.get(batch.stage, 99), -(batch.id or 0)))
        return batches[0]

    def _resolve_order_batch_no(self, order: ProductionOrder, preferred_batch: ProductionBatch | None = None):
        batch_number = str(order.batch_number or "").strip()
        if batch_number:
            return batch_number
        if preferred_batch and preferred_batch.batch_no:
            return preferred_batch.batch_no
        return None


class ProductionBatchListCreateAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionBatchSerializer
    filterset_map = {"stage": "stage", "status": "status"}

    def get_queryset(self):
        return ProductionBatch.objects.filter(
            production_order_id=self.kwargs["order_pk"]
        ).select_related("machine", "bom_variant", "operator").prefetch_related(
            "weight_entries__item",
            "weight_entries__bom_component__item",
            "weight_entries__bom_component__product_subtype__category",
            "regrind_entries__item",
        ).order_by("stage", "created_at")

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return success_response(message="Batches fetched.", data=list(ProductionBatchSerializer(qs, many=True).data))

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(ProductionOrder, pk=self.kwargs["order_pk"])
        stage = request.data.get("stage")
        valid_stages = [s[0] for s in ProductionBatch.Stage.choices]
        if stage not in valid_stages:
            return success_response(message=f"Invalid stage. Must be one of: {', '.join(valid_stages)}", data={}, status_code=400)

        bom_variant_id = request.data.get("bom_variant") or None
        machine_id = request.data.get("machine") or None
        notes = request.data.get("notes", "")

        batch = ProductionBatch.objects.create(
            production_order=order,
            stage=stage,
            bom_variant_id=bom_variant_id,
            machine_id=machine_id,
            notes=notes,
            operator=request.user,
            status=ProductionBatch.BatchStatus.PENDING,
        )

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
        full_batch = ProductionBatch.objects.prefetch_related(
            "weight_entries__item",
            "weight_entries__bom_component__item",
            "weight_entries__bom_component__product_subtype__category",
            "regrind_entries__item"
        ).get(pk=batch.pk)
        return success_response(message="Batch created.", data=ProductionBatchSerializer(full_batch).data, status_code=201)


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

    NEXT_PRODUCTION_TYPE_BY_STAGE = {
        ProductionBatch.Stage.AD: "WPE Blend Production",
        ProductionBatch.Stage.BL: "WPE Granulated Blend Production",
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
        primary_token = self._sanitize_scancode_token(batch.batch_no or batch.production_order.production_id or "PRD")
        return f"BIN-{primary_token}/ITEM-OUT{sequence:03d}/REF-{captured_at.strftime('%Y%m%d%H%M%S')}"

    def _create_next_stage_batch(self, batch: ProductionBatch):
        next_stage = self.NEXT_STAGE_BY_STAGE.get(batch.stage)
        if not next_stage:
            return None

        next_batch = ProductionBatch.objects.create(
            production_order=batch.production_order,
            bom_variant=batch.bom_variant,
            stage=next_stage,
            machine=batch.machine,
            status=ProductionBatch.BatchStatus.PENDING,
            operator=batch.operator,
            notes=f"Auto-created from {batch.batch_no} after {batch.stage} completion.",
        )

        if batch.bom_variant_id:
            for component in batch.bom_variant.components.filter(is_active=True):
                BatchWeightEntry.objects.get_or_create(
                    batch=next_batch,
                    bom_component=component,
                    defaults={
                        "item": component.item,
                        "target_weight_grams": component.target_weight_grams,
                        "entered_by": self.request.user,
                    }
                )

        next_production_type = self.NEXT_PRODUCTION_TYPE_BY_STAGE.get(batch.stage)
        if next_production_type:
            updates = {"production_type": next_production_type}
            if next_batch.batch_no:
                updates["batch_number"] = next_batch.batch_no
            ProductionOrder.objects.filter(pk=batch.production_order_id).update(**updates)

        return next_batch

    def _create_output_capture(self, batch: ProductionBatch):
        if batch.stage != ProductionBatch.Stage.AD:
            return None

        existing_capture = getattr(batch, "output_capture", None)
        if existing_capture is not None:
            return existing_capture

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

    def post(self, request, order_pk, pk, *args, **kwargs):
        batch = get_object_or_404(
            ProductionBatch.objects.prefetch_related("weight_entries"),
            pk=pk, production_order_id=order_pk
        )
        if batch.status != ProductionBatch.BatchStatus.IN_PROGRESS:
            return success_response(message="Only IN_PROGRESS batches can be confirmed.", data={}, status_code=400)

        entries = list(batch.weight_entries.all())
        missing = [e for e in entries if e.entered_weight_grams is None]
        invalid = [e for e in entries if e.is_valid is False]

        if missing:
            return success_response(message=f"{len(missing)} component(s) have no weight entered yet.", data={"missing_count": len(missing)}, status_code=400)
        if invalid:
            return success_response(message=f"{len(invalid)} weight entry(ies) are out of valid range.", data={"invalid_count": len(invalid)}, status_code=400)

        with transaction.atomic():
            batch.status = ProductionBatch.BatchStatus.COMPLETED
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "completed_at", "updated_at"])
            self._create_output_capture(batch)
            self._create_next_stage_batch(batch)

        return success_response(message="Batch confirmed and completed.", data=ProductionBatchSerializer(batch).data)


class ProductionOutputCaptureListAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_pk, *args, **kwargs):
        get_object_or_404(ProductionOrder, pk=order_pk)
        captures = (
            ProductionOutputCapture.objects.filter(production_order_id=order_pk)
            .select_related("production_order", "source_batch")
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
        return success_response(
            message="Output captures fetched.",
            data=list(ProductionOutputCaptureSerializer(captures, many=True).data),
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
