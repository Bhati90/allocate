# # services/settlement.py

# from decimal import Decimal
# from django.utils import timezone
# from django.db import transaction
from tender.models import (
    Job, Allocation, MukkadamJobSettlement,
    ClusterMukkadamAssignment, MukkadamWeeklyPayment, ActivityCatalog
)

from tender.models import (
        Allocation, MukkadamJobSettlement, ClusterMukkadamAssignment,
        MukkadamWeeklyPayment, MukkadamMiscCost
    )


def get_shoot_selection_date(job: Job):
    """
    Returns the scheduled_date of the shoot selection activity for this job.
    Returns None if no shoot selection activity exists or date not set.
    """
    shoot_activity = job.activities.filter(
        activity__name__icontains='shoot selection',
        scheduled_date__isnull=False
    ).order_by('scheduled_date').last()

    return shoot_activity.scheduled_date if shoot_activity else None


def is_settlement_triggered(job: Job) -> bool:
    """Shoot selection date must have passed"""
    shoot_date = get_shoot_selection_date(job)
    if not shoot_date:
        return False
    return shoot_date <= timezone.localdate()

# from django.db.models import Sum
# from tender.models import MukkadamMiscCost
# def calculate_settlement_for_mukkadam(mukkadam, job, cluster=None) -> dict:
#     today = timezone.localdate()

#     # ── FIXED: Don't filter by date — include ALL allocations for this job ──
#     # Settlement should include everything allocated, not just past dates
#     allocations = Allocation.objects.filter(
#         mukkadam=mukkadam,
#         job_activity__job=job,
#     ).select_related('job_activity__activity')

#     gross = Decimal('0')
#     for a in allocations:
#         if a.use_actual_for_settlement and a.actual_area_done is not None:
#             effective_area = Decimal(str(a.actual_area_done))
#         else:
#             effective_area = Decimal(str(a.allocated_area or 0))
#         rate = Decimal(str(a.mukkadam_rate or 0))
#         gross += (effective_area * rate).quantize(Decimal('0.01'))

#     deposit_held = (gross * Decimal('0.10')).quantize(Decimal('0.01'))
#     payable_this_job = gross - deposit_held  # 90%

#     # ── Previous job deposit carried forward ──
#     prev_settlement = MukkadamJobSettlement.objects.filter(
#         mukkadam=mukkadam,
#         status__in=['paid', 'no_payment_needed'],
#     ).exclude(job=job).order_by('-created_at').first()

#     deposit_carried = Decimal('0')
#     if prev_settlement:
#         deposit_carried = (
#             prev_settlement.gross_amount * Decimal('0.10')
#         ).quantize(Decimal('0.01'))

#     # ── FIXED: Advance deduction ──
#     # Check if advance was used in any OTHER job's settlement
#     advance_used_before = MukkadamJobSettlement.objects.filter(
#         mukkadam=mukkadam,
#         advance_deducted__gt=0,
#     ).exclude(job=job).exists()  # ← exclude current job

#     advance_to_deduct = Decimal('0')
#     if not advance_used_before:
#         # ── FIXED: Try to find assignment even if cluster is None ──
#         assignment_qs = ClusterMukkadamAssignment.objects.filter(
#             mukkadam=mukkadam,
#             is_active=True,
#         )
#         if cluster:
#             assignment_qs = assignment_qs.filter(cluster=cluster)

#         assignment = assignment_qs.first()
#         if assignment and assignment.advance_amount:
#             advance_to_deduct = Decimal(str(assignment.advance_amount))

#     # ── Weekly payments not yet applied to any settlement ──
#     already_applied_ids = MukkadamWeeklyPayment.objects.filter(
#         settlements__isnull=False
#     ).exclude(
#         settlements__job=job  # allow re-applying to same job if recalculating
#     ).values_list('id', flat=True)

#     unapplied_weekly = MukkadamWeeklyPayment.objects.filter(
#         assignment__mukkadam=mukkadam,
#         payment_date__lte=today,
#     ).exclude(id__in=already_applied_ids)

#     weekly_total = sum(
#         Decimal(str(w.amount)) for w in unapplied_weekly
#     )

#     # ── Misc costs ──
#     from django.db.models import Sum as DSum
#     misc_total = MukkadamMiscCost.objects.filter(
#         mukkadam=mukkadam,
#         job=job,
#     ).aggregate(total=DSum('amount'))['total'] or Decimal('0')
#     misc_total = Decimal(str(misc_total))
#     credit_carried = Decimal('0')
#     prev_negative = MukkadamJobSettlement.objects.filter(
#         mukkadam=mukkadam,
#         net_payable__lt=0,
#         status__in=['paid', 'no_payment_needed'],
#     ).exclude(job=job).aggregate(
#         total=Sum('net_payable')
#     )['total'] or Decimal('0')
    
#     credit_carried = abs(prev_negative)  # positive number representing credit

#     # ── Net payable ──
    
#     net_payable = (
#         payable_this_job
#         + deposit_carried
#         - advance_to_deduct
        
#         - weekly_total
#         - misc_total
#         - credit_carried        # ← deduct credit from previous jobs
#     ).quantize(Decimal('0.01'))

    

#     return {
#         'mukkadam': mukkadam,
#         'job': job,
#         'cluster': cluster,
#         'allocations': allocations,
#         'gross_amount': gross,
#         'deposit_held': deposit_held,
#         'payable_this_job': payable_this_job,
#         'deposit_carried_forward': deposit_carried,
#         'advance_deducted': advance_to_deduct,
#         'credit_carried_forward': credit_carried,
#         'net_payable': net_payable,
#         'weekly_payments_deducted': weekly_total,
#         'unapplied_weekly_ids': list(unapplied_weekly.values_list('id', flat=True)),
#         'net_payable': net_payable,
#         'misc_total': misc_total,
#     }

# def calculate_settlement_for_mukkadam_updated(mukkadam, job, cluster):
#     """
#     Updated settlement calculation with:
#     - Dispute check (skip disputed allocations without override)
#     - Advance deducted from first job only
#     - Weekly deducted from first job only
#     """
#     from decimal import Decimal, ROUND_HALF_UP
    

#     allocations = Allocation.objects.filter(
#         mukkadam     = mukkadam,
#         job_activity__job = job,
#     ).select_related('job_activity__activity')

#     gross = Decimal('0')
#     for alloc in allocations:
#         # ── DISPUTE CHECK ──────────────────────────────────────────────
#         # If disputed and no override yet → skip this allocation
#         if alloc.payment_status == 'dispute' and not alloc.use_actual_for_settlement:
#             continue

#         # Effective area for billing
#         if alloc.use_actual_for_settlement and alloc.actual_area_done:
#             effective_area = alloc.actual_area_done
#         elif alloc.admin_override_area:
#             effective_area = alloc.admin_override_area
#         else:
#             effective_area = alloc.allocated_area

#         if alloc.mukkadam_rate and effective_area:
#             gross += effective_area * alloc.mukkadam_rate

#     deposit_held         = (gross * Decimal('0.10')).quantize(Decimal('0.01'), ROUND_HALF_UP)
#     payable_this_job     = gross - deposit_held

#     # ── Deposit from previous PAID job ────────────────────────────────
#     prev_settlement = MukkadamJobSettlement.objects.filter(
#         mukkadam = mukkadam,
#         status__in = ['paid', 'no_payment_needed'],
#     ).exclude(job=job).order_by('-calculated_at').first()

#     deposit_carried = Decimal('0')
#     if prev_settlement:
#         deposit_carried = (prev_settlement.gross_amount * Decimal('0.10')).quantize(
#             Decimal('0.01'), ROUND_HALF_UP
#         )

#     # ── Credit from previous jobs (negative net_payable) ──────────────
#     credit_carried = Decimal('0')
#     prev_negatives = MukkadamJobSettlement.objects.filter(
#         mukkadam  = mukkadam,
#         status__in = ['paid', 'no_payment_needed'],
#         net_payable__lt = 0,
#     ).exclude(job=job)
#     for neg in prev_negatives:
#         credit_carried += abs(neg.net_payable)

#     # ── ADVANCE — first job only ───────────────────────────────────────
#     advance_to_deduct = Decimal('0')
#     already_advanced = MukkadamJobSettlement.objects.filter(
#         mukkadam       = mukkadam,
#         advance_deducted__gt = 0,
#     ).exclude(job=job).exists()

#     if not already_advanced:
#         try:
#             assignment = ClusterMukkadamAssignment.objects.filter(
#                 mukkadam = mukkadam,
#                 cluster  = cluster,
#                 is_active = True,
#             ).first() or ClusterMukkadamAssignment.objects.filter(
#                 mukkadam  = mukkadam,
#                 is_active = True,
#             ).first()
#             if assignment:
#                 advance_to_deduct = Decimal(str(assignment.advance_amount or 0))
#         except Exception:
#             pass

#     # ── WEEKLY — first job only ────────────────────────────────────────
#     # Get unapplied weekly payments for this mukkadam
#     already_applied_ids = set()
#     other_settlements = MukkadamJobSettlement.objects.filter(
#         mukkadam = mukkadam,
#     ).exclude(job=job)
#     for s in other_settlements:
#         already_applied_ids.update(s.weekly_payments_applied.values_list('id', flat=True))

#     from django.utils import timezone as tz
#     unapplied_weekly = MukkadamWeeklyPayment.objects.filter(
#         assignment__mukkadam = mukkadam,
#         payment_date__lte    = tz.now().date(),
#     ).exclude(id__in=already_applied_ids)

#     weekly_total      = sum(w.amount for w in unapplied_weekly) or Decimal('0')
#     unapplied_ids     = list(unapplied_weekly.values_list('id', flat=True))

#     # ── Misc costs ────────────────────────────────────────────────────
#     misc_total = Decimal('0')
#     misc_costs = MukkadamMiscCost.objects.filter(mukkadam=mukkadam, job=job)
#     for m in misc_costs:
#         misc_total += m.amount

#     # ── Net payable ───────────────────────────────────────────────────
#     net_payable = (
#         payable_this_job
#         + deposit_carried
#         + credit_carried
#         - advance_to_deduct
#         - weekly_total
#         - misc_total
#     )

#     return {
#         'gross_amount':           gross,
#         'deposit_held':           deposit_held,
#         'payable_this_job':       payable_this_job,
#         'deposit_carried_forward': deposit_carried,
#         'credit_carried_forward': credit_carried,
#         'advance_deducted':       advance_to_deduct,
#         'weekly_payments_deducted': weekly_total,
#         'misc_costs':             misc_total,
#         'net_payable':            net_payable,
#         'unapplied_weekly_ids':   unapplied_ids,
#     }


# @transaction.atomic
# def create_or_update_settlement(mukkadam, job, cluster=None) -> MukkadamJobSettlement:
#     """
#     Calculate and save/update settlement for a mukkadam+job.
#     Safe to call multiple times — updates if already exists.
#     """
#     data = calculate_settlement_for_mukkadam(mukkadam, job, cluster)

#     settlement, _ = MukkadamJobSettlement.objects.update_or_create(
#         mukkadam=mukkadam,
#         job=job,
#         defaults={
#             'cluster': cluster,
#             'gross_amount': data['gross_amount'],
#             'payable_amount': data['payable_this_job'],
#             'deposit_carried_forward': data['deposit_carried_forward'],
#             'credit_carried_forward': data['credit_carried_forward'],
#             'advance_deducted': data['advance_deducted'],
#             'weekly_payments_deducted': data['weekly_payments_deducted'],
#             'net_payable': data['net_payable'],
#             'status': 'no_payment_needed' if data['net_payable'] <= 0 else 'calculated',
#             'calculated_at': timezone.now(),
#         }
#     )

#     # Link which weekly payments were consumed
#     settlement.weekly_payments_applied.set(data['unapplied_weekly_ids'])

#     return settlement

# def process_all_completed_settlements():
#     """
#     Treat ALL allocations whose allocated_date <= today as completed.
#     No shoot selection date check. Settle everything done so far.
#     """
#     from tender.models import Mukkadam

#     today = timezone.localdate()
#     results = []
#     summary = []

#     # All jobs that have at least one allocation in the past
#     jobs_with_past_allocs = Job.objects.filter(
#         activities__allocations__allocated_date__lte=today
#     ).distinct()

#     for job in jobs_with_past_allocs:
#         mukkadams_on_job = Mukkadam.objects.filter(
#             allocations__job_activity__job=job,
#             allocations__allocated_date__lte=today,
#         ).distinct()

#         cluster = job.clusters.first()

#         for mukkadam in mukkadams_on_job:
#             data = calculate_settlement_for_mukkadam(mukkadam, job, cluster)

#             if data['gross_amount'] <= 0:
#                 continue

#             settlement = create_or_update_settlement(mukkadam, job, cluster)
#             results.append(settlement)

#             summary.append({
#                 'type': 'mukkadam',
#                 'name': mukkadam.mukkadam_name,
#                 'job_id': job.job_id,
#                 'farmer': job.farmer.farmer_name if hasattr(job, 'farmer') else '—',
#                 'gross': data['gross_amount'],
#                 'weekly_deducted': data['weekly_payments_deducted'],
#                 'advance_deducted': data['advance_deducted'],
#                 'net_payable': data['net_payable'],
#                 'status': 'PENDING' if data['net_payable'] > 0 else 'CLEARED',
#             })

#         # Farmer billing summary
#         from .farmerbill import get_farmer_billing_for_job
#         farmer_data = get_farmer_billing_for_job(job.job_id)
#         if farmer_data:
#             summary.append({
#                 'type': 'farmer',
#                 'name': farmer_data['farmer_name'],
#                 'job_id': job.job_id,
#                 'farmer': farmer_data['farmer_name'],
#                 'billed_so_far': farmer_data['summary']['total_billable_so_far'],
#                 'total_paid': farmer_data['summary']['total_paid'],
#                 'balance_due': farmer_data['summary']['balance_due'],
#                 'status': 'PENDING' if farmer_data['summary']['balance_due'] > 0 else 'CLEARED',
#             })

#     return results, summary
# def process_all_triggered_settlements():
#     """
#     Run this daily (management command / celery).
#     Finds all jobs where shoot selection date passed and settlement not yet calculated.
#     """
#     from tender.models import Job, Mukkadam

#     today = timezone.localdate()

#     # Jobs with shoot selection date passed
#     triggered_jobs = Job.objects.filter(
#         activities__activity__name__icontains='shoot selection',
#         activities__scheduled_date__lte=today,
#     ).distinct()

#     results = []
#     for job in triggered_jobs:
#         # Find all mukkadams who worked on this job
#         mukkadams_on_job = Mukkadam.objects.filter(
#             allocations__job_activity__job=job
#         ).distinct()

#         for mukkadam in mukkadams_on_job:
#             # Skip if already settled
#             if MukkadamJobSettlement.objects.filter(
#                 mukkadam=mukkadam, job=job,
#                 status__in=['paid', 'no_payment_needed', 'payment_raised']
#             ).exists():
#                 continue

#             cluster = job.clusters.first()
#             settlement = create_or_update_settlement(mukkadam, job, cluster)
#             results.append(settlement)

#     return results



# from decimal import Decimal
# from tender.models import (
#     MukkadamJobSettlement, MukkadamWeeklyPayment, Allocation,
#      Job
# )
# from tender.utils import get_presigned_urls_batch,get_presigned_url
# import django.db.models as models
# # from .utils import get_presigned_url, get_presigned_urls_batch


# def build_week_ledger(mukkadam, assignment):
#     """
#     Build the complete week-wise ledger for one mukkadam.
    
#     Logic:
#     - Start with advance as first debit
#     - For each weekly payment (sorted by date):
#         * Add weekly debit
#         * Find billing events that happened IN that week:
#             - Shoot selection completed in this week → shoot_billing event
#             - All activities done in this week (post-shoot) → deposit_release event
#         * Calculate running balance
#     - Running balance > 0 → payment due
#     """
    
#     # ── 1. Get all weekly payments sorted ──────────────────────────────────
#     weekly_payments = list(
#         MukkadamWeeklyPayment.objects.filter(assignment=assignment)
#         .order_by('payment_date')
#         .values('id', 'payment_date', 'amount', 'crew_size_on_date', 'proof_s3_key')
#     )
    
#     # Batch presign proof URLs
#     weekly_proof_keys = [w['proof_s3_key'] for w in weekly_payments if w['proof_s3_key']]
#     weekly_proof_map = {}
#     if weekly_proof_keys:
#         urls = get_presigned_urls_batch(weekly_proof_keys)
#         weekly_proof_map = dict(zip(weekly_proof_keys, urls))
    
#     # ── 2. Get all settlements for this mukkadam ────────────────────────────
#     settlements = list(
#         MukkadamJobSettlement.objects.filter(
#             assignment=assignment
#         ).select_related('job', 'job__farmer')
#         .exclude(status='pending')
#         .order_by('calculated_at')
#     )
    
#     # For each settlement, get activities
#     settlement_activities = {}
#     for s in settlements:
#         allocs = Allocation.objects.filter(
#             job_activity__job=s.job,
#             mukkadam=mukkadam,
#             work_status='completed',
#         ).select_related('job_activity')
#         settlement_activities[s.job.job_id] = list(allocs)
    
#     # ── 3. Get pending work (no shoot selection yet) ─────────────────────────
#     # Jobs that have completed allocations but no settlement calculated
#     settled_job_ids = {s.job.job_id for s in settlements}
#     all_jobs = Job.objects.filter(
#         activities__allocations__mukkadam=mukkadam,
#         activities__allocations__assignment=assignment,
#     ).distinct()
    
#     pending_jobs = []
#     for job in all_jobs:
#         if job.job_id in settled_job_ids:
#             continue
#         allocs = Allocation.objects.filter(
#             job_activity__job=job,
#             mukkadam=mukkadam,
#             work_status='completed',
#         ).select_related('job_activity')
#         if allocs.exists():
#             gross = sum(
#                 float(_get_activity_gross(a)) for a in allocs
#             )
#             pending_jobs.append({
#                 'farmer_name': job.farmer.farmer_name,
#                 'job_id': str(job.job_id),
#                 'gross_so_far': gross,
#                 'note': 'Shoot selection pending — not yet payable',
#                 'activities': [
#                     {
#                         'activity_name': a.job_activity.activity_name,
#                         'area': float(a.actual_area_done or a.allocated_area),
#                         'rate': float(a.mukkadam_rate),
#                         'amount': float(_get_activity_gross(a)),
#                     }
#                     for a in allocs
#                 ]
#             })
    
#     # ── 4. Assign billing events to week buckets ────────────────────────────
#     # Each settlement has:
#     #   calculated_at → shoot selection week
#     #   all_done_at   → deposit release week (need to add this field, or derive from activities)
    
#     # Get weekly payment dates as sorted list for bucket assignment
#     weekly_dates = [str(w['payment_date']) for w in weekly_payments]
    
#     def get_week_bucket(date_str):
#         """Return the weekly payment date this event falls into."""
#         if not date_str or not weekly_dates:
#             return None
#         ds = str(date_str)[:10]
#         # Find the weekly payment date that this date falls before
#         for wd in weekly_dates:
#             if ds <= wd:
#                 return wd
#         return weekly_dates[-1]  # after last weekly → put in last week
    
#     # Build events per week bucket
#     # event types: shoot_billing, deposit_release
#     events_by_week = {wd: [] for wd in weekly_dates}
    
#     for s in settlements:
#         farmer_name = s.job.farmer.farmer_name
#         job_id = str(s.job.job_id)
#         allocs = settlement_activities.get(s.job.job_id, [])
        
#         # Shoot billing event — in the week shoot selection was calculated
#         if s.calculated_at:
#             bucket = get_week_bucket(str(s.calculated_at.date()))
#             if bucket and bucket in events_by_week:
#                 # Activities at shoot selection time = all completed allocs
#                 # (we don't know exactly which were pre-shoot vs post-shoot without a date marker)
#                 # Use payable_amount as the payable at shoot selection
#                 events_by_week[bucket].append({
#                     'type': 'shoot_billing',
#                     'farmer_name': farmer_name,
#                     'job_id': job_id,
#                     'description': f'Shoot Selection — 90% of ₹{int(float(s.gross_amount)):,}',
#                     'gross_at_event': float(s.gross_amount),
#                     'payable': float(s.payable_amount),
#                     'deposit_held': float(s.deposit_held),
#                     'deposit_released': 0,
#                     'activities': [
#                         {
#                             'activity_name': a.job_activity.activity_name,
#                             'area': float(a.actual_area_done or a.allocated_area),
#                             'rate': float(a.mukkadam_rate),
#                             'amount': float(_get_activity_gross(a)),
#                         }
#                         for a in allocs
#                     ]
#                 })
        
#         # Deposit release event — all activities done
#         # Check if deposit was released (deposit_held = 0 but status != pending)
#         # and there's a separate "all done" completion
#         if float(s.deposit_held) == 0 and s.status in ('calculated', 'paid', 'no_payment_needed'):
#             # Find when last activity was completed for this job
#             last_alloc = Allocation.objects.filter(
#                 job_activity__job=s.job,
#                 mukkadam=mukkadam,
#                 work_status='completed',
#             ).order_by('-updated_at').first()
            
#             if last_alloc and s.calculated_at:
#                 all_done_date = last_alloc.updated_at.date()
#                 # Only show deposit release if it happened AFTER shoot selection
#                 if all_done_date > s.calculated_at.date():
#                     bucket = get_week_bucket(str(all_done_date))
#                     if bucket and bucket in events_by_week:
#                         # Post-shoot gross = additional activities after shoot selection
#                         # For simplicity: show total deposit released + any additional work
#                         # Backend should track this separately — for now derive from gross update
#                         # Additional gross = current gross - gross at shoot selection
#                         # (We don't have gross_at_shoot stored, so show deposit only for now)
#                         old_deposit = (Decimal(str(s.gross_amount)) * Decimal('0.1')).quantize(Decimal('0.01'))
                        
#                         events_by_week[bucket].append({
#                             'type': 'deposit_release',
#                             'farmer_name': farmer_name,
#                             'job_id': job_id,
#                             'description': f'All activities done — 10% deposit released',
#                             'gross_at_event': 0,
#                             'payable': float(old_deposit),
#                             'deposit_held': 0,
#                             'deposit_released': float(old_deposit),
#                             'activities': []
#                         })
    
#     # ── 5. Build week-wise ledger ───────────────────────────────────────────
#     advance = float(assignment.advance_amount or 0)
#     running_balance = -advance
    
#     ledger = []
    
#     # Advance row (before week 1)
#     if advance > 0:
#         ledger.append({
#             'week_num': 0,
#             'type': 'advance',
#             'payment_date': None,
#             'weekly_paid': advance,
#             'weekly_proof_url': None,
#             'billing_events': [],
#             'running_balance': running_balance,
#             'payable_this_week': 0,
#             'label': f'Advance Given',
#         })
    
#     for wi, w in enumerate(weekly_payments):
#         wd = str(w['payment_date'])
#         weekly_amount = float(w['amount'])
#         events = events_by_week.get(wd, [])
        
#         payable_this_week = sum(e['payable'] for e in events)
#         running_balance = running_balance - weekly_amount + payable_this_week
        
#         ledger.append({
#             'week_num': wi + 1,
#             'type': 'week',
#             'payment_date': wd,
#             'weekly_paid': weekly_amount,
#             'weekly_proof_url': weekly_proof_map.get(w['proof_s3_key']) if w['proof_s3_key'] else None,
#             'billing_events': events,
#             'running_balance': round(running_balance, 2),
#             'payable_this_week': round(payable_this_week, 2),
#             'can_pay': running_balance > 0.01,
#         })
    
#     # ── 6. Summary ──────────────────────────────────────────────────────────
#     total_gross = sum(float(s.gross_amount) for s in settlements)
#     total_deposit_held = sum(float(s.deposit_held) for s in settlements)
#     total_weekly_paid = sum(w['amount'] for w in weekly_payments)
#     net_payable = sum(
#         float(s.net_payable) for s in settlements
#         if s.status == 'calculated'
#     )
    
#     return {
#         'week_ledger': ledger,
#         'pending_work': pending_jobs,
#         'summary': {
#             'total_gross': round(total_gross, 2),
#             'total_advance': round(advance, 2),
#             'total_weekly_paid': float(total_weekly_paid),
#             'total_deposit_held': round(total_deposit_held, 2),
#             'net_payable': round(net_payable, 2),
#             'running_balance': round(running_balance, 2),
#         }
#     }


# def _get_activity_gross(allocation):
#     """Get effective mukkadam billing amount for one allocation."""
#     if (allocation.payment_status == 'dispute'
#             and not allocation.admin_override_area
#             and not allocation.use_actual_for_settlement):
#         return Decimal('0')
#     if allocation.admin_override_area:
#         area = allocation.admin_override_area
#     elif allocation.use_actual_for_settlement and allocation.actual_area_done:
#         area = allocation.actual_area_done
#     else:
#         area = allocation.allocated_area
#     return (area * allocation.mukkadam_rate).quantize(Decimal('0.01'))

# services/settlement.py
#
# KEY CHANGE: Settlement is now per (mukkadam + job + plot)
# Same mukkadam working on Job 1929 Plot A and Job 1929 Plot B
# = TWO separate settlements, billed independently.
#
# Model change required:
#   Add to MukkadamJobSettlement:
#       plot = models.ForeignKey(Plot, null=True, blank=True, on_delete=models.SET_NULL)
#   Change unique_together:
#       unique_together = ['mukkadam', 'job', 'plot']
#   Run: python manage.py makemigrations && python manage.py migrate

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from tender.models import (
    Job, Allocation, MukkadamJobSettlement,
    ClusterMukkadamAssignment, MukkadamWeeklyPayment,
    MukkadamMiscCost
)
from tender.utils import get_presigned_urls_batch, get_presigned_url


# ═══════════════════════════════════════════════════════════════════
# PLOT HELPER
# ═══════════════════════════════════════════════════════════════════

def get_plot_from_allocation(allocation):
    """Get plot from allocation via job_activity.plot"""
    return allocation.job_activity.plot


# ═══════════════════════════════════════════════════════════════════
# TRIGGER CHECKS — per plot
# ═══════════════════════════════════════════════════════════════════

def is_settlement_triggered(job, mukkadam, plot) -> bool:
    """
    Settlement triggered ONLY when shoot selection is completed + farmer verified
    for this specific plot.
    """
    import django.db.models as _m
    return Allocation.objects.filter(
        job_activity__job=job,
        job_activity__plot=plot,
        mukkadam=mukkadam,
        work_status='completed',
        job_activity__activity__name__icontains='shoot selection',
    ).filter(
        _m.Q(farmer_agreed=True) |
        _m.Q(payment_status='done') |
        _m.Q(admin_override_area__isnull=False)
    ).exists()


def is_all_activities_done(job, mukkadam, plot) -> bool:
    """
    Returns True when ALL allocations for this job+plot are completed + verified.
    """
    all_allocs = Allocation.objects.filter(
        job_activity__job=job,
        job_activity__plot=plot,
        mukkadam=mukkadam,
    )
    if not all_allocs.exists():
        return False
    return all_allocs.filter(
        work_status='completed',
        farmer_agreed=True,
    ).count() == all_allocs.count()


# ═══════════════════════════════════════════════════════════════════
# GROSS CALCULATION — per plot, only verified completed work
# ═══════════════════════════════════════════════════════════════════

def calculate_gross_for_mukkadam(mukkadam, job, plot):
    """
    Gross = sum of completed + farmer-verified allocations for this job+plot only.
    """
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam,
        job_activity__job=job,
        job_activity__plot=plot,        # ← plot filter
        work_status='completed',
        farmer_agreed=True,
    )

    gross = Decimal('0')
    for alloc in allocations:
        if alloc.payment_status == 'dispute' and not alloc.use_actual_for_settlement:
            continue
        if alloc.admin_override_area:
            area = alloc.admin_override_area
        elif alloc.use_actual_for_settlement and alloc.actual_area_done:
            area = alloc.actual_area_done
        else:
            area = alloc.allocated_area
        rate = alloc.mukkadam_rate or Decimal('0')
        if area and rate:
            gross += (area * rate).quantize(Decimal('0.01'), ROUND_HALF_UP)

    return gross


# ═══════════════════════════════════════════════════════════════════
# CROSS-JOB DEDUCTIONS — advance + weekly absorbed once across ALL plots/jobs
# ═══════════════════════════════════════════════════════════════════

def get_cross_job_deductions(mukkadam, assignment, current_job, current_plot):
    """
    Advance and weekly are deducted ONCE across all jobs+plots for this mukkadam.
    Checks ALL other settlements (any job, any plot) to see what's already absorbed.

    deposit_carried and credit_carried only come from no_payment_needed settlements
    — paid settlements are fully settled, nothing to carry forward.
    """
    # All other settlements for this mukkadam (any job, any plot)
    other_settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
    ).exclude(job=current_job, plot=current_plot)

    # ── Advance — deducted ONCE total ────────────────────────────────
    advance_already_used = other_settlements.filter(
        advance_deducted__gt=0,
    ).exists()

    advance_to_deduct = Decimal('0')
    if not advance_already_used:
        if assignment and assignment.advance_amount:
            advance_to_deduct = Decimal(str(assignment.advance_amount))

    # ── Weekly payments — check ALL other settlements ─────────────────
    already_applied_ids = set()
    for s in other_settlements:
        already_applied_ids.update(
            s.weekly_payments_applied.values_list('id', flat=True)
        )

    unapplied_weekly = MukkadamWeeklyPayment.objects.filter(
        assignment=assignment,
        payment_date__lte=timezone.localdate(),
    ).exclude(id__in=already_applied_ids)

    weekly_total  = sum(Decimal(str(w.amount)) for w in unapplied_weekly)
    unapplied_ids = list(unapplied_weekly.values_list('id', flat=True))

    # ── Credit from no_payment_needed (negative net) only ────────────
    prev_negatives = other_settlements.filter(
        status='no_payment_needed',
        net_payable__lt=0,
    )
    credit_carried = abs(
        prev_negatives.aggregate(t=Sum('net_payable'))['t'] or Decimal('0')
    )

    # ── Deposit from no_payment_needed only ──────────────────────────
    # paid = deposit already released. no_payment_needed = deposit still pending release.
    prev_unpaid = other_settlements.filter(
        status='no_payment_needed',
    ).order_by('-calculated_at').first()

    deposit_carried = Decimal('0')
    if prev_unpaid:
        deposit_pct     = prev_unpaid.deposit_percent or Decimal('10')
        deposit_carried = (
            prev_unpaid.gross_amount * deposit_pct / 100
        ).quantize(Decimal('0.01'), ROUND_HALF_UP)

    return advance_to_deduct, weekly_total, unapplied_ids, credit_carried, deposit_carried


# ═══════════════════════════════════════════════════════════════════
# MAIN SETTLEMENT CALCULATION — per plot
# ═══════════════════════════════════════════════════════════════════

def calculate_settlement_for_mukkadam_updated(mukkadam, job, plot, cluster=None) -> dict:
    """Calculate settlement for mukkadam on a specific job+plot."""
    assignment_qs = ClusterMukkadamAssignment.objects.filter(
        mukkadam=mukkadam, is_active=True,
    )
    if cluster:
        assignment_qs = assignment_qs.filter(cluster=cluster)
    assignment = assignment_qs.first()

    gross = calculate_gross_for_mukkadam(mukkadam, job, plot)

    deposit_held     = (gross * Decimal('0.10')).quantize(Decimal('0.01'), ROUND_HALF_UP)
    payable_this_job = gross - deposit_held  # 90%

    advance_to_deduct, weekly_total, unapplied_ids, credit_carried, deposit_carried = \
        get_cross_job_deductions(mukkadam, assignment, job, plot)

    misc_total = MukkadamMiscCost.objects.filter(
        mukkadam=mukkadam, job=job,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    misc_total = Decimal(str(misc_total))

    net_payable = (
        payable_this_job
        + deposit_carried
        - credit_carried
        - advance_to_deduct
        - weekly_total
        - misc_total
    ).quantize(Decimal('0.01'), ROUND_HALF_UP)

    return {
        'gross_amount':             gross,
        'deposit_held':             deposit_held,
        'payable_this_job':         payable_this_job,
        'deposit_carried_forward':  deposit_carried,
        'credit_carried_forward':   credit_carried,
        'advance_deducted':         advance_to_deduct,
        'weekly_payments_deducted': weekly_total,
        'misc_costs':               misc_total,
        'net_payable':              net_payable,
        'unapplied_weekly_ids':     unapplied_ids,
        'assignment':               assignment,
    }


# ═══════════════════════════════════════════════════════════════════
# SAVE / UPDATE — per plot
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def create_or_update_settlement(mukkadam, job, plot, cluster=None) -> MukkadamJobSettlement:
    """
    Create or update settlement for mukkadam + job + plot.

    Rules:
    - paid               → NEVER overwrite deductions
    - calculated/no_pay  → only update gross delta, keep deductions
    - pending/missing    → full calculation from scratch
    """
    existing = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        job=job,
        plot=plot,
    ).first()

    # PAID — locked
    if existing and existing.status == 'paid':
        return existing

    # CALCULATED — update gross only, keep deductions
    if existing and existing.status in ('calculated', 'no_payment_needed'):
        new_gross = calculate_gross_for_mukkadam(mukkadam, job, plot)
        if new_gross == existing.gross_amount:
            return existing

        gross_delta = new_gross - existing.gross_amount
        deposit_pct = existing.deposit_percent or Decimal('10')
        new_payable = existing.payable_amount + (gross_delta * (1 - deposit_pct / 100))
        new_net     = existing.net_payable    + (gross_delta * (1 - deposit_pct / 100))

        new_status = existing.status
        if new_net > Decimal('0'):
            new_status = 'calculated'

        # Use queryset update to bypass post_save signal chain
        MukkadamJobSettlement.objects.filter(pk=existing.pk).update(
            gross_amount   = new_gross,
            payable_amount = new_payable.quantize(Decimal('0.01'), ROUND_HALF_UP),
            net_payable    = new_net.quantize(Decimal('0.01'), ROUND_HALF_UP),
            status         = new_status,
        )
        existing.refresh_from_db()
        return existing

    # PENDING / NEW — full calculation
    data = calculate_settlement_for_mukkadam_updated(mukkadam, job, plot, cluster)

    settlement, _ = MukkadamJobSettlement.objects.update_or_create(
        mukkadam=mukkadam,
        job=job,
        plot=plot,
        defaults={
            'cluster':                    cluster,
            'gross_amount':               data['gross_amount'],
            'payable_amount':             data['payable_this_job'],
            'deposit_carried_forward':    data['deposit_carried_forward'],
            'credit_carried_forward':     data['credit_carried_forward'],
            'advance_deducted':           data['advance_deducted'],
            'weekly_payments_deducted':   data['weekly_payments_deducted'],
            'net_payable':                data['net_payable'],
            'status': (
                'no_payment_needed' if data['net_payable'] <= 0 else 'calculated'
            ),
            'calculated_at': timezone.now(),
        }
    )
    settlement.weekly_payments_applied.set(data['unapplied_weekly_ids'])
    return settlement


@transaction.atomic
def update_settlement_on_all_done(mukkadam, job, plot, cluster=None) -> MukkadamJobSettlement:
    """
    Called when ALL activities for this job+plot are completed + verified.
    Releases 10% deposit and adds post-shoot work gross.
    """
    settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        job=job,
        plot=plot,
    ).exclude(status='pending').first()

    if not settlement:
        return None

    # Already processed — skip
    if float(settlement.payable_amount) >= float(settlement.gross_amount) - 0.01 and float(settlement.gross_amount) > 0:
        return settlement

    current_gross    = calculate_gross_for_mukkadam(mukkadam, job, plot)
    old_gross        = settlement.gross_amount
    post_shoot_gross = current_gross - old_gross

    deposit_pct  = settlement.deposit_percent or Decimal('10')
    old_deposit  = (old_gross * deposit_pct / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)
    additional   = post_shoot_gross + old_deposit  # post-shoot (100%) + deposit released

    if settlement.status == 'paid':
        # Already paid — new remaining amount only
        if additional <= Decimal('0.01'):
            return settlement
        new_net    = additional
        new_status = 'calculated'
    else:
        new_net    = settlement.net_payable + additional
        new_status = 'calculated' if new_net > Decimal('0') else settlement.status

    # queryset update — bypasses signal
    MukkadamJobSettlement.objects.filter(pk=settlement.pk).update(
        gross_amount   = current_gross,
        payable_amount = current_gross,   # 100% — deposit released
        net_payable    = new_net.quantize(Decimal('0.01'), ROUND_HALF_UP),
        status         = new_status,
    )
    settlement.refresh_from_db()
    return settlement


@transaction.atomic
def reset_settlement_if_stale(mukkadam, job, plot):
    """Reset settlement to pending if shoot selection is no longer completed."""
    settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        job=job,
        plot=plot,
    ).exclude(status__in=['pending', 'paid']).first()

    if not settlement:
        return

    if not is_settlement_triggered(job, mukkadam, plot):
        MukkadamJobSettlement.objects.filter(pk=settlement.pk).update(
            status                   = 'pending',
            gross_amount             = Decimal('0'),
            payable_amount           = Decimal('0'),
            net_payable              = Decimal('0'),
            advance_deducted         = Decimal('0'),
            weekly_payments_deducted = Decimal('0'),
            credit_carried_forward   = Decimal('0'),
            deposit_carried_forward  = Decimal('0'),
            calculated_at            = None,
        )
        settlement.weekly_payments_applied.clear()


def process_all_triggered_settlements():
    """Daily task — find all shoot selections done, calculate settlements."""
    shoot_done = Allocation.objects.filter(
        work_status='completed',
        farmer_agreed=True,
        job_activity__activity__name__icontains='shoot selection',
    ).select_related('job_activity__job', 'job_activity__plot', 'mukkadam')

    results = []
    seen = set()

    for alloc in shoot_done:
        job      = alloc.job_activity.job
        mukkadam = alloc.mukkadam
        plot     = alloc.job_activity.plot
        key      = (job.job_id, mukkadam.mukkadam_id, getattr(plot, 'id', None))

        if key in seen:
            continue
        seen.add(key)

        if MukkadamJobSettlement.objects.filter(
            mukkadam=mukkadam, job=job, plot=plot,
            status__in=['paid', 'no_payment_needed'],
        ).exists():
            continue

        cluster    = job.clusters.first()
        settlement = create_or_update_settlement(mukkadam, job, plot, cluster)
        results.append(settlement)

        if is_all_activities_done(job, mukkadam, plot):
            update_settlement_on_all_done(mukkadam, job, plot, cluster)

    return results


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _get_activity_gross(allocation):
    if (allocation.payment_status == 'dispute'
            and not allocation.admin_override_area
            and not allocation.use_actual_for_settlement):
        return Decimal('0')
    if allocation.admin_override_area:
        area = allocation.admin_override_area
    elif allocation.use_actual_for_settlement and allocation.actual_area_done:
        area = allocation.actual_area_done
    else:
        area = allocation.allocated_area
    return (area * allocation.mukkadam_rate).quantize(Decimal('0.01'))


def build_week_ledger(mukkadam, assignment):
    """Build week-wise ledger — grouped by plot within each week."""
    weekly_payments = list(
        MukkadamWeeklyPayment.objects.filter(assignment=assignment)
        .order_by('payment_date')
        .values('id', 'payment_date', 'amount', 'crew_size_on_date', 'proof_s3_key')
    )

    weekly_proof_keys = [w['proof_s3_key'] for w in weekly_payments if w['proof_s3_key']]
    weekly_proof_map  = {}
    if weekly_proof_keys:
        urls = get_presigned_urls_batch(weekly_proof_keys)
        weekly_proof_map = dict(zip(weekly_proof_keys, urls))

    # Settlements now include plot
    settlements = list(
        MukkadamJobSettlement.objects.filter(assignment=assignment)
        .select_related('job', 'job__farmer', 'plot')
        .exclude(status='pending')
        .order_by('calculated_at')
    )

    settlement_activities = {}
    for s in settlements:
        key   = (s.job.job_id, getattr(s.plot, 'id', None))
        allocs = Allocation.objects.filter(
            job_activity__job=s.job,
            job_activity__plot=s.plot,
            mukkadam=mukkadam,
            work_status='completed',
        ).select_related('job_activity')
        settlement_activities[key] = list(allocs)

    # Pending work — jobs+plots with completed work but no settlement
    settled_keys = {(s.job.job_id, getattr(s.plot, 'id', None)) for s in settlements}
    pending_jobs = []

    all_allocs = Allocation.objects.filter(
        mukkadam=mukkadam,
        assignment=assignment,
        work_status='completed',
    ).select_related('job_activity__job', 'job_activity__plot', 'job_activity__activity')

    seen_keys = set()
    for alloc in all_allocs:
        job  = alloc.job_activity.job
        plot = alloc.job_activity.plot
        key  = (job.job_id, getattr(plot, 'id', None))
        if key in settled_keys or key in seen_keys:
            continue
        seen_keys.add(key)

        plot_allocs = [a for a in all_allocs if a.job_activity.job.job_id == job.job_id
                       and getattr(a.job_activity.plot, 'id', None) == getattr(plot, 'id', None)]
        gross = sum(float(_get_activity_gross(a)) for a in plot_allocs)

        pending_jobs.append({
            'farmer_name': job.farmer.farmer_name,
            'job_id':      str(job.job_id),
            'plot_name':   plot.name if plot else '—',
            'gross_so_far': gross,
            'note': 'Shoot selection pending — not yet payable',
            'activities': [
                {
                    'activity_name': a.job_activity.activity.name,
                    'area':   float(a.actual_area_done or a.allocated_area),
                    'rate':   float(a.mukkadam_rate),
                    'amount': float(_get_activity_gross(a)),
                }
                for a in plot_allocs
            ]
        })

    weekly_dates = [str(w['payment_date']) for w in weekly_payments]

    def get_week_bucket(date_str):
        if not date_str or not weekly_dates:
            return None
        ds = str(date_str)[:10]
        for wd in weekly_dates:
            if ds <= wd:
                return wd
        return weekly_dates[-1]

    events_by_week = {wd: [] for wd in weekly_dates}

    for s in settlements:
        farmer_name = s.job.farmer.farmer_name
        job_id      = str(s.job.job_id)
        plot_name   = s.plot.name if s.plot else '—'
        key         = (s.job.job_id, getattr(s.plot, 'id', None))
        allocs      = settlement_activities.get(key, [])

        if s.calculated_at:
            bucket = get_week_bucket(str(s.calculated_at.date()))
            if bucket and bucket in events_by_week:
                events_by_week[bucket].append({
                    'type':           'shoot_billing',
                    'farmer_name':    farmer_name,
                    'job_id':         job_id,
                    'plot_name':      plot_name,
                    'description':    f'Shoot Selection — {plot_name} — 90% of ₹{int(float(s.gross_amount)):,}',
                    'gross_at_event': float(s.gross_amount),
                    'payable':        float(s.payable_amount),
                    'deposit_held':   float((s.gross_amount * (s.deposit_percent or Decimal('10')) / 100).quantize(Decimal('0.01'))),
                    'deposit_released': 0,
                    'activities': [
                        {
                            'activity_name': a.job_activity.activity.name,
                            'area':   float(a.actual_area_done or a.allocated_area),
                            'rate':   float(a.mukkadam_rate),
                            'amount': float(_get_activity_gross(a)),
                        }
                        for a in allocs
                    ]
                })

        deposit_now = float((s.gross_amount * (s.deposit_percent or Decimal('10')) / 100).quantize(Decimal('0.01')))
        if s.status in ('calculated', 'paid', 'no_payment_needed') and float(s.payable_amount) >= float(s.gross_amount) - 0.01:
            last_alloc = Allocation.objects.filter(
                job_activity__job=s.job,
                job_activity__plot=s.plot,
                mukkadam=mukkadam,
                work_status='completed',
            ).order_by('-updated_at').first()

            if last_alloc and s.calculated_at:
                all_done_date = last_alloc.updated_at.date()
                if all_done_date > s.calculated_at.date():
                    bucket = get_week_bucket(str(all_done_date))
                    if bucket and bucket in events_by_week:
                        events_by_week[bucket].append({
                            'type':             'deposit_release',
                            'farmer_name':      farmer_name,
                            'job_id':           job_id,
                            'plot_name':        plot_name,
                            'description':      f'All activities done — {plot_name} — deposit released',
                            'gross_at_event':   0,
                            'payable':          deposit_now,
                            'deposit_held':     0,
                            'deposit_released': deposit_now,
                            'activities':       []
                        })

    advance         = float(assignment.advance_amount or 0)
    running_balance = -advance
    ledger          = []

    if advance > 0:
        ledger.append({
            'week_num':        0,
            'type':            'advance',
            'payment_date':    None,
            'weekly_paid':     advance,
            'weekly_proof_url': None,
            'billing_events':  [],
            'running_balance': running_balance,
            'payable_this_week': 0,
            'label':           'Advance Given',
        })

    for wi, w in enumerate(weekly_payments):
        wd                = str(w['payment_date'])
        weekly_amount     = float(w['amount'])
        events            = events_by_week.get(wd, [])
        payable_this_week = sum(e['payable'] for e in events)
        running_balance   = running_balance - weekly_amount + payable_this_week

        ledger.append({
            'week_num':        wi + 1,
            'type':            'week',
            'payment_date':    wd,
            'weekly_paid':     weekly_amount,
            'weekly_proof_url': weekly_proof_map.get(w['proof_s3_key']) if w['proof_s3_key'] else None,
            'billing_events':  events,
            'running_balance': round(running_balance, 2),
            'payable_this_week': round(payable_this_week, 2),
            'can_pay':         running_balance > 0.01,
        })

    total_gross        = sum(float(s.gross_amount) for s in settlements)
    total_deposit_held = sum(
        float((s.gross_amount * (s.deposit_percent or Decimal('10')) / 100).quantize(Decimal('0.01')))
        for s in settlements
        if float(s.payable_amount) < float(s.gross_amount)
    )
    total_weekly_paid  = sum(w['amount'] for w in weekly_payments)
    net_payable        = sum(
        float(s.net_payable) for s in settlements if s.status == 'calculated'
    )

    return {
        'week_ledger':  ledger,
        'pending_work': pending_jobs,
        'summary': {
            'total_gross':        round(total_gross, 2),
            'total_advance':      round(advance, 2),
            'total_weekly_paid':  float(total_weekly_paid),
            'total_deposit_held': round(total_deposit_held, 2),
            'net_payable':        round(net_payable, 2),
            'running_balance':    round(running_balance, 2),
        }
    }