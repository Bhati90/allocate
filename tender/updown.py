"""
updown_settlement.py
====================

Handles the full lifecycle for **updown-team** mukkadams:

  1. GET  /api/mukkadam/<id>/updown-allocations/
         → Lists all active (non-completed) allocations for this updown mukkadam.

  2. POST /api/mukkadam/<id>/updown-allocations/<allocation_id>/complete/
         → Marks allocation complete, creates MukkadamJobSettlement,
           fires webhook with full bill including transport cost.

TRANSPORT COST LOGIC
──────────────────────────────────────────────────────────────────────────────
An updown mukkadam can have multiple assignments in the same cluster over time:

  Assignment A: joined_at = 1 Mar,  transport_price = ₹8,000
  Assignment B: joined_at = 8 Mar,  transport_price = ₹2,000

For a given allocation on date D, we pick the assignment whose joined_at.date()
is the LATEST one that is still <= D. That assignment's transport_price is used.

  allocation on 5 Mar  → Assignment A  → ₹8,000
  allocation on 12 Mar → Assignment B  → ₹2,000

BILL FORMULA (updown team)
──────────────────────────────────────────────────────────────────────────────
  gross_amount        = effective_area × mukkadam_rate
  transport_deducted  = transport_price from matching assignment (0 if none)
  net_payable         = gross_amount + transport_deducted
  deposit_percent     = 0   (no deposit hold)
  advance_deducted    = 0   (no advance)
  weekly_deducted     = 0   (no weekly payments)

PERMANENT TEAM — NOT affected by this file. Their settlement flow is unchanged.

──────────────────────────────────────────────────────────────────────────────
REQUIRES: migration 0001_add_transport_deducted.py to add transport_deducted
          field to MukkadamJobSettlement model.

ADD TO settings.py:
  UPDOWN_WEBHOOK_URL = "https://your-webhook-endpoint.com/updown-bill"

ADD TO urls.py:
  from .updown_settlement import updown_allocation_list, updown_complete_allocation
  path('api/mukkadam/<int:mukkadam_id>/updown-allocations/',
       updown_allocation_list, name='updown-allocation-list'),
  path('api/mukkadam/<int:mukkadam_id>/updown-allocations/<int:allocation_id>/complete/',
       updown_complete_allocation, name='updown-complete-allocation'),
"""

import logging
import requests
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Mukkadam,
    Allocation,
    ClusterMukkadamAssignment,
    MukkadamJobSettlement,
)

logger = logging.getLogger(__name__)

UPDOWN_TYPE = 'updown'


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: get active updown assignment
# ─────────────────────────────────────────────────────────────────────────────

def _get_updown_assignment(mukkadam):
    """Return the first active updown assignment for this mukkadam, or None."""
    return (
        ClusterMukkadamAssignment.objects
        .filter(mukkadam=mukkadam, is_active=True, mukkadam_type=UPDOWN_TYPE)
        .select_related('cluster')
        .first()
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: resolve transport cost for a given allocation date
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_transport_cost(mukkadam, cluster_id, allocation_date):
    """
    Find the correct transport_price for this mukkadam on allocation_date.

    Logic:
      - Fetch ALL assignments for (mukkadam, cluster) ordered by joined_at ASC
      - Walk through them; the LAST assignment whose joined_at.date() <= allocation_date
        is the one in effect on that date.
      - If no assignment qualifies, return Decimal('0').

    Example:
      Assignment A: joined 2025-03-01, transport = 8000
      Assignment B: joined 2025-03-08, transport = 2000

      allocation_date = 2025-03-05  → A qualifies, B does not yet  → 8000
      allocation_date = 2025-03-08  → both qualify, B is latest    → 2000
      allocation_date = 2025-03-15  → both qualify, B is latest    → 2000
      allocation_date = 2025-02-28  → neither qualifies            → 0
    """
    assignments = (
        ClusterMukkadamAssignment.objects
        .filter(
            mukkadam=mukkadam,
            cluster_id=cluster_id,
            mukkadam_type=UPDOWN_TYPE,
        )
        .order_by('joined_at')  # oldest first → last match wins
    )

    applicable_transport = Decimal('0')
    for asgn in assignments:
        asgn_date = asgn.joined_at.date() if asgn.joined_at else None
        if asgn_date is None:
            continue
        if asgn_date <= allocation_date:
            # Keep overwriting — last assignment that qualifies wins
            applicable_transport = Decimal(str(asgn.transport_price or 0))

    return applicable_transport


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: effective area for updown billing
# ─────────────────────────────────────────────────────────────────────────────

def _effective_area(allocation):
    """
    Use actual_area_done if set (admin may pass it at complete time),
    otherwise fall back to allocated_area.
    """
    if allocation.actual_area_done is not None:
        return Decimal(str(allocation.actual_area_done))
    return Decimal(str(allocation.allocated_area or 0))


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: build webhook / API response payload
# ─────────────────────────────────────────────────────────────────────────────

def _build_bill_payload(mukkadam, allocation, settlement, assignment):
    """Full bill payload for webhook and API response."""
    ja     = allocation.job_activity
    job    = ja.job
    plot   = ja.plot
    farmer = job.farmer

    eff_area  = _effective_area(allocation)
    rate      = Decimal(str(allocation.mukkadam_rate or 0))
    gross     = (eff_area * rate).quantize(Decimal('0.01'))
    transport = Decimal(str(settlement.transport_deducted or 0))

    return {
        # ── Mukkadam ──────────────────────────────────────────────────
        'mukkadam_id':   str(mukkadam.pk),
        'mukkadam_name': mukkadam.mukkadam_name,
        'mobile':        mukkadam.mobile_numbers,
        'mukkadam_type': UPDOWN_TYPE,

        # ── Assignment / cluster ──────────────────────────────────────
        'assignment_id': assignment.id,
        'cluster_id':    assignment.cluster_id,
        'cluster_name':  assignment.cluster.name if assignment.cluster else '—',

        # ── Job / farmer ──────────────────────────────────────────────
        'job_id':      str(job.job_id),
        'farmer_id':   str(farmer.farmer_id) if farmer else None,
        'farmer_name': farmer.farmer_name    if farmer else '—',

        # ── Activity / plot ───────────────────────────────────────────
        'allocation_id':  allocation.id,
        'activity_name':  ja.activity.name if ja.activity else '—',
        'plot_code':      plot.plot_code   if plot else '—',
        'plot_name':      plot.name        if plot else '—',
        'allocated_date': str(allocation.allocated_date) if allocation.allocated_date else None,
        'completed_at':   str(timezone.now()),

        # ── Work detail ───────────────────────────────────────────────
        'allocated_area':   float(allocation.allocated_area or 0),
        'actual_area_done': float(allocation.actual_area_done) if allocation.actual_area_done is not None else None,
        'effective_area':   float(eff_area),
        'mukkadam_rate':    float(rate),

        # ── Bill breakdown ────────────────────────────────────────────
        'bill': {
            'gross_amount':     float(gross),
            'transport_cost':   float(transport),
            'deposit_held':     0.0,   # updown → no deposit
            'advance_deducted': 0.0,   # updown → no advance
            'weekly_deducted':  0.0,   # updown → no weekly
            'net_payable':      float(settlement.net_payable),
        },

        # ── Settlement ────────────────────────────────────────────────
        'settlement_id':     settlement.id,
        'settlement_status': settlement.status,
        'net_payable':       float(settlement.net_payable),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: fire webhook
# ─────────────────────────────────────────────────────────────────────────────

def _fire_webhook(payload):
    """POST payload to UPDOWN_WEBHOOK_URL. Logs errors, never raises."""
    url = getattr(settings, 'UPDOWN_WEBHOOK_URL', None)
    if not url:
        logger.info('[updown webhook] UPDOWN_WEBHOOK_URL not set — skipping.')
        return
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f'[updown webhook] OK → {url} | status={resp.status_code}')
    except Exception as exc:
        logger.error(f'[updown webhook] FAILED → {url} | {exc}', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# CORE: create / update updown settlement
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_updown_settlement(mukkadam, allocation, assignment):
    """
    Creates (or idempotently updates) a MukkadamJobSettlement for
    a single updown allocation completion.

    Formula:
        gross            = effective_area × mukkadam_rate
        transport        = transport_price from matching assignment date range
        net_payable      = gross + transport
        everything else  = 0  (no deposit / advance / weekly for updown team)
    """
    ja   = allocation.job_activity
    job  = ja.job
    plot = ja.plot

    eff_area  = _effective_area(allocation)
    rate      = Decimal(str(allocation.mukkadam_rate or 0))
    gross     = (eff_area * rate).quantize(Decimal('0.01'))

    # Resolve transport cost based on allocation date vs assignment history
    cluster_id = assignment.cluster_id
    alloc_date = allocation.allocated_date
    transport  = (
        _resolve_transport_cost(mukkadam, cluster_id, alloc_date)
        if alloc_date else Decimal('0')
    )

    net    = (gross + transport).quantize(Decimal('0.01'))
    status = 'calculated' if net > Decimal('0') else 'no_payment_needed'

    settlement, created = MukkadamJobSettlement.objects.get_or_create(
    mukkadam=mukkadam,
    job=job,
    plot=plot,
    defaults={
        'gross_amount':           gross,
        'transport_deducted':     transport,
        'deposit_percent':        Decimal('0'),
        'payable_amount':         gross + transport,
        'advance_deducted':       Decimal('0'),
        'weekly_payments_deducted': Decimal('0'),
        'net_payable':            gross + transport,
        'status':                 'calculated',
    }
)

    if not created:
        # Idempotent recalc in case actual_area_done was updated at complete time
        settlement.gross_amount       = gross
        settlement.payable_amount     = gross
        settlement.transport_deducted = transport
        settlement.net_payable        = net
        settlement.status             = status
        settlement.calculated_at      = timezone.now()
        settlement.save(update_fields=[
            'gross_amount', 'payable_amount', 'transport_deducted',
            'net_payable', 'status', 'calculated_at',
        ])

    return settlement


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1 — list non-completed updown allocations (work detail screen)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def updown_allocation_list(request, mukkadam_id):
    """
    GET /api/mukkadam/<id>/updown-allocations/

    Returns all non-completed allocations for this updown mukkadam.
    Each row shows an estimated bill preview (gross + transport).
    """
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    assignment = _get_updown_assignment(mukkadam)
    if not assignment:
        return Response({'error': 'No active updown assignment found'}, status=404)

    allocations = (
        Allocation.objects
        .filter(mukkadam=mukkadam)
        .exclude(work_status='completed')
        .select_related(
            'job_activity__activity',
            'job_activity__plot',
            'job_activity__job',
            'job_activity__job__farmer',
            'cluster',
        )
        .order_by('allocated_date')
    )

    rows = []
    for a in allocations:
        ja     = a.job_activity
        job    = ja.job
        plot   = ja.plot
        farmer = job.farmer if job else None

        eff_area  = _effective_area(a)
        rate      = Decimal(str(a.mukkadam_rate or 0))
        gross_est = (eff_area * rate).quantize(Decimal('0.01'))

        # Preview: what transport would apply if completed today
        transport_est = (
            _resolve_transport_cost(mukkadam, a.cluster_id, a.allocated_date)
            if a.allocated_date and a.cluster_id else Decimal('0')
        )

        rows.append({
            'allocation_id':   a.id,
            'allocated_date':  str(a.allocated_date) if a.allocated_date else None,

            'job_id':          str(job.job_id) if job else None,
            'farmer_name':     farmer.farmer_name if farmer else '—',
            'farmer_id':       str(farmer.farmer_id) if farmer else None,

            'activity_name':   ja.activity.name if ja.activity else '—',
            'plot_code':       plot.plot_code   if plot else '—',
            'plot_name':       plot.name        if plot else '—',

            'allocated_area':   float(a.allocated_area or 0),
            'actual_area_done': float(a.actual_area_done) if a.actual_area_done is not None else None,
            'effective_area':   float(eff_area),
            'mukkadam_rate':    float(rate),

            # Bill preview shown on work detail screen
            'estimated_bill': {
                'gross_amount':   float(gross_est),
                'transport_cost': float(transport_est),
                'net_payable':    float(gross_est + transport_est),
            },

            'work_status':       a.work_status or 'work_not_started',
            'report_submitted':  a.report_submitted,
            'allocated_workers': a.allocated_workers or 0,
            'actual_crew_size':  a.actual_crew_size,

            'cluster_id':   a.cluster_id,
            'cluster_name': a.cluster.name if a.cluster else '—',
            'can_complete': a.work_status != 'completed',
        })

    return Response({
        'mukkadam_id':   mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'mukkadam_type': UPDOWN_TYPE,
        'assignment_id': assignment.id,
        'cluster_name':  assignment.cluster.name if assignment.cluster else '—',
        'total':         len(rows),
        'allocations':   rows,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 2 — mark complete → create bill → fire webhook
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def updown_complete_allocation(request, mukkadam_id, allocation_id):
    """
    POST /api/mukkadam/<id>/updown-allocations/<allocation_id>/complete/

    Optional body:
    {
        "actual_area_done": 2.5,    // overrides allocated_area for billing
        "actual_crew_size": 8
    }

    Steps:
      1. Validate mukkadam is updown type
      2. Mark allocation work_status = 'completed'
      3. Resolve transport cost from assignment date ranges
      4. Create MukkadamJobSettlement:
             gross         = effective_area × mukkadam_rate
             transport     = resolved transport_price
             net_payable   = gross + transport
      5. Fire webhook
      6. Return full bill
    """
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    assignment = _get_updown_assignment(mukkadam)
    if not assignment:
        return Response({'error': 'No active updown assignment for this mukkadam'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'job_activity__activity',
            'job_activity__plot',
            'job_activity__job',
            'job_activity__job__farmer',
            'cluster',
        ).get(pk=allocation_id, mukkadam=mukkadam)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    # ── Already completed — idempotent response ───────────────────────────────
    if allocation.work_status == 'completed':
        existing = MukkadamJobSettlement.objects.filter(
            mukkadam=mukkadam,
            job=allocation.job_activity.job,
            plot=allocation.job_activity.plot,
        ).first()
        if existing:
            payload = _build_bill_payload(mukkadam, allocation, existing, assignment)
            return Response({'already_completed': True, 'bill': payload})

    # ── Parse optional body ───────────────────────────────────────────────────
    actual_area = request.data.get('actual_area_done')
    actual_crew = request.data.get('actual_crew_size')

    with transaction.atomic():
        # 1. Update allocation
        update_fields = ['work_status']
        allocation.work_status = 'completed'

        if actual_area is not None:
            allocation.actual_area_done = Decimal(str(actual_area))
            update_fields.append('actual_area_done')
        if actual_crew is not None:
            allocation.actual_crew_size = int(actual_crew)
            update_fields.append('actual_crew_size')

        allocation.save(update_fields=update_fields)

        # 2. Create / update settlement with transport resolved inside
        settlement = create_updown_settlement(mukkadam, allocation, assignment)

    # 3. Fire webhook outside transaction — failure must not roll back the bill
    payload = _build_bill_payload(mukkadam, allocation, settlement, assignment)
    _fire_webhook(payload)

    return Response({
        'success': True,
        'message': (
            f'Allocation complete. '
            f'Gross ₹{settlement.gross_amount} + '
            f'Transport ₹{settlement.transport_deducted} = '
            f'Net ₹{settlement.net_payable}'
        ),
        'bill': payload,
    }, status=201)