# import requests
# import os
# import django

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
# django.setup()

# from tender.models import Job

# API_URL     = "https://ops.bharatintelligence.ai/ops/allocation_booked_visits/"
# TOKEN       = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"
# WEBHOOK_URL = "http://localhost:8000/api/booking-webhook/"

# def fetch_all_jobs():
#     res = requests.get(API_URL, headers={"Authorization": f"Token {TOKEN}"}, timeout=30)
#     res.raise_for_status()
#     data = res.json()
#     print(f"Total in API: {data.get('count')}")
#     return data.get('data', [])

# def run():
#     all_jobs = fetch_all_jobs()
#     print(f"Fetched: {len(all_jobs)} jobs")

#     # Filter tender only
#     tender_jobs = [j for j in all_jobs if (j.get('booking') or {}).get('booking_type') == 'tender']
#     print(f"Tender jobs: {len(tender_jobs)}")

#     # Find missing from DB
#     api_ids     = {str(j['id']) for j in tender_jobs}
#     db_ids      = set(Job.objects.filter(job_id__in=api_ids).values_list('job_id', flat=True))
#     missing_ids = api_ids - db_ids
#     print(f"Already in DB: {len(db_ids)} | Missing: {len(missing_ids)}")

#     missing_jobs = [j for j in tender_jobs if str(j['id']) in missing_ids]

#     created = 0
#     failed  = 0
#     for i, job in enumerate(missing_jobs, 1):
#         try:
#             res = requests.post(WEBHOOK_URL, json=job, timeout=30)
#             if res.status_code == 200:
#                 print(f"[{i}/{len(missing_jobs)}] ✅ Created job {job['id']}")
#                 created += 1
#             else:
#                 print(f"[{i}/{len(missing_jobs)}] ❌ Failed job {job['id']} — {res.status_code}: {res.text[:120]}")
#                 failed += 1
#         except Exception as e:
#             print(f"[{i}/{len(missing_jobs)}] ❌ Error job {job['id']} — {e}")
#             failed += 1

#     print(f"\nDone. ✅ Created: {created} | ❌ Failed: {failed}")


# run()


import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from tender.models import Job
from tender.webhook import booking_webhook,sync_webhook
from unittest.mock import MagicMock


API_URL     = "https://ops.bharatintelligence.ai/ops/allocation_booked_visits/"
TOKEN       = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"

def fetch_all_jobs():
    res = requests.get(API_URL, headers={"Authorization": f"Token {TOKEN}"}, timeout=30)
    res.raise_for_status()
    data = res.json()
    return data.get('data', [])

def run():
    all_jobs = fetch_all_jobs()
    tender_jobs = [j for j in all_jobs if (j.get('booking') or {}).get('booking_type') == 'tender']
    
    api_ids     = {str(j['id']) for j in tender_jobs}
    db_ids      = set(Job.objects.filter(job_id__in=api_ids).values_list('job_id', flat=True))
    missing_ids = api_ids - db_ids
    print(f"Tender: {len(tender_jobs)} | In DB: {len(db_ids)} | Missing: {len(missing_ids)}")

    missing_jobs = [j for j in tender_jobs if str(j['id']) in missing_ids]

    created = 0
    failed  = 0
    for i, job in enumerate(missing_jobs, 1):
        try:
            # Call function directly — no HTTP, no CSRF
            mock_request = MagicMock()
            mock_request.data = job
            response = sync_webhook(mock_request)

            import json
            body = json.loads(response.content)
            if response.status_code == 200:
                print(f"[{i}/{len(missing_jobs)}] ✅ Created job {job['id']} — {body.get('activities_processed')} activities")
                created += 1
            else:
                print(f"[{i}/{len(missing_jobs)}] ❌ Failed job {job['id']} — {body}")
                failed += 1
        except Exception as e:
            print(f"[{i}/{len(missing_jobs)}] ❌ Error job {job['id']} — {e}")
            failed += 1

    print(f"\nDone. ✅ Created: {created} | ❌ Failed: {failed}")

run()