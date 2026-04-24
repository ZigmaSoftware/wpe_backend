from django.db import models


class GRN(models.Model):
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
    # either store JSONField or
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

    # =========================
    # System Fields
    # =========================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.BooleanField(default=True)

    def __str__(self):
        return self.grn_no