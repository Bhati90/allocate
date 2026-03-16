# serializers.py
from rest_framework import serializers
from .models import (
    ActivityCatalog, ActivityScheduleRule, Cluster, ClusterActivityScheduleRule, ExtraWorker, Farmer, Job, JobActivity, JobBooking, FarmerPayment, Leave,
    Mukkadam, MukkadamActivityRate, MukkadamAvailability,
    Allocation, MukkadamPayment,ActivityLogTender, Plot
)


# =============================================================================
# ACTIVITY CATALOG SERIALIZERS
# =============================================================================
class ActivityCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCatalog
        fields = [
            'id',
            'name',
            'activity_type',
            'default_rate_per_acre',
            'is_strict',
            'estimated_workers_per_acre',
            'default_gap_days',
        ]
# serializers.py

class ActivityCatalogDetailSerializer(serializers.ModelSerializer):
    """Detailed activity with all default values"""
    class Meta:
        model = ActivityCatalog
        fields = [
            'id',
            'name',
            'activity_type',
            'default_rate_per_acre',
            'is_strict',
            'estimated_workers_per_acre',
            'default_gap_days',
            'source',
            'created_at',
            'updated_at',
        ]

class CreateActivitySerializer(serializers.Serializer):
    """Serializer for creating a new global activity"""
    name = serializers.CharField(max_length=200)
    activity_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Farmer defaults
    default_rate_per_acre = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    default_gap_days = serializers.IntegerField(default=3)
    
    # Mukkadam defaults
    mukkadam_rate_per_acre = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0
    )
    mukkadam_productivity_per_worker = serializers.DecimalField(
        max_digits=5, 
        decimal_places=3, 
        default=0.150
    )
    
    # Common
    is_strict = serializers.BooleanField(default=False)
    estimated_workers_per_acre = serializers.IntegerField(default=10)
class InsertActivitySerializer(serializers.Serializer):
    """Serializer for inserting activity between existing ones"""
    name = serializers.CharField(max_length=200)
    activity_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Rates
    default_rate_per_acre = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Position in lifecycle
    insert_after_activity_id = serializers.IntegerField(
        help_text="Insert this activity after which activity? (activity ID)"
    )
    gap_days_from_previous = serializers.IntegerField(
        default=3,
        help_text="How many days after the previous activity?"
    )
    
    # Mukkadam defaults (optional)
    mukkadam_rate_per_acre = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        required=False
    )
    mukkadam_productivity_per_worker = serializers.DecimalField(
        max_digits=5, 
        decimal_places=3, 
        default=0.150,
        required=False
    )
    
    # Common
    is_strict = serializers.BooleanField(default=False)
    estimated_workers_per_acre = serializers.IntegerField(default=10)

class AddClusterActivitySerializer(serializers.Serializer):
    """Serializer for adding activity to a specific cluster"""
    activity_id = serializers.IntegerField(required=False)
    activity_name = serializers.CharField(max_length=200, required=False)
    
    # Farmer rates
    farmer_rate_per_acre = serializers.DecimalField(max_digits=10, decimal_places=2)
    gap_days = serializers.IntegerField()
    
    # Mukkadam rates
    mukkadam_rate_per_acre = serializers.DecimalField(max_digits=10, decimal_places=2)
    mukkadam_productivity_per_worker = serializers.DecimalField(
        max_digits=5, 
        decimal_places=3, 
        default=0.150
    )
# =============================================================================
# FARMER & JOB SERIALIZERS
# =============================================================================
from rest_framework import serializers
from django.db.models import Sum, Count, Avg, F, Q
class FarmerSerializer(serializers.ModelSerializer):
    clusters = serializers.PrimaryKeyRelatedField(
        queryset=Cluster.objects.all(), many=True, required=False
    )
    village = serializers.SerializerMethodField(read_only=True)
    taluka = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    total_acres = serializers.SerializerMethodField()  # ✅ ADD

    class Meta:
        model = Farmer
        fields = [
            'farmer_id',
            'farmer_name',
            'clusters',
            'phone_number',
            'village',
            'taluka',
            'district',
            'location',
            'latitude',
            'longitude',
            'total_acres',   # ✅ ADD
        ]
        read_only_fields = ['village', 'taluka', 'district', 'total_acres']

    def get_total_acres(self, obj):
        total = obj.plots.aggregate(total=Sum('area_acres'))['total']
        return float(total) if total else 0.0


    def get_village(self, obj):
        first = obj.clusters.first()
        return first.village if first else ''

    def get_taluka(self, obj):
        first = obj.clusters.first()
        return first.taluka if first else ''

    def get_district(self, obj):
        first = obj.clusters.first()
        return first.district if first else ''

class JobActivitySerializer(serializers.ModelSerializer):
    activity_id = serializers.IntegerField(source='activity.id', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    is_strict = serializers.BooleanField(read_only=False)
    plot = serializers.PrimaryKeyRelatedField(read_only=True)
    plot_name = serializers.CharField(source='plot.name', read_only=True)
    moved_to_date = serializers.SerializerMethodField()   # ← ADD

    def get_moved_to_date(self, obj):                     # ← ADD
        child = obj.moved_children.order_by('scheduled_date').first()
        return str(child.scheduled_date) if child else None

    class Meta:
        model = JobActivity
        fields = [
            'id',
            'activity_id',
            'activity_name',
            'activity_type',
            'is_strict',
            'is_manually_moved',
            'total_area',
            'allocated_area',
            'remaining_area',
            'crop_bundles',
            'scheduled_date',
            'scheduled_time',
            'estimated_workers',
            'rate_per_acre',
            'total_price',
            'transport_cost',
            'other_cost',
            'plot',
            'plot_name',
            'original_scheduled_date',
            'moved_to_date',           # ← ADD
            'subtotal',
            'allocation_status',
            'is_fully_allocated',
            'is_manually_edited',
            'is_lost',
            'lost_reason',
            'is_manually_moved',
            'moved_from_activity',
            'move_reason',
            'location'
        ]
        read_only_fields = ['remaining_area', 'allocation_status', 'is_fully_allocated']
class FarmerPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmerPayment
        fields = [
            'payment_id',
            'mode',
            'amount',
            'notes',
            'paid_status',
            'paid_at',
            'created_at'
        ]
        read_only_fields = ['created_at']


class JobBookingSerializer(serializers.ModelSerializer):
    payments = FarmerPaymentSerializer(many=True, read_only=True)
    
    class Meta:
        model = JobBooking
        fields = [
            'booking_id',
            'status',
            'total_amount',
            'advance_paid',
            'balance',
            'assignee_number',
            'payments'
        ]

from .models import Plot


# =============================================================================
# MUKKADAM SERIALIZERS
# =============================================================================

# serializers.py
class MukkadamActivityRateSerializer(serializers.ModelSerializer):
    activity_id = serializers.IntegerField(source='activity.id')
    activity_name = serializers.CharField(source='activity.name')
    rate_id = serializers.IntegerField(source='id')  # ← add this

    class Meta:
        model = MukkadamActivityRate
        fields = [
            'rate_id',                   # ← add this
            'activity_id',
            'activity_name',
            'rate_per_acre',
            'productivity_per_worker',
            'is_active'
        ]

class MukkadamSerializer(serializers.ModelSerializer):
    activity_rates = MukkadamActivityRateSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mukkadam
        fields = '__all__'


class MukkadamAvailabilitySerializer(serializers.ModelSerializer):
    mukkadam_name = serializers.CharField(source='mukkadam.mukkadam_name', read_only=True)
    
    class Meta:
        model = MukkadamAvailability
        fields = [
            'id',
            'mukkadam',
            'mukkadam_name',
            'date',
            'is_available',
            'is_on_leave',
            'available_crew_size',
            'allocated_workers',
            'remaining_capacity',
            'is_manually_set',
            'notes'
        ]
        read_only_fields = ['remaining_capacity']


# class MukkadamSerializer(serializers.ModelSerializer):
#     activity_rates = serializers.SerializerMethodField()
#     cluster = serializers.PrimaryKeyRelatedField(
#         queryset=Cluster.objects.all(), allow_null=True, required=False
#     )
#     class Meta:
#         model = Mukkadam
#         fields = [
#             'mukkadam_id',
#             'mukkadam_name',
#             'mobile_numbers',
#             'is_permanent',
#             'district',
#             'taluka',
#             'village',
#             'current_latitude',
#             'current_longitude',
#             'start_date',
#             'end_date',
#             'cluster',
#             'crew_size',
#             'has_smartphone',
#             'work_mode',
#             'activity_rates',
#             'rate_card',
#             'tender_activities'
#         ]
    
#     def get_activity_rates(self, obj):
#         """Get active activity rates with productivity"""
#         rates = obj.activity_rates.filter(is_active=True).select_related('activity')
#         return [{
#             'id': r.id,
#             'activity_id': r.activity.id,
#             'activity_name': r.activity.name,
#             'rate_per_acre': float(r.rate_per_acre),
#             'productivity_per_worker': float(r.productivity_per_worker),
#             'daily_capacity': obj.crew_size * float(r.productivity_per_worker),
#             'source': r.source
#         } for r in rates]


# =============================================================================
# ALLOCATION SERIALIZERS
# =============================================================================
# serializers.py

# serializers.py

class JobActivityCreateUpdateSerializer(serializers.ModelSerializer):
    activity_id = serializers.IntegerField(write_only=True)
    plot = serializers.PrimaryKeyRelatedField(
        queryset=Plot.objects.all(), allow_null=True, required=False
    )
    
    class Meta:
        model = JobActivity
        fields = [
            'id',
            'job',
            'plot',           # NOW INCLUDED
            'activity_id',
            'total_area',
            'rate_per_acre',
            'is_strict',
            'scheduled_date',
            'scheduled_time',
        ]
    
    def validate(self, attrs):
        plot = attrs.get('plot') or getattr(self.instance, 'plot', None)
        total_area = attrs.get('total_area') or getattr(self.instance, 'total_area', None)
        
        if plot and total_area and plot.area_acres and total_area > plot.area_acres:
            raise serializers.ValidationError(
                {"total_area": f"Total area {total_area} ac cannot exceed plot size {plot.area_acres} ac"}
            )
        return attrs
    
    def create(self, validated_data):
        job = validated_data.pop('job')
        activity_id = validated_data.pop('activity_id')
        activity = ActivityCatalog.objects.get(id=activity_id)
        
        ja = JobActivity.objects.create(
            job=job,
            activity=activity,
            **validated_data,
        )
        return ja
    
    def update(self, instance, validated_data):
        activity_id = validated_data.pop('activity_id', None)
        if activity_id:
            instance.activity = ActivityCatalog.objects.get(id=activity_id)
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.is_manually_edited = True
        instance.save()
        return instance

from rest_framework import serializers
from django.db import models
class LeaveSerializer(serializers.ModelSerializer):
    mukkadam_name = serializers.CharField(
        source='mukkadam.mukkadam_name',
        read_only=True
    )

    class Meta:
        model = Leave
        fields = [
            'id',
            'date',
            'leave_type',
            'mukkadam',
            'crew_on_leave',
            'mukkadam_name',
            'reason',
            'is_active',
            'created_at',
            'cluster',
        ]
        read_only_fields = ['created_at']

    def validate(self, attrs):
        from .models import Mukkadam, Leave

        leave_type = attrs.get('leave_type', getattr(self.instance, 'leave_type', None))
        mukkadam = attrs.get('mukkadam', getattr(self.instance, 'mukkadam', None))
        date = attrs.get('date', getattr(self.instance, 'date', None))
        crew_on_leave = attrs.get('crew_on_leave', getattr(self.instance, 'crew_on_leave', 0))

        if leave_type == 'mukkadam' and mukkadam and date:
          # sum of other leaves
          qs = Leave.objects.filter(
              leave_type='mukkadam',
              mukkadam=mukkadam,
              date=date,
              is_active=True,
          )
          if self.instance:
              qs = qs.exclude(pk=self.instance.pk)

          existing_total = qs.aggregate(total=models.Sum('crew_on_leave'))['total'] or 0
          total_after = existing_total + (crew_on_leave or 0)

          if total_after > mukkadam.crew_size:
              raise serializers.ValidationError(
                  {'crew_on_leave': f'Only {max(mukkadam.crew_size - existing_total, 0)} workers can be marked on leave for this mukkadam on this date.'}
              )

        return attrs

class AllocationSerializer(serializers.ModelSerializer):
    job_id = serializers.CharField(source='job_activity.job.job_id', read_only=True)
    farmer_id = serializers.CharField(source='job_activity.job.farmer.farmer_id', read_only=True)
    farmer_name = serializers.CharField(source='job_activity.job.farmer.farmer_name', read_only=True)
    activity_id = serializers.IntegerField(source='job_activity.activity.id', read_only=True)
    activity_name = serializers.CharField(source='job_activity.activity.name', read_only=True)
    is_strict = serializers.BooleanField(source='job_activity.activity.is_strict', read_only=True)
    mukkadam_name = serializers.CharField(source='mukkadam.mukkadam_name', read_only=True)

    class Meta:
        model = Allocation
        fields = [
            'activity_id',
            'id', 'job_activity', 'job_activity_id', 'mukkadam', 'mukkadam_id',
            'cluster', 'farmer_id', 'mukkadam_name', 'is_strict', 'activity_name',
            'farmer_name', 'job_id', 'allocated_date', 'allocated_area', 'allocated_workers',
            'farmer_rate', 'mukkadam_rate', 'farmer_amount', 'mukkadam_amount',
            'profit', 'status', 'notes', 'is_carry_forward', 'carry_forward_from',
            'allows_second_job',           # ✅ ADD THIS — needed by frontend to skip capacity deduction

            # Day-end report fields
            'report_submitted',
            'report_submitted_at',
            'actual_start_time',
            'actual_end_time',
            'actual_crew_size',
            'actual_area_done',

            # Farmer verification fields
            'farmer_agreed',
            'farmer_response_at',
            'farmer_dispute_reason',
            'use_actual_for_settlement',

            'created_at', 'updated_at',
        ]
class AllocationDetailSerializer(serializers.ModelSerializer):
    job_activity = serializers.SerializerMethodField()
    mukkadam = serializers.SerializerMethodField()
    cluster = serializers.SerializerMethodField()

    class Meta:
        model = Allocation
        fields = [
            "id",
            "allocated_date",
            "allocated_area",
            "allocated_workers",
            "farmer_rate",
            "mukkadam_rate",
            "status",
            "created_at",
            "job_activity",
            "mukkadam",
            "cluster",
        ]

    def get_job_activity(self, obj):
        ja = obj.job_activity
        job = ja.job
        plot = job.plot
        farmer = job.farmer
        return {
            "id": ja.id,
            "activity_name": ja.activity.name,
            "scheduled_date": ja.scheduled_date,
            "total_area": ja.total_area,
            "allocated_area": ja.allocated_area,
            "job": {
                "id": job.id,
                "job_number": job.job_number,
                "crop": job.crop.name if job.crop else None,
                "variety": job.variety,
            },
            "plot": {
                "id": plot.id,
                "name": plot.name,
                "area_acres": plot.area_acres,
            },
            "farmer": {
                "id": farmer.id,
                "farmer_id": farmer.farmer_id,
                "name": farmer.farmer_name,
                "mobile": farmer.phone_number,
            },
        }

    def get_mukkadam(self, obj):
        m = obj.mukkadam
        return {
            "id": m.id,
            "mukkadam_id": m.mukkadam_id,
            "name": m.name,
            "mobile_numbers": m.mobile_numbers,
            "crew_size": m.crew_size,
        }

    def get_cluster(self, obj):
        c = obj.cluster
        return {
            "id": c.id,
            "name": c.name,
            "village": c.village,
            "taluka": c.taluka,
            "district": c.district,
        }

class MukkadamPaymentSerializer(serializers.ModelSerializer):
    mukkadam_name = serializers.CharField(source='mukkadam.mukkadam_name', read_only=True)
    allocation_count = serializers.IntegerField(source='allocations.count', read_only=True)
    
    class Meta:
        model = MukkadamPayment
        fields = [
            'payment_id',
            'mukkadam',
            'mukkadam_name',
            'mode',
            'amount',
            'notes',
            'paid_at',
            'allocations',
            'allocation_count',
            'created_at'
        ]
        read_only_fields = ['created_at', 'allocation_count']

# serializers.py
class ExtraWorkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraWorker
        fields = ['id', 'mukkadam', 'date', 'workers', 'note']

# =============================================================================
# NESTED SERIALIZERS (for specific endpoints)
# =============================================================================
class JobSerializer(serializers.ModelSerializer):
    farmer_name   = serializers.CharField(source='farmer.farmer_name', read_only=True)
    farmer_phone  = serializers.CharField(source='farmer.phone_number', read_only=True)
    plot_name     = serializers.CharField(source='plot.name', read_only=True)
    plot_code     = serializers.CharField(source='plot.plot_code', read_only=True)
    cluster_names = serializers.SerializerMethodField()
    booking_data  = serializers.SerializerMethodField()
    activities_data = serializers.SerializerMethodField()

    def get_cluster_names(self, obj):
        return [{'id': c.id, 'name': c.name} for c in obj.clusters.all()]

    def get_booking_data(self, obj):
        try:
            b = obj.booking
            return {
                'total_amount': float(b.total_amount),
                'advance_paid': float(b.advance_paid),
                'balance':      float(b.balance),
                'status':       b.status,
            }
        except:
            return None

    def get_activities_data(self, obj):
        result = []
        for a in obj.activities.all():
            allocations = []
            for alloc in a.allocations.select_related('mukkadam').order_by('allocated_date'):
                allocations.append({
                    'allocation_id':    alloc.id,
                    'mukkadam_id':      alloc.mukkadam.mukkadam_id,
                    'mukkadam_name':    alloc.mukkadam.mukkadam_name,
                    'mukkadam_mobile':  alloc.mukkadam.mobile_numbers,
                    'allocated_date':   str(alloc.allocated_date) if alloc.allocated_date else None,
                    'allocated_area':   float(alloc.allocated_area or 0),
                    'allocated_workers':alloc.allocated_workers or 0,
                    'actual_area_done': float(alloc.actual_area_done) if alloc.actual_area_done else None,
                    'actual_crew_size': alloc.actual_crew_size,
                    'work_status':      alloc.work_status,
                    'payment_status':   alloc.payment_status,
                    'mukkadam_rate':    float(alloc.mukkadam_rate or 0),
                    'farmer_rate':      float(alloc.farmer_rate or 0),
                    'mukkadam_amount':  float(alloc.mukkadam_amount or 0),
                    'report_submitted': alloc.report_submitted,
                    'farmer_agreed':    alloc.farmer_agreed,
                })
            result.append({
                'id':                a.id,
                'name':              a.activity.name,
                'total_area':        float(a.total_area),
                'allocated_area':    float(a.allocated_area),
                'remaining_area':    float(a.remaining_area),
                'allocation_status': a.allocation_status,
                'scheduled_date':    str(a.scheduled_date) if a.scheduled_date else None,
                'total_price':       float(a.total_price),
                'allocations':       allocations,
            })
        return result

    class Meta:
        model = Job
        fields = [
            'job_id', 'work_id', 'status', 'priority',
            'crop_name', 'variety', 'booking_type',
            'scheduled_date', 'completed_date', 'created_at',
            'farmer_name', 'farmer_phone',
            'plot_name', 'plot_code',
            'cluster_names', 'booking_data', 'activities_data',
            'total_activities_amount',
        ]
class JobSerializer(serializers.ModelSerializer):
    farmer = serializers.PrimaryKeyRelatedField(
        queryset=Farmer.objects.all(), write_only=True
    )
    cluster = serializers.PrimaryKeyRelatedField(
        queryset=Cluster.objects.all(), allow_null=True, required=False
    )

    plot = serializers.PrimaryKeyRelatedField(
        queryset=Plot.objects.all(), allow_null=True, required=False
    )
    plot_name = serializers.CharField(source='plot.name', read_only=True)

    farmer_id = serializers.CharField(source='farmer.farmer_id', read_only=True)
    farmer_name = serializers.CharField(source='farmer.farmer_name', read_only=True)

    activities = JobActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'job_id',
            'work_id',
            'cluster',
            'farmer',
            'farmer_id',
            'farmer_name',
            'variety',
            'crop_name',
            'plot',
            'plot_name',
            'status',
            'priority',
            'scheduled_date',
            'booking_type',
            'activity_notes',
            'internal_notes',
            'total_activities_amount',
            'created_at',
            'updated_at',
            'activities',
        ]
        read_only_fields = ['created_at', 'updated_at']

# serializers.py
from rest_framework import serializers
from .models import Cluster,ClusterMukkadamAssignment


class ClusterSerializer(serializers.ModelSerializer):
    district         = serializers.SerializerMethodField()
    taluka           = serializers.SerializerMethodField()
    village          = serializers.SerializerMethodField()
    date_range       = serializers.SerializerMethodField()
    farmer_count     = serializers.IntegerField(read_only=True)
    mukkadam_count   = serializers.IntegerField(read_only=True)
    activity_count   = serializers.IntegerField(read_only=True)
    allocation_count = serializers.IntegerField(read_only=True)
    farmer_due       = serializers.SerializerMethodField()
    mukkadam_due     = serializers.SerializerMethodField()
    # ── ADD THESE ──
    total_area       = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=0)
    allocated_area   = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=0)
    today_team       = serializers.SerializerMethodField()
    cluster_mukkadams = serializers.SerializerMethodField()

    class Meta:
        model  = Cluster
        fields = '__all__'
        read_only_fields = ['id']

    def get_district (self, obj): return ', '.join(obj.districts) if obj.districts else ''
    def get_taluka   (self, obj): return ', '.join(obj.talukas)   if obj.talukas   else ''
    def get_village  (self, obj): return ', '.join(obj.villages)  if obj.villages  else ''

    def get_date_range(self, obj):
        return {
            'start_date': getattr(obj, 'activity_start', None),
            'end_date':   getattr(obj, 'activity_end',   None),
        }

    def get_farmer_due  (self, obj): return 0
    def get_mukkadam_due(self, obj): return 0

    def get_today_team(self, obj):
        from datetime import date
        today = date.today()
        allocs = (
            Allocation.objects
            .filter(cluster=obj, allocated_date=today)
            .select_related(
                'mukkadam',
                'job_activity__activity',
                'job_activity__job__farmer',
            )
            .order_by('mukkadam_id')
            .distinct()
        )
        seen = set()
        result = []
        for a in allocs:
            mk_id = a.mukkadam_id
            if mk_id in seen:
                continue
            seen.add(mk_id)
            result.append({
                'mukkadam_name':  a.mukkadam.mukkadam_name,
                'crew_size':      a.mukkadam.crew_size,
                'activity_name':  a.job_activity.activity.name,
                'farmer_name':    a.job_activity.job.farmer.farmer_name,
            })
        return result

    def get_cluster_mukkadams(self, obj):
        assignments = (
            ClusterMukkadamAssignment.objects
            .filter(cluster=obj, is_active=True)
            .select_related('mukkadam')
        )
        result = []
        for a in assignments:
            # which clusters is this mukkadam working in today
            from datetime import date
            today_clusters = (
                Allocation.objects
                .filter(mukkadam=a.mukkadam, allocated_date=date.today())
                .select_related('cluster')
                .values_list('cluster__name', flat=True)
                .distinct()
            )
            result.append({
                'mukkadam_id':    a.mukkadam.mukkadam_id,
                'mukkadam_name':  a.mukkadam.mukkadam_name,
                'crew_size':      a.mukkadam.crew_size,
                'mukkadam_type':  a.mukkadam_type,
                'weekly_amount':  float(a.weekly_amount or 0),
                'today_clusters': list(today_clusters),
            })
        return result


class PlotSerializer(serializers.ModelSerializer):
    clusters = serializers.PrimaryKeyRelatedField(
        queryset=Cluster.objects.all(), many=True, required=False
    )

    class Meta:
        model = Plot
        fields = ['id', 'farmer', 'clusters', 'name', 'area_acres', 'plot_code',
                'crop_name', 'variety', 'pruning_date',  # ✅ add these 3
                'latitude', 'longitude']
class ActivityScheduleRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityScheduleRule
        fields = ['id', 'activity', 'gap_days', 'phase_order']


class ClusterActivityScheduleRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterActivityScheduleRule
        fields = ['id', 'cluster', 'activity', 'gap_days']

class MukkadamDetailSerializer(MukkadamSerializer):
    """Extended mukkadam serializer with availability"""
    daily_availability = serializers.SerializerMethodField()
    
    def get_daily_availability(self, obj):
        """Get availability for next 7 days"""
        from datetime import date, timedelta
        
        today = date.today()
        availabilities = []
        
        for i in range(7):
            check_date = today + timedelta(days=i)
            try:
                availability = obj.daily_availability.get(date=check_date)
                availabilities.append({
                    'date': str(check_date),
                    'is_available': availability.is_available,
                    'available_crew_size': availability.available_crew_size,
                    'remaining_capacity': availability.remaining_capacity
                })
            except MukkadamAvailability.DoesNotExist:
                availabilities.append({
                    'date': str(check_date),
                    'is_available': True,
                    'available_crew_size': obj.crew_size,
                    'remaining_capacity': obj.crew_size
                })
        
        return availabilities
    

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile

class UserDetailSerializer(serializers.ModelSerializer):
    # We fetch these fields from the related 'profile' model
    full_name = serializers.CharField(source='profile.full_name')
    mobile_number = serializers.CharField(source='profile.mobile_number')
    role = serializers.CharField(source='profile.role')

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'mobile_number', 'role']


# serializers.py — add JobNoteSerializer

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import JobNote


class NoteAuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


# serializers.py — replace JobNoteSerializer with this fixed version

class JobNoteSerializer(serializers.ModelSerializer):
    author        = NoteAuthorSerializer(read_only=True)
    resolved_by   = NoteAuthorSerializer(read_only=True)
    mentions      = NoteAuthorSerializer(many=True, read_only=True)
    mention_ids   = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )
    tag_labels    = serializers.SerializerMethodField()

    # ✅ FIX: explicitly declare job_id as a writable field that maps to the job FK
    job_id = serializers.CharField(write_only=False)  # read + write as string

    class Meta:
        model  = JobNote
        fields = [
            'id', 'job_id', 'author', 'text', 'tags', 'tag_labels',
            'mentions', 'mention_ids',
            'is_resolved', 'resolved_by', 'resolved_at', 'resolution_note',
            'note_date', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'author', 'is_resolved', 'resolved_by',
                            'resolved_at', 'created_at', 'updated_at']

    TAG_LABEL_MAP = dict(JobNote.TAG_CHOICES)

    def get_tag_labels(self, obj):
        return [self.TAG_LABEL_MAP.get(t, t) for t in (obj.tags or [])]

    def validate_job_id(self, value):
        # Confirm the job exists
        from .models import Job
        if not Job.objects.filter(job_id=value).exists():
            raise serializers.ValidationError(f"Job '{value}' does not exist.")
        return value

    def create(self, validated_data):
        mention_ids = validated_data.pop('mention_ids', [])
        job_id      = validated_data.pop('job_id')          # ✅ pop the string id

        from .models import Job
        job = Job.objects.get(job_id=job_id)                # ✅ look up the Job instance

        note = JobNote.objects.create(job=job, **validated_data)  # ✅ pass FK instance

        if mention_ids:
            from django.contrib.auth.models import User
            note.mentions.set(User.objects.filter(id__in=mention_ids))

        return note
    