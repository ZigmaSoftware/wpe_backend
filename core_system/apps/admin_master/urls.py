"""URL routing for admin master DRF APIs and legacy compatibility aliases."""

from __future__ import annotations

from collections import OrderedDict

from django.urls import include, path

from core_system.api_router import ExtendedDefaultRouter

from .views import (
    MainScreenViewSet,
    ScreenSectionViewSet,
    StaffViewSet,
    UserCreationViewSet,
    UserScreenViewSet,
    UserTypePermissionViewSet,
    UserTypeViewSet,
)


router = ExtendedDefaultRouter()
router.register(r"main-screens", MainScreenViewSet, basename="main-screen")
router.register(r"screen-sections", ScreenSectionViewSet, basename="screen-section")
router.register(r"staff", StaffViewSet, basename="staff")
router.register(r"user-screens", UserScreenViewSet, basename="user-screen")
router.register(r"user-types", UserTypeViewSet, basename="user-type")
router.register(r"users-creation", UserCreationViewSet, basename="user-creation")
router.register(r"user-permissions", UserTypePermissionViewSet, basename="user-permission")
router.extra_api_root_dict = OrderedDict(
    {
        "users_creation_legacy": "user-list",
        "user_screens_legacy": "user-screen-list",
        "user_types_legacy": "user-type-list",
        "user_permissions_legacy": "user-permission-list",
    }
)


user_patterns = [
    path(
        "users_creation/",
        UserCreationViewSet.as_view({"get": "list", "post": "create"}),
        name="user-list",
    ),
    path(
        "users_creation/create/",
        UserCreationViewSet.as_view({"post": "create"}),
        name="user-create",
    ),
    path(
        "users_creation/<int:pk>/",
        UserCreationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="user-detail",
    ),
    path(
        "users_creation/<int:pk>/toggle/",
        UserCreationViewSet.as_view({"patch": "toggle_status"}),
        name="user-toggle",
    ),
]


user_screen_patterns = [
    path(
        "user-screens/create/",
        UserScreenViewSet.as_view({"post": "create"}),
        name="user-screen-create",
    ),
    path(
        "user-screens/<int:pk>/toggle/",
        UserScreenViewSet.as_view({"patch": "toggle_status"}),
        name="user-screen-toggle",
    ),
    path(
        "user-screens/table-columns/",
        UserScreenViewSet.as_view({"get": "table_columns"}),
        name="user-screen-table-columns",
    ),
]


user_type_patterns = [
    path(
        "user-types/create/",
        UserTypeViewSet.as_view({"post": "create"}),
        name="user-type-create",
    ),
    path(
        "user-types/<int:pk>/toggle/",
        UserTypeViewSet.as_view({"patch": "toggle_status"}),
        name="user-type-toggle",
    ),
]


screen_patterns = [
    path(
        "main-screens/list/",
        MainScreenViewSet.as_view({"get": "lookup"}),
        name="main-screen-list",
    ),
    path(
        "screen-sections/lookup/",
        ScreenSectionViewSet.as_view({"get": "lookup"}),
        name="screen-section-lookup",
    ),
]


permission_patterns = [
    path(
        "user-permissions/create/",
        UserTypePermissionViewSet.as_view({"post": "create"}),
        name="user-permission-create",
    ),
    path(
        "user-permissions/assign/",
        UserTypePermissionViewSet.as_view({"post": "assign"}),
        name="user-permission-assign",
    ),
    path(
        "user-permissions/resolved/",
        UserTypePermissionViewSet.as_view({"get": "resolved"}),
        name="user-permission-resolved",
    ),
    path(
        "user-permissions/menu/",
        UserTypePermissionViewSet.as_view({"get": "menu"}),
        name="user-permission-menu",
    ),
    path(
        "user-permissions/<int:pk>/toggle/",
        UserTypePermissionViewSet.as_view({"patch": "toggle_status"}),
        name="user-permission-toggle",
    ),
]


urlpatterns = (
    user_patterns
    + user_screen_patterns
    + user_type_patterns
    + screen_patterns
    + permission_patterns
    + [path("", include(router.urls))]
)
