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

def _get_updown_assignment(mukkadam, cluster_id=None):
    """
    Return the updown assignment for this mukkadam.
    If cluster_id given, return that cluster's assignment.
    Otherwise return the first active updown assignment.
    """
    qs = (
        ClusterMukkadamAssignment.objects
        .filter(mukkadam=mukkadam, is_active=True, mukkadam_type=UPDOWN_TYPE)
        .select_related('cluster')
    )
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    return qs.first()
# ─────────────────────────────────────────────────────────────────────────────
# HELPER: resolve transport cost for a given allocation date
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_transport_cost(mukkadam, cluster_id, alloc_date):
    """
    Find the transport_price for this mukkadam+cluster on the given date.
    Picks the assignment where joined_at.date() <= alloc_date (latest wins).
    """
    assignments = (
        ClusterMukkadamAssignment.objects
        .filter(
            mukkadam=mukkadam,
            cluster_id=cluster_id,
            mukkadam_type=UPDOWN_TYPE,
            is_active=True,
        )
        .order_by('joined_at')
    )

    transport = Decimal('0')
    for asgn in assignments:
        if asgn.joined_at and asgn.joined_at.date() <= alloc_date:
            transport = Decimal(str(asgn.transport_price or 0))

    return transport
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
    ja     = allocation.job_activity
    job    = ja.job
    plot   = ja.plot
    farmer = job.farmer

    # Use settlement values (cumulative) not per-allocation recalc
    gross     = Decimal(str(settlement.gross_amount))
    transport = Decimal(str(settlement.transport_deducted or 0))

    return {
        'mukkadam_id':   str(mukkadam.pk),
        'mukkadam_name': mukkadam.mukkadam_name,
        'mobile':        mukkadam.mobile_numbers,
        'mukkadam_type': UPDOWN_TYPE,
        'assignment_id': assignment.id,
        'cluster_id':    assignment.cluster_id,
        'cluster_name':  assignment.cluster.name if assignment.cluster else '—',
        'job_id':        str(job.job_id),
        'farmer_id':     str(farmer.farmer_id) if farmer else None,
        'farmer_name':   farmer.farmer_name    if farmer else '—',
        'allocation_id':  allocation.id,
        'activity_name':  ja.activity.name if ja.activity else '—',
        'plot_code':      plot.plot_code   if plot else '—',
        'plot_name':      plot.name        if plot else '—',
        'allocated_date': str(allocation.allocated_date) if allocation.allocated_date else None,
        'completed_at':   str(timezone.now()),
        'allocated_area':   float(allocation.allocated_area or 0),
        'actual_area_done': float(allocation.actual_area_done) if allocation.actual_area_done is not None else None,
        'effective_area':   float(_effective_area(allocation)),
        'mukkadam_rate':    float(allocation.mukkadam_rate or 0),
        'bill': {
            'gross_amount':     float(gross),       # cumulative across all completed allocs
            'transport_cost':   float(transport),   # charged once per job
            'deposit_held':     0.0,
            'advance_deducted': 0.0,
            'weekly_deducted':  0.0,
            'net_payable':      float(settlement.net_payable),
        },
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
    ja   = allocation.job_activity
    job  = ja.job
    plot = ja.plot

    # Gross for THIS allocation only
    area  = Decimal(str(allocation.actual_area_done or allocation.allocated_area or 0))
    rate  = Decimal(str(allocation.mukkadam_rate or 0))
    gross = (area * rate).quantize(Decimal('0.01'))

    # Transport for THIS allocation's cluster + date only
    transport = Decimal('0')
    if allocation.allocated_date:
        transport = _resolve_transport_cost(
            mukkadam, allocation.cluster_id, allocation.allocated_date
        )

    net    = (gross + transport).quantize(Decimal('0.01'))
    status = 'calculated' if net > Decimal('0') else 'no_payment_needed'

    # One settlement per allocation — use allocation as the unique key
    try:
        settlement = MukkadamJobSettlement.objects.get(
            allocation=allocation
        )
        # Update if not paid
        if settlement.status not in ('paid',):
            settlement.gross_amount       = gross
            settlement.transport_deducted = transport
            settlement.payable_amount     = net
            settlement.net_payable        = net
            settlement.calculated_at      = timezone.now()
            settlement.status             = status
            settlement.save(update_fields=[
                'gross_amount', 'transport_deducted', 'payable_amount',
                'net_payable', 'calculated_at', 'status',
            ])
        return settlement

    except MukkadamJobSettlement.DoesNotExist:
        return MukkadamJobSettlement.objects.create(
            mukkadam              = mukkadam,
            job                   = job,
            plot                  = plot,
            allocation            = allocation,   # ← unique per allocation
            gross_amount          = gross,
            transport_deducted    = transport,
            deposit_percent       = Decimal('0'),
            payable_amount        = net,
            advance_deducted      = Decimal('0'),
            weekly_payments_deducted = Decimal('0'),
            net_payable           = net,
            status                = status,
            calculated_at         = timezone.now(),
        )

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
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

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

    # ── Get assignment for THIS allocation's cluster ──────────────────
    assignment = _get_updown_assignment(mukkadam, cluster_id=allocation.cluster_id)
    if not assignment:
        return Response(
            {'error': f'No active updown assignment for cluster {allocation.cluster_id}'},
            status=400
        )

    # ── Idempotent — already completed ───────────────────────────────
    if allocation.work_status == 'completed':
        existing = MukkadamJobSettlement.objects.filter(
    allocation=allocation
).first()
        if existing:
            payload = _build_bill_payload(mukkadam, allocation, existing, assignment)
            return Response({'already_completed': True, 'bill': payload})

    actual_area = request.data.get('actual_area_done')
    actual_crew = request.data.get('actual_crew_size')

    with transaction.atomic():
        update_fields = ['work_status']
        allocation.work_status = 'completed'

        if actual_area is not None:
            allocation.actual_area_done = Decimal(str(actual_area))
            update_fields.append('actual_area_done')
        if actual_crew is not None:
            allocation.actual_crew_size = int(actual_crew)
            update_fields.append('actual_crew_size')

        allocation.save(update_fields=update_fields)

        # settlement now accumulates all completed allocs for this job+plot
        settlement = create_updown_settlement(mukkadam, allocation, assignment)

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