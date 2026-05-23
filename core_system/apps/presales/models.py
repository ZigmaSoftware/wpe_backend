# models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class PreSales(models.Model):
    order_code = models.CharField(max_length=50, unique=True)

    stage = models.CharField(max_length=50)
    sale_type = models.CharField(max_length=50)
    sale_category = models.CharField(max_length=50)

    project_name = models.CharField(max_length=255)
    version_no = models.CharField(max_length=50, blank=True)

    description = models.TextField(blank=True)

    lead_source = models.CharField(max_length=100)
    sale_contact = models.CharField(max_length=100)

    gp_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gp_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    line_of_business = models.CharField(max_length=100)
    sub_segment = models.CharField(max_length=100)
    segment_keyword = models.CharField(max_length=255, blank=True)

    required_date = models.DateField(null=True)
    request_person_id = models.IntegerField(null=True)
    request_department = models.CharField(max_length=100, blank=True)

    required_time_start = models.TimeField(null=True)
    required_time_end = models.TimeField(null=True)

    required_reason = models.CharField(max_length=255, blank=True)

    internal_ref_id = models.IntegerField(null=True)
    invoice_ref_id = models.IntegerField(null=True)

    tolerance = models.CharField(max_length=50, blank=True)
    profile_type = models.CharField(max_length=100, blank=True)
    capex = models.CharField(max_length=100, blank=True)

    tl_code = models.CharField(max_length=50, blank=True)
    delivery_challan_type = models.CharField(max_length=100, blank=True)

    indent_number = models.CharField(max_length=100, blank=True)
    indent_date = models.DateTimeField(null=True)
    indent_receiving_datetime = models.DateTimeField(null=True)

    movement_description = models.TextField(blank=True)

    customer_po = models.CharField(max_length=100, blank=True)
    customer_po_date = models.DateField(null=True)

    destination = models.CharField(max_length=255, blank=True)

    document_contact = models.TextField(blank=True)
    previous_document_contact = models.TextField(blank=True)

    base_order_id = models.IntegerField(null=True)
    base_customer_id = models.IntegerField(null=True)
    base_customer_name = models.CharField(max_length=255, blank=True)
    base_order_date = models.DateTimeField(null=True)
    activity_id = models.IntegerField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PresalesRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted for Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SENT_TO_PRODUCTION = "SENT_TO_PRODUCTION", "Sent to Production"

    class Category(models.TextChoices):
        STORE = "STORE", "Store"
        PURCHASE = "PURCHASE", "Purchase"

    request_no = models.CharField(max_length=20, unique=True, blank=True)
    request_date = models.DateField()
    category = models.CharField(max_length=20, choices=Category.choices)
    request_person = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    required_reason = models.TextField()
    customer_type = models.CharField(max_length=50, default="ADDITIVE_MO")
    customer_name = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_presales_requests")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_presales_requests")
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_remarks = models.TextField(blank=True)
    sent_to_prod_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_presales_requests")
    sent_to_prod_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_presales_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.request_no:
            self.request_no = f"PS-{self.pk:08d}"
            PresalesRequest.objects.filter(pk=self.pk).update(request_no=self.request_no)

    def __str__(self):
        return self.request_no or f"Presales-{self.pk}"


class PresalesRequestItem(models.Model):
    presales_request = models.ForeignKey(PresalesRequest, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("Items.Item", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=20, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.presales_request} — {self.item}"


class PresalesAuditLog(models.Model):
    presales_request = models.ForeignKey(PresalesRequest, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]