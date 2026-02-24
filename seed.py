"""
Seed script — fills every model with realistic test data.

Covers ALL scenarios:
  1. Normal allocation (not reported yet)
  2. Day-end reported, farmer pending verification
  3. Farmer agreed, carry-forward created (less done)
  4. Farmer agreed, extra done (future allocation reduced)
  5. Farmer disputed
  6. Carry-forward allocation itself
  7. Settlement calculated, paid
  8. Settlement with misc cost deduction
  9. General holiday leave
  10. Mukkadam leave

Run:
    python manage.py shell < seed_data.py
OR
    python manage.py runscript seed_data   (if django-extensions installed)
"""

import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')  # ← change to your settings module
django.setup()

from decimal import Decimal
from datetime import date, timedelta, datetime
from django.utils import timezone
from django.db import transaction

from tender.models import (
    ActivityCatalog,
    Cluster,
    Farmer,
    Plot,
    ClusterActivityRate,
    MukkadamActivityRate,
    Mukkadam,
    ClusterMukkadamAssignment,
    MukkadamWeeklyPayment,
    MukkadamAvailability,
    Job,
    JobActivity,
    JobBooking,
    FarmerPayment,
    Allocation,
    Leave,
)

# Try importing settlement models — they may or may not exist yet
try:
    from tender.models import (
        MukkadamJobSettlement,
        MukkadamMiscCost,
        MukkadamPayment,
    )
    HAS_SETTLEMENT = True
except ImportError:
    HAS_SETTLEMENT = False
    print("⚠️  Settlement models not found — skipping settlement seed")

TODAY       = date.today()
YESTERDAY   = TODAY - timedelta(days=1)
TWO_DAYS_AGO = TODAY - timedelta(days=2)
TOMORROW    = TODAY + timedelta(days=1)
DAY_AFTER   = TODAY + timedelta(days=2)

print("🌱 Starting seed...")

with transaction.atomic():

    # ──────────────────────────────────────────────────────────────────────────
    # 1. ACTIVITY CATALOG
    # ──────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────
    # 1. ACTIVITY CATALOG
    # ──────────────────────────────────────────────────────────────────────────
    # Changed 'activity_name' to 'name' to match your model schema
    pruning, _    = ActivityCatalog.objects.get_or_create(
        name="Pruning",
        defaults={"activity_type": "field", "is_strict": True}
    )
    desuckering, _ = ActivityCatalog.objects.get_or_create(
        name="Desuckering",
        defaults={"activity_type": "field", "is_strict": False}
    )
    tying, _       = ActivityCatalog.objects.get_or_create(
        name="Tying",
        defaults={"activity_type": "field", "is_strict": False}
    )
    print("✅ ActivityCatalog")
    print("✅ ActivityCatalog")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. CLUSTER
    # ──────────────────────────────────────────────────────────────────────────
    cluster, _ = Cluster.objects.get_or_create(
        name="Nashik Alpha Cluster",
        defaults={
            "districts": ["Nashik"],
            "talukas": ["Niphad"],
            "villages": ["Pimpalgaon", "Lasalgaon"],
            "district_codes": ["NAS"],
            "taluka_codes": ["NIP"],
            "village_codes": ["PIMP", "LAS"],
        }
    )
    print("✅ Cluster")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. CLUSTER ACTIVITY RATES (farmer-facing rates)
    # ──────────────────────────────────────────────────────────────────────────
    ClusterActivityRate.objects.get_or_create(
        cluster=cluster, activity=pruning,
        defaults={"rate_per_acre": Decimal("4500")}
    )
    ClusterActivityRate.objects.get_or_create(
        cluster=cluster, activity=desuckering,
        defaults={"rate_per_acre": Decimal("2800")}
    )
    ClusterActivityRate.objects.get_or_create(
        cluster=cluster, activity=tying,
        defaults={"rate_per_acre": Decimal("2200")}
    )
    print("✅ ClusterActivityRate")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. FARMERS
    # ──────────────────────────────────────────────────────────────────────────
    farmer1, _ = Farmer.objects.get_or_create(
        farmer_id="F-001",
        defaults={
            "farmer_name": "Ramesh Patil",
            "phone_number": "9876543210",
            "location": "Pimpalgaon, Niphad, Nashik",
            "latitude": Decimal("20.0760"),
            "longitude": Decimal("74.1120"),
        }
    )
    farmer2, _ = Farmer.objects.get_or_create(
        farmer_id="F-002",
        defaults={
            "farmer_name": "Suresh Jadhav",
            "phone_number": "9876500002",
            "location": "Lasalgaon, Niphad, Nashik",
            "latitude": Decimal("20.1200"),
            "longitude": Decimal("74.0900"),
        }
    )
    print("✅ Farmers")

    # ──────────────────────────────────────────────────────────────────────────
    # 5. PLOTS
    # ──────────────────────────────────────────────────────────────────────────
    plot1, _ = Plot.objects.get_or_create(
        farmer=farmer1,
        name="Plot A",
        defaults={
            "area_acres": Decimal("5.0"),
            "crop_name": "Grapes",
            "variety": "Thompson Seedless",
            "pruning_date": TODAY - timedelta(days=30),
            "plot_code": "F001-PA",
            "latitude": Decimal("20.0765"),
            "longitude": Decimal("74.1125"),
        }
    )
    plot2, _ = Plot.objects.get_or_create(
        farmer=farmer2,
        name="Plot B",
        defaults={
            "area_acres": Decimal("3.5"),
            "crop_name": "Grapes",
            "variety": "Sharad Seedless",
            "pruning_date": TODAY - timedelta(days=25),
            "plot_code": "F002-PB",
        }
    )
    print("✅ Plots")

    # ──────────────────────────────────────────────────────────────────────────
    # 6. MUKKADAMS
    # ──────────────────────────────────────────────────────────────────────────
    m1, _ = Mukkadam.objects.get_or_create(
        mukkadam_id=101,
        defaults={
            "mukkadam_name": "Vijay Shinde",
            "mobile_numbers": "9900001111",
            "crew_size": 20,
            "max_crew_capacity": 25,
            "efficiency": Decimal("0.90"),
            "is_permanent": True,
            "work_mode": "field",
            "district": "Nashik",
            "taluka": "Niphad",
            "village": "Pimpalgaon",
            "start_date": TODAY - timedelta(days=60),
            "end_date": TODAY + timedelta(days=90),
        }
    )
    m2, _ = Mukkadam.objects.get_or_create(
        mukkadam_id=102,
        defaults={
            "mukkadam_name": "Santosh More",
            "mobile_numbers": "9900002222",
            "crew_size": 15,
            "max_crew_capacity": 18,
            "efficiency": Decimal("0.85"),
            "is_permanent": True,
            "work_mode": "field",
            "district": "Nashik",
            "taluka": "Niphad",
            "village": "Lasalgaon",
            "start_date": TODAY - timedelta(days=45),
            "end_date": TODAY + timedelta(days=90),
        }
    )
    print("✅ Mukkadams")

    # ──────────────────────────────────────────────────────────────────────────
    # 7. MUKKADAM ACTIVITY RATES
    # ──────────────────────────────────────────────────────────────────────────
    MukkadamActivityRate.objects.get_or_create(
        mukkadam=m1, activity=pruning,
        defaults={"rate_per_acre": Decimal("3800"), "productivity_per_worker": Decimal("0.20")}
    )
    MukkadamActivityRate.objects.get_or_create(
        mukkadam=m1, activity=desuckering,
        defaults={"rate_per_acre": Decimal("2200"), "productivity_per_worker": Decimal("0.25")}
    )
    MukkadamActivityRate.objects.get_or_create(
        mukkadam=m1, activity=tying,
        defaults={"rate_per_acre": Decimal("1700"), "productivity_per_worker": Decimal("0.30")}
    )
    MukkadamActivityRate.objects.get_or_create(
        mukkadam=m2, activity=pruning,
        defaults={"rate_per_acre": Decimal("3600"), "productivity_per_worker": Decimal("0.18")}
    )
    MukkadamActivityRate.objects.get_or_create(
        mukkadam=m2, activity=desuckering,
        defaults={"rate_per_acre": Decimal("2000"), "productivity_per_worker": Decimal("0.22")}
    )
    print("✅ MukkadamActivityRates")

    # ──────────────────────────────────────────────────────────────────────────
    # 8. CLUSTER-MUKKADAM ASSIGNMENTS
    # ──────────────────────────────────────────────────────────────────────────
    assign1, _ = ClusterMukkadamAssignment.objects.get_or_create(
        mukkadam=m1, cluster=cluster,
        defaults={
            "transport_price": Decimal("3000"),
            "advance_amount": Decimal("20000"),
            "weekly_payment_day": 0,  # Monday
            "total_weekly_payments": Decimal("30000"),
            "is_active": True,
        }
    )
    assign2, _ = ClusterMukkadamAssignment.objects.get_or_create(
        mukkadam=m2, cluster=cluster,
        defaults={
            "transport_price": Decimal("2500"),
            "advance_amount": Decimal("20000"),
            "weekly_payment_day": 1,  # Tuesday
            "total_weekly_payments": Decimal("20000"),
            "is_active": True,
        }
    )
    print("✅ ClusterMukkadamAssignments")

    # ──────────────────────────────────────────────────────────────────────────
    # 9. WEEKLY PAYMENTS
    # ──────────────────────────────────────────────────────────────────────────
    for i in range(3):
        pdate = TODAY - timedelta(weeks=3 - i)
        MukkadamWeeklyPayment.objects.get_or_create(
            assignment=assign1,
            payment_date=pdate,
            defaults={
                "amount": Decimal("10000"),
                "crew_size_on_date": 20,
                "is_auto_generated": True,
                "notes": f"Auto weekly payment week {i+1}",
            }
        )
    for i in range(2):
        pdate = TODAY - timedelta(weeks=2 - i)
        MukkadamWeeklyPayment.objects.get_or_create(
            assignment=assign2,
            payment_date=pdate,
            defaults={
                "amount": Decimal("10000"),
                "crew_size_on_date": 15,
                "is_auto_generated": True,
            }
        )
    print("✅ MukkadamWeeklyPayments")

    # ──────────────────────────────────────────────────────────────────────────
    # 10. MUKKADAM AVAILABILITY
    # ──────────────────────────────────────────────────────────────────────────
    MukkadamAvailability.objects.get_or_create(
        mukkadam=m1,
        date=TODAY,
        defaults={"available_crew_size": 20, "notes": "Full crew available"}
    )
    MukkadamAvailability.objects.get_or_create(
        mukkadam=m1,
        date=TOMORROW,
        defaults={"available_crew_size": 18, "notes": "2 on leave tomorrow"}
    )
    MukkadamAvailability.objects.get_or_create(
        mukkadam=m2,
        date=TODAY,
        defaults={"available_crew_size": 12, "notes": "3 on leave today"}
    )
    print("✅ MukkadamAvailability")

    # ──────────────────────────────────────────────────────────────────────────
    # 11. LEAVES
    # ──────────────────────────────────────────────────────────────────────────
    # General holiday tomorrow
    Leave.objects.get_or_create(
        date=DAY_AFTER,
        leave_type='general',
        mukkadam=None,
        defaults={
            "cluster": cluster,
            "reason": "Local festival — Shimga",
            "is_active": True,
        }
    )
    # Mukkadam 2 leave today
    Leave.objects.get_or_create(
        date=TODAY,
        leave_type='mukkadam',
        mukkadam=m2,
        defaults={
            "cluster": cluster,
            "crew_on_leave": 3,
            "reason": "3 workers travelling",
            "is_active": True,
        }
    )
    print("✅ Leaves")

    # ──────────────────────────────────────────────────────────────────────────
    # 12. JOBS
    # ──────────────────────────────────────────────────────────────────────────
    # Fix 1: Changed 'job_status' to 'status'
    # Fix 2: Removed 'clusters' from defaults because it's a ManyToManyField
    job1, _ = Job.objects.get_or_create(
        job_id="JOB-001",
        defaults={
            "farmer": farmer1,
            "plot": plot1,
            "crop_name": "Grapes",
            "variety": "Thompson Seedless",
            "status": "active",  # Changed from job_status
            "latitude": Decimal("20.0765"),
            "longitude": Decimal("74.1125"),
        }
    )
    job1.clusters.add(cluster) # Correct way to add ManyToMany relationship

    job2, _ = Job.objects.get_or_create(
        job_id="JOB-002",
        defaults={
            "farmer": farmer2,
            "plot": plot2,
            "crop_name": "Grapes",
            "variety": "Sharad Seedless",
            "status": "active", # Changed from job_status
        }
    )
    job2.clusters.add(cluster)

    job3, _ = Job.objects.get_or_create(
        job_id="JOB-003",
        defaults={
            "farmer": farmer1,
            "plot": plot1,
            "crop_name": "Grapes",
            "variety": "Thompson Seedless",
            "status": "completed", # Changed from job_status
        }
    )
    job3.clusters.add(cluster)
    print("✅ Jobs")
# ──────────────────────────────────────────────────────────────────────────
    # 13. JOB BOOKINGS
    # ──────────────────────────────────────────────────────────────────────────
    # Fix 1: Added mandatory 'booking_id'
    # Fix 2: Removed 'shoot_selection_date' (not in models.py)
    JobBooking.objects.get_or_create(
        job=job1,
        defaults={
            "booking_id": 1000001,  # Added mandatory field
            "total_amount": Decimal("22500"),
            "advance_paid": Decimal("5000"),
            "balance": Decimal("17500"), # Recommended to match model
        }
    )
    JobBooking.objects.get_or_create(
        job=job2,
        defaults={
            "booking_id": 1000002,  # Added mandatory field
            "total_amount": Decimal("15750"),
            "advance_paid": Decimal("3000"),
            "balance": Decimal("12750"),
        }
    )
    JobBooking.objects.get_or_create(
        job=job3,
        defaults={
            "booking_id": 1000003,  # Added mandatory field
            "total_amount": Decimal("9800"),
            "advance_paid": Decimal("2000"),
            "balance": Decimal("7800"),
        }
    )
    print("✅ JobBookings")
    # ──────────────────────────────────────────────────────────────────────────
    # 14. JOB ACTIVITIES
    # ──────────────────────────────────────────────────────────────────────────

    # JOB1 — Pruning: 5 ac total, 2 days (3 ac today, 2 ac tomorrow)
    ja1_pruning, _ = JobActivity.objects.get_or_create(
        job=job1,
        activity=pruning,
        scheduled_date=YESTERDAY,
        defaults={
            "total_area": Decimal("5.0"),
            "allocated_area": Decimal("5.0"),
            "remaining_area": Decimal("0.0"),
            "rate_per_acre": Decimal("4500"),
            "is_strict": True,
            "is_manually_moved": False,
        }
    )

    # JOB1 — Desuckering: 5 ac, scheduled today
    ja1_desuckering, _ = JobActivity.objects.get_or_create(
        job=job1,
        activity=desuckering,
        scheduled_date=TODAY,
        defaults={
            "total_area": Decimal("5.0"),
            "allocated_area": Decimal("3.5"),
            "remaining_area": Decimal("1.5"),
            "rate_per_acre": Decimal("2800"),
            "is_strict": False,
            "is_manually_moved": False,
        }
    )

    # JOB1 — Tying: future (unallocated)
    ja1_tying, _ = JobActivity.objects.get_or_create(
        job=job1,
        activity=tying,
        scheduled_date=TODAY + timedelta(days=5),
        defaults={
            "total_area": Decimal("5.0"),
            "allocated_area": Decimal("0.0"),
            "remaining_area": Decimal("5.0"),
            "rate_per_acre": Decimal("2200"),
            "is_strict": False,
            "is_manually_moved": False,
        }
    )

    # JOB2 — Pruning: 3.5 ac, partially done
    ja2_pruning, _ = JobActivity.objects.get_or_create(
        job=job2,
        activity=pruning,
        scheduled_date=YESTERDAY,
        defaults={
            "total_area": Decimal("3.5"),
            "allocated_area": Decimal("3.5"),
            "remaining_area": Decimal("0.0"),
            "rate_per_acre": Decimal("4500"),
            "is_strict": True,
            "is_manually_moved": False,
        }
    )

    # JOB2 — Desuckering: future, manually moved
    ja2_desuckering, _ = JobActivity.objects.get_or_create(
        job=job2,
        activity=desuckering,
        scheduled_date=TODAY + timedelta(days=3),
        defaults={
            "total_area": Decimal("3.5"),
            "allocated_area": Decimal("0.0"),
            "remaining_area": Decimal("3.5"),
            "rate_per_acre": Decimal("2800"),
            "is_strict": False,
            "is_manually_moved": True,
            "lost_reason": "Farmer requested delay — irrigation pending",
        }
    )

    # JOB3 — Pruning: completed job (for settlement)
    ja3_pruning, _ = JobActivity.objects.get_or_create(
        job=job3,
        activity=pruning,
        scheduled_date=TODAY - timedelta(days=15),
        defaults={
            "total_area": Decimal("2.0"),
            "allocated_area": Decimal("2.0"),
            "remaining_area": Decimal("0.0"),
            "rate_per_acre": Decimal("4500"),
            "is_strict": True,
            "is_manually_moved": False,
        }
    )
    print("✅ JobActivities")
# ──────────────────────────────────────────────────────────────────────────
    # 15. ALLOCATIONS — all 6 scenarios
    # ──────────────────────────────────────────────────────────────────────────

    # SCENARIO 1: Normal allocation — report not submitted yet (today's desuckering)
    alloc_normal, _ = Allocation.objects.get_or_create(
        job_activity=ja1_desuckering,
        mukkadam=m1,
        allocated_date=TODAY,
        defaults={
            "allocated_area": Decimal("3.5"),
            "allocated_workers": 14,
            "farmer_rate": Decimal("2800"),
            "mukkadam_rate": Decimal("2200"),
            "status": "scheduled",
            "cluster": cluster,
            "report_submitted": False,
            "farmer_agreed": None,
            "is_carry_forward": False,
        }
    )

    # SCENARIO 2: Reported, farmer PENDING verification (yesterday's pruning)
    alloc_pending, _ = Allocation.objects.get_or_create(
        job_activity=ja1_pruning,
        mukkadam=m1,
        allocated_date=YESTERDAY,
        defaults={
            "allocated_area": Decimal("3.0"),
            "allocated_workers": 15,
            "farmer_rate": Decimal("4500"),
            "mukkadam_rate": Decimal("3800"),
            "status": "completed",
            "cluster": cluster,
            "report_submitted": True,
            "actual_area_done": Decimal("2.5"),
            "actual_crew_size": 15,
            "actual_start_time": timezone.make_aware(
                datetime.combine(YESTERDAY, datetime.min.time().replace(hour=7, minute=30))
            ),
            "actual_end_time": timezone.make_aware(
                datetime.combine(YESTERDAY, datetime.min.time().replace(hour=13, minute=0))
            ),
            "report_submitted_at": timezone.now() - timedelta(hours=10),
            "farmer_agreed": None,
            "use_actual_for_settlement": False,
            "is_carry_forward": False,
        }
    )

    # SCENARIO 3: Farmer AGREED — less done, carry-forward created
    alloc_agreed_less, _ = Allocation.objects.get_or_create(
        job_activity=ja2_pruning,
        mukkadam=m2,
        allocated_date=YESTERDAY,
        defaults={
            "allocated_area": Decimal("2.0"),
            "allocated_workers": 11,
            "farmer_rate": Decimal("4500"),
            "mukkadam_rate": Decimal("3600"),
            "status": "completed",
            "cluster": cluster,
            "report_submitted": True,
            "actual_area_done": Decimal("1.6"),
            "actual_crew_size": 10,
            "actual_start_time": timezone.make_aware(
                datetime.combine(YESTERDAY, datetime.min.time().replace(hour=8, minute=0))
            ),
            "actual_end_time": timezone.make_aware(
                datetime.combine(YESTERDAY, datetime.min.time().replace(hour=12, minute=30))
            ),
            "report_submitted_at": timezone.now() - timedelta(hours=18),
            "farmer_agreed": True,
            "use_actual_for_settlement": True,
            "is_carry_forward": False,
        }
    )

    # SCENARIO 4: Carry-forward allocation (created by service after scenario 3)
    alloc_carry, _ = Allocation.objects.get_or_create(
        job_activity=ja2_pruning,
        mukkadam=m2,
        allocated_date=TODAY,
        defaults={
            "allocated_area": Decimal("0.4"),
            "allocated_workers": 11,
            "farmer_rate": Decimal("4500"),
            "mukkadam_rate": Decimal("3600"),
            "status": "scheduled",
            "cluster": cluster,
            "report_submitted": False,
            "farmer_agreed": None,
            "use_actual_for_settlement": False,
            "is_carry_forward": True,
            "notes": "Auto carry-forward of 0.4 ac from yesterday",
        }
    )

    # SCENARIO 5: Farmer DISPUTED
    alloc_disputed, _ = Allocation.objects.get_or_create(
        job_activity=ja3_pruning,
        mukkadam=m1,
        allocated_date=TODAY - timedelta(days=15),
        defaults={
            "allocated_area": Decimal("2.0"),
            "allocated_workers": 10,
            "farmer_rate": Decimal("4500"),
            "mukkadam_rate": Decimal("3800"),
            "status": "completed",
            "cluster": cluster,
            "report_submitted": True,
            "actual_area_done": Decimal("2.3"),
            "actual_crew_size": 10,
            "report_submitted_at": timezone.now() - timedelta(days=14),
            "farmer_agreed": False,
            "farmer_response_at": timezone.now() - timedelta(days=13),
            "farmer_dispute_reason": "Area done is less than reported — only 1.8 ac done",
            "use_actual_for_settlement": False,
            "is_carry_forward": False,
        }
    )

    # SCENARIO 6: Farmer AGREED — more done (over-delivery)
    alloc_more_done, _ = Allocation.objects.get_or_create(
        job_activity=ja1_pruning,
        mukkadam=m1,
        allocated_date=TWO_DAYS_AGO,
        defaults={
            "allocated_area": Decimal("2.0"),
            "allocated_workers": 10,
            "farmer_rate": Decimal("4500"),
            "mukkadam_rate": Decimal("3800"),
            "status": "completed",
            "cluster": cluster,
            "report_submitted": True,
            "actual_area_done": Decimal("2.5"),
            "actual_crew_size": 11,
            "report_submitted_at": timezone.now() - timedelta(days=2, hours=8),
            "farmer_agreed": True,
            "farmer_response_at": timezone.now() - timedelta(days=2, hours=6),
            "use_actual_for_settlement": True,
            "is_carry_forward": False,
        }
    )

    print("✅ Allocations (all 6 scenarios)")
# ──────────────────────────────────────────────────────────────────────────
    # 16. FARMER PAYMENTS
    # ──────────────────────────────────────────────────────────────────────────
    # Note: FarmerPayment links to JobBooking, not Job.
    # We fetch the booking created in Section 13.
    booking1 = JobBooking.objects.get(job=job1)
    booking3 = JobBooking.objects.get(job=job3)

    FarmerPayment.objects.get_or_create(
        payment_id=9001,  # Added mandatory unique ID
        booking=booking1, # Changed from job to booking
        defaults={
            "amount": Decimal("5000"),
            "mode": "CASH",   # Changed from payment_mode and case-sensitive
            "notes": "Advance payment",
            "paid_at": timezone.now() - timedelta(days=10),
        }
    )
    FarmerPayment.objects.get_or_create(
        payment_id=9002,
        booking=booking3,
        defaults={
            "amount": Decimal("7500"),
            "mode": "UPI",    # Changed from payment_mode
            "notes": "Partial payment after pruning",
            "paid_at": timezone.now() - timedelta(days=12),
        }
    )
    print("✅ FarmerPayments")

    # ──────────────────────────────────────────────────────────────────────────
    # 17. SETTLEMENT MODELS
    # ──────────────────────────────────────────────────────────────────────────
    if HAS_SETTLEMENT:
        # Misc cost for mukkadam 1 on job3
        mc, _ = MukkadamMiscCost.objects.get_or_create(
            mukkadam=m1,
            job=job3,
            defaults={
                "amount": Decimal("500"),
                "reason": "Tool repair charges",
            }
        )

        gross = Decimal("7600.00")
        payable = gross * Decimal("0.90")
        advance = Decimal("20000")
        weekly_total = Decimal("30000")
        misc_total = Decimal("500")
        net = payable - advance - weekly_total - misc_total

        settlement, _ = MukkadamJobSettlement.objects.get_or_create(
            mukkadam=m1,
            job=job3,
            defaults={
                "cluster": cluster,
                "gross_amount": gross,
                "payable_amount": payable,
                "advance_deducted": advance,
                "weekly_payments_deducted": weekly_total,
                "net_payable": max(net, Decimal("0")),
                "status": "calculated",
                "calculated_at": timezone.now() - timedelta(days=5),
            }
        )

        if net > 0:
            MukkadamPayment.objects.get_or_create(
                mukkadam=m1,
                payment_id="PAY-101-JOB3", # Added mandatory unique ID
                defaults={
                    "amount": net,
                    "mode": "BANK_TRANSFER", # Matches choices in models.py
                    "notes": "Settlement for JOB-003",
                    "paid_at": timezone.now() - timedelta(days=3),
                }
            )
        print("✅ Settlement models (MukkadamJobSettlement, MukkadamMiscCost)")

    # ──────────────────────────────────────────────────────────────────────────
    # 17. SETTLEMENT MODELS (if available)
    # ──────────────────────────────────────────────────────────────────────────
    if HAS_SETTLEMENT:
        # Misc cost for mukkadam 1 on job3
        mc, _ = MukkadamMiscCost.objects.get_or_create(
            mukkadam=m1,
            job=job3,
            defaults={
                "amount": Decimal("500"),
                "reason": "Tool repair charges",
                "created_at": timezone.now() - timedelta(days=10),
            }
        )

        # Settlement for JOB3 (completed)
        # Gross: 2.0 ac × ₹3800 = 7600 (but farmer disputed, so use original area)
        gross = Decimal("7600.00")
        deposit_pct = Decimal("10")
        payable = gross * Decimal("0.90")
        misc_total = Decimal("500")
        advance = Decimal("20000")
        weekly_total = Decimal("30000")
        net = payable - advance - weekly_total - misc_total
        # net will be negative here (advance+weekly exceed payable) — shows in dashboard as settled

        settlement, _ = MukkadamJobSettlement.objects.get_or_create(
            mukkadam=m1,
            job=job3,
            defaults={
                "cluster": cluster,
                "gross_amount": gross,
                "deposit_percent": deposit_pct,
                "payable_amount": payable,
                "deposit_carried_forward": gross - payable,
                "advance_deducted": advance,
                "weekly_payments_deducted": weekly_total,
                "misc_deductions": misc_total,
                "net_payable": max(net, Decimal("0")),
                "status": "calculated",
                "calculated_at": timezone.now() - timedelta(days=5),
            }
        )

        # Mukkadam payment record
        if HAS_SETTLEMENT and net > 0:
            MukkadamPayment.objects.get_or_create(
                mukkadam=m1,
                defaults={
                    "amount": net,
                    "payment_mode": "bank_transfer",
                    "notes": "Settlement for JOB-003",
                    "paid_at": timezone.now() - timedelta(days=3),
                }
            )
        print("✅ Settlement models (MukkadamJobSettlement, MukkadamMiscCost)")
    else:
        print("⏭️  Skipped settlement models")

print()
print("=" * 60)
print("🎉 SEED COMPLETE — Summary of what you can now see:")
print("=" * 60)
print()
print("📋 ALLOCATIONS TAB:")
print("  • Normal (no report yet)           → Desuckering, JOB-001, today")
print("  • ⏳ Pending farmer verification   → Pruning, JOB-001, yesterday (2.5ac done, 3.0 planned)")
print("  • ✅ Agreed, less done + CF badge  → Pruning, JOB-002, yesterday (1.6ac done, 2.0 planned)")
print("  • 🔄 Carry-forward allocation      → Pruning, JOB-002, today (0.4ac)")
print("  • ❌ Disputed                      → Pruning, JOB-003, 15 days ago")
print("  • ✅ Agreed, more done             → Pruning, JOB-001, 2 days ago (2.5ac done, 2.0 planned)")
print()
print("📋 JOBS TAB:")
print("  • Pruning JOB-001 → status mix (agreed + more done)")
print("  • Desuckering JOB-001 today → pending verify badge")
print("  • Tying JOB-001 future → unallocated, team suggestion shows")
print("  • Desuckering JOB-002 → manually moved (H badge)")
print()
print("📋 LEAVES TAB:")
print(f"  • General holiday on {DAY_AFTER} — Shimga")
print(f"  • Mukkadam Santosh More — 3 workers absent today")
print()
print("📋 MAX WORK TAB:")
print("  • Both mukkadams with productivity × available workers")
print()
if HAS_SETTLEMENT:
    print("📋 PAYMENT DASHBOARD:")
    print("  • JOB-003 settlement calculated for Vijay Shinde")
    print("  • Misc cost ₹500 deducted")
    print("  • Farmer payments visible for JOB-001 and JOB-003")
print()
print("🔍 Open the calendar on dates:")
print(f"  • {TWO_DAYS_AGO}  — over-delivery allocation")
print(f"  • {YESTERDAY}     — pending verify + agreed allocations")
print(f"  • {TODAY}         — carry-forward + normal + leave alert")
print(f"  • {DAY_AFTER}     — general holiday")