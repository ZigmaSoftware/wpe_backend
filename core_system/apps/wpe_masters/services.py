"""Service layer for WPE user provisioning and profile lifecycle."""

from __future__ import annotations

from django.db import transaction
from common.user_provisioning import (
    delete_auth_user_if_unlinked,
    get_or_prepare_auth_user,
    split_full_name,
    sync_auth_user,
)
from rest_framework.exceptions import ValidationError

from .models import WPEUserCreation


@transaction.atomic
def upsert_wpe_user_creation(
    *,
    instance: WPEUserCreation | None = None,
    username: str,
    full_name: str,
    password: str | None = None,
    job_title: str | None = None,
    email: str | None = None,
    phone_no: str | None = None,
    location=None,
    default_branch=None,
    role=None,
    is_active: bool = True,
    authorized_branches=None,
    authorized_price_books=None,
    authorized_warehouses=None,
    authorized_production_types=None,
    authorized_sale_types=None,
    authorized_purchase_types=None,
) -> WPEUserCreation:
    username = (username or "").strip()
    full_name = (full_name or "").strip()

    if not username:
        raise ValidationError({"username": "Username is required."})
    if not full_name:
        raise ValidationError({"full_name": "Full name is required."})

    user = get_or_prepare_auth_user(
        profile_model=WPEUserCreation,
        related_name="wpe_profile",
        username=username,
        instance=instance,
        profile_exists_message="This username is already linked to another WPE user.",
    )
    if instance is None and not getattr(user, "pk", None) and not password:
        raise ValidationError({"password": "Password is required when creating a new user."})

    first_name, last_name = split_full_name(full_name)
    sync_auth_user(
        user,
        email=email or "",
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
        password=password,
    )

    profile = instance or WPEUserCreation(user=user)
    profile.user = user
    profile.full_name = full_name
    profile.job_title = job_title or ""
    profile.email = email or ""
    profile.phone_no = phone_no or ""
    profile.location = location
    profile.default_branch = default_branch
    profile.role = role
    profile.is_active = is_active
    profile.save()

    m2m_fields = {
        "authorized_branches": authorized_branches,
        "authorized_price_books": authorized_price_books,
        "authorized_warehouses": authorized_warehouses,
        "authorized_production_types": authorized_production_types,
        "authorized_sale_types": authorized_sale_types,
        "authorized_purchase_types": authorized_purchase_types,
    }
    for field_name, items in m2m_fields.items():
        if items is not None:
            getattr(profile, field_name).set(items)

    return profile


@transaction.atomic
def toggle_wpe_user_creation_status(instance: WPEUserCreation) -> WPEUserCreation:
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active", "updated_at"])
    if instance.user_id:
        instance.user.is_active = instance.is_active
        instance.user.save(update_fields=["is_active"])
    return instance


@transaction.atomic
def delete_wpe_user_creation(instance: WPEUserCreation) -> None:
    linked_user = instance.user
    instance.delete()
    if linked_user:
        delete_auth_user_if_unlinked(linked_user)
