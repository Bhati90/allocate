import os
import sys
import django

# ── Django setup ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")  # ← your project name
django.setup()

# ── Imports (after django.setup) ─────────────────────────────────────────────
from collections import defaultdict

# ← Change 'yourapp' to the app where FarmerBillWebhookLog is defined
from tender.models import FarmerBillWebhookLog


# ── Fetch all logs ────────────────────────────────────────────────────────────
logs = FarmerBillWebhookLog.objects.exclude(full_payload__isnull=True)
print(f"\nTotal logs found: {logs.count()}")

# ── Aggregate acres per activity ──────────────────────────────────────────────
activity_acres   = defaultdict(float)
activity_entries = defaultdict(list)

for log in logs:
    payload   = log.full_payload
    work_done = payload.get("work_done", [])

    for entry in work_done:
        activity   = entry.get("activity", "Unknown Activity")
        acres_done = float(entry.get("acres_done", 0) or 0)

        activity_acres[activity] += acres_done
        activity_entries[activity].append({
            "date":          entry.get("date", ""),
            "plot_name":     entry.get("plot_name", ""),
            "acres_done":    acres_done,
            "rate_per_acre": entry.get("rate_per_acre", ""),
            "amount":        entry.get("amount", ""),
            "job_id":        log.job_id or "",
            "farmer_name":   log.farmer_name or "",
            "cluster":       str(log.cluster) if log.cluster else "—",
        })

# ── Summary Table ─────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(f"{'ACTIVITY':<38} {'TOTAL ACRES':>12}  {'RECORDS':>8}")
print("=" * 65)

grand_total = 0.0
for activity, total_acres in sorted(activity_acres.items(), key=lambda x: -x[1]):
    count        = len(activity_entries[activity])
    grand_total += total_acres
    print(f"{activity:<38} {total_acres:>12.2f}  {count:>8}")

print("-" * 65)
print(f"{'GRAND TOTAL':<38} {grand_total:>12.2f}")
print("=" * 65)

# ── Detail Breakdown per Activity ─────────────────────────────────────────────
print("\n\n DETAIL BREAKDOWN")
for activity, rows in sorted(activity_entries.items()):
    total = sum(r["acres_done"] for r in rows)
    print(f"\n{'─'*80}")
    print(f"  Activity : {activity}")
    print(f"  Records  : {len(rows)}    Total Acres: {total:.2f}")
    print(f"{'─'*80}")
    print(f"  {'Date':<12} {'Plot':<22} {'Acres':>6}  {'Rate':>8}  {'Farmer':<25} Cluster")
    print(f"  {'─'*12} {'─'*22} {'─'*6}  {'─'*8}  {'─'*25} {'─'*15}")
    for r in rows:
        print(
            f"  {str(r['date']):<12} "
            f"{str(r['plot_name']):<22} "
            f"{r['acres_done']:>6.2f}  "
            f"{str(r['rate_per_acre']):>8}  "
            f"{str(r['farmer_name']):<25} "
            f"{r['cluster']}"
        )