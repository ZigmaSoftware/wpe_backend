from django.db import models

class Item(models.Model):

    category = models.CharField(max_length=150)
    group = models.CharField(max_length=150)
    sub_group = models.CharField(max_length=150)

    item_name = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100, unique=True)
    hsn_code = models.CharField(max_length=50, blank=True, null=True)

    unit = models.CharField(max_length=50)

    product_details = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    min_max_status = models.BooleanField(default=False)
    status = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item_name} ({self.item_code})"