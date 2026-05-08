"""Validation helpers for common master entities."""

from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


MOBILE_NUMBER_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")
PHONE_NUMBER_PATTERN = re.compile(r"^\+?[0-9][0-9\-\s]{5,19}$")
GST_NUMBER_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
PAN_NUMBER_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_CODE_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
SWIFT_CODE_PATTERN = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
PINCODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-\s]{2,11}$")
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2,3}$")
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3,10}$")

ALLOWED_DOCUMENT_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "doc",
    "docx",
    "xls",
    "xlsx",
}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def blank_to_none(value):
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def normalize_name(value: str | None, *, field_label: str) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None
    return " ".join(text.split())


def normalize_country_code(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not COUNTRY_CODE_PATTERN.match(normalized):
        raise ValidationError("Country code must be a valid ISO alpha-2 or alpha-3 code.")
    return normalized


def normalize_currency_code(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
    if not CURRENCY_CODE_PATTERN.match(normalized):
        raise ValidationError("Currency code must contain 3 to 10 uppercase letters or digits.")
    return normalized


def normalize_mobile_number(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.replace(" ", "").replace("-", "")
    if not MOBILE_NUMBER_PATTERN.match(normalized):
        raise ValidationError("Enter a valid mobile number with 10 to 15 digits.")
    return normalized.lstrip("+")


def normalize_phone_number(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.strip()
    compact = normalized.replace(" ", "").replace("-", "")
    if not PHONE_NUMBER_PATTERN.match(normalized) or not compact.lstrip("+").isdigit():
        raise ValidationError("Enter a valid phone number.")
    return compact.lstrip("+")


def normalize_pan_number(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not PAN_NUMBER_PATTERN.match(normalized):
        raise ValidationError("Enter a valid PAN number.")
    return normalized


def normalize_gst_number(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not GST_NUMBER_PATTERN.match(normalized):
        raise ValidationError("Enter a valid GST number.")
    return normalized


def normalize_ifsc_code(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not IFSC_CODE_PATTERN.match(normalized):
        raise ValidationError("Enter a valid IFSC code.")
    return normalized


def normalize_swift_code(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not SWIFT_CODE_PATTERN.match(normalized):
        raise ValidationError("Enter a valid SWIFT code.")
    return normalized


def normalize_pincode(value: str | None) -> str | None:
    text = blank_to_none(value)
    if text is None:
        return None

    normalized = text.upper()
    if not PINCODE_PATTERN.match(normalized):
        raise ValidationError("Enter a valid pincode or postal code.")
    return normalized


def validate_tax_percentage(value) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Enter a valid tax percentage.") from exc

    if decimal_value < Decimal("0") or decimal_value > Decimal("100"):
        raise ValidationError("Tax percentage must be between 0 and 100.")
    return decimal_value


def validate_uploaded_document(file_obj) -> None:
    if not file_obj:
        return

    extension = os.path.splitext(file_obj.name or "")[1].lower().lstrip(".")
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type. Allowed extensions: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
        )

    if getattr(file_obj, "size", 0) > MAX_DOCUMENT_SIZE:
        raise ValidationError("Document size must not exceed 10 MB.")


def validate_state_country_relationship(*, state=None, country=None) -> None:
    if state is not None and country is not None and state.country_id != country.id:
        raise ValidationError({"state": "Selected state does not belong to the selected country."})


def validate_city_state_country_relationship(*, city=None, state=None, country=None) -> None:
    if city is None:
        return

    if state is not None and city.state_id != state.id:
        raise ValidationError({"city": "Selected city does not belong to the selected state."})

    if country is not None and city.country_id != country.id:
        raise ValidationError({"city": "Selected city does not belong to the selected country."})
