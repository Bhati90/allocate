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
from .models import FCMDevice
from .serializers import FCMDeviceSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def get_fcm_by_mobile(request):
    """
    Get active FCM token(s) by mobile number

    POST /api/fcm/by-mobile/
    {
        "mobile_number": "9876543210"
    }
    """
    mobile_number = request.data.get('mobile_number')

    if not mobile_number:
        return Response(
            {"success": "false", "message": "mobile_number is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    devices = FCMDevice.objects.filter(
        mobile_number=mobile_number,
        is_active=True
    ).order_by('-last_used_at')

    if not devices.exists():
        return Response(
            {
                "success": False,
                "message": "No active FCM tokens found for this mobile number"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = FCMDeviceSerializer(devices, many=True)

    return Response(
        {
            "success": True,
            "mobile_number": mobile_number,
            "count": devices.count(),
            "tokens": serializer.data
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def jobs_list(request):
    """
    Fetch jobs from external API and enrich with:
    1. Allocation data from database
    2. Farmer details from farmer API
    """
    print("="*80)
    print("🔍 FETCHING JOBS FROM EXTERNAL API")
    print("="*80)
    
    try:
        # Fetch jobs from external API
        token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        print(f"📡 API URL: {api_url}")
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=10
        )
        
        print(f"📊 Response Status: {response.status_code}")
        response.raise_for_status()
        
        # Parse JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error: {str(e)}")
            return Response(
                {'error': f'Invalid JSON from external API: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Handle different response formats
        if isinstance(response_data, dict):
            if 'data' in response_data:
                jobs_from_api = response_data['data']
                print(f"✅ Extracted {len(jobs_from_api)} jobs from 'data' key")
            elif 'results' in response_data:
                jobs_from_api = response_data['results']
            else:
                jobs_from_api = [response_data]
        else:
            jobs_from_api = response_data
        
        if not isinstance(jobs_from_api, list):
            print(f"❌ Unexpected response type: {type(jobs_from_api)}")
            return Response(
                {'error': f'Expected list, got {type(jobs_from_api).__name__}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        print(f"✅ Found {len(jobs_from_api)} jobs from API")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {str(e)}")
        return Response(
            {'error': f'Failed to fetch jobs from external API: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    if not jobs_from_api:
        print("⚠️ No jobs returned from API")
        return Response([])
    
    # ========================================
    # ✅ STEP 1: BATCH FETCH ALL FARMER DETAILS
    # ========================================
    print("\n👥 FETCHING FARMER DETAILS...")
    
    # Extract unique farmer IDs
    farmer_ids = set()
    for job in jobs_from_api:
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    print(f"   Found {len(farmer_ids)} unique farmers: {farmer_ids}")
    
    # Fetch all farmer details (batch request)
    farmers_cache = {}
    FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
    tok = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'
    for farmer_id in farmer_ids:
        try:
            farmer_response = requests.get(
                f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/',
                headers={'Authorization': tok},
                timeout=3
            )
            if farmer_response.status_code == 200:
                farmer_data = farmer_response.json()
                farmers_cache[farmer_id] = {
                    'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                    'phone_number': farmer_data.get('phone_number', 'N/A'),
                    'village': farmer_data.get('village', 'N/A'),
                    'taluka': farmer_data.get('taluka', 'N/A'),
                    'district': farmer_data.get('district', 'N/A'),
                    'location': f"{farmer_data.get('village', 'N/A')}, {farmer_data.get('taluka', 'N/A')}, {farmer_data.get('district', 'N/A')}"
                }
                print(f"   ✅ Fetched farmer {farmer_id}: {farmers_cache[farmer_id]['farmer_name']}")
            else:
                print(f"   ❌ Failed to fetch farmer {farmer_id}: Status {farmer_response.status_code}")
                farmers_cache[farmer_id] = None
        except Exception as e:
            print(f"   ❌ Error fetching farmer {farmer_id}: {str(e)}")
            farmers_cache[farmer_id] = None
    
    # ========================================
    # STEP 2: ENRICH JOBS WITH ALLOCATIONS & FARMER DATA
    # ========================================
    enriched_jobs = []
    
    print(f"\n🔄 Enriching {len(jobs_from_api)} jobs with allocation data...")
    
    for idx, job in enumerate(jobs_from_api):
        # Get job_id
        job_id = str(
            job.get('work_id') or 
            job.get('id') or 
            job.get('job_id') or 
            f"UNKNOWN_{idx}"
        )
        
        print(f"\n  📌 Job {idx + 1}: {job_id}")
        
        # ✅ GET FARMER DETAILS FROM CACHE
        farmer_id = str(job.get('farmer_id', ''))
        farmer_details = farmers_cache.get(farmer_id)
        
        # GET ACTIVITIES FROM API
        activities_from_api = job.get('activities', [])
        print(f"     📊 Found {len(activities_from_api)} activities from API")
        
        # ENRICH WITH ALLOCATION DATA FROM DB
        activities_data = []
        
        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))
            
            # Check if this activity has been allocated
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()
            
            # Build allocations list
            allocations_data = []
            allocated_area = Decimal('0')
            
            if db_activity:
                print(f"     💾 Activity {activity_id} found in DB with {db_activity.allocations.count()} allocations")
                
                for alloc in db_activity.allocations.all():
                    allocated_area += Decimal(str(alloc.allocated_area))
                    
                    # Fetch mukkadam name
                    try:
                        mukkadam_response = requests.get(
                            f'{SUPPLY_API_URL}/api/mukkadam/{alloc.mukkadam_id}/',
                            timeout=2
                        )
                        mukkadam_data = mukkadam_response.json()
                        mukkadam_name = mukkadam_data.get('mukkadam_name', 'Unknown')
                    except:
                        mukkadam_name = f'Mukkadam #{alloc.mukkadam_id}'
                    
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
            
            print(f"     🔍 Activity {activity_id} ({api_activity.get('activity_name')})")
            print(f"        Total: {total_area}, Allocated: {allocated_area}, Remaining: {remaining_area}")
            print(f"        Is Fully Allocated: {is_fully_allocated}")

            def safe_date(value):
                if not value:
                    return ''
                return str(value).split('T')[0]
            
            # ✅ ADD ACTIVITY WITH PRICING FROM API
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
                
                # ✅ PRICING FROM API
                'rate_per_acre': float(api_activity.get('total_price', 0)) / float(total_area) if float(total_area) > 0 else 0,
                'total_price': float(api_activity.get('total_price', 0)),  # Revenue
                'transport_cost': float(api_activity.get('transport_cost', 0)),  # Expected transport cost
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
            
            print(f"\n     📊 STATUS CALCULATION:")
            print(f"        Total Activities: {len(activities)}")
            print(f"        Fully Allocated: {fully_allocated}")
            print(f"        Partially Allocated: {partially_allocated}")
            
            if fully_allocated == len(activities):
                status = 'fully_allocated'
            elif fully_allocated > 0 or partially_allocated > 0:
                status = 'partially_allocated'
            else:
                status = 'pending'
            
            print(f"        Final Status: {status}")
            return status
        
        job_status = calculate_status(activities_data)
        
        # ✅ BUILD ENRICHED JOB WITH FARMER DETAILS
        enriched_job = {
            **job,  # All original data from external API
            'work_id': job_id,
            
            # ✅ FARMER DETAILS
            'farmer': farmer_details,  # Complete farmer object
            
            # ACTIVITIES WITH ALLOCATIONS
            'activities': activities_data,
            
            # JOB METADATA
            'status': job_status,
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1,
            
            # ✅ BOOKING INFO (from API)
            'booking': job.get('booking', {})
        }
        
        enriched_jobs.append(enriched_job)
    
    print(f"\n✅ Successfully enriched {len(enriched_jobs)} jobs")
    print("="*80)
    
    return Response(enriched_jobs)


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


@api_view(['GET'])
@permission_classes([AllowAny])
def allocations_by_mobile(request):
    """
    Get all allocations for a mukkadam by mobile number
    GET /api/allocations/by-mobile/?mobile_number=9876543210
    
    This API:
    1. Calls Supply App to get mukkadam_id from mobile number
    2. Fetches allocations from Allocation App database
    3. Calls Supply App to get transport provider details
    4. Returns combined data
    """
    mobile_number = request.GET.get('mobile_number')
    
    if not mobile_number:
        return Response(
            {'error': 'mobile_number query parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
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
        
    except requests.exceptions.RequestException as e:
        return Response(
            {'error': f'Failed to connect to Supply App: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    # ✅ STEP 2: Get allocations from Allocation App database
    allocations = Allocation.objects.filter(
        mukkadam_id__in=mukkadam_ids
    ).select_related('job_activity', 'allocated_by').order_by('-allocated_at')
    
    # ✅ STEP 3: Build response with transport provider details from Supply App
    allocations_data = []
    total_area = Decimal('0')
    total_cost = Decimal('0')
    
    # ✅ Cache transport provider data to avoid multiple API calls
    transport_provider_cache = {}
    
    for alloc in allocations:
        # Find which mukkadam this allocation belongs to
        mukkadam = next((m for m in mukkadams if m['id'] == alloc.mukkadam_id), None)
        
        # ✅ Get transport provider name from Supply App API if applicable
        transport_provider_name = None
        transport_provider_details = None
        
        if alloc.transport_type == 'provider' and alloc.transport_provider_id:
            # Check cache first
            if alloc.transport_provider_id in transport_provider_cache:
                provider_data = transport_provider_cache[alloc.transport_provider_id]
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
                        else:
                            provider_data = None
                    else:
                        provider_data = None
                        
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ Failed to fetch transport provider {alloc.transport_provider_id}: {str(e)}")
                    provider_data = None
            
            # Set provider name and details
            if provider_data:
                transport_provider_name = provider_data.get('name')
                transport_provider_details = {
                    'id': provider_data.get('id'),
                    'name': provider_data.get('name'),
                    'contact_number': provider_data.get('contact_number'),
                    'base_location': provider_data.get('base_location'),
                    'vehicle_type': provider_data.get('vehicle_type')
                }
            else:
                transport_provider_name = f'Provider #{alloc.transport_provider_id}'
        
        allocation_data = {
            'allocation_id': alloc.id,
            'mukkadam_id': alloc.mukkadam_id,
            'mukkadam_name': mukkadam['mukkadam_name'] if mukkadam else 'Unknown',
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
            'transport_type': alloc.transport_type,
            'transport_price': float(alloc.transport_price or 0),
            'transport_provider': transport_provider_name,
            'transport_provider_details': transport_provider_details,  # ✅ Full details
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
    }
    
    return Response({
        'mukkadams': mukkadams,  # From Supply App
        'mukkadams_count': len(mukkadams),
        'allocations': allocations_data,  # From Allocation App + Supply App
        'summary': summary
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_logs_list(request):
    """Get all allocation activity logs"""
    allocations = Allocation.objects.all().select_related('job_activity', 'allocated_by').order_by('-allocated_at')
    
    logs = []
    for allocation in allocations:
        # Get mukkadam name
        try:
            mukkadam_response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/{allocation.mukkadam_id}/',
                timeout=2
            )
            mukkadam_data = mukkadam_response.json()
            mukkadam_name = mukkadam_data.get('mukkadam_name', 'Unknown')
        except:
            mukkadam_name = f'Mukkadam #{allocation.mukkadam_id}'
        
        # Get transport name based on transport_type
        transport_name = "Unknown"
        transport_price = float(allocation.transport_price or 0)
        
        if allocation.transport_type == 'none':
            transport_name = "No Transport"
            transport_price = 0
        elif allocation.transport_type == 'own':
            transport_name = "Own Transport"
            transport_price = float(allocation.own_transport_price or 0)
        elif allocation.transport_type == 'provider' and allocation.transport_provider_id:
            try:
                transport_response = requests.get(
                    f'{SUPPLY_API_URL}/api/transport-providers/{allocation.transport_provider_id}/',
                    timeout=2
                )
                transport_data = transport_response.json()
                transport_name = transport_data.get('name', 'Unknown Provider')
            except:
                transport_name = f'Provider #{allocation.transport_provider_id}'
        
        # Get user name
        user_name = allocation.allocated_by.username if allocation.allocated_by else 'System'
        
        logs.append({
            'id': allocation.id,
            'allocation_id': allocation.id,
            'job_id': allocation.job_activity.job_id,
            'mukkadam_id': allocation.mukkadam_id,
            'mukkadam_name': mukkadam_name,
            'transport_type': allocation.transport_type,
            'transport_provider_id': allocation.transport_provider_id,
            'transport_name': transport_name,
            'mukkadam_price': float(allocation.mukkadam_price),
            'transport_price': transport_price,
            'total_price': float(allocation.mukkadam_price) + transport_price,
            'user_name': user_name,
            'timestamp': allocation.allocated_at.isoformat(),
            'work_date': str(allocation.work_date) if allocation.work_date else None,
            'allocated_area': float(allocation.allocated_area) if allocation.allocated_area else None,
            'crew_size': allocation.crew_size,
            'activity_name': allocation.job_activity.activity_name if allocation.job_activity else None
        })
    
    return Response(logs)




# views.py - REMOVE THE MUKKADAM IMPORT
# from .models import JobActivity, Allocation, AllocationStats, Mukkadam  # ❌ WRONG

from .models import JobActivity, Allocation, AllocationStats  # ✅ CORRECT

@api_view(['GET'])
@permission_classes([AllowAny])
def allocations_list(request):
    """
    Get all allocations with complete details from external APIs
    
    Filters:
    - mukkadam_phone: Filter by mukkadam mobile number
    - work_date: Filter by work date (YYYY-MM-DD)
    - status: pending/confirmed/completed
    
    Example: /ap/allocations/by-mobile/main/?mukkadam_phone=9876543210
    """
    print("="*80)
    print("📋 FETCHING ALLOCATIONS WITH FULL DETAILS")
    print("="*80)
    
    # Get query parameters
    mukkadam_phone = request.GET.get('mukkadam_phone')
    work_date = request.GET.get('work_date')
    allocation_status = request.GET.get('status')
    
    print(f"🔍 Filters: phone={mukkadam_phone}, date={work_date}, status={allocation_status}")
    
    # ========================================
    # STEP 1: GET ALLOCATIONS FROM DATABASE
    # ========================================
    allocations_query = Allocation.objects.all().select_related('job_activity')
    
    # Apply filters
    if work_date:
        allocations_query = allocations_query.filter(work_date=work_date)
    
    if allocation_status:
        allocations_query = allocations_query.filter(status=allocation_status)
    
    # ✅ FIX: Use 'allocated_at' instead of 'created_at'
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
            # ✅ GET MUKKADAM FROM SUPPLY API
            # SUPPLY_API_URL = 'http://localhost:8000'  # Your Supply API URL
            
            # Search for mukkadam by phone
            mukkadam_response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/minimal_list/',
                params={'search': mukkadam_phone},
                timeout=5
            )
            
            if mukkadam_response.status_code == 200:
                mukkadams_data = mukkadam_response.json()
                
                # Extract mukkadam IDs from response
                if isinstance(mukkadams_data, list):
                    mukkadam_ids = [m['id'] for m in mukkadams_data if mukkadam_phone in m.get('mobile_numbers', '')]
                elif isinstance(mukkadams_data, dict) and 'results' in mukkadams_data:
                    mukkadam_ids = [m['id'] for m in mukkadams_data['results'] if mukkadam_phone in m.get('mobile_numbers', '')]
                else:
                    mukkadam_ids = []
                
                print(f"   Found {len(mukkadam_ids)} mukkadams with phone {mukkadam_phone}: {mukkadam_ids}")
                
                if not mukkadam_ids:
                    print("   ⚠️ No mukkadams found with that phone number")
                    return Response({'count': 0, 'allocations': []})
                
                # Filter allocations by mukkadam IDs
                allocations = [a for a in allocations if a.mukkadam_id in mukkadam_ids]
                print(f"   ✅ Filtered to {len(allocations)} allocations")
            else:
                print(f"   ❌ Supply API error: {mukkadam_response.status_code}")
                return Response(
                    {'error': 'Failed to fetch mukkadam data from Supply API'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            print(f"   ❌ Error filtering by phone: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return Response(
                {'error': f'Error filtering by phone: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # ========================================
    # STEP 3: BATCH FETCH JOB DETAILS
    # ========================================
    print("\n🔄 Fetching job details from external API...")
    
    job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)
    print(f"   Found {len(job_ids)} unique jobs")
    
    jobs_cache = {}
    EXTERNAL_API_URL = 'https://ops.bharatintelligence.ai/ops/api'
    job_token = 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'
    
    try:
        # Fetch all jobs in one call
        response = requests.get(
            f'{EXTERNAL_API_URL}/get_allocated_jobs/',
            headers={'Authorization': job_token},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            jobs_list = data.get('data', []) if isinstance(data, dict) else data
            
            # Cache jobs by ID
            for job in jobs_list:
                job_id = str(job.get('work_id') or job.get('id') or job.get('job_id'))
                if job_id in job_ids:
                    jobs_cache[job_id] = job
                    print(f"   ✅ Cached job {job_id}")
        else:
            print(f"   ❌ Failed to fetch jobs: Status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error fetching jobs: {str(e)}")
    
    # ========================================
    # STEP 4: BATCH FETCH FARMER DETAILS
    # ========================================
    print("\n👥 Fetching farmer details...")
    
    farmer_ids = set()
    for job in jobs_cache.values():
        farmer_id = job.get('farmer_id')
        if farmer_id:
            farmer_ids.add(str(farmer_id))
    
    print(f"   Found {len(farmer_ids)} unique farmers")
    
    farmers_cache = {}
    FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
    farmer_token = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'
    
    for farmer_id in farmer_ids:
        try:
            farmer_response = requests.get(
                f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/',
                headers={'Authorization': farmer_token},
                timeout=3
            )
            
            if farmer_response.status_code == 200:
                farmer_data = farmer_response.json()
                farmers_cache[farmer_id] = {
                    'farmer_id': farmer_id,
                    'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                    'phone_number': farmer_data.get('phone_number', 'N/A'),
                    'village': farmer_data.get('village', 'N/A'),
                    'taluka': farmer_data.get('taluka', 'N/A'),
                    'district': farmer_data.get('district', 'N/A'),
                    'location': f"{farmer_data.get('village', 'N/A')}, {farmer_data.get('taluka', 'N/A')}, {farmer_data.get('district', 'N/A')}"
                }
                print(f"   ✅ Cached farmer {farmer_id}")
            else:
                print(f"   ⚠️ Farmer {farmer_id} returned {farmer_response.status_code}")
        except Exception as e:
            print(f"   ❌ Error fetching farmer {farmer_id}: {str(e)}")
    
    # ========================================
    # STEP 5: BATCH FETCH MUKKADAM DETAILS FROM SUPPLY API
    # ========================================
    print("\n👷 Fetching mukkadam details from Supply API...")
    
    mukkadam_ids = set(alloc.mukkadam_id for alloc in allocations)
    print(f"   Found {len(mukkadam_ids)} unique mukkadams")
    
    mukkadams_cache = {}
    # SUPPLY_API_URL = 'http://localhost:8000'  # ✅ YOUR SUPPLY API URL
    
    for mukkadam_id in mukkadam_ids:
        try:
            mukkadam_response = requests.get(
                f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
                timeout=3
            )
            
            if mukkadam_response.status_code == 200:
                mukkadam_data = mukkadam_response.json()
                mukkadams_cache[mukkadam_id] = {
                    'mukkadam_id': mukkadam_id,
                    'mukkadam_name': mukkadam_data.get('mukkadam_name', 'Unknown'),
                    'mobile_numbers': mukkadam_data.get('mobile_numbers', 'N/A'),
                    'village': mukkadam_data.get('village', 'N/A'),
                    'crew_size': mukkadam_data.get('crew_size', 'N/A'),
                    'has_smartphone': mukkadam_data.get('has_smartphone', 'no'),
                    'transport_mode': mukkadam_data.get('transport_mode', 'N/A')
                }
                print(f"   ✅ Cached mukkadam {mukkadam_id}: {mukkadams_cache[mukkadam_id]['mukkadam_name']}")
            else:
                print(f"   ⚠️ Mukkadam {mukkadam_id} not found, using fallback")
                mukkadams_cache[mukkadam_id] = {
                    'mukkadam_id': mukkadam_id,
                    'mukkadam_name': f'Mukkadam #{mukkadam_id}',
                    'mobile_numbers': 'N/A',
                    'village': 'N/A',
                    'crew_size': 'N/A',
                    'has_smartphone': 'no',
                    'transport_mode': 'N/A'
                }
        except Exception as e:
            print(f"   ❌ Error fetching mukkadam {mukkadam_id}: {str(e)}")
            mukkadams_cache[mukkadam_id] = {
                'mukkadam_id': mukkadam_id,
                'mukkadam_name': f'Mukkadam #{mukkadam_id}',
                'mobile_numbers': 'N/A',
                'village': 'N/A',
                'crew_size': 'N/A',
                'has_smartphone': 'no',
                'transport_mode': 'N/A'
            }
    
    # ========================================
    # STEP 6: BUILD ENRICHED ALLOCATIONS
    # ========================================
    print("\n🔄 Building enriched allocation data...")
    
    enriched_allocations = []
    
    for idx, allocation in enumerate(allocations):
        print(f"\n  📌 Allocation {idx + 1}/{len(allocations)}: ID={allocation.id}")
        
        job_activity = allocation.job_activity
        if not job_activity:
            print(f"     ⚠️ No job activity found")
            continue
        
        job_id = str(job_activity.job_id)
        activity_id = str(job_activity.activity_id)
        
        # Get cached data
        job_data = jobs_cache.get(job_id, {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id)
        mukkadam_data = mukkadams_cache.get(allocation.mukkadam_id, {})
        
        # Get activity details
        activity_details = None
        if job_data and 'activities' in job_data:
            activity_details = next(
                (a for a in job_data.get('activities', []) 
                 if str(a.get('id') or a.get('activity_id')) == activity_id),
                None
            )
        
        # ✅ GET CENTRAL TEAM CONTACT from booking
        central_team_phone = 'N/A'
        if job_data and 'booking' in job_data:
            booking = job_data['booking']
            central_team_phone = booking.get('phone_number', 'N/A')
        
        # Calculate payment
        revenue = float(allocation.mukkadam_price) * float(allocation.allocated_area)
        transport_cost = float(allocation.transport_price or 0)
        total_cost = revenue + transport_cost
        
        # ✅ BUILD COMPLETE ALLOCATION
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
                'total_amount': total_cost,
            },
        }
        
        enriched_allocations.append(enriched_allocation)
        print(f"     ✅ Enriched allocation")
    
    print(f"\n✅ Successfully enriched {len(enriched_allocations)} allocations")
    print("="*80)
    
    return Response({
        'count': len(enriched_allocations),
        'allocations': enriched_allocations
    })



# data/views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_work_history(request):
    """
    Get complete work history and analytics for a mukkadam
    
    GET /ap/mukkadam-history/?mukkadam_phone=9876543210
    GET /ap/mukkadam-history/?mukkadam_id=134
    
    Returns:
    - All allocations (past, current, upcoming)
    - Total earnings
    - Completion statistics
    - Performance metrics
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
    print("\n👤 Fetching mukkadam details...")
    
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
        
        print(f"   ✅ Found: {mukkadam_data.get('mukkadam_name')} (ID: {mukkadam_id})")
    
    except Exception as e:
        print(f"   ❌ Error fetching mukkadam: {str(e)}")
        return Response(
            {'error': f'Failed to fetch mukkadam details: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # ========================================
    # STEP 2: GET ALL ALLOCATIONS FOR THIS MUKKADAM
    # ========================================
    print(f"\n📋 Fetching all allocations for mukkadam ID: {mukkadam_id}")
    
    allocations = Allocation.objects.filter(
        mukkadam_id=mukkadam_id
    ).select_related('job_activity').order_by('-work_date')
    
    print(f"   Found {allocations.count()} total allocations")
    
    if allocations.count() == 0:
        return Response({
            'mukkadam': {
                'mukkadam_id': mukkadam_id,
                'mukkadam_name': mukkadam_data.get('mukkadam_name'),
                'mobile_numbers': mukkadam_data.get('mobile_numbers'),
                'village': mukkadam_data.get('village'),
            },
            'summary': {
                'total_allocations': 0,
                'total_earnings': 0,
                'completed_jobs': 0,
                'pending_jobs': 0,
                'upcoming_jobs': 0,
            },
            'allocations': [],
            'monthly_breakdown': []
        })
    
    # ========================================
    # STEP 3: CATEGORIZE ALLOCATIONS BY STATUS
    # ========================================
    from datetime import datetime, date
    
    today = date.today()
    
    completed_allocations = []
    pending_allocations = []
    upcoming_allocations = []
    
    total_earnings = 0
    total_area_worked = 0
    
    for allocation in allocations:
        work_date = allocation.work_date
        
        # Calculate earnings
        earnings = float(allocation.mukkadam_price) * float(allocation.allocated_area)
        total_earnings += earnings
        total_area_worked += float(allocation.allocated_area)
        
        # Categorize by date and status
        if allocation.status == 'completed':
            completed_allocations.append(allocation)
        elif work_date and work_date < today:
            # Past date but not marked completed
            pending_allocations.append(allocation)
        elif work_date and work_date >= today:
            # Future date
            upcoming_allocations.append(allocation)
        else:
            pending_allocations.append(allocation)
    
    print(f"   Completed: {len(completed_allocations)}")
    print(f"   Pending: {len(pending_allocations)}")
    print(f"   Upcoming: {len(upcoming_allocations)}")
    
    # ========================================
    # STEP 4: FETCH JOB & FARMER DETAILS
    # ========================================
    print("\n🔄 Fetching job and farmer details...")
    
    job_ids = set(alloc.job_activity.job_id for alloc in allocations if alloc.job_activity)
    
    jobs_cache = {}
    farmers_cache = {}
    
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
                job_id = str(job.get('work_id') or job.get('id'))
                if job_id in job_ids:
                    jobs_cache[job_id] = job
    except Exception as e:
        print(f"   ⚠️ Error fetching jobs: {str(e)}")
    
    # Fetch farmer details
    farmer_ids = set()
    for job in jobs_cache.values():
        if job.get('farmer_id'):
            farmer_ids.add(str(job['farmer_id']))
    
    FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
    farmer_token = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'
    
    for farmer_id in farmer_ids:
        try:
            response = requests.get(
                f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/',
                headers={'Authorization': farmer_token},
                timeout=3
            )
            if response.status_code == 200:
                farmers_cache[farmer_id] = response.json()
        except Exception as e:
            print(f"   ⚠️ Error fetching farmer {farmer_id}: {str(e)}")
    
    # ========================================
    # STEP 5: BUILD ALLOCATION DETAILS
    # ========================================
    print("\n📦 Building allocation details...")
    
    def build_allocation_detail(allocation):
        job_activity = allocation.job_activity
        if not job_activity:
            return None
        
        job_id = str(job_activity.job_id)
        activity_id = str(job_activity.activity_id)
        
        job_data = jobs_cache.get(job_id, {})
        farmer_id = str(job_data.get('farmer_id', ''))
        farmer_data = farmers_cache.get(farmer_id, {})
        
        activity_details = None
        if job_data and 'activities' in job_data:
            activity_details = next(
                (a for a in job_data['activities'] 
                 if str(a.get('id') or a.get('activity_id')) == activity_id),
                None
            )
        
        central_team_phone = 'N/A'
        if job_data and 'booking' in job_data:
            central_team_phone = job_data['booking'].get('phone_number', 'N/A')
        
        earnings = float(allocation.mukkadam_price) * float(allocation.allocated_area)
        transport_cost = float(allocation.transport_price or 0)
        
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
            
            'payment': {
                'rate_per_acre': float(allocation.mukkadam_price),
                'allocated_acres': float(allocation.allocated_area),
                'total_earnings': earnings,
                'transport_cost': transport_cost,
                'total_payment': earnings + transport_cost,
            }
        }
    
    completed_details = [build_allocation_detail(a) for a in completed_allocations]
    completed_details = [d for d in completed_details if d]
    
    pending_details = [build_allocation_detail(a) for a in pending_allocations]
    pending_details = [d for d in pending_details if d]
    
    upcoming_details = [build_allocation_detail(a) for a in upcoming_allocations]
    upcoming_details = [d for d in upcoming_details if d]
    
    # ========================================
    # STEP 6: CALCULATE MONTHLY BREAKDOWN
    # ========================================
    from collections import defaultdict
    
    monthly_stats = defaultdict(lambda: {
        'month': '',
        'allocations': 0,
        'area_worked': 0,
        'earnings': 0,
        'completed': 0
    })
    
    for allocation in allocations:
        if allocation.work_date:
            month_key = allocation.work_date.strftime('%Y-%m')
            month_name = allocation.work_date.strftime('%B %Y')
            
            earnings = float(allocation.mukkadam_price) * float(allocation.allocated_area)
            
            monthly_stats[month_key]['month'] = month_name
            monthly_stats[month_key]['allocations'] += 1
            monthly_stats[month_key]['area_worked'] += float(allocation.allocated_area)
            monthly_stats[month_key]['earnings'] += earnings
            
            if allocation.status == 'completed':
                monthly_stats[month_key]['completed'] += 1
    
    monthly_breakdown = sorted(
        monthly_stats.values(),
        key=lambda x: x['month'],
        reverse=True
    )
    
    # ========================================
    # STEP 7: BUILD FINAL RESPONSE
    # ========================================
    print(f"\n✅ Successfully compiled work history")
    print(f"   Total Earnings: ₹{total_earnings:,.2f}")
    print(f"   Total Area: {total_area_worked:.2f} acres")
    print("="*80)
    
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
        
        'summary': {
            'total_allocations': allocations.count(),
            'completed_jobs': len(completed_allocations),
            'pending_jobs': len(pending_allocations),
            'upcoming_jobs': len(upcoming_allocations),
            'completion_rate': round(completion_rate, 2),
            
            'total_earnings': round(total_earnings, 2),
            'total_area_worked': round(total_area_worked, 2),
            'average_earnings_per_job': round(total_earnings / allocations.count(), 2) if allocations.count() > 0 else 0,
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
            'average_area_per_job': round(total_area_worked / allocations.count(), 2) if allocations.count() > 0 else 0,
            'most_recent_work': str(allocations.first().work_date) if allocations.first() and allocations.first().work_date else None,
        }
    }
    
    return Response(response_data)