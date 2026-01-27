# allocation_service/signals.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Allocation, PaymentRequest, TransportPaymentRequest, ActivityLog
from decimal import Decimal
import requests
from django.conf import settings
SUPPLY_API_URL = getattr(settings, 'SUPPLY_API_URL')
# SUPPLY_API_URL = 'https://supply.bharatintelligence.ai' # Change to your actual Supply App URL
# SUPPLY_API_URL = 'http://localhost:8000'
# ✅ Thread-local storage to track old values
import threading
_thread_locals = threading.local()

def get_mukkadam_name(mukkadam_id):
    """Fetch mukkadam name from supply service"""
    try:
        # REMOVED the '$' before {SUPPLY_API_URL}
        response = requests.get(
            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/', 
            timeout=5 # Reduced timeout (70s is too long for a signal)
        )
        if response.status_code == 200:
            return response.json().get('mukkadam_name', f'Mukkadam #{mukkadam_id}')
        else:
            print(f"Error fetching Mukkadam: Status {response.status_code}") # Debug print
    except Exception as e:
        print(f"Exception fetching Mukkadam: {str(e)}") # Print the actual error
        pass
    return f'Mukkadam #{mukkadam_id}'
def get_transport_provider_name(provider_id):
    """Fetch transport provider name from supply service"""
    try:
        response = requests.get(
            f'{SUPPLY_API_URL}/api/transport-providers/{provider_id}/',
            timeout=2
        )
        if response.status_code == 200:
            return response.json().get('name', f'Provider #{provider_id}')
    except:
        pass
    return f'Provider #{provider_id}'

# ========================================
# ALLOCATION SIGNALS WITH CHANGE TRACKING
# ========================================

@receiver(pre_save, sender=Allocation)
def capture_allocation_old_values(sender, instance, **kwargs):
    """Capture old values before save"""
    if instance.pk:  # Only for updates
        try:
            old_instance = Allocation.objects.get(pk=instance.pk)
            _thread_locals.old_allocation = old_instance
        except Allocation.DoesNotExist:
            _thread_locals.old_allocation = None
    else:
        _thread_locals.old_allocation = None

@receiver(post_save, sender=Allocation)
def log_allocation_activity_with_changes(sender, instance, created, **kwargs):
    """Log allocation with detailed change tracking"""
    
    # Get names
    mukkadam_name = get_mukkadam_name(instance.mukkadam_id)
    transport_name = None
    if instance.transport_provider_id:
        transport_name = get_transport_provider_name(instance.transport_provider_id)
    
    if created:
        # New allocation - log all fields as "new"
        ActivityLog.objects.create(
            activity_type='allocation_created',
            description=f"Allocated {instance.allocated_area} acres to {mukkadam_name} for {instance.job_activity.activity_name}",
            allocation=instance,
            # allocation_id=instance.id,
            job_id=instance.job_activity.job_id,
            mukkadam_id=instance.mukkadam_id,
            mukkadam_name=mukkadam_name,
            transport_provider_id=instance.transport_provider_id,
            transport_name=transport_name,
            amount=instance.total_cost,
            performed_by=instance.allocated_by,
            changes={
                'allocated_area': {'old': None, 'new': float(instance.allocated_area)},
                'mukkadam_price': {'old': None, 'new': float(instance.mukkadam_price)},
                'transport_price': {'old': None, 'new': float(instance.transport_price or 0)},
                'work_date': {'old': None, 'new': str(instance.work_date)},
                'crew_size': {'old': None, 'new': instance.crew_size},
                'transport_type': {'old': None, 'new': instance.transport_type},
            },
            metadata={
                'activity_name': instance.job_activity.activity_name,
                'status': instance.status,
            }
        )
    else:
        # Update - track what changed
        old_instance = getattr(_thread_locals, 'old_allocation', None)
        if not old_instance:
            return
        
        changes = {}
        
        # Track field changes
        fields_to_track = {
            'allocated_area': 'Area',
            'mukkadam_price': 'Mukkadam Price',
            'transport_price': 'Transport Price',
            'work_date': 'Work Date',
            'crew_size': 'Crew Size',
            'transport_type': 'Transport Type',
            'transport_provider_id': 'Transport Provider',
            'status': 'Status',
            'notes': 'Notes',
        }
        
        for field, label in fields_to_track.items():
            old_val = getattr(old_instance, field)
            new_val = getattr(instance, field)
            
            # Convert Decimal to float for comparison
            if isinstance(old_val, Decimal):
                old_val = float(old_val)
            if isinstance(new_val, Decimal):
                new_val = float(new_val)
            
            if old_val != new_val:
                changes[field] = {
                    'label': label,
                    'old': str(old_val) if old_val is not None else 'Not set',
                    'new': str(new_val) if new_val is not None else 'Not set'
                }
        
        # Only log if there are actual changes
        if changes:
            # Build description
            changed_fields = ', '.join([changes[k]['label'] for k in changes.keys()])
            
            ActivityLog.objects.create(
                activity_type='allocation_updated',
                description=f"Updated allocation for {mukkadam_name}: Changed {changed_fields}",
                allocation=instance,
                # allocation_id=instance.id,
                job_id=instance.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                mukkadam_name=mukkadam_name,
                transport_provider_id=instance.transport_provider_id,
                transport_name=transport_name,
                amount=instance.total_cost,
                performed_by=instance.allocated_by,
                changes=changes,
                metadata={
                    'activity_name': instance.job_activity.activity_name,
                    'total_changes': len(changes),
                }
            )
        
        # Clean up thread local
        _thread_locals.old_allocation = None

@receiver(post_delete, sender=Allocation)
def log_allocation_deletion(sender, instance, **kwargs):
    """Log when allocation is deleted"""
    mukkadam_name = get_mukkadam_name(instance.mukkadam_id)
    
    ActivityLog.objects.create(
        activity_type='allocation_deleted',
        description=f"Deleted allocation for {mukkadam_name} - {instance.allocated_area} acres",
        # allocation_id=instance.id,
        allocation=None,
        job_id=instance.job_activity.job_id,
        mukkadam_id=instance.mukkadam_id,
        mukkadam_name=mukkadam_name,
        transport_provider_id=instance.transport_provider_id,
        amount=instance.total_cost,
        changes={
            'allocated_area': {'old': float(instance.allocated_area), 'new': None},
            'mukkadam_price': {'old': float(instance.mukkadam_price), 'new': None},
        },
        metadata={
            'activity_name': instance.job_activity.activity_name,
            'reason': 'Reallocation or cancellation'
        }
    )

# ========================================
# PAYMENT REQUEST SIGNALS WITH CHANGE TRACKING
# ========================================

@receiver(pre_save, sender=PaymentRequest)
def capture_payment_old_values(sender, instance, **kwargs):
    """Capture old payment values before save"""
    if instance.pk:
        try:
            old_instance = PaymentRequest.objects.get(pk=instance.pk)
            _thread_locals.old_payment = old_instance
        except PaymentRequest.DoesNotExist:
            _thread_locals.old_payment = None
    else:
        _thread_locals.old_payment = None

@receiver(post_save, sender=PaymentRequest)
def log_payment_activity_with_changes(sender, instance, created, **kwargs):
    """Log payment request activities with change tracking"""
    
    mukkadam_name = get_mukkadam_name(instance.mukkadam_id)
    
    if created:
        ActivityLog.objects.create(
            activity_type='payment_requested',
            description=f"Payment requested by {mukkadam_name} for ₹{instance.requested_amount}",
            allocation=instance.allocation,
            # allocation_id=instance.allocation.id,
            payment_request=instance,
            job_id=instance.allocation.job_activity.job_id,
            mukkadam_id=instance.mukkadam_id,
            mukkadam_name=mukkadam_name,
            amount=instance.requested_amount,
            performed_by=instance.requested_by,
            changes={
                'status': {'old': None, 'new': 'pending'},
                'amount': {'old': None, 'new': float(instance.requested_amount)}
            },
            metadata={
                'activity_name': instance.allocation.job_activity.activity_name,
                'notes': instance.notes,
            }
        )
    else:
        old_instance = getattr(_thread_locals, 'old_payment', None)
        if not old_instance:
            return
        
        changes = {}
        
        # Track status change
        if old_instance.status != instance.status:
            changes['status'] = {
                'label': 'Status',
                'old': old_instance.status,
                'new': instance.status
            }
        
        # Track amount change
        if old_instance.requested_amount != instance.requested_amount:
            changes['requested_amount'] = {
                'label': 'Amount',
                'old': float(old_instance.requested_amount),
                'new': float(instance.requested_amount)
            }
        
        # Determine activity type based on status
        if instance.status == 'paid' and old_instance.status != 'paid':
            ActivityLog.objects.create(
                activity_type='payment_paid',
                description=f"Payment approved for {mukkadam_name} - ₹{instance.requested_amount}",
                allocation=instance.allocation,
                # allocation_id=instance.allocation.id,
                payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                mukkadam_name=mukkadam_name,
                amount=instance.requested_amount,
                performed_by=instance.paid_by,
                changes=changes,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'paid_at': str(instance.paid_at),
                }
            )
        
        elif instance.status == 'rejected' and old_instance.status != 'rejected':
            ActivityLog.objects.create(
                activity_type='payment_rejected',
                description=f"Payment rejected for {mukkadam_name} - ₹{instance.requested_amount}",
                allocation=instance.allocation,
                # allocation_id=instance.allocation.id,
                payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                mukkadam_name=mukkadam_name,
                amount=instance.requested_amount,
                performed_by=instance.rejected_by,
                changes=changes,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'rejection_reason': instance.rejection_reason,
                }
            )
        
        elif instance.status == 'pending' and old_instance.status == 'rejected':
            # Re-request after rejection
            ActivityLog.objects.create(
                activity_type='payment_requested',
                description=f"Payment re-requested by {mukkadam_name} after rejection - ₹{instance.requested_amount}",
                allocation=instance.allocation,
                # allocation_id=instance.allocation.id,
                payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.mukkadam_id,
                mukkadam_name=mukkadam_name,
                amount=instance.requested_amount,
                performed_by=instance.requested_by,
                changes=changes,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'is_resubmission': True,
                }
            )
        
        # Clean up
        _thread_locals.old_payment = None

# ========================================
# TRANSPORT PAYMENT SIGNALS (Similar pattern)
# ========================================

@receiver(pre_save, sender=TransportPaymentRequest)
def capture_transport_payment_old_values(sender, instance, **kwargs):
    """Capture old transport payment values"""
    if instance.pk:
        try:
            old_instance = TransportPaymentRequest.objects.get(pk=instance.pk)
            _thread_locals.old_transport_payment = old_instance
        except TransportPaymentRequest.DoesNotExist:
            _thread_locals.old_transport_payment = None
    else:
        _thread_locals.old_transport_payment = None

@receiver(post_save, sender=TransportPaymentRequest)
def log_transport_payment_activity_with_changes(sender, instance, created, **kwargs):
    """Log transport payment with change tracking"""
    
    transport_name = get_transport_provider_name(instance.transport_provider_id)
    mukkadam_name = get_mukkadam_name(instance.allocation.mukkadam_id)
    
    if created:
        ActivityLog.objects.create(
            activity_type='transport_payment_requested',
            description=f"Transport payment requested for {transport_name} - ₹{instance.requested_amount}",
            allocation=instance.allocation,
            # allocation_id=instance.allocation.id,
            transport_payment_request=instance,
            job_id=instance.allocation.job_activity.job_id,
            mukkadam_id=instance.allocation.mukkadam_id,
            mukkadam_name=mukkadam_name,
            transport_provider_id=instance.transport_provider_id,
            transport_name=transport_name,
            amount=instance.requested_amount,
            performed_by=instance.requested_by,
            changes={
                'status': {'old': None, 'new': 'pending'},
                'amount': {'old': None, 'new': float(instance.requested_amount)}
            },
            metadata={
                'activity_name': instance.allocation.job_activity.activity_name,
            }
        )
    else:
        old_instance = getattr(_thread_locals, 'old_transport_payment', None)
        if not old_instance:
            return
        
        changes = {}
        
        if old_instance.status != instance.status:
            changes['status'] = {
                'label': 'Status',
                'old': old_instance.status,
                'new': instance.status
            }
        
        if old_instance.requested_amount != instance.requested_amount:
            changes['requested_amount'] = {
                'label': 'Amount',
                'old': float(old_instance.requested_amount),
                'new': float(instance.requested_amount)
            }
        
        if instance.status == 'paid' and old_instance.status != 'paid':
            ActivityLog.objects.create(
                activity_type='transport_payment_paid',
                description=f"Transport payment approved for {transport_name} - ₹{instance.requested_amount}",
                allocation=instance.allocation,
                # allocation_id=instance.allocation.id,
                transport_payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.allocation.mukkadam_id,
                mukkadam_name=mukkadam_name,
                transport_provider_id=instance.transport_provider_id,
                transport_name=transport_name,
                amount=instance.requested_amount,
                performed_by=instance.paid_by,
                changes=changes,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                }
            )
        
        elif instance.status == 'rejected' and old_instance.status != 'rejected':
            ActivityLog.objects.create(
                activity_type='transport_payment_rejected',
                description=f"Transport payment rejected for {transport_name}",
                allocation=instance.allocation,
                # allocation_id=instance.allocation.id,
                transport_payment_request=instance,
                job_id=instance.allocation.job_activity.job_id,
                mukkadam_id=instance.allocation.mukkadam_id,
                mukkadam_name=mukkadam_name,
                transport_provider_id=instance.transport_provider_id,
                transport_name=transport_name,
                amount=instance.requested_amount,
                performed_by=instance.rejected_by,
                changes=changes,
                metadata={
                    'activity_name': instance.allocation.job_activity.activity_name,
                    'rejection_reason': instance.rejection_reason,
                }
            )
        
        _thread_locals.old_transport_payment = None

# ========================================
# SYNC PAYMENT AMOUNTS ON ALLOCATION PRICE CHANGE
# ========================================

@receiver(post_save, sender=Allocation)
def sync_payment_request_amount(sender, instance, **kwargs):
    """Auto-sync payment request amount when allocation price changes"""
    try:
        if hasattr(instance, 'payment_request'):
            payment_request = instance.payment_request
            new_amount = float(instance.mukkadam_price)
            
            if payment_request.requested_amount != new_amount:
                old_amount = payment_request.requested_amount
                payment_request.requested_amount = new_amount
                payment_request.save(update_fields=['requested_amount'])
                
                print(f"✅ [AUTO-SYNC] Payment Request #{payment_request.id} amount updated: ₹{old_amount} → ₹{new_amount}")
    except Exception as e:
        print(f"⚠️ Error syncing payment request: {str(e)}")