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
