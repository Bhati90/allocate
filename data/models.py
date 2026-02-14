# allocation_app/models.py

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
import logging

logger = logging.getLogger(__name__)

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

    # ✅ ADD THIS NEW FIELD
    farmer_work_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Farmer work ID from external farmer management system"
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
            models.Index(fields=['farmer_work_id']),  # ✅ Add this
            models.Index(fields=['farmer_work_id', 'scheduled_datetime']),  # ✅ For farmer queries
        ]
    
    @property
    def remaining_area(self):
        """Calculate remaining area"""
        return self.total_area - self.allocated_area
    @property
    def allocation_status(self):
        """Calculate allocation status based on allocated vs total area"""
        if self.total_area == 0:
            return 'no_area'
        
        allocated = self.allocated_area or Decimal('0')
        
        if allocated == 0:
            return 'pending'
        elif allocated < self.total_area:
            return 'partially_allocated'
        else:
            return 'fully_allocated'
    
    @property
    def allocation_percentage(self):
        """Calculate percentage of area allocated"""
        if self.total_area == 0:
            return 0
        
        allocated = self.allocated_area or Decimal('0')
        return round((allocated / self.total_area) * 100, 2)

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

# 1. Master Farmer Lookup (for sheet import)

# ========================================
# EXISTING MODEL (Updated)
# ========================================
class ImportedFarmer(models.Model):
    name = models.CharField(max_length=255)
    contact_no = models.CharField(max_length=20, blank=True)
    external_farmer_id = models.CharField(max_length=100, unique=True, db_index=True,null = True) # ✅ Make unique
    location = models.CharField(max_length=255, blank=True)
    created_from_import = models.BooleanField(default=True)
    is_dummy_id = models.BooleanField(default=False)
    dummy_id_number = models.IntegerField(null=True, blank=True)
    
    # ✅ NEW: Additional fields from external API
    village = models.CharField(max_length=100, blank=True,null = True)
    taluka = models.CharField(max_length=100, blank=True,null = True)
    district = models.CharField(max_length=100, blank=True,null = True)
    state = models.CharField(max_length=100, blank=True,null = True)
    
    created_at = models.DateTimeField(auto_now_add=True,null = True)
    updated_at = models.DateTimeField(auto_now=True,null = True)
    
    class Meta:
        indexes = [
            models.Index(fields=['external_farmer_id']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.external_farmer_id})"


# models.py

class ImportedPayment(models.Model):
    """
    Track customer/booking payments from webhook (INCOMING payments)
    """
    
    PAYMENT_MODE_CHOICES = [
        ('UPI', 'UPI'),
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CARD', 'Card'),
        ('CHEQUE', 'Cheque'),
        ('WILL_PAY_LATER', 'Will Pay Later'),  # ✅ Add this
        ('CREDIT', 'Credit'),
        ('OTHER', 'Other'),
    ]
    
    # Link to job
    imported_job = models.ForeignKey(
        'ImportedJob',
        on_delete=models.CASCADE,
        related_name='booking_payments',
        help_text="Job this payment is for"
    )
    
    # Link to farmer (who made the payment)
    imported_farmer = models.ForeignKey(
        'ImportedFarmer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_payments_made',
        help_text="Farmer who made this payment"
    )
    
    # Payment identification
    external_payment_id = models.IntegerField(
        unique=True, 
        db_index=True,
        help_text="Payment ID from external system"
    )
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=50)  # ✅ Remove choices to accept any value
    paid_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    paid_status = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    synced_from_webhook_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-paid_at']
        indexes = [
            models.Index(fields=['external_payment_id']),
            models.Index(fields=['imported_job']),
            models.Index(fields=['imported_farmer']),
            models.Index(fields=['paid_at']),
        ]
        verbose_name = "Customer Booking Payment"
        verbose_name_plural = "Customer Booking Payments"
    
    def __str__(self):
        return f"Booking Payment #{self.external_payment_id} - ₹{self.amount} ({self.mode})"

# ========================================
# NEW MODEL: Visit Records
# ========================================
class ImportedVisit(models.Model):
    """Store visit records from webhook"""
    imported_job = models.ForeignKey(
        'ImportedJob',
        on_delete=models.CASCADE,
        related_name='visits'
    )
    
    # Visit identification
    external_visit_id = models.IntegerField(unique=True, db_index=True)
    
    # Visit details
    status = models.CharField(max_length=50)  # booked, completed, cancelled
    assigned_to = models.CharField(max_length=255, blank=True)
    
    # Store raw media_locations JSON
    media_locations = models.JSONField(default=list)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['external_visit_id']),
            models.Index(fields=['imported_job']),
        ]
    
    def __str__(self):
        return f"Visit #{self.external_visit_id} - {self.status}"


# ========================================
# NEW MODEL: Media/Location Records
# ========================================
class ImportedMedia(models.Model):
    """Store media location data from visits"""
    visit = models.ForeignKey(
        'ImportedVisit',
        on_delete=models.CASCADE,
        related_name='media_records'
    )
    
    external_media_id = models.IntegerField(db_index=True)
    media_type = models.CharField(max_length=50)  # image, video
    
    # Location data
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    address = models.TextField(blank=True)
    is_field_location = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['external_media_id']),
        ]
    
    def __str__(self):
        return f"Media #{self.external_media_id} - {self.media_type}"
 
# 2. Master Mukkadam/Labour Team Lookup
class ImportedMukkadam(models.Model):
    team_name = models.CharField(max_length=255, unique=True)
    external_mukkadam_id = models.IntegerField(blank=True, null=True)  # Maps to supply API
    contact_no = models.CharField(max_length=20, blank=True)
    created_from_import = models.BooleanField(default=True)
    
# 3. Master Transporter Lookup
class ImportedTransporter(models.Model):
    name = models.CharField(max_length=255, unique=True)
    external_transporter_id = models.IntegerField(blank=True, null=True)  # Maps to transport API
    contact_no = models.CharField(max_length=20, blank=True)
    created_from_import = models.BooleanField(default=True)


class Allocation(models.Model):
    """Allocation of activity to mukkadam"""
    TRANSPORT_TYPES = [
        ('provider', 'Transport Provider'),
        ('own', 'Own Transport'),
        ('none', 'No Transport Needed'),
    ]
    
    # ✅ UPDATED STATUS CHOICES
    STATUS_CHOICES = [
            ('fully_allocated', 'Fully Allocated'),      # ✅
            ('partially_allocated', 'Partially Allocated'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ]
    
    # ... all your existing fields ...
    
    imported_farmer = models.ForeignKey(
        'ImportedFarmer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocations'
    )
    
    job_activity = models.ForeignKey(
        JobActivity, 
        on_delete=models.CASCADE, 
        related_name='allocations'
    )

    farmer_poc_id = models.IntegerField(null=True, blank=True)
    farmer_poc = models.CharField(max_length=100, blank=True, null=True)
    
    labour_poc_id = models.IntegerField(null=True, blank=True)
    labour_poc = models.CharField(max_length=100, blank=True, null=True)
    
    field_poc_id = models.IntegerField(null=True, blank=True)
    field_poc = models.CharField(max_length=100, blank=True, null=True)
    
    farmer_name = models.CharField(max_length=255, blank=True, null=True)
    farmer_contact = models.CharField(max_length=20, blank=True, null=True)
    
    mukkadam_id = models.IntegerField(
        help_text="Mukkadam ID from external service"
    )
    imported_mukkadam = models.ForeignKey(
        'ImportedMukkadam',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocations'
    )
    
    imported_transporter = models.ForeignKey(
        'ImportedTransporter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocations'
    )
    
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
    
    mukkadam_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2
    )
    
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
    
    allocated_at = models.DateTimeField(auto_now_add=True)
    allocated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=25,  # ✅ Increased to fit 'partially_allocated'
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
            models.Index(fields=['farmer_name']),
        ]
    
    @property
    def total_cost(self):
        mukkadam = self.mukkadam_price or 0
        transport = self.transport_price or 0
        return mukkadam + transport
    
    @property
    def farmer_work_id(self):
        return self.job_activity.farmer_work_id or self.job_activity.job_id
    
    @property
    def created_by(self):
        return self.allocated_by
    
    def __str__(self):
        return f"{self.job_activity.job_id} - {self.job_activity.activity_name} - Mukkadam #{self.mukkadam_id}"
    
    def save(self, *args, **kwargs):
        # Sync transport_price
        if self.transport_type == 'own':
            self.transport_price = self.own_transport_price or 0
        elif self.transport_type == 'none':
            self.transport_price = 0
        
        # ✅ AUTO-UPDATE status based on activity allocation coverage
        job_activity = self.job_activity
        total_area = job_activity.total_area
        
        from django.db.models import Sum
        from decimal import Decimal
        
        # Calculate total allocated area for this activity (including this allocation)
        other_allocations_area = Allocation.objects.filter(
            job_activity=job_activity
        ).exclude(
            id=self.id
        ).aggregate(
            total=Sum('allocated_area')
        )['total'] or Decimal('0')
        
        total_allocated = other_allocations_area + (self.allocated_area or Decimal('0'))
        
        # ✅ Set status based on total coverage
        if self.status in ['allocated', 'partially_allocated', 'fully_allocated']:  # Only auto-update these statuses
            if total_allocated >= total_area:
                self.status = 'fully_allocated'
            else:
                self.status = 'partially_allocated'
        
        super().save(*args, **kwargs)
        
        # ✅ AFTER SAVE: Update ALL other allocations for the same activity
        if self.status == 'fully_allocated':
            # If this activity is now fully allocated, update ALL allocations
            Allocation.objects.filter(
                job_activity=job_activity
            ).exclude(
                id=self.id
            ).exclude(
                status__in=['completed', 'in_progress', 'cancelled']  # Don't override these
            ).update(
                status='fully_allocated'
            )


class ImportBatch(models.Model):
    """Track import operations"""
    batch_id = models.CharField(max_length=50, unique=True)
    filename = models.CharField(max_length=255)
    imported_at = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    total_records = models.IntegerField(default=0)
    successful_imports = models.IntegerField(default=0)
    failed_imports = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ])

# models.py - UPDATED ImportedJobSheet
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

@receiver(post_save, sender=Allocation)
def update_allocation_relationships(sender, instance, created, **kwargs):
    """
    Auto-link Allocation to ImportedMukkadam and ImportedTransporter
    This runs AFTER allocation is saved
    """
    if created:  # Only run on creation
        print(f"🔗 Signal triggered for Allocation #{instance.id}")
        
        # ✅ Link to ImportedMukkadam if not already linked
        if not instance.imported_mukkadam and instance.mukkadam_id:
            try:
                mukkadam = ImportedMukkadam.objects.filter(
                    external_mukkadam_id=instance.mukkadam_id
                ).first()
                
                if mukkadam:
                    instance.imported_mukkadam = mukkadam
                    print(f"   ✅ Linked to mukkadam: {mukkadam.team_name}")
                else:
                    print(f"   ⚠️ Mukkadam {instance.mukkadam_id} not found in ImportedMukkadam")
            except Exception as e:
                print(f"   ❌ Error linking mukkadam: {str(e)}")
        
        # ✅ Link to ImportedTransporter if provider type
        if (instance.transport_type == 'provider' and 
            not instance.imported_transporter and 
            instance.transport_provider_id):
            try:
                transporter = ImportedTransporter.objects.filter(
                    external_transporter_id=instance.transport_provider_id
                ).first()
                
                if transporter:
                    instance.imported_transporter = transporter
                    print(f"   ✅ Linked to transporter: {transporter.name}")
                else:
                    print(f"   ⚠️ Transporter {instance.transport_provider_id} not found")
            except Exception as e:
                print(f"   ❌ Error linking transporter: {str(e)}")
        
        # ✅ Link to ImportedFarmer
        if not instance.imported_farmer and instance.job_activity:
            farmer_id = instance.job_activity.farmer_work_id
            if farmer_id:
                try:
                    farmer = ImportedFarmer.objects.filter(
                        external_farmer_id=farmer_id
                    ).first()
                    
                    if farmer:
                        instance.imported_farmer = farmer
                        instance.farmer_name = farmer.name
                        instance.farmer_contact = farmer.contact_no
                        print(f"   ✅ Linked to farmer: {farmer.name}")
                except Exception as e:
                    print(f"   ❌ Error linking farmer: {str(e)}")
        
        # Save if any relationships were updated
        if (instance.imported_mukkadam or 
            instance.imported_transporter or 
            instance.imported_farmer):
            instance.save(update_fields=[
                'imported_mukkadam', 
                'imported_transporter', 
                'imported_farmer',
                'farmer_name',
                'farmer_contact'
            ])
            print(f"   💾 Relationships saved")
class ImportedJob(models.Model):
    """
    Parent model: One Job (from webhook)
    Stores job-level data
    """
    # ========================================
    # JOB IDENTIFICATION
    # ========================================
    external_job_id = models.IntegerField(
        unique=True, 
        db_index=True,
        null = True,
        blank=True,
        help_text="Job ID from external OPS API"
    )

    BOOKING_TYPE_CHOICES = [
        ('TENDER', 'Tender'),
        ('ON_DEMAND', 'On Demand'),
    ]
    booking_type = models.CharField(
        max_length=20,
        choices=BOOKING_TYPE_CHOICES,
        default='ON_DEMAND',
        help_text="Tender vs On-demand booking type",null=True,blank = True
    )

    generated_job_id = models.CharField(
        max_length=100, 
        unique=True,
        db_index=True,
        help_text="Internal job ID (e.g., JOB-637)"
    )
    
    # ========================================
    # JOB-LEVEL DATA
    # ========================================
    farmer_id = models.CharField(max_length=100, db_index=True)
    plot_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, help_text="PENDING, BOOKED, etc")
    priority = models.CharField(max_length=20, help_text="HIGH, MEDIUM, LOW")
    scheduled_date = models.DateField(null=True, blank=True)
    is_field_verified = models.BooleanField(default=False)
    
    # Notes
    activity_notes = models.TextField(blank=True,null = True)
    internal_notes = models.TextField(blank=True,null = True)
    
    # Total job amount (sum of all activities)
    total_activities_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # ========================================
    # BOOKING DATA
    # ========================================
    booking_id = models.IntegerField(null=True, blank=True, db_index=True)
    booking_status = models.CharField(max_length=50, blank=True)
    booking_total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_advance_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    assignee_number = models.CharField(max_length=20, blank=True)
    
    # ========================================
    # FARMER INFO (Cache from ImportedFarmer)
    # ========================================
    farmer_name = models.CharField(max_length=255, blank=True)
    farmer_contact = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    # Link to ImportedFarmer
    # ✅ Add ForeignKey to ImportedFarmer
    imported_farmer = models.ForeignKey(
        ImportedFarmer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs'
    )
    # ========================================
    # RAW DATA STORAGE
    # ========================================
    raw_booking_data = models.JSONField(null=True, blank=True)
    raw_visits_data = models.JSONField(null=True, blank=True)
    raw_payments_data = models.JSONField(null=True, blank=True)
    raw_full_payload = models.JSONField(null=True, blank=True)
    
    # ========================================
    # TRACKING
    # ========================================
    created_at = models.DateTimeField()
    last_webhook_sync = models.DateTimeField(auto_now=True)
    webhook_update_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['external_job_id']),
            models.Index(fields=['generated_job_id']),
            models.Index(fields=['farmer_id']),
            models.Index(fields=['status']),
            models.Index(fields=['booking_id']),
        ]
    
    def __str__(self):
        return f"Job #{self.generated_job_id} - Farmer {self.farmer_id}"
    
    @property
    def activity_count(self):
        """Count of activities in this job"""
        return self.activities.count()


class ImportedJobSheet(models.Model):
    """
    Child model: One Activity (belongs to ImportedJob)
    Stores activity-specific data
    """
    total_booking_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # ✅ ADD THIS
    # ========================================
    # LINK TO PARENT JOB (ONE-TO-MANY)
    # ========================================
    imported_job = models.ForeignKey(
        ImportedJob,
        on_delete=models.CASCADE,
        related_name='activities',
        help_text="Parent job this activity belongs to",
        null = True,blank = True
    )
    
    # ========================================
    # SOURCE TRACKING
    # ========================================
    SOURCE_CHOICES = [
        ('sheet_import', 'Sheet Import'),
        ('external_api', 'External API'),
        ('manual', 'Manual Entry')
    ]
    data_source = models.CharField(
        max_length=20, 
        choices=SOURCE_CHOICES, 
        default='sheet_import',
        db_index=True
    )
    BOOKING_TYPE_CHOICES = [
        ('TENDER', 'Tender'),
        ('ON_DEMAND', 'On Demand'),
    ]
    booking_type = models.CharField(
        max_length=20,
        choices=BOOKING_TYPE_CHOICES,
        default='ON_DEMAND',
        help_text="Tender vs On-demand booking type",null=True,blank = True
    )
    # ========================================
    # ACTIVITY IDENTIFICATION
    # ========================================
    external_activity_id = models.IntegerField(
        unique=True,
        db_index=True,
        null = True,
        blank=True,
        help_text="Activity ID from external OPS API"
    )
    
    # ========================================
    # ACTIVITY DATA
    # ========================================
    activity_name = models.CharField(max_length=255)
    activity_datetime = models.DateTimeField(null=True, blank=True)
    activity_start_date = models.DateField(null=True, blank=True)
    
    acres = models.CharField(max_length=255)
    
    # Activity pricing breakdown
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    other_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    activity_note = models.TextField(blank=True)
    crop_bundles = models.JSONField(null=True, blank=True)
    
    # ========================================
    # SHEET IMPORT FIELDS (for backward compatibility)
    # ========================================
    import_batch = models.ForeignKey(
        ImportBatch, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    # Legacy fields for sheet imports
    farmer_name = models.CharField(max_length=255, blank=True)
    farmer_contact = models.CharField(max_length=20, blank=True)
    finalised_rate_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variety = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    google_maps_link = models.URLField(blank=True)
    
    # Allocation data from sheet
    labour_team_name = models.CharField(max_length=255, blank=True)
    team_count = models.IntegerField(null=True, blank=True)
    allocation_status = models.CharField(max_length=100, blank=True)
    labour_rates = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    transporter_name = models.CharField(max_length=255, blank=True)
    transport_rates = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # POC fields
    farmer_poc = models.CharField(max_length=100, blank=True)
    labour_poc = models.CharField(max_length=100, blank=True)
    field_poc = models.CharField(max_length=100, blank=True)
    bi_poc_assigned = models.CharField(max_length=100, blank=True)
    
    # Remarks
    allocation_team_remarks = models.TextField(blank=True)
    field_team_remarks = models.TextField(blank=True)
    
    # ========================================
    # GENERATED IDs
    # ========================================
    generated_job_id = models.CharField(max_length=100, db_index=True, blank=True)
    generated_farmer_id = models.CharField(max_length=100, blank=True)
    generated_mukkadam_id = models.IntegerField(null=True, blank=True)
    generated_transporter_id = models.IntegerField(null=True, blank=True)
    
    # ========================================
    # RELATIONSHIPS
    # ========================================
    job_activity = models.ForeignKey(
        JobActivity, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='imported_sheet_record'
    )
    
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_sheet_record'
    )
    
    # ========================================
    # IMPORT TRACKING
    # ========================================
    import_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('imported', 'Imported'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped')
    ], default='pending')
    import_error = models.TextField(blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-activity_start_date']
        indexes = [
            models.Index(fields=['external_activity_id']),
            models.Index(fields=['generated_job_id']),
            models.Index(fields=['data_source']),
            models.Index(fields=['activity_start_date']),
        ]
    
    def __str__(self):
        if self.data_source == 'external_api':
            return f"Activity #{self.external_activity_id} - {self.activity_name} (Job {self.imported_job.generated_job_id})"
        else:
            return f"Sheet: {self.generated_job_id} - {self.activity_name}"
    
    def save(self, *args, **kwargs):
        # Auto-populate generated_job_id from parent job
        if self.imported_job:
            self.generated_job_id = self.imported_job.generated_job_id
        super().save(*args, **kwargs)

    @property
    def acres_numeric(self):
        """
        Try to extract numeric value from acres field
        Returns decimal or 0 if can't parse
        """
        try:
            # Extract first number from string like "7 Labours" or "1.5"
            import re
            match = re.search(r'[\d.]+', self.acres)
            if match:
                return Decimal(match.group())
            return Decimal(0)
        except:
            return Decimal(0)
        
    from decimal import Decimal, InvalidOperation

    def save(self, *args, **kwargs):
        if self.imported_job:
            self.generated_job_id = self.imported_job.generated_job_id

        def to_decimal(value):
            if value in (None, '', 'null'):
                return Decimal('0')
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError):
                return Decimal('0')

        labour = to_decimal(self.labour_rates)
        transport = to_decimal(self.transport_rates)
        other = to_decimal(self.other_cost)

        self.subtotal = labour + transport + other
        self.total_price = self.subtotal

        super().save(*args, **kwargs)


# models.py
from django.db import models
from decimal import Decimal

class FarmerPayment(models.Model):
    """Track all payments made to farmers from demand sheet"""
    
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ]
    
    PAYMENT_ROUTE_CHOICES = [
        ('cheque', 'Cheque'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('zoho', 'Zoho'),
        ('other', 'Other'),
    ]
    
    # Link to ImportedFarmer
    imported_farmer = models.ForeignKey(
        'ImportedFarmer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='farmer_payments'
    )
    
    # Link to JobActivity (matched by date, farmer, activity, booking value)
    job_activity = models.ForeignKey(
        'JobActivity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='farmer_payments'
    )
    
    # Original data from demand sheet
    activity_date = models.DateField()
    village = models.CharField(max_length=255, blank=True)
    farmer_name = models.CharField(max_length=255)
    activity_name = models.CharField(max_length=255)
    acres = models.CharField(max_length=50, blank=True)
    booking_rate_per_acre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exact_bundles_used = models.CharField(max_length=100, blank=True)
    
    # Payment amounts
    booking_value = models.DecimalField(max_digits=10, decimal_places=2)
    transportation_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Payment details
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    payment_route = models.CharField(max_length=50, choices=PAYMENT_ROUTE_CHOICES, blank=True)
    date_of_payment = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    reference_no = models.CharField(max_length=255, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Matching status
    is_matched = models.BooleanField(default=False, help_text="Matched with JobActivity")
    match_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['farmer_name']),
            models.Index(fields=['activity_date']),
            models.Index(fields=['payment_status']),
        ]
    
    def __str__(self):
        return f"{self.farmer_name} - {self.activity_date} - ₹{self.booking_value}"
    
    @property
    def calculated_total(self):
        """Calculate total value"""
        booking = self.booking_value or Decimal('0')
        transport = self.transportation_cost or Decimal('0')
        return booking + transport

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
        ('activity_marked_edited', 'Activity Edited'),  # ✅ ADD THIS
        ('activity_marked_lost', 'Activity Marked Lost'),  # ✅ ADD THIS (if you use it)
        ('activity_marked_restored', 'Activity Restored'),  
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
        ('web_dialpad','Web')
    ]
    
    # Primary identifiers
    call_sid = models.CharField(max_length=100, unique=True, db_index=True)
    user_id = models.CharField(max_length=100, blank=True, default='system')
    mobile_number = models.CharField(max_length=15)
    from_number = models.CharField(max_length=20)
    
    # Call metadata
    purpose = models.CharField(max_length=20, choices=CALL_PURPOSE_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='pending')
    direction = models.CharField(max_length=20, default='outbound')
    state = models.CharField(max_length=20, blank=True)
    
    # Call metrics
    duration = models.IntegerField(null=True, blank=True, help_text="Total duration in seconds")
    talk_time = models.IntegerField(null=True, blank=True, help_text="Actual talk time in seconds")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Recording
    recording_url = models.URLField(blank=True, null=True)
    recording_urls = models.JSONField(default=list, blank=True, help_text="Array of recording URLs")
    s3_key = models.CharField(max_length=500, blank=True, null=True, help_text="S3 key for recording")  # ✅ NEW
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_time = models.DateTimeField(null=True, blank=True)
    updated_time = models.DateTimeField(null=True, blank=True)
    
    # Exotel specific
    virtual_number = models.CharField(max_length=20, blank=True)
    custom_field = models.CharField(max_length=255, blank=True)
    legs_url = models.CharField(max_length=500, blank=True)
    
    # Extra context
    job_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    webhook_data = models.JSONField(default=dict, blank=True, help_text="Full webhook response")
    
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
        return bool(self.recording_url or self.recording_urls or self.s3_key)  # ✅ UPDATED
    
    @property
    def primary_recording_url(self):
        """Get the primary recording URL"""
        if self.recording_url:
            return self.recording_url
        if self.recording_urls and len(self.recording_urls) > 0:
            return self.recording_urls[0]
        return None
    
    def _get_presigned_url(self, s3_key):
        """Internal helper to fetch presigned URL from external service"""
        if not s3_key:
            return None
        
        try:
            presign_url = 'https://demand.bharatintelligence.ai/chat/presign_obj_api/'
            response = requests.get(
                presign_url,
                params={'key': s3_key},
                # Note: Consider moving this token to settings.py for security
                headers={'Authorization': 'Token c432208626a204d2d8de3d00b29f948eae61ebdb'},
                timeout=10 # Reduced timeout for better UX
            )
            
            if response.status_code == 200:
                data = response.json()
                # Handle both dictionary response or direct string
                return data.get('url') if isinstance(data, dict) else data
            return None
                
        except Exception as e:
            logger.error(f"Error getting presigned URL for {s3_key}: {e}")
            return None

    @property
    def audio_url(self):
        """
        The dynamic property for the frontend.
        Priority: 1. Presigned S3 Link, 2. Direct Recording URL
        """
        if self.s3_key:
            return self._get_presigned_url(self.s3_key)
        return self.primary_recording_url
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