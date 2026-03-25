# # views.py or webhooks.py

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
    booking = webhook_data.get('booking') or {}

    # ── booking_type: read from booking object ────────────────────
    raw_booking_type = (booking.get('booking_type') or '').lower()
    if raw_booking_type == 'ondemand':
        booking_type = 'ondemand'
    elif raw_booking_type == 'tender':
        booking_type = 'tender'
    else:
        booking_type = 'tender'  # default fallback

    # ── scheduled_date: use activity date_time if available ───────
    scheduled_date = None

    # First try job-level scheduled_date
    raw_date = webhook_data.get('scheduled_date')
    if raw_date:
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            parsed = parse_datetime(str(raw_date)) or parse_date(str(raw_date))
            scheduled_date = parsed.date() if hasattr(parsed, 'date') else parsed
        except Exception:
            pass

    # If no job-level date, use first activity's date_time directly
    if not scheduled_date:
        activities = webhook_data.get('activities') or []
        for act in activities:
            raw_act_date = act.get('date_time') or act.get('scheduled_date')
            if raw_act_date:
                try:
                    from django.utils.dateparse import parse_datetime, parse_date
                    if 'T' in str(raw_act_date):
                        parsed = parse_datetime(str(raw_act_date))
                        scheduled_date = parsed.date() if parsed else None
                    else:
                        scheduled_date = parse_date(str(raw_act_date))
                    if scheduled_date:
                        break
                except Exception:
                    pass

    defaults = {
        'farmer': farmer,
        'work_id': str(job_id),
        'crop_name': crop_name,
        'variety': variety,
        'booking_amount': (
            booking.get('total_amount') and
            __import__('decimal').Decimal(str(booking.get('total_amount', 0)))
        ) or __import__('decimal').Decimal('0'),
        'status': 'pending',
        'priority': webhook_data.get('priority', 'MEDIUM'),
        'scheduled_date': scheduled_date,
        'activity_notes': webhook_data.get('activity_notes', '') or '',
        'internal_notes': webhook_data.get('internal_notes', '') or '',
        'total_activities_amount': __import__('decimal').Decimal(
            str(webhook_data.get('total_activities_amount', 0))
        ),
        'is_field_verified': webhook_data.get('is_field_verified', False),
        'booking_type': booking_type,  # ✅ correctly derived
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
    booking_id = booking_data.get('id')
    if not booking_id:
        return None

    total_amount = Decimal(str(booking_data.get('total_amount', 0)))
    advance_paid = Decimal(str(booking_data.get('advance_paid', 0)))
    balance      = Decimal(str(booking_data.get('balance', total_amount - advance_paid)))

    raw_status = booking_data.get('status', 'BOOKED').upper()
    if raw_status == 'PAID':
        status = 'PAID'
    elif raw_status in ['PARTIAL', 'PARTIALLY_PAID']:
        status = 'PARTIALLY_PAID'
    elif raw_status == 'REFUNDED':
        status = 'REFUNDED'
    else:
        status = 'UNPAID'

    try:
        booking = JobBooking.objects.get(booking_id=int(booking_id))

        changed_fields = []
        if booking.status != status:
            booking.status = status
            changed_fields.append('status')
        # ✅ Round both sides to 2dp before comparing to avoid Decimal precision mismatch
        if booking.total_amount.quantize(Decimal('0.01')) != total_amount.quantize(Decimal('0.01')):
            booking.total_amount = total_amount
            changed_fields.append('total_amount')
        if booking.advance_paid.quantize(Decimal('0.01')) != advance_paid.quantize(Decimal('0.01')):
            booking.advance_paid = advance_paid
            changed_fields.append('advance_paid')
        if booking.balance.quantize(Decimal('0.01')) != balance.quantize(Decimal('0.01')):
            booking.balance = balance
            changed_fields.append('balance')
        assignee = booking_data.get('assignee_number', '') or ''
        if booking.assignee_number != assignee:
            booking.assignee_number = assignee
            changed_fields.append('assignee_number')

        if changed_fields:
            booking.save(update_fields=changed_fields)
            logger.info(f"Booking {booking_id} updated: {changed_fields}")
        else:
            logger.info(f"Booking {booking_id} unchanged — skipped")

    except JobBooking.DoesNotExist:
        booking = JobBooking.objects.create(
            job=job,
            booking_id=int(booking_id),
            status=status,
            total_amount=total_amount,
            advance_paid=advance_paid,
            balance=balance,
            assignee_number=booking_data.get('assignee_number', '') or '',
        )
        logger.info(f"Booking {booking_id} created for job {job.job_id}")

    # ✅ Payments — only create new ones
    existing_payment_ids = set(
        booking.payments.values_list('payment_id', flat=True)
    )
    for payment_data in booking_data.get('payments', []):
        payment_id = payment_data.get('id')
        if not payment_id or int(payment_id) in existing_payment_ids:
            continue

        paid_at_raw = payment_data.get('paid_at')
        if paid_at_raw:
            from django.utils.dateparse import parse_datetime
            paid_at = parse_datetime(paid_at_raw)
        else:
            from django.utils.timezone import now
            paid_at = now()

        raw_mode = (payment_data.get('mode') or 'CASH').upper()
        valid_modes = {'CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE', 'WILL_PAY_LATER', 'OTHER'}
        mode = raw_mode if raw_mode in valid_modes else 'OTHER'

        FarmerPayment.objects.create(
            payment_id  = int(payment_id),
            booking     = booking,
            mode        = mode,
            amount      = Decimal(str(payment_data.get('amount', 0))),
            notes       = payment_data.get('notes', '') or '',
            paid_status = payment_data.get('paid_status', True),
            paid_at     = paid_at,
        )
        logger.info(f"Payment {payment_id} created for booking {booking_id}")

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
                # Inside sync_activities, replace the entire date logic else block:

                else:
                    # Non-pruning activity
                    if pruning_date:
                        # Tender with pruning date — compute gap-based schedule
                        scheduled_date = get_scheduled_date_for_activity(
                            activity_catalog, job, pruning_date
                        )
                        logger.info(f"Plot {plot_code} '{activity_name}' → date={scheduled_date} from pruning={pruning_date}")
                    else:
                        # No pruning date (ondemand OR tender without pruning) 
                        # → use the activity's own date_time directly
                        raw_act_date = activity_data.get('date_time') or activity_data.get('scheduled_date')
                        if raw_act_date:
                            try:
                                if 'T' in str(raw_act_date):
                                    parsed = parse_datetime(str(raw_act_date))
                                    if parsed:
                                        scheduled_date = parsed.date()
                                        scheduled_time = parsed.time()
                                else:
                                    scheduled_date = parse_date(str(raw_act_date))
                                logger.info(f"Plot {plot_code} '{activity_name}' → date={scheduled_date} from activity date_time (no pruning)")
                            except Exception as e:
                                logger.warning(f"Could not parse activity date for '{activity_name}': {e}")
                        else:
                            logger.warning(f"Plot {plot_code}: no pruning date and no activity date for '{activity_name}'")
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
# ALLOCATION_API_TOKEN = "Token b5920d610d85bff62bb0ab70f971ed6a44eb1b8c"
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


def _compute_scheduled_date(activity_catalog, job_clusters, plot, act_data, today):
    """
    Priority:
    1. pruning_date + cluster gap override  (if cluster + plot.pruning_date exist)
    2. pruning_date + global gap            (if plot.pruning_date exists)
    3. date from webhook act_data           (fallback)
    4. today                               (last resort)

    Never returns a date before today.
    """
    from datetime import timedelta
    from django.utils.dateparse import parse_datetime, parse_date
    from .models import ClusterActivityScheduleRule, ActivityScheduleRule

    pruning_date = plot.pruning_date if plot else None

    if pruning_date:
        # Try cluster-level gap first
        gap_days = None

        for cluster in job_clusters:
            rule = ClusterActivityScheduleRule.objects.filter(
                cluster=cluster,
                activity=activity_catalog,
            ).first()
            if rule:
                gap_days = rule.gap_days
                break

        # Fall back to global gap
        if gap_days is None:
            global_rule = ActivityScheduleRule.objects.filter(
                activity=activity_catalog
            ).first()
            gap_days = global_rule.gap_days if global_rule else activity_catalog.default_gap_days

        computed = pruning_date + timedelta(days=gap_days)
        return max(computed, today)  # never in the past

    # No pruning date — use webhook date
    raw = act_data.get('date_time') or act_data.get('scheduled_date')
    if raw:
        try:
            parsed = (
                parse_datetime(str(raw)).date()
                if 'T' in str(raw)
                else parse_date(str(raw))
            )
            if parsed:
                return max(parsed, today)
        except Exception:
            pass

    return today  # last resort

@api_view(['POST'])
def run_mukkadam_sync(request):
    sync_tender_mukkadams()
    return JsonResponse({"success": True})
def _sync_existing_job_activities(job, activities_data):
    from datetime import date
    from decimal import Decimal
    from .models import ActivityCatalog, JobActivity

    today = date.today()

    incoming_api_ids = set(
        str(act.get('id') or '')
        for act in activities_data
        if act.get('id')
    )

    existing_api_id_map = {
        a.api_activity_id: a
        for a in job.activities.all()
        if a.api_activity_id
    }

    job_clusters = list(job.clusters.all())
    plot = job.plot

    # ── 1. Handle cancelled activities from webhook ────────────────
    for act_data in activities_data:
        api_act_id = str(act_data.get('id') or '')
        status     = (act_data.get('status') or act_data.get('activity_status') or '').upper()

        if status == 'CANCELLED' and api_act_id in existing_api_id_map:
            act = existing_api_id_map[api_act_id]
            if act.allocation_status == 'completed':
                logger.info(f"[ACTIVITY SYNC] Activity {act.id} (api_id={api_act_id}) cancelled in webhook but completed — skipped")
            else:
                for alloc in act.allocations.exclude(status='completed'):
                    alloc.status = 'cancelled'
                    alloc.save(update_fields=['status'])
                act.delete()
                del existing_api_id_map[api_act_id]
                logger.info(f"[ACTIVITY SYNC] Deleted activity {act.id} (api_id={api_act_id}) — cancelled in webhook")

    # ── 2. Hard delete activities no longer in webhook ─────────────
    for api_id, act in list(existing_api_id_map.items()):  # 👈 list() snapshot
        if api_id not in incoming_api_ids:
            if act.allocation_status == 'completed':
                logger.info(f"[ACTIVITY SYNC] Activity {act.id} (api_id={api_id}) removed but completed — skipped")
            else:
                for alloc in act.allocations.exclude(status='completed'):
                    alloc.status = 'cancelled'
                    alloc.save(update_fields=['status'])
                act.delete()
                logger.info(f"[ACTIVITY SYNC] Deleted activity {act.id} (api_id={api_id}) — removed from webhook")

    # ── 3. Add new activities not yet on this job ──────────────────
    for act_data in activities_data:
        api_act_id = str(act_data.get('id') or '')
        status     = (act_data.get('status') or act_data.get('activity_status') or '').upper()

        if status == 'CANCELLED':
            continue

        if not api_act_id:
            continue

        # 👇 skip only if exists AND is active (not cancelled)
        existing = existing_api_id_map.get(api_act_id)
        if existing and not existing.is_lost:
            continue

        # If existing but is_lost=True — delete old row first, then re-create
        if existing and existing.is_lost:
            existing.delete()
            logger.info(f"[ACTIVITY SYNC] Deleted is_lost activity {existing.id} (api_id={api_act_id}) — re-creating")

        activity_name = act_data.get('activity_name', '').strip()
        if not activity_name:
            continue

        activity_catalog = ActivityCatalog.objects.filter(
            name__iexact=activity_name
        ).first()
        if not activity_catalog:
            activity_catalog, _ = ActivityCatalog.objects.get_or_create(
                name=activity_name,
                defaults={'source': 'api'}
            )

        scheduled_date = _compute_scheduled_date(
            activity_catalog, job_clusters, plot, act_data, today
        )

        total_area    = Decimal(str(act_data.get('acres') or 0))
        total_price   = Decimal(str(act_data.get('total_price') or 0))
        rate_per_acre = (total_price / total_area).quantize(Decimal('0.01')) if total_area else Decimal('0')

        try:
            JobActivity.objects.create(
                job             = job,
                activity        = activity_catalog,
                plot            = plot,
                api_activity_id = api_act_id,
                total_area      = total_area,
                allocated_area  = Decimal('0'),
                remaining_area  = total_area,
                scheduled_date  = scheduled_date,
                rate_per_acre   = rate_per_acre,
                source          = 'api',
                original_source = 'api',
            )
            logger.info(f"[ACTIVITY SYNC] Created activity {api_act_id} — {activity_name} on job {job.job_id}")
        except Exception as e:
            logger.error(f"[ACTIVITY SYNC] Failed to create activity {api_act_id}: {e}")
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def booking_webhook(request):

    webhook_data    = request.data

    job_id          = str(webhook_data.get('id', ''))
    print(job_id)
    print(webhook_data)
    booking_data    = webhook_data.get('booking') or {}
    activities_data = webhook_data.get('activities') or []

    try:
        # ── Job exists → sync booking + activities ───────────
        job = Job.objects.select_related('booking').prefetch_related(
            'clusters', 'activities__activity'
        ).get(job_id=job_id)

        with transaction.atomic():
            # 1. Sync booking — update if changed, never change booking_id
            sync_booking(job, booking_data)

            # 2. Sync activities — add new, delete removed (except completed)
            if activities_data:
                _sync_existing_job_activities(job, activities_data)

        return JsonResponse({
            'status': 'success',
            'action': 'updated',
            'job_id': job_id,
        }, status=200)

    except Job.DoesNotExist:
        # ── New job → full create ────────────────────────────
        log_data = {
            'webhook_data':         webhook_data,
            'status':               'failed',
            'error_type':           None,
            'error_message':        None,
            'farmer_id':            None,
            'job_id':               None,
            'cluster_matched':      False,
            'cluster_id':           None,
            'activities_processed': 0,
            'activities_failed':    0,
            'plots_created':        0,
        }

        farmer_id = str(webhook_data.get('farmer_id', ''))
        plot_code = str(webhook_data.get('plot_id') or '')

        if not plot_code and activities_data:
            for act in activities_data:
                pid = str(act.get('plot_id') or '')
                if pid not in ('', 'None', 'null'):
                    plot_code = pid
                    break

        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            farmer_details = {}

        with transaction.atomic():
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data,
                                 target_plot_code=plot_code)

            crop_name, variety = '', ''
            if farmer_details and plot_code:
                for pd in farmer_details.get('plots', []):
                    pid = str(pd.get('plot_id') or pd.get('id') or '')
                    if pid == plot_code:
                        crop_name = pd.get('crop', '') or ''
                        variety   = pd.get('variety', '') or ''
                        break

            from django.utils.dateparse import parse_datetime, parse_date
            pruning_date = None
            for act in activities_data:
                name = act.get('activity_name', '')
                if 'pruning' in name.lower() or 'छाटणी' in name:
                    raw = act.get('date_time') or act.get('scheduled_date')
                    if raw:
                        try:
                            pruning_date = (
                                parse_datetime(str(raw)).date()
                                if 'T' in str(raw)
                                else parse_date(str(raw))
                            )
                        except Exception:
                            pass
                    break

            plot = None
            if plot_code:
                plot, created = get_or_create_plot(
                    plot_code, farmer,
                    activities_data[0].get('acres', 0) if activities_data else 0,
                    crop_name=crop_name, variety=variety,
                )
                if created:
                    log_data['plots_created'] += 1

                update_fields = []
                if pruning_date:
                    plot.pruning_date = pruning_date
                    update_fields.append('pruning_date')
                if crop_name and not plot.crop_name:
                    plot.crop_name = crop_name
                    plot.variety   = variety
                    update_fields.extend(['crop_name', 'variety'])
                if update_fields:
                    plot.save(update_fields=update_fields)

            job, _ = sync_job(job_id, farmer, webhook_data, plot=plot,
                              crop_name=crop_name, variety=variety)

            if plot:
                for c in plot.clusters.all():
                    job.clusters.add(c)
                    log_data['cluster_matched'] = True
                    log_data['cluster_id'] = c.id

            sync_booking(job, booking_data)
            sync_activities(job, farmer, activities_data, log_data)

        log_data['status'] = 'success' if log_data['activities_failed'] == 0 else 'partial'
        WebhookLog.objects.create(**log_data)

        return JsonResponse({
            'status':               'success',
            'action':               'created',
            'job_id':               job_id,
            'activities_processed': log_data['activities_processed'],
        }, status=200)

    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def sync_webhook(request):
    webhook_data = request.data
    job_id = str(webhook_data.get('id', ''))
    booking_data = webhook_data.get('booking', {})

    try:
        # ── Job exists ──────────────────────────────────────
        job = Job.objects.get(job_id=job_id)
        
        # Only check booking
        sync_booking(job, booking_data)
        
        return JsonResponse({
            'status': 'success',
            'action': 'booking_checked',
            'job_id': job_id,
        }, status=200)

    except Job.DoesNotExist:
        # ── Brand new job — full create ──────────────────────
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

        farmer_id = str(webhook_data.get('farmer_id', ''))
        plot_code = str(webhook_data.get('plot_id') or '')
        activities_data = webhook_data.get('activities', [])

        if not plot_code and activities_data:
            for act in activities_data:
                pid = str(act.get('plot_id') or '')
                if pid not in ('', 'None', 'null'):
                    plot_code = pid
                    break

        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            farmer_details = {}

        with transaction.atomic():
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data,
                                 target_plot_code=plot_code)

            crop_name, variety = '', ''
            if farmer_details and plot_code:
                for plot_data in farmer_details.get('plots', []):
                    pid = str(plot_data.get('plot_id') or plot_data.get('id') or '')
                    if pid == plot_code:
                        crop_name = plot_data.get('crop', '') or ''
                        variety   = plot_data.get('variety', '') or ''
                        break

            from django.utils.dateparse import parse_datetime, parse_date
            pruning_date_for_plot = None
            for act in activities_data:
                name = act.get('activity_name', '')
                if 'pruning' in name.lower() or 'छाटणी' in name:
                    raw = act.get('date_time') or act.get('scheduled_date')
                    if raw:
                        try:
                            pruning_date_for_plot = parse_datetime(str(raw)).date() if 'T' in str(raw) else parse_date(str(raw))
                        except Exception:
                            pass
                    break

            plot = None
            if plot_code:
                plot, created = get_or_create_plot(
                    plot_code, farmer,
                    activities_data[0].get('acres', 0) if activities_data else 0,
                    crop_name=crop_name, variety=variety,
                )
                if created:
                    log_data['plots_created'] += 1

                update_fields = []
                if pruning_date_for_plot:
                    plot.pruning_date = pruning_date_for_plot
                    update_fields.append('pruning_date')
                if crop_name and not plot.crop_name:
                    plot.crop_name = crop_name
                    plot.variety   = variety
                    update_fields.extend(['crop_name', 'variety'])
                if update_fields:
                    plot.save(update_fields=update_fields)

            job, _ = sync_job(job_id, farmer, webhook_data, plot=plot,
                              crop_name=crop_name, variety=variety)

            if plot:
                for c in plot.clusters.all():
                    job.clusters.add(c)
                    log_data['cluster_matched'] = True
                    log_data['cluster_id'] = c.id

            sync_booking(job, booking_data)
            sync_activities(job, farmer, activities_data, log_data)

            

        log_data['status'] = 'success' if log_data['activities_failed'] == 0 else 'partial'
        WebhookLog.objects.create(**log_data)

        return JsonResponse({
            'status': 'success',
            'action': 'created',
            'job_id': job_id,
            'activities_processed': log_data['activities_processed'],
        }, status=200)

    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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





from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import requests
import logging

from .models import FarmerBillWebhookLog

logger = logging.getLogger(__name__)

# ── Paste your webhook URL here ──────────────────────────────
FARMER_BILL_WEBHOOK_URL =''
# FARMER_BILL_WEBHOOK_URL = 'https://ops.bharatintelligence.ai/ops/allocation/bill_collect/'
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, authentication_classes
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def send_farmer_bill_to_webhook(request):
    import threading
    try:
        data = request.data

        required = ['farmer', 'job', 'mukkadam', 'work_done', 'bill_summary']
        missing  = [f for f in required if f not in data]
        if missing:
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

        farmer        = data.get('farmer', {})
        job           = data.get('job', {})
        mukkadam      = data.get('mukkadam', {})
        payments      = data.get('payment_history', [])
        bill          = data.get('bill_summary', {})
        work_done     = data.get('work_done', [])
        activity_name = data.get('activity_name', '')

        # ── Auth token ────────────────────────────────────────
        auth_header = request.headers.get('Authorization', '')
        auth_token  = auth_header.replace('Token ', '').replace('Bearer ', '').strip() or data.get('auth_token', '')

        # ── User + Cluster in parallel threads ───────────────
        sent_by_name  = None
        sent_by_email = None
        sent_by_id    = None
        cluster_obj   = None

        def resolve_user():
            nonlocal sent_by_name, sent_by_email, sent_by_id
            try:
                from rest_framework.authtoken.models import Token
                if not auth_token:
                    return
                token_obj = Token.objects.select_related('user__profile').filter(key=auth_token).first()
                if token_obj:
                    user          = token_obj.user
                    sent_by_id    = str(user.id)
                    sent_by_email = user.email
                    sent_by_name  = (
                        getattr(user, 'get_full_name', lambda: '')() or
                        getattr(user.profile, 'full_name', None) or
                        user.username
                    )
            except Exception as e:
                logger.warning(f"Could not resolve user: {e}")

        def resolve_cluster():
            nonlocal cluster_obj
            try:
                job_id = job.get('id')
                if job_id:
                    # One query — get cluster directly
                    from .models import Job
                    job_obj = Job.objects.filter(job_id=job_id).prefetch_related('clusters').first()
                    if job_obj:
                        cluster_obj = job_obj.clusters.first()
            except Exception as e:
                logger.warning(f"Could not resolve cluster: {e}")

        # Run user + cluster lookup in parallel
        t1 = threading.Thread(target=resolve_user)
        t2 = threading.Thread(target=resolve_cluster)
        t1.start(); t2.start()
        t1.join();  t2.join()

        # ── Build payload ─────────────────────────────────────
        payload = {
            'event':         'farmer_bill_collect_initiated',
            'timestamp':     data.get('timestamp'),
            'activity_name': activity_name,
            'sent_by':       {'name': sent_by_name, 'email': sent_by_email, 'id': sent_by_id},
            'farmer':        {'id': farmer.get('id'), 'name': farmer.get('name'), 'phone': farmer.get('phone')},
            'job':           {'id': job.get('id'), 'crop': job.get('crop'), 'plot': job.get('plot')},
            'mukkadam':      {'name': mukkadam.get('name'), 'mobile': mukkadam.get('mobile')},
            'work_done': [{
                'activity':      w.get('activity'),
                'plot_name':     w.get('plot_name', ''),
                'date':          w.get('date'),
                'acres_done':    w.get('acres_done'),
                'rate_per_acre': w.get('rate_per_acre'),
                'amount':        w.get('amount'),
            } for w in work_done],
            'payment_history': [{
                'date': p.get('date'), 'amount': p.get('amount'),
                'mode': p.get('mode'), 'notes': p.get('notes', ''),
            } for p in payments],
            'bill_summary': {
                'total_billed':       bill.get('total_billed'),
                'total_already_paid': bill.get('total_already_paid'),
                'balance_due_now':    bill.get('balance_due_now'),
                'why_this_bill':      bill.get('why_this_bill'),
            },
        }

        # ── Fire webhook + save DB in parallel ───────────────
        webhook_status         = None
        webhook_response       = None
        webhook_detail         = None
        webhook_booking_id     = None
        webhook_booking_status = None
        webhook_success        = None

        def fire_webhook():
            nonlocal webhook_status, webhook_response, webhook_detail
            nonlocal webhook_booking_id, webhook_booking_status, webhook_success
            try:
                wh_res = requests.post(
                    FARMER_BILL_WEBHOOK_URL,
                    json=payload,
                    timeout=10,
                    headers={
                        'Content-Type':  'application/json',
                        'Authorization': 'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000',
                    },
                )
                webhook_status   = wh_res.status_code
                webhook_response = wh_res.text
                try:
                    resp_json              = wh_res.json()
                    webhook_detail         = resp_json.get('detail') or resp_json.get('message') or resp_json.get('error')
                    webhook_booking_id     = str(resp_json.get('booking_id', '')) or None
                    webhook_booking_status = resp_json.get('status')
                    webhook_success        = wh_res.status_code == 200 and 'already paid' not in str(webhook_detail or '').lower()
                except Exception:
                    webhook_success = wh_res.status_code == 200
            except Exception as e:
                webhook_response = str(e)
                webhook_success  = False

        # Fire webhook in background — don't block response
        wh_thread = threading.Thread(target=fire_webhook)
        wh_thread.start()
        wh_thread.join(timeout=8)  # wait max 8s, then continue

        # ── Save to DB ────────────────────────────────────────
        FarmerBillWebhookLog.objects.create(
            auth_token             = auth_token,
            sent_by_name           = sent_by_name,
            sent_by_email          = sent_by_email,
            sent_by_id             = sent_by_id,
            cluster                = cluster_obj,
            farmer_id              = farmer.get('id'),
            farmer_name            = farmer.get('name'),
            farmer_phone           = farmer.get('phone'),
            job_id                 = job.get('id'),
            crop_name              = job.get('crop'),
            plot_name              = job.get('plot'),
            mukkadam_name          = mukkadam.get('name'),
            mukkadam_mobile        = mukkadam.get('mobile'),
            activity_name          = activity_name,
            total_billed           = bill.get('total_billed'),
            total_paid             = bill.get('total_already_paid'),
            balance_due            = bill.get('balance_due_now'),
            full_payload           = payload,
            webhook_status         = webhook_status,
            webhook_response       = webhook_response,
            webhook_detail         = webhook_detail,
            webhook_booking_id     = webhook_booking_id,
            webhook_booking_status = webhook_booking_status,
            webhook_success        = webhook_success,
        )

        return Response({
            'success':         True,
            'webhook_status':  webhook_status,
            'webhook_success': webhook_success,
            'detail':          webhook_detail,
            'booking_status':  webhook_booking_status,
            'message':         webhook_detail or 'Bill details sent and saved successfully',
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



FARMER_PAYMENT_CONFIRMATION_WEBHOOK_URL = ''
# ── Paste your confirmation webhook URL here ─────────────────
# FARMER_PAYMENT_CONFIRMATION_WEBHOOK_URL = 'https://ops.bharatintelligence.ai/ops/allocation/bill_collect/'
from .models import FarmerPaymentWebhookLog

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def farmer_payment_webhook(request):
    """
    Receives payment from farmer's payment link and records it.

    Expected payload:
    {
        "booking_id": "434",
        "amount": 2000,
        "mode": "UPI",                        ← optional, default UPI
        "transaction_id": "TXN123456",        ← optional
        "notes": "Paid via link",             ← optional
        "paid_at": "2026-03-10T14:00:00Z",   ← optional, default now
        "confirmation_webhook_url": "https://your-crm.com/webhook/"  ← optional override
    }
    """
    from datetime import datetime
    import uuid

    raw_payload = request.data
    log = None

    try:
        booking_id     = str(raw_payload.get('booking_id', '')).strip()
        amount         = raw_payload.get('amount')
        mode           = raw_payload.get('mode', 'UPI').upper()
        transaction_id = raw_payload.get('transaction_id') or str(uuid.uuid4())[:8]
        notes          = raw_payload.get('notes', 'Paid via farmer payment link')
        paid_at_raw    = raw_payload.get('paid_at')
        confirmation_url = raw_payload.get('confirmation_webhook_url') or FARMER_PAYMENT_CONFIRMATION_WEBHOOK_URL

        # ── Validate ─────────────────────────────────────────
        if not booking_id:
            return Response({'error': 'booking_id is required'}, status=400)
        if not amount:
            return Response({'error': 'amount is required'}, status=400)

        try:
            amount = Decimal(str(amount))
        except Exception:
            return Response({'error': 'Invalid amount'}, status=400)

        # ── Parse paid_at ─────────────────────────────────────
        if paid_at_raw:
            try:
                from django.utils.dateparse import parse_datetime
                paid_at = parse_datetime(paid_at_raw)
            except Exception:
                paid_at = datetime.now()
        else:
            paid_at = datetime.now()

        # ── Create initial log ────────────────────────────────
        log = FarmerPaymentWebhookLog.objects.create(
            booking_ref = booking_id,
            amount         = amount,
            mode           = mode,
            transaction_id = transaction_id,
            notes          = notes,
            paid_at        = paid_at,
            raw_payload    = raw_payload,
            status         = 'received',
            confirmation_webhook_url = confirmation_url,
        )

        # ── Find booking ──────────────────────────────────────
        try:
            booking = JobBooking.objects.get(booking_id=booking_id)
        except JobBooking.DoesNotExist:
            log.status = 'failed'
            log.error  = f'Booking #{booking_id} not found'
            log.save()
            return Response({'error': f'Booking #{booking_id} not found'}, status=404)

        log.booking = booking
        log.save()

        # ── Duplicate check ───────────────────────────────────
        already_exists = FarmerPayment.objects.filter(
            booking=booking,
            amount=amount,
            paid_at__date=paid_at.date() if paid_at else datetime.now().date(),
        ).exists()

        if already_exists:
            log.status = 'duplicate'
            log.save()
            return Response({
                'success': False,
                'message': 'Duplicate payment — already recorded for this booking/amount/date',
            }, status=200)

        # ── Generate payment_id ───────────────────────────────
        last_payment = FarmerPayment.objects.order_by('-payment_id').first()
        new_payment_id = (last_payment.payment_id + 1) if last_payment else 100001

        # ── Create FarmerPayment ──────────────────────────────
        farmer_payment = FarmerPayment.objects.create(
            booking    = booking,
            payment_id = new_payment_id,
            mode       = mode if mode in ['CASH','UPI','ZOHO_PAYMENT','BANK_TRANSFER','CHEQUE','OTHER'] else 'UPI',
            amount     = amount,
            notes      = f"{notes} | txn: {transaction_id}",
            paid_at    = paid_at or datetime.now(),
            paid_status = True,
        )

        # ── Update JobBooking status ──────────────────────────
        all_payments = FarmerPayment.objects.filter(booking=booking, paid_status=True)
        total_paid   = sum(p.amount for p in all_payments)

        if total_paid >= booking.total_amount:
            booking.status  = 'PAID'
        elif total_paid > 0:
            booking.status  = 'PARTIALLY_PAID'

        booking.balance = max(Decimal('0'), booking.total_amount - total_paid)
        booking.save()

        # ── Update log ────────────────────────────────────────
        log.payment_created = True
        log.farmer_payment  = farmer_payment
        log.status          = 'processed'
        log.save()

        # ── Send confirmation webhook ─────────────────────────
        confirmation_payload = {
            'event':       'farmer_payment_received',
            'timestamp':   datetime.now().isoformat(),
            'booking_id':  booking_id,
            'job_id':      booking.job.job_id,
            'farmer_name': booking.job.farmer.farmer_name if booking.job.farmer else '—',
            'farmer_phone': getattr(booking.job.farmer, 'phone_number', '') or getattr(booking.job.farmer, 'mobile_number', ''),
            'payment': {
                'payment_id':    new_payment_id,
                'amount':        float(amount),
                'mode':          mode,
                'transaction_id': transaction_id,
                'paid_at':       str(paid_at),
            },
            'booking_summary': {
                'total_amount': float(booking.total_amount),
                'total_paid':   float(total_paid),
                'balance':      float(booking.balance),
                'status':       booking.status,
            },
        }

        try:
            conf_res = requests.post(
                confirmation_url,
                json=confirmation_payload,
                timeout=10,
                headers={'Content-Type': 'application/json','Authorization' :'Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000'},
             )
            log.confirmation_sent   = True
            log.confirmation_status = conf_res.status_code
            log.save()
        except Exception as e:
            logger.warning(f"Confirmation webhook failed: {e}")
            log.confirmation_sent = False
            log.save()

        logger.info(f"Payment webhook processed — Booking #{booking_id} ₹{amount}")

        return Response({
            'success':    True,
            'message':    f'Payment of ₹{amount} recorded for booking #{booking_id}',
            'payment_id': new_payment_id,
            'booking_status': booking.status,
            'balance_remaining': float(booking.balance),
        }, status=200)

    except Exception as e:
        logger.error(f"farmer_payment_webhook error: {e}")
        if log:
            log.status = 'failed'
            log.error  = str(e)
            log.save()
        return Response({'error': str(e)}, status=500)





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
def sync_booking(job: Job, booking_data: dict):
    booking_id = booking_data.get('id')
    if not booking_id:
        return None

    total_amount = Decimal(str(booking_data.get('total_amount', 0)))
    advance_paid = Decimal(str(booking_data.get('advance_paid', 0)))
    balance      = Decimal(str(booking_data.get('balance', total_amount - advance_paid)))

    raw_status = booking_data.get('status', 'BOOKED').upper()
    if raw_status == 'PAID':
        status = 'PAID'
    elif raw_status in ['PARTIAL', 'PARTIALLY_PAID']:
        status = 'PARTIALLY_PAID'
    elif raw_status == 'REFUNDED':
        status = 'REFUNDED'
    else:
        status = 'UNPAID'

    try:
        booking = JobBooking.objects.get(booking_id=int(booking_id))

        changed_fields = []
        if booking.status != status:
            booking.status = status
            changed_fields.append('status')
        # ✅ Round both sides to 2dp before comparing to avoid Decimal precision mismatch
        if booking.total_amount.quantize(Decimal('0.01')) != total_amount.quantize(Decimal('0.01')):
            booking.total_amount = total_amount
            changed_fields.append('total_amount')
        if booking.advance_paid.quantize(Decimal('0.01')) != advance_paid.quantize(Decimal('0.01')):
            booking.advance_paid = advance_paid
            changed_fields.append('advance_paid')
        if booking.balance.quantize(Decimal('0.01')) != balance.quantize(Decimal('0.01')):
            booking.balance = balance
            changed_fields.append('balance')
        assignee = booking_data.get('assignee_number', '') or ''
        if booking.assignee_number != assignee:
            booking.assignee_number = assignee
            changed_fields.append('assignee_number')

        if changed_fields:
            booking.save(update_fields=changed_fields)
            logger.info(f"Booking {booking_id} updated: {changed_fields}")
        else:
            logger.info(f"Booking {booking_id} unchanged — skipped")

    except JobBooking.DoesNotExist:
        booking = JobBooking.objects.create(
            job=job,
            booking_id=int(booking_id),
            status=status,
            total_amount=total_amount,
            advance_paid=advance_paid,
            balance=balance,
            assignee_number=booking_data.get('assignee_number', '') or '',
        )
        logger.info(f"Booking {booking_id} created for job {job.job_id}")

    # ✅ Payments — only create new ones
    existing_payment_ids = set(
        booking.payments.values_list('payment_id', flat=True)
    )
    for payment_data in booking_data.get('payments', []):
        payment_id = payment_data.get('id')
        if not payment_id or int(payment_id) in existing_payment_ids:
            continue

        paid_at_raw = payment_data.get('paid_at')
        if paid_at_raw:
            from django.utils.dateparse import parse_datetime
            paid_at = parse_datetime(paid_at_raw)
        else:
            from django.utils.timezone import now
            paid_at = now()

        raw_mode = (payment_data.get('mode') or 'CASH').upper()
        valid_modes = {'CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE', 'WILL_PAY_LATER', 'OTHER'}
        mode = raw_mode if raw_mode in valid_modes else 'OTHER'

        FarmerPayment.objects.create(
            payment_id  = int(payment_id),
            booking     = booking,
            mode        = mode,
            amount      = Decimal(str(payment_data.get('amount', 0))),
            notes       = payment_data.get('notes', '') or '',
            paid_status = payment_data.get('paid_status', True),
            paid_at     = paid_at,
        )
        logger.info(f"Payment {payment_id} created for booking {booking_id}")

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
                    # Non-pruning activity
                    if pruning_date:
                        # Has pruning date → compute gap-based schedule
                        scheduled_date = get_scheduled_date_for_activity(
                            activity_catalog, job, pruning_date
                        )
                        logger.info(f"Plot {plot_code} '{activity_name}' → date={scheduled_date} from pruning={pruning_date}")
                    else:
                        # No pruning date → use activity's own date_time directly
                        raw_act_date = activity_data.get('date_time') or activity_data.get('scheduled_date')
                        if raw_act_date:
                            try:
                                if 'T' in str(raw_act_date):
                                    parsed = parse_datetime(str(raw_act_date))
                                    if parsed:
                                        scheduled_date = parsed.date()
                                        scheduled_time = parsed.time()
                                else:
                                    scheduled_date = parse_date(str(raw_act_date))
                                logger.info(f"Plot {plot_code} '{activity_name}' → date={scheduled_date} from activity date_time (no pruning)")
                            except Exception as e:
                                logger.warning(f"Could not parse activity date for '{activity_name}': {e}")
                        else:
                            logger.warning(f"Plot {plot_code}: no pruning date and no activity date for '{activity_name}'")
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
# ALLOCATION_API_TOKEN = "Token b5920d610d85bff62bb0ab70f971ed6a44eb1b8c"
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
    webhook_data = request.data
    
    # ✅ Add this debug line temporarily
    print("RAW DATA:", webhook_data)
    print("JOB ID:", webhook_data.get('id'))
    

    webhook_data = request.data
    job_id       = str(webhook_data.get('id', ''))
    booking_data = webhook_data.get('booking', {})

    try:
        # ── Job exists → only check booking ─────────────────
        job = Job.objects.get(job_id=job_id)
        sync_booking(job, booking_data)
        return JsonResponse({
            'status': 'success',
            'action': 'booking_checked',
            'job_id': job_id,
        }, status=200)

    except Job.DoesNotExist:
        # ── New job → full create ────────────────────────────
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

        farmer_id       = str(webhook_data.get('farmer_id', ''))
        activities_data = webhook_data.get('activities', [])
        plot_code       = str(webhook_data.get('plot_id') or '')

        if not plot_code and activities_data:
            for act in activities_data:
                pid = str(act.get('plot_id') or '')
                if pid not in ('', 'None', 'null'):
                    plot_code = pid
                    break

        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            farmer_details = {}

        with transaction.atomic():
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data,
                                 target_plot_code=plot_code)

            crop_name, variety = '', ''
            if farmer_details and plot_code:
                for pd in farmer_details.get('plots', []):
                    pid = str(pd.get('plot_id') or pd.get('id') or '')
                    if pid == plot_code:
                        crop_name = pd.get('crop', '') or ''
                        variety   = pd.get('variety', '') or ''
                        break

            from django.utils.dateparse import parse_datetime, parse_date
            pruning_date = None
            for act in activities_data:
                name = act.get('activity_name', '')
                if 'pruning' in name.lower() or 'छाटणी' in name:
                    raw = act.get('date_time') or act.get('scheduled_date')
                    if raw:
                        try:
                            pruning_date = parse_datetime(str(raw)).date() if 'T' in str(raw) else parse_date(str(raw))
                        except Exception:
                            pass
                    break

            plot = None
            if plot_code:
                plot, created = get_or_create_plot(
                    plot_code, farmer,
                    activities_data[0].get('acres', 0) if activities_data else 0,
                    crop_name=crop_name, variety=variety,
                )
                if created:
                    log_data['plots_created'] += 1

                update_fields = []
                if pruning_date:
                    plot.pruning_date = pruning_date
                    update_fields.append('pruning_date')
                if crop_name and not plot.crop_name:
                    plot.crop_name = crop_name
                    plot.variety   = variety
                    update_fields.extend(['crop_name', 'variety'])
                if update_fields:
                    plot.save(update_fields=update_fields)

            job, _ = sync_job(job_id, farmer, webhook_data, plot=plot,
                              crop_name=crop_name, variety=variety)

            if plot:
                for c in plot.clusters.all():
                    job.clusters.add(c)
                    log_data['cluster_matched'] = True
                    log_data['cluster_id'] = c.id

            sync_booking(job, booking_data)
            sync_activities(job, farmer, activities_data, log_data)

            
        log_data['status'] = 'success' if log_data['activities_failed'] == 0 else 'partial'
        WebhookLog.objects.create(**log_data)

        return JsonResponse({
            'status': 'success',
            'action': 'created',
            'job_id': job_id,
            'activities_processed': log_data['activities_processed'],
        }, status=200)

    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
def sync_webhook(request):
    webhook_data = request.data
    job_id = str(webhook_data.get('id', ''))
    booking_data = webhook_data.get('booking', {})

    try:
        # ── Job exists ──────────────────────────────────────
        job = Job.objects.get(job_id=job_id)
        
        # Only check booking
        sync_booking(job, booking_data)
        
        return JsonResponse({
            'status': 'success',
            'action': 'booking_checked',
            'job_id': job_id,
        }, status=200)

    except Job.DoesNotExist:
        # ── Brand new job — full create ──────────────────────
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

        farmer_id = str(webhook_data.get('farmer_id', ''))
        plot_code = str(webhook_data.get('plot_id') or '')
        activities_data = webhook_data.get('activities', [])

        if not plot_code and activities_data:
            for act in activities_data:
                pid = str(act.get('plot_id') or '')
                if pid not in ('', 'None', 'null'):
                    plot_code = pid
                    break

        farmer_details, api_error = fetch_farmer_details(farmer_id)
        if api_error:
            farmer_details = {}

        with transaction.atomic():
            farmer = sync_farmer(farmer_id, farmer_details or {}, webhook_data,
                                 target_plot_code=plot_code)

            crop_name, variety = '', ''
            if farmer_details and plot_code:
                for plot_data in farmer_details.get('plots', []):
                    pid = str(plot_data.get('plot_id') or plot_data.get('id') or '')
                    if pid == plot_code:
                        crop_name = plot_data.get('crop', '') or ''
                        variety   = plot_data.get('variety', '') or ''
                        break

            from django.utils.dateparse import parse_datetime, parse_date
            pruning_date_for_plot = None
            for act in activities_data:
                name = act.get('activity_name', '')
                if 'pruning' in name.lower() or 'छाटणी' in name:
                    raw = act.get('date_time') or act.get('scheduled_date')
                    if raw:
                        try:
                            pruning_date_for_plot = parse_datetime(str(raw)).date() if 'T' in str(raw) else parse_date(str(raw))
                        except Exception:
                            pass
                    break

            plot = None
            if plot_code:
                plot, created = get_or_create_plot(
                    plot_code, farmer,
                    activities_data[0].get('acres', 0) if activities_data else 0,
                    crop_name=crop_name, variety=variety,
                )
                if created:
                    log_data['plots_created'] += 1

                update_fields = []
                if pruning_date_for_plot:
                    plot.pruning_date = pruning_date_for_plot
                    update_fields.append('pruning_date')
                if crop_name and not plot.crop_name:
                    plot.crop_name = crop_name
                    plot.variety   = variety
                    update_fields.extend(['crop_name', 'variety'])
                if update_fields:
                    plot.save(update_fields=update_fields)

            job, _ = sync_job(job_id, farmer, webhook_data, plot=plot,
                              crop_name=crop_name, variety=variety)

            if plot:
                for c in plot.clusters.all():
                    job.clusters.add(c)
                    log_data['cluster_matched'] = True
                    log_data['cluster_id'] = c.id

            sync_booking(job, booking_data)
            sync_activities(job, farmer, activities_data, log_data)

            

        log_data['status'] = 'success' if log_data['activities_failed'] == 0 else 'partial'
        WebhookLog.objects.create(**log_data)

        return JsonResponse({
            'status': 'success',
            'action': 'created',
            'job_id': job_id,
            'activities_processed': log_data['activities_processed'],
        }, status=200)

    except Exception as e:
        logger.error(f"Webhook failed: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
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

