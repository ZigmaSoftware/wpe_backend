"""Models for WPE-specific master tables and user creation flow."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify

from apps.common_master.services import build_running_number


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


class CodeTrackedMaster(BaseMaster):
    code = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        editable=False,
    )
    description = models.TextField(blank=True)

    code_prefix = ""
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = True

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()
        if not self.code and self.code_prefix:
            with transaction.atomic():
                self.code = build_running_number(
                    type(self),
                    field_name="code",
                    prefix=self.code_prefix,
                    width=self.code_width,
                    instance=self,
                )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


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

    code_prefix = ""
    code_width = 3

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.description = (self.description or "").strip()
        if not self.code:
            if self.code_prefix:
                with transaction.atomic():
                    self.code = build_running_number(
                        type(self),
                        field_name="code",
                        prefix=self.code_prefix,
                        width=self.code_width,
                        instance=self,
                    )
                    return super().save(*args, **kwargs)
            self.code = build_unique_code(
                type(self),
                self.name,
                instance=self,
                prefix=self._meta.model_name,
            )
        return super().save(*args, **kwargs)


class LocationMaster(BaseMaster):
    class CenterType(models.TextChoices):
        GRN_CENTER = "GRN_CENTER", "GRN Stock Center"
        BLENDING_CENTER = "BLENDING_CENTER", "Blending Stock Center"
        WAREHOUSE_CENTER = "WAREHOUSE_CENTER", "Warehouse Stock Center"

    center_type = models.CharField(
        max_length=20,
        choices=CenterType.choices,
        default=CenterType.BLENDING_CENTER,
        db_index=True,
    )

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


class WarehouseMaster(CodeTrackedMaster):
    class WarehouseType(models.TextChoices):
        FG = "FG", "FG"
        RM = "RM", "RM"
        SCRAP = "SCRAP", "Scrap"

    warehouse_type = models.CharField(
        max_length=10,
        choices=WarehouseType.choices,
        default=WarehouseType.RM,
    )
    code_prefix = "WH"
    code_width = 3

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


class DepartmentMaster(CodeTrackedMaster):
    department_head = models.ForeignKey(
        "WPEUserCreation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )
    code_prefix = "DEPT"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_department_master"
        verbose_name = "Department Master"
        verbose_name_plural = "Department Masters"


class DesignationMaster(CodeTrackedMaster):
    name = models.CharField(max_length=200, db_index=True)
    department = models.ForeignKey(
        DepartmentMaster,
        on_delete=models.PROTECT,
        related_name="designations",
    )
    code_prefix = "DES"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_designation_master"
        verbose_name = "Designation Master"
        verbose_name_plural = "Designation Masters"
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"],
                name="wpe_designation_department_name_uniq",
            ),
        ]


class RoleMaster(CodeTrackedMaster):
    designation = models.ForeignKey(
        DesignationMaster,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="roles",
    )
    code_prefix = "ROLE"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_role_master"
        verbose_name = "Role Master"
        verbose_name_plural = "Role Masters"


class StoreMaster(CodeTrackedMaster):
    code_prefix = "STORE"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_store_master"
        verbose_name = "Store Master"
        verbose_name_plural = "Store Masters"


class UnitMaster(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    uom_code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=120, unique=True, db_index=True)
    decimal_allowed = models.BooleanField(default=False)
    decimal_places = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wpe_unit_master"
        ordering = ["name", "id"]
        verbose_name = "Unit Master"
        verbose_name_plural = "Unit Masters"

    def __str__(self) -> str:
        return f"{self.uom_code} - {self.name}"

    def clean(self):
        self.uom_code = (self.uom_code or "").strip().upper()
        self.name = (self.name or "").strip()
        if not self.uom_code:
            raise ValidationError({"uom_code": "UOM code is required."})
        if not self.name:
            raise ValidationError({"name": "UOM name is required."})
        if not self.decimal_allowed:
            self.decimal_places = 0

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class ProductTypeCategory(ProductTypeGovernedMaster):
    code_prefix = "CAT"
    code_width = 3

    class Meta:
        db_table = "wpe_product_type_category"
        verbose_name = "Item Category"
        verbose_name_plural = "Item Categories"
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
    code_prefix = "SUB"
    code_width = 3

    class Meta:
        db_table = "wpe_product_type_subtype"
        verbose_name = "Item Sub Category"
        verbose_name_plural = "Item Sub Categories"
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
        return super().save(*args, **kwargs)


class ItemMaster(models.Model):
    class ItemType(models.TextChoices):
        RM = "RM", "RM"
        ADDITIVE = "ADDITIVE", "Additive"
        PACKING = "PACKING", "Packing"
        FG = "FG", "FG"

    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    item_code = models.CharField(max_length=40, unique=True, db_index=True, blank=True, null=True, editable=False)
    item_name = models.CharField(max_length=200, db_index=True)
    sub_category = models.ForeignKey(
        ProductTypeSubtype,
        on_delete=models.PROTECT,
        related_name="items",
    )
    description = models.TextField(blank=True, default="")
    item_type = models.CharField(max_length=12, choices=ItemType.choices, default=ItemType.RM, db_index=True)
    uom = models.ForeignKey(
        UnitMaster,
        on_delete=models.PROTECT,
        related_name="items",
    )
    hsn_code = models.CharField(max_length=50, blank=True)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    maximum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0.000"))
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wpe_item_master"
        ordering = ["item_name", "id"]
        verbose_name = "Item Variant"
        verbose_name_plural = "Item Variants"
        constraints = [
            models.UniqueConstraint(
                fields=["sub_category", "item_name"],
                name="wpe_item_subcategory_name_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["sub_category", "is_active"], name="wpe_item_subcat_active_idx"),
            models.Index(fields=["item_type", "is_active"], name="wpe_item_type_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item_name} ({self.item_code or 'pending'})"

    def clean(self):
        self.item_name = (self.item_name or "").strip()
        self.description = (self.description or "").strip()
        self.hsn_code = (self.hsn_code or "").strip()
        if not self.item_name:
            raise ValidationError({"item_name": "Item name is required."})
        duplicate_queryset = type(self).objects.filter(
            sub_category=self.sub_category,
            item_name=self.item_name,
        )
        if self.pk:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.pk)
        if duplicate_queryset.exists():
            raise ValidationError(
                {"item_name": "An item variant with this name already exists in the selected item sub category."}
            )
        for field_name in ("gst_percentage", "minimum_stock", "maximum_stock", "reorder_level"):
            current_value = getattr(self, field_name)
            try:
                normalized_value = Decimal(str(current_value or "0"))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError({field_name: f"Invalid numeric value for {field_name.replace('_', ' ')}."}) from exc
            setattr(self, field_name, normalized_value)
        if self.minimum_stock > self.maximum_stock:
            raise ValidationError({"minimum_stock": "Minimum stock cannot exceed maximum stock."})
        if self.reorder_level > self.maximum_stock:
            raise ValidationError({"reorder_level": "Reorder level cannot exceed maximum stock."})

    def save(self, *args, **kwargs):
        self.clean()
        if not self.item_code:
            with transaction.atomic():
                self.item_code = build_running_number(
                    type(self),
                    field_name="item_code",
                    prefix="RM",
                    width=3,
                    instance=self,
                )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class WeighmentScaleMaster(CodeTrackedMaster):
    class ConnectionType(models.TextChoices):
        SERIAL = "SERIAL", "Serial"
        USB = "USB", "USB"
        API = "API", "API"

    class Parity(models.TextChoices):
        NONE = "NONE", "None"

    department = models.ForeignKey(
        DepartmentMaster,
        on_delete=models.PROTECT,
        related_name="weighment_scales",
    )
    machine = models.ForeignKey(
        "production.ProductionMachine",
        on_delete=models.PROTECT,
        related_name="weighment_scales",
    )
    connection_type = models.CharField(
        max_length=20,
        choices=ConnectionType.choices,
        default=ConnectionType.SERIAL,
    )
    port_name = models.CharField(max_length=50, blank=True, default="COM1")
    baud_rate = models.PositiveIntegerField(default=9600)
    data_bits = models.PositiveSmallIntegerField(default=8)
    parity = models.CharField(max_length=20, choices=Parity.choices, default=Parity.NONE)
    stop_bits = models.PositiveSmallIntegerField(default=1)
    unit = models.ForeignKey(
        UnitMaster,
        on_delete=models.PROTECT,
        related_name="weighment_scales",
        null=True,
        blank=True,
    )
    is_auto_capture = models.BooleanField(default=False)
    code_prefix = "SCALE"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_weighment_scale_master"
        verbose_name = "Weighment Scale Master"
        verbose_name_plural = "Weighment Scale Masters"


class PrinterMaster(CodeTrackedMaster):
    class PrinterType(models.TextChoices):
        BARCODE = "BARCODE", "Barcode"
        QR = "QR", "QR"
        STICKER = "STICKER", "Sticker"

    class ConnectionType(models.TextChoices):
        USB = "USB", "USB"
        NETWORK = "NETWORK", "Network"

    department = models.ForeignKey(
        DepartmentMaster,
        on_delete=models.PROTECT,
        related_name="printers",
    )
    printer_type = models.CharField(max_length=20, choices=PrinterType.choices)
    connection_type = models.CharField(max_length=20, choices=ConnectionType.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    paper_size = models.CharField(max_length=40, default="LABEL")
    code_prefix = "PRN"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_printer_master"
        verbose_name = "Printer Master"
        verbose_name_plural = "Printer Masters"


class QRLabelTemplateMaster(CodeTrackedMaster):
    class LabelType(models.TextChoices):
        BIN = "BIN", "Bin"
        BAG = "BAG", "Bag"
        PRODUCT = "PRODUCT", "Product"
        REGRIND = "REGRIND", "Regrind"

    class DataFormat(models.TextChoices):
        JSON = "JSON", "JSON"
        TEXT = "TEXT", "Text"

    label_type = models.CharField(max_length=20, choices=LabelType.choices)
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    qr_data_format = models.CharField(max_length=20, choices=DataFormat.choices, default=DataFormat.JSON)
    printer = models.ForeignKey(
        PrinterMaster,
        on_delete=models.PROTECT,
        related_name="qr_label_templates",
    )
    code_prefix = "QR"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_qr_label_template_master"
        verbose_name = "QR Label Template Master"
        verbose_name_plural = "QR Label Template Masters"


class SerialPortConfigurationMaster(CodeTrackedMaster):
    class Parity(models.TextChoices):
        NONE = "NONE", "None"

    class ReadFormat(models.TextChoices):
        ASCII = "ASCII", "ASCII"
        HEX = "HEX", "HEX"

    port_name = models.CharField(max_length=100, blank=True, default="/dev/ttyS1")
    baud_rate = models.PositiveIntegerField(default=9600)
    parity = models.CharField(max_length=20, choices=Parity.choices, default=Parity.NONE)
    data_bits = models.PositiveSmallIntegerField(default=8)
    stop_bits = models.PositiveSmallIntegerField(default=1)
    timeout = models.PositiveIntegerField(null=True, blank=True)
    read_format = models.CharField(max_length=20, choices=ReadFormat.choices, default=ReadFormat.ASCII)
    code_prefix = "SERIAL"
    code_width = 3

    class Meta(BaseMaster.Meta):
        abstract = False
        db_table = "wpe_serial_port_configuration_master"
        verbose_name = "Serial Port Configuration Master"
        verbose_name_plural = "Serial Port Configuration Masters"


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
