"""
sync_missing_scheduled_dates.py

Fetches jobs from the external API and fills `scheduled_date` ONLY for
JobActivity rows where scheduled_date is currently NULL.

Usage:
    # Dry run — preview what will be filled, no DB writes:
    python sync_missing_scheduled_dates.py --token YOUR_TOKEN

    # Actually write to DB:
    python sync_missing_scheduled_dates.py --token YOUR_TOKEN --apply

Run from Django project root. Set DJANGO_SETTINGS_MODULE if needed:
    DJANGO_SETTINGS_MODULE=config.settings python sync_missing_scheduled_dates.py --token ...
"""

import os
import sys
import django
import argparse
import requests
from datetime import datetime, timezone

# ── Django bootstrap ─────────────────────────────────────────────────────────
def bootstrap_django():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # ⚠️ adjust if needed
    django.setup()

# ── Constants ────────────────────────────────────────────────────────────────
API_URL = "https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/"

# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_all_jobs(token: str) -> list:
    """Fetch all jobs from the API (handles pagination if 'next' key exists)."""
    headers = {"Authorization": f"Token {token}"}
    all_jobs = []
    url = API_URL

    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        jobs = payload.get("data", [])
        all_jobs.extend(jobs)
        print(f"  → Fetched {len(jobs)} jobs (total: {len(all_jobs)})")
        url = payload.get("next")  # None if API isn't paginated

    return all_jobs


def parse_date(date_str):
    """Parse ISO-8601 datetime string → Python date (UTC date part only)."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).date()
    except Exception:
        return None


def build_api_activity_map(jobs: list) -> dict:
    """
    Flatten all activities across all jobs into:
        { api_activity_id (int) -> date }
    Only include activities that have a valid date.
    """
    activity_map = {}
    for job in jobs:
        for act in job.get("activities", []):
            act_id = act.get("id")
            date = parse_date(act.get("date_time"))
            if act_id and date:
                activity_map[act_id] = date
    return activity_map


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fill missing scheduled_date in JobActivity from API.")
    parser.add_argument("--token", required=True, help="API auth token")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB (default is dry run)")
    args = parser.parse_args()

    bootstrap_django()

    # Import after Django setup
    from tender.models import JobActivity  # ⚠️ adjust app name if needed

    print("\n📡 Fetching jobs from API...")
    jobs = fetch_all_jobs(args.token)
    print(f"✅ Total jobs fetched: {len(jobs)}")

    print("\n🗺️  Building activity ID → date map...")
    api_map = build_api_activity_map(jobs)
    print(f"✅ Total activities with dates in API: {len(api_map)}")

    # Only care about JobActivity rows where scheduled_date IS NULL
    print("\n🔍 Querying JobActivity rows with no scheduled_date...")
    null_jas = JobActivity.objects.filter(scheduled_date__isnull=True)
    print(f"✅ JobActivity rows missing scheduled_date: {null_jas.count()}")

    # Match: api_activity_id on JobActivity must be a string of the int id
    to_update = []
    no_match = []

    for ja in null_jas.select_related("job", "activity"):
        # api_activity_id is stored as a CharField (e.g. "7497")
        try:
            api_id = int(ja.api_activity_id) if ja.api_activity_id else None
        except (ValueError, TypeError):
            api_id = None

        if api_id and api_id in api_map:
            to_update.append((ja, api_map[api_id]))
        else:
            no_match.append(ja)

    # ── Preview ──────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  PREVIEW — {'DRY RUN (pass --apply to write)' if not args.apply else 'WILL WRITE TO DB'}")
    print(f"{'='*65}")
    print(f"\n✅ Will fill scheduled_date for {len(to_update)} JobActivity rows:\n")
    print(f"  {'JA ID':<8} {'API Act ID':<12} {'Job ID':<20} {'Activity':<30} {'Date to Set'}")
    print(f"  {'-'*8} {'-'*12} {'-'*20} {'-'*30} {'-'*12}")

    for ja, date in to_update:
        print(
            f"  {ja.pk:<8} {ja.api_activity_id:<12} {str(ja.job_id):<20} "
            f"{ja.activity.name[:30]:<30} {date}"
        )

    print(f"\n⚠️  {len(no_match)} JobActivity rows have no matching API activity ID (skipped).")
    if no_match:
        print("  Sample skipped (first 10):")
        for ja in no_match[:10]:
            print(f"    JA ID={ja.pk}, api_activity_id='{ja.api_activity_id}'")

    # ── Apply ─────────────────────────────────────────────────────────────────
    if args.apply:
        print(f"\n💾 Writing to DB...")
        updated_count = 0
        for ja, date in to_update:
            ja.scheduled_date = date
            # Use update_fields to skip save() side effects (recalculations etc.)
            JobActivity.objects.filter(pk=ja.pk).update(scheduled_date=date)
            updated_count += 1

        print(f"✅ Done! Updated {updated_count} JobActivity rows.")
    else:
        print(f"\n🟡 Dry run complete. Run with --apply to write to DB.")


if __name__ == "__main__":
    main()