from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    label = "inventory"
    verbose_name = "Production Inventory"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from apps.blending.models import BlendingOutward

        from . import signals

        post_save.connect(
            signals.on_blending_outward_saved,
            sender=BlendingOutward,
            dispatch_uid="inventory.blending_outward.post_save",
        )
        post_delete.connect(
            signals.on_blending_outward_deleted,
            sender=BlendingOutward,
            dispatch_uid="inventory.blending_outward.post_delete",
        )
