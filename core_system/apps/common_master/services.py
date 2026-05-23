"""Service helpers for common master workflows."""

from __future__ import annotations

import os
import re
import uuid
from typing import Iterable

from django.db import transaction
from django.utils.text import slugify


def build_unique_code(
    model_cls,
    source_value: str,
    *,
    field_name: str = "code",
    prefix: str = "master",
    max_length: int = 50,
    instance=None,
) -> str:
    base = slugify(source_value or "")[:max_length].strip("-") or prefix
    candidate = base
    counter = 2

    queryset = model_cls.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(**{field_name: candidate}).exists():
        suffix = f"-{counter}"
        trimmed = base[: max_length - len(suffix)]
        candidate = f"{trimmed}{suffix}"
        counter += 1

    return candidate


def build_running_number(model_cls, *, field_name: str, prefix: str, width: int = 4, instance=None) -> str:
    queryset = model_cls.objects.select_for_update().filter(**{f"{field_name}__startswith": prefix})
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    last_instance = queryset.order_by("-id").only(field_name).first()
    last_number = 0
    if last_instance:
        current_value = getattr(last_instance, field_name, "") or ""
        match = re.search(r"(\d+)$", current_value)
        if match:
            last_number = int(match.group(1))

    return f"{prefix}{last_number + 1:0{width}d}"


def document_upload_path(scope: str, reference: str | int, filename: str) -> str:
    _, extension = os.path.splitext(filename or "")
    extension = extension.lower() or ".bin"
    unique_name = f"{uuid.uuid4().hex}{extension}"
    return f"{scope}/{reference}/{unique_name}"


def customer_document_upload_path(instance, filename: str) -> str:
    reference = instance.customer.customer_no or instance.customer_id
    return document_upload_path("customers/documents", reference, filename)


def supplier_document_upload_path(instance, filename: str) -> str:
    reference = instance.supplier.supplier_no or instance.supplier_id
    return document_upload_path("suppliers/documents", reference, filename)


def company_logo_upload_path(instance, filename: str) -> str:
    reference = instance.code or instance.pk or "company"
    return document_upload_path("company/logo", reference, filename)


def company_document_upload_path(instance, filename: str) -> str:
    reference = instance.code or instance.pk or "company"
    return document_upload_path("company/docs", reference, filename)


def extract_nested_payload(validated_data: dict, field_name: str, default=None):
    if field_name not in validated_data:
        return default, False
    return validated_data.pop(field_name), True


def sync_one_to_one_relation(parent, *, related_name: str, model_cls, payload: dict | None, foreign_key: str) -> None:
    existing_instance = getattr(parent, related_name, None)

    if payload is None:
        if existing_instance is not None:
            existing_instance.delete()
        return

    if existing_instance is None:
        model_cls.objects.create(**{foreign_key: parent}, **payload)
        return

    for field_name, value in payload.items():
        setattr(existing_instance, field_name, value)
    existing_instance.save()


def sync_many_relation(
    parent,
    *,
    relation_name: str,
    model_cls,
    payload: Iterable[dict] | None,
    foreign_key: str,
) -> None:
    if payload is None:
        return

    manager = getattr(parent, relation_name)
    existing_by_id = {obj.id: obj for obj in manager.all()}
    keep_ids: list[int] = []

    for row in payload:
        row = dict(row)
        object_id = row.pop("id", None)
        if object_id:
            instance = existing_by_id.get(object_id)
            if instance is None:
                raise ValueError(f"Invalid related object id: {object_id}")
            for field_name, value in row.items():
                setattr(instance, field_name, value)
            instance.save()
            keep_ids.append(instance.id)
            continue

        instance = model_cls.objects.create(**{foreign_key: parent}, **row)
        keep_ids.append(instance.id)

    manager.exclude(id__in=keep_ids).delete()


def replicate_address_fields(source_payload: dict | None) -> dict | None:
    if not source_payload:
        return None

    replicated = dict(source_payload)
    replicated.pop("id", None)
    replicated["same_as_billing"] = False
    return replicated


@transaction.atomic
def save_customer_relations(customer, *, billing_payload=None, shipping_payload=None, contacts=None, banks=None, statutory=None):
    from .models import CustomerAddress, CustomerBankDetail, CustomerContactPerson, CustomerStatutoryDetail

    sync_many_relation(
        customer,
        relation_name="contact_persons",
        model_cls=CustomerContactPerson,
        payload=contacts,
        foreign_key="customer",
    )
    sync_many_relation(
        customer,
        relation_name="bank_details",
        model_cls=CustomerBankDetail,
        payload=banks,
        foreign_key="customer",
    )
    if statutory is not False:
        sync_one_to_one_relation(
            customer,
            related_name="statutory_detail",
            model_cls=CustomerStatutoryDetail,
            payload=statutory,
            foreign_key="customer",
        )

    if shipping_payload and shipping_payload.get("same_as_billing"):
        shipping_payload = replicate_address_fields(billing_payload or _find_existing_address_payload(customer, "billing"))

    if billing_payload is not False:
        _upsert_party_address(customer, CustomerAddress, billing_payload, address_type="billing")
    if shipping_payload is not False:
        _upsert_party_address(customer, CustomerAddress, shipping_payload, address_type="shipping")


@transaction.atomic
def save_supplier_relations(supplier, *, billing_payload=None, shipping_payload=None, contacts=None, banks=None, statutory=None):
    from .models import SupplierAddress, SupplierBankDetail, SupplierContactPerson, SupplierStatutoryDetail

    sync_many_relation(
        supplier,
        relation_name="contact_persons",
        model_cls=SupplierContactPerson,
        payload=contacts,
        foreign_key="supplier",
    )
    sync_many_relation(
        supplier,
        relation_name="bank_details",
        model_cls=SupplierBankDetail,
        payload=banks,
        foreign_key="supplier",
    )
    if statutory is not False:
        sync_one_to_one_relation(
            supplier,
            related_name="statutory_detail",
            model_cls=SupplierStatutoryDetail,
            payload=statutory,
            foreign_key="supplier",
        )

    if shipping_payload and shipping_payload.get("same_as_billing"):
        shipping_payload = replicate_address_fields(billing_payload or _find_existing_address_payload(supplier, "billing"))

    if billing_payload is not False:
        _upsert_party_address(supplier, SupplierAddress, billing_payload, address_type="billing")
    if shipping_payload is not False:
        _upsert_party_address(supplier, SupplierAddress, shipping_payload, address_type="shipping")


def _find_existing_address_payload(parent, address_type: str) -> dict | None:
    address = parent.addresses.filter(address_type=address_type).first()
    if address is None:
        return None

    return {
        "name": address.name,
        "address": address.address,
        "country": address.country,
        "state": address.state,
        "city": address.city,
        "pincode": address.pincode,
        "contact_name": address.contact_name,
        "contact_no": address.contact_no,
        "gst_number": address.gst_number,
        "gst_status": address.gst_status,
        "ecc_no": address.ecc_no,
        "is_active": address.is_active,
    }


def _upsert_party_address(parent, model_cls, payload: dict | None, *, address_type: str) -> None:
    existing = parent.addresses.filter(address_type=address_type).first()
    if payload is None:
        if existing is not None:
            existing.delete()
        return

    payload = dict(payload)
    payload.pop("same_as_billing", None)
    payload["address_type"] = address_type

    if existing is None:
        model_cls.objects.create(**{parent.__class__.__name__.lower(): parent}, **payload)
        return

    for field_name, value in payload.items():
        setattr(existing, field_name, value)
    existing.save()
