"""Bootstrap helper for purchase-master seed data in development."""

import os

from django.conf import settings

from apps.common_master.models import Company


def ensure_dev_purchase_master_data() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    for company_name in ["Blue Planet"]:
        Company.objects.get_or_create(
            name=company_name,
            defaults={"code": company_name.upper().replace(" ", "_")}
    )
