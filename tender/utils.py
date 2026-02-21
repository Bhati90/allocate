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


# ============================================================================
# CAPACITY & AVAILABILITY UTILITIES
# ============================================================================
from django.db import models
from datetime import datetime

def get_mukkadam_remaining_workers(mukkadam_id, date):
    """
    Returns how many workers are still free for this mukkadam on this date,
    after considering leaves, extra workers, and existing allocations.
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)

    # use your existing effective-crew logic
    eff_crew = get_effective_crew_size(mukkadam, date)

    used_workers = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date=date,
    ).aggregate(total=models.Sum('allocated_workers'))['total'] or 0

    remaining = max(eff_crew - used_workers, 0)

    return {
        "effective_crew": eff_crew,
        "used_workers": used_workers,
        "remaining_workers": remaining,
    }

def get_mukkadam_availability(mukkadam_id, date):
    """
    Get mukkadam availability for a specific date.
    Calculates dynamically based on leaves, extra workers, and existing allocations.
    """
    mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    
    # Get effective crew size (base - leaves + extra workers)
    eff_crew = get_effective_crew_size(mukkadam, date)
    
    # Calculate workers already allocated on this date
    allocated_workers = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date=date,
    ).aggregate(total=models.Sum('allocated_workers'))['total'] or 0
    
    # Calculate remaining capacity
    remaining = max(eff_crew - allocated_workers, 0)
    
    return {
        'is_available': eff_crew > 0,
        'available_crew_size': eff_crew,
        'allocated_workers': allocated_workers,
        'remaining_capacity': remaining,
    }


def get_available_mukkadams(date, min_workers=1, activity_id=None):
    """
    Get all mukkadams available on a specific date
    
    Args:
        date: target date
        min_workers: minimum workers needed
        activity_id: filter by mukkadams who have rates for this activity
    
    Returns: list of available mukkadams with capacity info
    """
    mukkadams = Mukkadam.objects.all()
    
    # Filter by activity if specified
    if activity_id:
        mukkadams = mukkadams.filter(
            activity_rates__activity_id=activity_id,
            activity_rates__is_active=True
        ).distinct()
    
    available = []
    for mukkadam in mukkadams:
        availability = get_mukkadam_availability(mukkadam.mukkadam_id, date)
        
        if availability and availability['is_available'] and availability['remaining_capacity'] >= min_workers:
            available.append(availability)
    
    return available

def check_can_allocate(job_activity_id, mukkadam_id, date, area, workers, skip_strict_check=False):
    """
    Check if allocation is possible with PRODUCTIVITY validation
    
    Returns: (bool, str, dict) - (can_allocate, error_message, warnings)


    """

    from decimal import Decimal, ROUND_HALF_UP

    area = Decimal(str(area))
    workers = int(workers)
    try:
        job_activity = JobActivity.objects.get(id=job_activity_id)
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist):
        return False, "Job activity or mukkadam not found", {}
    
    warnings = {}
    
    # Check remaining area
    # Check remaining area
    if not skip_strict_check and area > job_activity.remaining_area:
        return False, f"Area exceeds remaining: {job_activity.remaining_area} acres still not allocated", {}

    # Check mukkadam capacity
    availability = get_mukkadam_availability(mukkadam_id, date)
    if not availability['is_available']:
        return False, f"Mukkadam not available on {date}", {}
    
    if workers > availability['remaining_capacity']:
        return False, f"Workers capacity is wrong: {availability['remaining_capacity']} workers available", {}
    
    # ⚠️ NEW: PRODUCTIVITY CHECK
    try:
        mukkadam_rate = mukkadam.activity_rates.get(
            activity=job_activity.activity,
            is_active=True
        )
        
        productivity = Decimal(str(mukkadam_rate.productivity_per_worker))
        max_capacity = workers * productivity  # now Decimal * int = Decimal ✓

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
                    'deficit': f"{area - max_capacity} acres short"
                },
                'suggestions': [
                    {
                        'option': 'reduce_area',
                        'description': f"Allocate only {suggested_area:.2f} acres (what team can complete)",
                        'allocation': {
                            'area': suggested_area,
                            'workers': workers,
                            'will_complete': True
                        }
                    },
                    {
                        'option': 'add_workers',
                        'description': f"Increase workers from {workers} to {required_workers} workers",
                        'allocation': {
                            'area': area,
                            'workers': required_workers,
                            'will_complete': True,
                            'note': f"Need {required_workers - workers} more workers"
                        }
                    },
                    {
                        'option': 'update_productivity',
                        'description': f"Update productivity from {productivity} to {required_productivity:.3f} acres/worker/day",
                        'allocation': {
                            'area': area,
                            'workers': workers,
                            'new_productivity': required_productivity,
                            'will_complete': True
                        }
                    },
                    {
                        'option': 'split_days',
                        'description': f"Split: {suggested_area:.2f} acres today + {area - suggested_area:.2f} acres tomorrow",
                        'allocations': [
                            {'date': date, 'area': suggested_area, 'workers': workers},
                            {'date': 'next_day', 'area': area - suggested_area, 'workers': workers}
                        ]
                    }
                ]
            }
            
            return False, "Productivity puted higher then real ", warnings
        
        elif area > (max_capacity * Decimal('0.9')):
            # Warning: Close to capacity (90%+)
            warnings['productivity_warning'] = {
                'severity': 'warning',
                'message': f"Team will be at {(area/max_capacity)*100:.1f}% capacity",
                'details': {
                    'workers': workers,
                    'productivity_per_worker': f"{productivity} acres/worker/day",
                    'max_capacity': f"{max_capacity} acres/day",
                    'requested': f"{area} acres",
                    'utilization': f"{(area/max_capacity)*100:.1f}%"
                },
                'note': "Allocation is possible but team will be working at near-maximum capacity"
            }
    
    except mukkadam.activity_rates.model.DoesNotExist:
        warnings['no_rate_card'] = {
            'severity': 'warning',
            'message': "No productivity data available for this mukkadam-activity combination",
            'note': "Proceeding without productivity validation"
        }
    
    # Check strict activities
    if job_activity.activity.is_strict and not skip_strict_check:
        scheduled_date = job_activity.scheduled_date
        # Only enforce date on FIRST allocation (nothing allocated yet)
        # Once work has started (allocated_area > 0), future dates are allowed
        if scheduled_date and str(scheduled_date) != str(date):
            if float(job_activity.allocated_area) == 0:
                return (
                    False,
                    f"Strict activity must start on its scheduled date: {scheduled_date}",
                    warnings,
                )
            # else: work already started, allow any future date
    # if job_activity.activity.is_strict and not skip_strict_check:
    #     # full_remaining = float(job_activity.remaining_area)

    #     # # How much already allocated on this date for this activity
    #     # existing_today = Allocation.objects.filter(
    #     #     job_activity=job_activity,
    #     #     allocated_date=date,
    #     # ).aggregate(total=models.Sum('allocated_area'))['total'] or 0.0

    #     # # Total after this allocation
    #     # total_for_date = existing_today + area

    #     # # For strict activities, total for the day must equal full remaining
    #     # if abs(total_for_date - full_remaining) > 1e-6:
    #     #     return (
    #     #         False,
    #     #         (
    #     #             f"Strict activity requires {full_remaining:.2f} ac total on one date. "
    #     #             f"Currently allocated: {existing_today:.2f} ac. "
    #     #             f"You're trying to add: {area:.2f} ac. "
    #     #             f"Total would be: {total_for_date:.2f} ac."
    #     #         ),
    #     #         warnings,
    #     #     )

    #     # Check if this mukkadam can handle their part
    #     # (No need to check if ALL mukkadams combined can do it - that's checked per allocation)
    #     max_capacity_this_mukkadam = workers * productivity if productivity else 0
    #     if area > max_capacity_this_mukkadam:
    #         return (
    #             False,
    #             f"This mukkadam's team ({workers} workers) can only handle {max_capacity_this_mukkadam:.2f} ac, but you're allocating {area:.2f} ac.",
    #             warnings,
    #         )

    return True, "OK", warnings # 👈 MAKE SURE THIS LINE EXISTS AT THE END

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
def get_effective_crew_size(mukkadam, date):
    if isinstance(date, str):
        from datetime import datetime
        date = datetime.strptime(date, "%Y-%m-%d").date()

    # ✅ CHECK GENERAL HOLIDAY FIRST
    is_holiday = Leave.objects.filter(
        date=date,
        leave_type='general',
        is_active=True,
        cluster__mukkadams=mukkadam  # ✅ holiday in mukkadam's cluster
    ).exists()

    if is_holiday:
        return 0  # ✅ entire cluster blocked, ignore leaves/extra workers

    base = mukkadam.crew_size

    from django.db import models

    leave_count = Leave.objects.filter(
        mukkadam=mukkadam,
        date=date,
    ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

    extra_count = ExtraWorker.objects.filter(
        mukkadam=mukkadam,
        date=date,
    ).aggregate(total=models.Sum('workers'))['total'] or 0

    eff = max(base - leave_count + extra_count, 0)
    return eff
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