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
    mobile_number = models.CharField(max_length=15, unique=True, db_index=True)
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
        return f"{self.full_name or self.user.username} - {self.mobile_number}"



# Auto-create profile when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)



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