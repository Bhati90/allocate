"""
check_rates.py
--------------
Fetches https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/
and compares each activity's implied rate (total_price / acres) against
your local JobActivity.rate_per_acre.

Skips:
  - total_area == 0
  - is_lost == True

Usage:
    python check_rates.py --token YOUR_AUTH_TOKEN
    python check_rates.py --token YOUR_AUTH_TOKEN --job-ids 2175 2133 884
    python check_rates.py --token YOUR_AUTH_TOKEN --tolerance 1.0
"""

import os
import sys
import argparse
import requests
import django

# ── Django setup ──────────────────────────────────────────────
# Adjust this path to your project root (where manage.py lives)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")  # ← change this
django.setup()

from tender.models import JobActivity  # ← adjust app name if different

# ── Farmer → Job ID mapping (from your list) ─────────────────
FARMER_JOBS = {
    "Abhijit Jibhau Ahire":           [2175, 2133],
    "Ramdas Waman Patil (Rawalgaon)": [2132],
    "Ramdas Waman Patil (Nilwandi)":  [2050],
    "Gorakh Babanrao Pawar":          [2196],
    "Vikram Chintaman Kapadnis":      [884, 885],
    "Punam Dinesh Ahire":             [866, 870],
    "Bansidhar Pandurang Pawar":      [1245],
    "Rajendra Varpe":                 [1574],
    "Navnath Kumbharkar":             [1512],
    "Shobha Trambakrao Chavan":       [1760],
    "Chindu Gangadhar Bornare":       [1749],
    "Anil Prakash Kad":               [2092],
    "Pravin Arjun Varpe":             [1563],
    "Yogeshwar Bajirao Thombare":     [1513],
    "Ramnath Pansare":                [1497],
}

ALL_JOB_IDS = [jid for ids in FARMER_JOBS.values() for jid in ids]

API_URL = "https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/"


def fetch_api(token):
    """Fetch all allocated jobs from API."""
    headers = {"Authorization": f"Token {token}"}
    resp = requests.get(API_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def get_db_activities(job_ids):
    """
    Returns dict: {(job_id, api_activity_id): rate_per_acre}
    Skips is_lost=True and total_area=0.
    """
    qs = JobActivity.objects.filter(
        job__job_id__in=job_ids,
        is_lost=False,
    ).exclude(total_area=0).select_related("job", "activity")

    db = {}
    for ja in qs:
        key = (str(ja.job.job_id), str(ja.api_activity_id))
        db[key] = {
            "rate_per_acre"  : float(ja.rate_per_acre),
            "total_price"    : float(ja.total_price),
            "total_area"     : float(ja.total_area),
            "activity_name"  : ja.activity.name,
            "scheduled_date" : str(ja.scheduled_date),
        }
    return db


def check(token, job_ids=None, tolerance=0.5):
    target_ids = [str(j) for j in (job_ids or ALL_JOB_IDS)]

    print(f"\n{'─'*70}")
    print(f"  Fetching API...")
    api_jobs = fetch_api(token)
    print(f"  API returned {len(api_jobs)} jobs total")

    # Filter only jobs we care about
    relevant = [j for j in api_jobs if str(j["id"]) in target_ids]
    print(f"  Matching our {len(target_ids)} job IDs → found {len(relevant)} in API")

    if not relevant:
        print("\n  ⚠️  None of your job IDs found in API response.")
        return

    # Build API lookup: {(job_id, activity_id): {...}}
    api_lookup = {}
    for job in relevant:
        job_id = str(job["id"])
        for act in job.get("activities", []):
            acres = act.get("acres") or 0
            total_price = act.get("total_price") or 0
            api_rate = round(total_price / acres, 2) if acres else 0
            key = (job_id, str(act["id"]))
            api_lookup[key] = {
                "activity_name": act["activity_name"],
                "acres"        : acres,
                "total_price"  : total_price,
                "api_rate"     : api_rate,
                "plot_id"      : act.get("plot_id"),
                "date"         : act.get("date_time", "")[:10],
            }

    # Fetch DB
    print(f"\n  Querying local DB for job IDs: {target_ids}")
    db_lookup = get_db_activities([int(j) for j in target_ids])
    print(f"  DB returned {len(db_lookup)} active activities\n")

    mismatches = []
    only_in_api = []
    only_in_db  = []

    # Check API activities vs DB
    for key, api_act in api_lookup.items():
        job_id, act_id = key
        if key in db_lookup:
            db_act   = db_lookup[key]
            api_rate = api_act["api_rate"]
            db_rate  = db_act["rate_per_acre"]
            diff     = abs(api_rate - db_rate)
            if diff > tolerance:
                mismatches.append({
                    "job_id"       : job_id,
                    "activity_id"  : act_id,
                    "activity_name": api_act["activity_name"],
                    "plot_id"      : api_act["plot_id"],
                    "date"         : api_act["date"],
                    "acres"        : api_act["acres"],
                    "api_rate"     : api_rate,
                    "db_rate"      : db_rate,
                    "diff"         : round(diff, 2),
                    "api_total"    : api_act["total_price"],
                    "db_total"     : db_act["total_price"],
                })
        else:
            only_in_api.append({
                "job_id"       : job_id,
                "activity_id"  : act_id,
                "activity_name": api_act["activity_name"],
                "plot_id"      : api_act["plot_id"],
                "date"         : api_act["date"],
                "acres"        : api_act["acres"],
                "api_rate"     : api_act["api_rate"],
                "api_total"    : api_act["total_price"],
            })

    # Check DB activities not in API
    for key, db_act in db_lookup.items():
        if key not in api_lookup:
            job_id, act_id = key
            only_in_db.append({
                "job_id"       : job_id,
                "activity_id"  : act_id,
                "activity_name": db_act["activity_name"],
                "db_rate"      : db_act["rate_per_acre"],
                "db_total"     : db_act["total_price"],
                "date"         : db_act["scheduled_date"],
            })

    # ── Print results ─────────────────────────────────────────
    print(f"{'═'*70}")
    print(f"  RATE MISMATCHES  (tolerance ±₹{tolerance}/acre)")
    print(f"{'═'*70}")

    if mismatches:
        for m in sorted(mismatches, key=lambda x: x["job_id"]):
            print(
                f"\n  ❌ Job {m['job_id']} | Act {m['activity_id']} | Plot {m['plot_id']}"
                f"\n     Activity : {m['activity_name']}"
                f"\n     Date     : {m['date']}  |  Acres: {m['acres']}"
                f"\n     API rate : ₹{m['api_rate']}/ac  (total ₹{m['api_total']})"
                f"\n     DB  rate : ₹{m['db_rate']}/ac  (total ₹{m['db_total']})"
                f"\n     Diff     : ₹{m['diff']}/ac"
            )
    else:
        print("\n  ✅ All matched activities have consistent rates!\n")

    if only_in_api:
        print(f"\n{'─'*70}")
        print(f"  IN API but NOT in DB  ({len(only_in_api)} activities)")
        print(f"{'─'*70}")
        for a in only_in_api:
            print(
                f"  Job {a['job_id']} | Act {a['activity_id']} | Plot {a['plot_id']}"
                f" | {a['activity_name']} | {a['date']} | {a['acres']}ac"
                f" | ₹{a['api_rate']}/ac | Total ₹{a['api_total']}"
            )

    if only_in_db:
        print(f"\n{'─'*70}")
        print(f"  IN DB but NOT in API  ({len(only_in_db)} activities)")
        print(f"{'─'*70}")
        for d in only_in_db:
            print(
                f"  Job {d['job_id']} | Act {d['activity_id']}"
                f" | {d['activity_name']} | {d['date']}"
                f" | ₹{d['db_rate']}/ac | Total ₹{d['db_total']}"
            )

    print(f"\n{'─'*70}")
    print(f"  Summary: {len(mismatches)} mismatches | "
          f"{len(only_in_api)} only-in-API | {len(only_in_db)} only-in-DB")
    print(f"{'─'*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check activity rates API vs DB")
    parser.add_argument("--token",     required=True, help="Auth token")
    parser.add_argument("--job-ids",   nargs="*", type=int, help="Specific job IDs to check (default: all)")
    parser.add_argument("--tolerance", type=float, default=0.5, help="Allowed rate diff ₹/ac (default: 0.5)")
    args = parser.parse_args()

    check(
        token     = args.token,
        job_ids   = args.job_ids,
        tolerance = args.tolerance,
    )