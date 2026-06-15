from django.db import models


class Contact(models.Model):
    class Category(models.TextChoices):
        LEAD             = "Lead",             "Lead"
        PROSPECT         = "Prospect",         "Prospect"
        CUSTOMER         = "Customer",         "Customer"
        SUPPLIER         = "Supplier",         "Supplier"
        DEALER           = "Dealer",           "Dealer"
        DISTRIBUTOR      = "Distributor",      "Distributor"
        SHIPPER          = "Shipper",          "Shipper"
        SERVICE_PROVIDER = "Service Provider", "Service Provider"

    class CustomerLoyalty(models.TextChoices):
        PLATINUM = "Platinum", "Platinum"
        GOLD     = "Gold",     "Gold"
        SILVER   = "Silver",   "Silver"
        BRONZE   = "Bronze",   "Bronze"

    # ── Identity ──────────────────────────────────────────────────────────────
    ref_code     = models.CharField(max_length=32, unique=True, blank=True, null=True, editable=False)
    name         = models.CharField(max_length=255)                        # Full Name
    display_name = models.CharField(max_length=255, blank=True, default="")
    contact_code = models.CharField(max_length=50,  blank=True, default="")  # Code / Contact Identification

    # ── Classification ────────────────────────────────────────────────────────
    category          = models.CharField(max_length=32,  choices=Category.choices)  # Contact Type
    contact_category  = models.CharField(max_length=100, blank=True, default="")   # Category (Factories etc.)
    customer_loyalty  = models.CharField(max_length=50,  blank=True, default="",   choices=CustomerLoyalty.choices)
    division          = models.CharField(max_length=100, blank=True, default="")
    zone              = models.CharField(max_length=100, blank=True, default="")
    subzone           = models.CharField(max_length=100, blank=True, default="")

    # ── Company / Tax ─────────────────────────────────────────────────────────
    company_name       = models.CharField(max_length=255, blank=True, null=True)
    gstin              = models.CharField(max_length=15,  blank=True, null=True)
    pan                = models.CharField(max_length=10,  blank=True, default="")
    accounting_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tds_category       = models.CharField(max_length=100, blank=True, default="")
    tds_percent        = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ── Sales ─────────────────────────────────────────────────────────────────
    sale_person    = models.CharField(max_length=255, blank=True, default="")
    lead_source    = models.CharField(max_length=150, blank=True, default="")
    market_segment = models.CharField(max_length=150, blank=True, default="")

    # ── Personnel (primary contact person) ────────────────────────────────────
    contact_person = models.CharField(max_length=255, blank=True, default="")  # Name / Department
    designation    = models.CharField(max_length=100, blank=True, default="")
    phone          = models.CharField(max_length=20)                           # Work Phone 1
    work_phone_2   = models.CharField(max_length=20,  blank=True, default="")
    work_phone_3   = models.CharField(max_length=20,  blank=True, default="")
    fax            = models.CharField(max_length=20,  blank=True, default="")
    email          = models.EmailField(blank=True, null=True)

    # ── Billing Address ───────────────────────────────────────────────────────
    address              = models.TextField()                                  # Mailing Address (Door No., Road)
    billing_landmark     = models.CharField(max_length=255, blank=True, default="")
    billing_city         = models.CharField(max_length=100, blank=True, default="")
    state                = models.CharField(max_length=100)                    # Billing State
    billing_postal_code  = models.CharField(max_length=20,  blank=True, default="")
    billing_country      = models.CharField(max_length=100, blank=True, default="India")

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes = models.TextField(blank=True, default="")

    # ── Status ────────────────────────────────────────────────────────────────
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["phone"],    name="contacts_phone_idx"),
            models.Index(fields=["name"],     name="contacts_name_idx"),
            models.Index(fields=["category"], name="contacts_category_idx"),
        ]

    def __str__(self):
        if self.ref_code:
            return f"{self.name} ({self.ref_code})"
        return self.name

    @staticmethod
    def build_ref_code(contact_id):
        return f"c{contact_id}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.ref_code:
            self.ref_code = None
            super().save(*args, **kwargs)
            self.ref_code = self.build_ref_code(self.pk)
            type(self).objects.filter(pk=self.pk).update(ref_code=self.ref_code)
            return

        if self.pk and not self.ref_code:
            self.ref_code = self.build_ref_code(self.pk)

        super().save(*args, **kwargs)
