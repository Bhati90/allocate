# your_app/management/commands/sync_to_sheets.py
"""
Bulk sync all JobActivities to Google Sheets.

Usage:
    python manage.py sync_to_sheets            # full wipe + rewrite
    python manage.py sync_to_sheets --dry-run  # count rows only, no write

Optimisations vs original:
  - Streams DB rows in chunks of 500 with .iterator() — flat RAM regardless of row count
  - Writes to Sheets in 500-row chunks — avoids 10 MB API payload limit
  - Zero extra DB queries per row — _job_activity_to_row() uses only the prefetch cache
"""

from django.core.management.base import BaseCommand
from tender.sheets_sync import (
    get_sheet,
    _HEADERS_WITH_KEY,
    _job_activity_to_row,
    _CHUNK_SIZE,
)
from tender.models import JobActivity


class Command(BaseCommand):
    help = "Bulk sync all JobActivities to Google Sheets (chunked, low RAM)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count rows and exit without writing to Sheets.",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=_CHUNK_SIZE,
            help=f"Rows per Sheets API write (default: {_CHUNK_SIZE}).",
        )

    def handle(self, *args, **options):
        dry_run    = options["dry_run"]
        chunk_size = options["chunk_size"]

        qs = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters", "allocations__mukkadam")
            .filter(total_area__gt=0, is_lost=False)
            .order_by("scheduled_date", "pk")
        )

        if dry_run:
            count = qs.count()
            self.stdout.write(self.style.WARNING(
                f"[Dry run] Would sync {count} job activities — no writes made."
            ))
            return

        ws = get_sheet()
        self.stdout.write("Clearing sheet…")
        ws.clear()
        ws.append_row(_HEADERS_WITH_KEY)

        total     = 0
        sheet_row = 2       # row 1 = header
        chunk     = []

        self.stdout.write(f"Streaming rows in chunks of {chunk_size}…")

        for ja in qs.iterator(chunk_size=chunk_size):
            chunk.append(_job_activity_to_row(ja))

            if len(chunk) >= chunk_size:
                ws.update(
                    f"A{sheet_row}:M{sheet_row + len(chunk) - 1}",
                    chunk,
                    value_input_option="USER_ENTERED",
                )
                sheet_row += len(chunk)
                total     += len(chunk)
                self.stdout.write(f"  … {total} rows written")
                chunk = []

        # Final partial chunk
        if chunk:
            ws.update(
                f"A{sheet_row}:M{sheet_row + len(chunk) - 1}",
                chunk,
                value_input_option="USER_ENTERED",
            )
            total += len(chunk)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Synced {total} job activities to Google Sheets."
        ))