from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, ExpressionWrapper, DateField
from datetime import timedelta

from tender.models import JobActivity  # ← adjust import


# ── Excluded for ALL clusters (including cluster 10) ─────────────────────────
EXCLUDED_ALL_CLUSTERS = frozenset([
    "Pruning (छाटणी)",
    "Pruning (छाटणी) 1",
    "Pruning (छाटणी) 2",
    "Hand Pasting (पेस्टींग)",
    "Cordan Tying (ओलांढे बांधणे)",
    "Cordan Tying (सुटलेले ओलांढे बांधणे)",
    "Full Cordan Tying",
    "Full Cordan Tying (सरसकट ओलांढे बांधणे)",
])

# ── ADDITIONALLY excluded only for cluster 10 ─────────────────────────────────
EXCLUDED_CLUSTER_10_ONLY = frozenset([
    "Shoot Selection (विरळणी)",
    "Shoot Selection (विरळणी) 1",
    "Subcane (सबकेन) 1",
    "Subcane (सबकेन) 2",
    "Subcane (सबकेन) 3",
])

# Combined for cluster 10
EXCLUDED_CLUSTER_10 = EXCLUDED_ALL_CLUSTERS | EXCLUDED_CLUSTER_10_ONLY

SHIFT_DAYS = 28
# ─────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = (
        f"Shift scheduled_date by +{SHIFT_DAYS} days for eligible JobActivities. "
        "Cluster 10 has a stricter exclusion list than all other clusters."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview affected rows without writing to DB",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # ── Cluster 10 queryset ───────────────────────────────────────────────
        qs_cluster10 = JobActivity.objects.filter(
            job__clusters__id=10,
            scheduled_date__isnull=False,
        ).exclude(
            activity__name__in=EXCLUDED_CLUSTER_10,
        )

        # ── All other clusters queryset ───────────────────────────────────────
        qs_others = JobActivity.objects.filter(
            scheduled_date__isnull=False,
        ).exclude(
            job__clusters__id=10,          # skip cluster 10 entirely
        ).exclude(
            activity__name__in=EXCLUDED_ALL_CLUSTERS,
        )

        count_10     = qs_cluster10.count()
        count_others = qs_others.count()
        total        = count_10 + count_others

        if total == 0:
            self.stdout.write(self.style.WARNING("No matching activities found."))
            return

        self.stdout.write(
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"Cluster 10   → {count_10} activities to shift\n"
            f"Other clusters → {count_others} activities to shift\n"
            f"Total          → {total} rows\n"
        )

        if dry_run:
            self.stdout.write("\n── Cluster 10 Preview (capped at 50) ──")
            self._print_preview(qs_cluster10, limit=50)
            self.stdout.write("\n── Other Clusters Preview (capped at 50) ──")
            self._print_preview(qs_others, limit=50)
            return

        confirm = input(f"\nProceed with updating {total} rows? [yes/no]: ").strip().lower()
        if confirm != "yes":
            self.stdout.write(self.style.WARNING("Aborted."))
            return

        with transaction.atomic():
            updated_10 = qs_cluster10.update(
                scheduled_date=ExpressionWrapper(
                    F("scheduled_date") + timedelta(days=SHIFT_DAYS),
                    output_field=DateField(),
                )
            )
            updated_others = qs_others.update(
                scheduled_date=ExpressionWrapper(
                    F("scheduled_date") + timedelta(days=SHIFT_DAYS),
                    output_field=DateField(),
                )
            )

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done.\n"
            f"   Cluster 10     → {updated_10} rows shifted\n"
            f"   Other clusters → {updated_others} rows shifted\n"
            f"   Total          → {updated_10 + updated_others} rows\n"
        ))

    def _print_preview(self, qs, limit=50):
        self.stdout.write(f"{'ID':<8} {'Activity':<50} {'Old Date':<14} {'New Date':<14}")
        self.stdout.write("-" * 90)
        for ja in qs.select_related("activity").order_by("scheduled_date")[:limit]:
            old = ja.scheduled_date
            new = old + timedelta(days=SHIFT_DAYS)
            self.stdout.write(
                f"{ja.pk:<8} {ja.activity.name[:48]:<50} {str(old):<14} {str(new):<14}"
            )
        remaining = qs.count() - limit
        if remaining > 0:
            self.stdout.write(f"  ... and {remaining} more rows.")
