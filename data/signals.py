from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Allocation, PaymentRequest, TransportPaymentRequest, ActivityLog

@receiver(post_save, sender=Allocation)
def log_allocation_activity(sender, instance, created, **kwargs):
    """Log allocation creation or update"""
    if created:
        ActivityLog.objects.create(
            activity_type='allocation_created',
            description=f"Allocated {instance.allocated_area} acres to Mukkadam #{instance.mukkadam_id}",
            allocation=instance,
            job_id=instance.job_activity.job_id,
            mukkadam_id=instance.mukkadam_id,
            transport_provider_id=instance.transport_provider_id,
            amount=instance.total_cost,
            performed_by=instance.allocated_by,
            metadata={
                'activity_name': instance.job_activity.activity_name,
                'work_date': str(instance.work_date),
                'crew_size': instance.crew_size,
                'mukkadam_price': float(instance.mukkadam_price),
                'transport_price': float(instance.transport_price or 0),
                'transport_type': instance.transport_type,
            }
        )
    else:
        ActivityLog.objects.create(
            activity_type='allocation_updated',
            description=f"Updated allocation for Mukkadam #{instance.mukkadam_id}",
            allocation=instance,
            job_id=instance.job_activity.job_id,
            mukkadam_id=instance.mukkadam_id,
            transport_provider_id=instance.transport_provider_id,
            amount=instance.total_cost,
            performed_by=instance.allocated_by,
            metadata={
                'activity_name': instance.job_activity.activity_name,
                'work_date': str(instance.work_date),
            }
        )

@receiver(post_delete, sender=Allocation)
def log_allocation_deletion(sender, instance, **kwargs):
    """Log when allocation is deleted (reallocation)"""
    ActivityLog.objects.create(
        activity_type='allocation_deleted',
        description=f"Deleted allocation for reallocation - Mukkadam #{instance.mukkadam_id}",
        job_id=instance.job_activity.job_id,
        mukkadam_id=instance.mukkadam_id,
        transport_provider_id=instance.transport_provider_id,
        amount=instance.total_cost,
        metadata={
            'activity_name': instance.job_activity.activity_name,
            'allocated_area': float(instance.allocated_area),
        }
    )

@receiver(post_save, sender=PaymentRequest)
def log_payment_request_activity(sender, instance, created, **kwargs):
    """Log payment request activities"""
    if created:
        ActivityLog.objects.create(
            activity_type='payment_requested',
            description=f"Payment requested by Mukkadam #{instance.mukkadam_id}",
            allocation=instance.allocation,
            payment_request=instance,
            job_id=instance.allocation.job_activity.job_id,
            mukkadam_id=instance.mukkadam_id,
            amount=instance.requested_amount,
            performed_by=instance.requested_by,
            metadata={
                'activity_name': instance.allocation.job_activity.activity_name,
            }
        )
    else:
        # Check status changes
        if instance.status == 'paid' and instance.paid_at:
            ActivityLog.objects.create(
                activity_type='payment_paid',
                description=f"Payment approved for Mukkadam #{instance.mukkadam_id}",
                allocation=instance.allocation,
                payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                amount=instance.requested_amount,
                performed_by=instance.paid_by,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                }
            )
        elif instance.status == 'rejected' and instance.rejected_at:
            ActivityLog.objects.create(
                activity_type='payment_rejected',
                description=f"Payment rejected for Mukkadam #{instance.mukkadam_id}",
                allocation=instance.allocation,
                payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                amount=instance.requested_amount,
                performed_by=instance.rejected_by,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'rejection_reason': instance.rejection_reason,
                }
            )

@receiver(post_save, sender=TransportPaymentRequest)
def log_transport_payment_activity(sender, instance, created, **kwargs):
    """Log transport payment activities"""
    if created:
        ActivityLog.objects.create(
            activity_type='transport_payment_requested',
            description=f"Transport payment requested for Provider #{instance.transport_provider_id}",
            allocation=instance.allocation,
            transport_payment_request=instance,
            job_id=instance.allocation.job_activity.job_id,
            mukkadam_id=instance.allocation.mukkadam_id,
            transport_provider_id=instance.transport_provider_id,
            amount=instance.requested_amount,
            performed_by=instance.requested_by,
            metadata={
                'activity_name': instance.allocation.job_activity.activity_name,
            }
        )
    else:
        if instance.status == 'paid' and instance.paid_at:
            ActivityLog.objects.create(
                activity_type='transport_payment_paid',
                description=f"Transport payment approved for Provider #{instance.transport_provider_id}",
                allocation=instance.allocation,
                transport_payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.allocation.mukkadam_id,
                transport_provider_id=instance.transport_provider_id,
                amount=instance.requested_amount,
                performed_by=instance.paid_by,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                }
            )
        elif instance.status == 'rejected' and instance.rejected_at:
            ActivityLog.objects.create(
                activity_type='transport_payment_rejected',
                description=f"Transport payment rejected for Provider #{instance.transport_provider_id}",
                allocation=instance.allocation,
                transport_payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.allocation.mukkadam_id,
                transport_provider_id=instance.transport_provider_id,
                amount=instance.requested_amount,
                performed_by=instance.rejected_by,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'rejection_reason': instance.rejection_reason,
                }
            )