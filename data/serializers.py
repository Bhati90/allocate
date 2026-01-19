# allocation_app/serializers.py

from rest_framework import serializers
from .models import JobActivity, Allocation, AllocationStats,ActivityLog
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']
    
    def get_full_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full if full else obj.username

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
from .models import PaymentRequest, TransportPaymentRequest, Allocation

class PaymentRequestSerializer(serializers.ModelSerializer):
    # Allocation details
    job_id = serializers.CharField(source='allocation.job_activity.job_id', read_only=True)
    activity_name = serializers.CharField(source='allocation.job_activity.activity_name', read_only=True)
    work_date = serializers.DateField(source='allocation.work_date', read_only=True)
    allocated_area = serializers.DecimalField(
        source='allocation.allocated_area',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    # User details
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.username', read_only=True)
    rejected_by_name = serializers.CharField(source='rejected_by.username', read_only=True)
    
    class Meta:
        model = PaymentRequest
        fields = [
            'id',
            'allocation',
            'mukkadam_id',
            'requested_amount',
            'status',
            
            # Allocation details
            'job_id',
            'activity_name',
            'work_date',
            'allocated_area',
            
            # Timestamps
            'requested_at',
            'paid_at',
            'rejected_at',
            
            # Users
            'requested_by',
            'requested_by_name',
            'paid_by',
            'paid_by_name',
            'rejected_by',
            'rejected_by_name',
            
            # Notes
            'rejection_reason',
            'notes',
        ]
        read_only_fields = [
            'id',
            'mukkadam_id',
            'requested_amount',
            'requested_at',
            'requested_by',
            'paid_at',
            'paid_by',
            'rejected_at',
            'rejected_by',
        ]


class TransportPaymentRequestSerializer(serializers.ModelSerializer):
    # Allocation details
    job_id = serializers.CharField(source='allocation.job_activity.job_id', read_only=True)
    activity_name = serializers.CharField(source='allocation.job_activity.activity_name', read_only=True)
    work_date = serializers.DateField(source='allocation.work_date', read_only=True)
    mukkadam_id = serializers.IntegerField(source='allocation.mukkadam_id', read_only=True)
    
    # User details
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.username', read_only=True)
    rejected_by_name = serializers.CharField(source='rejected_by.username', read_only=True)
    
    class Meta:
        model = TransportPaymentRequest
        fields = [
            'id',
            'allocation',
            'transport_provider_id',
            'requested_amount',
            'status',
            
            # Allocation details
            'job_id',
            'activity_name',
            'work_date',
            'mukkadam_id',
            
            # Timestamps
            'requested_at',
            'paid_at',
            'rejected_at',
            
            # Users
            'requested_by',
            'requested_by_name',
            'paid_by',
            'paid_by_name',
            'rejected_by',
            'rejected_by_name',
            
            # Notes
            'rejection_reason',
            'notes',
        ]
        read_only_fields = [
            'id',
            'transport_provider_id',
            'requested_amount',
            'requested_at',
            'requested_by',
            'paid_at',
            'paid_by',
            'rejected_at',
            'rejected_by',
        ]

class ActivityLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True, allow_null=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    formatted_changes = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'activity_type',
            'activity_type_display',
            'description',
            'allocation_id',  # ✅ This is auto-generated by Django from the FK
            'job_id',
            'mukkadam_id',
            'mukkadam_name',
            'transport_provider_id',
            'transport_name',
            'amount',
            'performed_by',
            'performed_by_name',
            'performed_at',
            'changes',
            'formatted_changes',
            'metadata',
        ]
    
    # ... rest of serializer stays the same ...
    
    def get_formatted_changes(self, obj):
        """Format changes for frontend display"""
        if not obj.changes:
            return []
        
        formatted = []
        for field, change_data in obj.changes.items():
            if isinstance(change_data, dict) and 'old' in change_data and 'new' in change_data:
                formatted.append({
                    'field': field,
                    'label': change_data.get('label', field.replace('_', ' ').title()),
                    'old_value': change_data['old'],
                    'new_value': change_data['new'],
                })
        
        return formatted
from rest_framework import serializers




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


from rest_framework import serializers
