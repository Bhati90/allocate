

import os
import django
import json
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from tender.models import JobActivity
API_URL   = "https://ops.bharatintelligence.ai/ops/allocation_booked_visits/"
API_TOKEN = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"  # replace with your actual token

# ── STEP 1: Fetch from API (tender only) ─────────────────────────────────────
print("Fetching from API...")
api_job_activities = {}  # job_id → set of (activity_name, plot_id)
total_jobs_seen    = 0
url = API_URL

while url:
    resp = requests.get(url, headers={"Authorization": f"Token {API_TOKEN}"}, timeout=15)
    if resp.status_code != 200:
        print(f"API error: {resp.status_code}")
        break

    payload = resp.json()
    jobs    = payload.get("data") or payload.get("results") or []

    for job in jobs:
        total_jobs_seen += 1

        # ── Only process tender bookings ──────────────────────
        booking      = job.get("booking") or {}
        booking_type = (booking.get("booking_type") or "").strip().lower()
        if booking_type != "tender":
            continue

        job_id = str(job.get("id"))
        pairs  = set()
        for act in (job.get("activities") or []):
            activity_name = (act.get("activity_name") or "").strip()
            plot_id       = str(act.get("plot_id") or "").strip()
            pairs.add((activity_name, plot_id))
        api_job_activities[job_id] = pairs

    url = payload.get("next")

print(f"  Total jobs seen in API : {total_jobs_seen}")
print(f"  Tender jobs only       : {len(api_job_activities)}")

# ── STEP 2: Fetch from DB (tender jobs only) ──────────────────────────────────
print("\nFetching from DB...")
tender_job_ids = set(api_job_activities.keys())

db_job_activities = {}  # job_id → set of (activity_name, plot_code)

for ja in JobActivity.objects.filter(
    job_id__in=tender_job_ids
).select_related('activity', 'job', 'plot'):
    job_id        = str(ja.job_id)
    activity_name = ja.activity.name.strip()
    plot_code     = str(ja.plot.plot_code or "").strip() if ja.plot else ""
    db_job_activities.setdefault(job_id, set()).add((activity_name, plot_code))

print(f"  Tender jobs in DB      : {len(db_job_activities)}")

# ── STEP 3: Compare ───────────────────────────────────────────────────────────
print("\nComparing...")
all_job_ids   = set(api_job_activities.keys()) | set(db_job_activities.keys())
in_api_not_db = []
in_db_not_api = []

def fmt(pairs):
    return [{"activity_name": a, "plot_code": p} for a, p in sorted(pairs)]

for job_id in sorted(all_job_ids):
    api_pairs = api_job_activities.get(job_id, set())
    db_pairs  = db_job_activities.get(job_id, set())

    missing_in_db  = api_pairs - db_pairs
    missing_in_api = db_pairs  - api_pairs

    if missing_in_db:
        in_api_not_db.append({
            "job_id":        job_id,
            "missing_in_db": fmt(missing_in_db),
            "api_pairs":     fmt(api_pairs),
            "db_pairs":      fmt(db_pairs),
        })

    if missing_in_api:
        in_db_not_api.append({
            "job_id":          job_id,
            "missing_in_api":  fmt(missing_in_api),
            "api_pairs":       fmt(api_pairs),
            "db_pairs":        fmt(db_pairs),
        })

# ── STEP 4: Save to JSON ──────────────────────────────────────────────────────
result = {
    "summary": {
        "total_api_jobs_seen":                total_jobs_seen,
        "total_tender_jobs_in_api":           len(api_job_activities),
        "total_tender_jobs_in_db":            len(db_job_activities),
        "jobs_with_activities_in_api_not_db": len(in_api_not_db),
        "jobs_with_activities_in_db_not_api": len(in_db_not_api),
    },
    "in_api_not_in_db": in_api_not_db,
    "in_db_not_in_api": in_db_not_api,
}

with open("activity_check.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

# ── STEP 5: Print summary ─────────────────────────────────────────────────────
print("\n" + "="*60)
print(f"  Total jobs seen in API            : {total_jobs_seen}")
print(f"  Tender jobs in API                : {len(api_job_activities)}")
print(f"  Tender jobs in DB                 : {len(db_job_activities)}")
print(f"  Jobs: activities in API not DB    : {len(in_api_not_db)}")
print(f"  Jobs: activities in DB not API    : {len(in_db_not_api)}")
print("="*60)

if in_api_not_db:
    print("\n⚠️  IN API BUT MISSING IN DB:")
    for row in in_api_not_db:
        print(f"\n  Job {row['job_id']}:")
        for item in row['missing_in_db']:
            print(f"    - {item['activity_name']} | plot_code: {item['plot_code'] or '(none)'}")

if in_db_not_api:
    print("\n⚠️  IN DB BUT MISSING IN API:")
    for row in in_db_not_api:
        print(f"\n  Job {row['job_id']}:")
        for item in row['missing_in_api']:
            print(f"    - {item['activity_name']} | plot_code: {item['plot_code'] or '(none)'}")

if not in_api_not_db and not in_db_not_api:
    print("\n✅ All tender activity + plot combinations match perfectly!")

print("\n✅ Full report saved to activity_check.json")