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

# tender/webhook.py

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
    Farmer, Job, Plot, JobActivity, JobBooking,
    FarmerPayment, Cluster, ActivityCatalog, WebhookLog, Mukkadam
)

logger = logging.getLogger(__name__)

FARMER_API_BASE_URL = "https://demand.bharatintelligence.ai/fir"
FARMER_API_TOKEN = "e8fa8310c9af344ca22ec6bd23960d609b09c704"


# ============================================================
# HELPERS
# ============================================================

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


def get_or_create_activity_catalog(activity_name: str):
    """Get or create activity in catalog"""
    activity, created = ActivityCatalog.objects.get_or_create(
        name=activity_name,
        defaults={
            'source': 'webhook',
            'default_rate_per_acre': 0,
            'estimated_workers_per_acre': 10,
            'default_gap_days': 3,
        }
    )
    return activity


def sync_farmer(farmer_id: str, farmer_details: dict, webhook_data: dict) -> Farmer:
    """
    Create or update Farmer from API details.
    Clusters NOT touched here — manual assignment only.
    New plots from farmer API auto-connected to farmer.
    """
    defaults = {
        'farmer_name': (
            farmer_details.get('name') or
            farmer_details.get('farmer_name') or
            webhook_data.get('farmer_name') or
            f"Farmer {farmer_id}"
        ),
        'phone_number': (
            farmer_details.get('phone') or
            farmer_details.get('mobile') or
            farmer_details.get('phone_number') or ''
        ),
        'location': (
            farmer_details.get('location') or
            f"{farmer_details.get('village', '')}, "
            f"{farmer_details.get('taluka', '')}, "
            f"{farmer_details.get('district', '')}"
        ).strip(', '),
        'latitude': farmer_details.get('latitude') or None,
        'longitude': farmer_details.get('longitude') or None,
    }

    farmer, created = Farmer.objects.update_or_create(
        farmer_id=str(farmer_id),
        defaults=defaults
    )

    action = "Created" if created else "Updated"
    logger.info(f"{action} farmer {farmer_id}: {farmer.farmer_name}")

    # ✅ Sync plots from farmer API (auto-connect to farmer)
    if farmer_details and 'plots' in farmer_details:
        for plot_data in farmer_details.get('plots', []):
            plot_code = str(
                plot_data.get('plot_id') or
                plot_data.get('id') or ''
            )
            if not plot_code:
                continue

            Plot.objects.update_or_create(
                plot_code=str(plot_code),
                defaults={
                    'farmer': farmer,
                    'name': (
                        plot_data.get('name') or
                        plot_data.get('plot_name') or
                        f"Plot {plot_code}"
                    ),
                    # ✅ FIX: farmer API uses 'acre' not 'area_acres' or 'area'
                    'area_acres': (lambda v: Decimal(str(v)) if str(v).replace('.','').isdigit() else Decimal('0'))(
    plot_data.get('acre') or plot_data.get('area_acres') or plot_data.get('area') or 0
),
                    'latitude': plot_data.get('latitude') or None,
                    'longitude': plot_data.get('longitude') or None,
                    # ✅ Also store crop/variety from farmer API
                    'crop_name': plot_data.get('crop', ''),
                    'variety': plot_data.get('variety', ''),
                    'pruning_date': plot_data.get('pruning_date') or None,
                }
            )
            logger.info(f"Synced plot {plot_code} for farmer {farmer_id}")

    return farmer


def get_or_create_plot(plot_code: str, farmer: Farmer, activity_area: float) -> Plot:
    """
    Get plot by plot_code. If not found, create and connect to farmer.
    Uses activity area as fallback area.
    """
    plot, created = Plot.objects.get_or_create(
    plot_code=str(plot_code),
    defaults={
        'farmer': farmer,
        'name': f"Plot {plot_code}",
        'area_acres': Decimal(str(
            activity_area or 0  # uses activity acres as fallback when plot not in farmer API
        )),
    }
)

    # If plot exists but farmer is different — log warning, don't override
    if not created and plot.farmer_id != farmer.farmer_id:
        logger.warning(
            f"Plot {plot_code} belongs to farmer {plot.farmer_id}, "
            f"but webhook sent farmer {farmer.farmer_id}. Keeping original."
        )

    return plot, created


def sync_job(job_id: str, farmer: Farmer, webhook_data: dict, plot: Plot = None) -> tuple:
    """Create or update Job record"""
    booking = webhook_data.get('booking', {})

    scheduled_date = None
    raw_date = webhook_data.get('scheduled_date')
    if raw_date:
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            parsed = parse_datetime(raw_date) or parse_date(raw_date)
            scheduled_date = parsed.date() if hasattr(parsed, 'date') else parsed
        except Exception:
            pass

    defaults = {
        'farmer': farmer,
        'work_id': str(job_id),
        'booking_amount': Decimal(str(booking.get('total_amount', 0))),
        'status': 'pending',
        'priority': webhook_data.get('priority', 'MEDIUM'),
        'scheduled_date': scheduled_date,
        'activity_notes': webhook_data.get('activity_notes', '') or '',
        'internal_notes': webhook_data.get('internal_notes', '') or '',
        'total_activities_amount': Decimal(str(
            webhook_data.get('total_activities_amount', 0)
        )),
        'is_field_verified': webhook_data.get('is_field_verified', False),
        'booking_type': 'tender',
        'api_raw_data': webhook_data,
    }

    if plot:
        defaults['plot'] = plot

    job, created = Job.objects.update_or_create(
        job_id=str(job_id),
        defaults=defaults
    )

    return job, created


def sync_booking(job: Job, booking_data: dict):
    """Create or update JobBooking"""
    booking_id = booking_data.get('id')
    if not booking_id:
        return None

    total_amount = Decimal(str(booking_data.get('total_amount', 0)))
    advance_paid = Decimal(str(booking_data.get('advance_paid', 0)))
    balance = Decimal(str(booking_data.get('balance', total_amount - advance_paid)))

    # Map status
    raw_status = booking_data.get('status', 'BOOKED').upper()
    if raw_status in ['PAID']:
        status = 'PAID'
    elif raw_status in ['PARTIAL', 'PARTIALLY_PAID']:
        status = 'PARTIALLY_PAID'
    elif raw_status in ['REFUNDED']:
        status = 'REFUNDED'
    else:
        status = 'UNPAID'

    booking, created = JobBooking.objects.update_or_create(
        job=job,
        defaults={
            'booking_id': int(booking_id),
            'status': status,
            'total_amount': total_amount,
            'advance_paid': advance_paid,
            'balance': balance,
            'assignee_number': booking_data.get('assignee_number', '') or '',
        }
    )

    # ✅ Sync payments
    for payment_data in booking_data.get('payments', []):
        payment_id = payment_data.get('id')
        if not payment_id:
            continue

        paid_at_raw = payment_data.get('paid_at')
        if paid_at_raw:
            from django.utils.dateparse import parse_datetime
            paid_at = parse_datetime(paid_at_raw)
        else:
            from django.utils.timezone import now
            paid_at = now()

        # Map payment mode
        raw_mode = (payment_data.get('mode') or 'CASH').upper()
        valid_modes = {'CASH', 'UPI', 'BANK_TRANSFER', 'CHEQUE', 'WILL_PAY_LATER', 'OTHER'}
        mode = raw_mode if raw_mode in valid_modes else 'OTHER'

        FarmerPayment.objects.update_or_create(
            payment_id=int(payment_id),
            defaults={
                'booking': booking,
                'mode': mode,
                'amount': Decimal(str(payment_data.get('amount', 0))),
                'notes': payment_data.get('notes', '') or '',
                'paid_status': payment_data.get('paid_status', True),
                'paid_at': paid_at,
            }
        )

    return booking


def sync_activities(job, farmer, activities_data, log_data, job_plot=None):
    """
    Sync activities for a job.
    - If activity_id already exists for this job → UPDATE
    - If new activity_id → CREATE
    - Dedup by activity api_activity_id
    """
    processed = 0
    failed = 0

    # Track existing activity IDs for this job
    existing_activity_ids = set(
        job.activities.values_list('api_activity_id', flat=True)
    )

    for activity_data in activities_data:
        try:
            activity_name = activity_data.get('activity_name', '').strip()
            plot_code = str(activity_data.get('plot_id', '') or '')
            api_activity_id = str(activity_data.get('id', '') or '')

            if not activity_name:
                logger.warning(f"Skipping activity with no name: {activity_data}")
                failed += 1
                continue

            # Get activity catalog entry
            activity_catalog = get_or_create_activity_catalog(activity_name)

            # Get or create plot
            plot = None
            if plot_code:
                plot, plot_created = get_or_create_plot(
                    plot_code, farmer,
                    activity_data.get('acres', 0)
                )
                if plot_created:
                    log_data['plots_created'] += 1
            else:
                plot = job_plot  # ✅ use job-level matched plot as fallback


            # Parse scheduled date
            scheduled_date = None
            scheduled_time = None
            raw_datetime = activity_data.get('date_time') or activity_data.get('scheduled_date')
            if raw_datetime:
                try:
                    from django.utils.dateparse import parse_datetime, parse_date
                    if 'T' in str(raw_datetime):
                        parsed = parse_datetime(str(raw_datetime))
                        if parsed:
                            scheduled_date = parsed.date()
                            scheduled_time = parsed.time()
                    else:
                        scheduled_date = parse_date(str(raw_datetime))
                except Exception as e:
                    logger.warning(f"Could not parse date {raw_datetime}: {e}")

            # Area and pricing
            total_area = Decimal(str(activity_data.get('acres', 0) or 0))
            total_price = Decimal(str(activity_data.get('total_price', 0) or 0))
            transport_cost = Decimal(str(activity_data.get('transport_cost', 0) or 0))
            other_cost = Decimal(str(activity_data.get('other_cost', 0) or 0))

            rate_per_acre = (
                (total_price / total_area).quantize(Decimal('0.01'))
                if total_area > 0
                else Decimal('0')
            )

            activity_defaults = {
                'activity': activity_catalog,
                'plot': plot,
                'total_area': total_area,
                'remaining_area': total_area,   # Will recalculate on save
                'allocated_area': Decimal('0'),
                'scheduled_date': scheduled_date,
                'scheduled_time': scheduled_time,
                'estimated_workers': activity_data.get('estimated_workers', 10),
                'rate_per_acre': rate_per_acre,
                'total_price': total_price,
                'transport_cost': transport_cost,
                'other_cost': other_cost,
                'crop_bundles': int(activity_data.get('crop_bundles', 0) or 0),
                'location': activity_data.get('location', 'N/A') or 'N/A',
            }

            if api_activity_id and api_activity_id in existing_activity_ids:
                # ✅ UPDATE existing activity
                job.activities.filter(
                    api_activity_id=api_activity_id
                ).update(**activity_defaults)
                logger.info(f"Updated activity {api_activity_id} for job {job.job_id}")
            else:
                # ✅ CREATE new activity
                JobActivity.objects.create(
                    job=job,
                    api_activity_id=api_activity_id,
                    **activity_defaults
                )
                logger.info(f"Created activity {api_activity_id} for job {job.job_id}")

            processed += 1

        except Exception as e:
            logger.error(f"Failed to process activity {activity_data}: {str(e)}", exc_info=True)
            failed += 1

    log_data['activities_processed'] += processed
    log_data['activities_failed'] += failed

    # ✅ Update job complexity flag
    total_activities = job.activities.count()
    Job.objects.filter(job_id=job.job_id).update(
        is_complex=total_activities > 1,
        total_activities_amount=sum(
            a.total_price for a in job.activities.all()
        )
    )


ALLOCATION_API_BASE_URL = "http://localhost:8000"  # your other backend
ALLOCATION_API_TOKEN = "Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000"

from tender.models import Mukkadam, MukkadamActivityRate, ActivityCatalog

def sync_tender_mukkadams():
    try:
        response = requests.get(
            f"{ALLOCATION_API_BASE_URL}/api/mukkadam/?is_tender_mukkadam=true",
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        mukkadams_list = data if isinstance(data, list) else data.get('results', data.get('data', []))
        
        for m in mukkadams_list:
            mukkadam_id = m.get('id')
            if not mukkadam_id:
                continue
            
            mukkadam, _ = Mukkadam.objects.update_or_create(
                mukkadam_id=int(mukkadam_id),
                defaults={
                    'mukkadam_name': m.get('mukkadam_name', ''),
                    'mobile_numbers': m.get('mobile_numbers', ''),
                    'crew_size': int(m.get('crew_size') or 0),
                    'max_crew_capacity': int(m.get('max_crew_capacity') or 0),
                    'has_smartphone': m.get('has_smartphone', 'no'),
                    'work_mode': m.get('work_mode', ''),
                    'start_date': m.get('start_date') or None,
                    'end_date': m.get('end_date') or None,
                    'state': m.get('state', ''),
                    'state_code': m.get('state_code', ''),
                    'district': m.get('district', ''),
                    'district_code': m.get('district_code', ''),
                    'taluka': m.get('taluka', ''),
                    'taluka_code': m.get('taluka_code', ''),
                    'village': m.get('village', ''),
                    'village_code': m.get('village_code', ''),
                    'tender_activities': m.get('tender_activities', {}),
                    'rate_card': m.get('rate_card', {}),
                    'api_raw_data': m,
                }
            )

            # ✅ Sync activity_rates from tender_activities JSON
            tender_activities = m.get('tender_activities', {})
            activities_list = tender_activities.get('activities', [])

            for act_data in activities_list:
                name = (act_data.get('name') or '').strip()
                price = act_data.get('price') or 0

                if not name:  # skip empty entries
                    continue

                try:
                    price = Decimal(str(price))
                except Exception:
                    price = Decimal('0')

                # Get or create activity catalog entry
                activity_catalog, _ = ActivityCatalog.objects.get_or_create(
                    name=name,
                    defaults={
                        'source': 'webhook',
                        'default_rate_per_acre': price,
                        'estimated_workers_per_acre': 10,
                        'default_gap_days': 3,
                    }
                )

                # ✅ Create or update rate record
                MukkadamActivityRate.objects.update_or_create(
                    mukkadam=mukkadam,
                    activity=activity_catalog,
                    defaults={
                        'rate_per_acre': price,
                        'productivity_per_worker': Decimal('0.15'),  # default
                    }
                )

            logger.info(f"Synced mukkadam {mukkadam_id} with {len([a for a in activities_list if a.get('name','').strip()])} activity rates")

    except Exception as e:
        logger.error(f"Failed to sync mukkadams: {str(e)}")
# ============================================================
# MAIN WEBHOOK VIEW
# ============================================================


@api_view(['POST'])
def run_mukkadam_sync(request):
    sync_tender_mukkadams()
    return JsonResponse({"success": True})

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def booking_webhook(request):
    """
    Webhook: receives merged tender job data.
    - Only processes booking_type='tender'
    - Creates/updates: Farmer, Plot, Job, JobActivity, JobBooking, FarmerPayment
    - Clusters NOT auto-assigned (manual only)
    """

    webhook_data = request.data

    log_data = {
        'webhook_data': webhook_data,
        'status': 'failed',
        'error_type': None,
        'error_message': None,
        'farmer_id': None,
        'job_id': None,
        'cluster_matched': False,
        'cluster_id': None,
        'activities_processed': 0,
        'activities_failed': 0,
        'plots_created': 0,
    }

    try:
        # ✅ STEP 0: Validate booking_type
        booking = webhook_data.get('booking', {})
        # allowed_types = ['tender', 'general']
        # if booking.get('booking_type') != allowed_types:
        #     log_data['status'] = 'failed'
        #     log_data['error_type'] = 'invalid_booking_type'
        #     log_data['error_message'] = (
        #         f"booking_type='{booking.get('booking_type')}' — only 'tender' accepted"
        #     )
        #     WebhookLog.objects.create(**log_data)
        #     return JsonResponse({
        #         'status': 'skipped',
        #         'message': 'Only tender bookings are processed'
        #     }, status=200)

        # ✅ STEP 1: Extract core fields
        farmer_id = str(webhook_data.get('farmer_id', ''))
        job_id = str(webhook_data.get('id', ''))
        activities_data = webhook_data.get('activities', [])

        if not farmer_id or not job_id:
            raise ValueError("Missing farmer_id or id in webhook payload")

        log_data['farmer_id'] = farmer_id
        log_data['job_id'] = job_id

        # ✅ STEP 2: Fetch farmer details from external API
        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            logger.warning(f"Farmer API error for {farmer_id}: {api_error} — continuing with webhook data only")
            farmer_details = {}

        with transaction.atomic():

            # ✅ STEP 3: Sync Farmer (no cluster assignment)
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data)

            # ✅ STEP 3.5: Get plot object (we need plots.id not plot_code)
            plot = None
            plot_code = str(webhook_data.get('plot_id') or '')

            if not plot_code and activities_data:
                plot_code = str(activities_data[0].get('plot_id') or '')

            if plot_code:
                # ✅ Just fetch by plot_code — sync_farmer already created it above
                plot = Plot.objects.filter(plot_code=plot_code, farmer=farmer).first()
                if not plot:
                    # fallback: create it
                    plot, created = get_or_create_plot(
                        plot_code, farmer,
                        activities_data[0].get('acres', 0) if activities_data else 0
                    )
                    if created:
                        log_data['plots_created'] += 1
                logger.info(f"Job {job_id} → Plot id={plot.id} plot_code={plot.plot_code}")
            else:
                # No plot_code at all — try match from farmer's plots by area
                farmer_plots = list(Plot.objects.filter(farmer=farmer))
                if farmer_plots and activities_data:
                    activity_area = Decimal(str(activities_data[0].get('acres', 0) or 0))
                    plot = next(
                        (p for p in farmer_plots if abs(p.area_acres - activity_area) < Decimal('0.1')),
                        farmer_plots[0]
                    )
                logger.info(f"No plot_code in webhook — matched plot id={plot.id if plot else None}")

            # ✅ STEP 4: sync_job sets job.plot = plot (the Plot object, Django saves plot_id = plot.id)
            job, job_created = sync_job(job_id, farmer, webhook_data, plot=plot)
            logger.info(f"{'Created' if job_created else 'Updated'} job {job_id}")

            if plot:
                plot_clusters = list(plot.clusters.all())
                if plot_clusters:
                    for c in plot_clusters:
                        job.clusters.add(c)
                    log_data['cluster_matched'] = True
                    log_data['cluster_id'] = plot_clusters[0].id

            # ✅ STEP 5: Sync Booking + Payments
            sync_booking(job, booking)

            # ✅ STEP 6: Sync Activities (create new + update existing)
            sync_activities(job, farmer, activities_data, log_data)

            try:
                sync_tender_mukkadams()
                # log_data['mukkadam_sync_attempted'] = True # Add this field to your WebhookLog model
            except Exception as e:
                logger.error(f"Mukkadam sync failed during webhook: {e}")

        # ✅ STEP 7: Determine status
        if log_data['activities_failed'] == 0:
            log_data['status'] = 'success'
        elif log_data['activities_processed'] > 0:
            log_data['status'] = 'partial'
        else:
            log_data['status'] = 'failed'

        WebhookLog.objects.create(**log_data)

        return JsonResponse({
            'status': log_data['status'],
            'farmer_id': farmer_id,
            'job_id': job_id,
            'job_created': job_created,
            'activities_processed': log_data['activities_processed'],
            'activities_failed': log_data['activities_failed'],
            'plots_created': log_data['plots_created'],
            'message': (
                f"Job {'created' if job_created else 'updated'} with "
                f"{log_data['activities_processed']} activities"
            )
        }, status=200)
    


    except Exception as e:
        logger.error(f"Webhook failed: {str(e)}", exc_info=True)
        log_data['status'] = 'failed'
        log_data['error_type'] = 'processing_error'
        log_data['error_message'] = str(e)

        WebhookLog.objects.create(**log_data)



        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# tender/webhook.py - ADD THIS FUNCTION


# def fetch_farmer_details(farmer_id: str):
#     """Fetch farmer details from external API"""
#     try:
#         response = requests.get(
#             f"{FARMER_API_BASE_URL}/api/get_farmer_details/{farmer_id}/",
#             headers={"Authorization": f"Token {FARMER_API_TOKEN}"},
#             timeout=10
#         )
#         response.raise_for_status()
#         return response.json(), None
#     except requests.RequestException as e:
#         logger.error(f"Failed to fetch farmer {farmer_id}: {str(e)}")
#         return None, str(e)


# def get_or_create_activity(activity_name: str):
#     """Get or create activity in catalog"""
#     activity, created = ActivityCatalog.objects.get_or_create(
#         name=activity_name,
#         defaults={
#             'source': 'api',
#             'default_rate_per_acre': 0,
#             'estimated_workers_per_acre': 10,
#             'default_gap_days': 3,
#         }
#     )
#     return activity, created


# def safe_update_farmer(farmer_id: str, webhook_data: dict, farmer_details: dict, matched_cluster):
#     """
#     Safely update farmer with only valid fields
#     """
#     # Get all valid field names from Farmer model
#     valid_fields = {f.name for f in Farmer._meta.get_fields() if not f.many_to_many and not f.one_to_many}
    
#     # Build defaults with only valid fields
#     farmer_defaults = {
#         'cluster': matched_cluster,
#     }
    
#     # Try to add farmer_name
#     if 'farmer_name' in valid_fields:
#         farmer_defaults['farmer_name'] = webhook_data.get('farmer_name', f"Farmer {farmer_id}")
    
#     # If farmer API returned data, use it
#     if farmer_details:
#         # Map common field names (only if they exist in model)
#         field_mapping = {
#             'name': 'farmer_name',
#             'village': 'village',
#             'taluka': 'taluka', 
#             'district': 'district',
#             'state': 'state',
#             'phone': 'phone',
#             'mobile': 'phone',
#             'latitude': 'latitude',
#             'longitude': 'longitude',
#         }
        
#         for api_field, model_field in field_mapping.items():
#             if model_field in valid_fields and api_field in farmer_details:
#                 value = farmer_details[api_field]
#                 if value:  # Only set non-empty values
#                     farmer_defaults[model_field] = value
    
#     return Farmer.objects.update_or_create(
#         farmer_id=farmer_id,
#         defaults=farmer_defaults
#     )

# def safe_update_plot(plot_code: str, farmer, matched_cluster, plot_data: dict):
#     """
#     Safely update plot with only valid fields
#     """
#     # Get all valid field names from Plot model
#     valid_fields = {f.name for f in Plot._meta.get_fields() if not f.many_to_many and not f.one_to_many}
    
#     plot_defaults = {
#         'farmer': farmer,
#         'cluster': matched_cluster,
#     }
    
#     # Map common field names (only if they exist in model)
#     field_mapping = {
#         'name': 'name',
#         'plot_name': 'name',
#         'area_acres': 'area_acres',
#         'area': 'area_acres',
#         'latitude': 'latitude',
#         'longitude': 'longitude',
#         'village': 'village',
#         'crop_name': 'crop_name',
#         'variety': 'variety',
#     }
    
#     for api_field, model_field in field_mapping.items():
#         if model_field in valid_fields and api_field in plot_data:
#             value = plot_data[api_field]
#             if value is not None:  # Allow 0 but not None
#                 plot_defaults[model_field] = value
    
#     # CRITICAL: Ensure area_acres has a default value if required
#     if 'area_acres' in valid_fields and 'area_acres' not in plot_defaults:
#         plot_defaults['area_acres'] = 0.0  # Default to 0 if not provided
    
#     # Default name if not provided
#     if 'name' in valid_fields and 'name' not in plot_defaults:
#         plot_defaults['name'] = f"Plot {plot_code}"
    
#     return Plot.objects.update_or_create(
#         plot_code=plot_code,
#         defaults=plot_defaults
#     )


# @csrf_exempt
# @require_http_methods(["POST"])
# @api_view(['POST'])
# @permission_classes([AllowAny])
# def booking_webhook(request):
#     """
#     Webhook endpoint to receive booking data
#     Only processes bookings with booking_type='tender'
#     """
    
#     webhook_data = request.data
#     log_data = {
#         'webhook_data': webhook_data,
#         'status': 'failed',
#         'error_type': None,
#         'error_message': None,
#         'activities_processed': 0,
#         'activities_failed': 0,
#         'plots_created': 0,
#         'cluster_matched': False,
#     }
    
#     try:
#         # Validate booking type
#         booking = webhook_data.get('booking', {})
#         if booking.get('booking_type') != 'tender':
#             log_data['error_type'] = 'invalid_booking_type'
#             log_data['error_message'] = f"Booking type is '{booking.get('booking_type')}', not 'tender'"
#             WebhookLog.objects.create(**log_data)
#             return JsonResponse({
#                 'status': 'skipped',
#                 'message': 'Only tender bookings are processed'
#             }, status=200)
        
#         # Extract data
#         farmer_id = webhook_data.get('farmer_id')
#         job_id = webhook_data.get('id')  # Internal ID from webhook
#         activities_data = webhook_data.get('activities', [])
        
#         if not farmer_id or not job_id:
#             raise ValueError("Missing farmer_id or job_id in webhook data")
        
#         log_data['farmer_id'] = farmer_id
#         log_data['job_id'] = job_id
        
#         # Fetch farmer details from API
#         farmer_details, api_error = fetch_farmer_details(farmer_id)
        
#         # Extract location from farmer API if available
#         village = None
#         taluka = None
#         district = None
        
#         if farmer_details:
#             village = farmer_details.get('village')
#             taluka = farmer_details.get('taluka')
#             district = farmer_details.get('district')
        
#         # Match cluster
#         matched_cluster = None
#         if village and taluka and district:
#             matched_cluster = match_cluster_by_location(village, taluka, district)
#             if matched_cluster:
#                 log_data['cluster_matched'] = True
#                 log_data['cluster_id'] = matched_cluster.id
        
#         with transaction.atomic():
#             # 1. Create or update Farmer (safely)
#             farmer, farmer_created = safe_update_farmer(
#                 farmer_id, 
#                 webhook_data, 
#                 farmer_details, 
#                 matched_cluster
#             )
            
#             # 2. Create or update Plots from farmer API
#             if farmer_details and 'plots' in farmer_details:
#                 for plot_data in farmer_details['plots']:
#                     plot_code = plot_data.get('plot_id') or plot_data.get('id')
#                     if not plot_code:
#                         continue
                    
#                     plot, plot_created = safe_update_plot(
#                         plot_code,
#                         farmer,
#                         matched_cluster,
#                         plot_data
#                     )
                    
#                     if plot_created:
#                         log_data['plots_created'] += 1
            
#             # 3. Create or update Job
#             job_defaults = {
#                 'farmer': farmer,
#                 'cluster': matched_cluster,
#                 'work_id': job_id,  # Same as job_id
#                 'crop_name': webhook_data.get('crop_name', ''),
#                 'variety': webhook_data.get('variety', ''),
#                 'booking_amount': booking.get('total_amount', 0),
#                 'api_raw_data': webhook_data,
#             }
            
#             job, job_created = Job.objects.update_or_create(
#                 job_id=job_id,
#                 defaults=job_defaults
#             )
            
#             # Around line 235-250 in your webhook.py
#             # 4. Process Activities
#             for activity_data in activities_data:
#                 try:
#                     activity_name = activity_data.get('activity_name')
#                     plot_code = activity_data.get('plot_id')
                    
#                     if not activity_name or not plot_code:
#                         log_data['activities_failed'] += 1
#                         continue
                    
#                     # Get or create activity in catalog
#                     activity, _ = get_or_create_activity(activity_name)
                    
#                     # Get plot
#                     try:
#                         plot = Plot.objects.get(plot_code=plot_code)
#                     except Plot.DoesNotExist:
#                         # Create plot if not found
#                         plot_data = {
#                             'area': activity_data.get('area', 0),  # Get area from activity
#                             'area_acres': activity_data.get('area', 0),  # ADD THIS LINE
#                         }
#                         plot, _ = safe_update_plot(
#                             plot_code,
#                             farmer,
#                             matched_cluster,
#                             plot_data
#                         )
#                         log_data['plots_created'] += 1
                    
#                 except Exception as e:
#                     logger.error(f"Failed to process activity: {str(e)}")
#                     log_data['activities_failed'] += 1
            
#             # Determine overall status
#             if log_data['activities_failed'] == 0:
#                 log_data['status'] = 'success'
#             else:
#                 log_data['status'] = 'partial'
        
#         # Create webhook log
#         WebhookLog.objects.create(**log_data)
        
#         return JsonResponse({
#             'status': log_data['status'],
#             'farmer_id': farmer_id,
#             'job_id': job_id,
#             'cluster_matched': log_data['cluster_matched'],
#             'cluster_id': log_data.get('cluster_id'),
#             'activities_processed': log_data['activities_processed'],
#             'activities_failed': log_data['activities_failed'],
#         }, status=200)
        
#     except Exception as e:
#         logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
#         log_data['status'] = 'failed'
#         log_data['error_type'] = 'processing_error'
#         log_data['error_message'] = str(e)
        
#         WebhookLog.objects.create(**log_data)
        
#         return JsonResponse({
#             'status': 'error',
#             'message': str(e)
#         }, status=500)
    



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

