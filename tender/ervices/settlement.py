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


def calculate_settlement_for_mukkadam(mukkadam, job, cluster=None) -> dict:
    """
    Calculate what we owe (or don't owe) a mukkadam for a specific job.
    Does NOT save — returns a dict for preview or saving.
    """
    today = timezone.localdate()

    # ── 1. Gross: sum of all completed/scheduled allocations for this mukkadam on this job
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam,
        job_activity__job=job,
        job_activity__scheduled_date__lte=today,  # date passed
    ).select_related('job_activity__activity')

    gross = sum(a.mukkadam_amount for a in allocations)
    deposit_held = (gross * Decimal('10') / Decimal('100')).quantize(Decimal('0.01'))
    payable_this_job = gross - deposit_held  # 90%

    # ── 2. Deposit carried forward from previous job (the 10% held last time)
    prev_settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        status__in=['paid', 'no_payment_needed'],
    ).order_by('-created_at').first()

    deposit_carried = Decimal('0')
    if prev_settlement:
        # Previous job's 10% is now released
        deposit_carried = (
            prev_settlement.gross_amount * Decimal('10') / Decimal('100')
        ).quantize(Decimal('0.01'))

    # ── 3. Advance — only deduct if not yet used in any previous settlement
    advance_used_before = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
        advance_deducted__gt=0
    ).exists()

    advance_to_deduct = Decimal('0')
    if not advance_used_before:
        # Find advance from cluster assignment
        assignment = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam,
            cluster=cluster,
            is_active=True
        ).first()
        if assignment:
            advance_to_deduct = assignment.advance_amount

    # ── 4. Weekly payments — only ones not already applied to a previous settlement
    already_applied_ids = MukkadamWeeklyPayment.objects.filter(
        settlements__mukkadam=mukkadam
    ).values_list('id', flat=True)

    unapplied_weekly = MukkadamWeeklyPayment.objects.filter(
        assignment__mukkadam=mukkadam,
        payment_date__lte=today,
        is_auto_generated=True,
    ).exclude(id__in=already_applied_ids)

    weekly_total = sum(w.amount for w in unapplied_weekly)

    # ── 5. Net
    net_payable = (
        payable_this_job
        + deposit_carried
        - advance_to_deduct
        - weekly_total
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
        'weekly_payments_deducted': weekly_total,
        'unapplied_weekly_ids': list(unapplied_weekly.values_list('id', flat=True)),
        'net_payable': net_payable,
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