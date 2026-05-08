"""Bootstrap helper for shared common-master seed data in development."""

import os

from django.conf import settings

from .models import CommonMaster, Continent


def ensure_dev_common_master_data() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    for continent_name in [
        "Asia",
        "Europe",
        "Africa",
        "North America",
        "South America",
        "Antarctica",
        "Australia",
    ]:
        Continent.objects.get_or_create(name=continent_name, defaults={"status": True})

    for city_type in ["Metro", "Urban", "Rural"]:
        CommonMaster.objects.get_or_create(
            type="CITY_TYPE",
            name=city_type,
            defaults={"is_active": True},
        )
