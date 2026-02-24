"""
Carry-forward service: triggered after farmer agrees with mukkadam's day-end report.

Rules:
- Less done: actual < allocated → reduce current, carry diff to next working day
- More done: actual > allocated → reduce next day's allocation by the extra
- "Next working day" = next calendar day skipping Leave (general or mukkadam) for this mukkadam
- Carry-forward allocation: full crew, skip availability/worker check, skip productivity check
- This only runs when farmer_agreed = True (use_actual_for_settlement already set)
"""
# tender/ervices/carry_forward.py
from django.db import models
from tender.models import Leave, Allocation, JobActivity  # add whatever models are used
from django.db.models import Q
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction

from tender.models import (
    Allocation, JobActivity, MukkadamAvailability, Leave
)

def is_working_day(check_date: date, mukkadam) -> bool:
    is_blocked = Leave.objects.filter(
        date=check_date,
        is_active=True
    ).filter(
        Q(leave_type='general') |
        Q(leave_type='mukkadam', mukkadam=mukkadam)
    ).exists()

    return not is_blocked

def next_working_day(from_date: date, mukkadam, max_lookahead: int = 30) -> date | None:
    """
    Returns the next working day after from_date for this mukkadam.
    Returns None if no working day found within max_lookahead days.
    """
    check = from_date + timedelta(days=1)
    for _ in range(max_lookahead):
        if is_working_day(check, mukkadam):
            return check
        check += timedelta(days=1)
    return None


def get_next_allocation_for_activity(job_activity, mukkadam, after_date: date) -> Allocation | None:
    """
    Find the next existing allocation for this job_activity + mukkadam after a given date.
    """
    return Allocation.objects.filter(
        job_activity=job_activity,
        mukkadam=mukkadam,
        allocated_date__gt=after_date,
    ).order_by('allocated_date').first()


# ─────────────────────────────────────────────────────────────────────────────
# CORE: LESS DONE (actual < allocated)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_less_done(allocation: Allocation, carry_area: Decimal) -> dict:
    """
    carry_area = allocated - actual (e.g. 0.2)

    Steps:
    1. Find next working day
    2. Check if there's an existing allocation for same job_activity on that day
       a. YES → reduce it by carry_area, push that same carry_area one more day (recursive)
       b. NO  → create new carry-forward allocation (full crew, skip all checks)
    """
    mukkadam = allocation.mukkadam
    job_activity = allocation.job_activity
    current_date = allocation.allocated_date
    log = []

    # Find next working day
    target_date = next_working_day(current_date, mukkadam)
    if not target_date:
        return {
            'success': False,
            'error': 'No working day found in next 30 days to carry forward',
            'carry_area': float(carry_area),
        }

    result = _place_carry_forward(
        job_activity=job_activity,
        mukkadam=mukkadam,
        carry_area=carry_area,
        target_date=target_date,
        full_workers=allocation.allocated_workers,
        farmer_rate=allocation.farmer_rate,
        mukkadam_rate=allocation.mukkadam_rate,
        cluster=allocation.cluster,
        depth=0,
        log=log,
    )

    return {
        'success': result,
        'log': log,
    }


def _place_carry_forward(
    job_activity, mukkadam, carry_area: Decimal,
    target_date: date, full_workers: int,
    farmer_rate: Decimal, mukkadam_rate: Decimal,
    cluster, depth: int, log: list,
    max_depth: int = 10,
) -> bool:
    """
    Recursive placement of carry_area onto target_date.

    If existing allocation found on target_date for this job:
      - Reduce it by carry_area
      - Push that same carry_area to the next working day
    Else:
      - Create new allocation (full crew, is_carry_forward=True)
    """
    if depth >= max_depth:
        log.append(f'Max depth reached, could not place {carry_area} ac')
        return False

    existing = get_next_allocation_for_activity(
        job_activity, mukkadam, target_date - timedelta(days=1)
    )
    # Check if that existing allocation is exactly on target_date
    existing_on_target = None
    if existing and existing.allocated_date == target_date:
        existing_on_target = existing

    if existing_on_target:
        # Reduce existing by carry_area
        old_area = existing_on_target.allocated_area
        new_area = old_area - carry_area

        if new_area <= Decimal('0'):
            # Edge case: carry is >= existing allocation → absorb it fully, delete existing
            actual_carry = carry_area - old_area  # what remains after absorbing
            log.append(
                f'Day {target_date}: existing {old_area} ac fully absorbed by carry {carry_area} ac'
                + (f', still {actual_carry} ac to place' if actual_carry > 0 else '')
            )

            # Update job_activity.allocated_area (reduce by old_area since we're removing it)
            job_activity.allocated_area -= old_area
            job_activity.save(update_fields=['allocated_area'])

            existing_on_target.delete()

            if actual_carry > Decimal('0'):
                next_date = next_working_day(target_date, mukkadam)
                if not next_date:
                    log.append('No further working day found')
                    return False
                return _place_carry_forward(
                    job_activity, mukkadam, actual_carry,
                    next_date, full_workers,
                    farmer_rate, mukkadam_rate, cluster,
                    depth + 1, log,
                )
            return True

        else:
            # Reduce existing, push carry_area to next day
            existing_on_target.allocated_area = new_area
            existing_on_target.save(update_fields=['allocated_area'])

            # Update job_activity allocated_area (net zero since carry will be re-added next day)
            # No change needed on job_activity here — the carry was already counted as unallocated

            log.append(
                f'Day {target_date}: reduced existing allocation from {old_area} to {new_area} ac, '
                f'pushing {carry_area} ac to next working day'
            )

            next_date = next_working_day(target_date, mukkadam)
            if not next_date:
                log.append('No further working day found after displacement')
                return False

            return _place_carry_forward(
                job_activity, mukkadam, carry_area,
                next_date, full_workers,
                farmer_rate, mukkadam_rate, cluster,
                depth + 1, log,
            )

    else:
        # No existing allocation on target_date → create carry-forward
        new_alloc = Allocation.objects.create(
            job_activity=job_activity,
            mukkadam=mukkadam,
            allocated_date=target_date,
            allocated_area=carry_area,
            allocated_workers=full_workers,
            farmer_rate=farmer_rate,
            mukkadam_rate=mukkadam_rate,
            status='scheduled',
            cluster=cluster,
            is_carry_forward=True,   # flag — add this field to model
            notes=f'Auto carry-forward of {carry_area} ac from previous day',
        )
        # job_activity.allocated_area stays the same — this area was already counted
        # as "allocated" before actual was confirmed; now we're re-placing it
        log.append(
            f'Day {target_date}: created carry-forward allocation of {carry_area} ac '
            f'with {full_workers} workers (id={new_alloc.id})'
        )
        return True


# ─────────────────────────────────────────────────────────────────────────────
# CORE: MORE DONE (actual > allocated)
# ─────────────────────────────────────────────────────────────────────────────

def _handle_more_done(allocation: Allocation, extra_area: Decimal) -> dict:
    """
    extra_area = actual - allocated (e.g. 0.5)

    Find next allocation for same job_activity + mukkadam.
    Reduce it by extra_area.
    If it goes to 0 or below, delete it (and cascade further if needed).
    """
    mukkadam = allocation.mukkadam
    job_activity = allocation.job_activity
    log = []

    remaining_to_absorb = extra_area

    # Walk through future allocations for this job_activity+mukkadam in date order
    future_allocs = Allocation.objects.filter(
        job_activity=job_activity,
        mukkadam=mukkadam,
        allocated_date__gt=allocation.allocated_date,
    ).order_by('allocated_date')

    for future_alloc in future_allocs:
        if remaining_to_absorb <= Decimal('0'):
            break

        if future_alloc.allocated_area <= remaining_to_absorb:
            # Absorb fully
            remaining_to_absorb -= future_alloc.allocated_area
            log.append(
                f'Day {future_alloc.allocated_date}: fully absorbed {future_alloc.allocated_area} ac, '
                f'deleting allocation (id={future_alloc.id})'
            )
            job_activity.allocated_area -= future_alloc.allocated_area
            job_activity.save(update_fields=['allocated_area'])
            future_alloc.delete()
        else:
            # Partial reduction
            old_area = future_alloc.allocated_area
            future_alloc.allocated_area -= remaining_to_absorb
            future_alloc.save(update_fields=['allocated_area'])

            job_activity.allocated_area -= remaining_to_absorb
            job_activity.save(update_fields=['allocated_area'])

            log.append(
                f'Day {future_alloc.allocated_date}: reduced from {old_area} to {future_alloc.allocated_area} ac'
            )
            remaining_to_absorb = Decimal('0')

    if remaining_to_absorb > Decimal('0'):
        log.append(
            f'Warning: {remaining_to_absorb} ac extra done but no future allocations to absorb it. '
            f'Job activity may be over-completed.'
        )

    return {'success': True, 'log': log}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def process_carry_forward(allocation_id: int) -> dict:
    """
    Called after farmer_agreed = True is saved on an allocation.

    1. Update current allocation's allocated_area to actual_area_done
    2. Update job_activity.allocated_area accordingly
    3. If less done → carry forward the diff
    4. If more done → reduce future allocations
    5. If exact → nothing to do
    """
    try:
        allocation = Allocation.objects.select_related(
            'job_activity', 'mukkadam', 'cluster'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return {'success': False, 'error': 'Allocation not found'}

    if not allocation.farmer_agreed:
        return {'success': False, 'error': 'Farmer has not agreed yet'}

    if not allocation.actual_area_done:
        return {'success': False, 'error': 'No actual_area_done on this allocation'}

    allocated = allocation.allocated_area
    actual = allocation.actual_area_done
    diff = actual - allocated   # positive = more done, negative = less done

    if abs(diff) < Decimal('0.01'):
        return {'success': True, 'message': 'Exact match, no carry-forward needed', 'log': []}

    # Step 1: Update current allocation area to actual
    old_allocated = allocation.allocated_area
    allocation.allocated_area = actual
    allocation.save(update_fields=['allocated_area'])

    # Step 2: Update job_activity.allocated_area
    job_activity = allocation.job_activity
    job_activity.allocated_area = job_activity.allocated_area + (actual - old_allocated)
    job_activity.save(update_fields=['allocated_area'])

    if diff < 0:
        # Less done — carry forward
        carry_area = abs(diff)
        result = _handle_less_done(allocation, carry_area)
        result['type'] = 'less_done'
        result['allocated_was'] = float(allocated)
        result['actual_done'] = float(actual)
        result['carried_forward'] = float(carry_area)
        return result

    else:
        # More done — reduce future
        result = _handle_more_done(allocation, diff)
        result['type'] = 'more_done'
        result['allocated_was'] = float(allocated)
        result['actual_done'] = float(actual)
        result['absorbed_extra'] = float(diff)
        return result