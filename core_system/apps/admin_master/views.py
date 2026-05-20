"""DRF viewsets for admin master masters, user creation, and RBAC APIs."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.login_home.models import Department
from common.drf import (
    EnvelopedMutationMixin,
    LookupQuerysetMixin,
    ProtectedDestroyMixin,
    QueryParamFilterMixin,
    ResponseSerializerMixin,
    StandardizedListMixin,
    ToggleStatusMixin,
)

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
    UserTypeSerializer,
)
from .services import delete_user_creation_profile, resolve_subject_permissions


class StandardizedModelViewSet(
    StandardizedListMixin,
    EnvelopedMutationMixin,
    ProtectedDestroyMixin,
    ToggleStatusMixin,
    LookupQuerysetMixin,
    QueryParamFilterMixin,
    ResponseSerializerMixin,
    viewsets.ModelViewSet,
):
    permission_classes = [AdminMasterRBACPermission]
    pagination_class = AdminMasterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    resource_name = "Record"
    status_field = "is_active"
    protected_error_as_validation_error = True

    @property
    def protected_error_message(self):
        return f"{self.resource_name} cannot be deleted because dependent records exist."

    def build_destroy_success_response(self):
        return Response({"message": f"{self.resource_name} deleted successfully."})

    @action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        return self.perform_toggle_status()


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
        return self.build_lookup_response("id", "name", "code", "order_no")


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
        return self.build_lookup_response(
            "id",
            "name",
            "code",
            "main_screen_id",
            "order_no",
        )


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
        return self.build_lookup_response(
            "id",
            "screen_name",
            "code",
            "folder_name",
            "main_screen_id",
            "screen_section_id",
            "order_no",
        )


class StaffViewSet(StandardizedModelViewSet):
    queryset = Staff.objects.select_related("department").all().order_by("staff_code", "name", "id")
    serializer_class = StaffSerializer
    resource_name = "Staff"
    permission_screen_code = "staff-master"
    search_fields = ("staff_code", "name", "mobile", "email", "designation", "department__name")
    ordering_fields = ("staff_code", "name", "id")
    filterset_map = {
        "department": "department_id",
        "is_active": "is_active",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        return self.build_lookup_response(
            "id",
            "staff_code",
            "name",
            "mobile",
            "email",
        )


class UserTypeViewSet(StandardizedModelViewSet):
    queryset = UserType.objects.all().order_by("name", "id")
    serializer_class = UserTypeSerializer
    resource_name = "User type"
    permission_screen_code = "user-type-master"
    search_fields = ("name", "code")
    ordering_fields = ("name", "created_at", "id")
    filterset_map = {
        "is_active": "is_active",
        "code": "code",
    }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        return self.build_lookup_response("id", "name", "code")


class UserCreationViewSet(StandardizedModelViewSet):
    queryset = UserCreation.objects.select_related(
        "user",
        "staff",
        "user_type",
        "company",
        "department",
        "role",
    ).prefetch_related("team_members")
    serializer_class = UserCreationReadSerializer
    response_serializer_class = UserCreationReadSerializer
    resource_name = "User account"
    permission_screen_code = "user-account-master"
    search_fields = (
        "user__username",
        "staff__name",
        "staff__mobile",
        "user_type__name",
        "company__name",
        "department__name",
    )
    ordering_fields = ("created_at", "updated_at", "user__username", "staff__name", "id")
    filterset_map = {
        "user_type": "user_type_id",
        "user_type_id": "user_type_id",
        "company": "company_id",
        "company_id": "company_id",
        "department": "department_id",
        "department_id": "department_id",
        "account_status": "account_status",
        "is_active": "is_active",
    }

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UserCreationWriteSerializer
        return UserCreationReadSerializer

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
        delete_user_creation_profile(instance)


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
    resource_name = "User permission"
    permission_screen_code = "user-permission-master"
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

    def get_serializer_class(self):
        if self.action == "assign":
            return PermissionAssignmentSerializer
        return UserTypePermissionSerializer

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
                raise ValidationError({"user_id": "User account not found."})
            data = resolve_subject_permissions(user_type=user_profile.user_type)
        else:
            data = resolve_subject_permissions(user=request.user)

        return Response(data)

    @action(detail=False, methods=["get"], url_path="menu")
    def menu(self, request):
        data = self.resolved(request).data
        return Response(data.get("menu", []))


class DepartmentLookupViewSet(viewsets.ViewSet):
    permission_classes = [AdminMasterRBACPermission]

    def list(self, request):
        queryset = Department.objects.filter(is_active=True).order_by("name").values("id", "name")
        return Response(list(queryset))
