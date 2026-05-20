from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import ValidationError


UserModel = get_user_model()
PROFILE_RELATED_NAMES = ("admin_profile", "wpe_profile")


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in (full_name or "").strip().split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def get_or_prepare_auth_user(
    *,
    profile_model,
    related_name: str,
    username: str,
    instance=None,
    username_exists_message: str = "A user with this username already exists.",
    profile_exists_message: str = "This username is already linked to another profile.",
):
    existing_user = UserModel.objects.select_for_update().filter(username__iexact=username).first()

    if instance and getattr(instance, "user_id", None):
        if existing_user and existing_user.pk != instance.user_id:
            raise ValidationError({"username": username_exists_message})
        user = instance.user
        user.username = username
        return user

    if existing_user:
        try:
            existing_profile = getattr(existing_user, related_name)
        except profile_model.DoesNotExist:
            existing_profile = None
        if existing_profile and (instance is None or existing_profile.pk != instance.pk):
            raise ValidationError({"username": profile_exists_message})
        return existing_user

    return UserModel(username=username)


def sync_auth_user(
    user,
    *,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
):
    if email is not None:
        user.email = (email or "").strip()
    if first_name is not None:
        user.first_name = (first_name or "").strip()
    if last_name is not None:
        user.last_name = (last_name or "").strip()
    if is_active is not None:
        user.is_active = is_active

    password_changed = False
    if password:
        user.set_password(password)
        password_changed = True

    user.save()
    return password_changed


def delete_auth_user_if_unlinked(user, *, related_names: tuple[str, ...] = PROFILE_RELATED_NAMES) -> bool:
    if not user:
        return False
    if getattr(user, "pk", None):
        user = UserModel.objects.filter(pk=user.pk).first()
    if not user:
        return False

    for related_name in related_names:
        try:
            getattr(user, related_name)
        except (AttributeError, ObjectDoesNotExist):
            continue
        return False

    user.delete()
    return True
