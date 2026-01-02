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

SUPPLY_APP_URL = 'https://supply.bharatintelligence.ai'  # Change to your actual Supply App URL

def about(request):
    return render(request,'data/index.html')


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
                            f'{SUPPLY_API_BASE}/api/mukkadam/{alloc.mukkadam_id}/',
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


# ✅ URL of your Supply App API
SUPPLY_APP_URL = 'https://supply.bharatintelligence.ai'  # Change to your actual Supply App URL

# allocation_app/views.py

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
            f'{SUPPLY_APP_URL}/api/mukkadam/by-mobile/',
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
                        f'{SUPPLY_APP_URL}/api/transport-provider/{alloc.transport_provider_id}/',
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
                f'{SUPPLY_APP_URL}/api/mukkadam/{allocation.mukkadam_id}/',
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
                    f'{SUPPLY_APP_URL}/api/transport-providers/{allocation.transport_provider_id}/',
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