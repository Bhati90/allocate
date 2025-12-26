# serializers.py

from rest_framework import serializers
from .models import Job, JobActivity, Allocation, AllocationStats
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
    activity_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = JobActivity
        fields = [
            'id',
            'activity_type',
            'activity_display',
            'location',
            'total_area',
            'allocated_area',
            'remaining_area',
            'scheduled_date',
            'estimated_workers_needed',
            'rate_per_acre',
            'is_fully_allocated'
        ]


class JobSerializer(serializers.ModelSerializer):
    activities = JobActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id',
            'job_id',
            'farmer_name',
            'farmer_contact',
            'created_at',
            'updated_at',
            'status',
            'notes',
            'activities'
        ]
        
class AllocationSerializer(serializers.ModelSerializer):
    allocated_by = UserSerializer(read_only=True)
    created_by = serializers.SerializerMethodField()
    activity_name = serializers.CharField(source='job_activity.get_activity_type_display', read_only=True)
    job_id = serializers.CharField(source='job_activity.job.job_id', read_only=True)
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
            'crew_size',  # ✅ ADD THIS
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
        read_only_fields = ['id', 'allocated_at', 'completed_at', 'allocated_by', 'total_cost']
    
    def get_created_by(self, obj):
        if obj.allocated_by:
            return UserSerializer(obj.allocated_by).data
        return None
    
class AllocationStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllocationStats
        fields = '__all__'