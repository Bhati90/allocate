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
        all_activities = ActivityCatalog.objects.all()
        
        calendar = []
        for activity in all_activities:
            cluster_rate = ClusterActivityRate.objects.filter(
                cluster=cluster, activity=activity
            ).first()

            cluster_gap = ClusterActivityScheduleRule.objects.filter(
                cluster=cluster, activity=activity
            ).first()

            global_rule = ActivityScheduleRule.objects.filter(
                activity=activity
            ).first()

            # Use cluster override if exists, else global default
            farmer_rate = float(cluster_rate.rate_per_acre) if cluster_rate else float(activity.default_rate_per_acre)
            rate_overridden = bool(cluster_rate)

            gap_days = cluster_gap.gap_days if cluster_gap else (
                global_rule.gap_days if global_rule else activity.default_gap_days
            )
            gap_overridden = bool(cluster_gap)

            mukkadam_cluster_rate = ClusterMukkadamActivityRate.objects.filter(
                cluster=cluster, activity=activity
            ).first()

            mukkadam_rate = float(mukkadam_cluster_rate.rate_per_acre) if mukkadam_cluster_rate else farmer_rate * 0.8
            mukkadam_productivity = float(mukkadam_cluster_rate.productivity_per_worker) if mukkadam_cluster_rate else float(activity.estimated_workers_per_acre) if activity.estimated_workers_per_acre else 0.150
            mukkadam_rate_overridden = bool(mukkadam_cluster_rate)

            calendar.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'activity_type': activity.activity_type,
                'rate_per_acre': farmer_rate,
                'rate_overridden': rate_overridden,
                'gap_days': gap_days,
                'gap_overridden': gap_overridden,
                'mukkadam_rate_per_acre': mukkadam_rate,
                'mukkadam_productivity': mukkadam_productivity,
                'mukkadam_rate_overridden': mukkadam_rate_overridden,
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

@api_view(['GET', 'POST'])
def global_activity_catalog(request):
    if request.method == 'GET':
        activities = ActivityCatalog.objects.all()
        catalog_data = []
        
        for activity in activities:
            global_rule = ActivityScheduleRule.objects.filter(activity=activity).first()
            
            # 1. Use the actual model fields for the master defaults
            farmer_rate = float(activity.default_rate_per_acre)
            
            # Use estimated_workers_per_acre as the Global productivity default
            # Use a fallback only if the field is null
            mukkadam_productivity = float(activity.estimated_workers_per_acre) if activity.estimated_workers_per_acre else 0.150
            
            # Global Gap Days fallback logic
            gap_days = global_rule.gap_days if global_rule else activity.default_gap_days
            
            catalog_data.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'activity_type': activity.activity_type,
                'default_rate_per_acre': farmer_rate,
                'default_gap_days': gap_days,
                # For Global, we usually keep the 80% logic or 
                # you can add a 'default_mukkadam_rate' field to ActivityCatalog
                'mukkadam_default_rate': farmer_rate * 0.8, 
                'mukkadam_default_productivity': mukkadam_productivity, # <--- FIXED
                'is_strict': activity.is_strict,
                'phase_order': global_rule.phase_order if global_rule else 0,
            })

        catalog_data.sort(key=lambda x: x['phase_order'])
        return Response({'activities': catalog_data})

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
    queryset = Farmer.objects.all().prefetch_related('clusters')


    serializer_class = FarmerSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        
        queryset = super().get_queryset()
        
        # Filter by cluster
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(clusters__id=cluster_id)
        
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
    # ✅ M2M: filter plots where clusters contains this cluster
    plots = Plot.objects.filter(clusters__id=cluster_id).select_related('farmer')
    plot_list = [{
        'id': plot.id,
        'name': plot.name,
        'area_acres': float(plot.area_acres),
        'plot_code': plot.plot_code,
        'farmer_id': plot.farmer.farmer_id if plot.farmer else None,
        'farmer_name': plot.farmer.farmer_name if plot.farmer else None,
    } for plot in plots]
    return Response({'plots': plot_list})


class PlotViewSet(viewsets.ModelViewSet):
    queryset = Plot.objects.all().select_related('farmer').prefetch_related('clusters')
    serializer_class = PlotSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        qs = super().get_queryset()  # ✅ use 'qs' not 'queryset'
        
        farmer_id = self.request.query_params.get('farmer_id')
        if farmer_id:
            qs = qs.filter(farmer_id=farmer_id)
        
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            qs = qs.filter(clusters__id=cluster_id)
        
        return qs.order_by('-created_at')


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

@api_view(['GET'])
@permission_classes([AllowAny])
def search_villages(request):
    """
    Search villages by name prefix across all talukas for a state.
    GET /locations/search_villages/?state_code=MH&q=sat
    """
    state_code = request.query_params.get('state_code', '').strip().upper()
    q = request.query_params.get('q', '').strip().lower()

    if not state_code or not q:
        return Response([])

    state_file_mapping = {
        'MH': 'maharashtra_villages.json',
        'GJ': 'gujarat_villages.json',
    }

    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)

    all_villages = load_location_data(filename)

    results = []
    seen = set()

    for v in all_villages:
        if not isinstance(v, dict):
            continue

        name_en = normalize_field_name(v, 'villagenameenglish', 'Village Name', 'Village name', 'Village Name ')
        name_local = normalize_field_name(v, 'villagelocalname', 'Village Name', 'Village name', 'Village Name ')
        code = normalize_field_name(v, 'villagecode', 'Village Code', 'Village code')

        if not code or code in seen:
            continue

        if name_en.lower().startswith(q) or name_local.lower().startswith(q):
            seen.add(code)
            results.append({
                'villagecode': code,
                'villagenameenglish': name_en,
                'villagelocalname': name_local,
                'subdistrictcode': normalize_field_name(v, 'subdistrictcode', 'Subdistrict Code', 'Sub-District Code'),
                'districtcode': normalize_field_name(v, 'districtcode', 'District Code'),
            })

        if len(results) >= 30:
            break

    return Response(results)

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
            queryset = queryset.filter(cluster__id=cluster_id).distinct()


        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        leave_type = self.request.query_params.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)

        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        return queryset.filter(is_active=True).order_by('date')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        cluster_id = request.query_params.get('cluster_id')

        # ✅ For each general holiday, set crew_on_leave = total cluster crew
        for i, leave in enumerate(queryset):
            if leave.leave_type == 'general' and cluster_id:
                total_crew = Mukkadam.objects.filter(
                    clusters__id=cluster_id
                ).aggregate(
                    total=models.Sum('crew_size')
                )['total'] or 0

                data[i]['crew_on_leave'] = total_crew  # ✅ show total blocked workers
                data[i]['is_general_holiday'] = True   # ✅ flag for frontend

        return Response(data)

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
from decimal import Decimal
class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        queryset = Job.objects.all().select_related('farmer', 'plot').prefetch_related(
            'clusters',  # ✅ ADD THIS
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
            queryset = queryset.filter(clusters__id=cluster_id).distinct()

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
                'is_manually_moved': activity.is_manually_moved, 
                'remaining_area': float(activity.remaining_area),
                'allocation_percentage': (
                    (activity.allocated_area / activity.total_area * 100) 
                    if activity.total_area > 0 else 0
                ),
                'source': 'manual' if activity.is_manually_moved else 'ai',
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
    
    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        activity = self.get_object()
        
        new_date = request.data.get('new_date')
        area = request.data.get('area')
        reason = request.data.get('reason', '').strip()

        if not new_date:
            return Response({'error': 'new_date is required'}, status=400)
        
        if not reason:
            return Response({'error': 'reason is required'}, status=400)

        try:
            area = Decimal(str(area))
        except Exception:
            return Response({'error': 'Invalid area'}, status=400)
        
        if area <= 0:
            return Response({'error': 'Area must be greater than 0'}, status=400)
        
        if area > activity.remaining_area:
            return Response({
                'error': f'Area ({area}) exceeds remaining area ({activity.remaining_area})'
            }, status=400)
        
        activity.total_area = activity.total_area - area
        activity.save()
        
        new_activity = JobActivity.objects.create(
            job=activity.job,
            activity=activity.activity,
            plot=activity.plot,
            is_strict=activity.is_strict,
            total_area=area,
            allocated_area=Decimal('0'),
            remaining_area=area,
            scheduled_date=new_date,
            rate_per_acre=activity.rate_per_acre,
            transport_cost=activity.transport_cost,
            other_cost=activity.other_cost,
            estimated_workers=activity.estimated_workers,
            location=activity.location,
            is_manually_moved=True,
            lost_reason=reason,   # reuse lost_reason field to store move reason
            api_activity_id='',
        )
        
        return Response({
            'message': f'{area} ac moved to {new_date}',
            'reason': reason,
            'original_activity_id': activity.id,
            'original_remaining': float(activity.remaining_area),
            'new_activity_id': new_activity.id,
            'new_date': new_date,
            'new_area': float(area),
            'is_manually_moved': True,
        }, status=200)

# views.py - Update MukkadamViewSet
# views.py - Add new viewset
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def mukkadam_misc_costs(request, mukkadam_id, job_id):
    """
    GET  /api/mukkadam/<id>/job/<job_id>/misc/
    POST /api/mukkadam/<id>/job/<job_id>/misc/
    """
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
    except (Mukkadam.DoesNotExist, Job.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        costs = MukkadamMiscCost.objects.filter(mukkadam=mukkadam, job=job)
        return Response([{
            'id': c.id,
            'amount': float(c.amount),
            'reason': c.reason,
            'created_at': str(c.created_at.date()),
        } for c in costs])

    # POST — add new misc cost
    amount = request.data.get('amount')
    reason = request.data.get('reason', '').strip()

    if not amount or float(amount) <= 0:
        return Response({'error': 'Invalid amount'}, status=400)
    if not reason:
        return Response({'error': 'Reason is required'}, status=400)

    cost = MukkadamMiscCost.objects.create(
        mukkadam=mukkadam, job=job,
        amount=amount, reason=reason,
    )

    # Recalculate settlement net_payable
    _recalculate_settlement_misc(mukkadam, job)

    return Response({
        'id': cost.id,
        'amount': float(cost.amount),
        'reason': cost.reason,
        'created_at': str(cost.created_at.date()),
    }, status=201)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def mukkadam_misc_cost_delete(request, mukkadam_id, job_id, cost_id):
    """DELETE /api/mukkadam/<id>/job/<job_id>/misc/<cost_id>/"""
    try:
        cost = MukkadamMiscCost.objects.get(
            pk=cost_id, mukkadam_id=mukkadam_id, job__job_id=job_id
        )
    except MukkadamMiscCost.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    cost.delete()

    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
        _recalculate_settlement_misc(mukkadam, job)
    except Exception:
        pass

    return Response({'success': True})


def _recalculate_settlement_misc(mukkadam, job):
    """Update settlement net_payable after misc cost change."""
    from decimal import Decimal
    try:
        settlement = MukkadamJobSettlement.objects.get(mukkadam=mukkadam, job=job)
        total_misc = MukkadamMiscCost.objects.filter(
            mukkadam=mukkadam, job=job
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # net = payable + deposit_carried_forward - advance - weekly - misc
        settlement.net_payable = (
            settlement.payable_amount
            + settlement.deposit_carried_forward
            - settlement.advance_deducted
            - settlement.weekly_payments_deducted
            - total_misc
        )
        settlement.save()
    except MukkadamJobSettlement.DoesNotExist:
        pass
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
    queryset = Mukkadam.objects.all().prefetch_related('clusters')
    serializer_class = MukkadamSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(clusters__id=cluster_id).distinct()
        
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
            qs = qs.filter(clusters__id=cluster_id)

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
            qs = qs.filter(clusters__id=cluster_id)
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


    @action(detail=False, methods=['patch'])
    def add_day_crew(self, request):
        """
        Add extra workers to a mukkadam's base crew for a specific date.
        PATCH /api/mukkadams/add_day_crew/
        Body: {
            "mukkadam_id": 123,
            "date": "2026-02-18",
            "extra_crew": 5,
            "cluster_id": 1
        }
        """
        mukkadam_id = request.data.get('mukkadam_id')
        date_str = request.data.get('date')
        extra_crew = request.data.get('extra_crew', 0)

        if not mukkadam_id or not date_str:
            return Response(
                {'error': 'mukkadam_id and date are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            
            # Use update_or_create to store the manual adjustment
            # Assuming your MukkadamAvailability model has an 'extra_workers' field
            availability, created = MukkadamAvailability.objects.update_or_create(
                mukkadam=mukkadam,
                date=date_str,
                defaults={
                    'extra_workers': int(extra_crew),
                    'is_manually_set': True
                }
            )

            # Recalculate total effective crew for that day
            # This logic should be shared with your get_effective_crew_size util
            effective_size = get_effective_crew_size(mukkadam, date_str)
            availability.available_crew_size = effective_size
            availability.save()

            return Response({
                'success': True,
                'message': f'Added {extra_crew} extra workers for {mukkadam.mukkadam_name}',
                'new_total_capacity': effective_size
            })

        except Mukkadam.DoesNotExist:
            return Response({'error': 'Mukkadam not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

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
            job__clusters__id=cluster_id,
            remaining_area__gt=0,
            scheduled_date__isnull=False,
        ).select_related("job__farmer", "activity")


        mukkadams = Mukkadam.objects.filter(clusters__id=cluster_id)

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
                'plot_name': ja.plot.name if ja.plot else '',
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
    queryset = Cluster.objects.all().order_by('name').prefetch_related(
        'jobs__activities'  # prefetch for date_range calculation
    )
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
    
    @action(detail=True, methods=['post'], url_path='set_weekly_payment_day')
    def set_weekly_payment_day(self, request, pk=None):
        """
        Set the weekly payment day for a specific mukkadam in this cluster.
        
        POST /api/clusters/{id}/set_weekly_payment_day/
        Body: {
            "mukkadam_id": 123,
            "weekly_payment_day": 0   // 0=Monday ... 6=Sunday
        }
        """
        cluster = self.get_object()
        mukkadam_id = request.data.get('mukkadam_id')
        weekly_payment_day = request.data.get('weekly_payment_day')

        if mukkadam_id is None or weekly_payment_day is None:
            return Response(
                {'error': 'mukkadam_id and weekly_payment_day are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if weekly_payment_day not in range(7):
            return Response(
                {'error': 'weekly_payment_day must be between 0 (Monday) and 6 (Sunday)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            assignment = ClusterMukkadamAssignment.objects.get(
                cluster=cluster,
                mukkadam_id=mukkadam_id,
                is_active=True
            )
        except ClusterMukkadamAssignment.DoesNotExist:
            return Response(
                {'error': 'Mukkadam is not assigned to this cluster'},
                status=status.HTTP_404_NOT_FOUND
            )

        assignment.weekly_payment_day = weekly_payment_day
        assignment.save()

        day_name = dict(ClusterMukkadamAssignment.WEEKDAY_CHOICES)[weekly_payment_day]

        return Response({
            'success': True,
            'message': f'Weekly payment day set to {day_name} for {assignment.mukkadam.mukkadam_name} in {cluster.name}',
            'mukkadam_id': mukkadam_id,
            'cluster_id': cluster.id,
            'weekly_payment_day': weekly_payment_day,
            'weekly_payment_day_name': day_name,
            'weekly_payment_amount': float(assignment.get_weekly_payment_amount()),
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

# tender/views.py — ADD THESE

@api_view(['GET'])
@permission_classes([AllowAny])
def search_farmers_for_cluster(request, cluster_id):
    """
    Search farmers with their plots + cluster membership info.
    GET /api/clusters/<id>/search_farmers/?q=hemant
    """
    q = request.query_params.get('q', '').strip()
    
    farmers_qs = Farmer.objects.prefetch_related(
        'clusters',
        Prefetch('plots', queryset=Plot.objects.prefetch_related('clusters'))
    )
    if q:
        farmers_qs = farmers_qs.filter(
            Q(farmer_name__icontains=q) |
            Q(farmer_id__icontains=q) |
            Q(phone_number__icontains=q)
        )
    
    farmers_qs = farmers_qs[:20]
    
    result = []
    for farmer in farmers_qs:
        farmer_clusters = list(farmer.clusters.all())
        plots_data = []
        for plot in farmer.plots.all():
            plot_clusters = list(plot.clusters.all())
            in_this_cluster = any(pc.id == cluster_id for pc in plot_clusters)
            plots_data.append({
                'plot_id': plot.id,
                'plot_code': plot.plot_code,
                'name': plot.name,
                'area_acres': float(plot.area_acres),
                'crop_name': plot.crop_name,
                'in_this_cluster': in_this_cluster,
                'other_clusters': [
                    {'id': pc.id, 'name': pc.name}
                    for pc in plot_clusters if pc.id != cluster_id
                ],
            })
        
        result.append({
            'farmer_id': farmer.farmer_id,
            'farmer_name': farmer.farmer_name,
            'phone_number': farmer.phone_number,
            'location': farmer.location,
            'in_this_cluster': any(fc.id == cluster_id for fc in farmer_clusters),
            'other_clusters': [
                {'id': fc.id, 'name': fc.name}
                for fc in farmer_clusters if fc.id != cluster_id
            ],
            'plots': plots_data,
        })
    
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def add_farmer_plots_to_cluster(request, cluster_id):
    cluster = Cluster.objects.get(id=cluster_id)
    farmer_id = request.data.get('farmer_id')
    plot_ids = request.data.get('plot_ids', [])

    farmer = Farmer.objects.get(farmer_id=farmer_id)
    farmer.clusters.add(cluster)

    added_plots = []
    fixed_jobs = 0

    for plot_id in plot_ids:
        try:
            plot = Plot.objects.get(id=plot_id, farmer=farmer)
            plot.clusters.add(cluster)
            added_plots.append(plot.name)

            # ✅ Fix all jobs on this plot with no cluster
            jobs_on_plot = Job.objects.filter(plot=plot)
            for job in jobs_on_plot:
                job.clusters.add(cluster)
            fixed_jobs += jobs_on_plot.count()

        except Plot.DoesNotExist:
            pass

    return Response({
        'success': True,
        'farmer_name': farmer.farmer_name,
        'cluster_name': cluster.name,
        'plots_added': added_plots,
        'jobs_fixed': fixed_jobs,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def search_mukkadams_for_cluster(request, cluster_id):
    q = request.query_params.get('q', '').strip()
    
    mukkadams_qs = Mukkadam.objects.prefetch_related(
        'clusters',
        'activity_rates__activity'  # ✅ prefetch rates
    )
    if q:
        mukkadams_qs = mukkadams_qs.filter(
            Q(mukkadam_name__icontains=q) |
            Q(mobile_numbers__icontains=q)
        )
    
    mukkadams_qs = mukkadams_qs[:20]
    
    result = []
    for m in mukkadams_qs:
        m_clusters = list(m.clusters.all())

        # ✅ Use activity_rates (has real ID) instead of tender_activities JSON
        activities = [
            {
                'id': rate.id,
                'name': rate.activity.name,
                'price': float(rate.rate_per_acre or 0),
                'productivity': float(rate.productivity_per_worker or 0.15),
            }
            for rate in m.activity_rates.all()
        ]

        result.append({
            'id': m.mukkadam_id,
            'name': m.mukkadam_name,
            'mobile': m.mobile_numbers,
            'crew_size': m.crew_size,
            'max_crew_capacity': m.max_crew_capacity,
            'village': m.village,
            'district': m.district,
            'activities': activities,
            'in_this_cluster': any(mc.id == cluster_id for mc in m_clusters),
            'other_clusters': [
                {'id': mc.id, 'name': mc.name}
                for mc in m_clusters if mc.id != cluster_id
            ],
        })
    
    return Response(result)
@api_view(['POST'])
@permission_classes([AllowAny])
def add_mukkadam_to_cluster(request, cluster_id):
    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)

    mukkadam_id = request.data.get('mukkadam_id')
    transport_price = request.data.get('transport_price')
    weekly_payment_day = request.data.get('weekly_payment_day')
    advance_amount = request.data.get('advance_amount')
    weekly_amount = request.data.get('weekly_amount')

    if not mukkadam_id:
        return Response({'error': 'mukkadam_id required'}, status=400)

    if transport_price is None:
        return Response({'error': 'transport_price is required'}, status=400)

    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    if ClusterMukkadamAssignment.objects.filter(mukkadam=mukkadam, cluster=cluster, is_active=True).exists():
        return Response({'error': 'Mukkadam is already assigned to this cluster'}, status=400)

    if weekly_payment_day is not None and weekly_payment_day not in range(7):
        return Response({'error': 'weekly_payment_day must be 0 (Monday) to 6 (Sunday)'}, status=400)

    # Create assignment first
    assignment = ClusterMukkadamAssignment.objects.create(
        mukkadam=mukkadam,
        cluster=cluster,
        transport_price=transport_price,
        weekly_payment_day=weekly_payment_day,
        is_active=True,
    )

    # Override auto-calculated values if provided
    if advance_amount is not None:
        assignment.advance_amount = Decimal(str(advance_amount))
    if weekly_amount is not None:
        assignment.weekly_payment_amount = Decimal(str(weekly_amount))

    if advance_amount is not None or weekly_amount is not None:
        assignment.save()

    day_name = (
        dict(ClusterMukkadamAssignment.WEEKDAY_CHOICES)[weekly_payment_day]
        if weekly_payment_day is not None else None
    )

    return Response({
        'success': True,
        'mukkadam_name': mukkadam.mukkadam_name,
        'cluster_name': cluster.name,
        'crew_size': mukkadam.crew_size,
        'transport_price': float(assignment.transport_price),
        'advance_amount': float(assignment.advance_amount),
        'weekly_payment_amount': float(assignment.get_weekly_payment_amount()),
        'weekly_payment_day': weekly_payment_day,
        'weekly_payment_day_name': day_name,
        'message': (
            f'{mukkadam.mukkadam_name} added to {cluster.name}. '
            f'Advance: ₹{assignment.advance_amount}, '
            f'Transport: ₹{transport_price}, '
            f'Weekly: ₹{assignment.get_weekly_payment_amount()}'
            + (f' every {day_name}' if day_name else ' (payment day not set yet)')
        )
    }, status=201)

# tender/views.py - ADD THIS
# models.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Prefetch, Sum

@api_view(['GET'])
@permission_classes([AllowAny])
def tender_dashboard(request):
    """
    Single endpoint for the tender dashboard page.
    Returns mukkadams (tab 1) + farmers with plots/jobs/payments (tab 2).
    
    Query params:
    - cluster_id: filter farmers by cluster (optional)
    """
    cluster_id = request.query_params.get('cluster_id')

    # ============ MUKKADAMS ============
    mukkadams_qs = Mukkadam.objects.all().prefetch_related(
        'clusters',
        Prefetch(
            'activity_rates',
            queryset=MukkadamActivityRate.objects.filter(
                is_active=True
            ).select_related('activity'),
            to_attr='prefetched_rates'
        )
    )
    
    mukkadams_data = []
    for m in mukkadams_qs:
        activities = (m.tender_activities or {}).get('activities', [])
        # Filter out empty activities
        rates = m.prefetched_rates  # from prefetch above
        
        activity_rates = [
            {
                'rate_id': rate.id,                                    # ← key field
                'activity_id': rate.activity.id,
                'activity_name': rate.activity.name,
                'rate_per_acre': float(rate.rate_per_acre),
                'productivity_per_worker': float(rate.productivity_per_worker),
                'is_active': rate.is_active,
            }
            for rate in rates
        ]
        
        total_price = 0
        try:
            total_price = float((m.tender_activities or {}).get('total_price', 0) or 0)
        except (ValueError, TypeError):
            pass

        mukkadams_data.append({
            'id': m.mukkadam_id,
            'name': m.mukkadam_name,
            'mobile': m.mobile_numbers,
            'crew_size': m.crew_size,
            'max_crew_capacity': m.max_crew_capacity,
            'location': {
                'state': m.state,
                'district': m.district,
                'taluka': m.taluka,
                'village': m.village,
            },
            'availability': {
                'start_date': str(m.start_date) if m.start_date else None,
                'end_date': str(m.end_date) if m.end_date else None,
            },
            'activities': activity_rates,  
            'total_price': total_price,
            'reference_image_url': (m.tender_activities or {}).get('reference_image_url', ''),
            'efficiency': float(m.efficiency),
            'clusters': [
                {'id': c.id, 'name': c.name}
                for c in m.clusters.all()
            ],
        })

    # ============ FARMERS ============
    farmers_qs = Farmer.objects.prefetch_related(
        'clusters',
        Prefetch(
            'plots',
            queryset=Plot.objects.prefetch_related('clusters')
        ),
        Prefetch(
            'jobs',
            queryset=Job.objects.filter(booking_type='tender').prefetch_related(
                Prefetch(
                    'activities',
                    queryset=JobActivity.objects.select_related('activity', 'plot')
                ),
                'booking__payments'
            )
        )
    )

    # Apply cluster filter if provided
    if cluster_id:
        farmers_qs = farmers_qs.filter(clusters__id=cluster_id)

    farmers_data = []
    for farmer in farmers_qs:
        farmer_clusters = list(farmer.clusters.all())
        all_plots = list(farmer.plots.all())
        all_jobs = list(farmer.jobs.all())

        # Group plots by cluster
        # Group plots by cluster
        plots_by_cluster = {}
        for plot in all_plots:
            plot_clusters = list(plot.clusters.all())
            
            if plot_clusters:
                cluster_groups = [(str(pc.id), pc.id, pc.name) for pc in plot_clusters]
            else:
                cluster_groups = [('none', None, 'No Cluster')]
            
            # Find jobs for this plot
            plot_jobs = [j for j in all_jobs if j.plot_id == plot.id or
                        any(a.plot_id == plot.id for a in j.activities.all())]
            
            total_amount = sum(float(j.booking.total_amount) for j in plot_jobs if hasattr(j, 'booking'))
            advance_paid = sum(float(j.booking.advance_paid) for j in plot_jobs if hasattr(j, 'booking'))
            balance = total_amount - advance_paid

            plot_entry = {
                'plot_id': plot.id,
                'plot_code': plot.plot_code,
                'name': plot.name,
                'area_acres': float(plot.area_acres),
                'crop_name': getattr(plot, 'crop_name', ''),
                'variety': getattr(plot, 'variety', ''),
                'pruning_date': str(plot.pruning_date) if getattr(plot, 'pruning_date', None) else None,
                'jobs_count': len(plot_jobs),
                'payment_summary': {
                    'total_amount': total_amount,
                    'advance_paid': advance_paid,
                    'balance': balance,
                    'is_fully_paid': balance <= 0,
                },
                'jobs': [
                    {
                        'job_id': j.job_id,
                        'status': j.status,
                        'priority': j.priority,
                        'scheduled_date': str(j.scheduled_date) if j.scheduled_date else None,
                        'total_activities_amount': float(j.total_activities_amount),
                        'activities': [
                            {
                                'id': a.id,
                                'name': a.activity.name,
                                'total_area': float(a.total_area),
                                'allocated_area': float(a.allocated_area),
                                'remaining_area': float(a.remaining_area),
                                'scheduled_date': str(a.scheduled_date) if a.scheduled_date else None,
                                'total_price': float(a.total_price),
                                'allocation_status': a.allocation_status,
                            }
                            for a in j.activities.all()
                        ],
                        'booking': {
                            'booking_id': j.booking.booking_id,
                            'status': j.booking.status,
                            'total_amount': float(j.booking.total_amount),
                            'advance_paid': float(j.booking.advance_paid),
                            'balance': float(j.booking.balance),
                            'payments': [
                                {
                                    'payment_id': p.payment_id,
                                    'amount': float(p.amount),
                                    'mode': p.mode,
                                    'paid_at': str(p.paid_at),
                                    'paid_status': p.paid_status,
                                    'notes': p.notes,
                                }
                                for p in j.booking.payments.all()
                            ]
                        } if hasattr(j, 'booking') else None,
                    }
                    for j in plot_jobs
                ]
            }

            # ✅ Add plot to each cluster group it belongs to
            for cluster_key, cluster_id_val, cluster_name in cluster_groups:
                if cluster_key not in plots_by_cluster:
                    plots_by_cluster[cluster_key] = {
                        'cluster_id': cluster_id_val,
                        'cluster_name': cluster_name,
                        'plots': []
                    }
                plots_by_cluster[cluster_key]['plots'].append(plot_entry)

        # Overall payment summary for this farmer
        farmer_total = sum(
            float(j.booking.total_amount)
            for j in all_jobs if hasattr(j, 'booking')
        )
        farmer_advance = sum(
            float(j.booking.advance_paid)
            for j in all_jobs if hasattr(j, 'booking')
        )

        farmers_data.append({
            'farmer_id': farmer.farmer_id,
            'farmer_name': farmer.farmer_name,
            'phone_number': farmer.phone_number,
            'location': farmer.location,
            'clusters': [{'id': c.id, 'name': c.name} for c in farmer_clusters],
            'total_plots': len(all_plots),
            'total_jobs': len(all_jobs),
            'payment_summary': {
                'total_amount': farmer_total,
                'advance_paid': farmer_advance,
                'balance': farmer_total - farmer_advance,
            },
            'plots_by_cluster': list(plots_by_cluster.values()),
        })

    # ============ SUMMARY STATS ============
    total_mukkadams = len(mukkadams_data)
    total_farmers = len(farmers_data)

    return Response({
        'summary': {
            'total_mukkadams': total_mukkadams,
            'total_farmers': total_farmers,
            'total_tender_jobs': Job.objects.filter(booking_type='tender').count(),
        },
        'mukkadams': mukkadams_data,
        'farmers': farmers_data,
    })


# views.py
from .ervices.settlement import is_settlement_triggered,create_or_update_settlement

from django.utils import timezone



@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_settlement_detail(request, mukkadam_id, job_id):
    """
    GET /api/mukkadam/<id>/settlement/<job_id>/
    Returns full breakdown for frontend display.
    """
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
    except (Mukkadam.DoesNotExist, Job.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if not is_settlement_triggered(job):
        return Response({'triggered': False, 'message': 'Shoot selection not yet completed'})

    settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam, job=job
    ).first()

    if not settlement:
        cluster = job.clusters.first()
        settlement = create_or_update_settlement(mukkadam, job, cluster)

    # Build activity breakdown
    today = timezone.localdate()
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam,
        job_activity__job=job,
        job_activity__scheduled_date__lte=today,
    ).select_related('job_activity__activity', 'job_activity__plot')

    breakdown = []
    for a in allocations:
        breakdown.append({
            'activity_name': a.job_activity.activity.name,
            'plot_code': a.job_activity.plot.plot_code if a.job_activity.plot else '—',
            'scheduled_date': a.job_activity.scheduled_date,
            'allocated_area': float(a.allocated_area),
            'mukkadam_rate': float(a.mukkadam_rate),
            'gross_amount': float(a.mukkadam_amount),
        })

    weekly_applied = settlement.weekly_payments_applied.all().values(
        'payment_date', 'amount', 'crew_size_on_date'
    )

    return Response({
        'triggered': True,
        'mukkadam_name': mukkadam.mukkadam_name,
        'job_id': job.job_id,
        'farmer_name': job.farmer.farmer_name,
        'settlement_status': settlement.status,
        'breakdown': {
            'activities': breakdown,
            'gross_amount': float(settlement.gross_amount),
            'deposit_held_10pct': float(
                settlement.gross_amount * Decimal('10') / Decimal('100')
            ),
            'payable_90pct': float(settlement.payable_amount),
            'deposit_from_prev_job': float(settlement.deposit_carried_forward),
            'advance_deducted': float(settlement.advance_deducted),
            'weekly_payments': list(weekly_applied),
            'weekly_payments_total': float(settlement.weekly_payments_deducted),
            'net_payable': float(settlement.net_payable),
        },
        'show_raise_payment': settlement.net_payable > 0 and settlement.status == 'calculated',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def raise_mukkadam_payment(request, mukkadam_id, job_id):
    """
    POST /api/mukkadam/<id>/settlement/<job_id>/pay/
    Marks as paid in one click.
    """
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        settlement = MukkadamJobSettlement.objects.get(
            mukkadam=mukkadam, job__job_id=job_id
        )
    except (Mukkadam.DoesNotExist, MukkadamJobSettlement.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if settlement.net_payable <= 0:
        return Response({'error': 'No payment needed'}, status=400)

    if settlement.status == 'paid':
        return Response({'error': 'Already paid'}, status=400)

    with transaction.atomic():
        # Create MukkadamPayment record
        payment = MukkadamPayment.objects.create(
            mukkadam=mukkadam,
            payment_id=f"SETTLE-{job_id}-{mukkadam_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            amount=settlement.net_payable,
            mode='CASH',
            paid_at=timezone.now(),
            notes=f'Auto settlement for job {job_id}',
        )
        settlement.status = 'paid'
        settlement.paid_at = timezone.now()
        settlement.save(update_fields=['status', 'paid_at'])

    return Response({
        'success': True,
        'paid_amount': float(settlement.net_payable),
        'payment_id': payment.payment_id,
        'message': f'₹{settlement.net_payable} paid to {mukkadam.mukkadam_name}',
    })


# views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_all_settlements(request, mukkadam_id):
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    today = timezone.localdate()

    settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam
    ).select_related(
        'job', 'job__farmer', 'cluster'
    ).prefetch_related(
        'weekly_payments_applied'
    ).order_by('-created_at')

    data = []
    for s in settlements:

        # ── Activity breakdown for this settlement ──
        allocations = Allocation.objects.filter(
            mukkadam=mukkadam,
            job_activity__job=s.job,
            job_activity__scheduled_date__lte=today,
        ).select_related(
            'job_activity__activity',
            'job_activity__plot',
        ).order_by('job_activity__scheduled_date')

        activity_rows = []
        for a in allocations:
            ja = a.job_activity
            activity_rows.append({
                'activity_name': ja.activity.name,
                'plot_code': ja.plot.plot_code if ja.plot else '—',
                'plot_name': ja.plot.name if ja.plot else '—',
                'scheduled_date': str(ja.scheduled_date) if ja.scheduled_date else '—',
                'allocated_area': float(a.allocated_area),
                'mukkadam_rate': float(a.mukkadam_rate),
                'gross_amount': float(a.mukkadam_amount),
                'allocation_status': a.status,
            })

        # ── Weekly payments breakdown ──
        weekly_rows = []
        for w in s.weekly_payments_applied.all().order_by('payment_date'):
            weekly_rows.append({
                'payment_date': str(w.payment_date),
                'amount': float(w.amount),
                'crew_size': w.crew_size_on_date,
            })

        deposit_held = round(float(s.gross_amount) * 0.10, 2)

        data.append({
            'job_id': s.job.job_id,
            'farmer_name': s.job.farmer.farmer_name,
            'farmer_id': s.job.farmer.farmer_id,
            'cluster_name': s.cluster.name if s.cluster else '—',
            'status': s.status,
            'calculated_at': s.calculated_at,
            'paid_at': s.paid_at,

            # Financials
            'gross_amount': float(s.gross_amount),
            'deposit_held_10pct': deposit_held,
            'payable_90pct': float(s.payable_amount),
            'deposit_carried_forward': float(s.deposit_carried_forward),
            'advance_deducted': float(s.advance_deducted),
            'weekly_payments_deducted': float(s.weekly_payments_deducted),
            'net_payable': float(s.net_payable),

            # Breakdowns
            'activity_breakdown': activity_rows,
            'weekly_breakdown': weekly_rows,
        })

    total_gross = sum(s.gross_amount for s in settlements)
    total_paid = sum(
        s.net_payable for s in settlements
        if s.status == 'paid' and s.net_payable > 0
    )
    total_pending = sum(
        s.net_payable for s in settlements
        if s.status == 'calculated' and s.net_payable > 0
    )

    return Response({
        'mukkadam_name': mukkadam.mukkadam_name,
        'summary': {
            'total_jobs': len(data),
            'total_gross': float(total_gross),
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
        },
        'settlements': data,
    })

# views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def list_all_settlements(request):
    """
    GET /api/settlements/
    All settlements across all mukkadams — for the Payments tab.
    Supports: ?cluster_id=, ?status=, ?search=
    """
    qs = MukkadamJobSettlement.objects.select_related(
        'mukkadam', 'job', 'job__farmer', 'cluster'
    ).order_by('-created_at')

    # Filters
    cluster_id = request.query_params.get('cluster_id')
    status = request.query_params.get('status')
    search = request.query_params.get('search', '').strip()

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            models.Q(mukkadam__mukkadam_name__icontains=search) |
            models.Q(job__farmer__farmer_name__icontains=search) |
            models.Q(job__job_id__icontains=search)
        )

    data = []
    for s in qs:
        data.append({
            'mukkadam_id': s.mukkadam.pk,
            'mukkadam_name': s.mukkadam.mukkadam_name,
            'crew_size': s.mukkadam.crew_size,
            'job_id': s.job.job_id,
            'farmer_name': s.job.farmer.farmer_name,
            'farmer_id': s.job.farmer.farmer_id,
            'cluster_name': s.cluster.name if s.cluster else '—',
            'gross_amount': float(s.gross_amount),
            'advance_deducted': float(s.advance_deducted),
            'weekly_payments_deducted': float(s.weekly_payments_deducted),
            'net_payable': float(s.net_payable),
            'status': s.status,
            'calculated_at': s.calculated_at,
            'paid_at': s.paid_at,
        })

    return Response(data)



from tender.ervices.farmerbill import get_farmer_billing_for_job
from django.utils import timezone

@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_job_billing(request, farmer_id, job_id):
    """GET /api/farmer/<farmer_id>/job/<job_id>/billing/"""
    data = get_farmer_billing_for_job(job_id)
    if not data:
        return Response({'error': 'Job not found'}, status=404)
    if data['farmer_id'] != farmer_id:
        return Response({'error': 'Job does not belong to this farmer'}, status=400)
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_all_jobs_billing(request, farmer_id):
    """GET /api/farmer/<farmer_id>/billing/  — all jobs for this farmer"""
    jobs = Job.objects.filter(farmer_id=farmer_id).values_list('job_id', flat=True)
    results = []
    for job_id in jobs:
        billing = get_farmer_billing_for_job(job_id)
        if billing:
            results.append(billing)
    return Response(results)


@api_view(['POST'])
@permission_classes([AllowAny])
def record_farmer_payment(request, farmer_id, job_id):
    """
    POST /api/farmer/<farmer_id>/job/<job_id>/payment/
    Body: { amount, mode, notes }
    """
    try:
        job = Job.objects.get(job_id=job_id, farmer_id=farmer_id)
        booking = job.booking
    except (Job.DoesNotExist, JobBooking.DoesNotExist):
        return Response({'error': 'Job or booking not found'}, status=404)

    amount = request.data.get('amount')
    mode = request.data.get('mode', 'CASH')
    notes = request.data.get('notes', '')

    if not amount or float(amount) <= 0:
        return Response({'error': 'Invalid amount'}, status=400)

    payment = FarmerPayment.objects.create(
        booking=booking,
        payment_id=int(timezone.now().timestamp() * 1000),  # simple unique id
        mode=mode,
        amount=amount,
        notes=notes,
        paid_at=timezone.now(),
    )

    # Update booking balance
    total_paid = booking.advance_paid + FarmerPayment.objects.filter(
        booking=booking
    ).aggregate(total=Sum('amount'))['total'] or 0
    booking.balance = booking.total_amount - total_paid
    booking.advance_paid = booking.advance_paid  # unchanged
    if booking.balance <= 0:
        booking.status = 'PAID'
    elif total_paid > 0:
        booking.status = 'PARTIALLY_PAID'
    booking.save()

    return Response({
        'success': True,
        'payment_id': payment.payment_id,
        'amount_recorded': float(payment.amount),
        'new_balance': float(booking.balance),
        'message': f'₹{float(amount):,.0f} recorded successfully',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def cluster_payment_dashboard(request, cluster_id):
    """
    GET /api/cluster/<cluster_id>/payment-dashboard/
    Returns farmer billing + mukkadam settlements for this cluster.
    """
    from datetime import date
    from decimal import Decimal
    from django.db.models import Sum, Q

    today = date.today()

    # ── FARMERS ──────────────────────────────────────────────
    # Farmers whose plots are in this cluster → jobs → activities
    farmers_in_cluster = Farmer.objects.filter(clusters__id=cluster_id).distinct()

    farmer_data = []
    for farmer in farmers_in_cluster:
        # Get all jobs for this farmer that have activities in this cluster
        jobs = Job.objects.filter(
            farmer=farmer,
            activities__plot__clusters__id=cluster_id
        ).distinct().prefetch_related('activities', 'booking')

        for job in jobs:
            try:
                booking = job.booking
            except JobBooking.DoesNotExist:
                booking = None

            activities = job.activities.filter(
                plot__clusters__id=cluster_id
            ).select_related('activity', 'plot').order_by('scheduled_date')

            activity_rows = []
            total_billable = Decimal('0')
            all_past = True

            for act in activities:
                is_past = act.scheduled_date and act.scheduled_date <= today
                if not is_past:
                    all_past = False

                billable = Decimal('0')
                if is_past and act.allocated_area and act.rate_per_acre:
                    billable = (act.allocated_area * act.rate_per_acre).quantize(Decimal('0.01'))
                    total_billable += billable

                activity_rows.append({
                    'activity_id': act.id,
                    'activity_name': act.activity.name,
                    'plot_code': act.plot.plot_code if act.plot else '—',
                    'scheduled_date': str(act.scheduled_date) if act.scheduled_date else None,
                    'is_past': is_past,
                    'allocated_area': float(act.allocated_area or 0),
                    'total_area': float(act.total_area or 0),
                    'rate_per_acre': float(act.rate_per_acre or 0),
                    'billable_amount': float(billable),
                    'allocation_status': act.allocation_status,
                })

            advance_paid = Decimal(str(booking.advance_paid)) if booking else Decimal('0')
            additional_paid = Decimal('0')
            payment_history = []

            if booking:
                fps = FarmerPayment.objects.filter(booking=booking).order_by('paid_at')
                additional_paid = sum(Decimal(str(p.amount)) for p in fps)
                if advance_paid > 0:
                    payment_history.append({
                        'type': 'advance', 'date': str(booking.created_at.date()),
                        'amount': float(advance_paid), 'mode': 'Advance', 'notes': 'Initial advance',
                    })
                for p in fps:
                    payment_history.append({
                        'type': 'payment', 'date': str(p.paid_at.date()),
                        'amount': float(p.amount), 'mode': p.mode, 'notes': p.notes,
                    })
            
            total_paid = advance_paid + additional_paid
            balance_due = total_billable - total_paid
            booking_total = Decimal(str(booking.total_amount)) if booking else Decimal('0')
            final_gap = (booking_total - total_paid) if all_past and booking else Decimal('0')

            farmer_data.append({
                'farmer_id': farmer.farmer_id,
                'farmer_name': farmer.farmer_name,
                'phone_number': farmer.phone_number,
                'job_id': job.job_id,
                'booking_id': booking.booking_id if booking else None,
                'booking_total': float(booking_total),
                'activities': activity_rows,
                'summary': {
                    'total_billable_so_far': float(total_billable),
                    'advance_paid': float(advance_paid),
                    'additional_paid': float(additional_paid),
                    'total_paid': float(total_paid),
                    'balance_due': float(balance_due),
                    'all_activities_past': all_past,
                    'final_gap': float(final_gap),
                    'show_collect_button': balance_due > Decimal('0.01'),
                    'show_final_collection': all_past and final_gap > Decimal('0.01'),
                },
                'payment_history': payment_history,
            })

    # ── MUKKADAMS ─────────────────────────────────────────────
    # Mukkadams assigned to this cluster via ClusterMukkadamAssignment
    assignments = ClusterMukkadamAssignment.objects.filter(
        cluster_id=cluster_id
    ).select_related('mukkadam')

    mukkadam_data = []
    for assignment in assignments:
        mukkadam = assignment.mukkadam

        settlements = MukkadamJobSettlement.objects.filter(
            mukkadam=mukkadam,
            cluster_id=cluster_id
        ).select_related('job', 'job__farmer').order_by('-created_at')

        settlement_rows = []
        for s in settlements:
            # Activity breakdown
            allocations = Allocation.objects.filter(
                mukkadam=mukkadam,
                job_activity__job=s.job,
            ).select_related('job_activity__activity', 'job_activity__plot')

            activities = []
            for alloc in allocations:
                act = alloc.job_activity
                activities.append({
                    'activity_name': act.activity.name,
                    'plot_code': act.plot.plot_code if act.plot else '—',
                    'scheduled_date': str(act.scheduled_date) if act.scheduled_date else None,
                    'allocated_area': float(alloc.allocated_area or 0),
                    'mukkadam_rate': float(alloc.mukkadam_rate or 0),
                    'gross_amount': float(alloc.mukkadam_amount or 0),
                    'allocation_status': act.allocation_status,
                })

            # Weekly payments
            weekly = list(s.weekly_payments_applied.all().values(
                'payment_date', 'amount', 'crew_size_on_date'
            ))

            
            misc_costs = MukkadamMiscCost.objects.filter(
                mukkadam=mukkadam, job=s.job
            )
            total_misc = sum(float(c.amount) for c in misc_costs)
            settlement_rows.append({
                'job_id': s.job.job_id,
                'misc_costs': [{
                    'id': c.id,
                    'amount': float(c.amount),
                    'reason': c.reason,
                    'created_at': str(c.created_at.date()),
                } for c in misc_costs],
                'total_misc': total_misc,
                'farmer_name': s.job.farmer.farmer_name,
                'farmer_id': s.job.farmer.farmer_id,
                'status': s.status,
                'gross_amount': float(s.gross_amount),
                'deposit_held': float(s.gross_amount * Decimal('0.1')),
                'payable_90pct': float(s.payable_amount),
                'advance_deducted': float(s.advance_deducted),
                'weekly_payments_deducted': float(s.weekly_payments_deducted),
                'net_payable': float(s.net_payable),
                'calculated_at': str(s.calculated_at.date()) if s.calculated_at else None,
                'paid_at': str(s.paid_at.date()) if s.paid_at else None,
                'show_raise_payment': s.status == 'calculated' and s.net_payable > 0,
                'activities': activities,
                'weekly_payments': [
                    {
                        'payment_date': str(w['payment_date']),
                        'amount': float(w['amount']),
                        'crew_size_on_date': w['crew_size_on_date'],
                    } for w in weekly
                ],
                'weekly_payments_total': float(s.weekly_payments_deducted),
            })

        total_net = sum(s['net_payable'] for s in settlement_rows if s['status'] == 'calculated')
        total_paid_out = sum(s['net_payable'] for s in settlement_rows if s['status'] == 'paid')

        mukkadam_data.append({
            'mukkadam_id': mukkadam.mukkadam_id,
            'mukkadam_name': mukkadam.mukkadam_name,
            'mobile': mukkadam.mobile_numbers,
            'crew_size': mukkadam.crew_size,
            'advance_amount': float(assignment.advance_amount or 0),
            'settlements': settlement_rows,
            'summary': {
                'total_jobs': len(settlement_rows),
                'pending_payment': float(total_net),
                'total_paid_out': float(total_paid_out),
            },
        })

    # ── CLUSTER SUMMARY ───────────────────────────────────────
    total_farmer_due = sum(
        max(0, f['summary']['balance_due']) for f in farmer_data
    )
    total_mukkadam_due = sum(
        max(0, m['summary']['pending_payment']) for m in mukkadam_data
    )

    return Response({
        'cluster_id': cluster_id,
        'farmer_count': len(set(f['farmer_id'] for f in farmer_data)),
        'mukkadam_count': len(mukkadam_data),
        'total_farmer_due': float(total_farmer_due),
        'total_mukkadam_due': float(total_mukkadam_due),
        'farmers': farmer_data,
        'mukkadams': mukkadam_data,
    })


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