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

# =============================================================================
# FARMER & JOB SERIALIZERS
# =============================================================================
class FarmerSerializer(serializers.ModelSerializer):
    cluster = serializers.PrimaryKeyRelatedField(
        queryset=Cluster.objects.all(), allow_null=True, required=False
    )

    # derive from cluster
    village = serializers.SerializerMethodField(read_only=True)
    taluka = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Farmer
        fields = [
            'farmer_id',
            'farmer_name',
            'cluster',
            'phone_number',
            'village',
            'taluka',
            'district',
            'location',
            'latitude',
            'longitude',
        ]
        read_only_fields = ['village', 'taluka', 'district']

    def get_village(self, obj):
        return obj.cluster.village if obj.cluster else ''

    def get_taluka(self, obj):
        return obj.cluster.taluka if obj.cluster else ''

    def get_district(self, obj):
        return obj.cluster.district if obj.cluster else ''

class JobActivitySerializer(serializers.ModelSerializer):
    activity_id = serializers.IntegerField(source='activity.id', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    activity_type = serializers.CharField(source='activity.activity_type', read_only=True)
    is_strict = serializers.BooleanField(read_only=False)
    plot = serializers.PrimaryKeyRelatedField(read_only=True)
    plot_name = serializers.CharField(source='plot.name', read_only=True)
    
    class Meta:
        model = JobActivity
        fields = [
            'id',
            'activity_id',
            'activity_name',
            'activity_type',
            'is_strict',
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
            'subtotal',
            'allocation_status',
            'is_fully_allocated',
            'is_manually_edited',
            'is_lost',
            'lost_reason',
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
    
    class Meta:
        model = MukkadamActivityRate
        fields = [
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
            'cluster',          # ⬅️ add this
        ]
        read_only_fields = ['created_at']

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
            'id',
            'job_activity',
            'job_id',
            'farmer_id',
            'farmer_name',
            'activity_id',
            'activity_name',
            'is_strict',
            'mukkadam',
            'mukkadam_name',
            'allocated_date',
            'allocated_area',
            'allocated_workers',
            'farmer_rate',
            'mukkadam_rate',
            'farmer_amount',
            'mukkadam_amount',
            'profit',
            'status',
            'actual_workers',
            'actual_area_completed',
            'start_time',
            'end_time',
            'efficiency_score',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'farmer_amount',
            'mukkadam_amount',
            'profit',
            'efficiency_score',
            'created_at',
            'updated_at'
        ]


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
from .models import Cluster

class ClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = [
            'id',
            'name',
            
            'state_code',
            'district_code',
            'taluka_code',
            'village_code',
            'district',
            'taluka',
            'village',
            'note',
        ]
        read_only_fields = ['id']
# serializers.py
class PlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plot
        fields = ['id', 'farmer', 'cluster', 'name', 'area_acres', 'plot_code',
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