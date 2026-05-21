"""DRF viewsets for WPE master tables and user creation."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Prefetch, ProtectedError, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.admin_master.models import MainScreen, UserScreen
from apps.admin_master.permissions import AdminMasterRBACPermission

from .models import (
    BranchMaster,
    DepartmentMaster,
    LocationMaster,
    PriceBookMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    RoleMaster,
    SaleTypeMaster,
    WarehouseMaster,
    WPEUserCreation,
    WPERolePermission,
    WPEUserScreenPermission,
)
from .serializers import (
    BranchMasterSerializer,
    DepartmentMasterSerializer,
    LocationMasterSerializer,
    PriceBookMasterSerializer,
    ProductTypeCategorySerializer,
    ProductTypeCategoryTreeSerializer,
    ProductTypeSubtypeSerializer,
    ProductionTypeMasterSerializer,
    PurchaseTypeMasterSerializer,
    RoleMasterSerializer,
    SaleTypeMasterSerializer,
    WarehouseMasterSerializer,
    WPEUserCreationReadSerializer,
    WPEUserCreationWriteSerializer,
    PERMISSION_FIELDS,
)
from .pagination import WpeMasterPagination


def _coerce_filter_value(value: str):
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return value


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


class BranchMasterViewSet(BaseMasterViewSet):
    queryset = BranchMaster.objects.all()
    serializer_class = BranchMasterSerializer


class PriceBookMasterViewSet(BaseMasterViewSet):
    queryset = PriceBookMaster.objects.all()
    serializer_class = PriceBookMasterSerializer


class WarehouseMasterViewSet(BaseMasterViewSet):
    queryset = WarehouseMaster.objects.all()
    serializer_class = WarehouseMasterSerializer


class ProductionTypeMasterViewSet(BaseMasterViewSet):
    queryset = ProductionTypeMaster.objects.all()
    serializer_class = ProductionTypeMasterSerializer


class SaleTypeMasterViewSet(BaseMasterViewSet):
    queryset = SaleTypeMaster.objects.all()
    serializer_class = SaleTypeMasterSerializer


class PurchaseTypeMasterViewSet(BaseMasterViewSet):
    queryset = PurchaseTypeMaster.objects.all()
    serializer_class = PurchaseTypeMasterSerializer


class RoleMasterViewSet(BaseMasterViewSet):
    queryset = RoleMaster.objects.all()
    serializer_class = RoleMasterSerializer


class DepartmentMasterViewSet(BaseMasterViewSet):
    queryset = DepartmentMaster.objects.all()
    serializer_class = DepartmentMasterSerializer


class ProductTypeCategoryViewSet(ProductTypeManagedViewSet):
    serializer_class = ProductTypeCategorySerializer
    search_fields = ["name", "code", "description"]

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
        subtype_queryset = ProductTypeSubtype.objects.order_by("sort_order", "name", "id")
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


class ProductTypeSubtypeViewSet(ProductTypeManagedViewSet):
    serializer_class = ProductTypeSubtypeSerializer
    search_fields = ["name", "code", "description", "category__name", "category__code"]
    filterset_map = {
        "category": "category_id",
        "category_id": "category_id",
        "is_active": "is_active",
    }

    def get_queryset(self):
        return ProductTypeSubtype.objects.select_related("category").all()

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


class RolePermissionMatrixView(viewsets.ViewSet):
    """
    Provides a Role × MainScreen permission matrix.
    GET  ?main_screen_id=<id>  → full matrix for that screen (all active roles)
    POST bulk-save/            → upsert permissions for one main screen
    GET  screens/              → list main screens that have active user screens
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def screens(self, request):
        screens = (
            MainScreen.objects.filter(
                status=True,
                user_screens__is_active=True,
            )
            .distinct()
            .order_by("order_no", "name")
            .values("id", "name", "code", "order_no")
        )
        return Response(list(screens))

    @action(detail=False, methods=["get"])
    def matrix(self, request):
        main_screen_id = request.query_params.get("main_screen_id")
        if not main_screen_id:
            return Response({"detail": "main_screen_id query param is required."}, status=400)

        roles = RoleMaster.objects.filter(is_active=True).order_by("name")
        existing = {
            p.role_id: p
            for p in WPERolePermission.objects.filter(main_screen_id=main_screen_id)
        }

        result = []
        for role in roles:
            p = existing.get(role.id)
            row = {"role_id": role.id, "role_name": role.name}
            for field in PERMISSION_FIELDS:
                row[field] = getattr(p, field) if p else False
            result.append(row)

        return Response(result)

    @action(detail=False, methods=["post"], url_path="bulk-save")
    def bulk_save(self, request):
        main_screen_id = request.data.get("main_screen_id")
        permissions = request.data.get("permissions", [])

        if not main_screen_id:
            return Response({"detail": "main_screen_id is required."}, status=400)

        try:
            main_screen = MainScreen.objects.get(pk=main_screen_id)
        except MainScreen.DoesNotExist:
            return Response({"detail": "MainScreen not found."}, status=404)

        with transaction.atomic():
            for item in permissions:
                role_id = item.get("role_id")
                if not role_id:
                    continue
                defaults = {field: bool(item.get(field, False)) for field in PERMISSION_FIELDS}
                WPERolePermission.objects.update_or_create(
                    role_id=role_id,
                    main_screen=main_screen,
                    defaults=defaults,
                )

        return Response({"detail": "Permissions saved successfully."})


class UserScreenPermMatrixView(viewsets.ViewSet):
    """
    Provides a UserScreen permission matrix grouped by MainScreen tabs.
    GET  screens/              → list main screens that have active user screens
    GET  matrix/?main_screen_id=<id>  → all active user screens + their permissions
    POST bulk-save/            → upsert permissions per user_screen
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def screens(self, request):
        screens = (
            MainScreen.objects.filter(
                status=True,
                user_screens__is_active=True,
            )
            .distinct()
            .order_by("order_no", "name")
            .values("id", "name", "code", "order_no")
        )
        return Response(list(screens))

    @action(detail=False, methods=["get"])
    def matrix(self, request):
        main_screen_id = request.query_params.get("main_screen_id")
        if not main_screen_id:
            return Response({"detail": "main_screen_id query param is required."}, status=400)

        user_screens = (
            UserScreen.objects.filter(main_screen_id=main_screen_id, is_active=True)
            .select_related("screen_section")
            .order_by("order_no", "screen_name")
        )
        existing = {
            p.user_screen_id: p
            for p in WPEUserScreenPermission.objects.filter(
                user_screen__main_screen_id=main_screen_id
            )
        }

        result = []
        for us in user_screens:
            p = existing.get(us.id)
            row = {
                "user_screen_id": us.id,
                "screen_name": us.screen_name,
                "screen_section_name": us.screen_section.name if us.screen_section_id else "",
            }
            for field in PERMISSION_FIELDS:
                row[field] = getattr(p, field) if p else False
            result.append(row)

        return Response(result)

    @action(detail=False, methods=["post"], url_path="bulk-save")
    def bulk_save(self, request):
        main_screen_id = request.data.get("main_screen_id")
        permissions = request.data.get("permissions", [])

        if not main_screen_id:
            return Response({"detail": "main_screen_id is required."}, status=400)

        if not MainScreen.objects.filter(pk=main_screen_id).exists():
            return Response({"detail": "MainScreen not found."}, status=404)

        with transaction.atomic():
            for item in permissions:
                user_screen_id = item.get("user_screen_id")
                if not user_screen_id:
                    continue
                defaults = {field: bool(item.get(field, False)) for field in PERMISSION_FIELDS}
                WPEUserScreenPermission.objects.update_or_create(
                    user_screen_id=user_screen_id,
                    defaults=defaults,
                )

        return Response({"detail": "Permissions saved successfully."})
