from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.db import transaction
from datetime import datetime, timedelta
from .models import *
from .serializers import *
from .utils import check_can_allocate, get_mukkadam_availability, get_mukkadam_remaining_workers
# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Prefetch
from django.db import transaction
from datetime import datetime, timedelta
from .models import (
    ActivityCatalog, Job, JobActivity, JobBooking, FarmerPayment,
    Mukkadam, MukkadamActivityRate, MukkadamAvailability,
    Allocation, Farmer
)
from .serializers import (
    ActivityCatalogSerializer, JobSerializer, MukkadamSerializer,
    JobActivitySerializer, MukkadamAvailabilitySerializer,
    AllocationSerializer, MukkadamActivityRateSerializer,ClusterSerializer
)
from rest_framework.permissions import AllowAny
from .serializers import FarmerSerializer, JobSerializer
# tender/auth.py
from rest_framework.authentication import SessionAuthentication
import logging

logger = logging.getLogger(__name__)
import os
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # disable CSRF check
from rest_framework.permissions import IsAuthenticatedOrReadOnly
def about(request):
    return render(request,'tender/index.html')


# views.py - Update cluster_activity_calendar

@api_view(['GET', 'POST'])
def cluster_activity_calendar(request, cluster_id):
    """
    GET: Retrieve cluster activity calendar with farmer & mukkadam rates
    POST: Update cluster-specific overrides for farmer rates, gaps, and mukkadam rates
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
    except Cluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)
    
    if request.method == 'GET':
        activities = ActivityCatalog.objects.all().order_by('id')
        
        calendar = []
        for activity in activities:
            # Farmer rate logic (existing)
            cluster_rate = ClusterActivityRate.objects.filter(
                cluster=cluster, activity=activity
            ).first()
            
            cluster_gap = ClusterActivityScheduleRule.objects.filter(
                cluster=cluster, activity=activity
            ).first()
            
            global_rule = ActivityScheduleRule.objects.filter(activity=activity).first()
            
            farmer_rate = float(cluster_rate.rate_per_acre) if cluster_rate else float(activity.default_rate_per_acre)
            rate_overridden = bool(cluster_rate)
            
            gap_days = cluster_gap.gap_days if cluster_gap else (global_rule.gap_days if global_rule else activity.default_gap_days)
            gap_overridden = bool(cluster_gap)
            
            # ✅ Mukkadam rate logic (NEW)
            mukkadam_cluster_rate = ClusterMukkadamActivityRate.objects.filter(
                cluster=cluster, activity=activity
            ).first()
            
            mukkadam_rate = float(mukkadam_cluster_rate.rate_per_acre) if mukkadam_cluster_rate else farmer_rate * 0.8  # 80% of farmer rate as default
            mukkadam_productivity = float(mukkadam_cluster_rate.productivity_per_worker) if mukkadam_cluster_rate else 0.150
            mukkadam_rate_overridden = bool(mukkadam_cluster_rate)
            
            calendar.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'activity_type': activity.activity_type,
                # Farmer rates
                'rate_per_acre': farmer_rate,
                'rate_overridden': rate_overridden,
                'gap_days': gap_days,
                'gap_overridden': gap_overridden,
                # Mukkadam rates (NEW)
                'mukkadam_rate_per_acre': mukkadam_rate,
                'mukkadam_productivity': mukkadam_productivity,
                'mukkadam_rate_overridden': mukkadam_rate_overridden,
                # Common
                'is_strict': activity.is_strict,
                'phase_order': global_rule.phase_order if global_rule else 0,
            })
        
        calendar.sort(key=lambda x: x['phase_order'])
        
        return Response({
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'activities': calendar
        })
    
    elif request.method == 'POST':
        rate_overrides = request.data.get('rate_overrides', [])
        gap_overrides = request.data.get('gap_overrides', [])
        mukkadam_rate_overrides = request.data.get('mukkadam_rate_overrides', [])  # ✅ NEW
        
        # Update farmer rates (existing)
        for override in rate_overrides:
            activity_id = override.get('activity_id')
            rate = override.get('rate_per_acre')
            
            if not activity_id or rate is None:
                continue
            
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)
                ClusterActivityRate.objects.update_or_create(
                    cluster=cluster,
                    activity=activity,
                    defaults={'rate_per_acre': rate}
                )
            except ActivityCatalog.DoesNotExist:
                continue
        
        # Update gaps (existing)
        for override in gap_overrides:
            activity_id = override.get('activity_id')
            gap_days = override.get('gap_days')
            
            if not activity_id or gap_days is None:
                continue
            
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)
                ClusterActivityScheduleRule.objects.update_or_create(
                    cluster=cluster,
                    activity=activity,
                    defaults={'gap_days': gap_days}
                )
            except ActivityCatalog.DoesNotExist:
                continue
        
        # ✅ Update mukkadam rates (NEW)
        for override in mukkadam_rate_overrides:
            activity_id = override.get('activity_id')
            rate = override.get('rate_per_acre')
            productivity = override.get('productivity_per_worker')
            
            if not activity_id or rate is None or productivity is None:
                continue
            
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)
                ClusterMukkadamActivityRate.objects.update_or_create(
                    cluster=cluster,
                    activity=activity,
                    defaults={
                        'rate_per_acre': rate,
                        'productivity_per_worker': productivity
                    }
                )
            except ActivityCatalog.DoesNotExist:
                continue
        
        return Response({'success': True, 'message': 'Calendar updated'})
@api_view(['GET'])
def get_cluster_info(request, cluster_id):
    """
    GET: Get cluster details with location info
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        return Response({
            'id': cluster.id,
            'name': cluster.name,
            'district': cluster.district,
            'taluka': cluster.taluka,
            'village': cluster.village,
        })
    except Cluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)


@api_view(['DELETE'])
def reset_cluster_activity_rate(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific rate override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityRate.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Rate override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)


@api_view(['DELETE'])
def reset_cluster_activity_gap(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific gap override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Gap override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

@api_view(['DELETE'])
def reset_cluster_activity_override(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)


class FarmerViewSet(viewsets.ModelViewSet):
    queryset = Farmer.objects.all().select_related('cluster')
    serializer_class = FarmerSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by cluster
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)
        
        # Search by name or phone
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(farmer_name__icontains=search) | 
                Q(phone_number__icontains=search)
            )
        
        return queryset.order_by('farmer_name')

@api_view(['GET'])
def get_cluster_plots(request, cluster_id):
    """
    GET: Get all plots in a cluster with farmer info
    """
    try:
        plots = Plot.objects.filter(cluster_id=cluster_id).select_related('farmer')
        
        plot_list = []
        for plot in plots:
            plot_list.append({
                'id': plot.id,
                'name': plot.name,
                'area_acres': float(plot.area_acres),
                'plot_code': plot.plot_code,
                'farmer_id': plot.farmer.farmer_id if plot.farmer else None,
                'farmer_name': plot.farmer.farmer_name if plot.farmer else None,
            })
        
        return Response({'plots': plot_list})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

class PlotViewSet(viewsets.ModelViewSet):
    queryset = Plot.objects.all().select_related('farmer', 'cluster')
    serializer_class = PlotSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by farmer
        farmer_id = self.request.query_params.get('farmer_id')
        if farmer_id:
            queryset = queryset.filter(farmer_id=farmer_id)
        
        # Filter by cluster
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)
        
        return queryset.order_by('-created_at')



def load_location_data(filename):
    """
    Load location data from static JSON files and transform from 
    column-based format to row-based array of objects
    """
    file_path = os.path.join(settings.BASE_DIR, 'static', 'location_data', filename)
    
    logger.info(f"Attempting to load: {file_path}")
    logger.info(f"File exists: {os.path.exists(file_path)}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Loaded data type: {type(data)}")
        
        # ✅ Check if data is already an array (correct format)
        if isinstance(data, list):
            logger.info(f"Data is list with {len(data)} items")
            return data
        
        # ✅ Transform column-based JSON to row-based array
        if isinstance(data, dict):
            columns = list(data.keys())
            logger.info(f"Data is dict with columns: {columns}")
            
            if not columns:
                return []
            
            first_column = data[columns[0]]
            row_indices = sorted(first_column.keys(), key=lambda x: int(x))
            
            result = []
            for index in row_indices:
                row_obj = {}
                for column in columns:
                    value = data[column].get(index, '')
                    row_obj[column] = value.strip() if isinstance(value, str) else str(value).strip()
                result.append(row_obj)
            
            logger.info(f"Transformed to {len(result)} rows")
            return result
        
        return []
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error in {filename}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading {filename}: {str(e)}")
        return []


def normalize_field_name(d, *field_variations):
    """
    Get value from dict trying multiple field name variations
    Returns the first matching field value, or empty string if none found
    """
    for field in field_variations:
        if field in d:
            value = d[field]
            return value.strip() if isinstance(value, str) else str(value).strip()
    return ''


@api_view(['GET'])
@permission_classes([AllowAny])
def get_states(request):
    """Returns available states"""
    states = [
        {
            'state_code': 'MH',
            'state_name_english': 'Maharashtra',
            'state_name_local': 'महाराष्ट्र'
        },
        {
            'state_code': 'GJ',
            'state_name_english': 'Gujarat',
            'state_name_local': 'ગુજરાત'
        }
    ]
    return Response(states)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_districts(request):
    """Returns unique districts for a state"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    
    logger.info(f"📍 get_districts called with state_code: {state_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_districts.json',
        'GJ': 'gujarat_districts.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        logger.error(f"❌ Invalid state_code: {state_code}")
        return Response({'error': 'Invalid state_code'}, status=400)
    
    logger.info(f"📂 Loading file: {filename}")
    districts = load_location_data(filename)
    
    logger.info(f"✅ Loaded {len(districts)} districts for {state_code}")
    
    # ✅ Deduplicate and clean - handle multiple field name formats
    seen = set()
    unique_districts = []
    
    for d in districts:
        if not isinstance(d, dict):
            continue
        
        # Try multiple field name variations
        code = normalize_field_name(d, 'districtcode', 'District Code', 'District code')
        name_english = normalize_field_name(d, 'districtnameenglish', 'District Name', 'District name')
        name_local = normalize_field_name(d, 'districtlocalname', 'District Name', 'District name')
        
        if code and code not in seen:
            seen.add(code)
            unique_districts.append({
                'districtcode': code,
                'districtnameenglish': name_english,
                'districtlocalname': name_local
            })
    
    logger.info(f"✅ Returning {len(unique_districts)} unique districts")
    return Response(unique_districts)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_talukas(request):
    """Returns unique talukas for a district"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    district_code = request.query_params.get('district_code', '').strip()
    
    logger.info(f"📍 get_talukas called with state: {state_code}, district: {district_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    if not district_code:
        return Response({'error': 'district_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_talukas.json',
        'GJ': 'gujarat_talukas.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)
    
    all_talukas = load_location_data(filename)
    
    # Filter and deduplicate - handle multiple field name formats
    seen = set()
    unique_talukas = []
    
    for t in all_talukas:
        if not isinstance(t, dict):
            continue
        
        # Get district code with multiple field name variations
        t_district_code = normalize_field_name(t, 'districtcode', 'District Code', 'District code')
        
        if t_district_code == district_code:
            code = normalize_field_name(t, 'subdistrictcode', 'Subdistrict Code', 'Subdistrict code')
            name_english = normalize_field_name(t, 'subdistrictnameenglish', 'Subdistrict Name', 'Subdistrict Name  ')
            name_local = normalize_field_name(t, 'subdistrictlocalname', 'Subdistrict Name', 'Subdistrict Name  ')
            
            if code and code not in seen:
                seen.add(code)
                unique_talukas.append({
                    'districtcode': t_district_code,
                    'subdistrictcode': code,
                    'subdistrictnameenglish': name_english,
                    'subdistrictlocalname': name_local
                })
    
    logger.info(f"✅ Returning {len(unique_talukas)} talukas")
    return Response(unique_talukas)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_villages(request):
    """Returns unique villages for a taluka"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    taluka_code = request.query_params.get('taluka_code', '').strip()
    
    logger.info(f"📍 get_villages called with state: {state_code}, taluka: {taluka_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    if not taluka_code:
        return Response({'error': 'taluka_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_villages.json',
        'GJ': 'gujarat_villages.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)
    
    all_villages = load_location_data(filename)
    
    # Filter and deduplicate - handle multiple field name formats
    seen = set()
    unique_villages = []
    
    for v in all_villages:
        if not isinstance(v, dict):
            continue
        
        # ✅ FIXED: Added 'Sub-District Code' variation (with hyphen)
        v_taluka_code = normalize_field_name(
            v, 
            'subdistrictcode', 
            'Subdistrict Code', 
            'Subdistrict code',
            'Sub-District Code',  # ← Added this
            'Sub-district Code'
        )
        
        if v_taluka_code == taluka_code:
            # ✅ FIXED: Added hyphenated variations for all fields
            district_code = normalize_field_name(
                v, 
                'districtcode', 
                'District Code', 
                'District code'
            )
            
            code = normalize_field_name(
                v, 
                'villagecode', 
                'Village Code', 
                'Village code'
            )
            
            name_english = normalize_field_name(
                v, 
                'villagenameenglish', 
                'Village Name', 
                'Village name',
                'Village Name '  # ← Note trailing space in Gujarat data
            )
            
            name_local = normalize_field_name(
                v, 
                'villagelocalname', 
                'Village Name', 
                'Village name',
                'Village Name '  # ← Note trailing space
            )
            
            if code and code not in seen:
                seen.add(code)
                unique_villages.append({
                    'districtcode': district_code,
                    'subdistrictcode': v_taluka_code,
                    'villagecode': code,
                    'villagenameenglish': name_english,
                    'villagelocalname': name_local
                })
    
    logger.info(f"✅ Returning {len(unique_villages)} villages")
    return Response(unique_villages)



# =============================================================================
# ACTIVITY CATALOG VIEWSET
# =============================================================================

# views.py

class ActivityCatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing activity catalog
    """
    queryset = ActivityCatalog.objects.all()
    serializer_class = ActivityCatalogSerializer
    permission_classes = [AllowAny]   
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by source (api/custom)
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)
        
        # Filter by is_strict
        is_strict = self.request.query_params.get('is_strict')
        if is_strict is not None:
            queryset = queryset.filter(is_strict=is_strict.lower() == 'true')
        
        # Search by name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')
    
    @action(detail=False, methods=['post'])
    def create_global_activity(self, request):
        """
        Create a new global activity with farmer and mukkadam defaults
        
        POST /api/activities/create_global_activity/
        Body: {
            "name": "New Activity",
            "activity_type": "pruning",
            "default_rate_per_acre": 1000,
            "default_gap_days": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150,
            "is_strict": false,
            "estimated_workers_per_acre": 10
        }
        """
        serializer = CreateActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
            return Response(
                {'error': f'Activity "{data["name"]}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create activity in catalog
        activity = ActivityCatalog.objects.create(
            name=data['name'],
            activity_type=data.get('activity_type', ''),
            default_rate_per_acre=data['default_rate_per_acre'],
            is_strict=data['is_strict'],
            estimated_workers_per_acre=data['estimated_workers_per_acre'],
            default_gap_days=data['default_gap_days'],
            source='custom'
        )
        
        # Create global schedule rule
        ActivityScheduleRule.objects.create(
            activity=activity,
            gap_days=data['default_gap_days'],
            phase_order=ActivityScheduleRule.objects.count() + 1
        )
        
        # Note: Mukkadam defaults are stored per cluster, not globally
        # They will be used when clusters are created or when adding to clusters
        
        return Response(
            {
                'success': True,
                'message': f'Activity "{data["name"]}" created successfully',
                'activity': ActivityCatalogDetailSerializer(activity).data,
                'mukkadam_defaults': {
                    'rate_per_acre': data['mukkadam_rate_per_acre'],
                    'productivity_per_worker': data['mukkadam_productivity_per_worker']
                }
            },
            status=status.HTTP_201_CREATED
        )
    @action(detail=False, methods=['post'])
    def add_custom_activity(self, request):
        """
        Add a custom activity from frontend
        
        POST /api/activities/add_custom_activity/
        Body: {
            "name": "Custom Activity Name",
            "activity_type": "pruning",
            "is_strict": false,
            "default_rate_per_acre": 500,
            "estimated_workers_per_acre": 10
        }
        """
        name = request.data.get('name')
        activity_type = request.data.get('activity_type', '')
        is_strict = request.data.get('is_strict', False)
        default_rate = request.data.get('default_rate_per_acre', 0)
        estimated_workers = request.data.get('estimated_workers_per_acre', 10)
        
        if not name:
            return Response(
                {'error': 'Activity name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=name).exists():
            return Response(
                {'error': f'Activity "{name}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activity = ActivityCatalog.objects.create(
            name=name,
            activity_type=activity_type,
            is_strict=is_strict,
            default_rate_per_acre=default_rate,
            estimated_workers_per_acre=estimated_workers,
            source='custom'
        )
        
        serializer = self.get_serializer(activity)
        return Response(
            {
                'success': True,
                'message': f'Activity "{name}" created successfully',
                'activity': serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['patch'])
    def update_strict_status(self, request, pk=None):
        """
        Update strict status of an activity
        
        PATCH /api/activities/{id}/update_strict_status/
        Body: { "is_strict": true }
        """
        activity = self.get_object()
        is_strict = request.data.get('is_strict')
        
        if is_strict is None:
            return Response(
                {'error': 'is_strict field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activity.is_strict = is_strict
        activity.save()
        
        serializer = self.get_serializer(activity)
        return Response({
            'success': True,
            'message': f'Activity strict status updated',
            'activity': serializer.data
        })
    
# views.py - Inside ActivityCatalogViewSet class

    @action(detail=False, methods=['post'])
    def insert_between(self, request):  # ✅ Changed name and added 'self'
        """
        Insert a new activity between two existing activities in the lifecycle
        
        POST /api/activities/insert_between/
        Body: {
            "name": "New Activity Name",
            "activity_type": "pruning",
            "default_rate_per_acre": 1000,
            "gap_days_from_previous": 5,
            "insert_after_activity_id": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150,
            "is_strict": false,
            "estimated_workers_per_acre": 10
        }
        """
        serializer = InsertActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
            return Response(
                {'error': f'Activity "{data["name"]}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the activity we're inserting after
        try:
            previous_activity = ActivityCatalog.objects.get(id=data['insert_after_activity_id'])
        except ActivityCatalog.DoesNotExist:
            return Response(
                {'error': 'Previous activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get the previous activity's schedule rule
        try:
            previous_rule = ActivityScheduleRule.objects.get(activity=previous_activity)
            new_phase_order = previous_rule.phase_order + 1
        except ActivityScheduleRule.DoesNotExist:
            return Response(
                {'error': 'Previous activity has no schedule rule'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Create the new activity
            new_activity = ActivityCatalog.objects.create(
                name=data['name'],
                activity_type=data.get('activity_type', ''),
                default_rate_per_acre=data['default_rate_per_acre'],
                is_strict=data['is_strict'],
                estimated_workers_per_acre=data['estimated_workers_per_acre'],
                default_gap_days=data['gap_days_from_previous'],
                source='custom'
            )
            
            # Shift all activities after this one by +1 in phase_order
            ActivityScheduleRule.objects.filter(
                phase_order__gte=new_phase_order
            ).update(phase_order=models.F('phase_order') + 1)
            
            # Create schedule rule for new activity
            ActivityScheduleRule.objects.create(
                activity=new_activity,
                gap_days=data['gap_days_from_previous'],
                phase_order=new_phase_order
            )
            
            return Response({
                'success': True,
                'message': f'Activity "{data["name"]}" inserted after "{previous_activity.name}"',
                'activity': {
                    'id': new_activity.id,
                    'name': new_activity.name,
                    'phase_order': new_phase_order,
                    'gap_days': data['gap_days_from_previous'],
                    'inserted_after': previous_activity.name
                }
            }, status=status.HTTP_201_CREATED)


# =============================================================================
# JOB VIEWSET
# =============================================================================
class LeaveViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveSerializer

    def get_queryset(self):
        queryset = Leave.objects.all().select_related('mukkadam')

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        cluster_id = self.request.query_params.get('cluster_id')

        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)

        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        leave_type = self.request.query_params.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)

        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        return queryset.filter(is_active=True).order_by('date')

    @action(detail=False, methods=['get'])
    def check_availability(self, request):
        date = request.query_params.get('date')
        mukkadam_id = request.query_params.get('mukkadam_id')
        cluster_id = request.query_params.get('cluster_id')  # ⬅️ add

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_qs = Leave.objects.filter(
            date=date,
            is_active=True,
        )
        if cluster_id:
            base_qs = base_qs.filter(cluster_id=cluster_id)

        # 1) general holiday
        general_holiday = base_qs.filter(leave_type='general').first()
        if general_holiday:
            return Response({
                'available': False,
                'reason': 'holiday',
                'message': f'all team off: {general_holiday.reason}',
            })

        if mukkadam_id:
            from .models import Mukkadam

            try:
                mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            except Mukkadam.DoesNotExist:
                return Response(
                    {'error': 'Mukkadam not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            leave_qs = base_qs.filter(
                leave_type='mukkadam',
                mukkadam_id=mukkadam_id,
            )

            total_on_leave = leave_qs.aggregate(total=Sum('crew_on_leave'))['total'] or 0
            effective_crew = max(mukkadam.crew_size - total_on_leave, 0)

            return Response({
                'available': effective_crew > 0,
                'reason': 'mukkadam_partial_leave' if total_on_leave > 0 else 'no_leave',
                'message': (
                    f'{total_on_leave} workers on leave, {effective_crew} available'
                    if total_on_leave > 0
                    else 'No leave for this mukkadam'
                ),
                'crew_size': mukkadam.crew_size,
                'crew_on_leave': total_on_leave,
                'available_workers': effective_crew,
            })

        return Response({
            'available': True,
            'reason': 'no_leave',
            'message': 'Available for allocation',
        })

from django.db.models import Prefetch

class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        queryset = Job.objects.all().select_related('farmer', 'plot').prefetch_related(
            Prefetch(
                'activities',
                queryset=JobActivity.objects
                    .select_related('activity', 'plot')
                    .order_by('scheduled_date')
            )
        )

        status_filter = self.request.query_params.get('status')
        if status_filter:
            statuses = status_filter.split(',')
            queryset = queryset.filter(status__in=statuses)

        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)

        # NEW: filter jobs on a specific plot inside this cluster
        plot_id = self.request.query_params.get('plot')
        if plot_id:
            queryset = queryset.filter(plot_id=plot_id)

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        booking_type = self.request.query_params.get('booking_type')
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type)

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(scheduled_date__range=[start_date, end_date])

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(job_id__icontains=search) |
                Q(farmer__farmer_name__icontains=search)
            )

        farmer_id = self.request.query_params.get('farmer_id')
        if farmer_id:
            queryset = queryset.filter(farmer_id=farmer_id)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['get'])
    def activities_summary(self, request, pk=None):
        """
        Get detailed activities summary for a job
        
        GET /api/jobs/{job_id}/activities_summary/
        """
        job = self.get_object()
        activities = job.activities.all()
        
        summary = {
            'job_id': job.job_id,
            'farmer_name': job.farmer.farmer_name,
            'total_activities': activities.count(),
            'fully_allocated': activities.filter(is_fully_allocated=True).count(),
            'partially_allocated': activities.filter(
                allocated_area__gt=0,
                is_fully_allocated=False
            ).count(),
            'not_allocated': activities.filter(allocated_area=0).count(),
            'activities': []
        }
        
        for activity in activities:
            allocations = activity.allocations.all()
            
            activity_data = {
                'id': activity.id,
                'name': activity.activity.name,
                'is_strict': activity.activity.is_strict,
                'total_area': float(activity.total_area),
                'allocated_area': float(activity.allocated_area),
                'remaining_area': float(activity.remaining_area),
                'allocation_percentage': (
                    (activity.allocated_area / activity.total_area * 100) 
                    if activity.total_area > 0 else 0
                ),
                'scheduled_date': activity.scheduled_date,
                'allocation_count': allocations.count(),
                'status': activity.allocation_status
            }
            
            summary['activities'].append(activity_data)
        
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        job = self.get_object()
        data = request.data.copy()
        data['job'] = job.pk
        
        serializer = JobActivityCreateUpdateSerializer(
            data=data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        ja = serializer.save()
        
        return Response(
            JobActivitySerializer(ja).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Get financial summary for a job
        
        GET /api/jobs/{job_id}/financial_summary/
        """
        from .utils import calculate_job_financials
        
        job = self.get_object()
        financials = calculate_job_financials(job.job_id)
        
        if not financials:
            return Response(
                {'error': 'Unable to calculate financials'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(financials)
    
    @action(detail=False, methods=['get'])
    def pending_jobs(self, request):
        """
        Get all jobs with remaining work
        
        GET /api/jobs/pending_jobs/
        """
        jobs = self.get_queryset().filter(
            activities__is_fully_allocated=False
        ).distinct()
        
        serializer = self.get_serializer(jobs, many=True)
        return Response({
            'count': jobs.count(),
            'jobs': serializer.data
        })


from rest_framework.decorators import api_view
from datetime import datetime, timedelta

@api_view(['GET'])
def suggest_activity_date(request):
    """
    GET /api/activity-schedule/suggest-date/?base_date=2026-02-10&cluster_id=1&activity_id=5
    Returns: {"suggested_date": "2026-02-13"}
    """
    base_date_str = request.query_params.get('base_date')
    cluster_id = request.query_params.get('cluster_id')
    activity_id = request.query_params.get('activity_id')
    
    if not (base_date_str and cluster_id and activity_id):
        return Response(
            {'error': 'base_date, cluster_id, activity_id required'}, 
            status=400
        )
    
    try:
        base_date = datetime.strptime(base_date_str, '%Y-%m-%d').date()
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        gap = effective_gap_days(cluster, activity)
        suggested = base_date + timedelta(days=gap)
        return Response({'suggested_date': suggested.isoformat()})
    except Exception as e:
        return Response({'error': str(e)}, status=400)

from .utils import get_effective_crew_size 
from rest_framework.decorators import api_view
# =============================================================================
# MUKKADAM VIEWSET
# =============================================================================
class JobActivityViewSet(viewsets.ModelViewSet):
    queryset = JobActivity.objects.all().select_related('job', 'activity', 'plot')
    serializer_class = JobActivityCreateUpdateSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return JobActivitySerializer
        return JobActivityCreateUpdateSerializer
    
    def update(self, request, *args, **kwargs):
        """Override update to add validation for total_area"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Validate total_area if it's being updated
        new_total_area = request.data.get('total_area')
        if new_total_area is not None:
            new_total_area = Decimal(str(new_total_area))
            if new_total_area < instance.allocated_area:
                return Response(
                    {
                        'error': 'Total area cannot be less than allocated area',
                        'allocated_area': float(instance.allocated_area),
                        'requested_area': float(new_total_area)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """PATCH method"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


# views.py - Update MukkadamViewSet
# views.py - Add new viewset

class MukkadamActivityRateViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for mukkadam activity rates
    """
    queryset = MukkadamActivityRate.objects.all().select_related('mukkadam', 'activity')
    serializer_class = MukkadamActivityRateSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam__mukkadam_id=mukkadam_id)
        
        return queryset.filter(is_active=True).order_by('activity__name')
# views.py - Update MukkadamViewSet

class MukkadamViewSet(viewsets.ModelViewSet):
    queryset = Mukkadam.objects.all().select_related('cluster')
    serializer_class = MukkadamSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(mukkadam_name__icontains=search) | 
                Q(mobile_numbers__icontains=search)
            )
        
        return queryset.order_by('mukkadam_name')
    
    @action(detail=True, methods=['post'])
    def add_activity_rate(self, request, pk=None):
        """
        Add or update activity rate for mukkadam
        POST /api/mukkadams/{mukkadam_id}/add_activity_rate/
        
        Body: {
            "activity_id": 1,
            "rate_per_acre": 1000,
            "productivity_per_worker": 0.15
        }
        """
        mukkadam = self.get_object()
        activity_id = request.data.get('activity_id')
        rate_per_acre = request.data.get('rate_per_acre')
        productivity_per_worker = request.data.get('productivity_per_worker', 0.150)
        
        if not activity_id or not rate_per_acre:
            return Response(
                {'error': 'activity_id and rate_per_acre required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            activity = ActivityCatalog.objects.get(id=activity_id)
            
            rate_obj, created = MukkadamActivityRate.objects.update_or_create(
                mukkadam=mukkadam,
                activity=activity,
                defaults={
                    'rate_per_acre': rate_per_acre,
                    'productivity_per_worker': productivity_per_worker,
                    'is_active': True
                }
            )
            
            return Response({
                'success': True,
                'message': 'Activity rate added' if created else 'Activity rate updated',
                'rate': MukkadamActivityRateSerializer(rate_obj).data
            })
        except ActivityCatalog.DoesNotExist:
            return Response(
                {'error': 'Activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def activity_rates_with_fallback(self, request, pk=None):
        """
        Get all activities with rates (mukkadam-specific → cluster → global)
        GET /api/mukkadams/{mukkadam_id}/activity_rates_with_fallback/?cluster_id={cluster_id}
        """
        mukkadam = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = ActivityCatalog.objects.all().order_by('name')
        result = []
        
        for activity in activities:
            # 1. Try mukkadam-specific rate
            mukkadam_rate = MukkadamActivityRate.objects.filter(
                mukkadam=mukkadam,
                activity=activity,
                is_active=True
            ).first()
            
            if mukkadam_rate:
                rate = float(mukkadam_rate.rate_per_acre)
                productivity = float(mukkadam_rate.productivity_per_worker)
                source = 'mukkadam'
            else:
                # 2. Try cluster rate
                cluster_rate = ClusterActivityRate.objects.filter(
                    cluster=cluster,
                    activity=activity
                ).first()
                
                if cluster_rate:
                    rate = float(cluster_rate.rate_per_acre)
                    source = 'cluster'
                else:
                    # 3. Use global default
                    rate = float(activity.default_rate_per_acre)
                    source = 'global'
                
                productivity = 0.150  # Default productivity
            
            result.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'rate_per_acre': rate,
                'productivity_per_worker': productivity,
                'rate_source': source,
                'is_strict': activity.is_strict
            })
        
        return Response(result)
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """
        Get mukkadam availability for date range
        
        GET /api/mukkadams/{id}/availability/?start_date=2026-02-01&end_date=2026-02-28
        """
        mukkadam = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create availability for date range
        from datetime import datetime, timedelta
        
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        availabilities = []
        current = start
         # or wherever you put it

        while current <= end:
            availability, created = MukkadamAvailability.objects.get_or_create(
                mukkadam=mukkadam,
                date=current,
                defaults={
                    'available_crew_size': get_effective_crew_size(mukkadam, current),
                    'is_available': True,
                    'allocated_workers': 0
                }
            )
            availability.available_crew_size = get_effective_crew_size(mukkadam, current)
            availability.save()
            
            serializer = MukkadamAvailabilitySerializer(availability)
            availabilities.append(serializer.data)
            
            current += timedelta(days=1)
        
        return Response(availabilities)
    
    @action(detail=True, methods=['post'])
    def update_availability(self, request, pk=None):
        """
        Update mukkadam availability for a specific date
        
        POST /api/mukkadams/{id}/update_availability/
        Body: {
            "date": "2026-02-15",
            "available_crew_size": 8,
            "is_available": true,
            "is_on_leave": false
        }
        """
        mukkadam = self.get_object()
        date = request.data.get('date')
        
        if not date:
            return Response(
                {'error': 'date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available_crew_size = request.data.get('available_crew_size', mukkadam.crew_size)
        is_available = request.data.get('is_available', True)
        is_on_leave = request.data.get('is_on_leave', False)
        
        availability, created = MukkadamAvailability.objects.update_or_create(
            mukkadam=mukkadam,
            date=date,
            defaults={
                'available_crew_size': get_effective_crew_size(mukkadam, date),
                'is_available': is_available,
                'is_on_leave': is_on_leave,
                'is_manually_set': True  # Mark as manually updated
            }
        )
        availability.available_crew_size = get_effective_crew_size(mukkadam, date)
        availability.save()
        
        serializer = MukkadamAvailabilitySerializer(availability)
        return Response({
            'success': True,
            'message': f'Availability updated for {date}',
            'availability': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def activity_rates(self, request, pk=None):
        """
        Get all activity rates for a mukkadam
        
        GET /api/mukkadams/{id}/activity_rates/
        """
        mukkadam = self.get_object()
        rates = mukkadam.activity_rates.filter(is_active=True).select_related('activity')
        
        serializer = MukkadamActivityRateSerializer(rates, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def daily_capacity(self, request, pk=None):
        mukkadam = self.get_object()
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        availability = get_mukkadam_availability(mukkadam.mukkadam_id, date)
        if not availability:
            return Response(
                {'error': 'Unable to fetch availability'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(availability)
    @action(detail=True, methods=['get'])
    def remaining_capacity(self, request, pk=None):
        """
        GET /tender/api/mukkadams/{id}/remaining_capacity/?date=2026-02-09
        """
        mukkadam = self.get_object()
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        info = get_mukkadam_remaining_workers(mukkadam.mukkadam_id, date)

        return Response({
            'effective_crew_size': info['effective_crew'],
            'used_workers': info['used_workers'],
            'available_crew_size': info['remaining_workers'],
        })
    @action(detail=False, methods=['get'])
    def available_on_date(self, request):
        """
        Get all mukkadams available on a specific date
        
        GET /api/mukkadams/available_on_date/?date=2026-02-15&min_workers=5
        """
        from .utils import get_available_mukkadams
        
        date = request.query_params.get('date')
        min_workers = int(request.query_params.get('min_workers', 1))
        activity_id = request.query_params.get('activity_id')
        
        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available = get_available_mukkadams(date, min_workers, activity_id)
        
        return Response({
            'date': date,
            'count': len(available),
            'mukkadams': available
        })
    
    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Get financial summary for mukkadam
        
        GET /api/mukkadams/{id}/financial_summary/?start_date=2026-02-01&end_date=2026-02-28
        """
        from .utils import calculate_mukkadam_financials
        
        mukkadam = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        financials = calculate_mukkadam_financials(
            mukkadam.mukkadam_id,
            start_date,
            end_date
        )
        
        if not financials:
            return Response(
                {'error': 'Unable to calculate financials'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(financials)
    @action(detail=False, methods=['get'])
    def daily_capacity_all(self, request):
        """
        Get available_crew_size for all mukkadams for a given date.
        GET /tender/api/mukkadams/daily_capacity_all/?date=2026-02-06&cluster_id=1
        """
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date is required'}, status=400)

        from datetime import datetime
        date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # 👇 NEW: filter by cluster_id if provided
        cluster_id = request.query_params.get('cluster_id')
        qs = Mukkadam.objects.all()
        if cluster_id:
            qs = qs.filter(cluster_id=cluster_id)

        data = []
        for m in qs:
            availability = get_mukkadam_availability(m.mukkadam_id, date)
            data.append({
                'mukkadam_id': m.mukkadam_id,
                'available_crew_size': availability['available_crew_size'],
            })

        return Response(data)

        # inside AllocationViewSet or a small API view
    @action(detail=False, methods=['get'])
    def day_total_capacity(self, request):
        """
        GET /tender/api/mukkadams/day_total_capacity/?date=2026-02-21&cluster_id=1
        """
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date is required'}, status=400)

        date = datetime.strptime(date_str, "%Y-%m-%d").date()

        cluster_id = request.query_params.get('cluster_id')
        qs = Mukkadam.objects.all()
        if cluster_id:
            qs = qs.filter(cluster_id=cluster_id)

        total = 0
        for m in qs:
            availability = get_mukkadam_availability(m.mukkadam_id, date)
            total += availability['available_crew_size']

        return Response({'date': date_str, 'total_capacity': total})


# views.py - Add to MukkadamViewSet

    @action(detail=True, methods=['get'])
    def available_activities(self, request, pk=None):
        """
        Get all activities with rates (mukkadam-specific, cluster, or global)
        GET /api/mukkadams/{id}/available_activities/?cluster_id={cluster_id}
        """
        mukkadam = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = ActivityCatalog.objects.all().order_by('name')
        result = []
        
        for activity in activities:
            # Try mukkadam-specific rate first
            mukkadam_rate = MukkadamActivityRate.objects.filter(
                mukkadam=mukkadam,
                activity=activity,
                is_active=True
            ).first()
            
            if mukkadam_rate:
                rate = float(mukkadam_rate.rate_per_acre)
                productivity = float(mukkadam_rate.productivity_per_worker)
                source = 'mukkadam'
            else:
                # Try cluster rate
                cluster_rate = ClusterActivityRate.objects.filter(
                    cluster=cluster,
                    activity=activity
                ).first()
                
                if cluster_rate:
                    rate = float(cluster_rate.rate_per_acre)
                    source = 'cluster'
                else:
                    rate = float(activity.default_rate_per_acre)
                    source = 'global'
                
                productivity = 0.150  # Default
            
            result.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'rate_per_acre': rate,
                'productivity_per_worker': productivity,
                'rate_source': source,
                'is_strict': activity.is_strict
            })
        
        return Response(result)


from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime

class PlanningViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def by_activity_date(self, request):
        """
        For each activity in a cluster, check if remaining area on its
        scheduled_date can be done by all mukkadams of that cluster on that date.

        GET /tender/api/planning/by_activity_date/?cluster_id=1
        """
        cluster_id = request.query_params.get('cluster_id')
        if not cluster_id:
            return Response({'error': 'cluster_id is required'}, status=400)

        from .models import JobActivity, Mukkadam, MukkadamActivityRate

        # activities with a scheduled date and some remaining area
        activities = JobActivity.objects.filter(
            job__cluster_id=cluster_id,
            remaining_area__gt=0,
            scheduled_date__isnull=False,
        ).select_related("job__farmer", "activity")


        mukkadams = Mukkadam.objects.filter(cluster_id=cluster_id)

        results = []

        for ja in activities:
            remaining = float(ja.remaining_area or 0)
            if remaining <= 0:
                continue

            day = ja.scheduled_date
            if day is None:
                continue  # or handle missing date

            date_str = day.isoformat()

            # 3) capacity on that date only
            total_capacity_area = 0.0

            for m in mukkadams:
                # workers remaining for that mukkadam on that day
                info = get_mukkadam_remaining_workers(m.mukkadam_id, date_str)
                remaining_workers = info['remaining_workers']

                # activity-specific productivity for that mukkadam
                try:
                    rate = MukkadamActivityRate.objects.get(
                        mukkadam=m,
                        activity_id=ja.activity_id,
                        is_active=True,
                    )
                    prod = float(rate.productivity_per_worker)
                except MukkadamActivityRate.DoesNotExist:
                    prod = 0.0

                total_capacity_area += remaining_workers * prod

            deficit = max(remaining - total_capacity_area, 0.0)
            overloaded = deficit > 0

            results.append({
                'job_id': ja.job.job_id,
                'plot_name': ja.plot.name,
                'farmer_id': ja.job.farmer.farmer_id,
                'farmer_name': ja.job.farmer.farmer_name, 
                  'crop_name': ja.job.crop_name,
                  'variety_name': ja.job.variety,   
                'activity_id': ja.activity_id,
                'activity_name': ja.activity.name,
                'scheduled_date': date_str,
                'remaining_area': round(remaining, 2),
                'available_capacity_area': round(total_capacity_area, 2),
                'deficit': round(deficit, 2),
                'overloaded': overloaded,
            })


        return Response(results)

@api_view(['POST'])
def insert_activity_between(request):
    """
    Insert a new activity between two existing activities in the lifecycle
    
    POST /api/activities/insert_between/
    Body: {
        "name": "New Activity Name",
        "activity_type": "pruning",
        "default_rate_per_acre": 1000,
        "gap_days_from_previous": 5,
        "insert_after_activity_id": 7,  // Insert after this activity (e.g., after Pruning)
        "mukkadam_rate_per_acre": 800,
        "mukkadam_productivity_per_worker": 0.150,
        "is_strict": false,
        "estimated_workers_per_acre": 10
    }
    """
    serializer = InsertActivitySerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Check if activity already exists
    if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
        return Response(
            {'error': f'Activity "{data["name"]}" already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get the activity we're inserting after
    try:
        previous_activity = ActivityCatalog.objects.get(id=data['insert_after_activity_id'])
    except ActivityCatalog.DoesNotExist:
        return Response(
            {'error': 'Previous activity not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get the previous activity's schedule rule to find its phase_order
    try:
        previous_rule = ActivityScheduleRule.objects.get(activity=previous_activity)
        new_phase_order = previous_rule.phase_order + 1
    except ActivityScheduleRule.DoesNotExist:
        return Response(
            {'error': 'Previous activity has no schedule rule'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    with transaction.atomic():
        # Create the new activity
        new_activity = ActivityCatalog.objects.create(
            name=data['name'],
            activity_type=data.get('activity_type', ''),
            default_rate_per_acre=data['default_rate_per_acre'],
            is_strict=data['is_strict'],
            estimated_workers_per_acre=data['estimated_workers_per_acre'],
            default_gap_days=data['gap_days_from_previous'],
            source='custom'
        )
        
        # Shift all activities after this one by +1 in phase_order
        ActivityScheduleRule.objects.filter(
            phase_order__gte=new_phase_order
        ).update(phase_order=models.F('phase_order') + 1)
        
        # Create schedule rule for new activity
        ActivityScheduleRule.objects.create(
            activity=new_activity,
            gap_days=data['gap_days_from_previous'],
            phase_order=new_phase_order
        )
        
        return Response({
            'success': True,
            'message': f'Activity "{data["name"]}" inserted after "{previous_activity.name}"',
            'activity': {
                'id': new_activity.id,
                'name': new_activity.name,
                'phase_order': new_phase_order,
                'gap_days': data['gap_days_from_previous'],
                'inserted_after': previous_activity.name
            }
        }, status=status.HTTP_201_CREATED)


# views.py
class ExtraWorkerViewSet(viewsets.ModelViewSet):
    queryset = ExtraWorker.objects.all()
    serializer_class = ExtraWorkerSerializer

    def create(self, request, *args, **kwargs):
        mukkadam_id = request.data.get('mukkadam')
        date_str = request.data.get('date')
        workers = int(request.data.get('workers', 0))

        if not mukkadam_id or not date_str:
            return Response(
                {'detail': 'mukkadam and date are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        extra, _ = ExtraWorker.objects.update_or_create(
            mukkadam=mukkadam,
            date=date,
            defaults={'workers': workers},
        )

        serializer = self.get_serializer(extra)
        return Response(serializer.data, status=status.HTTP_200_OK)

# =============================================================================
# HELPER FUNCTIONS (if needed in views)
# =============================================================================

def generate_unique_payment_id():
    """Generate unique payment ID"""
    from django.utils import timezone
    timestamp = int(timezone.now().timestamp() * 1000)
    return timestamp

from decimal import Decimal
from django.db import transaction
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
# views.py
from rest_framework import viewsets, permissions
from .models import Cluster
from .serializers import ClusterSerializer

class ClusterViewSet(viewsets.ModelViewSet):
    queryset = Cluster.objects.all().order_by('name')
    serializer_class = ClusterSerializer
    permission_classes = [permissions.AllowAny]

    # optional: simple filter by state/district etc.
    def get_queryset(self):
        qs = super().get_queryset()
        state_code = self.request.query_params.get('state_code')
        district_code = self.request.query_params.get('district_code')
        if state_code:
            qs = qs.filter(state_code=state_code)
        if district_code:
            qs = qs.filter(district_code=district_code)
        return qs
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        """
        Add an activity to this cluster with custom rates
        Can either use existing activity_id or create new one with activity_name
        
        POST /api/clusters/{id}/add_activity/
        Body: {
            "activity_id": 5,  // OR "activity_name": "New Activity"
            "farmer_rate_per_acre": 1000,
            "gap_days": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150
        }
        """
        cluster = self.get_object()
        serializer = AddClusterActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get or create activity
        if 'activity_id' in data:
            try:
                activity = ActivityCatalog.objects.get(id=data['activity_id'])
            except ActivityCatalog.DoesNotExist:
                return Response(
                    {'error': 'Activity not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif 'activity_name' in data:
            # Create new activity if doesn't exist
            activity, created = ActivityCatalog.objects.get_or_create(
                name=data['activity_name'],
                defaults={
                    'source': 'custom',
                    'default_rate_per_acre': data['farmer_rate_per_acre'],
                    'default_gap_days': data['gap_days'],
                    'estimated_workers_per_acre': 10,
                }
            )
            
            if created:
                # Create global schedule rule
                ActivityScheduleRule.objects.create(
                    activity=activity,
                    gap_days=data['gap_days'],
                    phase_order=ActivityScheduleRule.objects.count() + 1
                )
        else:
            return Response(
                {'error': 'Either activity_id or activity_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add/Update farmer rate for cluster
        farmer_rate, created = ClusterActivityRate.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={'rate_per_acre': data['farmer_rate_per_acre']}
        )
        
        # Add/Update schedule rule for cluster
        schedule_rule, _ = ClusterActivityScheduleRule.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={'gap_days': data['gap_days']}
        )
        
        # Add/Update mukkadam default rate for cluster
        mukkadam_rate, _ = ClusterMukkadamActivityRate.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={
                'rate_per_acre': data['mukkadam_rate_per_acre'],
                'productivity_per_worker': data['mukkadam_productivity_per_worker']
            }
        )
        
        return Response({
            'success': True,
            'message': f'Activity "{activity.name}" {"created and " if created else ""}added to cluster "{cluster.name}"',
            'activity': {
                'id': activity.id,
                'name': activity.name,
                'farmer_rate': float(farmer_rate.rate_per_acre),
                'gap_days': schedule_rule.gap_days,
                'mukkadam_rate': float(mukkadam_rate.rate_per_acre),
                'mukkadam_productivity': float(mukkadam_rate.productivity_per_worker),
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def available_activities(self, request, pk=None):
        """
        Get all activities that can be added to this cluster
        
        GET /api/clusters/{id}/available_activities/
        """
        cluster = self.get_object()
        
        # Get activities already in cluster
        existing_activity_ids = ClusterActivityRate.objects.filter(
            cluster=cluster
        ).values_list('activity_id', flat=True)
        
        # Get all activities not yet in cluster
        available = ActivityCatalog.objects.exclude(
            id__in=existing_activity_ids
        ).values('id', 'name', 'activity_type', 'default_rate_per_acre', 'default_gap_days')
        
        return Response({
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'available_activities': list(available)
        })

class AllocationViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = Allocation.objects.all().select_related(
            'job_activity__job__farmer',
            'job_activity__activity',
            'mukkadam',
        )

        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            qs = qs.filter(cluster_id=cluster_id)

        return qs
    serializer_class = AllocationSerializer



    @action(detail=False, methods=['post'])
    def create_allocation(self, request):
        """
        Create allocation with productivity validation.
        """

        job_activity_id = request.data.get('job_activity_id')
        mukkadam_id = request.data.get('mukkadam_id')
        allocated_date = request.data.get('allocated_date')
        cluster_id = request.data.get('cluster_id')

        # Parse numbers as Decimal / int
        allocated_area = Decimal(str(request.data.get('allocated_area', '0')))
        allocated_workers = int(request.data.get('allocated_workers', 0))
        farmer_rate = Decimal(str(request.data.get('farmer_rate', '0')))
        mukkadam_rate = Decimal(str(request.data.get('mukkadam_rate', '0')))
        force = bool(request.data.get('force', False))
        skip_strict_check = bool(request.data.get('skip_strict_check', False))  # 👈 ADD THIS

        # Optional: basic cluster check
        if not cluster_id:
            return Response({'error': 'cluster_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 1) Validate
        can_allocate, message, warnings = check_can_allocate(
            job_activity_id,
            mukkadam_id,
            allocated_date,
            float(allocated_area),
            allocated_workers,
            skip_strict_check=skip_strict_check,  # 👈 PASS IT HERE
        )

        if not can_allocate:
            productivity_warning = warnings.get('productivity_warning', {})
            if not (force and productivity_warning.get('severity') == 'error'):
                return Response(
                    {'error': message, 'warnings': warnings},
                    status=status.HTTP_400_BAD_REQUEST,
                )


        # 2) Load objects
        try:
            job_activity = JobActivity.objects.get(id=job_activity_id)
            mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            cluster = Cluster.objects.get(id=cluster_id)  # 👈
        except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist, Cluster.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        # 3) Create allocation + update related models atomically
        try:
            with transaction.atomic():
                allocation = Allocation.objects.create(
                    job_activity=job_activity,
                    mukkadam=mukkadam,
                    allocated_date=allocated_date,
                    allocated_area=allocated_area,
                    allocated_workers=allocated_workers,
                    farmer_rate=farmer_rate,
                    mukkadam_rate=mukkadam_rate,
                    status='scheduled',
                    cluster=cluster,  # 👈 store cluster
                    created_by=request.user if request.user.is_authenticated else None,
                )

                job_activity.allocated_area += allocated_area
                job_activity.save()

                availability, _ = MukkadamAvailability.objects.get_or_create(
                    mukkadam=mukkadam,
                    date=allocated_date,
                    defaults={
                        'available_crew_size': mukkadam.crew_size,
                        'is_available': True,
                        'allocated_workers': 0,
                    },
                )
                availability.allocated_workers += allocated_workers
                availability.save()

                serializer = self.get_serializer(allocation)

                response_data = {
                    'success': True,
                    'allocation': serializer.data,
                    'message': 'Allocation created successfully',
                }

                if warnings:
                    response_data['warnings'] = warnings
                    if force:
                        response_data['message'] = (
                            'Allocation created with productivity override'
                        )

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Failed to create allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'])
    def validate_allocation(self, request):
        """
        Validate allocation BEFORE creating it
        Returns detailed warnings about productivity, capacity, etc.
        
        Frontend calls this FIRST to check if allocation is possible
        """
        job_activity_id = request.data.get('job_activity_id')
        mukkadam_id = request.data.get('mukkadam_id')
        allocated_area = float(request.data.get('allocated_area', 0))
        allocated_workers = int(request.data.get('allocated_workers', 0))
        skip_strict_check = bool(request.data.get('skip_strict_check', False))  # 👈 NEW
        
        allocated_date_str = request.data.get('allocated_date')

        try:
            allocated_date = datetime.strptime(allocated_date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"can_allocate": False, "error": "Invalid allocated_date", "warnings": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call check_can_allocate with skip_strict_check parameter
        result = check_can_allocate(
            job_activity_id, 
            mukkadam_id, 
            allocated_date,
            allocated_area, 
            allocated_workers,
            skip_strict_check=skip_strict_check  # 👈 PASS IT HERE
        )

        # Unpack the result
        if not result or len(result) != 3:
            return Response(
                {
                    "can_allocate": False,
                    "error": "Internal validation error",
                    "warnings": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        can_allocate, message, warnings = result

        # If validation failed, return error
        if not can_allocate:
            return Response({
                'can_allocate': False,
                'error': message,
                'warnings': warnings
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get rate information for preview
        try:
            job_activity = JobActivity.objects.get(id=job_activity_id)
            mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            
            mukkadam_rate_obj = mukkadam.activity_rates.get(
                activity=job_activity.activity,
                is_active=True
            )
            
            farmer_rate = float(job_activity.rate_per_acre)
            mukkadam_rate = float(mukkadam_rate_obj.rate_per_acre)
            
            # Calculate amounts
            farmer_amount = allocated_area * farmer_rate
            mukkadam_amount = allocated_area * mukkadam_rate
            profit = farmer_amount - mukkadam_amount
            
            return Response({
                'can_allocate': True,
                'message': message,
                'warnings': warnings,
                'preview': {
                    'job_id': job_activity.job.job_id,
                    'farmer_name': job_activity.job.farmer.farmer_name,
                    'activity': job_activity.activity.name,
                    'mukkadam': mukkadam.mukkadam_name,
                    'date': allocated_date,
                    'area': allocated_area,
                    'workers': allocated_workers,
                    'productivity': float(mukkadam_rate_obj.productivity_per_worker),
                    'max_capacity': allocated_workers * float(mukkadam_rate_obj.productivity_per_worker),
                    'pricing': {
                        'farmer_rate': farmer_rate,
                        'mukkadam_rate': mukkadam_rate,
                        'farmer_amount': farmer_amount,
                        'mukkadam_amount': mukkadam_amount,
                        'profit': profit,
                        'profit_margin': f"{(profit/farmer_amount)*100:.1f}%" if farmer_amount > 0 else "0%"
                    }
                }
            })
            
        except Exception as e:
            return Response({
                'can_allocate': True,
                'message': message,
                'warnings': warnings,
                'note': str(e)
            })
    @action(detail=True, methods=['post'])
    def update_productivity_and_reallocate(self, request, pk=None):
        """
        Update mukkadam's productivity for an activity and re-validate allocation
        
        Use case: User decides to update productivity instead of reducing area
        """
        allocation = self.get_object()
        new_productivity = float(request.data.get('productivity_per_worker'))
        
        try:
            # Update productivity
            mukkadam_rate = allocation.mukkadam.activity_rates.get(
                activity=allocation.job_activity.activity,
                is_active=True
            )
            
            old_productivity = float(mukkadam_rate.productivity_per_worker)
            mukkadam_rate.productivity_per_worker = new_productivity
            mukkadam_rate.save()
            
            # Re-validate with new productivity
            new_capacity = allocation.allocated_workers * new_productivity
            
            return Response({
                'success': True,
                'message': 'Productivity updated',
                'changes': {
                    'old_productivity': old_productivity,
                    'new_productivity': new_productivity,
                    'old_capacity': allocation.allocated_workers * old_productivity,
                    'new_capacity': new_capacity,
                    'allocated_area': float(allocation.allocated_area),
                    'can_complete': new_capacity >= float(allocation.allocated_area)
                }
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def productivity_report(self, request):
        """
        Get productivity report for all mukkadams
        Shows efficiency for each activity
        """
        mukkadam_id = request.query_params.get('mukkadam_id')
        
        if mukkadam_id:
            mukkadams = Mukkadam.objects.filter(mukkadam_id=mukkadam_id)
        else:
            mukkadams = Mukkadam.objects.all()
        
        report = []
        
        for mukkadam in mukkadams:
            rates = mukkadam.activity_rates.filter(is_active=True)
            
            mukkadam_data = {
                'mukkadam_id': mukkadam.mukkadam_id,
                'mukkadam_name': mukkadam.mukkadam_name,
                'crew_size': mukkadam.crew_size,
                'activities': []
            }
            
            for rate in rates:
                productivity = float(rate.productivity_per_worker)
                daily_capacity = mukkadam.crew_size * productivity
                
                mukkadam_data['activities'].append({
                    'activity': rate.activity.name,
                    'rate_per_acre': float(rate.rate_per_acre),
                    'productivity_per_worker': productivity,
                    'daily_capacity_with_full_crew': daily_capacity,
                    'efficiency_rating': (
                        'Excellent' if productivity >= 0.20 else
                        'Good' if productivity >= 0.15 else
                        'Average' if productivity >= 0.10 else
                        'Below Average'
                    )
                })
            
            report.append(mukkadam_data)
        
        return Response({'report': report})

    @action(detail=True, methods=['post'])
    def change_date(self, request, pk=None):
        allocation = self.get_object()
        date_str = request.data.get('allocated_date')
        
        if not date_str:
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            with transaction.atomic():
                # 1. TEMPORARILY "DELETE" the old impact to free up area
                job_act = allocation.job_activity
                job_act.allocated_area -= allocation.allocated_area
                job_act.save()

                # 2. VALIDATE if it can fit on the NEW date
                can_allocate, message, warnings = check_can_allocate(
                    job_act.id,
                    allocation.mukkadam.mukkadam_id,
                    new_date,
                    float(allocation.allocated_area),
                    allocation.allocated_workers,
                    skip_strict_check=False
                )

                if not can_allocate:
                    # ROLLBACK: Put the area back if validation fails
                    job_act.allocated_area += allocation.allocated_area
                    job_act.save()
                    return Response({'error': message, 'warnings': warnings}, status=status.HTTP_400_BAD_REQUEST)

                # 3. SUCCESS - Update Availability for OLD date
                old_avail = MukkadamAvailability.objects.filter(
                    mukkadam=allocation.mukkadam, 
                    date=allocation.allocated_date
                ).first()
                if old_avail:
                    old_avail.allocated_workers -= allocation.allocated_workers
                    old_avail.save()

                # 4. UPDATE Allocation to NEW date
                allocation.allocated_date = new_date
                allocation.save()

                # 5. UPDATE Job Activity and NEW date availability
                job_act.allocated_area += allocation.allocated_area
                job_act.save()

                new_avail, _ = MukkadamAvailability.objects.get_or_create(
                    mukkadam=allocation.mukkadam,
                    date=new_date,
                    defaults={'available_crew_size': allocation.mukkadam.crew_size}
                )
                new_avail.allocated_workers += allocation.allocated_workers
                new_avail.save()

            return Response({'success': True, 'message': 'Moved successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """
        Get allocations grouped by date for calendar view
        
        GET /api/allocations/calendar_view/?start_date=2026-01-31&end_date=2026-02-27
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date parameters required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get allocations in date range
        allocations = self.get_queryset().filter(
            allocated_date__range=[start_date, end_date]
        ).order_by('allocated_date')
        
        # Group by date
        calendar_data = {}
        for allocation in allocations:
            date_str = str(allocation.allocated_date)
            if date_str not in calendar_data:
                calendar_data[date_str] = []
            
            serializer = self.get_serializer(allocation)
            calendar_data[date_str].append(serializer.data)
        
        return Response(calendar_data)
 
    # views.py - Add to AllocationViewSet
# views.py - Add to AllocationViewSet

    @action(detail=True, methods=['patch'])
    def update_allocation(self, request, pk=None):
        """
        Update an existing allocation
        PATCH /api/allocations/{id}/update_allocation/?cluster_id={cluster_id}
        
        Editable: mukkadam, date, workers, area
        NOT editable: activity, job
        
        Reuses the same validation logic as create_allocation
        """
        allocation = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new values (or keep existing)
        mukkadam_id = request.data.get('mukkadam_id', allocation.mukkadam.mukkadam_id)
        allocated_date_str = request.data.get('allocated_date', str(allocation.allocated_date))
        allocated_workers = int(request.data.get('allocated_workers', allocation.allocated_workers))
        allocated_area = Decimal(str(request.data.get('allocated_area', allocation.allocated_area)))
        
        try:
            allocated_date = datetime.strptime(allocated_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # 1) TEMPORARILY ROLLBACK the old allocation impact
                old_job_activity = allocation.job_activity
                old_job_activity.allocated_area -= allocation.allocated_area
                old_job_activity.save()
                
                old_avail = MukkadamAvailability.objects.filter(
                    mukkadam=allocation.mukkadam,
                    date=allocation.allocated_date
                ).first()
                if old_avail:
                    old_avail.allocated_workers -= allocation.allocated_workers
                    old_avail.save()
                
                # 2) VALIDATE with new parameters (same as create_allocation)
                can_allocate, message, warnings = check_can_allocate(
                    old_job_activity.id,
                    mukkadam_id,
                    allocated_date,
                    float(allocated_area),
                    allocated_workers,
                    skip_strict_check=False  # Don't skip strict check for edits
                )
                
                if not can_allocate:
                    # ROLLBACK: Restore old values if validation fails
                    old_job_activity.allocated_area += allocation.allocated_area
                    old_job_activity.save()
                    if old_avail:
                        old_avail.allocated_workers += allocation.allocated_workers
                        old_avail.save()
                    
                    return Response(
                        {'error': message, 'warnings': warnings},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 3) Get new mukkadam and rates
                new_mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
                cluster = Cluster.objects.get(id=cluster_id)
                
                try:
                    mukkadam_rate_obj = new_mukkadam.activity_rates.get(
                        activity=old_job_activity.activity,
                        is_active=True
                    )
                    new_mukkadam_rate = mukkadam_rate_obj.rate_per_acre
                except MukkadamRate.DoesNotExist:
                    # ROLLBACK
                    old_job_activity.allocated_area += allocation.allocated_area
                    old_job_activity.save()
                    if old_avail:
                        old_avail.allocated_workers += allocation.allocated_workers
                        old_avail.save()
                    
                    return Response(
                        {'error': f'Mukkadam {new_mukkadam.mukkadam_name} does not have rate for {old_job_activity.activity.name}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 4) Apply new values
                allocation.mukkadam = new_mukkadam
                allocation.allocated_date = allocated_date
                allocation.allocated_workers = allocated_workers
                allocation.allocated_area = allocated_area
                allocation.mukkadam_rate = new_mukkadam_rate
                allocation.cluster = cluster
                # farmer_rate stays the same
                allocation.save()
                
                # 5) Update job activity with new area
                old_job_activity.allocated_area += allocated_area
                old_job_activity.save()
                
                # 6) Update new mukkadam availability
                new_avail, _ = MukkadamAvailability.objects.get_or_create(
                    mukkadam=new_mukkadam,
                    date=allocated_date,
                    defaults={
                        'available_crew_size': new_mukkadam.crew_size,
                        'is_available': True,
                        'allocated_workers': 0
                    }
                )
                new_avail.allocated_workers += allocated_workers
                new_avail.save()
                
                serializer = self.get_serializer(allocation)
                
                response_data = {
                    'success': True,
                    'allocation': serializer.data,
                    'message': 'Allocation updated successfully'
                }
                
                if warnings:
                    response_data['warnings'] = warnings
                
                return Response(response_data)
                
        except Mukkadam.DoesNotExist:
            return Response(
                {'error': 'Mukkadam not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to update allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_allocation(self, request, pk=None):
        allocation = self.get_object()

        with transaction.atomic():
            # 1) Restore job activity area
            job_activity = allocation.job_activity
            job_activity.allocated_area -= allocation.allocated_area
            job_activity.save()

            # 2) Restore mukkadam availability
            avail = MukkadamAvailability.objects.filter(
                mukkadam=allocation.mukkadam,
                date=allocation.allocated_date
            ).first()
            if avail:
                avail.allocated_workers -= allocation.allocated_workers
                avail.save()

            # 3) Now delete
            allocation.delete()

        return Response(
            {'success': True, 'message': 'Allocation deleted'},
            status=status.HTTP_204_NO_CONTENT,
        )


    @action(detail=False, methods=['post'])
    def auto_allocate_day(self, request):
        date_str = request.data.get('date')
        cluster_id = request.data.get('cluster_id')

        if not date_str or not cluster_id:
            return Response({'error': 'date and cluster_id are required'}, status=400)

        try:
            alloc_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            cluster = Cluster.objects.get(id=cluster_id)
        except (ValueError, Cluster.DoesNotExist):
            return Response({'error': 'Invalid date or cluster'}, status=400)

        job_activities = JobActivity.objects.filter(
            job__cluster=cluster,
            scheduled_date=alloc_date,
        ).select_related('activity', 'job__farmer', 'job__plot')

        job_activities = [
            ja for ja in job_activities 
            if float(ja.total_area - ja.allocated_area) > 0
        ]

        # ✅ Track workers used per mukkadam within this run
        workers_used_today = {}  # mukkadam_id -> workers already allocated today

        # Pre-load already existing allocations for this date
        existing_allocs = MukkadamAvailability.objects.filter(
            mukkadam__cluster=cluster,
            date=alloc_date,
        )
        for avail in existing_allocs:
            workers_used_today[avail.mukkadam_id] = avail.allocated_workers

        results = []
        failures = []

        for ja in job_activities:
            remaining_area = float(ja.total_area - ja.allocated_area)

            rate_obj = MukkadamActivityRate.objects.filter(
                activity=ja.activity,
                is_active=True,
                mukkadam__cluster=cluster,
            ).select_related('mukkadam').first()

            if not rate_obj:
                failures.append({
                    'job_activity_id': ja.id,
                    'job_id': ja.job.job_id,
                    'activity': ja.activity.name,
                    'farmer': ja.job.farmer.farmer_name,
                    'reason': 'No mukkadam with rate card for this activity',
                    'reason_code': 'NO_MUKKADAM',
                    'best_date': None,
                })
                continue

            mukkadam = rate_obj.mukkadam
            productivity = float(rate_obj.productivity_per_worker)

            # ✅ Available workers = crew - already used (existing + this run)
            already_used = workers_used_today.get(mukkadam.mukkadam_id, 0)
            available_workers = max(mukkadam.crew_size - already_used, 0)

            if available_workers == 0:
                # Find best future date
                best_date = _find_best_future_date(
                    ja, mukkadam, rate_obj, remaining_area,
                    math.ceil(remaining_area / productivity),
                    alloc_date, cluster
                )
                failures.append({
                    'job_activity_id': ja.id,
                    'job_id': ja.job.job_id,
                    'activity': ja.activity.name,
                    'farmer': ja.job.farmer.farmer_name,
                    'plot': ja.job.plot.plot_name if ja.job.plot else '',
                    'reason': f'No workers available — team fully booked today',
                    'reason_code': 'WORKER_CAPACITY',
                    'best_date': str(best_date) if best_date else None,
                    'mukkadam': mukkadam.mukkadam_name,
                    'area_needed': remaining_area,
                    'max_capacity': 0,
                })
                continue

            # ✅ Minimum workers needed, capped at available
            workers_needed = math.ceil(remaining_area / productivity)
            workers = min(workers_needed, available_workers)
            max_area_with_workers = round(workers * productivity, 2)

            # ✅ Check if available workers can cover full area
            if max_area_with_workers < remaining_area:
                # Cannot fully allocate — find best future date
                best_date = _find_best_future_date(
                    ja, mukkadam, rate_obj, remaining_area,
                    workers_needed,
                    alloc_date, cluster
                )
                failures.append({
                    'job_activity_id': ja.id,
                    'job_id': ja.job.job_id,
                    'activity': ja.activity.name,
                    'farmer': ja.job.farmer.farmer_name,
                    'plot': ja.job.plot.plot_name if ja.job.plot else '',
                    'reason': (
                        f'Only {available_workers} workers available '
                        f'(need {workers_needed}) — can cover '
                        f'{max_area_with_workers} ac of {remaining_date} ac'
                    ),
                    'reason_code': 'WORKER_CAPACITY',
                    'best_date': str(best_date) if best_date else None,
                    'mukkadam': mukkadam.mukkadam_name,
                    'area_needed': remaining_area,
                    'max_capacity': max_area_with_workers,
                })
                continue

            # ✅ Can fully allocate
            can_allocate, message, warnings = check_can_allocate(
                ja.id,
                mukkadam.mukkadam_id,
                alloc_date,
                remaining_area,
                workers,
                skip_strict_check=False,
            )

            if not can_allocate:
                best_date = _find_best_future_date(
                    ja, mukkadam, rate_obj, remaining_area,
                    workers, alloc_date, cluster
                )
                failures.append({
                    'job_activity_id': ja.id,
                    'job_id': ja.job.job_id,
                    'activity': ja.activity.name,
                    'farmer': ja.job.farmer.farmer_name,
                    'plot': ja.job.plot.plot_name if ja.job.plot else '',
                    'reason': message,
                    'reason_code': _classify_reason(message),
                    'best_date': str(best_date) if best_date else None,
                    'mukkadam': mukkadam.mukkadam_name,
                    'area_needed': remaining_area,
                    'max_capacity': max_area_with_workers,
                })
                continue

            try:
                with transaction.atomic():
                    allocation = Allocation.objects.create(
                        job_activity=ja,
                        mukkadam=mukkadam,
                        allocated_date=alloc_date,
                        allocated_area=Decimal(str(remaining_area)),
                        allocated_workers=workers,
                        farmer_rate=ja.rate_per_acre,
                        mukkadam_rate=rate_obj.rate_per_acre,
                        status='scheduled',
                        cluster=cluster,
                    )

                    ja.allocated_area += Decimal(str(remaining_area))
                    ja.save()

                    availability, _ = MukkadamAvailability.objects.get_or_create(
                        mukkadam=mukkadam,
                        date=alloc_date,
                        defaults={
                            'available_crew_size': mukkadam.crew_size,
                            'is_available': True,
                            'allocated_workers': 0,
                        },
                    )
                    availability.allocated_workers += workers
                    availability.save()

                    # ✅ Update local tracker so next job sees correct available workers
                    workers_used_today[mukkadam.mukkadam_id] = (
                        workers_used_today.get(mukkadam.mukkadam_id, 0) + workers
                    )

                    results.append({
                        'job_activity_id': ja.id,
                        'job_id': ja.job.job_id,
                        'activity': ja.activity.name,
                        'farmer': ja.job.farmer.farmer_name,
                        'mukkadam': mukkadam.mukkadam_name,
                        'area': remaining_area,
                        'workers': workers,
                        'status': 'allocated',
                    })

            except Exception as e:
                failures.append({
                    'job_activity_id': ja.id,
                    'job_id': ja.job.job_id,
                    'activity': ja.activity.name,
                    'farmer': ja.job.farmer.farmer_name,
                    'reason': str(e),
                    'reason_code': 'ERROR',
                    'best_date': None,
                })

        return Response({
            'success': True,
            'allocated': results,
            'failures': failures,
            'summary': f'{len(results)} allocated, {len(failures)} need attention',
        })
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Cluster
from .ervices.potential import compute_cluster_potential
@api_view(["GET"])
def cluster_potential_jobs(request, cluster_id: int):
    cluster = Cluster.objects.get(id=cluster_id)
    potential_map = compute_cluster_potential(cluster)
    
    out = {}
    for date_str, items in potential_map.items():
        out[date_str] = [
            {
                "date": p.date,
                "activityId": p.activity_id,
                "activityName": p.activity_name,
                "status": p.status, 
                "cropName": p.crop_name,
                "variety": p.variety,
                "unbookedArea": p.area,
                "clusterRate": p.cluster_rate,
                "potentialRevenue": p.potential_revenue,
                "farmerId": p.farmer_id,
                "farmerName": p.farmer_name,
                "plotId": p.plot_id,
                "plotName": p.plot_name,
                "jobId": p.job_id,
            }
            for p in items
        ]
    return Response(out)


# Example usage in views
def example_allocation_flow(request):
    """
    Example: Complete allocation flow with productivity validation
    
    This shows how frontend would interact with the API
    """
    
    # Step 1: Frontend gets allocation form data
    data = {
        'job_activity_id': 123,
        'mukkadam_id': 278,
        'allocated_date': '2026-02-15',
        'allocated_area': 2.0,
        'allocated_workers': 10,
        'farmer_rate': 1000,
        'mukkadam_rate': 800
    }
    
    # Step 2: Frontend calls validate_allocation endpoint
    # POST /api/allocations/validate_allocation/
    response = {
        'can_allocate': False,
        'error': 'Productivity constraint violated',
        'warnings': {
            'productivity_warning': {
                'severity': 'error',
                'message': 'Team cannot complete 2.0 acres in 1 day!',
                'details': {
                    'workers': 10,
                    'productivity_per_worker': '0.15 acres/worker/day',
                    'max_capacity': '1.5 acres/day',
                    'requested': '2.0 acres',
                    'deficit': '0.5 acres short'
                },
                'suggestions': [
                    {
                        'option': 'reduce_area',
                        'description': 'Allocate only 1.50 acres (what team can complete)',
                        'allocation': {
                            'area': 1.5,
                            'workers': 10,
                            'will_complete': True
                        }
                    },
                    {
                        'option': 'add_workers',
                        'description': 'Increase workers from 10 to 14 workers',
                        'allocation': {
                            'area': 2.0,
                            'workers': 14,
                            'will_complete': True,
                            'note': 'Need 4 more workers'
                        }
                    },
                    {
                        'option': 'update_productivity',
                        'description': 'Update productivity from 0.15 to 0.200 acres/worker/day',
                        'allocation': {
                            'area': 2.0,
                            'workers': 10,
                            'new_productivity': 0.2,
                            'will_complete': True
                        }
                    },
                    {
                        'option': 'split_days',
                        'description': 'Split: 1.50 acres today + 0.50 acres tomorrow',
                        'allocations': [
                            {'date': '2026-02-15', 'area': 1.5, 'workers': 10},
                            {'date': 'next_day', 'area': 0.5, 'workers': 10}
                        ]
                    }
                ]
            }
        }
    }
    
    # Step 3: Frontend shows modal with options
    # User chooses one of:
    
    # OPTION A: Reduce area to 1.5 acres
    data_updated = {**data, 'allocated_area': 1.5}
    # POST /api/allocations/create_allocation/ with updated data
    
    # OPTION B: Update productivity
    # POST /api/mukkadam-rates/update_rate_and_productivity/
    # Then POST /api/allocations/create_allocation/ with original data
    
    # OPTION C: Force allocation (override warning)
    data_force = {**data, 'force': True}
    # POST /api/allocations/create_allocation/ with force=true
    
    # OPTION D: Split into 2 allocations
    # POST /api/allocations/create_allocation/ (Day 1: 1.5 acres)
    # POST /api/allocations/create_allocation/ (Day 2: 0.5 acres)
    
    return response