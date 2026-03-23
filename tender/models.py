from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import json

from django.core.exceptions import ValidationError

# ============================================================================
# MASTER DATA MODELS
# ============================================================================
import requests
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
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

    # In your migrations
    default_productivity_per_worker = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal('0.150'),
        help_text="Global default: acres per worker per day"
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
    # 👇 NEW
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clusters_created',
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clusters_modified',
    )
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

    @property
    def date_range(self):
        """
        Compute start/end dates from all JobActivities 
        linked to jobs in this cluster.
        """
        from django.db.models import Min, Max
        
        result = JobActivity.objects.filter(
            job__clusters=self,
            scheduled_date__isnull=False
        ).aggregate(
            start_date=Min('scheduled_date'),
            end_date=Max('scheduled_date')
        )
        return {
            'start_date': result['start_date'],
            'end_date': result['end_date'],
        }

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

    # ✅ CHANGED: ManyToMany - manual assignment
    clusters = models.ManyToManyField(
        'Cluster',
        blank=True,
        related_name='farmers'
    )

    last_cluster_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='farmers_cluster_modified',
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
    clusters = models.ManyToManyField(
        Cluster, blank=True, related_name='plots'
    )

    name = models.CharField(max_length=100)  # e.g. "Plot 1", "Bagal Wadi"
    area_acres = models.DecimalField(max_digits=10, decimal_places=2)

    crop_name = models.CharField(max_length=100, blank=True)
    variety = models.CharField(max_length=100, blank=True)
    pruning_date = models.DateField(null=True, blank=True)
    # optional: geo / code
    plot_code = models.CharField(max_length=50, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_cluster_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plots_cluster_modified',
    )
    last_cluster_modified_at = models.DateTimeField(null=True, blank=True)

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


import logging

logger = logging.getLogger(__name__)


import requests

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
        db_table = "tender_farmer_calls"
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

class MukkadamOTPRequest(models.Model):
    mukkadam     = models.ForeignKey('Mukkadam', on_delete=models.CASCADE)
    phone        = models.CharField(max_length=15)
    crew_size    = models.PositiveIntegerField(null=True, blank=True)
    allocation   = models.ForeignKey('Allocation', on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    is_used      = models.BooleanField(default=False)

    otp_type = models.CharField(
        max_length=10,
        choices=[('start', 'Start Work'), ('end', 'End Work')],
        default='start'
    )

    class Meta:
        ordering = ['-requested_at']

    def is_expired(self):
        from django.utils import timezone
        return (timezone.now() - self.requested_at).seconds > 600


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
    # ADD this:
    clusters = models.ManyToManyField(
        Cluster, blank=True,
        related_name='jobs'
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
        farmer_name = None
        try:
            if self.farmer_id:
                farmer_name = getattr(self.farmer, "farmer_name", None)
        except Exception:
            farmer_name = None

        if farmer_name:
            return f"{self.job_id} - {farmer_name}"

        if self.crop_name:
            return f"{self.job_id} - {self.crop_name}"

        return str(self.job_id)


# models.py
class JobActivity(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='activities')
    activity = models.ForeignKey(ActivityCatalog, on_delete=models.PROTECT, related_name='job_activities')
    # In JobActivity model, add:
    sales_date = models.DateField(null=True, blank=True, help_text="Expected sales/next activity date based on gap days")
    # which plot this activity is on
    plot = models.ForeignKey(
        Plot, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activities'
    )

    # models.py — JobActivity
    original_gap_days = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Gap in days from the previous activity in sequence at the time this "
            "activity was created. Used for cascade recalculation after a move."
        )
    )


    # In JobActivity model, add this field:
    is_manually_moved = models.BooleanField(default=False)  # ✅ True = moved via H button  

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

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_activities_created',
    )
    last_moved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_activities_moved',
    )
    last_moved_at = models.DateTimeField(
        null=True,
        blank=True,
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

    moved_from_activity = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='moved_children'
    )
    move_reason = models.TextField(blank=True)

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

    source = models.CharField(
        max_length=10,
        choices=[('ai', 'AI'), ('manual', 'Manual')],
        default='ai',
    )
    original_source = models.CharField(      # 🔹 new
        max_length=10,
        choices=[('ai', 'AI'), ('manual', 'Manual')],
        default='ai',
    )
    original_scheduled_date = models.DateField(null=True, blank=True)
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
        
        self.remaining_area = max(Decimal('0'), self.total_area - self.allocated_area)

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

        if not self.sales_date:
            try:
                from datetime import timedelta
                pruning_date = self.job.scheduled_date
                if pruning_date:
                    gap_days = 3

                    clusters = list(self.plot.clusters.all()) if self.plot_id else []
                    if not clusters:
                        clusters = list(self.job.clusters.all())

                    for cluster in clusters:
                        rule = ClusterActivityScheduleRule.objects.filter(
                            cluster=cluster, activity=self.activity
                        ).first()
                        if rule:
                            gap_days = rule.gap_days
                            break
                    else:
                        global_rule = ActivityScheduleRule.objects.filter(
                            activity=self.activity
                        ).first()
                        if global_rule:
                            gap_days = global_rule.gap_days
                        else:
                            gap_days = self.activity.default_gap_days or 3

                    self.sales_date = pruning_date + timedelta(days=gap_days)
            except Exception as e:
                logger.warning(f"Could not calculate sales_date for JA {self.pk}: {e}")



     
        super().save(*args, **kwargs)


# models.py — add this model

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class JobNote(models.Model):

    TAG_CHOICES = [
        ('urgent',          '🔴 Urgent'),
        ('important',       '⚠️ Important'),
        ('mukkadam_issue',  '👷 Mukkadam Issue'),
        ('farmer_issue',    '🌾 Farmer Issue'),
        ('sales',           '💼 Sales'),
        ('operations',      '⚙️ Operations'),
        ('data_wrong',      '📊 Data Wrong'),
        ('price_mismatch',  '💰 Price Mismatch'),
        ('team_charging',   '⚡ Team Charging'),
    ]

    job         = models.ForeignKey(
        'Job', on_delete=models.CASCADE, related_name='notes'
    )
    author      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='job_notes_authored'
    )
    text        = models.TextField()                          # raw text with @username inline
    tags        = models.JSONField(default=list, blank=True)  # list of tag keys e.g. ["urgent","sales"]
    mentions    = models.ManyToManyField(
        User, blank=True, related_name='job_notes_mentioned'
    )

    # Resolution
    is_resolved     = models.BooleanField(default=False)
    resolved_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='job_notes_resolved'
    )
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    # Index by date so DayDetailModal can query notes for a specific day
    note_date   = models.DateField(db_index=True)             # set to job activity scheduled_date on create

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['note_date']),
            models.Index(fields=['is_resolved']),
            models.Index(fields=['job', 'note_date']),
        ]

    def __str__(self):
        return f"Note on {self.job_id} by {self.author} [{', '.join(self.tags)}]"

    def resolve(self, user, resolution_note=''):
        self.is_resolved     = True
        self.resolved_by     = user
        self.resolved_at     = timezone.now()
        self.resolution_note = resolution_note
        self.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at', 'resolution_note', 'updated_at'])

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
        ('ZOHO_PAYMENT', 'Zoho Payment'),   # ← ADD THIS
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
    proof_s3_key = models.CharField(max_length=500, blank=True, null=True,
                                     help_text='S3 key of payment proof image/PDF')

    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'farmer_payments'
        ordering = ['-paid_at']
    
    def __str__(self):
        return f"₹{self.amount} - {self.mode} - {self.paid_at.date()}"


class FarmerPaymentWebhookLog(models.Model):
    """Logs incoming payment webhooks from farmer payment links"""
    
    booking         = models.ForeignKey(JobBooking, on_delete=models.SET_NULL, null=True, blank=True, related_name='webhook_logs')
    booking_ref         = models.CharField(max_length=100)  # ← renamed
    
    # Payment details received
    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    mode            = models.CharField(max_length=50, default='UPI')
    transaction_id  = models.CharField(max_length=255, blank=True, null=True)
    notes           = models.TextField(blank=True, null=True)
    paid_at         = models.DateTimeField(blank=True, null=True)
    
    # What we did
    payment_created = models.BooleanField(default=False)  # did we create FarmerPayment
    farmer_payment  = models.ForeignKey('FarmerPayment', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Raw payload
    raw_payload     = models.JSONField()
    
    # Confirmation webhook we sent back
    confirmation_sent         = models.BooleanField(default=False)
    confirmation_webhook_url  = models.CharField(max_length=500, blank=True, null=True)
    confirmation_status       = models.IntegerField(blank=True, null=True)
    
    status   = models.CharField(max_length=50, default='received')  # received / processed / failed / duplicate
    error    = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Farmer Payment Webhook Log'
        verbose_name_plural = 'Farmer Payment Webhook Logs'

    def __str__(self):
        return f"Booking #{self.booking_id} | ₹{self.amount} | {self.status} | {self.created_at.date()}"
    

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


# models.py

class MukkadamLedgerEntry(models.Model):
    """
    Single flat ledger for all mukkadam payments.
    One row = one payment event (advance, transport, weekly, job payment).
    """

    PAYMENT_TYPE_CHOICES = [
        ('advance', 'Advance'),
        ('transport', 'Transport'),
        ('weekly_payment', 'Weekly Payment'),
        ('per_acre', 'Per Acre (Job)'),
        ('misc', 'Misc'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('pending', 'Pending'),
        ('na', 'NA'),
    ]

    # ── Who ───────────────────────────────────────────────────────────
    mukkadam        = models.ForeignKey(
        'Mukkadam', on_delete=models.CASCADE, related_name='ledger_entries'
    )
    cluster         = models.ForeignKey(
        'Cluster', on_delete=models.SET_NULL, null=True, blank=True
    )

    # ── Farmer & Job (optional — blank for advance/transport/weekly) ──
    farmer_name     = models.CharField(max_length=255, blank=True)
    farmer_contact  = models.CharField(max_length=50, blank=True)
    job             = models.ForeignKey(
        'Job', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries'
    )
    job_activity    = models.ForeignKey(
        'JobActivity', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries'
    )
    activity_name   = models.CharField(max_length=100, blank=True)  # fallback if no FK

    # ── What ──────────────────────────────────────────────────────────
    payment_type    = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    acres           = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Only for per_acre type"
    )
    amount          = models.DecimalField(max_digits=12, decimal_places=2)

    # ── When ──────────────────────────────────────────────────────────
    job_date        = models.DateField(null=True, blank=True, help_text="Date work was done")
    payment_date    = models.DateField(null=True, blank=True, help_text="Date payment was made")

    # ── Status ────────────────────────────────────────────────────────
    payment_status  = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='paid'
    )
    remark          = models.TextField(blank=True)

    # ── Proof ─────────────────────────────────────────────────────────
    proof_s3_key    = models.CharField(max_length=500, blank=True, null=True)

    # ── Audit ─────────────────────────────────────────────────────────
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    created_by      = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        db_table = 'mukkadam_ledger'
        ordering = ['payment_date', 'created_at']

    def __str__(self):
        return f"{self.mukkadam.mukkadam_name} | {self.payment_type} | ₹{self.amount} | {self.payment_date}"
# class Mukkadam(models.Model):
#     """
#     Mukkadam/Labor contractor information (synced from API)
#     """
#     mukkadam_id = models.BigIntegerField(unique=True, primary_key=True)
#     mukkadam_name = models.CharField(max_length=200)
#     mobile_numbers = models.CharField(max_length=100)
#     # ✅ CHANGED: ManyToMany - manual assignment
#     clusters = models.ManyToManyField(
#         'Cluster',
#         blank=True,
#         related_name='mukkadams'
#     )
    
#     is_permanent = models.BooleanField(default=False)
    
#     # Location
#     district = models.CharField(max_length=100, blank=True)
#     taluka = models.CharField(max_length=100, blank=True)
#     village = models.CharField(max_length=100, blank=True)
#     current_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
#     current_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
#     # Availability
#     start_date = models.DateField(null=True, blank=True)
#     end_date = models.DateField(null=True, blank=True)
    
#     # Crew information
#     crew_size = models.IntegerField(default=0)
#     has_smartphone = models.CharField(max_length=10, default='no')
#     work_mode = models.CharField(max_length=50, blank=True)
    
#     # Rate cards (from API)
#     rate_card = models.JSONField(default=dict, blank=True)
#     tender_activities = models.JSONField(default=dict, blank=True)
    
#     # API raw data
#     api_raw_data = models.JSONField(default=dict, blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     last_synced = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'mukkadams'
#         ordering = ['mukkadam_name']
    
#     def __str__(self):
#         return f"{self.mukkadam_name} (Crew: {self.crew_size})"

class Mukkadam(models.Model):
    mukkadam_id = models.BigIntegerField(unique=True, primary_key=True)
    mukkadam_name = models.CharField(max_length=200)
    mobile_numbers = models.CharField(max_length=100)

    MUKKADAM_STATUS_CHOICES = [
    ('active',   'Active'),
    ('on_hold',  'On Hold'),
    ('inactive', 'Inactive'),
    ]
    manual_status_set_by  = models.CharField(max_length=255, null=True, blank=True)
    manual_status      = models.CharField(max_length=20, choices=MUKKADAM_STATUS_CHOICES, null=True, blank=True)
    manual_status_note = models.CharField(max_length=255, null=True, blank=True)
    manual_status_set_at = models.DateTimeField(null=True, blank=True)
    clusters = models.ManyToManyField(
        'Cluster', 
        through='ClusterMukkadamAssignment',
        blank=True, 
        related_name='mukkadams'
    )
    is_permanent = models.BooleanField(default=False)

    # Location (stored from API)
    state = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=20, blank=True)
    district = models.CharField(max_length=100, blank=True)
    district_code = models.CharField(max_length=20, blank=True)
    taluka = models.CharField(max_length=100, blank=True)
    taluka_code = models.CharField(max_length=20, blank=True)
    village = models.CharField(max_length=100, blank=True)
    village_code = models.CharField(max_length=20, blank=True)

    current_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    # Crew
    crew_size = models.IntegerField(default=0)
    max_crew_capacity = models.IntegerField(default=0)  # ✅ NEW

    has_smartphone = models.CharField(max_length=10, default='no')
    work_mode = models.CharField(max_length=50, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Activities + rates (from API)
    tender_activities = models.JSONField(default=dict, blank=True)
    rate_card = models.JSONField(default=dict, blank=True)

    # ✅ Efficiency - default 0.10, updatable later
    efficiency = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.10'))

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
        max_digits=15, 
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


from django.db import models

class FarmerBillWebhookLog(models.Model):
    # ── Who sent it ──────────────────────────────────────────
    auth_token        = models.TextField(blank=True, null=True)
    sent_by_name      = models.CharField(max_length=255, blank=True, null=True)
    sent_by_email     = models.CharField(max_length=255, blank=True, null=True)
    sent_by_id        = models.CharField(max_length=100, blank=True, null=True)
    # In FarmerBillWebhookLog model
    activity_name = models.CharField(max_length=255, blank=True, null=True)
    sent_at       = models.DateTimeField(auto_now_add=True, blank=True,null = True)  # if not already there
    # ── Farmer ───────────────────────────────────────────────
    farmer_id         = models.CharField(max_length=100, blank=True, null=True)
    farmer_name       = models.CharField(max_length=255, blank=True, null=True)
    farmer_phone      = models.CharField(max_length=50,  blank=True, null=True)

    # Add to FarmerBillWebhookLog:
    webhook_detail        = models.TextField(blank=True, null=True)   # parsed 'detail' message
    webhook_booking_id    = models.CharField(max_length=100, blank=True, null=True)
    webhook_booking_status = models.CharField(max_length=50, blank=True, null=True)
    webhook_success       = models.BooleanField(null=True, blank=True)  # True=success, False=failed/already paid

    # ── Job ──────────────────────────────────────────────────
    job_id            = models.CharField(max_length=100, blank=True, null=True)
    crop_name         = models.CharField(max_length=255, blank=True, null=True)
    plot_name         = models.CharField(max_length=255, blank=True, null=True)


    # In FarmerBillWebhookLog model, add this field:
    cluster = models.ForeignKey(
        'Cluster',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bill_webhook_logs',
    )
    # ── Mukkadam ─────────────────────────────────────────────
    mukkadam_name     = models.CharField(max_length=255, blank=True, null=True)
    mukkadam_mobile   = models.CharField(max_length=50,  blank=True, null=True)

    # ── Bill ─────────────────────────────────────────────────
    total_billed      = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    total_paid        = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    balance_due       = models.DecimalField(max_digits=12, decimal_places=2, null=True)

    # ── Full payload + response ───────────────────────────────
    full_payload      = models.JSONField()
    webhook_status    = models.IntegerField(blank=True, null=True)
    webhook_response  = models.TextField(blank=True, null=True)

    # ── Timestamp ────────────────────────────────────────────
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name     = 'Farmer Bill Webhook Log'
        verbose_name_plural = 'Farmer Bill Webhook Logs'

    def __str__(self):
        return f"{self.farmer_name} | Job #{self.job_id} | ₹{self.balance_due} | {self.created_at.date()}"
    
    
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
# models.py
class AllocationAuditLog(models.Model):
    ACTION_CHOICES = [
        ('created',  'Created'),
        ('deleted',  'Deleted'),
        ('moved',    'Moved'),
        ('verified', 'Verified'),
        ('disputed', 'Disputed'),
    ]

    action          = models.CharField(max_length=20, choices=ACTION_CHOICES)
    allocation_id   = models.IntegerField()  # store raw ID, not FK — so it survives deletion
    job_activity_id = models.IntegerField(null=True, blank=True)
    job_id          = models.CharField(max_length=50, blank=True)
    mukkadam_id     = models.IntegerField(null=True, blank=True)
    mukkadam_name   = models.CharField(max_length=255, blank=True)
    farmer_name     = models.CharField(max_length=255, blank=True)
    activity_name   = models.CharField(max_length=255, blank=True)
    allocated_date  = models.DateField(null=True, blank=True)
    allocated_area  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    allocated_workers = models.IntegerField(null=True, blank=True)
    snapshot        = models.JSONField(default=dict)  # full before-state
    changed_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at      = models.DateTimeField(auto_now_add=True)
    notes           = models.TextField(blank=True)

    class Meta:
        db_table = 'allocation_audit_logs'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.action} — alloc#{self.allocation_id} by {self.changed_by} at {self.changed_at}"


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

    allows_second_job = models.BooleanField(
    default=False,
    help_text="If True, this allocation's workers are NOT subtracted from daily "
              "capacity — the mukkadam can take a second job in the other half of the day."
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

    # In Allocation model, add these fields after `notes`:

    # ── Mukkadam Day-End Report ──────────────────────────────
    actual_start_time = models.DateTimeField(
        null=True, blank=True,
        help_text="When mukkadam actually started work"
    )
    actual_end_time = models.DateTimeField(
        null=True, blank=True,
        help_text="When mukkadam submitted day-end report"
    )
    actual_crew_size = models.IntegerField(
        null=True, blank=True,
        help_text="Actual crew who showed up (mukkadam reported)"
    )
    actual_area_done = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Acres actually completed today (mukkadam reported)"
    )
    report_submitted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when mukkadam hit submit"
    )
    report_submitted = models.BooleanField(default=False)

    # ── Farmer Verification ──────────────────────────────────
    farmer_agreed = models.BooleanField(
        null=True, blank=True,
        help_text="True=agreed, False=disputed, None=not yet responded"
    )
    farmer_response_at = models.DateTimeField(null=True, blank=True)
    farmer_dispute_reason = models.TextField(blank=True)

    # ── Priority override ────────────────────────────────────
    # After day-end report, use actual_area_done instead of allocated_area
    use_actual_for_settlement = models.BooleanField(
        default=False,
        help_text="If True, settlement uses actual_area_done over allocated_area"
    )

    # 👇 NEW: who last moved / changed this allocation (date/area)
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocations_modified'
    )
    last_modified_at = models.DateTimeField(
        null=True,
        blank=True
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

    WORK_STATUS_CHOICES = [
    ('work_not_started', 'Work Not Started'),
    ('in_progress',      'In Progress'),
    ('completed',        'Completed'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending',  'Pending'),      # not yet completed
        ('dispute',  'Dispute'),      # completed but farmer didn't verify
        ('done',     'Done'),         # farmer verified via OTP
        ('settled',  'Settled'),      # final payment raised
    ]

    work_status          = models.CharField(max_length=20, choices=WORK_STATUS_CHOICES,
                                        default='work_not_started')
    payment_status       = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES,
                                            default='pending')
    mukkadam_claimed_area = models.DecimalField(max_digits=10, decimal_places=2,
                                                null=True, blank=True,
                                                help_text="Area claimed by mukkadam at day end")
    admin_override_area  = models.DecimalField(max_digits=10, decimal_places=2,
                                                null=True, blank=True,
                                                help_text="Team override after dispute resolution")
    dispute_reason       = models.TextField(blank=True, null=True,
                                            help_text="Farmer's reason filled by team on call")
    dispute_resolved_at  = models.DateTimeField(null=True, blank=True)
    dispute_resolved_by  = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name='resolved_disputes')
            
    
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
    # In tender/models.py — Allocation model, add these two fields:

    is_carry_forward = models.BooleanField(
        default=False,
        help_text='Auto-created by carry-forward service when farmer agrees actual < allocated'
    )
    # models.py — Allocation model, add this field
    is_auto_allocated = models.BooleanField(
        default=False,
        help_text="True = created by auto-allocation engine"
    )
    carry_forward_from = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='carry_forward_allocations',
        help_text='Original allocation this was carried forward from'
    )
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

PAYMENT_PROOF_TYPE_CHOICES = [
    ('farmer',   'Farmer Payment'),
    ('mukkadam', 'Mukkadam Payment'),
    ('weekly',   'Weekly Payment'),
]
class PaymentProof(models.Model):
    proof_type   = models.CharField(max_length=20, choices=PAYMENT_PROOF_TYPE_CHOICES)
    reference_id = models.IntegerField(help_text="FarmerPayment.id or MukkadamPayment.id or WeeklyPayment.id")
    s3_key       = models.CharField(max_length=500)
    s3_url       = models.URLField(max_length=1000, blank=True)
    file_name    = models.CharField(max_length=255)
    uploaded_at  = models.DateTimeField(auto_now_add=True)
    uploaded_by  = models.ForeignKey('auth.User', null=True, blank=True,
                                      on_delete=models.SET_NULL)

    class Meta:
        db_table = 'payment_proof'

    def __str__(self):
        return f"{self.proof_type} proof for ref {self.reference_id}"
    

class MukkadamPayment(models.Model):
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='payments')
    settlement = models.ForeignKey(
        'MukkadamJobSettlement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payments'
    )
    allocations = models.ManyToManyField(Allocation, related_name='mukkadam_payments', blank=True)
    PAYMENT_MODES = [
        ('CASH', 'Cash'),
        ('UPI', 'UPI'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other'),
    ]
    payment_id = models.CharField(max_length=50, unique=True)
    mode = models.CharField(
        max_length=50, 
        choices=PAYMENT_MODES, # ✅ Corrected from [...]
        default='CASH'
    )
    proof_s3_key = models.CharField(max_length=500, blank=True, null=True)  # NEW

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mukkadam_payments'
        ordering = ['-paid_at']


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
    allocation = models.ForeignKey(
        Allocation, 
        on_delete=models.SET_NULL, # Essential for keeping logs after deletion
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

# models.py
from django.db.models import CharField, DateField, JSONField
from django.db import models
from decimal import Decimal


class ClusterMukkadamAssignment(models.Model):
    mukkadam = models.ForeignKey(
        Mukkadam,
        on_delete=models.CASCADE,
        related_name='cluster_assignments'
    )
    cluster = models.ForeignKey(
        Cluster,
        on_delete=models.CASCADE,
        related_name='mukkadam_assignments'
    )

    weekly_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Weekly payment amount agreed for this mukkadam in this cluster"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cluster_mukkadam_assignments_created',
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cluster_mukkadam_assignments_modified',
    )

    transport_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_is_manual = models.BooleanField(default=False)

    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    weekly_payment_day = models.IntegerField(choices=WEEKDAY_CHOICES, null=True, blank=True)
    total_weekly_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    joined_date = models.DateField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MUKKADAM_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('updown', 'Updown'),
    ]

    mukkadam_type = models.CharField(
        max_length=20,
        choices=MUKKADAM_TYPE_CHOICES,
        default='permanent'
    )

    UPDOWN_MODE_CHOICES = [
        ('range', 'Range'),
        ('specific', 'Specific Dates'),
    ]

    updown_mode = models.CharField(
        max_length=20,
        choices=UPDOWN_MODE_CHOICES,
        null=True,
        blank=True
    )

    updown_from_date = models.DateField(null=True, blank=True)
    updown_to_date = models.DateField(null=True, blank=True)

    updown_specific_dates = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'cluster_mukkadam_assignments'
        
    def save(self, *args, **kwargs):

        if not self.joined_date and self.joined_at:
            self.joined_date = self.joined_at.date()

        super().save(*args, **kwargs)

    def __str__(self):
        cluster_name = self.cluster.name if self.cluster else '—'
        mukkadam_name = self.mukkadam.mukkadam_name if self.mukkadam else '—'
        return f"{mukkadam_name} → {cluster_name}"



    # ✅ FIXED: remove @property because it needs parameter
    def is_available_on(self, date):
        if self.mukkadam_type == 'permanent':
            return True

        if self.updown_mode == 'range':
            if self.updown_from_date and self.updown_to_date:
                return self.updown_from_date <= date <= self.updown_to_date

        if self.updown_mode == 'specific':
            return str(date) in self.updown_specific_dates

        return False

class MukkadamWeeklyPayment(models.Model):
    """
    Each weekly payment entry added on the cluster's weekly_payment_day
    """
    assignment = models.ForeignKey(
        ClusterMukkadamAssignment, 
        on_delete=models.CASCADE, 
        related_name='weekly_payments'
    )
    payment_date = models.DateField()
    crew_size_on_date = models.IntegerField()  # snapshot of crew size at time of payment
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=50, choices=[           # NEW
        ('CASH', 'Cash'), ('UPI', 'UPI'),
        ('ZOHO_PAYMENT', 'Zoho Payment'),
        ('BANK_TRANSFER', 'Bank Transfer'), ('CHEQUE', 'Cheque'),
    ], default='CASH')
    proof_s3_key = models.CharField(max_length=500, blank=True, null=True)  # NEW


    # Was this auto-generated by the weekly job or manually added?
    is_auto_generated = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mukkadam_weekly_payments'
        unique_together = ['assignment', 'payment_date']
        ordering = ['-payment_date']
# models.py
class MukkadamMiscCost(models.Model):
    mukkadam = models.ForeignKey(Mukkadam, on_delete=models.CASCADE, related_name='misc_costs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='mukkadam_misc_costs',
                            null=True, blank=True)   # ← add null=True, blank=True
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    proof_s3_key = models.CharField(max_length=500, blank=True, null=True)
    verified    = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_misc_costs')
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'mukkadam_misc_costs'
        ordering = ['-created_at']

class MukkadamJobSettlement(models.Model):
    """
    Tracks financial settlement for a mukkadam per job.
    Calculated after shoot selection date passes.
    """
    mukkadam = models.ForeignKey(
        Mukkadam, on_delete=models.CASCADE, related_name='job_settlements'
    )
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name='mukkadam_settlements'
    )
    cluster = models.ForeignKey(
        Cluster, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Transport cost (updown team only — permanent team always 0)
    transport_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Transport cost added to updown team bill. 0 for permanent team."
    )

    # In MukkadamJobSettlement model
    credit_carried_forward = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Credit from previous job's negative balance"
    )

    # Gross calculation
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text="% held as deposit"
    )
    payable_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="90% of gross"
    )

    # Carry-forward deposit from previous job
    deposit_carried_forward = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="10% deposit released from previous job"
    )

    allocation = models.OneToOneField(
        'Allocation',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='updown_settlement',
    )

    # Deductions
    advance_deducted = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Advance amount applied to this job (one-time)"
    )
    weekly_payments_deducted = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Sum of weekly payments applied to this job"
    )

    # Final
    net_payable = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Positive = we owe mukkadam. Negative = mukkadam in credit."
    )

    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),        # not yet triggered
        ('calculated', 'Calculated'),  # shoot selection passed, calculated
        ('payment_raised', 'Payment Raised'),
        ('paid', 'Paid'),
        ('no_payment_needed', 'No Payment Needed'),  # net_payable <= 0
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Which weekly payments were used in this settlement
    weekly_payments_applied = models.ManyToManyField(
        'MukkadamWeeklyPayment',
        blank=True,
        related_name='settlements'
    )
    plot = models.ForeignKey(
        'Plot', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mukkadam_settlements'
    )

    calculated_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mukkadam_job_settlements'
        # unique_together = ['mukkadam', 'job', 'plot']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mukkadam.mukkadam_name} | {self.job.job_id} | ₹{self.net_payable}"
    

    
    @property
    def deposit_held(self):
        """
        10% deposit held from gross.
        Returns 0 if all activities done (payable_amount = gross = 100%).
        """
        if not self.gross_amount:
            return Decimal('0')
        # If payable_amount == gross_amount → deposit was released (all activities done)
        if self.payable_amount >= self.gross_amount:
            return Decimal('0')
        pct = self.deposit_percent or Decimal('10')
        return (self.gross_amount * pct / 100).quantize(Decimal('0.01'))



class FarmerClusterMukkadamAssignment(models.Model):
    """
    Primary mukkadam assigned to a farmer within a cluster.
    Used for auto-allocation and backup logic.
    """
    farmer = models.ForeignKey(
        Farmer, on_delete=models.CASCADE,
        related_name='mukkadam_assignments'
    )
    cluster = models.ForeignKey(
        Cluster, on_delete=models.CASCADE,
        related_name='farmer_mukkadam_assignments'
    )
    primary_mukkadam = models.ForeignKey(
        Mukkadam, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='primary_farmer_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farmer_cluster_mukkadam_assignments'
        unique_together = ['farmer', 'cluster']

    def __str__(self):
        return f"{self.farmer.farmer_name} → {self.primary_mukkadam.mukkadam_name if self.primary_mukkadam else 'Unassigned'} [{self.cluster.name}]"
    

class WebhookLog(models.Model):
    """Log all webhook attempts for debugging"""
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ]
    
    webhook_data = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_type = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # What was processed
    farmer_id = models.CharField(max_length=50, blank=True, null=True)
    job_id = models.CharField(max_length=100, blank=True, null=True)
    cluster_matched = models.BooleanField(default=False)
    cluster_id = models.IntegerField(blank=True, null=True)
    
    # Processing details
    activities_processed = models.IntegerField(default=0)
    activities_failed = models.IntegerField(default=0)
    plots_created = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'webhook_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['farmer_id']),
            models.Index(fields=['job_id']),
        ]
    
    def __str__(self):
        return f"Webhook {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
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
