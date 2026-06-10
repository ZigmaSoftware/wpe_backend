from __future__ import annotations

from django.utils.text import slugify


ADMIN_ROLE_TOKENS = {
    "admin",
    "administrator",
    "super_admin",
    "superadmin",
}
STORE_ROLE_TOKENS = {
    "store",
    "store_user",
    "store_manager",
    "stores",
}
BLENDING_ROLE_TOKENS = {
    "blending",
    "blending_user",
    "blending_manager",
}
PRODUCTION_ROLE_TOKENS = {
    "production",
    "production_user",
    "production_manager",
    "operator",
}


def _normalize_role_token(value) -> str | None:
    if value in (None, ""):
        return None
    normalized = slugify(str(value)).replace("-", "_").strip("_")
    return normalized or None


def resolve_user_role_tokens(user) -> set[str]:
    if not getattr(user, "is_authenticated", False):
        return set()

    tokens: set[str] = set()
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        tokens.update(ADMIN_ROLE_TOKENS)

    profile = getattr(user, "admin_profile", None)
    if profile is None:
        return tokens

    values = [
        getattr(getattr(profile, "user_type", None), "name", None),
        getattr(getattr(profile, "user_type", None), "code", None),
        getattr(getattr(profile, "role", None), "name", None),
        getattr(getattr(profile, "department", None), "name", None),
        getattr(getattr(getattr(profile, "staff", None), "department", None), "name", None),
    ]
    for value in values:
        token = _normalize_role_token(value)
        if token:
            tokens.add(token)
    return tokens


def user_has_role(user, *allowed_role_sets: set[str]) -> bool:
    tokens = resolve_user_role_tokens(user)
    if not tokens:
        return False

    if tokens & ADMIN_ROLE_TOKENS:
        return True

    for role_set in allowed_role_sets:
        if tokens & role_set:
            return True
    return False
