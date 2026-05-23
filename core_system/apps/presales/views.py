from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from common.drf import QueryParamFilterMixin, StandardResultsSetPagination, success_response
from apps.items.models import Item

from .models import PreSales, PresalesRequest, PresalesRequestItem, PresalesAuditLog
from .serializers import (
    PreSalesSerializer,
    PresalesRequestSerializer,
    PresalesRequestCreateSerializer,
    PresalesAuditLogSerializer,
)


class PreSalesViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PreSales.objects.all().order_by("-id")
    serializer_class = PreSalesSerializer


class PresalesRequestListCreateAPIView(QueryParamFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PresalesRequestSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ("request_no", "request_person", "department", "customer_name")
    ordering_fields = ("request_date", "status", "created_at", "id")
    filterset_map = {
        "status": "status",
        "category": "category",
        "department": "department",
    }

    def get_queryset(self):
        qs = PresalesRequest.objects.select_related(
            "submitted_by", "approved_by", "created_by"
        ).prefetch_related("items__item").order_by("-created_at")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(request_date__gte=date_from)
        if date_to:
            qs = qs.filter(request_date__lte=date_to)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return success_response(
                message="Presales requests fetched successfully.",
                data=self.paginator.get_paginated_data(serializer.data),
            )
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Presales requests fetched successfully.",
            data={"count": queryset.count(), "results": serializer.data},
        )

    def post(self, request, *args, **kwargs):
        write_ser = PresalesRequestCreateSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        vd = write_ser.validated_data

        pr = PresalesRequest.objects.create(
            request_date=vd["request_date"],
            category=vd["category"],
            request_person=vd["request_person"],
            department=vd["department"],
            required_reason=vd["required_reason"],
            customer_type=vd.get("customer_type", "ADDITIVE_MO"),
            customer_name=vd.get("customer_name", ""),
            remarks=vd.get("remarks", ""),
            created_by=request.user,
        )
        for item_data in vd["items"]:
            item = get_object_or_404(Item, pk=item_data["item_id"])
            PresalesRequestItem.objects.create(
                presales_request=pr,
                item=item,
                quantity=item_data["quantity"],
                unit=item_data.get("unit", "") or item.unit or "",
                remarks=item_data.get("remarks", ""),
            )
        PresalesAuditLog.objects.create(
            presales_request=pr, action="CREATED", performed_by=request.user, notes="Request created.",
        )
        pr.refresh_from_db()
        return success_response(
            message="Presales request created successfully.",
            data=PresalesRequestSerializer(
                PresalesRequest.objects.select_related("submitted_by", "approved_by", "created_by")
                .prefetch_related("items__item")
                .get(pk=pr.pk)
            ).data,
            status_code=status.HTTP_201_CREATED,
        )


class PresalesRequestDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PresalesRequestSerializer

    def get_queryset(self):
        return PresalesRequest.objects.select_related(
            "submitted_by", "approved_by", "created_by"
        ).prefetch_related("items__item")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(
            message="Presales request fetched successfully.",
            data=PresalesRequestSerializer(instance).data,
        )

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in (PresalesRequest.Status.DRAFT, PresalesRequest.Status.REJECTED):
            return success_response(
                message="Only DRAFT or REJECTED requests can be edited.", data={}, status_code=400,
            )
        write_ser = PresalesRequestCreateSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        vd = write_ser.validated_data

        for field in ("request_date", "category", "request_person", "department", "required_reason"):
            setattr(instance, field, vd[field])
        instance.customer_type = vd.get("customer_type", "ADDITIVE_MO")
        instance.customer_name = vd.get("customer_name", "")
        instance.remarks = vd.get("remarks", "")
        instance.save()

        instance.items.all().delete()
        for item_data in vd["items"]:
            item = get_object_or_404(Item, pk=item_data["item_id"])
            PresalesRequestItem.objects.create(
                presales_request=instance, item=item,
                quantity=item_data["quantity"],
                unit=item_data.get("unit", "") or item.unit or "",
                remarks=item_data.get("remarks", ""),
            )
        PresalesAuditLog.objects.create(
            presales_request=instance, action="UPDATED", performed_by=request.user, notes="Request updated.",
        )
        instance.refresh_from_db()
        return success_response(
            message="Presales request updated successfully.",
            data=PresalesRequestSerializer(
                PresalesRequest.objects.select_related("submitted_by", "approved_by", "created_by")
                .prefetch_related("items__item").get(pk=instance.pk)
            ).data,
        )


class PresalesRequestSubmitAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        pr = get_object_or_404(PresalesRequest, pk=pk)
        if pr.status != PresalesRequest.Status.DRAFT:
            return success_response(message="Only DRAFT requests can be submitted.", data={}, status_code=400)
        pr.status = PresalesRequest.Status.SUBMITTED
        pr.submitted_by = request.user
        pr.submitted_at = timezone.now()
        pr.save()
        PresalesAuditLog.objects.create(presales_request=pr, action="SUBMITTED", performed_by=request.user, notes="Submitted for approval.")
        return success_response(message="Request submitted for approval.", data=PresalesRequestSerializer(pr).data)


class PresalesRequestApproveAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        pr = get_object_or_404(PresalesRequest, pk=pk)
        if pr.status != PresalesRequest.Status.SUBMITTED:
            return success_response(message="Only SUBMITTED requests can be approved.", data={}, status_code=400)
        remarks = request.data.get("approval_remarks", "")
        pr.status = PresalesRequest.Status.APPROVED
        pr.approved_by = request.user
        pr.approved_at = timezone.now()
        pr.approval_remarks = remarks
        pr.save()
        PresalesAuditLog.objects.create(presales_request=pr, action="APPROVED", performed_by=request.user, notes=remarks or "Approved.")
        return success_response(message="Request approved.", data=PresalesRequestSerializer(pr).data)


class PresalesRequestRejectAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        pr = get_object_or_404(PresalesRequest, pk=pk)
        if pr.status != PresalesRequest.Status.SUBMITTED:
            return success_response(message="Only SUBMITTED requests can be rejected.", data={}, status_code=400)
        remarks = request.data.get("approval_remarks", "").strip()
        if not remarks:
            return success_response(message="Rejection remarks are required.", data={}, status_code=400)
        pr.status = PresalesRequest.Status.REJECTED
        pr.approved_by = request.user
        pr.approved_at = timezone.now()
        pr.approval_remarks = remarks
        pr.save()
        PresalesAuditLog.objects.create(presales_request=pr, action="REJECTED", performed_by=request.user, notes=remarks)
        return success_response(message="Request rejected.", data=PresalesRequestSerializer(pr).data)


class PresalesRequestSendToProductionAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        pr = get_object_or_404(PresalesRequest, pk=pk)
        if pr.status != PresalesRequest.Status.APPROVED:
            return success_response(message="Only APPROVED requests can be sent to production.", data={}, status_code=400)
        pr.status = PresalesRequest.Status.SENT_TO_PRODUCTION
        pr.sent_to_prod_by = request.user
        pr.sent_to_prod_at = timezone.now()
        pr.save()
        PresalesAuditLog.objects.create(presales_request=pr, action="SENT_TO_PRODUCTION", performed_by=request.user, notes="Sent to production queue.")
        return success_response(message="Request sent to production.", data=PresalesRequestSerializer(pr).data)


class PresalesRequestAuditLogAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PresalesAuditLogSerializer

    def get_queryset(self):
        return PresalesAuditLog.objects.filter(presales_request_id=self.kwargs["pk"]).select_related("performed_by")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return success_response(message="Audit log fetched.", data=list(PresalesAuditLogSerializer(qs, many=True).data))


class PresalesDashboardAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        qs = PresalesRequest.objects
        return success_response(message="Dashboard fetched.", data={
            "draft": qs.filter(status="DRAFT").count(),
            "submitted": qs.filter(status="SUBMITTED").count(),
            "approved": qs.filter(status="APPROVED").count(),
            "rejected": qs.filter(status="REJECTED").count(),
            "sent_to_production": qs.filter(status="SENT_TO_PRODUCTION").count(),
            "total": qs.count(),
        })
