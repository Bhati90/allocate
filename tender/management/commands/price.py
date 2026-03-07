# tender/management/commands/recalc_activity_rates.py

from decimal import Decimal
from contextlib import nullcontext  # Python 3.11+; for lower versions, see note below

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tender.models import JobActivity, ActivityCatalog  # adjust to your app paths


# Your rate card mapped by ActivityCatalog.name
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
        "Update JobActivity.rate_per_acre from the rate card (by ActivityCatalog.name) "
        "and recalculate total_price & subtotal via JobActivity.save()."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving.",
        )
        parser.add_argument(
            "--activity-name",
            type=str,
            nargs="*",
            help="Optional: limit to specific activity names (ActivityCatalog.name).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        activity_names = options.get("activity_name")

        if not RATE_CARD:
            raise CommandError("RATE_CARD is empty.")

        # Base queryset
        qs = JobActivity.objects.select_related("activity")

        # Restrict to given names (if passed)
        if activity_names:
            qs = qs.filter(activity__name__in=activity_names)

        # Restrict to names present in RATE_CARD
        qs = qs.filter(activity__name__in=RATE_CARD.keys())

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No JobActivity records to update."))
            return

        self.stdout.write(f"Found {total} JobActivity rows to update.")

        updated = 0
        ctx = transaction.atomic() if not dry_run else nullcontext()

        with ctx:
            for ja in qs.iterator(chunk_size=500):
                name = ja.activity.name
                new_rate = RATE_CARD.get(name)
                if new_rate is None:
                    # Should not happen because of the filter, but be safe
                    if options["verbosity"] >= 2:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping JobActivity {ja.id}: no rate found for '{name}'."
                            )
                        )
                    continue

                old_rate = ja.rate_per_acre
                old_total_price = ja.total_price
                old_subtotal = ja.subtotal

                ja.rate_per_acre = new_rate
                # Triggers your save() which recomputes total_price and subtotal
                ja.save()

                updated += 1

                if options["verbosity"] >= 2:
                    self.stdout.write(
                        f"JobActivity {ja.id} [{name}]: "
                        f"rate_per_acre {old_rate} -> {ja.rate_per_acre}, "
                        f"total_price {old_total_price} -> {ja.total_price}, "
                        f"subtotal {old_subtotal} -> {ja.subtotal}"
                    )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would update {updated} JobActivity rows; no changes saved."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Updated {updated} JobActivity rows.")
                )
