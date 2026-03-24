# load_fixtures.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from django.core.serializers import deserialize
from django.db.models.signals import post_save, pre_save
from tender.models import JobActivity

# Disconnect signals
post_save.disconnect(sender=JobActivity)
pre_save.disconnect(sender=JobActivity)

filepath = r'C:\Users\bhati\New folder (5)\worktender\allocate\jobActvitity23_03.json'

with open(filepath, 'r', encoding='utf-8') as f:
    raw = f.read()

clean = raw[raw.index('['):]

count = 0
skipped = 0

for obj in deserialize('json', clean):
    try:
        obj.save()
        count += 1
    except Exception:
        skipped += 1  # Job doesn't exist — skip silently

print(f"Done. Saved: {count}, Skipped (no job): {skipped}")