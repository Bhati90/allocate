"""
tender/views/sheet_sync_payment_views.py
=========================================
Django REST endpoints consumed by MukkadamPayments.gs

Add to your urls.py:
    path('api/sheet-sync/updown-bill/', sheet_sync_updown_bill, name='sheet_sync_updown_bill'),
    path('api/sheet-sync/updown-bill/list/', sheet_sync_updown_bill_list, name='sheet_sync_updown_bill_list'),
    path('api/sheet-sync/permanent-settlement/', sheet_sync_permanent_settlement, name='sheet_sync_permanent_settlement'),
    path('api/sheet-sync/permanent-settlement/list/', sheet_sync_permanent_settlement_list, name='sheet_sync_permanent_settlement_list'),
"""

import logging
from decimal import Decimal
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json

from .models import (
    MukkadamUpdownBill,
    MukkadamPermanentSettlement,
    SheetSyncLog,
    Allocation,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# UPDOWN BILL – receive edit from sheet
# POST /tender/api/sheet-sync/updown-bill/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sheet_sync_updown_bill(request):
    data = request.data
    bill_id = data.get('bill_id')
    if not bill_id:
        return JsonResponse({'success': False, 'error': 'bill_id required'}, status=400)

    try:
        bill = MukkadamUpdownBill.objects.select_related('mukkadam', 'cluster', 'allocation').get(id=bill_id)
    except MukkadamUpdownBill.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Bill {bill_id} not found'}, status=404)

    action = 'update'
    paid_at_str = None

    try:
        # Always update costs + remarks
        bill.transport_cost = Decimal(str(data.get('transport_cost', 0)))
        bill.other_cost     = Decimal(str(data.get('other_cost', 0)))
        bill.other_cost_remark = data.get('other_cost_remark', '') or ''
        bill.compute_final_amount()

        new_status = str(data.get('status', '')).lower().strip()

        if new_status == 'paid' and bill.status != 'paid':
            # Mark paid
            action = 'mark_paid'
            bill.mark_paid(
                paid_by_user=request.user,
                mode=data.get('payment_mode', 'CASH') or 'CASH',
                reference=data.get('payment_reference', '') or '',
                remark=data.get('remark', '') or '',
            )
            paid_at_str = bill.paid_at.strftime('%Y-%m-%d %H:%M') if bill.paid_at else None
        else:
            # Just update metadata
            bill.payment_mode      = data.get('payment_mode', '') or ''
            bill.payment_reference = data.get('payment_reference', '') or ''
            bill.remark            = data.get('remark', '') or ''
            bill.last_synced_at    = timezone.now()
            bill.save()

        SheetSyncLog.objects.create(
            sheet_name='updown_payments',
            sheet_row_id=f'updown_{bill_id}',
            action=action,
            updown_bill_id=bill.id,
            payload=data,
            success=True,
        )

        return JsonResponse({
            'success'     : True,
            'bill_id'     : bill.id,
            'final_amount': float(bill.final_amount),
            'status'      : bill.status,
            'paid_at'     : paid_at_str,
        })

    except Exception as e:
        logger.exception(f'sheet_sync_updown_bill error for bill {bill_id}')
        SheetSyncLog.objects.create(
            sheet_name='updown_payments',
            sheet_row_id=f'updown_{bill_id}',
            action='error',
            updown_bill_id=bill_id,
            payload=data,
            success=False,
            error_message=str(e),
        )
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# UPDOWN BILL LIST – push to sheet
# GET /tender/api/sheet-sync/updown-bill/list/
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sheet_sync_updown_bill_list(request):
    """Return all updown bills for the sheet to display."""
    cluster_id = request.query_params.get('cluster_id')
    qs = MukkadamUpdownBill.objects.select_related('mukkadam', 'cluster', 'allocation')
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    bills = []
    for b in qs.order_by('-work_date'):
        bills.append({
            'id'               : b.id,
            'allocation_id'    : b.allocation_id,
            'mukkadam_name'    : b.mukkadam.mukkadam_name,
            'cluster_name'     : b.cluster.name if b.cluster else '',
            'work_date'        : str(b.work_date),
            'allocated_area'   : float(b.allocated_area),
            'mukkadam_rate'    : float(b.mukkadam_rate),
            'base_amount'      : float(b.base_amount),
            'transport_cost'   : float(b.transport_cost),
            'other_cost'       : float(b.other_cost),
            'other_cost_remark': b.other_cost_remark,
            'final_amount'     : float(b.final_amount),
            'status'           : b.status,
            'payment_mode'     : b.payment_mode,
            'payment_reference': b.payment_reference,
            'remark'           : b.remark,
            'paid_at'          : b.paid_at.strftime('%Y-%m-%d %H:%M') if b.paid_at else '',
        })

    return JsonResponse(bills, safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# PERMANENT SETTLEMENT – receive edit from sheet
# POST /tender/api/sheet-sync/permanent-settlement/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sheet_sync_permanent_settlement(request):
    data = request.data
    settlement_id = data.get('settlement_id')
    if not settlement_id:
        return JsonResponse({'success': False, 'error': 'settlement_id required'}, status=400)

    try:
        settlement = MukkadamPermanentSettlement.objects.select_related(
            'mukkadam', 'cluster'
        ).get(id=settlement_id)
    except MukkadamPermanentSettlement.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Settlement {settlement_id} not found'}, status=404)

    action = 'update'
    paid_at_str = None

    try:
        new_status = str(data.get('status', '')).lower().strip()

        if new_status == 'paid' and settlement.status != 'paid':
            action = 'mark_paid'
            settlement.mark_paid(
                paid_by_user=request.user,
                mode=data.get('payment_mode', 'CASH') or 'CASH',
                reference=data.get('payment_reference', '') or '',
                remark_extra=data.get('remark', '') or '',
            )
            paid_at_str = settlement.paid_at.strftime('%Y-%m-%d %H:%M') if settlement.paid_at else None

        elif new_status == 'payment_raised' and settlement.status == 'calculated':
            settlement.status = 'payment_raised'
            settlement.payment_mode      = data.get('payment_mode', '') or ''
            settlement.payment_reference = data.get('payment_reference', '') or ''
            if data.get('remark'):
                settlement.remark += '\n' + data['remark']
            settlement.last_synced_at = timezone.now()
            settlement.save()
        else:
            # metadata update only
            settlement.payment_mode      = data.get('payment_mode', '') or ''
            settlement.payment_reference = data.get('payment_reference', '') or ''
            if data.get('remark'):
                settlement.remark += '\n' + data['remark']
            settlement.last_synced_at = timezone.now()
            settlement.save()

        SheetSyncLog.objects.create(
            sheet_name='permanent_settlements',
            sheet_row_id=f'perm_{settlement_id}',
            action=action,
            permanent_settlement_id=settlement.id,
            payload=data,
            success=True,
        )

        return JsonResponse({
            'success'      : True,
            'settlement_id': settlement.id,
            'status'       : settlement.status,
            'paid_at'      : paid_at_str,
            'net_payable'  : float(settlement.net_payable),
            'remark'       : settlement.remark,
        })

    except Exception as e:
        logger.exception(f'sheet_sync_permanent_settlement error for {settlement_id}')
        SheetSyncLog.objects.create(
            sheet_name='permanent_settlements',
            sheet_row_id=f'perm_{settlement_id}',
            action='error',
            permanent_settlement_id=settlement_id,
            payload=data,
            success=False,
            error_message=str(e),
        )
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# PERMANENT SETTLEMENT LIST – push to sheet
# GET /tender/api/sheet-sync/permanent-settlement/list/
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sheet_sync_permanent_settlement_list(request):
    cluster_id = request.query_params.get('cluster_id')
    qs = MukkadamPermanentSettlement.objects.select_related('mukkadam', 'cluster')
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    result = []
    for s in qs.order_by('-period_end'):
        result.append({
            'id'                          : s.id,
            'mukkadam_name'               : s.mukkadam.mukkadam_name,
            'cluster_name'                : s.cluster.name if s.cluster else '',
            'period_start'                : str(s.period_start),
            'period_end'                  : str(s.period_end),
            'work_earned'                 : float(s.work_earned),
            'advance_applied'             : float(s.advance_applied),
            'weekly_payments_sum'         : float(s.weekly_payments_sum),
            'misc_costs_sum'              : float(s.misc_costs_sum),
            'carry_forward_credit'        : float(s.carry_forward_credit),
            'total_paid_before_settlement': float(s.total_paid_before_settlement),
            'running_balance'             : float(s.running_balance),
            'net_payable'                 : float(s.net_payable),
            'no_payment_needed'           : s.no_payment_needed,
            'status'                      : s.status,
            'payment_mode'                : s.payment_mode,
            'payment_reference'           : s.payment_reference,
            'remark'                      : s.remark,
            'paid_at'                     : s.paid_at.strftime('%Y-%m-%d %H:%M') if s.paid_at else '',
        })

    return JsonResponse(result, safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY: Create updown bill when allocation is marked 'completed'
# Call this from your existing allocation update view / signal
# ─────────────────────────────────────────────────────────────────────────────

def auto_create_updown_bill_if_needed(allocation):
    """
    Call after setting allocation.payment_status = 'done' (work completed)
    for an updown mukkadam. Creates the bill if it doesn't exist yet.
    """
    from ..models import ClusterMukkadamAssignment

    # Check it's an updown assignment
    is_updown = ClusterMukkadamAssignment.objects.filter(
        mukkadam=allocation.mukkadam,
        cluster=allocation.cluster,
        mukkadam_type='updown',
    ).exists()

    if not is_updown:
        return None

    # Avoid duplicates
    if hasattr(allocation, 'updown_bill'):
        return allocation.updown_bill

    bill = MukkadamUpdownBill.create_from_allocation(allocation)
    logger.info(f'Created updown bill {bill.id} for allocation {allocation.id}')
    return bill
"""
mukkadam_sheet_views.py
=======================
Sheet sync views — NO DRF token auth.
Uses a simple X-Sheet-Secret header instead.

URLs to register in urls.py:
    path('tender/api/sheet/mukkadam-roster/',       views.sheet_mukkadam_roster,          name='sheet_mukkadam_roster'),
    path('tender/api/sheet/weekly-payments/',       views.sheet_weekly_payments_list,     name='sheet_weekly_payments_list'),
    path('tender/api/sheet/weekly-payment/update/', views.sheet_weekly_payment_update,    name='sheet_weekly_payment_update'),
"""

import json
import logging
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from tender.models import (
    ClusterMukkadamAssignment,
    MukkadamWeeklyPayment,
    MukkadamPaymentRecord,
)

logger = logging.getLogger(__name__)

# Must match SHEET_SECRET in MukkadamSheet.gs
SHEET_SYNC_SECRET = 'django-insecure-l6c$=vdsv7n-ng7cd_^6fvi7lig^+_a2!dzg5oy1^a6qklw$9t'


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _auth(request):
    """Return True if the request carries the correct sheet secret."""
    return request.headers.get('X-Sheet-Secret', '') == SHEET_SYNC_SECRET


def _parse_body(request):
    """Safely parse JSON body; return (data_dict, error_response_or_None)."""
    try:
        return json.loads(request.body or '{}'), None
    except json.JSONDecodeError as exc:
        return {}, JsonResponse({'success': False, 'error': f'Invalid JSON: {exc}'}, status=400)


def _to_decimal(value, default=Decimal('0')):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — MUKKADAM ROSTER  (read-only in sheet)
# GET /tender/api/sheet/mukkadam-roster/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['GET'])
def sheet_mukkadam_roster(request):
    """
    Returns every active ClusterMukkadamAssignment (permanent + updown).
    Optional query param: ?cluster_id=<id>
    """
    if not _auth(request):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    cluster_id = request.GET.get('cluster_id')
    qs = (
        ClusterMukkadamAssignment.objects
        .select_related('mukkadam', 'cluster')
        .filter(is_active=True)
        .order_by('cluster__name', 'mukkadam_type', 'mukkadam__mukkadam_name')
    )
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    rows = []
    for a in qs:
        m = a.mukkadam
        c = a.cluster

        if a.mukkadam_type == 'updown':
            if a.updown_mode == 'range' and a.updown_from_date and a.updown_to_date:
                date_range = f"{a.updown_from_date} → {a.updown_to_date}"
            elif a.updown_mode == 'specific' and a.updown_specific_dates:
                date_range = ', '.join(str(d) for d in (a.updown_specific_dates or []))
            else:
                date_range = ''
        else:
            date_range = ''

        rows.append({
            'assignment_id'        : a.id,
            'mukkadam_id'          : m.mukkadam_id,
            'mukkadam_name'        : m.mukkadam_name,
            'mobile'               : m.mobile_numbers or '',
            'cluster_name'         : c.name if c else '',
            'mukkadam_type'        : a.mukkadam_type,
            'updown_mode'          : a.updown_mode or '',
            'date_range'           : date_range,
            'joined_date'          : str(a.joined_date) if a.joined_date else '',
            'weekly_amount'        : float(a.weekly_amount or 0),
            'transport_price'      : float(a.transport_price or 0),
            'advance_amount'       : float(a.advance_amount or 0),
            'crew_size'            : m.crew_size,
            'max_crew_capacity'    : m.max_crew_capacity,
            'weekly_payment_day'   : (
                a.get_weekly_payment_day_display()
                if a.mukkadam_type == 'permanent' and a.weekly_payment_day is not None
                else ''
            ),
            'total_weekly_payments': float(a.total_weekly_payments or 0),
            'is_active'            : a.is_active,
        })

    return JsonResponse(rows, safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — WEEKLY PAYMENTS LIST  (read — filled by pullFromDjango)
# GET /tender/api/sheet/weekly-payments/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['GET'])
def sheet_weekly_payments_list(request):
    """
    Returns all weekly payments for permanent mukkadams.
    Optional query param: ?cluster_id=<id>
    """
    if not _auth(request):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    cluster_id = request.GET.get('cluster_id')
    qs = (
        MukkadamWeeklyPayment.objects
        .select_related('assignment__mukkadam', 'assignment__cluster')
        .filter(assignment__mukkadam_type='permanent')
        .order_by('-payment_date')
    )
    if cluster_id:
        qs = qs.filter(assignment__cluster_id=cluster_id)

    rows = []
    for w in qs:
        a = w.assignment
        rows.append({
            'weekly_id'            : w.id,
            'assignment_id'        : a.id if a else '',
            'mukkadam_name'        : a.mukkadam.mukkadam_name if a else '',
            'cluster_name'         : a.cluster.name if a and a.cluster else '',
            'payment_date'         : str(w.payment_date),
            'crew_size'            : w.crew_size_on_date,
            'weekly_agreed_amount' : float(a.weekly_amount or 0) if a else 0,
            'amount_paid'          : float(w.amount),
            'mode'                 : w.mode or '',
            'payment_reference'    : w.payment_reference or '',
            'notes'                : w.notes or '',
            'is_auto_generated'    : w.is_auto_generated,
        })

    return JsonResponse(rows, safe=False)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — WEEKLY PAYMENT UPDATE  (write — called by onEdit)
# POST /tender/api/sheet/weekly-payment/update/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def sheet_weekly_payment_update(request):
    """
    Called from Google Sheet onEdit when a Weekly Payment row is filled/edited.

    Case A – weekly_id present  → UPDATE existing MukkadamWeeklyPayment
    Case B – weekly_id absent   → CREATE new MukkadamWeeklyPayment

    Required for CREATE: assignment_id, payment_date, amount_paid
    Required for UPDATE: weekly_id + any editable field
    """
    if not _auth(request):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    data, err = _parse_body(request)
    if err:
        return err

    # ── Test ping from testConnection() ──────────────────────────────────────
    if data.get('test'):
        return JsonResponse({'success': True, 'message': 'Connection OK'})

    weekly_id = data.get('weekly_id')

    try:
        if weekly_id:
            # ── UPDATE ───────────────────────────────────────────────────────
            try:
                wp = MukkadamWeeklyPayment.objects.select_related(
                    'assignment__mukkadam', 'assignment__cluster'
                ).get(id=weekly_id)
            except MukkadamWeeklyPayment.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': f'Weekly payment {weekly_id} not found'},
                    status=404,
                )

            if 'amount_paid' in data and data['amount_paid'] not in ('', None):
                wp.amount = _to_decimal(data['amount_paid'])
            if data.get('mode'):
                wp.mode = str(data['mode']).strip().upper()
            if 'payment_reference' in data:
                wp.payment_reference = data['payment_reference'] or ''
            if 'notes' in data:
                wp.notes = data['notes'] or ''
            if data.get('crew_size') not in ('', None):
                wp.crew_size_on_date = int(data['crew_size'])

            wp.is_auto_generated = False
            wp.save()

            _refresh_assignment_weekly_total(wp.assignment)
            _upsert_payment_record(wp)

            return JsonResponse({
                'success'     : True,
                'action'      : 'updated',
                'weekly_id'   : wp.id,
                'amount_paid' : float(wp.amount),
                'mukkadam'    : wp.assignment.mukkadam.mukkadam_name if wp.assignment else '',
                'payment_date': str(wp.payment_date),
            })

        else:
            # ── CREATE ───────────────────────────────────────────────────────
            assignment_id = data.get('assignment_id')
            payment_date  = data.get('payment_date')
            amount_paid   = data.get('amount_paid')

            if not assignment_id:
                return JsonResponse(
                    {'success': False, 'error': 'assignment_id required to create a weekly payment'},
                    status=400,
                )
            if not payment_date:
                return JsonResponse(
                    {'success': False, 'error': 'payment_date required'},
                    status=400,
                )
            if amount_paid in ('', None):
                return JsonResponse(
                    {'success': False, 'error': 'amount_paid required'},
                    status=400,
                )

            try:
                assignment = ClusterMukkadamAssignment.objects.select_related(
                    'mukkadam', 'cluster'
                ).get(id=assignment_id)
            except ClusterMukkadamAssignment.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': f'Assignment {assignment_id} not found'},
                    status=404,
                )

            if assignment.mukkadam_type != 'permanent':
                return JsonResponse(
                    {'success': False, 'error': 'Weekly payments are only for permanent mukkadams'},
                    status=400,
                )

            wp = MukkadamWeeklyPayment.objects.create(
                assignment        = assignment,
                payment_date      = payment_date,
                crew_size_on_date = int(data.get('crew_size') or assignment.mukkadam.crew_size or 1),
                amount            = _to_decimal(amount_paid),
                mode              = str(data.get('mode') or 'CASH').strip().upper(),
                payment_reference = data.get('payment_reference') or '',
                notes             = data.get('notes') or '',
                is_auto_generated = False,
            )

            _refresh_assignment_weekly_total(assignment)
            _upsert_payment_record(wp)

            return JsonResponse({
                'success'     : True,
                'action'      : 'created',
                'weekly_id'   : wp.id,
                'amount_paid' : float(wp.amount),
                'mukkadam'    : assignment.mukkadam.mukkadam_name,
                'cluster'     : assignment.cluster.name if assignment.cluster else '',
                'payment_date': str(wp.payment_date),
            }, status=201)

    except Exception as exc:
        logger.exception('sheet_weekly_payment_update error')
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _refresh_assignment_weekly_total(assignment):
    """Recompute assignment.total_weekly_payments from all its weekly rows."""
    if not assignment:
        return
    from django.db.models import Sum
    total = (
        MukkadamWeeklyPayment.objects
        .filter(assignment=assignment)
        .aggregate(t=Sum('amount'))['t'] or Decimal('0')
    )
    assignment.total_weekly_payments = total
    assignment.save(update_fields=['total_weekly_payments'])


def _upsert_payment_record(wp):
    """Keep the MukkadamPaymentRecord ledger in sync for every weekly payment."""
    if not wp.assignment:
        return
    MukkadamPaymentRecord.objects.update_or_create(
        weekly_payment=wp,
        defaults=dict(
            mukkadam          = wp.assignment.mukkadam,
            cluster           = wp.assignment.cluster,
            payment_type      = 'weekly',
            amount            = wp.amount,
            payment_date      = wp.payment_date,
            payment_mode      = wp.mode,
            payment_reference = wp.payment_reference or '',
            remark            = wp.notes or '',
        ),
    )