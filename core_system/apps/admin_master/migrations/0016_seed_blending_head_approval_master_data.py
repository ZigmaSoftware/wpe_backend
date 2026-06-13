from django.db import migrations


def seed_blending_head_approval_master_data(apps, schema_editor):
    DepartmentMaster = apps.get_model("wpe_masters", "DepartmentMaster")
    DesignationMaster = apps.get_model("wpe_masters", "DesignationMaster")
    RoleMaster = apps.get_model("wpe_masters", "RoleMaster")
    UserType = apps.get_model("admin_master", "UserType")

    department, _ = DepartmentMaster.objects.get_or_create(
        name="Blending",
        defaults={"description": "Blending department"},
    )
    designation, _ = DesignationMaster.objects.get_or_create(
        department=department,
        name="Blending Head",
        defaults={"description": "Approves Blending Store Requests before Store issue."},
    )
    role, _ = RoleMaster.objects.get_or_create(
        name="Blending Request Approver",
        defaults={
            "designation": designation,
            "description": "Approves Blending Store Requests.",
        },
    )
    if role.designation_id != designation.id:
        role.designation_id = designation.id
        role.save(update_fields=["designation"])

    UserType.objects.update_or_create(
        name="Blending Head",
        defaults={
            "code": "BLENDING_HEAD",
            "department": department,
            "role": role,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0015_merge_20260613_0459"),
        ("wpe_masters", "0012_locationmaster_center_type"),
    ]

    operations = [
        migrations.RunPython(seed_blending_head_approval_master_data, migrations.RunPython.noop),
    ]
