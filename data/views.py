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
    AllocationStatsSerializer
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

SUPPLY_API_URL = 'https://supply.bharatintelligence.ai'  # Change to your actual Supply App URL
# SUPPLY_API_URL = 'http://localhost:8000'
def about(request):
    return render(request,'data/index.html')



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
            timeout=5
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
                        timeout=3
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
        requested_amount = float(allocation.mukkadam_price) * float(allocation.allocated_area)
        
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
            timeout=10
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
                f'{SUPPLY_API_URL}/api/mukkadam/minimal_list/',
                params={'search': mukkadam_phone},
                timeout=5
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
            timeout=10
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
        central_team_phone = 'N/A'
        if job_data and 'booking' in job_data:
            booking = job_data['booking']
            central_team_phone = booking.get('phone_number', 'N/A')
        
        # Calculate payment
        revenue = float(allocation.mukkadam_price) * float(allocation.allocated_area)
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


# data/views.py
# data/views.py
# allocation_app/views.py

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
                timeout=10
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
                timeout=5
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
            timeout=8
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
                        timeout=3
                    )
                    if f_resp.status_code == 200:
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
                timeout=3
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
                'google_maps_link': f"https://www.google.com/maps/search/?api=1&query={job_data.get('location', '')}" 
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
            'base_location': provider_data.get('base_location')
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
                timeout=5
            )
            if response.status_code == 200:
                mukkadam_data = response.json()
                mukkadam_id = int(mukkadam_id)
        else:
            # Search by phone
            response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/minimal_list/',
                timeout=5
            )
            if response.status_code == 200:
                mukkadams = response.json()
                for m in mukkadams:
                    if mukkadam_phone in m.get('mobile_numbers', ''):
                        mukkadam_id = m['id']
                        # Fetch full details
                        full_response = requests.get(
                            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
                            timeout=5
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
    allocations = Allocation.objects.filter(
        mukkadam_id=mukkadam_id
    ).select_related('job_activity', 'payment_request').order_by('-work_date')
    
    # ========================================
    # STEP 3: CATEGORIZE ALLOCATIONS & CALCULATE EARNINGS
    # ========================================
    from datetime import datetime, date
    
    today = date.today()
    
    completed_allocations = []
    pending_allocations = []  # Past due but not completed
    upcoming_allocations = [] # Future dates
    
    total_allocated_area = 0  # Sum of ALL allocations
    total_area_worked = 0      # Sum of COMPLETED allocations only
    
    # --- 💰 FINANCIAL BREAKDOWN VARIABLES ---
    total_potential_earnings = 0  # Total allocated one (Sum of everything)
    total_paid_earnings = 0       # Actually paid
    total_pending_payout = 0      # Completed but NOT paid yet
    total_upcoming_income = 0     # Jobs not yet completed (Pending + Upcoming)

    for allocation in allocations:
        work_date = allocation.work_date
        
        # Calculate earnings for this specific allocation
        earnings = float(allocation.mukkadam_price) * float(allocation.allocated_area)
        
        # 1. Add to Total Potential (Allocated One)
        # 1. Add to Total Potential (Allocated One)
        total_potential_earnings += earnings
        total_allocated_area += float(allocation.allocated_area)  # ALL allocations
        
        # 2. Categorize and Calculate Specific Financials
        if allocation.status == 'completed':
            completed_allocations.append(allocation)
            total_area_worked += float(allocation.allocated_area)  # Only completed


            # Calculate remaining area
            
            
            # CHECK PAYMENT STATUS
            # If payment request exists AND status is 'paid'
            if hasattr(allocation, 'payment_request') and allocation.payment_request.status == 'paid':
                total_paid_earnings += earnings
            else:
                # Completed, but payment is Pending, Rejected, or Not Requested yet
                total_pending_payout += earnings
                
        elif work_date and work_date < today:
            # Past date but not marked completed (Pending Job)
            pending_allocations.append(allocation)
            total_upcoming_income += earnings # Still counted as potential future income once done
            
        else:
            # Future date (Upcoming Job)
            upcoming_allocations.append(allocation)
            total_upcoming_income += earnings # Projected income

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
        response = requests.get(f'{EXTERNAL_API_URL}/get_allocated_jobs/', headers={'Authorization': job_token}, timeout=10)
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
            response = requests.get(f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/', headers={'Authorization': farmer_token}, timeout=3)
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
        central_team_phone = 'N/A'
        if job_data and 'booking' in job_data:
            central_team_phone = job_data['booking'].get('phone_number', 'N/A')
        
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

# allocation_app/views.py

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



