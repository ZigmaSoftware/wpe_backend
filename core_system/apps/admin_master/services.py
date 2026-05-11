"""Service layer for admin master user provisioning and RBAC resolution."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    PERMISSION_ACTIONS,
    SCREEN_ACTIONS,
    MainScreen,
    Staff,
    UserCreation,
    UserScreen,
    UserType,
    UserTypePermission,
    build_permission_key,
    default_action_permissions,
)
from .validators import (
    has_any_granted_action,
    normalize_action_permissions,
    validate_mobile_number,
    validate_scope_relationship,
)


UserModel = get_user_model()
MAX_FAILED_LOGIN_ATTEMPTS = 5


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in (full_name or "").strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def sync_staff_contact_details(
    staff: Staff,
    *,
    mobile_no: str | None = None,
    email: str | None = None,
    department=None,
    designation: str | None = None,
) -> Staff:
    update_fields: list[str] = []

    normalized_mobile = validate_mobile_number(mobile_no)
    if normalized_mobile is not None and staff.mobile != normalized_mobile:
        staff.mobile = normalized_mobile
        update_fields.append("mobile")

    if email is not None and staff.email != email:
        staff.email = email or None
        update_fields.append("email")

    if department is not None and staff.department_id != getattr(department, "id", department):
        staff.department = department
        update_fields.append("department")

    if designation is not None and staff.designation != designation:
        staff.designation = designation or None
        update_fields.append("designation")

    if update_fields:
        staff.save(update_fields=update_fields)

    return staff


def _get_or_prepare_auth_user(
    *,
    instance: UserCreation | None = None,
    username: str,
) -> Any:
    existing_user = (
        UserModel.objects.select_for_update()
        .filter(username__iexact=username)
        .first()
    )

    if instance and instance.user_id:
        if existing_user and existing_user.pk != instance.user_id:
            raise ValidationError({"username": "A user with this username already exists."})
        user = instance.user
        user.username = username
        return user

    if existing_user:
        try:
            existing_profile = existing_user.admin_profile
        except UserCreation.DoesNotExist:
            existing_profile = None
        if existing_profile and (instance is None or existing_profile.pk != instance.pk):
            raise ValidationError({"username": "This username is already linked to another user account."})
        return existing_user

    return UserModel(username=username)


@transaction.atomic
def upsert_user_creation(
    *,
    instance: UserCreation | None = None,
    username: str,
    password: str | None,
    staff: Staff,
    user_type: UserType,
    account_status: str,
    force_password_change: bool = False,
    company=None,
    department=None,
    project: str | None = None,
    under_users: str | None = None,
    is_team_head: bool = False,
    team_members=None,
    role=None,
    ticket_user_type=None,
    mobile_no: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    designation: str | None = None,
) -> UserCreation:
    if not username:
        raise ValidationError({"username": "Username is required."})

    if instance is None and not password:
        raise ValidationError({"password": "Password is required."})

    sync_staff_contact_details(
        staff,
        mobile_no=mobile_no,
        email=email,
        department=department,
        designation=designation,
    )

    user = _get_or_prepare_auth_user(instance=instance, username=username.strip())
    staff_first_name, staff_last_name = split_full_name(staff.name)

    user.email = (email or staff.email or "").strip()
    user.first_name = (first_name if first_name is not None else user.first_name or staff_first_name).strip()
    user.last_name = (last_name if last_name is not None else user.last_name or staff_last_name).strip()
    user.is_active = account_status == UserCreation.AccountStatus.ACTIVE

    password_changed = False
    if password:
        user.set_password(password)
        password_changed = True

    user.save()

    profile = instance or UserCreation(user=user, staff=staff)
    profile.user = user
    profile.staff = staff
    profile.user_type = user_type
    profile.role = role
    profile.ticket_user_type = ticket_user_type
    profile.company = company
    profile.department = department
    profile.project = project
    profile.under_users = under_users
    profile.account_status = account_status
    profile.force_password_change = force_password_change
    profile.is_team_head = is_team_head

    if account_status != UserCreation.AccountStatus.LOCKED:
        profile.failed_login_attempts = 0

    profile.save()

    if password_changed:
        profile.password_changed_at = timezone.now()
        profile.save(update_fields=["password_changed_at", "updated_at"])

    if team_members is not None:
        profile.team_members.set(team_members)

    return profile


def increment_failed_login_attempts(username: str) -> UserCreation | None:
    if not username:
        return None

    profile = (
        UserCreation.objects.select_related("user")
        .filter(user__username__iexact=username)
        .first()
    )
    if not profile:
        return None

    profile.failed_login_attempts += 1
    update_fields = ["failed_login_attempts", "updated_at"]

    if profile.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        profile.account_status = UserCreation.AccountStatus.LOCKED
        profile.is_active = False
        update_fields.extend(["account_status", "is_active"])
        if profile.user_id:
            UserModel.objects.filter(pk=profile.user_id).update(is_active=False)

    profile.save(update_fields=update_fields)
    return profile


def reset_failed_login_attempts(user) -> UserCreation | None:
    if not getattr(user, "pk", None):
        return None

    profile = UserCreation.objects.filter(user=user).first()
    if not profile:
        return None

    update_fields: list[str] = []
    if profile.failed_login_attempts:
        profile.failed_login_attempts = 0
        update_fields.append("failed_login_attempts")

    if profile.account_status == UserCreation.AccountStatus.ACTIVE and not profile.is_active:
        profile.is_active = True
        update_fields.append("is_active")

    if update_fields:
        profile.save(update_fields=[*update_fields, "updated_at"])

    return profile


def _build_effective_permission_map(permission_rows: list[UserTypePermission], screen: UserScreen) -> dict[str, bool]:
    effective_permissions = default_action_permissions()

    main_permission = next(
        (
            permission
            for permission in permission_rows
            if permission.scope_type == UserTypePermission.ScopeType.MAIN_SCREEN
            and permission.main_screen_id == screen.main_screen_id
            and permission.status
        ),
        None,
    )
    section_permission = next(
        (
            permission
            for permission in permission_rows
            if permission.scope_type == UserTypePermission.ScopeType.SECTION
            and permission.screen_section_id == screen.screen_section_id
            and permission.status
        ),
        None,
    )
    screen_permission = next(
        (
            permission
            for permission in permission_rows
            if permission.scope_type == UserTypePermission.ScopeType.SCREEN
            and permission.user_screen_id == screen.id
            and permission.status
        ),
        None,
    )

    for permission in (main_permission, section_permission, screen_permission):
        if not permission:
            continue
        effective_permissions.update(permission.action_permissions or {})

    if effective_permissions.get("all"):
        for action in screen.available_actions:
            effective_permissions[action] = True

    return {
        "all": bool(effective_permissions.get("all")),
        **{
            action: action in screen.available_actions and bool(effective_permissions.get(action))
            for action in SCREEN_ACTIONS
        },
    }


def _build_full_access_permission_map(screen: UserScreen) -> dict[str, bool]:
    return {
        "all": True,
        **{
            action: action in screen.available_actions
            for action in SCREEN_ACTIONS
        },
    }


def _active_user_screens() -> list[UserScreen]:
    return list(
        UserScreen.objects.select_related("main_screen", "screen_section")
        .filter(
            is_active=True,
            main_screen__status=True,
            screen_section__is_active=True,
        )
        .order_by("main_screen__order_no", "screen_section__order_no", "order_no", "id")
    )


def _build_menu_payload(
    *,
    active_screens: list[UserScreen],
    permission_builder,
    subject: dict[str, Any],
) -> dict[str, Any]:
    menu_map: dict[int, dict[str, Any]] = {}

    for screen in active_screens:
        effective_permissions = permission_builder(screen)
        if not has_any_granted_action(effective_permissions, available_actions=screen.available_actions):
            continue

        main_bucket = menu_map.setdefault(
            screen.main_screen_id,
            {
                "id": screen.main_screen_id,
                "name": screen.main_screen.name,
                "code": screen.main_screen.code,
                "order_no": screen.main_screen.order_no,
                "sections": {},
            },
        )
        section_bucket = main_bucket["sections"].setdefault(
            screen.screen_section_id,
            {
                "id": screen.screen_section_id,
                "name": screen.screen_section.name,
                "code": screen.screen_section.code,
                "order_no": screen.screen_section.order_no,
                "screens": [],
            },
        )
        section_bucket["screens"].append(
            {
                "id": screen.id,
                "screen_name": screen.screen_name,
                "code": screen.code,
                "route_path": screen.folder_name,
                "icon": screen.icon,
                "description": screen.description,
                "order_no": screen.order_no,
                "available_actions": screen.available_actions,
                "action_permissions": effective_permissions,
            }
        )

    ordered_menu = []
    for main_bucket in sorted(menu_map.values(), key=lambda item: (item["order_no"], item["name"])):
        ordered_sections = []
        for section_bucket in sorted(
            main_bucket["sections"].values(),
            key=lambda item: (item["order_no"], item["name"]),
        ):
            ordered_sections.append(section_bucket)
        main_bucket["sections"] = ordered_sections
        ordered_menu.append(main_bucket)

    return {
        "user_type": subject,
        "menu": ordered_menu,
    }


def resolve_user_type_permissions(user_type: UserType) -> dict[str, Any]:
    permission_rows = list(
        UserTypePermission.objects.select_related(
            "main_screen",
            "screen_section",
            "user_screen",
        )
        .filter(user_type=user_type)
        .order_by("main_screen__order_no", "screen_section__order_no", "user_screen__order_no", "id")
    )

    return _build_menu_payload(
        active_screens=_active_user_screens(),
        permission_builder=lambda screen: _build_effective_permission_map(permission_rows, screen),
        subject={
            "id": user_type.id,
            "name": user_type.name,
            "code": user_type.code,
        },
    )


def resolve_full_access_permissions(user) -> dict[str, Any]:
    return _build_menu_payload(
        active_screens=_active_user_screens(),
        permission_builder=_build_full_access_permission_map,
        subject={
            "id": getattr(user, "id", None),
            "name": getattr(user, "username", "") or getattr(user, "get_username", lambda: "")(),
            "code": "full-access",
        },
    )


def resolve_subject_permissions(*, user_type=None, user=None) -> dict[str, Any]:
    resolved_user_type = user_type

    if resolved_user_type is None and user is not None:
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return resolve_full_access_permissions(user)

    if resolved_user_type is None:
        profile = getattr(user, "admin_profile", None)
        resolved_user_type = getattr(profile, "user_type", None)

    if resolved_user_type is None:
        raise ValidationError({"user_type": "A valid user type is required to resolve permissions."})

    return resolve_user_type_permissions(resolved_user_type)


@transaction.atomic
def upsert_permission_assignments(
    *,
    user_type: UserType,
    permission_entries: list[dict[str, Any]],
) -> list[UserTypePermission]:
    saved_permissions: list[UserTypePermission] = []

    for entry in permission_entries:
        scope_type = entry["scope_type"]
        main_screen = entry.get("main_screen")
        screen_section = entry.get("screen_section")
        user_screen = entry.get("user_screen")
        is_active = bool(entry.get("is_active", True))

        if scope_type == UserTypePermission.ScopeType.SECTION and screen_section and not main_screen:
            main_screen = screen_section.main_screen

        if scope_type == UserTypePermission.ScopeType.SCREEN and user_screen:
            main_screen = user_screen.main_screen
            screen_section = user_screen.screen_section

        if not main_screen:
            raise ValidationError({"main_screen": "Main screen is required."})

        validate_scope_relationship(
            main_screen=main_screen,
            screen_section=screen_section,
            user_screen=user_screen,
        )

        available_actions = user_screen.available_actions if user_screen else SCREEN_ACTIONS
        action_permissions = normalize_action_permissions(
            entry.get("action_permissions"),
            available_actions=available_actions,
        )

        scope_id = main_screen.id
        if scope_type == UserTypePermission.ScopeType.SECTION:
            if not screen_section:
                raise ValidationError({"screen_section": "Screen section is required for section scope."})
            scope_id = screen_section.id
        elif scope_type == UserTypePermission.ScopeType.SCREEN:
            if not user_screen:
                raise ValidationError({"user_screen": "User screen is required for screen scope."})
            scope_id = user_screen.id

        permission_key = build_permission_key(user_type.id, scope_type, scope_id)
        permission, _created = UserTypePermission.objects.update_or_create(
            permission_key=permission_key,
            defaults={
                "user_type": user_type,
                "main_screen": main_screen,
                "screen_section": screen_section,
                "user_screen": user_screen,
                "scope_type": scope_type,
                "action_permissions": action_permissions,
                "status": is_active,
            },
        )
        saved_permissions.append(permission)

    return saved_permissions


def user_has_screen_action(user, *, screen_code: str, action: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    profile = getattr(user, "admin_profile", None)
    if not profile or not profile.user_type_id or profile.account_status != UserCreation.AccountStatus.ACTIVE:
        return False

    screen = (
        UserScreen.objects.select_related("main_screen", "screen_section")
        .filter(code=screen_code, is_active=True)
        .first()
    )
    if not screen:
        return False

    permission_rows = list(
        UserTypePermission.objects.filter(user_type=profile.user_type, status=True).filter(
            Q(scope_type=UserTypePermission.ScopeType.MAIN_SCREEN, main_screen_id=screen.main_screen_id)
            | Q(
                scope_type=UserTypePermission.ScopeType.SECTION,
                screen_section_id=screen.screen_section_id,
            )
            | Q(scope_type=UserTypePermission.ScopeType.SCREEN, user_screen_id=screen.id)
        )
    )
    effective_permissions = _build_effective_permission_map(permission_rows, screen)

    if action == "all":
        return effective_permissions.get("all", False)
    return bool(effective_permissions.get(action))
