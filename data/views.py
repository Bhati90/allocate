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

from .models import JobActivity, Allocation, AllocationStats
from .serializers import (
    JobActivitySerializer,
    AllocationSerializer,
    AllocationStatsSerializer
)

# External API base URL
EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'

SUPPLY_API_URL = 'https://supply.bharatintelligence.ai' # Change to your actual Supply App URL
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


class AllocationViewSet(viewsets.ModelViewSet):
    queryset = Allocation.objects.all()
    serializer_class = AllocationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Allocation.objects.all()

        # Filter by mukkadam_id
        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        # Filter by work_date
        work_date = self.request.query_params.get('work_date')
        if work_date:
            queryset = queryset.filter(work_date=work_date)

        return queryset.select_related('job_activity', 'allocated_by')

    def create(self, request, *args, **kwargs):
        """Create allocation for any activity type"""
        print("="*80)
        print("📥 ALLOCATION REQUEST RECEIVED")
        print("="*80)
        print(f"Raw data: {request.data}")

        activity_id = request.data.get('activity_id')

        if not activity_id:
            return Response(
                {'error': 'activity_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # First, try to find existing JobActivity by database ID
            job_activity = JobActivity.objects.filter(pk=activity_id).first()

            # If not found, try to find by job_id + activity_id (external ID)
            if not job_activity:
                print(f"⚠️ JobActivity with pk={activity_id} not found, checking by external ID...")

                # Get job_id from request or from activity
                job_id = request.data.get('job_id')

                if not job_id:
                    # Try to extract from the activity_id itself if it's a string like "job123_activity456"
                    # Or fetch from external API
                    return Response(
                        {'error': 'JobActivity not found in database. Please provide job_id to auto-create.'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Try to find by job_id and external activity_id
                job_activity = JobActivity.objects.filter(
                    job_id=str(job_id),
                    activity_id=str(activity_id)
                ).first()

                if not job_activity:
                    print(f"🔨 Creating new JobActivity for job_id={job_id}, activity_id={activity_id}")

                    # Create JobActivity from request data
                    job_activity = JobActivity.objects.create(
                        job_id=str(job_id),
                        activity_id=str(activity_id),
                        activity_name=request.data.get('activity_name', 'Unknown Activity'),
                        activity_type=request.data.get('activity_type', ''),
                        scheduled_datetime=request.data.get('scheduled_datetime') or timezone.now(),
                        total_area=Decimal(str(request.data.get('total_area', 0))),
                        total_price=Decimal(str(request.data.get('total_price', 0))),
                        transport_cost=Decimal(str(request.data.get('transport_cost', 0))),
                        other_cost=Decimal(str(request.data.get('other_cost', 0))),
                        subtotal=Decimal(str(request.data.get('subtotal', 0))),
                        location=request.data.get('location', ''),
                        estimated_workers=int(request.data.get('estimated_workers', 10)),
                        rate_per_acre=Decimal(str(request.data.get('rate_per_acre', 0)))
                    )
                    print(f"✅ Created JobActivity #{job_activity.id}")

            print(f"✅ Found/Created Activity: {job_activity.activity_name} ({job_activity.total_area} acres)")

        except JobActivity.DoesNotExist:
            return Response(
                {'error': f'Activity with id {activity_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error finding/creating JobActivity: {str(e)}")
            return Response(
                {'error': f'Error processing activity: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Prepare data
        data = request.data.copy()
        data['job_activity'] = job_activity.id  # Use the database ID
        data.pop('activity_id', None)
        data.pop('job_id', None)  # Remove these since we've processed them

        # Convert to Decimal for comparison
        allocated_area = Decimal(str(data.get('allocated_area', 0)))

        # Validate allocated area doesn't exceed remaining
        if allocated_area > job_activity.remaining_area:
            return Response(
                {'error': f'Cannot allocate {allocated_area} acres. Only {job_activity.remaining_area} acres remaining.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create allocation
        serializer = self.get_serializer(data=data)

        if not serializer.is_valid():
            print(f"❌ VALIDATION FAILED: {serializer.errors}")
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user and request.user.is_authenticated:
            allocation = serializer.save(allocated_by=request.user)
        else:
            allocation = serializer.save()

        # Update JobActivity allocated_area
        job_activity.allocated_area = job_activity.allocated_area + allocated_area
        job_activity.save()

        # 3. ✅ NEW: Trigger WhatsApp Notifications
        self._send_whatsapp_notifications(allocation)
        
        print("="*80)
        print("✅ ALLOCATION CREATED")
        print("="*80)
        print(f"   Job: {allocation.job_activity.job_id}")
        print(f"   Activity: {allocation.job_activity.activity_name}")
        print(f"   Area: {allocation.allocated_area} acres")
        print(f"   Remaining: {job_activity.remaining_area} acres")
        print(f"   Crew: {allocation.crew_size or 'Default'} workers")
        print(f"   Total Cost: ₹{allocation.total_cost}")
        print("="*80)

        return Response(
            {
                'message': 'Allocation created successfully',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    def _send_whatsapp_notifications(self, allocation):
        """Helper to trigger notifications for Mukkadam and Transporter"""
        try:
            from .services import WhatsAppService
            # A. Notify Mukkadam
            WhatsAppService.send_allocation_to_mukkadam(allocation)
            print(f"📲 WhatsApp sent to Mukkadam: {allocation.mukkadam_id}")

            # B. Notify Transporter (if assigned)
            if hasattr(allocation, 'transport_provider_id') :
                WhatsAppService.send_allocation_to_transporter(allocation)
                print(f"📲 WhatsApp sent to Transporter: {allocation.transport_provider_id}")

        except Exception as e:
            logger.error(f"⚠️ WhatsApp Notification Flow failed: {str(e)}")
    def destroy(self, request, *args, **kwargs):
        """Delete allocation and update activity allocated_area"""
        allocation = self.get_object()
        job_activity = allocation.job_activity

        # Reduce allocated area
        allocated_area = Decimal(str(allocation.allocated_area))
        job_activity.allocated_area = job_activity.allocated_area - allocated_area
        job_activity.save()

        print(f"✅ Allocation deleted. {job_activity.remaining_area} acres now available for {job_activity.activity_name}")

        return super().destroy(request, *args, **kwargs)


    def perform_create(self, serializer):
        allocation = super().perform_create(serializer)
        # Clear mukkadam cache when new allocation is created
        clear_mukkadam_cache(allocation.mukkadam_id)
        return allocation
    

from .models import JobActivity, Allocation, AllocationStats  # ✅ CORRECT

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from .models import PaymentRequest, TransportPaymentRequest, Allocation
from .serializers import PaymentRequestSerializer, TransportPaymentRequestSerializer

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
            return Response(
                {
                    'error': 'Payment request already exists for this allocation',
                    'existing_request': PaymentRequestSerializer(allocation.payment_request).data
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

        serializer = self.get_serializer(payment_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

        # In PaymentRequestViewSet
    # In PaymentRequestViewSet

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

        payment_request.status = 'rejected'
        payment_request.save()

        # ✅ FIX: Use ActivityLog
        ActivityLog.objects.create(
            activity_type='payment_rejected',
            description=request.data.get('rejection_reason', 'Payment request rejected'),
            payment_request=payment_request,
            allocation=payment_request.allocation,
            performed_by=request.user if request.user.is_authenticated else None,
            job_id=payment_request.allocation.farmer_work_id,
            mukkadam_id=payment_request.mukkadam_id,
            amount=payment_request.requested_amount
        )
        serializer = self.get_serializer(payment_request)
        return Response({
            'message': 'Payment request rejected successfully',
            'payment_request': serializer.data
        })

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark payment as paid"""
        payment_request = self.get_object()
        payment_request.status = 'paid'
        payment_request.paid_at = timezone.now()
        payment_request.paid_by = request.user if request.user.is_authenticated else None
        payment_request.save()
        # Update allocation status
        allocation = payment_request.allocation
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
            amount=payment_request.requested_amount
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
            timeout=20
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
                        timeout=20
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

@api_view(['GET'])
@permission_classes([AllowAny])
def activity_logs_list(request):
    """
    Get all activity logs with external data enriched
    OPTIMIZED with caching + async
    """
    import time
    start_time = time.time()

    # Get query parameters
    activity_type = request.query_params.get('activity_type')
    mukkadam_id = request.query_params.get('mukkadam_id')
    job_id = request.query_params.get('job_id')
    days = request.query_params.get('days', 30)  # Default last 30 days

    print(f"🔍 Filters: activity_type={activity_type}, mukkadam_id={mukkadam_id}, job_id={job_id}, days={days}")

    # Build queryset
    queryset = ActivityLog.objects.all()

    if activity_type:
        queryset = queryset.filter(activity_type=activity_type)
    if mukkadam_id:
        queryset = queryset.filter(mukkadam_id=mukkadam_id)
    if job_id:
        queryset = queryset.filter(job_id=job_id)

    # Filter by date range
    if days:
        from_date = timezone.now() - timedelta(days=int(days))
        queryset = queryset.filter(performed_at__gte=from_date)

    queryset = queryset.select_related('performed_by').order_by('-performed_at')[:200]  # Limit to last 200

    # Convert to list to iterate multiple times
    logs_queryset = list(queryset)

    print(f"📊 Found {len(logs_queryset)} activity logs")

    if not logs_queryset:
        return Response([])

    # ========================================
    # ✅ STEP 1: COLLECT ALL UNIQUE IDs
    # ========================================
    mukkadam_ids = set()
    transport_provider_ids = set()

    for log in logs_queryset:
        if log.mukkadam_id:
            mukkadam_ids.add(log.mukkadam_id)
        if log.transport_provider_id:
            transport_provider_ids.add(log.transport_provider_id)

    print(f"   Unique mukkadams: {len(mukkadam_ids)}")
    print(f"   Unique transport providers: {len(transport_provider_ids)}")

    # ========================================
    # ✅ STEP 2: BATCH FETCH ALL DATA IN PARALLEL
    # ========================================
    print("\n⚡ PARALLEL BATCH FETCHING...")
    batch_start = time.time()

    mukkadams_cache = {}
    transport_providers_cache = {}

    if mukkadam_ids:
        mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=15)

    if transport_provider_ids:
        transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=10)

    batch_elapsed = time.time() - batch_start
    print(f"✅ Batch fetching completed in {batch_elapsed:.2f}s")

    # ========================================
    # STEP 3: BUILD LOGS WITH CACHED DATA
    # ========================================
    print("\n🔄 Building enriched logs...")

    logs = []
    for log in logs_queryset:
        # Get mukkadam name from cache
        mukkadam_name = 'Unknown'
        if log.mukkadam_id:
            mukkadam_data = mukkadams_cache.get(log.mukkadam_id)
            if mukkadam_data:
                mukkadam_name = mukkadam_data.get('mukkadam_name', f'Mukkadam #{log.mukkadam_id}')
            else:
                mukkadam_name = f'Mukkadam #{log.mukkadam_id}'

        # Get transport provider name from cache
        transport_name = None
        transport_details = None
        if log.transport_provider_id:
            transport_data = transport_providers_cache.get(log.transport_provider_id)
            if transport_data:
                transport_name = transport_data.get('name', f'Provider #{log.transport_provider_id}')
                transport_details = transport_data
            else:
                transport_name = f'Provider #{log.transport_provider_id}'

        logs.append({
            'id': log.id,
            'activity_type': log.activity_type,
            'activity_type_display': log.get_activity_type_display(),
            'description': log.description,
            'job_id': log.job_id,
            'mukkadam_id': log.mukkadam_id,
            'mukkadam_name': mukkadam_name,
            'transport_provider_id': log.transport_provider_id,
            'transport_name': transport_name,
            'transport_details': transport_details,  # ✅ Full transport provider details
            'amount': float(log.amount) if log.amount else None,
            'performed_by_name': log.performed_by.username if log.performed_by else 'System',
            'performed_at': log.performed_at.isoformat(),
            'metadata': log.metadata,
        })

    total_elapsed = time.time() - start_time
    print(f"\n✅ Activity logs API completed in {total_elapsed:.2f}s")
    print(f"   Database query + build: {total_elapsed - batch_elapsed:.2f}s")
    print(f"   Batch fetching: {batch_elapsed:.2f}s")
    print("="*80)

    return Response({
        'count': len(logs),
        'logs': logs,
        'performance': {
            'total_time': f'{total_elapsed:.2f}s',
            'batch_fetch_time': f'{batch_elapsed:.2f}s',
            'mukkadams_fetched': len(mukkadams_cache),
            'providers_fetched': len(transport_providers_cache)
        }
    })

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

# Import your models
# from .models import Allocation, ActivityLog

@api_view(['GET'])
@permission_classes([AllowAny])
def jobs_list(request):
    """
    Fetch jobs from external API and enrich with allocation data
    OPTIMIZED with caching + async
    """
    import time
    start_time = time.time()

    try:
        # Fetch jobs from external API
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'

        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=20
        )

        response.raise_for_status()
        response_data = response.json()

        if isinstance(response_data, dict):
            jobs_from_api = response_data.get('data', response_data.get('results', [response_data]))
        else:
            jobs_from_api = response_data

        if not isinstance(jobs_from_api, list):
            return Response(
                {'error': f'Expected list, got {type(jobs_from_api).__name__}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except requests.exceptions.RequestException as e:
        return Response(
            {'error': f'Failed to fetch jobs from external API: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    if not jobs_from_api:
        return Response([])

    # ========================================
    # STEP 1: COLLECT ALL UNIQUE IDs
    # ========================================
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

    # ========================================
    # ✅ STEP 2: BATCH FETCH ALL DATA IN PARALLEL
    # ========================================
    print(f"\n⚡ PARALLEL BATCH FETCHING...")
    batch_start = time.time()

    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)  # ✅ Reduced
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)  # ✅ Reduced
    # transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)  # ✅ Reduced

    batch_elapsed = time.time() - batch_start
    print(f"✅ Batch fetching completed in {batch_elapsed:.2f}s")

    # ========================================
    # STEP 3: ENRICH JOBS
    # ========================================
    enriched_jobs = []

    for idx, job in enumerate(jobs_from_api):
        job_id = str(
            job.get('work_id') or
            job.get('id') or
            job.get('job_id') or
            f"UNKNOWN_{idx}"
        )

        # Get farmer details from cache
        farmer_id = str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)

        # Get activities
        activities_from_api = job.get('activities', [])
        activities_data = []

        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))

            # Check if allocated
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()

            allocations_data = []
            allocated_area = Decimal('0')

            if db_activity:
                for alloc in db_activity.allocations.all():
                    allocated_area += Decimal(str(alloc.allocated_area))

                    # Get mukkadam from cache
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
            total_area = Decimal(str(api_activity.get('acres', 0)))
            remaining_area = total_area - allocated_area
            is_fully_allocated = allocated_area >= total_area

            def safe_date(value):
                if not value:
                    return ''
                return str(value).split('T')[0]

            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': api_activity.get('activity_name', 'Unknown'),
                'activity_type': api_activity.get('activity_type', ''),
                'location': api_activity.get('location', 'N/A'),
                'total_area': float(total_area),
                'allocated_area': float(allocated_area),
                'remaining_area': float(remaining_area),
                'scheduled_date': safe_date(
                    api_activity.get('date_time') or
                    api_activity.get('scheduled_date') or
                    job.get('scheduled_date')
                ),
                'scheduled_time': api_activity.get('scheduled_time', ''),
                'estimated_workers': api_activity.get('estimated_workers', 10),
                'rate_per_acre': float(api_activity.get('total_price', 0)) / float(total_area) if float(total_area) > 0 else 0,
                'total_price': float(api_activity.get('total_price', 0)),
                'transport_cost': float(api_activity.get('transport_cost', 0)),
                'other_cost': float(api_activity.get('other_cost', 0)),
                'subtotal': float(api_activity.get('subtotal', 0)),
                'is_fully_allocated': is_fully_allocated,
                'allocations': allocations_data
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

        enriched_job = {
            **job,
            'work_id': job_id,
            'farmer': farmer_details,
            'activities': activities_data,
            'status': job_status,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            'booking': job.get('booking', {})
        }

        enriched_jobs.append(enriched_job)

    total_elapsed = time.time() - start_time
    print(f"\n✅ Jobs API completed in {total_elapsed:.2f}s")

    return Response(enriched_jobs)

# allocation_app/views.py

from .utils import batch_fetch_mukkadams, batch_fetch_farmers, batch_fetch_transport_providers

@api_view(['GET'])
@permission_classes([AllowAny])
def allocations_list(request):
    """
    Get all allocations with complete details from external APIs
    OPTIMIZED with caching + async
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
                timeout=20
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
            timeout=20
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
    for job in jobs_cache.values():
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))

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
    batch_start = time.time()

    # Fetch all data types in parallel
    farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)  # ✅ Reduced
    mukkadams_cache = batch_fetch_mukkadams(list(mukkadam_ids), max_workers=5)  # ✅ Reduced
    transport_providers_cache = batch_fetch_transport_providers(list(transport_provider_ids), max_workers=5)  # ✅ Reduced

    batch_elapsed = time.time() - batch_start
    print(f"✅ Batch fetching completed in {batch_elapsed:.2f}s")

    # ========================================
    # STEP 6: BUILD ENRICHED ALLOCATIONS
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

        # Get cached data
        job_data = jobs_cache.get(job_id, {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id)
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
                 if str(a.get('id') or a.get('activity_id')) == activity_id),
                None
            )

        # Central team contact
        central_team_phone = "+91-804-7361465"
        if job_data and 'booking' in job_data:
            booking = job_data['booking']
            central_team_phone = "+91-804-7361465"

        # Calculate payment
        revenue = float(allocation.mukkadam_price) 
        transport_cost = float(allocation.transport_price or 0)
        total_cost_alloc = revenue + transport_cost

        enriched_allocation = {
            'allocation_id': allocation.id,
            'work_date': str(allocation.work_date) if allocation.work_date else None,
            'allocated_area': float(allocation.allocated_area),
            'crew_size': allocation.crew_size,
            'status': allocation.status,
            'notes': allocation.notes,
            'allocated_at': allocation.allocated_at.isoformat() if allocation.allocated_at else None,

            'mukkadam': mukkadam_data,
            'farmer': farmer_data,

            'job': {
                'job_id': job_id,
                'job_name': job_data.get('job_name', 'N/A'),
                'scheduled_date': job_data.get('scheduled_date', 'N/A'),
                'location': job_data.get('location', 'N/A'),
                'central_team_phone': central_team_phone,
            },

            'activity': {
                'activity_id': activity_id,
                'activity_name': activity_details.get('activity_name', 'Unknown') if activity_details else 'Unknown',
                'activity_type': activity_details.get('activity_type', 'N/A') if activity_details else 'N/A',
                'total_area': float(activity_details.get('acres', 0)) if activity_details else 0,
                'scheduled_date': activity_details.get('scheduled_date', 'N/A') if activity_details else 'N/A',
                'scheduled_time': activity_details.get('scheduled_time', 'N/A') if activity_details else 'N/A',
            },

            'payment': {
                'mukkadam_price_per_acre': float(allocation.mukkadam_price),
                'allocated_acres': float(allocation.allocated_area),
                'mukkadam_total_payment': revenue,
                'transport_type': allocation.transport_type,
                'transport_price': transport_cost,
                'total_amount': total_cost_alloc,
            },

            # Transport provider details
            'transport': {
                'transport_type': allocation.transport_type,
                'transport_price': transport_cost,
                'transport_provider_id': allocation.transport_provider_id if allocation.transport_type == 'provider' else None,
                'transport_provider_details': transport_provider_data,
            }
        }

        enriched_allocations.append(enriched_allocation)
        total_area += allocation.allocated_area
        total_cost += Decimal(str(total_cost_alloc))

    # Summary
    summary = {
        'total_allocations': len(allocations),
        'total_area_allocated': float(total_area),
        'total_earnings': float(total_cost),
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
                timeout=20
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
                timeout=20
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
            timeout=20
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
                        timeout=20
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
                timeout=20
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
ALLOCATION_API_BASE = 'https://allocation.bharatintelligence.ai'

def get_supply_users_mapping():
    """Fetch all users from Supply API for created_by mapping"""
    try:
        response = requests.get(
            f'{SUPPLY_API_URL}/api/users/all/',
            timeout=20
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
            f'{ALLOCATION_API_BASE}/ap/users/all/',
            timeout=20
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
            timeout=30
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
            f'{ALLOCATION_API_BASE}/ap/allocations/by-mobile/main/',
            timeout=60
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
            timeout=20
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
            timeout=20
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
                timeout=20
            )
            if response.status_code == 200:
                mukkadam_data = response.json()
                mukkadam_id = int(mukkadam_id)
        else:
            # Search by phone
            response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/',
                timeout=20
            )
            if response.status_code == 200:
                mukkadams = response.json()
                for m in mukkadams:
                    if mukkadam_phone in m.get('mobile_numbers', ''):
                        mukkadam_id = m['id']
                        # Fetch full details
                        full_response = requests.get(
                            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
                            timeout=20
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
        response = requests.get(f'{EXTERNAL_API_URL}/get_allocated_jobs/', headers={'Authorization': job_token}, timeout=20)
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
            response = requests.get(f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/', headers={'Authorization': farmer_token}, timeout=20)
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
            call_record.status = call_details.get('status', 'unknown').lower()
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
            # call_record.custom_field = call_details.get('custom_field', '')
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

            # Save the updated record
            call_record.save()

            logger.info(f"✅ Updated call {call_sid} - Status: {call_record.status}, Talk Time: {call_record.talk_time}s")

            return Response({
                "success": True,
                "message": "Call updated successfully",
                "call_sid": call_sid,
                "status": call_record.status,
                "talk_time": call_record.talk_time,
                "has_recording": call_record.has_recording
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Webhook error: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from django.db.models import Prefetch

@api_view(['GET'])
@permission_classes([AllowAny])
def get_job_details(request, job_id):
    """
    Get full breakdown of a specific job from LOCAL DB only (Fast).
    Reconstructs the job object structure expected by the frontend.
    """
    # 1. Fetch all activities for this job from local DB
    activities = JobActivity.objects.filter(job_id=job_id).prefetch_related(
        Prefetch('allocations', queryset=Allocation.objects.select_related('payment_request'))
    )

    if not activities.exists():
        return Response({'error': 'Job not found locally'}, status=404)

    # 2. Build the structure manually
    activities_data = []
    total_revenue = 0

    # We try to guess the job title/farmer from the first activity if possible,
    # or leave it generic since we are avoiding the external API.
    job_title = f"Job #{job_id}"

    for activity in activities:
        # Sum allocations
        allocs_data = []
        allocated_area = Decimal('0')

        for alloc in activity.allocations.all():
            allocated_area += alloc.allocated_area

            # Fetch mukkadam name (optional: could be optimized with a separate mukkadam cache if slow)
            # For speed, we just return the ID, and let frontend fetch details if needed,
            # OR we fetch it here if your Supply API is fast.
            # Assuming we just send basic data:

            allocs_data.append({
                'allocation_id': alloc.id,
                'mukkadam_id': alloc.mukkadam_id,
                'mukkadam_name': f"Mukkadam #{alloc.mukkadam_id}", # Frontend will enrich this if needed
                'allocated_area': float(alloc.allocated_area),
                'crew_size': alloc.crew_size,
                'mukkadam_price': float(alloc.mukkadam_price),
                'transport_price': float(alloc.transport_price or 0),
                'work_date': str(alloc.work_date) if alloc.work_date else None,
                'status': alloc.status
            })

        # Calculate pricing
        # If rate_per_acre is 0, try to calc from totals
        rate = float(activity.rate_per_acre)
        revenue = float(activity.total_price)
        total_revenue += revenue

        activities_data.append({
            'activity_id': activity.activity_id,
            'activity_name': activity.activity_name,
            'total_area': float(activity.total_area),
            'allocated_area': float(allocated_area),
            'remaining_area': float(activity.remaining_area),
            'rate_per_acre': rate,
            'total_price': revenue,
            'allocations': allocs_data
        })

    response_data = {
        'work_id': job_id,
        'title': job_title,
        'activities': activities_data,
        'farmer_id': None, # We don't have this locally in JobActivity, frontend handles null gracefully
    }

    return Response(response_data)


# # allocation_app/views.py
# import requests
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny
# from rest_framework.response import Response
# from rest_framework import status
# from django.contrib.auth.models import User
# from datetime import datetime, date
# from decimal import Decimal

# from .models import Allocation, JobActivity, PaymentRequest

# # # API Configuration
# # SUPPLY_API_URL = 'https://demand.bharatintelligence.ai/supply'
# EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
# FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'

# JOB_TOKEN = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
# FARMER_TOKEN = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'


# def get_supply_users_mapping():
#     """Fetch all users from Supply API for created_by mapping"""
#     try:
#         response = requests.get(
#             f'{SUPPLY_API_URL}/api/users/all/',
#             timeout=20
#         )
#         if response.status_code == 200:
#             users_data = response.json()
#             return {
#                 user['id']: user.get('username') or user.get('full_name') or f"User #{user['id']}"
#                 for user in users_data
#             }
#     except Exception as e:
#         print(f"Error fetching supply users: {e}")
    
#     return {}


# def get_allocation_users_mapping():
#     """Get users from Django User model for allocated_by mapping"""
#     try:
#         users = User.objects.all().values('id', 'username', 'first_name', 'last_name')
#         return {
#             user['id']: user.get('username') or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or f"User #{user['id']}"
#             for user in users
#         }
#     except Exception as e:
#         print(f"Error fetching allocation users from DB: {e}")
#         return {}


# def get_all_mukkadams_from_supply():
#     """Get all mukkadams from Supply API"""
#     try:
#         response = requests.get(
#             f'{SUPPLY_API_URL}/api/mukkadam/',
#             timeout=30
#         )
        
#         if response.status_code == 200:
#             data = response.json()
            
#             if isinstance(data, list):
#                 return data
#             elif isinstance(data, dict) and 'results' in data:
#                 return data['results']
#             else:
#                 return []
#         else:
#             print(f"Error fetching mukkadams: {response.status_code}")
#             return []
    
#     except Exception as e:
#         print(f"Error fetching mukkadams from Supply API: {e}")
#         return []


# def batch_fetch_mukkadams(mukkadam_ids, max_workers=10):
#     """Fetch mukkadam details in parallel"""
#     mukkadams_cache = {}
    
#     def fetch_single(mid):
#         try:
#             response = requests.get(
#                 f'{SUPPLY_API_URL}/api/mukkadam/{mid}/',
#                 timeout=20
#             )
#             if response.status_code == 200:
#                 return mid, response.json()
#         except:
#             pass
#         return mid, None
    
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         futures = {executor.submit(fetch_single, mid): mid for mid in mukkadam_ids}
        
#         for future in as_completed(futures):
#             mid, data = future.result()
#             if data:
#                 mukkadams_cache[mid] = data
    
#     return mukkadams_cache


# def batch_fetch_farmers(farmer_ids, max_workers=10):
#     """Fetch farmer details in parallel"""
#     farmers_cache = {}
    
#     def fetch_single(fid):
#         try:
#             response = requests.get(
#                 f'{FARMER_API_BASE}/get_farmer_details/{fid}/',
#                 headers={'Authorization': FARMER_TOKEN},
#                 timeout=20
#             )
#             if response.status_code == 200:
#                 return str(fid), response.json()
#         except:
#             pass
#         return str(fid), None
    
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         futures = {executor.submit(fetch_single, fid): fid for fid in farmer_ids}
        
#         for future in as_completed(futures):
#             fid, data = future.result()
#             if data:
#                 farmers_cache[fid] = data
    
#     return farmers_cache


# @api_view(['GET'])
# @permission_classes([AllowAny])
# def mukkadam_scorecard_summary(request):
#     """
#     Get mukkadam scorecard summary with all filters
#     """
#     print("="*80)
#     print("📊 MUKKADAM SCORECARD SUMMARY API")
#     print("="*80)
    
#     # ========================================
#     # STEP 1: FETCH USER MAPPINGS
#     # ========================================
#     print("👥 Fetching user mappings...")
#     supply_users_map = get_supply_users_mapping()
#     allocation_users_map = get_allocation_users_mapping()
#     print(f"✅ Loaded {len(supply_users_map)} supply users and {len(allocation_users_map)} allocation users")
    
#     # ========================================
#     # STEP 2: GET ALL MUKKADAMS FROM SUPPLY API
#     # ========================================
#     print("🔄 Fetching all mukkadams from Supply API...")
#     all_mukkadams = get_all_mukkadams_from_supply()
    
#     if not all_mukkadams:
#         return Response({
#             'error': 'Failed to fetch mukkadams from Supply API',
#             'count': 0,
#             'summary': {},
#             'mukkadams': []
#         })
    
#     print(f"✅ Fetched {len(all_mukkadams)} mukkadams from Supply API")
    
#     # ========================================
#     # STEP 3: APPLY FILTERS ON MUKKADAM DATA
#     # ========================================
#     filtered_mukkadams = all_mukkadams
    
#     # Search by name or mobile
#     search = request.GET.get('search')
#     if search:
#         filtered_mukkadams = [
#             m for m in filtered_mukkadams
#             if search.lower() in m.get('mukkadam_name', '').lower() or
#                search in m.get('mobile_numbers', '')
#         ]
#         print(f"🔍 Search filter: {search} -> {len(filtered_mukkadams)} results")
    
#     # Filter by created_by
#     created_by = request.GET.get('created_by')
#     if created_by:
#         try:
#             created_by_id = int(created_by)
#             filtered_mukkadams = [
#                 m for m in filtered_mukkadams
#                 if m.get('created_by') == created_by_id
#             ]
#             print(f"👤 Created by: {created_by} -> {len(filtered_mukkadams)} results")
#         except ValueError:
#             pass
    
#     # Location filters
#     district = request.GET.get('district')
#     if district:
#         filtered_mukkadams = [
#             m for m in filtered_mukkadams
#             if m.get('district', '').lower() == district.lower()
#         ]
#         print(f"📍 District: {district} -> {len(filtered_mukkadams)} results")
    
#     taluka = request.GET.get('taluka')
#     if taluka:
#         filtered_mukkadams = [
#             m for m in filtered_mukkadams
#             if m.get('taluka', '').lower() == taluka.lower()
#         ]
#         print(f"📍 Taluka: {taluka} -> {len(filtered_mukkadams)} results")
    
#     village = request.GET.get('village')
#     if village:
#         filtered_mukkadams = [
#             m for m in filtered_mukkadams
#             if m.get('village', '').lower() == village.lower()
#         ]
#         print(f"📍 Village: {village} -> {len(filtered_mukkadams)} results")
    
#     # Registration date filter
#     date_from = request.GET.get('date_from')
#     date_to = request.GET.get('date_to')
#     date_filter_type = request.GET.get('date_filter_type', 'work_date')
    
#     if date_filter_type == 'registration' and (date_from or date_to):
#         def parse_date(date_str):
#             try:
#                 return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
#             except:
#                 return None
        
#         if date_from:
#             date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
#             filtered_mukkadams = [
#                 m for m in filtered_mukkadams
#                 if parse_date(m.get('created_at')) and parse_date(m.get('created_at')) >= date_from_obj
#             ]
        
#         if date_to:
#             date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
#             filtered_mukkadams = [
#                 m for m in filtered_mukkadams
#                 if parse_date(m.get('created_at')) and parse_date(m.get('created_at')) <= date_to_obj
#             ]
        
#         print(f"📅 Registration date filter: {date_from} to {date_to} -> {len(filtered_mukkadams)} results")
    
#     mukkadam_ids = [m['id'] for m in filtered_mukkadams]
    
#     # ========================================
#     # STEP 4: GET ALLOCATIONS FROM DATABASE
#     # ========================================
#     print("🔄 Fetching allocations from database...")
    
#     allocations_qs = Allocation.objects.filter(
#         mukkadam_id__in=mukkadam_ids
#     ).select_related('job_activity', 'allocated_by').prefetch_related('payment_request')
    
#     # Apply allocation filters
#     activity_type = request.GET.get('activity_type')
#     if activity_type:
#         allocations_qs = allocations_qs.filter(
#             job_activity__activity_type__iexact=activity_type
#         )
#         print(f"🎯 Activity type: {activity_type}")
    
#     allocated_by = request.GET.get('allocated_by')
#     if allocated_by:
#         allocations_qs = allocations_qs.filter(allocated_by_id=allocated_by)
#         print(f"👤 Allocated by: {allocated_by}")
    
#     if date_filter_type == 'work_date' and (date_from or date_to):
#         if date_from:
#             allocations_qs = allocations_qs.filter(work_date__gte=date_from)
#         if date_to:
#             allocations_qs = allocations_qs.filter(work_date__lte=date_to)
#         print(f"📅 Work date filter: {date_from} to {date_to}")
    
#     allocations = list(allocations_qs)
#     print(f"✅ Found {len(allocations)} allocations")
    
#     # ========================================
#     # STEP 5: FETCH EXTERNAL DATA (Jobs & Farmers)
#     # ========================================
#     if not allocations:
#         print("⚠️ No allocations found, skipping external API calls")
#         jobs_cache = {}
#         farmers_cache = {}
#         mukkadams_detail_cache = {}
#     else:
#         print("🔄 Fetching job and farmer details from external APIs...")
        
#         # Get unique job IDs
#         job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)
        
#         # Fetch jobs
#         jobs_cache = {}
#         try:
#             response = requests.get(
#                 f'{EXTERNAL_API_URL}/get_allocated_jobs/',
#                 headers={'Authorization': JOB_TOKEN},
#                 timeout=20
#             )
            
#             if response.status_code == 200:
#                 data = response.json()
#                 jobs_list = data.get('data', []) if isinstance(data, dict) else data
                
#                 for job in jobs_list:
#                     job_id = str(job.get('work_id') or job.get('id'))
#                     if job_id in job_ids:
#                         jobs_cache[job_id] = job
#         except Exception as e:
#             print(f"⚠️ Error fetching jobs: {e}")
        
#         # Get farmer IDs and fetch them
#         farmer_ids = set(j.get('farmer_id') for j in jobs_cache.values() if j.get('farmer_id'))
#         farmers_cache = batch_fetch_farmers(list(farmer_ids), max_workers=5)
        
#         # Get mukkadam details
#         unique_mukkadam_ids = set(alloc.mukkadam_id for alloc in allocations)
#         mukkadams_detail_cache = batch_fetch_mukkadams(list(unique_mukkadam_ids), max_workers=5)
        
#         print(f"✅ Fetched {len(jobs_cache)} jobs, {len(farmers_cache)} farmers, {len(mukkadams_detail_cache)} mukkadam details")
    
#     # ========================================
#     # STEP 6: BUILD MUKKADAM STATS
#     # ========================================
#     mukkadam_stats = {}
    
#     for alloc in allocations:
#         mid = alloc.mukkadam_id
        
#         if mid not in mukkadam_stats:
#             mukkadam_stats[mid] = {
#                 'allocations': [],
#                 'unique_jobs': set(),
#                 'total_area': 0,
#                 'total_workers': 0,
#                 'total_earnings': 0,
#                 'total_paid': 0,
#                 'total_pending': 0,
#                 'status_counts': {
#                     'allocated': 0,
#                     'in_progress': 0,
#                     'completed': 0,
#                     'cancelled': 0
#                 },
#                 'first_work_date': None,
#             }
        
#         stats = mukkadam_stats[mid]
        
#         # Build enriched allocation data
#         job_activity = alloc.job_activity
#         job_id = str(job_activity.job_id) if job_activity else 'Unknown'
#         activity_id = str(job_activity.activity_id) if job_activity else 'Unknown'
        
#         job_data = jobs_cache.get(job_id, {})
#         farmer_id = str(job_data.get('farmer_id', ''))
#         farmer_data = farmers_cache.get(farmer_id, {})
#         mukkadam_detail = mukkadams_detail_cache.get(mid, {})
        
#         # Get activity details
#         activity_name = 'Unknown'
#         activity_type_val = 'Unknown'
#         if job_data and 'activities' in job_data:
#             activity_details = next(
#                 (a for a in job_data['activities'] if str(a.get('id') or a.get('activity_id')) == activity_id),
#                 None
#             )
#             if activity_details:
#                 activity_name = activity_details.get('activity_name', 'Unknown')
#                 activity_type_val = activity_details.get('activity_type', 'Unknown')
        
#         # Payment tracking
#         payment_status = 'unpaid'
#         if hasattr(alloc, 'payment_request'):
#             payment_req = alloc.payment_request
#             payment_status = payment_req.status
            
#             if payment_status == 'paid':
#                 stats['total_paid'] += float(payment_req.requested_amount)
#             elif payment_status == 'pending':
#                 stats['total_pending'] += float(payment_req.requested_amount)
        
#         location = job_data.get('location') or farmer_data.get('village', 'Unknown')
        
#         enriched_alloc = {
#             'allocation_id': alloc.id,
#             'job_id': job_id,
#             'activity_name': activity_name,
#             'activity_type': activity_type_val,
#             'work_date': str(alloc.work_date) if alloc.work_date else None,
#             'location': location,
#             'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
#             'farmer_phone': farmer_data.get('phone_number', 'N/A'),
#             'area': float(alloc.allocated_area),
#             'crew_size': alloc.crew_size or 0,
#             'earnings': float(alloc.mukkadam_price),
#             'status': alloc.status,
#             'payment_status': payment_status,
#             'allocated_by': allocation_users_map.get(
#                 alloc.allocated_by.id,
#                 f"User #{alloc.allocated_by.id}"
#             ) if alloc.allocated_by else 'Unknown',
#         }
        
#         stats['allocations'].append(enriched_alloc)
        
#         if job_activity:
#             stats['unique_jobs'].add(job_activity.job_id)
        
#         stats['total_area'] += float(alloc.allocated_area)
#         stats['total_workers'] += (alloc.crew_size or 0)
#         stats['total_earnings'] += float(alloc.mukkadam_price)
        
#         # Status tracking
#         stats['status_counts'][alloc.status] = stats['status_counts'].get(alloc.status, 0) + 1
        
#         # First work date
#         if alloc.work_date:
#             if stats['first_work_date'] is None or alloc.work_date < stats['first_work_date']:
#                 stats['first_work_date'] = alloc.work_date
    
#     # ========================================
#     # STEP 7: BUILD FINAL MUKKADAM LIST
#     # ========================================
#     mukkadam_list = []
#     today = date.today()

#     for mukkadam in filtered_mukkadams:
#         mid = mukkadam['id']
#         stats = mukkadam_stats.get(mid, {
#             'allocations': [],
#             'unique_jobs': set(),
#             'total_area': 0,
#             'total_workers': 0,
#             'total_earnings': 0,
#             'total_paid': 0,
#             'total_pending': 0,
#             'status_counts': {},
#             'first_work_date': None,
#         })
        
#         # Calculate active status
#         has_jobs = len(stats['allocations']) > 0
        
#         # ========================================
#         # ✅ ENHANCED AVAILABILITY LOGIC
#         # ========================================
#         start_date = mukkadam.get('start_date')
#         end_date = mukkadam.get('end_date')
#         team_availabilities = mukkadam.get('team_availabilities', [])
        
#         is_available_now = False
#         all_availability_periods = []
        
#         # Check mukkadam-level dates
#         if start_date:
#             try:
#                 start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
#                 end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
                
#                 all_availability_periods.append({
#                     'type': 'main',
#                     'start_date': start_date,
#                     'end_date': end_date,
#                 })
                
#                 # Check if available now
#                 if end_date_obj:
#                     if start_date_obj <= today <= end_date_obj:
#                         is_available_now = True
#                 else:
#                     if start_date_obj <= today:
#                         is_available_now = True
#             except:
#                 pass
        
#         # Check team availabilities
#         if team_availabilities:
#             for team_avail in team_availabilities:
#                 if team_avail.get('status') == 'Available':
#                     team_start = team_avail.get('startDate')
#                     team_end = team_avail.get('endDate')
                    
#                     if team_start:
#                         try:
#                             team_start_obj = datetime.strptime(team_start, '%Y-%m-%d').date()
#                             team_end_obj = datetime.strptime(team_end, '%Y-%m-%d').date() if team_end else None
                            
#                             all_availability_periods.append({
#                                 'type': 'team',
#                                 'team_name': team_avail.get('teamName', 'Unknown Team'),
#                                 'start_date': team_start,
#                                 'end_date': team_end,
#                             })
                            
#                             # Check if available now
#                             if not is_available_now:  # Only check if not already available
#                                 if team_end_obj:
#                                     if team_start_obj <= today <= team_end_obj:
#                                         is_available_now = True
#                                 else:
#                                     if team_start_obj <= today:
#                                         is_available_now = True
#                         except:
#                             pass
        
#         has_availability = len(all_availability_periods) > 0
        
#         # Active logic: has jobs OR is available now
#         is_active = has_jobs or is_available_now
        
#         # Days to first job
#         days_to_first_job = None
#         if stats['first_work_date'] and mukkadam.get('created_at'):
#             try:
#                 created_date = datetime.fromisoformat(mukkadam['created_at'].replace('Z', '+00:00')).date()
#                 days_to_first_job = (stats['first_work_date'] - created_date).days
#             except:
#                 pass
        
#         # Location display
#         location_parts = []
#         if mukkadam.get('village'): location_parts.append(mukkadam['village'])
#         if mukkadam.get('taluka'): location_parts.append(mukkadam['taluka'])
#         if mukkadam.get('district'): location_parts.append(mukkadam['district'])
#         location_display = ", ".join(location_parts) if location_parts else "Not Specified"
        
#         mukkadam_obj = {
#             'id': mid,
#             'mukkadam_name': mukkadam.get('mukkadam_name', 'Unknown'),
#             'mobile_numbers': mukkadam.get('mobile_numbers', ''),
#             'village': mukkadam.get('village', ''),
#             'taluka': mukkadam.get('taluka', ''),
#             'district': mukkadam.get('district', ''),
#             'crew_size': mukkadam.get('crew_size', 0),
#             'is_permanent': mukkadam.get('is_permanent', False),
#             'created_at': mukkadam.get('created_at'),
#             'created_by_name': supply_users_map.get(
#                 mukkadam.get('created_by'),
#                 f"User #{mukkadam.get('created_by')}"
#             ) if mukkadam.get('created_by') else 'Unknown',
#             'location_display': location_display,
            
#             # ✅ Enhanced Availability
#             'start_date': start_date,
#             'end_date': end_date,
#             'availability_status': {
#                 'is_available_now': is_available_now,
#                 'has_availability': has_availability,
#                 'all_periods': all_availability_periods,  # ✅ Show all availability periods
#                 'total_periods': len(all_availability_periods),
#             },
            
#             # Activity status
#             'is_active': is_active,
#             'first_allocation_date': str(stats['first_work_date']) if stats['first_work_date'] else None,
#             'days_to_first_job': days_to_first_job,
            
#             # Job statistics
#             'total_allocations': len(stats['allocations']),
#             'total_unique_jobs': len(stats['unique_jobs']),
#             'total_area_allocated': round(stats['total_area'], 2),
#             'total_workers_supplied': stats['total_workers'],
#             'total_earnings': round(stats['total_earnings'], 2),
#             'total_paid': round(stats['total_paid'], 2),
#             'total_pending': round(stats['total_pending'], 2),
            
#             # Status breakdown
#             'allocations_by_status': stats['status_counts'],
            
#             # Job summary (last 10)
#             'job_summary': stats['allocations'][:10],
#         }
        
#         mukkadam_list.append(mukkadam_obj)
        
#     # ========================================
#     # STEP 8: APPLY POST-FILTERS
#     # ========================================
#     has_jobs = request.GET.get('has_jobs')
#     if has_jobs == 'true':
#         mukkadam_list = [m for m in mukkadam_list if m['total_allocations'] > 0]
#     elif has_jobs == 'false':
#         mukkadam_list = [m for m in mukkadam_list if m['total_allocations'] == 0]
#     else:
#         mukkadam_list = [
#             m for m in mukkadam_list
#             if m['total_allocations'] > 0 or m['availability_status']['has_availability']
#         ]
    
#     is_active_filter = request.GET.get('is_active')
#     if is_active_filter:
#         is_active_bool = is_active_filter.lower() == 'true'
#         mukkadam_list = [m for m in mukkadam_list if m['is_active'] == is_active_bool]
    
#     # ========================================
#     # STEP 9: CALCULATE SUMMARY
#     # ========================================
#     total_mukkadams = len(mukkadam_list)
#     active_mukkadams = len([m for m in mukkadam_list if m['is_active']])
    
#     summary = {
#         'total_mukkadams': total_mukkadams,
#         'active_mukkadams': active_mukkadams,
#         'inactive_mukkadams': total_mukkadams - active_mukkadams,
#         'total_allocations': sum(m['total_allocations'] for m in mukkadam_list),
#         'total_unique_jobs': sum(m['total_unique_jobs'] for m in mukkadam_list),
#         'total_area_allocated': round(sum(m['total_area_allocated'] for m in mukkadam_list), 2),
#         'total_workers_supplied': sum(m['total_workers_supplied'] for m in mukkadam_list),
#         'total_earnings': round(sum(m['total_earnings'] for m in mukkadam_list), 2),
#         'total_paid': round(sum(m['total_paid'] for m in mukkadam_list), 2),
#         'total_pending': round(sum(m['total_pending'] for m in mukkadam_list), 2),
#     }
    
#     print(f"✅ Final count: {total_mukkadams} mukkadams")
#     print("="*80)
    
#     return Response({
#         'count': total_mukkadams,
#         'summary': summary,
#         'mukkadams': mukkadam_list
#     })
# @api_view(['GET'])
# @permission_classes([AllowAny])
# def mukkadam_complete_dashboard(request):
#     """
#     SUPER API: Combined Mukkadam Profile + Work History +
#     Utilization (Available vs Worked) + Financials + Activity Logs
#     """
#     start_time = time.time()

#     # 1. Input parameters
#     mukkadam_phone = request.GET.get('mukkadam_phone')
#     mukkadam_id = request.GET.get('mukkadam_id')
#     days_history = int(request.GET.get('logs_days', 30))

#     if not mukkadam_phone and not mukkadam_id:
#         return Response({'error': 'mukkadam_phone or mukkadam_id required'}, status=400)

#     # =========================================================
#     # STEP 1: FETCH MUKKADAM BASIC PROFILE (SUPPLY APP)
#     # =========================================================
#     mukkadam_profile = None
#     try:
#         if mukkadam_id:
#             url = f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/'
#         else:
#             # Helper to find ID by phone first
#             search_res = requests.get(f'{SUPPLY_API_URL}/api/mukkadam/minimal_list/', params={'search': mukkadam_phone}, timeout=5)
#             m_list = search_res.json()
#             # Logic to match exact phone
#             target_m = next((m for m in m_list if mukkadam_phone in m.get('mobile_numbers', '')), None)
#             if not target_m: return Response({'error': 'Mukkadam not found'}, status=404)
#             mukkadam_id = target_m['id']
#             url = f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/'
#         mukkadam_profile = requests.get(url, timeout=5).json()
#     except Exception as e:
#         return Response({'error': f'Supply App Error: {str(e)}'}, status=500)

#     # =========================================================
#     # STEP 2: DATABASE DATA (ALLOCATIONS & LOGS)
#     # =========================================================
#     # Fetch Allocations
#     allocations_qs = Allocation.objects.filter(mukkadam_id=mukkadam_id).select_related('job_activity').order_by('-work_date')
#     allocations_list = list(allocations_qs)

#     # Fetch Activity Logs
#     logs_qs = ActivityLog.objects.filter(
#         mukkadam_id=mukkadam_id,
#         performed_at__gte=timezone.now() - timedelta(days=days_history)
#     ).order_by('-performed_at')[:50]

#     # =========================================================
#     # STEP 3: EXTERNAL ENRICHMENT (JOBS & FARMERS)
#     # =========================================================
#     job_ids = set(str(a.job_activity.job_id) for a in allocations_list if a.job_activity)

#     # Batch fetch helper (parallelizing calls to Ops and Farmer APIs)
#     jobs_cache = {}
#     farmers_cache = {}

#     # This is where we call your existing batch_fetch logic
#     with ThreadPoolExecutor(max_workers=5) as executor:
#         # Fetch jobs from Ops API
#         future_jobs = executor.submit(fetch_ops_jobs_batch, list(job_ids))
#         jobs_cache = future_jobs.result()

#         # Collect Farmer IDs from jobs
#         farmer_ids = set(str(j.get('farmer_id')) for j in jobs_cache.values() if j.get('farmer_id'))

#         # Fetch farmers from Demand API
#         future_farmers = executor.submit(batch_fetch_farmers, list(farmer_ids))
#         farmers_cache = future_farmers.result()

#     # =========================================================
#     # STEP 4: CALCULATE UTILIZATION & FINANCIALS
#     # =========================================================
#     today = date.today()

#     # Utilization Logic
#     available_start = mukkadam_profile.get('start_date')
#     available_end = mukkadam_profile.get('end_date')

#     total_available_days = 0
#     if available_start and available_end:
#         d1 = datetime.strptime(available_start, '%Y-%m-%d').date()
#         d2 = datetime.strptime(available_end, '%Y-%m-%d').date()
#         total_available_days = (d2 - d1).days + 1

#     # Unique dates worked
#     unique_work_dates = set(a.work_date for a in allocations_list if a.status == 'completed')
#     actual_days_worked = len(unique_work_dates)
#     # Utilization Rate
#     utilization_rate = (actual_days_worked / total_available_days * 100) if total_available_days > 0 else 0

#     # Financials
#     stats = {
#         'potential': 0.0, 'paid': 0.0, 'pending_payout': 0.0, 'upcoming': 0.0,
#         'area_completed': 0.0, 'area_planned': 0.0
#     }

#     for a in allocations_list:
#         val = float(a.mukkadam_price) * float(a.allocated_area)
#         stats['potential'] += val
#         if a.status == 'completed':
#             stats['area_completed'] += float(a.allocated_area)
#             if hasattr(a, 'payment_request') and a.payment_request.status == 'paid':
#                 stats['paid'] += val
#             else:
#                 stats['pending_payout'] += val
#         else:
#             stats['area_planned'] += float(a.allocated_area)
#             stats['upcoming'] += val

#     # =========================================================
#     # STEP 5: CATEGORIZE WORK HISTORY & LOGS
#     # =========================================================
# # =========================================================
# # STEP 5: CATEGORIZE WORK HISTORY & LOGS (UPDATED)
# # =========================================================
#     history = {'completed': [], 'pending': [], 'upcoming': []}

#     for a in allocations_list:
#         # Build enriched object
#         job_data = jobs_cache.get(str(a.job_activity.job_id), {})
#         farmer_id = str(job_data.get('farmer_id', ''))

#         # FIX: Use .get() with a default empty dict {} so farmer_data is never None
#         farmer_data = farmers_cache.get(farmer_id) or {}

#         entry = {
#             'id': a.id,
#             'date': str(a.work_date),
#             'area': float(a.allocated_area),
#             'status': a.status,
#             'job_name': job_data.get('job_name', 'N/A'),
#             # Now this will safe-fail to 'N/A' if farmer_data is an empty dict
#             'farmer_name': farmer_data.get('farmer_name', 'N/A'),
#             'total_cost': float(a.mukkadam_price) * float(a.allocated_area) + float(a.transport_price or 0)
#         }

#         if a.status == 'completed':
#             history['completed'].append(entry)
#         elif a.work_date and a.work_date < today:
#             history['pending'].append(entry)
#         else:
#             history['upcoming'].append(entry)
#     enriched_logs = []
#     for log in logs_qs:
#         # Use get_activity_type_display() instead of activity_type_display
#         enriched_logs.append({
#             'type': log.get_activity_type_display(), # ✅ FIXED THIS LINE
#             'time': log.performed_at.isoformat(),
#             'desc': log.description,
#             'changes': log.metadata.get('changes', {}), # Safe get for changes
#             'user': log.performed_by.username if log.performed_by else "System"
#         })

#     # =========================================================
#     # STEP 6: FINAL RESPONSE
#     # =========================================================
#     return Response({
#         'mukkadam': {
#             'info': mukkadam_profile,
#             'is_active': len(allocations_list) > 0,
#             'utilization': {
#                 'available_days': total_available_days,
#                 'worked_days': actual_days_worked,
#                 'utilization_rate': round(utilization_rate, 2),
#                 'available_from': available_start,
#                 'available_to': available_end
#             }
#         },
#         'financial_summary': {
#             'total_earning_potential': round(stats['potential'], 2),
#             'total_received': round(stats['paid'], 2),
#             'pending_from_completed': round(stats['pending_payout'], 2),
#             'upcoming_projected': round(stats['upcoming'], 2),
#         },
#         'work_history': history,
#         'recent_activity': enriched_logs,
#         'performance': {
#             'total_time_ms': int((time.time() - start_time) * 1000)
#         }
#     })

# # --- Helper function for Jobs ---
# def fetch_ops_jobs_batch(job_ids):
#     EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
#     headers = {'Authorization': 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'}
#     try:
#         res = requests.get(f'{EXTERNAL_API_URL}/get_allocated_jobs/', headers=headers, timeout=10)
#         if res.status_code == 200:
#             all_jobs = res.json().get('data', [])
#             return {str(j.get('work_id')): j for j in all_jobs if str(j.get('work_id')) in job_ids}
#     except: return {}


# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny
# from rest_framework.response import Response
# from django.db.models import Count, Sum, Q, F, Prefetch
# from django.utils import timezone
# from datetime import timedelta, datetime
# from collections import defaultdict
# import requests
# from .models import Allocation, JobActivity, AllocationStats
# from .utils import batch_fetch_mukkadams, batch_fetch_transport_providers

# @api_view(['GET'])
# @permission_classes([AllowAny])
# def comprehensive_analytics(request):
#     """
#     Comprehensive allocation analytics with mukkadam details
#     GET /api/allocation-analytics/
#     Query Params:
#     - start_date: Filter start (default: 30 days ago)
#     - end_date: Filter end (default: today)
#     - include_future: Include future allocations (default: true)
#     """
#     try:
#         # === 1. TIME RANGE SETUP ===
#         end_date_str = request.query_params.get('end_date')
#         start_date_str = request.query_params.get('start_date')
#         include_future = request.query_params.get('include_future', 'true').lower() == 'true'
#         if end_date_str:
#             end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
#         else:
#             end_date = timezone.now().date() + timedelta(days=30 if include_future else 0)
#         if start_date_str:
#             start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
#         else:
#             start_date = timezone.now().date() - timedelta(days=30)

#         today = timezone.now().date()

#         # === 2. FETCH ALLOCATIONS ===
#         allocations = Allocation.objects.filter(
#             work_date__gte=start_date,
#             work_date__lte=end_date
#         ).exclude(
#             status='cancelled'
#         ).select_related(
#             'job_activity', 'allocated_by'
#         ).order_by('work_date')
#         allocations_data = list(allocations.values(
#             'id', 'mukkadam_id', 'allocated_area', 'work_date',
#             'crew_size', 'mukkadam_price', 'transport_price',
#             'transport_type', 'transport_provider_id', 'status',
#             'allocated_at', 'notes',
#             'allocated_by__username', 'allocated_by__first_name', 'allocated_by__last_name',
#             'job_activity__job_id', 'job_activity__activity_name',
#             'job_activity__location', 'job_activity__scheduled_datetime'
#         ))

#         # === 3. FETCH MUKKADAM DETAILS (Batch) ===
#         mukkadam_ids = list(set([a['mukkadam_id'] for a in allocations_data]))
#         mukkadams_dict = batch_fetch_mukkadams(mukkadam_ids) if mukkadam_ids else {}

#         # === 4. FETCH TRANSPORT PROVIDER DETAILS (Batch) ===
#         transport_ids = list(set([
#             a['transport_provider_id']
#             for a in allocations_data
#             if a['transport_provider_id']
#         ]))
#         transporters_dict = batch_fetch_transport_providers(transport_ids) if transport_ids else {}

#         # === 5. CALCULATE MUKKADAM UTILIZATION ===
#         mukkadam_utilization = {}

#         for mukkadam_id in mukkadam_ids:
#             mukkadam_data = mukkadams_dict.get(mukkadam_id, {})

#             # Get availability schedule
#             team_availabilities = mukkadam_data.get('team_availabilities', [])

#             # Count available days in date range
#             available_days = set()
#             for availability_slot in team_availabilities:
#                 if availability_slot.get('status') == 'Available':
#                     slot_start = datetime.strptime(availability_slot['startDate'], '%Y-%m-%d').date()
#                     slot_end = datetime.strptime(availability_slot['endDate'], '%Y-%m-%d').date()

#                     # Add all days in this availability range that fall within our analysis range
#                     current = max(slot_start, start_date)
#                     end = min(slot_end, end_date)

#                     while current <= end:
#                         if current >= today:  # Only count future availability
#                             available_days.add(current)
#                         current += timedelta(days=1)

#             # Count work days (days with allocations)
#             work_days = set([
#                 a['work_date']
#                 for a in allocations_data
#                 if a['mukkadam_id'] == mukkadam_id
#             ])

#             # Calculate utilization
#             total_available = len(available_days)
#             total_worked = len(work_days)
#             utilization_rate = (total_worked / total_available * 100) if total_available > 0 else 0
#             mukkadam_utilization[mukkadam_id] = {
#                 'mukkadam_id': mukkadam_id,
#                 'mukkadam_name': mukkadam_data.get('mukkadam_name', f'Mukkadam #{mukkadam_id}'),
#                 'village': mukkadam_data.get('village', 'Unknown'),
#                 'mobile_numbers': mukkadam_data.get('mobile_numbers', ''),
#                 'crew_size': mukkadam_data.get('crew_size', 0),
#                 'registered_by': mukkadam_data.get('created_by', {}).get('username', 'Unknown') if isinstance(mukkadam_data.get('created_by'), dict) else 'Unknown',
#                 'registered_at': mukkadam_data.get('created_at', ''),
#                 'available_days': list(available_days),
#                 'work_days': list(work_days),
#                 'total_available_days': total_available,
#                 'total_work_days': total_worked,
#                 'idle_days': total_available - total_worked,
#                 'utilization_rate': round(utilization_rate, 1),
#                 'total_allocations': len([a for a in allocations_data if a['mukkadam_id'] == mukkadam_id]),
#                 'total_area_allocated': sum([float(a['allocated_area']) for a in allocations_data if a['mukkadam_id'] == mukkadam_id]),
#                 'total_earnings': sum([float(a['mukkadam_price']) for a in allocations_data if a['mukkadam_id'] == mukkadam_id]),
#             }
#         # === 6. LOCATION-BASED ANALYTICS ===
#         location_stats = defaultdict(lambda: {
#             'state': None,
#             'district': None,
#             'village': None,
#             'total_allocations': 0,
#             'total_workers': 0,
#             'total_area': 0,
#             'total_cost': 0,
#             'mukkadam_cost': 0,
#             'transport_cost': 0,
#             'activities': defaultdict(int),
#             'mukkadams': set(),
#             'jobs': set(),
#             'allocated_by': defaultdict(int),
#         })

#         for alloc in allocations_data:
#             mukkadam_id = alloc['mukkadam_id']
#             mukkadam_data = mukkadams_dict.get(mukkadam_id, {})

#             # Use mukkadam's location as primary location
#             state = mukkadam_data.get('state', 'Unknown')
#             district = mukkadam_data.get('district', 'Unknown')
#             village = mukkadam_data.get('village', 'Unknown')

#             location_key = f"{state}|{district}|{village}"

#             stats = location_stats[location_key]
#             stats['state'] = state
#             stats['district'] = district
#             stats['village'] = village
#             stats['total_allocations'] += 1
#             stats['total_workers'] += alloc['crew_size'] or 0
#             stats['total_area'] += float(alloc['allocated_area'])
#             stats['mukkadam_cost'] += float(alloc['mukkadam_price'])
#             stats['transport_cost'] += float(alloc['transport_price'] or 0)
#             stats['total_cost'] += float(alloc['mukkadam_price']) + float(alloc['transport_price'] or 0)
#             stats['activities'][alloc['job_activity__activity_name']] += 1
#             stats['mukkadams'].add(mukkadam_id)
#             stats['jobs'].add(alloc['job_activity__job_id'])
#             stats['allocated_by'][alloc['allocated_by__username']] += 1
#         # Convert sets to counts
#         location_analytics = []
#         for location_key, stats in location_stats.items():
#             location_analytics.append({
#                 'location': f"{stats['village']}, {stats['district']}, {stats['state']}",
#                 'state': stats['state'],
#                 'district': stats['district'],
#                 'village': stats['village'],
#                 'total_allocations': stats['total_allocations'],
#                 'unique_mukkadams': len(stats['mukkadams']),
#                 'unique_jobs': len(stats['jobs']),
#                 'total_workers': stats['total_workers'],
#                 'total_area': round(stats['total_area'], 2),
#                 'total_cost': round(stats['total_cost'], 2),
#                 'mukkadam_cost': round(stats['mukkadam_cost'], 2),
#                 'transport_cost': round(stats['transport_cost'], 2),
#                 'top_activities': dict(sorted(stats['activities'].items(), key=lambda x: x[1], reverse=True)[:3]),
#                 'allocated_by': dict(stats['allocated_by']),
#             })

#         # Sort by total cost
#         location_analytics.sort(key=lambda x: x['total_cost'], reverse=True)

#         # === 7. ALLOCATOR ANALYTICS ===
#         allocator_stats = defaultdict(lambda: {
#             'username': None,
#             'full_name': None,
#             'total_allocations': 0,
#             'total_cost': 0,
#             'unique_mukkadams': set(),
#             'unique_jobs': set(),
#         })
#         for alloc in allocations_data:
#             username = alloc['allocated_by__username']
#             if not username:
#                 continue
#             stats = allocator_stats[username]
#             stats['username'] = username
#             stats['full_name'] = f"{alloc['allocated_by__first_name'] or ''} {alloc['allocated_by__last_name'] or ''}".strip()
#             stats['total_allocations'] += 1
#             stats['total_cost'] += float(alloc['mukkadam_price']) + float(alloc['transport_price'] or 0)
#             stats['unique_mukkadams'].add(alloc['mukkadam_id'])
#             stats['unique_jobs'].add(alloc['job_activity__job_id'])
#         allocator_analytics = [
#             {
#                 'username': username,
#                 'full_name': stats['full_name'] or username,
#                 'total_allocations': stats['total_allocations'],
#                 'total_cost': round(stats['total_cost'], 2),
#                 'unique_mukkadams': len(stats['unique_mukkadams']),
#                 'unique_jobs': len(stats['unique_jobs']),
#                 'avg_cost_per_allocation': round(stats['total_cost'] / stats['total_allocations'], 2) if stats['total_allocations'] > 0 else 0,
#             }
#             for username, stats in allocator_stats.items()
#         ]

#         allocator_analytics.sort(key=lambda x: x['total_allocations'], reverse=True)

#         # === 8. ACTIVITY TYPE ANALYTICS ===
#         activity_stats = defaultdict(lambda: {
#             'activity_name': None,
#             'total_allocations': 0,
#             'total_area': 0,
#             'total_workers': 0,
#             'total_cost': 0,
#             'locations': set(),
#         })
#         for alloc in allocations_data:
#             activity = alloc['job_activity__activity_name']
#             stats = activity_stats[activity]
#             stats['activity_name'] = activity
#             stats['total_allocations'] += 1
#             stats['total_area'] += float(alloc['allocated_area'])
#             stats['total_workers'] += alloc['crew_size'] or 0
#             stats['total_cost'] += float(alloc['mukkadam_price']) + float(alloc['transport_price'] or 0)

#             mukkadam_data = mukkadams_dict.get(alloc['mukkadam_id'], {})
#             location = f"{mukkadam_data.get('district', 'Unknown')}, {mukkadam_data.get('state', 'Unknown')}"
#             stats['locations'].add(location)

#         activity_analytics = [
#             {
#                 'activity_name': activity,
#                 'total_allocations': stats['total_allocations'],
#                 'total_area': round(stats['total_area'], 2),
#                 'total_workers': stats['total_workers'],
#                 'total_cost': round(stats['total_cost'], 2),
#                 'unique_locations': len(stats['locations']),
#                 'avg_cost_per_acre': round(stats['total_cost'] / stats['total_area'], 2) if stats['total_area'] > 0 else 0,
#             }
#             for activity, stats in activity_stats.items()
#         ]

#         activity_analytics.sort(key=lambda x: x['total_cost'], reverse=True)

#         # === 9. DAILY TREND ===
#         daily_trend = defaultdict(lambda: {
#             'date': None,
#             'allocations': 0,
#             'cost': 0,
#             'workers': 0,
#         })
#         for alloc in allocations_data:
#             date = alloc['work_date']
#             daily_trend[date]['date'] = str(date)
#             daily_trend[date]['allocations'] += 1
#             daily_trend[date]['cost'] += float(alloc['mukkadam_price']) + float(alloc['transport_price'] or 0)
#             daily_trend[date]['workers'] += alloc['crew_size'] or 0

#         daily_analytics = sorted(daily_trend.values(), key=lambda x: x['date'])

#         # === 10. SUMMARY STATS ===
#         past_allocations = [a for a in allocations_data if a['work_date'] <= today]
#         future_allocations = [a for a in allocations_data if a['work_date'] > today]

#         summary = {
#             'date_range': {
#                 'start': str(start_date),
#                 'end': str(end_date),
#                 'today': str(today),
#             },
#             'totals': {
#                 'total_allocations': len(allocations_data),
#                 'past_allocations': len(past_allocations),
#                 'future_allocations': len(future_allocations),
#                 'active_mukkadams': len(mukkadam_ids),
#                 'active_transporters': len(transport_ids),
#                 'unique_jobs': len(set([a['job_activity__job_id'] for a in allocations_data])),
#                 'total_workers': sum([a['crew_size'] or 0 for a in allocations_data]),
#                 'total_area': round(sum([float(a['allocated_area']) for a in allocations_data]), 2),
#                 'total_cost': round(sum([float(a['mukkadam_price']) + float(a['transport_price'] or 0) for a in allocations_data]), 2),
#                 'mukkadam_cost': round(sum([float(a['mukkadam_price']) for a in allocations_data]), 2),
#                 'transport_cost': round(sum([float(a['transport_price'] or 0) for a in allocations_data]), 2),
#             },
#             'averages': {
#                 'avg_crew_size': round(sum([a['crew_size'] or 0 for a in allocations_data]) / len(allocations_data), 1) if allocations_data else 0,
#                 'avg_area': round(sum([float(a['allocated_area']) for a in allocations_data]) / len(allocations_data), 2) if allocations_data else 0,
#                 'avg_cost': round(sum([float(a['mukkadam_price']) + float(a['transport_price'] or 0) for a in allocations_data]) / len(allocations_data), 2) if allocations_data else 0,
#             }
#         }
#         # === 11. RETURN RESPONSE ===
#         return Response({
#             'success': True,
#             'summary': summary,
#             'mukkadam_utilization': list(mukkadam_utilization.values()),
#             'location_analytics': location_analytics,
#             'allocator_analytics': allocator_analytics,
#             'activity_analytics': activity_analytics,
#             'daily_trend': daily_analytics,
#             'raw_allocations': allocations_data[:100],  # Limit for performance
#         })
#     except Exception as e:
#         import traceback
#         print("ERROR in comprehensive_analytics:")
#         print(traceback.format_exc())
#         return Response({
#             'success': False,
#             'error': str(e)
#         }, status=500)

# # allocation_app/views.py

# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny
# from rest_framework.response import Response
# from django.db.models import Count, Sum, Q, F, Min, Max
# from django.utils import timezone
# from datetime import timedelta, datetime, date
# from collections import defaultdict
# from .models import Allocation, JobActivity
# from .utils import (
#     batch_fetch_mukkadams,
#     batch_fetch_transport_providers,
#     get_all_mukkadams_from_api,
#     get_all_transport_providers_from_api
# )

# @api_view(['GET'])
# @permission_classes([AllowAny])
# def supply_health_dashboard(request):
#     """
#     Complete Supply Health Metrics
#     GET /api/supply-health/

#     Query Params:
#     - reference_date: Reference date for "this week" (default: today)
#     """

#     try:
#         # === 1. DATE SETUP ===
#         reference_date_str = request.query_params.get('reference_date')
#         if reference_date_str:
#             reference_date = datetime.strptime(reference_date_str, '%Y-%m-%d').date()
#         else:
#             reference_date = timezone.now().date()

#         # This week: Monday to Sunday
#         this_week_start = reference_date - timedelta(days=reference_date.weekday())
#         this_week_end = this_week_start + timedelta(days=6)

#         # Overall period (last 90 days for averages)
#         overall_start = reference_date - timedelta(days=90)
#         overall_end = reference_date

#         print(f"📊 Supply Health Dashboard")
#         print(f"This Week: {this_week_start} to {this_week_end}")
#         print(f"Overall: {overall_start} to {overall_end}")

#         # === 2. FETCH ALL MUKKADAMS VIA API ===
#         all_mukkadams = get_all_mukkadams_from_api()
#         mukkadam_ids = [m['id'] for m in all_mukkadams]

#         # Create a lookup dictionary for quick access
#         mukkadams_by_id = {m['id']: m for m in all_mukkadams}

#         print(f"Total Mukkadams from API: {len(mukkadam_ids)}")

#         # === 3. CALCULATE AVAILABILITY & UTILIZATION ===
#         mukkadam_details = []

#         for mukkadam in all_mukkadams:
#             mukkadam_id = mukkadam['id']

#             # Get availability schedule
#             team_availabilities = mukkadam.get('team_availabilities', [])

#             # Available days this week
#             available_days_this_week = set()
#             available_days_overall = set()

#             for slot in team_availabilities:
#                 if slot.get('status') == 'Available':
#                     try:
#                         slot_start = datetime.strptime(slot['startDate'], '%Y-%m-%d').date()
#                         slot_end = datetime.strptime(slot['endDate'], '%Y-%m-%d').date()
#                         # This week
#                         current = max(slot_start, this_week_start)
#                         end = min(slot_end, this_week_end)
#                         while current <= end:
#                             available_days_this_week.add(current)
#                             current += timedelta(days=1)
#                         # Overall
#                         current = max(slot_start, overall_start)
#                         end = min(slot_end, overall_end)
#                         while current <= end:
#                             available_days_overall.add(current)
#                             current += timedelta(days=1)
#                     except:
#                         continue
#             # Get work days from allocations
#             work_days_this_week = set(
#                 Allocation.objects.filter(
#                     mukkadam_id=mukkadam_id,
#                     work_date__gte=this_week_start,
#                     work_date__lte=this_week_end
#                 ).exclude(status='cancelled').values_list('work_date', flat=True)
#             )
#             work_days_overall = set(
#                 Allocation.objects.filter(
#                     mukkadam_id=mukkadam_id,
#                     work_date__gte=overall_start,
#                     work_date__lte=overall_end
#                 ).exclude(status='cancelled').values_list('work_date', flat=True)
#             )
#             # Calculate utilization
#             total_available_this_week = len(available_days_this_week)
#             total_work_this_week = len(work_days_this_week)
#             utilization_this_week = (total_work_this_week / total_available_this_week * 100) if total_available_this_week > 0 else 0

#             total_available_overall = len(available_days_overall)
#             total_work_overall = len(work_days_overall)
#             utilization_overall = (total_work_overall / total_available_overall * 100) if total_available_overall > 0 else 0

#             # Idle days (available but no work)
#             idle_days_this_week = available_days_this_week - work_days_this_week
#             idle_days_overall = available_days_overall - work_days_overall

#             # Day-by-day breakdown for this week
#             day_breakdown = []
#             for day in sorted(available_days_this_week):
#                 has_work = day in work_days_this_week
#                 allocations_on_day = Allocation.objects.filter(
#                     mukkadam_id=mukkadam_id,
#                     work_date=day
#                 ).exclude(status='cancelled').values(
#                     'id', 'allocated_area', 'crew_size',
#                     'mukkadam_price', 'job_activity__job_id',
#                     'job_activity__activity_name'
#                 )

#                 day_breakdown.append({
#                     'date': str(day),
#                     'day_name': day.strftime('%A'),
#                     'has_work': has_work,
#                     'allocations': list(allocations_on_day),
#                     'status': '🟢 Working' if has_work else '🔴 Idle'
#                 })
#             # Calculate earnings
#             earnings_this_week = Allocation.objects.filter(
#                 mukkadam_id=mukkadam_id,
#                 work_date__gte=this_week_start,
#                 work_date__lte=this_week_end
#             ).exclude(status='cancelled').aggregate(
#                 total=Sum('mukkadam_price')
#             )['total'] or 0
#             earnings_overall = Allocation.objects.filter(
#                 mukkadam_id=mukkadam_id,
#                 work_date__gte=overall_start,
#                 work_date__lte=overall_end
#             ).exclude(status='cancelled').aggregate(
#                 total=Sum('mukkadam_price')
#             )['total'] or 0
#             # Calculate ₹/person/day
#             crew_size_str = mukkadam.get('crew_size', '1')
#             try:
#                 crew_size = int(crew_size_str) if crew_size_str else 1
#             except (ValueError, TypeError):
#                 crew_size = 1

#             earnings_per_person_day_this_week = (earnings_this_week / (total_work_this_week * crew_size)) if (total_work_this_week > 0 and crew_size > 0) else 0
#             earnings_per_person_day_overall = (earnings_overall / (total_work_overall * crew_size)) if (total_work_overall > 0 and crew_size > 0) else 0

#             # First job date
#             first_allocation = Allocation.objects.filter(
#                 mukkadam_id=mukkadam_id
#             ).exclude(status='cancelled').order_by('allocated_at').first()
#             days_to_first_job = None
#             if first_allocation and mukkadam.get('created_at'):
#                 try:
#                     created_at = datetime.fromisoformat(mukkadam['created_at'].replace('Z', '+00:00'))
#                     days_to_first_job = (first_allocation.allocated_at.date() - created_at.date()).days
#                 except:
#                     days_to_first_job = None

#             # Is active this week?
#             is_active_this_week = total_available_this_week > 0

#             # Status for utilization
#             if utilization_this_week >= 75:
#                 utilization_status = '🟢'
#             elif utilization_this_week >= 50:
#                 utilization_status = '🟠'
#             else:
#                 utilization_status = '🔴'
#             # Get created_by username
#             created_by_username = 'Unknown'
#             if mukkadam.get('created_by'):
#                 if isinstance(mukkadam['created_by'], dict):
#                     created_by_username = mukkadam['created_by'].get('username', 'Unknown')
#                 else:
#                     created_by_username = str(mukkadam['created_by'])
#             mukkadam_details.append({
#                 'mukkadam_id': mukkadam_id,
#                 'mukkadam_name': mukkadam.get('mukkadam_name', f'Mukkadam #{mukkadam_id}'),
#                 'village': mukkadam.get('village', 'Unknown'),
#                 'mobile_numbers': mukkadam.get('mobile_numbers', 'N/A'),
#                 'crew_size': crew_size,
#                 'registered_at': mukkadam.get('created_at'),
#                 'registered_by': created_by_username,
#                 # This Week
#                 'is_active_this_week': is_active_this_week,
#                 'available_days_this_week': total_available_this_week,
#                 'work_days_this_week': total_work_this_week,
#                 'idle_days_this_week': len(idle_days_this_week),
#                 'utilization_this_week': round(utilization_this_week, 1),
#                 'utilization_status': utilization_status,
#                 'earnings_this_week': float(earnings_this_week),
#                 'earnings_per_person_day_this_week': round(float(earnings_per_person_day_this_week), 2),
#                 'day_breakdown': day_breakdown,
#                 # Overall
#                 'available_days_overall': total_available_overall,
#                 'work_days_overall': total_work_overall,
#                 'idle_days_overall': len(idle_days_overall),
#                 'utilization_overall': round(utilization_overall, 1),
#                 'earnings_overall': float(earnings_overall),
#                 'earnings_per_person_day_overall': round(float(earnings_per_person_day_overall), 2),
#                 # Registration metrics
#                 'days_to_first_job': days_to_first_job,
#                 'has_received_job': first_allocation is not None,
#             })

#         # === 4. SECTION 1: SUPPLY HEALTH SNAPSHOT ===
#         active_teams_this_week = [m for m in mukkadam_details if m['is_active_this_week']]
#         active_teams_overall = [m for m in mukkadam_details if m['available_days_overall'] > 0]

#         total_available_days_this_week = sum(m['available_days_this_week'] for m in active_teams_this_week)
#         total_work_days_this_week = sum(m['work_days_this_week'] for m in active_teams_this_week)
#         avg_utilization_this_week = (total_work_days_this_week / total_available_days_this_week * 100) if total_available_days_this_week > 0 else 0

#         total_available_days_overall = sum(m['available_days_overall'] for m in active_teams_overall)
#         total_work_days_overall = sum(m['work_days_overall'] for m in active_teams_overall)
#         avg_utilization_overall = (total_work_days_overall / total_available_days_overall * 100) if total_available_days_overall > 0 else 0

#         # Idle teams (available but 0 work days)
#         idle_teams_this_week = [m for m in active_teams_this_week if m['work_days_this_week'] == 0]

#         # Avg earnings per person per day
#         total_earnings_this_week = sum(m['earnings_this_week'] for m in active_teams_this_week)
#         total_person_days_this_week = sum(m['work_days_this_week'] * m['crew_size'] for m in active_teams_this_week)
#         avg_earnings_per_person_day_this_week = (total_earnings_this_week / total_person_days_this_week) if total_person_days_this_week > 0 else 0

#         total_earnings_overall = sum(m['earnings_overall'] for m in active_teams_overall)
#         total_person_days_overall = sum(m['work_days_overall'] * m['crew_size'] for m in active_teams_overall)
#         avg_earnings_per_person_day_overall = (total_earnings_overall / total_person_days_overall) if total_person_days_overall > 0 else 0

#         # Transport cost %
#         allocations_this_week = Allocation.objects.filter(
#             work_date__gte=this_week_start,
#             work_date__lte=this_week_end
#         ).exclude(status='cancelled')

#         total_mukkadam_cost_this_week = allocations_this_week.aggregate(Sum('mukkadam_price'))['mukkadam_price__sum'] or 0
#         total_transport_cost_this_week = allocations_this_week.aggregate(Sum('transport_price'))['transport_price__sum'] or 0
#         transport_cost_pct_this_week = (total_transport_cost_this_week / (total_mukkadam_cost_this_week + total_transport_cost_this_week) * 100) if (total_mukkadam_cost_this_week + total_transport_cost_this_week) > 0 else 0

#         allocations_overall = Allocation.objects.filter(
#             work_date__gte=overall_start,
#             work_date__lte=overall_end
#         ).exclude(status='cancelled')

#         total_mukkadam_cost_overall = allocations_overall.aggregate(Sum('mukkadam_price'))['mukkadam_price__sum'] or 0
#         total_transport_cost_overall = allocations_overall.aggregate(Sum('transport_price'))['transport_price__sum'] or 0
#         transport_cost_pct_overall = (total_transport_cost_overall / (total_mukkadam_cost_overall + total_transport_cost_overall) * 100) if (total_mukkadam_cost_overall + total_transport_cost_overall) > 0 else 0

#         # Status indicators
#         def get_status(value, good_threshold, warning_threshold, higher_is_better=True):
#             if higher_is_better:
#                 if value >= good_threshold:
#                     return '🟢'
#                 elif value >= warning_threshold:
#                     return '🟠'
#                 else:
#                     return '🔴'
#             else:
#                 if value <= good_threshold:
#                     return '🟢'
#                 elif value <= warning_threshold:
#                     return '🟠'
#                 else:
#                     return '🔴'
#         supply_health_snapshot = {
#             'active_teams': {
#                 'this_week': len(active_teams_this_week),
#                 'overall_avg': round(len(active_teams_overall) / 13, 1),
#                 'status': get_status(len(active_teams_this_week), 20, 10, higher_is_better=True)
#             },
#             'available_team_days': {
#                 'this_week': total_available_days_this_week,
#                 'overall_avg': round(total_available_days_overall / 13, 1),
#                 'status': get_status(total_available_days_this_week, 100, 50, higher_is_better=True),
#                 'mukkadam_breakdown': active_teams_this_week
#             },
#             'avg_utilization': {
#                 'this_week': round(avg_utilization_this_week, 1),
#                 'overall_avg': round(avg_utilization_overall, 1),
#                 'status': get_status(avg_utilization_this_week, 70, 50, higher_is_better=True)
#             },
#             'idle_teams': {
#                 'this_week': len(idle_teams_this_week),
#                 'overall_avg': round(len([m for m in active_teams_overall if m['work_days_overall'] == 0]) / 13, 1),
#                 'status': get_status(len(idle_teams_this_week), 2, 5, higher_is_better=False),
#                 'idle_team_list': idle_teams_this_week
#             },
#             'avg_earnings_per_person_day': {
#                 'this_week': round(avg_earnings_per_person_day_this_week, 2),
#                 'overall_avg': round(avg_earnings_per_person_day_overall, 2),
#                 'status': get_status(avg_earnings_per_person_day_this_week, 500, 300, higher_is_better=True)
#             },
#             'transport_cost_pct': {
#                 'this_week': round(transport_cost_pct_this_week, 1),
#                 'overall_avg': round(transport_cost_pct_overall, 1),
#                 'status': get_status(transport_cost_pct_this_week, 15, 25, higher_is_better=False)
#             }
#         }

#         # === 5. SECTION 2: SUPPLY INFLOW (THIS WEEK) ===
#         # Count mukkadams registered this week (from API data)
#         teams_registered_this_week = len([
#             m for m in all_mukkadams
#             if m.get('created_at') and
#             datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).date() >= this_week_start and
#             datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).date() <= this_week_end + timedelta(days=1)
#         ])

#         # Fetch transport providers count from API
#         all_transport_providers = get_all_transport_providers_from_api()
#         transporters_registered_this_week = len([
#             t for t in all_transport_providers
#             if t.get('created_at') and
#             datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')).date() >= this_week_start and
#             datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')).date() <= this_week_end + timedelta(days=1)
#         ])
#         # Teams confirmed for allocation (have availability set)
#         teams_confirmed_this_week = len([
#             m for m in all_mukkadams
#             if m.get('created_at') and
#             datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).date() >= this_week_start and
#             datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).date() <= this_week_end + timedelta(days=1) and
#             m.get('team_availabilities', [])
#         ])
#         # Teams allocated this week
#         teams_allocated_this_week = Allocation.objects.filter(
#             allocated_at__gte=this_week_start,
#             allocated_at__lte=this_week_end + timedelta(days=1)
#         ).exclude(status='cancelled').values('mukkadam_id').distinct().count()

#         # Activation % (teams that got first job / total registered)
#         activation_pct = (teams_allocated_this_week / teams_registered_this_week * 100) if teams_registered_this_week > 0 else 0

#         # Avg days to first job (for teams registered)
#         teams_with_jobs = [m for m in mukkadam_details if m['days_to_first_job'] is not None and m['registered_at']]
#         avg_days_to_first_job = sum(m['days_to_first_job'] for m in teams_with_jobs) / len(teams_with_jobs) if teams_with_jobs else 0

#         # Teams rejected (registered 30+ days ago, no job yet)
#         cutoff_date = reference_date - timedelta(days=30)
#         teams_rejected = len([
#             m for m in all_mukkadams
#             if m.get('created_at') and
#             datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).date() <= cutoff_date and
#             not any(md['mukkadam_id'] == m['id'] and md['has_received_job'] for md in mukkadam_details)
#         ])
#         supply_inflow = {
#             'teams_registered': teams_registered_this_week,
#             'transporters_registered': transporters_registered_this_week,
#             'teams_confirmed': teams_confirmed_this_week,
#             'teams_allocated': teams_allocated_this_week,
#             'activation_pct': round(activation_pct, 1),
#             'avg_days_to_first_job': round(avg_days_to_first_job, 1),
#             'teams_rejected': teams_rejected
#         }
#         # === 6. SECTION 3: UTILIZATION & IDLE RISK ===
#         utilization_buckets = {
#             '0-25%': [m for m in mukkadam_details if m['available_days_overall'] > 0 and m['utilization_overall'] < 25],
#             '25-50%': [m for m in mukkadam_details if 25 <= m['utilization_overall'] < 50],
#             '50-75%': [m for m in mukkadam_details if 50 <= m['utilization_overall'] < 75],
#             '75-90%': [m for m in mukkadam_details if 75 <= m['utilization_overall'] < 90],
#             '90%+': [m for m in mukkadam_details if m['utilization_overall'] >= 90],
#         }

#         total_teams_with_availability = len([m for m in mukkadam_details if m['available_days_overall'] > 0])

#         utilization_distribution = [
#             {
#                 'bucket': '0-25%',
#                 'count': len(utilization_buckets['0-25%']),
#                 'percentage': round(len(utilization_buckets['0-25%']) / total_teams_with_availability * 100, 1) if total_teams_with_availability > 0 else 0,
#                 'teams': utilization_buckets['0-25%']
#             },
#             {
#                 'bucket': '25-50%',
#                 'count': len(utilization_buckets['25-50%']),
#                 'percentage': round(len(utilization_buckets['25-50%']) / total_teams_with_availability * 100, 1) if total_teams_with_availability > 0 else 0,
#                 'teams': utilization_buckets['25-50%']
#             },
#             {
#                 'bucket': '50-75%',
#                 'count': len(utilization_buckets['50-75%']),
#                 'percentage': round(len(utilization_buckets['50-75%']) / total_teams_with_availability * 100, 1) if total_teams_with_availability > 0 else 0,
#                 'teams': utilization_buckets['50-75%']
#             },
#             {
#                 'bucket': '75-90%',
#                 'count': len(utilization_buckets['75-90%']),
#                 'percentage': round(len(utilization_buckets['75-90%']) / total_teams_with_availability * 100, 1) if total_teams_with_availability > 0 else 0,
#                 'teams': utilization_buckets['75-90%']
#             },
#             {
#                 'bucket': '90%+',
#                 'count': len(utilization_buckets['90%+']),
#                 'percentage': round(len(utilization_buckets['90%+']) / total_teams_with_availability * 100, 1) if total_teams_with_availability > 0 else 0,
#                 'teams': utilization_buckets['90%+']
#             },
#         ]
#         # === 7. RETURN RESPONSE ===
#         return Response({
#             'success': True,
#             'reference_date': str(reference_date),
#             'week_range': {
#                 'start': str(this_week_start),
#                 'end': str(this_week_end)
#             },
#             'section_1_supply_health_snapshot': supply_health_snapshot,
#             'section_2_supply_inflow': supply_inflow,
#             'section_3_utilization_distribution': utilization_distribution,
#         })
#     except Exception as e:
#         import traceback
#         print("ERROR in supply_health_dashboard:")
#         print(traceback.format_exc())
#         return Response({
#             'success': False,
#             'error': str(e)
#         }, status=500)


# data/views.py
# data/views.py
# allocation_app/views.py
