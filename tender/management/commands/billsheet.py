"""
Management command: billsheet
"""

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from collections import defaultdict

from tender.models import FarmerBillWebhookLog


class Command(BaseCommand):
    help = "Bulk sync FarmerBillWebhookLog records to Google Sheet"

    def add_arguments(self, parser):
        parser.add_argument("--farmer-id",  type=str,  help="Sync only a specific farmer")
        parser.add_argument("--from-date",  type=str,  help="Sync records from date (YYYY-MM-DD)")
        parser.add_argument("--dry-run",    action="store_true", help="Preview without sending")
        parser.add_argument("--batch-size", type=int,  default=50)
        parser.add_argument("--url",        type=str)
        parser.add_argument("--debug",      action="store_true", help="Print raw Apps Script response")

    def handle(self, *args, **options):
        qs = FarmerBillWebhookLog.objects.all().order_by("farmer_id", "job_id", "created_at")

        if options["farmer_id"]:
            qs = qs.filter(farmer_id=options["farmer_id"])

        if options["from_date"]:
            d = parse_date(options["from_date"])
            qs = qs.filter(created_at__date__gte=d)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Found {total} records to sync"))

        if options["dry_run"]:
            self._preview(qs)
            return

        webhook_url = options.get("url") or getattr(settings, "GOOGLE_SHEET_WEBHOOK_URL", None)

        if not webhook_url:
            self.stdout.write(self.style.ERROR(
                "\n❌ No webhook URL.\n"
                "Add to settings.py:\n"
                "    GOOGLE_SHEET_WEBHOOK_URL = 'https://script.google.com/macros/s/YOUR_ID/exec'\n"
                "Or pass: --url 'https://...'\n"
            ))
            return

        self._sync(qs, webhook_url=webhook_url,
                   batch_size=options["batch_size"], debug=options["debug"])

    def _preview(self, qs):
        payloads = self._build_payloads(qs)
        self.stdout.write(self.style.WARNING("\n[DRY RUN]\n"))
        for p in payloads:
            self.stdout.write(
                f"  Farmer {str(p['farmer_id']):>8} | Job {str(p['job_id']):>6} | "
                f"{p['farmer_name']:<35} | [{p['activity_name']}] | "
                f"₹{p['total_billed']:>10,.0f} | Balance ₹{p['balance_due']:>10,.0f} | {p['status']}"
            )
        self.stdout.write(f"\nTotal payloads: {len(payloads)}")

    def _sync(self, qs, webhook_url, batch_size, debug=False):
        payloads = self._build_payloads(qs)
        success = failed = 0

        for i, payload in enumerate(payloads, 1):
            try:
                resp = requests.post(webhook_url, json=payload, timeout=15)
                resp.raise_for_status()

                raw = resp.text

                if debug:
                    self.stdout.write(self.style.WARNING(f"  RAW RESPONSE: {raw[:500]}"))

                try:
                    result = resp.json()
                except Exception:
                    self.stdout.write(self.style.ERROR(
                        f"[{i}/{len(payloads)}] ⚠️  Farmer {payload['farmer_id']} "
                        f"Job {payload['job_id']} — not JSON:\n{raw[:300]}"
                    ))
                    failed += 1
                    continue

                action = result.get("action", "?")
                row    = result.get("row", "?")
                status = result.get("status", "?")
                err    = result.get("message", "")

                if status == "error":
                    self.stdout.write(self.style.ERROR(
                        f"[{i}/{len(payloads)}] ❌ Farmer {payload['farmer_id']} "
                        f"Job {payload['job_id']} [{payload['activity_name']}] — {err}"
                    ))
                    failed += 1
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"[{i}/{len(payloads)}] ✅ Farmer {payload['farmer_id']} "
                        f"Job {payload['job_id']} [{payload['activity_name']}] → {action} row {row}"
                    ))
                    success += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"[{i}/{len(payloads)}] ❌ Farmer {payload['farmer_id']} "
                    f"Job {payload['job_id']} [{payload['activity_name']}] failed: {e}"
                ))
                failed += 1

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"Done: {success} synced, {failed} failed"))
    def _build_payloads(self, qs):
        job_logs = defaultdict(list)
        for log in qs:
            key = (str(log.farmer_id), str(log.job_id or ""))
            job_logs[key].append(log)

        payloads = []
        for (farmer_id, job_id), logs in job_logs.items():
            last_log = logs[-1]

            all_plots   = set()
            total_acres = 0.0
            activity_acres = defaultdict(float)   # ← NEW

            for log in logs:
                try:
                    work_done = (log.full_payload or {}).get("work_done", [])
                    for w in work_done:
                        plot = w.get("plot_name", "").strip()
                        if plot:
                            all_plots.add(plot)
                        acres = w.get("acres_done", 0)
                        if acres:
                            total_acres += float(acres)
                            # ← NEW: accumulate per activity
                            act = log.activity_name or "Unknown Activity"
                            activity_acres[act] += float(acres)
                except Exception:
                    pass

            seen_activities = set()
            for log in logs:
                activity = log.activity_name or "Unknown Activity"
                if activity in seen_activities:
                    continue
                seen_activities.add(activity)

                plots_done = f"{len(all_plots)}/{len(all_plots)}" if all_plots else "?"

                generated_at = ""
                if log.created_at:
                    from django.utils.timezone import localtime
                    generated_at = localtime(log.created_at).strftime("%d %b %Y, %I:%M %p")

                payloads.append({
                    "farmer_id"      : farmer_id,
                    "farmer_name"    : log.farmer_name or "",
                    "job_id"         : job_id,
                    "poc"            : log.sent_by_name or "",
                    "plots_done"     : plots_done,
                    "total_acres"    : round(total_acres, 2),
                    "activity_name"  : activity,
                    "activity_acres" : round(activity_acres[activity], 2),  # ← NEW
                    "total_billed"   : float(log.total_billed or 0),
                    "total_paid"     : float(log.total_paid or 0),
                    "balance_due"    : float(last_log.balance_due or 0),
                    "status"         : "✅ Paid" if float(last_log.balance_due or 0) <= 0 else "Generated",
                    "generated_at"   : generated_at,
                })

        return payloads