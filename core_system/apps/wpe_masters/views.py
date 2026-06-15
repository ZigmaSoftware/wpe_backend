"""DRF viewsets for WPE master tables and user creation."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Prefetch, ProtectedError, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.admin_master.permissions import AdminMasterRBACPermission
from apps.common_master.services import build_running_number

from .models import (
    BranchMaster,
    DepartmentMaster,
    DesignationMaster,
    ItemMaster,
    LocationMaster,
    PrinterMaster,
    PriceBookMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    QRLabelTemplateMaster,
    RoleMaster,
    SaleTypeMaster,
    SerialPortConfigurationMaster,
    StoreMaster,
    UnitMaster,
    WarehouseMaster,
    WeighmentScaleMaster,
    WPEUserCreation,
)
from .serializers import (
    BranchMasterSerializer,
    DepartmentMasterSerializer,
    DesignationMasterSerializer,
    ItemMasterSerializer,
    LocationMasterSerializer,
    PrinterMasterSerializer,
    PriceBookMasterSerializer,
    ProductTypeCategorySerializer,
    ProductTypeCategoryTreeSerializer,
    ProductTypeSubtypeSerializer,
    ProductionTypeMasterSerializer,
    PurchaseTypeMasterSerializer,
    QRLabelTemplateMasterSerializer,
    RoleMasterSerializer,
    SaleTypeMasterSerializer,
    SerialPortConfigurationMasterSerializer,
    StoreMasterSerializer,
    UnitMasterSerializer,
    WarehouseMasterSerializer,
    WeighmentScaleMasterSerializer,
    WPEUserCreationReadSerializer,
    WPEUserCreationWriteSerializer,
)
from .pagination import WpeMasterPagination


def _coerce_filter_value(value: str):
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return value


def _next_code_response(model_cls, *, field_name: str, prefix: str, width: int) -> Response:
    with transaction.atomic():
        code = build_running_number(
            model_cls,
            field_name=field_name,
            prefix=prefix,
            width=width,
        )
    return Response({"code": code})


class QueryParamFilterMixin:
    filterset_map: dict[str, str] = {}

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        search_value = (
            self.request.query_params.get("search[value]")
            if not self.request.query_params.get("search")
            else None
        )
        if search_value:
            query = Q()
            for field_name in getattr(self, "search_fields", ()):
                if field_name.startswith(("^", "=", "@", "$")):
                    field_name = field_name[1:]
                query |= Q(**{f"{field_name}__icontains": search_value})
            queryset = queryset.filter(query)

        for param, lookup in self.filterset_map.items():
            value = self.request.query_params.get(param)
            if value in (None, ""):
                continue
            queryset = queryset.filter(**{lookup: _coerce_filter_value(value)})

        return queryset


class BaseMasterViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = WpeMasterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "is_active"]
    ordering = ["name"]
    filterset_map = {
        "is_active": "is_active",
    }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        qs = self.get_queryset().filter(is_active=True).values("id", "name")
        return Response(list(qs))

    @action(detail=True, methods=["patch"], url_path="toggle")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        instance.is_active = not instance.is_active
        instance.save(update_fields=["is_active", "updated_at"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete: this record is referenced by other data."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CodeTrackedMasterViewSet(BaseMasterViewSet):
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at", "is_active"]
    next_code_prefix: str | None = None
    next_code_width = 3

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.get_queryset().filter(is_active=True).values("id", "name", "code")
        return Response(list(queryset))

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        if not self.next_code_prefix:
            return Response({"detail": "Next code preview is not configured for this resource."}, status=status.HTTP_404_NOT_FOUND)
        return _next_code_response(
            self.get_queryset().model,
            field_name="code",
            prefix=self.next_code_prefix,
            width=self.next_code_width,
        )


class ProductTypeManagedViewSet(BaseMasterViewSet):
    permission_classes = [AdminMasterRBACPermission]
    permission_screen_code = "wpe-product-type-master"
    ordering_fields = ["sort_order", "name", "code", "is_active", "created_at"]
    ordering = ["sort_order", "name"]
    filterset_map = {
        "is_active": "is_active",
    }


class LocationMasterViewSet(BaseMasterViewSet):
    queryset = LocationMaster.objects.all()
    serializer_class = LocationMasterSerializer
    filterset_map = {
        "center_type": "center_type",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values("id", "name")
        return Response(list(queryset))


class BranchMasterViewSet(BaseMasterViewSet):
    queryset = BranchMaster.objects.all()
    serializer_class = BranchMasterSerializer


class PriceBookMasterViewSet(BaseMasterViewSet):
    queryset = PriceBookMaster.objects.all()
    serializer_class = PriceBookMasterSerializer


class WarehouseMasterViewSet(CodeTrackedMasterViewSet):
    queryset = WarehouseMaster.objects.all()
    serializer_class = WarehouseMasterSerializer
    search_fields = ["name", "code", "warehouse_type", "description"]
    ordering_fields = ["name", "code", "warehouse_type", "created_at", "is_active"]
    next_code_prefix = "WH"


class ProductionTypeMasterViewSet(BaseMasterViewSet):
    queryset = ProductionTypeMaster.objects.all()
    serializer_class = ProductionTypeMasterSerializer


class SaleTypeMasterViewSet(BaseMasterViewSet):
    queryset = SaleTypeMaster.objects.all()
    serializer_class = SaleTypeMasterSerializer


class PurchaseTypeMasterViewSet(BaseMasterViewSet):
    queryset = PurchaseTypeMaster.objects.all()
    serializer_class = PurchaseTypeMasterSerializer


class StoreMasterViewSet(CodeTrackedMasterViewSet):
    queryset = StoreMaster.objects.all()
    serializer_class = StoreMasterSerializer
    next_code_prefix = "STORE"


class DepartmentMasterViewSet(CodeTrackedMasterViewSet):
    queryset = DepartmentMaster.objects.select_related("department_head").all()
    serializer_class = DepartmentMasterSerializer
    search_fields = ["name", "code", "description", "department_head__full_name", "department_head__user__username"]
    next_code_prefix = "DEPT"


class DesignationMasterViewSet(CodeTrackedMasterViewSet):
    queryset = DesignationMaster.objects.select_related("department").all()
    serializer_class = DesignationMasterSerializer
    search_fields = ["name", "code", "description", "department__name"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "is_active": "is_active",
    }
    ordering_fields = ["department__name", "name", "code", "created_at", "is_active"]
    ordering = ["department__name", "name"]
    next_code_prefix = "DES"

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True)
        return Response(
            [
                {
                    "id": designation.id,
                    "name": designation.name,
                    "code": designation.code,
                    "department_id": designation.department_id,
                    "department_name": getattr(designation.department, "name", None),
                }
                for designation in queryset
            ]
        )


class RoleMasterViewSet(CodeTrackedMasterViewSet):
    queryset = RoleMaster.objects.select_related("designation", "designation__department").all()
    serializer_class = RoleMasterSerializer
    search_fields = ["name", "code", "description", "designation__name", "designation__department__name"]
    filterset_map = {
        "designation": "designation_id",
        "designation_id": "designation_id",
        "department": "designation__department_id",
        "department_id": "designation__department_id",
        "is_active": "is_active",
    }
    ordering_fields = ["designation__name", "name", "code", "created_at", "is_active"]
    ordering = ["designation__name", "name"]
    next_code_prefix = "ROLE"

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True)
        return Response(
            [
                {
                    "id": role.id,
                    "name": role.name,
                    "code": role.code,
                    "designation_id": role.designation_id,
                    "designation_name": getattr(role.designation, "name", None),
                    "department_id": getattr(getattr(role.designation, "department", None), "id", None),
                    "department_name": getattr(getattr(role.designation, "department", None), "name", None),
                }
                for role in queryset
            ]
        )


class UnitMasterViewSet(BaseMasterViewSet):
    queryset = UnitMaster.objects.all()
    serializer_class = UnitMasterSerializer
    search_fields = ["name", "uom_code"]
    ordering_fields = ["name", "uom_code", "decimal_places", "created_at", "is_active"]
    ordering = ["name"]

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = self.get_queryset().filter(is_active=True).values("id", "name", "uom_code", "decimal_allowed", "decimal_places")
        return Response(list(queryset))


class ItemMasterViewSet(BaseMasterViewSet):
    queryset = ItemMaster.objects.select_related("sub_category", "sub_category__category", "uom").all()
    serializer_class = ItemMasterSerializer
    search_fields = [
        "item_name",
        "item_code",
        "sub_category__name",
        "sub_category__category__name",
        "uom__uom_code",
        "uom__name",
    ]
    ordering_fields = ["item_name", "item_code", "item_type", "created_at", "is_active"]
    ordering = ["item_name", "id"]
    filterset_map = {
        "sub_category": "sub_category_id",
        "sub_category_id": "sub_category_id",
        "category": "sub_category__category_id",
        "category_id": "sub_category__category_id",
        "uom": "uom_id",
        "uom_id": "uom_id",
        "item_type": "item_type",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(is_active=True, sub_category__is_active=True, sub_category__category__is_active=True, uom__is_active=True)
            .values("id", "item_name", "item_code")
        )
        return Response(
            [{"id": row["id"], "name": row["item_name"], "code": row["item_code"]} for row in queryset]
        )

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(ItemMaster, field_name="item_code", prefix="RM", width=3)


class WeighmentScaleMasterViewSet(CodeTrackedMasterViewSet):
    queryset = WeighmentScaleMaster.objects.select_related("department", "machine", "unit").all()
    serializer_class = WeighmentScaleMasterSerializer
    search_fields = ["name", "code", "department__name", "machine__name", "machine__machine_code", "port_name"]
    ordering_fields = ["name", "code", "department__name", "machine__name", "created_at", "is_active"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "machine": "machine_id",
        "machine_id": "machine_id",
        "unit": "unit_id",
        "unit_id": "unit_id",
        "connection_type": "connection_type",
        "is_auto_capture": "is_auto_capture",
        "is_active": "is_active",
    }
    next_code_prefix = "SCALE"


class PrinterMasterViewSet(CodeTrackedMasterViewSet):
    queryset = PrinterMaster.objects.select_related("department").all()
    serializer_class = PrinterMasterSerializer
    search_fields = ["name", "code", "printer_type", "department__name", "connection_type", "ip_address", "paper_size"]
    ordering_fields = ["name", "code", "printer_type", "department__name", "created_at", "is_active"]
    filterset_map = {
        "department": "department_id",
        "department_id": "department_id",
        "printer_type": "printer_type",
        "connection_type": "connection_type",
        "is_active": "is_active",
    }
    next_code_prefix = "PRN"


class QRLabelTemplateMasterViewSet(CodeTrackedMasterViewSet):
    queryset = QRLabelTemplateMaster.objects.select_related("printer", "printer__department").all()
    serializer_class = QRLabelTemplateMasterSerializer
    search_fields = ["name", "code", "label_type", "printer__name", "printer__code", "qr_data_format"]
    ordering_fields = ["name", "code", "label_type", "printer__name", "created_at", "is_active"]
    filterset_map = {
        "printer": "printer_id",
        "printer_id": "printer_id",
        "label_type": "label_type",
        "qr_data_format": "qr_data_format",
        "is_active": "is_active",
    }
    next_code_prefix = "QR"


class SerialPortConfigurationMasterViewSet(CodeTrackedMasterViewSet):
    queryset = SerialPortConfigurationMaster.objects.all()
    serializer_class = SerialPortConfigurationMasterSerializer
    search_fields = ["name", "code", "port_name", "read_format"]
    ordering_fields = ["name", "code", "port_name", "created_at", "is_active"]
    filterset_map = {
        "read_format": "read_format",
        "is_active": "is_active",
    }
    next_code_prefix = "SERIAL"


class ProductTypeCategoryViewSet(ProductTypeManagedViewSet):
    serializer_class = ProductTypeCategorySerializer
    search_fields = ["name", "code", "description"]

    @property
    def permission_screen_codes(self):
        if getattr(self, "action", None) in {"list", "retrieve", "lookup", "tree"}:
            return ("wpe-product-type-master", "wpe-product-subtype-master", "item-creation-master")
        return ("wpe-product-type-master",)

    def get_queryset(self):
        return ProductTypeCategory.objects.annotate(
            subtype_count=Count("subtypes", distinct=True)
        ).all()

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(is_active=True)
            .values("id", "name", "code", "sort_order")
            .order_by("sort_order", "name", "id")
        )
        return Response(list(queryset))

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        subtype_queryset = ProductTypeSubtype.objects.annotate(
            variant_count=Count("items", distinct=True)
        ).order_by("sort_order", "name", "id")
        if request.query_params.get("subtypes_is_active") not in (None, ""):
            subtype_queryset = subtype_queryset.filter(
                is_active=_coerce_filter_value(request.query_params["subtypes_is_active"])
            )

        queryset = self.filter_queryset(
            self.get_queryset().prefetch_related(
                Prefetch(
                    "subtypes",
                    queryset=subtype_queryset,
                    to_attr="prefetched_subtypes",
                )
            )
        )
        serializer = ProductTypeCategoryTreeSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(ProductTypeCategory, field_name="code", prefix="CAT", width=3)


class ProductTypeSubtypeViewSet(ProductTypeManagedViewSet):
    serializer_class = ProductTypeSubtypeSerializer
    search_fields = ["name", "code", "description", "category__name", "category__code"]
    filterset_map = {
        "category": "category_id",
        "category_id": "category_id",
        "is_active": "is_active",
    }

    @property
    def permission_screen_codes(self):
        if getattr(self, "action", None) in {"list", "retrieve", "lookup"}:
            return ("wpe-product-type-master", "wpe-product-subtype-master", "item-creation-master")
        return ("wpe-product-subtype-master",)

    def get_queryset(self):
        return ProductTypeSubtype.objects.select_related("category").annotate(
            variant_count=Count("items", distinct=True)
        ).all()

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(is_active=True, category__is_active=True)
            .values("id", "name", "code", "category_id", "category__name", "sort_order")
            .order_by("category__sort_order", "category__name", "sort_order", "name", "id")
        )

        return Response(
            [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "code": row["code"],
                    "category": row["category_id"],
                    "category_name": row["category__name"],
                    "sort_order": row["sort_order"],
                }
                for row in queryset
            ]
        )

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return _next_code_response(ProductTypeSubtype, field_name="code", prefix="SUB", width=3)


class WPEUserCreationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = WpeMasterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "email", "phone_no", "user__username"]
    ordering_fields = ["full_name", "created_at", "is_active"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return WPEUserCreation.objects.select_related(
            "user", "location", "default_branch", "role"
        ).prefetch_related(
            "authorized_branches",
            "authorized_price_books",
            "authorized_warehouses",
            "authorized_production_types",
            "authorized_sale_types",
            "authorized_purchase_types",
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return WPEUserCreationWriteSerializer
        return WPEUserCreationReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        read_serializer = WPEUserCreationReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        read_serializer = WPEUserCreationReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)

    @action(detail=True, methods=["patch"], url_path="toggle")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        instance.is_active = not instance.is_active
        instance.save(update_fields=["is_active", "updated_at"])
        if instance.user_id:
            instance.user.is_active = instance.is_active
            instance.user.save(update_fields=["is_active"])
        read_serializer = WPEUserCreationReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            if instance.user_id:
                instance.user.delete()
            else:
                instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete: this user is referenced by other data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        queryset = (
            self.get_queryset()
            .filter(is_active=True)
            .values("id", "full_name", "user__username")
            .order_by("full_name", "id")
        )
        return Response(
            [
                {
                    "id": row["id"],
                    "name": row["full_name"],
                    "username": row["user__username"],
                }
                for row in queryset
            ]
        )
