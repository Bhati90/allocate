# load_allocation.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from django.core.serializers import deserialize
from django.db.models.signals import post_save, pre_save
from tender.models import Allocation

# Disconnect signals
post_save.disconnect(sender=Allocation)
pre_save.disconnect(sender=Allocation)

filepath = r'C:\Users\bhati\New folder (5)\worktender\allocate\allocation.json'

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
        skipped += 1  # JobActivity doesn't exist — skip silently

print(f"Done. Saved: {count}, Skipped (no job activity): {skipped}")