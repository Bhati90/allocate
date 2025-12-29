from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Allocation
from .serializers import AllocationSerializer
    
from django.db.models import Count, Sum
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication

# views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Job, JobActivity, Allocation, AllocationStats
from .serializers import (
    JobSerializer, JobActivitySerializer, 
    AllocationSerializer, AllocationStatsSerializer
)
import requests
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Allocation, Job, JobActivity
from .serializers import AllocationSerializer
import requests
@api_view(['GET'])
@permission_classes([AllowAny])
def jobs_list(request):
    """
    Return all jobs with their activities and allocation status
    Works with ANY activity names from the API
    """
    # Get all jobs with their activities
    jobs = Job.objects.all().prefetch_related('activities__allocations')
    
    def get_activity_allocations(activity):
        """Get all allocations for a specific activity"""
        activity_allocs = activity.allocations.all()
        
        # ✅ Use Decimal for calculations
        total_allocated_area = sum(Decimal(str(a.allocated_area or 0)) for a in activity_allocs)
        
        alloc_list = []
        for alloc in activity_allocs:
            # Fetch mukkadam name from external API
            try:
                mukkadam_response = requests.get(
                    f'http://127.0.0.1:8000/api/mukkadam/{alloc.mukkadam_id}/',
                    timeout=2
                )
                mukkadam_data = mukkadam_response.json()
                mukkadam_name = mukkadam_data.get('mukkadam_name', 'Unknown')
            except:
                mukkadam_name = f'Mukkadam #{alloc.mukkadam_id}'
            
            alloc_list.append({
                'allocation_id': alloc.id,
                'mukkadam_id': alloc.mukkadam_id,
                'mukkadam_name': mukkadam_name,
                'allocated_area': float(alloc.allocated_area or 0),
                'work_date': str(alloc.work_date) if alloc.work_date else None,
                'crew_size': alloc.crew_size,
                'mukkadam_price': float(alloc.mukkadam_price),
                'transport_type': alloc.transport_type,
                'transport_price': float(alloc.transport_price or 0)
            })
        
        return float(total_allocated_area), alloc_list
    
    def calculate_job_status(activities):
        """Calculate job status based on activities"""
        if not activities:
            return 'pending'
        
        fully_allocated = 0
        partially_allocated = 0
        
        for activity in activities:
            if activity['is_fully_allocated']:
                fully_allocated += 1
            elif activity['allocated_area'] > 0:
                partially_allocated += 1
        
        if fully_allocated == len(activities):
            return 'fully_allocated'
        elif fully_allocated > 0 or partially_allocated > 0:
            return 'partially_allocated'
        else:
            return 'pending'
    
    # Build response
    jobs_data = []
    for job in jobs:
        activities_data = []
        
        for activity in job.activities.all():
            allocated_area, alloc_list = get_activity_allocations(activity)
            
            activities_data.append({
                "id": activity.id,  # Use actual database ID
                "activity_id": activity.activity_id,  # External API ID
                "activity_name": activity.activity_name,  # Display name from API
                "activity_type": activity.activity_type,  # Normalized type
                "location": activity.location or "N/A",
                "total_area": float(activity.total_area),
                "allocated_area": allocated_area,
                "remaining_area": float(activity.total_area) - allocated_area,
                "scheduled_date": str(activity.scheduled_datetime.date()),
                "scheduled_time": str(activity.scheduled_datetime.time()),
                "estimated_workers": activity.estimated_workers,
                "rate_per_acre": float(activity.rate_per_acre),
                "total_price": float(activity.total_price),
                "transport_cost": float(activity.transport_cost),
                "other_cost": float(activity.other_cost),
                "subtotal": float(activity.subtotal),
                "is_fully_allocated": allocated_area >= float(activity.total_area),
                "allocations": alloc_list
            })
        
        jobs_data.append({
            "id": job.id,
            "work_id": job.job_id,  # External API ID (e.g., FV123)
            "farmer_id": job.farmer_id,
            "plot_id": job.plot_id,
            "title": job.title or f"Job {job.job_id}",
            "description": job.description or "",
            "status": calculate_job_status(activities_data),
            "api_status": job.status,  # Original API status
            "priority": job.priority,
            "is_complex": True,
            "total_activities": len(activities_data),
            "activities": activities_data,
            "scheduled_date": str(job.scheduled_date),
            "created_at": str(job.created_at),
            "activity_notes": job.activity_notes,
            "internal_notes": job.internal_notes,
            "total_activities_amount": float(job.total_activities_amount),
            "booking": {
                "booking_id": job.booking_id,
                "total_amount": float(job.booking_total_amount or 0),
                "advance_paid": float(job.booking_advance_paid or 0),
                "balance": float(job.booking_balance or 0)
            } if job.booking_id else None
        })
    
    return Response(jobs_data)
from decimal import Decimal

class AllocationViewSet(viewsets.ModelViewSet):
    queryset = Allocation.objects.all()
    serializer_class = AllocationSerializer
    permission_classes = [AllowAny]

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
            job_activity = JobActivity.objects.get(pk=activity_id)
            print(f"✅ Found Activity: {job_activity.activity_name} ({job_activity.total_area} acres)")
        except JobActivity.DoesNotExist:
            return Response(
                {'error': f'Activity with id {activity_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Prepare data
        data = request.data.copy()
        data['job_activity'] = activity_id
        data.pop('activity_id', None)
        
        # ✅ Convert to Decimal for comparison
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
        
        # ✅ Update JobActivity allocated_area using Decimal
        job_activity.allocated_area = job_activity.allocated_area + allocated_area
        job_activity.save()
        
        print("="*80)
        print("✅ ALLOCATION CREATED")
        print("="*80)
        print(f"   Job: {allocation.job_activity.job.job_id}")
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
        
        # ✅ Reduce allocated area using Decimal
        allocated_area = Decimal(str(allocation.allocated_area))
        job_activity.allocated_area = job_activity.allocated_area - allocated_area
        job_activity.save()
        
        print(f"✅ Allocation deleted. {job_activity.remaining_area} acres now available for {job_activity.activity_name}")
        
        return super().destroy(request, *args, **kwargs)
    
    def update_job_status(self, job):
        """Update job status based on activities"""
        try:
            activities = job.activities.all()
            total_activities = activities.count()
            
            if total_activities == 0:
                return
            
            fully_allocated = activities.filter(allocated_area__gte=F('total_area')).count()
            partially_allocated = activities.filter(
                allocated_area__gt=0,
                allocated_area__lt=F('total_area')
            ).count()
            
            if fully_allocated == total_activities:
                job.status = 'fully_allocated'
            elif partially_allocated > 0 or fully_allocated > 0:
                job.status = 'partially_allocated'
            else:
                job.status = 'pending'
            
            job.save()
        except Exception as e:
            print(f"Warning: Could not update job status: {e}")
    
    def update_daily_stats(self, allocation):
        """Update daily allocation statistics"""
        date = allocation.allocated_at.date()
        stats, created = AllocationStats.objects.get_or_create(date=date)
        
        stats.total_allocations += 1
        stats.total_area_allocated += allocation.allocated_area
        stats.total_mukkadam_price += allocation.mukkadam_price
        stats.total_transport_price += allocation.transport_price
        
        # Update user-wise count
        user_name = allocation.allocated_by.username if allocation.allocated_by else 'Unknown'
        if not isinstance(stats.allocations_by_user, dict):
            stats.allocations_by_user = {}
        stats.allocations_by_user[user_name] = stats.allocations_by_user.get(user_name, 0) + 1
        
        stats.save()
    
    @action(detail=False, methods=['post'])
    def smart_allocate(self, request):
        """
        Smart allocation that considers mukkadam crew capacity
        
        POST /api/allocations/smart_allocate/
        {
            "job_activity_id": 1,
            "mukkadam_id": 2,
            "work_date": "2025-01-15",
            "mukkadam_price": 5000,
            "transport_type": "provider|own|none",
            "transport_provider_id": 1,  // if provider
            "own_transport_price": 1500  // if own
        }
        """
        activity_id = request.data.get('job_activity_id')
        mukkadam_id = request.data.get('mukkadam_id')
        work_date = request.data.get('work_date')
        
        try:
            activity = JobActivity.objects.get(id=activity_id)
        except JobActivity.DoesNotExist:
            return Response({'error': 'Activity not found'}, status=400)
        
        # Fetch mukkadam details from external service
        try:
            mukkadam_response = requests.get(
                f'http://127.0.0.1:8000/api/mukkadam/{mukkadam_id}/'
            )
            mukkadam = mukkadam_response.json()
            crew_size = int(mukkadam.get('crew_size', 10))
        except:
            crew_size = 10  # Default crew size
        
        # Calculate how much area this crew can handle
        # Assuming 1 worker can handle 0.5 acres per day for most activities
        workers_per_acre = 2  # 2 workers per acre
        max_area_per_day = crew_size / workers_per_acre
        
        remaining_area = activity.remaining_area
        
        # Determine allocation area
        allocated_area = min(float(max_area_per_day), float(remaining_area))
        
        # Create allocation
        allocation_data = {
            'job_activity': activity.id,
            'mukkadam_id': mukkadam_id,
            'allocated_area': allocated_area,
            'work_date': work_date,
            'mukkadam_price': request.data.get('mukkadam_price'),
            'transport_type': request.data.get('transport_type', 'provider'),
            'transport_provider_id': request.data.get('transport_provider_id'),
            'own_transport_price': request.data.get('own_transport_price'),
            'transport_price': request.data.get('transport_price'),
            'notes': request.data.get('notes', '')
        }
        
        serializer = self.get_serializer(data=allocation_data)
        serializer.is_valid(raise_exception=True)
        allocation = serializer.save(allocated_by=request.user)
        
        # Update activity
        activity.allocated_area += allocated_area
        activity.save()
        
        # Update job status
        self.update_job_status(activity.job)
        
        # Update daily stats
        self.update_daily_stats(allocation)
        
        # Calculate if more allocations are needed
        new_remaining = activity.remaining_area
        suggestions = []
        
        if new_remaining > 0:
            # Suggest next allocation
            if new_remaining <= max_area_per_day:
                suggestions.append({
                    'type': 'complete_same_mukkadam',
                    'message': f'Can complete remaining {new_remaining} acres with same mukkadam on another day'
                })
            else:
                days_needed = int(new_remaining / max_area_per_day) + 1
                suggestions.append({
                    'type': 'split_days',
                    'message': f'Need {days_needed} more days with this mukkadam to complete',
                    'area_per_day': max_area_per_day
                })
                suggestions.append({
                    'type': 'split_mukkadams',
                    'message': f'Or allocate {new_remaining} acres to other mukkadams'
                })
        
        return Response({
            'message': 'Smart allocation created',
            'allocation': serializer.data,
            'allocated_area': allocated_area,
            'remaining_area': float(new_remaining),
            'crew_capacity': {
                'crew_size': crew_size,
                'max_area_per_day': max_area_per_day
            },
            'suggestions': suggestions
        })
    
    @property
    def created_by(self):
        """Backward compatibility - return allocated_by as created_by"""
        return self.allocated_by
    
    @property
    def total_cost(self):
        return self.mukkadam_price + self.transport_price
    
    def __str__(self):
        if self.job_activity:
            return f"{self.job_activity.job.job_id} - Mukkadam #{self.mukkadam_id} ({self.allocated_area} acres)"
        return f"{self.farmer_work_id} - Mukkadam #{self.mukkadam_id}"
    
    @action(detail=False, methods=['get'])
    def dashboard_metrics(self, request):
        """Get comprehensive dashboard metrics"""
        
        # Count registered mukkadams
        try:
            mukkadam_response = requests.get('http://127.0.0.1:8000/api/mukkadam/')
            total_mukkadams = len(mukkadam_response.json())
        except:
            total_mukkadams = 0
        
        # Count registered transport providers
        try:
            transport_response = requests.get('http://127.0.0.1:8000/api/transport-providers/')
            total_transporters = len(transport_response.json())
        except:
            total_transporters = 0
        
        # Get allocation stats
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        
        daily_stats = AllocationStats.objects.filter(
            date__gte=last_30_days
        ).order_by('-date')
        
        total_allocations = Allocation.objects.count()
        total_jobs = Job.objects.count()
        pending_jobs = Job.objects.filter(status='pending').count()
        
        return Response({
            'registered_counts': {
                'total_mukkadams': total_mukkadams,
                'total_transporters': total_transporters
            },
            'allocation_summary': {
                'total_allocations': total_allocations,
                'total_jobs': total_jobs,
                'pending_jobs': pending_jobs,
                'allocated_jobs': total_jobs - pending_jobs
            },
            'daily_stats': AllocationStatsSerializer(daily_stats, many=True).data
        })
    
    @action(detail=False, methods=['get'])
    def day_wise_stats(self, request):
        """Get day-wise allocation statistics"""
        date_from = request.query_params.get('from', (timezone.now().date() - timedelta(days=30)))
        date_to = request.query_params.get('to', timezone.now().date())
        
        stats = AllocationStats.objects.filter(
            date__range=[date_from, date_to]
        ).order_by('date')
        
        return Response(AllocationStatsSerializer(stats, many=True).data)



class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=['get'])
    def allocation_progress(self, request, pk=None):
        """Get allocation progress for a job"""
        job = self.get_object()
        activities = job.activities.all()
        
        progress = []
        for activity in activities:
            progress.append({
                'activity': activity.get_activity_type_display(),
                'total_area': float(activity.total_area),
                'allocated_area': float(activity.allocated_area),
                'remaining_area': float(activity.remaining_area),
                'percentage': (float(activity.allocated_area) / float(activity.total_area) * 100) if activity.total_area > 0 else 0,
                'is_fully_allocated': activity.is_fully_allocated
            })
        
        return Response(progress)


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_logs_list(request):
    """Get all allocation activity logs"""
    allocations = Allocation.objects.all().order_by('-allocated_at')
    
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
            # Only fetch if provider type and ID exists
            try:
                transport_response = requests.get(
                    f'http://127.0.0.1:8001/api/transport-providers/{allocation.transport_provider_id}/',
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
            'job_id': allocation.job_activity.job.job_id,
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