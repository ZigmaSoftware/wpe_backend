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
    search_fields = ['production_id', 'batch_number', 'plan_id', 'line_name']
    ordering_fields = ['production_date', 'created_at', 'total_cost']
    ordering = ['-production_date', '-created_at']

    def get_serializer_class(self):
        """Choose serializer based on action"""
        if self.action == 'retrieve':
            return ProductionOrderDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductionOrderCreateUpdateSerializer
        return ProductionOrderListSerializer

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


# ===== NEW OIMS PRODUCTION VIEWS =====

from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework import status as drf_status
from rest_framework.permissions import IsAuthenticated

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from .models import (
    ProductionMachine, BOMVariant, BOMVariantComponent,
    ProductionBatch, BatchWeightEntry, RegrindMaterialEntry,
    WEIGHT_MIN_GRAMS, WEIGHT_MAX_GRAMS,
)
from .serializers import (
    ProductionMachineSerializer,
    BOMVariantListSerializer,
    BOMVariantDetailSerializer,
    ProductionBatchSerializer,
    BatchWeightEntrySerializer,
    RegrindMaterialEntrySerializer,
)


class ProductionMachineListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionMachineSerializer

    def get_queryset(self):
        qs = ProductionMachine.objects.filter(is_active=True)
        stage = self.request.query_params.get("stage")
        if stage:
            qs = qs.filter(applicable_stages__icontains=stage)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return success_response(message="Machines fetched.", data=list(ProductionMachineSerializer(qs, many=True).data))


class BOMVariantListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BOMVariantListSerializer

    def get_queryset(self):
        return BOMVariant.objects.filter(is_active=True).prefetch_related("components")

    def list(self, request, *args, **kwargs):
        return success_response(message="BOM variants fetched.", data=list(BOMVariantListSerializer(self.get_queryset(), many=True).data))


class BOMVariantVerifyPasswordAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk, is_active=True)
        password = request.data.get("password", "")
        if not password:
            return success_response(message="Password is required.", data={"verified": False}, status_code=400)
        if bom.check_password(str(password)):
            return success_response(message="Password verified. Recipe access granted.", data={"verified": True})
        return success_response(message="Invalid password. Recipe access denied.", data={"verified": False}, status_code=403)


class BOMVariantRecipeAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        bom = get_object_or_404(BOMVariant, pk=pk, is_active=True)
        password = request.data.get("password", "")
        if not bom.check_password(str(password)):
            return success_response(message="Invalid password.", data={}, status_code=403)
        return success_response(message="Recipe fetched.", data=BOMVariantDetailSerializer(bom).data)


class ProductionBatchListCreateAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionBatchSerializer
    filterset_map = {"stage": "stage", "status": "status"}

    def get_queryset(self):
        return ProductionBatch.objects.filter(
            production_order_id=self.kwargs["order_pk"]
        ).select_related("machine", "bom_variant", "operator").prefetch_related(
            "weight_entries__item", "weight_entries__bom_component",
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
            bom = BOMVariant.objects.prefetch_related("components__item").get(pk=bom_variant_id)
            for component in bom.components.all():
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
            "weight_entries__item", "weight_entries__bom_component",
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

        batch.status = ProductionBatch.BatchStatus.COMPLETED
        batch.completed_at = timezone.now()
        batch.save()
        return success_response(message="Batch confirmed and completed.", data=ProductionBatchSerializer(batch).data)


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
