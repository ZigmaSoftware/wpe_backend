from random import SystemRandom

from django.db import models
from django.utils import timezone


_random = SystemRandom()


def generate_wpe_unique_id() -> str:
    return f"WPE-{_random.randrange(100000000):08d}"


class WPEUniqueIDModel(models.Model):
    unique_id = models.CharField(max_length=12, unique=True, editable=False, default=generate_wpe_unique_id)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = generate_wpe_unique_id()

        model = self.__class__
        while model.objects.filter(unique_id=self.unique_id).exclude(pk=self.pk).exists():
            self.unique_id = generate_wpe_unique_id()

        return super().save(*args, **kwargs)


class GRN(WPEUniqueIDModel):
    PROCESS_STATUS_GATE_ENTRY = "Gate Entry"
    PROCESS_STATUS_GRN_PENDING = "GRN Pending"
    PROCESS_STATUS_QCR = "Moved to QCR"
    PROCESS_STATUS_MOVED_TO_GRN = "Moved to GRN"
    PROCESS_STATUS_APPROVED = "GRN Approved"
    PROCESS_STATUS_REJECTED = "Rejected"

    # =========================
    # Document Details
    # =========================
    po_no = models.CharField(max_length=100, blank=True, null=True)
    po_date = models.DateField(blank=True, null=True)

    grn_no = models.CharField(max_length=100, unique=True)
    grn_date = models.DateField(blank=True, null=True)

    supplier_invoice_no = models.CharField(max_length=100, blank=True, null=True)
    supplier_invoice_date = models.DateField(blank=True, null=True)

    gateentry_bookno = models.CharField(max_length=100, blank=True, null=True)
    gateentry_bookdate = models.DateField(blank=True, null=True)

    tolerance = models.CharField(max_length=50, blank=True, null=True)

    # =========================
    # Requirement Details
    # =========================
    req_date = models.CharField(max_length=100, blank=True, null=True)
    req_person_name = models.CharField(max_length=255, blank=True, null=True)
    req_person_id = models.CharField(max_length=100, blank=True, null=True)
    req_department = models.CharField(max_length=255, blank=True, null=True)
    req_reason = models.TextField(blank=True, null=True)

    # =========================
    # Supplier Details
    # =========================
    supplier_id = models.CharField(max_length=100, blank=True, null=True)
    gstin = models.CharField(max_length=100, blank=True, null=True)

    contact_name = models.CharField(max_length=255, blank=True, null=True)
    trade_name = models.CharField(max_length=255, blank=True, null=True)
    contact_type = models.CharField(max_length=100, blank=True, null=True)

    address1 = models.TextField(blank=True, null=True)
    address2 = models.TextField(blank=True, null=True)

    location = models.CharField(max_length=255, blank=True, null=True)
    pincode = models.CharField(max_length=50, blank=True, null=True)

    state_name = models.CharField(max_length=255, blank=True, null=True)
    state_code = models.CharField(max_length=50, blank=True, null=True)

    country = models.CharField(max_length=100, blank=True, null=True)

    person_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    category = models.CharField(max_length=255, blank=True, null=True)
    segment = models.CharField(max_length=255, blank=True, null=True)
    sub_segment = models.CharField(max_length=255, blank=True, null=True)

    sales_contact_id = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=100, blank=True, null=True)

    # =========================
    # Item Details (Single Item)
    # If multiple items come,
    # either store JSONField orq
    # create child table.
    # Since you asked same table,
    # keeping first-level fields here.
    # =========================
    
    item_id = models.CharField(max_length=100, blank=True, null=True)
    item_serial_number = models.IntegerField(blank=True, null=True)

    product_description = models.TextField(blank=True, null=True)
    hsn_code = models.CharField(max_length=100, blank=True, null=True)

    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    free_quantity = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    accepted_qty = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    rejected_qty = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    unit = models.CharField(max_length=100, blank=True, null=True)

    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    discount = models.CharField(max_length=100, blank=True, null=True)
    assessable_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    gst_rate = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    total_item_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # =========================
    # Value Details
    # =========================
    freight_charge = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    loading_unloading_charge = models.CharField(max_length=100, blank=True, null=True)

    total_before_tax = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    total_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    total_after_tax = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    grn_pending_items = models.JSONField(default=list, blank=True)

    # =========================
    # Invoice / Order Details (Gate Entry editable)
    # =========================
    purchase_bill_no = models.CharField(max_length=100, unique=True, blank=True, null=True)
    purchase_bill_date = models.DateField(blank=True, null=True)
    dc_numbers = models.TextField(blank=True, null=True)
    delivery_days_gap = models.IntegerField(default=0, blank=True, null=True)
    delivery_note_no = models.CharField(max_length=100, blank=True, null=True)
    delivery_note_date = models.DateTimeField(blank=True, null=True)
    order_rating = models.IntegerField(default=0, blank=True, null=True)

    # =========================
    # Warehouse Routing (Gate Entry editable)
    # =========================
    grn_warehouse = models.CharField(max_length=255, default="QC Pending Warehouse - CBE", blank=True)
    source_warehouse = models.CharField(max_length=255, blank=True, null=True)
    accepted_warehouse = models.CharField(max_length=255, default="Stores", blank=True)
    rejected_warehouse = models.CharField(max_length=255, default="Rejected Warehouse - CBE", blank=True)

    # =========================
    # System Fields
    # =========================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.BooleanField(default=True)
    process_status = models.CharField(max_length=100, default=PROCESS_STATUS_GATE_ENTRY)
    qc_status = models.CharField(max_length=20, default="Pending", blank=True)
    moved_to_qcr_at = models.DateTimeField(blank=True, null=True)
    moved_to_qcr_by = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.purchase_bill_date:
            self.purchase_bill_date = timezone.localdate()
        super().save(*args, **kwargs)
        if is_new and not self.purchase_bill_no:
            purchase_bill_no = f"PB-{self.pk:08d}"
            GRN.objects.filter(pk=self.pk).update(purchase_bill_no=purchase_bill_no)
            self.purchase_bill_no = purchase_bill_no

    def __str__(self):
        return self.grn_no


class QCR(WPEUniqueIDModel):
    source_grn = models.OneToOneField(GRN, on_delete=models.PROTECT, related_name="qcr_record")
    grn_reference_no = models.CharField(max_length=100, db_index=True)
    snapshot = models.JSONField(default=dict)
    qcr_items = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=100, default="Active")
    remarks = models.TextField(blank=True, null=True)
    moved_to_qcr_at = models.DateTimeField()
    moved_to_qcr_by = models.CharField(max_length=255, blank=True, null=True)
    qcr_completed_at = models.DateTimeField(blank=True, null=True)
    qcr_completed_by = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"QCR-{self.grn_reference_no}"


class GRNAuditLog(models.Model):
    STAGE_GRN_CREATED = "GRN Created"
    STAGE_GRN_EDITED = "Gate Entry Edited"
    STAGE_MOVED_TO_GRN_PENDING = "Moved to GRN Pending"
    STAGE_MOVED_TO_QCR = "Moved to QCR"
    STAGE_QCR_ACCEPTED = "QCR Accepted"
    STAGE_QCR_REJECTED = "QCR Rejected"
    STAGE_ADDED_TO_STORE = "Added to Store"

    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name="audit_logs")
    stage = models.CharField(max_length=100)
    actor = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.grn.grn_no} - {self.stage}"
