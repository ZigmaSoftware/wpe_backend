from __future__ import annotations

from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response

from apps.store.inventory_monitoring import BaseInventoryHistoryAPIView, BaseInventorySummaryAPIView
from apps.store.models import StockRequest
from apps.store.selectors import availability_map_for_requests, store_request_queryset
from apps.store.serializers import (
    StockRequestCancelSerializer,
    StockRequestCreateSerializer,
    StockRequestSerializer,
)
from apps.store.services import request_stock

from .permissions import IsBlendingUser
from .serializers import (
    BlendingAdditiveRequestSerializer,
    BlendingStockSerializer,
)
from .services import (
    BLENDING_DEPARTMENT,
    blending_stock_queryset,
    cancel_blending_store_request,
    create_blending_store_request,
    get_blending_warehouse,
    requestable_additive_stock_queryset,
    update_blending_store_request,
)


class WrappedBlendingListAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    list_message = "Records fetched successfully."

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return success_response(
                message=self.list_message,
                data=self.paginator.get_paginated_data(serializer.data),
            )

        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message=self.list_message,
            data={"count": len(serializer.data), "results": serializer.data},
        )


class RequestBlendingStockAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    serializer_class = BlendingAdditiveRequestSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = (
        "item__item_code",
        "item__item_name",
        "item__category",
        "item__group",
        "item__sub_group",
        "warehouse__code",
        "warehouse__name",
    )
    ordering_fields = ("available_qty", "updated_at", "item__item_name", "id")

    def get_serializer_class(self):
        if self.request.method == "GET":
            return BlendingStockSerializer
        return BlendingAdditiveRequestSerializer

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(requestable_additive_stock_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)

        if page is not None:
            return success_response(
                message="Requestable store stock fetched successfully.",
                data=self.paginator.get_paginated_data(serializer.data),
            )

        return success_response(
            message="Requestable store stock fetched successfully.",
            data={"count": len(serializer.data), "results": serializer.data},
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = serializer.validated_data["item"]
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
                "detail": "Store request submitted to store.",
                "request": StockRequestSerializer(
                    stock_request,
                    context={"availability_map": availability_map_for_requests([stock_request])},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BlendingStoreRequestListCreateAPIView(WrappedBlendingListAPIView, generics.CreateAPIView):
    serializer_class = StockRequestSerializer
    search_fields = ("request_no", "requested_by__username", "items__item__item_name", "items__item__item_code")
    ordering_fields = ("requested_at", "request_no", "status", "id")
    filterset_map = {
        "status": "status",
        "requested_by": "requested_by_id",
        "request_type": "request_type",
        "department": "department",
    }
    list_message = "Blending store requests fetched successfully."

    def get_queryset(self):
        queryset = store_request_queryset().filter(requesting_warehouse=get_blending_warehouse())
        request_no = self.request.query_params.get("request_no")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if request_no:
            queryset = queryset.filter(request_no__icontains=request_no)
        if date_from:
            queryset = queryset.filter(requested_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(requested_at__date__lte=date_to)
        return queryset.distinct()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StockRequestCreateSerializer
        return StockRequestSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method != "POST":
            if hasattr(self, "paginator") and getattr(self, "paginator", None) and getattr(self.paginator, "page", None):
                request_rows = list(self.paginator.page.object_list)
            else:
                request_rows = list(self.filter_queryset(self.get_queryset()))
            context["availability_map"] = availability_map_for_requests(request_rows)
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_request = create_blending_store_request(
            requested_by=request.user,
            items=[
                {
                    "item": row["item"],
                    "quantity": row["quantity"],
                    "remarks": row.get("remarks"),
                }
                for row in serializer.validated_data["items"]
            ],
            remarks=serializer.validated_data.get("remarks"),
            request_type=serializer.validated_data.get("request_type", StockRequest.RequestType.GENERAL),
            department=serializer.validated_data.get("department", BLENDING_DEPARTMENT),
            requested_for_name=serializer.validated_data.get("requested_for_name", ""),
            request_reason=serializer.validated_data.get("request_reason", ""),
        )
        response_serializer = StockRequestSerializer(
            stock_request,
            context={"availability_map": availability_map_for_requests([stock_request])},
        )
        return success_response(
            message="Store request created successfully.",
            data=response_serializer.data,
            status_code=status.HTTP_201_CREATED,
        )


class BlendingStoreRequestDetailAPIView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    serializer_class = StockRequestSerializer

    def get_queryset(self):
        return store_request_queryset().filter(requesting_warehouse=get_blending_warehouse())

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return StockRequestCreateSerializer
        return StockRequestSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            context={
                **self.get_serializer_context(),
                "availability_map": availability_map_for_requests([instance]),
            },
        )
        return success_response(message="Store request fetched successfully.", data=serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        stock_request = update_blending_store_request(
            instance.pk,
            requested_by=request.user,
            items=[
                {
                    "item": row["item"],
                    "quantity": row["quantity"],
                    "remarks": row.get("remarks"),
                }
                for row in serializer.validated_data["items"]
            ],
            remarks=serializer.validated_data.get("remarks"),
            request_type=serializer.validated_data.get("request_type", StockRequest.RequestType.GENERAL),
            department=serializer.validated_data.get("department", BLENDING_DEPARTMENT),
            requested_for_name=serializer.validated_data.get("requested_for_name", ""),
            request_reason=serializer.validated_data.get("request_reason", ""),
        )
        response_serializer = StockRequestSerializer(
            stock_request,
            context={"availability_map": availability_map_for_requests([stock_request])},
        )
        return success_response(
            message="Store request updated successfully.",
            data=response_serializer.data,
        )


class CancelBlendingStoreRequestAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    serializer_class = StockRequestCancelSerializer

    def post(self, request, pk: int, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_request = cancel_blending_store_request(
            pk,
            request.user,
            remarks=serializer.validated_data.get("remarks"),
        )
        response_serializer = StockRequestSerializer(
            stock_request,
            context={"availability_map": availability_map_for_requests([stock_request])},
        )
        return success_response(
            message="Store request cancelled successfully.",
            data=response_serializer.data,
        )


class BlendingInventorySummaryAPIView(BaseInventorySummaryAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    list_message = "Blending inventory summary fetched successfully."

    def get_warehouse(self):
        return get_blending_warehouse()


class BlendingInventoryHistoryAPIView(BaseInventoryHistoryAPIView):
    permission_classes = [IsAuthenticated, IsBlendingUser]
    list_message = "Blending inventory history fetched successfully."

    def get_warehouse(self):
        return get_blending_warehouse()


class BlendingStockListAPIView(WrappedBlendingListAPIView):
    serializer_class = BlendingStockSerializer
    search_fields = ("item__item_code", "item__item_name", "warehouse__code", "warehouse__name")
    ordering_fields = ("available_qty", "updated_at", "item__item_name", "id")
    filterset_map = {
        "item": "item_id",
        "item_id": "item_id",
    }
    list_message = "Blending stock fetched successfully."

    def get_queryset(self):
        stock_scope = (self.request.query_params.get("stock_scope") or "").strip().lower()
        if stock_scope in {"requestable", "requestable_additives", "store_additives"}:
            return requestable_additive_stock_queryset()
        return blending_stock_queryset()


class BlendingRequestableAdditiveStockListAPIView(WrappedBlendingListAPIView):
    serializer_class = BlendingStockSerializer
    search_fields = (
        "item__item_code",
        "item__item_name",
        "item__category",
        "item__group",
        "item__sub_group",
        "warehouse__code",
        "warehouse__name",
    )
    ordering_fields = ("available_qty", "updated_at", "item__item_name", "id")
    filterset_map = {
        "item": "item_id",
        "item_id": "item_id",
    }
    list_message = "Requestable store stock fetched successfully."

    def get_queryset(self):
        return requestable_additive_stock_queryset()
