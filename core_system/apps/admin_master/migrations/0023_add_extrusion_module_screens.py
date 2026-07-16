from django.db import migrations


ALL_ACTIONS = ["add", "update", "list", "delete", "view", "print"]

# Extrusion Production / Packing / Weight Verification / Sticker / Scrap KPI module
# (FRD Extrusion_Scrap_Packing_KPI_FRD_V1_0). Purely additive — registers new
# screens under the existing "production-workspace" / "production-master"
# sections so the module's roles can be granted access via the existing
# UserType / UserScreen permission system.
WORKSPACE_SCREENS = (
    ("production-extrusion-workorder-workspace", "Extrusion Work Orders", "/app/production/extrusion/work-orders", 20),
    ("production-extrusion-inspection-workspace", "Extrusion Quality Inspection", "/app/production/extrusion/inspections", 21),
    ("production-extrusion-packing-workspace", "Extrusion Packing", "/app/production/extrusion/packing", 22),
    ("production-extrusion-weighing-workspace", "Extrusion Weight Verification", "/app/production/extrusion/weighing", 23),
    ("production-extrusion-sticker-workspace", "Extrusion Sticker & Scan", "/app/production/extrusion/stickers", 24),
    ("production-extrusion-shift-approval-workspace", "Extrusion Shift-End QC Approval", "/app/production/extrusion/shift-approval", 25),
    ("production-extrusion-scrap-workspace", "Extrusion Scrap Management", "/app/production/extrusion/scrap", 26),
    ("production-extrusion-warehouse-workspace", "Extrusion Warehouse Transfer", "/app/production/extrusion/warehouse", 27),
    ("production-extrusion-kpi-dashboard", "Extrusion Scrap KPI Dashboard", "/app/production/extrusion/kpi-dashboard", 28),
)

MASTER_SCREENS = (
    ("production-extrusion-profile-config-master", "Extrusion Profile Config", "/masters/production-masters/extrusion-profile-configs", 20),
    ("production-extrusion-scrap-category-master", "Scrap Category Master", "/masters/production-masters/scrap-categories", 21),
    ("production-extrusion-scrap-reason-master", "Scrap Reason Master", "/masters/production-masters/scrap-reasons", 22),
)


def add_extrusion_screens(apps, schema_editor):
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")

    def _seed(section_code, screen_definitions):
        section = ScreenSection.objects.filter(code=section_code).first()
        if not section:
            return
        for code, name, folder_name, order_no in screen_definitions:
            UserScreen.objects.get_or_create(
                code=code,
                defaults={
                    "main_screen": section.main_screen,
                    "screen_section": section,
                    "screen_name": name,
                    "folder_name": folder_name,
                    "order_no": order_no,
                    "is_active": True,
                    "available_actions": ALL_ACTIONS,
                },
            )

    _seed("production-workspace", WORKSPACE_SCREENS)
    _seed("production-master", MASTER_SCREENS)


def remove_extrusion_screens(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    codes = [code for code, *_ in WORKSPACE_SCREENS] + [code for code, *_ in MASTER_SCREENS]
    UserScreen.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0022_add_tare_master_screen"),
    ]

    operations = [
        migrations.RunPython(add_extrusion_screens, remove_extrusion_screens),
    ]
