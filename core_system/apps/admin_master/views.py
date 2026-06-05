"""DRF viewsets for admin master masters, user creation, and RBAC APIs."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import MainScreen, ScreenSection, Staff, UserCreation, UserScreen, UserType, UserTypePermission
from .pagination import AdminMasterPagination
from .permissions import AdminMasterRBACPermission
from .serializers import (
    MainScreenSerializer,
    PermissionAssignmentSerializer,
    ScreenSectionSerializer,
    StaffSerializer,
    UserCreationReadSerializer,
    UserCreationWriteSerializer,
    UserScreenSerializer,
    UserTypePermissionSerializer,
    UserTypePermissionSummarySerializer,
    UserTypeSerializer,
)
from .services import resolve_subject_permissions
from .services import delete_user_creation


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


class StandardizedModelViewSet(QueryParamFilterMixin, viewsets.ModelViewSet):
    permission_classes = [AdminMasterRBACPermission]
    pagination_class = AdminMasterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    resource_name = "Record"
    status_field = "is_active"
    response_serializer_class = None

    def get_response_serializer_class(self):
        return self.response_serializer_class or self.get_serializer_class()

    def serialize_instance(self, instance):
        serializer_class = self.get_response_serializer_class()
        serializer = serializer_class(instance, context=self.get_serializer_context())
        return serializer.data

    def list(self, request, *args, **kwargs):
        base_queryset = self.get_queryset()
        total_count = base_queryset.count()
        filtered_queryset = self.filter_queryset(base_queryset)
        filtered_count = filtered_queryset.count()

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if getattr(self.paginator, "datatables_mode", False):
                response.data["recordsTotal"] = total_count
                response.data["recordsFiltered"] = filtered_count
            return response

        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data if isinstance(serializer.data, dict) else {})
        return Response(
            {
                "message": f"{self.resource_name} created successfully.",
                "data": self.serialize_instance(serializer.instance),
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {
                "message": f"{self.resource_name} updated successfully.",
                "data": self.serialize_instance(serializer.instance),
            }
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            raise ValidationError(
                {"detail": f"{self.resource_name} cannot be deleted because dependent records exist."}
            )
        return Response({"message": f"{self.resource_name} deleted successfully."})

    @action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        field_name = self.status_field
        new_value = not bool(getattr(instance, field_name))
        setattr(instance, field_name, new_value)
        instance.save(update_fields=[field_name])
        return Response({"message": f"{self.resource_name} status updated.", "status": new_value})


class MainScreenViewSet(StandardizedModelViewSet):
    queryset = MainScreen.objects.all().order_by("order_no", "name", "id")
    serializer_class = MainScreenSerializer
    resource_name = "Main screen"
    permission_screen_code = "main-screen-master"
    status_field = "status"
    search_fields = ("name", "code")
    ordering_fields = ("order_no", "name", "id")
    filterset_map = {
        "is_active": "status",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.get_queryset().filter(status=True).values("id", "name", "code", "order_no")
        return Response(list(queryset))


class ScreenSectionViewSet(StandardizedModelViewSet):
    queryset = ScreenSection.objects.select_related("main_screen").all().order_by(
        "main_screen__order_no",
        "order_no",
        "name",
        "id",
    )
    serializer_class = ScreenSectionSerializer
    resource_name = "Screen section"
    permission_screen_code = "screen-section-master"
    search_fields = ("name", "code", "description", "main_screen__name")
    ordering_fields = ("order_no", "name", "main_screen__order_no", "id")
    filterset_map = {
        "main_screen": "main_screen_id",
        "main_screen_id": "main_screen_id",
        "is_active": "is_active",
        "code": "code",
    }

    def list(self, request, *args, **kwargs):
        if request.query_params.get("main_screen_id") and not any(
            param in request.query_params for param in ("draw", "page", "page_size", "search")
        ):
            queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values(
                "id",
                "name",
                "code",
                "main_screen_id",
                "order_no",
            )
            return Response(list(queryset))
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values(
            "id",
            "name",
            "code",
            "main_screen_id",
            "order_no",
        )
        return Response(list(queryset))


class UserScreenViewSet(StandardizedModelViewSet):
    queryset = UserScreen.objects.select_related("main_screen", "screen_section").all().order_by(
        "main_screen__order_no",
        "screen_section__order_no",
        "order_no",
        "id",
    )
    serializer_class = UserScreenSerializer
    resource_name = "User screen"
    permission_screen_code = "user-screen-master"
    search_fields = (
        "screen_name",
        "code",
        "folder_name",
        "description",
        "main_screen__name",
        "screen_section__name",
    )
    ordering_fields = ("order_no", "screen_name", "main_screen__order_no", "screen_section__order_no", "id")
    filterset_map = {
        "main_screen": "main_screen_id",
        "main_screen_id": "main_screen_id",
        "screen_section": "screen_section_id",
        "screen_section_id": "screen_section_id",
        "is_active": "is_active",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True).values(
            "id",
            "screen_name",
            "code",
            "folder_name",
            "main_screen_id",
            "screen_section_id",
            "order_no",
        )
        return Response(list(queryset))


class UserTypeViewSet(StandardizedModelViewSet):
    queryset = UserType.objects.select_related("department", "role").all().order_by(
        "department__name",
        "role__name",
        "id",
    )
    serializer_class = UserTypeSerializer
    resource_name = "User type"
    permission_screen_code = "user-type-master"
    search_fields = ("department__name", "role__name", "name", "code")
    ordering_fields = ("department__name", "role__name", "created_at", "id")
    filterset_map = {
        "is_active": "is_active",
        "department": "department_id",
        "department_id": "department_id",
        "role": "role_id",
        "role_id": "role_id",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_active=True)
        return Response(
            [
                {
                    "id": user_type.id,
                    "name": user_type.name,
                    "code": user_type.code,
                    "department_id": user_type.department_id,
                    "department_name": getattr(user_type.department, "name", None),
                    "role_id": user_type.role_id,
                    "role_name": getattr(user_type.role, "name", None),
                }
                for user_type in queryset
            ]
        )


class StaffViewSet(StandardizedModelViewSet):
    queryset = Staff.objects.select_related("department_master", "role_master").all().order_by("staff_code", "name", "id")
    serializer_class = StaffSerializer
    response_serializer_class = StaffSerializer
    resource_name = "Staff"
    search_fields = (
        "staff_code",
        "name",
        "department_master__name",
        "role_master__name",
        "mobile",
        "email",
        "emergency_contact_no",
    )
    ordering_fields = ("staff_code", "name", "department_master__name", "role_master__name", "id")
    filterset_map = {
        "is_active": "is_active",
        "gender": "gender",
        "department": "department_master_id",
        "department_id": "department_master_id",
        "role": "role_master_id",
        "role_id": "role_master_id",
    }


class UserCreationViewSet(StandardizedModelViewSet):
    queryset = UserCreation.objects.select_related(
        "user",
        "staff",
        "user_type",
        "user_type__department",
        "user_type__role",
        "company",
        "department",
        "role",
    )
    serializer_class = UserCreationReadSerializer
    response_serializer_class = UserCreationReadSerializer
    resource_name = "User creation"
    permission_screen_code = "user-creation-master"
    permission_screen_codes = ("user-creation-master", "user-account-master")
    search_fields = (
        "user__username",
        "staff__name",
        "staff__mobile",
        "staff__email",
        "user_type__department__name",
        "user_type__role__name",
        "company__name",
    )
    ordering_fields = ("created_at", "updated_at", "user__username", "staff__name", "id")
    filterset_map = {
        "user_type": "user_type_id",
        "user_type_id": "user_type_id",
        "company": "company_id",
        "company_id": "company_id",
        "department": "user_type__department_id",
        "department_id": "user_type__department_id",
        "role": "user_type__role_id",
        "role_id": "user_type__role_id",
        "account_status": "account_status",
        "is_active": "is_active",
    }

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UserCreationWriteSerializer
        return UserCreationReadSerializer

    @action(detail=False, methods=["get"], url_path="lookup-options")
    def lookup_options(self, request):
        queryset = (
            Staff.objects.select_related("department_master", "role_master")
            .filter(is_active=True)
            .order_by("staff_code", "name", "id")
        )
        return Response(
            [
                {
                    "id": staff.id,
                    "staff_code": staff.staff_code,
                    "name": staff.name,
                    "mobile": staff.mobile,
                    "email": staff.email,
                    "department_id": staff.department_master_id,
                    "department_name": getattr(staff.department_master, "name", None),
                    "role_id": staff.role_master_id,
                    "role_name": getattr(staff.role_master, "name", None),
                }
                for staff in queryset
            ]
        )

    @action(detail=False, methods=["get"], url_path="department-options")
    def department_options(self, request):
        user_types = (
            UserType.objects.select_related("department")
            .filter(is_active=True, department__isnull=False)
            .order_by("department__name", "department_id", "id")
        )

        options = []
        seen_department_ids = set()
        for user_type in user_types:
            department = user_type.department
            if not department or department.id in seen_department_ids:
                continue
            seen_department_ids.add(department.id)
            options.append(
                {
                    "id": department.id,
                    "name": department.name,
                    "code": getattr(department, "code", None),
                }
            )

        return Response(options)

    @action(detail=False, methods=["get"], url_path="role-options")
    def role_options(self, request):
        department_id = request.query_params.get("department") or request.query_params.get("department_id")
        if not department_id:
            return Response([])

        user_types = (
            UserType.objects.select_related("role")
            .filter(
                is_active=True,
                department_id=department_id,
                role__isnull=False,
            )
            .order_by("role__name", "role_id", "id")
        )

        options = []
        seen_role_ids = set()
        for user_type in user_types:
            role = user_type.role
            if not role or role.id in seen_role_ids:
                continue
            seen_role_ids.add(role.id)
            options.append(
                {
                    "id": role.id,
                    "name": role.name,
                    "code": getattr(role, "code", None),
                }
            )

        return Response(options)

    @action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        instance = self.get_object()
        new_status = (
            UserCreation.AccountStatus.INACTIVE
            if instance.account_status == UserCreation.AccountStatus.ACTIVE
            else UserCreation.AccountStatus.ACTIVE
        )
        instance.account_status = new_status
        instance.save(update_fields=["account_status", "is_active", "updated_at"])
        if instance.user_id:
            instance.user.is_active = instance.is_active
            instance.user.save(update_fields=["is_active"])
        return Response(
            {
                "message": f"{self.resource_name} status updated.",
                "status": instance.account_status,
            }
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        delete_user_creation(instance)


class UserTypePermissionViewSet(StandardizedModelViewSet):
    queryset = UserTypePermission.objects.select_related(
        "user_type",
        "main_screen",
        "screen_section",
        "user_screen",
    ).all().order_by(
        "user_type__name",
        "main_screen__order_no",
        "screen_section__order_no",
        "user_screen__order_no",
        "id",
    )
    serializer_class = UserTypePermissionSerializer
    response_serializer_class = UserTypePermissionSerializer
    resource_name = "User screen permission"
    permission_screen_code = "user-screen-permission-master"
    permission_screen_codes = ("user-screen-permission-master", "user-permission-master")
    allow_self_permission_lookup = True
    status_field = "status"
    search_fields = (
        "user_type__name",
        "main_screen__name",
        "screen_section__name",
        "user_screen__screen_name",
        "user_screen__code",
    )
    ordering_fields = (
        "created_at",
        "updated_at",
        "main_screen__order_no",
        "screen_section__order_no",
        "user_screen__order_no",
        "id",
    )
    filterset_map = {
        "user_type": "user_type_id",
        "user_type_id": "user_type_id",
        "main_screen": "main_screen_id",
        "main_screen_id": "main_screen_id",
        "screen_section": "screen_section_id",
        "screen_section_id": "screen_section_id",
        "user_screen": "user_screen_id",
        "user_screen_id": "user_screen_id",
        "scope_type": "scope_type",
        "is_active": "status",
    }

    def _summary_queryset(self):
        return (
            UserType.objects.filter(permissions__isnull=False)
            .annotate(
                active_permission_count=Count("permissions", filter=Q(permissions__status=True), distinct=True),
                permission_count=Count("permissions", distinct=True),
            )
            .order_by("name", "id")
        )

    def _get_user_type_permissions(self, user_type_id):
        permissions = UserTypePermission.objects.filter(user_type_id=user_type_id)
        if not permissions.exists():
            raise ValidationError({"user_type": "User type permissions not found."})
        return permissions

    def get_serializer_class(self):
        if self.action == "assign":
            return PermissionAssignmentSerializer
        return UserTypePermissionSerializer

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        base_queryset = self._summary_queryset()
        filtered_queryset = base_queryset

        search_value = request.query_params.get("search") or request.query_params.get("search[value]")
        if search_value:
            filtered_queryset = filtered_queryset.filter(name__icontains=search_value.strip())

        status_value = request.query_params.get("is_active")
        if status_value not in (None, ""):
            desired_status = _coerce_filter_value(status_value)
            if desired_status is True:
                filtered_queryset = filtered_queryset.filter(active_permission_count__gt=0)
            elif desired_status is False:
                filtered_queryset = filtered_queryset.filter(active_permission_count=0)

        total_count = base_queryset.count()
        filtered_count = filtered_queryset.count()

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = UserTypePermissionSummarySerializer(
                page,
                many=True,
                context=self.get_serializer_context(),
            )
            response = self.get_paginated_response(serializer.data)
            if getattr(self.paginator, "datatables_mode", False):
                response.data["recordsTotal"] = total_count
                response.data["recordsFiltered"] = filtered_count
            return response

        serializer = UserTypePermissionSummarySerializer(
            filtered_queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="assign")
    def assign(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permissions = serializer.save()
        response_serializer = UserTypePermissionSerializer(
            permissions,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(
            {
                "message": "Permissions assigned successfully.",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["patch"], url_path=r"summary/(?P<user_type_id>[^/.]+)/toggle-status")
    def toggle_summary_status(self, request, user_type_id=None):
        permissions = self._get_user_type_permissions(user_type_id)
        new_status = not permissions.filter(status=True).exists()
        permissions.update(status=new_status)
        return Response(
            {
                "message": "User type permission status updated.",
                "status": new_status,
            }
        )

    @action(detail=False, methods=["delete"], url_path=r"summary/(?P<user_type_id>[^/.]+)")
    def destroy_summary(self, request, user_type_id=None):
        permissions = self._get_user_type_permissions(user_type_id)
        permissions.delete()
        return Response({"message": "User type permissions deleted successfully."})

    @action(detail=False, methods=["get"], url_path="resolved")
    def resolved(self, request):
        user_type_id = request.query_params.get("user_type")
        user_id = request.query_params.get("user_id")

        if user_type_id:
            user_type = UserType.objects.filter(pk=user_type_id).first()
            if not user_type:
                raise ValidationError({"user_type": "User type not found."})
            data = resolve_subject_permissions(user_type=user_type)
        elif user_id:
            user_profile = UserCreation.objects.select_related("user_type").filter(pk=user_id).first()
            if not user_profile:
                raise ValidationError({"user_id": "User creation record not found."})
            data = resolve_subject_permissions(user_type=user_profile.user_type)
        else:
            data = resolve_subject_permissions(user=request.user)

        return Response(data)

    @action(detail=False, methods=["get"], url_path="menu")
    def menu(self, request):
        data = self.resolved(request).data
        return Response(data.get("menu", []))
