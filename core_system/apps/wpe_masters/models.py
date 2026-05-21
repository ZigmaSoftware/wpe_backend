"""Models for WPE-specific master tables and user creation flow."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def build_unique_code(
    model_cls: type[models.Model],
    source_value: str,
    *,
    instance: models.Model | None = None,
    field_name: str = "code",
    prefix: str = "wpe-master",
    max_length: int = 120,
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


class BaseMaster(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=200, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductTypeGovernedMaster(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(
        max_length=200,
        db_index=True,
        db_collation="utf8mb4_bin",
    )
    code = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
        editable=False,
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()
        if not self.code:
            self.code = build_unique_code(
                type(self),
                self.name,
                instance=self,
                prefix=self._meta.model_name,
            )
        return super().save(*args, **kwargs)


class LocationMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_location_master"
        verbose_name = "Location Master"
        verbose_name_plural = "Location Masters"


class BranchMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_branch_master"
        verbose_name = "Branch Master"
        verbose_name_plural = "Branch Masters"


class PriceBookMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_price_book_master"
        verbose_name = "Price Book Master"
        verbose_name_plural = "Price Book Masters"


class WarehouseMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_warehouse_master"
        verbose_name = "Warehouse Master"
        verbose_name_plural = "Warehouse Masters"


class ProductionTypeMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_production_type_master"
        verbose_name = "Production Type Master"
        verbose_name_plural = "Production Type Masters"


class SaleTypeMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_sale_type_master"
        verbose_name = "Sale Type Master"
        verbose_name_plural = "Sale Type Masters"


class PurchaseTypeMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_purchase_type_master"
        verbose_name = "Purchase Type Master"
        verbose_name_plural = "Purchase Type Masters"


class RoleMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_role_master"
        verbose_name = "Role Master"
        verbose_name_plural = "Role Masters"


class DepartmentMaster(BaseMaster):
    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_department_master"
        verbose_name = "Department Master"
        verbose_name_plural = "Department Masters"


class ProductTypeCategory(ProductTypeGovernedMaster):
    class Meta:
        db_table = "wpe_product_type_category"
        verbose_name = "Product Type Category"
        verbose_name_plural = "Product Type Categories"
        ordering = ["sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="wpe_pt_category_name_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["is_active", "sort_order"],
                name="wpe_pt_cat_active_sort_idx",
            ),
            models.Index(
                fields=["sort_order", "name"],
                name="wpe_pt_cat_sort_name_idx",
            ),
        ]


class ProductTypeSubtype(ProductTypeGovernedMaster):
    category = models.ForeignKey(
        ProductTypeCategory,
        on_delete=models.PROTECT,
        related_name="subtypes",
    )

    class Meta:
        db_table = "wpe_product_type_subtype"
        verbose_name = "Product Type Subtype"
        verbose_name_plural = "Product Type Subtypes"
        ordering = ["category__sort_order", "category__name", "sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="wpe_pt_subtype_category_name_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["category", "is_active"],
                name="wpe_pt_subtype_cat_active_idx",
            ),
            models.Index(
                fields=["category", "sort_order"],
                name="wpe_pt_subtype_cat_sort_idx",
            ),
            models.Index(
                fields=["sort_order", "name"],
                name="wpe_pt_subtype_sort_name_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()
        if not self.code:
            category_name = self.category.name if self.category_id else "category"
            self.code = build_unique_code(
                type(self),
                f"{category_name}-{self.name}",
                instance=self,
                prefix="product-type-subtype",
            )
        return super().save(*args, **kwargs)


class WPEUserCreation(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wpe_profile",
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=200)
    job_title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone_no = models.CharField(max_length=20, blank=True)
    location = models.ForeignKey(
        LocationMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    default_branch = models.ForeignKey(
        BranchMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_branch_users",
    )
    authorized_branches = models.ManyToManyField(
        BranchMaster,
        related_name="authorized_branch_users",
        blank=True,
    )
    authorized_price_books = models.ManyToManyField(
        PriceBookMaster,
        related_name="authorized_users",
        blank=True,
    )
    authorized_warehouses = models.ManyToManyField(
        WarehouseMaster,
        related_name="authorized_users",
        blank=True,
    )
    authorized_production_types = models.ManyToManyField(
        ProductionTypeMaster,
        related_name="authorized_users",
        blank=True,
    )
    authorized_sale_types = models.ManyToManyField(
        SaleTypeMaster,
        related_name="authorized_users",
        blank=True,
    )
    authorized_purchase_types = models.ManyToManyField(
        PurchaseTypeMaster,
        related_name="authorized_users",
        blank=True,
    )
    role = models.ForeignKey(
        RoleMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wpe_user_creation"
        ordering = ["-created_at"]
        verbose_name = "WPE User Creation"
        verbose_name_plural = "WPE User Creations"

    def __str__(self) -> str:
        if self.user_id:
            return f"{self.full_name} ({self.user.username})"
        return self.full_name


class WPERolePermission(models.Model):
    """Stores CRUD + special access permissions per Role per MainScreen."""

    role = models.ForeignKey(
        RoleMaster,
        on_delete=models.CASCADE,
        related_name="screen_permissions",
    )
    main_screen = models.ForeignKey(
        "admin_master.MainScreen",
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    view_all = models.BooleanField(default=False)
    view_self = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_duplicate = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    generate_invoice_access = models.BooleanField(default=False)
    invoice_access = models.BooleanField(default=False)
    access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wpe_role_permission"
        unique_together = [("role", "main_screen")]
        ordering = ["main_screen__order_no", "role__name"]
        verbose_name = "WPE Role Permission"
        verbose_name_plural = "WPE Role Permissions"

    def __str__(self) -> str:
        return f"{self.role.name} — {self.main_screen.name}"


class WPEUserScreenPermission(models.Model):
    """Stores CRUD + special access permissions per UserScreen."""

    user_screen = models.OneToOneField(
        "admin_master.UserScreen",
        on_delete=models.CASCADE,
        related_name="wpe_permissions",
    )
    view_all = models.BooleanField(default=False)
    view_self = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_duplicate = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    generate_invoice_access = models.BooleanField(default=False)
    invoice_access = models.BooleanField(default=False)
    access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wpe_user_screen_permission"
        ordering = ["user_screen__main_screen__order_no", "user_screen__order_no"]
        verbose_name = "WPE User Screen Permission"
        verbose_name_plural = "WPE User Screen Permissions"

    def __str__(self) -> str:
        return f"{self.user_screen.screen_name} permissions"
