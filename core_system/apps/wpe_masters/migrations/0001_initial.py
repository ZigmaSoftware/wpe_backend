import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LocationMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_location_master", "ordering": ["name"], "verbose_name": "Location Master", "verbose_name_plural": "Location Masters"},
        ),
        migrations.CreateModel(
            name="BranchMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_branch_master", "ordering": ["name"], "verbose_name": "Branch Master", "verbose_name_plural": "Branch Masters"},
        ),
        migrations.CreateModel(
            name="PriceBookMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_price_book_master", "ordering": ["name"], "verbose_name": "Price Book Master", "verbose_name_plural": "Price Book Masters"},
        ),
        migrations.CreateModel(
            name="WarehouseMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_warehouse_master", "ordering": ["name"], "verbose_name": "Warehouse Master", "verbose_name_plural": "Warehouse Masters"},
        ),
        migrations.CreateModel(
            name="ProductionTypeMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_production_type_master", "ordering": ["name"], "verbose_name": "Production Type Master", "verbose_name_plural": "Production Type Masters"},
        ),
        migrations.CreateModel(
            name="SaleTypeMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_sale_type_master", "ordering": ["name"], "verbose_name": "Sale Type Master", "verbose_name_plural": "Sale Type Masters"},
        ),
        migrations.CreateModel(
            name="PurchaseTypeMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_purchase_type_master", "ordering": ["name"], "verbose_name": "Purchase Type Master", "verbose_name_plural": "Purchase Type Masters"},
        ),
        migrations.CreateModel(
            name="RoleMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_role_master", "ordering": ["name"], "verbose_name": "Role Master", "verbose_name_plural": "Role Masters"},
        ),
        migrations.CreateModel(
            name="DepartmentMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(db_index=True, max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={"db_table": "wpe_department_master", "ordering": ["name"], "verbose_name": "Department Master", "verbose_name_plural": "Department Masters"},
        ),
        migrations.CreateModel(
            name="WPEUserCreation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("full_name", models.CharField(max_length=200)),
                ("job_title", models.CharField(blank=True, max_length=200)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone_no", models.CharField(blank=True, max_length=20)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="wpe_profile", to=settings.AUTH_USER_MODEL)),
                ("location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="users", to="wpe_masters.locationmaster")),
                ("default_branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="default_branch_users", to="wpe_masters.branchmaster")),
                ("role", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="users", to="wpe_masters.rolemaster")),
                ("authorized_branches", models.ManyToManyField(blank=True, related_name="authorized_branch_users", to="wpe_masters.branchmaster")),
                ("authorized_price_books", models.ManyToManyField(blank=True, related_name="authorized_users", to="wpe_masters.pricebookmaster")),
                ("authorized_warehouses", models.ManyToManyField(blank=True, related_name="authorized_users", to="wpe_masters.warehousemaster")),
                ("authorized_production_types", models.ManyToManyField(blank=True, related_name="authorized_users", to="wpe_masters.productiontypemaster")),
                ("authorized_sale_types", models.ManyToManyField(blank=True, related_name="authorized_users", to="wpe_masters.saletypemaster")),
                ("authorized_purchase_types", models.ManyToManyField(blank=True, related_name="authorized_users", to="wpe_masters.purchasetypemaster")),
            ],
            options={"db_table": "wpe_user_creation", "ordering": ["-created_at"], "verbose_name": "WPE User Creation", "verbose_name_plural": "WPE User Creations"},
        ),
    ]
