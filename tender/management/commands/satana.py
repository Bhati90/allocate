# tender/management/commands/satana_reprice.py

from decimal import Decimal
from contextlib import nullcontext  # For Python <3.11, see note below

from django.core.management.base import BaseCommand
from django.db import transaction

from tender.models import Cluster, JobActivity, Allocation  # adjust import paths


# ---- RATE CARD FROM YOUR ACTIVITIES LIST ----

RATE_CARD = {
    "Pruning (छाटणी)": Decimal("4000"),
    "Shoot Selection (विरळणी)": Decimal("3000"),
    "1st Lateral Removal (बगल काढणे)": Decimal("2500"),
    "Shenda Stopping (शेंडा स्टॉपिंग)": Decimal("2000"),
    "2nd Laterals Removal & Tendrils Removal (दुसरी बगल बाळी काढणे)": Decimal("4000"),

    "One Time Subcane (सबकेन)": Decimal("2500"),
    "1st Subcane (पहिली सबकेन)": Decimal("1500"),
    "2nd Subcane (दुसरी सबकेन)": Decimal("1500"),
    "3rd Subcane (तिसरी सबकेन)": Decimal("1500"),

    "Hand Pasting (पेस्टींग)": Decimal("2000"),
    "Cordan Tying (सुटलेले ओलांढे बांधणे)": Decimal("500"),
    "Full Cordan Tying (सरसकट ओलांढे बांधणे)": Decimal("1500"),

    "Cane Tying with Clips (काडी बांधणे - क्लिप्स)": Decimal("7500"),
    "Cane Selection (काडी निवड)": Decimal("2500"),
    "Cane Tying with Strings/Thread (सुतळीने काडी बांधणे)": Decimal("5500"),

    "Extra Leaf removal (पाने काढणे)": Decimal("2500"),
    "1st Round Extra Leaf removal": Decimal("2500"),
    "2nd Round Extra Leaf removal": Decimal("2500"),
    "3rd Round Extra Leaf removal": Decimal("2500"),
}


class Command(BaseCommand):
    help = (
        "For Satana,Nashik cluster only: "
        "1) Update JobActivity.rate_per_acre from RATE_CARD based on activity.name, "
        "2) Then sync Allocation.farmer_rate from JobActivity.rate_per_acre."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving.",
        )
        parser.add_argument(
            "--cluster-name",
            type=str,
            default="Satana,Nashik",
            help="Cluster name (default: Satana,Nashik).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cluster_name = options["cluster_name"]

        try:
            cluster = Cluster.objects.get(name=cluster_name)
        except Cluster.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Cluster '{cluster_name}' not found."))
            return

        self.stdout.write(f"Using cluster: {cluster.id} - {cluster.name}")

        ctx = transaction.atomic() if not dry_run else nullcontext()

        with ctx:
            # 1) Update JobActivity.rate_per_acre for jobs in this cluster
            ja_qs = (
                JobActivity.objects
                .select_related("activity", "job")
                .filter(
                    job__clusters=cluster,             # job belongs to this cluster
                    activity__name__in=RATE_CARD.keys()
                )
                .distinct()
            )

            ja_count = ja_qs.count()
            self.stdout.write(f"Found {ja_count} JobActivity rows in '{cluster_name}' to check.")

            ja_updated = 0
            for ja in ja_qs.iterator(chunk_size=500):
                act_name = ja.activity.name
                new_rate = RATE_CARD[act_name]

                if ja.rate_per_acre == new_rate:
                    continue  # already correct

                old_rate = ja.rate_per_acre
                old_total_price = ja.total_price
                old_subtotal = ja.subtotal

                ja.rate_per_acre = new_rate
                ja.save()  # recalculates total_price & subtotal

                ja_updated += 1

                if options["verbosity"] >= 2:
                    self.stdout.write(
                        f"JobActivity {ja.id} [{act_name}]: "
                        f"rate_per_acre {old_rate} -> {ja.rate_per_acre}, "
                        f"total_price {old_total_price} -> {ja.total_price}, "
                        f"subtotal {old_subtotal} -> {ja.subtotal}"
                    )

            self.stdout.write(self.style.SUCCESS(f"JobActivity updated: {ja_updated}"))

            # 2) Sync Allocation.farmer_rate for allocations in this cluster
            alloc_qs = (
                Allocation.objects
                .select_related("job_activity", "job_activity__activity", "job_activity__job", "cluster")
                .filter(
                    job_activity__job__clusters=cluster,
                    job_activity__activity__name__in=RATE_CARD.keys(),
                )
                .distinct()
            )

            alloc_total = alloc_qs.count()
            self.stdout.write(
                f"Found {alloc_total} Allocation rows (via job->cluster) in '{cluster_name}' to check."
            )

            alloc_updated = 0
            for alloc in alloc_qs.iterator(chunk_size=500):
                act_name = alloc.job_activity.activity.name
                new_farmer_rate = RATE_CARD[act_name]

                if alloc.farmer_rate == new_farmer_rate:
                    continue  # already correct

                old_farmer_rate = alloc.farmer_rate
                old_farmer_amount = alloc.farmer_amount
                old_mukkadam_amount = alloc.mukkadam_amount
                old_profit = alloc.profit

                alloc.farmer_rate = new_farmer_rate
                alloc.save()  # allocation.save recalculates amounts & profit

                alloc_updated += 1

                if options["verbosity"] >= 2:
                    self.stdout.write(
                        f"Allocation {alloc.id} [{act_name}]: "
                        f"farmer_rate {old_farmer_rate} -> {alloc.farmer_rate}, "
                        f"farmer_amount {old_farmer_amount} -> {alloc.farmer_amount}, "
                        f"mukkadam_amount {old_mukkadam_amount} -> {alloc.mukkadam_amount}, "
                        f"profit {old_profit} -> {alloc.profit}"
                    )

            self.stdout.write(self.style.SUCCESS(f"Allocations updated: {alloc_updated}"))

            if dry_run:
                raise SystemExit(
                    self.style.WARNING(
                        "[DRY RUN] Transaction rolled back; no changes saved."
                    )
                )
