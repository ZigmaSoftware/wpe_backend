# models.py

from django.db import models

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