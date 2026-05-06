from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.items.models import STOCK_ZERO
from apps.store.serializers import StockRequestSerializer
from apps.store.services import request_stock

from .models import BlendingStock
from .serializers import BlendingStockSerializer


class RequestBlendingStockAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = StockRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_request = request_stock(
            item=serializer.validated_data["item"],
            quantity=serializer.validated_data["quantity"],
            user=request.user,
        )

        return Response(
            {
                "detail": "Stock request submitted to store.",
                "request": StockRequestSerializer(stock_request).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BlendingStockListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        blending_stock = (
            BlendingStock.objects.select_related("item")
            .filter(quantity__gt=STOCK_ZERO)
            .order_by("item__item_name", "item_id")
        )
        return Response(BlendingStockSerializer(blending_stock, many=True).data)
