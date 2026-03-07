from collections import defaultdict
from tender.models import JobActivity

qs = JobActivity.objects.select_related(
    "job__farmer",
    "activity",
    "plot"
).filter(
    plot__isnull=False,
    job__farmer__isnull=False
)

groups = defaultdict(lambda: {"ai": [], "moved": []})

for ja in qs.iterator():
    farmer = ja.job.farmer

    key = (
        farmer.farmer_id,
        ja.plot_id,
        ja.activity_id,
    )

    if ja.is_manually_moved or ja.source == "manual":
        groups[key]["moved"].append(ja)

    elif ja.source == "ai" and not ja.is_manually_moved:
        groups[key]["ai"].append(ja)


print("\nGroups with both AI and moved activities:\n")

for (farmer_id, plot_id, activity_id), bucket in groups.items():

    if not bucket["ai"] or not bucket["moved"]:
        continue

    print("-" * 80)
    print(f"Farmer: {farmer_id}, Plot: {plot_id}, Activity: {activity_id}")

    print("AI activities:")
    for a in bucket["ai"]:
        print(
            f"id={a.id}, job={a.job.job_id}, date={a.scheduled_date}, "
            f"area={a.total_area}, source={a.source}, moved={a.is_manually_moved}"
        )

    print("MANUAL/MOVED activities:")
    for m in bucket["moved"]:
        print(
            f"id={m.id}, job={m.job.job_id}, date={m.scheduled_date}, "
            f"area={m.total_area}, source={m.source}, moved={m.is_manually_moved}"
        )