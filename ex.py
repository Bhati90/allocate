import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')  # adjust if needed
django.setup()

from tender.models import Farmer, Plot, Job, JobActivity, JobBooking
from django.core.serializers.json import DjangoJSONEncoder

data = {
    "farmers": list(Farmer.objects.all().values()),
    "plots": list(Plot.objects.all().values()),
    "jobs": list(Job.objects.all().values()),
    "job_activities": list(JobActivity.objects.all().values()),
    "job_bookings": list(JobBooking.objects.all().values()),
}

with open('export.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)

print("Done! export.json created.")
for key, val in data.items():
    print(f"  {key}: {len(val)} records")