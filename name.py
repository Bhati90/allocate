import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from tender.models import JobActivity

ids = [1201, 1822, 1825, 2002, 2023, 2044, 2049, 2092, 2163]

jas = JobActivity.objects.filter(id__in=ids).values(
    'id',
    'job__job_id',
    'job__farmer__farmer_name',
    'job__farmer__phone_number',
    'activity__name',
    'scheduled_date',
    'allocation_status',
)

print(f"{'ID':<8} {'Job ID':<12} {'Farmer Name':<30} {'Phone':<15} {'Activity':<40} {'Date':<12} {'Status'}")
print("-" * 130)

for ja in jas:
    print(
        f"{ja['id']:<8}",
        f"{ja['job__job_id']:<12}",
        f"{(ja['job__farmer__farmer_name'] or '—'):<30}",
        f"{(ja['job__farmer__phone_number'] or '—'):<15}",
        f"{(ja['activity__name'] or '—'):<40}",
        f"{str(ja['scheduled_date'] or '—'):<12}",
        f"{ja['allocation_status']}",
    )

print(f"\nTotal: {len(jas)} records")