from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
import json
from .models import (
    Allocation, AllocationChangeLogTender, FarmerPayment, MukkadamPayment,
    PaymentChangeLog, JobActivity, MukkadamAvailability
)
from .models import (
    Allocation, AllocationChangeLogTender, FarmerPayment, MukkadamPayment,
    PaymentChangeLog, JobActivity, MukkadamAvailability, Job  # ← add Job
)

# ============================================================================
# ALLOCATION SIGNALS
# ============================================================================

@receiver(pre_save, sender=Allocation)
def track_allocation_changes(sender, instance, **kwargs):
    """
    Track changes to allocations before saving
    """
    if instance.pk:  # Only for updates
        try:
            old_instance = Allocation.objects.get(pk=instance.pk)
            
            # Compare fields
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
            
            # Store changes for post_save
            instance._changed_fields = changed_fields
            instance._old_instance = old_instance
            
        except Allocation.DoesNotExist:
            pass


@receiver(post_save, sender=Allocation)
def log_allocation_changes(sender, instance, created, **kwargs):
    """
    Create audit log after allocation is saved
    """
    from .serializers import AllocationSerializer
    
    if created:
        # New allocation created
        AllocationChangeLogTender.objects.create(
            allocation=instance,
            change_type='created',
            changed_by=instance.created_by,
            allocation_snapshot=AllocationSerializer(instance).data
        )
    else:
        # Allocation updated
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
    """
    Log when allocation is deleted
    """
    from .serializers import AllocationSerializer
    
    AllocationChangeLogTender.objects.create(
        allocation=None,  # Allocation is deleted
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
        ).update(allocated_workers=models.F('allocated_workers') - instance.allocated_workers)
    except Exception:
        pass

# ============================================================================
# PAYMENT SIGNALS
# ============================================================================

@receiver(pre_save, sender=FarmerPayment)
def track_farmer_payment_changes(sender, instance, **kwargs):
    """Track farmer payment changes"""
    if instance.pk:
        try:
            old_instance = FarmerPayment.objects.get(pk=instance.pk)
            instance._old_instance = old_instance
        except FarmerPayment.DoesNotExist:
            pass


@receiver(post_save, sender=FarmerPayment)
def log_farmer_payment_changes(sender, instance, created, **kwargs):
    """Log farmer payment changes"""
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
        changed = []
        
        for field in ['amount', 'mode', 'paid_at', 'paid_status']:
            old_val = getattr(old, field)
            new_val = getattr(instance, field)
            if old_val != new_val:
                PaymentChangeLog.objects.create(
                    payment_type='farmer',
                    farmer_payment=instance,
                    change_type='updated',
                    field_changed=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    changed_by=instance.created_by,
                    payment_snapshot=FarmerPaymentSerializer(instance).data
                )

from django.db import models

@receiver(post_save, sender=FarmerPayment)
def update_booking_on_payment(sender, instance, created, **kwargs):
    """Update booking balance when payment is added/updated"""
    booking = instance.booking
    
    # Recalculate advance_paid from all payments
    total_paid = booking.payments.filter(paid_status=True).aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    booking.advance_paid = total_paid
    booking.balance = booking.total_amount - total_paid
    
    # Update status
    if booking.balance <= 0:
        booking.status = 'PAID'
    elif booking.advance_paid > 0:
        booking.status = 'PARTIALLY_PAID'
    else:
        booking.status = 'UNPAID'
    
    booking.save()


@receiver(pre_save, sender=MukkadamPayment)
def track_mukkadam_payment_changes(sender, instance, **kwargs):
    """Track mukkadam payment changes"""
    if instance.pk:
        try:
            old_instance = MukkadamPayment.objects.get(pk=instance.pk)
            instance._old_instance = old_instance
        except MukkadamPayment.DoesNotExist:
            pass


@receiver(post_save, sender=MukkadamPayment)
def log_mukkadam_payment_changes(sender, instance, created, **kwargs):
    """Log mukkadam payment changes"""
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
            old_val = getattr(old, field)
            new_val = getattr(instance, field)
            if old_val != new_val:
                PaymentChangeLog.objects.create(
                    payment_type='mukkadam',
                    mukkadam_payment=instance,
                    change_type='updated',
                    field_changed=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
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
# ============================================================================

@receiver(post_save, sender=MukkadamAvailability)
def validate_availability_capacity(sender, instance, **kwargs):
    """
    Ensure allocated_workers doesn't exceed available_crew_size
    """
    if instance.allocated_workers > instance.available_crew_size:
        # This should be caught by validation, but as a safety net
        instance.is_available = False
        instance.save(update_fields=['is_available'])



# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal


# ── 1. Auto-calculate settlement when shoot selection activity is saved ──
@receiver(post_save, sender='tender.JobActivity')
def trigger_settlement_on_shoot_selection(sender, instance, **kwargs):
    """
    When a JobActivity with 'shoot selection' is saved and its scheduled_date
    has passed, auto-calculate settlement for all mukkadams on that job.
    """
    if 'shoot selection' not in instance.activity.name.lower():
        return

    today = timezone.localdate()
    if not instance.scheduled_date or instance.scheduled_date > today:
        return

    from .ervices.settlement import create_or_update_settlement
    from .models import Mukkadam

    job = instance.job
    cluster = job.clusters.first()

    mukkadams = Mukkadam.objects.filter(
        allocations__job_activity__job=job
    ).distinct()

    for mukkadam in mukkadams:
        try:
            create_or_update_settlement(mukkadam, job, cluster)
        except Exception as e:
            print(f"[settlement signal] Error for {mukkadam.mukkadam_name}: {e}")


@receiver(pre_save, sender=Allocation)
def track_farmer_agreed_change(sender, instance, **kwargs):
    if not instance.pk:
        instance._farmer_agreed_changed = False
        return
    try:
        old = Allocation.objects.get(pk=instance.pk)
        instance._farmer_agreed_changed = (old.farmer_agreed != instance.farmer_agreed)
    except Allocation.DoesNotExist:
        instance._farmer_agreed_changed = False


@receiver(post_save, sender=Allocation)
def recalculate_settlement_on_verification(sender, instance, **kwargs):
    if not getattr(instance, '_farmer_agreed_changed', False):
        return
    if instance.farmer_agreed is None:
        return

    from .ervices.settlement import create_or_update_settlement
    from .models import MukkadamJobSettlement

    job = instance.job_activity.job
    mukkadam = instance.mukkadam
    cluster = instance.cluster or job.clusters.first()

    if not MukkadamJobSettlement.objects.filter(mukkadam=mukkadam, job=job).exists():
        return

    try:
        create_or_update_settlement(mukkadam, job, cluster)
    except Exception as e:
        print(f"[settlement signal] Recalc error: {e}")
# ── 3. Auto-create weekly payment record on correct weekday ──
@receiver(post_save, sender='tender.Allocation')
def generate_weekly_payment_on_allocation(sender, instance, created, **kwargs):
    """
    When a new allocation is saved, check if today is the weekly payment day
    for that mukkadam's assignment. If yes, create the weekly payment record.
    """
    if not created:
        return

    from .models import ClusterMukkadamAssignment, MukkadamWeeklyPayment
    from datetime import date

    today = date.today()
    cluster = instance.cluster or instance.job_activity.plot.clusters.first() if instance.job_activity.plot else None

    if not cluster:
        return

    try:
        assignment = ClusterMukkadamAssignment.objects.get(
            mukkadam=instance.mukkadam,
            cluster=cluster,
            is_active=True,
            weekly_payment_day__isnull=False,
        )
    except ClusterMukkadamAssignment.DoesNotExist:
        return

    # Only create if today is the payment weekday
    if today.weekday() != assignment.weekly_payment_day:
        return

    # Already exists for today?
    if MukkadamWeeklyPayment.objects.filter(
        assignment=assignment,
        payment_date=today,
    ).exists():
        return

    # Has work this week?
    from datetime import timedelta
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    has_work = Allocation.objects.filter(
        mukkadam=instance.mukkadam,
        job_activity__plot__clusters=cluster,
        allocated_date__gte=week_start,
        allocated_date__lte=week_end,
    ).exists()

    if not has_work:
        return

    amount = assignment.get_weekly_payment_amount()

    try:
        MukkadamWeeklyPayment.objects.create(
            assignment=assignment,
            payment_date=today,
            crew_size_on_date=instance.mukkadam.crew_size or 0,
            amount=amount,
            is_auto_generated=True,
            notes=f"Auto weekly | Week {week_start} to {week_end}",
        )
        # Update running total
        assignment.total_weekly_payments = (
            assignment.total_weekly_payments or Decimal('0')
        ) + amount
        assignment.save(update_fields=['total_weekly_payments', 'updated_at'])
    except Exception as e:
        print(f"[weekly payment signal] Error: {e}")



@receiver(post_save, sender=Allocation)
def trigger_settlement_after_verification(sender, instance, **kwargs):
    if not getattr(instance, '_farmer_agreed_changed', False):
        return
    if instance.farmer_agreed is None:
        return

    from .ervices.settlement import create_or_update_settlement

    job = instance.job_activity.job
    mukkadam = instance.mukkadam
    cluster = instance.cluster or job.clusters.first()

    # Check if shoot selection date has passed
    from django.utils import timezone
    today = timezone.localdate()
    
    shoot_selection = job.activities.filter(
        activity__name__icontains='shoot selection'
    ).first()

    if not shoot_selection or not shoot_selection.scheduled_date:
        return
    
    if shoot_selection.scheduled_date > today:
        return  # not yet time

    create_or_update_settlement(mukkadam, job, cluster)