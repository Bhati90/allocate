from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
import json
from .models import (
    Allocation, AllocationChangeLogTender, FarmerPayment, MukkadamPayment,
    PaymentChangeLog, JobActivity, MukkadamAvailability
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
    """
    Update job activity allocated_area when allocation is created/updated
    """
    if created:
        # Add to allocated area
        job_activity = instance.job_activity
        job_activity.allocated_area += instance.allocated_area
        job_activity.save()


@receiver(post_save, sender=Allocation)
def update_mukkadam_availability(sender, instance, created, **kwargs):
    """
    Update mukkadam availability when allocation is created
    """
    if created:
        availability, _ = MukkadamAvailability.objects.get_or_create(
            mukkadam=instance.mukkadam,
            date=instance.allocated_date,
            defaults={
                'available_crew_size': instance.mukkadam.crew_size,
                'is_available': True,
                'allocated_workers': 0
            }
        )
        
        availability.allocated_workers += instance.allocated_workers
        availability.save()


@receiver(post_delete, sender=Allocation)
def restore_capacity_on_deletion(sender, instance, **kwargs):
    """
    Restore capacity when allocation is deleted
    """
    # Restore job activity area
    job_activity = instance.job_activity
    job_activity.allocated_area -= instance.allocated_area
    job_activity.save()
    
    # Restore mukkadam availability
    try:
        availability = MukkadamAvailability.objects.get(
            mukkadam=instance.mukkadam,
            date=instance.allocated_date
        )
        availability.allocated_workers -= instance.allocated_workers
        availability.save()
    except MukkadamAvailability.DoesNotExist:
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
    """Update job total_activities_amount when activity prices change"""
    job = instance.job
    
    # Sum all activity totals
    total = job.activities.aggregate(
        total=models.Sum('total_price')
    )['total'] or 0
    
    job.total_activities_amount = total
    job.save(update_fields=['total_activities_amount'])


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