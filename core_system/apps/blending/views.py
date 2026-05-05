from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.items.models import Item, STOCK_ZERO
from apps.items.serializers import ItemStockTransactionSerializer

from .models import DepartmentStock
from .serializers import DepartmentStockSerializer, StockTransferRequestSerializer, StockTransferSerializer
from .services import transfer_stock


class RequestBlendingStockAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = StockTransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transfer, from_stock, to_stock, transfer_out_transaction, transfer_in_transaction = transfer_stock(
                item_id=serializer.validated_data["item_id"],
                quantity=serializer.validated_data["quantity"],
            )
        except Item.DoesNotExist:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "detail": "Stock transferred to blending department.",
                "transfer": StockTransferSerializer(transfer).data,
                "from_department_stock": DepartmentStockSerializer(from_stock).data,
                "to_department_stock": DepartmentStockSerializer(to_stock).data,
                "transactions": ItemStockTransactionSerializer(
                    [transfer_out_transaction, transfer_in_transaction],
                    many=True,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BlendingStockListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        blending_stock = (
            DepartmentStock.objects.select_related("item")
            .filter(
                department=DepartmentStock.Department.BLENDING,
                quantity__gt=STOCK_ZERO,
            )
            .order_by("item__item_name", "item_id")
        )
        return Response(DepartmentStockSerializer(blending_stock, many=True).data)
