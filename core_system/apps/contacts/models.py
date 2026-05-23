from django.db import models


class Contact(models.Model):
    class Category(models.TextChoices):
        LEAD = "Lead", "Lead"
        PROSPECT = "Prospect", "Prospect"
        CUSTOMER = "Customer", "Customer"
        SUPPLIER = "Supplier", "Supplier"
        DEALER = "Dealer", "Dealer"
        DISTRIBUTOR = "Distributor", "Distributor"
        SHIPPER = "Shipper", "Shipper"
        SERVICE_PROVIDER = "Service Provider", "Service Provider"

    ref_code = models.CharField(max_length=32, unique=True, blank=True, null=True, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    state = models.CharField(max_length=100)
    address = models.TextField()
    lead_source = models.CharField(max_length=150, blank=True)
    market_segment = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["phone"], name="contacts_phone_idx"),
            models.Index(fields=["name"], name="contacts_name_idx"),
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

