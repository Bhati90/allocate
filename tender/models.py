from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import json

from django.core.exceptions import ValidationError

# ============================================================================
# MASTER DATA MODELS
# ============================================================================

class ActivityCatalog(models.Model):
    """
    Master catalog of all activities (from API + custom added from frontend)
    """
    name = models.CharField(max_length=200, unique=True)
    activity_type = models.CharField(max_length=100, blank=True)  # pruning, harvesting, etc.
    default_rate_per_acre = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    is_strict = models.BooleanField(
        default=False,
        help_text="Strict activities must be completed on scheduled date and before other activities"
    )
    estimated_workers_per_acre = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Estimated workers needed per acre"
    )
    source = models.CharField(
        max_length=20,
        choices=[('api', 'From API'), ('custom', 'Custom Added')],
        default='api'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    default_gap_days = models.PositiveIntegerField(default=3)
    
    class Meta:
        db_table = 'activity_catalog'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_strict']),
        ]
    
    def __str__(self):
        return f"{self.name} {'(Strict)' if self.is_strict else ''}"

class Cluster(models.Model):
    name = models.CharField(max_length=100, unique=True)

    state_code = models.CharField(max_length=10, blank=True, null=True)
    
    # Change to JSONField for multiple selections
    district_codes = models.JSONField(default=list, blank=True)  # List of district codes
    taluka_codes = models.JSONField(default=list, blank=True)    # List of taluka codes
    village_codes = models.JSONField(default=list, blank=True)   # List of village codes

    # Store names for display
    districts = models.JSONField(default=list, blank=True)  # List of district names
    talukas = models.JSONField(default=list, blank=True)    # List of taluka names
    villages = models.JSONField(default=list, blank=True)   # List of village names

    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    # Helper properties for backward compatibility
    @property
    def district(self):
        return ', '.join(self.districts) if self.districts else ''
    
    @property
    def taluka(self):
        return ', '.join(self.talukas) if self.talukas else ''
    
    @property
    def village(self):
        return ', '.join(self.villages) if self.villages else ''
# ============================================================================
# JOB/BOOKING MODELS
# ============================================================================
class Farmer(models.Model):
    """
    Farmer information (synced from API)
    """
    farmer_id = models.CharField(max_length=50, unique=True, primary_key=True)
    farmer_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20, blank=True)

    # only cluster, derive location from it
    cluster = models.ForeignKey(
        Cluster, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='farmers'
    )

    location = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farmers'

    @property
    def village(self):
        return self.cluster.village if self.cluster else ''

    @property
    def taluka(self):
        return self.cluster.taluka if self.cluster else ''

    @property
    def district(self):
        return self.cluster.district if self.cluster else ''

    def __str__(self):
        return f"{self.farmer_name} ({self.farmer_id})"

class Plot(models.Model):
    farmer = models.ForeignKey(
        Farmer, on_delete=models.CASCADE, related_name='plots'
    )
    cluster = models.ForeignKey(
        Cluster, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='plots'
    )

    name = models.CharField(max_length=100)  # e.g. "Plot 1", "Bagal Wadi"
    area_acres = models.DecimalField(max_digits=10, decimal_places=2)

    # optional: geo / code
    plot_code = models.CharField(max_length=50, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'plots'
        unique_together = ('farmer', 'name')

    def __str__(self):
        return f"{self.farmer.farmer_name} - {self.name}"
class ClusterActivityRate(models.Model):
    """
    Cluster-specific default rate for activities
    """
    cluster = models.ForeignKey(
        Cluster, on_delete=models.CASCADE, related_name='activity_rates'
    )
    activity = models.ForeignKey(
        ActivityCatalog, on_delete=models.CASCADE, related_name='cluster_rates'
    )
    rate_per_acre = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cluster_activity_rates'
        unique_together = ['cluster', 'activity']
    
    def __str__(self):
        return f"{self.cluster.name} - {self.activity.name}: ₹{self.rate_per_acre}/ac"

class Job(models.Model):
    job_id = models.CharField(max_length=50, unique=True, primary_key=True)
    work_id = models.CharField(max_length=50)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='jobs')
    crop_name = models.CharField(max_length=100, blank=True, default='')
    variety = models.CharField(max_length=100, blank=True, default='')
    plot = models.ForeignKey(
        Plot, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='jobs'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('partial', 'Partial'),
            ('paid', 'Paid'),
        ],
        default='pending',
        blank=True
    )
    cluster = models.ForeignKey(
        Cluster, null=True, blank=True,
        on_delete=models.SET_NULL
    )
    booking_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )

    priority = models.CharField(
        max_length=20,
        choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('URGENT', 'Urgent')],
        default='MEDIUM'
    )

    completed_date = models.DateField(null=True, blank=True)

    scheduled_date = models.DateField(null=True, blank=True)
    booking_type = models.CharField(max_length=50, default='Tender')

    activity_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    total_activities_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    is_field_verified = models.BooleanField(default=False)
    is_complex = models.BooleanField(default=False)
    point_of_contact = models.CharField(max_length=200, blank=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    api_raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['scheduled_date']),
            models.Index(fields=['booking_type']),
        ]

    def __str__(self):
        return f"{self.job_id} - {self.farmer.farmer_name}"

# models.py
class JobActivity(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='activities')
    activity = models.ForeignKey(ActivityCatalog, on_delete=models.PROTECT, related_name='job_activities')

    # which plot this activity is on
    plot = models.ForeignKey(
        Plot, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activities'
    )

    is_strict = models.BooleanField(default=False)

    total_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    allocated_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    remaining_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    crop_bundles = models.IntegerField(default=0)

    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    estimated_workers = models.IntegerField(default=10)

    rate_per_acre = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    allocation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('partially_allocated', 'Partially Allocated'),
            ('fully_allocated', 'Fully Allocated'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='pending'
    )

    is_fully_allocated = models.BooleanField(default=False)
    is_manually_edited = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    lost_reason = models.TextField(blank=True)

    location = models.CharField(max_length=255, default='N/A')

    api_activity_id = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_activities'
        ordering = ['scheduled_date', 'activity__is_strict']
        indexes = [
            models.Index(fields=['allocation_status']),
            models.Index(fields=['scheduled_date']),
            models.Index(fields=['is_fully_allocated']),
        ]

    def __str__(self):
        return f"{self.job.job_id} - {self.activity.name} ({self.remaining_area}ac remaining)"

    def clean(self):
        # enforce area <= plot size if plot is set
        if self.plot and self.total_area and self.plot.area_acres:
            if self.total_area > self.plot.area_acres:
                raise ValidationError(
                    {"total_area": f"Total area {self.total_area} ac cannot exceed plot size {self.plot.area_acres} ac"}
                )

    def save(self, *args, **kwargs):
        from decimal import Decimal, ROUND_HALF_UP
        
        self.remaining_area = self.total_area - self.allocated_area

        # status
        if self.allocated_area == 0:
            self.allocation_status = 'pending'
            self.is_fully_allocated = False
        elif self.allocated_area >= self.total_area:
            self.allocation_status = 'fully_allocated'
            self.is_fully_allocated = True
        else:
            self.allocation_status = 'partially_allocated'
            self.is_fully_allocated = False

        # price - ROUND TO 2 DECIMAL PLACES
        self.total_price = (self.total_area * self.rate_per_acre).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.subtotal = (self.total_price + self.transport_cost + self.other_cost).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        self.full_clean()
        super().save(*args, **kwargs)


class JobBooking(models.Model):
    """
    Booking/Payment information for a job
    """
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='booking')
    booking_id = models.BigIntegerField(unique=True)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('UNPAID', 'Unpaid'),
            ('PARTIALLY_PAID', 'Partially Paid'),
            ('PAID', 'Paid'),
            ('REFUNDED', 'Refunded'),
        ],
        default='UNPAID'
    )
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    assignee_number = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_bookings'
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.job.job_id}"


class FarmerPayment(models.Model):
    """
    Payment received from farmer (multiple payments possible)
    """
    booking = models.ForeignKey(JobBooking, on_delete=models.CASCADE, related_name='payments')
    payment_id = models.BigIntegerField(unique=True)
    
    mode = models.CharField(
        max_length=50,
        choices=[
            ('CASH', 'Cash'),
            ('UPI', 'UPI'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('CHEQUE', 'Cheque'),
            ('WILL_PAY_LATER', 'Will Pay Later'),
            ('OTHER', 'Other'),
        ],
        default='CASH'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    paid_status = models.BooleanField(default=True)
    paid_at = models.DateTimeField()
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'farmer_payments'
        ordering = ['-paid_at']
    
    def __str__(self):
        return f"₹{self.amount} - {self.mode} - {self.paid_at.date()}"

class ActivityScheduleRule(models.Model):
    """
    Global default schedule rules per activity.
    Example: do 'Pruning' every 3 days after planting.
    """
    activity = models.OneToOneField(
        ActivityCatalog, on_delete=models.CASCADE, related_name='global_schedule'
    )
    gap_days = models.PositiveIntegerField(default=3)

    # optional: order/phase number in lifecycle
    phase_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.activity.name} every {self.gap_days} days"


class ClusterActivityScheduleRule(models.Model):
    """
    Per-cluster override for activity scheduling gap.
    """
    cluster = models.ForeignKey(
        Cluster, on_delete=models.CASCADE, related_name='activity_schedule_overrides'
    )
    activity = models.ForeignKey(
        ActivityCatalog, on_delete=models.CASCADE, related_name='cluster_schedule_overrides'
    )
    gap_days = models.PositiveIntegerField()

    class Meta:
        unique_together = ('cluster', 'activity')

    def __str__(self):
        return f"{self.cluster.name} - {self.activity.name}: {self.gap_days} days"
    

def effective_gap_days(cluster, activity):
    override = ClusterActivityScheduleRule.objects.filter(
        cluster=cluster, activity=activity
    ).first()
    if override:
        return override.gap_days
    return ActivityScheduleRule.objects.get(activity=activity).gap_days

# ============================================================================
# MUKKADAM (TEAM) MODELS
# ============================================================================

class Mukkadam(models.Model):
    """
    Mukkadam/Labor contractor information (synced from API)
    """
    mukkadam_id = models.BigIntegerField(unique=True, primary_key=True)
    mukkadam_name = models.CharField(max_length=200)
    mobile_numbers = models.CharField(max_length=100)
    cluster = models.ForeignKey(Cluster, null=True, blank=True,
                                on_delete=models.SET_NULL)
    
    is_permanent = models.BooleanField(default=False)
    
    # Location
    district = models.CharField(max_length=100, blank=True)
    taluka = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    current_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    # Availability
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Crew information
    crew_size = models.IntegerField(default=0)
    has_smartphone = models.CharField(max_length=10, default='no')
    work_mode = models.CharField(max_length=50, blank=True)
    
    # Rate cards (from API)
    rate_card = models.JSONField(default=dict, blank=True)
    tender_activities = models.JSONField(default=dict, blank=True)
    
    # API raw data
    api_raw_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mukkadams'
        ordering = ['mukkadam_name']
    
    def __str__(self):
        return f"{self.mukkadam_name} (Crew: {self.crew_size})"

# models.py - Add new model

class ClusterMukkadamActivityRate(models.Model):
    """
    Cluster-level default mukkadam rate for activities
    Used as default when creating new mukkadams in this cluster
    """
    cluster = models.ForeignKey(
        Cluster, 
        on_delete=models.CASCADE, 
        related_name='mukkadam_activity_defaults'
    )
    activity = models.ForeignKey(
        ActivityCatalog, 
        on_delete=models.CASCADE, 
        related_name='cluster_mukkadam_defaults'
    )
    rate_per_acre = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    productivity_per_worker = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=0.150,
        validators=[MinValueValidator(0)],
        help_text="Default efficiency (acres per worker per day)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cluster_mukkadam_activity_rates'
        unique_together = ['cluster', 'activity']
        indexes = [
            models.Index(fields=['cluster', 'activity']),
        ]
    
    def __str__(self):
        return f"{self.cluster.name} - {self.activity.name}: ₹{self.rate_per_acre}/ac (Mukkadam Default)"

class MukkadamActivityRate(models.Model):
    """
    Mukkadam-specific rate for activities
    Falls back to cluster rate, then global default
    """
    mukkadam = models.ForeignKey(
        'Mukkadam', 
        on_delete=models.CASCADE, 
        related_name='activity_rates'
    )
    activity = models.ForeignKey(
        ActivityCatalog, 
        on_delete=models.CASCADE, 
        related_name='mukkadam_rates'
    )
    rate_per_acre = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    productivity_per_worker = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=0.150,
        validators=[MinValueValidator(0)],
        help_text="Acres per worker per day"
    )
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mukkadam_activity_rates'
        unique_together = ['mukkadam', 'activity']
        indexes = [
            models.Index(fields=['mukkadam', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.mukkadam.mukkadam_name} - {self.activity.name}: ₹{self.rate_per_acre}/ac"

class MukkadamAvailability(models.Model):
    """
    Day-wise availability for mukkadam
    Priority: DB data > API data
    """
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='daily_availability')
    date = models.DateField()
    
    # Crew configuration for this day
    available_crew_size = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Override crew size for this specific day"
    )
    
    is_available = models.BooleanField(default=True)
    is_on_leave = models.BooleanField(default=False)
    
    # Capacity tracking
    allocated_workers = models.IntegerField(default=0)
    remaining_capacity = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    # Override tracking
    is_manually_set = models.BooleanField(
        default=False,
        help_text="If True, this overrides API availability data"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mukkadam_availability'
        unique_together = ['mukkadam', 'date']
        ordering = ['date']
        indexes = [
            models.Index(fields=['mukkadam', 'date']),
            models.Index(fields=['date', 'is_available']),
        ]
    
    def __str__(self):
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.mukkadam.mukkadam_name} - {self.date}: {status} ({self.remaining_capacity}/{self.available_crew_size})"
    
    def save(self, *args, **kwargs):
        # Auto-calculate remaining capacity
        self.remaining_capacity = self.available_crew_size - self.allocated_workers
        super().save(*args, **kwargs)


# ============================================================================
# ALLOCATION & SCHEDULING MODELS
# ============================================================================

class Allocation(models.Model):
    """
    Core allocation model - assigns job activities to mukkadams
    """
    job_activity = models.ForeignKey(JobActivity, on_delete=models.CASCADE, related_name='allocations')
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='allocations')
    cluster = models.ForeignKey(Cluster, null=True, blank=True,
                                on_delete=models.SET_NULL)
    # Allocation details
    allocated_date = models.DateField()
    allocated_area = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    allocated_workers = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of workers from this mukkadam's crew"
    )
    
    # Pricing
    farmer_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Rate charged to farmer per acre"
    )
    mukkadam_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Rate paid to mukkadam per acre"
    )
    
    # Calculated amounts
    farmer_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total amount to charge farmer (allocated_area * farmer_rate)"
    )
    mukkadam_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total amount to pay mukkadam (allocated_area * mukkadam_rate)"
    )
    profit = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Profit/Loss (farmer_amount - mukkadam_amount)"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='scheduled'
    )
    
    # Performance tracking
    actual_workers = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Actual workers who showed up"
    )
    actual_area_completed = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual area completed"
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    efficiency_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Performance score (0-100)"
    )
    
    notes = models.TextField(blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='allocations_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'allocations'
        ordering = ['allocated_date', '-created_at']
        indexes = [
            models.Index(fields=['allocated_date', 'status']),
            models.Index(fields=['mukkadam', 'allocated_date']),
            models.Index(fields=['job_activity', 'status']),
        ]
    
    def __str__(self):
        return f"{self.job_activity.job.job_id} - {self.job_activity.activity.name} → {self.mukkadam.mukkadam_name} ({self.allocated_date})"
    
    def save(self, *args, **kwargs):
        # Auto-calculate amounts
        self.farmer_amount = self.allocated_area * self.farmer_rate
        self.mukkadam_amount = self.allocated_area * self.mukkadam_rate
        self.profit = self.farmer_amount - self.mukkadam_amount
        
        # Calculate efficiency if completed
        if self.status == 'completed' and self.actual_area_completed:
            expected = float(self.allocated_area)
            actual = float(self.actual_area_completed)
            if expected > 0:
                self.efficiency_score = Decimal((actual / expected) * 100)
        
        super().save(*args, **kwargs)


class MukkadamPayment(models.Model):
    """
    Payments made to mukkadam (can be for one or multiple allocations)
    """
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='payments')
    allocations = models.ManyToManyField(Allocation, related_name='mukkadam_payments', blank=True)
    
    payment_id = models.CharField(max_length=50, unique=True)
    
    mode = models.CharField(
        max_length=50,
        choices=[
            ('CASH', 'Cash'),
            ('UPI', 'UPI'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('CHEQUE', 'Cheque'),
            ('WILL_PAY_LATER', 'Will Pay Later'),
            ('OTHER', 'Other'),
        ],
        default='CASH'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    
    paid_at = models.DateTimeField()
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mukkadam_payments'
        ordering = ['-paid_at']
    
    def __str__(self):
        return f"₹{self.amount} to {self.mukkadam.mukkadam_name} - {self.paid_at.date()}"

# models.py
class ActivityLogTender(models.Model):
    ACTION_CHOICES = [
        ('JOB_ACTIVITY_CREATED', 'Job activity created'),
        ('JOB_ACTIVITY_UPDATED', 'Job activity updated'),
    ]

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='activity_logs')
    job_activity = models.ForeignKey(
        JobActivity, on_delete=models.CASCADE,
        related_name='activity_logs', null=True, blank=True
    )
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-created_at']

# ============================================================================
# AUDIT & LOGGING MODELS
# ============================================================================

class ExtraWorker(models.Model):
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE)
    date = models.DateField()
    workers = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ('mukkadam', 'date')

class Leave(models.Model):
    """
    Model for tracking mukkadam leaves and general holidays
    """
    LEAVE_TYPE_CHOICES = [
        ('mukkadam', 'Mukkadam Leave'),
        ('general', 'General Holiday'),
    ]
    cluster = models.ForeignKey(Cluster, null=True, blank=True,
                                on_delete=models.SET_NULL)
    date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    mukkadam = models.ForeignKey(
        Mukkadam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='leaves'
    )
    crew_on_leave = models.PositiveIntegerField(
        default=0,
        help_text="Number of workers from this mukkadam's crew on leave"
    )
    reason = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['date', 'leave_type', 'mukkadam']
    
    def __str__(self):
        if self.leave_type == 'general':
            return f"General Holiday - {self.date}"
        return f"{self.mukkadam.mukkadam_name} Leave - {self.date}"


class AllocationChangeLogTender(models.Model):
    """
    Detailed audit log for all allocation changes
    """
    allocation = models.ForeignKey(Allocation, on_delete=models.CASCADE, related_name='change_logs')
    
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('deleted', 'Deleted'),
            ('status_change', 'Status Changed'),
            ('payment_update', 'Payment Updated'),
        ]
    )
    
    field_changed = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    change_reason = models.TextField(blank=True)
    
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    # Snapshot of allocation at time of change
    allocation_snapshot = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'allocation_change_logs'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['allocation', '-changed_at']),
        ]
    
    def __str__(self):
        return f"{self.change_type} - {self.allocation} at {self.changed_at}"


class PaymentChangeLog(models.Model):
    """
    Audit log for payment changes (both farmer and mukkadam)
    """
    payment_type = models.CharField(
        max_length=20,
        choices=[('farmer', 'Farmer Payment'), ('mukkadam', 'Mukkadam Payment')]
    )
    
    # Foreign keys (one will be null)
    farmer_payment = models.ForeignKey(
        FarmerPayment, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='change_logs'
    )
    mukkadam_payment = models.ForeignKey(
        MukkadamPayment, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='change_logs'
    )
    
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('deleted', 'Deleted'),
        ]
    )
    
    field_changed = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    
    change_reason = models.TextField(blank=True)
    
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    payment_snapshot = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'payment_change_logs'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.payment_type} {self.change_type} at {self.changed_at}"


# ============================================================================
# HELPER/UTILITY MODELS
# ============================================================================

class SystemConfiguration(models.Model):
    """
    System-wide configuration and settings
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'system_configuration'
    
    def __str__(self):
        return self.key


class APISync(models.Model):
    """
    Track API synchronization status
    """
    sync_type = models.CharField(
        max_length=20,
        choices=[('jobs', 'Jobs'), ('mukkadams', 'Mukkadams')]
    )
    
    last_sync_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[('success', 'Success'), ('failed', 'Failed'), ('partial', 'Partial')]
    )
    
    records_synced = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'api_sync'
        ordering = ['-last_sync_at']
    
    def __str__(self):
        return f"{self.sync_type} - {self.status} at {self.last_sync_at}"