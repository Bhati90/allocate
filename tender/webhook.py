# views.py or webhooks.py

import logging
import requests
from decimal import Decimal
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from tender.models import (
    Farmer, Job, Plot, JobActivity, Cluster,
    ActivityCatalog, WebhookLog
)

logger = logging.getLogger(__name__)

# Configure your farmer API base URL
FARMER_API_BASE_URL = "https://demand.bharatintelligence.ai/fir"  # UPDATE THIS
FARMER_API_TOKEN = "e8fa8310c9af344ca22ec6bd23960d609b09c704"
# webhook.py



def fetch_farmer_details(farmer_id: str):
    """Fetch farmer details from external API"""
    try:
        response = requests.get(
            f"{FARMER_API_BASE_URL}/api/get_farmer_details/{farmer_id}/",
            headers={"Authorization": f"Token {FARMER_API_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        logger.error(f"Failed to fetch farmer {farmer_id}: {str(e)}")
        return None, str(e)


def match_cluster_by_location(village: str, taluka: str, district: str):
    """
    Match cluster by checking if village, taluka, and district ALL match
    Returns cluster or None
    """
    if not (village and taluka and district):
        return None
    
    clusters = Cluster.objects.all()
    
    for cluster in clusters:
        # Check if all three match
        village_match = village.lower() in [v.lower() for v in (cluster.villages or [])]
        taluka_match = taluka.lower() in [t.lower() for t in (cluster.talukas or [])]
        district_match = district.lower() in [d.lower() for d in (cluster.districts or [])]
        
        if village_match and taluka_match and district_match:
            return cluster
    
    return None


def get_or_create_activity(activity_name: str):
    """Get or create activity in catalog"""
    activity, created = ActivityCatalog.objects.get_or_create(
        name=activity_name,
        defaults={
            'source': 'api',
            'default_rate_per_acre': 0,
            'estimated_workers_per_acre': 10,
            'default_gap_days': 3,
        }
    )
    return activity, created


def safe_update_farmer(farmer_id: str, webhook_data: dict, farmer_details: dict, matched_cluster):
    """
    Safely update farmer with only valid fields
    """
    # Get all valid field names from Farmer model
    valid_fields = {f.name for f in Farmer._meta.get_fields() if not f.many_to_many and not f.one_to_many}
    
    # Build defaults with only valid fields
    farmer_defaults = {
        'cluster': matched_cluster,
    }
    
    # Try to add farmer_name
    if 'farmer_name' in valid_fields:
        farmer_defaults['farmer_name'] = webhook_data.get('farmer_name', f"Farmer {farmer_id}")
    
    # If farmer API returned data, use it
    if farmer_details:
        # Map common field names (only if they exist in model)
        field_mapping = {
            'name': 'farmer_name',
            'village': 'village',
            'taluka': 'taluka', 
            'district': 'district',
            'state': 'state',
            'phone': 'phone',
            'mobile': 'phone',
            'latitude': 'latitude',
            'longitude': 'longitude',
        }
        
        for api_field, model_field in field_mapping.items():
            if model_field in valid_fields and api_field in farmer_details:
                value = farmer_details[api_field]
                if value:  # Only set non-empty values
                    farmer_defaults[model_field] = value
    
    return Farmer.objects.update_or_create(
        farmer_id=farmer_id,
        defaults=farmer_defaults
    )

def safe_update_plot(plot_code: str, farmer, matched_cluster, plot_data: dict):
    """
    Safely update plot with only valid fields
    """
    # Get all valid field names from Plot model
    valid_fields = {f.name for f in Plot._meta.get_fields() if not f.many_to_many and not f.one_to_many}
    
    plot_defaults = {
        'farmer': farmer,
        'cluster': matched_cluster,
    }
    
    # Map common field names (only if they exist in model)
    field_mapping = {
        'name': 'name',
        'plot_name': 'name',
        'area_acres': 'area_acres',
        'area': 'area_acres',
        'latitude': 'latitude',
        'longitude': 'longitude',
        'village': 'village',
        'crop_name': 'crop_name',
        'variety': 'variety',
    }
    
    for api_field, model_field in field_mapping.items():
        if model_field in valid_fields and api_field in plot_data:
            value = plot_data[api_field]
            if value is not None:  # Allow 0 but not None
                plot_defaults[model_field] = value
    
    # CRITICAL: Ensure area_acres has a default value if required
    if 'area_acres' in valid_fields and 'area_acres' not in plot_defaults:
        plot_defaults['area_acres'] = 0.0  # Default to 0 if not provided
    
    # Default name if not provided
    if 'name' in valid_fields and 'name' not in plot_defaults:
        plot_defaults['name'] = f"Plot {plot_code}"
    
    return Plot.objects.update_or_create(
        plot_code=plot_code,
        defaults=plot_defaults
    )
@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([AllowAny])
def booking_webhook(request):
    """
    Webhook endpoint to receive booking data
    Only processes bookings with booking_type='tender'
    """
    
    webhook_data = request.data
    log_data = {
        'webhook_data': webhook_data,
        'status': 'failed',
        'error_type': None,
        'error_message': None,
        'activities_processed': 0,
        'activities_failed': 0,
        'plots_created': 0,
        'cluster_matched': False,
    }
    
    try:
        # Validate booking type
        booking = webhook_data.get('booking', {})
        if booking.get('booking_type') != 'tender':
            log_data['error_type'] = 'invalid_booking_type'
            log_data['error_message'] = f"Booking type is '{booking.get('booking_type')}', not 'tender'"
            WebhookLog.objects.create(**log_data)
            return JsonResponse({
                'status': 'skipped',
                'message': 'Only tender bookings are processed'
            }, status=200)
        
        # Extract data
        farmer_id = webhook_data.get('farmer_id')
        job_id = webhook_data.get('id')  # Internal ID from webhook
        activities_data = webhook_data.get('activities', [])
        
        if not farmer_id or not job_id:
            raise ValueError("Missing farmer_id or job_id in webhook data")
        
        log_data['farmer_id'] = farmer_id
        log_data['job_id'] = job_id
        
        # Fetch farmer details from API
        farmer_details, api_error = fetch_farmer_details(farmer_id)
        
        # Extract location from farmer API if available
        village = None
        taluka = None
        district = None
        
        if farmer_details:
            village = farmer_details.get('village')
            taluka = farmer_details.get('taluka')
            district = farmer_details.get('district')
        
        # Match cluster
        matched_cluster = None
        if village and taluka and district:
            matched_cluster = match_cluster_by_location(village, taluka, district)
            if matched_cluster:
                log_data['cluster_matched'] = True
                log_data['cluster_id'] = matched_cluster.id
        
        with transaction.atomic():
            # 1. Create or update Farmer (safely)
            farmer, farmer_created = safe_update_farmer(
                farmer_id, 
                webhook_data, 
                farmer_details, 
                matched_cluster
            )
            
            # 2. Create or update Plots from farmer API
            if farmer_details and 'plots' in farmer_details:
                for plot_data in farmer_details['plots']:
                    plot_code = plot_data.get('plot_id') or plot_data.get('id')
                    if not plot_code:
                        continue
                    
                    plot, plot_created = safe_update_plot(
                        plot_code,
                        farmer,
                        matched_cluster,
                        plot_data
                    )
                    
                    if plot_created:
                        log_data['plots_created'] += 1
            
            # 3. Create or update Job
            job_defaults = {
                'farmer': farmer,
                'cluster': matched_cluster,
                'work_id': job_id,  # Same as job_id
                'crop_name': webhook_data.get('crop_name', ''),
                'variety': webhook_data.get('variety', ''),
                'booking_amount': booking.get('total_amount', 0),
                'api_raw_data': webhook_data,
            }
            
            job, job_created = Job.objects.update_or_create(
                job_id=job_id,
                defaults=job_defaults
            )
            
            # Around line 235-250 in your webhook.py
            # 4. Process Activities
            for activity_data in activities_data:
                try:
                    activity_name = activity_data.get('activity_name')
                    plot_code = activity_data.get('plot_id')
                    
                    if not activity_name or not plot_code:
                        log_data['activities_failed'] += 1
                        continue
                    
                    # Get or create activity in catalog
                    activity, _ = get_or_create_activity(activity_name)
                    
                    # Get plot
                    try:
                        plot = Plot.objects.get(plot_code=plot_code)
                    except Plot.DoesNotExist:
                        # Create plot if not found
                        plot_data = {
                            'area': activity_data.get('area', 0),  # Get area from activity
                            'area_acres': activity_data.get('area', 0),  # ADD THIS LINE
                        }
                        plot, _ = safe_update_plot(
                            plot_code,
                            farmer,
                            matched_cluster,
                            plot_data
                        )
                        log_data['plots_created'] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process activity: {str(e)}")
                    log_data['activities_failed'] += 1
            
            # Determine overall status
            if log_data['activities_failed'] == 0:
                log_data['status'] = 'success'
            else:
                log_data['status'] = 'partial'
        
        # Create webhook log
        WebhookLog.objects.create(**log_data)
        
        return JsonResponse({
            'status': log_data['status'],
            'farmer_id': farmer_id,
            'job_id': job_id,
            'cluster_matched': log_data['cluster_matched'],
            'cluster_id': log_data.get('cluster_id'),
            'activities_processed': log_data['activities_processed'],
            'activities_failed': log_data['activities_failed'],
        }, status=200)
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        log_data['status'] = 'failed'
        log_data['error_type'] = 'processing_error'
        log_data['error_message'] = str(e)
        
        WebhookLog.objects.create(**log_data)
        
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)