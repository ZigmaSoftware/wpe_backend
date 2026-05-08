from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.items.models import STOCK_ZERO
from rest_framework.exceptions import ValidationError

from apps.store.models import StockRequest
from apps.store.serializers import StockRequestSerializer
from apps.store.services import request_stock

from .models import BlendingStock
from .serializers import BlendingAdditiveRequestSerializer, BlendingStockSerializer
from .services import BLENDING_DEPARTMENT, is_additive_item


class RequestBlendingStockAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = BlendingAdditiveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = serializer.validated_data["item"]
        if not is_additive_item(item):
            raise ValidationError({"item_id": "Only additive items can be requested through the blending additive flow."})

        stock_request = request_stock(
            item=item,
            quantity=serializer.validated_data["quantity"],
            user=request.user,
            request_type=StockRequest.RequestType.ADDITIVE,
            department=serializer.validated_data.get("department") or BLENDING_DEPARTMENT,
            requested_for_name=serializer.validated_data["requested_for_name"],
            request_reason=serializer.validated_data["request_reason"],
        )

        return Response(
            {
                "detail": "Additive store request submitted to store.",
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
