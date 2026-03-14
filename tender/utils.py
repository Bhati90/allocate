"""
Utility functions for farm scheduling system
"""

# from asyncssh import logger
from django.db.models import Sum, Q, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import (
    ExtraWorker, Job, JobActivity, Mukkadam, MukkadamAvailability, 
    Allocation, ActivityCatalog
)

   
import requests
import logging

logger = logging.getLogger(__name__)
import concurrent.futures
PRESIGN_API_URL = 'https://demand.bharatintelligence.ai/chat/presign_obj_api/'
PRESIGN_TOKEN = 'c432208626a204d2d8de3d00b29f948eae61ebdb'
from django.core.cache import cache
def get_presigned_urls_batch(s3_keys):
    """
    ✅ Get multiple presigned URLs in parallel
    Returns: dict {s3_key: presigned_url}
    """
    if not s3_keys:
        return {}
    
    urls = {}
    
    def fetch_url(key):
        url = get_presigned_url(key)
        return (key, url)
    
    # Fetch in parallel with max 10 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_url, s3_keys)
        urls = dict(results)
    
    return urls
def get_presigned_url(s3_key):
    if not s3_key:
        return None
    
    # ✅ Check cache first (presigned URLs valid for 60 min)
    cache_key = f'presign_{s3_key}'
    cached_url = cache.get(cache_key)
    if cached_url:
        return cached_url
    
    # Fetch from API
    try:
        response = requests.get(
            PRESIGN_API_URL,
            params={'key': s3_key},
            headers={'Authorization': f'Token {PRESIGN_TOKEN}'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            url = data.get('url') or data
            
            # ✅ Cache for 55 minutes (5 min buffer before expiry)
            cache.set(cache_key, url, 3300)
            return url
    except Exception as e:
        logger.error(f"Error: {e}")
    
    return None
# ============================================================================
# CAPACITY & AVAILABILITY UTILITIES
# ============================================================================
# ── REPLACE your existing get_effective_crew_size + check_can_allocate ───────
# File: allocation_utils.py (or wherever these currently live)

from decimal import Decimal
from datetime import date as date_type, datetime
from django.db import models


def get_effective_crew_size(mukkadam, date, exclude_allocation_id=None):
    """
    Returns how many workers are effectively available for this mukkadam on this date.

    Key change: allocations with allows_second_job=True are NOT counted as "used"
    because the mukkadam will do those in the first half of the day and is free
    for a second job in the second half.
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    # General holiday in any of the mukkadam's clusters → 0
    is_holiday = Leave.objects.filter(
        date=date,
        leave_type='general',
        is_active=True,
        cluster__mukkadams=mukkadam,
    ).exists()
    if is_holiday:
        return 0

    base = mukkadam.crew_size

    leave_count = Leave.objects.filter(
        mukkadam=mukkadam,
        date=date,
        is_active=True,
    ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

    extra_count = ExtraWorker.objects.filter(
        mukkadam=mukkadam,
        date=date,
    ).aggregate(total=models.Sum('workers'))['total'] or 0

    eff = max(base - leave_count + extra_count, 0)
    return eff


def get_mukkadam_remaining_workers(mukkadam_id, date, exclude_allocation_id=None):
    """
    Returns remaining available workers for a mukkadam on a date.

    Allocations with allows_second_job=True are EXCLUDED from the 'used' count
    because the mukkadam is flagged as available for a second job.
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    eff_crew = get_effective_crew_size(mukkadam, date)

    # Only count allocations where allows_second_job=False
    # (half-day allocations don't block the rest of the day)
    used_qs = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date=date,
        allows_second_job=False,          # ← KEY CHANGE
        status__in=['scheduled', 'in_progress'],
    )
    if exclude_allocation_id:
        used_qs = used_qs.exclude(pk=exclude_allocation_id)

    used_workers = used_qs.aggregate(total=models.Sum('allocated_workers'))['total'] or 0
    remaining = max(eff_crew - used_workers, 0)

    return {
        "effective_crew": eff_crew,
        "used_workers": used_workers,
        "remaining_workers": remaining,
    }
import math

def get_mukkadam_availability(mukkadam_id, date, exclude_allocation_id=None):
    """
    Updated to skip allows_second_job allocations in the 'used workers' sum.
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    eff_crew = get_effective_crew_size(mukkadam, date)

    # Only allocations that actually block the day
    used_qs = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date=date,
        allows_second_job=False,          # ← KEY CHANGE
        status__in=['scheduled', 'in_progress'],
    )
    if exclude_allocation_id:
        used_qs = used_qs.exclude(pk=exclude_allocation_id)

    allocated_workers = used_qs.aggregate(total=models.Sum('allocated_workers'))['total'] or 0
    remaining = max(eff_crew - allocated_workers, 0)

    return {
        'is_available': eff_crew > 0,
        'available_crew_size': eff_crew,
        'allocated_workers': allocated_workers,
        'remaining_capacity': remaining,
    }

from .models import ClusterMukkadamAssignment
def check_can_allocate(job_activity_id, mukkadam_id, date, area, workers,
                       skip_strict_check=False, cluster_id=None,
                       exclude_allocation_id=None):

    area = Decimal(str(area))
    workers = int(workers)

    if isinstance(date, str):
        date = date_type.fromisoformat(str(date))

    try:
        job_activity = JobActivity.objects.get(id=job_activity_id)
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist):
        return False, "Job activity or mukkadam not found", {}

    warnings = {}

    # ── UPDOWN CHECK ──────────────────────────────────────────────────────────
    check_date_str = str(date)
    # ── UPDOWN CHECK ──────────────────────────────────────────────────────────
    if cluster_id:
        assignments = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam,
            cluster_id=cluster_id,
            is_active=True,
        )
        
        # If ANY assignment covers this date, they're available
        updown_assignments = [a for a in assignments if a.mukkadam_type == 'updown']
        
        if updown_assignments:
            available = False
            for assignment in updown_assignments:
                if assignment.updown_mode == 'range':
                    if assignment.updown_from_date and assignment.updown_to_date:
                        if assignment.updown_from_date <= date <= assignment.updown_to_date:
                            available = True
                            break
                elif assignment.updown_mode == 'specific':
                    if check_date_str in (assignment.updown_specific_dates or []):
                        available = True
                        break
            
            if not available:
                return (
                    False,
                    f"{mukkadam.mukkadam_name} is not available on {check_date_str} in this cluster",
                    {},
                )
    # ── REMAINING AREA CHECK ──────────────────────────────────────────────────
    if not skip_strict_check and area > job_activity.remaining_area:
        return False, f"Area exceeds remaining: {job_activity.remaining_area} acres still not allocated", {}

    # ── GET CREW SIZE & LEAVES ────────────────────────────────────────────────
    eff_crew = get_effective_crew_size(mukkadam, date)
    if eff_crew == 0:
        return False, f"Mukkadam not available on {date} (holiday or zero crew)", {}

    # ── HALF-DAY COMBINED CAPACITY CHECK ─────────────────────────────────────
    # Get any existing half-day allocations for this mukkadam on this date.
    # These don't block the day but their *needed* workers must combine
    # with this new job's workers to stay within crew_size.
    # ── HALF-DAY COMBINED CAPACITY CHECK ─────────────────────────────────────
    half_day_allocs = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date=date,
        allows_second_job=True,
        status__in=['scheduled', 'in_progress'],
    )
    if exclude_allocation_id:
        half_day_allocs = half_day_allocs.exclude(pk=exclude_allocation_id)

    if half_day_allocs.exists():
        # ── Calculate NEEDED workers for each half-day job (not allocated_workers) ──
        # "needed" = ceil(area / productivity), capped at crew_size
        half_day_needed_total = 0
        for hd_alloc in half_day_allocs:
            try:
                hd_rate = hd_alloc.mukkadam.activity_rates.get(
                    activity=hd_alloc.job_activity.activity,
                    is_active=True,
                )
                hd_productivity = float(hd_rate.productivity_per_worker)
                if hd_productivity > 0:
                    hd_needed = math.ceil(float(hd_alloc.job_activity.total_area) / hd_productivity)
                else:
                    hd_needed = hd_alloc.allocated_workers  # fallback
            except Exception:
                hd_needed = hd_alloc.allocated_workers  # fallback

            half_day_needed_total += hd_needed

        # "needed" for THIS job
        try:
            this_rate = mukkadam.activity_rates.get(
                activity=job_activity.activity,
                is_active=True,
            )
            this_productivity = float(this_rate.productivity_per_worker)
            this_needed = math.ceil(float(area) / this_productivity) if this_productivity > 0 else workers
        except Exception:
            this_needed = workers  # fallback

        on_leave = Leave.objects.filter(
            leave_type='mukkadam',
            mukkadam=mukkadam,
            date=date,
            is_active=True,
        ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

        available_crew = eff_crew - on_leave
        combined_needed = half_day_needed_total + this_needed
        available_crew = available_crew * 2.20

        if combined_needed > available_crew:
            return (
                False,
                f"Combined workers exceed crew capacity: "
                f"{half_day_needed_total} needed (½ day job) + {this_needed} needed (this job) "
                f"= {combined_needed} > {available_crew} available workers.",
                warnings,
            )

        # Also block if a full-day allocation already exists
        normal_used_count = Allocation.objects.filter(
            mukkadam=mukkadam,
            allocated_date=date,
            allows_second_job=False,
            status__in=['scheduled', 'in_progress'],
        ).exclude(pk=exclude_allocation_id or 0).aggregate(
            total=models.Sum('allocated_workers')
        )['total'] or 0

        if normal_used_count > 0:
            return (
                False,
                f"{mukkadam.mukkadam_name} already has a full-day allocation today.",
                warnings,
            )

        warnings['half_day_split'] = {
            'severity': 'info',
            'message': (
                f"2nd job for {mukkadam.mukkadam_name} today. "
                f"Day split: {half_day_needed_total}w (1st job) + {this_needed}w (this job) "
                f"= {combined_needed}/{available_crew} workers used."
            ),
        }

    else:
        # ── Standard capacity check (no half-day allocs) ──────────────────────
        normal_workers_sum = Allocation.objects.filter(
            mukkadam=mukkadam,
            allocated_date=date,
            allows_second_job=False,
            status__in=['scheduled', 'in_progress'],
        ).exclude(pk=exclude_allocation_id or 0).aggregate(
            total=models.Sum('allocated_workers')
        )['total'] or 0

        on_leave = Leave.objects.filter(
            leave_type='mukkadam',
            mukkadam=mukkadam,
            date=date,
            is_active=True,
        ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

        remaining_capacity = max(eff_crew - on_leave - normal_workers_sum, 0)
        if workers > remaining_capacity:
            return (
                False,
                f"Workers capacity exceeded: {remaining_capacity} workers available, "
                f"{workers} requested.",
                warnings,
            )
    # ── PRODUCTIVITY CHECK ────────────────────────────────────────────────────
    try:
        mukkadam_rate = mukkadam.activity_rates.get(
            activity=job_activity.activity,
            is_active=True,
        )
        productivity = Decimal(str(mukkadam_rate.productivity_per_worker))
        max_capacity = workers * productivity
        max_capacity = max_capacity*3

        if area > max_capacity:
            suggested_area = float(max_capacity)
            required_workers = int(float(area) / float(productivity)) if productivity > 0 else workers
            required_productivity = float(area) / workers if workers > 0 else float(productivity)

            warnings['productivity_warning'] = {
                'severity': 'error',
                'message': f"Team cannot complete {area} acres in 1 day!",
                'details': {
                    'workers': workers,
                    'productivity_per_worker': f"{productivity} acres/worker/day",
                    'max_capacity': f"{max_capacity} acres/day",
                    'requested': f"{area} acres",
                    'deficit': f"{area - max_capacity} acres short",
                },
                'suggestions': [
                    {
                        'option': 'reduce_area',
                        'description': f"Allocate only {suggested_area:.2f} acres",
                        'allocation': {'area': suggested_area, 'workers': workers, 'will_complete': True},
                    },
                    {
                        'option': 'add_workers',
                        'description': f"Increase workers to {required_workers}",
                        'allocation': {'area': area, 'workers': required_workers, 'will_complete': True,
                                       'note': f"Need {required_workers - workers} more workers"},
                    },
                    {
                        'option': 'update_productivity',
                        'description': f"Update productivity to {required_productivity:.3f} acres/worker/day",
                        'allocation': {'area': area, 'workers': workers,
                                       'new_productivity': required_productivity, 'will_complete': True},
                    },
                    {
                        'option': 'split_days',
                        'description': f"Split: {suggested_area:.2f} ac today + {float(area) - suggested_area:.2f} ac tomorrow",
                        'allocations': [
                            {'date': str(date), 'area': suggested_area, 'workers': workers},
                            {'date': 'next_day', 'area': float(area) - suggested_area, 'workers': workers},
                        ],
                    },
                ],
            }
            return False, "Productivity set higher than real", warnings

        elif area > (max_capacity * Decimal('0.9')):
            warnings['productivity_warning'] = {
                'severity': 'warning',
                'message': f"Team will be at {(area / max_capacity) * 100:.1f}% capacity",
                'details': {
                    'workers': workers,
                    'productivity_per_worker': f"{productivity} acres/worker/day",
                    'max_capacity': f"{max_capacity} acres/day",
                    'requested': f"{area} acres",
                    'utilization': f"{(area / max_capacity) * 100:.1f}%",
                },
                'note': "Near-maximum capacity",
            }

    except mukkadam.activity_rates.model.DoesNotExist:
        warnings['no_rate_card'] = {
            'severity': 'warning',
            'message': "No productivity data for this mukkadam-activity combination",
            'note': "Proceeding without productivity validation",
        }

    # ── STRICT ACTIVITY CHECK ─────────────────────────────────────────────────
    if job_activity.activity.is_strict and not skip_strict_check:
        scheduled_date = job_activity.scheduled_date
        if scheduled_date and str(scheduled_date) != str(date):
            if float(job_activity.allocated_area) == 0:
                return (
                    False,
                    f"Strict activity must start on its scheduled date: {scheduled_date}",
                    warnings,
                )

    return True, "OK", warnings

# ============================================================================
# SCHEDULING UTILITIES
# ============================================================================
from django.db import models

def auto_schedule_activity(job_activity_id, start_date, end_date, preferred_mukkadam_ids=None):
    """
    Automatically schedule an activity across available dates and mukkadams
    
    Args:
        job_activity_id: activity to schedule
        start_date: earliest date
        end_date: latest date
        preferred_mukkadam_ids: list of preferred mukkadam IDs (optional)
    
    Returns: list of created allocations or error message
    """
    try:
        job_activity = JobActivity.objects.get(id=job_activity_id)
    except JobActivity.DoesNotExist:
        return {'error': 'Job activity not found'}
    
    remaining_area = job_activity.remaining_area
    if remaining_area <= 0:
        return {'error': 'No remaining area to allocate'}
    
    # Get activity rate
    farmer_rate = job_activity.rate_per_acre
    
    # Get available mukkadams
    mukkadams = Mukkadam.objects.all()
    if preferred_mukkadam_ids:
        mukkadams = mukkadams.filter(mukkadam_id__in=preferred_mukkadam_ids)
    
    # Get mukkadams with rates for this activity
    mukkadams_with_rates = mukkadams.filter(
        activity_rates__activity=job_activity.activity,
        activity_rates__is_active=True
    ).distinct()
    
    if not mukkadams_with_rates.exists():
        return {'error': 'No mukkadams have rates for this activity'}
    
    allocations = []
    current_date = start_date
    
    while remaining_area > 0 and current_date <= end_date:
        # Get available mukkadams for this date
        day_allocations = []
        
        for mukkadam in mukkadams_with_rates:
            availability = get_mukkadam_availability(mukkadam.mukkadam_id, current_date)
            
            if not availability['is_available'] or availability['remaining_capacity'] == 0:
                continue
            
            # Get mukkadam rate
            try:
                mukkadam_rate_obj = mukkadam.activity_rates.get(
                    activity=job_activity.activity,
                    is_active=True
                )
                mukkadam_rate = mukkadam_rate_obj.rate_per_acre
            except:
                continue
            
            # Calculate how much this mukkadam can do
            workers_available = availability['remaining_capacity']
            
            # Estimate area per worker (simplified)
            productivity = job_activity.activity.estimated_workers_per_acre
            area_possible = workers_available / productivity if productivity > 0 else 1
            
            allocate_area = min(area_possible, remaining_area)
            allocate_workers = min(workers_available, int(allocate_area * productivity))
            
            if allocate_area > 0 and allocate_workers > 0:
                # Create allocation
                allocation = Allocation(
                    job_activity=job_activity,
                    mukkadam=mukkadam,
                    allocated_date=current_date,
                    allocated_area=allocate_area,
                    allocated_workers=allocate_workers,
                    farmer_rate=farmer_rate,
                    mukkadam_rate=mukkadam_rate,
                    status='scheduled'
                )
                
                day_allocations.append(allocation)
                remaining_area -= allocate_area
                
                if remaining_area <= 0:
                    break
        
        if day_allocations:
            allocations.extend(day_allocations)
        
        current_date += timedelta(days=1)
    
    if remaining_area > 0:
        return {
            'warning': f'Could not allocate all area. Remaining: {remaining_area} acres',
            'allocations': allocations
        }
    
    return {'success': True, 'allocations': allocations}


# ============================================================================
# FINANCIAL UTILITIES
# ============================================================================

def calculate_job_financials(job_id):
    """
    Calculate complete financial summary for a job
    """
    try:
        job = Job.objects.get(job_id=job_id)
    except Job.DoesNotExist:
        return None
    
    # Get all allocations for this job
    allocations = Allocation.objects.filter(job_activity__job=job)
    
    summary = {
        'job_id': job_id,
        'farmer_name': job.farmer.farmer_name,
        'total_farmer_revenue': allocations.aggregate(Sum('farmer_amount'))['farmer_amount__sum'] or 0,
        'total_mukkadam_cost': allocations.aggregate(Sum('mukkadam_amount'))['mukkadam_amount__sum'] or 0,
        'total_profit': 0,
        'activities': []
    }
    
    summary['total_profit'] = summary['total_farmer_revenue'] - summary['total_mukkadam_cost']
    
    # Per activity breakdown
    for activity in job.activities.all():
        activity_allocations = allocations.filter(job_activity=activity)
        
        activity_summary = {
            'activity_name': activity.activity.name,
            'total_area': activity.total_area,
            'allocated_area': activity.allocated_area,
            'remaining_area': activity.remaining_area,
            'farmer_revenue': activity_allocations.aggregate(Sum('farmer_amount'))['farmer_amount__sum'] or 0,
            'mukkadam_cost': activity_allocations.aggregate(Sum('mukkadam_amount'))['mukkadam_amount__sum'] or 0,
            'profit': 0,
            'allocations': []
        }
        
        activity_summary['profit'] = activity_summary['farmer_revenue'] - activity_summary['mukkadam_cost']
        
        for allocation in activity_allocations:
            activity_summary['allocations'].append({
                'date': str(allocation.allocated_date),
                'mukkadam': allocation.mukkadam.mukkadam_name,
                'area': float(allocation.allocated_area),
                'workers': allocation.allocated_workers,
                'farmer_amount': float(allocation.farmer_amount),
                'mukkadam_amount': float(allocation.mukkadam_amount),
                'profit': float(allocation.profit)
            })
        
        summary['activities'].append(activity_summary)
    
    return summary


def calculate_mukkadam_financials(mukkadam_id, start_date=None, end_date=None):
    """
    Calculate financial summary for a mukkadam
    """
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return None
    
    allocations = Allocation.objects.filter(mukkadam=mukkadam)
    
    if start_date:
        allocations = allocations.filter(allocated_date__gte=start_date)
    if end_date:
        allocations = allocations.filter(allocated_date__lte=end_date)
    
    total_due = allocations.aggregate(Sum('mukkadam_amount'))['mukkadam_amount__sum'] or 0
    
    # Get payments
    payments = mukkadam.payments.all()
    if start_date:
        payments = payments.filter(paid_at__date__gte=start_date)
    if end_date:
        payments = payments.filter(paid_at__date__lte=end_date)
    
    total_paid = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    return {
        'mukkadam_id': mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'total_due': float(total_due),
        'total_paid': float(total_paid),
        'balance': float(total_due - total_paid),
        'allocation_count': allocations.count(),
        'payment_count': payments.count()
    }


# ============================================================================
# REPORTING UTILITIES
# ============================================================================

def get_daily_capacity_report(date):
    """
    Get capacity report for all mukkadams on a specific date
    """
    report = []
    
    for mukkadam in Mukkadam.objects.all():
        availability = get_mukkadam_availability(mukkadam.mukkadam_id, date)
        
        # Get allocations for this date
        allocations = Allocation.objects.filter(
            mukkadam=mukkadam,
            allocated_date=date
        ).select_related('job_activity__job__farmer', 'job_activity__activity')
        
        allocation_details = []
        for allocation in allocations:
            allocation_details.append({
                'job_id': allocation.job_activity.job.job_id,
                'farmer': allocation.job_activity.job.farmer.farmer_name,
                'activity': allocation.job_activity.activity.name,
                'area': float(allocation.allocated_area),
                'workers': allocation.allocated_workers
            })
        
        report.append({
            'mukkadam': {
                'id': mukkadam.mukkadam_id,
                'name': mukkadam.mukkadam_name,
                'total_crew': mukkadam.crew_size
            },
            'availability': availability,
            'allocations': allocation_details,
            'utilization_percent': (availability['allocated_workers'] / availability['available_crew_size'] * 100) 
                                  if availability['available_crew_size'] > 0 else 0
        })
    
    return report


def get_weekly_summary(start_date, end_date):
    """
    Get weekly summary of all activities
    """
    allocations = Allocation.objects.filter(
        allocated_date__range=[start_date, end_date]
    ).select_related(
        'job_activity__job__farmer',
        'job_activity__activity',
        'mukkadam'
    )
    
    summary = {
        'period': f"{start_date} to {end_date}",
        'total_allocations': allocations.count(),
        'total_area': float(allocations.aggregate(Sum('allocated_area'))['allocated_area__sum'] or 0),
        'total_farmer_revenue': float(allocations.aggregate(Sum('farmer_amount'))['farmer_amount__sum'] or 0),
        'total_mukkadam_cost': float(allocations.aggregate(Sum('mukkadam_amount'))['mukkadam_amount__sum'] or 0),
        'total_profit': 0,
        'by_activity': {},
        'by_mukkadam': {},
        'by_day': {}
    }
    
    summary['total_profit'] = summary['total_farmer_revenue'] - summary['total_mukkadam_cost']
    
    # Group by activity
    for allocation in allocations:
        activity_name = allocation.job_activity.activity.name
        if activity_name not in summary['by_activity']:
            summary['by_activity'][activity_name] = {
                'count': 0,
                'area': 0,
                'revenue': 0,
                'cost': 0,
                'profit': 0
            }
        
        summary['by_activity'][activity_name]['count'] += 1
        summary['by_activity'][activity_name]['area'] += float(allocation.allocated_area)
        summary['by_activity'][activity_name]['revenue'] += float(allocation.farmer_amount)
        summary['by_activity'][activity_name]['cost'] += float(allocation.mukkadam_amount)
        summary['by_activity'][activity_name]['profit'] += float(allocation.profit)
        
        # Group by mukkadam
        mukkadam_name = allocation.mukkadam.mukkadam_name
        if mukkadam_name not in summary['by_mukkadam']:
            summary['by_mukkadam'][mukkadam_name] = {
                'count': 0,
                'area': 0,
                'payment_due': 0
            }
        
        summary['by_mukkadam'][mukkadam_name]['count'] += 1
        summary['by_mukkadam'][mukkadam_name]['area'] += float(allocation.allocated_area)
        summary['by_mukkadam'][mukkadam_name]['payment_due'] += float(allocation.mukkadam_amount)
        
        # Group by day
        day_str = str(allocation.allocated_date)
        if day_str not in summary['by_day']:
            summary['by_day'][day_str] = {
                'allocations': 0,
                'area': 0,
                'profit': 0
            }
        
        summary['by_day'][day_str]['allocations'] += 1
        summary['by_day'][day_str]['area'] += float(allocation.allocated_area)
        summary['by_day'][day_str]['profit'] += float(allocation.profit)
    
    return summary


# ============================================================================
# DATA VALIDATION UTILITIES
# ============================================================================
from django.db.models import Sum
from .models import Leave, Mukkadam

import logging
logger = logging.getLogger(__name__)

def validate_allocation_data(data):
    """
    Validate allocation data before creation
    
    Returns: (bool, dict) - (is_valid, errors)
    """
    errors = {}
    
    required_fields = [
        'job_activity_id', 'mukkadam_id', 'allocated_date',
        'allocated_area', 'allocated_workers', 'farmer_rate', 'mukkadam_rate'
    ]
    
    for field in required_fields:
        if field not in data or data[field] is None:
            errors[field] = 'This field is required'
    
    if errors:
        return False, errors
    
    # Validate numeric values
    try:
        if float(data['allocated_area']) <= 0:
            errors['allocated_area'] = 'Must be greater than 0'
    except (ValueError, TypeError):
        errors['allocated_area'] = 'Invalid number'
    
    try:
        if int(data['allocated_workers']) <= 0:
            errors['allocated_workers'] = 'Must be greater than 0'
    except (ValueError, TypeError):
        errors['allocated_workers'] = 'Invalid number'
    
    # Check existence
    if 'job_activity_id' in data:
        if not JobActivity.objects.filter(id=data['job_activity_id']).exists():
            errors['job_activity_id'] = 'Job activity not found'
    
    if 'mukkadam_id' in data:
        if not Mukkadam.objects.filter(mukkadam_id=data['mukkadam_id']).exists():
            errors['mukkadam_id'] = 'Mukkadam not found'
    
    return len(errors) == 0, errors

