from rest_framework import serializers
from .models import Mukkadam,Allocation

class MukkadamFullSerializer(serializers.ModelSerializer):
    # Read-only fields to show names instead of just IDs
    referred_by_name = serializers.CharField(source='referred_by.mukkadam_name', read_only=True)
    
    # Get list of people this person has referred
    referrals_list = serializers.SerializerMethodField()

    class Meta:
        model = Mukkadam
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'referrals_list', 'referred_by_name']

    def get_referrals_list(self, obj):
        # Return a list of names and IDs of people this person referred
        return obj.referrals_made.values('id', 'mukkadam_name', 'village')

# Helper serializer for the Dropdown in the Form
class MukkadamDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        fields = ['id', 'mukkadam_name', 'mobile_numbers', 'village']

class MukkadamListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        # Exclude sensitive fields for the general list
        exclude = [
            'mobile_numbers', 
            'deputy_mukkadam_mobile', 
            'payment_details', 
            'team_members',
            'aadhar_card',
            'pan_card',
            'bank_proof'
        ]

class MukkadamMinimalSerializer(serializers.ModelSerializer):
    """Minimal mukkadam info"""
    class Meta:
        model = Mukkadam
        fields = [
            'id',
            'mukkadam_name', 
            'mobile_numbers', 
            'village',
            'crew_size',
            'has_smartphone',
            'preferred_work_locations',
            'work_mode'
        ]


class MukkadamQuickRegistrationSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for quick mukkadam registration
    Only requires: name, village, mobile, crew_size, is_permanent
    """
    class Meta:
        model = Mukkadam
        fields = [
            'id',
            'mukkadam_name',
            'village',
            'mobile_numbers',
            'crew_size',
            'is_permanent',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        
from rest_framework import serializers
from .models import Job, JobAssignment, Mukkadam, AssignmentLog


class MukkadamBasicSerializer(serializers.ModelSerializer):
    """Basic mukkadam info for dropdowns and lists"""
    class Meta:
        model = Mukkadam
        fields = [
            'id', 
            'mukkadam_name', 
            'mobile_numbers', 
            'village',
            'crew_size',
            'max_crew_capacity',
            'has_smartphone',
            'team_members',
        ]



class AllocationSerializer(serializers.ModelSerializer):
    # Optional: Show readable names instead of just IDs
    job_title = serializers.CharField(source='job.title', read_only=True)
    mukkadam_name = serializers.CharField(source='mukkadam.mukkadam_name', read_only=True)
    
    class Meta:
        model = Allocation
        fields = [
            'id',
            'farmer_work_id',
            'mukkadam',
            'transport_provider_name',
            'mukkadam_price',
            'transport_price',
            'completed_at',
            # Read-only display fields
            'job_title',
            'mukkadam_name',
        ]
        read_only_fields = ['id', 'completed_at', 'job_title', 'mukkadam_name']


class AssignmentLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AssignmentLog
        fields = ['id', 'action', 'details', 'timestamp', 'user', 'user_name']