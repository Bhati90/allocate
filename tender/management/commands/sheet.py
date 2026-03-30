# your_app/management/commands/sync_to_sheets.py
from django.core.management.base import BaseCommand
from tender.sheets_sync import get_sheet, _HEADERS_WITH_KEY, _job_activity_to_row
from tender.models import JobActivity


class Command(BaseCommand):
    help = "Bulk sync all JobActivities to Google Sheets"

    def handle(self, *args, **options):
        ws = get_sheet()
        ws.clear()

        qs = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters", "allocations__mukkadam")
            .filter(total_area__gt=0)      # ADD THIS — exclude acre <= 0
            .order_by("scheduled_date")
        )

        rows = [_HEADERS_WITH_KEY]
        for ja in qs:
            rows.append(_job_activity_to_row(ja))

        ws.update("A1", rows)

        self.stdout.write(
            self.style.SUCCESS(f"Synced {len(rows) - 1} job activities to sheet")
        )