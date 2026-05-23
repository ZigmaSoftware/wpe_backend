"""Database models for shared common masters and ERP partner masters."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from .services import (
    build_running_number,
    build_unique_code,
    company_document_upload_path,
    company_logo_upload_path,
    customer_document_upload_path,
    supplier_document_upload_path,
)
from .validators import (
    blank_to_none,
    normalize_country_code,
    normalize_currency_code,
    normalize_gst_number,
    normalize_ifsc_code,
    normalize_mobile_number,
    normalize_name,
    normalize_pan_number,
    normalize_phone_number,
    normalize_pincode,
    normalize_swift_code,
    validate_city_state_country_relationship,
    validate_state_country_relationship,
    validate_tax_percentage,
    validate_uploaded_document,
)


class UniqueIDMixin(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class ActiveTimestampedModel(UniqueIDMixin):
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = True


class LocationFieldsMixin(models.Model):
    country = models.ForeignKey(
        "Country",
        on_delete=models.PROTECT,
        related_name="%(class)s_country_set",
        null=True,
        blank=True,
    )
    state = models.ForeignKey(
        "State",
        on_delete=models.PROTECT,
        related_name="%(class)s_state_set",
        null=True,
        blank=True,
    )
    city = models.ForeignKey(
        "City",
        on_delete=models.PROTECT,
        related_name="%(class)s_city_set",
        null=True,
        blank=True,
    )
    address = models.TextField(null=True, blank=True)
    pincode = models.CharField(max_length=12, null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    def normalize_location_fields(self) -> None:
        self.pincode = normalize_pincode(self.pincode)
        validate_state_country_relationship(state=self.state, country=self.country)
        validate_city_state_country_relationship(city=self.city, state=self.state, country=self.country)


class StatutoryFieldsMixin(models.Model):
    ecc_no = models.CharField(max_length=50, null=True, blank=True)
    commissionerate = models.CharField(max_length=150, null=True, blank=True)
    division = models.CharField(max_length=150, null=True, blank=True)
    range_name = models.CharField(max_length=150, null=True, blank=True)
    cst_no = models.CharField(max_length=50, null=True, blank=True)
    tin_no = models.CharField(max_length=50, null=True, blank=True)
    service_tax_no = models.CharField(max_length=50, null=True, blank=True)
    iec_code = models.CharField(max_length=50, null=True, blank=True)
    cin_no = models.CharField(max_length=50, null=True, blank=True)
    tan_no = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        abstract = True


class AddressDetailsMixin(LocationFieldsMixin):
    class GSTStatus(models.TextChoices):
        REGISTERED = "registered", "Registered"
        UNREGISTERED = "unregistered", "Unregistered"
        PROVISIONAL = "provisional", "Provisional"

    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=150, null=True, blank=True)
    contact_no = models.CharField(max_length=20, null=True, blank=True)
    gst_number = models.CharField(max_length=15, null=True, blank=True)
    gst_status = models.CharField(
        max_length=20,
        choices=GSTStatus.choices,
        default=GSTStatus.UNREGISTERED,
    )
    ecc_no = models.CharField(max_length=50, null=True, blank=True)
    same_as_billing = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def normalize_address_fields(self) -> None:
        self.name = normalize_name(self.name, field_label="name")
        self.contact_no = normalize_phone_number(self.contact_no)
        self.gst_number = normalize_gst_number(self.gst_number)
        self.normalize_location_fields()


class Continent(UniqueIDMixin):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    order_no = models.PositiveIntegerField(default=1, db_index=True)
    status = models.BooleanField(default=True, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        ordering = ["order_no", "name", "id"]

    def __str__(self):
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = value

    def clean(self):
        self.name = normalize_name(self.name, field_label="continent name")
        if self.code:
            self.code = build_unique_code(
                Continent,
                self.code,
                field_name="code",
                prefix="continent",
                max_length=50,
                instance=self,
            )

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="continent name")
        if not self.code:
            self.code = build_unique_code(
                Continent,
                self.name,
                field_name="code",
                prefix="continent",
                max_length=50,
                instance=self,
            )
        super().save(*args, **kwargs)


class Country(UniqueIDMixin):
    continent = models.ForeignKey(
        Continent,
        on_delete=models.CASCADE,
        related_name="countries",
    )
    name = models.CharField(max_length=150, db_index=True)
    code = models.CharField(max_length=10, db_index=True)
    status = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        unique_together = ("name", "code")
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["continent", "status"], name="cm_country_cont_st_idx"),
            models.Index(fields=["code"], name="cm_country_code_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = value

    def clean(self):
        self.name = normalize_name(self.name, field_label="country name")
        self.code = normalize_country_code(self.code)
        queryset = Country.objects.exclude(pk=self.pk)
        if queryset.filter(name__iexact=self.name).exists():
            raise ValidationError({"name": "Country name must be unique."})
        if queryset.filter(code__iexact=self.code).exists():
            raise ValidationError({"code": "Country code must be unique."})

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="country name")
        self.code = normalize_country_code(self.code)
        super().save(*args, **kwargs)


class State(UniqueIDMixin):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="states",
    )
    name = models.CharField(max_length=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        unique_together = ("country", "name")
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["country", "is_active"], name="cm_state_country_act_idx"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        self.name = normalize_name(self.name, field_label="state name")

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="state name")
        super().save(*args, **kwargs)


class CommonMaster(UniqueIDMixin):
    type = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "common_master"
        ordering = ["type", "name", "id"]
        indexes = [
            models.Index(fields=["type", "is_active"], name="cm_type_active_idx"),
        ]

    def __str__(self):
        return f"{self.type} / {self.name}"

    def save(self, *args, **kwargs):
        self.type = blank_to_none(self.type) or ""
        self.name = normalize_name(self.name, field_label="common master name")
        super().save(*args, **kwargs)


class City(UniqueIDMixin):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="cities",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name="cities",
    )
    name = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=12, null=True, blank=True, db_index=True)
    city_type = models.ForeignKey(
        CommonMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cities",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "common_master_city"
        unique_together = ("state", "name")
        indexes = [
            models.Index(fields=["state"], name="cm_city_state_idx"),
            models.Index(fields=["name"], name="cm_city_name_idx"),
            models.Index(fields=["country", "pincode"], name="cm_city_country_pin_idx"),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        self.name = normalize_name(self.name, field_label="city name")
        self.pincode = normalize_pincode(self.pincode)
        validate_state_country_relationship(state=self.state, country=self.country)

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="city name")
        self.pincode = normalize_pincode(self.pincode)
        super().save(*args, **kwargs)


class Tax(UniqueIDMixin):
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taxes",
    )
    name = models.CharField(max_length=100, db_index=True)
    value = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "common_master_tax"
        unique_together = ("country", "name")
        indexes = [
            models.Index(fields=["name"], name="cm_tax_name_idx"),
            models.Index(fields=["country"], name="cm_tax_country_idx"),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        self.name = normalize_name(self.name, field_label="tax name")
        self.value = validate_tax_percentage(self.value)

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="tax name")
        self.value = validate_tax_percentage(self.value)
        super().save(*args, **kwargs)


class Currency(ActiveTimestampedModel):
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="currencies",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    symbol = models.CharField(max_length=10, null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_currency"
        ordering = ["name", "code", "id"]
        constraints = [
            models.UniqueConstraint(fields=["country", "name"], name="cm_curr_country_name_uq"),
            models.UniqueConstraint(fields=["country", "code"], name="cm_curr_country_code_uq"),
        ]
        indexes = [
            models.Index(fields=["country", "is_active"], name="cm_curr_country_act_idx"),
            models.Index(fields=["code"], name="cm_curr_code_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        self.name = normalize_name(self.name, field_label="currency name")
        self.code = normalize_currency_code(self.code)

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="currency name")
        self.code = normalize_currency_code(self.code)
        super().save(*args, **kwargs)


class Customer(ActiveTimestampedModel, LocationFieldsMixin):
    class CustomerGroup(models.TextChoices):
        INTERNATIONAL = "international", "International"
        DOMESTIC = "domestic", "Domestic"

    class CustomerStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        BLOCKED = "blocked", "Blocked"

    customer_no = models.CharField(max_length=10, unique=True, editable=False, db_index=True)
    customer_name = models.CharField(max_length=255, db_index=True)
    customer_group = models.CharField(max_length=20, choices=CustomerGroup.choices, db_index=True)
    customer_division = models.CharField(max_length=150, null=True, blank=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    mobile_no = models.CharField(max_length=15, null=True, blank=True, db_index=True)
    phone_no = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True, db_index=True)
    pan_number = models.CharField(max_length=10, null=True, blank=True, unique=True)
    gst_number = models.CharField(max_length=15, null=True, blank=True, unique=True)
    gst_registered = models.BooleanField(default=False)
    gst_provisional = models.BooleanField(default=False)
    customer_status = models.CharField(
        max_length=20,
        choices=CustomerStatus.choices,
        default=CustomerStatus.ACTIVE,
        db_index=True,
    )
    website = models.URLField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    payment_terms = models.CharField(max_length=255, null=True, blank=True)
    customer_since = models.DateField(null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer"
        ordering = ["customer_name", "customer_no", "id"]
        constraints = [
            models.UniqueConstraint(fields=["customer_name", "country"], name="cm_customer_name_ct_uq"),
        ]
        indexes = [
            models.Index(fields=["customer_group", "customer_status"], name="cm_customer_grp_st_idx"),
            models.Index(fields=["country", "state", "city"], name="cm_customer_geo_idx"),
            models.Index(fields=["customer_no"], name="cm_customer_no_idx"),
        ]

    def __str__(self):
        return f"{self.customer_no} - {self.customer_name}"

    def clean(self):
        self.customer_name = normalize_name(self.customer_name, field_label="customer name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        self.phone_no = normalize_phone_number(self.phone_no)
        self.pan_number = normalize_pan_number(self.pan_number)
        self.gst_number = normalize_gst_number(self.gst_number)
        self.normalize_location_fields()
        if self.gst_registered and not self.gst_number:
            raise ValidationError({"gst_number": "GST number is required when GST is registered."})
        if self.gst_provisional and not self.gst_registered:
            raise ValidationError({"gst_provisional": "GST provisional cannot be true when GST is not registered."})

    def save(self, *args, **kwargs):
        self.customer_name = normalize_name(self.customer_name, field_label="customer name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        self.phone_no = normalize_phone_number(self.phone_no)
        self.pan_number = normalize_pan_number(self.pan_number)
        self.gst_number = normalize_gst_number(self.gst_number)
        self.normalize_location_fields()
        self.is_active = self.customer_status == self.CustomerStatus.ACTIVE

        if not self.customer_no:
            with transaction.atomic():
                self.customer_no = build_running_number(
                    Customer,
                    field_name="customer_no",
                    prefix="CUS",
                    width=4,
                    instance=self,
                )
                return super().save(*args, **kwargs)

        return super().save(*args, **kwargs)


class CustomerContactPerson(ActiveTimestampedModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="contact_persons",
    )
    contact_person_name = models.CharField(max_length=150)
    designation = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    mobile_no = models.CharField(max_length=15, null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer_contact"
        ordering = ["contact_person_name", "id"]
        indexes = [
            models.Index(fields=["customer", "is_active"], name="cm_cust_contact_act_idx"),
        ]

    def __str__(self):
        return self.contact_person_name

    def save(self, *args, **kwargs):
        self.contact_person_name = normalize_name(self.contact_person_name, field_label="contact person name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        super().save(*args, **kwargs)


class CustomerStatutoryDetail(ActiveTimestampedModel, StatutoryFieldsMixin):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="statutory_detail",
    )

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer_statutory"
        ordering = ["customer_id"]

    def __str__(self):
        return f"{self.customer.customer_no} statutory"


class CustomerBankDetail(ActiveTimestampedModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="bank_details",
    )
    bank_name = models.CharField(max_length=150)
    bank_address = models.TextField(null=True, blank=True)
    ifsc_code = models.CharField(max_length=11, null=True, blank=True)
    beneficiary_account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=34)
    is_primary = models.BooleanField(default=False)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer_bank"
        ordering = ["-is_primary", "bank_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["customer", "account_number"], name="cm_cust_bank_acct_uq"),
        ]
        indexes = [
            models.Index(fields=["customer", "is_active"], name="cm_cust_bank_act_idx"),
        ]

    def __str__(self):
        return f"{self.customer.customer_no} - {self.bank_name}"

    def save(self, *args, **kwargs):
        self.bank_name = normalize_name(self.bank_name, field_label="bank name")
        self.beneficiary_account_name = normalize_name(
            self.beneficiary_account_name,
            field_label="beneficiary account name",
        )
        self.ifsc_code = normalize_ifsc_code(self.ifsc_code)
        self.account_number = blank_to_none(self.account_number) or ""
        super().save(*args, **kwargs)


class CustomerAddress(ActiveTimestampedModel, AddressDetailsMixin):
    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=20, choices=AddressType.choices, db_index=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer_address"
        ordering = ["address_type", "id"]
        constraints = [
            models.UniqueConstraint(fields=["customer", "address_type"], name="cm_cust_addr_type_uq"),
        ]
        indexes = [
            models.Index(fields=["customer", "address_type"], name="cm_cust_addr_type_idx"),
        ]

    def __str__(self):
        return f"{self.customer.customer_no} {self.address_type}"

    def save(self, *args, **kwargs):
        self.normalize_address_fields()
        super().save(*args, **kwargs)


class CustomerDocument(ActiveTimestampedModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=50, db_index=True)
    file = models.FileField(upload_to=customer_document_upload_path)
    remarks = models.CharField(max_length=255, null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_customer_document"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["customer", "document_type"], name="cm_cust_doc_type_idx"),
        ]

    def __str__(self):
        return f"{self.customer.customer_no} {self.document_type}"

    def clean(self):
        self.document_type = normalize_name(self.document_type, field_label="document type")
        validate_uploaded_document(self.file)

    def save(self, *args, **kwargs):
        self.document_type = normalize_name(self.document_type, field_label="document type")
        validate_uploaded_document(self.file)
        super().save(*args, **kwargs)


class Supplier(ActiveTimestampedModel, LocationFieldsMixin):
    class GSTStatus(models.TextChoices):
        REGISTERED = "registered", "Registered"
        UNREGISTERED = "unregistered", "Unregistered"
        PROVISIONAL = "provisional", "Provisional"

    class MSMEType(models.TextChoices):
        MICRO = "micro", "Micro"
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        NOT_APPLICABLE = "not_applicable", "Not Applicable"

    supplier_no = models.CharField(max_length=10, unique=True, editable=False, db_index=True)
    supplier_name = models.CharField(max_length=255, db_index=True)
    supplier_group = models.CharField(max_length=150, null=True, blank=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="suppliers",
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=150, null=True, blank=True)
    corporate_address = models.TextField(null=True, blank=True)
    mobile_no = models.CharField(max_length=15, null=True, blank=True)
    phone_no = models.CharField(max_length=20, null=True, blank=True)
    fax_no = models.CharField(max_length=20, null=True, blank=True)
    pan_number = models.CharField(max_length=10, null=True, blank=True, unique=True)
    gst_number = models.CharField(max_length=15, null=True, blank=True, unique=True)
    gst_registration_date = models.DateField(null=True, blank=True)
    gst_status = models.CharField(
        max_length=20,
        choices=GSTStatus.choices,
        default=GSTStatus.UNREGISTERED,
    )
    email = models.EmailField(null=True, blank=True, db_index=True)
    website = models.URLField(null=True, blank=True)
    msme_type = models.CharField(
        max_length=20,
        choices=MSMEType.choices,
        default=MSMEType.NOT_APPLICABLE,
    )
    arn_no = models.CharField(max_length=50, null=True, blank=True)
    payment_terms = models.CharField(max_length=255, null=True, blank=True)
    credit_days = models.PositiveIntegerField(default=0)
    vendor_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
    )
    remarks = models.TextField(null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier"
        ordering = ["supplier_name", "supplier_no", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier_name", "country"], name="cm_supplier_name_ct_uq"),
        ]
        indexes = [
            models.Index(fields=["country", "state", "city"], name="cm_supplier_geo_idx"),
            models.Index(fields=["supplier_no"], name="cm_supplier_no_idx"),
        ]

    def __str__(self):
        return f"{self.supplier_no} - {self.supplier_name}"

    def clean(self):
        self.supplier_name = normalize_name(self.supplier_name, field_label="supplier name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        self.phone_no = normalize_phone_number(self.phone_no)
        self.fax_no = normalize_phone_number(self.fax_no)
        self.pan_number = normalize_pan_number(self.pan_number)
        self.gst_number = normalize_gst_number(self.gst_number)
        self.normalize_location_fields()
        if self.gst_status != self.GSTStatus.UNREGISTERED and not self.gst_number:
            raise ValidationError({"gst_number": "GST number is required for the selected GST status."})

    def save(self, *args, **kwargs):
        self.supplier_name = normalize_name(self.supplier_name, field_label="supplier name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        self.phone_no = normalize_phone_number(self.phone_no)
        self.fax_no = normalize_phone_number(self.fax_no)
        self.pan_number = normalize_pan_number(self.pan_number)
        self.gst_number = normalize_gst_number(self.gst_number)
        self.normalize_location_fields()

        if not self.supplier_no:
            with transaction.atomic():
                self.supplier_no = build_running_number(
                    Supplier,
                    field_name="supplier_no",
                    prefix="SUP",
                    width=4,
                    instance=self,
                )
                return super().save(*args, **kwargs)

        return super().save(*args, **kwargs)


class SupplierContactPerson(ActiveTimestampedModel):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="contact_persons",
    )
    contact_person_name = models.CharField(max_length=150)
    designation = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    mobile_no = models.CharField(max_length=15, null=True, blank=True)
    landline = models.CharField(max_length=20, null=True, blank=True)
    department = models.CharField(max_length=150, null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier_contact"
        ordering = ["contact_person_name", "id"]
        indexes = [
            models.Index(fields=["supplier", "is_active"], name="cm_supp_contact_act_idx"),
        ]

    def __str__(self):
        return self.contact_person_name

    def save(self, *args, **kwargs):
        self.contact_person_name = normalize_name(self.contact_person_name, field_label="contact person name")
        self.mobile_no = normalize_mobile_number(self.mobile_no)
        self.landline = normalize_phone_number(self.landline)
        super().save(*args, **kwargs)


class SupplierStatutoryDetail(ActiveTimestampedModel, StatutoryFieldsMixin):
    supplier = models.OneToOneField(
        Supplier,
        on_delete=models.CASCADE,
        related_name="statutory_detail",
    )

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier_statutory"
        ordering = ["supplier_id"]

    def __str__(self):
        return f"{self.supplier.supplier_no} statutory"


class SupplierBankDetail(ActiveTimestampedModel):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="bank_details",
    )
    bank_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=34)
    account_holder_name = models.CharField(max_length=150)
    bank_address = models.TextField(null=True, blank=True)
    ifsc_code = models.CharField(max_length=11, null=True, blank=True)
    swift_code = models.CharField(max_length=11, null=True, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier_bank"
        ordering = ["-is_primary", "bank_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "account_number"], name="cm_supp_bank_acct_uq"),
        ]
        indexes = [
            models.Index(fields=["supplier", "is_active"], name="cm_supp_bank_act_idx"),
        ]

    def __str__(self):
        return f"{self.supplier.supplier_no} - {self.bank_name}"

    def save(self, *args, **kwargs):
        self.bank_name = normalize_name(self.bank_name, field_label="bank name")
        self.account_holder_name = normalize_name(self.account_holder_name, field_label="account holder name")
        self.ifsc_code = normalize_ifsc_code(self.ifsc_code)
        self.swift_code = normalize_swift_code(self.swift_code)
        self.account_number = blank_to_none(self.account_number) or ""
        super().save(*args, **kwargs)


class SupplierAddress(ActiveTimestampedModel, AddressDetailsMixin):
    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=20, choices=AddressType.choices, db_index=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier_address"
        ordering = ["address_type", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "address_type"], name="cm_supp_addr_type_uq"),
        ]
        indexes = [
            models.Index(fields=["supplier", "address_type"], name="cm_supp_addr_type_idx"),
        ]

    def __str__(self):
        return f"{self.supplier.supplier_no} {self.address_type}"

    def save(self, *args, **kwargs):
        self.normalize_address_fields()
        super().save(*args, **kwargs)


class SupplierDocument(ActiveTimestampedModel):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=50, db_index=True)
    file = models.FileField(upload_to=supplier_document_upload_path)
    remarks = models.CharField(max_length=255, null=True, blank=True)

    class Meta(ActiveTimestampedModel.Meta):
        abstract = False
        db_table = "common_master_supplier_document"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["supplier", "document_type"], name="cm_supp_doc_type_idx"),
        ]

    def __str__(self):
        return f"{self.supplier.supplier_no} {self.document_type}"

    def clean(self):
        self.document_type = normalize_name(self.document_type, field_label="document type")
        validate_uploaded_document(self.file)

    def save(self, *args, **kwargs):
        self.document_type = normalize_name(self.document_type, field_label="document type")
        validate_uploaded_document(self.file)
        super().save(*args, **kwargs)


class Company(UniqueIDMixin):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies",
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies",
    )
    pincode = models.CharField(max_length=12, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    logo = models.ImageField(upload_to=company_logo_upload_path, null=True, blank=True)
    document = models.FileField(upload_to=company_document_upload_path, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "common_master_CompanyCreation"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["code"], name="cm_company_code_idx"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="company name")
        self.pincode = normalize_pincode(self.pincode)
        validate_state_country_relationship(state=self.state, country=self.country)
        validate_city_state_country_relationship(city=self.city, state=self.state, country=self.country)
        if self.document:
            validate_uploaded_document(self.document)
        super().save(*args, **kwargs)


class Project(UniqueIDMixin):
    company = models.ForeignKey("Company", on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    client_name = models.CharField(max_length=255, null=True, blank=True)
    application_type = models.ForeignKey(
        CommonMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"type": "APPLICATION_TYPE"},
    )
    capacity = models.CharField(max_length=100, null=True, blank=True)
    duration = models.CharField(max_length=100, null=True, blank=True)
    project_date = models.DateField()
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    pincode = models.CharField(max_length=12, null=True, blank=True)
    pan_number = models.CharField(max_length=20, null=True, blank=True)
    gst_number = models.CharField(max_length=20, null=True, blank=True)
    gst_reg_date = models.DateField(null=True, blank=True)
    contact_person = models.CharField(max_length=150, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(UniqueIDMixin.Meta):
        abstract = False
        db_table = "common_master_ProjectCreation"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["code"], name="cm_project_code_idx"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name, field_label="project name")
        self.client_name = normalize_name(self.client_name, field_label="client name")
        self.pincode = normalize_pincode(self.pincode)
        self.contact_number = normalize_phone_number(self.contact_number)
        validate_state_country_relationship(state=self.state, country=self.country)
        validate_city_state_country_relationship(city=self.city, state=self.state, country=self.country)
        super().save(*args, **kwargs)
