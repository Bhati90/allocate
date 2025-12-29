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

@api_view(['GET'])
@permission_classes([AllowAny])
def jobs_list(request):
    """
    Fetch jobs from external API and enrich with allocation data from database
    """
    print("="*80)
    print("🔍 FETCHING JOBS FROM EXTERNAL API")
    print("="*80)
    
    try:
        # Fetch jobs from external API
        token = 'Token aaec365adef48dae27067536987eded8968c982c'
        api_url = f'{EXTERNAL_API_URL}/get_allocated_jobs/'
        
        print(f"📡 API URL: {api_url}")
        
        response = requests.get(
            api_url,
            headers={'Authorization': token},
            timeout=10
        )
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {response.headers.get('Content-Type', 'unknown')}")
        
        response.raise_for_status()
        
        # Get raw response
        raw_response = response.text
        print(f"📄 Raw Response (first 500 chars): {raw_response[:500]}")
        
        # Parse JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error: {str(e)}")
            return Response(
                {'error': f'Invalid JSON from external API: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Debug: Check type of response
        print(f"📦 Response Type: {type(response_data)}")
        
        # Handle different response formats
        if isinstance(response_data, dict):
            # Response is wrapped in {status, count, data}
            if 'data' in response_data:
                jobs_from_api = response_data['data']
                print(f"✅ Extracted {len(jobs_from_api)} jobs from 'data' key")
            elif 'results' in response_data:
                jobs_from_api = response_data['results']
                print(f"✅ Extracted {len(jobs_from_api)} jobs from 'results' key")
            else:
                # Might be a single job wrapped in dict
                jobs_from_api = [response_data]
                print(f"✅ Treating response as single job")
        else:
            jobs_from_api = response_data
        
        # Ensure it's a list
        if not isinstance(jobs_from_api, list):
            print(f"❌ Unexpected response type: {type(jobs_from_api)}")
            return Response(
                {'error': f'Expected list, got {type(jobs_from_api).__name__}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        print(f"✅ Found {len(jobs_from_api)} jobs from API")
        
        # Debug: Print first job structure
        if jobs_from_api:
            first_job = jobs_from_api[0]
            print(f"📋 First Job Type: {type(first_job)}")
            if isinstance(first_job, dict):
                print(f"📋 First Job Keys: {list(first_job.keys())}")
                print(f"📋 First Job has {len(first_job.get('activities', []))} activities")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {str(e)}")
        return Response(
            {'error': f'Failed to fetch jobs from external API: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    # If API returned empty list
    if not jobs_from_api:
        print("⚠️ No jobs returned from API")
        return Response([])
    
    # Validate that jobs are dictionaries
    if not all(isinstance(job, dict) for job in jobs_from_api):
        print("❌ Jobs are not dictionaries!")
        return Response(
            {'error': 'External API returned invalid job format'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Enrich jobs with allocation data
    enriched_jobs = []
    
    print(f"\n🔄 Enriching {len(jobs_from_api)} jobs with allocation data...")
    
    for idx, job in enumerate(jobs_from_api):
        # Get job_id with multiple fallbacks
        job_id = str(
            job.get('work_id') or 
            job.get('id') or 
            job.get('job_id') or 
            f"UNKNOWN_{idx}"
        )
        
        print(f"\n  📌 Job {idx + 1}: {job_id}")
        
        # ========================================
        # GET ACTIVITIES FROM API (PRIMARY SOURCE)
        # ========================================
        activities_from_api = job.get('activities', [])
        print(f"     📊 Found {len(activities_from_api)} activities from API")
        
        # ========================================
        # ENRICH WITH ALLOCATION DATA FROM DB
        # ========================================
        activities_data = []
        
        for api_activity in activities_from_api:
            activity_id = str(api_activity.get('id') or api_activity.get('activity_id', ''))
            
            # Check if this activity has been allocated (exists in DB)
            db_activity = JobActivity.objects.filter(
                job_id=job_id,
                activity_id=activity_id
            ).prefetch_related('allocations').first()
            
            # Build allocations list
            allocations_data = []
            allocated_area = 0
            
            if db_activity:
                print(f"     💾 Activity {activity_id} found in DB with {db_activity.allocations.count()} allocations")
                allocated_area = float(db_activity.allocated_area)
                
                for alloc in db_activity.allocations.all():
                    # Fetch mukkadam name
                    try:
                        mukkadam_response = requests.get(
                            f'http://127.0.0.1:8000/api/mukkadam/{alloc.mukkadam_id}/',
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
            
            # Use activity data from API
            total_area = float(api_activity.get('acres', 0))
            remaining_area = total_area - allocated_area
            
            activities_data.append({
                'id': db_activity.id if db_activity else None,
                'activity_id': activity_id,
                'activity_name': api_activity.get('activity_name', 'Unknown'),
                'activity_type': api_activity.get('activity_type', ''),
                'location': api_activity.get('location', 'N/A'),
                'total_area': total_area,
                'allocated_area': allocated_area,
                'remaining_area': remaining_area,
                'scheduled_date': api_activity.get('scheduled_date', job.get('scheduled_date', '')).split('T')[0],
                'scheduled_time': api_activity.get('scheduled_time', ''),
                'estimated_workers': api_activity.get('estimated_workers', 10),
                'rate_per_acre': float(api_activity.get('rate_per_acre', 0)),
                'total_price': float(api_activity.get('total_price', 0)),
                'is_fully_allocated': allocated_area >= total_area,
                'allocations': allocations_data
            })
        
        # Calculate job status based on activities
        def calculate_status(activities):
            if not activities:
                return 'pending'
            
            fully_allocated = sum(1 for a in activities if a['is_fully_allocated'])
            partially_allocated = sum(1 for a in activities if a['allocated_area'] > 0 and not a['is_fully_allocated'])
            
            if fully_allocated == len(activities):
                return 'fully_allocated'
            elif fully_allocated > 0 or partially_allocated > 0:
                return 'partially_allocated'
            return 'pending'
        
        # Add enriched job data
        enriched_jobs.append({
            **job,  # All data from external API
            'work_id': job_id,  # Ensure work_id exists as string
            'activities': activities_data,
            'status': calculate_status(activities_data),
            'total_activities': len(activities_data),
            'is_complex': len(activities_data) > 1
        })
    
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
def activity_logs_list(request):
    """Get all allocation activity logs"""
    allocations = Allocation.objects.all().select_related('job_activity', 'allocated_by').order_by('-allocated_at')
    
    logs = []
    for allocation in allocations:
        # Get mukkadam name
        try:
            mukkadam_response = requests.get(
                f'http://127.0.0.1:8000/api/mukkadam/{allocation.mukkadam_id}/',
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
                    f'http://127.0.0.1:8000/api/transport-providers/{allocation.transport_provider_id}/',
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