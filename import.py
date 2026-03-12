import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from django.utils.dateparse import parse_datetime, parse_date
from tender.models import (
    ActivityCatalog,
    Cluster,
    Farmer,
    Plot,
    ClusterActivityRate,
    FarmerCall,
    MukkadamOTPRequest,
    Job,
    JobActivity,
    JobNote,
    JobBooking,
    FarmerPayment,
    FarmerPaymentWebhookLog,
    ActivityScheduleRule,
    ClusterActivityScheduleRule,
    MukkadamLedgerEntry,
    Mukkadam,
    ClusterMukkadamActivityRate,
    FarmerBillWebhookLog,
    MukkadamActivityRate,
    MukkadamAvailability,
    Allocation,
    PaymentProof,
    MukkadamPayment,
    ActivityLogTender,
    ExtraWorker,
    Leave,
    AllocationChangeLogTender,
    PaymentChangeLog,
    ClusterMukkadamAssignment,
    MukkadamWeeklyPayment,
    MukkadamMiscCost,
    MukkadamJobSettlement,
    FarmerClusterMukkadamAssignment,
)

print("📂 Loading export.json...")
with open('export.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"✅ Loaded. Keys: {len(data)}\n")


def upsert(model, rows, pk_field, skip_fields=None):
    """
    For each row: update if exists (by pk_field), else create.
    skip_fields: fields to skip on update (e.g. auto_now_add fields).
    """
    skip_fields = set(skip_fields or [])
    created = updated = skipped = 0

    for row in rows:
        pk_val = row.get(pk_field)
        if pk_val is None:
            skipped += 1
            continue

        # Remove fields that can't be set directly
        row_clean = {k: v for k, v in row.items() if k not in skip_fields}

        try:
            obj = model.objects.get(**{pk_field: pk_val})
            # Update all fields
            for k, v in row_clean.items():
                if k != pk_field:
                    setattr(obj, k, v)
            obj.save()
            updated += 1
        except model.DoesNotExist:
            try:
                model.objects.create(**row_clean)
                created += 1
            except Exception as e:
                print(f"  ⚠️  CREATE failed [{model.__name__}] pk={pk_val}: {e}")
                skipped += 1
        except Exception as e:
            print(f"  ⚠️  UPDATE failed [{model.__name__}] pk={pk_val}: {e}")
            skipped += 1

    return created, updated, skipped


def report(name, created, updated, skipped):
    print(f"  {name:<45} created={created:>5}  updated={updated:>5}  skipped={skipped:>5}")


# ══════════════════════════════════════════════════════════════════════════
# Import order matters — respect FK dependencies
# ══════════════════════════════════════════════════════════════════════════

print("🚀 Starting import...\n")
print(f"  {'Model':<45} {'created':>10}  {'updated':>10}  {'skipped':>10}")
print("  " + "-" * 70)

with transaction.atomic():

    # ── No FK dependencies ────────────────────────────────────────────
    r = upsert(ActivityCatalog, data.get('activity_catalog', []), 'id')
    report('activity_catalog', *r)

    r = upsert(Cluster, data.get('clusters', []), 'id')
    report('clusters', *r)

    r = upsert(Farmer, data.get('farmers', []), 'farmer_id')
    report('farmers', *r)

    r = upsert(Mukkadam, data.get('mukkadams', []), 'mukkadam_id')
    report('mukkadams', *r)

    # ── Depends on Farmer, Cluster ────────────────────────────────────
    r = upsert(Plot, data.get('plots', []), 'id')
    report('plots', *r)

    r = upsert(ClusterActivityRate, data.get('cluster_activity_rates', []), 'id')
    report('cluster_activity_rates', *r)

    r = upsert(FarmerCall, data.get('farmer_calls', []), 'id')
    report('farmer_calls', *r)

    r = upsert(MukkadamOTPRequest, data.get('mukkadam_otp_requests', []), 'id')
    report('mukkadam_otp_requests', *r)

    r = upsert(ActivityScheduleRule, data.get('activity_schedule_rules', []), 'id')
    report('activity_schedule_rules', *r)

    r = upsert(ClusterActivityScheduleRule, data.get('cluster_activity_schedule_rules', []), 'id')
    report('cluster_activity_schedule_rules', *r)

    r = upsert(MukkadamActivityRate, data.get('mukkadam_activity_rates', []), 'id')
    report('mukkadam_activity_rates', *r)

    r = upsert(MukkadamAvailability, data.get('mukkadam_availability', []), 'id')
    report('mukkadam_availability', *r)

    r = upsert(ClusterMukkadamAssignment, data.get('cluster_mukkadam_assignments', []), 'id')
    report('cluster_mukkadam_assignments', *r)

    r = upsert(ClusterMukkadamActivityRate, data.get('cluster_mukkadam_activity_rates', []), 'id')
    report('cluster_mukkadam_activity_rates', *r)

    r = upsert(FarmerClusterMukkadamAssignment, data.get('farmer_cluster_mukkadam_assignments', []), 'id')
    report('farmer_cluster_mukkadam_assignments', *r)

    # ── Depends on Job (needs Job first) ──────────────────────────────
    r = upsert(Job, data.get('jobs', []), 'job_id')
    report('jobs', *r)

    r = upsert(JobActivity, data.get('job_activities', []), 'id')
    report('job_activities', *r)

    r = upsert(JobNote, data.get('job_notes', []), 'id')
    report('job_notes', *r)

    r = upsert(JobBooking, data.get('job_bookings', []), 'id')
    report('job_bookings', *r)

    r = upsert(FarmerPayment, data.get('farmer_payments', []), 'id')
    report('farmer_payments', *r)

    r = upsert(FarmerPaymentWebhookLog, data.get('farmer_payment_webhook_logs', []), 'id')
    report('farmer_payment_webhook_logs', *r)

    r = upsert(FarmerBillWebhookLog, data.get('farmer_bill_webhook_logs', []), 'id')
    report('farmer_bill_webhook_logs', *r)

    r = upsert(MukkadamLedgerEntry, data.get('mukkadam_ledger_entries', []), 'id')
    report('mukkadam_ledger_entries', *r)

    r = upsert(Allocation, data.get('allocations', []), 'id')
    report('allocations', *r)

    r = upsert(PaymentProof, data.get('payment_proofs', []), 'id')
    report('payment_proofs', *r)

    r = upsert(MukkadamPayment, data.get('mukkadam_payments', []), 'id')
    report('mukkadam_payments', *r)

    r = upsert(ActivityLogTender, data.get('activity_logs', []), 'id')
    report('activity_logs', *r)

    r = upsert(ExtraWorker, data.get('extra_workers', []), 'id')
    report('extra_workers', *r)

    r = upsert(Leave, data.get('leaves', []), 'id')
    report('leaves', *r)

    r = upsert(AllocationChangeLogTender, data.get('allocation_change_logs', []), 'id')
    report('allocation_change_logs', *r)

    r = upsert(PaymentChangeLog, data.get('payment_change_logs', []), 'id')
    report('payment_change_logs', *r)

    r = upsert(MukkadamWeeklyPayment, data.get('mukkadam_weekly_payments', []), 'id')
    report('mukkadam_weekly_payments', *r)

    r = upsert(MukkadamMiscCost, data.get('mukkadam_misc_costs', []), 'id')
    report('mukkadam_misc_costs', *r)

    r = upsert(MukkadamJobSettlement, data.get('mukkadam_job_settlements', []), 'id')
    report('mukkadam_job_settlements', *r)

print("\n" + "  " + "=" * 70)
print("✅ Import complete!")