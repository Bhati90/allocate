import requests
from tender.models import Plot

API_URL = "https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/"
TOKEN = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"

# Just fetch once - no pagination
resp = requests.get(
    API_URL,
    headers={"Authorization": f"Token {TOKEN}"},
    timeout=60
)
data = resp.json()
all_jobs = data.get("data", [])
print(f"Total jobs from API: {len(all_jobs)}")

mismatches = []
missing_plots = []
correct = 0
seen = set()

for job in all_jobs:
    job_id = job["id"]
    for act in job.get("activities", []):
        plot_id = str(act.get("plot_id") or "")
        api_plot_area = act.get("plot_area")
        if not plot_id or api_plot_area is None:
            continue
        if plot_id in seen:
            continue
        seen.add(plot_id)

        try:
            db_plot = Plot.objects.get(plot_code=plot_id)
            db_area = float(db_plot.area_acres)
            api_area = float(api_plot_area)
            if abs(db_area - api_area) > 0.01:
                mismatches.append((job_id, plot_id, db_plot.name, db_area, api_area))
            else:
                correct += 1
        except Plot.DoesNotExist:
            missing_plots.append((job_id, plot_id, api_plot_area))

print(f"\nCorrect: {correct}")
print(f"Mismatches: {len(mismatches)}")
print(f"Missing in DB: {len(missing_plots)}")

print("\n--- MISMATCHES ---")
for job_id, plot_id, name, db_a, api_a in mismatches:
    print(f"  Job {job_id} | Plot {plot_id} | name={name} | DB={db_a} | API={api_a} | diff={round(db_a-api_a,2)}")

print("\n--- MISSING IN DB ---")
for job_id, plot_id, api_a in missing_plots:
    print(f"  Job {job_id} | Plot {plot_id} | API area={api_a}")