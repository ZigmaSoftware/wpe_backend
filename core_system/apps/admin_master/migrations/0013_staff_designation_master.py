from django.db import migrations, models
import django.db.models.deletion


def populate_staff_designation_master(apps, schema_editor):
    Staff = apps.get_model("admin_master", "Staff")
    DesignationMaster = apps.get_model("wpe_masters", "DesignationMaster")

    for staff in Staff.objects.select_related("role_master", "department_master").all():
        designation_id = None

        role_master = getattr(staff, "role_master", None)
        if role_master and getattr(role_master, "designation_id", None):
            designation_id = role_master.designation_id

        if designation_id is None and staff.designation:
            queryset = DesignationMaster.objects.filter(name__iexact=staff.designation.strip())
            if staff.department_master_id:
                queryset = queryset.filter(department_id=staff.department_master_id)
            match = queryset.order_by("id").first()
            designation_id = getattr(match, "id", None)

        if designation_id and staff.designation_master_id != designation_id:
            staff.designation_master_id = designation_id
            staff.save(update_fields=["designation_master"])


class Migration(migrations.Migration):

    dependencies = [
        ("wpe_masters", "0011_alter_producttypecategory_options_and_more"),
        ("admin_master", "0012_add_designation_admin_screen"),
    ]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="designation_master",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="staff_members",
                to="wpe_masters.designationmaster",
            ),
        ),
        migrations.RunPython(populate_staff_designation_master, migrations.RunPython.noop),
    ]
