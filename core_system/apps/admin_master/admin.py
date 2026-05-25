"""Admin registrations for admin master entities."""

from django.contrib import admin

from .models import (
    MainScreen,
    Role,
    ScreenSection,
    TicketUserType,
    UserCreation,
    UserScreen,
    UserType,
    UserTypePermission,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "unique_id")
    search_fields = ("name",)


@admin.register(TicketUserType)
class TicketUserTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "unique_id")
    search_fields = ("name",)


@admin.register(MainScreen)
class MainScreenAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "order_no", "status")
    list_filter = ("status",)
    search_fields = ("name", "code")
    ordering = ("order_no", "name")


@admin.register(ScreenSection)
class ScreenSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "main_screen", "code", "order_no", "is_active")
    list_filter = ("main_screen", "is_active")
    search_fields = ("name", "code", "main_screen__name")
    ordering = ("main_screen__order_no", "order_no", "name")


@admin.register(UserScreen)
class UserScreenAdmin(admin.ModelAdmin):
    list_display = ("screen_name", "code", "main_screen", "screen_section", "order_no", "is_active")
    list_filter = ("main_screen", "screen_section", "is_active")
    search_fields = ("screen_name", "code", "folder_name")
    ordering = ("main_screen__order_no", "screen_section__order_no", "order_no")


@admin.register(UserType)
class UserTypeAdmin(admin.ModelAdmin):
    list_display = ("department", "role", "name", "code", "is_active")
    list_filter = ("is_active", "department", "role")
    search_fields = ("department__name", "role__name", "name", "code")
    ordering = ("department__name", "role__name", "name")


@admin.register(UserCreation)
class UserCreationAdmin(admin.ModelAdmin):
    list_display = ("user", "staff", "user_type", "account_status", "is_active", "failed_login_attempts")
    list_filter = ("account_status", "is_active", "user_type", "company", "department")
    search_fields = ("user__username", "staff__name", "staff__staff_code")
    raw_id_fields = ("staff",)
    autocomplete_fields = ("user_type", "team_members", "role", "ticket_user_type")


@admin.register(UserTypePermission)
class UserTypePermissionAdmin(admin.ModelAdmin):
    list_display = ("user_type", "scope_type", "main_screen", "screen_section", "user_screen", "status")
    list_filter = ("scope_type", "status", "user_type", "main_screen")
    search_fields = (
        "user_type__name",
        "main_screen__name",
        "screen_section__name",
        "user_screen__screen_name",
        "permission_key",
    )
    autocomplete_fields = ("user_type", "main_screen", "screen_section", "user_screen")
