# convert_fixture.py  — place in your project root
import json

with open('jobActvitity23_03.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

fixtures = []
for row in raw:
    pk = row.pop('id', None)
    fixtures.append({
        "model": "tender.jobactivity",
        "pk": pk,
        "fields": row
    })

with open('jobactivity_fixture.json', 'w', encoding='utf-8') as f:
    json.dump(fixtures, f, indent=2, default=str)

print(f"Converted {len(fixtures)} records → jobactivity_fixture.json")
