# allocation_app/views.py

from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import requests
from .utils import clear_mukkadam_cache
from .models import JobActivity, Allocation, AllocationStats
from django.db.models import Q
from .serializers import (
    JobActivitySerializer,
    AllocationSerializer,
    AllocationStatsSerializer,
    UserDetailSerializer
)
from django.conf import settings
# allocation_app/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import requests
import json

from .models import JobActivity, Allocation, AllocationStats,FarmerCall
from .serializers import (
    JobActivitySerializer,
    AllocationSerializer,
    AllocationStatsSerializer
)
ALLOCATION_API_URL = getattr(settings, 'ALLOCATION_API_URL')
# External API base URL
EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
SUPPLY_API_URL = getattr(settings, 'SUPPLY_API_URL')
# SUPPLY_API_URL = 'https://supply.bharatintelligence.ai' # Change to your actual Supply App URL
# SUPPLY_API_URL = 'http://localhost:8000'
def about(request):
    return render(request,'data/index.html')



# allocation_app/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import UserProfile  # ✅ Import UserProfile model
# views.py
class MakeCallViews(APIView):
    """
    Web dialpad - Call any number using central Exotel number
    """
    permission_classes = [AllowAny]
    
    CENTRAL_PHONE = '+918047361465'
    
    def post(self, request):
        to_number = request.data.get('to_number')
        user_id = request.data.get('user_id')
        username = request.data.get('username', 'web_dialpad')
        purpose = request.data.get('purpose', 'web_dialpad')
        notes = request.data.get('notes', '')
        
        if not to_number:
            return Response({
                'success': False,
                'message': 'Phone number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ Clean and add +91 if missing
        to_number = to_number.replace(' ', '').replace('-', '')
        if not to_number.startswith('+'):
            to_number = f'+91{to_number}'  # Add +91 prefix
        
        
        try:
            # 1️⃣ Make the call via Exotel
            exotel = ExotelService()
            call_result = exotel.make_call(
                from_number=self.CENTRAL_PHONE,
                to_number=to_number,
            )
            
            if not call_result['success']:
                return Response({
                    'success': False,
                    'message': 'Failed to initiate call',
                    'error': call_result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 2️⃣ Save call record
            call_data = {
                'call_sid': call_result['call_sid'],
                'mobile_number': to_number,
                'from_number': self.CENTRAL_PHONE,
                'purpose': purpose,
                'status': call_result.get('status', 'pending'),
                'notes': notes,
                'direction': 'outbound',
                'user_id': user_id or 'anonymous',
                'created_by': request.user if request.user.is_authenticated else None,
                
            }
            
            call = FarmerCall.objects.create(**call_data)
            
            logger.info(f"✅ Web dialpad call by user {user_id}: {call.call_sid} → {to_number}")
            logger.info(f"   S3 Key stored: {call.s3_key}")
            
            return Response({
                'success': True,
                'message': 'Calling...',
                'call_sid': call_result['call_sid'],
                'call_id': call.id,
                'to': to_number,
               
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ Error making call: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user

        try:
            # ✅ Get UserProfile to check role
            profile = user.profile

            return Response({
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name,
                'mobile_number': profile.mobile_number,
                'role': profile.role,
                'is_admin': profile.role == 'admin',  # ✅ Check role field
                'is_verified': profile.is_mobile_verified
            })
        except UserProfile.DoesNotExist:
            return Response({
                'error': 'User profile not found'
            }, status=status.HTTP_404_NOT_FOUND)


# ... rest of your views (JobActivityViewSet, AllocationViewSet, activity_logs_list) remain the same ...
class JobActivityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing job activities
    Activities are created when jobs are synced from external API
    """
    queryset = JobActivity.objects.all()
    serializer_class = JobActivitySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = JobActivity.objects.all()

        # Filter by job_id
        job_id = self.request.query_params.get('job_id')
        if job_id:
            queryset = queryset.filter(job_id=job_id)

        return queryset.prefetch_related('allocations')

    @action(detail=False, methods=['post'])
    def sync_from_api(self, request):
        """
        Sync activities from external API
        POST /api/job-activities/sync_from_api/
        {
            "job_id": "FV123",
            "activities": [...]
        }
        """
        job_id = request.data.get('job_id')
        activities = request.data.get('activities', [])

        if not job_id or not activities:
            return Response(
                {'error': 'job_id and activities are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_count = 0
        updated_count = 0

        for activity_data in activities:
            activity_id = activity_data.get('activity_id') or activity_data.get('id')

            # Check if activity already exists
            existing = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).first()

            if existing:
                # Update existing activity
                for key, value in activity_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.save()
                updated_count += 1
            else:
                # Create new activity
                JobActivity.objects.create(
                    job_id=job_id,
                    **activity_data
                )
                created_count += 1

        return Response({
            'message': 'Activities synced successfully',
            'created': created_count,
            'updated': updated_count
        })
from .models import AllocationChangeLog
from django.db import transaction
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.cache import cache
# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from decimal import Decimal
from .models import FarmerPayment, JobActivity
from .serializers import FarmerPaymentSerializer, FarmerPaymentSummarySerializer


class FarmerPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for FarmerPayment
    """
    queryset = FarmerPayment.objects.all()
    serializer_class = FarmerPaymentSerializer
    
    def get_queryset(self):
        """
        Filter by job_activity if provided in query params
        """
        queryset = super().get_queryset()
        
        # Filter by job activity
        job_activity_id = self.request.query_params.get('job_activity', None)
        if job_activity_id:
            queryset = queryset.filter(job_activity_id=job_activity_id)
        
        # Filter by farmer
        farmer_id = self.request.query_params.get('farmer', None)
        if farmer_id:
            queryset = queryset.filter(imported_farmer_id=farmer_id)
        
        # Filter by payment status
        payment_status = self.request.query_params.get('payment_status', None)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        return queryset.order_by('-activity_date', '-date_of_payment')
    
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Get payment summary for a specific job activity or overall
        Usage: 
        - /ap/farmer-payments/summary/?job_activity=123
        - /ap/farmer-payments/summary/ (overall summary)
        """
        job_activity_id = request.query_params.get('job_activity', None)
        
        # Base queryset
        if job_activity_id:
            payments = FarmerPayment.objects.filter(job_activity_id=job_activity_id)
        else:
            payments = FarmerPayment.objects.all()
        
        # Calculate aggregates
        paid_payments = payments.filter(payment_status='paid')
        pending_payments = payments.filter(payment_status='pending')
        
        total_paid = paid_payments.aggregate(
            total=Sum('booking_value')
        )['total'] or Decimal('0')
        
        total_pending = pending_payments.aggregate(
            total=Sum('booking_value')
        )['total'] or Decimal('0')
        
        total_expected = total_paid + total_pending
        
        # Get last payment date
        last_payment = paid_payments.filter(
            date_of_payment__isnull=False
        ).order_by('-date_of_payment').first()
        
        last_payment_date = last_payment.date_of_payment if last_payment else None
        
        # Calculate completion percentage
        completion_percentage = 0
        if total_expected > 0:
            completion_percentage = float((total_paid / total_expected) * 100)
        
        summary_data = {
            'total_expected': total_expected,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'payment_count': payments.count(),
            'paid_count': paid_payments.count(),
            'pending_count': pending_payments.count(),
            'last_payment_date': last_payment_date,
            'completion_percentage': round(completion_percentage, 2)
        }
        
        serializer = FarmerPaymentSummarySerializer(summary_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-farmer')
    def by_farmer(self, request):
        """
        Get all payments for a specific farmer across all jobs
        Usage: /ap/farmer-payments/by-farmer/?farmer_id=123
        """
        farmer_id = request.query_params.get('farmer_id', None)
        
        if not farmer_id:
            return Response(
                {'error': 'farmer_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payments = FarmerPayment.objects.filter(
            imported_farmer_id=farmer_id
        ).order_by('-activity_date')
        
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)
@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_payment_summary(request):
    """
    Get comprehensive farmer payment summary
    Shows total expected, paid, pending amounts from FarmerPayment model
    ✅ USES total_value (booking + transport) instead of just booking_value
    """
    import time
    from decimal import Decimal
    from django.db.models import Sum, Count, Q
    
    start_time = time.time()
    
    # Get filter params
    farmer_id = request.GET.get('farmer_id')
    job_id = request.GET.get('job_id')
    days = request.GET.get('days')  # ✅ Remove default=30 to get ALL records
    
    # Base queryset
    queryset = FarmerPayment.objects.select_related('job_activity', 'imported_farmer')
    
    # Apply filters
    if farmer_id:
        queryset = queryset.filter(imported_farmer__external_farmer_id=farmer_id)
    
    if job_id:
        queryset = queryset.filter(job_activity__job_id=job_id)
    
    if days:  # ✅ Only filter by days if explicitly provided
        from django.utils import timezone
        from datetime import timedelta
        from_date = timezone.now() - timedelta(days=int(days))
        queryset = queryset.filter(activity_date__gte=from_date)
    
    # ✅ Calculate totals using total_value (not booking_value)
    totals = queryset.aggregate(
        total_expected=Sum('total_value'),  # ✅ Changed from booking_value
        total_paid=Sum('total_value', filter=Q(payment_status='paid')),  # ✅ Changed
        total_pending=Sum('total_value', filter=Q(payment_status='pending')),  # ✅ Changed
        payment_count=Count('id'),
        paid_count=Count('id', filter=Q(payment_status='paid')),
        pending_count=Count('id', filter=Q(payment_status='pending')),
    )
    
    total_expected = totals['total_expected'] or Decimal('0')
    total_paid = totals['total_paid'] or Decimal('0')
    total_pending = totals['total_pending'] or Decimal('0')
    
    # ✅ Get payment breakdown by farmer (using total_value)
    farmer_breakdown = queryset.values(
        'imported_farmer__external_farmer_id',
        'imported_farmer__name'
    ).annotate(
        farmer_total=Sum('total_value'),  # ✅ Changed from booking_value
        farmer_paid=Sum('total_value', filter=Q(payment_status='paid')),  # ✅ Changed
        farmer_pending=Sum('total_value', filter=Q(payment_status='pending')),  # ✅ Changed
        payment_count=Count('id'),
        paid_count=Count('id', filter=Q(payment_status='paid')),
        pending_count=Count('id', filter=Q(payment_status='pending')),
    ).order_by('-farmer_total')[:20]  # Top 20 farmers
    
    # Get recent payments
    recent_payments = queryset.filter(payment_status='paid').order_by('-date_of_payment')[:10]
    
    recent_payments_data = []
    for payment in recent_payments:
        recent_payments_data.append({
            'payment_id': payment.id,
            'farmer_id': payment.imported_farmer.external_farmer_id if payment.imported_farmer else None,
            'farmer_name': payment.imported_farmer.name if payment.imported_farmer else 'Unknown',
            'job_id': payment.job_activity.job_id if payment.job_activity else None,
            'activity_name': payment.job_activity.activity_name if payment.job_activity else 'N/A',
            'amount': float(payment.total_value or payment.booking_value),  # ✅ Use total_value
            'booking_value': float(payment.booking_value),
            'transport_cost': float(payment.transportation_cost or 0),
            'payment_date': str(payment.date_of_payment),
            'payment_route': payment.payment_route,
            'reference_no': payment.reference_no,
        })
    
    # Get pending payments (urgent - oldest first)
    pending_payments = queryset.filter(payment_status='pending').order_by('activity_date')[:10]
    
    pending_payments_data = []
    for payment in pending_payments:
        from django.utils import timezone
        days_pending = (timezone.now().date() - payment.activity_date).days if payment.activity_date else 0
        
        pending_payments_data.append({
            'payment_id': payment.id,
            'farmer_id': payment.imported_farmer.external_farmer_id if payment.imported_farmer else None,
            'farmer_name': payment.imported_farmer.name if payment.imported_farmer else 'Unknown',
            'job_id': payment.job_activity.job_id if payment.job_activity else None,
            'activity_name': payment.job_activity.activity_name if payment.job_activity else 'N/A',
            'amount': float(payment.total_value or payment.booking_value),  # ✅ Use total_value
            'booking_value': float(payment.booking_value),
            'transport_cost': float(payment.transportation_cost or 0),
            'activity_date': str(payment.activity_date),
            'days_pending': days_pending,
            'village': payment.village,
            'acres': payment.acres,
        })
    
    # Format farmer breakdown
    farmer_breakdown_data = []
    for farmer in farmer_breakdown:
        farmer_paid = farmer['farmer_paid'] or Decimal('0')
        farmer_total = farmer['farmer_total'] or Decimal('0')
        
        farmer_breakdown_data.append({
            'farmer_id': farmer['imported_farmer__external_farmer_id'],
            'farmer_name': farmer['imported_farmer__name'],
            'total_expected': float(farmer_total),
            'total_paid': float(farmer_paid),
            'total_pending': float(farmer['farmer_pending'] or Decimal('0')),
            'payment_count': farmer['payment_count'],
            'paid_count': farmer['paid_count'],
            'pending_count': farmer['pending_count'],
            'completion_percentage': round(
                (float(farmer_paid) / float(farmer_total) * 100) if farmer_total > 0 else 0,
                1
            )
        })
    
    elapsed = time.time() - start_time
    
    return Response({
        'success': True,
        'summary': {
            'total_expected': float(total_expected),
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
            'completion_percentage': round(
                (float(total_paid) / float(total_expected) * 100) if total_expected > 0 else 0,
                1
            ),
            'payment_count': totals['payment_count'],
            'paid_count': totals['paid_count'],
            'pending_count': totals['pending_count'],
        },
        'farmer_breakdown': farmer_breakdown_data,
        'recent_payments': recent_payments_data,
        'pending_payments': pending_payments_data,
        'performance': {
            'query_time': f'{elapsed:.2f}s',
            'farmers_analyzed': len(farmer_breakdown_data),
            'total_records': queryset.count(),
        }
    })

class AllocationViewSet(viewsets.ModelViewSet):
    queryset = Allocation.objects.all()
    serializer_class = AllocationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Allocation.objects.select_related(
            'job_activity',
            'allocated_by',
            'imported_mukkadam',
            'imported_transporter',
            'imported_farmer'  # ✅ Make sure this is here!
        ).all()

        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        work_date = self.request.query_params.get('work_date')
        if work_date:
            queryset = queryset.filter(work_date=work_date)

        return queryset

    # ✅ REMOVE: list() method - No need for batch fetching anymore
    # ✅ REMOVE: _batch_fetch_external_data()
    # ✅ REMOVE: _fetch_farmers_batch()
    # ✅ REMOVE: _fetch_jobs_batch()
    def create(self, request, *args, **kwargs):
        """Create allocation - fetch from ImportedJobSheet if not in JobActivity"""
        print("="*80)
        print("📥 ALLOCATION REQUEST RECEIVED")
        print("="*80)

        activity_id = request.data.get('activity_id')
        job_id = request.data.get('job_id')
        activity_name = request.data.get('activity_name')

        if not activity_id:
            return Response(
                {'error': 'activity_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ✅ FIRST: Try to find by job_id + activity_name (most reliable)
            job_activity = JobActivity.objects.filter(
                job_id=str(job_id),
                activity_name__iexact=activity_name
            ).first()
            
            # ✅ SECOND: If not found, try by job_id + activity_id
            if not job_activity:
                job_activity = JobActivity.objects.filter(
                    job_id=str(job_id),
                    activity_id=str(activity_id)
                ).first()

            # If not found, create from ImportedJobSheet
            if not job_activity:
                print(f"🔨 JobActivity not in DB. Looking in ImportedJobSheet...")
                
                if not activity_name:
                    return Response(
                        {'error': 'activity_name is required when JobActivity not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Find in ImportedJobSheet
                job_sheet = ImportedJobSheet.objects.filter(
                    generated_job_id=str(job_id),
                    activity_name__iexact=activity_name
                ).first()
                
                if not job_sheet:
                    return Response(
                        {'error': f'Job {job_id} with activity "{activity_name}" not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # ✅ TRIPLE CHECK: Does JobActivity exist but with different activity_id?
                existing_ja = JobActivity.objects.filter(
                    job_id=str(job_id),
                    activity_name__iexact=activity_name
                ).first()
                
                if existing_ja:
                    print(f"✅ Found existing JobActivity #{existing_ja.id} (was searching with wrong activity_id)")
                    job_activity = existing_ja
                else:
                    # Create new JobActivity
                    from datetime import datetime
                    from django.utils import timezone
                    from decimal import Decimal, InvalidOperation
                    import re
                    
                    scheduled_datetime = timezone.make_aware(
                        datetime.combine(job_sheet.activity_start_date, datetime.min.time())
                    ) if job_sheet.activity_start_date else timezone.now()
                    
                    # Parse acres
                    try:
                        acres_str = str(job_sheet.acres).strip()
                        match = re.search(r'[\d.]+', acres_str)
                        total_area = Decimal(match.group()) if match else Decimal('0')
                    except (ValueError, InvalidOperation):
                        total_area = Decimal('0')
                    
                    total_price = job_sheet.total_price or job_sheet.booking_value or Decimal('0')
                    transport_cost = job_sheet.transport_cost or Decimal('0')
                    rate_per_acre = total_price / total_area if total_area > 0 else Decimal('0')
                    
                    job_activity = JobActivity.objects.create(
                        job_id=str(job_id),
                        activity_id=str(activity_id),
                        activity_name=job_sheet.activity_name,
                        activity_type=job_sheet.activity_name,
                        scheduled_datetime=scheduled_datetime,
                        total_area=total_area,
                        total_price=total_price,
                        transport_cost=transport_cost,
                        other_cost=Decimal('0'),
                        subtotal=job_sheet.subtotal or total_price,
                        location=job_sheet.location or '',
                        estimated_workers=10,
                        rate_per_acre=rate_per_acre,
                        farmer_work_id=job_sheet.generated_farmer_id or '',
                        is_manually_edited=False,
                        allocated_area=Decimal('0')
                    )
                    
                    print(f"✅ Created NEW JobActivity #{job_activity.id}")
                
                # Link ImportedJobSheet to this JobActivity
                if not job_sheet.job_activity:
                    job_sheet.job_activity = job_activity
                    job_sheet.save(update_fields=['job_activity'])

            print(f"✅ Using JobActivity #{job_activity.id}: {job_activity.activity_name}")
            print(f"   Total Area: {job_activity.total_area} acres")
            print(f"   Allocated Area: {job_activity.allocated_area} acres")

        except Exception as e:
            import traceback
            print(f"❌ Error finding/creating JobActivity: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Error processing activity: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Prepare allocation data
        data = request.data.copy()
        data['job_activity'] = job_activity.id
        data.pop('activity_id', None)
        data.pop('job_id', None)
        data.pop('activity_name', None)

        print(f"📋 Allocation data prepared:")
        print(f"   job_activity: {data.get('job_activity')}")
        print(f"   mukkadam_id: {data.get('mukkadam_id')}")
        print(f"   allocated_area: {data.get('allocated_area')}")

        # Validate allocated area
        try:
            from decimal import Decimal, InvalidOperation
            allocated_area = Decimal(str(data.get('allocated_area', 0)))
            print(f"✅ Allocated area validated: {allocated_area} acres")
        except (ValueError, InvalidOperation) as e:
            print(f"❌ Invalid allocated_area: {e}")
            return Response(
                {'error': 'Invalid allocated_area value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    # After validating allocated_area
        job_activity.refresh_from_db()
        
        if allocated_area > job_activity.remaining_area:
            return Response(
                {'error': f'Cannot allocate {allocated_area} acres. Only {job_activity.remaining_area} acres remaining.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ NEW: Set initial status based on allocation coverage
        total_area = job_activity.total_area
        total_allocated_after = job_activity.allocated_area + allocated_area
        if total_allocated_after >= total_area:
            initial_status = 'fully_allocated'  # ✅ CHANGED: Use 'fully_allocated' not 'allocated'
        else:
            initial_status = 'partially_allocated'  # Partial coverage

                
        data['status'] = initial_status  # ✅ Add status to data
        print(f"📊 Setting initial status: {initial_status} ({total_allocated_after}/{total_area} acres)")
        
        # Create allocation using serializer
        serializer = self.get_serializer(data=data)

        # Create allocation using serializer
        print(f"🔧 Creating serializer with data...")
        serializer = self.get_serializer(data=data)

        print(f"🔍 Validating serializer...")
        if not serializer.is_valid():
            print(f"❌ VALIDATION FAILED!")
            print(f"   Errors: {serializer.errors}")
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        print(f"✅ Serializer validated successfully!")


        
        
        # Save allocation
        try:
            print(f"💾 Saving allocation...")
            if request.user and request.user.is_authenticated:
                allocation = serializer.save(allocated_by=request.user)
            else:
                allocation = serializer.save()
            
            print(f"✅ Allocation created with ID: {allocation.id}")
            
        except Exception as e:
            import traceback
            print(f"❌ Error saving allocation: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Error saving allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Update JobActivity allocated_area
        try:
            print(f"📈 Updating JobActivity allocated_area...")
            from django.db.models import F
            JobActivity.objects.filter(pk=job_activity.pk).update(
                allocated_area=F('allocated_area') + allocated_area
            )
            job_activity.refresh_from_db()
            print(f"   After: {job_activity.allocated_area} acres")
            
        except Exception as e:
            print(f"❌ Error updating JobActivity: {str(e)}")
            # ✅ Don't return here - continue to save the allocation

        # Send WhatsApp notifications
        try:
            self._send_whatsapp_notifications(allocation)
        except Exception as e:
            print(f"⚠️ WhatsApp notification failed: {str(e)}")
        
        print("="*80)
        print("✅ ALLOCATION CREATED SUCCESSFULLY")
        print("="*80)

        # Create activity log
        try:
            mukkadam_name = 'Unknown'
            try:
                mukkadam = ImportedMukkadam.objects.filter(
                    external_mukkadam_id=allocation.mukkadam_id
                ).first()
                if mukkadam:
                    mukkadam_name = mukkadam.team_name
            except:
                mukkadam_name = f'#{allocation.mukkadam_id}'

            ActivityLog.objects.create(
                activity_type='allocation_created',
                description=f"Created allocation for {allocation.job_activity.activity_name}",
                allocation=allocation,
                job_id=allocation.job_activity.job_id,
                mukkadam_id=allocation.mukkadam_id,
                mukkadam_name=mukkadam_name,
                transport_provider_id=allocation.transport_provider_id if allocation.transport_type == 'provider' else None,
                amount=allocation.total_cost,
                performed_by=request.user if request.user.is_authenticated else None,
                metadata={
                    'allocated_area': float(allocation.allocated_area),
                    'work_date': str(allocation.work_date),
                    'crew_size': allocation.crew_size,
                    'mukkadam_price': float(allocation.mukkadam_price),
                    'transport_type': allocation.transport_type,
                    'transport_price': float(allocation.transport_price or 0),
                }
            )
            print(f"✅ Activity log created")
        except Exception as e:
            print(f"⚠️ Activity log creation failed: {str(e)}")

        # ✅ MUST RETURN Response at the end!
        return Response(
            {
                'message': 'Allocation created successfully',
                'allocation_id': allocation.id,
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED
        )


    # ... rest of your code stays the same ...

    def _send_whatsapp_notifications(self, allocation):
        """Helper to trigger notifications for Mukkadam and Transporter"""
        try:
            from .services import WhatsAppService
            WhatsAppService.send_allocation_to_mukkadam(allocation)
            print(f"📲 WhatsApp sent to Mukkadam: {allocation.mukkadam_id}")

            if hasattr(allocation, 'transport_provider_id'):
                WhatsAppService.send_allocation_to_transporter(allocation)
                print(f"📲 WhatsApp sent to Transporter: {allocation.transport_provider_id}")

        except Exception as e:
            logger.error(f"⚠️ WhatsApp Notification Flow failed: {str(e)}")
    
    # ✅ Keep destroy(), update(), partial_update(), change_history() as-is
    # (No changes needed - they don't use external API)
    
    def destroy(self, request, *args, **kwargs):
        """Delete allocation and update activity allocated_area"""
        allocation = self.get_object()
        job_activity = allocation.job_activity

        allocated_area = Decimal(str(allocation.allocated_area))
        job_activity.allocated_area = job_activity.allocated_area - allocated_area
        job_activity.save()

        print(f"✅ Allocation deleted. {job_activity.remaining_area} acres now available")

        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update allocation with mandatory change reason"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        change_reason = request.data.get('change_reason', '').strip()
        if not change_reason:
            return Response(
                {'error': 'Change reason is required when editing an allocation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(change_reason) < 10:
            return Response(
                {'error': 'Change reason must be at least 10 characters long'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_area_decimal = instance.allocated_area
        
        old_values = {
            'allocated_area': str(instance.allocated_area),
            'work_date': str(instance.work_date),
            'crew_size': str(instance.crew_size) if instance.crew_size else None,
            'mukkadam_price': str(instance.mukkadam_price),
            'transport_type': instance.transport_type,
            'transport_provider_id': str(instance.transport_provider_id) if instance.transport_provider_id else None,
            'own_transport_price': str(instance.own_transport_price) if instance.own_transport_price else None,
            'transport_price': str(instance.transport_price) if instance.transport_price else None,
            'mukkadam_id': str(instance.mukkadam_id),
        }
        
        if 'allocated_area' in request.data:
            new_area = Decimal(str(request.data['allocated_area']))
            job_activity = instance.job_activity
            available_area = job_activity.remaining_area + old_area_decimal
            
            if new_area > available_area:
                return Response(
                    {'error': f'Cannot allocate {new_area} acres. Only {available_area} acres available.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            with transaction.atomic():
                serializer = self.get_serializer(instance, data=request.data, partial=partial)
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                updated_instance = self.get_object()
                
                changes_made = []
                new_values = {
                    'allocated_area': str(updated_instance.allocated_area),
                    'work_date': str(updated_instance.work_date),
                    'crew_size': str(updated_instance.crew_size) if updated_instance.crew_size else None,
                    'mukkadam_price': str(updated_instance.mukkadam_price),
                    'transport_type': updated_instance.transport_type,
                    'transport_provider_id': str(updated_instance.transport_provider_id) if updated_instance.transport_provider_id else None,
                    'own_transport_price': str(updated_instance.own_transport_price) if updated_instance.own_transport_price else None,
                    'transport_price': str(updated_instance.transport_price) if updated_instance.transport_price else None,
                    'mukkadam_id': str(updated_instance.mukkadam_id),
                }
                
                for field, old_val in old_values.items():
                    new_val = new_values.get(field)
                    if old_val != new_val:
                        AllocationChangeLog.objects.create(
                            allocation=updated_instance,
                            changed_by=request.user if request.user.is_authenticated else None,
                            change_reason=change_reason,
                            field_name=field,
                            old_value=old_val or '',
                            new_value=new_val or ''
                        )
                        changes_made.append(field)
                
                if 'allocated_area' in request.data:
                    new_area_decimal = updated_instance.allocated_area
                    area_diff = new_area_decimal - old_area_decimal
                    
                    job_activity = updated_instance.job_activity
                    job_activity.allocated_area = job_activity.allocated_area + area_diff
                    job_activity.save()
                
                # Create activity log
                if changes_made:
                    mukkadam_name = 'Unknown'
                    try:
                        mukkadam = ImportedMukkadam.objects.filter(external_mukkadam_id=updated_instance.mukkadam_id).first()
                        if mukkadam:
                            mukkadam_name = mukkadam.team_name
                    except:
                        mukkadam_name = f'#{updated_instance.mukkadam_id}'
                    
                    changes_dict = {}
                    for field in changes_made:
                        changes_dict[field] = {
                            'old': old_values.get(field),
                            'new': new_values.get(field)
                        }
                    
                    ActivityLog.objects.create(
                        activity_type='allocation_updated',
                        description=f"Updated allocation for {updated_instance.job_activity.activity_name}",
                        allocation=updated_instance,
                        job_id=updated_instance.job_activity.job_id,
                        mukkadam_id=updated_instance.mukkadam_id,
                        mukkadam_name=mukkadam_name,
                        transport_provider_id=updated_instance.transport_provider_id,
                        amount=updated_instance.total_cost,
                        performed_by=request.user if request.user.is_authenticated else None,
                        changes=changes_dict,
                        metadata={
                            'change_reason': change_reason,
                            'changed_fields': changes_made,
                            'allocation_id': updated_instance.id,
                        }
                    )

                return Response({
                    'message': 'Allocation updated successfully',
                    'changes_made': changes_made,
                    'data': serializer.data
                })
                
        except Exception as e:
            print(f"❌ Error updating allocation: {str(e)}")
            return Response(
                {'error': f'Failed to update allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def change_history(self, request, pk=None):
        """Get change history for an allocation"""
        allocation = self.get_object()
        logs = allocation.change_logs.all()
        
        history = []
        for log in logs:
            history.append({
                'changed_at': log.changed_at,
                'changed_by': log.changed_by.username if log.changed_by else 'System',
                'field_name': log.field_name,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'reason': log.change_reason
            })
        
        return Response({'history': history})
# views.py
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction, models
from datetime import datetime
import json
import logging

from .models import (
    ImportedJob, 
    ImportedJobSheet, 
    ImportedFarmer, 
    ImportedPayment, 
    ImportedVisit, 
    ImportedMedia
)

logger = logging.getLogger(__name__)

# External API Configuration
EXTERNAL_API_URL_A = getattr(settings, 'EXTERNAL_API_URL', 'https://demand.bharatintelligence.ai/fir/api')
JOB_TOKEN = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'

# views.py

def fetch_farmer_from_external_api(farmer_id):
    """
    Fetch farmer details from external API with detailed logging
    """
    try:
        url = f"{EXTERNAL_API_URL_A}/get_farmer_details/{farmer_id}/"
        headers = {
            'Authorization': JOB_TOKEN,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"🌐 Fetching farmer {farmer_id}")
        logger.info(f"📍 URL: {url}")  # ✅ Log full URL
        
        response = requests.get(url, headers=headers, timeout=10)
        
        logger.info(f"📡 Status Code: {response.status_code}")
        logger.info(f"📄 Response Headers: {dict(response.headers)}")
        
        # ✅ Log response body regardless of status
        try:
            response_data = response.json()
            logger.info(f"📦 Response Data: {response_data}")
        except:
            logger.info(f"📦 Response Text: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            farmer_name = data.get('farmer_name') or data.get('name', 'Unknown')
            logger.info(f"✅ Fetched farmer: {farmer_name}")
            return data
        elif response.status_code == 404:
            logger.warning(f"⚠️  Farmer {farmer_id} not found in external API (404)")
            return None
        else:
            logger.warning(f"⚠️  API error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout fetching farmer {farmer_id}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
        return None

def get_or_create_farmer(farmer_id):
    """
    Get farmer from local DB or fetch from external API
    Returns: (ImportedFarmer instance, created: bool)
    """
    # Step 1: Check local database
    try:
        farmer = ImportedFarmer.objects.get(external_farmer_id=farmer_id)
        logger.info(f"📋 Found farmer in local DB: {farmer.name}")
        return farmer, False
    except ImportedFarmer.DoesNotExist:
        pass
    
    # Step 2: Fetch from external API
    farmer_data = fetch_farmer_from_external_api(farmer_id)
    
    if farmer_data:
        # ✅ FIX: Use correct field names from API
        farmer = ImportedFarmer.objects.create(
            external_farmer_id=farmer_id,
            name=farmer_data.get('farmer_name', f'Farmer {farmer_id}'),  # ✅ Changed from 'name'
            contact_no=farmer_data.get('phone_number', ''),  # ✅ Changed from 'contact_no'
            location=farmer_data.get('location', ''),
            village=farmer_data.get('village', ''),
            taluka=farmer_data.get('taluka', ''),
            district=farmer_data.get('district', ''),
            state='Maharashtra',  # ✅ Default or parse from location
            created_from_import=False,
        )
        logger.info(f"✅ Created farmer from API: {farmer.name}")
        return farmer, True
    else:
        # Create placeholder farmer
        farmer = ImportedFarmer.objects.create(
            external_farmer_id=farmer_id,
            name=f'Farmer {farmer_id}',
            contact_no='',
            location='',
            created_from_import=False,
        )
        logger.warning(f"⚠️  Created placeholder farmer: {farmer_id}")
        return farmer, True

@csrf_exempt
@require_http_methods(["POST"])
def ops_webhook_receiver(request):
    """
    Complete webhook receiver with:
    - Auto-fetch farmer from API
    - Store payments
    - Store visits
    - Store media locations
    """
    logger.info(f"📥 Webhook received from {request.META.get('REMOTE_ADDR')}")
    
    try:
        payload = json.loads(request.body)
        job_id = payload.get('id')
        logger.info(f"📦 Processing Job ID: {job_id}")
        
        # Extract job-level data
        farmer_id = payload.get('farmer_id')
        plot_id = payload.get('plot_id', '')
        status = payload.get('status', 'PENDING')
        priority = payload.get('priority', 'MEDIUM')
        scheduled_date = payload.get('scheduled_date')
        activity_notes = payload.get('activity_notes') or ''
        internal_notes = payload.get('internal_notes') or ''
        total_activities_amount = payload.get('total_activities_amount', 0)
        is_field_verified = payload.get('is_field_verified', False)
        booking_type_value = payload.get('booking_type', '')
        
        # Booking data
        booking = payload.get('booking', {})
        visits = payload.get('visits', [])
        
        # Parse created_at
        created_at_str = payload.get('created_at')
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if created_at_str else timezone.now()
        
        # Generate job_id
        generated_job_id = f"JOB-{job_id}"




        
        with transaction.atomic():
            # ✅ STEP 1: Get or create farmer
            farmer, farmer_created = get_or_create_farmer(farmer_id)
            
            # ✅ STEP 2: Create/Update Job
            try:
                job = ImportedJob.objects.get(external_job_id=job_id)
                job_created = False
                
                # Update existing job
                job.generated_job_id = generated_job_id
                job.farmer_id = str(farmer_id)
                job.imported_farmer = farmer  # ✅ Link to farmer
                job.plot_id = str(plot_id) if plot_id else ''
                job.status = status
                job.priority = priority
                job.scheduled_date = datetime.fromisoformat(scheduled_date).date() if scheduled_date else None
                job.activity_notes = activity_notes
                job.internal_notes = internal_notes
                job.total_activities_amount = total_activities_amount
                job.is_field_verified = is_field_verified
                job.booking_id = booking.get('id')
                job.booking_status = booking.get('status', '')
                job.booking_total_amount = booking.get('total_amount', 0)
                job.booking_type = booking_type_value
                job.booking_advance_paid = booking.get('advance_paid', 0)
                job.booking_balance = booking.get('balance', 0)
                job.assignee_number = booking.get('assignee_number', '')
                
                # Add farmer details
                job.farmer_name = farmer.name
                job.farmer_contact = farmer.contact_no
                job.location = farmer.location
                
                job.raw_booking_data = booking
                job.raw_visits_data = visits
                job.raw_payments_data = booking.get('payments', [])
                job.raw_full_payload = payload
                job.last_webhook_sync = timezone.now()
                job.webhook_update_count = models.F('webhook_update_count') + 1
                job.save()
                
                logger.info(f"🔄 Updated ImportedJob #{job_id}")

            
            
                
            except ImportedJob.DoesNotExist:
                # Create new job
                job = ImportedJob.objects.create(
                    external_job_id=job_id,
                    generated_job_id=generated_job_id,
                    farmer_id=str(farmer_id),
                    imported_farmer=farmer,  # ✅ Link to farmer
                    plot_id=str(plot_id) if plot_id else '',
                    status=status,
                    priority=priority,
                    scheduled_date=datetime.fromisoformat(scheduled_date).date() if scheduled_date else None,
                    activity_notes=activity_notes,
                    internal_notes=internal_notes,
                    total_activities_amount=total_activities_amount,
                    is_field_verified=is_field_verified,
                    booking_id=booking.get('id'),
                    booking_status=booking.get('status', ''),
                    booking_total_amount=booking.get('total_amount', 0),
                    booking_type=booking_type_value,
                    booking_advance_paid=booking.get('advance_paid', 0),
                    booking_balance=booking.get('balance', 0),
                    assignee_number=booking.get('assignee_number', ''),
                    farmer_name=farmer.name,
                    farmer_contact=farmer.contact_no,
                    location=farmer.location,
                    raw_booking_data=booking,
                    raw_visits_data=visits,
                    raw_payments_data=booking.get('payments', []),
                    raw_full_payload=payload,
                    created_at=created_at,
                    last_webhook_sync=timezone.now(),
                    webhook_update_count=1,
                )
                job_created = True
                logger.info(f"✅ Created ImportedJob #{job_id}")
            
            # ✅ STEP 3: Process Payments
            payments = booking.get('payments', [])
            payment_records = []
            
            for payment_data in payments:
                payment_id = payment_data.get('id')
                
                # Check if payment already exists
                if not ImportedPayment.objects.filter(external_payment_id=payment_id).exists():
                    payment = ImportedPayment.objects.create(
                        imported_job=job,
                        external_payment_id=payment_id,
                        amount=payment_data.get('amount', 0),
                        mode=payment_data.get('mode', ''),
                        paid_at=datetime.fromisoformat(payment_data.get('paid_at').replace('Z', '+00:00')),
                        notes=payment_data.get('notes', ''),
                        paid_status=payment_data.get('paid_status', False),
                    )
                    payment_records.append(payment_id)
                    logger.info(f"  ✅ Created Payment #{payment_id}: ₹{payment.amount}")
                else:
                    logger.info(f"  ⏭️  Payment #{payment_id} already exists")
            
            # ✅ STEP 4: Process Visits
            visit_records = []
            
            for visit_data in visits:
                visit_id = visit_data.get('visit_id')
                
                # Create or update visit
                visit, created = ImportedVisit.objects.update_or_create(
                    external_visit_id=visit_id,
                    defaults={
                        'imported_job': job,
                        'status': visit_data.get('status', ''),
                        'assigned_to': visit_data.get('assigned_to', ''),
                        'media_locations': visit_data.get('media_locations', []),
                    }
                )
                visit_records.append(visit_id)
                logger.info(f"  {'✅ Created' if created else '🔄 Updated'} Visit #{visit_id}")
                
                # Process media locations
                media_locations = visit_data.get('media_locations', [])
                for media_data in media_locations:
                    media_id = media_data.get('media_id')
                    location = media_data.get('location', {})
                    
                    ImportedMedia.objects.update_or_create(
                        visit=visit,
                        external_media_id=media_id,
                        defaults={
                            'media_type': media_data.get('media_type', ''),
                            'latitude': location.get('latitude'),
                            'longitude': location.get('longitude'),
                            'address': location.get('address', ''),
                            'is_field_location': location.get('is_field_location', False),
                        }
                    )
                    logger.info(f"    📸 Stored Media #{media_id}")
            
            # ✅ STEP 5: Process Activities
            activities = payload.get('activities', [])
            activity_records = []
            
            logger.info(f"📋 Processing {len(activities)} activities")
            
            for idx, activity in enumerate(activities, 1):
                activity_id = activity.get('id')
                activity_name = activity.get('activity_name', 'Unknown')
                date_time_str = activity.get('date_time')
                acres = activity.get('acres', 0)
                total_price = activity.get('total_price', 0)
                transport_cost = activity.get('transport_cost', 0)
                other_cost = activity.get('other_cost', 0)
                subtotal = activity.get('subtotal', 0)
                activity_note = activity.get('activity_note') or ''
                crop_bundles = activity.get('crop_bundles')
                
                # Parse datetime
                activity_datetime = None
                activity_start_date = None
                if date_time_str:
                    try:
                        activity_datetime = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
                        activity_start_date = activity_datetime.date()
                    except:
                        pass
                
                # Create/Update activity
                sheet, created = ImportedJobSheet.objects.update_or_create(
                    external_activity_id=activity_id,
                    defaults={
                        'imported_job': job,
                        'data_source': 'external_api',
                        'activity_name': activity_name,
                        'activity_datetime': activity_datetime,
                        'activity_start_date': activity_start_date,
                        'acres': str(acres),
                        'total_price': total_price,
                        'transport_cost': transport_cost,
                        'other_cost': other_cost,
                        'subtotal': subtotal,
                        'activity_note': activity_note,
                        'crop_bundles': crop_bundles,
                        'generated_job_id': generated_job_id,
                        'generated_farmer_id': str(farmer_id),
                        'farmer_name': farmer.name,
                        'farmer_contact': farmer.contact_no,
                        'location': farmer.location,
                        'import_status': 'pending',
                    }
                )
                
                activity_records.append({
                    'activity_id': activity_id,
                    'activity_name': activity_name,
                    'created': created
                })
                
                logger.info(f"  [{ idx}/{len(activities)}] {'✅ Created' if created else '🔄 Updated'} Activity #{activity_id}: {activity_name}")
        
        # Success response
        logger.info(f"🎉 Successfully processed Job #{job_id}")
        logger.info(f"   - Farmer: {farmer.name} ({'created' if farmer_created else 'existing'})")
        logger.info(f"   - Activities: {len(activity_records)}")
        logger.info(f"   - Payments: {len(payment_records)}")
        logger.info(f"   - Visits: {len(visit_records)}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Processed job #{job_id}',
            'job': {
                'job_id': job_id,
                'generated_job_id': generated_job_id,
                'created': job_created,
            },
            'farmer': {
                'farmer_id': farmer_id,
                'name': farmer.name,
                'created': farmer_created,
            },
            'counts': {
                'activities': len(activity_records),
                'payments': len(payment_records),
                'visits': len(visit_records),
            }
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from .models import PaymentRequest, TransportPaymentRequest, Allocation
from .serializers import PaymentRequestSerializer, TransportPaymentRequestSerializer
from .signals import get_mukkadam_name,get_transport_provider_name
class PaymentRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for mukkadam payment requests"""
    serializer_class = PaymentRequestSerializer
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production

    def get_queryset(self):
        """Filter by mukkadam_id or show all for admin"""
        queryset = PaymentRequest.objects.all()

        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def create(self, request, *args, **kwargs):
        """Create payment request for an allocation"""
        allocation_id = request.data.get('allocation_id')

        if not allocation_id:
            return Response(
                {'error': 'allocation_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            allocation = Allocation.objects.get(id=allocation_id)
        except Allocation.DoesNotExist:
            return Response(
                {'error': 'Allocation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Check if payment request already exists
        if hasattr(allocation, 'payment_request'):
            existing_request = allocation.payment_request
            
            # ✅ If rejected, update and resubmit the existing request
            if existing_request.status == 'rejected':
                existing_request.status = 'pending'
                existing_request.requested_at = timezone.now()
                existing_request.requested_by = request.user if request.user.is_authenticated else None
                existing_request.notes = request.data.get('notes', existing_request.notes)
                existing_request.save()
                
                # Log the re-request activity
                ActivityLog.objects.create(
                    activity_type='payment_requested',
                    description="Payment re-requested after rejection",
                    payment_request=existing_request,
                    allocation=allocation,
                    performed_by=request.user if request.user.is_authenticated else None,
                    job_id=allocation.farmer_work_id,
                    mukkadam_id=allocation.mukkadam_id,
                    metadata={"notes": existing_request.notes}
                )
                
                serializer = self.get_serializer(existing_request)
                return Response({
                    'message': 'Payment request resubmitted successfully',
                    'payment_request': serializer.data
                }, status=status.HTTP_200_OK)
            
            # ✅ If pending or paid, return error
            elif existing_request.status == 'pending':
                return Response(
                    {
                        'error': 'Payment request already exists and is pending approval',
                        'existing_request': PaymentRequestSerializer(existing_request).data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing_request.status == 'paid':
                return Response(
                    {
                        'error': 'Payment has already been made for this allocation',
                        'existing_request': PaymentRequestSerializer(existing_request).data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Calculate amount from allocation
        requested_amount = float(allocation.mukkadam_price) 

        # Create payment request
        payment_request = PaymentRequest.objects.create(
            allocation=allocation,
            mukkadam_id=allocation.mukkadam_id,
            requested_amount=requested_amount,
            requested_by=request.user if request.user.is_authenticated else None,
            notes=request.data.get('notes', '')
        )
        
        # Log the creation
        ActivityLog.objects.create(
            activity_type='payment_requested',
            description="New payment request created",
            payment_request=payment_request,
            allocation=allocation,
            performed_by=request.user if request.user.is_authenticated else None,
            job_id=allocation.farmer_work_id,
            mukkadam_id=allocation.mukkadam_id,
            metadata={"notes": payment_request.notes}
        )

        serializer = self.get_serializer(payment_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    # ... existing imports ...
    # Ensure you import ActivityLog
    # from .models import ActivityLog

    @action(detail=True, methods=['post'])
    def re_request(self, request, pk=None):
        """Allow mukkadam to re-request payment after rejection"""
        payment_request = self.get_object()
        if payment_request.status != 'rejected':
            return Response(
                {'error': 'Can only re-request payments that were rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_request.status = 'pending'
        payment_request.requested_at = timezone.now()
        payment_request.save()

        # ✅ FIX: Use ActivityLog instead of PaymentActivity
        ActivityLog.objects.create(
            activity_type='payment_requested',  # Use one of the choices from your model
            description="Payment re-requested after rejection",
            payment_request=payment_request,
            allocation=payment_request.allocation,
            performed_by=request.user if request.user.is_authenticated else None,
            job_id=payment_request.allocation.farmer_work_id,  # Required field in ActivityLog
            mukkadam_id=payment_request.mukkadam_id,          # Required field in ActivityLog
            metadata={"notes": "Re-request"}
        )
        serializer = self.get_serializer(payment_request)
        return Response({
            'message': 'Payment request submitted successfully',
            'payment_request': serializer.data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a payment request"""
        payment_request = self.get_object()
        if payment_request.status == 'paid':
            return Response(
                {'error': 'Cannot reject a payment that has already been paid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Store old status for logging
        old_status = payment_request.status
        
        # Update payment request
        payment_request.status = 'rejected'
        payment_request.rejected_at = timezone.now()
        payment_request.rejected_by = request.user if request.user.is_authenticated else None
        payment_request.rejection_reason = request.data.get('rejection_reason', '')
        payment_request.save()

        # ✅ UPDATE ALLOCATION STATUS BACK TO ALLOCATED
        allocation = payment_request.allocation
        old_allocation_status = allocation.status
        
        if allocation.status == 'completed':
            allocation.status = 'allocated'
            allocation.completed_at = None  # ✅ Clear completion timestamp
            allocation.save()
            
            print(f"✅ Allocation #{allocation.id} status changed: {old_allocation_status} → allocated")

        # ✅ Log the rejection with status change details
        ActivityLog.objects.create(
            activity_type='payment_rejected',
            description=request.data.get('rejection_reason', 'Payment request rejected'),
            payment_request=payment_request,
            allocation=payment_request.allocation,
            performed_by=request.user if request.user.is_authenticated else None,
            job_id=payment_request.allocation.farmer_work_id,
            mukkadam_id=payment_request.mukkadam_id,
            mukkadam_name=get_mukkadam_name(payment_request.mukkadam_id),  # ✅ Add name
            amount=payment_request.requested_amount,
            changes={
                'payment_status': {
                    'label': 'Payment Status',
                    'old': old_status,
                    'new': 'rejected'
                },
                'allocation_status': {
                    'label': 'Allocation Status',
                    'old': old_allocation_status,
                    'new': allocation.status
                }
            },
            metadata={
                'rejection_reason': payment_request.rejection_reason,
                'activity_name': allocation.job_activity.activity_name,
            }
        )
        serializer = self.get_serializer(payment_request)
        return Response({
            'message': 'Payment request rejected successfully',
            'payment_request': serializer.data,
            'allocation': {
                'id': allocation.id,
                'status': allocation.status,
                'status_changed': old_allocation_status != allocation.status
            }
        })

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark payment as paid"""
        payment_request = self.get_object()
        
        # ✅ Store old status for logging
        old_payment_status = payment_request.status
        
        # Update payment request
        payment_request.status = 'paid'
        payment_request.paid_at = timezone.now()
        payment_request.paid_by = request.user if request.user.is_authenticated else None
        payment_request.save()
        # Update allocation status
        allocation = payment_request.allocation
        old_allocation_status = allocation.status
        allocation.status = 'completed'
        allocation.completed_at = timezone.now()
        allocation.save()
        # ✅ FIX: Use ActivityLog (This caused your NameError)
        ActivityLog.objects.create(
            activity_type='payment_paid',
            description=f"Payment marked as paid by {request.user.username if request.user.is_authenticated else 'Unknown'}",
            payment_request=payment_request,
            allocation=allocation,
            performed_by=request.user if request.user.is_authenticated else None,
            job_id=allocation.farmer_work_id,
            mukkadam_id=allocation.mukkadam_id,
            mukkadam_name=get_mukkadam_name(allocation.mukkadam_id),  # ✅ Add name
            amount=payment_request.requested_amount,
            changes={
                'payment_status': {
                    'label': 'Payment Status',
                    'old': old_payment_status,
                    'new': 'paid'
                },
                'allocation_status': {
                    'label': 'Allocation Status',
                    'old': old_allocation_status,
                    'new': 'completed'
                }
            },
            metadata={
                'activity_name': allocation.job_activity.activity_name,
                'paid_at': str(payment_request.paid_at),
            }
        )
        return Response({
            'message': 'Payment marked as paid successfully',
            'allocation': AllocationSerializer(allocation).data,
            'payment_request': self.get_serializer(payment_request).data
        })
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get payment requests for specific mukkadam"""
        mukkadam_id = request.query_params.get('mukkadam_id')
        if not mukkadam_id:
            return Response(
                {'error': 'mukkadam_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        requests = PaymentRequest.objects.filter(mukkadam_id=mukkadam_id)

        # Filter by status if provided
        status_param = request.query_params.get('status')
        if status_param:
            requests = requests.filter(status=status_param)

        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending payment requests (admin view)"""
        requests = PaymentRequest.objects.filter(status='pending')
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)


class TransportPaymentRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for transport provider payment requests"""
    serializer_class = TransportPaymentRequestSerializer
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production

    def get_queryset(self):
        """Filter by transport_provider_id or show all for admin"""
        queryset = TransportPaymentRequest.objects.all()

        provider_id = self.request.query_params.get('transport_provider_id')
        if provider_id:
            queryset = queryset.filter(transport_provider_id=provider_id)

        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def create(self, request, *args, **kwargs):
        """Create transport payment request for an allocation"""
        allocation_id = request.data.get('allocation_id')

        if not allocation_id:
            return Response(
                {'error': 'allocation_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            allocation = Allocation.objects.get(id=allocation_id)
        except Allocation.DoesNotExist:
            return Response(
                {'error': 'Allocation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Check if this allocation has transport provider
        if not allocation.transport_provider_id:
            return Response(
                {'error': 'This allocation does not have a transport provider'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Check if payment request already exists
        if hasattr(allocation, 'transport_payment_request'):
            return Response(
                {
                    'error': 'Transport payment request already exists for this allocation',
                    'existing_request': TransportPaymentRequestSerializer(allocation.transport_payment_request).data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get amount from allocation
        requested_amount = float(allocation.transport_price or 0)

        if requested_amount <= 0:
            return Response(
                {'error': 'Transport cost is zero or not set'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Create payment request
        payment_request = TransportPaymentRequest.objects.create(
            allocation=allocation,
            transport_provider_id=allocation.transport_provider_id,
            requested_amount=requested_amount,
            requested_by=request.user if request.user.is_authenticated else None,
            notes=request.data.get('notes', '')
        )

        serializer = self.get_serializer(payment_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Admin marks transport payment as paid"""
        payment_request = self.get_object()
        if payment_request.status == 'paid':
            return Response(
                {'error': 'Payment already marked as paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # ✅ UPDATE: Mark payment as paid
        payment_request.status = 'paid'
        payment_request.paid_at = timezone.now()
        payment_request.paid_by = request.user if request.user.is_authenticated else None
        payment_request.save()

        # ✅ NEW: Check if mukkadam payment is also paid, then mark allocation complete
        allocation = payment_request.allocation

        # Only mark as completed if mukkadam payment is also paid (or doesn't exist)
        mukkadam_payment = getattr(allocation, 'payment_request', None)
        if not mukkadam_payment or mukkadam_payment.status == 'paid':
            allocation.status = 'completed'
            allocation.save()
        serializer = self.get_serializer(payment_request)
        return Response(serializer.data)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a payment request"""
        payment_request = self.get_object()
        if payment_request.status == 'paid':
            return Response(
                {'error': 'Cannot reject a payment that has already been paid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_request.status = 'rejected'
        payment_request.save()

        serializer = self.get_serializer(payment_request)
        return Response({
            'message': 'Payment request rejected successfully',
            'payment_request': serializer.data
        })
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get payment requests for specific transport provider"""
        provider_id = request.query_params.get('transport_provider_id')
        if not provider_id:
            return Response(
                {'error': 'transport_provider_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        requests = TransportPaymentRequest.objects.filter(transport_provider_id=provider_id)

        # Filter by status if provided
        status_param = request.query_params.get('status')
        if status_param:
            requests = requests.filter(status=status_param)

        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending transport payment requests (admin view)"""
        requests = TransportPaymentRequest.objects.filter(status='pending')
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

from .models import ActivityLog
from .serializers import ActivityLogSerializer

from .utils import batch_fetch_mukkadams, batch_fetch_transport_providers


@api_view(['GET'])
@permission_classes([AllowAny])
def allocations_by_mobile(request):
    """
    Get all allocations for a mukkadam by mobile number with assigned transporter details
    GET /api/allocations/by-mobile/?mobile_number=9876543210
    GET /api/allocations/by-mobile/?mukkadam_phone=9876543210
    This API:
    1. Calls Supply App to get mukkadam_id from mobile number
    2. Fetches allocations from Allocation App database
    3. For each allocation, calls Supply App to get assigned transport provider details
    4. Returns combined data with transporter info
    """
    # ✅ Accept both parameter names
    mobile_number = request.GET.get('mobile_number') or request.GET.get('mukkadam_phone')
    if not mobile_number:
        return Response(
            {'error': 'mobile_number or mukkadam_phone query parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    print("=" * 80)
    print(f"📞 FETCHING ALLOCATIONS FOR MUKKADAM: {mobile_number}")
    print("=" * 80)

    # ✅ STEP 1: Call Supply App API to get mukkadam(s)
    try:
        supply_response = requests.get(
            f'{SUPPLY_API_URL}/api/mukkadam/by-mobile/',
            params={'mobile_number': mobile_number},
            timeout=5000
        )
        supply_data = supply_response.json()
        if not supply_data.get('found'):
            return Response({
                'success': False,
                'error': 'No mukkadam found with this mobile number',
                'mobile_number': mobile_number,
                'mukkadams': [],
                'allocations': [],
                'summary': {
                    'total_allocations': 0,
                    'total_earnings': 0
                }
            }, status=status.HTTP_404_NOT_FOUND)

        mukkadams = supply_data.get('mukkadams', [])
        mukkadam_ids = [m['id'] for m in mukkadams]

        print(f"✅ Found {len(mukkadams)} mukkadam(s): {[m['mukkadam_name'] for m in mukkadams]}")

    except requests.exceptions.RequestException as e:
        return Response(
            {'success': False, 'error': f'Failed to connect to Supply App: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    # ✅ STEP 2: Get allocations from Allocation App database
    allocations = Allocation.objects.filter(
        mukkadam_id__in=mukkadam_ids
    ).select_related('job_activity', 'allocated_by').order_by('-allocated_at')

    print(f"📋 Found {allocations.count()} allocation(s)")

    # ✅ STEP 3: Build response with transport provider details from Supply App
    allocations_data = []
    total_area = Decimal('0')
    total_cost = Decimal('0')

    # ✅ Cache transport provider data to avoid multiple API calls
    transport_provider_cache = {}
    transporters_found = 0

    for alloc in allocations:
        # Find which mukkadam this allocation belongs to
        mukkadam = next((m for m in mukkadams if m['id'] == alloc.mukkadam_id), None)

        # ✅ Get transport provider FULL details from Supply App API if applicable
        transport_provider_id = None
        transport_provider_name = None
        transport_provider_contact = None
        transport_provider_details = None

        if alloc.transport_type == 'provider' and alloc.transport_provider_id:
            transport_provider_id = alloc.transport_provider_id

            print(f"🚛 Fetching transporter #{transport_provider_id} for allocation #{alloc.id}")

            # Check cache first
            if alloc.transport_provider_id in transport_provider_cache:
                provider_data = transport_provider_cache[alloc.transport_provider_id]
                print(f"   ✅ Using cached transporter data")
            else:
                # Fetch from Supply App API
                try:
                    provider_response = requests.get(
                        f'{SUPPLY_API_URL}/api/transport-provider/{alloc.transport_provider_id}/',
                        timeout=500
                    )
                    if provider_response.status_code == 200:
                        provider_json = provider_response.json()
                        if provider_json.get('found'):
                            provider_data = provider_json.get('provider')
                            transport_provider_cache[alloc.transport_provider_id] = provider_data
                            print(f"   ✅ Fetched transporter: {provider_data.get('name')}")
                        else:
                            provider_data = None
                            print(f"   ⚠️ Transporter not found in database")
                    else:
                        provider_data = None
                        print(f"   ❌ API returned status {provider_response.status_code}")

                except requests.exceptions.RequestException as e:
                    print(f"   ❌ Failed to fetch transport provider: {str(e)}")
                    provider_data = None

            # ✅ Set provider name and COMPLETE details
            if provider_data:
                transport_provider_name = provider_data.get('name')
                transport_provider_contact = provider_data.get('contact_number')
                # ✅ Include ALL fields from the transport provider
                transport_provider_details = {
                    'id': provider_data.get('id'),
                    'name': provider_data.get('name'),
                    'contact_number': provider_data.get('contact_number'),
                    'base_location': provider_data.get('base_location'),
                    'district': provider_data.get('district'),
                    'taluka': provider_data.get('taluka'),
                    'village': provider_data.get('village'),
                    'max_distance': provider_data.get('max_distance'),
                    'vehicle_type': provider_data.get('vehicle_type'),
                    'is_active': provider_data.get('is_active'),
                    'capacity': provider_data.get('capacity'),
                }
                transporters_found += 1
            else:
                # Transporter ID exists but details not found
                transport_provider_name = f'Provider #{alloc.transport_provider_id}'
                transport_provider_contact = None

        allocation_data = {
            'allocation_id': alloc.id,

            # Mukkadam Info
            'mukkadam_id': alloc.mukkadam_id,
            'mukkadam_name': mukkadam['mukkadam_name'] if mukkadam else 'Unknown',
            'mukkadam_phone': mukkadam.get('contact_number') if mukkadam else None,
            'mukkadam_village': mukkadam.get('village') if mukkadam else None,
            'status': alloc.status,
            # Job details
            'job_id': alloc.job_activity.job_id,
            'activity_id': alloc.job_activity.activity_id,
            'activity_name': alloc.job_activity.activity_name,
            'activity_type': alloc.job_activity.activity_type,
            'location': alloc.job_activity.location,
            # Allocation details
            'allocated_area': float(alloc.allocated_area),
            'work_date': str(alloc.work_date),
            'crew_size': alloc.crew_size,

            # Pricing
            'mukkadam_price': float(alloc.mukkadam_price),

            # ✅ TRANSPORTER INFO - Easy access at top level
            'transport_type': alloc.transport_type,
            'transport_price': float(alloc.transport_price or 0),
            'transport_provider_id': transport_provider_id,  # ✅ ID
            'transport_provider_name': transport_provider_name,  # ✅ Name
            'transport_provider_contact': transport_provider_contact,  # ✅ Contact
            'transport_provider_details': transport_provider_details,  # ✅ Full details object

            'total_cost': float(alloc.total_cost),

            # Metadata
            'allocated_at': alloc.allocated_at.isoformat(),
            'allocated_by': alloc.allocated_by.username if alloc.allocated_by else None,
            'notes': alloc.notes,
            # Activity details
            'scheduled_datetime': alloc.job_activity.scheduled_datetime.isoformat(),
            'total_activity_area': float(alloc.job_activity.total_area),
            'remaining_activity_area': float(alloc.job_activity.remaining_area),
        }

        allocations_data.append(allocation_data)
        total_area += alloc.allocated_area
        total_cost += Decimal(str(alloc.total_cost))

    # Summary statistics
    summary = {
        'total_allocations': allocations.count(),
        'total_area_allocated': float(total_area),
        'total_earnings': float(total_cost),
        'active_allocations': allocations.filter(status='allocated').count(),
        'completed_allocations': allocations.filter(status='completed').count(),
        'in_progress_allocations': allocations.filter(status='in_progress').count(),
        'transporters_assigned': transporters_found,  # ✅ Count of allocations with transporters
    }
    print("=" * 80)
    print(f"✅ RESPONSE READY")
    print(f"   Allocations: {summary['total_allocations']}")
    print(f"   Transporters found: {transporters_found}")
    print("=" * 80)
    return Response({
        'success': True,
        'mobile_number': mobile_number,
        'mukkadams': mukkadams,  # From Supply App
        'mukkadams_count': len(mukkadams),
        'allocations': allocations_data,  # From Allocation App + Supply App (with transporter details)
        'summary': summary
    })

# views.py - REMOVE THE MUKKADAM IMPORT
# from .models import JobActivity, Allocation, AllocationStats, Mukkadam  # ❌ WRONG
# allocation/views.py

# allocation/views.py
# allocation/views.py
# allocation/views.py
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .utils import get_farmer_cached
# (Assuming imports for ActivityLog, get_farmer_cached, etc. exist)
# allocation/views.py (INSPECTION VERSION)
import time
import pprint # STRICTLY FOR DEBUGGING
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
# allocation/views.py
import time
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Ensure you import Job alongside ActivityLog
from .models import ActivityLog

# allocation/views.py
import time
import requests
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

# Import models
from .models import ActivityLog

# Ensure these are imported or defined in your file
# from .utils import batch_fetch_farmers, batch_fetch_mukkadams, batch_fetch_transport_providers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

class ActivityLogPagination(PageNumberPagination):
    """Custom pagination for activity logs"""
    page_size = 20  # Default items per page
    page_size_query_param = 'page_size'  # Allow client to override
    max_page_size = 100  # Maximum items per page


from .models import PaymentRequest, TransportPaymentRequest

# allocation_app/views.py

import time
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
import requests

from .models import ActivityLog, Allocation, JobActivity, PaymentRequest, TransportPaymentRequest
from .utils import batch_fetch_farmers, batch_fetch_mukkadams, batch_fetch_transport_providers
from .pagination import StandardResultsPagination, CompletedAllocationsPagination, PendingJobsPagination

EXTERNAL_API_URL = getattr(settings, 'EXTERNAL_API_URL', 'https://ops.bharatintelligence.ai/ops/api')

# ============================================
# 1. ACTIVITY LOGS ENDPOINT (Server-Side Pagination)
# ============================================

# @api_view(['GET'])
# @permission_classes([AllowAny])
# def activity_logs_list(request):
#     """
#     Get all activity logs with complete details and pagination
#     Query params:
#     - page: Page number (default: 1)
#     - page_size: Items per page (default: 20, max: 100)
#     - activity_type: Filter by activity type
#     - mukkadam_id: Filter by mukkadam
#     - job_id: Filter by job
#     - search: Search in job_id, mukkadam, farmer, description
#     - date: Filter by specific date (YYYY-MM-DD)
#     - days: Filter by days (default: 30)
#     """
#     start_time = time.time()
    
#     # Build queryset with filters
#     activity_type = request.query_params.get('activity_type')
#     mukkadam_id = request.query_params.get('mukkadam_id')
#     job_id = request.query_params.get('job_id')
#     search = request.query_params.get('search', '').strip()
#     filter_date = request.query_params.get('date')
#     days = request.query_params.get('days', 30)

#     queryset = ActivityLog.objects.all()

#     # Apply filters
#     if activity_type and activity_type != 'all':
#         if activity_type == 'payment':
#             queryset = queryset.filter(activity_type__icontains='payment')
#         else:
#             queryset = queryset.filter(activity_type=activity_type)
    
#     if mukkadam_id:
#         queryset = queryset.filter(mukkadam_id=mukkadam_id)
    
#     if job_id:
#         queryset = queryset.filter(job_id=job_id)
    
#     if filter_date:
#         # Filter by specific date
#         from datetime import datetime
#         target_date = datetime.strptime(filter_date, '%Y-%m-%d').date()
#         queryset = queryset.filter(performed_at__date=target_date)
#     elif days:
#         # Filter by days range
#         from_date = timezone.now() - timedelta(days=int(days))
#         queryset = queryset.filter(performed_at__gte=from_date)

#     # Search filter (applied before pagination for accurate count)
#     if search:
#         queryset = queryset.filter(
#             Q(job_id__icontains=search) |
#             Q(description__icontains=search) |
#             Q(mukkadam_id__icontains=search) |
#             Q(transport_provider_id__icontains=search)
#         )

#     # Order by most recent first
#     queryset = queryset.select_related('performed_by').order_by('-performed_at')

#     # Apply pagination
#     paginator = StandardResultsPagination()
#     paginated_queryset = paginator.paginate_queryset(queryset, request)

#     if not paginated_queryset:
#         return Response({
#             'count': 0,
#             'next': None,
#             'previous': None,
#             'total_pages': 0,
#             'current_page': 1,
#             'logs': []
#         })

#     # Fetch related data for current page only
#     job_ids = set()
#     for log in paginated_queryset:
#         if log.job_id:
#             job_ids.add(str(log.job_id))

#     jobs_cache = {}
#     job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'

#     if job_ids:
#         try:
#             response = requests.get(
#                 f'{EXTERNAL_API_URL}/get_allocated_jobs/',
#                 headers={'Authorization': job_token},
#                 timeout=50
#             )
#             if response.status_code == 200:
#                 data = response.json()
#                 jobs_list = data.get('data', data) if isinstance(data, dict) else data
                
#                 if isinstance(jobs_list, list):
#                     for job in jobs_list:
#                         j_id = str(job.get('work_id') or job.get('id') or job.get('job_id'))
#                         if j_id in job_ids:
#                             jobs_cache[j_id] = job
#         except Exception as e:
#             print(f"❌ Error fetching jobs: {str(e)}")

#     # Extract IDs for batch fetching
#     farmer_ids = set()
#     for job in jobs_cache.values():
#         f_id = job.get('farmer_id')
#         if f_id:
#             farmer_ids.add(str(f_id))

#     mukkadam_ids = set()
#     transport_provider_ids = set()
#     for log in paginated_queryset:
#         if log.mukkadam_id:
#             mukkadam_ids.add(log.mukkadam_id)
#         if log.transport_provider_id:
#             transport_provider_ids.add(log.transport_provider_id)

#     # Batch fetch
#     batch_start = time.time()
#     farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
#     mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
#     transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)
#     batch_elapsed = time.time() - batch_start

#     # Build enriched logs
#     logs = []
#     for log in paginated_queryset:
#         mukkadam_name = 'Unknown'
#         if log.mukkadam_id:
#             m_data = mukkadams_cache.get(log.mukkadam_id)
#             mukkadam_name = m_data.get('mukkadam_name', f'#{log.mukkadam_id}') if m_data else f'#{log.mukkadam_id}'

#         transport_name = None
#         if log.transport_provider_id:
#             t_data = transport_providers_cache.get(log.transport_provider_id)
#             transport_name = t_data.get('name', f'#{log.transport_provider_id}') if t_data else f'#{log.transport_provider_id}'

#         farmer_name = None
#         farmer_details = None
#         job_details = None
        
#         if log.job_id:
#             job_data = jobs_cache.get(str(log.job_id))
#             if job_data:
#                 f_id = str(job_data.get('farmer_id', ''))
#                 f_details = farmers_cache.get(f_id)
#                 if f_details:
#                     farmer_details = f_details
#                     farmer_name = (
#                         f_details.get('farmer_name') or 
#                         f_details.get('name') or 
#                         f_details.get('full_name') or 
#                         f_details.get('first_name')
#                     )
#                 else:
#                     farmer_name = f'Farmer #{f_id}' if f_id else 'Unknown Farmer'

#                 job_details = {
#                     'job_name': job_data.get('job_name'),
#                     'location': job_data.get('location'),
#                     'scheduled_date': job_data.get('scheduled_date')
#                 }

#         logs.append({
#             'id': log.id,
#             'activity_type': log.activity_type,
#             'activity_type_display': log.get_activity_type_display(),
#             'description': log.description,
#             'job_id': log.job_id,
#             'job_details': job_details,
#             'mukkadam_id': log.mukkadam_id,
#             'mukkadam_name': mukkadam_name,
#             'transport_provider_id': log.transport_provider_id,
#             'transport_name': transport_name,
#             'farmer_id': farmer_details.get('id') if farmer_details else None,
#             'farmer_name': farmer_name,
#             'farmer_details': farmer_details,
#             'amount': float(log.amount) if log.amount else None,
#             'performed_by_name': log.performed_by.username if log.performed_by else 'System',
#             'performed_at': log.performed_at.isoformat(),
#             'timestamp': log.performed_at.isoformat(),
#             'metadata': log.metadata,
#             'changes': log.changes,
#             'reason': log.reason if hasattr(log, 'reason') else None,
#             'allocation_id': log.metadata.get('allocation_id') if log.metadata else None,
#         })

#     total_elapsed = time.time() - start_time

#     return Response({
#         'count': paginator.page.paginator.count,
#         'next': paginator.get_next_link(),
#         'previous': paginator.get_previous_link(),
#         'total_pages': paginator.page.paginator.num_pages,
#         'current_page': paginator.page.number,
#         'page_size': len(logs),
#         'logs': logs,
#         'performance': {
#             'total_time': f'{total_elapsed:.2f}s',
#             'batch_fetch_time': f'{batch_elapsed:.2f}s',
#         }
#     })


# ============================================
# 2. COMPLETED ALLOCATIONS ENDPOINT (Server-Side Pagination)
# ============================================

@api_view(['GET'])
@permission_classes([AllowAny])
def completed_allocations_list(request):
    """
    Get completed allocations with pagination
    Query params:
    - page: Page number
    - page_size: Items per page (default: 10, max: 50)
    - search: Search in job_id, farmer, mukkadam, activity
    - work_date: Filter by work date (YYYY-MM-DD)
    """
    start_time = time.time()
    
    search = request.query_params.get('search', '').strip()
    work_date_filter = request.query_params.get('work_date')
    
    # Get all allocations
    queryset = Allocation.objects.select_related(
        'job_activity', 
        'allocated_by'
    ).all()
    
    # Filter for completed allocations
    completed_allocation_ids = []
    
    # Get all payment requests
    mukkadam_payments = PaymentRequest.objects.filter(
        status__in=['pending', 'paid']
    ).values_list('allocation_id', flat=True)
    
    transport_payments = TransportPaymentRequest.objects.filter(
        status__in=['pending', 'paid']
    ).values_list('allocation_id', flat=True)
    
    payment_allocation_ids = set(list(mukkadam_payments) + list(transport_payments))
    
    for allocation in queryset:
        # Include if completed OR has payment
        is_completed = allocation.status == 'completed'
        has_payment = allocation.id in payment_allocation_ids
        
        # Exclude if payment was rejected
        rejected_payment = PaymentRequest.objects.filter(
            allocation_id=allocation.id,
            status='rejected'
        ).exists()
        
        if (is_completed or has_payment) and not rejected_payment:
            completed_allocation_ids.append(allocation.id)
    
    # Filter queryset to completed only
    queryset = queryset.filter(id__in=completed_allocation_ids)
    
    # Apply work_date filter
    if work_date_filter:
        queryset = queryset.filter(work_date=work_date_filter)
    
    # Search filter (before pagination)
    # Search filter (before pagination)
    if search:
        queryset = queryset.filter(
            # Q(farmer_work_id__icontains=search) |
            Q(job_activity__activity_name__icontains=search) |  # ✅ UNCOMMENTED
            Q(job_activity__job_id__icontains=search) |
            Q(mukkadam_id__icontains=search)
        )
    
    # Order by most recent work_date
    queryset = queryset.order_by('-work_date', '-allocated_at')
    
    # Apply pagination
    paginator = CompletedAllocationsPagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    
    if not paginated_queryset:
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'total_pages': 0,
            'current_page': 1,
            'allocations': []
        })
    
    # Collect IDs for batch fetching
    job_ids = set()
    farmer_ids = set()
    mukkadam_ids = set()
    transport_provider_ids = set()
    
    for allocation in paginated_queryset:
        job_ids.add(str(allocation.farmer_work_id))
        mukkadam_ids.add(allocation.mukkadam_id)
        if allocation.transport_provider_id:
            transport_provider_ids.add(allocation.transport_provider_id)
    
    # Fetch jobs from external API
    jobs_cache = {}
    try:
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=500
        )
        
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', data) if isinstance(data, dict) else data
            
            if isinstance(jobs_list, list):
                for job in jobs_list:
                    j_id = str(job.get('work_id') or job.get('id'))
                    if j_id in job_ids:
                        jobs_cache[j_id] = job
                        # Extract farmer_id
                        f_id = job.get('farmer_id')
                        if f_id:
                            farmer_ids.add(str(f_id))
    except Exception as e:
        print(f"❌ Error fetching jobs: {str(e)}")
    
    # Batch fetch related data
    batch_start = time.time()
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)
    batch_elapsed = time.time() - batch_start
    
    # Get payment requests
    mukkadam_payment_dict = {}
    for payment in PaymentRequest.objects.filter(allocation_id__in=[a.id for a in paginated_queryset]):
        mukkadam_payment_dict[payment.allocation_id] = {
            'id': payment.id,
            'status': payment.status,
            'amount': float(payment.requested_amount),
            'requested_at': payment.requested_at.isoformat()
        }
    
    transport_payment_dict = {}
    for payment in TransportPaymentRequest.objects.filter(allocation_id__in=[a.id for a in paginated_queryset]):
        transport_payment_dict[payment.allocation_id] = {
            'id': payment.id,
            'status': payment.status,
            'amount': float(payment.requested_amount),
            'requested_at': payment.requested_at.isoformat()
        }
    
    # Build response
    # Build response
    allocations_data = []
    for allocation in paginated_queryset:
        # Get job and farmer info
        job_data = jobs_cache.get(str(allocation.farmer_work_id), {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})
        
        # Get mukkadam info
        mukkadam_data = mukkadams_cache.get(allocation.mukkadam_id, {})
        
        # Get transport info
        transport_data = None
        if allocation.transport_provider_id:
            transport_data = transport_providers_cache.get(allocation.transport_provider_id, {})
        
        # ✅ SAFELY GET ACTIVITY NAME
        activity_name = 'Unknown'
        if allocation.job_activity:
            activity_name = allocation.job_activity.activity_name
        
        allocations_data.append({
            'id': allocation.id,
            'farmer_work_id': allocation.farmer_work_id,
            'activity_name': activity_name,  # ✅ NOW INCLUDED
            'allocated_area': float(allocation.allocated_area),
            'work_date': str(allocation.work_date) if allocation.work_date else None,
            'crew_size': allocation.crew_size,
            'status': allocation.status,
            
            # Mukkadam info
            'mukkadam_id': allocation.mukkadam_id,
            'mukkadam_name': mukkadam_data.get('mukkadam_name', f'#{allocation.mukkadam_id}'),
            'mukkadam_price': float(allocation.mukkadam_price),
            'mukkadam_payment': mukkadam_payment_dict.get(allocation.id),
            
            # Transport info
            'transport_type': allocation.transport_type,
            'transport_provider_id': allocation.transport_provider_id,
            'transport_name': transport_data.get('name') if transport_data else None,
            'transport_price': float(allocation.transport_price or 0),
            'transport_payment': transport_payment_dict.get(allocation.id),
            
            # Farmer info
            'farmer': {
                'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                'phone_number': farmer_data.get('phone_number', 'N/A'),
                'location': farmer_data.get('location', 'N/A'),
                'village': farmer_data.get('village', 'N/A'),
            },
            
            # Metadata
            'created_at': allocation.allocated_at.isoformat(),
            'total_cost': float(allocation.total_cost),
        })

    total_elapsed = time.time() - start_time
    
    return Response({
        'count': paginator.page.paginator.count,
        'next': paginator.get_next_link(),
        'previous': paginator.get_previous_link(),
        'total_pages': paginator.page.paginator.num_pages,
        'current_page': paginator.page.number,
        'page_size': len(allocations_data),
        'allocations': allocations_data,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
        }
    })

# ============================================
# 3. PENDING JOBS ENDPOINT (Server-Side Pagination)
# ============================================
@api_view(['GET'])
@permission_classes([AllowAny])
def pending_jobs_list(request):
    """
    Get pending jobs with pagination - ENRICHED with DB data like jobs_list
    Query params:
    - page: Page number
    - page_size: Items per page (default: 10, max: 50)
    - search: Search in job_id, farmer, activity_name
    - date: Filter by scheduled date (YYYY-MM-DD)
    - activity_name: Filter by activity name
    """
    start_time = time.time()
    
    search = request.query_params.get('search', '').strip()
    date_filter = request.query_params.get('date')
    activity_name_filter = request.query_params.get('activity_name', '').strip()
    
    # ============================================
    # STEP 1: FETCH & ENRICH ALL JOBS (Same as jobs_list)
    # ============================================
    try:
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=500
        )
        response.raise_for_status()
        response_data = response.json()
        
        if isinstance(response_data, dict):
            jobs_from_api = response_data.get('data', response_data.get('results', [response_data]))
        else:
            jobs_from_api = response_data
            
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch jobs: {str(e)}'},
            status=503
        )
    
    if not jobs_from_api:
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'total_pages': 0,
            'current_page': 1,
            'jobs': []
        })
    
    # Collect farmer and mukkadam IDs
    farmer_ids = set()
    mukkadam_ids = set()
    
    for job in jobs_from_api:
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    # Get mukkadam IDs from allocations
    all_allocations = Allocation.objects.all().select_related('job_activity')
    for alloc in all_allocations:
        mukkadam_ids.add(alloc.mukkadam_id)
    
    # Batch fetch
    batch_start = time.time()
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    batch_elapsed = time.time() - batch_start
    
    # ============================================
    # STEP 2: ENRICH JOBS WITH DB DATA (Same as jobs_list)
    # ============================================
    enriched_jobs = []
    
    for idx, job in enumerate(jobs_from_api):
        job_id = str(
            job.get('work_id') or
            job.get('id') or
            job.get('job_id') or
            f"UNKNOWN_{idx}"
        )
        
        # Get farmer details
        farmer_id = str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)
        
        # Get activities
        activities_from_api = job.get('activities', [])
        activities_data = []
        
        for api_activity in activities_from_api:
            # ✅ FIXED: Prioritize activity_id over id
            activity_id = str(api_activity.get('activity_id') or api_activity.get('id', ''))
            
            # ✅ CHECK IF ACTIVITY EXISTS IN DB
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()
            
            # ✅ PRIORITY LOGIC: DB if edited/lost, else API
            if db_activity and (db_activity.is_manually_edited or hasattr(db_activity, 'lost_record')):
                activity_name = db_activity.activity_name
                total_area = db_activity.total_area
                total_price = db_activity.total_price
                transport_cost = db_activity.transport_cost
                other_cost = db_activity.other_cost
                crop_bundles = getattr(db_activity, 'crop_bundles', api_activity.get('crop_bundles', 0))
                scheduled_date = db_activity.scheduled_datetime.date() if db_activity.scheduled_datetime else None
                rate_per_acre = db_activity.rate_per_acre
                location = db_activity.location or api_activity.get('location', 'N/A')
            else:
                activity_name = api_activity.get('activity_name', 'Unknown')
                total_area = Decimal(str(api_activity.get('acres', 0)))
                total_price = Decimal(str(api_activity.get('total_price', 0)))
                transport_cost = Decimal(str(api_activity.get('transport_cost', 0)))
                crop_bundles = api_activity.get('crop_bundles', 0)
                other_cost = Decimal(str(api_activity.get('other_cost', 0)))
                scheduled_date = api_activity.get('date_time') or api_activity.get('scheduled_date')
                rate_per_acre = round(
                    float(total_price) / float(total_area), 2
                ) if float(total_area) > 0 else 0.00
                location = api_activity.get('location', 'N/A')
            
            # ✅ CALCULATE ALLOCATIONS
            allocations_data = []
            allocated_area = Decimal('0')
            
            if db_activity:
                for alloc in db_activity.allocations.all():
                    allocated_area += Decimal(str(alloc.allocated_area))
                    mukkadam_data = mukkadams_cache.get(alloc.mukkadam_id, {})
                    mukkadam_name = mukkadam_data.get('mukkadam_name', f'Mukkadam #{alloc.mukkadam_id}')
                    
                    allocations_data.append({
                        'allocation_id': alloc.id,
                        'mukkadam_id': alloc.mukkadam_id,
                        'mukkadam_name': mukkadam_name,
                        'allocated_area': float(alloc.allocated_area),
                        'work_date': str(alloc.work_date) if alloc.work_date else None,
                        'crew_size': alloc.crew_size,
                        'mukkadam_price': float(alloc.mukkadam_price),
                        'transport_type': alloc.transport_type,
                        'transport_price': float(alloc.transport_price or 0),
                        'total_cost': float(alloc.total_cost)
                    })
            
            # Calculate areas
            remaining_area = total_area - allocated_area
            is_fully_allocated = allocated_area >= total_area
            
            def safe_date(value):
                if not value:
                    return ''
                if isinstance(value, str):
                    return value.split('T')[0]
                return str(value)
            
            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': activity_name,
                'activity_type': api_activity.get('activity_type', ''),
                'location': location,
                'total_area': float(total_area),
                'crop_bundles': crop_bundles,
                'allocated_area': float(allocated_area),
                'remaining_area': float(remaining_area),
                'scheduled_date': safe_date(scheduled_date),
                'scheduled_time': api_activity.get('scheduled_time', ''),
                'estimated_workers': api_activity.get('estimated_workers', 10),
                'rate_per_acre': float(rate_per_acre),
                'total_price': float(total_price),
                'transport_cost': float(transport_cost),
                'other_cost': float(other_cost),
                'subtotal': float(api_activity.get('subtotal', 0)),
                'is_fully_allocated': is_fully_allocated,
                'is_manually_edited': db_activity.is_manually_edited if db_activity else False,
                'allocations': allocations_data,
                'is_lost': db_activity.lost_record.is_active if (db_activity and hasattr(db_activity, 'lost_record')) else False,
                'lost_reason': db_activity.lost_record.reason if (db_activity and hasattr(db_activity, 'lost_record') and db_activity.lost_record.is_active) else None,
                'edit_history_count': db_activity.edit_history.count() if db_activity else 0,
            })
        
        # Calculate job status
        def calculate_status(activities):
            if not activities:
                return 'pending'
            fully_allocated = sum(1 for a in activities if a['is_fully_allocated'])
            partially_allocated = sum(1 for a in activities if a['allocated_area'] > 0 and not a['is_fully_allocated'])
            if fully_allocated == len(activities):
                return 'fully_allocated'
            elif fully_allocated > 0 or partially_allocated > 0:
                return 'partially_allocated'
            else:
                return 'pending'
        
        job_status = calculate_status(activities_data)
        
        # Extract visits and POC
        visits_data = job.get('visits', [])
        point_of_contact = None
        if visits_data and isinstance(visits_data, list):
            point_of_contact = visits_data[0].get('assigned_to')
        
        enriched_job = {
            **job,
            'work_id': job_id,
            'farmer': farmer_details,
            'activities': activities_data,
            'status': job_status,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            'booking': job.get('booking', {}),
            'visits': visits_data,
            'point_of_contact': point_of_contact,
        }
        
        enriched_jobs.append(enriched_job)
    
    # ============================================
    # STEP 3: FILTER FOR PENDING JOBS ONLY
    # ============================================
    pending_jobs = []
    
    for job in enriched_jobs:
        # Skip jobs where ALL activities are lost
        non_lost_activities = [a for a in job['activities'] if not a['is_lost']]
        if not non_lost_activities:
            continue
        
        # Check if job has any non-fully-allocated activities
        has_pending = any(a['remaining_area'] > 0 for a in non_lost_activities)
        
        if has_pending:
            pending_jobs.append(job)
    
    # ============================================
    # STEP 4: APPLY FILTERS
    # ============================================
    filtered_jobs = []
    
    for job in pending_jobs:
        # Date filter
        if date_filter:
            job_date = job.get('scheduled_date', '')
            if not job_date or not job_date.startswith(date_filter):
                activities = job.get('activities', [])
                has_matching_date = False
                for activity in activities:
                    if activity.get('is_lost'):
                        continue
                    act_date = activity.get('scheduled_date', '')
                    if act_date and act_date.startswith(date_filter):
                        has_matching_date = True
                        break
                if not has_matching_date:
                    continue
        
        # Activity name filter
        if activity_name_filter:
            activities = job.get('activities', [])
            has_matching_activity = False
            for activity in activities:
                if activity.get('is_lost'):
                    continue
                if activity_name_filter.lower() in activity.get('activity_name', '').lower():
                    has_matching_activity = True
                    break
            if not has_matching_activity:
                continue
        
        # Search filter
        if search:
            farmer = job.get('farmer', {})
            farmer_name = farmer.get('farmer_name', '')
            farmer_phone = farmer.get('phone_number', '')
            job_id = str(job.get('work_id', ''))
            
            if (search.lower() in job_id.lower() or 
                search.lower() in farmer_name.lower() or 
                search in farmer_phone):
                filtered_jobs.append(job)
            else:
                # Check activities
                activities = job.get('activities', [])
                for activity in activities:
                    if search.lower() in activity.get('activity_name', '').lower():
                        filtered_jobs.append(job)
                        break
        else:
            filtered_jobs.append(job)
    
    # ============================================
    # STEP 5: SORT BY DATE
    # ============================================
# ============================================
# STEP 5: SORT BY DATE
# ============================================
    from datetime import datetime
    def get_job_date(job):
        date_str = job.get('scheduled_date')
        if not date_str:
            activities = job.get('activities', [])
            dates = [a.get('scheduled_date') for a in activities if not a.get('is_lost')]
            dates = [d for d in dates if d]
            if dates:
                date_str = sorted(dates)[0]
        
        if date_str:
            try:
                # Remove timezone info to make it naive
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return parsed_date.replace(tzinfo=None)
            except:
                pass
        return datetime.min  # Now both are naive

    filtered_jobs.sort(key=get_job_date)
    
    # ============================================
    # STEP 6: PAGINATION
    # ============================================
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    page_size = min(page_size, 50)
    
    total_count = len(filtered_jobs)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_jobs = filtered_jobs[start_idx:end_idx]
    
    # Build pagination links
    base_url = request.build_absolute_uri(request.path)
    next_link = None
    prev_link = None
    
    if page < total_pages:
        next_link = f"{base_url}?page={page + 1}&page_size={page_size}"
        if search:
            next_link += f"&search={search}"
        if date_filter:
            next_link += f"&date={date_filter}"
        if activity_name_filter:
            next_link += f"&activity_name={activity_name_filter}"
    
    if page > 1:
        prev_link = f"{base_url}?page={page - 1}&page_size={page_size}"
        if search:
            prev_link += f"&search={search}"
        if date_filter:
            prev_link += f"&date={date_filter}"
        if activity_name_filter:
            prev_link += f"&activity_name={activity_name_filter}"
    
    total_elapsed = time.time() - start_time
    
    return Response({
        'count': total_count,
        'next': next_link,
        'previous': prev_link,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': len(paginated_jobs),
        'jobs': paginated_jobs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def partially_allocated_jobs_list(request):
    """
    Get partially allocated jobs with pagination
    Query params:
    - page: Page number
    - page_size: Items per page (default: 10, max: 50)
    - search: Search in job_id, farmer, activity_name
    - date: Filter by scheduled date (YYYY-MM-MM)
    """
    start_time = time.time()
    
    search = request.query_params.get('search', '').strip()
    date_filter = request.query_params.get('date')
    
    # ============================================
    # STEP 1: FETCH & ENRICH ALL JOBS (Same as pending_jobs_list)
    # ============================================
    try:
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=500
        )
        response.raise_for_status()
        response_data = response.json()
        
        if isinstance(response_data, dict):
            jobs_from_api = response_data.get('data', response_data.get('results', [response_data]))
        else:
            jobs_from_api = response_data
            
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch jobs: {str(e)}'},
            status=503
        )
    
    if not jobs_from_api:
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'total_pages': 0,
            'current_page': 1,
            'jobs': []
        })
    
    # Collect farmer and mukkadam IDs
    farmer_ids = set()
    mukkadam_ids = set()
    
    for job in jobs_from_api:
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    # Get mukkadam IDs from allocations
    all_allocations = Allocation.objects.all().select_related('job_activity')
    for alloc in all_allocations:
        mukkadam_ids.add(alloc.mukkadam_id)
    
    # Batch fetch
    batch_start = time.time()
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    batch_elapsed = time.time() - batch_start
    
    # ============================================
    # STEP 2: ENRICH JOBS WITH DB DATA
    # ============================================
    enriched_jobs = []
    
    for idx, job in enumerate(jobs_from_api):
        job_id = str(
            job.get('work_id') or
            job.get('id') or
            job.get('job_id') or
            f"UNKNOWN_{idx}"
        )
        
        # Get farmer details
        farmer_id = str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)
        
        # Get activities
        activities_from_api = job.get('activities', [])
        activities_data = []
        
        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))
            
            # Check DB for activity
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()
            
            # Priority logic: DB if edited/lost, else API
            if db_activity and (db_activity.is_manually_edited or hasattr(db_activity, 'lost_record')):
                activity_name = db_activity.activity_name
                total_area = db_activity.total_area
                total_price = db_activity.total_price
                transport_cost = db_activity.transport_cost
                other_cost = db_activity.other_cost
                crop_bundles = getattr(db_activity, 'crop_bundles', api_activity.get('crop_bundles', 0))
                scheduled_date = db_activity.scheduled_datetime.date() if db_activity.scheduled_datetime else None
                rate_per_acre = db_activity.rate_per_acre
                location = db_activity.location or api_activity.get('location', 'N/A')
            else:
                activity_name = api_activity.get('activity_name', 'Unknown')
                total_area = Decimal(str(api_activity.get('acres', 0)))
                total_price = Decimal(str(api_activity.get('total_price', 0)))
                transport_cost = Decimal(str(api_activity.get('transport_cost', 0)))
                crop_bundles = api_activity.get('crop_bundles', 0)
                other_cost = Decimal(str(api_activity.get('other_cost', 0)))
                scheduled_date = api_activity.get('date_time') or api_activity.get('scheduled_date')
                rate_per_acre = round(
                    float(total_price) / float(total_area), 2
                ) if float(total_area) > 0 else 0.00
                location = api_activity.get('location', 'N/A')
            
            # Calculate allocations
            allocations_data = []
            allocated_area = Decimal('0')
            
            if db_activity:
                for alloc in db_activity.allocations.all():
                    allocated_area += Decimal(str(alloc.allocated_area))
                    mukkadam_data = mukkadams_cache.get(alloc.mukkadam_id, {})
                    mukkadam_name = mukkadam_data.get('mukkadam_name', f'Mukkadam #{alloc.mukkadam_id}')
                    
                    allocations_data.append({
                        'allocation_id': alloc.id,
                        'mukkadam_id': alloc.mukkadam_id,
                        'mukkadam_name': mukkadam_name,
                        'allocated_area': float(alloc.allocated_area),
                        'work_date': str(alloc.work_date) if alloc.work_date else None,
                        'crew_size': alloc.crew_size,
                        'mukkadam_price': float(alloc.mukkadam_price),
                        'transport_type': alloc.transport_type,
                        'transport_price': float(alloc.transport_price or 0),
                        'total_cost': float(alloc.total_cost)
                    })
            
            # Calculate areas
            remaining_area = total_area - allocated_area
            is_fully_allocated = allocated_area >= total_area
            
            def safe_date(value):
                if not value:
                    return ''
                if isinstance(value, str):
                    return value.split('T')[0]
                return str(value)
            
            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': activity_name,
                'activity_type': api_activity.get('activity_type', ''),
                'location': location,
                'total_area': float(total_area),
                'crop_bundles': crop_bundles,
                'allocated_area': float(allocated_area),
                'remaining_area': float(remaining_area),
                'scheduled_date': safe_date(scheduled_date),
                'scheduled_time': api_activity.get('scheduled_time', ''),
                'estimated_workers': api_activity.get('estimated_workers', 10),
                'rate_per_acre': float(rate_per_acre),
                'total_price': float(total_price),
                'transport_cost': float(transport_cost),
                'other_cost': float(other_cost),
                'subtotal': float(api_activity.get('subtotal', 0)),
                'is_fully_allocated': is_fully_allocated,
                'is_manually_edited': db_activity.is_manually_edited if db_activity else False,
                'allocations': allocations_data,
                'is_lost': db_activity.lost_record.is_active if (db_activity and hasattr(db_activity, 'lost_record')) else False,
                'lost_reason': db_activity.lost_record.reason if (db_activity and hasattr(db_activity, 'lost_record') and db_activity.lost_record.is_active) else None,
                'edit_history_count': db_activity.edit_history.count() if db_activity else 0,
            })
        
        # Calculate job status
        def calculate_status(activities):
            if not activities:
                return 'pending'
            fully_allocated = sum(1 for a in activities if a['is_fully_allocated'])
            partially_allocated = sum(1 for a in activities if a['allocated_area'] > 0 and not a['is_fully_allocated'])
            if fully_allocated == len(activities):
                return 'fully_allocated'
            elif fully_allocated > 0 or partially_allocated > 0:
                return 'partially_allocated'
            else:
                return 'pending'
        
        job_status = calculate_status(activities_data)
        
        # Extract visits and POC
        visits_data = job.get('visits', [])
        point_of_contact = None
        if visits_data and isinstance(visits_data, list):
            point_of_contact = visits_data[0].get('assigned_to')
        
        enriched_job = {
            **job,
            'work_id': job_id,
            'farmer': farmer_details,
            'activities': activities_data,
            'status': job_status,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            'booking': job.get('booking', {}),
            'visits': visits_data,
            'point_of_contact': point_of_contact,
        }
        
        enriched_jobs.append(enriched_job)
    
    # ============================================
    # STEP 3: FILTER FOR PARTIALLY ALLOCATED JOBS ONLY
    # ============================================
    partially_allocated_jobs = []
    
    for job in enriched_jobs:
        # Skip jobs where ALL activities are lost
        non_lost_activities = [a for a in job['activities'] if not a['is_lost']]
        if not non_lost_activities:
            continue
        
        # Check if job has:
        # 1. At least one activity with some allocation (allocated_area > 0)
        # 2. At least one activity not fully allocated (remaining_area > 0)
        has_some_allocation = any(a['allocated_area'] > 0 for a in non_lost_activities)
        has_remaining = any(a['remaining_area'] > 0 for a in non_lost_activities)
        
        # Job is "partially allocated" if it has both
        if has_some_allocation and has_remaining:
            partially_allocated_jobs.append(job)
    
    # ============================================
    # STEP 4: APPLY FILTERS
    # ============================================
    filtered_jobs = []
    
    for job in partially_allocated_jobs:
        # Date filter
        if date_filter:
            job_date = job.get('scheduled_date', '')
            if not job_date or not job_date.startswith(date_filter):
                activities = job.get('activities', [])
                has_matching_date = False
                for activity in activities:
                    if activity.get('is_lost'):
                        continue
                    act_date = activity.get('scheduled_date', '')
                    if act_date and act_date.startswith(date_filter):
                        has_matching_date = True
                        break
                if not has_matching_date:
                    continue
        
        # Search filter
        if search:
            farmer = job.get('farmer', {})
            farmer_name = farmer.get('farmer_name', '')
            farmer_phone = farmer.get('phone_number', '')
            job_id = str(job.get('work_id', ''))
            
            if (search.lower() in job_id.lower() or 
                search.lower() in farmer_name.lower() or 
                search in farmer_phone):
                filtered_jobs.append(job)
            else:
                # Check activities
                activities = job.get('activities', [])
                for activity in activities:
                    if search.lower() in activity.get('activity_name', '').lower():
                        filtered_jobs.append(job)
                        break
        else:
            filtered_jobs.append(job)
    
    # ============================================
    # STEP 5: SORT BY DATE
    # ============================================
    from datetime import datetime
    def get_job_date(job):
        date_str = job.get('scheduled_date')
        if not date_str:
            activities = job.get('activities', [])
            dates = [a.get('scheduled_date') for a in activities if not a.get('is_lost')]
            dates = [d for d in dates if d]
            if dates:
                date_str = sorted(dates)[0]
        
        if date_str:
            try:
                # Remove timezone info to make it naive
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return parsed_date.replace(tzinfo=None)
            except:
                pass
        return datetime.min
    
    filtered_jobs.sort(key=get_job_date)
    
    # ============================================
    # STEP 6: PAGINATION
    # ============================================
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    page_size = min(page_size, 50)
    
    total_count = len(filtered_jobs)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_jobs = filtered_jobs[start_idx:end_idx]
    
    # Build pagination links
    base_url = request.build_absolute_uri(request.path)
    next_link = None
    prev_link = None
    
    if page < total_pages:
        next_link = f"{base_url}?page={page + 1}&page_size={page_size}"
        if search:
            next_link += f"&search={search}"
        if date_filter:
            next_link += f"&date={date_filter}"
    
    if page > 1:
        prev_link = f"{base_url}?page={page - 1}&page_size={page_size}"
        if search:
            prev_link += f"&search={search}"
        if date_filter:
            prev_link += f"&date={date_filter}"
    
    total_elapsed = time.time() - start_time
    
    return Response({
        'count': total_count,
        'next': next_link,
        'previous': prev_link,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': len(paginated_jobs),
        'jobs': paginated_jobs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def lost_jobs_list(request):
    """
    Get jobs with lost activities with pagination
    Query params:
    - page: Page number
    - page_size: Items per page (default: 10, max: 50)
    - search: Search in farmer name/phone
    - job_id: Filter by job ID
    - date: Filter by scheduled date of lost activities
    """
    start_time = time.time()
    
    search = request.query_params.get('search', '').strip()
    job_id_filter = request.query_params.get('job_id', '').strip()
    date_filter = request.query_params.get('date')
    
    # ============================================
    # STEP 1: FETCH & ENRICH ALL JOBS
    # ============================================
    try:
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=500
        )
        response.raise_for_status()
        response_data = response.json()
        
        if isinstance(response_data, dict):
            jobs_from_api = response_data.get('data', response_data.get('results', [response_data]))
        else:
            jobs_from_api = response_data
            
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch jobs: {str(e)}'},
            status=503
        )
    
    if not jobs_from_api:
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'total_pages': 0,
            'current_page': 1,
            'jobs': []
        })
    
    # Collect farmer and mukkadam IDs
    farmer_ids = set()
    mukkadam_ids = set()
    
    for job in jobs_from_api:
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    # Get mukkadam IDs from allocations
    all_allocations = Allocation.objects.all().select_related('job_activity')
    for alloc in all_allocations:
        mukkadam_ids.add(alloc.mukkadam_id)
    
    # Batch fetch
    batch_start = time.time()
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    batch_elapsed = time.time() - batch_start
    
    # ============================================
    # STEP 2: ENRICH JOBS WITH DB DATA
    # ============================================
    enriched_jobs = []
    
    for idx, job in enumerate(jobs_from_api):
        job_id = str(
            job.get('work_id') or
            job.get('id') or
            job.get('job_id') or
            f"UNKNOWN_{idx}"
        )
        
        # Get farmer details
        farmer_id = str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)
        
        # Get activities
        activities_from_api = job.get('activities', [])
        activities_data = []
        
        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))
            
            # Check DB for activity
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()
            
            # Priority logic: DB if edited/lost, else API
            if db_activity and (db_activity.is_manually_edited or hasattr(db_activity, 'lost_record')):
                activity_name = db_activity.activity_name
                total_area = db_activity.total_area
                total_price = db_activity.total_price
                transport_cost = db_activity.transport_cost
                other_cost = db_activity.other_cost
                crop_bundles = getattr(db_activity, 'crop_bundles', api_activity.get('crop_bundles', 0))
                scheduled_date = db_activity.scheduled_datetime.date() if db_activity.scheduled_datetime else None
                rate_per_acre = db_activity.rate_per_acre
                location = db_activity.location or api_activity.get('location', 'N/A')
            else:
                activity_name = api_activity.get('activity_name', 'Unknown')
                total_area = Decimal(str(api_activity.get('acres', 0)))
                total_price = Decimal(str(api_activity.get('total_price', 0)))
                transport_cost = Decimal(str(api_activity.get('transport_cost', 0)))
                crop_bundles = api_activity.get('crop_bundles', 0)
                other_cost = Decimal(str(api_activity.get('other_cost', 0)))
                scheduled_date = api_activity.get('date_time') or api_activity.get('scheduled_date')
                rate_per_acre = round(
                    float(total_price) / float(total_area), 2
                ) if float(total_area) > 0 else 0.00
                location = api_activity.get('location', 'N/A')
            
            # Calculate allocations
            allocations_data = []
            allocated_area = Decimal('0')
            
            if db_activity:
                for alloc in db_activity.allocations.all():
                    allocated_area += Decimal(str(alloc.allocated_area))
                    mukkadam_data = mukkadams_cache.get(alloc.mukkadam_id, {})
                    mukkadam_name = mukkadam_data.get('mukkadam_name', f'Mukkadam #{alloc.mukkadam_id}')
                    
                    allocations_data.append({
                        'allocation_id': alloc.id,
                        'mukkadam_id': alloc.mukkadam_id,
                        'mukkadam_name': mukkadam_name,
                        'allocated_area': float(alloc.allocated_area),
                        'work_date': str(alloc.work_date) if alloc.work_date else None,
                        'crew_size': alloc.crew_size,
                        'mukkadam_price': float(alloc.mukkadam_price),
                        'transport_type': alloc.transport_type,
                        'transport_price': float(alloc.transport_price or 0),
                        'total_cost': float(alloc.total_cost)
                    })
            
            # Calculate areas
            remaining_area = total_area - allocated_area
            is_fully_allocated = allocated_area >= total_area
            
            def safe_date(value):
                if not value:
                    return ''
                if isinstance(value, str):
                    return value.split('T')[0]
                return str(value)
            
            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': activity_name,
                'activity_type': api_activity.get('activity_type', ''),
                'location': location,
                'total_area': float(total_area),
                'crop_bundles': crop_bundles,
                'allocated_area': float(allocated_area),
                'remaining_area': float(remaining_area),
                'scheduled_date': safe_date(scheduled_date),
                'scheduled_time': api_activity.get('scheduled_time', ''),
                'estimated_workers': api_activity.get('estimated_workers', 10),
                'rate_per_acre': float(rate_per_acre),
                'total_price': float(total_price),
                'transport_cost': float(transport_cost),
                'other_cost': float(other_cost),
                'subtotal': float(api_activity.get('subtotal', 0)),
                'is_fully_allocated': is_fully_allocated,
                'is_manually_edited': db_activity.is_manually_edited if db_activity else False,
                'allocations': allocations_data,
                'is_lost': db_activity.lost_record.is_active if (db_activity and hasattr(db_activity, 'lost_record')) else False,
                'lost_reason': db_activity.lost_record.reason if (db_activity and hasattr(db_activity, 'lost_record') and db_activity.lost_record.is_active) else None,
                'edit_history_count': db_activity.edit_history.count() if db_activity else 0,
            })
        
        # Extract visits and POC
        visits_data = job.get('visits', [])
        point_of_contact = None
        if visits_data and isinstance(visits_data, list):
            point_of_contact = visits_data[0].get('assigned_to')
        
        enriched_job = {
            **job,
            'work_id': job_id,
            'farmer': farmer_details,
            'activities': activities_data,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            'booking': job.get('booking', {}),
            'visits': visits_data,
            'point_of_contact': point_of_contact,
        }
        
        enriched_jobs.append(enriched_job)
    
    # ============================================
    # STEP 3: FILTER FOR JOBS WITH LOST ACTIVITIES
    # ============================================
    lost_jobs = []
    
    for job in enriched_jobs:
        # Check if job has any lost activities
        has_lost = any(a['is_lost'] for a in job['activities'])
        
        if has_lost:
            lost_jobs.append(job)
    
    # ============================================
    # STEP 4: APPLY FILTERS
    # ============================================
    filtered_jobs = []
    
    for job in lost_jobs:
        # Job ID filter
        if job_id_filter:
            if job_id_filter not in str(job.get('work_id', '')):
                continue
        
        # Date filter (check lost activities only)
        if date_filter:
            lost_activities = [a for a in job['activities'] if a['is_lost']]
            has_matching_date = any(
                a.get('scheduled_date', '').startswith(date_filter)
                for a in lost_activities
            )
            if not has_matching_date:
                continue
        
        # Search filter (farmer name/phone)
        if search:
            farmer = job.get('farmer', {})
            farmer_name = farmer.get('farmer_name', '')
            farmer_phone = farmer.get('phone_number', '')
            
            if not (search.lower() in farmer_name.lower() or search in farmer_phone):
                continue
        
        filtered_jobs.append(job)
    
    # ============================================
    # STEP 5: SORT (by work_id or date if needed)
    # ============================================
    # Sort by work_id for now
    filtered_jobs.sort(key=lambda x: str(x.get('work_id', '')))
    
    # ============================================
    # STEP 6: PAGINATION
    # ============================================
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    page_size = min(page_size, 50)
    
    total_count = len(filtered_jobs)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_jobs = filtered_jobs[start_idx:end_idx]
    
    # Build pagination links
    base_url = request.build_absolute_uri(request.path)
    next_link = None
    prev_link = None
    
    if page < total_pages:
        next_link = f"{base_url}?page={page + 1}&page_size={page_size}"
        if search:
            next_link += f"&search={search}"
        if job_id_filter:
            next_link += f"&job_id={job_id_filter}"
        if date_filter:
            next_link += f"&date={date_filter}"
    
    if page > 1:
        prev_link = f"{base_url}?page={page - 1}&page_size={page_size}"
        if search:
            prev_link += f"&search={search}"
        if job_id_filter:
            prev_link += f"&job_id={job_id_filter}"
        if date_filter:
            prev_link += f"&date={date_filter}"
    
    total_elapsed = time.time() - start_time
    
    return Response({
        'count': total_count,
        'next': next_link,
        'previous': prev_link,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': len(paginated_jobs),
        'jobs': paginated_jobs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def allocated_jobs_list(request):
    """
    Get allocated jobs (grouped by job_id) with pagination
    Query params:
    - page: Page number
    - page_size: Items per page (default: 10, max: 50)
    - search: Search in job_id, farmer, mukkadam, activity
    - date: Filter by scheduled date (YYYY-MM-DD)
    - activity_name: Filter by activity name
    """
    start_time = time.time()
    
    search = request.query_params.get('search', '').strip()
    date_filter = request.query_params.get('date')
    activity_name_filter = request.query_params.get('activity_name', '').strip()
    
    # Get allocated/in-progress allocations
    queryset = Allocation.objects.filter(
        status__in=['allocated', 'in_progress']
    ).select_related('job_activity', 'allocated_by').order_by('-allocated_at')
    
    # Collect job IDs and related IDs
    job_ids = set()
    farmer_ids = set()
    mukkadam_ids = set()
    transport_provider_ids = set()
    
    for allocation in queryset:
        job_id = str(allocation.farmer_work_id)
        job_ids.add(job_id)
        mukkadam_ids.add(allocation.mukkadam_id)
        if allocation.transport_provider_id:
            transport_provider_ids.add(allocation.transport_provider_id)
    
    # Fetch jobs from external API
    jobs_cache = {}
    try:
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=500
        )
        
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', data) if isinstance(data, dict) else data
            
            if isinstance(jobs_list, list):
                for job in jobs_list:
                    j_id = str(job.get('work_id') or job.get('id'))
                    if j_id in job_ids:
                        jobs_cache[j_id] = job
                        f_id = job.get('farmer_id')
                        if f_id:
                            farmer_ids.add(str(f_id))
    except Exception as e:
        print(f"❌ Error fetching jobs: {str(e)}")
    
    # Batch fetch related data
    batch_start = time.time()
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)
    batch_elapsed = time.time() - batch_start
    
    # Group allocations by job_id
    allocations_by_job = {}
    for allocation in queryset:
        job_id = str(allocation.farmer_work_id)
        if job_id not in allocations_by_job:
            allocations_by_job[job_id] = []
        allocations_by_job[job_id].append(allocation)
    
    # Filter and enrich jobs
    from datetime import datetime
    def get_effective_job_date(job):
        if not job:
            return datetime.min
        date_str = job.get('scheduled_date')
        if not date_str and job.get('activities'):
            dates = [a.get('scheduled_date') for a in job.get('activities', []) if a.get('scheduled_date')]
            if dates:
                date_str = sorted(dates)[0]
        
        if date_str:
            try:
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return parsed_date.replace(tzinfo=None)
            except:
                pass
        return datetime.min
    
    enriched_jobs = []
    
    for job_id, job_allocations in allocations_by_job.items():
        job_data = jobs_cache.get(job_id, {})
        
        # Apply date filter
        if date_filter:
            job_time = get_effective_job_date(job_data)
            if job_time != datetime.min:
                job_date_str = job_time.strftime('%Y-%m-%d')
                if job_date_str != date_filter:
                    continue
            else:
                continue
        
        # Apply activity name filter
        if activity_name_filter:
            has_matching_activity = any(
                activity_name_filter.lower() in (alloc.job_activity.activity_name or '').lower()
                for alloc in job_allocations
            )
            if not has_matching_activity:
                continue
        
        # Apply search filter
        if search:
            farmer_id = str(job_data.get('farmer_id', ''))
            farmer_data = farmers_cache.get(farmer_id, {})
            farmer_name = farmer_data.get('farmer_name', '')
            
            mukkadam_names = [
                mukkadams_cache.get(alloc.mukkadam_id, {}).get('mukkadam_name', '')
                for alloc in job_allocations
            ]
            
            search_lower = search.lower()
            if not (
                search_lower in job_id.lower() or
                search_lower in (job_data.get('title', '') or '').lower() or
                search_lower in farmer_name.lower() or
                search_lower in (job_data.get('point_of_contact', '') or '').lower() or
                any(search_lower in name.lower() for name in mukkadam_names)
            ):
                continue
        
        # Enrich job data
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})
        
        # Enrich allocations
        enriched_allocations = []
        for allocation in job_allocations:
            mukkadam_data = mukkadams_cache.get(allocation.mukkadam_id, {})
            transport_data = None
            if allocation.transport_provider_id:
                transport_data = transport_providers_cache.get(allocation.transport_provider_id, {})
            
            enriched_allocations.append({
                'id': allocation.id,
                'farmer_work_id': allocation.farmer_work_id,
                'activity_name': allocation.job_activity.activity_name if allocation.job_activity else 'Unknown',
                'allocated_area': float(allocation.allocated_area),
                'work_date': str(allocation.work_date) if allocation.work_date else None,
                'crew_size': allocation.crew_size,
                'status': allocation.status,
                'mukkadam_id': allocation.mukkadam_id,
                'mukkadam_name': mukkadam_data.get('mukkadam_name', f'#{allocation.mukkadam_id}'),
                'mukkadam_price': float(allocation.mukkadam_price),
                'transport_type': allocation.transport_type,
                'transport_provider_id': allocation.transport_provider_id,
                'transport_name': transport_data.get('name') if transport_data else None,
                'transport_price': float(allocation.transport_price or 0),
                'total_cost': float(allocation.total_cost),
                'allocated_at': allocation.allocated_at.isoformat(),
            })

        effective_date = None
        date_str = job_data.get('scheduled_date')

        # Try to get from API job data first
        if not date_str and job_data.get('activities'):
            activity_dates = []
            for activity in job_data.get('activities', []):
                if not activity.get('is_lost'):
                    act_date = activity.get('scheduled_date') or activity.get('date_time')
                    if act_date:
                        activity_dates.append(act_date)
            
            if activity_dates:
                date_str = sorted(activity_dates)[0]

        # ✅ FALLBACK: If job not in external API, get from JobActivity DB records
        if not date_str:
            db_dates = []
            for allocation in job_allocations:
                if allocation.job_activity and allocation.job_activity.scheduled_datetime:
                    db_dates.append(allocation.job_activity.scheduled_datetime)
            
            if db_dates:
                earliest_date = min(db_dates)
                date_str = earliest_date.strftime('%Y-%m-%d')

        if date_str:
            effective_date = date_str.split('T')[0]  # Get just the date part (YYYY-MM-DD)

        enriched_jobs.append({
            'job_id': job_id,
            'job_data': {
                **job_data,
                'farmer': farmer_data,
                'scheduled_date': effective_date,  # ✅ ADD CALCULATED DATE
            },
            'allocations': enriched_allocations,
            'total_mukkadam_cost': sum(float(a.mukkadam_price) for a in job_allocations),
            'total_transport_cost': sum(float(a.transport_price or 0) for a in job_allocations),
            'total_area': sum(float(a.allocated_area) for a in job_allocations),
        })
    
    # Sort by scheduled date
    enriched_jobs.sort(key=lambda x: get_effective_job_date(x['job_data']))
    
    # Manual pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    page_size = min(page_size, 50)
    
    total_count = len(enriched_jobs)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_jobs = enriched_jobs[start_idx:end_idx]
    
    # Build pagination links
    base_url = request.build_absolute_uri(request.path)
    next_link = None
    prev_link = None
    
    if page < total_pages:
        next_link = f"{base_url}?page={page + 1}&page_size={page_size}"
        if search:
            next_link += f"&search={search}"
        if date_filter:
            next_link += f"&date={date_filter}"
        if activity_name_filter:
            next_link += f"&activity_name={activity_name_filter}"
    
    if page > 1:
        prev_link = f"{base_url}?page={page - 1}&page_size={page_size}"
        if search:
            prev_link += f"&search={search}"
        if date_filter:
            prev_link += f"&date={date_filter}"
        if activity_name_filter:
            prev_link += f"&activity_name={activity_name_filter}"
    
    total_elapsed = time.time() - start_time
    
    return Response({
        'count': total_count,
        'next': next_link,
        'previous': prev_link,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': len(paginated_jobs),
        'jobs': paginated_jobs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
        }
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def activity_logs_list(request):
    """
    Get all activity logs with complete details from LOCAL DB
    NO external API calls - everything from ImportedJobSheet, ImportedFarmer, etc.
    """
    start_time = time.time()
    
    # ========================================
    # STEP 1: GET LOGS FROM DATABASE
    # ========================================
    activity_type = request.query_params.get('activity_type')
    mukkadam_id = request.query_params.get('mukkadam_id')
    job_id = request.query_params.get('job_id')
    days = request.query_params.get('days', 30)

    queryset = ActivityLog.objects.all()

    if activity_type:
        queryset = queryset.filter(activity_type=activity_type)
    if mukkadam_id:
        queryset = queryset.filter(mukkadam_id=mukkadam_id)
    if job_id:
        queryset = queryset.filter(job_id=job_id)
    if days:
        from_date = timezone.now() - timedelta(days=int(days))
        queryset = queryset.filter(performed_at__gte=from_date)

    # Fetch 200 most recent logs
    logs_queryset = list(queryset.select_related('performed_by').order_by('-performed_at'))[:200]

    if not logs_queryset:
        return Response({'count': 0, 'logs': []})

    # ========================================
    # STEP 2: COLLECT ALL UNIQUE IDs
    # ========================================
    print("\n📊 Processing activity logs from local DB...")
    
    job_ids = set()
    farmer_ids = set()
    mukkadam_ids = set()
    transport_provider_ids = set()

    for log in logs_queryset:
        if log.job_id:
            job_ids.add(str(log.job_id))
        if log.mukkadam_id:
            mukkadam_ids.add(log.mukkadam_id)
        if log.transport_provider_id:
            transport_provider_ids.add(log.transport_provider_id)

    # ========================================
    # STEP 3: FETCH ALL DATA FROM LOCAL DB
    # ========================================
    print(f"⚡ Fetching from local DB...")
    print(f"   Jobs: {len(job_ids)}")
    print(f"   Mukkadams: {len(mukkadam_ids)}")
    print(f"   Transporters: {len(transport_provider_ids)}")
    
    batch_start = time.time()

    # ✅ 1. Fetch Jobs from ImportedJobSheet
    jobs_cache = {}
    if job_ids:
        job_sheets = ImportedJobSheet.objects.filter(
            generated_job_id__in=job_ids
        ).values('generated_job_id', 'farmer_name', 'location', 'activity_start_date', 
                 'generated_farmer_id', 'allocation_status',)
        
        # Group by job_id (in case multiple activities per job)
        for sheet in job_sheets:
            job_id = sheet['generated_job_id']
            if job_id not in jobs_cache:
                jobs_cache[job_id] = {
                    'job_id': job_id,
                    'job_name': f"Job #{job_id}",
                    'location': sheet['location'] or 'N/A',
                    'scheduled_date': str(sheet['activity_start_date']) if sheet['activity_start_date'] else 'N/A',
                    'farmer_id': sheet['generated_farmer_id'],
                    # 'status': sheet['job_status'] or 'PENDING',
                    # 'priority': sheet['job_priority'] or 'MEDIUM',
                    'farmer_name': sheet['farmer_name'],
                }
                
                # Add farmer_id to set
                if sheet['generated_farmer_id']:
                    farmer_ids.add(str(sheet['generated_farmer_id']))

    # ✅ 2. Fetch Farmers from ImportedFarmer
    farmers_cache = {}
    if farmer_ids:
        farmers_qs = ImportedFarmer.objects.filter(external_farmer_id__in=farmer_ids)
        for farmer in farmers_qs:
            location_parts = farmer.location.split(',') if farmer.location else []
            farmers_cache[farmer.external_farmer_id] = {
                'farmer_id': farmer.external_farmer_id,
                'farmer_name': farmer.name,
                'phone_number': farmer.contact_no or 'N/A',
                'location': farmer.location or 'N/A',
                'village': location_parts[0].strip() if len(location_parts) > 0 else '',
                'taluka': location_parts[1].strip() if len(location_parts) > 1 else '',
                'district': location_parts[2].strip() if len(location_parts) > 2 else '',
            }

    # ✅ 3. Fetch Mukkadams from ImportedMukkadam
    mukkadams_cache = {}
    if mukkadam_ids:
        mukkadams_qs = ImportedMukkadam.objects.filter(external_mukkadam_id__in=mukkadam_ids)
        for mukkadam in mukkadams_qs:
            mukkadams_cache[mukkadam.external_mukkadam_id] = {
                'mukkadam_id': mukkadam.external_mukkadam_id,
                'mukkadam_name': mukkadam.team_name,
                'contact_no': mukkadam.contact_no or 'N/A'
            }

    # ✅ 4. Fetch Transporters from ImportedTransporter
    transport_providers_cache = {}
    if transport_provider_ids:
        transporters_qs = ImportedTransporter.objects.filter(external_transporter_id__in=transport_provider_ids)
        for transporter in transporters_qs:
            transport_providers_cache[transporter.external_transporter_id] = {
                'transporter_id': transporter.external_transporter_id,
                'name': transporter.name,
                'contact_no': transporter.contact_no or 'N/A'
            }

    batch_elapsed = time.time() - batch_start
    print(f"✅ Local DB fetching completed in {batch_elapsed:.2f}s")
    print(f"   Jobs found: {len(jobs_cache)}")
    print(f"   Farmers found: {len(farmers_cache)}")
    print(f"   Mukkadams found: {len(mukkadams_cache)}")
    print(f"   Transporters found: {len(transport_providers_cache)}")

    # ========================================
    # STEP 4: BUILD ENRICHED LOGS
    # ========================================
    logs = []

    for log in logs_queryset:
        # 1. Mukkadam Data
        mukkadam_name = 'Unknown'
        mukkadam_contact = None
        if log.mukkadam_id:
            m_data = mukkadams_cache.get(log.mukkadam_id)
            if m_data:
                mukkadam_name = m_data.get('mukkadam_name', f'#{log.mukkadam_id}')
                mukkadam_contact = m_data.get('contact_no')
            else:
                mukkadam_name = f'#{log.mukkadam_id}'

        # 2. Transport Data
        transport_name = None
        transport_contact = None
        if log.transport_provider_id:
            t_data = transport_providers_cache.get(log.transport_provider_id)
            if t_data:
                transport_name = t_data.get('name', f'#{log.transport_provider_id}')
                transport_contact = t_data.get('contact_no')
            else:
                transport_name = f'#{log.transport_provider_id}'

        # 3. Job & Farmer Data (from ImportedJobSheet + ImportedFarmer)
        farmer_name = None
        farmer_details = None
        job_details = None
        
        if log.job_id:
            job_data = jobs_cache.get(str(log.job_id))
            
            if job_data:
                # Get Farmer ID from the Job
                f_id = str(job_data.get('farmer_id', ''))
                
                # Get Farmer Details from Cache
                f_details = farmers_cache.get(f_id)
                if f_details:
                    farmer_details = f_details
                    farmer_name = f_details.get('farmer_name', 'Unknown Farmer')
                else:
                    # Fallback to farmer_name from ImportedJobSheet
                    farmer_name = job_data.get('farmer_name', f'Farmer #{f_id}' if f_id else 'Unknown Farmer')
                    farmer_details = {
                        'farmer_id': f_id,
                        'farmer_name': farmer_name,
                        'phone_number': 'N/A',
                        'location': 'N/A'
                    }

                # Store job info for the log
                job_details = {
                    'job_id': job_data.get('job_id'),
                    'job_name': job_data.get('job_name'),
                    'location': job_data.get('location'),
                    'scheduled_date': job_data.get('scheduled_date'),
                    'status': job_data.get('status'),
                    'priority': job_data.get('priority'),
                }
            else:
                # Job not found in ImportedJobSheet
                job_details = {
                    'job_id': log.job_id,
                    'job_name': f'Job #{log.job_id}',
                    'location': 'N/A',
                    'scheduled_date': 'N/A',
                    'status': 'N/A',
                }

        # 4. Construct Final Object
        log_entry = {
            'id': log.id,
            'activity_type': log.activity_type,
            'activity_type_display': log.get_activity_type_display(),
            'description': log.description,
            'job_id': log.job_id,
            'job_details': job_details,
            
            'mukkadam_id': log.mukkadam_id,
            'mukkadam_name': mukkadam_name,
            'mukkadam_contact': mukkadam_contact,
            
            'transport_provider_id': log.transport_provider_id,
            'transport_name': transport_name,
            'transport_contact': transport_contact,
            
            # Farmer fields
            'farmer_id': farmer_details.get('farmer_id') if farmer_details else None,
            'farmer_name': farmer_name,
            'farmer_details': farmer_details,
            
            'amount': float(log.amount) if log.amount else None,
            'performed_by': log.performed_by.username if log.performed_by else 'System',
            'performed_by_name': log.performed_by.username if log.performed_by else 'System',
            'performed_at': log.performed_at.isoformat(),
            'metadata': log.metadata,
            'changes': log.changes,
        }
        
        # Format changes for display (if exists)
        if log.changes:
            log_entry['formatted_changes'] = format_changes_for_display(log.changes)
        
        logs.append(log_entry)

    total_elapsed = time.time() - start_time
    
    return Response({
        'count': len(logs),
        'logs': logs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
            'jobs_fetched': len(jobs_cache),
            'farmers_fetched': len(farmers_cache),
            'mukkadams_fetched': len(mukkadams_cache),
            'transporters_fetched': len(transport_providers_cache),
        }
    })


# Helper function for formatting changes
def format_changes_for_display(changes):
    """
    Format changes dict for human-readable display
    
    Input:
    {
        "allocated_area": {"old": "1.5", "new": "2.0"},
        "mukkadam_price": {"old": "5000", "new": "5500"}
    }
    
    Output:
    [
        {"field": "Allocated Area", "old_value": "1.5 acres", "new_value": "2.0 acres"},
        {"field": "Mukkadam Price", "old_value": "₹5000", "new_value": "₹5500"}
    ]
    """
    if not changes or not isinstance(changes, dict):
        return []
    
    formatted = []
    
    # Field name mappings for display
    field_labels = {
        'allocated_area': 'Allocated Area',
        'work_date': 'Work Date',
        'crew_size': 'Crew Size',
        'mukkadam_price': 'Mukkadam Price',
        'transport_type': 'Transport Type',
        'transport_provider_id': 'Transport Provider',
        'transport_price': 'Transport Price',
        'own_transport_price': 'Own Transport Price',
        'mukkadam_id': 'Mukkadam',
        'status': 'Status',
    }
    
    # Value formatting rules
    def format_value(field, value):
        if value is None or value == '':
            return 'N/A'
        
        if field in ['mukkadam_price', 'transport_price', 'own_transport_price']:
            return f"₹{float(value):,.2f}"
        
        if field == 'allocated_area':
            return f"{value} acres"
        
        if field == 'crew_size':
            return f"{value} workers"
        
        if field == 'transport_type':
            return value.replace('_', ' ').title()
        
        return str(value)
    
    for field, change_data in changes.items():
        if isinstance(change_data, dict) and 'old' in change_data and 'new' in change_data:
            formatted.append({
                'field': field_labels.get(field, field.replace('_', ' ').title()),
                'old_value': format_value(field, change_data['old']),
                'new_value': format_value(field, change_data['new']),
            })
    
    return formatted


def batch_fetch_farmers_debug(farmer_ids, max_workers=5):
    print(f"🔄 Executing batch_fetch for: {farmer_ids}")
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {
            executor.submit(get_farmer_cached, f_id): str(f_id) 
            for f_id in farmer_ids
        }
        
        first_success_printed = False
        
        for future in as_completed(future_to_id):
            f_id_str = future_to_id[future]
            try:
                data = future.result()
                
                if data:
                    results[f_id_str] = data
                    
                    # CRITICAL: Print the structure of the first successful result
                    if not first_success_printed:
                        print(f"\n🔎 [INSPECT API DATA] Result for ID {f_id_str}:")
                        pprint.pprint(data)
                        print(f"👉 Available Keys: {list(data.keys())}\n")
                        first_success_printed = True
                else:
                    print(f"⚠️ API returned None/Empty for ID: {f_id_str}")
                    
            except Exception as e:
                print(f"❌ EXCEPTION for ID {f_id_str}: {e}")
                
    return results# ✅ HELPER FUNCTION: Format changes for display
def format_changes_for_display(changes):
    """Convert changes dict to user-friendly format"""
    if not changes:
        return []
    
    formatted = []
    field_labels = {
        'activity_name': 'Activity Name',
        'total_area': 'Total Area',
        'scheduled_datetime': 'Scheduled Date',
        'total_price': 'Mukkadam Price',
        'transport_cost': 'Transport Cost',
        'other_cost': 'Other Cost',
        'subtotal': 'Total Price',
        'rate_per_acre': 'Rate/Acre',
        'mukkadam_id': 'Mukkadam',
        'transport_provider_id': 'Transport Provider',
    }
    
    for field, change_data in changes.items():
        if isinstance(change_data, dict):
            old_val = change_data.get('old_value', change_data.get('old'))
            new_val = change_data.get('new_value', change_data.get('new'))
            
            formatted.append({
                'field': field,
                'label': field_labels.get(field, field.replace('_', ' ').title()),
                'old_value': old_val,
                'new_value': new_val,
            })
    
    return formatted

# ✅ HELPER FUNCTION: Format changes for display
def format_changes_for_display(changes):
    """Convert changes dict to user-friendly format"""
    if not changes:
        return []
    
    formatted = []
    field_labels = {
        'activity_name': 'Activity Name',
        'total_area': 'Total Area',
        'scheduled_datetime': 'Scheduled Date',
        'total_price': 'Mukkadam Price',
        'transport_cost': 'Transport Cost',
        'other_cost': 'Other Cost',
        'subtotal': 'Total Price',
        'rate_per_acre': 'Rate/Acre',
        'mukkadam_id': 'Mukkadam',
        'transport_provider_id': 'Transport Provider',
    }
    
    for field, change_data in changes.items():
        if isinstance(change_data, dict):
            old_val = change_data.get('old_value', change_data.get('old'))
            new_val = change_data.get('new_value', change_data.get('new'))
            
            formatted.append({
                'field': field,
                'label': field_labels.get(field, field.replace('_', ' ').title()),
                'old_value': old_val,
                'new_value': new_val,
            })
    
    return formatted


# ✅ HELPER FUNCTION: Format changes for display
def format_changes_for_display(changes):
    """Convert changes dict to user-friendly format"""
    if not changes:
        return []
    
    formatted = []
    field_labels = {
        'activity_name': 'Activity Name',
        'total_area': 'Total Area',
        'scheduled_datetime': 'Scheduled Date',
        'total_price': 'Mukkadam Price',
        'transport_cost': 'Transport Cost',
        'other_cost': 'Other Cost',
        'subtotal': 'Total Price',
        'rate_per_acre': 'Rate/Acre',
        'mukkadam_id': 'Mukkadam',
        'transport_provider_id': 'Transport Provider',
    }
    
    for field, change_data in changes.items():
        if isinstance(change_data, dict):
            old_val = change_data.get('old_value', change_data.get('old'))
            new_val = change_data.get('new_value', change_data.get('new'))
            
            formatted.append({
                'field': field,
                'label': field_labels.get(field, field.replace('_', ' ').title()),
                'old_value': old_val,
                'new_value': new_val,
            })
    
    return formatted

# ✅ HELPER FUNCTION: Format changes for display
def format_changes_for_display(changes):
    """Convert changes dict to user-friendly format"""
    if not changes:
        return []
    
    formatted = []
    field_labels = {
        'activity_name': 'Activity Name',
        'total_area': 'Total Area',
        'scheduled_datetime': 'Scheduled Date',
        'total_price': 'Mukkadam Price',
        'transport_cost': 'Transport Cost',
        'other_cost': 'Other Cost',
        'subtotal': 'Total Price',
        'rate_per_acre': 'Rate/Acre',
        'mukkadam_id': 'Mukkadam',
        'transport_provider_id': 'Transport Provider',
    }
    
    for field, change_data in changes.items():
        if isinstance(change_data, dict):
            old_val = change_data.get('old_value', change_data.get('old'))
            new_val = change_data.get('new_value', change_data.get('new'))
            
            formatted.append({
                'field': field,
                'label': field_labels.get(field, field.replace('_', ' ').title()),
                'old_value': old_val,
                'new_value': new_val,
            })
    
    return formatted

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import requests
import time
from concurrent.futures import ThreadPoolExecutor
# allocation_app/views.py
from rest_framework import viewsets, permissions
from .models import FarmerCall
from .serializers import FarmerCallSerializer

class FarmerCallViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows FarmerCalls to be viewed.
    """
    queryset = FarmerCall.objects.all().order_by('-initiated_at')
    serializer_class = FarmerCallSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Optional: Filter by mobile_number or job_id if passed in params
        queryset = super().get_queryset()
        mobile = self.request.query_params.get('mobile_number')
        if mobile:
            queryset = queryset.filter(mobile_number=mobile)
        return queryset


# Import your models
import random
from django.db.models import Q
from decimal import Decimal
from .models import ImportedJobSheet
import random
from django.db.models import Q
from decimal import Decimal
@api_view(['GET'])
@permission_classes([AllowAny])
def jobs_list(request):
    """
    Fetch jobs from LOCAL DB (ImportedJobSheet) and enrich with allocation data
    ✅ Check allocations in BOTH JobActivity AND Allocation table directly
    """
    import time
    import random
    from decimal import Decimal
    
    start_time = time.time()

    # Get filter params
    farmer_name_filter = request.GET.get('farmer_name', '').strip()
    status_filter = request.GET.get('status', '').strip()
    booking_type_filter = request.GET.get('booking_type', '').strip().upper()


    # ========================================
    # STEP 1: FETCH JOBS FROM DB
    # ========================================
    print("📥 Fetching jobs from ImportedJobSheet...")
    
    # ✅ FIX: Use 'imported_job' instead of 'job_activity'
    job_sheets = ImportedJobSheet.objects.all().select_related(
        'imported_job',
        'job_activity'
    ).order_by('generated_job_id', 'activity_start_date')
    
    total_count = job_sheets.count()
    print(f"📊 Total records in ImportedJobSheet: {total_count}")
    
    if total_count == 0:
        print("⚠️ WARNING: No data in ImportedJobSheet!")
        return Response({
            'error': 'No data found in ImportedJobSheet. Please sync data first.',
            'suggestion': 'Run: python manage.py sync_external_jobs'
        }, status=404)
    
    # ========================================
    # STEP 2: GROUP BY JOB
    # ========================================
    jobs_dict = {}
    
    for sheet in job_sheets:
        job_id = sheet.generated_job_id
        
        if job_id not in jobs_dict:
            # ✅ FIX: Get external_job_id from imported_job relationship
            if sheet.imported_job:
                external_job_id = sheet.imported_job.external_job_id
                job_status = sheet.imported_job.status
                job_priority = sheet.imported_job.priority
                scheduled_date = sheet.imported_job.scheduled_date
                activity_notes = sheet.imported_job.activity_notes
                internal_notes = sheet.imported_job.internal_notes
                total_activities_amount = float(sheet.total_booking_value or 0)
                is_field_verified = sheet.imported_job.is_field_verified
                plot_id = sheet.imported_job.plot_id
                raw_booking_data = sheet.imported_job.raw_booking_data
                raw_visits_data = sheet.imported_job.raw_visits_data
                created_at = sheet.imported_job.created_at
                booking_type = sheet.imported_job.booking_type
            else:
                # Fallback for sheet imports
                external_job_id = int(job_id.replace('SHEET_', '').replace('_', '')) if 'SHEET' in job_id else None
                job_status = 'PENDING'
                job_priority = 'MEDIUM'
                scheduled_date = None
                activity_notes = sheet.allocation_team_remarks or ''
                internal_notes = sheet.field_team_remarks or ''
                total_activities_amount = 0
                is_field_verified = False
                plot_id = None
                booking_type = sheet.imported_job.booking_type if sheet.imported_job else 'ON_DEMAND'
                raw_booking_data = {}
                raw_visits_data = []
                created_at = sheet.activity_start_date
            
            jobs_dict[job_id] = {
                'id': job_id,
                'work_id': job_id,
                'farmer_id': sheet.generated_farmer_id or '',
                'plot_id': plot_id,
                'status': job_status,
                'priority': job_priority,
                'scheduled_date': scheduled_date.isoformat() if scheduled_date else None,
                'activity_notes': activity_notes,
                'internal_notes': internal_notes,
                'total_activities_amount': float(sheet.total_booking_value or 0),
                'is_field_verified': is_field_verified,
                'booking_type': booking_type,
                'activities': [],
                'booking': raw_booking_data or {},
                'visits': raw_visits_data or [],
                'created_at': created_at.isoformat() if created_at else None,
            }
        
        # Parse acres
        try:
            acres_str = str(sheet.acres or '0')
            # Extract numbers from strings like "7 Labours" or "1.5"
            import re
            match = re.search(r'[\d.]+', acres_str)
            acres_value = float(match.group()) if match else 0
        except:
            acres_value = 0
        
        activity_id = sheet.external_activity_id if sheet.external_activity_id else f"{job_id}_ACT_{len(jobs_dict[job_id]['activities']) + 1}"
        subtotal_value = sheet.total_booking_value
        if subtotal_value is None:
            # fall back to total_price or booking_value or 0
            if sheet.total_price is not None:
                subtotal_value = sheet.total_price
            elif sheet.booking_value is not None:
                subtotal_value = sheet.booking_value
            else:
                subtotal_value = 0
        jobs_dict[job_id]['activities'].append({
            'id': activity_id,
            'activity_id': str(activity_id),
            'activity_name': sheet.activity_name,
            'activity_type': '',
            'date_time': sheet.activity_start_date.isoformat() if sheet.activity_start_date else None,
            'acres': acres_value,
            'total_price':  (float(sheet.booking_value) if sheet.booking_value else 0),  # ✅ Use total_price or booking_value
            'transport_cost': float(sheet.transport_cost) if sheet.transport_cost else 0,
            'other_cost': float(sheet.other_cost) if sheet.other_cost else 0,
            'subtotal': float(subtotal_value),
            'activity_note': sheet.allocation_team_remarks or sheet.activity_note or None,
            'crop_bundles': 0,
            'location': sheet.location or 'N/A',
            'sheet_id': sheet.id,
        })

        
        # Update total if from booking value
        if sheet.booking_value:
            if jobs_dict[job_id]['total_activities_amount'] == 0:  # Only update if not set from ImportedJob
                jobs_dict[job_id]['total_activities_amount'] += float(sheet.booking_value)
    
    jobs_from_api = list(jobs_dict.values())
    
    print(f"✓ Grouped into {len(jobs_from_api)} jobs\n")
    
    if len(jobs_from_api) == 0:
        return Response([])


    # ========================================
    # STEP 3: FILTER BY BOOKING TYPE (TENDER / ON_DEMAND)
    # ========================================
    if booking_type_filter:
        # Expect values: TENDER or ON_DEMAND (matches ImportedJob.booking_type)
        jobs_from_api = [
            job for job in jobs_from_api
            if str(job.get('booking_type') or '').upper() == booking_type_filter
        ]
        print(f"🔍 Filtered by booking_type={booking_type_filter}, remaining jobs: {len(jobs_from_api)}")

        if not jobs_from_api:
            return Response([])

    
    # ========================================
    # STEP 3: FILTER BY FARMER NAME (if provided)
    # ========================================
    if farmer_name_filter:
        print(f"🔍 Filtering jobs by farmer name: {farmer_name_filter}")
        
        matching_farmers = ImportedFarmer.objects.filter(
            name__icontains=farmer_name_filter
        ).values_list('external_farmer_id', flat=True)
        
        jobs_from_api = [
            job for job in jobs_from_api 
            if job.get('farmer_id') in list(matching_farmers)
        ]
        
        print(f"✓ Found {len(jobs_from_api)} jobs for farmer '{farmer_name_filter}'\n")
        
        if not jobs_from_api:
            return Response([])

    # ========================================
    # STEP 4: COLLECT ALL UNIQUE IDs FOR ENRICHMENT
    # ========================================
    farmer_ids = set()
    mukkadam_ids = set()

    for job in jobs_from_api:
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))

    job_ids_from_api = set(str(job.get('work_id') or job.get('id')) for job in jobs_from_api)
    
    # ✅ FIX: Get JobActivity by job_id OR by sheet relationship
    db_activities = JobActivity.objects.filter(
        job_id__in=job_ids_from_api
    ).values('id', 'job_id', 'farmer_work_id', 'activity_name')
    
    job_to_farmer_map = {}
    job_activity_map = {}  # Map by job_id -> activity_name -> JobActivity
    
    for activity in db_activities:
        job_id = str(activity['job_id'])
        farmer_work_id = str(activity['farmer_work_id']) if activity['farmer_work_id'] else None
        activity_name = activity['activity_name'].lower()
        
        if farmer_work_id:
            job_to_farmer_map[job_id] = farmer_work_id
            farmer_ids.add(farmer_work_id)
        
        if job_id not in job_activity_map:
            job_activity_map[job_id] = {}
        
        job_activity_map[job_id][activity_name] = activity['id']
    
    # ✅ Get ALL allocations for these JobActivities
    all_allocations_qs = Allocation.objects.filter(
        job_activity__job_id__in=job_ids_from_api
    ).select_related('job_activity')
    
    for alloc in all_allocations_qs:
        if alloc.mukkadam_id:
            mukkadam_ids.add(alloc.mukkadam_id)

    # ========================================
    # STEP 5: FETCH FARMERS & MUKKADAMS FROM LOCAL DB
    # ========================================
    print(f"\n⚡ FETCHING FROM LOCAL DB...")
    print(f"   Fetching {len(farmer_ids)} farmers, {len(mukkadam_ids)} mukkadams")
    batch_start = time.time()

    farmers_cache = {}
    if farmer_ids:
        farmers_qs = ImportedFarmer.objects.filter(external_farmer_id__in=farmer_ids)
        for farmer in farmers_qs:
            location_parts = farmer.location.split(',') if farmer.location else []
            farmers_cache[farmer.external_farmer_id] = {
                'farmer_id': farmer.external_farmer_id,
                'farmer_name': farmer.name,
                'phone_number': farmer.contact_no,
                'village': location_parts[0].strip() if len(location_parts) > 0 else '',
                'taluka': location_parts[1].strip() if len(location_parts) > 1 else '',
                'district': location_parts[2].strip() if len(location_parts) > 2 else '',
                'location': farmer.location or ''
            }

    mukkadams_cache = {}
    if mukkadam_ids:
        mukkadams_qs = ImportedMukkadam.objects.filter(external_mukkadam_id__in=mukkadam_ids)
        for mukkadam in mukkadams_qs:
            mukkadams_cache[mukkadam.external_mukkadam_id] = {
                'mukkadam_name': mukkadam.team_name,
                'contact_no': mukkadam.contact_no
            }

    batch_elapsed = time.time() - batch_start
    print(f"✅ Local DB fetching completed in {batch_elapsed:.2f}s")

    # ========================================
    # STEP 6: ENRICH JOBS (WITH REAL STATUS CALCULATION)
    # ========================================
    enriched_jobs = []
    MH_LAT_MIN, MH_LAT_MAX = 16.0, 21.0
    MH_LON_MIN, MH_LON_MAX = 73.0, 79.0

    for idx, job in enumerate(jobs_from_api):
        job_id = str(job.get('work_id') or job.get('id'))

        farmer_id = job_to_farmer_map.get(job_id) or str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)

        # ✅ Get JobActivities for this job
        job_activities_for_job = JobActivity.objects.filter(
            job_id=job_id
        ).prefetch_related('allocations')
        
        # Create a map by activity name
        job_activities_by_name = {}
        for ja in job_activities_for_job:
            job_activities_by_name[ja.activity_name.lower()] = ja

        activities_from_api = job.get('activities', [])
        activities_data = []

        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))
            activity_name = api_activity.get('activity_name', 'Unknown')

            # ✅ Match by activity name
            db_activity = job_activities_by_name.get(activity_name.lower())

            # Use DB data if manually edited, otherwise use API data
            if db_activity and db_activity.is_manually_edited:
                activity_name = db_activity.activity_name
                total_area = db_activity.total_area
                total_price = db_activity.total_price
                transport_cost = db_activity.transport_cost
                other_cost = db_activity.other_cost
                crop_bundles = getattr(db_activity, 'crop_bundles', 0)
                scheduled_date = db_activity.scheduled_datetime.date() if db_activity.scheduled_datetime else None
                rate_per_acre = db_activity.rate_per_acre
                location = db_activity.location
            else:
                activity_name = api_activity.get('activity_name', 'Unknown')
                total_area = Decimal(str(api_activity.get('acres', 0)))
                total_price = Decimal(str(api_activity.get('total_price', 0)))
                transport_cost = Decimal(str(api_activity.get('transport_cost', 0)))
                crop_bundles = 0
                other_cost = Decimal('0')
                scheduled_date = api_activity.get('date_time', '')
                rate_per_acre = round(float(total_price) / float(total_area), 2) if float(total_area) > 0 else 0
                location = api_activity.get('location', 'N/A')

            # Get allocations
            allocations_data = []
            allocated_area = Decimal('0')

            pending_count = 0
            completed_count = 0
            in_progress_count = 0
            partially_allocated_count = 0
            fully_allocated_count = 0  # ✅ NEW
            mukkadam_price =0
            transport_price = 0
            total_price = 0
            other_cost = 0
            subtotal_value = 0

            if db_activity:
                for alloc in db_activity.allocations.all():
                    allocated_area += alloc.allocated_area
                    
                    # ✅ UPDATED: Handle legacy 'allocated' status
                    alloc_status = alloc.status
                    
                    # Map legacy 'allocated' to appropriate status
                    if alloc_status == 'allocated':
                        # Check if activity is fully allocated
                        if is_fully_allocated or alloc.allocated_area >= db_activity.total_area:
                            alloc_status = 'fully_allocated'
                        else:
                            alloc_status = 'partially_allocated'
                    
                    # Count by status
                    if alloc_status == 'completed':
                        completed_count += 1
                    elif alloc_status == 'in_progress':
                        in_progress_count += 1
                    elif alloc_status == 'partially_allocated':
                        partially_allocated_count += 1
                    elif alloc_status == 'fully_allocated':
                        fully_allocated_count += 1
                    else:
                        pending_count += 1

                    # ✅ Get mukkadam name (with auto-fetch from external API)
                    mukkadam_name = None
                    mukkadam_contact = None

                    # First check if linked to ImportedMukkadam
                    if alloc.imported_mukkadam:
                        mukkadam_name = alloc.imported_mukkadam.team_name
                        mukkadam_contact = alloc.imported_mukkadam.contact_no
                    else:
                        # Check mukkadams_cache (from external API call)
                        mukkadam_data = mukkadams_cache.get(alloc.mukkadam_id, {})
                        if mukkadam_data:
                            mukkadam_name = mukkadam_data.get('mukkadam_name', None)
                            mukkadam_contact = mukkadam_data.get('mobile_numbers', None)
                        
                        # If still not found, check local DB
                        if not mukkadam_name:
                            local_mukkadam = ImportedMukkadam.objects.filter(
                                external_mukkadam_id=alloc.mukkadam_id
                            ).first()
                            
                            if local_mukkadam:
                                mukkadam_name = local_mukkadam.team_name
                                mukkadam_contact = local_mukkadam.contact_no
                            else:
                                # ✅ FETCH FROM EXTERNAL API AND CACHE IN DB
                                mukkadam_name, mukkadam_contact = fetch_and_cache_mukkadam(alloc.mukkadam_id)
            # ✅ Get payment request info
                    payment_request_data = None
                    try:
                        if hasattr(alloc, 'payment_request'):
                            pr = alloc.payment_request
                            payment_request_data = {
                                'status': pr.status,
                                'requested_amount': float(pr.requested_amount),
                                'requested_at': pr.requested_at.isoformat() if pr.requested_at else None,
                                'paid_at': pr.paid_at.isoformat() if pr.paid_at else None,
                            }
                    except:
                        pass

                    # ✅ Get transport payment request info
                    
                    transport_payment_data = None
                    try:
                        if hasattr(alloc, 'transport_payment_request'):
                            tpr = alloc.transport_payment_request
                            transport_payment_data = {
                                'status': tpr.status,
                                'requested_amount': float(tpr.requested_amount),
                                'requested_at': tpr.requested_at.isoformat() if tpr.requested_at else None,
                                'paid_at': tpr.paid_at.isoformat() if tpr.paid_at else None,
                            }
                    except:
                        pass

                    allocations_data.append({
                        'allocation_id': alloc.id,
                        'mukkadam_id': alloc.mukkadam_id,
                        'mukkadam_name': mukkadam_name,
                        'allocated_area': float(alloc.allocated_area),
                        'work_date': str(alloc.work_date),
                        'crew_size': alloc.crew_size,
                        'mukkadam_price': float(alloc.mukkadam_price),
                        'transport_type': alloc.transport_type,
                        'transport_provider_id': alloc.transport_provider_id,
                        'own_transport_price': float(alloc.own_transport_price or 0),
                        'transport_price': float(alloc.transport_price or 0),
                        'total_cost': float(alloc.total_cost),
                        'status': alloc_status,
                        'payment_request': payment_request_data,  # ✅ ADD THIS
                        'transport_payment_request': transport_payment_data,  # ✅ ADD THIS
                    })


            remaining_area = total_area - allocated_area
            is_fully_allocated = allocated_area >= total_area

            mukkadam_price = float(db_activity.total_price) if db_activity and db_activity.total_price else float(total_price)
            transport_price = float(db_activity.transport_cost) if db_activity and db_activity.transport_cost else float(transport_cost)
            other_cost = float(db_activity.other_cost) if db_activity and db_activity.other_cost else float(other_cost)
            subtotal_value = float(db_activity.total_price + db_activity.transport_cost + db_activity.other_cost) if db_activity else float(subtotal_value)
            def safe_date(value):
                if not value:
                    return ''
                if isinstance(value, str):
                    return value.split('T')[0]
                return str(value)

            # ✅ UPDATED: Calculate activity allocation status
            activity_allocation_status = 'pending'

            if allocations_data:
                # Priority: completed > in_progress > fully_allocated > partially_allocated
                if completed_count == len(allocations_data):
                    activity_allocation_status = 'completed'
                elif in_progress_count > 0 or completed_count > 0:
                    activity_allocation_status = 'in_progress'
                elif fully_allocated_count > 0 and is_fully_allocated:  # ✅ Check for fully_allocated
                    activity_allocation_status = 'fully_allocated'
                elif partially_allocated_count > 0 or (allocated_area > 0 and not is_fully_allocated):
                    activity_allocation_status = 'partially_allocated'
                else:
                    activity_allocation_status = 'allocated'
            # ✅✅✅ ADD FARMER PAYMENTS BEFORE APPENDING TO activities_data
            farmer_payments_data = None
            if db_activity:
                # Fetch farmer payments for this activity
                farmer_payments_qs = db_activity.farmer_payments.all()
                
                farmer_payment_list = []
                total_farmer_paid = Decimal('0')
                total_farmer_pending = Decimal('0')
                
                for fp in farmer_payments_qs:
                    farmer_payment_list.append({
                        'payment_id': fp.id,
                        'booking_value': float(fp.booking_value),
                        'payment_status': fp.payment_status,
                        'payment_route': fp.payment_route,
                        'date_of_payment': str(fp.date_of_payment) if fp.date_of_payment else None,
                        'activity_date': str(fp.activity_date),
                        'reference_no': fp.reference_no,
                        'description': fp.description,
                        'village': fp.village,
                        'acres': fp.acres
                    })
                    
                    if fp.payment_status == 'paid':
                        total_farmer_paid += fp.booking_value
                    else:
                        total_farmer_pending += fp.booking_value
                
                total_expected = total_farmer_paid + total_farmer_pending
                
                farmer_payments_data = {
                    'total_expected': float(total_expected),
                    'total_paid': float(total_farmer_paid),
                    'total_pending': float(total_farmer_pending),
                    'payment_count': len(farmer_payment_list),
                    'paid_count': sum(1 for p in farmer_payment_list if p['payment_status'] == 'paid'),
                    'pending_count': sum(1 for p in farmer_payment_list if p['payment_status'] == 'pending'),
                    'completion_percentage': round(
                        (float(total_farmer_paid) / float(total_expected) * 100) 
                        if total_expected > 0 else 0, 
                        2
                    ),
                    'payments': farmer_payment_list
                }

            # ✅ NOW APPEND WITH farmer_payments
            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': activity_name,
                'activity_type': '',
                'location': location,
                'total_area': float(total_area),
                'crop_bundles': crop_bundles,
                'allocated_area': float(allocated_area),
                'remaining_area': float(remaining_area),
                'scheduled_date': safe_date(scheduled_date),
                'scheduled_time': '',
                'estimated_workers': 10,
                'rate_per_acre': float(rate_per_acre),
                'total_price': mukkadam_price,
                'transport_cost': transport_price,
                'other_cost': other_cost,
                'subtotal': subtotal_value,
                'is_fully_allocated': is_fully_allocated,
                'is_manually_edited': db_activity.is_manually_edited if db_activity else False,
                'allocations': allocations_data,
                'allocation_status': activity_allocation_status,
                'allocation_counts': {
                    'total': len(allocations_data),
                    'pending': pending_count,
                    'in_progress': in_progress_count,
                    'completed': completed_count,
                    'partially_allocated': partially_allocated_count,
                    'fully_allocated': fully_allocated_count,
                },
                'is_lost': db_activity.lost_record.is_active if (db_activity and hasattr(db_activity, 'lost_record')) else False,
                'lost_reason': db_activity.lost_record.reason if (db_activity and hasattr(db_activity, 'lost_record') and db_activity.lost_record.is_active) else None,
                'farmer_payments': farmer_payments_data,  # ✅✅✅ ADD THIS LINE
            })


        # Calculate JOB-LEVEL status
        def calculate_job_status(activities):
            if not activities:
                return 'pending'

            all_statuses = [a['allocation_status'] for a in activities]
            
            # If any activity is in progress, job is in progress
            if 'in_progress' in all_statuses:
                return 'in_progress'
            
            # If all activities are completed
            if all(status == 'completed' for status in all_statuses):
                return 'completed'
            
            # ✅ If all activities are fully allocated (not necessarily completed)
            if all(status in ['completed', 'fully_allocated'] for status in all_statuses):
                if any(status == 'completed' for status in all_statuses):
                    return 'in_progress'  # Some completed = work started
                return 'fully_allocated'  # All allocated but not started
            
            # If any activity has some allocation
            if any(status in ['partially_allocated', 'fully_allocated', 'in_progress', 'completed'] for status in all_statuses):
                # If at least one activity is NOT fully allocated
                if any(status == 'partially_allocated' for status in all_statuses):
                    return 'partially_allocated'
                # All that have allocations are fully allocated
                return 'partially_allocated'  # Some activities might still be pending
            
            return 'pending'

        job_status = calculate_job_status(activities_data)

                
        job_allocation_summary = {
            'total_activities': len(activities_data),
            'total_allocations': sum(a['allocation_counts']['total'] for a in activities_data),
            'pending_allocations': sum(a['allocation_counts']['pending'] for a in activities_data),
            'in_progress_allocations': sum(a['allocation_counts']['in_progress'] for a in activities_data),
            'completed_allocations': sum(a['allocation_counts']['completed'] for a in activities_data),
        }
        
        visits_data = job.get('visits', [])
        point_of_contact = visits_data[0].get('assigned_to') if visits_data and len(visits_data) > 0 else None
        
        random.seed(str(job_id))
        latitude = round(random.uniform(MH_LAT_MIN, MH_LAT_MAX), 6)
        longitude = round(random.uniform(MH_LON_MIN, MH_LON_MAX), 6)
        random.seed()

        enriched_job = {
            **job,
            'work_id': job_id,
            'farmer': farmer_details,
            'farmer_id': farmer_id,
            'activities': activities_data,
            'status': job_status,
            'allocation_summary': job_allocation_summary,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            'booking': job.get('booking', {}),
            'visits': visits_data,
            'point_of_contact': point_of_contact,
            'latitude': latitude,
            'longitude': longitude
        }

        enriched_jobs.append(enriched_job)

    # ========================================
    # STEP 7: ENRICH MISSING FARMER DATA
    # ========================================
    print(f"\n🔍 Checking for jobs with missing farmer data...")

    jobs_needing_farmer_fetch = []
    for job in enriched_jobs:
        if not job.get('farmer') or not job.get('farmer_id'):
            jobs_needing_farmer_fetch.append(job)

    if jobs_needing_farmer_fetch:
        print(f"   Found {len(jobs_needing_farmer_fetch)} jobs missing farmer data")
        print(f"   Fetching from job-details API...")
        
        from django.test.client import RequestFactory
        factory = RequestFactory()
        
        for job in jobs_needing_farmer_fetch:
            job_id = job.get('work_id') or job.get('id')
            
            try:
                # Call job-details API
                fake_request = factory.get(f'/ap/job-details/{job_id}/')
                fake_request.user = request.user
                
                details_response = get_job_details(fake_request, job_id)
                
                if details_response.status_code == 200:
                    details_data = details_response.data
                    
                    # Extract farmer info
                    if details_data.get('farmer'):
                        job['farmer'] = details_data['farmer']
                        job['farmer_id'] = details_data['farmer'].get('farmer_id', '')
                        print(f"   ✓ Enriched {job_id} with farmer: {details_data['farmer'].get('farmer_name')}")
            except Exception as e:
                print(f"   ✗ Failed to fetch farmer for {job_id}: {e}")
                continue

    print(f"✅ Farmer enrichment completed\n")

    # ========================================
    # STEP 7: FILTER BY CALCULATED STATUS (if provided)
    # ========================================
    if status_filter:
        print(f"🔍 Filtering by status: {status_filter}")
        
        status_filter_lower = status_filter.lower().replace('_', '').replace(' ', '')
        
        filtered_jobs = []
        for job in enriched_jobs:
            job_status_normalized = job['status'].lower().replace('_', '').replace(' ', '')
            
            if job_status_normalized == status_filter_lower:
                filtered_jobs.append(job)
        
        enriched_jobs = filtered_jobs
        print(f"✓ Found {len(enriched_jobs)} jobs with status '{status_filter}'\n")

    total_elapsed = time.time() - start_time
    print(f"\n✅ Jobs API completed in {total_elapsed:.2f}s")
    print(f"   Total jobs returned: {len(enriched_jobs)}")

    return Response(enriched_jobs)


from django.db.models import Q, Count, Sum, Min, Max
from datetime import datetime

# allocation_app/views.py

from django.db.models import Q, Count, Sum, Min, Max, Prefetch
from datetime import datetime
# # allocation_app/views.py


from django.db.models import Q, Count, Sum, Min, Max, Prefetch
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from django.db import models
from django.db.models import Min  # ✅ Add this import

from django.db.models import Min  # ✅ Add this import at top
from django.db.models import Min, Sum, Q
from decimal import Decimal
import time
# views.py
@api_view(['GET'])
@permission_classes([AllowAny])
def total_jobs_view(request):
    """
    Total jobs view with filters and payment summary
    SIMPLIFIED VERSION - Direct filtering on enriched data
    """
    
    import time
    start_time = time.time()
    
    # ========================================
    # GET FILTER PARAMETERS
    # ========================================
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    farmer_name = request.GET.get('farmer_name', '')
    mukkadam_name = request.GET.get('mukkadam_name', '')
    transporter_name = request.GET.get('transporter_name', '')
    payment_type = request.GET.get('payment_type', 'all')
    payment_status_filter = request.GET.get('payment_status', 'all')
    
    # ========================================
    # CALL EXISTING jobs_list API (NO FILTERS)
    # ========================================
    from django.test.client import RequestFactory
    factory = RequestFactory()
    
    # ✅ Don't pass any filters to jobs_list - let it return everything
    fake_request = factory.get('/ap/jobs/')
    fake_request.user = request.user
    fake_request.GET = {}  # Empty GET params
    
    jobs_response = jobs_list(fake_request)
    
    if jobs_response.status_code != 200:
        return Response({'error': 'Failed to fetch jobs'}, status=500)
    
    all_jobs = jobs_response.data if isinstance(jobs_response.data, list) else []
    
    # ========================================
    # MARK JOBS AS FULLY LOST
    # ========================================
    for job in all_jobs:
        activities = job.get('activities', [])
        if activities:
            all_lost = all(activity.get('is_lost', False) for activity in activities)
            job['is_fully_lost'] = all_lost
            if all_lost:
                job['status'] = 'fully_lost'
        else:
            job['is_fully_lost'] = False
    
    # ========================================
    # APPLY ALL FILTERS
    # ========================================
    filtered_jobs = all_jobs
    
    # 1. STATUS FILTER
    if status_filter != 'all':
        temp = []
        for j in filtered_jobs:
            if status_filter == 'fully_lost':
                if j.get('is_fully_lost', False):
                    temp.append(j)
            else:
                if not j.get('is_fully_lost', False) and j.get('status', '').lower() == status_filter.lower():
                    temp.append(j)
        filtered_jobs = temp
    
    # 2. SEARCH FILTER (Job ID or Farmer Name)
    if search_query:
        search_lower = search_query.lower()
        temp = []
        for j in filtered_jobs:
            # Check work_id
            if search_lower in str(j.get('work_id', '')).lower():
                temp.append(j)
                continue
            # Check farmer_id
            if search_lower in str(j.get('farmer_id', '')).lower():
                temp.append(j)
                continue
            # Check farmer name
            farmer = j.get('farmer')
            if farmer:
                farmer_name_val = farmer.get('farmer_name', '')
                if farmer_name_val and search_lower in str(farmer_name_val).lower():
                    temp.append(j)
        filtered_jobs = temp
    
    # 3. DATE RANGE FILTER
    if date_from or date_to:
        from datetime import datetime
        
        def parse_date(date_str):
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return None
        
        from_dt = parse_date(date_from) if date_from else None
        to_dt = parse_date(date_to) if date_to else None
        
        temp = []
        for job in filtered_jobs:
            activities = job.get('activities', [])
            matched = False
            
            for activity in activities:
                sched = activity.get('scheduled_date', '')
                if not sched:
                    continue
                
                sched_dt = parse_date(sched.split('T')[0] if 'T' in sched else sched)
                if not sched_dt:
                    continue
                
                if from_dt and sched_dt < from_dt:
                    continue
                if to_dt and sched_dt > to_dt:
                    continue
                
                matched = True
                break
            
            if matched:
                temp.append(job)
        
        filtered_jobs = temp
    
    # 4. FARMER NAME FILTER
    if farmer_name:
        farmer_lower = farmer_name.lower()
        temp = []
        for j in filtered_jobs:
            farmer = j.get('farmer')
            if farmer:
                fname = farmer.get('farmer_name', '')
                if fname and farmer_lower in str(fname).lower():
                    temp.append(j)
        filtered_jobs = temp
    
    # 5. MUKKADAM NAME FILTER
    if mukkadam_name:
        mukkadam_lower = mukkadam_name.lower()
        temp = []
        for job in filtered_jobs:
            found = False
            for activity in job.get('activities', []):
                for alloc in activity.get('allocations', []):
                    mname = alloc.get('mukkadam_name', '')
                    if mname and mukkadam_lower in str(mname).lower():
                        found = True
                        break
                if found:
                    break
            if found:
                temp.append(job)
        filtered_jobs = temp
    
    # 6. TRANSPORTER NAME FILTER
    if transporter_name:
        transporter_lower = transporter_name.lower()
        temp = []
        for job in filtered_jobs:
            found = False
            for activity in job.get('activities', []):
                for alloc in activity.get('allocations', []):
                    tname = alloc.get('transporter_name', '')
                    if tname and transporter_lower in str(tname).lower():
                        found = True
                        break
                if found:
                    break
            if found:
                temp.append(job)
        filtered_jobs = temp
    
    # 7. PAYMENT TYPE FILTER
    if payment_type != 'all':
        temp = []
        for job in filtered_jobs:
            found = False
            for activity in job.get('activities', []):
                if payment_type == 'farmer':
                    fp = activity.get('farmer_payments')
                    if fp and fp.get('payment_count', 0) > 0:
                        found = True
                        break
                elif payment_type == 'mukkadam':
                    for alloc in activity.get('allocations', []):
                        if alloc.get('payment_request'):
                            found = True
                            break
                elif payment_type == 'transport':
                    for alloc in activity.get('allocations', []):
                        if alloc.get('transport_payment_request'):
                            found = True
                            break
                if found:
                    break
            if found:
                temp.append(job)
        filtered_jobs = temp
    
    # 8. PAYMENT STATUS FILTER
    if payment_status_filter != 'all':
        temp = []
        for job in filtered_jobs:
            found = False
            for activity in job.get('activities', []):
                # Check farmer payments
                fp = activity.get('farmer_payments')
                if fp and fp.get('payments'):
                    for payment in fp['payments']:
                        if payment.get('payment_status') == payment_status_filter:
                            found = True
                            break
                
                if found:
                    break
                
                # Check mukkadam/transport payments
                for alloc in activity.get('allocations', []):
                    pr = alloc.get('payment_request')
                    if pr and pr.get('status') == payment_status_filter:
                        found = True
                        break
                    
                    tpr = alloc.get('transport_payment_request')
                    if tpr and tpr.get('status') == payment_status_filter:
                        found = True
                        break
                
                if found:
                    break
            
            if found:
                temp.append(job)
        filtered_jobs = temp
    
    # ========================================
    # CALCULATE STATS FROM FILTERED JOBS
    # ========================================
    stats = {
        'total': len(filtered_jobs),
        'pending': 0,
        'partial': 0,
        'allocated': 0,
        'completed': 0,
        'lost': 0,
    }
    
    for job in filtered_jobs:
        if job.get('is_fully_lost', False):
            stats['lost'] += 1
        else:
            status = job.get('status', 'pending').lower()
            if status == 'completed':
                stats['completed'] += 1
            elif 'partial' in status:
                stats['partial'] += 1
            elif 'allocated' in status:
                stats['allocated'] += 1
            else:
                stats['pending'] += 1
    
    # ========================================
    # CALCULATE PAYMENT SUMMARY
    # ========================================
    payment_summary = {
        'total_revenue': 0,
        'total_cost': 0,
        'total_profit': 0,
        'farmer_payments_expected': 0,
        'farmer_payments_paid': 0,
        'farmer_payments_pending': 0,
        'mukkadam_payments_expected': 0,
        'mukkadam_payments_paid': 0,
        'mukkadam_payments_pending': 0,
        'transport_payments_expected': 0,
        'transport_payments_paid': 0,
        'transport_payments_pending': 0,
    }
    
    for job in filtered_jobs:
        for activity in job.get('activities', []):
            if activity.get('is_lost', False):
                continue
            
            # Revenue
            payment_summary['total_revenue'] += float(activity.get('subtotal', 0))
            
            # Farmer payments
            fp = activity.get('farmer_payments')
            if fp:
                payment_summary['farmer_payments_expected'] += float(fp.get('total_expected', 0))
                payment_summary['farmer_payments_paid'] += float(fp.get('total_paid', 0))
                payment_summary['farmer_payments_pending'] += float(fp.get('total_pending', 0))
            
            # Mukkadam and Transport costs
            for alloc in activity.get('allocations', []):
                mukkadam_price = float(alloc.get('mukkadam_price', 0))
                transport_price = float(alloc.get('transport_price', 0))
                
                payment_summary['total_cost'] += mukkadam_price + transport_price
                
                # Mukkadam payment status
                pr = alloc.get('payment_request')
                if pr:
                    amount = float(pr.get('requested_amount', 0))
                    payment_summary['mukkadam_payments_expected'] += amount
                    if pr.get('status') == 'paid':
                        payment_summary['mukkadam_payments_paid'] += amount
                    elif pr.get('status') == 'pending':
                        payment_summary['mukkadam_payments_pending'] += amount
                
                # Transport payment status
                tpr = alloc.get('transport_payment_request')
                if tpr:
                    amount = float(tpr.get('requested_amount', 0))
                    payment_summary['transport_payments_expected'] += amount
                    if tpr.get('status') == 'paid':
                        payment_summary['transport_payments_paid'] += amount
                    elif tpr.get('status') == 'pending':
                        payment_summary['transport_payments_pending'] += amount
    
    payment_summary['total_profit'] = payment_summary['total_revenue'] - payment_summary['total_cost']
    
    elapsed = time.time() - start_time
    
    return Response({
        'success': True,
        'stats': stats,
        'count': len(filtered_jobs),
        'jobs': filtered_jobs,
        'payment_summary': payment_summary,
        'performance': {
            'query_time': f'{elapsed:.2f}s',
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def financial_breakdown_detail(request):
    """
    Get detailed breakdown for financial metrics
    Type: revenue, farmer_payments, mukkadam, transport, profitable, loss, low_margin
    ✅ REVENUE: Uses JobActivity.subtotal and excludes lost activities
    """
    breakdown_type = request.GET.get('type')
    
    if not breakdown_type:
        return Response({'error': 'type parameter required'}, status=400)
    
    from decimal import Decimal
    from django.db.models import Sum, Q, F
    from django.db.models.functions import Coalesce
    
    result = {
        'type': breakdown_type,
        'title': '',
        'items': [],
        'summary': {},
        'count': 0
    }
    
    # ========================================
    # 1. REVENUE BREAKDOWN (CORRECTED)
    # ========================================
    if breakdown_type == 'revenue':
        result['title'] = 'Revenue Breakdown by Job (from Activity Subtotals)'
        
        # ✅ Get all NON-LOST JobActivities grouped by job_id
        activities = JobActivity.objects.exclude(
            lost_record__is_active=True  # ✅ Exclude lost activities
        ).select_related('lost_record').order_by('job_id', 'activity_name')
        
        job_revenue = {}
        for activity in activities:
            job_id = activity.job_id
            
            if job_id not in job_revenue:
                job_revenue[job_id] = {
                    'job_id': job_id,
                    'total_revenue': Decimal('0'),
                    'activities_count': 0,
                    'activities': []
                }
            
            # ✅ Use subtotal (which is total_price + transport_cost + other_cost)
            activity_revenue = activity.subtotal or Decimal('0')
            
            job_revenue[job_id]['total_revenue'] += activity_revenue
            job_revenue[job_id]['activities_count'] += 1
            job_revenue[job_id]['activities'].append({
                'activity_name': activity.activity_name,
                'activity_id': activity.activity_id,
                'area': float(activity.total_area),
                'total_price': float(activity.total_price),
                'transport_cost': float(activity.transport_cost),
                'other_cost': float(activity.other_cost),
                'subtotal': float(activity_revenue),
                'scheduled_date': str(activity.scheduled_datetime.date()) if activity.scheduled_datetime else None,
                'rate_per_acre': float(activity.rate_per_acre),
                'is_lost': False,
            })
        
        result['items'] = sorted(
            job_revenue.values(),
            key=lambda x: x['total_revenue'],
            reverse=True
        )
        
        # Convert Decimal to float for JSON serialization
        total_revenue_sum = Decimal('0')
        for item in result['items']:
            item['total_revenue'] = float(item['total_revenue'])
            total_revenue_sum += Decimal(str(item['total_revenue']))
        
        result['summary'] = {
            'total_revenue': float(total_revenue_sum),
            'total_jobs': len(result['items']),
            'total_activities': sum(item['activities_count'] for item in result['items']),
        }
    
    # ========================================
    # 2. FARMER PAYMENTS BREAKDOWN
    # ========================================
    elif breakdown_type == 'farmer_payments':
        result['title'] = 'Farmer Payments Breakdown'
        
        payments = FarmerPayment.objects.select_related(
            'imported_farmer',
            'job_activity'
        ).order_by('-activity_date')
        
        for payment in payments:
            result['items'].append({
                'id': payment.id,
                'farmer_id': payment.imported_farmer.external_farmer_id if payment.imported_farmer else None,
                'farmer_name': payment.farmer_name,
                'job_id': payment.job_activity.job_id if payment.job_activity else 'N/A',
                'activity_name': payment.activity_name,
                'activity_date': str(payment.activity_date),
                'village': payment.village,
                'acres': payment.acres,
                'booking_value': float(payment.booking_value),
                'transport_cost': float(payment.transportation_cost or 0),
                'total_value': float(payment.total_value or payment.booking_value),
                'payment_status': payment.payment_status,
                'payment_route': payment.payment_route,
                'date_of_payment': str(payment.date_of_payment) if payment.date_of_payment else None,
                'reference_no': payment.reference_no,
                'description': payment.description,
            })
        
        result['summary'] = {
            'total_expected': float(payments.aggregate(total=Coalesce(Sum('total_value'), Decimal('0')))['total']),
            'total_paid': float(payments.filter(payment_status='paid').aggregate(total=Coalesce(Sum('total_value'), Decimal('0')))['total']),
            'total_pending': float(payments.filter(payment_status='pending').aggregate(total=Coalesce(Sum('total_value'), Decimal('0')))['total']),
            'total_count': payments.count(),
            'paid_count': payments.filter(payment_status='paid').count(),
            'pending_count': payments.filter(payment_status='pending').count(),
        }
    
    # ========================================
    # 3. MUKKADAM PAYMENTS BREAKDOWN
    # ========================================
    elif breakdown_type == 'mukkadam':
        result['title'] = 'Mukkadam Payments Breakdown'
        
        payment_requests = PaymentRequest.objects.select_related(
            'allocation__job_activity',
            'allocation__imported_mukkadam',
            'requested_by',
            'paid_by'
        ).order_by('-requested_at')
        
        for pr in payment_requests:
            alloc = pr.allocation
            result['items'].append({
                'id': pr.id,
                'allocation_id': alloc.id,
                'job_id': alloc.job_activity.job_id if alloc.job_activity else None,
                'activity_name': alloc.job_activity.activity_name if alloc.job_activity else 'N/A',
                'mukkadam_id': pr.mukkadam_id,
                'mukkadam_name': alloc.imported_mukkadam.team_name if alloc.imported_mukkadam else f'Mukkadam #{pr.mukkadam_id}',
                'mukkadam_contact': alloc.imported_mukkadam.contact_no if alloc.imported_mukkadam else 'N/A',
                'work_date': str(alloc.work_date),
                'allocated_area': float(alloc.allocated_area),
                'crew_size': alloc.crew_size,
                'requested_amount': float(pr.requested_amount),
                'status': pr.status,
                'requested_at': pr.requested_at.isoformat(),
                'requested_by': pr.requested_by.username if pr.requested_by else 'System',
                'paid_at': pr.paid_at.isoformat() if pr.paid_at else None,
                'paid_by': pr.paid_by.username if pr.paid_by else None,
                'notes': pr.notes,
            })
        
        result['summary'] = {
            'total_requested': float(payment_requests.aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_paid': float(payment_requests.filter(status='paid').aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_pending': float(payment_requests.filter(status='pending').aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_count': payment_requests.count(),
            'paid_count': payment_requests.filter(status='paid').count(),
            'pending_count': payment_requests.filter(status='pending').count(),
        }
    
    # ========================================
    # 4. TRANSPORT PAYMENTS BREAKDOWN
    # ========================================
    elif breakdown_type == 'transport':
        result['title'] = 'Transport Payments Breakdown'
        
        transport_requests = TransportPaymentRequest.objects.select_related(
            'allocation__job_activity',
            'allocation__imported_transporter',
            'requested_by',
            'paid_by'
        ).order_by('-requested_at')
        
        for tr in transport_requests:
            alloc = tr.allocation
            result['items'].append({
                'id': tr.id,
                'allocation_id': alloc.id,
                'job_id': alloc.job_activity.job_id if alloc.job_activity else None,
                'activity_name': alloc.job_activity.activity_name if alloc.job_activity else 'N/A',
                'transport_provider_id': tr.transport_provider_id,
                'transporter_name': alloc.imported_transporter.name if alloc.imported_transporter else f'Transporter #{tr.transport_provider_id}',
                'transporter_contact': alloc.imported_transporter.contact_no if alloc.imported_transporter else 'N/A',
                'transport_type': alloc.transport_type,
                'work_date': str(alloc.work_date),
                'allocated_area': float(alloc.allocated_area),
                'requested_amount': float(tr.requested_amount),
                'status': tr.status,
                'requested_at': tr.requested_at.isoformat(),
                'requested_by': tr.requested_by.username if tr.requested_by else 'System',
                'paid_at': tr.paid_at.isoformat() if tr.paid_at else None,
                'paid_by': tr.paid_by.username if tr.paid_by else None,
                'notes': tr.notes,
            })
        
        result['summary'] = {
            'total_requested': float(transport_requests.aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_paid': float(transport_requests.filter(status='paid').aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_pending': float(transport_requests.filter(status='pending').aggregate(total=Coalesce(Sum('requested_amount'), Decimal('0')))['total']),
            'total_count': transport_requests.count(),
            'paid_count': transport_requests.filter(status='paid').count(),
            'pending_count': transport_requests.filter(status='pending').count(),
        }
    
    # ========================================
    # 5. PROFITABLE ALLOCATIONS
    # ========================================
    elif breakdown_type == 'profitable':
        result['title'] = 'Profitable Allocations'
        
        allocations = Allocation.objects.select_related(
            'job_activity',
            'imported_mukkadam',
            'imported_transporter'
        ).filter(
            job_activity__isnull=False
        ).exclude(
            job_activity__lost_record__is_active=True  # ✅ Exclude lost
        )
        
        for alloc in allocations:
            # ✅ Use subtotal for revenue
            revenue = alloc.job_activity.subtotal or Decimal('0')
            cost = alloc.total_cost
            profit = revenue - cost
            
            if profit > 0:
                result['items'].append({
                    'allocation_id': alloc.id,
                    'job_id': alloc.job_activity.job_id,
                    'activity_name': alloc.job_activity.activity_name,
                    'work_date': str(alloc.work_date),
                    'mukkadam_name': alloc.imported_mukkadam.team_name if alloc.imported_mukkadam else f'#{alloc.mukkadam_id}',
                    'transporter_name': alloc.imported_transporter.name if alloc.imported_transporter else 'Own/None',
                    'allocated_area': float(alloc.allocated_area),
                    'revenue': float(revenue),
                    'mukkadam_cost': float(alloc.mukkadam_price),
                    'transport_cost': float(alloc.transport_price or 0),
                    'total_cost': float(cost),
                    'profit': float(profit),
                    'profit_margin': round((float(profit) / float(revenue) * 100), 1) if revenue > 0 else 0,
                    'status': alloc.status,
                })
        
        result['items'].sort(key=lambda x: x['profit'], reverse=True)
        
        result['summary'] = {
            'total_revenue': sum(item['revenue'] for item in result['items']),
            'total_cost': sum(item['total_cost'] for item in result['items']),
            'total_profit': sum(item['profit'] for item in result['items']),
        }
    
    # ========================================
    # 6. LOSS-MAKING ALLOCATIONS
    # ========================================
    elif breakdown_type == 'loss':
        result['title'] = 'Loss-Making Allocations'
        
        allocations = Allocation.objects.select_related(
            'job_activity',
            'imported_mukkadam',
            'imported_transporter'
        ).filter(
            job_activity__isnull=False
        ).exclude(
            job_activity__lost_record__is_active=True  # ✅ Exclude lost
        )
        
        for alloc in allocations:
            # ✅ Use subtotal for revenue
            revenue = alloc.job_activity.subtotal or Decimal('0')
            cost = alloc.total_cost
            loss = revenue - cost
            
            if loss < 0:
                result['items'].append({
                    'allocation_id': alloc.id,
                    'job_id': alloc.job_activity.job_id,
                    'activity_name': alloc.job_activity.activity_name,
                    'work_date': str(alloc.work_date),
                    'mukkadam_name': alloc.imported_mukkadam.team_name if alloc.imported_mukkadam else f'#{alloc.mukkadam_id}',
                    'transporter_name': alloc.imported_transporter.name if alloc.imported_transporter else 'Own/None',
                    'allocated_area': float(alloc.allocated_area),
                    'revenue': float(revenue),
                    'mukkadam_cost': float(alloc.mukkadam_price),
                    'transport_cost': float(alloc.transport_price or 0),
                    'total_cost': float(cost),
                    'loss': float(abs(loss)),
                    'loss_margin': round((float(abs(loss)) / float(revenue) * 100), 1) if revenue > 0 else 0,
                    'status': alloc.status,
                })
        
        result['items'].sort(key=lambda x: x['loss'], reverse=True)
        
        result['summary'] = {
            'total_revenue': sum(item['revenue'] for item in result['items']),
            'total_cost': sum(item['total_cost'] for item in result['items']),
            'total_loss': sum(item['loss'] for item in result['items']),
        }
    
    # ========================================
    # 7. LOW MARGIN ALLOCATIONS
    # ========================================
    elif breakdown_type == 'low_margin':
        result['title'] = 'Low Margin Allocations (0-10% profit)'
        
        allocations = Allocation.objects.select_related(
            'job_activity',
            'imported_mukkadam',
            'imported_transporter'
        ).filter(
            job_activity__isnull=False
        ).exclude(
            job_activity__lost_record__is_active=True  # ✅ Exclude lost
        )
        
        for alloc in allocations:
            # ✅ Use subtotal for revenue
            revenue = alloc.job_activity.subtotal or Decimal('0')
            cost = alloc.total_cost
            profit = revenue - cost
            profit_margin = (float(profit) / float(revenue) * 100) if revenue > 0 else 0
            
            if 0 < profit_margin < 10:
                result['items'].append({
                    'allocation_id': alloc.id,
                    'job_id': alloc.job_activity.job_id,
                    'activity_name': alloc.job_activity.activity_name,
                    'work_date': str(alloc.work_date),
                    'mukkadam_name': alloc.imported_mukkadam.team_name if alloc.imported_mukkadam else f'#{alloc.mukkadam_id}',
                    'transporter_name': alloc.imported_transporter.name if alloc.imported_transporter else 'Own/None',
                    'allocated_area': float(alloc.allocated_area),
                    'revenue': float(revenue),
                    'mukkadam_cost': float(alloc.mukkadam_price),
                    'transport_cost': float(alloc.transport_price or 0),
                    'total_cost': float(cost),
                    'profit': float(profit),
                    'profit_margin': round(profit_margin, 1),
                    'status': alloc.status,
                })
        
        result['items'].sort(key=lambda x: x['profit_margin'])
        
        result['summary'] = {
            'total_revenue': sum(item['revenue'] for item in result['items']),
            'total_cost': sum(item['total_cost'] for item in result['items']),
            'total_profit': sum(item['profit'] for item in result['items']),
            'avg_margin': round(sum(item['profit_margin'] for item in result['items']) / len(result['items']), 1) if result['items'] else 0,
        }
    
    else:
        return Response({'error': 'Invalid type'}, status=400)
    
    result['count'] = len(result['items'])
    return Response(result)


from .utils import batch_fetch_mukkadams, batch_fetch_farmers, batch_fetch_transport_providers
# allocation_app/views.py
# Add this new endpoint to your views.py file

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import requests

EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'

@api_view(['PATCH'])
@permission_classes([AllowAny])
def update_activity(request):
    """
    Forward activity update to external ops API
    
    Expected payload:
    {
        "job_id": "616",
        "activity_id": "183",
        "updates": {
            "activity_name": "Finger Thinning",
            "acres": 2.5,
            "date_time": "2026-01-15T10:00:00",
            "total_price": 5000.0
        }
    }
    """
    try:
        # Get data from request
        job_id = request.data.get('job_id')
        activity_id = request.data.get('activity_id')
        updates = request.data.get('updates', {})
        
        # Validate required fields
        if not job_id or not activity_id:
            return Response(
                {'error': 'job_id and activity_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not updates:
            return Response(
                {'error': 'No updates provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare payload for ops API
        payload = {
            'job_id': job_id,
            'activity_id': activity_id,
            'updates': updates
        }
        
        # Forward to ops API
        # TODO: Replace with actual endpoint URL from ops team
        ops_update_url = f'{EXTERNAL_API_URL}/update_activity/'
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        
        print(f"\n📤 Forwarding activity update to ops API...")
        print(f"   Job ID: {job_id}")
        print(f"   Activity ID: {activity_id}")
        print(f"   Updates: {updates}")
        
        response = requests.patch(
            ops_update_url,
            json=payload,
            headers={
                'Authorization': token,
                'Content-Type': 'application/json'
            },
            timeout=300
        )
        
        response.raise_for_status()
        
        print(f"✅ Update successful: {response.status_code}")
        
        return Response({
            'success': True,
            'message': 'Activity updated successfully',
            'data': response.json() if response.text else {}
        }, status=status.HTTP_200_OK)
        
    except requests.exceptions.HTTPError as e:
        error_detail = str(e)
        try:
            error_detail = e.response.json()
        except:
            pass
            
        return Response({
            'success': False,
            'error': f'Ops API error: {error_detail}'
        }, status=status.HTTP_502_BAD_GATEWAY)
        
    except requests.exceptions.RequestException as e:
        return Response({
            'success': False,
            'error': f'Failed to connect to ops API: {str(e)}'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def allocations_list(request):
    """
    Get all allocations with complete details from external APIs
    OPTIMIZED with caching + async
    ✅ Returns simplified structure matching the required format
    """
    import time
    start_time = time.time()

    # Get query parameters
    mukkadam_phone = request.GET.get('mukkadam_phone')
    work_date = request.GET.get('work_date')
    allocation_status = request.GET.get('status')

    print(f"🔍 Filters: phone={mukkadam_phone}, date={work_date}, status={allocation_status}")

    # ========================================
    # STEP 1: GET ALLOCATIONS FROM DATABASE
    # ========================================
    allocations_query = Allocation.objects.all().select_related('job_activity')

    if work_date:
        allocations_query = allocations_query.filter(work_date=work_date)

    if allocation_status:
        allocations_query = allocations_query.filter(status=allocation_status)

    allocations = list(allocations_query.order_by('-allocated_at'))

    print(f"📊 Found {len(allocations)} allocations in database")

    if not allocations:
        return Response({'count': 0, 'allocations': []})

    # ========================================
    # STEP 2: FILTER BY MUKKADAM PHONE (via Supply API)
    # ========================================
    if mukkadam_phone:
        print(f"\n📱 Filtering by mukkadam phone: {mukkadam_phone}")

        try:
            mukkadam_response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/',
                params={'search': mukkadam_phone},
                timeout=500
            )

            if mukkadam_response.status_code == 200:
                mukkadams_data = mukkadam_response.json()

                if isinstance(mukkadams_data, list):
                    mukkadam_ids = [m['id'] for m in mukkadams_data if mukkadam_phone in m.get('mobile_numbers', '')]
                elif isinstance(mukkadams_data, dict) and 'results' in mukkadams_data:
                    mukkadam_ids = [m['id'] for m in mukkadams_data['results'] if mukkadam_phone in m.get('mobile_numbers', '')]
                else:
                    mukkadam_ids = []

                if not mukkadam_ids:
                    return Response({'count': 0, 'allocations': []})

                allocations = [a for a in allocations if a.mukkadam_id in mukkadam_ids]

        except Exception as e:
            return Response(
                {'error': f'Error filtering by phone: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ========================================
    # STEP 3: FETCH JOBS FROM EXTERNAL API
    # ========================================
    print("\n🔄 Fetching job details from external API...")

    job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)

    jobs_cache = {}
    EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
    job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'

    try:
        response = requests.get(
            f'{EXTERNAL_API_URL}/get_allocated_jobs/',
            headers={'Authorization': job_token},
            timeout=500
        )

        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', []) if isinstance(data, dict) else data

            for job in jobs_list:
                job_id = str(job.get('work_id') or job.get('id') or job.get('job_id'))
                if job_id in job_ids:
                    jobs_cache[job_id] = job
    except Exception as e:
        print(f"❌ Error fetching jobs: {str(e)}")

    # ========================================
    # STEP 4: COLLECT ALL UNIQUE IDs
    # ========================================
    farmer_ids = set()
    
    # ✅ Get farmer IDs from BOTH sources
    # 1. From API jobs
    for job in jobs_cache.values():
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    # 2. From JobActivity.farmer_work_id (for imported records)
    for alloc in allocations:
        if alloc.job_activity and alloc.job_activity.farmer_work_id:
            farmer_ids.add(str(alloc.job_activity.farmer_work_id))

    mukkadam_ids = set(alloc.mukkadam_id for alloc in allocations)

    transport_provider_ids = set(
        alloc.transport_provider_id
        for alloc in allocations
        if alloc.transport_type == 'provider' and alloc.transport_provider_id
    )

    # ========================================
    # ✅ STEP 5: BATCH FETCH ALL DATA IN PARALLEL
    # ========================================
    print("\n⚡ PARALLEL BATCH FETCHING...")
    print(f"   Fetching {len(farmer_ids)} farmers, {len(mukkadam_ids)} mukkadams, {len(transport_provider_ids)} transporters")
    batch_start = time.time()

    # Fetch all data types in parallel
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)
    transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)

    batch_elapsed = time.time() - batch_start
    print(f"✅ Batch fetching completed in {batch_elapsed:.2f}s")

    # ========================================
    # STEP 6: BUILD SIMPLIFIED ALLOCATIONS (MATCHING REQUIRED FORMAT)
    # ========================================
    enriched_allocations = []
    total_area = Decimal('0')
    total_cost = Decimal('0')

    for allocation in allocations:
        job_activity = allocation.job_activity
        if not job_activity:
            continue

        job_id = str(job_activity.job_id)
        activity_id = str(job_activity.activity_id)

        # Get cached job data
        job_data = jobs_cache.get(job_id, {})
        
        # ✅ Get farmer ID with priority logic
        farmer_id = None
        if job_activity.farmer_work_id:
            # Priority 1: Use farmer_work_id from JobActivity
            farmer_id = str(job_activity.farmer_work_id)
        elif job_data.get('farmer_id'):
            # Priority 2: Use farmer_id from API job
            farmer_id = str(job_data.get('farmer_id'))
        
        # Get farmer details from cache
        farmer_data = farmers_cache.get(farmer_id) if farmer_id else None
        
        # Get mukkadam data
        mukkadam_data = mukkadams_cache.get(allocation.mukkadam_id, {})

        # Get transport provider data
        transport_provider_data = None
        if allocation.transport_type == 'provider' and allocation.transport_provider_id:
            transport_provider_data = transport_providers_cache.get(allocation.transport_provider_id)

        # Get activity details
        activity_details = None
        if job_data and 'activities' in job_data:
            activity_details = next(
                (a for a in job_data.get('activities', [])
                if str(a.get('activity_id') or a.get('id')) == activity_id),
                None
            )

        # Central team contact
        central_team_phone = "+91-804-7361465"

        # Calculate costs
        mukkadam_price = float(allocation.mukkadam_price) if allocation.mukkadam_price else 0.0
        transport_price = float(allocation.transport_price) if allocation.transport_price else 0.0
        total_cost_alloc = mukkadam_price + transport_price

        # ✅ BUILD SIMPLIFIED STRUCTURE MATCHING REQUIRED FORMAT
        enriched_allocation = {
            'allocation_id': allocation.id,
            'farmer_id': farmer_id,
            
            # ✅ Farmer object with simplified structure
            'farmer': {
                'farmer_id': farmer_id,
                'farmer_name': farmer_data.get('farmer_name', 'N/A') if farmer_data else 'N/A',
                'phone_number': farmer_data.get('phone_number', 'N/A') if farmer_data else 'N/A',
                'location': farmer_data.get('location', 'N/A') if farmer_data else 'N/A',
            } if farmer_data else None,
            
            # ✅ Job object
            'job': {
                'job_id': job_id,
                'job_name': job_data.get('job_name', 'N/A'),
                'scheduled_date': job_data.get('scheduled_date', 'N/A'),
                'location': job_data.get('location', 'N/A'),
                'central_team_phone': central_team_phone,
            },
            
            # ✅ Activity object
            'activity': {
                'activity_id': activity_id,
                'activity_name': activity_details.get('activity_name', 'Unknown') if activity_details else 'Unknown',
                'activity_type': activity_details.get('activity_type', 'N/A') if activity_details else 'N/A',
                'total_area': float(activity_details.get('acres', 0)) if activity_details else 0,
                'scheduled_date': activity_details.get('scheduled_date', 'N/A') if activity_details else 'N/A',
                'scheduled_time': activity_details.get('scheduled_time', 'N/A') if activity_details else 'N/A',
            },
            
            # ✅ Direct fields (matching required format)
            'mukkadam_id': allocation.mukkadam_id,
            'allocated_area': float(allocation.allocated_area),
            'work_date': str(allocation.work_date) if allocation.work_date else None,
            'mukkadam_price': mukkadam_price,
            'transport_type': allocation.transport_type,
            'transport_provider_id': allocation.transport_provider_id if allocation.transport_type == 'provider' else None,
            'transport_price': transport_price,
            'status': allocation.status,
            
            # ✅ Additional useful fields
            'crew_size': allocation.crew_size,
            'notes': allocation.notes,
            'allocated_at': allocation.allocated_at.isoformat() if allocation.allocated_at else None,
            'completed_at': allocation.completed_at.isoformat() if allocation.completed_at else None,
            
            # ✅ Mukkadam details (nested for frontend convenience)
            'mukkadam': mukkadam_data,
            
            # ✅ Transport provider details (nested for frontend convenience)
            'transport_provider': transport_provider_data,
        }

        enriched_allocations.append(enriched_allocation)
        total_area += allocation.allocated_area
        total_cost += Decimal(str(total_cost_alloc))

    # Summary
    summary = {
        'total_allocations': len(allocations),
        'total_area_allocated': float(total_area),
        'total_cost': float(total_cost),
        'active_allocations': len([a for a in allocations if a.status == 'allocated']),
        'completed_allocations': len([a for a in allocations if a.status == 'completed']),
        'in_progress_allocations': len([a for a in allocations if a.status == 'in_progress']),
    }

    total_elapsed = time.time() - start_time
    print(f"\n✅ API completed in {total_elapsed:.2f}s")
    print("="*80)

    return Response({
        'count': len(enriched_allocations),
        'allocations': enriched_allocations,
        'summary': summary,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s'
        }
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def transporter_work_history(request):
    """
    Get complete work history and analytics for a Transporter
    """
    print("="*80)
    print("🚚 FETCHING TRANSPORTER WORK HISTORY & ANALYTICS")
    print("="*80)

    mobile_number = request.GET.get('mobile_number')
    provider_id = request.GET.get('transport_provider_id')

    if not mobile_number and not provider_id:
        return Response(
            {'error': 'Either mobile_number or transport_provider_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ========================================
    # STEP 1: GET TRANSPORTER DETAILS FROM SUPPLY API
    # ========================================
    provider_data = None

    try:
        if provider_id:
            # Fetch by ID
            print(f"   🔍 Fetching by ID: {provider_id}")
            response = requests.get(
                f'{SUPPLY_API_URL}/api/transport-providers/{provider_id}/',
                timeout=500
            )
            if response.status_code == 200:
                provider_data = response.json()
                provider_id = int(provider_id)
            else:
                print(f"   ❌ Supply API Error (ID): {response.status_code} - {response.text}")

        else:
            # Search by phone using check-transporter
            print(f"   🔍 Searching for transporter with mobile: {mobile_number}")
            check_url = f'{SUPPLY_API_URL}/api/check-transporter/'

            print(f"   📡 POST Request to: {check_url}")
            response = requests.post(
                check_url,
                json={'contact_number': mobile_number}, # Send data in body
                timeout=500
            )

            print(f"   📊 Response Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('registered'):
                    # Extract data
                    provider_data = result.get('data')
                    provider_id = result.get('transporter_id')
                    print(f"   ✅ Found transporter ID: {provider_id}")
                else:
                    print(f"   ⚠️ Transporter not registered: {result.get('message')}")
            else:
                # IMPORTANT: This prints why it failed (e.g., 404 URL not found, 500 Server Error)
                print(f"   ❌ Supply API Failed: {response.status_code}")
                print(f"   📄 Response Body: {response.text}")

        if not provider_data:
            return Response(
                {'error': 'Transporter not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        print(f"   ❌ Error fetching transporter: {str(e)}")
        return Response(
            {'error': f'Failed to fetch transporter details: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ... (Rest of Step 2, 3, 4, 5 remains exactly the same) ...

    # ========================================
    # STEP 2: GET ALLOCATIONS FOR THIS TRANSPORTER
    # ========================================
    allocations = Allocation.objects.filter(
        transport_provider_id=provider_id
    ).select_related('job_activity', 'transport_payment_request').order_by('-work_date')

    # ========================================
    # STEP 3: BATCH FETCH JOB & MUKKADAM DETAILS
    # ========================================
    # Collect IDs for batch fetching
    job_ids = set()
    mukkadam_ids = set()

    for alloc in allocations:
        if alloc.job_activity:
            job_ids.add(str(alloc.job_activity.job_id))
        mukkadam_ids.add(alloc.mukkadam_id)

    # --- A. Fetch Jobs ---
    jobs_cache = {}
    farmers_cache = {}

    try:
        EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
        job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'

        response = requests.get(
            f'{EXTERNAL_API_URL}/get_allocated_jobs/',
            headers={'Authorization': job_token},
            timeout=500
        )

        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', []) if isinstance(data, dict) else data

            for job in jobs_list:
                jid = str(job.get('work_id') or job.get('id'))
                if jid in job_ids:
                    jobs_cache[jid] = job

            FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
            farmer_token = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'

            farmer_ids = set(j.get('farmer_id') for j in jobs_cache.values() if j.get('farmer_id'))

            for fid in farmer_ids:
                try:
                    f_resp = requests.get(
                        f'{FARMER_API_BASE}/get_farmer_details/{fid}/',
                        headers={'Authorization': farmer_token},
                        timeout=500
                    )
                    if f_resp.status_code == 200:
                        print(f"   ✅ Fetched farmer ID: {fid}")
                        farmers_cache[str(fid)] = f_resp.json()
                except:
                    pass
    except Exception as e:
        print(f"   ⚠️ Error fetching external job data: {e}")

    # --- B. Fetch Mukkadams (Who they need to contact) ---
    mukkadams_cache = {}
    try:
        for mid in mukkadam_ids:
            m_resp = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/{mid}/',
                timeout=500
            )
            if m_resp.status_code == 200:
                mukkadams_cache[mid] = m_resp.json()
    except Exception as e:
        print(f"   ⚠️ Error fetching mukkadams: {e}")

    # ========================================
    # STEP 4: BUILD RESPONSE DATA
    # ========================================
    from datetime import date
    today = date.today()

    completed_jobs = []
    upcoming_jobs = []

    total_earnings = 0
    pending_payout = 0

    for alloc in allocations:
        # Get related data from caches
        job_id = str(alloc.job_activity.job_id)
        job_data = jobs_cache.get(job_id, {})

        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})

        mukkadam_data = mukkadams_cache.get(alloc.mukkadam_id, {})

        # Payment Status Logic
        payment_status = 'pending_work' # Default
        transport_amount = float(alloc.transport_price or 0)

        # Check explicit payment request
        if hasattr(alloc, 'transport_payment_request'):
            req = alloc.transport_payment_request
            payment_status = req.status # 'pending', 'paid', 'rejected'

            if payment_status == 'paid':
                total_earnings += float(req.requested_amount)
            elif payment_status == 'pending':
                pending_payout += float(req.requested_amount)

        elif alloc.status == 'completed' or (alloc.work_date and alloc.work_date < today):
             payment_status = 'unclaimed'
             pending_payout += transport_amount

        # Build Job Object
        job_obj = {
            'allocation_id': alloc.id,
            'work_date': str(alloc.work_date),
            'status': alloc.status, # 'allocated', 'completed'
            'payment_status': payment_status,
            'amount': transport_amount,

            # Job / Location Info (Where to go)
            'job': {
                'id': job_id,
                'location': job_data.get('location') or farmer_data.get('village', 'Unknown'),
                'farmer_name': farmer_data.get('farmer_name', 'Unknown Farmer'),
                'farmer_mobile': farmer_data.get('phone_number', 'N/A'),
                'location': job_data.get('location') or farmer_data.get('village') or 'Unknown',
            },

            # Contact Person (Mukkadam)
            'contact_person': {
                'role': 'Mukkadam',
                'name': mukkadam_data.get('mukkadam_name', f'Mukkadam #{alloc.mukkadam_id}'),
                'mobile': mukkadam_data.get('mobile_numbers', 'N/A'),
                'crew_size': alloc.crew_size or mukkadam_data.get('crew_size', 0)
            }
        }

        # Categorize
        if alloc.status == 'completed' or (alloc.work_date and alloc.work_date < today):
            completed_jobs.append(job_obj)
        else:
            upcoming_jobs.append(job_obj)

    # ========================================
    # STEP 5: FINAL RESPONSE
    # ========================================
    return Response({
        'transporter': {
            'id': provider_data.get('id'),
            'name': provider_data.get('name'),
            'mobile': provider_data.get('contact_number'),
            'vehicle': provider_data.get('vehicle_type'),
            'base_location': provider_data.get('base_location'),
            'central_team_phone': "+91-804-7361465"
        },
        'stats': {
            'total_trips': len(allocations),
            'completed_trips': len(completed_jobs),
            'upcoming_trips': len(upcoming_jobs),
            'total_earnings': total_earnings,
            'pending_payout': pending_payout
        },
        'upcoming_jobs': upcoming_jobs,
        'history': completed_jobs
    })

# allocation_app/views.py
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count, Sum
from datetime import datetime, date
from decimal import Decimal

from .models import Allocation, JobActivity, PaymentRequest


# ALLOCATION_API_BASE = 'http://localhost:8001'  # ← Change to your actual allocation API URL
# ALLOCATION_API_BASE = 'https://allocation.bharatintelligence.ai'
# SUPPLY_API_URL = getattr(settings, 'ALLOCATION_API_URL')

def get_supply_users_mapping():
    """Fetch all users from Supply API for created_by mapping"""
    try:
        response = requests.get(
            f'{SUPPLY_API_URL}/api/users/all/',
            timeout=500
        )
        if response.status_code == 200:
            users_data = response.json()
            # Create mapping: user_id -> username
            return {
                user['id']: user.get('username') or user.get('full_name') or f"User #{user['id']}"
                for user in users_data
            }
    except Exception as e:
        print(f"Error fetching supply users: {e}")
    
    return {}


def get_allocation_users_mapping():
    """Fetch all users from Allocation API for allocated_by mapping"""
    try:
        response = requests.get(
            f'{ALLOCATION_API_URL}/ap/users/all/',
            timeout=500
        )
        if response.status_code == 200:
            users_data = response.json()
            # Create mapping: user_id -> username
            return {
                user['id']: user.get('username') or user.get('full_name') or f"User #{user['id']}"
                for user in users_data
            }
    except Exception as e:
        print(f"Error fetching allocation users: {e}")
    
    return {}


def get_all_mukkadams_from_supply():
    """Get all mukkadams from Supply API"""
    try:
        response = requests.get(
            f'{SUPPLY_API_URL}/api/mukkadam/',
            timeout=500
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Handle both list and paginated response
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'results' in data:
                return data['results']
            else:
                return []
        else:
            print(f"Error fetching mukkadams: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"Error fetching mukkadams from Supply API: {e}")
        return []


@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_scorecard_summary(request):
    """
    Get mukkadam scorecard summary with all filters
    
    Query Parameters:
    - search: Name or mobile number
    - created_by: User ID who registered the mukkadam
    - district: District filter
    - taluka: Taluka filter
    - village: Village filter
    - has_jobs: true/false - Filter by whether mukkadam has allocations
    - activity_type: Filter by activity type
    - allocated_by: User ID who allocated jobs
    - date_from: Start date (registration or work date)
    - date_to: End date (registration or work date)
    - date_filter_type: 'registration' or 'work_date' (default: work_date)
    - is_active: true/false - Filter by active status
    """
    print("="*80)
    print("📊 MUKKADAM SCORECARD SUMMARY API")
    print("="*80)
    
    # ========================================
    # STEP 1: FETCH USER MAPPINGS
    # ========================================
    print("👥 Fetching user mappings...")
    supply_users_map = get_supply_users_mapping()  # For created_by
    allocation_users_map = get_allocation_users_mapping()  # For allocated_by
    print(f"✅ Loaded {len(supply_users_map)} supply users and {len(allocation_users_map)} allocation users")
    
    # ========================================
    # STEP 2: GET ALL MUKKADAMS FROM SUPPLY API
    # ========================================
    print("🔄 Fetching all mukkadams from Supply API...")
    all_mukkadams = get_all_mukkadams_from_supply()
    
    if not all_mukkadams:
        return Response({
            'error': 'Failed to fetch mukkadams from Supply API',
            'count': 0,
            'summary': {},
            'mukkadams': []
        })
    
    print(f"✅ Fetched {len(all_mukkadams)} mukkadams from Supply API")
    
    # ========================================
    # STEP 3: APPLY FILTERS ON MUKKADAM DATA
    # ========================================
    filtered_mukkadams = all_mukkadams
    
    # Search by name or mobile
    search = request.GET.get('search')
    if search:
        filtered_mukkadams = [
            m for m in filtered_mukkadams
            if search.lower() in m.get('mukkadam_name', '').lower() or
               search in m.get('mobile_numbers', '')
        ]
        print(f"🔍 Search filter: {search} -> {len(filtered_mukkadams)} results")
    
    # Filter by created_by
    created_by = request.GET.get('created_by')
    if created_by:
        try:
            created_by_id = int(created_by)
            filtered_mukkadams = [
                m for m in filtered_mukkadams
                if m.get('created_by') == created_by_id
            ]
            print(f"👤 Created by: {created_by} -> {len(filtered_mukkadams)} results")
        except ValueError:
            pass
    
    # Location filters
    district = request.GET.get('district')
    if district:
        filtered_mukkadams = [
            m for m in filtered_mukkadams
            if m.get('district', '').lower() == district.lower()
        ]
        print(f"📍 District: {district} -> {len(filtered_mukkadams)} results")
    
    taluka = request.GET.get('taluka')
    if taluka:
        filtered_mukkadams = [
            m for m in filtered_mukkadams
            if m.get('taluka', '').lower() == taluka.lower()
        ]
        print(f"📍 Taluka: {taluka} -> {len(filtered_mukkadams)} results")
    
    village = request.GET.get('village')
    if village:
        filtered_mukkadams = [
            m for m in filtered_mukkadams
            if m.get('village', '').lower() == village.lower()
        ]
        print(f"📍 Village: {village} -> {len(filtered_mukkadams)} results")
    
    # Registration date filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    date_filter_type = request.GET.get('date_filter_type', 'work_date')
    
    if date_filter_type == 'registration' and (date_from or date_to):
        def parse_date(date_str):
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except:
                return None
        
        if date_from:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            filtered_mukkadams = [
                m for m in filtered_mukkadams
                if parse_date(m.get('created_at')) and parse_date(m.get('created_at')) >= date_from_obj
            ]
        
        if date_to:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            filtered_mukkadams = [
                m for m in filtered_mukkadams
                if parse_date(m.get('created_at')) and parse_date(m.get('created_at')) <= date_to_obj
            ]
        
        print(f"📅 Registration date filter: {date_from} to {date_to} -> {len(filtered_mukkadams)} results")
    
    mukkadam_ids = [m['id'] for m in filtered_mukkadams]
    
    # ========================================
    # STEP 4: GET ALL ALLOCATIONS FROM YOUR API
    # ========================================
    print("🔄 Fetching all allocations from local API...")
    
    try:
        allocations_response = requests.get(
            f'{ALLOCATION_API_URL}/ap/allocations/by-mobile/main/',
            timeout=600
        )
        
        if allocations_response.status_code == 200:
            allocations_data = allocations_response.json()
            all_allocations = allocations_data.get('allocations', [])
            print(f"✅ Fetched {len(all_allocations)} enriched allocations")
        else:
            print(f"❌ Error fetching allocations: {allocations_response.status_code}")
            all_allocations = []

    except Exception as e:
        print(f"❌ Error calling allocations API: {e}")
        all_allocations = []
       # ========================================
    # STEP 5: BUILD MUKKADAM STATS FROM ENRICHED ALLOCATIONS
    # ========================================
    mukkadam_stats = {}
    
    # Get filters
    activity_type = request.GET.get('activity_type')
    allocated_by = request.GET.get('allocated_by')
    
    for alloc_data in all_allocations:
        mid = alloc_data['mukkadam']['mukkadam_id']
        
        # Filter by mukkadam_ids from filtered mukkadams
        if mid not in mukkadam_ids:
            continue
        
        # Activity type filter
        if activity_type:
            alloc_activity_type = alloc_data['activity'].get('activity_type', '').lower()
            if alloc_activity_type != activity_type.lower() and alloc_activity_type != 'n/a':
                continue
        
        # Allocated by filter - Need to get this from Allocation model
        # (Your allocations/list API doesn't include allocated_by yet)
        if allocated_by:
            # Get allocation from DB to check allocated_by
            try:
                alloc_obj = Allocation.objects.get(id=alloc_data['allocation_id'])
                if not alloc_obj.allocated_by or alloc_obj.allocated_by.id != int(allocated_by):
                    continue
            except:
                continue
        
        # Work date filter
        if date_filter_type == 'work_date':
            work_date = alloc_data.get('work_date')
            if date_from and work_date and work_date < date_from:
                continue
            if date_to and work_date and work_date > date_to:
                continue
        
        if mid not in mukkadam_stats:
            mukkadam_stats[mid] = {
                'allocations': [],
                'unique_jobs': set(),
                'total_area': 0,
                'total_workers': 0,
                'total_earnings': 0,
                'total_paid': 0,
                'total_pending': 0,
                'total_man_days_worked': 0,
                'status_counts': {
                    'allocated': 0,
                    'in_progress': 0,
                    'completed': 0,
                    'cancelled': 0
                },
                'first_work_date': None,
            }
        
        stats = mukkadam_stats[mid]
        stats['allocations'].append(alloc_data)
        stats['unique_jobs'].add(alloc_data['job']['job_id'])
        
        current_alloc_crew = alloc_data.get('crew_size') or 0
        stats['total_area'] += alloc_data['allocated_area']
        stats['total_workers'] += current_alloc_crew
        stats['total_earnings'] += alloc_data['payment']['mukkadam_total_payment']
        
        # NEW LOGIC: Calculate actual man-days worked for this allocation
        # Since each allocation represents 1 work day in your logic
        stats['total_man_days_worked'] += current_alloc_crew
        
        # Payment tracking - Check if payment_request exists
        try:
            alloc_obj = Allocation.objects.select_related('payment_request').get(id=alloc_data['allocation_id'])
            if hasattr(alloc_obj, 'payment_request'):
                payment = alloc_obj.payment_request
                if payment.status == 'paid':
                    stats['total_paid'] += float(payment.requested_amount)
                elif payment.status == 'pending':
                    stats['total_pending'] += float(payment.requested_amount)
        except:
            pass
        
        # Status tracking
        status_key = alloc_data['status']
        stats['status_counts'][status_key] = stats['status_counts'].get(status_key, 0) + 1
        
        # First work date
        work_date_str = alloc_data.get('work_date')
        if work_date_str:
            try:
                work_date_obj = datetime.strptime(work_date_str, '%Y-%m-%d').date()
                if stats['first_work_date'] is None or work_date_obj < stats['first_work_date']:
                    stats['first_work_date'] = work_date_obj
            except:
                pass
    
    # ========================================
    # STEP 7: BUILD FINAL MUKKADAM LIST
    # ========================================
    mukkadam_list = []
    today = date.today()

    for mukkadam in filtered_mukkadams:
        mid = mukkadam['id']
        stats = mukkadam_stats.get(mid, {
            'allocations': [],
            'unique_jobs': set(),
            'total_area': 0,
            'total_workers': 0,
            'total_earnings': 0,
            'total_paid': 0,
            'total_pending': 0,
            'status_counts': {},
            'first_work_date': None,
        })
        
        # Calculate active status
        has_jobs = len(stats['allocations']) > 0
        
        # ========================================
        # ✅ ENHANCED AVAILABILITY LOGIC
        # ========================================
        start_date = mukkadam.get('start_date')
        end_date = mukkadam.get('end_date')
        team_availabilities = mukkadam.get('team_availabilities', [])
        
        is_available_now = False
        all_availability_periods = []
        
        # Check mukkadam-level dates
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
                
                all_availability_periods.append({
                    'type': 'main',
                    'start_date': start_date,
                    'end_date': end_date,
                })
                
                # Check if available now
                if end_date_obj:
                    if start_date_obj <= today <= end_date_obj:
                        is_available_now = True
                else:
                    if start_date_obj <= today:
                        is_available_now = True
            except:
                pass
        
        # Check team availabilities
        if team_availabilities:
            for team_avail in team_availabilities:
                if team_avail.get('status') == 'Available':
                    team_start = team_avail.get('startDate')
                    team_end = team_avail.get('endDate')
                    
                    if team_start:
                        try:
                            team_start_obj = datetime.strptime(team_start, '%Y-%m-%d').date()
                            team_end_obj = datetime.strptime(team_end, '%Y-%m-%d').date() if team_end else None
                            
                            all_availability_periods.append({
                                'type': 'team',
                                'team_name': team_avail.get('teamName', 'Unknown Team'),
                                'start_date': team_start,
                                'end_date': team_end,
                            })
                            
                            # Check if available now
                            if not is_available_now:  # Only check if not already available
                                if team_end_obj:
                                    if team_start_obj <= today <= team_end_obj:
                                        is_available_now = True
                                else:
                                    if team_start_obj <= today:
                                        is_available_now = True
                        except:
                            pass
        
        has_availability = len(all_availability_periods) > 0
        
        # Active logic: has jobs OR is available now
        is_active = has_jobs or is_available_now
        
        # Days to first job
        days_to_first_job = None
        if stats['first_work_date'] and mukkadam.get('created_at'):
            try:
                created_date = datetime.fromisoformat(mukkadam['created_at'].replace('Z', '+00:00')).date()
                days_to_first_job = (stats['first_work_date'] - created_date).days
            except:
                pass

        # ✅ NEW: MAN-DAY AND UTILIZATION CALCULATIONS
        total_available_calendar_days = 0
        for period in all_availability_periods:
            try:
                s_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                e_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date() if period['end_date'] else today
                
                # Days in period (inclusive)
                days_diff = (e_date - s_date).days + 1
                if days_diff > 0:
                    total_available_calendar_days += days_diff
            except:
                continue

                # 1. Ensure base_crew_size is an integer
        try:
            base_crew_size = int(mukkadam.get('crew_size', 0) or 0)
        except (ValueError, TypeError):
            base_crew_size = 0

        # 2. Calculate potential_man_days
        potential_man_days = total_available_calendar_days * base_crew_size

        # 3. Ensure actual_man_days_worked is a number (from your stats in Step 5)
        actual_man_days_worked = stats.get('total_man_days_worked', 0)
        if not isinstance(actual_man_days_worked, (int, float)):
            try:
                actual_man_days_worked = float(actual_man_days_worked)
            except:
                actual_man_days_worked = 0

        # 4. Final calculation with float safety
        if potential_man_days > 0:
            utilization_rate = (actual_man_days_worked / potential_man_days) * 100
        else:
            utilization_rate = 0

        # 5. Avg Daily Earning per Worker
        if actual_man_days_worked > 0:
            avg_worker_earning = stats['total_earnings'] / actual_man_days_worked
        else:
            avg_worker_earning = 0
        
        # Location display
        location_parts = []
        if mukkadam.get('village'): location_parts.append(mukkadam['village'])
        if mukkadam.get('taluka'): location_parts.append(mukkadam['taluka'])
        if mukkadam.get('district'): location_parts.append(mukkadam['district'])
        location_display = ", ".join(location_parts) if location_parts else "Not Specified"
        
        mukkadam_obj = {
            'id': mid,
            'mukkadam_name': mukkadam.get('mukkadam_name', 'Unknown'),
            'mobile_numbers': mukkadam.get('mobile_numbers', ''),
            'village': mukkadam.get('village', ''),
            'taluka': mukkadam.get('taluka', ''),
            'district': mukkadam.get('district', ''),
            'crew_size': mukkadam.get('crew_size', 0),
            'is_permanent': mukkadam.get('is_permanent', False),
            'created_at': mukkadam.get('created_at'),
            'created_by_name': supply_users_map.get(
                mukkadam.get('created_by'),
                f"User #{mukkadam.get('created_by')}"
            ) if mukkadam.get('created_by') else 'Unknown',
            'location_display': location_display,
            "potential_man_days": int(potential_man_days or 0),
            'actual_man_days_worked': actual_man_days_worked,
            'utilization_rate': round(utilization_rate, 1),
            'avg_earning_per_worker_day': round(avg_worker_earning, 2),
            # ✅ Enhanced Availability
            'start_date': start_date,
            'end_date': end_date,
            'availability_status': {
                'is_available_now': is_available_now,
                'has_availability': has_availability,
                'all_periods': all_availability_periods,  # ✅ Show all availability periods
                'total_periods': len(all_availability_periods),
            },
            
            # Activity status
            'is_active': is_active,
            'first_allocation_date': str(stats['first_work_date']) if stats['first_work_date'] else None,
            'days_to_first_job': days_to_first_job,
            
            # Job statistics
            'total_allocations': len(stats['allocations']),
            'total_unique_jobs': len(stats['unique_jobs']),
            'total_area_allocated': round(stats['total_area'], 2),
            'total_workers_supplied': stats['total_workers'],
            'total_earnings': round(stats['total_earnings'], 2),
            'total_paid': round(stats['total_paid'], 2),
            'total_pending': round(stats['total_pending'], 2),
            
            # Status breakdown
            'allocations_by_status': stats['status_counts'],
            
            # Job summary (last 10)
            'job_summary': stats['allocations'][:10],
        }
        
        mukkadam_list.append(mukkadam_obj)
        
    # ========================================
    # STEP 7: APPLY POST-FILTERS
    # ========================================
    
    # Filter by has_jobs
    has_jobs = request.GET.get('has_jobs')
    if has_jobs == 'true':
        mukkadam_list = [m for m in mukkadam_list if m['total_allocations'] > 0]
        print(f"✅ Has jobs filter: true -> {len(mukkadam_list)} results")
    elif has_jobs == 'false':
        mukkadam_list = [m for m in mukkadam_list if m['total_allocations'] == 0]
        print(f"❌ Has jobs filter: false -> {len(mukkadam_list)} results")
    else:
        # Include mukkadams with jobs OR availability
        mukkadam_list = [
            m for m in mukkadam_list
            if m['total_allocations'] > 0 or m['availability_status']['has_availability']
        ]
        print(f"📋 Including mukkadams with jobs OR availability -> {len(mukkadam_list)} results")
    
    # Filter by is_active
    is_active_filter = request.GET.get('is_active')
    if is_active_filter:
        is_active_bool = is_active_filter.lower() == 'true'
        mukkadam_list = [m for m in mukkadam_list if m['is_active'] == is_active_bool]
        print(f"🔥 Active status filter: {is_active_filter} -> {len(mukkadam_list)} results")
    
    # ========================================
    # STEP 8: CALCULATE SUMMARY
    # ========================================
    total_mukkadams = len(mukkadam_list)
    active_mukkadams = len([m for m in mukkadam_list if m['is_active']])
    
    total_allocations = sum(m['total_allocations'] for m in mukkadam_list)
    total_unique_jobs = sum(m['total_unique_jobs'] for m in mukkadam_list)
    total_area = sum(m['total_area_allocated'] for m in mukkadam_list)
    total_workers = sum(m['total_workers_supplied'] for m in mukkadam_list)
    total_earnings = sum(m['total_earnings'] for m in mukkadam_list)
    total_paid = sum(m['total_paid'] for m in mukkadam_list)
    total_pending = sum(m['total_pending'] for m in mukkadam_list)
    
    summary = {
        'total_mukkadams': total_mukkadams,
        'active_mukkadams': active_mukkadams,
        'inactive_mukkadams': total_mukkadams - active_mukkadams,
        'total_allocations': total_allocations,
        'total_unique_jobs': total_unique_jobs,
        'total_area_allocated': round(total_area, 2),
        'total_workers_supplied': total_workers,
        'total_earnings': round(total_earnings, 2),
        'total_paid': round(total_paid, 2),
        'total_pending': round(total_pending, 2),
    }
    
    print(f"✅ Final count: {total_mukkadams} mukkadams")
    print("="*80)
    
    return Response({
        'count': total_mukkadams,
        'summary': summary,
        'mukkadams': mukkadam_list
    })


from rest_framework import generics
from django.contrib.auth.models import User
class UserListAPIView(generics.ListAPIView):
    # Use select_related to improve performance (joins the tables in 1 query)
    queryset = User.objects.select_related('profile').all()
    serializer_class = UserDetailSerializer
@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_scorecard_details(request, mukkadam_id):
    """
    Get detailed scorecard for a specific mukkadam with breakdowns
    """
    print("="*80)
    print(f"📊 MUKKADAM SCORECARD DETAILS - ID: {mukkadam_id}")
    print("="*80)
    
    
    # ========================================
    # STEP 1: GET MUKKADAM FROM SUPPLY API
    # ========================================
    try:
        mukkadam_response = requests.get(
            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
            timeout=500
        )
        
        if mukkadam_response.status_code != 200:
            return Response(
                {'error': 'Mukkadam not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        mukkadam_data = mukkadam_response.json()
        print(f"✅ Found mukkadam: {mukkadam_data.get('mukkadam_name')}")
        
    except Exception as e:
        return Response(
            {'error': f'Error fetching mukkadam: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # ========================================
    # STEP 2: GET USER MAPPINGS
    # ========================================
    allocation_users_map = get_allocation_users_mapping()
    supply_users_map = get_supply_users_mapping()
    
    # ========================================
    # STEP 3: GET ALLOCATIONS FROM DATABASE
    # ========================================
    allocations = Allocation.objects.filter(
        mukkadam_id=mukkadam_id
    ).select_related('job_activity', 'allocated_by').prefetch_related('payment_request').order_by('-work_date')
    
    if not allocations.exists():
        return Response({
            'mukkadam': mukkadam_data,
            'summary': {
                'total_allocations': 0,
                'total_unique_jobs': 0,
                'total_area': 0,
                'total_workers': 0,
                'total_earnings': 0,
                'total_paid': 0,
                'total_pending': 0,
                'avg_area_per_allocation': 0,
                'avg_earnings_per_allocation': 0,
            },
            'allocations': [],
            'breakdowns': {
                'by_activity': [],
                'by_status': [],
                'by_month': [],
                'by_location': [],
                'by_allocated_by': []
            }
        })
    
    # ========================================
    # STEP 4: FETCH EXTERNAL DATA
    # ========================================
    job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)
    
    jobs_cache = {}
    farmers_cache = {}
    
    try:
        job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        response = requests.get(
            f'{EXTERNAL_API_URL}/get_allocated_jobs/',
            headers={'Authorization': job_token},
            timeout=500
        )
        
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', []) if isinstance(data, dict) else data
            
            for job in jobs_list:
                job_id = str(job.get('work_id') or job.get('id'))
                if job_id in job_ids:
                    jobs_cache[job_id] = job
            
            # Fetch farmers
            farmer_ids = set(j.get('farmer_id') for j in jobs_cache.values() if j.get('farmer_id'))
            farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
    
    except Exception as e:
        print(f"⚠️ Error fetching external data: {e}")
    
    # ========================================
    # STEP 5: BUILD ENRICHED ALLOCATIONS & BREAKDOWNS
    # ========================================
    enriched_allocations = []

    first_work_date = None
    
    # For breakdowns
    activity_breakdown = {}
    status_breakdown = {}
    month_breakdown = {}
    location_breakdown = {}
    allocated_by_breakdown = {}
    
    # For summary
    total_area = 0
    total_workers = 0
    total_earnings = 0
    total_paid = 0
    total_pending = 0
    unique_jobs = set()
    
    for alloc in allocations:
        if alloc.work_date:
            if first_work_date is None or alloc.work_date < first_work_date:
                first_work_date = alloc.work_date
        job_activity = alloc.job_activity
        if not job_activity:
            continue
        
        job_id = str(job_activity.job_id)
        activity_id = str(job_activity.activity_id)
        unique_jobs.add(job_id)
        
        # Get cached data
        job_data = jobs_cache.get(job_id, {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})
        
        # Get activity details
        activity_name = 'Unknown'
        activity_type = 'Unknown'
        
        if job_data and 'activities' in job_data:
            activity_details = next(
                (a for a in job_data.get('activities', [])
                 if str(a.get('id') or a.get('activity_id')) == activity_id),
                None
            )
            if activity_details:
                activity_name = activity_details.get('activity_name', 'Unknown')
                activity_type = activity_details.get('activity_type', 'Unknown')
        
        # Payment details
        payment_status = 'unpaid'
        paid_amount = 0
        pending_amount = 0

        
        
        if hasattr(alloc, 'payment_request'):
            payment_req = alloc.payment_request
            payment_status = payment_req.status
            
            if payment_status == 'paid':
                paid_amount = float(payment_req.requested_amount)
            elif payment_status == 'pending':
                pending_amount = float(payment_req.requested_amount)
        
        # Location from job
        location = job_data.get('location') or farmer_data.get('village', 'Unknown')
        
        # Allocated by
        allocated_by_name = allocation_users_map.get(
            alloc.allocated_by.id,
            f"User #{alloc.allocated_by.id}"
        ) if alloc.allocated_by else 'Unknown'
        
        # Build allocation object
        enriched_alloc = {
            'allocation_id': alloc.id,
            'work_date': str(alloc.work_date) if alloc.work_date else None,
            'allocated_area': float(alloc.allocated_area),
            'crew_size': alloc.crew_size,
            'status': alloc.status,
            'notes': alloc.notes,
            'allocated_at': alloc.allocated_at.isoformat() if alloc.allocated_at else None,
            
            'allocated_by': allocated_by_name,
            
            'job': {
                'job_id': job_id,
                'job_name': job_data.get('job_name', 'N/A'),
                'scheduled_date': job_data.get('scheduled_date', 'N/A'),
                'location': location,
            },
            
            'activity': {
                'activity_id': activity_id,
                'activity_name': activity_name,
                'activity_type': activity_type,
            },
            
            'farmer': {
                'farmer_id': farmer_id,
                'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                'phone': farmer_data.get('phone_number', 'N/A'),
                'village': farmer_data.get('village', 'N/A'),
            },
            
            'payment': {
                'mukkadam_price': float(alloc.mukkadam_price),
                'total_earnings': float(alloc.mukkadam_price),
                'payment_status': payment_status,
                'paid_amount': paid_amount,
                'pending_amount': pending_amount,
            }
        }
        
        enriched_allocations.append(enriched_alloc)
        
        # Update summary stats
        total_area += float(alloc.allocated_area)
        total_workers += (alloc.crew_size or 0)
        total_earnings += float(alloc.mukkadam_price)
        total_paid += paid_amount
        total_pending += pending_amount
        
        # Update breakdowns
        # By activity
        if activity_name not in activity_breakdown:
            activity_breakdown[activity_name] = {
                'count': 0,
                'area': 0,
                'earnings': 0
            }
        activity_breakdown[activity_name]['count'] += 1
        activity_breakdown[activity_name]['area'] += float(alloc.allocated_area)
        activity_breakdown[activity_name]['earnings'] += float(alloc.mukkadam_price)
        
        # By status
        if alloc.status not in status_breakdown:
            status_breakdown[alloc.status] = 0
        status_breakdown[alloc.status] += 1
        
        # By month
        if alloc.work_date:
            month_key = alloc.work_date.strftime('%Y-%m')
            if month_key not in month_breakdown:
                month_breakdown[month_key] = {
                    'count': 0,
                    'area': 0,
                    'earnings': 0
                }
            month_breakdown[month_key]['count'] += 1
            month_breakdown[month_key]['area'] += float(alloc.allocated_area)
            month_breakdown[month_key]['earnings'] += float(alloc.mukkadam_price)
        
        # By location
        if location not in location_breakdown:
            location_breakdown[location] = {
                'count': 0,
                'area': 0,
                'earnings': 0
            }
        location_breakdown[location]['count'] += 1
        location_breakdown[location]['area'] += float(alloc.allocated_area)
        location_breakdown[location]['earnings'] += float(alloc.mukkadam_price)
        
        # By allocated_by
        if allocated_by_name not in allocated_by_breakdown:
            allocated_by_breakdown[allocated_by_name] = {
                'count': 0,
                'area': 0,
                'earnings': 0
            }
        allocated_by_breakdown[allocated_by_name]['count'] += 1
        allocated_by_breakdown[allocated_by_name]['area'] += float(alloc.allocated_area)
        allocated_by_breakdown[allocated_by_name]['earnings'] += float(alloc.mukkadam_price)
    
    # ========================================
    # STEP 6: FORMAT BREAKDOWNS
    # ========================================
    activity_breakdown_list = [
        {
            'activity_name': k,
            'count': v['count'],
            'area': round(v['area'], 2),
            'earnings': round(v['earnings'], 2)
        }
        for k, v in sorted(activity_breakdown.items(), key=lambda x: x[1]['count'], reverse=True)
    ]
    
    status_breakdown_list = [
        {'status': k, 'count': v}
        for k, v in status_breakdown.items()
    ]
    
    month_breakdown_list = [
        {
            'month': k,
            'count': v['count'],
            'area': round(v['area'], 2),
            'earnings': round(v['earnings'], 2)
        }
        for k, v in sorted(month_breakdown.items())
    ]
    
    location_breakdown_list = [
        {
            'location': k,
            'count': v['count'],
            'area': round(v['area'], 2),
            'earnings': round(v['earnings'], 2)
        }
        for k, v in sorted(location_breakdown.items(), key=lambda x: x[1]['count'], reverse=True)
    ]
    
    allocated_by_breakdown_list = [
        {
            'allocated_by': k,
            'count': v['count'],
            'area': round(v['area'], 2),
            'earnings': round(v['earnings'], 2)
        }
        for k, v in sorted(allocated_by_breakdown.items(), key=lambda x: x[1]['count'], reverse=True)
    ]
    
    # ========================================
    # STEP 7: BUILD FINAL RESPONSE
    # ========================================

    days_to_first_job = None
    registration_date_str = mukkadam_data.get('created_at')
    
    if first_work_date and registration_date_str:
        try:
            # Parse registration date (handling ISO format with 'Z' or offset)
            from datetime import datetime
            reg_date = datetime.fromisoformat(registration_date_str.replace('Z', '+00:00')).date()
            
            # Difference in days
            delta = (first_work_date - reg_date).days
            days_to_first_job = max(0, delta) # Ensure no negative numbers
        except Exception as e:
            print(f"⚠️ Error calculating activation days: {e}")
    summary = {
        'total_allocations': len(allocations),
        'total_unique_jobs': len(unique_jobs),
        'total_area': round(total_area, 2),
        'total_workers': total_workers,
        'total_earnings': round(total_earnings, 2),
        'total_paid': round(total_paid, 2),
        'total_pending': round(total_pending, 2),
        # ✅ NEW FIELD ADDED HERE
        'days_to_first_job': days_to_first_job, 
        'first_work_date': str(first_work_date) if first_work_date else None,
        'avg_area_per_allocation': round(total_area / len(allocations), 2) if len(allocations) > 0 else 0,
        'avg_earnings_per_allocation': round(total_earnings / len(allocations), 2) if len(allocations) > 0 else 0,
    }
    
    print(f"✅ Processed {len(allocations)} allocations")
    print("="*80)
    
    return Response({
        'mukkadam': mukkadam_data,
        'summary': summary,
        'allocations': enriched_allocations,
        'breakdowns': {
            'by_activity': activity_breakdown_list,
            'by_status': status_breakdown_list,
            'by_month': month_breakdown_list,
            'by_location': location_breakdown_list,
            'by_allocated_by': allocated_by_breakdown_list,
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_work_history(request):
    """
    Get complete work history and analytics for a mukkadam
    """
    print("="*80)
    print("📊 FETCHING MUKKADAM WORK HISTORY & ANALYTICS")
    print("="*80)

    mukkadam_phone = request.GET.get('mukkadam_phone')
    mukkadam_id = request.GET.get('mukkadam_id')

    if not mukkadam_phone and not mukkadam_id:
        return Response(
            {'error': 'Either mukkadam_phone or mukkadam_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ========================================
    # STEP 1: GET MUKKADAM DETAILS FROM SUPPLY API
    # ========================================
    # ... (Keep existing Step 1 code exactly as is) ...
    # SUPPLY_API_URL = 'http://localhost:8000'
    mukkadam_data = None

    try:
        if mukkadam_id:
            # Fetch by ID
            response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
                timeout=500
            )
            if response.status_code == 200:
                mukkadam_data = response.json()
                mukkadam_id = int(mukkadam_id)
        else:
            # Search by phone
            response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/',
                timeout=500
            )
            if response.status_code == 200:
                mukkadams = response.json()
                for m in mukkadams:
                    if mukkadam_phone in m.get('mobile_numbers', ''):
                        mukkadam_id = m['id']
                        # Fetch full details
                        full_response = requests.get(
                            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
                            timeout=500
                        )
                        if full_response.status_code == 200:
                            mukkadam_data = full_response.json()
                        break

        if not mukkadam_data:
            return Response(
                {'error': 'Mukkadam not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        print(f"   ❌ Error fetching mukkadam: {str(e)}")
        return Response(
            {'error': f'Failed to fetch mukkadam details: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ========================================
    # STEP 2: GET ALL ALLOCATIONS FOR THIS MUKKADAM
    # ========================================
    # allocations = Allocation.objects.filter(
    #     mukkadam_id=mukkadam_id
    # ).select_related('job_activity', 'payment_request').order_by('-work_date')

# Update your Step 2 Query
    allocations = Allocation.objects.filter(
        mukkadam_id=mukkadam_id
    ).select_related('job_activity').prefetch_related('payment_request').order_by('-work_date')
    # ========================================
    # STEP 3: CATEGORIZE ALLOCATIONS & CALCULATE EARNINGS
    # ========================================
    from datetime import date
    today = date.today()

    completed_allocations = []
    pending_allocations = []
    upcoming_allocations = []

    total_allocated_area = 0
    total_area_worked = 0

    total_potential_earnings = 0
    total_paid_earnings = 0
    total_pending_payout = 0
    total_upcoming_income = 0

    for allocation in allocations:
        work_date = allocation.work_date
        earnings = float(allocation.mukkadam_price) * float(allocation.allocated_area)

        has_payment_req = hasattr(allocation, 'payment_request')

        total_potential_earnings += earnings
        total_allocated_area += float(allocation.allocated_area)

        # ============================
        # COMPLETED JOBS
        # ============================
        if allocation.status == 'completed':
            completed_allocations.append(allocation)
            total_area_worked += float(allocation.allocated_area)

            if has_payment_req and allocation.payment_request.status == 'paid':
                total_paid_earnings += earnings
            else:
                # ✅ Completed but not paid → pending payout
                total_pending_payout += earnings
                pending_allocations.append(allocation)

        # ============================
        # PAST DATE OR PAYMENT REQUEST
        # ============================
        elif (work_date and work_date < today) or has_payment_req:
            pending_allocations.append(allocation)

            # ✅ Always pending payout
            total_pending_payout += earnings

        # ============================
        # FUTURE JOBS
        # ============================
        else:
            upcoming_allocations.append(allocation)
            total_upcoming_income += earnings
    
    total_area_remaining = total_allocated_area - total_area_worked

    # ========================================
    # STEP 4: FETCH JOB & FARMER DETAILS (External APIs)
    # ========================================
    # ... (Keep existing Step 4 code exactly as is) ...
    job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)
    jobs_cache = {}
    farmers_cache = {}
    EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
    job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
    try:
        response = requests.get(f'{EXTERNAL_API_URL}/get_allocated_jobs/', headers={'Authorization': job_token}, timeout=500)
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', []) if isinstance(data, dict) else data
            for job in jobs_list:
                job_id = str(job.get('work_id') or job.get('id'))
                if job_id in job_ids:
                    jobs_cache[job_id] = job
    except Exception as e:
        print(f"   ⚠️ Error fetching jobs: {str(e)}")

    farmer_ids = set()
    for job in jobs_cache.values():
        if job.get('farmer_id'):
            farmer_ids.add(str(job['farmer_id']))
    FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
    farmer_token = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'
    for farmer_id in farmer_ids:
        try:
            response = requests.get(f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/', headers={'Authorization': farmer_token}, timeout=500)
            if response.status_code == 200:
                farmers_cache[farmer_id] = response.json()
        except Exception:
            pass

    # ========================================
    # STEP 5: BUILD ALLOCATION DETAILS
    # ========================================
    # ... (Keep existing build_allocation_detail function logic) ...
    def build_allocation_detail(allocation):
        job_activity = allocation.job_activity
        if not job_activity: return None
        job_id = str(job_activity.job_id)
        activity_id = str(job_activity.activity_id)
        job_data = jobs_cache.get(job_id, {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})
        activity_details = next((a for a in job_data.get('activities',[]) if str(a.get('id') or a.get('activity_id')) == activity_id), None)
        central_team_phone = '+91-804-7361465'
        if job_data and 'booking' in job_data:
            central_team_phone = '+91-804-7361465'

        # Determine payment object for response
        payment_info = {
            'has_request': False,
            'can_request': allocation.status == 'completed',
            'status': 'N/A'
        }
        if hasattr(allocation, 'payment_request'):
            pr = allocation.payment_request
            payment_info = {
                'has_request': True,
                'request_id': pr.id,
                'status': pr.status,
                'requested_amount': float(pr.requested_amount),
                'requested_at': pr.requested_at.isoformat(),
                'paid_at': pr.paid_at.isoformat() if pr.paid_at else None,
            }

        return {
            'allocation_id': allocation.id,
            'work_date': str(allocation.work_date) if allocation.work_date else None,
            'allocated_area': float(allocation.allocated_area),
            'crew_size': allocation.crew_size,
            'status': allocation.status,
            'allocated_at': allocation.allocated_at.isoformat() if allocation.allocated_at else None,
            'job': {
                'job_id': job_id,
                'job_name': job_data.get('job_name', 'N/A'),
                'location': job_data.get('location', 'N/A'),
                'central_team_phone': central_team_phone,
            },
            'farmer': {
                'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                'phone_number': farmer_data.get('phone_number', 'N/A'),
                'location': f"{farmer_data.get('village', 'N/A')}, {farmer_data.get('taluka', 'N/A')}"
            } if farmer_data else None,
            'activity': {
                'activity_name': activity_details.get('activity_name', 'Unknown') if activity_details else 'Unknown',
                'activity_type': activity_details.get('activity_type', 'N/A') if activity_details else 'N/A',
            },
            'payment': payment_info,
        }

    completed_details = [d for d in [build_allocation_detail(a) for a in completed_allocations] if d]
    pending_details = [d for d in [build_allocation_detail(a) for a in pending_allocations] if d]
    upcoming_details = [d for d in [build_allocation_detail(a) for a in upcoming_allocations] if d]

    # ========================================
    # STEP 6: MONTHLY BREAKDOWN
    # ========================================
    # ... (Keep existing monthly logic) ...
    from collections import defaultdict
    monthly_stats = defaultdict(lambda: {'month': '', 'allocations': 0, 'area_worked': 0, 'earnings': 0, 'completed': 0})
    for allocation in allocations:
        if allocation.work_date:
            month_key = allocation.work_date.strftime('%Y-%m')
            monthly_stats[month_key]['month'] = allocation.work_date.strftime('%B %Y')
            monthly_stats[month_key]['allocations'] += 1
            monthly_stats[month_key]['area_worked'] += float(allocation.allocated_area)
            monthly_stats[month_key]['earnings'] += float(allocation.mukkadam_price) * float(allocation.allocated_area)
            if allocation.status == 'completed':
                monthly_stats[month_key]['completed'] += 1

    monthly_breakdown = sorted(monthly_stats.values(), key=lambda x: x['month'], reverse=True)

    # ========================================
    # STEP 7: BUILD FINAL RESPONSE (UPDATED SUMMARY)
    # ========================================
    completion_rate = (len(completed_allocations) / allocations.count() * 100) if allocations.count() > 0 else 0

    response_data = {
        'mukkadam': {
            'mukkadam_id': mukkadam_id,
            'mukkadam_name': mukkadam_data.get('mukkadam_name'),
            'mobile_numbers': mukkadam_data.get('mobile_numbers'),
            'village': mukkadam_data.get('village'),
            'crew_size': mukkadam_data.get('crew_size'),
            'has_smartphone': mukkadam_data.get('has_smartphone'),
        },

        # ✅ UPDATED FINANCIAL SUMMARY BASED ON YOUR REQUEST
        'summary': {
            'total_allocations': allocations.count(),
            'completed_jobs': len(completed_allocations),
            'pending_jobs': len(pending_allocations),
            'upcoming_jobs': len(upcoming_allocations),
            'completion_rate': round(completion_rate, 2),

            # 1. Total Earning Potential (From all allocations)
            'total_potential_earnings': round(total_potential_earnings, 2),

            # 2. Total Paid (Completed & Paid status)
            'total_paid_earnings': round(total_paid_earnings, 2),

            # 3. Pending Payout (Completed & Not Paid/Requested)
            'total_pending_payout': round(total_pending_payout, 2),

            # 4. Upcoming Income (Allocated or Pending Jobs)
            'total_upcoming_income': round(total_upcoming_income, 2),
            # Area Metrics
            'total_allocated_area': round(total_allocated_area, 2),  # ALL allocations
            'total_area_worked': round(total_area_worked, 2),        # COMPLETED only
            'total_area_remaining': round(total_area_remaining, 2),  # Pending + Upcoming
        },

        'work_history': {
            'completed': completed_details,
            'pending': pending_details,
            'upcoming': upcoming_details,
        },

        'monthly_breakdown': monthly_breakdown,

        'performance_metrics': {
            'total_jobs_completed': len(completed_allocations),
            'total_jobs_pending': len(pending_allocations),
            'average_area_per_job': round(total_allocated_area / allocations.count(), 2) if allocations.count() > 0 else 0,
            'most_recent_work': str(allocations.first().work_date) if allocations.first() and allocations.first().work_date else None,
        }
    }

    return Response(response_data)


# core/views.py (add to existing views)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# from .services.exotel_service import ExotelService
from .exotel_services import ExotelService
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from .models import FarmerCall




logger = logging.getLogger(__name__)
class MakeCallView(APIView):
    """
    Simple call API - Just provide from_number and to_number
    Accepts user_id in payload
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from_number = request.data.get('from_number')
        to_number = request.data.get('to_number')

        # Optional metadata
        purpose = request.data.get('purpose', 'general')
        job_id = request.data.get('job_id', '')
        notes = request.data.get('notes', '')
        user_id = request.data.get('user_id')  # ✅ NEW: Accept from payload
        # custom_field = request.data.get('custom_field', '')  # ✅ Optional custom field

        # Basic validation
        if not from_number or not to_number:
            return Response({
                'success': False,
                'message': 'Both from_number and to_number are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1️⃣ Make the call via Exotel
            exotel = ExotelService()
            call_result = exotel.make_call(
                from_number=from_number,
                to_number=to_number,
                # custom_field=custom_field  # Pass to Exotel if needed
            )

            if not call_result['success']:
                return Response({
                    'success': False,
                    'message': 'Failed to initiate call',
                    'error': call_result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 2️⃣ Prepare call record data
            call_data = {
                'call_sid': call_result['call_sid'],
                'mobile_number': to_number,
                'from_number': from_number,
                'purpose': purpose,
                'status': call_result.get('status', 'pending'),
                'job_id': job_id,
                'notes': notes,
                'direction': 'outbound',
                # 'custom_field': custom_field,
            }

            # ✅ Handle user_id from payload OR authenticated user
            if user_id:
                # User ID provided in payload (from mobile app)
                call_data['user_id'] = str(user_id)
                
                # Try to link to Django User if exists
                try:
                    from django.contrib.auth.models import User
                    django_user = User.objects.filter(
                        Q(id=user_id) | Q(username=user_id)
                    ).first()
                    call_data['created_by'] = django_user
                except:
                    call_data['created_by'] = None
                    
            elif request.user.is_authenticated:
                # Authenticated API call (from web/backend)
                call_data['user_id'] = str(request.user.id)
                call_data['created_by'] = request.user
            else:
                # Anonymous call
                call_data['user_id'] = 'anonymous'
                call_data['created_by'] = None

            # 3️⃣ Create call record
            call = FarmerCall.objects.create(**call_data)

            logger.info(f"✅ Call initiated: {call.call_sid} - {from_number} → {to_number} (User: {call.user_id})")

            return Response({
                'success': True,
                'message': 'Call initiated successfully',
                'call_sid': call_result['call_sid'],
                'call_id': call.id,
                'status': call_result.get('status', 'pending'),
                'from': from_number,
                'to': to_number,
                'user_id': call.user_id,
                'purpose': purpose
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Error making call: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# allocation_app/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Q

@api_view(['GET'])
@permission_classes([AllowAny])
def get_user_calls(request):
    """
    Get call history for a user
    GET /api/calls/user/?user_id=12345
    GET /api/calls/user/?user_id=12345&status=completed
    GET /api/calls/user/?user_id=12345&date_from=2026-01-01
    """
    user_id = request.query_params.get('user_id')
    
    if not user_id:
        return Response({
            'error': 'user_id parameter is required'
        }, status=400)
    
    # Query calls
    calls = FarmerCall.objects.filter(user_id=user_id)
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        calls = calls.filter(status=status_filter)
    
    date_from = request.query_params.get('date_from')
    if date_from:
        from datetime import datetime
        date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
        calls = calls.filter(initiated_at__gte=date_from_dt)
    
    date_to = request.query_params.get('date_to')
    if date_to:
        from datetime import datetime
        date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
        calls = calls.filter(initiated_at__lte=date_to_dt)
    
    # Order by most recent
    calls = calls.order_by('-initiated_at')
    
    # Serialize
    calls_data = []
    for call in calls:
        calls_data.append({
            'id': call.id,
            'call_sid': call.call_sid,
            'from_number': call.from_number,
            'to_number': call.mobile_number,
            'purpose': call.purpose,
            'status': call.status,
            'direction': call.direction,
            'duration': call.duration,
            'talk_time': call.talk_time,
            'initiated_at': call.initiated_at.isoformat() if call.initiated_at else None,
            'completed_at': call.completed_at.isoformat() if call.completed_at else None,
            'has_recording': call.has_recording,
            'recording_url': call.primary_recording_url,
            'job_id': call.job_id,
            'notes': call.notes,
        })
    
    # Stats
    from django.db.models import Count, Avg, Sum
    stats = calls.aggregate(
        total_calls=Count('id'),
        completed_calls=Count('id', filter=Q(status='completed')),
        total_duration=Sum('duration'),
        avg_duration=Avg('duration'),
    )
    
    return Response({
        'user_id': user_id,
        'total_calls': calls.count(),
        'stats': {
            'total_calls': stats['total_calls'] or 0,
            'completed_calls': stats['completed_calls'] or 0,
            'total_duration_seconds': stats['total_duration'] or 0,
            'avg_duration_seconds': int(stats['avg_duration'] or 0),
        },
        'calls': calls_data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_call_details(request, call_id):
    """
    Get detailed information about a specific call
    GET /api/calls/{call_id}/
    """
    try:
        call = FarmerCall.objects.get(id=call_id)
        
        return Response({
            'id': call.id,
            'call_sid': call.call_sid,
            'user_id': call.user_id,
            'from_number': call.from_number,
            'to_number': call.mobile_number,
            'purpose': call.purpose,
            'status': call.status,
            'direction': call.direction,
            'state': call.state,
            
            # Metrics
            'duration': call.duration,
            'talk_time': call.talk_time,
            'price': float(call.price) if call.price else None,
            
            # Recordings
            'has_recording': call.has_recording,
            'recording_url': call.recording_url,
            'recording_urls': call.recording_urls,
            'primary_recording_url': call.primary_recording_url,
            
            # Timestamps
            'initiated_at': call.initiated_at.isoformat() if call.initiated_at else None,
            'answered_at': call.answered_at.isoformat() if call.answered_at else None,
            'completed_at': call.completed_at.isoformat() if call.completed_at else None,
            'created_time': call.created_time.isoformat() if call.created_time else None,
            'updated_time': call.updated_time.isoformat() if call.updated_time else None,
            
            # Exotel specific
            'virtual_number': call.virtual_number,
            # 'custom_field': call.custom_field,
            'legs_url': call.legs_url,
            
            # Context
            'job_id': call.job_id,
            'notes': call.notes,
            'webhook_data': call.webhook_data,
            
            # User info
            'created_by': {
                'id': call.created_by.id,
                'username': call.created_by.username,
                'full_name': call.created_by.get_full_name()
            } if call.created_by else None
        })
        
    except FarmerCall.DoesNotExist:
        return Response({
            'error': 'Call not found'
        }, status=404)
    

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import FarmerCall
from django.utils import timezone
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ExotelWebhookView(APIView):
    """
    Receive call status updates from Exotel
    POST /api/calls/webhook/
    Exotel sends webhook in this format:
    {
        "call_details": {
            "sid": "...",
            "status": "completed",
            "total_talk_time": 25,
            "recordings": [{"url": "..."}],
            ...
        },
        "event_details": {
            "event_type": "terminal"
        }
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            data = request.data
            logger.info(f"📞 Received webhook: {data}")

            # Extract call_details
            call_details = data.get('call_details', {})
            event_details = data.get('event_details', {})

            # Get call_sid (Exotel uses 'sid' not 'call_sid')
            call_sid = call_details.get('sid')

            if not call_sid:
                logger.error("❌ No call_sid in webhook")
                return Response(
                    {"error": "No call_sid found in webhook data"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Find the call record
            call_record = FarmerCall.objects.filter(call_sid=call_sid).first()

            if not call_record:
                logger.warning(f"⚠️ Call record not found for SID: {call_sid}")
                return Response(
                    {"error": "Call not found", "call_sid": call_sid},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Update call status
            call_status = call_details.get('status', 'unknown').lower()
            call_record.status = call_status
            call_record.state = call_details.get('state', '')
            call_record.direction = call_details.get('direction', 'outbound')
            
            # Update duration and talk time
            if call_details.get('total_talk_time'):
                call_record.talk_time = int(call_details['total_talk_time'])
                call_record.duration = int(call_details['total_talk_time'])  # Fallback

            if call_details.get('total_duration'):
                call_record.duration = int(call_details['total_duration'])

            # Update virtual number and custom field
            call_record.virtual_number = call_details.get('virtual_number', '')
            call_record.legs_url = call_details.get('legs', '')
            
            # Parse and update timestamps
            def parse_datetime(dt_string):
                """Parse datetime string from Exotel format"""
                if not dt_string:
                    return None
                try:
                    # Exotel format: '2026-01-10T14:59:44+05:30'
                    return datetime.fromisoformat(dt_string)
                except:
                    return None

            if call_details.get('created_time'):
                call_record.created_time = parse_datetime(call_details['created_time'])

            if call_details.get('updated_time'):
                call_record.updated_time = parse_datetime(call_details['updated_time'])

            if call_details.get('start_time'):
                call_record.answered_at = parse_datetime(call_details['start_time'])

            if call_details.get('end_time'):
                call_record.completed_at = parse_datetime(call_details['end_time'])

            # Handle recordings array
            recordings = call_details.get('recordings', [])
            if recordings and len(recordings) > 0:
                # Extract URLs from recordings array
                recording_urls = [rec.get('url') for rec in recordings if rec.get('url')]
                call_record.recording_urls = recording_urls

                # Set primary recording URL
                if recording_urls:
                    call_record.recording_url = recording_urls[0]

            # Store full webhook data for debugging
            call_record.webhook_data = data

            # ✅ NEW: POST TO RECORDING WEBHOOK WHEN CALL ENDS
            event_type = event_details.get('event_type', '').lower()
            
            logger.info(f"📊 Event type: {event_type}, Call status: {call_status}")
            
            # Check if call ended (terminal event OR completed status)
            if event_type == 'terminal' or call_status in ['completed', 'terminal', 'failed', 'busy', 'no-answer']:
                logger.info(f"📞 Call ended - Status: {call_status}, Event: {event_type}")
                
                # Only fetch s3_key for COMPLETED calls with talk time
                if call_status == 'completed' and call_record.talk_time and call_record.talk_time > 0:
                    logger.info(f"🎙️ Call has recording (talk_time: {call_record.talk_time}s) - Fetching s3_key...")
                    
                    # Import ExotelService
                    from .exotel_services import ExotelService
                    
                    # Create instance and call recording webhook
                    exotel = ExotelService()
                    webhook_result = exotel.post_to_recording_webhook(call_sid)
                    
                    if webhook_result.get('success') and webhook_result.get('s3_key'):
                        call_record.s3_key = webhook_result['s3_key']
                        logger.info(f"✅ S3 Key stored: {call_record.s3_key}")
                    else:
                        logger.warning(f"⚠️ Failed to get s3_key from recording webhook")
                else:
                    logger.info(f"⚠️ Skipping s3_key fetch - Status: {call_status}, Talk time: {call_record.talk_time}s")

            # Save the updated record
            call_record.save()

            logger.info(f"✅ Updated call {call_sid} - Status: {call_record.status}, Talk Time: {call_record.talk_time}s, S3 Key: {call_record.s3_key or 'None'}")

            return Response({
                "success": True,
                "message": "Call updated successfully",
                "call_sid": call_sid,
                "status": call_record.status,
                "talk_time": call_record.talk_time,
                "has_recording": call_record.has_recording,
                "s3_key": call_record.s3_key  # ✅ Include s3_key in response
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Webhook error: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

from django.db.models import Prefetch
# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Prefetch, Sum, Q
from decimal import Decimal
from .models import (
    JobActivity, Allocation, ImportedFarmer, ImportedMukkadam, 
    ImportedTransporter, PaymentRequest, TransportPaymentRequest,
    FarmerPayment
)

# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Prefetch, Sum, Q
from decimal import Decimal
from .models import (
    JobActivity, Allocation, ImportedFarmer, ImportedMukkadam, 
    ImportedTransporter, PaymentRequest, TransportPaymentRequest,
    FarmerPayment
)


@api_view(['POST'])
@permission_classes([AllowAny])
def link_farmer_payment(request):
    """
    Link a farmer payment to a job activity.
    
    Body:
    {
        "farmer_payment_id": 123,
        "job_activity_id": 456,
        "notes": "Manual link by admin"
    }
    """
    
    farmer_payment_id = request.data.get('farmer_payment_id')
    job_activity_id = request.data.get('job_activity_id')
    notes = request.data.get('notes', '')
    
    # Validation
    if not farmer_payment_id or not job_activity_id:
        return Response({
            'error': 'Both farmer_payment_id and job_activity_id are required'
        }, status=400)
    
    try:
        payment = FarmerPayment.objects.get(id=farmer_payment_id)
    except FarmerPayment.DoesNotExist:
        return Response({'error': 'Farmer payment not found'}, status=404)
    
    try:
        activity = JobActivity.objects.get(id=job_activity_id)
    except JobActivity.DoesNotExist:
        return Response({'error': 'Job activity not found'}, status=404)
    
    # Check if already linked
    if payment.job_activity is not None:
        return Response({
            'error': 'This payment is already linked to another activity',
            'linked_to': {
                'job_id': payment.job_activity.job_id,
                'activity_name': payment.job_activity.activity_name
            }
        }, status=400)
    
    # ✅ Check for duplicate payment (same booking_value for same activity)
    duplicate_check = FarmerPayment.objects.filter(
        job_activity=activity,
        booking_value=payment.booking_value,
        activity_date=payment.activity_date
    ).exclude(id=payment.id).exists()
    
    if duplicate_check:
        return Response({
            'warning': 'A similar payment already exists for this activity',
            'proceed': 'Set force=true to proceed anyway'
        }, status=400)
    
    # Get user
    user = request.user if request.user.is_authenticated else None
    username = user.username if user else 'System'
    
    # Store old values for activity log
    old_values = {
        'job_activity': None,
        'is_matched': payment.is_matched,
        'match_notes': payment.match_notes
    }
    
    # Link payment
    payment.job_activity = activity
    payment.is_matched = True
    
    # Update match notes
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    new_note = f"[{timestamp}] Linked by {username} to Job #{activity.job_id} - {activity.activity_name}"
    if notes:
        new_note += f". Notes: {notes}"
    
    if payment.match_notes:
        payment.match_notes += f"\n{new_note}"
    else:
        payment.match_notes = new_note
    
    payment.save()
    
    # ✅ Create Activity Log
    ActivityLog.objects.create(
        activity_type='payment_linked',  # ✅ Add this to ACTIVITY_TYPES choices
        description=f"Farmer payment ₹{payment.booking_value} linked to activity {activity.activity_name}",
        allocation=None,  # Not related to specific allocation
        job_id=activity.job_id,
        mukkadam_id=0,  # N/A for farmer payments
        mukkadam_name=payment.farmer_name,
        amount=payment.booking_value,
        performed_by=user,
        changes={
            'farmer_payment_id': {
                'old': None,
                'new': payment.id
            },
            'job_activity': {
                'old': None,
                'new': f"{activity.job_id} - {activity.activity_name}"
            },
            'is_matched': {
                'old': old_values['is_matched'],
                'new': True
            }
        },
        metadata={
            'farmer_payment_id': payment.id,
            'job_activity_id': activity.id,
            'farmer_name': payment.farmer_name,
            'activity_date': str(payment.activity_date),
            'booking_value': float(payment.booking_value),
            'notes': notes
        }
    )
    
    return Response({
        'success': True,
        'message': f'Payment linked successfully to {activity.activity_name}',
        'payment': {
            'id': payment.id,
            'farmer_name': payment.farmer_name,
            'booking_value': float(payment.booking_value),
            'activity_date': str(payment.activity_date),
            'linked_to': {
                'job_id': activity.job_id,
                'activity_id': activity.id,
                'activity_name': activity.activity_name
            }
        }
    })


# views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def get_unmatched_farmer_payments(request):
    """
    Get unmatched farmer payments with smart suggestions for a specific activity.
    """
    
    # Base queryset - only unmatched payments
    payments = FarmerPayment.objects.filter(
        job_activity__isnull=True,
        is_matched=False
    ).select_related('imported_farmer')
    
    # Filters
    job_activity_id = request.query_params.get('job_activity_id')
    farmer_name = request.query_params.get('farmer_name')
    activity_name = request.query_params.get('activity_name')
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    payment_status = request.query_params.get('payment_status')
    
    # Apply filters
    if farmer_name:
        payments = payments.filter(farmer_name__icontains=farmer_name)
    
    if activity_name:
        payments = payments.filter(activity_name__icontains=activity_name)
    
    if date_from:
        payments = payments.filter(activity_date__gte=date_from)
    
    if date_to:
        payments = payments.filter(activity_date__lte=date_to)
    
    if payment_status:
        payments = payments.filter(payment_status=payment_status)
    
    print(f"📊 Filtered payments count: {payments.count()}")
    
    # Smart suggestions for specific activity
    suggestions = []
    if job_activity_id:
        try:
            activity = JobActivity.objects.prefetch_related(
                Prefetch(
                    'allocations',
                    queryset=Allocation.objects.select_related('imported_farmer')
                )
            ).get(id=job_activity_id)
            
            # ✅ Get activity date safely
            if activity.scheduled_datetime:
                activity_date = activity.scheduled_datetime.date()
            else:
                first_alloc = activity.allocations.first()
                if first_alloc and first_alloc.work_date:
                    activity_date = first_alloc.work_date
                else:
                    activity_date = timezone.now().date()
            
            print(f"🔍 Activity: {activity.activity_name} | Date: {activity_date}")
            
            # Get farmer info from allocations
            farmer_names = set()
            for alloc in activity.allocations.all():
                if alloc.farmer_name:
                    farmer_names.add(alloc.farmer_name.strip().lower())
                if alloc.imported_farmer and alloc.imported_farmer.name:
                    farmer_names.add(alloc.imported_farmer.name.strip().lower())
            
            print(f"   Farmer names in activity: {farmer_names}")
            
            activity_name_normalized = activity.activity_name.strip().lower()
            
            # Filter payments matching this activity
            for payment in payments:
                confidence = 'low'
                reasons = []
                score = 0
                
                # Farmer name match
                payment_farmer = payment.farmer_name.strip().lower()
                if payment_farmer in farmer_names:
                    score += 40
                    reasons.append("Farmer name matches")
                
                # Activity name match (fuzzy)
                payment_activity = payment.activity_name.strip().lower()
                if payment_activity in activity_name_normalized or activity_name_normalized in payment_activity:
                    score += 30
                    reasons.append("Activity name matches")
                
                # ✅ Date proximity (±10 days)
                date_diff = abs((payment.activity_date - activity_date).days)
                if date_diff <= 3:
                    score += 20
                    reasons.append(f"Date within {date_diff} days")
                elif date_diff <= 7:
                    score += 15
                    reasons.append(f"Date within {date_diff} days")
                elif date_diff <= 10:  # ✅ EXTENDED TO 10 DAYS
                    score += 10
                    reasons.append(f"Date within {date_diff} days")
                
                # Booking value check
                if activity.rate_per_acre > 0 and payment.acres:
                    try:
                        acres_float = float(payment.acres.split()[0]) if isinstance(payment.acres, str) else float(payment.acres)
                        expected_value = float(activity.rate_per_acre) * acres_float
                        actual_value = float(payment.booking_value)
                        variance = abs(expected_value - actual_value) / expected_value
                        if variance <= 0.15:
                            score += 10
                            reasons.append("Amount matches expected rate")
                    except (ValueError, ZeroDivisionError, IndexError):
                        pass
                
                # Determine confidence
                if score >= 70:
                    confidence = 'high'
                elif score >= 40:
                    confidence = 'medium'
                
                # ✅ ALWAYS ADD TO SUGGESTIONS (even with score 0)
                suggestions.append({
                    'payment': payment,
                    'confidence': confidence,
                    'score': score,
                    'reasons': reasons if reasons else ['No strong matches found'],
                    'match_suggestion': {
                        'job_activity_id': activity.id,
                        'job_id': activity.job_id,
                        'activity_name': activity.activity_name,
                        'scheduled_date': str(activity_date),
                    }
                })
            
            # Sort by score
            suggestions.sort(key=lambda x: x['score'], reverse=True)
            
            print(f"✅ Generated {len(suggestions)} suggestions")
        
        except JobActivity.DoesNotExist:
            print(f"❌ JobActivity {job_activity_id} not found")
            pass
    
    # Build response
    if suggestions:
        payments_data = []
        for item in suggestions:
            payment = item['payment']
            payments_data.append({
                'id': payment.id,
                'farmer_name': payment.farmer_name,
                'activity_name': payment.activity_name,
                'activity_date': str(payment.activity_date),
                'booking_value': float(payment.booking_value),
                'payment_status': payment.payment_status,
                'payment_route': payment.payment_route,
                'date_of_payment': str(payment.date_of_payment) if payment.date_of_payment else None,
                'village': payment.village,
                'acres': payment.acres,
                'reference_no': payment.reference_no,
                'description': payment.description,
                'match_suggestion': item['match_suggestion'],
                'confidence': item['confidence'],
                'score': item['score'],
                'reasons': item['reasons']
            })
    else:
        # Return all filtered payments without suggestions
        payments_data = []
        for payment in payments[:50]:
            payments_data.append({
                'id': payment.id,
                'farmer_name': payment.farmer_name,
                'activity_name': payment.activity_name,
                'activity_date': str(payment.activity_date),
                'booking_value': float(payment.booking_value),
                'payment_status': payment.payment_status,
                'payment_route': payment.payment_route,
                'date_of_payment': str(payment.date_of_payment) if payment.date_of_payment else None,
                'village': payment.village,
                'acres': payment.acres,
                'reference_no': payment.reference_no,
                'description': payment.description,
            })
    
    return Response({
        'count': len(payments_data),
        'payments': payments_data
    })
@api_view(['POST'])
@permission_classes([AllowAny])
def unlink_farmer_payment(request):
    """
    Unlink a farmer payment from a job activity.
    
    Body:
    {
        "farmer_payment_id": 123,
        "reason": "Wrong activity linked"
    }
    """
    
    farmer_payment_id = request.data.get('farmer_payment_id')
    reason = request.data.get('reason', 'No reason provided')
    
    if not farmer_payment_id:
        return Response({'error': 'farmer_payment_id is required'}, status=400)
    
    try:
        payment = FarmerPayment.objects.select_related('job_activity').get(id=farmer_payment_id)
    except FarmerPayment.DoesNotExist:
        return Response({'error': 'Farmer payment not found'}, status=404)
    
    # Check if linked
    if payment.job_activity is None:
        return Response({'error': 'This payment is not linked to any activity'}, status=400)
    
    # Get user
    user = request.user if request.user.is_authenticated else None
    username = user.username if user else 'System'
    
    # Store old values for log
    old_activity = payment.job_activity
    old_values = {
        'job_activity': f"{old_activity.job_id} - {old_activity.activity_name}",
        'is_matched': payment.is_matched
    }
    
    # Unlink payment
    payment.job_activity = None
    payment.is_matched = False
    
    # Update match notes
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    unlink_note = f"[{timestamp}] Unlinked by {username} from Job #{old_activity.job_id}. Reason: {reason}"
    
    if payment.match_notes:
        payment.match_notes += f"\n{unlink_note}"
    else:
        payment.match_notes = unlink_note
    
    payment.save()
    
    # ✅ Create Activity Log
    ActivityLog.objects.create(
        activity_type='payment_unlinked',  # ✅ Add this to ACTIVITY_TYPES choices
        description=f"Farmer payment ₹{payment.booking_value} unlinked from {old_activity.activity_name}",
        allocation=None,
        job_id=old_activity.job_id,
        mukkadam_id=0,
        mukkadam_name=payment.farmer_name,
        amount=payment.booking_value,
        performed_by=user,
        changes={
            'job_activity': {
                'old': old_values['job_activity'],
                'new': None
            },
            'is_matched': {
                'old': True,
                'new': False
            }
        },
        metadata={
            'farmer_payment_id': payment.id,
            'old_job_activity_id': old_activity.id,
            'farmer_name': payment.farmer_name,
            'reason': reason
        }
    )
    
    return Response({
        'success': True,
        'message': 'Payment unlinked successfully',
        'payment': {
            'id': payment.id,
            'farmer_name': payment.farmer_name,
            'booking_value': float(payment.booking_value),
            'is_matched': False
        }
    })


import requests
from django.conf import settings

# External API base URL
EXTERNAL_API_BASE = "http://localhost:8000"  # Or use settings.EXTERNAL_API_BASE_URL

def fetch_and_cache_mukkadam(mukkadam_id):
    """
    Fetch mukkadam details from external API and cache locally.
    Returns: (mukkadam_name, mukkadam_contact) tuple
    """
    try:
        # Check if already exists in local DB
        mukkadam = ImportedMukkadam.objects.filter(external_mukkadam_id=mukkadam_id).first()
        if mukkadam:
            return (mukkadam.team_name, mukkadam.contact_no)
        
        # Fetch from external API
        print(f"🔍 Fetching mukkadam #{mukkadam_id} from external API...")
        response = requests.get(
            f"{EXTERNAL_API_BASE}/api/mukkadam/minimal_list/",
            timeout=5
        )
        
        if response.status_code == 200:
            mukkadams = response.json()
            
            # Find the specific mukkadam
            for m in mukkadams:
                if m.get('id') == mukkadam_id:
                    # ✅ FIXED: Use correct field names from API
                    name = m.get('mukkadam_name') or m.get('team_name') or m.get('name') or f"Mukkadam #{mukkadam_id}"
                    contact = m.get('mobile_numbers') or m.get('contact_no') or m.get('phone') or ''
                    
                    # Cache it locally
                    mukkadam, created = ImportedMukkadam.objects.update_or_create(
                        external_mukkadam_id=mukkadam_id,
                        defaults={
                            'team_name': name,
                            'contact_no': contact,
                            'created_from_import': False
                        }
                    )
                    
                    print(f"✅ Cached mukkadam: {mukkadam.team_name} ({contact})")
                    return (mukkadam.team_name, mukkadam.contact_no)
        
        # If not found in API, create placeholder
        print(f"⚠️ Mukkadam #{mukkadam_id} not found in API, creating placeholder")
        mukkadam, created = ImportedMukkadam.objects.get_or_create(
            external_mukkadam_id=mukkadam_id,
            defaults={
                'team_name': f"Mukkadam #{mukkadam_id}",
                'contact_no': '',
                'created_from_import': False
            }
        )
        return (mukkadam.team_name, mukkadam.contact_no)
        
    except Exception as e:
        print(f"❌ Error fetching mukkadam #{mukkadam_id}: {e}")
        import traceback
        traceback.print_exc()
        return (f"Mukkadam #{mukkadam_id}", None)

def fetch_and_cache_transporter(transporter_id):
    """
    Fetch transporter details from external API and cache locally.
    Returns: transporter_name (str) or None
    """
    try:
        # Check if already exists in local DB
        transporter = ImportedTransporter.objects.filter(external_transporter_id=transporter_id).first()
        if transporter:
            return transporter.name
        
        # Fetch from external API (adjust endpoint as needed)
        print(f"🔍 Fetching transporter #{transporter_id} from external API...")
        response = requests.get(
            f"{EXTERNAL_API_BASE}/api/transporter/minimal_list/",  # Adjust endpoint
            timeout=5
        )
        
        if response.status_code == 200:
            transporters = response.json()
            
            # Find the specific transporter
            for t in transporters:
                if t.get('id') == transporter_id or t.get('transporter_id') == transporter_id:
                    # Cache it locally
                    transporter, created = ImportedTransporter.objects.update_or_create(
                        external_transporter_id=transporter_id,
                        defaults={
                            'name': t.get('name') or t.get('company_name') or f"Transporter #{transporter_id}",
                            'contact_no': t.get('contact_no') or t.get('phone') or '',
                            'created_from_import': False
                        }
                    )
                    
                    print(f"✅ Cached transporter: {transporter.name}")
                    return transporter.name
        
        # If not found in API, create placeholder
        transporter, created = ImportedTransporter.objects.get_or_create(
            external_transporter_id=transporter_id,
            defaults={
                'name': f"Transporter #{transporter_id}",
                'contact_no': '',
                'created_from_import': False
            }
        )
        return transporter.name
        
    except Exception as e:
        print(f"❌ Error fetching transporter #{transporter_id}: {e}")
        return f"Transporter #{transporter_id}"


@api_view(['GET'])
@permission_classes([AllowAny])
def get_job_details(request, job_id):
    """
    Get full breakdown of a specific job from LOCAL DB only (Fast).
    Includes farmer info, allocations, mukkadam/transporter details, and payment status.
    """
    
    # 1. Fetch all activities for this job with optimized prefetching
    activities = JobActivity.objects.filter(
        Q(job_id=job_id) | Q(farmer_work_id=job_id)
    ).prefetch_related(
        Prefetch(
            'allocations',
            queryset=Allocation.objects.select_related(
                'imported_mukkadam',
                'imported_transporter',
                'imported_farmer',
                'allocated_by'
            ).prefetch_related(
                Prefetch(
                    'payment_request',
                    queryset=PaymentRequest.objects.select_related('requested_by', 'paid_by')
                ),
                Prefetch(
                    'transport_payment_request',
                    queryset=TransportPaymentRequest.objects.select_related('requested_by', 'paid_by')
                )
            )
        ),
        Prefetch(
            'farmer_payments',
            queryset=FarmerPayment.objects.select_related('imported_farmer')
        )
    )

    if not activities.exists():
        return Response({'error': 'Job not found locally'}, status=404)

    # 2. Get farmer information from first activity
    first_activity = activities.first()
    farmer_info = None
    farmer_id = None
    
    # Try to get farmer from allocation's imported_farmer
    first_allocation = first_activity.allocations.first()
    if first_allocation and first_allocation.imported_farmer:
        farmer = first_allocation.imported_farmer
        farmer_info = {
            'farmer_id': farmer.external_farmer_id,
            'farmer_name': farmer.name,
            'contact_no': farmer.contact_no,
            'location': farmer.location,
            'is_dummy_id': farmer.is_dummy_id
        }
        farmer_id = farmer.external_farmer_id
    elif first_allocation and first_allocation.farmer_name:
        # Use farmer name/contact from allocation directly
        farmer_info = {
            'farmer_id': first_activity.farmer_work_id,
            'farmer_name': first_allocation.farmer_name,
            'contact_no': first_allocation.farmer_contact or '',
            'location': first_activity.location or '',
            'is_dummy_id': False
        }
        farmer_id = first_activity.farmer_work_id
    else:
        # Fallback: try to find farmer by external_farmer_id
        try:
            farmer = ImportedFarmer.objects.get(external_farmer_id=first_activity.farmer_work_id)
            farmer_info = {
                'farmer_id': farmer.external_farmer_id,
                'farmer_name': farmer.name,
                'contact_no': farmer.contact_no,
                'location': farmer.location,
                'is_dummy_id': farmer.is_dummy_id
            }
            farmer_id = farmer.external_farmer_id
        except ImportedFarmer.DoesNotExist:
            # Last resort: use job data
            farmer_info = {
                'farmer_id': first_activity.farmer_work_id,
                'farmer_name': 'Unknown',
                'contact_no': '',
                'location': first_activity.location or '',
                'is_dummy_id': False
            }
            farmer_id = first_activity.farmer_work_id

    # 3. Build activities data
    activities_data = []
    total_revenue = Decimal('0')
    total_allocated_cost = Decimal('0')

    for activity in activities:
        # Build allocations data
        allocs_data = []
        allocated_area = Decimal('0')
        activity_cost = Decimal('0')

        for alloc in activity.allocations.all():
            allocated_area += alloc.allocated_area
            
            # Calculate allocation cost
            alloc_total_cost = alloc.mukkadam_price + (alloc.transport_price or 0)
            activity_cost += alloc_total_cost

            # ✅ Get mukkadam name from ImportedMukkadam
            # ✅ Get mukkadam name from ImportedMukkadam (with auto-fetch)
            mukkadam_name = f"Mukkadam #{alloc.mukkadam_id}"
            mukkadam_contact = None

            if alloc.imported_mukkadam:
                mukkadam_name = alloc.imported_mukkadam.team_name
                mukkadam_contact = alloc.imported_mukkadam.contact_no
            else:
                # Try to fetch from ImportedMukkadam by external_mukkadam_id
                mukkadam = ImportedMukkadam.objects.filter(
                    external_mukkadam_id=alloc.mukkadam_id
                ).first()
                
                if mukkadam:
                    mukkadam_name = mukkadam.team_name
                    mukkadam_contact = mukkadam.contact_no
                else:
                    # ✅ FETCH FROM EXTERNAL API AND CACHE
                    mukkadam_name, mukkadam_contact = fetch_and_cache_mukkadam(alloc.mukkadam_id)

            # ✅ Get transporter name from ImportedTransporter (with auto-fetch)
            transporter_name = None
            transporter_contact = None

            if alloc.transport_type == 'provider' and alloc.transport_provider_id:
                if alloc.imported_transporter:
                    transporter_name = alloc.imported_transporter.name
                    transporter_contact = alloc.imported_transporter.contact_no
                else:
                    # Try to fetch from ImportedTransporter by external_transporter_id
                    transporter = ImportedTransporter.objects.filter(
                        external_transporter_id=alloc.transport_provider_id
                    ).first()
                    
                    
            # Get payment statuses
            mukkadam_payment_status = None
            transport_payment_status = None
            
            try:
                if hasattr(alloc, 'payment_request'):
                    mukkadam_payment_status = {
                        'status': alloc.payment_request.status,
                        'requested_at': alloc.payment_request.requested_at.isoformat() if alloc.payment_request.requested_at else None,
                        'paid_at': alloc.payment_request.paid_at.isoformat() if alloc.payment_request.paid_at else None,
                        'requested_amount': float(alloc.payment_request.requested_amount),
                        'requested_by': alloc.payment_request.requested_by.username if alloc.payment_request.requested_by else None,
                        'paid_by': alloc.payment_request.paid_by.username if alloc.payment_request.paid_by else None
                    }
            except PaymentRequest.DoesNotExist:
                pass

            try:
                if hasattr(alloc, 'transport_payment_request') and alloc.transport_type == 'provider':
                    transport_payment_status = {
                        'status': alloc.transport_payment_request.status,
                        'requested_at': alloc.transport_payment_request.requested_at.isoformat() if alloc.transport_payment_request.requested_at else None,
                        'paid_at': alloc.transport_payment_request.paid_at.isoformat() if alloc.transport_payment_request.paid_at else None,
                        'requested_amount': float(alloc.transport_payment_request.requested_amount),
                        'requested_by': alloc.transport_payment_request.requested_by.username if alloc.transport_payment_request.requested_by else None,
                        'paid_by': alloc.transport_payment_request.paid_by.username if alloc.transport_payment_request.paid_by else None
                    }
            except TransportPaymentRequest.DoesNotExist:
                pass

            # Build allocation object
            allocs_data.append({
                'allocation_id': alloc.id,
                
                # Mukkadam Details
                'mukkadam_id': alloc.mukkadam_id,
                'mukkadam_name': mukkadam_name,
                'mukkadam_contact': mukkadam_contact,
                
                # Allocation Details
                'allocated_area': float(alloc.allocated_area),
                'crew_size': alloc.crew_size,
                'mukkadam_price': float(alloc.mukkadam_price),
                
                # Transport Details
                'transport_type': alloc.transport_type,
                'transport_price': float(alloc.transport_price or 0),
                'transport_provider_id': alloc.transport_provider_id,
                'transporter_name': transporter_name,
                'transporter_contact': transporter_contact,
                
                # Work Details
                'work_date': str(alloc.work_date) if alloc.work_date else None,
                'status': alloc.status,
                'allocated_by': alloc.allocated_by.username if alloc.allocated_by else None,
                'allocated_at': alloc.allocated_at.isoformat() if alloc.allocated_at else None,
                'total_cost': float(alloc_total_cost),
                
                # ✅ POC Information (from Allocation model)
                'farmer_name': alloc.farmer_name,
                'farmer_contact': alloc.farmer_contact,
                'farmer_poc_id': alloc.farmer_poc_id,
                'farmer_poc': alloc.farmer_poc,
                'labour_poc_id': alloc.labour_poc_id,
                'labour_poc': alloc.labour_poc,
                'field_poc_id': alloc.field_poc_id,
                'field_poc': alloc.field_poc,
                
                # Payment statuses
                'mukkadam_payment': mukkadam_payment_status,
                'transport_payment': transport_payment_status,
                'notes': alloc.notes
            })

        total_allocated_cost += activity_cost
        revenue = activity.total_price + activity.transport_cost + activity.other_cost
        total_revenue += revenue # Include transport cost in revenue if exists 

        # Get farmer payments for this activity
        farmer_payments_data = []
        total_farmer_paid = Decimal('0')
        total_farmer_pending = Decimal('0')
        last_payment_date = None
        
        for fp in activity.farmer_payments.all():
            farmer_payments_data.append({
                'payment_id': fp.id,
                'booking_value': float(fp.booking_value),
                'payment_status': fp.payment_status,
                'payment_route': fp.payment_route,
                'date_of_payment': str(fp.date_of_payment) if fp.date_of_payment else None,
                'activity_date': str(fp.activity_date),
                'reference_no': fp.reference_no,
                'description': fp.description,
                'village': fp.village,
                'acres': fp.acres
            })
            
            if fp.payment_status == 'paid':
                total_farmer_paid += fp.booking_value
                if fp.date_of_payment:
                    if not last_payment_date or fp.date_of_payment > last_payment_date:
                        last_payment_date = fp.date_of_payment
            else:
                total_farmer_pending += fp.booking_value

        # Calculate farmer payment summary for this activity
        total_expected = total_farmer_paid + total_farmer_pending
        farmer_payment_summary = {
            'total_expected': float(total_expected),
            'total_paid': float(total_farmer_paid),
            'total_pending': float(total_farmer_pending),
            'payment_count': len(farmer_payments_data),
            'paid_count': sum(1 for p in farmer_payments_data if p['payment_status'] == 'paid'),
            'pending_count': sum(1 for p in farmer_payments_data if p['payment_status'] == 'pending'),
            'last_payment_date': str(last_payment_date) if last_payment_date else None,
            'completion_percentage': round(
                (float(total_farmer_paid) / float(total_expected) * 100) 
                if total_expected > 0 else 0, 
                2
            ),
            'payments': farmer_payments_data
        }

        # Build activity object
        activities_data.append({
            'id': activity.id,
            'activity_id': activity.activity_id,
            'activity_name': activity.activity_name,
            'activity_type': activity.activity_type,
            'scheduled_datetime': activity.scheduled_datetime.isoformat() if activity.scheduled_datetime else None,
            'total_area': float(activity.total_area),
            'allocated_area': float(allocated_area),
            'remaining_area': float(activity.total_area - allocated_area),
            'rate_per_acre': float(activity.rate_per_acre),
            'total_price': float(revenue),
            'transport_cost': float(activity.transport_cost),
            'others_cost': float(activity.other_cost),
            'location': activity.location,
            'is_fully_allocated': allocated_area >= activity.total_area,
            'activity_cost': float(activity.total_price + activity.transport_cost +activity.other_cost), # Revenue minus other costs (excluding transport which is part of revenue),
            'activity_profit': float(revenue - activity_cost),
            'allocations': allocs_data,
            'farmer_payments': farmer_payment_summary
        })

    # 4. Calculate overall job financials
    total_profit = total_revenue - total_allocated_cost
    profit_margin = (float(total_profit) / float(total_revenue) * 100) if total_revenue > 0 else 0

    # 5. Build response
    response_data = {
        'work_id': job_id,
        'job_id': first_activity.job_id,
        'farmer_work_id': first_activity.farmer_work_id,
        'title': f"Job #{job_id}",
        'farmer': farmer_info,
        'farmer_id': farmer_id,
        'activities': activities_data,
        'summary': {
            'total_activities': len(activities_data),
            'total_allocations': sum(len(act['allocations']) for act in activities_data),
            'total_revenue': float(total_revenue),
            'total_cost': float(total_allocated_cost),
            'total_profit': float(total_profit),
            'profit_margin': round(profit_margin, 2)
        }
    }

    return Response(response_data)

# allocation/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import datetime 


from .recomm import process_mukkadam_recommendations,fetch_enriched_mukkadam_data


class DetailedRecommendationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        POST /ap/detailed-recommendations/
        
        Request Body:
        {
            "work_date": "2025-01-20",
            "farmer_id": "12345",  # optional
            "activity_name": "Pruning",  # optional
            "location": "Niphad, Nashik"  # optional
        }
        
        Response:
        {
            "available_on_date": [...],
            "nearby_logistics": [...],
            "farmer_history": [...],
            "activity_experts": [...],
            "high_volume": [...],
            "new_local_recruits": [...],
            "overall_best": [...]
        }
        """
        try:
            data = request.data
            
            # Validate work_date
            work_date_str = data.get('work_date')
            if not work_date_str:
                return Response({
                    "error": "work_date is required (format: YYYY-MM-DD)"
                }, status=400)
            
            try:
                work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    "error": "Invalid date format. Use YYYY-MM-DD"
                }, status=400)
            
            # Build target requirement
# Build target requirement
            # ... inside post method ...

            # --- REPLACE THIS SECTION ---
            # Build target requirement
            job_lat = data.get('job_latitude')
            job_lon = data.get('job_longitude')

            # Helper function to safely parse floats
            def safe_float(val):
                try:
                    # Check for empty string or None before converting
                    if val in [None, '', 'null']: 
                        return None
                    return float(val)
                except (ValueError, TypeError):
                    return None

            target_req = {
                'date': work_date,
                'farmer_id': str(data.get('farmer_id', '')),
                'activity_name': data.get('activity_name', ''),
                'location_str': data.get('location', ''),
                'job_latitude': safe_float(job_lat),  # ✅ Use safe conversion
                'job_longitude': safe_float(job_lon)  # ✅ Use safe conversion
            }
            # -----------------------------
            
            # 1. Fetch enriched mukkadam data
            print(f"🔍 Fetching mukkadam data for recommendations...")
            all_mukkadams = fetch_enriched_mukkadam_data()
            print(f"✅ Loaded {len(all_mukkadams)} mukkadams")
            
            # 2. Process recommendations
            print(f"🧠 Processing recommendations for {work_date_str}...")
            result_buckets = process_mukkadam_recommendations(all_mukkadams, target_req)
            
            # 3. Add metadata
            response_data = {
                **result_buckets,
                'metadata': {
                    'total_mukkadams_analyzed': len(all_mukkadams),
                    'target_date': work_date_str,
                    'target_activity': target_req['activity_name'],
                    'target_location': target_req['location_str'],
                    'target_farmer_id': target_req['farmer_id']
                }
            }
            
            print(f"✅ Recommendations generated successfully")
            return Response(response_data)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                "error": str(e),
                "detail": "Failed to generate recommendations"
            }, status=500)

# allocation_app/views.py
from .models import ActivityEditHistory,ActivityLostRecord
from .serializers import JobActivitySerializer,ActivityEditHistorySerializer,ActivityLostRecordSerializer
# allocation_app/views.py

# REPLACE the entire edit_activity function (around line 450):
from datetime import datetime, date
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal

from .models import JobActivity, ActivityEditHistory, ActivityLog
from .serializers import JobActivitySerializer


from datetime import datetime, date
from decimal import Decimal
from django.utils import timezone


def make_aware_if_needed(value):
    if isinstance(value, datetime) and timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def parse_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return make_aware_if_needed(value)


def serialize_for_log(value):
    """
    Ensure JSON-safe values
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return value
@api_view(['PATCH'])
@permission_classes([AllowAny])
def edit_activity(request):
    """
    Edit activity - with allocation area validation and auto-status update
    """
    try:
        # Auth checks...
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not getattr(request.user, 'is_admin', False) and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can edit activities'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Input data...
        job_id = request.data.get('job_id')
        activity_id = request.data.get('activity_id')
        updates = request.data.get('updates', {})
        reason = request.data.get('reason', '').strip()

        if not job_id or not activity_id or not updates or not reason:
            return Response(
                {'error': 'job_id, activity_id, updates, and reason are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get activity name
        activity_name = updates.get('activity_name')
        
        # ✅ Find existing JobActivity
        existing_ja = None
        
        if activity_name:
            existing_ja = JobActivity.objects.filter(
                job_id=str(job_id),
                activity_name__iexact=activity_name
            ).first()
        
        if not existing_ja:
            existing_ja = JobActivity.objects.filter(
                job_id=str(job_id),
                activity_id=str(activity_id)
            ).first()

        if not existing_ja:
            return Response(
                {'error': 'Activity not found. Cannot edit non-existent activity.'},
                status=status.HTTP_404_NOT_FOUND
            )

        job_activity = existing_ja
        print(f"✅ Found existing JobActivity #{job_activity.id}")
        print(f"   Current total_area: {job_activity.total_area}")
        print(f"   Current allocated_area: {job_activity.allocated_area}")

        # ✅ VALIDATION: Check if new total_area is valid
        new_total_area = updates.get('total_area') or updates.get('acres')
        if new_total_area is not None:
            new_total_area = Decimal(str(new_total_area))
            current_allocated = job_activity.allocated_area or Decimal('0')
            
            print(f"   New total_area: {new_total_area}")
            print(f"   Allocated area: {current_allocated}")
            
            # ❌ Prevent reducing area below allocated amount
            if new_total_area < current_allocated:
                return Response(
                    {
                        'error': f'Cannot reduce total area to {new_total_area} acres. '
                                f'{current_allocated} acres already allocated. '
                                f'Please remove allocations first.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Parse datetime
        scheduled_dt = updates.get('scheduled_datetime') or updates.get('scheduled_date')
        if scheduled_dt:
            scheduled_dt = parse_datetime(scheduled_dt)

        # Calculate costs
        mukkadam_price = Decimal(str(updates.get('total_price', job_activity.total_price or 0)))
        transport_cost = Decimal(str(updates.get('transport_cost', job_activity.transport_cost or 0)))
        other_cost = Decimal(str(updates.get('other_cost', job_activity.other_cost or 0)))
        calculated_subtotal = mukkadam_price + transport_cost + other_cost

        # Field mapping
        field_mapping = {
            'activity_name': 'activity_name',
            'total_area': 'total_area',
            'acres': 'total_area',
            'scheduled_datetime': 'scheduled_datetime',
            'scheduled_date': 'scheduled_datetime',
            'date_time': 'scheduled_datetime',
            'total_price': 'total_price',
            'transport_cost': 'transport_cost',
            'other_cost': 'other_cost',
            'rate_per_acre': 'rate_per_acre',
        }

        changes = {}

        # Build changes
        for api_field, db_field in field_mapping.items():
            if api_field not in updates:
                continue

            new_value = updates[api_field]
            old_value = getattr(job_activity, db_field, None)

            # Decimal fields
            if db_field in ['total_area', 'total_price', 'transport_cost', 'other_cost', 'rate_per_acre']:
                old_comp = str(old_value) if old_value is not None else None
                new_comp = str(new_value)

            # Datetime field
            elif db_field == 'scheduled_datetime':
                new_value = parse_datetime(new_value)
                old_value = make_aware_if_needed(old_value)
                old_comp = serialize_for_log(old_value)
                new_comp = serialize_for_log(new_value)

            # Other fields
            else:
                old_comp = old_value
                new_comp = new_value

            if old_comp != new_comp:
                changes[db_field] = {
                    'old_value': serialize_for_log(old_value),
                    'new_value': serialize_for_log(new_value)
                }

        # Check subtotal change
        old_subtotal = job_activity.subtotal
        if str(old_subtotal) != str(calculated_subtotal):
            changes['subtotal'] = {
                'old_value': str(old_subtotal),
                'new_value': str(calculated_subtotal)
            }

        if not changes:
            return Response(
                {'message': 'No changes detected'},
                status=status.HTTP_200_OK
            )

        # Apply updates to job_activity
        for field, change in changes.items():
            value = change['new_value']

            if field == 'scheduled_datetime':
                value = parse_datetime(value)
            elif field in ['total_area', 'total_price', 'transport_cost', 'other_cost', 'subtotal', 'rate_per_acre']:
                value = Decimal(str(value))

            setattr(job_activity, field, value)

        job_activity.is_manually_edited = True
        job_activity.save()

        # ✅ NEW: Update allocation statuses if total_area changed
        if 'total_area' in changes:
            print(f"\n🔄 Total area changed, updating allocation statuses...")
            
            new_total = job_activity.total_area
            allocated = job_activity.allocated_area or Decimal('0')
            
            print(f"   New total: {new_total}, Allocated: {allocated}")
            
            # Update all allocations for this activity
            allocations = job_activity.allocations.all()
            
            for alloc in allocations:
                old_status = alloc.status
                
                # Calculate if this activity is now fully allocated
                if allocated >= new_total:
                    # Fully allocated
                    if alloc.status in ['allocated', 'partially_allocated']:
                        alloc.status = 'allocated'  # Full coverage
                        print(f"   📊 Allocation #{alloc.id}: {old_status} → allocated (full coverage)")
                else:
                    # Partially allocated
                    if alloc.status == 'allocated':
                        alloc.status = 'partially_allocated'
                        print(f"   📊 Allocation #{alloc.id}: {old_status} → partially_allocated")
                
                alloc.save()
            
            print(f"   ✅ Updated {allocations.count()} allocation(s)")

        # Create edit history
        ActivityEditHistory.objects.create(
            job_activity=job_activity,
            edited_by=request.user,
            reason=reason,
            changes=changes
        )

        # Update ImportedJobSheet link
        ImportedJobSheet.objects.filter(
            generated_job_id=str(job_id),
            activity_name__iexact=job_activity.activity_name
        ).update(job_activity=job_activity)

        # Activity log
        ActivityLog.objects.create(
            allocation=None,
            activity_type='activity_marked_edited',
            performed_by=request.user,
            description=f"Activity '{job_activity.activity_name}' edited.",
            job_id=job_id,
            mukkadam_id=0,
            mukkadam_name='N/A (Job-level)',
            transport_provider_id=None,
            transport_name=None,
            metadata={
                'job_id': job_id,
                'activity_id': activity_id,
                'activity_name': job_activity.activity_name,
                'changes': changes,
                'reason': reason,
                'cost_breakdown': {
                    'mukkadam_price': str(mukkadam_price),
                    'transport_cost': str(transport_cost),
                    'other_cost': str(other_cost),
                    'subtotal': str(calculated_subtotal)
                },
                'allocation_status_updated': 'total_area' in changes
            }
        )

        # Refresh to get latest data
        job_activity.refresh_from_db()

        return Response(
            {
                'success': True,
                'message': 'Activity updated successfully',
                'activity': JobActivitySerializer(job_activity).data,
                'allocation_status_updated': 'total_area' in changes,
                'current_status': {
                    'total_area': float(job_activity.total_area),
                    'allocated_area': float(job_activity.allocated_area),
                    'remaining_area': float(job_activity.remaining_area),
                    'is_fully_allocated': job_activity.allocated_area >= job_activity.total_area
                }
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# REPLACE the mark_activity_lost function:

@api_view(['POST'])
@permission_classes([AllowAny])
def mark_activity_lost(request):
    """
    Mark activity as lost - creates JobActivity if missing
    """
    try:
        # Check admin permission
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        if not getattr(request.user, 'is_admin', False) and not request.user.is_superuser:
            return Response({'error': 'Only admins can mark activities as lost'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get data
        job_id = request.data.get('job_id')
        activity_id = request.data.get('activity_id')
        reason = request.data.get('reason', '').strip()
        
        # Validate
        if not job_id or not activity_id or not reason:
            return Response(
                {'error': 'job_id, activity_id, and reason are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ GET OR CREATE JobActivity
        job_activity, created = JobActivity.objects.get_or_create(
            job_id=str(job_id),
            activity_id=str(activity_id),
            defaults={
                'activity_name': request.data.get('activity_name', 'Unknown Activity'),
                'activity_type': '',
                'scheduled_datetime': timezone.now(),
                'total_area': Decimal(str(request.data.get('total_area', 0))),
                'total_price': Decimal(str(request.data.get('total_price', 0))),
                'transport_cost': Decimal('0'),
                'other_cost': Decimal('0'),
                'subtotal': Decimal(str(request.data.get('total_price', 0))),
                'location': '',
                'estimated_workers': 10,
                'rate_per_acre': Decimal('0'),
                'is_manually_edited': False  # Lost activities don't count as edited
            }
        )
        
        if created:
            print(f"✅ Created new JobActivity for lost marking: {job_id} - {activity_id}")
        
        # ✅ CHECK IF ALREADY LOST
        if hasattr(job_activity, 'lost_record') and job_activity.lost_record.is_active:
            return Response({'error': 'Activity is already marked as lost'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ CREATE LOST RECORD
        lost_record, _ = ActivityLostRecord.objects.update_or_create(
            job_activity=job_activity,
            defaults={
                'marked_by': request.user,
                'marked_at': timezone.now(),
                'reason': reason,
                'is_active': True,
                'unmarked_by': None,
                'unmarked_at': None,
                'unmark_reason': None
            }
        )
        
        # WITH THIS (add required fields with null/empty values):
        ActivityLog.objects.create(
            allocation=None,
            activity_type='activity_marked_lost',
            performed_by=request.user,
            description=f"Activity '{job_activity.activity_name}' marked as LOST.",
            job_id=job_id,  # ✅ ADD
            mukkadam_id=0,  # ✅ ADD (0 or -1 means no mukkadam)
            mukkadam_name='N/A (Job-level)',  # ✅ ADD
            transport_provider_id=None,  # ✅ ADD
            transport_name=None,  # ✅ ADD
            
            metadata={
                'job_id': job_id,
                'activity_id': activity_id,
                'activity_name': job_activity.activity_name,
                'reason': reason,
                'total_price': float(job_activity.total_price)
            }
        )
        
        print(f"\n🚫 Activity Marked as LOST")
        print(f"   Job: {job_id}, Activity: {activity_id}")
        
        return Response({
            'success': True,
            'message': 'Activity marked as lost successfully',
            'lost_record': ActivityLostRecordSerializer(lost_record).data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated in production
def unmark_activity_lost(request):
    """
    Unmark activity as lost (restore it)
    
    Payload:
    {
        "job_id": "616",
        "activity_id": "183",
        "reason": "Farmer changed mind, work will proceed"
    }
    """
    try:
        # ✅ CHECK ADMIN PERMISSION
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not getattr(request.user, 'is_admin', False) and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can unmark lost activities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get data
        job_id = request.data.get('job_id')
        activity_id = request.data.get('activity_id')
        reason = request.data.get('reason', '').strip()
        
        # Validate
        if not job_id or not activity_id:
            return Response(
                {'error': 'job_id and activity_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {'error': 'Reason is required for unmarking activity'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find activity
        try:
            job_activity = JobActivity.objects.get(
                job_id=str(job_id),
                activity_id=str(activity_id)
            )
        except JobActivity.DoesNotExist:
            return Response(
                {'error': f'Activity not found: job_id={job_id}, activity_id={activity_id}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ CHECK IF MARKED LOST
        if not hasattr(job_activity, 'lost_record') or not job_activity.lost_record.is_active:
            return Response(
                {'error': 'Activity is not marked as lost'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ UNMARK
        lost_record = job_activity.lost_record
        lost_record.is_active = False
        lost_record.unmarked_by = request.user
        lost_record.unmarked_at = timezone.now()
        lost_record.unmark_reason = reason
        lost_record.save()
        
        # ✅ CREATE ACTIVITY LOG ENTRY
        ActivityLog.objects.create(
            allocation=None,
            activity_type='activity_marked_restored',
            performed_by=request.user,
            description=f"Activity '{job_activity.activity_name}' marked as Restored.",
            job_id=job_id,  # ✅ ADD
            mukkadam_id=0,  # ✅ ADD (0 or -1 means no mukkadam)
            mukkadam_name='N/A (Job-level)',  # ✅ ADD
            transport_provider_id=None,  # ✅ ADD
            transport_name=None,  # ✅ ADD
            metadata={
                'job_id': job_id,
                'activity_id': activity_id,
                'activity_name': job_activity.activity_name,
                'reason': reason
            }
        )
        
        print(f"\n✅ Activity UNMARKED as Lost (Restored)")
        print(f"   Job ID: {job_id}")
        print(f"   Activity: {job_activity.activity_name}")
        print(f"   Reason: {reason}")
        
        return Response({
            'success': True,
            'message': 'Activity restored successfully',
            'lost_record': ActivityLostRecordSerializer(lost_record).data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error unmarking activity: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)