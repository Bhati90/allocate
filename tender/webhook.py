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


def sync_farmer(farmer_id: str, farmer_details: dict, webhook_data: dict, 
                target_plot_code: str = None) -> Farmer:
    

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

    # ✅ Only sync the specific plot from the job, not all plots
    if farmer_details and 'plots' in farmer_details and target_plot_code:
        for plot_data in farmer_details.get('plots', []):
            plot_code = str(
                plot_data.get('plot_id') or
                plot_data.get('id') or ''
            )
            if plot_code != str(target_plot_code):
                continue  # ✅ skip all other plots

            Plot.objects.update_or_create(
                plot_code=plot_code,
                defaults={
                    'farmer': farmer,
                    'name': plot_data.get('name') or plot_data.get('plot_name') or f"Plot {plot_code}",
                    'area_acres': (lambda v: Decimal(str(v)) if str(v).replace('.','').isdigit() else Decimal('0'))(
                        plot_data.get('acre') or plot_data.get('area_acres') or plot_data.get('area') or 0
                    ),
                    'latitude': plot_data.get('latitude') or None,
                    'longitude': plot_data.get('longitude') or None,
                    'crop_name': plot_data.get('crop', '') or plot_data.get('crop_name', '') or '',
                    'variety': plot_data.get('variety', '') or '',
                    # 'pruning_date': plot_data.get('pruning_date') or None,
                }
            )
            logger.info(f"Synced plot {plot_code} for farmer {farmer_id}")
            break  # ✅ found it, stop

    return farmer

def get_or_create_plot(plot_code: str, farmer: Farmer, activity_area: float,
                        crop_name: str = '', variety: str = '') -> tuple:
    plot, created = Plot.objects.get_or_create(
        plot_code=str(plot_code),
        defaults={
            'farmer': farmer,
            'name': f"Plot {plot_code}",
            'area_acres': Decimal(str(activity_area or 0)),
            'crop_name': crop_name,
            'variety': variety,
        }
    )

    if not created and plot.farmer_id != farmer.farmer_id:
        logger.warning(
            f"Plot {plot_code} belongs to farmer {plot.farmer_id}, "
            f"but webhook sent farmer {farmer.farmer_id}. Keeping original."
        )

    # ✅ Update crop info if missing
    if not created and crop_name and not plot.crop_name:
        plot.crop_name = crop_name
        plot.variety = variety
        plot.save(update_fields=['crop_name', 'variety'])

    return plot, created
def sync_job(job_id: str, farmer: Farmer, webhook_data: dict, 
             plot: Plot = None, crop_name: str = '', variety: str = '') -> tuple:
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
        'crop_name': crop_name,   # ✅ from the specific plot's activity
        'variety': variety,        # ✅ from the specific plot's activity
        'booking_amount': Decimal(str(booking.get('total_amount', 0))),
        'status': 'pending',
        'priority': webhook_data.get('priority', 'MEDIUM'),
        'scheduled_date': scheduled_date,
        'activity_notes': webhook_data.get('activity_notes', '') or '',
        'internal_notes': webhook_data.get('internal_notes', '') or '',
        'total_activities_amount': Decimal(str(webhook_data.get('total_activities_amount', 0))),
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

def get_scheduled_date_for_activity(activity_catalog, job, pruning_date):
    from datetime import timedelta
    from .models import ClusterActivityScheduleRule, ActivityScheduleRule

    if not pruning_date:
        logger.warning(f"No pruning_date passed for '{activity_catalog.name}'")
        return None

    gap_days = None
    clusters = job.clusters.all()

    # 1. Cluster-specific
    if clusters.exists():
        cluster_rule = ClusterActivityScheduleRule.objects.filter(
            cluster__in=clusters,
            activity=activity_catalog
        ).first()
        if cluster_rule:
            gap_days = cluster_rule.gap_days
            logger.info(f"'{activity_catalog.name}': cluster rule → {gap_days} days")
        else:
            logger.info(f"'{activity_catalog.name}': no cluster rule found for clusters {[c.name for c in clusters]}")

    # 2. Global
    if gap_days is None:
        try:
            global_rule = ActivityScheduleRule.objects.get(activity=activity_catalog)
            gap_days = global_rule.gap_days
            logger.info(f"'{activity_catalog.name}': global rule → {gap_days} days")
        except ActivityScheduleRule.DoesNotExist:
            logger.warning(f"'{activity_catalog.name}': no global ActivityScheduleRule found")

    # 3. Fallback
    if gap_days is None:
        gap_days = activity_catalog.default_gap_days or 3
        logger.info(f"'{activity_catalog.name}': fallback default_gap_days → {gap_days} days")

    result = pruning_date + timedelta(days=gap_days)
    logger.info(f"'{activity_catalog.name}': {pruning_date} + {gap_days}d = {result}")
    return result

def sync_activities(job, farmer, activities_data, log_data, job_plot=None):
    from django.utils.dateparse import parse_datetime, parse_date
    from collections import defaultdict

    processed = 0
    failed = 0

    existing_activity_ids = set(
        job.activities.values_list('api_activity_id', flat=True)
    )

    # ✅ Group activities by plot_id
    plot_activities = defaultdict(list)
    for act in activities_data:
        pid = str(act.get('plot_id') or '')
        plot_activities[pid].append(act)

    # ✅ Extract pruning date PER PLOT
    def get_pruning_date_for_plot(activities):
        for act in activities:
            name = act.get('activity_name', '')
            if 'pruning' in name.lower() or 'छाटणी' in name:
                raw = act.get('date_time') or act.get('scheduled_date')
                if raw:
                    try:
                        if 'T' in str(raw):
                            p = parse_datetime(str(raw))
                            return p.date() if p else None
                        else:
                            return parse_date(str(raw))
                    except Exception:
                        pass
        return None

    clusters = list(job.clusters.all())
    logger.info(f"Job {job.job_id} clusters at sync time: {[c.name for c in clusters]}")

    for plot_id_key, activities in plot_activities.items():
        # ✅ Get pruning date for THIS plot only
        pruning_date = get_pruning_date_for_plot(activities)
        if pruning_date:
            logger.info(f"Plot {plot_id_key}: pruning_date={pruning_date}")
        else:
            logger.warning(f"Plot {plot_id_key}: no pruning date found")

        for activity_data in activities:
            try:
                activity_name = activity_data.get('activity_name', '').strip()
                plot_code = str(activity_data.get('plot_id', '') or '')
                api_activity_id = str(
                    activity_data.get('id') or
                    activity_data.get('activity_id') or
                    ''
                )

                if not api_activity_id or api_activity_id in ('None', 'null', '0'):
                    import hashlib
                    api_activity_id = hashlib.md5(
                        f"{job.job_id}-{plot_code}-{activity_name}".encode()
                    ).hexdigest()[:20]
                    logger.info(f"Generated stable id '{api_activity_id}' for '{activity_name}' plot '{plot_code}'")

                if not activity_name:
                    logger.warning(f"Skipping activity with no name: {activity_data}")
                    failed += 1
                    continue

                activity_catalog = get_or_create_activity_catalog(activity_name)

                # ✅ Resolve plot from activity's own plot_id
                plot = None
                if plot_code:
                    crop_name = activity_data.get('crop_name', '') or ''
                    variety = activity_data.get('variety', '') or ''

                    plot, plot_created = get_or_create_plot(
                        plot_code, farmer,
                        activity_data.get('acres', 0) or activity_data.get('total_area', 0),
                        crop_name=crop_name,
                        variety=variety,
                    )
                    if plot_created:
                        log_data['plots_created'] += 1

                    # ✅ If crop_name missing, fetch from farmer API
                    if not plot.crop_name:
                        fetched_crop, fetched_variety = fetch_plot_crop_details(
                            farmer.farmer_id, plot_code
                        )
                        if fetched_crop:
                            plot.crop_name = fetched_crop
                            plot.variety = fetched_variety
                            plot.save(update_fields=['crop_name', 'variety'])
                            logger.info(f"Fetched crop='{fetched_crop}' variety='{fetched_variety}' for plot {plot_code}")
                else:
                    plot = job_plot

                # ✅ Date logic using THIS plot's pruning date
                scheduled_date = None
                scheduled_time = None
                is_pruning = 'pruning' in activity_name.lower() or 'छाटणी' in activity_name

                if is_pruning:
                    raw_datetime = activity_data.get('date_time') or activity_data.get('scheduled_date')
                    if raw_datetime:
                        try:
                            if 'T' in str(raw_datetime):
                                parsed = parse_datetime(str(raw_datetime))
                                if parsed:
                                    scheduled_date = parsed.date()
                                    scheduled_time = parsed.time()
                            else:
                                scheduled_date = parse_date(str(raw_datetime))
                        except Exception as e:
                            logger.warning(f"Could not parse pruning date: {e}")

                    # ✅ Save pruning_date on the plot itself
                    if scheduled_date and plot and plot.pruning_date != scheduled_date:
                        plot.pruning_date = scheduled_date
                        plot.save(update_fields=['pruning_date'])
                        logger.info(f"Saved pruning_date={scheduled_date} on plot {plot_code}")
                else:
                    if pruning_date:
                        scheduled_date = get_scheduled_date_for_activity(
                            activity_catalog, job, pruning_date
                        )
                        logger.info(f"Plot {plot_code} '{activity_name}' → date={scheduled_date} from pruning={pruning_date}")
                    else:
                        logger.warning(f"Plot {plot_code}: no pruning date, cannot calculate date for '{activity_name}'")

                # ✅ Area and pricing
                total_area = Decimal(str(
                    activity_data.get('acres', 0) or
                    activity_data.get('total_area', 0) or 0
                ))
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
                    'remaining_area': total_area,
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
                    job.activities.filter(api_activity_id=api_activity_id).update(**activity_defaults)
                    logger.info(f"Updated activity {api_activity_id} plot={plot_code} for job {job.job_id}")
                else:
                    JobActivity.objects.create(
                        job=job,
                        api_activity_id=api_activity_id,
                        **activity_defaults
                    )
                    logger.info(f"Created activity {api_activity_id} plot={plot_code} for job {job.job_id}")

                processed += 1

            except Exception as e:
                logger.error(f"Failed to process activity {activity_data}: {str(e)}", exc_info=True)
                failed += 1

    log_data['activities_processed'] += processed
    log_data['activities_failed'] += failed

    Job.objects.filter(job_id=job.job_id).update(
        is_complex=job.activities.count() > 1,
        total_activities_amount=sum(a.total_price for a in job.activities.all())
    )
# ALLOCATION_API_BASE_URL = "http://localhost:8000"  # your other backend

ALLOCATION_API_BASE_URL = "https://supply.bharatintelligence.ai"
ALLOCATION_API_TOKEN = "Token 55d78dc15410726cbf90b3350690937f4e85ddf8"
ALLOCATION_API_TOKEN = "Token b5920d610d85bff62bb0ab70f971ed6a44eb1b8c"
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

    import json
    print("=" * 80)
    print("INCOMING WEBHOOK PAYLOAD:")
    print(json.dumps(webhook_data, indent=2, default=str))
    print("=" * 80)

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
        
        # ✅ STEP 1: Extract core fields
        farmer_id = str(webhook_data.get('farmer_id', ''))
        job_id = str(webhook_data.get('id', ''))
        activities_data = webhook_data.get('activities', [])

        # In booking_webhook, plot_code extraction:
        plot_code = str(webhook_data.get('plot_id') or '')
        if not plot_code and activities_data:
            # ✅ Find first activity with a non-empty plot_id
            for act in activities_data:
                pid = str(act.get('plot_id') or '')
                if pid and pid not in ('None', 'null', ''):
                    plot_code = pid
                    break
        logger.info(f"Resolved plot_code: '{plot_code}'")

        # ✅ STEP 2: Fetch farmer details
        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            logger.warning(f"Farmer API error for {farmer_id}: {api_error}")
            farmer_details = {}

        with transaction.atomic():

            # ✅ STEP 3: Sync Farmer — only the job's plot
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data,
                                target_plot_code=plot_code)

            # ✅ Get crop/variety from farmer API for this specific plot
            crop_name, variety = '', ''
            if farmer_details and plot_code:
                for plot_data in farmer_details.get('plots', []):
                    pid = str(plot_data.get('plot_id') or plot_data.get('id') or '')
                    if pid == plot_code:
                        crop_name = plot_data.get('crop', '') or plot_data.get('crop_name', '') or ''
                        variety = plot_data.get('variety', '') or ''
                        logger.info(f"Got crop='{crop_name}' variety='{variety}' from farmer API plot {plot_code}")
                        break

            # ✅ Extract pruning date from webhook activities
            from django.utils.dateparse import parse_datetime, parse_date

            pruning_date_for_plot = None
            for act in activities_data:
                name = act.get('activity_name', '')
                if 'pruning' in name.lower() or 'छाटणी' in name:
                    raw = act.get('date_time') or act.get('scheduled_date')
                    if raw:
                        try:
                            if 'T' in str(raw):
                                p = parse_datetime(str(raw))
                                pruning_date_for_plot = p.date() if p else None
                            else:
                                pruning_date_for_plot = parse_date(str(raw))
                        except Exception:
                            pass
                    logger.info(f"Pruning date for plot: {pruning_date_for_plot}")
                    break

            # ✅ STEP 3.5: Get plot object
            plot = None
            if plot_code:
                plot = Plot.objects.filter(plot_code=plot_code, farmer=farmer).first()
                if not plot:
                    plot, created = get_or_create_plot(
                        plot_code, farmer,
                        activities_data[0].get('acres', 0) if activities_data else 0,
                        crop_name=crop_name,
                        variety=variety,
                    )
                    if created:
                        log_data['plots_created'] += 1

                # ✅ Always update pruning_date + crop from webhook on this specific plot
                update_fields = []
                if pruning_date_for_plot:
                    plot.pruning_date = pruning_date_for_plot
                    update_fields.append('pruning_date')
                if crop_name and not plot.crop_name:
                    plot.crop_name = crop_name
                    plot.variety = variety
                    update_fields.extend(['crop_name', 'variety'])
                if update_fields:
                    plot.save(update_fields=update_fields)
                    logger.info(f"Updated plot {plot_code}: pruning_date={pruning_date_for_plot} crop='{crop_name}'")

                logger.info(f"Job {job_id} → Plot id={plot.id} plot_code={plot.plot_code}")
            # ✅ STEP 4: sync_job with crop_name & variety
            job, job_created = sync_job(job_id, farmer, webhook_data, plot=plot,
                                        crop_name=crop_name, variety=variety)
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


def fetch_plot_crop_details(farmer_id: str, plot_code: str):
    """Fetch crop/variety for a specific plot from farmer API"""
    try:
        response = requests.get(
            f"{FARMER_API_BASE_URL}/api/get_farmer_details/{farmer_id}/",
            headers={"Authorization": f"Token {FARMER_API_TOKEN}"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        plots = data.get('plots', [])
        for plot_data in plots:
            pid = str(plot_data.get('plot_id') or plot_data.get('id') or '')
            if pid == str(plot_code):
                crop_name = plot_data.get('crop', '') or plot_data.get('crop_name', '') or ''
                variety = plot_data.get('variety', '') or plot_data.get('variety_name', '') or ''
                logger.info(f"Found crop='{crop_name}' variety='{variety}' for plot {plot_code}")
                return crop_name, variety
        
        logger.warning(f"Plot {plot_code} not found in farmer API for farmer {farmer_id}")
        return '', ''
    except Exception as e:
        logger.error(f"Failed to fetch plot details: {e}")
        return '', ''