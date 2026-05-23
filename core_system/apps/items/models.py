from decimal import Decimal
import re

from django.db import models
from django.utils import timezone


STOCK_ZERO = Decimal("0.000")
ITEM_CODE_DIGITS = 6


def normalize_product_type(value):
    if value is None:
        return ""

    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def get_item_code_prefix(product_type):
    normalized = normalize_product_type(product_type)

    if "profile" in normalized:
        return "PR"
    if "scrap" in normalized:
        return "SI"
    if "general" in normalized or not normalized:
        return "GI"

    words = re.findall(r"[a-z0-9]+", normalized)
    if not words:
        return "GI"

    if len(words) == 1:
        return words[0][:2].upper().ljust(2, "I")

    return "".join(word[0] for word in words[:2]).upper()


class Item(models.Model):
    PRODUCT_TYPE_PROFILE = "Profile Item"
    PRODUCT_TYPE_SCRAP = "Scrap Item"
    PRODUCT_TYPE_GENERAL = "General Item"

    product_type = models.CharField(
        max_length=100,
        blank=True,
        default=PRODUCT_TYPE_GENERAL,
    )

    category = models.CharField(max_length=150)
    group = models.CharField(max_length=150)
    sub_group = models.CharField(max_length=150)

    item_name = models.CharField(max_length=255)
    external_item_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    item_code = models.CharField(max_length=100, unique=True, blank=True, editable=False)
    hsn_code = models.CharField(max_length=50, blank=True, null=True)

    unit = models.CharField(max_length=50)
    opening_stock = models.DecimalField(max_digits=14, decimal_places=3, default=STOCK_ZERO)
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=STOCK_ZERO)

    product_details = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    min_max_status = models.BooleanField(default=False)
    status = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["category", "group", "sub_group", "unit"], name="items_identity_lookup_idx"),
            models.Index(fields=["product_type", "item_code"], name="items_type_code_idx"),
        ]

    @property
    def on_hand(self):
        return self.current_stock

    def __str__(self):
        return f"{self.item_name} ({self.item_code})"

    @classmethod
    def generate_item_code(cls, product_type):
        prefix = get_item_code_prefix(product_type)
        pattern = re.compile(rf"^{re.escape(prefix)}(\d{{{ITEM_CODE_DIGITS}}})$")
        max_number = 0

        for item_code in cls.objects.filter(item_code__istartswith=prefix).values_list("item_code", flat=True):
            match = pattern.match((item_code or "").upper())
            if match:
                max_number = max(max_number, int(match.group(1)))

        return f"{prefix}{max_number + 1:0{ITEM_CODE_DIGITS}d}"

    def infer_product_type(self):
        normalized_product_type = normalize_product_type(self.product_type)
        if "profile" in normalized_product_type:
            return self.PRODUCT_TYPE_PROFILE
        if "scrap" in normalized_product_type:
            return self.PRODUCT_TYPE_SCRAP
        if normalized_product_type and "general" not in normalized_product_type:
            return self.product_type

        for value in (self.category, self.group, self.sub_group):
            normalized = normalize_product_type(value)
            if "profile" in normalized:
                return self.PRODUCT_TYPE_PROFILE
            if "scrap" in normalized:
                return self.PRODUCT_TYPE_SCRAP
            if "general" in normalized:
                return self.PRODUCT_TYPE_GENERAL

        return self.product_type or self.PRODUCT_TYPE_GENERAL

    def save(self, *args, **kwargs):
        self.product_type = self.infer_product_type()
        if self.external_item_id is not None:
            self.external_item_id = str(self.external_item_id).strip() or None
        if not self.item_code:
            self.item_code = self.generate_item_code(self.product_type)

        return super().save(*args, **kwargs)


class ItemStockTransaction(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_transactions")
    date = models.DateField(default=timezone.localdate)
    ref_id = models.CharField(max_length=100, blank=True, null=True)
    trans_type = models.CharField(max_length=150)
    sale_type = models.CharField(max_length=100, blank=True, null=True)
    doc_id = models.CharField(max_length=100, blank=True, null=True)
    contact = models.CharField(max_length=255, blank=True, null=True)
    warehouse = models.CharField(max_length=150, blank=True, null=True)
    bin = models.CharField(max_length=100, blank=True, null=True)
    inwards = models.DecimalField(max_digits=14, decimal_places=3, default=STOCK_ZERO)
    outwards = models.DecimalField(max_digits=14, decimal_places=3, default=STOCK_ZERO)
    balance = models.DecimalField(max_digits=14, decimal_places=3, default=STOCK_ZERO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        indexes = [
            models.Index(fields=["item", "date"], name="items_tx_item_date_idx"),
            models.Index(fields=["ref_id"], name="items_tx_ref_idx"),
            models.Index(fields=["trans_type"], name="items_tx_type_idx"),
            models.Index(fields=["warehouse", "bin"], name="items_tx_wh_bin_idx"),
        ]

    def __str__(self):
        return f"{self.item.item_code} {self.trans_type} {self.balance}"
