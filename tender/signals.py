import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import models
from django.db.models import Sum

from .models import (
    Allocation, AllocationChangeLogTender, FarmerPayment, MukkadamPayment,
    PaymentChangeLog, JobActivity, MukkadamAvailability, Job
)

logger = logging.getLogger(__name__)


# ============================================================================
# ALLOCATION SIGNALS — audit log + availability tracking
# ============================================================================

@receiver(pre_save, sender=Allocation)
def track_allocation_changes(sender, instance, **kwargs):
    """Track field changes before saving."""
    if instance.pk:
        try:
            old_instance = Allocation.objects.get(pk=instance.pk)
            changed_fields = []
            for field in ['allocated_area', 'allocated_workers', 'allocated_date',
                          'farmer_rate', 'mukkadam_rate', 'status']:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    changed_fields.append({
                        'field': field,
                        'old': str(old_value),
                        'new': str(new_value)
                    })
            instance._changed_fields = changed_fields
            instance._old_instance   = old_instance
        except Allocation.DoesNotExist:
            instance._changed_fields = []
            instance._old_instance   = None


@receiver(post_save, sender=Allocation)
def log_allocation_changes(sender, instance, created, **kwargs):
    """Create audit log after allocation is saved."""
    from .serializers import AllocationSerializer
    if created:
        AllocationChangeLogTender.objects.create(
            allocation=instance,
            change_type='created',
            changed_by=instance.created_by,
            allocation_snapshot=AllocationSerializer(instance).data
        )
    else:
        if hasattr(instance, '_changed_fields') and instance._changed_fields:
            for change in instance._changed_fields:
                AllocationChangeLogTender.objects.create(
                    allocation=instance,
                    change_type='updated',
                    field_changed=change['field'],
                    old_value=change['old'],
                    new_value=change['new'],
                    changed_by=instance.created_by,
                    allocation_snapshot=AllocationSerializer(instance).data
                )


@receiver(post_delete, sender=Allocation)
def log_allocation_deletion(sender, instance, **kwargs):
    from .serializers import AllocationSerializer
    AllocationChangeLogTender.objects.create(
        allocation=None,
        change_type='deleted',
        change_reason=f'Allocation {instance.id} deleted',
        allocation_snapshot=AllocationSerializer(instance).data
    )


@receiver(post_save, sender=Allocation)
def update_job_activity_on_allocation(sender, instance, created, **kwargs):
    if created:
        job_activity = instance.job_activity
        JobActivity.objects.filter(pk=job_activity.pk).update(
            allocated_area=models.F('allocated_area') + instance.allocated_area
        )


@receiver(post_save, sender=Allocation)
def update_mukkadam_availability(sender, instance, created, **kwargs):
    if created:
        availability, _ = MukkadamAvailability.objects.get_or_create(
            mukkadam=instance.mukkadam,
            date=instance.allocated_date,
            defaults={
                'available_crew_size': instance.mukkadam.crew_size,
                'is_available': True,
                'allocated_workers': 0,
            }
        )
        MukkadamAvailability.objects.filter(pk=availability.pk).update(
            allocated_workers=models.F('allocated_workers') + instance.allocated_workers
        )


@receiver(post_delete, sender=Allocation)
def restore_capacity_on_deletion(sender, instance, **kwargs):
    JobActivity.objects.filter(pk=instance.job_activity.pk).update(
        allocated_area=models.F('allocated_area') - instance.allocated_area
    )
    try:
        MukkadamAvailability.objects.filter(
            mukkadam=instance.mukkadam,
            date=instance.allocated_date
        ).update(
            allocated_workers=models.F('allocated_workers') - instance.allocated_workers
        )
    except Exception:
        pass


# ============================================================================
# SETTLEMENT TRIGGER
#
# RULES:
#   1. Shoot selection completed + farmer verified  → calculate settlement (first time only)
#   2. Any other activity verified after shoot done → update gross only, keep all deductions
#   3. All activities done                          → release deposit + add post-shoot work
#   4. status='paid'                               → NEVER recalculate deductions
#   5. farmer_agreed reset to False                → reset stale settlement
#
# REMOVED (were wrong):
#   ✗ trigger_settlement_on_shoot_selection   — date based, not completion based
#   ✗ recalculate_settlement_on_verification  — fired on ANY activity, no shoot check
#   ✗ trigger_settlement_after_verification   — duplicate + date based
# ============================================================================

@receiver(pre_save, sender=Allocation)
def track_farmer_agreed_change(sender, instance, **kwargs):
    """Track farmer_agreed and payment_status changes for settlement trigger."""
    if not instance.pk:
        instance._farmer_agreed_was     = None
        instance._payment_status_was    = None
        instance._farmer_agreed_changed = False
        return
    try:
        old = Allocation.objects.get(pk=instance.pk)
        instance._farmer_agreed_was     = old.farmer_agreed
        instance._payment_status_was    = old.payment_status
        instance._farmer_agreed_changed = (
            (old.farmer_agreed != instance.farmer_agreed) or
            (old.payment_status != instance.payment_status)
        )
    except Allocation.DoesNotExist:
        instance._farmer_agreed_was     = None
        instance._payment_status_was    = None
        instance._farmer_agreed_changed = False


# Prevent re-entrant signal calls
_settlement_processing = set()


@receiver(post_save, sender=Allocation)
def handle_settlement_on_farmer_verification(sender, instance, **kwargs):
    """Single correct settlement trigger — see rules above."""

    if not getattr(instance, '_farmer_agreed_changed', False):
        return  # Nothing changed — skip

    # Re-entrancy guard — prevents infinite loop if settlement.save() triggers this again
    key = str(instance.pk)
    if key in _settlement_processing:
        return
    _settlement_processing.add(key)

    try:
        _run_settlement_logic(instance)
    except Exception as e:
        logger.error(f"[settlement signal] Unhandled error for allocation {instance.pk}: {e}", exc_info=True)
    finally:
        _settlement_processing.discard(key)


def _run_settlement_logic(instance):
    from .ervices.settlement import (
        is_settlement_triggered,
        is_all_activities_done,
        create_or_update_settlement,
        update_settlement_on_all_done,
        reset_settlement_if_stale,
    )
    from .models import MukkadamJobSettlement

    job      = instance.job_activity.job
    mukkadam = instance.mukkadam
    plot     = instance.job_activity.plot    # ← per-plot settlement
    cluster  = job.clusters.first()

    # Activity name
    activity_name = (instance.job_activity.activity.name or '').lower()
    is_shoot = 'shoot selection' in activity_name or 'विरळणी' in activity_name

    is_now_verified = (instance.farmer_agreed is True) or (instance.payment_status == 'done')
    was_verified    = (instance._farmer_agreed_was is True) or (instance._payment_status_was == 'done')

    # ── CASE A: Farmer just verified ──────────────────────────────────
    if is_now_verified:

        existing = MukkadamJobSettlement.objects.filter(
            mukkadam=mukkadam,
            job=job,
            plot=plot,                       # ← filter by plot
        ).first()
        existing_status = existing.status if existing else None

        if existing_status == 'paid':
            logger.info(f"[settlement] Job {job.job_id} plot {getattr(plot,'id','?')} already paid — checking all_done only")

        elif is_shoot and existing_status not in ('calculated', 'no_payment_needed'):
            try:
                create_or_update_settlement(mukkadam, job, plot, cluster)
                logger.info(f"[settlement] Shoot billing: mukkadam={mukkadam.mukkadam_name} job={job.job_id} plot={getattr(plot,'id','?')}")
            except Exception as e:
                logger.error(f"[settlement signal] Shoot billing error: {e}", exc_info=True)

        elif not is_shoot and existing_status in ('calculated', 'no_payment_needed'):
            try:
                create_or_update_settlement(mukkadam, job, plot, cluster)
                logger.info(f"[settlement] Gross updated: job={job.job_id} plot={getattr(plot,'id','?')}")
            except Exception as e:
                logger.error(f"[settlement signal] Gross update error: {e}", exc_info=True)

        if is_all_activities_done(job, mukkadam, plot):
            try:
                update_settlement_on_all_done(mukkadam, job, plot, cluster)
                logger.info(f"[settlement] All done — deposit released: job={job.job_id} plot={getattr(plot,'id','?')}")
            except Exception as e:
                logger.error(f"[settlement signal] Deposit release error: {e}", exc_info=True)

    # ── CASE B: Verification reset ─────────────────────────────────────
    elif was_verified and not is_now_verified:
        try:
            reset_settlement_if_stale(mukkadam, job, plot)
            logger.info(f"[settlement] Stale settlement reset: job={job.job_id} plot={getattr(plot,'id','?')}")
        except Exception as e:
            logger.error(f"[settlement signal] Reset error: {e}", exc_info=True)


# ============================================================================
# PAYMENT SIGNALS
# ============================================================================

@receiver(pre_save, sender=FarmerPayment)
def track_farmer_payment_changes(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_instance = FarmerPayment.objects.get(pk=instance.pk)
        except FarmerPayment.DoesNotExist:
            pass


@receiver(post_save, sender=FarmerPayment)
def log_farmer_payment_changes(sender, instance, created, **kwargs):
    from .serializers import FarmerPaymentSerializer
    if created:
        PaymentChangeLog.objects.create(
            payment_type='farmer',
            farmer_payment=instance,
            change_type='created',
            changed_by=instance.created_by,
            payment_snapshot=FarmerPaymentSerializer(instance).data
        )
    elif hasattr(instance, '_old_instance'):
        old = instance._old_instance
        for field in ['amount', 'mode', 'paid_at', 'paid_status']:
            if getattr(old, field) != getattr(instance, field):
                PaymentChangeLog.objects.create(
                    payment_type='farmer',
                    farmer_payment=instance,
                    change_type='updated',
                    field_changed=field,
                    old_value=str(getattr(old, field)),
                    new_value=str(getattr(instance, field)),
                    changed_by=instance.created_by,
                    payment_snapshot=FarmerPaymentSerializer(instance).data
                )


# signals.py — find update_booking_on_payment, fix the arithmetic

from decimal import Decimal

# @receiver(post_save, sender=FarmerPayment)
# def update_booking_on_payment(sender, instance, **kwargs):
#     booking = instance.booking
    
#     # Get total paid — keep as Decimal
#     total_paid = booking.payments.aggregate(
#         total=Sum('amount')
#     )['total'] or Decimal('0')

#     # Cast everything to Decimal before arithmetic
#     total_amount = Decimal(str(booking.total_amount or 0))
    
#     booking.advance_paid = total_paid
#     booking.balance      = total_amount - total_paid   # both Decimal now

#     if total_paid <= 0:
#         booking.status = 'UNPAID'
#     elif total_paid >= total_amount:
#         booking.status = 'PAID'
#     else:
#         booking.status = 'PARTIALLY_PAID'

#     booking.save(update_fields=['advance_paid', 'balance', 'status'])

@receiver(pre_save, sender=MukkadamPayment)
def track_mukkadam_payment_changes(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_instance = MukkadamPayment.objects.get(pk=instance.pk)
        except MukkadamPayment.DoesNotExist:
            pass


@receiver(post_save, sender=MukkadamPayment)
def log_mukkadam_payment_changes(sender, instance, created, **kwargs):
    from .serializers import MukkadamPaymentSerializer
    if created:
        PaymentChangeLog.objects.create(
            payment_type='mukkadam',
            mukkadam_payment=instance,
            change_type='created',
            changed_by=instance.created_by,
            payment_snapshot=MukkadamPaymentSerializer(instance).data
        )
    elif hasattr(instance, '_old_instance'):
        old = instance._old_instance
        for field in ['amount', 'mode', 'paid_at']:
            if getattr(old, field) != getattr(instance, field):
                PaymentChangeLog.objects.create(
                    payment_type='mukkadam',
                    mukkadam_payment=instance,
                    change_type='updated',
                    field_changed=field,
                    old_value=str(getattr(old, field)),
                    new_value=str(getattr(instance, field)),
                    changed_by=instance.created_by,
                    payment_snapshot=MukkadamPaymentSerializer(instance).data
                )


# ============================================================================
# JOB ACTIVITY SIGNALS
# ============================================================================

@receiver(post_save, sender=JobActivity)
def update_job_total_on_activity_change(sender, instance, **kwargs):
    from django.db.models import Sum
    total = JobActivity.objects.filter(job=instance.job).aggregate(
        total=Sum('total_price')
    )['total'] or 0
    Job.objects.filter(pk=instance.job.pk).update(total_activities_amount=total)


# ============================================================================
# AVAILABILITY SIGNALS
@receiver(pre_save, sender=MukkadamAvailability)
def validate_availability_capacity(sender, instance, **kwargs):
    """Ensure is_available is consistent with crew vs allocated."""
    if instance.allocated_workers > instance.available_crew_size:
        instance.is_available = False
    # else: leave is_available as-is (don't force True, UI/logic may set holiday)


# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import JobActivity
from .planing import invalidate_planning_cache


def _get_cluster_ids(instance: JobActivity):
    return list(instance.job.clusters.values_list("id", flat=True))


@receiver(post_save, sender=JobActivity)
def on_job_activity_save(sender, instance, **kwargs):
    for cid in _get_cluster_ids(instance):
        invalidate_planning_cache(cid)


@receiver(post_delete, sender=JobActivity)
def on_job_activity_delete(sender, instance, **kwargs):
    for cid in _get_cluster_ids(instance):
        invalidate_planning_cache(cid)