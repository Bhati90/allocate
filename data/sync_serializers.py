# core/sync_serializers.py

from rest_framework import serializers
from .models import Contact, Message, CallLog


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'user_id', 'display_name', 'phones', 'emails', 'synced_at']
        read_only_fields = ['id', 'synced_at']
    
    def validate_phones(self, value):
        """Accept anything - convert to list if needed"""
        if value is None:
            return []
        if not isinstance(value, list):
            return [str(value)]
        return value if value else []
    
    def validate_emails(self, value):
        """Accept anything - convert to list if needed"""
        if value is None:
            return []
        if not isinstance(value, list):
            return [str(value)]
        return value if value else []


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'user_id', 'address', 'body', 'timestamp', 'type', 'read_status', 'synced_at']
        read_only_fields = ['id', 'synced_at']
    
    def validate_timestamp(self, value):
        """Accept ANY timestamp format - just convert to int"""
        if value is None or value == '':
            # Use current time in milliseconds
            import time
            return int(time.time() * 1000)
        
        # Try to convert to int
        try:
            if isinstance(value, str):
                # Remove any non-digit characters
                cleaned = ''.join(filter(str.isdigit, value))
                if cleaned:
                    value = int(cleaned)
                else:
                    import time
                    return int(time.time() * 1000)
            
            value = int(value)
            
            # If too small (probably seconds), convert to milliseconds
            if value < 10000000000:  # Less than Sep 2001 in seconds
                value = value * 1000
            
            # If negative, make positive
            if value < 0:
                value = abs(value)
            
            return value
        except:
            # If all else fails, use current time
            import time
            return int(time.time() * 1000)
    
    def validate_type(self, value):
        """Accept ANY type - just store it"""
        if not value:
            return 'inbox'
        
        # Convert to lowercase and clean
        value = str(value).lower().strip()
        
        # Map common variations
        type_mapping = {
            'received': 'inbox',
            'incoming': 'inbox',
            'in': 'inbox',
            'outgoing': 'sent',
            'outbox': 'sent',
            'out': 'sent',
        }
        
        return type_mapping.get(value, value)
    
    def validate_read_status(self, value):
        """Accept ANY read status - convert to 0 or 1"""
        if value is None or value == '':
            return 0
        
        # Try to convert to int
        try:
            value = int(value)
            return 1 if value else 0
        except:
            # If it's a string like "true", "read", etc.
            if isinstance(value, str):
                if value.lower() in ['true', 'read', '1', 'yes']:
                    return 1
            return 0
    
    def validate_address(self, value):
        """Accept any address"""
        if not value:
            return 'Unknown'
        return str(value)
    
    def validate_body(self, value):
        """Accept any body"""
        if value is None:
            return ''
        return str(value)
    
    def validate_user_id(self, value):
        """Accept any user_id"""
        if not value:
            return 'unknown'
        return str(value)


class CallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = ['id', 'user_id', 'name', 'number', 'type', 'duration', 'timestamp', 'synced_at']
        read_only_fields = ['id', 'synced_at']
    
    def validate_timestamp(self, value):
        """Accept ANY timestamp format - just convert to int"""
        if value is None or value == '':
            import time
            return int(time.time() * 1000)
        
        try:
            if isinstance(value, str):
                cleaned = ''.join(filter(str.isdigit, value))
                if cleaned:
                    value = int(cleaned)
                else:
                    import time
                    return int(time.time() * 1000)
            
            value = int(value)
            
            # If too small (probably seconds), convert to milliseconds
            if value < 10000000000:
                value = value * 1000
            
            if value < 0:
                value = abs(value)
            
            return value
        except:
            import time
            return int(time.time() * 1000)
    
    def validate_type(self, value):
        """Accept ANY call type"""
        if not value:
            return 'incoming'
        
        value = str(value).lower().strip()
        
        # Map variations
        type_mapping = {
            'in': 'incoming',
            'out': 'outgoing',
            'miss': 'missed',
            'reject': 'rejected',
        }
        
        return type_mapping.get(value, value)
    
    def validate_duration(self, value):
        """Accept any duration - convert to int"""
        if value is None or value == '':
            return 0
        
        try:
            return int(value)
        except:
            return 0
    
    def validate_number(self, value):
        """Accept any number"""
        if not value:
            return None
        return str(value)
    
    def validate_name(self, value):
        """Accept any name"""
        if not value:
            return 'Unknown'
        return str(value)
    
    def validate_user_id(self, value):
        """Accept any user_id"""
        if not value:
            return 'unknown'
        return str(value)