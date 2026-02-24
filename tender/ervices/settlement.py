# services/settlement.py

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from tender.models import (
    Job, Allocation, MukkadamJobSettlement,
    ClusterMukkadamAssignment, MukkadamWeeklyPayment, ActivityCatalog
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

from django.db.models import Sum
from tender.models import MukkadamMiscCost
def calculate_settlement_for_mukkadam(mukkadam, job, cluster=None) -> dict:
    today = timezone.localdate()

    # ── FIXED: Don't filter by date — include ALL allocations for this job ──
    # Settlement should include everything allocated, not just past dates
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam,
        job_activity__job=job,
    ).select_related('job_activity__activity')

    gross = Decimal('0')
    for a in allocations:
        if a.use_actual_for_settlement and a.actual_area_done is not None:
            effective_area = Decimal(str(a.actual_area_done))
        else:
            effective_area = Decimal(str(a.allocated_area or 0))
        rate = Decimal(str(a.mukkadam_rate or 0))
        gross += (effective_area * rate).quantize(Decimal('0.01'))

    deposit_held = (gross * Decimal('0.10')).quantize(Decimal('0.01'))
    payable_this_job = gross - deposit_held  # 90%

    # ── Previous job deposit carried forward ──
    prev_settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        status__in=['paid', 'no_payment_needed'],
    ).exclude(job=job).order_by('-created_at').first()

    deposit_carried = Decimal('0')
    if prev_settlement:
        deposit_carried = (
            prev_settlement.gross_amount * Decimal('0.10')
        ).quantize(Decimal('0.01'))

    # ── FIXED: Advance deduction ──
    # Check if advance was used in any OTHER job's settlement
    advance_used_before = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        advance_deducted__gt=0,
    ).exclude(job=job).exists()  # ← exclude current job

    advance_to_deduct = Decimal('0')
    if not advance_used_before:
        # ── FIXED: Try to find assignment even if cluster is None ──
        assignment_qs = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam,
            is_active=True,
        )
        if cluster:
            assignment_qs = assignment_qs.filter(cluster=cluster)

        assignment = assignment_qs.first()
        if assignment and assignment.advance_amount:
            advance_to_deduct = Decimal(str(assignment.advance_amount))

    # ── Weekly payments not yet applied to any settlement ──
    already_applied_ids = MukkadamWeeklyPayment.objects.filter(
        settlements__isnull=False
    ).exclude(
        settlements__job=job  # allow re-applying to same job if recalculating
    ).values_list('id', flat=True)

    unapplied_weekly = MukkadamWeeklyPayment.objects.filter(
        assignment__mukkadam=mukkadam,
        payment_date__lte=today,
    ).exclude(id__in=already_applied_ids)

    weekly_total = sum(
        Decimal(str(w.amount)) for w in unapplied_weekly
    )

    # ── Misc costs ──
    from django.db.models import Sum as DSum
    misc_total = MukkadamMiscCost.objects.filter(
        mukkadam=mukkadam,
        job=job,
    ).aggregate(total=DSum('amount'))['total'] or Decimal('0')
    misc_total = Decimal(str(misc_total))
    credit_carried = Decimal('0')
    prev_negative = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        net_payable__lt=0,
        status__in=['paid', 'no_payment_needed'],
    ).exclude(job=job).aggregate(
        total=Sum('net_payable')
    )['total'] or Decimal('0')
    
    credit_carried = abs(prev_negative)  # positive number representing credit

    # ── Net payable ──
    
    net_payable = (
        payable_this_job
        + deposit_carried
        - advance_to_deduct
        
        - weekly_total
        - misc_total
        - credit_carried        # ← deduct credit from previous jobs
    ).quantize(Decimal('0.01'))

    

    return {
        'mukkadam': mukkadam,
        'job': job,
        'cluster': cluster,
        'allocations': allocations,
        'gross_amount': gross,
        'deposit_held': deposit_held,
        'payable_this_job': payable_this_job,
        'deposit_carried_forward': deposit_carried,
        'advance_deducted': advance_to_deduct,
        'credit_carried_forward': credit_carried,
        'net_payable': net_payable,
        'weekly_payments_deducted': weekly_total,
        'unapplied_weekly_ids': list(unapplied_weekly.values_list('id', flat=True)),
        'net_payable': net_payable,
        'misc_total': misc_total,
    }

@transaction.atomic
def create_or_update_settlement(mukkadam, job, cluster=None) -> MukkadamJobSettlement:
    """
    Calculate and save/update settlement for a mukkadam+job.
    Safe to call multiple times — updates if already exists.
    """
    data = calculate_settlement_for_mukkadam(mukkadam, job, cluster)

    settlement, _ = MukkadamJobSettlement.objects.update_or_create(
        mukkadam=mukkadam,
        job=job,
        defaults={
            'cluster': cluster,
            'gross_amount': data['gross_amount'],
            'payable_amount': data['payable_this_job'],
            'deposit_carried_forward': data['deposit_carried_forward'],
            'credit_carried_forward': data['credit_carried_forward'],
            'advance_deducted': data['advance_deducted'],
            'weekly_payments_deducted': data['weekly_payments_deducted'],
            'net_payable': data['net_payable'],
            'status': 'no_payment_needed' if data['net_payable'] <= 0 else 'calculated',
            'calculated_at': timezone.now(),
        }
    )

    # Link which weekly payments were consumed
    settlement.weekly_payments_applied.set(data['unapplied_weekly_ids'])

    return settlement

def process_all_completed_settlements():
    """
    Treat ALL allocations whose allocated_date <= today as completed.
    No shoot selection date check. Settle everything done so far.
    """
    from tender.models import Mukkadam

    today = timezone.localdate()
    results = []
    summary = []

    # All jobs that have at least one allocation in the past
    jobs_with_past_allocs = Job.objects.filter(
        activities__allocations__allocated_date__lte=today
    ).distinct()

    for job in jobs_with_past_allocs:
        mukkadams_on_job = Mukkadam.objects.filter(
            allocations__job_activity__job=job,
            allocations__allocated_date__lte=today,
        ).distinct()

        cluster = job.clusters.first()

        for mukkadam in mukkadams_on_job:
            data = calculate_settlement_for_mukkadam(mukkadam, job, cluster)

            if data['gross_amount'] <= 0:
                continue

            settlement = create_or_update_settlement(mukkadam, job, cluster)
            results.append(settlement)

            summary.append({
                'type': 'mukkadam',
                'name': mukkadam.mukkadam_name,
                'job_id': job.job_id,
                'farmer': job.farmer.farmer_name if hasattr(job, 'farmer') else '—',
                'gross': data['gross_amount'],
                'weekly_deducted': data['weekly_payments_deducted'],
                'advance_deducted': data['advance_deducted'],
                'net_payable': data['net_payable'],
                'status': 'PENDING' if data['net_payable'] > 0 else 'CLEARED',
            })

        # Farmer billing summary
        from .farmerbill import get_farmer_billing_for_job
        farmer_data = get_farmer_billing_for_job(job.job_id)
        if farmer_data:
            summary.append({
                'type': 'farmer',
                'name': farmer_data['farmer_name'],
                'job_id': job.job_id,
                'farmer': farmer_data['farmer_name'],
                'billed_so_far': farmer_data['summary']['total_billable_so_far'],
                'total_paid': farmer_data['summary']['total_paid'],
                'balance_due': farmer_data['summary']['balance_due'],
                'status': 'PENDING' if farmer_data['summary']['balance_due'] > 0 else 'CLEARED',
            })

    return results, summary
def process_all_triggered_settlements():
    """
    Run this daily (management command / celery).
    Finds all jobs where shoot selection date passed and settlement not yet calculated.
    """
    from tender.models import Job, Mukkadam

    today = timezone.localdate()

    # Jobs with shoot selection date passed
    triggered_jobs = Job.objects.filter(
        activities__activity__name__icontains='shoot selection',
        activities__scheduled_date__lte=today,
    ).distinct()

    results = []
    for job in triggered_jobs:
        # Find all mukkadams who worked on this job
        mukkadams_on_job = Mukkadam.objects.filter(
            allocations__job_activity__job=job
        ).distinct()

        for mukkadam in mukkadams_on_job:
            # Skip if already settled
            if MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, job=job,
                status__in=['paid', 'no_payment_needed', 'payment_raised']
            ).exists():
                continue

            cluster = job.clusters.first()
            settlement = create_or_update_settlement(mukkadam, job, cluster)
            results.append(settlement)

    return results