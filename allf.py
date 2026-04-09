import os
import django
from collections import defaultdict

# 🔹 Setup Django environment (change project name)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")
django.setup()

from tender.models import Job

# ✅ Step 1: Clean farmer list
farmer_names = [
    "Bansidhar Pandurang Pawar",
    "Punam Dinesh Ahire",
    "Vikram Chintaman Kapadnis",
    "Abhijit Jibhau Ahire",
    "Yogeshwar Bajirao Thombare",
    "Chindu Gangadhar Bornare",
    "Ramdas Waman Patil (Rawalgaon)",
    "Ramdas Waman Patil (Nilwandi)",
    "Anil Prakash Kad",
    "Shobha Trambakrao Chavan",
    "Rajendra Varpe",
    "Pravin Arjun Varpe",
    "Sahebrao Hande",
    "Navnath Kumbharkar",
    "Ramnath Pansare",
    "Abhijeet Ahire",
    "Vijay Pundlik Kalamkar",
    "Gorakh Babanrao Pawar",
]

# 🔹 Remove duplicates + strip spaces
farmer_names = list(set(name.strip() for name in farmer_names if name.strip()))

# ✅ Step 2: Build fuzzy query
from django.db.models import Q

query = Q()
for name in farmer_names:
    query |= Q(farmer__farmer_name__icontains=name)

# ✅ Step 3: Fetch jobs
jobs = Job.objects.filter(query).values(
    "job_id",
    "farmer__farmer_name"
)

# ✅ Step 4: Group by farmer
result = defaultdict(list)

for j in jobs:
    result[j["farmer__farmer_name"]].append(j["job_id"])

# ✅ Step 5: Print output
print("\n===== FARMER JOB IDS =====\n")

for farmer, job_ids in result.items():
    print(f"{farmer}")
    for jid in job_ids:
        print(f"   - {jid}")
    print()

print("===== DONE =====")