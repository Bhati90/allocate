# allocation_app/serializers.py

from rest_framework import serializers
from .models import JobActivity, Allocation, AllocationStats
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']
    
    def get_full_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full if full else obj.username


class JobActivitySerializer(serializers.ModelSerializer):
    remaining_area = serializers.ReadOnlyField()
    is_fully_allocated = serializers.ReadOnlyField()
    
    class Meta:
        model = JobActivity
        fields = [
            'id',
            'job_id',
            'activity_id',
            'activity_name',
            'activity_type',
            'location',
            'total_area',
            'allocated_area',
            'remaining_area',
            'scheduled_datetime',
            'estimated_workers',
            'rate_per_acre',
            'total_price',
            'transport_cost',
            'other_cost',
            'subtotal',
            'is_fully_allocated',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'remaining_area', 'is_fully_allocated', 'created_at', 'updated_at']



from rest_framework import serializers
from .models import FCMDevice

class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = [
            'fcm_token',
            'device_type',
            'device_id',
            'last_used_at'
        ]

class AllocationSerializer(serializers.ModelSerializer):
    allocated_by = UserSerializer(read_only=True)
    created_by = serializers.SerializerMethodField()
    activity_name = serializers.CharField(
        source='job_activity.activity_name', 
        read_only=True
    )
    job_id = serializers.CharField(
        source='job_activity.job_id', 
        read_only=True
    )
    total_cost = serializers.ReadOnlyField()
    
    job_activity = serializers.PrimaryKeyRelatedField(
        queryset=JobActivity.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Allocation
        fields = [
            'id',
            'farmer_work_id',
            'job_activity',
            'job_id',
            'activity_name',
            'mukkadam_id',
            'allocated_area',
            'work_date',
            'crew_size',
            'mukkadam_price',
            'transport_type',
            'transport_provider_id',
            'own_transport_price',
            'transport_price',
            'total_cost',
            'allocated_at',
            'completed_at',
            'allocated_by',
            'created_by',
            'status',
            'notes',
        ]
        read_only_fields = [
            'id', 
            'allocated_at', 
            'completed_at', 
            'allocated_by', 
            'total_cost',
            'farmer_work_id',
            'job_id',
            'activity_name'
        ]
    
    def get_created_by(self, obj):
        if obj.allocated_by:
            return UserSerializer(obj.allocated_by).data
        return None


class AllocationStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllocationStats
        fields = '__all__'