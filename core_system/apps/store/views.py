from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blending.serializers import BlendingStockSerializer
from apps.items.serializers import ItemStockTransactionSerializer

from .models import StockRequest, StoreStock, StoreTransaction
from .serializers import StockRequestSerializer, StoreStockSerializer, StoreTransactionSerializer
from .services import approve_stock_request, reject_stock_request, request_stock


class StoreStockRequestAPIView(APIView):
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


class ApproveStockRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int, *args, **kwargs):
        try:
            approval_result = approve_stock_request(pk, request.user)
        except StockRequest.DoesNotExist:
            return Response({"detail": "Stock request not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "detail": "Stock request approved.",
                "request": StockRequestSerializer(approval_result["stock_request"]).data,
                "store_stock": StoreStockSerializer(approval_result["store_stock"]).data,
                "blending_stock": BlendingStockSerializer(approval_result["blending_stock"]).data,
                "store_transaction": StoreTransactionSerializer(approval_result["store_transaction"]).data,
                "item_transactions": ItemStockTransactionSerializer(
                    approval_result["item_transactions"],
                    many=True,
                ).data,
            }
        )


class RejectStockRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int, *args, **kwargs):
        try:
            stock_request = reject_stock_request(pk)
        except StockRequest.DoesNotExist:
            return Response({"detail": "Stock request not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "detail": "Stock request rejected.",
                "request": StockRequestSerializer(stock_request).data,
            }
        )


class StoreStockListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        queryset = StoreStock.objects.select_related("item").order_by("item__item_name", "item_id")
        return Response(StoreStockSerializer(queryset, many=True).data)


class StoreTransactionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        queryset = StoreTransaction.objects.select_related("item").order_by("-created_at", "-id")
        return Response(StoreTransactionSerializer(queryset, many=True).data)
