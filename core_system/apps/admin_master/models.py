"""Database models for admin master setup and role-based access control."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify


SCREEN_ACTIONS = ("add", "update", "list", "delete", "view", "print")
PERMISSION_ACTIONS = ("all",) + SCREEN_ACTIONS


def default_screen_actions() -> list[str]:
    return list(SCREEN_ACTIONS)


def default_table_columns() -> list[dict]:
    return []


def default_action_permissions() -> dict[str, bool]:
    return {action: False for action in PERMISSION_ACTIONS}


def staff_photo_upload_path(instance: models.Model, filename: str) -> str:
    return f"admin-master/staff/{instance.unique_id}/{filename}"


def build_unique_code(
    model_cls: type[models.Model],
    source_value: str,
    *,
    instance: models.Model | None = None,
    field_name: str = "code",
    prefix: str = "master",
    max_length: int = 100,
) -> str:
    base = slugify(source_value or "")[:max_length].strip("-") or prefix
    candidate = base
    counter = 2

    queryset = model_cls.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(**{field_name: candidate}).exists():
        suffix = f"-{counter}"
        trimmed_base = base[: max_length - len(suffix)]
        candidate = f"{trimmed_base}{suffix}"
        counter += 1

    return candidate


def build_permission_key(user_type_id: int, scope_type: str, scope_id: int) -> str:
    return f"{user_type_id}:{scope_type}:{scope_id}"


class UniqueIDMixin(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class Role(UniqueIDMixin):
    """Legacy role master kept for backward compatibility."""

    name = models.CharField(max_length=100, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class TicketUserType(UniqueIDMixin):
    """Legacy ticket user type mapping retained to avoid data loss."""

    name = models.CharField(max_length=100, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class UserType(UniqueIDMixin):
    name = models.CharField(max_length=150, unique=True, db_index=True)
    code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_user_types",
    )
    role = models.ForeignKey(
        "wpe_masters.RoleMaster",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_user_types",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "role"],
                name="admin_user_type_department_role_uniq",
            ),
        ]

    def __str__(self) -> str:
        if self.department_id and self.role_id:
            return f"{self.department.name} - {self.role.name}"
        return self.name

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()

        if self.department_id and self.role_id:
            self.name = f"{self.department.name} - {self.role.name}"
            self.code = build_unique_code(
                UserType,
                f"{self.department.name}-{self.role.name}",
                instance=self,
                prefix="user-type",
            )
        elif self.name and not self.code:
            self.code = build_unique_code(
                UserType,
                self.name,
                instance=self,
                prefix="user-type",
            )
        super().save(*args, **kwargs)


class Staff(UniqueIDMixin):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    staff_code = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=150, db_index=True)
    age = models.PositiveSmallIntegerField(blank=True, null=True)
    mobile = models.CharField(max_length=15, blank=True, null=True, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True)
    joining_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    emergency_contact_no = models.CharField(max_length=15, blank=True, null=True)
    photo = models.ImageField(upload_to=staff_photo_upload_path, blank=True, null=True)
    department_master = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    designation_master = models.ForeignKey(
        "wpe_masters.DesignationMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    role_master = models.ForeignKey(
        "wpe_masters.RoleMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    department = models.ForeignKey(
        "login_home.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    designation = models.CharField(max_length=150, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["staff_code", "name", "id"]
        indexes = [
            models.Index(fields=["name"], name="staff_name_idx"),
            models.Index(fields=["mobile"], name="staff_mobile_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.staff_code or '----'} - {self.name}"

    @classmethod
    def next_staff_code(cls) -> str:
        numeric_codes = (
            cls.objects.select_for_update()
            .exclude(staff_code__isnull=True)
            .exclude(staff_code="")
            .values_list("staff_code", flat=True)
        )
        last_number = max((int(code) for code in numeric_codes if str(code).isdigit()), default=0)
        return f"{last_number + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.staff_code:
            with transaction.atomic():
                self.staff_code = self.next_staff_code()
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class UserCreation(UniqueIDMixin):
    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        LOCKED = "locked", "Locked"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="admin_profile",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_accounts",
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.PROTECT,
        related_name="user_accounts",
    )
    ticket_user_type = models.ForeignKey(
        TicketUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_accounts",
    )
    user_type = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_accounts",
    )
    project = models.CharField(max_length=150, null=True, blank=True)
    under_users = models.CharField(max_length=150, null=True, blank=True)
    company = models.ForeignKey(
        "common_master.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_accounts",
    )
    department = models.ForeignKey(
        "login_home.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_user_accounts",
    )
    account_status = models.CharField(
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    password = models.CharField(max_length=128, null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    force_password_change = models.BooleanField(default=False)
    is_team_head = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    team_members = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="managed_by",
        blank=True,
    )

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "admin_master_usercreation"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["user_type", "account_status"], name="user_acc_type_status_idx"),
            models.Index(fields=["company", "department"], name="user_acc_org_idx"),
        ]

    def __str__(self) -> str:
        return self.username or self.staff.name

    @property
    def username(self) -> str:
        return self.user.username if self.user_id else ""

    @property
    def mobile_no(self) -> str:
        return self.staff.mobile or "" if self.staff_id else ""

    @property
    def last_login_at(self):
        return self.user.last_login if self.user_id else None

    def save(self, *args, **kwargs):
        self.is_active = self.account_status == self.AccountStatus.ACTIVE
        super().save(*args, **kwargs)


class MainScreen(UniqueIDMixin):
    name = models.CharField(max_length=150, unique=True, db_index=True)
    code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    order_no = models.PositiveIntegerField(default=1, db_index=True)
    status = models.BooleanField(default=True, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["order_no", "name", "id"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = value

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = build_unique_code(
                MainScreen,
                self.name,
                instance=self,
                prefix="main-screen",
            )
        super().save(*args, **kwargs)


class ScreenSection(UniqueIDMixin):
    main_screen = models.ForeignKey(
        MainScreen,
        on_delete=models.PROTECT,
        related_name="sections",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    order_no = models.PositiveIntegerField(default=1, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(null=True, blank=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["main_screen_id", "order_no", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["main_screen", "name"],
                name="unique_screen_section_per_main_screen",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.main_screen.name} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = build_unique_code(
                ScreenSection,
                f"{self.main_screen_id}-{self.name}",
                instance=self,
                prefix="screen-section",
            )
        super().save(*args, **kwargs)


class UserScreen(UniqueIDMixin):
    main_screen = models.ForeignKey(
        MainScreen,
        on_delete=models.PROTECT,
        related_name="user_screens",
    )
    screen_section = models.ForeignKey(
        ScreenSection,
        on_delete=models.PROTECT,
        related_name="user_screens",
    )
    screen_name = models.CharField(max_length=150, db_index=True)
    code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    folder_name = models.CharField(max_length=150, db_index=True, blank=True, null=True)
    order_no = models.PositiveIntegerField(db_index=True)
    icon = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    available_actions = models.JSONField(default=default_screen_actions)
    table_columns = models.JSONField(default=default_table_columns, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["main_screen_id", "screen_section_id", "order_no", "screen_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["main_screen", "screen_section", "screen_name"],
                name="unique_user_screen_per_section",
            ),
        ]
        indexes = [
            models.Index(
                fields=["main_screen", "screen_section", "is_active"],
                name="usr_screen_scope_active_idx",
            ),
            models.Index(fields=["screen_name"], name="usr_screen_name_idx"),
        ]

    def __str__(self) -> str:
        return self.screen_name

    def clean(self):
        if self.screen_section_id and self.main_screen_id:
            if self.screen_section.main_screen_id != self.main_screen_id:
                raise ValidationError(
                    {"screen_section": "Selected section does not belong to the selected main screen."}
                )

        invalid_actions = sorted(set(self.available_actions or []).difference(SCREEN_ACTIONS))
        if invalid_actions:
            raise ValidationError(
                {"available_actions": f"Unsupported screen actions: {', '.join(invalid_actions)}"}
            )

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = build_unique_code(
                UserScreen,
                self.folder_name or self.screen_name,
                instance=self,
                prefix="screen",
            )
        super().save(*args, **kwargs)


class UserTypePermission(UniqueIDMixin):
    class ScopeType(models.TextChoices):
        MAIN_SCREEN = "main_screen", "Main Screen"
        SECTION = "section", "Section"
        SCREEN = "screen", "Screen"

    user_type = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="permissions",
    )
    main_screen = models.ForeignKey(
        MainScreen,
        on_delete=models.PROTECT,
        related_name="permissions",
    )
    screen_section = models.ForeignKey(
        ScreenSection,
        on_delete=models.PROTECT,
        related_name="permissions",
        null=True,
        blank=True,
    )
    user_screen = models.ForeignKey(
        UserScreen,
        on_delete=models.PROTECT,
        related_name="permissions",
        null=True,
        blank=True,
    )
    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        default=ScopeType.SCREEN,
        db_index=True,
    )
    permission_key = models.CharField(max_length=120, unique=True, editable=False, null=True, blank=True)
    action_permissions = models.JSONField(default=default_action_permissions)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["user_type_id", "main_screen_id", "screen_section_id", "user_screen_id", "id"]
        indexes = [
            models.Index(fields=["user_type", "scope_type", "status"], name="usr_perm_type_scope_idx"),
            models.Index(fields=["main_screen", "status"], name="usr_perm_main_status_idx"),
            models.Index(fields=["user_screen", "status"], name="usr_perm_screen_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_type} / {self.scope_type}"

    @property
    def is_active(self) -> bool:
        return self.status

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = value

    def clean(self):
        if self.scope_type == self.ScopeType.MAIN_SCREEN:
            if self.screen_section_id or self.user_screen_id:
                raise ValidationError(
                    {"scope_type": "Main screen scope cannot include section or screen references."}
                )

        if self.scope_type == self.ScopeType.SECTION:
            if not self.screen_section_id:
                raise ValidationError({"screen_section": "Screen section is required for section scope."})
            if self.user_screen_id:
                raise ValidationError({"user_screen": "User screen must be empty for section scope."})
            if self.screen_section.main_screen_id != self.main_screen_id:
                raise ValidationError(
                    {"screen_section": "Selected section does not belong to the selected main screen."}
                )

        if self.scope_type == self.ScopeType.SCREEN:
            if not self.user_screen_id:
                raise ValidationError({"user_screen": "User screen is required for screen scope."})
            if self.user_screen.main_screen_id != self.main_screen_id:
                raise ValidationError(
                    {"user_screen": "Selected screen does not belong to the selected main screen."}
                )
            if self.screen_section_id and self.user_screen.screen_section_id != self.screen_section_id:
                raise ValidationError(
                    {"screen_section": "Selected section does not match the selected user screen."}
                )

        invalid_actions = sorted(set((self.action_permissions or {}).keys()).difference(PERMISSION_ACTIONS))
        if invalid_actions:
            raise ValidationError(
                {"action_permissions": f"Unsupported permission actions: {', '.join(invalid_actions)}"}
            )

    def save(self, *args, **kwargs):
        if self.scope_type == self.ScopeType.SECTION and self.screen_section_id:
            self.main_screen = self.screen_section.main_screen
        elif self.scope_type == self.ScopeType.SCREEN and self.user_screen_id:
            self.main_screen = self.user_screen.main_screen
            self.screen_section = self.user_screen.screen_section

        scope_id = self.main_screen_id
        if self.scope_type == self.ScopeType.SECTION:
            scope_id = self.screen_section_id
        elif self.scope_type == self.ScopeType.SCREEN:
            scope_id = self.user_screen_id

        if self.user_type_id and scope_id:
            self.permission_key = build_permission_key(self.user_type_id, self.scope_type, scope_id)

        super().save(*args, **kwargs)
