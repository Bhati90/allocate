# tender/management/commands/recalc_allocation_farmer_rates.py

from contextlib import nullcontext  # if Python <3.11, see note below
from django.core.management.base import BaseCommand
from django.db import transaction

from tender.models import Allocation  # adjust to your app path


class Command(BaseCommand):
    help = (
        "Sync Allocation.farmer_rate with JobActivity.rate_per_acre "
        "and recalculate farmer_amount, mukkadam_amount, profit via save()."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving.",
        )
        parser.add_argument(
            "--activity-id",
            type=int,
            nargs="*",
            help="Optional: limit to allocations of specific JobActivity IDs.",
        )
        parser.add_argument(
            "--cluster-id",
            type=int,
            nargs="*",
            help="Optional: limit to specific cluster IDs.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        activity_ids = options.get("activity_id")
        cluster_ids = options.get("cluster_id")

        qs = Allocation.objects.select_related("job_activity", "job_activity__activity")

        if activity_ids:
            qs = qs.filter(job_activity_id__in=activity_ids)
        if cluster_ids:
            qs = qs.filter(cluster_id__in=cluster_ids)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No Allocation rows to update."))
            return

        self.stdout.write(f"Found {total} Allocation rows to update.")

        updated = 0
        ctx = transaction.atomic() if not dry_run else nullcontext()

        with ctx:
            for alloc in qs.iterator(chunk_size=500):
                ja = alloc.job_activity
                new_farmer_rate = ja.rate_per_acre

                old_farmer_rate = alloc.farmer_rate
                old_farmer_amount = alloc.farmer_amount
                old_mukkadam_amount = alloc.mukkadam_amount
                old_profit = alloc.profit

                # Sync farmer_rate from JobActivity
                alloc.farmer_rate = new_farmer_rate
                # save() will recalc farmer_amount, mukkadam_amount, profit
                alloc.save()

                updated += 1

                if options["verbosity"] >= 2:
                    self.stdout.write(
                        f"Allocation {alloc.id} (JA {ja.id} / {ja.activity.name}): "
                        f"farmer_rate {old_farmer_rate} -> {alloc.farmer_rate}, "
                        f"farmer_amount {old_farmer_amount} -> {alloc.farmer_amount}, "
                        f"mukkadam_amount {old_mukkadam_amount} -> {alloc.mukkadam_amount}, "
                        f"profit {old_profit} -> {alloc.profit}"
                    )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would update {updated} Allocation rows; no changes saved."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Updated {updated} Allocation rows.")
                )
