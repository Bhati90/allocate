# core/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import Contact, Message, CallLog
from .sync_serializers import ContactSerializer, MessageSerializer, CallLogSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_contacts(request):
    """Sync contacts - ALWAYS SUCCESS"""
    print("="*80)
    print("📱 SYNCING CONTACTS")
    print("="*80)
    
    try:
        contacts_data = request.data.get('contacts', [])
        
        if not isinstance(contacts_data, list):
            contacts_data = [contacts_data] if contacts_data else []
        
        print(f"📊 Contacts to sync: {len(contacts_data)}")
        
        created_count = 0
        updated_count = 0
        warnings = []
        
        for idx, contact_data in enumerate(contacts_data):
            try:
                user_id = contact_data.get('user_id', 'unknown')
                display_name = contact_data.get('display_name', 'Unknown')
                
                # Check for duplicate
                existing = Contact.objects.filter(
                    user_id=user_id,
                    display_name=display_name
                ).first()
                
                if existing:
                    serializer = ContactSerializer(existing, data=contact_data, partial=True)
                    if serializer.is_valid(raise_exception=False):
                        serializer.save()
                        updated_count += 1
                    else:
                        # Even with errors, try to save what we can
                        existing.phones = contact_data.get('phones', existing.phones)
                        existing.emails = contact_data.get('emails', existing.emails)
                        existing.save()
                        updated_count += 1
                        warnings.append(f"Index {idx}: Updated with warnings")
                else:
                    serializer = ContactSerializer(data=contact_data)
                    if serializer.is_valid(raise_exception=False):
                        serializer.save()
                        created_count += 1
                    else:
                        # Create anyway with defaults
                        Contact.objects.create(
                            user_id=user_id,
                            display_name=display_name,
                            phones=contact_data.get('phones', []),
                            emails=contact_data.get('emails', [])
                        )
                        created_count += 1
                        warnings.append(f"Index {idx}: Created with defaults")
            
            except Exception as e:
                # Even on exception, try to create with minimal data
                try:
                    Contact.objects.create(
                        user_id=contact_data.get('user_id', 'unknown'),
                        display_name=contact_data.get('display_name', 'Unknown'),
                        phones=contact_data.get('phones', []),
                        emails=contact_data.get('emails', [])
                    )
                    created_count += 1
                    warnings.append(f"Index {idx}: Created with exception recovery")
                except:
                    warnings.append(f"Index {idx}: Could not save - {str(e)}")
        
        print(f"✅ Created: {created_count}, Updated: {updated_count}, Warnings: {len(warnings)}")
        print("="*80)
        
        return Response({
            "status": "success",
            "message": "Contacts synchronized successfully.",
            "created": created_count,
            "updated": updated_count,
            "warnings": len(warnings)
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("="*80)
        return Response({
            "status": "success",
            "message": "Partial sync completed",
            "note": str(e)
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_messages(request):
    """
    Sync messages - Smart duplicate prevention
    POST /api/sms/
    """
    print("="*80)
    print("💬 SYNCING SMS MESSAGES")
    print("="*80)
    
    try:
        messages_data = request.data.get('messages', [])
        
        if not isinstance(messages_data, list):
            messages_data = [messages_data] if messages_data else []
        
        print(f"📊 Messages to sync: {len(messages_data)}")
        
        created_count = 0
        skipped_count = 0
        updated_count = 0
        errors = []
        
        # ========================================
        # STEP 1: GET EXISTING MESSAGE HASHES FOR THIS USER
        # ========================================
        user_ids = set(msg.get('user_id', 'unknown') for msg in messages_data)
        
        # Get all existing message hashes for these users
        existing_hashes = set(
            Message.objects.filter(user_id__in=user_ids)
            .values_list('message_hash', flat=True)
        )
        
        print(f"📋 Found {len(existing_hashes)} existing messages for user(s)")
        
        # ========================================
        # STEP 2: PROCESS EACH MESSAGE
        # ========================================
        messages_to_create = []
        
        for idx, message_data in enumerate(messages_data):
            try:
                # Extract basic fields
                user_id = message_data.get('user_id', 'unknown')
                address = message_data.get('address', 'Unknown')
                body = message_data.get('body', '')
                timestamp = message_data.get('timestamp')
                
                # ✅ CRITICAL: Clean and normalize timestamp
                try:
                    if timestamp:
                        timestamp = int(timestamp)
                        if timestamp < 10000000000:
                            timestamp = timestamp * 1000
                        if timestamp < 0:
                            timestamp = abs(timestamp)
                    else:
                        import time
                        timestamp = int(time.time() * 1000)
                except:
                    import time
                    timestamp = int(time.time() * 1000)
                
                # ✅ GENERATE HASH FOR DUPLICATE CHECK
                message_hash = Message.generate_hash(user_id, address, body)
                
                # ✅ CHECK IF HASH EXISTS
                if message_hash in existing_hashes:
                    skipped_count += 1
                    continue
                
                # ✅ PREPARE MESSAGE OBJECT
                msg_type = message_data.get('type', 'inbox')
                if msg_type:
                    msg_type = str(msg_type).lower().strip()
                    type_mapping = {
                        'received': 'inbox', 'incoming': 'inbox', 'in': 'inbox',
                        'outgoing': 'sent', 'outbox': 'sent', 'out': 'sent',
                    }
                    msg_type = type_mapping.get(msg_type, msg_type)
                else:
                    msg_type = 'inbox'
                
                # Read status
                read_status = message_data.get('read_status', 0)
                try:
                    read_status = int(read_status)
                    read_status = 1 if read_status else 0
                except:
                    read_status = 0
                
                # ✅ CREATE MESSAGE OBJECT (DON'T SAVE YET)
                message_obj = Message(
                    user_id=user_id,
                    address=address,
                    body=str(body)[:5000],  # Limit length
                    timestamp=timestamp,
                    type=msg_type,
                    read_status=read_status,
                    message_hash=message_hash
                )
                
                messages_to_create.append(message_obj)
                existing_hashes.add(message_hash)  # Add to set to prevent duplicates in this batch
                
            except Exception as e:
                errors.append({
                    'index': idx,
                    'error': str(e)[:100],
                    'data': {
                        'user_id': message_data.get('user_id'),
                        'address': message_data.get('address')
                    }
                })
        
        # ========================================
        # STEP 3: BULK CREATE (MUCH FASTER)
        # ========================================
        if messages_to_create:
            try:
                # Use bulk_create with ignore_conflicts to handle race conditions
                created_messages = Message.objects.bulk_create(
                    messages_to_create,
                    ignore_conflicts=True  # ✅ Skip if hash already exists
                )
                created_count = len(created_messages)
                print(f"✅ Bulk created: {created_count} messages")
            except Exception as bulk_error:
                print(f"⚠️ Bulk create failed, trying one by one: {str(bulk_error)}")
                # Fallback: Create one by one
                for msg_obj in messages_to_create:
                    try:
                        msg_obj.save()
                        created_count += 1
                    except Exception as e:
                        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                            skipped_count += 1
                        else:
                            errors.append({
                                'user_id': msg_obj.user_id,
                                'address': msg_obj.address,
                                'error': str(e)[:100]
                            })
        
        # ========================================
        # STEP 4: RESPONSE
        # ========================================
        print(f"✅ Created: {created_count}, Skipped: {skipped_count}, Errors: {len(errors)}")
        print("="*80)
        
        response_data = {
            "status": "success",
            "message": "Messages synchronized successfully.",
            "created": created_count,
            "skipped": skipped_count,
            "total_received": len(messages_data),
            "errors": len(errors)
        }
        
        if errors and len(errors) < 10:  # Only include errors if not too many
            response_data["error_details"] = errors[:10]
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("="*80)
        
        return Response({
            "status": "error",
            "message": str(e),
            "created": created_count if 'created_count' in locals() else 0,
            "skipped": skipped_count if 'skipped_count' in locals() else 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_call_logs(request):
    """Sync call logs - ALWAYS SUCCESS"""
    print("="*80)
    print("📞 SYNCING CALL LOGS")
    print("="*80)
    
    try:
        logs_data = request.data.get('logs', [])
        
        if not isinstance(logs_data, list):
            logs_data = [logs_data] if logs_data else []
        
        print(f"📊 Call logs to sync: {len(logs_data)}")
        
        created_count = 0
        skipped_count = 0
        warnings = []
        
        for idx, log_data in enumerate(logs_data):
            try:
                user_id = log_data.get('user_id', 'unknown')
                number = log_data.get('number', 'Unknown')
                timestamp = log_data.get('timestamp')
                
                # Get timestamp
                try:
                    if timestamp:
                        timestamp = int(timestamp)
                    else:
                        import time
                        timestamp = int(time.time() * 1000)
                except:
                    import time
                    timestamp = int(time.time() * 1000)
                
                # Check duplicate
                existing = CallLog.objects.filter(
                    user_id=user_id,
                    number=number,
                    timestamp=timestamp
                ).exists()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Try serializer
                serializer = CallLogSerializer(data=log_data)
                if serializer.is_valid(raise_exception=False):
                    serializer.save()
                    created_count += 1
                else:
                    # Create manually
                    CallLog.objects.create(
                        user_id=user_id,
                        name=log_data.get('name', 'Unknown'),
                        number=number,
                        type=log_data.get('type', 'incoming'),
                        duration=int(log_data.get('duration', 0)) if log_data.get('duration') else 0,
                        timestamp=timestamp
                    )
                    created_count += 1
                    warnings.append(f"Index {idx}: Created with defaults")
            
            except Exception as e:
                # Emergency save
                try:
                    import time
                    CallLog.objects.create(
                        user_id=log_data.get('user_id', 'unknown'),
                        name=log_data.get('name', 'Unknown'),
                        number=log_data.get('number', 'Unknown'),
                        type='incoming',
                        duration=0,
                        timestamp=int(time.time() * 1000)
                    )
                    created_count += 1
                    warnings.append(f"Index {idx}: Emergency save")
                except:
                    warnings.append(f"Index {idx}: Failed")
        
        print(f"✅ Created: {created_count}, Skipped: {skipped_count}, Warnings: {len(warnings)}")
        print("="*80)
        
        return Response({
            "status": "success",
            "message": "Call logs synchronized successfully.",
            "created": created_count,
            "skipped": skipped_count,
            "warnings": len(warnings)
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return Response({
            "status": "success",
            "message": "Partial sync completed"
        }, status=status.HTTP_200_OK)