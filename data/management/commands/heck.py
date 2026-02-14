# your_app/management/commands/check_activity_amounts.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from data.models import JobActivity, ImportedJobSheet  # adjust app

class Command(BaseCommand):
    help = "Check that JobActivity and ImportedJobSheet money fields match"

    def handle(self, *args, **options):
        mismatches = []

        sheets = ImportedJobSheet.objects.filter(
            data_source__startswith="data_"
        ).select_related("job_activity")

        for sheet in sheets:
            activity = sheet.job_activity
            if not activity:
                mismatches.append(
                    {
                        "sheet_id": sheet.id,
                        "reason": "NO_JOB_ACTIVITY_LINK",
                    }
                )
                continue

            problems = []

            # Normalize nulls to Decimal(0)
            s_total_price = sheet.booking_value or Decimal("0")
            s_transport = sheet.transport_cost or Decimal("0")
            s_other = sheet.other_cost or Decimal("0")
            s_subtotal = sheet.subtotal or Decimal("0")
            s_booking = sheet.booking_value or Decimal("0")
            s_total_booking = sheet.total_booking_value or Decimal("0")

            a_total_price = activity.total_price or Decimal("0")
            a_transport = activity.transport_cost or Decimal("0")
            a_other = activity.other_cost or Decimal("0")
            a_subtotal = activity.subtotal or Decimal("0")

            # Exact equality; if you want tolerance, compare with quantize or +/- epsilon
            if a_total_price != s_total_price:
                problems.append(
                    f"total_price activity={a_total_price} sheet={s_total_price}"
                )
            if a_transport != s_transport:
                problems.append(
                    f"transport_cost activity={a_transport} sheet={s_transport}"
                )
            if a_other != s_other:
                problems.append(
                    f"other_cost activity={a_other} sheet={s_other}"
                )

            # Choose which field you consider the “master” for subtotal
            if a_subtotal != s_subtotal:
                problems.append(
                    f"subtotal activity={a_subtotal} sheet={s_subtotal}"
                )

            # Optional: check booking values too
            if s_total_booking and s_total_booking != a_subtotal:
                problems.append(
                    f"total_booking_value={s_total_booking} != activity_subtotal={a_subtotal}"
                )
            if s_booking and s_booking != a_total_price:
                problems.append(
                    f"booking_value={s_booking} != activity_total_price={a_total_price}"
                )

            if problems:
                mismatches.append(
                    {
                        "sheet_id": sheet.id,
                        "job_activity_id": activity.id,
                        "job_id": activity.job_id,
                        "activity_name": activity.activity_name,
                        "issues": problems,
                    }
                )

        if not mismatches:
            self.stdout.write(self.style.SUCCESS("✅ All matching between JobActivity and ImportedJobSheet"))
        else:
            self.stdout.write(self.style.WARNING(f"❌ Found {len(mismatches)} mismatches"))
            for m in mismatches:
                self.stdout.write("-" * 80)
                self.stdout.write(f"Sheet ID: {m.get('sheet_id')}, JobActivity ID: {m.get('job_activity_id')}")
                self.stdout.write(f"Job ID: {m.get('job_id')}, Activity: {m.get('activity_name')}")
                for issue in m["issues"]:
                    self.stdout.write(f"  - {issue}")
