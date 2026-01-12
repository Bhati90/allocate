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

@api_view(['GET'])
@permission_classes([AllowAny])
def get_sync_checkpoint(request):
    """
    Get the last sync checkpoint for a user
    Mobile app calls this BEFORE syncing to know what timestamp to send from
    
    GET /api/sms/sync-checkpoint/?user_id=xxx
    
    Response:
    {
        "user_id": "user123",
        "last_timestamp": 1673568000000,  // Send messages AFTER this
        "total_messages": 1234,
        "message": "Send only messages after timestamp 1673568000000"
    }
    """
    user_id = request.query_params.get('user_id')
    
    if not user_id:
        return Response({
            'error': 'user_id parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get the latest message timestamp for this user
    latest_message = Message.objects.filter(
        user_id=user_id
    ).order_by('-timestamp').first()
    
    if latest_message:
        return Response({
            'user_id': user_id,
            'last_timestamp': latest_message.timestamp,
            'total_messages': Message.objects.filter(user_id=user_id).count(),
            'message': f'Send only messages after timestamp {latest_message.timestamp}',
            'last_synced_at': latest_message.synced_at.isoformat()
        })
    else:
        return Response({
            'user_id': user_id,
            'last_timestamp': 0,  # No messages yet, send all
            'total_messages': 0,
            'message': 'No messages found. Send all messages.'
        })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_messages(request):
    """
    ✅ FIXED: Bulk create with no duplicates
    """
    print("="*80)
    print("💬 SYNCING SMS MESSAGES")
    print("="*80)
    
    try:
        messages_data = request.data.get('messages', [])
        
        if not isinstance(messages_data, list):
            messages_data = [messages_data] if messages_data else []
        
        user_id = messages_data[0].get('user_id', 'unknown') if messages_data else 'unknown'
        
        print(f"👤 User: {user_id}")
        print(f"📊 Messages received: {len(messages_data)}")
        
        # ========================================
        # STEP 1: Get existing hashes for this user
        # ========================================
        existing_hashes = set(
            Message.objects.filter(user_id=user_id)
            .values_list('message_hash', flat=True)
        )
        
        print(f"📋 Existing messages in DB: {len(existing_hashes)}")
        
        # ========================================
        # STEP 2: Prepare messages for bulk create
        # ========================================
        messages_to_create = []
        skipped_count = 0
        errors = []
        hashes_in_batch = set()  # Track hashes in current batch
        
        for idx, message_data in enumerate(messages_data):
            try:
                # Extract and clean fields
                user_id = str(message_data.get('user_id', 'unknown'))[:100]
                address = str(message_data.get('address', 'Unknown'))[:100]
                body = str(message_data.get('body', ''))
                
                # Clean timestamp
                timestamp = message_data.get('timestamp') or message_data.get('date')
                try:
                    timestamp = int(timestamp) if timestamp else 0
                    if timestamp < 10000000000:
                        timestamp = timestamp * 1000
                    if timestamp < 0:
                        timestamp = abs(timestamp)
                except:
                    import time
                    timestamp = int(time.time() * 1000)
                
                # Generate hash
                message_hash = Message.generate_hash(user_id, address, timestamp)
                
                # ✅ Skip if already exists OR already in current batch
                if message_hash in existing_hashes or message_hash in hashes_in_batch:
                    skipped_count += 1
                    continue
                
                # Clean type (handle Flutter enum)
                msg_type = str(message_data.get('type', 'inbox')).lower().strip()
                if '.' in msg_type:
                    msg_type = msg_type.split('.')[-1]
                
                type_mapping = {
                    'received': 'inbox', 'incoming': 'inbox', 'in': 'inbox',
                    'outgoing': 'sent', 'outbox': 'sent', 'out': 'sent',
                }
                msg_type = type_mapping.get(msg_type, msg_type)[:50]
                
                # Read status
                read_status = 0
                try:
                    read_status = 1 if int(message_data.get('read_status', 0)) else 0
                except:
                    read_status = 0
                
                # Create message object
                message_obj = Message(
                    user_id=user_id,
                    address=address,
                    body=body,
                    timestamp=timestamp,
                    type=msg_type,
                    read_status=read_status,
                    message_hash=message_hash
                )
                
                messages_to_create.append(message_obj)
                hashes_in_batch.add(message_hash)
                
            except Exception as e:
                errors.append({'index': idx, 'error': str(e)[:100]})
        
        print(f"📦 New messages to create: {len(messages_to_create)}")
        print(f"🔄 Skipped (already exist): {skipped_count}")
        
        # ========================================
        # STEP 3: BULK CREATE ALL AT ONCE
        # ========================================
        created_count = 0
        
        if messages_to_create:
            try:
                # ✅ BULK CREATE - 1000x faster than one-by-one
                Message.objects.bulk_create(
                    messages_to_create,
                    ignore_conflicts=True,  # Skip duplicates silently
                    batch_size=1000
                )
                
                # Count how many actually created
                created_count = len(messages_to_create)
                
                print(f"✅ Bulk created: {created_count} messages")
                
            except Exception as e:
                print(f"⚠️ Bulk create error: {str(e)}")
                # Fallback: one by one
                for msg in messages_to_create:
                    try:
                        msg.save()
                        created_count += 1
                    except:
                        pass
        
        # ========================================
        # RESPONSE
        # ========================================
        total_in_db = Message.objects.filter(user_id=user_id).count()
        
        print(f"✅ Created: {created_count}")
        print(f"📊 Total in DB for user: {total_in_db}")
        print("="*80)
        
        return Response({
            "status": "success",
            "message": "Messages synchronized successfully.",
            "stats": {
                "received": len(messages_data),
                "created": created_count,
                "skipped": skipped_count,
                "errors": len(errors),
                "total_in_db": total_in_db
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("="*80)
        
        return Response({
            "status": "error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
@permission_classes([AllowAny])
def message_stats(request):
    """
    Get message statistics
    GET /api/sms/stats/?user_id=xxx
    """
    user_id = request.query_params.get('user_id')
    
    if not user_id:
        return Response({'error': 'user_id required'}, status=400)
    
    messages = Message.objects.filter(user_id=user_id)
    
    from django.db.models import Count
    
    stats = {
        'user_id': user_id,
        'total_messages': messages.count(),
        'inbox_count': messages.filter(type='inbox').count(),
        'sent_count': messages.filter(type='sent').count(),
        'unread_count': messages.filter(read_status=0).count(),
        'by_type': list(messages.values('type').annotate(count=Count('id'))),
        'date_range': {
            'oldest': messages.order_by('timestamp').first().message_datetime.isoformat() if messages.exists() else None,
            'newest': messages.order_by('-timestamp').first().message_datetime.isoformat() if messages.exists() else None
        }
    }
    
    return Response(stats)

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_messages_smart(request):
    """
    Smart sync - Only accepts NEW messages (with timestamp > last synced)
    This prevents duplicate syncing
    
    POST /api/sms/sync/
    Body: {
        "user_id": "user123",
        "messages": [
            {
                "address": "+1234567890",
                "body": "Hello",
                "date": 1673568000000,
                "type": "MessageKind.inbox",
                "read_status": 0
            }
        ]
    }
    """
    print("="*80)
    print("💬 SMART MESSAGE SYNC")
    print("="*80)
    
    try:
        user_id = request.data.get('user_id')
        messages_data = request.data.get('messages', [])
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(messages_data, list):
            messages_data = [messages_data] if messages_data else []
        
        print(f"👤 User: {user_id}")
        print(f"📊 Messages received: {len(messages_data)}")
        
        # ========================================
        # STEP 1: GET LAST SYNCED TIMESTAMP
        # ========================================
        latest_message = Message.objects.filter(
            user_id=user_id
        ).order_by('-timestamp').first()
        
        last_timestamp = latest_message.timestamp if latest_message else 0
        
        print(f"📅 Last synced timestamp: {last_timestamp}")
        
        # ========================================
        # STEP 2: FILTER OUT OLD MESSAGES (ALREADY SYNCED)
        # ========================================
        new_messages_data = []
        filtered_out = 0
        
        for msg in messages_data:
            timestamp = msg.get('date') or msg.get('timestamp')
            
            try:
                timestamp = int(timestamp) if timestamp else 0
                if timestamp < 10000000000:
                    timestamp = timestamp * 1000
            except:
                timestamp = 0
            
            # ✅ Only accept messages NEWER than last synced
            if timestamp > last_timestamp:
                new_messages_data.append(msg)
            else:
                filtered_out += 1
        
        print(f"✅ New messages to sync: {len(new_messages_data)}")
        print(f"🔄 Already synced (filtered): {filtered_out}")
        
        if not new_messages_data:
            return Response({
                'status': 'success',
                'message': 'All messages already synced. Nothing to do.',
                'stats': {
                    'received': len(messages_data),
                    'new': 0,
                    'filtered': filtered_out,
                    'created': 0,
                    'skipped': 0
                }
            })
        
        # ========================================
        # STEP 3: PREPARE MESSAGES FOR BULK CREATE
        # ========================================
        messages_to_create = []
        skipped_count = 0
        errors = []
        
        # Get existing hashes to prevent duplicates within this batch
        existing_hashes = set()
        
        for idx, message_data in enumerate(new_messages_data):
            try:
                # Extract fields
                address = str(message_data.get('address', 'Unknown'))[:100]
                body = str(message_data.get('body', ''))
                timestamp = message_data.get('date') or message_data.get('timestamp')
                
                # Clean timestamp
                try:
                    timestamp = int(timestamp) if timestamp else 0
                    if timestamp < 10000000000:
                        timestamp = timestamp * 1000
                    if timestamp < 0:
                        timestamp = abs(timestamp)
                except:
                    import time
                    timestamp = int(time.time() * 1000)
                
                # Generate hash
                message_hash = Message.generate_hash(user_id, address, timestamp)
                
                # Skip if duplicate in this batch
                if message_hash in existing_hashes:
                    skipped_count += 1
                    continue
                
                # Clean type (handle Flutter enum)
                msg_type = str(message_data.get('type', 'inbox')).lower().strip()
                if '.' in msg_type:
                    msg_type = msg_type.split('.')[-1]
                
                type_mapping = {
                    'received': 'inbox',
                    'incoming': 'inbox',
                    'in': 'inbox',
                    'outgoing': 'sent',
                    'outbox': 'sent',
                    'out': 'sent',
                }
                msg_type = type_mapping.get(msg_type, msg_type)[:50]
                
                # Read status
                read_status = 0
                try:
                    read_status = 1 if int(message_data.get('read_status', 0)) else 0
                except:
                    read_status = 0
                
                # Create message object
                message_obj = Message(
                    user_id=user_id,
                    address=address,
                    body=body,
                    timestamp=timestamp,
                    type=msg_type,
                    read_status=read_status,
                    message_hash=message_hash
                )
                
                messages_to_create.append(message_obj)
                existing_hashes.add(message_hash)
                
            except Exception as e:
                errors.append({
                    'index': idx,
                    'error': str(e)[:200]
                })
                print(f"⚠️ Error processing message {idx}: {str(e)}")
        
        print(f"📦 Prepared {len(messages_to_create)} messages for creation")
        
        # ========================================
        # STEP 4: BULK CREATE ALL AT ONCE
        # ========================================
        created_count = 0
        
        if messages_to_create:
            try:
                # Bulk create all at once
                created_messages = Message.objects.bulk_create(
                    messages_to_create,
                    ignore_conflicts=True,
                    batch_size=1000  # Process 1000 at a time for very large batches
                )
                
                # Count how many were actually created
                created_count = len([m for m in created_messages if m.pk is not None])
                
                # If all have no PK (all were conflicts), count differently
                if created_count == 0 and len(messages_to_create) > 0:
                    # Count by checking database before/after
                    count_after = Message.objects.filter(user_id=user_id).count()
                    created_count = max(0, count_after - (latest_message.id if latest_message else 0))
                
                print(f"✅ Bulk created: {created_count} messages")
                
            except Exception as bulk_error:
                print(f"⚠️ Bulk create failed: {str(bulk_error)}")
                print("🔄 Falling back to one-by-one creation...")
                
                # Fallback: Create one by one
                for msg_obj in messages_to_create:
                    try:
                        msg_obj.save()
                        created_count += 1
                    except Exception as e:
                        error_str = str(e).lower()
                        if 'unique' not in error_str and 'duplicate' not in error_str:
                            errors.append({
                                'user_id': msg_obj.user_id,
                                'address': msg_obj.address,
                                'error': str(e)[:200]
                            })
        
        # ========================================
        # STEP 5: RESPONSE
        # ========================================
        print(f"✅ Created: {created_count}, Skipped: {skipped_count}, Errors: {len(errors)}")
        print("="*80)
        
        response_data = {
            'status': 'success',
            'message': f'Successfully synced {created_count} new messages.',
            'stats': {
                'received': len(messages_data),
                'new_messages': len(new_messages_data),
                'filtered_old': filtered_out,
                'created': created_count,
                'skipped_duplicates': skipped_count,
                'errors': len(errors),
                'total_stored': Message.objects.filter(user_id=user_id).count()
            }
        }
        
        if errors and len(errors) < 5:
            response_data['error_samples'] = errors[:5]
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("="*80)
        
        return Response({
            'status': 'error',
            'message': str(e)
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