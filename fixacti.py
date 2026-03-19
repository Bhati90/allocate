import os, django, requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from tender.models import JobActivity  # ← change app name if needed

# ── Fetch from API ────────────────────────────────────────────────────────────
API_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'
API_TOKEN = '89b9fd0698faed6c12c1a8e714fca12c86ee2000'  # ← add if auth needed, else remove header

print("Fetching from API...")
res = requests.get(API_URL, headers={'Authorization': f'Token {API_TOKEN}'}, timeout=30)
data = res.json()

visits = data.get('data', [])
print(f"Got {len(visits)} visits from API")

# ── Build lookup: plot_id + activity_name → api_activity_id ──────────────────
# Key: (plot_id_str, activity_name_lower) → api_activity_id
lookup: dict = {}
for visit in visits:
    farmer_id = str(visit.get('farmer_id', ''))
    for act in visit.get('activities', []):
        api_id   = str(act['id'])
        plot_id  = str(act.get('plot_id') or '')
        act_name = (act.get('activity_name') or '').strip().lower()
        key = (plot_id, act_name)
        lookup[key] = api_id

print(f"Built lookup with {len(lookup)} entries")

# ── Find JobActivities missing api_activity_id ────────────────────────────────
missing = JobActivity.objects.filter(
    api_activity_id=''
).select_related('plot', 'activity')

print(f"JobActivities missing api_activity_id: {missing.count()}")

updated  = 0
skipped  = 0
no_match = 0

for ja in missing:
    plot_id  = str(ja.plot.plot_code or ja.plot_id or '') if ja.plot else ''
    act_name = (ja.activity.name or '').strip().lower()
    key = (plot_id, act_name)

    api_id = lookup.get(key)
    if api_id:
        JobActivity.objects.filter(pk=ja.pk).update(api_activity_id=api_id)
        updated += 1
        print(f"  ✓ [{ja.id}] {ja.activity.name} / plot {plot_id} → api_id={api_id}")
    else:
        no_match += 1

print(f"\nDone. Updated: {updated}, No match: {no_match}, Skipped: {skipped}")