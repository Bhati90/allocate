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

# allocation_app/serializers.py
class ActivityLogSerializer(serializers.ModelSerializer):
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    mukkadam_name = serializers.SerializerMethodField()  # ✅ Use cache
    transport_name = serializers.SerializerMethodField()  # ✅ Use cache
    farmer_name = serializers.SerializerMethodField()
    farmer_work_id = serializers.SerializerMethodField()
    activity_edit_details = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityLog
        fields = [
            'id', 'activity_type', 'activity_type_display', 'description',
            'allocation', 'job_id', 'mukkadam_id', 'mukkadam_name',
            'transport_provider_id', 'transport_name', 'amount',
            'performed_by', 'performed_by_name', 'performed_at',
            'changes', 'metadata', 'reason',
            'farmer_name', 'farmer_work_id',
            'activity_edit_details',
            'payment_request', 'transport_payment_request'
        ]
        read_only_fields = ['performed_at']
    
    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.username
        return 'System'
    
    def get_mukkadam_name(self, obj):
        """Get mukkadam name from cache if available"""
        mukkadams_cache = self.context.get('mukkadams_cache', {})
        
        if obj.mukkadam_id and mukkadams_cache:
            mukkadam_data = mukkadams_cache.get(obj.mukkadam_id)
            if mukkadam_data:
                return mukkadam_data.get('mukkadam_name', f'Mukkadam #{obj.mukkadam_id}')
        
        # Fallback to stored name or ID
        return obj.mukkadam_name or f'Mukkadam #{obj.mukkadam_id}' if obj.mukkadam_id else 'Unknown'
    
    def get_transport_name(self, obj):
        """Get transport name from cache if available"""
        transport_cache = self.context.get('transport_providers_cache', {})
        
        if obj.transport_provider_id and transport_cache:
            transport_data = transport_cache.get(obj.transport_provider_id)
            if transport_data:
                return transport_data.get('name', f'Provider #{obj.transport_provider_id}')
        
        # Fallback to stored name or ID
        return obj.transport_name or f'Provider #{obj.transport_provider_id}' if obj.transport_provider_id else None
    
    def get_farmer_name(self, obj):
        """Fetch farmer name from allocation → job_activity"""
        try:
            # ✅ Check if allocation exists
            if not obj.allocation:
                return None
            
            # ✅ Get job_activity
            job_activity = obj.allocation.job_activity
            if not job_activity:
                return None
            
            # ✅ Get farmer_work_id field (you need to add this to JobActivity model!)
            farmer_work_id = getattr(job_activity, 'farmer_work_id', None)
            
            # ✅ TEMPORARY: If farmer_work_id doesn't exist yet, extract from job_id
            if not farmer_work_id:
                # If your job_id is like "FV123" and farmer API uses numeric IDs,
                # you might need to parse or look it up differently
                # For now, let's try using job_id directly
                farmer_work_id = job_activity.job_id
            
            if not farmer_work_id:
                return None
            
            # ✅ Fetch from cache/API
            from .utils import get_farmer_cached
            farmer_data = get_farmer_cached(str(farmer_work_id))
            
            if farmer_data:
                return farmer_data.get('farmer_name', 'Unknown')
            
            return 'Unknown'
                
        except Exception as e:
            print(f"❌ Error fetching farmer name for log {obj.id}: {str(e)}")
            return 'Unknown'
    
    def get_farmer_work_id(self, obj):
        """Get farmer_work_id from allocation"""
        try:
            if obj.allocation and obj.allocation.job_activity:
                # Try the new field first
                farmer_work_id = getattr(obj.allocation.job_activity, 'farmer_work_id', None)
                # Fallback to job_id if farmer_work_id doesn't exist
                return farmer_work_id or obj.allocation.job_activity.job_id
            return None
        except Exception:
            return None
    
    def get_reason(self, obj):
        """Extract reason - admin only"""
        is_admin = self.context.get('is_admin', False)
        
        if not is_admin:
            return None
        
        try:
            # Check metadata first
            if obj.metadata and 'reason' in obj.metadata:
                return obj.metadata['reason']
            
            # For activity edits, check changes
            if obj.activity_type == 'activity_marked_edited' and obj.changes:
                if 'reason' in obj.changes:
                    return obj.changes['reason']
            
            return None
        except Exception:
            return None
    
    def get_activity_edit_details(self, obj):
        """
        For activity_marked_edited logs, fetch ALL changes from ActivityEditHistory
        ADMIN ONLY
        """
        is_admin = self.context.get('is_admin', False)
        
        if not is_admin or obj.activity_type != 'activity_marked_edited':
            return None
        
        try:
            # ✅ Check if allocation exists
            if not obj.allocation:
                return None
            
            # ✅ Get job_activity from allocation
            job_activity = obj.allocation.job_activity
            if not job_activity:
                return None
            
            # ✅ Find the most recent ActivityEditHistory
            from .models import ActivityEditHistory
            edit_history = ActivityEditHistory.objects.filter(
                job_activity=job_activity
            ).order_by('-edited_at').first()
            
            if not edit_history:
                return None
            
            # ✅ Return all changes with formatted data
            return {
                'edited_by': edit_history.edited_by.username if edit_history.edited_by else 'System',
                'edited_at': edit_history.edited_at.isoformat(),
                'reason': edit_history.reason,
                'changes': edit_history.changes  # Contains all field changes
            }
            
        except Exception as e:
            print(f"❌ Error fetching activity edit details for log {obj.id}: {str(e)}")
            return None
    
    def to_representation(self, instance):
        """Add timestamp field for frontend compatibility"""
        data = super().to_representation(instance)
        data['timestamp'] = instance.performed_at  # Add alias for frontend
        return data

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

# allocation_app/serializers.py
from .models import ActivityEditHistory,ActivityLostRecord
class ActivityEditHistorySerializer(serializers.ModelSerializer):
    edited_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityEditHistory
        fields = '__all__'
    
    def get_edited_by_name(self, obj):
        return obj.edited_by.username if obj.edited_by else 'System'


class ActivityLostRecordSerializer(serializers.ModelSerializer):
    marked_by_name = serializers.SerializerMethodField()
    unmarked_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityLostRecord
        fields = '__all__'
    
    def get_marked_by_name(self, obj):
        return obj.marked_by.username if obj.marked_by else 'System'
    
    def get_unmarked_by_name(self, obj):
        return obj.unmarked_by.username if obj.unmarked_by else None


# Update JobActivitySerializer to include lost status
class JobActivitySerializer(serializers.ModelSerializer):
    remaining_area = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_fully_allocated = serializers.BooleanField(read_only=True)
    allocations = AllocationSerializer(many=True, read_only=True)
    
    # ✅ NEW FIELDS
    is_lost = serializers.SerializerMethodField()
    lost_reason = serializers.SerializerMethodField()
    edit_history_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobActivity
        fields = '__all__'
    
    def get_is_lost(self, obj):
        try:
            return obj.lost_record.is_active if hasattr(obj, 'lost_record') else False
        except ActivityLostRecord.DoesNotExist:
            return False
    
    def get_lost_reason(self, obj):
        try:
            return obj.lost_record.reason if hasattr(obj, 'lost_record') and obj.lost_record.is_active else None
        except ActivityLostRecord.DoesNotExist:
            return None
    
    def get_edit_history_count(self, obj):
        return obj.edit_history.count() if hasattr(obj, 'edit_history') else 0