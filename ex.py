import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from django.core.serializers.json import DjangoJSONEncoder
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

data = {
    "activity_catalog":                    list(ActivityCatalog.objects.all().values()),
    "clusters":                            list(Cluster.objects.all().values()),
    "farmers":                             list(Farmer.objects.all().values()),
    "plots":                               list(Plot.objects.all().values()),
    "cluster_activity_rates":              list(ClusterActivityRate.objects.all().values()),
    "farmer_calls":                        list(FarmerCall.objects.all().values()),
    "mukkadam_otp_requests":               list(MukkadamOTPRequest.objects.all().values()),
    "jobs":                                list(Job.objects.all().values()),
    "job_activities":                      list(JobActivity.objects.all().values()),
    "job_notes":                           list(JobNote.objects.all().values()),
    "job_bookings":                        list(JobBooking.objects.all().values()),
    "farmer_payments":                     list(FarmerPayment.objects.all().values()),
    "farmer_payment_webhook_logs":         list(FarmerPaymentWebhookLog.objects.all().values()),
    "activity_schedule_rules":             list(ActivityScheduleRule.objects.all().values()),
    "cluster_activity_schedule_rules":     list(ClusterActivityScheduleRule.objects.all().values()),
    "mukkadam_ledger_entries":             list(MukkadamLedgerEntry.objects.all().values()),
    "mukkadams":                           list(Mukkadam.objects.all().values()),
    "cluster_mukkadam_activity_rates":     list(ClusterMukkadamActivityRate.objects.all().values()),
    "farmer_bill_webhook_logs":            list(FarmerBillWebhookLog.objects.all().values()),
    "mukkadam_activity_rates":             list(MukkadamActivityRate.objects.all().values()),
    "mukkadam_availability":               list(MukkadamAvailability.objects.all().values()),
    "allocations":                         list(Allocation.objects.all().values()),
    "payment_proofs":                      list(PaymentProof.objects.all().values()),
    "mukkadam_payments":                   list(MukkadamPayment.objects.all().values()),
    "activity_logs":                       list(ActivityLogTender.objects.all().values()),
    "extra_workers":                       list(ExtraWorker.objects.all().values()),
    "leaves":                              list(Leave.objects.all().values()),
    "allocation_change_logs":              list(AllocationChangeLogTender.objects.all().values()),
    "payment_change_logs":                 list(PaymentChangeLog.objects.all().values()),
    "cluster_mukkadam_assignments":        list(ClusterMukkadamAssignment.objects.all().values()),
    "mukkadam_weekly_payments":            list(MukkadamWeeklyPayment.objects.all().values()),
    "mukkadam_misc_costs":                 list(MukkadamMiscCost.objects.all().values()),
    "mukkadam_job_settlements":            list(MukkadamJobSettlement.objects.all().values()),
    "farmer_cluster_mukkadam_assignments": list(FarmerClusterMukkadamAssignment.objects.all().values()),

    
}

with open('export.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)

print("✅ Export complete!")
print("-" * 40)
for key, val in data.items():
    print(f"  {key:<45} {len(val):>6} records")
print("-" * 40)
print(f"  {'TOTAL':<45} {sum(len(v) for v in data.values()):>6} records")