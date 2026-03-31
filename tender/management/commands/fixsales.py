# tender/management/commands/fix_dates.py
from django.core.management.base import BaseCommand
from tender.models import JobActivity
from datetime import timedelta


class Command(BaseCommand):
    help = "Fix scheduled_date for unallocated activities where scheduled_date < sales_date - 5 days"

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply changes. Without this flag, dry run only.',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        qs = JobActivity.objects.filter(
            is_lost=False,
            is_manually_moved=False,
            total_area__gt=0,
            allocation_status='pending',
            sales_date__isnull=False,
            scheduled_date__isnull=False,
        ).select_related('job__farmer', 'activity', 'plot')

        to_fix = []
        for ja in qs:
            threshold = ja.sales_date - timedelta(days=5)
            if ja.scheduled_date < threshold:
                new_date = ja.sales_date + timedelta(days=5)
                to_fix.append((ja, ja.scheduled_date, new_date))

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("No activities need fixing."))
            return

        mode = "APPLYING" if apply else "DRY RUN"
        self.stdout.write(f"\n{mode} — {len(to_fix)} activities to fix:\n")
        self.stdout.write(f"{'JA ID':<8} {'Farmer':<30} {'Activity':<25} {'Plot':<15} {'Sales':<12} {'Old Date':<12} {'New Date':<12}")
        self.stdout.write("-" * 114)

        for ja, old_date, new_date in to_fix:
            farmer = ja.job.farmer.farmer_name if ja.job and ja.job.farmer else "?"
            activity = ja.activity.name if ja.activity else "?"
            plot = ja.plot.name if ja.plot else "?"
            self.stdout.write(
                f"{ja.pk:<8} {farmer:<30} {activity:<25} {plot:<15} {ja.sales_date!s:<12} {old_date!s:<12} {new_date!s:<12}"
            )

            if apply:
                ja.scheduled_date = new_date
                ja.save(update_fields=['scheduled_date', 'updated_at'])

        if apply:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Updated {len(to_fix)} activities."))
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️  Dry run complete. Run with --apply to save changes."))