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
    completed_at = models.DateTimeField(auto_now_add=True)
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


# models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class FCMDevice(models.Model):
    """
    Store FCM tokens for push notifications
    """
    DEVICE_TYPE_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ]
    
    user_id = models.CharField(max_length=100, db_index=True)
    mobile_number = models.CharField(max_length=15, db_index=True)
    fcm_token = models.TextField(unique=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES, default='android')
    device_id = models.CharField(max_length=255, blank=True, null=True)  # Unique device identifier
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'data_fcm_devices'
        indexes = [
            models.Index(fields=['user_id', 'is_active']),
            models.Index(fields=['mobile_number', 'is_active']),
        ]
        verbose_name = 'FCM Device'
        verbose_name_plural = 'FCM Devices'
    
    def __str__(self):
        return f"{self.mobile_number} - {self.device_type} - {self.fcm_token[:20]}..."
    
    def mark_as_used(self):
        """Update last used timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class PushNotificationLog(models.Model):
    """
    Log all push notifications sent
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    fcm_device = models.ForeignKey(FCMDevice, on_delete=models.SET_NULL, null=True, blank=True)
    user_id = models.CharField(max_length=100, db_index=True)
    mobile_number = models.CharField(max_length=15, db_index=True)
    
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional custom data
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    scheduled_at = models.DateTimeField(null=True, blank=True)  # For scheduled notifications
    sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'push_notification_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['status', 'scheduled_at']),
        ]
    
    def __str__(self):
        return f"{self.mobile_number} - {self.title} - {self.status}"
    

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


class Message(models.Model):
    """
    Stores SMS messages from user's phone
    """
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="User ID from mobile app"
    )
    address = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Phone number or sender ID (e.g., AX-BANK)"
    )
    body = models.TextField(
        help_text="Full content of the message"
    )
    timestamp = models.BigIntegerField(
        db_index=True,
        help_text="Time received/sent in milliseconds since epoch"
    )
    type = models.CharField(
        max_length=20,
        help_text="Clean string: inbox, sent, draft"
    )
    read_status = models.IntegerField(
        default=0,
        help_text="1 for Read, 0 for Unread"
    )
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_messages'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user_id', '-timestamp']),
            models.Index(fields=['address', '-timestamp']),
            models.Index(fields=['user_id', 'address']),
        ]
    
    def __str__(self):
        return f"{self.type} - {self.address} (User: {self.user_id})"
    
    @property
    def message_datetime(self):
        """Convert milliseconds timestamp to datetime"""
        return datetime.fromtimestamp(self.timestamp / 1000.0)


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