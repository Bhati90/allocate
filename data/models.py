# models.py

from django.db import models
from django.contrib.auth.models import User

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Job(models.Model):
    """Farm Visit Job from external API"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    # External API fields
    job_id = models.CharField(max_length=100, unique=True, help_text="External farm visit ID (e.g., FV123)")
    farmer_id = models.CharField(max_length=100, help_text="External farmer ID")
    plot_id = models.CharField(max_length=100, help_text="External plot ID")
    
    # Job details
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Dates
    scheduled_date = models.DateTimeField(help_text="Scheduled date from API")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Notes
    activity_notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)
    
    # Financial
    total_activities_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Booking info (optional)
    booking_id = models.CharField(max_length=100, blank=True, null=True)
    booking_total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_advance_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.job_id} - {self.farmer_id}"

from decimal import Decimal

class JobActivity(models.Model):
    """Activity within a Job - flexible activity types"""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='activities')
    
    # External API fields
    activity_id = models.CharField(max_length=100, help_text="External activity ID (e.g., ACT001)")
    activity_name = models.CharField(max_length=255, help_text="Activity name from API")
    activity_type = models.CharField(max_length=100, blank=True, null=True, help_text="Normalized activity type")
    
    # Activity details
    scheduled_datetime = models.DateTimeField(help_text="Scheduled date/time for this activity")
    total_area = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total acres for this activity")
    
    # Pricing from API
    total_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base price from API")
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total from API")
    
    # Allocation tracking
    allocated_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Calculated fields
    estimated_workers = models.IntegerField(default=10, help_text="Estimated workers needed")
    rate_per_acre = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Location
    location = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['scheduled_datetime']
    
    def save(self, *args, **kwargs):
        # ✅ ENSURE ALL CALCULATIONS USE DECIMAL
        # Calculate remaining area
        self.remaining_area = self.total_area - self.allocated_area
        
        # Calculate rate per acre if total_price and area available
        if self.total_area > 0:
            self.rate_per_acre = self.total_price / self.total_area
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.job.job_id} - {self.activity_name} ({self.total_area} acres)"

class Allocation(models.Model):
    """Allocation of activity to mukkadam"""
    TRANSPORT_TYPES = [
        ('provider', 'Transport Provider'),
        ('own', 'Own Transport'),
        ('none', 'No Transport Needed'),
    ]
    
    # Required: Link to job activity
    job_activity = models.ForeignKey(
        JobActivity, 
        on_delete=models.CASCADE, 
        related_name='allocations'
    )
    
    mukkadam_id = models.IntegerField(help_text="Mukkadam ID from external service")
    
    # Area allocation
    allocated_area = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Area allocated to this mukkadam"
    )
    
    work_date = models.DateField(help_text="Date when mukkadam will do the work")
    
    crew_size = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Number of workers for this specific allocation"
    )
    
    # Pricing
    mukkadam_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Transport handling
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_TYPES, default='provider')
    transport_provider_id = models.IntegerField(null=True, blank=True)
    own_transport_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    transport_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Tracking
    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('allocated', 'Allocated'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='allocated'
    )
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-allocated_at']
    
    @property
    def total_cost(self):
        mukkadam = self.mukkadam_price or 0
        transport = self.transport_price or 0
        return mukkadam + transport
    
    @property
    def farmer_work_id(self):
        """Get work_id from job_activity"""
        return self.job_activity.job.job_id
    
    def __str__(self):
        return f"{self.job_activity.job.job_id} - {self.job_activity.activity_name} - Mukkadam #{self.mukkadam_id}"
class AllocationStats(models.Model):
    """Daily statistics for allocations"""
    date = models.DateField(unique=True)
    total_allocations = models.IntegerField(default=0)
    total_area_allocated = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_mukkadam_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_transport_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allocations_by_user = models.JSONField(default=dict, help_text="User-wise allocation count")
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Allocation Stats"
    
    def __str__(self):
        return f"Stats for {self.date}"