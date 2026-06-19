from django.conf import settings
from django.db import migrations, models


def forwards(apps, schema_editor):
    StockRequest = apps.get_model("store", "StockRequest")

    releasable_statuses = {"APPROVED", "PARTIALLY_APPROVED"}
    for stock_request in StockRequest.objects.filter(status__in=releasable_statuses).iterator():
        stock_request.release_action_by_id = stock_request.action_by_id
        stock_request.release_action_at = stock_request.action_at
        stock_request.release_remarks = stock_request.approval_remarks
        stock_request.status = "CLOSED_WON"
        stock_request.save(
            update_fields=[
                "release_action_by",
                "release_action_at",
                "release_remarks",
                "status",
            ]
        )

    StockRequest.objects.filter(status="PENDING_STORE_ISSUE").update(status="PENDING_REQUEST_PROCESS")
    StockRequest.objects.filter(status="REJECTED").update(status="REQUEST_REJECTED")


def backwards(apps, schema_editor):
    StockRequest = apps.get_model("store", "StockRequest")

    for stock_request in StockRequest.objects.filter(status="CLOSED_WON").iterator():
        stock_request.status = "APPROVED"
        if stock_request.release_remarks:
            stock_request.approval_remarks = stock_request.release_remarks
        if stock_request.release_action_by_id:
            stock_request.action_by_id = stock_request.release_action_by_id
        if stock_request.release_action_at:
            stock_request.action_at = stock_request.release_action_at
        stock_request.save(
            update_fields=[
                "status",
                "approval_remarks",
                "action_by",
                "action_at",
            ]
        )

    StockRequest.objects.filter(status="PENDING_REQUEST_PROCESS").update(status="PENDING_STORE_ISSUE")
    StockRequest.objects.filter(status="REQUEST_REJECTED").update(status="REJECTED")


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0009_stockrequest_head_action_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="stockrequest",
            name="release_action_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="release_action_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="released_store_stock_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="release_remarks",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="stockrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING_HEAD_APPROVAL", "Pending Head Approval"),
                    ("PENDING_REQUEST_PROCESS", "Pending Request Process"),
                    ("PENDING_STOCK_RELEASE", "Pending Stock Release"),
                    ("HEAD_REJECTED", "Rejected by Head"),
                    ("REQUEST_REJECTED", "Rejected During Request Process"),
                    ("RELEASE_REJECTED", "Rejected During Stock Release"),
                    ("CLOSED_WON", "Closed Won"),
                    ("CANCELLED", "Cancelled"),
                ],
                db_index=True,
                default="PENDING_HEAD_APPROVAL",
                max_length=25,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
