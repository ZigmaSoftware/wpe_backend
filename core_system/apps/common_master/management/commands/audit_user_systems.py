from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.admin_master.models import Role, UserCreation, UserType
from apps.login_home.models import Department
from apps.wpe_masters.models import DepartmentMaster, RoleMaster, WPEUserCreation


def normalize_name(value: str) -> str:
    return slugify(value or "").replace("-", "_")


class Command(BaseCommand):
    help = "Audit admin/WPE user systems for conflicting profile links and naming overlap."

    def handle(self, *args, **options):
        shared_auth_users = (
            UserCreation.objects.exclude(user__isnull=True)
            .filter(user_id__in=WPEUserCreation.objects.exclude(user__isnull=True).values("user_id"))
            .select_related("user", "staff", "user_type")
        )
        orphaned_admin_profiles = UserCreation.objects.filter(user__isnull=True)
        orphaned_wpe_profiles = WPEUserCreation.objects.filter(user__isnull=True)

        department_names = {normalize_name(name): name for name in Department.objects.values_list("name", flat=True)}
        department_master_names = {
            normalize_name(name): name for name in DepartmentMaster.objects.values_list("name", flat=True)
        }
        overlapping_departments = sorted(set(department_names).intersection(department_master_names))

        admin_role_names = {normalize_name(name): name for name in Role.objects.values_list("name", flat=True)}
        user_type_names = {normalize_name(name): name for name in UserType.objects.values_list("name", flat=True)}
        wpe_role_names = {normalize_name(name): name for name in RoleMaster.objects.values_list("name", flat=True)}
        overlapping_roles = sorted((set(admin_role_names) | set(user_type_names)).intersection(wpe_role_names))

        self.stdout.write(self.style.MIGRATE_HEADING("User System Audit"))
        self.stdout.write(f"Shared auth users across admin/WPE profiles: {shared_auth_users.count()}")
        for profile in shared_auth_users:
            self.stdout.write(
                f"  - user={profile.user.username} admin_profile={profile.pk} wpe_profile={profile.user.wpe_profile.pk}"
            )

        self.stdout.write(f"Orphaned admin profiles: {orphaned_admin_profiles.count()}")
        for profile in orphaned_admin_profiles[:20]:
            self.stdout.write(f"  - admin_profile={profile.pk} staff={profile.staff_id}")

        self.stdout.write(f"Orphaned WPE profiles: {orphaned_wpe_profiles.count()}")
        for profile in orphaned_wpe_profiles[:20]:
            self.stdout.write(f"  - wpe_profile={profile.pk} full_name={profile.full_name}")

        self.stdout.write(f"Department naming overlap: {len(overlapping_departments)}")
        for key in overlapping_departments:
            self.stdout.write(
                f"  - department={department_names[key]!r} department_master={department_master_names[key]!r}"
            )

        self.stdout.write(f"Role/UserType naming overlap with WPE roles: {len(overlapping_roles)}")
        for key in overlapping_roles:
            admin_role = admin_role_names.get(key)
            user_type = user_type_names.get(key)
            role_master = wpe_role_names.get(key)
            self.stdout.write(
                f"  - normalized={key} role={admin_role!r} user_type={user_type!r} wpe_role={role_master!r}"
            )
