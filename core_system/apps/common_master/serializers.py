"""Serializers for common master and ERP partner APIs."""

from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from .models import (
    City,
    CommonMaster,
    Company,
    Continent,
    Country,
    Currency,
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContactPerson,
    CustomerDocument,
    CustomerStatutoryDetail,
    Project,
    State,
    Supplier,
    SupplierAddress,
    SupplierBankDetail,
    SupplierContactPerson,
    SupplierDocument,
    SupplierStatutoryDetail,
    Tax,
)
from .services import extract_nested_payload, save_customer_relations, save_supplier_relations
from .validators import (
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


class LegacyStatusAliasSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="status", required=False)

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, "copy") else dict(data)
        if "status" in mutable_data and "is_active" not in mutable_data:
            mutable_data["is_active"] = mutable_data["status"]
        return super().to_internal_value(mutable_data)


class ContinentSerializer(LegacyStatusAliasSerializer):
    class Meta:
        model = Continent
        fields = ("id", "unique_id", "name", "code", "order_no", "is_active")
        read_only_fields = ("unique_id",)


class CountrySerializer(LegacyStatusAliasSerializer):
    continent_name = serializers.CharField(source="continent.name", read_only=True)

    class Meta:
        model = Country
        fields = (
            "id",
            "unique_id",
            "continent",
            "continent_name",
            "name",
            "code",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_name(self, value):
        normalized = normalize_name(value, field_label="country name")
        queryset = Country.objects.exclude(pk=getattr(self.instance, "pk", None))
        if queryset.filter(name__iexact=normalized).exists():
            raise serializers.ValidationError("Country name must be unique.")
        return normalized

    def validate_code(self, value):
        normalized = normalize_country_code(value)
        queryset = Country.objects.exclude(pk=getattr(self.instance, "pk", None))
        if queryset.filter(code__iexact=normalized).exists():
            raise serializers.ValidationError("Country code must be unique.")
        return normalized


class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = State
        fields = ("id", "unique_id", "country", "country_name", "name", "is_active", "created_at")
        read_only_fields = ("unique_id", "created_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="state name")

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        name = attrs.get("name") or getattr(self.instance, "name", None)
        queryset = State.objects.exclude(pk=getattr(self.instance, "pk", None))
        if country and name and queryset.filter(country=country, name__iexact=name).exists():
            raise serializers.ValidationError({"name": "State name already exists for the selected country."})
        return attrs


class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_type_name = serializers.CharField(source="city_type.name", read_only=True)

    class Meta:
        model = City
        fields = (
            "id",
            "unique_id",
            "country",
            "country_name",
            "state",
            "state_name",
            "name",
            "pincode",
            "city_type",
            "city_type_name",
            "is_active",
            "created_at",
        )
        read_only_fields = ("unique_id", "created_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="city name")

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        name = attrs.get("name") or getattr(self.instance, "name", None)

        validate_state_country_relationship(state=state, country=country)

        queryset = City.objects.exclude(pk=getattr(self.instance, "pk", None))
        if state and name and queryset.filter(state=state, name__iexact=name).exists():
            raise serializers.ValidationError({"name": "City name already exists for the selected state."})
        return attrs


class TaxSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = Tax
        fields = (
            "id",
            "unique_id",
            "country",
            "country_name",
            "name",
            "value",
            "is_active",
            "created_at",
        )
        read_only_fields = ("unique_id", "created_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="tax name")

    def validate_value(self, value):
        return validate_tax_percentage(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        name = attrs.get("name") or getattr(self.instance, "name", None)
        queryset = Tax.objects.exclude(pk=getattr(self.instance, "pk", None))
        if name and queryset.filter(country=country, name__iexact=name).exists():
            raise serializers.ValidationError({"name": "Tax name already exists for the selected nation."})
        return attrs


class CurrencySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = Currency
        fields = (
            "id",
            "unique_id",
            "country",
            "country_name",
            "name",
            "code",
            "symbol",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="currency name")

    def validate_code(self, value):
        return normalize_currency_code(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        name = attrs.get("name") or getattr(self.instance, "name", None)
        code = attrs.get("code") or getattr(self.instance, "code", None)
        queryset = Currency.objects.exclude(pk=getattr(self.instance, "pk", None))
        if country and name and queryset.filter(country=country, name__iexact=name).exists():
            raise serializers.ValidationError({"name": "Currency name already exists for the selected country."})
        if country and code and queryset.filter(country=country, code__iexact=code).exists():
            raise serializers.ValidationError({"code": "Currency code already exists for the selected country."})
        return attrs


class CustomerContactPersonSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CustomerContactPerson
        fields = (
            "id",
            "unique_id",
            "contact_person_name",
            "designation",
            "email",
            "mobile_no",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_contact_person_name(self, value):
        return normalize_name(value, field_label="contact person name")

    def validate_mobile_no(self, value):
        return normalize_mobile_number(value)


class CustomerStatutoryDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerStatutoryDetail
        exclude = ("customer",)


class CustomerBankDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CustomerBankDetail
        fields = (
            "id",
            "unique_id",
            "bank_name",
            "bank_address",
            "ifsc_code",
            "beneficiary_account_name",
            "account_number",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_bank_name(self, value):
        return normalize_name(value, field_label="bank name")

    def validate_beneficiary_account_name(self, value):
        return normalize_name(value, field_label="beneficiary account name")

    def validate_ifsc_code(self, value):
        return normalize_ifsc_code(value)


class CustomerAddressSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = CustomerAddress
        fields = (
            "id",
            "unique_id",
            "address_type",
            "same_as_billing",
            "name",
            "address",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "pincode",
            "contact_name",
            "contact_no",
            "gst_number",
            "gst_status",
            "ecc_no",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "address_type", "created_at", "updated_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="address name")

    def validate_contact_no(self, value):
        return normalize_phone_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs


class CustomerAddressWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        exclude = ("customer", "address_type")
        extra_kwargs = {
            "name": {"required": False},
            "address": {"required": False, "allow_null": True, "allow_blank": True},
            "country": {"required": False, "allow_null": True},
            "state": {"required": False, "allow_null": True},
            "city": {"required": False, "allow_null": True},
            "pincode": {"required": False, "allow_null": True, "allow_blank": True},
            "contact_name": {"required": False, "allow_null": True, "allow_blank": True},
            "contact_no": {"required": False, "allow_null": True, "allow_blank": True},
            "gst_number": {"required": False, "allow_null": True, "allow_blank": True},
            "ecc_no": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def validate_name(self, value):
        return normalize_name(value, field_label="address name")

    def validate_contact_no(self, value):
        return normalize_phone_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate(self, attrs):
        same_as_billing = attrs.get("same_as_billing", False)
        name = attrs.get("name") or getattr(self.instance, "name", None)
        if not same_as_billing and not name:
            raise serializers.ValidationError({"name": "Address name is required."})

        if same_as_billing:
            return attrs

        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs


class CustomerDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomerDocument
        fields = (
            "id",
            "unique_id",
            "customer",
            "document_type",
            "file",
            "file_url",
            "remarks",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "file_url", "created_at", "updated_at")

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None

    def validate_document_type(self, value):
        return normalize_name(value, field_label="document type")

    def validate_file(self, value):
        validate_uploaded_document(value)
        return value


class CustomerReadSerializer(serializers.ModelSerializer):
    currency_name = serializers.CharField(source="currency.name", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    contact_persons = CustomerContactPersonSerializer(many=True, read_only=True)
    statutory_detail = CustomerStatutoryDetailSerializer(read_only=True)
    bank_details = CustomerBankDetailSerializer(many=True, read_only=True)
    documents = CustomerDocumentSerializer(many=True, read_only=True)
    billing_address = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id",
            "unique_id",
            "customer_no",
            "customer_name",
            "customer_group",
            "customer_division",
            "currency",
            "currency_name",
            "currency_code",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "address",
            "pincode",
            "mobile_no",
            "phone_no",
            "email",
            "pan_number",
            "gst_number",
            "gst_registered",
            "gst_provisional",
            "customer_status",
            "is_active",
            "website",
            "remarks",
            "credit_limit",
            "payment_terms",
            "customer_since",
            "contact_persons",
            "statutory_detail",
            "bank_details",
            "billing_address",
            "shipping_address",
            "documents",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _serialize_address(self, obj, address_type: str):
        address = next((item for item in obj.addresses.all() if item.address_type == address_type), None)
        if address is None:
            return None
        return CustomerAddressSerializer(address, context=self.context).data

    def get_billing_address(self, obj):
        return self._serialize_address(obj, CustomerAddress.AddressType.BILLING)

    def get_shipping_address(self, obj):
        return self._serialize_address(obj, CustomerAddress.AddressType.SHIPPING)


class CustomerWriteSerializer(serializers.ModelSerializer):
    contact_persons = CustomerContactPersonSerializer(many=True, required=False)
    statutory_detail = CustomerStatutoryDetailSerializer(required=False, allow_null=True)
    bank_details = CustomerBankDetailSerializer(many=True, required=False)
    billing_address = CustomerAddressWriteSerializer(required=False, allow_null=True)
    shipping_address = CustomerAddressWriteSerializer(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Customer
        fields = (
            "id",
            "unique_id",
            "customer_no",
            "customer_name",
            "customer_group",
            "customer_division",
            "currency",
            "country",
            "state",
            "city",
            "address",
            "pincode",
            "mobile_no",
            "phone_no",
            "email",
            "pan_number",
            "gst_number",
            "gst_registered",
            "gst_provisional",
            "customer_status",
            "is_active",
            "website",
            "remarks",
            "credit_limit",
            "payment_terms",
            "customer_since",
            "contact_persons",
            "statutory_detail",
            "bank_details",
            "billing_address",
            "shipping_address",
        )
        read_only_fields = ("unique_id", "customer_no")

    def validate_customer_name(self, value):
        return normalize_name(value, field_label="customer name")

    def validate_mobile_no(self, value):
        return normalize_mobile_number(value)

    def validate_phone_no(self, value):
        return normalize_phone_number(value)

    def validate_pan_number(self, value):
        return normalize_pan_number(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)

        pan_number = attrs.get("pan_number") or getattr(self.instance, "pan_number", None)
        gst_number = attrs.get("gst_number") or getattr(self.instance, "gst_number", None)
        email = attrs.get("email") or getattr(self.instance, "email", None)
        customer_name = attrs.get("customer_name") or getattr(self.instance, "customer_name", None)
        customer_country = country or getattr(self.instance, "country", None)

        queryset = Customer.objects.exclude(pk=getattr(self.instance, "pk", None))
        if pan_number and queryset.filter(pan_number__iexact=pan_number).exists():
            raise serializers.ValidationError({"pan_number": "PAN number already exists."})
        if gst_number and queryset.filter(gst_number__iexact=gst_number).exists():
            raise serializers.ValidationError({"gst_number": "GST number already exists."})
        if customer_name and customer_country and queryset.filter(
            customer_name__iexact=customer_name,
            country=customer_country,
        ).exists():
            raise serializers.ValidationError(
                {"customer_name": "Customer name already exists for the selected country."}
            )

        is_active = attrs.pop("is_active", None)
        if is_active is not None and "customer_status" not in attrs:
            attrs["customer_status"] = (
                Customer.CustomerStatus.ACTIVE if is_active else Customer.CustomerStatus.INACTIVE
            )

        gst_registered = attrs.get("gst_registered", getattr(self.instance, "gst_registered", False))
        gst_provisional = attrs.get("gst_provisional", getattr(self.instance, "gst_provisional", False))
        if gst_registered and not gst_number:
            raise serializers.ValidationError({"gst_number": "GST number is required when GST is registered."})
        if gst_provisional and not gst_registered:
            raise serializers.ValidationError({"gst_provisional": "GST provisional requires GST registration."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        contacts = validated_data.pop("contact_persons", [])
        statutory = validated_data.pop("statutory_detail", None)
        banks = validated_data.pop("bank_details", [])
        billing_payload = validated_data.pop("billing_address", None)
        shipping_payload = validated_data.pop("shipping_address", None)

        customer = Customer.objects.create(**validated_data)
        save_customer_relations(
            customer,
            billing_payload=billing_payload,
            shipping_payload=shipping_payload,
            contacts=contacts,
            banks=banks,
            statutory=statutory,
        )
        return customer

    @transaction.atomic
    def update(self, instance, validated_data):
        contacts, contacts_provided = extract_nested_payload(validated_data, "contact_persons", None)
        statutory, statutory_provided = extract_nested_payload(validated_data, "statutory_detail", None)
        banks, banks_provided = extract_nested_payload(validated_data, "bank_details", None)
        billing_payload, billing_provided = extract_nested_payload(validated_data, "billing_address", None)
        shipping_payload, shipping_provided = extract_nested_payload(validated_data, "shipping_address", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        save_customer_relations(
            instance,
            billing_payload=billing_payload if billing_provided else False,
            shipping_payload=shipping_payload if shipping_provided else False,
            contacts=contacts if contacts_provided else None,
            banks=banks if banks_provided else None,
            statutory=statutory if statutory_provided else False,
        )
        return instance


class SupplierContactPersonSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SupplierContactPerson
        fields = (
            "id",
            "unique_id",
            "contact_person_name",
            "designation",
            "email",
            "mobile_no",
            "landline",
            "department",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_contact_person_name(self, value):
        return normalize_name(value, field_label="contact person name")

    def validate_mobile_no(self, value):
        return normalize_mobile_number(value)

    def validate_landline(self, value):
        return normalize_phone_number(value)


class SupplierStatutoryDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierStatutoryDetail
        exclude = ("supplier",)


class SupplierBankDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SupplierBankDetail
        fields = (
            "id",
            "unique_id",
            "bank_name",
            "account_number",
            "account_holder_name",
            "bank_address",
            "ifsc_code",
            "swift_code",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_bank_name(self, value):
        return normalize_name(value, field_label="bank name")

    def validate_account_holder_name(self, value):
        return normalize_name(value, field_label="account holder name")

    def validate_ifsc_code(self, value):
        return normalize_ifsc_code(value)

    def validate_swift_code(self, value):
        return normalize_swift_code(value)


class SupplierAddressSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = SupplierAddress
        fields = (
            "id",
            "unique_id",
            "address_type",
            "same_as_billing",
            "name",
            "address",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "pincode",
            "contact_name",
            "contact_no",
            "gst_number",
            "gst_status",
            "ecc_no",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "address_type", "created_at", "updated_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="address name")

    def validate_contact_no(self, value):
        return normalize_phone_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs


class SupplierAddressWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierAddress
        exclude = ("supplier", "address_type")
        extra_kwargs = {
            "name": {"required": False},
            "address": {"required": False, "allow_null": True, "allow_blank": True},
            "country": {"required": False, "allow_null": True},
            "state": {"required": False, "allow_null": True},
            "city": {"required": False, "allow_null": True},
            "pincode": {"required": False, "allow_null": True, "allow_blank": True},
            "contact_name": {"required": False, "allow_null": True, "allow_blank": True},
            "contact_no": {"required": False, "allow_null": True, "allow_blank": True},
            "gst_number": {"required": False, "allow_null": True, "allow_blank": True},
            "ecc_no": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def validate_name(self, value):
        return normalize_name(value, field_label="address name")

    def validate_contact_no(self, value):
        return normalize_phone_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate(self, attrs):
        same_as_billing = attrs.get("same_as_billing", False)
        name = attrs.get("name") or getattr(self.instance, "name", None)
        if not same_as_billing and not name:
            raise serializers.ValidationError({"name": "Address name is required."})

        if same_as_billing:
            return attrs

        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs


class SupplierDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SupplierDocument
        fields = (
            "id",
            "unique_id",
            "supplier",
            "document_type",
            "file",
            "file_url",
            "remarks",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "file_url", "created_at", "updated_at")

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None

    def validate_document_type(self, value):
        return normalize_name(value, field_label="document type")

    def validate_file(self, value):
        validate_uploaded_document(value)
        return value


class SupplierReadSerializer(serializers.ModelSerializer):
    currency_name = serializers.CharField(source="currency.name", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    contact_persons = SupplierContactPersonSerializer(many=True, read_only=True)
    statutory_detail = SupplierStatutoryDetailSerializer(read_only=True)
    bank_details = SupplierBankDetailSerializer(many=True, read_only=True)
    documents = SupplierDocumentSerializer(many=True, read_only=True)
    billing_address = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            "id",
            "unique_id",
            "supplier_no",
            "supplier_name",
            "supplier_group",
            "currency",
            "currency_name",
            "currency_code",
            "reference",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "pincode",
            "address",
            "corporate_address",
            "mobile_no",
            "phone_no",
            "fax_no",
            "pan_number",
            "gst_number",
            "gst_registration_date",
            "gst_status",
            "is_active",
            "email",
            "website",
            "msme_type",
            "arn_no",
            "payment_terms",
            "credit_days",
            "vendor_rating",
            "remarks",
            "contact_persons",
            "statutory_detail",
            "bank_details",
            "billing_address",
            "shipping_address",
            "documents",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _serialize_address(self, obj, address_type: str):
        address = next((item for item in obj.addresses.all() if item.address_type == address_type), None)
        if address is None:
            return None
        return SupplierAddressSerializer(address, context=self.context).data

    def get_billing_address(self, obj):
        return self._serialize_address(obj, SupplierAddress.AddressType.BILLING)

    def get_shipping_address(self, obj):
        return self._serialize_address(obj, SupplierAddress.AddressType.SHIPPING)


class SupplierWriteSerializer(serializers.ModelSerializer):
    contact_persons = SupplierContactPersonSerializer(many=True, required=False)
    statutory_detail = SupplierStatutoryDetailSerializer(required=False, allow_null=True)
    bank_details = SupplierBankDetailSerializer(many=True, required=False)
    billing_address = SupplierAddressWriteSerializer(required=False, allow_null=True)
    shipping_address = SupplierAddressWriteSerializer(required=False, allow_null=True)

    class Meta:
        model = Supplier
        fields = (
            "id",
            "unique_id",
            "supplier_no",
            "supplier_name",
            "supplier_group",
            "currency",
            "reference",
            "country",
            "state",
            "city",
            "pincode",
            "address",
            "corporate_address",
            "mobile_no",
            "phone_no",
            "fax_no",
            "pan_number",
            "gst_number",
            "gst_registration_date",
            "gst_status",
            "is_active",
            "email",
            "website",
            "msme_type",
            "arn_no",
            "payment_terms",
            "credit_days",
            "vendor_rating",
            "remarks",
            "contact_persons",
            "statutory_detail",
            "bank_details",
            "billing_address",
            "shipping_address",
        )
        read_only_fields = ("unique_id", "supplier_no")

    def validate_supplier_name(self, value):
        return normalize_name(value, field_label="supplier name")

    def validate_mobile_no(self, value):
        return normalize_mobile_number(value)

    def validate_phone_no(self, value):
        return normalize_phone_number(value)

    def validate_fax_no(self, value):
        return normalize_phone_number(value)

    def validate_pan_number(self, value):
        return normalize_pan_number(value)

    def validate_gst_number(self, value):
        return normalize_gst_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)

        pan_number = attrs.get("pan_number") or getattr(self.instance, "pan_number", None)
        gst_number = attrs.get("gst_number") or getattr(self.instance, "gst_number", None)
        supplier_name = attrs.get("supplier_name") or getattr(self.instance, "supplier_name", None)
        supplier_country = country or getattr(self.instance, "country", None)

        queryset = Supplier.objects.exclude(pk=getattr(self.instance, "pk", None))
        if pan_number and queryset.filter(pan_number__iexact=pan_number).exists():
            raise serializers.ValidationError({"pan_number": "PAN number already exists."})
        if gst_number and queryset.filter(gst_number__iexact=gst_number).exists():
            raise serializers.ValidationError({"gst_number": "GST number already exists."})
        if supplier_name and supplier_country and queryset.filter(
            supplier_name__iexact=supplier_name,
            country=supplier_country,
        ).exists():
            raise serializers.ValidationError(
                {"supplier_name": "Supplier name already exists for the selected country."}
            )

        gst_status = attrs.get("gst_status", getattr(self.instance, "gst_status", Supplier.GSTStatus.UNREGISTERED))
        if gst_status != Supplier.GSTStatus.UNREGISTERED and not gst_number:
            raise serializers.ValidationError({"gst_number": "GST number is required for the selected GST status."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        contacts = validated_data.pop("contact_persons", [])
        statutory = validated_data.pop("statutory_detail", None)
        banks = validated_data.pop("bank_details", [])
        billing_payload = validated_data.pop("billing_address", None)
        shipping_payload = validated_data.pop("shipping_address", None)

        supplier = Supplier.objects.create(**validated_data)
        save_supplier_relations(
            supplier,
            billing_payload=billing_payload,
            shipping_payload=shipping_payload,
            contacts=contacts,
            banks=banks,
            statutory=statutory,
        )
        return supplier

    @transaction.atomic
    def update(self, instance, validated_data):
        contacts, contacts_provided = extract_nested_payload(validated_data, "contact_persons", None)
        statutory, statutory_provided = extract_nested_payload(validated_data, "statutory_detail", None)
        banks, banks_provided = extract_nested_payload(validated_data, "bank_details", None)
        billing_payload, billing_provided = extract_nested_payload(validated_data, "billing_address", None)
        shipping_payload, shipping_provided = extract_nested_payload(validated_data, "shipping_address", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        save_supplier_relations(
            instance,
            billing_payload=billing_payload if billing_provided else False,
            shipping_payload=shipping_payload if shipping_provided else False,
            contacts=contacts if contacts_provided else None,
            banks=banks if banks_provided else None,
            statutory=statutory if statutory_provided else False,
        )
        return instance


class CompanySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    logo_url = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "unique_id",
            "name",
            "code",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "pincode",
            "latitude",
            "longitude",
            "logo",
            "logo_url",
            "document",
            "document_url",
            "is_active",
            "created_at",
        )
        read_only_fields = ("unique_id", "created_at", "logo_url", "document_url")

    def get_logo_url(self, obj):
        return obj.logo.url if obj.logo else None

    def get_document_url(self, obj):
        return obj.document.url if obj.document else None

    def validate_name(self, value):
        return normalize_name(value, field_label="company name")

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate_document(self, value):
        validate_uploaded_document(value)
        return value

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    application_type_name = serializers.CharField(source="application_type.name", read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "unique_id",
            "company",
            "company_name",
            "name",
            "code",
            "client_name",
            "application_type",
            "application_type_name",
            "capacity",
            "duration",
            "project_date",
            "country",
            "country_name",
            "state",
            "state_name",
            "city",
            "city_name",
            "address",
            "latitude",
            "longitude",
            "pincode",
            "pan_number",
            "gst_number",
            "gst_reg_date",
            "contact_person",
            "contact_number",
            "contact_email",
            "website",
            "description",
            "is_active",
            "created_at",
        )
        read_only_fields = ("unique_id", "created_at")

    def validate_name(self, value):
        return normalize_name(value, field_label="project name")

    def validate_client_name(self, value):
        return normalize_name(value, field_label="client name")

    def validate_contact_number(self, value):
        return normalize_phone_number(value)

    def validate_pincode(self, value):
        return normalize_pincode(value)

    def validate(self, attrs):
        country = attrs.get("country") or getattr(self.instance, "country", None)
        state = attrs.get("state") or getattr(self.instance, "state", None)
        city = attrs.get("city") or getattr(self.instance, "city", None)
        validate_state_country_relationship(state=state, country=country)
        validate_city_state_country_relationship(city=city, state=state, country=country)
        return attrs
