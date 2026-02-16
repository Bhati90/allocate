# allocation_app/serializers.py

from rest_framework import serializers
from .models import JobActivity, Allocation, AllocationStats,ActivityLog,ImportedTransporter,ImportedMukkadam,ImportedFarmer,ImportedJobSheet
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

from rest_framework import serializers
from .models import FarmerCall

# allocation_app/serializers.py

class FarmerCallSerializer(serializers.ModelSerializer):
    # This pulls the 'audio_url' @property from your FarmerCall model
    audio_url = serializers.ReadOnlyField()

    class Meta:
        model = FarmerCall
        fields = [
            'id', 
            'call_sid', 
            'mobile_number', 
            'status', 
            'purpose', 
            'initiated_at', 
            'duration', 
            's3_key', 
            'audio_url'  # ✅ Included here
        ]
class ListFarmerCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmerCall
        fields = [
            'id', 'call_sid', 'mobile_number', 'status', 
            'purpose', 'initiated_at', 'duration', 
            's3_key', 'audio_url'
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
    
import requests
# serializers.py
from rest_framework import serializers
from .models import FarmerPayment

class FarmerPaymentSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='imported_farmer.name', read_only=True)
    
    class Meta:
        model = FarmerPayment
        fields = [
            'id',
            'activity_date',
            'farmer_name',
            'activity_name',
            'acres',
            'booking_value',
            'transportation_cost',
            'total_value',
            'payment_status',
            'payment_route',
            'date_of_payment',
            'description',
            'reference_no',
            'is_matched',
            'job_activity',
            'imported_farmer'
        ]
        read_only_fields = ['id', 'is_matched']


class FarmerPaymentSummarySerializer(serializers.Serializer):
    """Summary of farmer payments for a specific job or overall"""
    total_expected = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_pending = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_count = serializers.IntegerField()
    paid_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    last_payment_date = serializers.DateField(allow_null=True)
    completion_percentage = serializers.FloatField()
class AllocationSerializer(serializers.ModelSerializer):
    # Renamed field to match frontend expectation
    allocation_id = serializers.IntegerField(source='id', read_only=True)
    mukkadam_name = serializers.CharField(required=False, write_only=True)
    mukkadam_contact = serializers.CharField(required=False, write_only=True)
    transporter_name = serializers.CharField(required=False, allow_null=True, write_only=True)
    transporter_contact = serializers.CharField(required=False, allow_null=True, write_only=True)
    
    # Job details (from ImportedJobSheet)
    job = serializers.SerializerMethodField()
    
    # Activity details (from JobActivity or ImportedJobSheet)
    activity = serializers.SerializerMethodField()
    
    # Mukkadam details (from ImportedMukkadam)
    
    # Keep existing fields
    allocated_by = UserSerializer(read_only=True)
    created_by = serializers.SerializerMethodField()
    
    # Legacy fields for backward compatibility
    activity_name = serializers.CharField(source='job_activity.activity_name', read_only=True)
    job_id = serializers.CharField(source='job_activity.job_id', read_only=True)
    total_cost = serializers.ReadOnlyField()
    
    job_activity = serializers.PrimaryKeyRelatedField(
        queryset=JobActivity.objects.all(),
        required=False,
        allow_null=True
    )
    farmer_id = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    
    class Meta:
        model = Allocation
        fields = [
            # ✅ NEW: Primary fields matching frontend
            'allocation_id',
            'farmer_id',
            'farmer',
            'job',
            'activity',
            
            # Core allocation fields
            'mukkadam_id',
            'mukkadam_name',
            'mukkadam_contact',
            'allocated_area',
            'work_date',
            'mukkadam_price',
            'transport_type',
            'transport_provider_id',
            'transporter_name',
            'transporter_contact',
            'transport_price',
            'status',
            
            # Additional fields
            'crew_size',
            'notes',
            'allocated_at',
            'completed_at',
            'allocated_by',
            'created_by',
            
            # POC fields
            'farmer_poc',
            'labour_poc',
            'field_poc',
            
            # ✅ Legacy fields (for backward compatibility)
            'id',
            'farmer_work_id',
            'job_activity',
            'job_id',
            'activity_name',
            'own_transport_price',
            'total_cost',
        ]
        read_only_fields = [
            'allocation_id',
            'id', 
            'allocated_at', 
            'completed_at', 
            'allocated_by', 
            'total_cost',
            'farmer_work_id',
            'job_id',
            'activity_name',
            'farmer_id',
            'farmer',
            'job',
            'activity',
            'mukkadam_name',
            'mukkadam_contact',
            'transporter_name',
            'transporter_contact',
        ]
    def get_farmer_id(self, obj):
        """
        ✅ FIX: Use the same logic as get_job_details
        Get farmer_id from JobActivity.farmer_work_id
        """
        if not obj.job_activity:
            return None
        
        # ✅ This is what get_job_details uses - farmer_work_id IS the farmer_id
        return obj.job_activity.farmer_work_id

    def get_farmer(self, obj):
        """
        Get farmer details - EXACT SAME LOGIC as get_job_details
        """
        if not obj.job_activity:
            return {
                'farmer_id': None,
                'farmer_name': 'N/A',
                'phone_number': 'N/A',
                'location': 'N/A'
            }
        
        farmer_id = obj.job_activity.farmer_work_id
        farmer_info = None
        
        # ✅ STEP 1: Try to get from allocation's imported_farmer (if relationship exists)
        if hasattr(obj, 'imported_farmer') and obj.imported_farmer:
            farmer = obj.imported_farmer
            return {
                'farmer_id': farmer.external_farmer_id,
                'farmer_name': farmer.name,
                'phone_number': farmer.contact_no or 'N/A',
                'location': farmer.location or 'N/A',
                'village': farmer.location.split(',')[0].strip() if farmer.location and ',' in farmer.location else '',
                'taluka': farmer.location.split(',')[1].strip() if farmer.location and farmer.location.count(',') >= 1 else '',
                'district': farmer.location.split(',')[2].strip() if farmer.location and farmer.location.count(',') >= 2 else '',
            }
        
        # ✅ STEP 2: Try allocation's farmer_name field
        elif obj.farmer_name:
            return {
                'farmer_id': farmer_id,
                'farmer_name': obj.farmer_name,
                'phone_number': obj.farmer_contact or 'N/A',
                'location': obj.job_activity.location or 'N/A'
            }
        
        # ✅ STEP 3: Try to find in ImportedFarmer by external_farmer_id
        else:
            if farmer_id:
                try:
                    farmer = ImportedFarmer.objects.filter(external_farmer_id=farmer_id).first()
                    if farmer:
                        location_parts = farmer.location.split(',') if farmer.location else []
                        return {
                            'farmer_id': farmer.external_farmer_id,
                            'farmer_name': farmer.name,
                            'phone_number': farmer.contact_no or 'N/A',
                            'location': farmer.location or 'N/A',
                            'village': location_parts[0].strip() if len(location_parts) > 0 else '',
                            'taluka': location_parts[1].strip() if len(location_parts) > 1 else '',
                            'district': location_parts[2].strip() if len(location_parts) > 2 else '',
                        }
                except Exception as e:
                    print(f"Error fetching farmer {farmer_id}: {str(e)}")
            
            # ✅ STEP 4: Last resort - use job data
            return {
                'farmer_id': farmer_id,
                'farmer_name': 'Unknown',
                'phone_number': 'N/A',
                'location': obj.job_activity.location or 'N/A'
            }

    def get_job(self, obj):
        """Get job details from ImportedJobSheet (LOCAL DB)"""
        if not obj.job_activity:
            return {
                'job_id': 'N/A',
                'job_name': 'N/A',
                'scheduled_date': 'N/A',
                'location': 'N/A',
                
            }
        
        job_id = obj.job_activity.job_id
        
        # ✅ Get from ImportedJobSheet (NOT external API)
        try:
            job_sheet = ImportedJobSheet.objects.filter(
                generated_job_id=job_id
            ).first()
            
            if job_sheet:
                return {
                    'job_id': job_id,
                    'job_name': f"Job #{job_id}",
                    'scheduled_date': str(job_sheet.activity_start_date) if job_sheet.activity_start_date else 'N/A',
                    'location': job_sheet.location or 'N/A',
                    
                    
                    'farmer_name': job_sheet.farmer_name,
                    'central_team_phone': '+91-804-7361465'
                }
        except Exception as e:
            print(f"❌ Error fetching job {job_id} from ImportedJobSheet: {str(e)}")
        
        # Fallback from JobActivity
        return {
            'job_id': job_id,
            'job_name': f"Job #{job_id}",
            'scheduled_date': str(obj.job_activity.scheduled_datetime.date()) if obj.job_activity.scheduled_datetime else 'N/A',
            'location': obj.job_activity.location or 'N/A',
            
            
        }
    
    def get_activity(self, obj):
        """Get activity details from JobActivity"""
        if not obj.job_activity:
            return {
                'activity_id': 'N/A',
                'activity_name': 'Unknown',
                'activity_type': 'N/A',
                'total_area': 0,
                'scheduled_date': 'N/A',
                'scheduled_time': 'N/A'
            }
        
        return {
            'activity_id': obj.job_activity.activity_id or 'N/A',
            'activity_name': obj.job_activity.activity_name or 'Unknown',
            'activity_type': obj.job_activity.activity_type or 'N/A',
            'total_area': float(obj.job_activity.total_area or 0),
            'scheduled_date': str(obj.job_activity.scheduled_datetime.date()) if obj.job_activity.scheduled_datetime else 'N/A',
            'scheduled_time': str(obj.job_activity.scheduled_datetime.time()) if obj.job_activity.scheduled_datetime else 'N/A'
        }
    
    def get_mukkadam_name(self, obj):
        """Get mukkadam name from ImportedMukkadam (LOCAL DB)"""
        if obj.imported_mukkadam:
            return obj.imported_mukkadam.team_name
        
        # Fallback: Try to fetch from ImportedMukkadam
        try:
            mukkadam = ImportedMukkadam.objects.filter(external_mukkadam_id=obj.mukkadam_id).first()
            if mukkadam:
                return mukkadam.team_name
        except:
            pass
        
        return f"Mukkadam #{obj.mukkadam_id}"
    
    def get_mukkadam_contact(self, obj):
        """Get mukkadam contact from ImportedMukkadam (LOCAL DB)"""
        if obj.imported_mukkadam:
            return obj.imported_mukkadam.contact_no
        
        # Fallback: Try to fetch from ImportedMukkadam
        try:
            mukkadam = ImportedMukkadam.objects.filter(external_mukkadam_id=obj.mukkadam_id).first()
            if mukkadam:
                return mukkadam.contact_no
        except:
            pass
        
        return None
    
    def get_transporter_name(self, obj):
        """Get transporter name from ImportedTransporter (LOCAL DB)"""
        if obj.transport_type != 'provider':
            return None
        
        if obj.imported_transporter:
            return obj.imported_transporter.name
        
        # Fallback: Try to fetch from ImportedTransporter
        if obj.transport_provider_id:
            try:
                transporter = ImportedTransporter.objects.filter(
                    external_transporter_id=obj.transport_provider_id
                ).first()
                if transporter:
                    return transporter.name
            except:
                pass
            
            return f"Transporter #{obj.transport_provider_id}"
        
        return None
    
    def get_transporter_contact(self, obj):
        """Get transporter contact from ImportedTransporter (LOCAL DB)"""
        if obj.transport_type != 'provider':
            return None
        
        if obj.imported_transporter:
            return obj.imported_transporter.contact_no
        
        # Fallback: Try to fetch from ImportedTransporter
        if obj.transport_provider_id:
            try:
                transporter = ImportedTransporter.objects.filter(
                    external_transporter_id=obj.transport_provider_id
                ).first()
                if transporter:
                    return transporter.contact_no
            except:
                pass
        
        return None
    
    def get_created_by(self, obj):
        if obj.allocated_by:
            return UserSerializer(obj.allocated_by).data
        return None
    
    def create(self, validated_data):
        # ✅ Extract name fields (not in Allocation model)
        mukkadam_name = validated_data.pop('mukkadam_name', None)
        mukkadam_contact = validated_data.pop('mukkadam_contact', None)
        transporter_name = validated_data.pop('transporter_name', None)
        transporter_contact = validated_data.pop('transporter_contact', None)
        
        mukkadam_id = validated_data.get('mukkadam_id')
        transport_provider_id = validated_data.get('transport_provider_id')
        
        # ✅ Get or create ImportedMukkadam
        if mukkadam_id and mukkadam_name:
            imported_mukkadam, created = ImportedMukkadam.objects.get_or_create(
                external_mukkadam_id=mukkadam_id,
                defaults={
                    'team_name': mukkadam_name,
                    'contact_no': mukkadam_contact or '',
                    'created_from_import': False,  # Created from allocation
                }
            )
            
            # Update name if it changed
            if not created and imported_mukkadam.team_name != mukkadam_name:
                imported_mukkadam.team_name = mukkadam_name
                if mukkadam_contact:
                    imported_mukkadam.contact_no = mukkadam_contact
                imported_mukkadam.save()
            
            validated_data['imported_mukkadam'] = imported_mukkadam
            print(f"✅ Linked ImportedMukkadam: {imported_mukkadam.team_name}")
        
        # ✅ Get or create ImportedTransporter
        if transport_provider_id and transporter_name:
            imported_transporter, created = ImportedTransporter.objects.get_or_create(
                external_transporter_id=transport_provider_id,
                defaults={
                    'name': transporter_name,
                    'contact_no': transporter_contact or '',
                    'created_from_import': False,
                }
            )
            
            # Update name if it changed
            if not created and imported_transporter.name != transporter_name:
                imported_transporter.name = transporter_name
                if transporter_contact:
                    imported_transporter.contact_no = transporter_contact
                imported_transporter.save()
            
            validated_data['imported_transporter'] = imported_transporter
            print(f"✅ Linked ImportedTransporter: {imported_transporter.name}")
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # ✅ Handle name updates
        mukkadam_name = validated_data.pop('mukkadam_name', None)
        mukkadam_contact = validated_data.pop('mukkadam_contact', None)
        transporter_name = validated_data.pop('transporter_name', None)
        transporter_contact = validated_data.pop('transporter_contact', None)
        
        mukkadam_id = validated_data.get('mukkadam_id', instance.mukkadam_id)
        transport_provider_id = validated_data.get('transport_provider_id', instance.transport_provider_id)
        
        # ✅ Update or create ImportedMukkadam
        if mukkadam_id and mukkadam_name:
            imported_mukkadam, created = ImportedMukkadam.objects.get_or_create(
                external_mukkadam_id=mukkadam_id,
                defaults={
                    'team_name': mukkadam_name,
                    'contact_no': mukkadam_contact or '',
                    'created_from_import': False,
                }
            )
            
            if not created:
                imported_mukkadam.team_name = mukkadam_name
                if mukkadam_contact:
                    imported_mukkadam.contact_no = mukkadam_contact
                imported_mukkadam.save()
            
            validated_data['imported_mukkadam'] = imported_mukkadam
        
        # ✅ Update or create ImportedTransporter
        if transport_provider_id and transporter_name:
            imported_transporter, created = ImportedTransporter.objects.get_or_create(
                external_transporter_id=transport_provider_id,
                defaults={
                    'name': transporter_name,
                    'contact_no': transporter_contact or '',
                    'created_from_import': False,
                }
            )
            
            if not created:
                imported_transporter.name = transporter_name
                if transporter_contact:
                    imported_transporter.contact_no = transporter_contact
                imported_transporter.save()
            
            validated_data['imported_transporter'] = imported_transporter
        
        return super().update(instance, validated_data)



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