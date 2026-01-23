# allocation_app/models.py

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """
    Company team member profile
    Links mobile number to Django User for mobile app login
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    mobile_number = models.CharField(
        max_length=15, 
        unique=True, 
        db_index=True,
        null=True,  # ✅ Allow NULL
        blank=True  # ✅ Allow empty in forms
    )
    full_name = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(
        max_length=50,
        choices=[
            ('admin', 'Admin'),
            ('manager', 'Manager'),
            ('supervisor', 'Field Supervisor'),
            ('staff', 'Staff')
        ],
        default='staff'
    )
    
    is_mobile_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['mobile_number']),
        ]
    
    def __str__(self):
        return f"{self.full_name or self.user.username} - {self.mobile_number or 'No mobile'}"


# ✅ Update the signal to set mobile_number as None explicitly
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, mobile_number=None)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class JobActivity(models.Model):
    """
    Activity within a Job - Job details come from external API
    We only store the activity details and link via job_id
    """
    # Link to external job
    job_id = models.CharField(
        max_length=100, 
        db_index=True,
        help_text="External job ID (e.g., FV123, WORK-001)"
    )
    
    # External API fields
    activity_id = models.CharField(
        max_length=100, 
        help_text="External activity ID (e.g., ACT001)"
    )
    activity_name = models.CharField(
        max_length=255, 
        help_text="Activity name from API (e.g., 'Pruning', 'Harvesting')"
    )
    activity_type = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Normalized activity type"
    )
    
    # Activity details
    scheduled_datetime = models.DateTimeField(
        help_text="Scheduled date/time for this activity"
    )
    total_area = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Total acres for this activity"
    )
    
    # Pricing from API
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Base price from API"
    )
    transport_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    other_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Total from API"
    )
    
    # Allocation tracking
    allocated_area = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    
    # Calculated fields
    estimated_workers = models.IntegerField(
        default=10, 
        help_text="Estimated workers needed"
    )
    rate_per_acre = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    
    # Location
    location = models.CharField(
        max_length=255, 
        blank=True, 
        null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_manually_edited = models.BooleanField(
        default=False,
        help_text="True if this activity has been manually edited by admin"
    )
    
    class Meta:
        ordering = ['scheduled_datetime']
        indexes = [
            models.Index(fields=['job_id', 'activity_id']),
            models.Index(fields=['job_id']),
        ]
    
    @property
    def remaining_area(self):
        """Calculate remaining area"""
        return self.total_area - self.allocated_area
    
    @property
    def is_fully_allocated(self):
        """Check if activity is fully allocated"""
        return self.allocated_area >= self.total_area
    
    def save(self, *args, **kwargs):
        # Calculate rate per acre if total_price and area available
        if self.total_area > 0:
            self.rate_per_acre = self.total_price / self.total_area
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.job_id} - {self.activity_name} ({self.total_area} acres)"


class Allocation(models.Model):
    """Allocation of activity to mukkadam"""
    TRANSPORT_TYPES = [
        ('provider', 'Transport Provider'),
        ('own', 'Own Transport'),
        ('none', 'No Transport Needed'),
    ]
    
    STATUS_CHOICES = [
        ('allocated', 'Allocated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    
    # Link to job activity
    job_activity = models.ForeignKey(
        JobActivity, 
        on_delete=models.CASCADE, 
        related_name='allocations'
    )
    
    # Mukkadam (from external service)
    mukkadam_id = models.IntegerField(
        help_text="Mukkadam ID from external service"
    )
    
    # Area allocation
    allocated_area = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Area allocated to this mukkadam"
    )
    
    work_date = models.DateField(
        help_text="Date when mukkadam will do the work"
    )
    
    crew_size = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Number of workers for this specific allocation"
    )
    
    # Pricing
    mukkadam_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2
    )
    
    # Transport handling
    transport_type = models.CharField(
        max_length=20, 
        choices=TRANSPORT_TYPES, 
        default='provider'
    )
    transport_provider_id = models.IntegerField(
        null=True, 
        blank=True
    )
    own_transport_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    transport_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        default=0
    )
    
    # Tracking
    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='allocated'
    )
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-allocated_at']
        indexes = [
            models.Index(fields=['mukkadam_id']),
            models.Index(fields=['work_date']),
            models.Index(fields=['allocated_at']),
        ]
    
    @property
    def total_cost(self):
        mukkadam = self.mukkadam_price or 0
        transport = self.transport_price or 0
        return mukkadam + transport
    
    @property
    def farmer_work_id(self):
        """Get work_id from job_activity"""
        return self.job_activity.job_id
    
    @property
    def created_by(self):
        """Backward compatibility - return allocated_by as created_by"""
        return self.allocated_by
    
    def __str__(self):
        return f"{self.job_activity.job_id} - {self.job_activity.activity_name} - Mukkadam #{self.mukkadam_id}"


class AllocationStats(models.Model):
    """Daily statistics for allocations"""
    date = models.DateField(unique=True)
    total_allocations = models.IntegerField(default=0)
    total_area_allocated = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    total_mukkadam_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    total_transport_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    allocations_by_user = models.JSONField(
        default=dict, 
        help_text="User-wise allocation count"
    )
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Allocation Stats"
    
    def __str__(self):
        return f"Stats for {self.date}"
    
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class PaymentRequest(models.Model):
    """Payment requests from mukkadams for completed work"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    # Link to allocation
    allocation = models.OneToOneField(
        Allocation,
        on_delete=models.CASCADE,
        related_name='payment_request',
        help_text="One payment request per allocation"
    )
    
    # Mukkadam info (redundant but useful for queries)
    mukkadam_id = models.IntegerField(db_index=True)
    
    # Amount (copied from allocation at creation)
    requested_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="mukkadam_price × allocated_area"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Timestamps and users
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_payment_requests'
    )
    
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paid_payment_requests'
    )
    
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_payment_requests'
    )
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['mukkadam_id', 'status']),
            models.Index(fields=['status', '-requested_at']),
        ]
    
    def __str__(self):
        return f"Payment Request #{self.id} - Mukkadam #{self.mukkadam_id} - ₹{self.requested_amount} ({self.status})"


class TransportPaymentRequest(models.Model):
    """Payment requests from transport providers"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    # Link to allocation
    allocation = models.OneToOneField(
        Allocation,
        on_delete=models.CASCADE,
        related_name='transport_payment_request',
        help_text="One payment request per allocation"
    )
    
    # Transport provider info
    transport_provider_id = models.IntegerField(db_index=True)
    
    # Amount (copied from allocation at creation)
    requested_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Transport cost from allocation"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Timestamps and users
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_transport_payment_requests'
    )
    
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paid_transport_payment_requests'
    )
    
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_transport_payment_requests'
    )
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['transport_provider_id', 'status']),
            models.Index(fields=['status', '-requested_at']),
        ]
    
    def __str__(self):
        return f"Transport Payment #{self.id} - Provider #{self.transport_provider_id} - ₹{self.requested_amount} ({self.status})"

class AllocationChangeLog(models.Model):
    """Track all changes made to allocations"""
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='change_logs'
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.TextField(
        help_text="Reason for making this change"
    )
    
    # Store what changed
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['allocation', '-changed_at']),
        ]
    
    def __str__(self):
        return f"{self.allocation.id} - {self.field_name} changed on {self.changed_at}"
class ActivityLog(models.Model):
    """Unified activity log with detailed change tracking"""
    
    ACTIVITY_TYPES = [
        ('allocation_created', 'Allocation Created'),
        ('allocation_updated', 'Allocation Updated'),
        ('allocation_deleted', 'Allocation Deleted'),
        ('payment_requested', 'Payment Requested'),
        ('payment_paid', 'Payment Paid'),
        ('payment_rejected', 'Payment Rejected'),
        ('transport_payment_requested', 'Transport Payment Requested'),
        ('transport_payment_paid', 'Transport Payment Paid'),
        ('transport_payment_rejected', 'Transport Payment Rejected'),
    ]
    
    # Activity details
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES, db_index=True)
    description = models.TextField()
    
    # Related objects
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.SET_NULL,  # ✅ Changed from CASCADE to SET_NULL to keep logs
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    # ❌ REMOVE THIS LINE - Django creates allocation_id automatically
    # allocation_id = models.IntegerField(null=True, blank=True, db_index=True)
    
    payment_request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.SET_NULL,  # ✅ Keep logs even if payment deleted
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    transport_payment_request = models.ForeignKey(
        TransportPaymentRequest,
        on_delete=models.SET_NULL,  # ✅ Keep logs even if transport payment deleted
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    
    # IDs for reference (in case objects are deleted)
    job_id = models.CharField(max_length=100, db_index=True)
    mukkadam_id = models.IntegerField(db_index=True)
    mukkadam_name = models.CharField(max_length=255, blank=True, null=True)
    transport_provider_id = models.IntegerField(null=True, blank=True)
    transport_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Financial data
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # User and timestamp
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    performed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # ✅ Detailed change tracking
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores field-by-field changes: {'field_name': {'old': value, 'new': value}}"
    )
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['activity_type', '-performed_at']),
            models.Index(fields=['job_id', '-performed_at']),
            models.Index(fields=['mukkadam_id', '-performed_at']),
            # ✅ Use the auto-generated allocation_id field for indexing
            models.Index(fields=['allocation_id', '-performed_at']),
        ]
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.job_id} at {self.performed_at}"
# core/models.py (add to your existing models)
from django.db import models
from django.utils import timezone
from django.db import models
from django.utils import timezone

class FarmerCall(models.Model):
    """Track calls made to farmers/mukadams"""
    CALL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('ringing', 'Ringing'),
        ('in-progress', 'In Progress'),
        ('answered', 'Answered'),
        ('completed', 'Completed'),
        ('terminal', 'Terminal'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
        ('no-answer', 'No Answer'),
        ('cancelled', 'Cancelled'),
    ]
    
    CALL_PURPOSE_CHOICES = [
        ('new_job', 'New Job Available'),
        ('payment', 'Payment Notification'),
        ('reminder', 'Work Reminder'),
        ('verification', 'Verification'),
        ('follow_up', 'Follow Up'),
        ('general', 'General'),
    ]
    
    # Primary identifiers
    call_sid = models.CharField(max_length=100, unique=True, db_index=True)
    user_id = models.CharField(max_length=100, blank=True, default='system')
    mobile_number = models.CharField(max_length=15)
    from_number = models.CharField(max_length=20)
    
    # Call metadata
    purpose = models.CharField(max_length=20, choices=CALL_PURPOSE_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='pending')
    direction = models.CharField(max_length=20, default='outbound')  # ✅ NEW
    state = models.CharField(max_length=20, blank=True)  # ✅ NEW (terminal, active, etc)
    
    # Call metrics
    duration = models.IntegerField(null=True, blank=True, help_text="Total duration in seconds")
    talk_time = models.IntegerField(null=True, blank=True, help_text="Actual talk time in seconds")  # ✅ NEW
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Recording
    recording_url = models.URLField(blank=True, null=True)
    recording_urls = models.JSONField(default=list, blank=True, help_text="Array of recording URLs")  # ✅ NEW
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)  # ✅ NEW (from Exotel)
    updated_time = models.DateTimeField(null=True, blank=True)  # ✅ NEW (from Exotel)
    
    # Exotel specific
    virtual_number = models.CharField(max_length=20, blank=True)  # ✅ NEW
    custom_field = models.CharField(max_length=255, blank=True)  # ✅ NEW
    legs_url = models.CharField(max_length=500, blank=True)  # ✅ NEW
    
    # Extra context
    job_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    webhook_data = models.JSONField(default=dict, blank=True, help_text="Full webhook response")  # ✅ NEW
    
    # User relationship
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = "data_farmer_calls"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['call_sid']),
            models.Index(fields=['mobile_number']),
            models.Index(fields=['status']),
            models.Index(fields=['-initiated_at']),
        ]
    
    def __str__(self):
        return f"{self.purpose} - {self.mobile_number} - {self.status}"
    
    @property
    def has_recording(self):
        """Check if call has any recordings"""
        return bool(self.recording_url or self.recording_urls)
    
    @property
    def primary_recording_url(self):
        """Get the primary recording URL"""
        if self.recording_url:
            return self.recording_url
        if self.recording_urls and len(self.recording_urls) > 0:
            return self.recording_urls[0]
        return None

# allocation_app/models.py

class ActivityEditHistory(models.Model):
    """Track all edits made to activities"""
    job_activity = models.ForeignKey(
        JobActivity,
        on_delete=models.CASCADE,
        related_name='edit_history'
    )
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    edited_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(help_text="Reason for editing")
    
    # Store old and new values as JSON
    changes = models.JSONField(
        help_text="Dictionary of field: {old_value, new_value}"
    )
    
    class Meta:
        ordering = ['-edited_at']
        verbose_name_plural = "Activity Edit Histories"
    
    def __str__(self):
        return f"Edit on {self.job_activity} by {self.edited_by} at {self.edited_at}"


class ActivityLostRecord(models.Model):
    """Track activities marked as lost"""
    job_activity = models.OneToOneField(
        JobActivity,
        on_delete=models.CASCADE,
        related_name='lost_record'
    )
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_lost_activities'
    )
    marked_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(help_text="Reason for marking as lost")
    
    is_active = models.BooleanField(
        default=True,
        help_text="False if unmarked later"
    )
    
    unmarked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unmarked_lost_activities'
    )
    unmarked_at = models.DateTimeField(null=True, blank=True)
    unmark_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-marked_at']
    
    def __str__(self):
        status = "ACTIVE" if self.is_active else "UNMARKED"
        return f"Lost: {self.job_activity} - {status}"
# core/models.py

from django.db import models
from django.utils import timezone
from datetime import datetime

class Contact(models.Model):
    """
    Stores contacts from user's phone
    """
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="User ID from mobile app"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Full name of the contact as saved on device"
    )
    phones = models.JSONField(
        default=list,
        help_text="Array of phone numbers (cleaned, digits only)"
    )
    emails = models.JSONField(
        default=list,
        help_text="Array of email addresses (empty array if none)"
    )
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_contacts'
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['user_id', '-synced_at']),
        ]
    
    def __str__(self):
        return f"{self.display_name} (User: {self.user_id})"

import hashlib
from django.db import models
from datetime import datetime
# models.py
import hashlib
from django.db import models
from datetime import datetime

class Message(models.Model):
    """
    Stores SMS messages from user's phone
    """
    user_id = models.CharField(
        max_length=100,  # ✅ Increased
        db_index=True,
        help_text="User ID from mobile app"
    )
    address = models.CharField(
        max_length=100,  # ✅ Increased
        db_index=True,
        help_text="Phone number or sender ID"
    )
    body = models.TextField(
        help_text="Full content of the message"
    )
    timestamp = models.BigIntegerField(
        db_index=True,
        help_text="Time received/sent in milliseconds since epoch"
    )
    type = models.CharField(
        max_length=50,  # ✅ Increased from 20 to 50
        help_text="Clean string: inbox, sent, draft"
    )
    read_status = models.IntegerField(
        default=0,
        help_text="1 for Read, 0 for Unread"
    )
    
    # ✅ NEW: Hash for duplicate prevention
    message_hash = models.CharField(
        max_length=64,
        unique=True,  # ✅ DATABASE-LEVEL UNIQUENESS
        db_index=True,
        editable=False,
        help_text="SHA256 hash: user_id + address + timestamp"
    )
    
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_messages'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user_id', '-timestamp']),
            models.Index(fields=['address', '-timestamp']),
            models.Index(fields=['user_id', 'address']),
            models.Index(fields=['message_hash']),  # ✅ NEW
        ]
        # ✅ COMPOUND UNIQUE CONSTRAINT (backup protection)
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'address', 'timestamp'],
                name='unique_message_per_user'
            )
        ]
    
    def __str__(self):
        return f"{self.type} - {self.address} (User: {self.user_id})"
    
    @property
    def message_datetime(self):
        """Convert milliseconds timestamp to datetime"""
        return datetime.fromtimestamp(self.timestamp / 1000.0)
    
    @staticmethod
    def generate_hash(user_id, address, timestamp):
        """Generate unique hash for duplicate detection"""
        content = f"{user_id}|{address}|{timestamp}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def save(self, *args, **kwargs):
        """Auto-generate hash before saving"""
        if not self.message_hash:
            self.message_hash = self.generate_hash(
                self.user_id,
                self.address,
                self.timestamp
            )
        super().save(*args, **kwargs)

class CallLog(models.Model):
    """
    Stores call logs from user's phone
    """
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="User ID from mobile app"
    )
    name = models.CharField(
        max_length=255,
        default="Unknown",
        help_text="Contact name as saved on device"
    )
    number = models.CharField(
        max_length=20,
        db_index=True,
        null=True,
        blank=True,
        help_text="Phone number"
    )
    type = models.CharField(
        max_length=20,
        help_text="Clean string: incoming, outgoing, missed, rejected, blocked"
    )
    duration = models.IntegerField(
        default=0,
        help_text="Duration in seconds"
    )
    timestamp = models.BigIntegerField(
        db_index=True,
        help_text="Time of call in milliseconds since epoch"
    )
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_call_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user_id', '-timestamp']),
            models.Index(fields=['number', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.type} - {self.number} ({self.duration}s) (User: {self.user_id})"
    
    @property
    def call_datetime(self):
        """Convert milliseconds timestamp to datetime"""
        return datetime.fromtimestamp(self.timestamp / 1000.0)