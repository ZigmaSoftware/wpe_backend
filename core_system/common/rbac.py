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
BLENDING_HEAD_ROLE_TOKENS = {
    "blending_head",
    "blending_incharge",
    "blending_manager",
    "blending_request_approver",
}
PRODUCTION_ROLE_TOKENS = {
    "production",
    "production_user",
    "production_manager",
    "operator",
}

# Extrusion Production / Packing / Weight Verification / Sticker / Scrap KPI module
# (Extrusion_Scrap_Packing_KPI_FRD_V1_0). Additive role tokens — do not remove or
# repurpose the sets above for this module.
EXTRUSION_PRODUCTION_ROLE_TOKENS = PRODUCTION_ROLE_TOKENS | {
    "extrusion_production_user",
    "extrusion_production",
}
EXTRUSION_QUALITY_INSPECTOR_ROLE_TOKENS = {
    "quality_inspector",
    "extrusion_quality_inspector",
    "qc_inspector",
    "qc",
}
EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS = {
    "packing_operator",
    "extrusion_packing_operator",
    "packing",
}
EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS = {
    "weighing_operator",
    "extrusion_weighing_operator",
    "weighing",
}
EXTRUSION_QC_APPROVER_ROLE_TOKENS = {
    "qc_approver",
    "extrusion_qc_approver",
}
EXTRUSION_WAREHOUSE_ROLE_TOKENS = {
    "warehouse_user",
    "extrusion_warehouse_user",
    "warehouse",
}
EXTRUSION_SUPERVISOR_ROLE_TOKENS = {
    "supervisor",
    "extrusion_supervisor",
    "administrator",
}
EXTRUSION_ALL_ROLE_TOKENS = (
    EXTRUSION_PRODUCTION_ROLE_TOKENS
    | EXTRUSION_QUALITY_INSPECTOR_ROLE_TOKENS
    | EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS
    | EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS
    | EXTRUSION_QC_APPROVER_ROLE_TOKENS
    | EXTRUSION_WAREHOUSE_ROLE_TOKENS
    | EXTRUSION_SUPERVISOR_ROLE_TOKENS
)


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
        getattr(getattr(getattr(profile, "user_type", None), "role", None), "name", None),
        getattr(
            getattr(getattr(getattr(profile, "user_type", None), "role", None), "designation", None),
            "name",
            None,
        ),
        getattr(getattr(profile, "role", None), "name", None),
        getattr(getattr(profile, "department", None), "name", None),
        getattr(getattr(getattr(profile, "staff", None), "department", None), "name", None),
        getattr(getattr(getattr(profile, "staff", None), "designation_master", None), "name", None),
        getattr(getattr(getattr(profile, "staff", None), "role_master", None), "name", None),
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
