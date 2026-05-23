from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Alias for seed_all_demo_data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-grn",
            action="store_true",
            help="Do not run the larger GRN/QCR seed command.",
        )
        parser.add_argument(
            "--flush-grn",
            action="store_true",
            help="Delete existing GRN/QCR demo records before seeding GRN data.",
        )

    def handle(self, *args, **options):
        call_command(
            "seed_all_demo_data",
            skip_grn=options["skip_grn"],
            flush_grn=options["flush_grn"],
            verbosity=options.get("verbosity", 1),
        )
