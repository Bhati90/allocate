from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import date

from .models import (
    Mukkadam, Allocation, MukkadamJobSettlement,
    MukkadamWeeklyPayment, MukkadamMiscCost, MukkadamPayment,
    ClusterMukkadamAssignment, Job
)


@api_view(['GET'])
def mukkadam_workbook(request):
    """
    GET /api/mukkadam/workbook/?mobile=9876543210
    Returns full work profile of a mukkadam — past, current, future jobs,
    farm details with lat/lng, earnings, settlements, payments.
    """
    mobile = request.query_params.get('mobile', '').strip()
    if not mobile:
        return Response(
            {'error': 'mobile query param is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find mukkadam by mobile (mobile_numbers is a CharField, may have multiple)
    mukkadam = Mukkadam.objects.filter(
        mobile_numbers__icontains=mobile
    ).first()

    if not mukkadam:
        return Response(
            {'error': f'No mukkadam found with mobile: {mobile}'},
            status=status.HTTP_404_NOT_FOUND
        )

    today = date.today()

    # ── 1. Mukkadam basic info ──────────────────────────────
    mukkadam_data = {
        'mukkadam_id': mukkadam.mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'mobile_numbers': mukkadam.mobile_numbers,
        'crew_size': mukkadam.crew_size,
        'max_crew_capacity': mukkadam.max_crew_capacity,
        'village': mukkadam.village,
        'taluka': mukkadam.taluka,
        'district': mukkadam.district,
        'state': mukkadam.state,
        'current_latitude': float(mukkadam.current_latitude) if mukkadam.current_latitude else None,
        'current_longitude': float(mukkadam.current_longitude) if mukkadam.current_longitude else None,
        'work_mode': mukkadam.work_mode,
        'has_smartphone': mukkadam.has_smartphone,
        'start_date': str(mukkadam.start_date) if mukkadam.start_date else None,
        'end_date': str(mukkadam.end_date) if mukkadam.end_date else None,
    }

    # ── 2. Cluster assignments ──────────────────────────────
    assignments = ClusterMukkadamAssignment.objects.filter(
        mukkadam=mukkadam
    ).select_related('cluster')

    WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    clusters_data = []
    for a in assignments:
        clusters_data.append({
            'cluster_id': a.cluster.id,
            'cluster_name': a.cluster.name,
            'advance_amount': float(a.advance_amount),
            'transport_price': float(a.transport_price),
            'weekly_payment_day': WEEKDAY_NAMES[a.weekly_payment_day] if a.weekly_payment_day is not None else None,
            'total_weekly_payments': float(a.total_weekly_payments),
            'is_active': a.is_active,
            'joined_at': a.joined_at.isoformat(),
        })

    # ── 3. All allocations for this mukkadam ────────────────
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam
    ).select_related(
        'job_activity',
        'job_activity__job',
        'job_activity__job__farmer',
        'job_activity__job__plot',
        'job_activity__activity',
        'job_activity__plot',
        'cluster',
    ).order_by('allocated_date')

    # Group by job
    job_map = {}  # job_id -> {job_obj, allocations[]}
    for alloc in allocations:
        job_activity = alloc.job_activity
        job = job_activity.job
        jid = job.job_id

        if jid not in job_map:
            job_map[jid] = {'job': job, 'allocations': []}
        job_map[jid]['allocations'].append(alloc)

    # ── 4. Settlements map ──────────────────────────────────
    settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam
    ).prefetch_related(
        'weekly_payments_applied'
    ).select_related('job')

    settlement_map = {s.job_id: s for s in settlements}

    # ── 5. Misc costs map ───────────────────────────────────
    misc_costs_qs = MukkadamMiscCost.objects.filter(
        mukkadam=mukkadam
    ).select_related('job')

    misc_map = {}  # job_id -> [costs]
    for mc in misc_costs_qs:
        misc_map.setdefault(mc.job_id, []).append(mc)

    # ── 6. Payments map ─────────────────────────────────────
    # MukkadamPayment has M2M to Allocation — group by job via allocations
    payments_qs = MukkadamPayment.objects.filter(
        mukkadam=mukkadam
    ).prefetch_related('allocations__job_activity__job')

    payment_map = {}  # job_id -> [payments]
    for pay in payments_qs:
        job_ids_for_pay = set()
        for alloc in pay.allocations.all():
            job_ids_for_pay.add(alloc.job_activity.job.job_id)
        for jid in job_ids_for_pay:
            payment_map.setdefault(jid, []).append(pay)

    # ── 7. Build jobs list ──────────────────────────────────
    jobs_data = []

    for jid, entry in job_map.items():
        job = entry['job']
        job_allocs = entry['allocations']

        # Plot / farm info — prefer job_activity.plot, fallback to job.plot
        plot = None
        for a in job_allocs:
            if a.job_activity.plot:
                plot = a.job_activity.plot
                break
        if not plot:
            plot = job.plot

        farmer = job.farmer

        # Farm address — build from farmer cluster location
        farmer_clusters = list(farmer.clusters.all())
        farm_address_parts = []
        if plot:
            if plot.name:
                farm_address_parts.append(plot.name)
        if farmer.location:
            farm_address_parts.append(farmer.location)
        for fc in farmer_clusters:
            if fc.village:
                farm_address_parts.extend(fc.villages[:1])
            if fc.taluka:
                farm_address_parts.extend(fc.talukas[:1])
            if fc.district:
                farm_address_parts.extend(fc.districts[:1])
            break  # first cluster is enough
        farm_address = ', '.join([p for p in farm_address_parts if p])

        # Lat/Lng priority: plot > job > farmer
        farm_lat = None
        farm_lng = None
        if plot and plot.latitude:
            farm_lat = float(plot.latitude)
            farm_lng = float(plot.longitude)
        elif job.latitude:
            farm_lat = float(job.latitude)
            farm_lng = float(job.longitude)
        elif farmer.latitude:
            farm_lat = float(farmer.latitude)
            farm_lng = float(farmer.longitude)

        farm_data = {
            'plot_id': plot.id if plot else None,
            'plot_name': plot.name if plot else None,
            'plot_code': plot.plot_code if plot else None,
            'area_acres': float(plot.area_acres) if plot else None,
            'crop_name': plot.crop_name if plot else job.crop_name,
            'variety': plot.variety if plot else job.variety,
            'pruning_date': str(plot.pruning_date) if plot and plot.pruning_date else None,
            'address': farm_address,
            'latitude': farm_lat,
            'longitude': farm_lng,
            'farmer_village': farmer_clusters[0].villages[0] if farmer_clusters and farmer_clusters[0].villages else '',
            'farmer_taluka': farmer_clusters[0].talukas[0] if farmer_clusters and farmer_clusters[0].talukas else '',
            'farmer_district': farmer_clusters[0].districts[0] if farmer_clusters and farmer_clusters[0].districts else '',
        }

        # Activities
        activities_data = []
        all_dates = []
        total_gross = 0

        for alloc in job_allocs:
            ja = alloc.job_activity
            gross = float(alloc.allocated_area) * float(alloc.mukkadam_rate)
            total_gross += gross
            all_dates.append(alloc.allocated_date)

            activities_data.append({
                'allocation_id': alloc.id,
                'job_activity_id': ja.id,
                'activity_name': ja.activity.name,
                'activity_type': ja.activity.activity_type,
                'is_strict': ja.is_strict,
                'scheduled_date': str(ja.scheduled_date) if ja.scheduled_date else None,
                'allocated_date': str(alloc.allocated_date),
                'allocated_area': float(alloc.allocated_area),
                'total_area': float(ja.total_area),
                'remaining_area': float(ja.remaining_area),
                'allocated_workers': alloc.allocated_workers,
                'allocation_status': alloc.status,
                'farmer_rate': float(alloc.farmer_rate),
                'mukkadam_rate': float(alloc.mukkadam_rate),
                'gross_earn': round(gross, 2),
                'farmer_amount': float(alloc.farmer_amount),
                'mukkadam_amount': float(alloc.mukkadam_amount),
                'profit_margin': float(alloc.profit),
                'is_manually_moved': ja.is_manually_moved,
                'cluster': alloc.cluster.name if alloc.cluster else None,

                'report_submitted': alloc.report_submitted,
                'actual_start_time': alloc.actual_start_time.isoformat() if alloc.actual_start_time else None,
                'actual_end_time': alloc.actual_end_time.isoformat() if alloc.actual_end_time else None,
                'actual_crew_size': alloc.actual_crew_size,
                'actual_area_done': float(alloc.actual_area_done) if alloc.actual_area_done else None,
                'report_submitted_at': alloc.report_submitted_at.isoformat() if alloc.report_submitted_at else None,

                # Farmer verification
                'farmer_agreed': alloc.farmer_agreed,
                'farmer_response_at': alloc.farmer_response_at.isoformat() if alloc.farmer_response_at else None,
                'farmer_dispute_reason': alloc.farmer_dispute_reason,
                'use_actual_for_settlement': alloc.use_actual_for_settlement,

                # Variance
                'area_variance': round(
                    float(alloc.actual_area_done - alloc.allocated_area), 2
                ) if alloc.actual_area_done else None,
                'notes': alloc.notes,
            })

        # Timeline flag
        if all_dates:
            if min(all_dates) > today:
                timeline = 'future'
            elif max(all_dates) < today:
                timeline = 'past'
            else:
                timeline = 'current'
        else:
            timeline = 'future'

        # Settlement
        settlement = settlement_map.get(jid)
        misc_costs = misc_map.get(jid, [])
        total_misc = sum(float(mc.amount) for mc in misc_costs)

        settlement_data = None
        if settlement:
            weekly_payments_list = [
                {
                    'payment_date': str(wp.payment_date),
                    'amount': float(wp.amount),
                    'crew_size_on_date': wp.crew_size_on_date,
                }
                for wp in settlement.weekly_payments_applied.all().order_by('payment_date')
            ]
            settlement_data = {
                'gross_amount': float(settlement.gross_amount),
                'deposit_held': float(settlement.gross_amount * settlement.deposit_percent / 100),
                'payable_90pct': float(settlement.payable_amount),
                'deposit_carried_forward': float(settlement.deposit_carried_forward),
                'advance_deducted': float(settlement.advance_deducted),
                'weekly_payments_deducted': float(settlement.weekly_payments_deducted),
                'misc_deductions': total_misc,
                'net_payable': float(settlement.net_payable),
                'status': settlement.status,
                'calculated_at': settlement.calculated_at.isoformat() if settlement.calculated_at else None,
                'paid_at': settlement.paid_at.isoformat() if settlement.paid_at else None,
                'weekly_payments': weekly_payments_list,
                'misc_costs': [
                    {
                        'amount': float(mc.amount),
                        'reason': mc.reason,
                        'created_at': mc.created_at.strftime('%Y-%m-%d'),
                    }
                    for mc in misc_costs
                ],
            }

        # Payments received for this job
        job_payments = payment_map.get(jid, [])
        payments_data = [
            {
                'payment_id': p.payment_id,
                'amount': float(p.amount),
                'mode': p.mode,
                'paid_at': p.paid_at.strftime('%Y-%m-%d'),
                'notes': p.notes,
            }
            for p in job_payments
        ]

        jobs_data.append({
            'job_id': jid,
            'timeline': timeline,
            'job_status': job.status,
            'crop_name': job.crop_name,
            'variety': job.variety,
            'scheduled_date': str(job.scheduled_date) if job.scheduled_date else None,
            'booking_type': job.booking_type,
            'activity_notes': job.activity_notes,
            'internal_notes': job.internal_notes,
            'farmer': {
                'farmer_id': farmer.farmer_id,
                'farmer_name': farmer.farmer_name,
                'phone_number': farmer.phone_number,
            },
            'farm': farm_data,
            'activities': activities_data,
            'settlement': settlement_data,
            'payments_received': payments_data,
        })

    # Sort: current → future → past
    order = {'current': 0, 'future': 1, 'past': 2}
    jobs_data.sort(key=lambda j: (order.get(j['timeline'], 3), j['job_id']))

    # ── 8. Work summary ─────────────────────────────────────
    total_gross_all = sum(
        act['gross_earn']
        for job in jobs_data
        for act in job['activities']
    )
    total_paid_out = sum(
        p['amount']
        for job in jobs_data
        for p in job['payments_received']
    )
    settled_net = sum(
        job['settlement']['net_payable']
        for job in jobs_data
        if job['settlement'] and job['settlement']['net_payable'] > 0
    )

    work_summary = {
        'total_jobs': len(jobs_data),
        'past_jobs': sum(1 for j in jobs_data if j['timeline'] == 'past'),
        'current_jobs': sum(1 for j in jobs_data if j['timeline'] == 'current'),
        'future_jobs': sum(1 for j in jobs_data if j['timeline'] == 'future'),
        'total_allocated_area': round(
            sum(a['allocated_area'] for j in jobs_data for a in j['activities']), 2
        ),
        'total_earned_gross': round(total_gross_all, 2),
        'total_paid_out': round(total_paid_out, 2),
        'pending_payment': round(settled_net - total_paid_out, 2),
    }

    return Response({
        'mukkadam': mukkadam_data,
        'clusters': clusters_data,
        'work_summary': work_summary,
        'jobs': jobs_data,
    })


@api_view(['GET'])
def mukkadam_future_work(request):
    """
    Returns upcoming/future jobs assigned to the mukkadam.
    Includes allocation-level work status, start/end times, and report info.
    """
    mobile = request.query_params.get('mobile', '').strip()
    if not mobile:
        return Response({'error': 'mobile required'}, status=status.HTTP_400_BAD_REQUEST)

    mukkadam = Mukkadam.objects.filter(mobile_numbers__icontains=mobile).first()
    if not mukkadam:
        return Response({'error': 'Mukkadam not found'}, status=status.HTTP_404_NOT_FOUND)

    today = date.today()

    future_allocs = Allocation.objects.filter(
        mukkadam=mukkadam,
        allocated_date__gte=today
    ).select_related(
        'job_activity__job__farmer',
        'job_activity__activity',
        'job_activity__plot'
    ).order_by('allocated_date')

    jobs_map = {}
    for alloc in future_allocs:
        job = alloc.job_activity.job
        jid = job.job_id

        if jid not in jobs_map:
            plot = alloc.job_activity.plot or getattr(job, 'plot', None)

            jobs_map[jid] = {
                'job_id':         jid,
                'farmer_id':      job.farmer.farmer_id,
                'farmer_name':    job.farmer.farmer_name,
                'farmer_phone':   job.farmer.phone_number,
                'scheduled_date': str(job.scheduled_date),
                'crop':           f"{job.crop_name} ({job.variety})",
                'location': {
                    'address': job.farmer.location,
                    'lat': float(plot.latitude)  if plot and plot.latitude  else float(job.latitude)  if job.latitude  else None,
                    'lng': float(plot.longitude) if plot and plot.longitude else float(job.longitude) if job.longitude else None,
                },
                'activities':          [],
                'projected_earnings':  0.0,

                # ── Job-level status summary ──────────────────────────
                # Derived from the allocations within this job:
                #   not_started  → all allocations are work_not_started
                #   in_progress  → at least one started, not all reported
                #   completed    → all allocations have report_submitted=True
                'job_work_status':     None,  # filled after all allocs added
            }

        projected = float(alloc.allocated_area * alloc.mukkadam_rate)
        jobs_map[jid]['projected_earnings'] += round(projected, 2)

        # ── Format times (IST-friendly string if present) ─────────────
        def fmt_time(dt):
            if not dt:
                return None
            try:
                from django.utils import timezone as tz
                local = tz.localtime(dt)
                return local.strftime('%Y-%m-%d %H:%M')
            except Exception:
                return str(dt)

        jobs_map[jid]['activities'].append({
            'allocation_id':    alloc.id,
            'name':             alloc.job_activity.activity.name,
            'date':             str(alloc.allocated_date),
            'area':             float(alloc.allocated_area),
            'workers':          alloc.allocated_workers,
            'rate':             float(alloc.mukkadam_rate),
            'earning':          round(projected, 2),

            # ── Work status ───────────────────────────────────────────
            'work_status':      alloc.work_status,          # work_not_started / in_progress / completed
            'status':           alloc.status,               # scheduled / in_progress / completed / cancelled

            # ── Start ─────────────────────────────────────────────────
            'started':          alloc.actual_start_time is not None,
            'start_time':       fmt_time(alloc.actual_start_time),

            # ── End / report ──────────────────────────────────────────
            'report_submitted': alloc.report_submitted,
            'end_time':         fmt_time(alloc.actual_end_time),
            'submitted_at':     fmt_time(alloc.report_submitted_at),

            # ── Claimed area (from day-end report) ────────────────────
            'actual_area_done': float(alloc.actual_area_done) if alloc.actual_area_done is not None else None,
            'actual_crew_size': alloc.actual_crew_size,
        })

    # ── Derive job-level work status from its allocations ─────────────────
    for job_data in jobs_map.values():
        acts = job_data['activities']
        if not acts:
            job_data['job_work_status'] = 'not_started'
        elif all(a['report_submitted'] for a in acts):
            job_data['job_work_status'] = 'completed'
        elif any(a['started'] or a['work_status'] != 'work_not_started' for a in acts):
            job_data['job_work_status'] = 'in_progress'
        else:
            job_data['job_work_status'] = 'not_started'

        # ── Earliest start and latest end across all allocations ──────
        start_times = [a['start_time'] for a in acts if a['start_time']]
        end_times   = [a['end_time']   for a in acts if a['end_time']]
        job_data['job_started_at'] = min(start_times) if start_times else None
        job_data['job_ended_at']   = max(end_times)   if end_times   else None

    return Response({
        'mukkadam_id':             mukkadam.mukkadam_id,
        'mukkadam_name':           mukkadam.mukkadam_name,
        'CENTRAL_PHONE' : '+918047361465',
        'total_future_jobs':       len(jobs_map),
        'total_projected_earning': round(sum(j['projected_earnings'] for j in jobs_map.values()), 2),
        'jobs':                    list(jobs_map.values()),
    })

from decimal import Decimal
from django.db.models import Sum
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from tender.models import Mukkadam, MukkadamJobSettlement, Allocation, MukkadamMiscCost


from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncWeek
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils.dateparse import parse_date


@api_view(['POST'])
@permission_classes([AllowAny])  # secure with token if needed
def mukkadam_day_end_report(request):
    """
    POST /api/mukkadam/day-end-report/

    Mukkadam hits this at end of day with actual work done.
    We store it on the Allocation. 
    Settlement will later use actual_area_done if farmer_agreed=True.

    Payload:
    {
        "mukkadam_id": 101,
        "allocation_id": 501,          // OR use job_id + job_activity_id
        "actual_start_time": "2025-12-10T07:30:00+05:30",
        "actual_end_time": "2025-12-10T17:00:00+05:30",
        "actual_crew_size": 18,
        "actual_area_done": 2.25
    }
    """
    data = request.data

    # ── Validate required fields ─────────────────────────
    required = ['mukkadam_id', 'allocation_id', 'actual_crew_size', 'actual_area_done']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response(
            {'error': f'Missing required fields: {", ".join(missing)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ── Fetch allocation ─────────────────────────────────
    try:
        allocation = Allocation.objects.select_related(
            'mukkadam',
            'job_activity',
            'job_activity__job',
            'job_activity__activity',
            'job_activity__plot',
        ).get(
            id=data['allocation_id'],
            mukkadam__mukkadam_id=data['mukkadam_id']
        )
    except Allocation.DoesNotExist:
        return Response(
            {'error': 'Allocation not found or mukkadam mismatch'},
            status=status.HTTP_404_NOT_FOUND
        )

    # ── Prevent duplicate submission ─────────────────────
    if allocation.report_submitted:
        return Response(
            {
                'error': 'Report already submitted for this allocation',
                'submitted_at': allocation.report_submitted_at,
                'actual_area_done': float(allocation.actual_area_done),
            },
            status=status.HTTP_409_CONFLICT
        )

    # ── Validate area ────────────────────────────────────
    actual_area = Decimal(str(data['actual_area_done']))
    if actual_area <= 0:
        return Response(
            {'error': 'actual_area_done must be greater than 0'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if actual_area > allocation.allocated_area * Decimal('1.2'):  # allow 20% over
        return Response(
            {'error': f'actual_area_done {actual_area} seems too high vs allocated {allocation.allocated_area}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ── Store report ─────────────────────────────────────
    now = timezone.now()

    allocation.actual_crew_size = int(data['actual_crew_size'])
    allocation.actual_area_done = actual_area
    allocation.report_submitted = True
    allocation.report_submitted_at = now

    if data.get('actual_start_time'):
        try:
            from django.utils.dateparse import parse_datetime
            allocation.actual_start_time = parse_datetime(data['actual_start_time'])
        except Exception:
            pass  # optional field, skip bad format

    if data.get('actual_end_time'):
        try:
            allocation.actual_end_time = parse_datetime(data['actual_end_time'])
        except Exception:
            pass

    allocation.save(update_fields=[
        'actual_crew_size', 'actual_area_done',
        'actual_start_time', 'actual_end_time',
        'report_submitted', 'report_submitted_at',
    ])

    ja = allocation.job_activity

    return Response({
        'success': True,
        'message': 'Day-end report submitted successfully',
        'allocation_id': allocation.id,
        'job_id': ja.job.job_id,
        'activity': ja.activity.name,
        'plot': ja.plot.name if ja.plot else None,
        'allocated_area': float(allocation.allocated_area),
        'actual_area_done': float(actual_area),
        'variance': round(float(actual_area - allocation.allocated_area), 2),
        'farmer_verification_pending': True,
        'submitted_at': now.isoformat(),
    }, status=status.HTTP_200_OK)

from django.db import models, transaction
@api_view(['POST'])
@permission_classes([AllowAny])
def farmer_verify_work(request):
    farmer_id = request.data.get('farmer_id', '').strip()
    allocation_id = request.data.get('allocation_id')
    agreed = request.data.get('agreed')
    dispute_reason = request.data.get('dispute_reason', '').strip()

    if not farmer_id or allocation_id is None or agreed is None:
        return Response({'error': 'farmer_id, allocation_id, agreed are required'}, status=400)

    if not agreed and not dispute_reason:
        return Response({'error': 'dispute_reason is required when agreed is false'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'job_activity__job__farmer', 'mukkadam'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    if allocation.job_activity.job.farmer.farmer_id != farmer_id:
        return Response({'error': 'This allocation does not belong to your job'}, status=403)

    if not allocation.report_submitted:
        return Response({'error': 'Mukkadam has not submitted report yet'}, status=400)

    if allocation.farmer_agreed is not None:
        return Response({'error': 'You have already responded to this allocation'}, status=409)

    with transaction.atomic():
        allocation.farmer_agreed = agreed
        allocation.farmer_response_at = timezone.now()
        allocation.farmer_dispute_reason = dispute_reason if not agreed else ''
        allocation.use_actual_for_settlement = bool(agreed)
        allocation.save(update_fields=[
            'farmer_agreed', 'farmer_response_at',
            'farmer_dispute_reason', 'use_actual_for_settlement'
        ])

        carry_result = None
        if agreed:
            # Trigger carry-forward
            from tender.ervices.carry_forward import process_carry_forward
            carry_result = process_carry_forward(allocation.id)

    response = {
        'success': True,
        'allocation_id': allocation.id,
        'agreed': agreed,
        'actual_area_done': float(allocation.actual_area_done) if allocation.actual_area_done else None,
        'use_actual_for_settlement': allocation.use_actual_for_settlement,
        'message': 'Work verified. Allocation adjusted automatically.' if agreed else 'Dispute recorded.',
    }

    if carry_result:
        response['carry_forward'] = carry_result

    return Response(response)
"""
Mukkadam Earnings & Settlement History APIs
============================================

Two endpoints:

1. GET /api/mukkadams/<id>/earnings/
   - All allocations where earning is recognized
   - Earning recognized when: allocated_date < today OR report_submitted=True
   - Grouped by: cluster, week (Mon-Sun), activity
   - Shows expected earning (allocated_area × rate) vs actual (claimed area if submitted)

2. GET /api/mukkadams/<id>/settlement-history/
   - Full settlement ledger matching cluster_payment_dashboard logic exactly
   - Week-wise (Mon-Sun) breakdown: what was worked, weekly payment made, running balance
   - Cluster-wise summary
   - Settlement status per job
   - Transaction history with running balance
"""


@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_earnings(request, mukkadam_id):
    """
    GET /api/mukkadams/<id>/earnings/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

    Returns all earned allocations for this mukkadam.
    An allocation is "earned" when:
      - allocated_date < today  (date is past)
      - OR report_submitted = True  (mukkadam submitted mark-end)

    Grouped by:
      - Overall totals
      - Per cluster
      - Per week (Mon-Sun calendar weeks)
      - Per job (settlement-linked jobs)

    Each allocation row shows:
      - Expected (allocated_area × mukkadam_rate)
      - Actual (mukkadam_claimed_area if submitted, else allocated_area)
      - Variance
    """
    from decimal import Decimal
    from datetime import date, timedelta
    from django.db.models import Sum, Q

    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    today = date.today()

    # ── Date range filter ─────────────────────────────────────────────
    start_str = request.query_params.get('start_date')
    end_str   = request.query_params.get('end_date')

    if start_str and end_str:
        from django.utils.dateparse import parse_date
        start = parse_date(start_str)
        end   = parse_date(end_str)
        if not start or not end:
            return Response({'error': 'Invalid start_date or end_date'}, status=400)
    else:
        # Default: last 90 days
        end   = today
        start = today - timedelta(days=90)

    # ── Fetch earned allocations ──────────────────────────────────────
    # Earning recognized when ANY of:
    #   1. allocated_date in range AND date is past
    #   2. report_submitted = True (mukkadam hit submit) — regardless of date
    #   3. work_status in ('completed', 'dispute') — regardless of date
    # NOTE: date range is NOT applied to submitted/completed allocations
    # because mukkadam may submit on a future-dated allocation (e.g. pre-scheduled)
    # ── DEBUG: show ALL allocations for this mukkadam to find what's being excluded ──
    _all = Allocation.objects.filter(mukkadam=mukkadam)
    import logging
    _logger = logging.getLogger(__name__)
    for _a in _all:
        _logger.warning(
            f"[EARNINGS DEBUG] alloc_id={_a.id} date={_a.allocated_date} "
            f"status={_a.status} work_status={_a.work_status} "
            f"report_submitted={_a.report_submitted} "
            f"in_status_filter={_a.status in ['scheduled','in_progress','completed']} "
            f"date_lt_today={_a.allocated_date < today} "
            f"in_range={start <= _a.allocated_date <= end}"
        )
    # ── END DEBUG ────────────────────────────────────────────────────

    qs = Allocation.objects.filter(
        mukkadam=mukkadam,
        status__in=['scheduled', 'in_progress', 'completed'],
    ).filter(
        Q(allocated_date__lt=today, allocated_date__range=(start, end))
        | Q(report_submitted=True)
        | Q(work_status__in=['completed', 'dispute'])
    ).select_related(
        'cluster',
        'job_activity',
        'job_activity__job',
        'job_activity__job__farmer',
        'job_activity__activity',
        'job_activity__plot',
    ).order_by('allocated_date')

    # ── Build allocation rows ─────────────────────────────────────────
    allocation_rows = []
    total_expected  = Decimal('0')
    total_actual    = Decimal('0')

    for a in qs:
        rate = Decimal(str(a.mukkadam_rate or 0))

        # Expected = what was planned
        expected_area   = Decimal(str(a.allocated_area or 0))
        expected_amount = (expected_area * rate).quantize(Decimal('0.01'))

        # Actual = what mukkadam claimed
        # Use claimed area if report submitted OR work_status shows mukkadam acted
        has_submission = a.report_submitted or a.work_status in ('completed', 'dispute')
        if has_submission:
            claimed = a.mukkadam_claimed_area or a.actual_area_done
            actual_area = Decimal(str(claimed)) if claimed is not None else expected_area
        else:
            actual_area = expected_area  # date past, not submitted yet → use planned

        actual_amount = (actual_area * rate).quantize(Decimal('0.01'))
        variance      = actual_area - expected_area

        total_expected += expected_amount
        total_actual   += actual_amount

        # Week info (Mon-Sun)
        alloc_date  = a.allocated_date
        # Monday of this week
        week_start  = alloc_date - timedelta(days=alloc_date.weekday())
        week_end    = week_start + timedelta(days=6)
        week_label  = f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
        week_key    = str(week_start)

        allocation_rows.append({
            'allocation_id':    a.id,
            'allocated_date':   str(alloc_date),
            'week_start':       week_key,
            'week_label':       week_label,
            'cluster_id':       a.cluster_id,
            'cluster_name':     a.cluster.name if a.cluster else '—',
            'job_id':           a.job_activity.job.job_id,
            'farmer_name':      a.job_activity.job.farmer.farmer_name if a.job_activity.job.farmer else '—',
            'activity_name':    a.job_activity.activity.name,
            'plot_code':        a.job_activity.plot.plot_code if a.job_activity.plot else '—',
            'plot_name':        a.job_activity.plot.name if a.job_activity.plot else '—',

            # Workers
            'allocated_workers': a.allocated_workers or 0,
            'actual_crew_size':  a.actual_crew_size,

            # Area
            'expected_area':    float(expected_area),
            'actual_area':      float(actual_area),
            'variance_area':    round(float(variance), 3),

            # Rate & amounts
            'mukkadam_rate':    float(rate),
            'expected_amount':  float(expected_amount),
            'actual_amount':    float(actual_amount),
            'variance_amount':  float(actual_amount - expected_amount),

            # Status flags
            'work_status':       getattr(a, 'work_status', 'work_not_started'),
            'report_submitted':  a.report_submitted,
            'farmer_agreed':     a.farmer_agreed,
            'billing_locked':    (
                getattr(a, 'payment_status', None) == 'dispute'
                and not getattr(a, 'use_actual_for_settlement', False)
                and getattr(a, 'admin_override_area', None) is None
            ),
        })

    # ── Group by cluster ──────────────────────────────────────────────
    cluster_map = {}
    for row in allocation_rows:
        cid = row['cluster_id']
        if cid not in cluster_map:
            cluster_map[cid] = {
                'cluster_id':       cid,
                'cluster_name':     row['cluster_name'],
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'allocations':      [],
            }
        cluster_map[cid]['total_expected']   += Decimal(str(row['expected_amount']))
        cluster_map[cid]['total_actual']     += Decimal(str(row['actual_amount']))
        cluster_map[cid]['allocation_count'] += 1
        cluster_map[cid]['allocations'].append(row)

    by_cluster = []
    for cdata in cluster_map.values():
        by_cluster.append({
            'cluster_id':       cdata['cluster_id'],
            'cluster_name':     cdata['cluster_name'],
            'allocation_count': cdata['allocation_count'],
            'total_expected':   float(cdata['total_expected']),
            'total_actual':     float(cdata['total_actual']),
            'variance':         float(cdata['total_actual'] - cdata['total_expected']),
        })

    # ── Group by week (Mon-Sun) ────────────────────────────────────────
    week_map = {}
    for row in allocation_rows:
        wk = row['week_start']
        if wk not in week_map:
            week_map[wk] = {
                'week_start':       wk,
                'week_label':       row['week_label'],
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'allocations':      [],
            }
        week_map[wk]['total_expected']   += Decimal(str(row['expected_amount']))
        week_map[wk]['total_actual']     += Decimal(str(row['actual_amount']))
        week_map[wk]['allocation_count'] += 1
        week_map[wk]['allocations'].append(row)

    by_week = []
    for wdata in sorted(week_map.values(), key=lambda x: x['week_start']):
        by_week.append({
            'week_start':       wdata['week_start'],
            'week_label':       wdata['week_label'],
            'allocation_count': wdata['allocation_count'],
            'total_expected':   float(wdata['total_expected']),
            'total_actual':     float(wdata['total_actual']),
            'variance':         float(wdata['total_actual'] - wdata['total_expected']),
            'allocations':      wdata['allocations'],
        })

    # ── Group by farmer ───────────────────────────────────────────────
    farmer_map = {}
    for row in allocation_rows:
        fid = row['job_id']  # unique per job; group by farmer_name+job
        # Use farmer_name as key since we may not have farmer_id here
        fname = row['farmer_name']
        if fname not in farmer_map:
            farmer_map[fname] = {
                'farmer_name':      fname,
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'jobs':             {},   # job_id → {job details}
            }
        farmer_map[fname]['total_expected']   += Decimal(str(row['expected_amount']))
        farmer_map[fname]['total_actual']     += Decimal(str(row['actual_amount']))
        farmer_map[fname]['allocation_count'] += 1

        jid = str(row['job_id'])
        if jid not in farmer_map[fname]['jobs']:
            farmer_map[fname]['jobs'][jid] = {
                'job_id':           jid,
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'allocations':      [],
            }
        farmer_map[fname]['jobs'][jid]['total_expected']   += Decimal(str(row['expected_amount']))
        farmer_map[fname]['jobs'][jid]['total_actual']     += Decimal(str(row['actual_amount']))
        farmer_map[fname]['jobs'][jid]['allocation_count'] += 1
        farmer_map[fname]['jobs'][jid]['allocations'].append(row)

    by_farmer = []
    for fdata in sorted(farmer_map.values(), key=lambda x: x['farmer_name']):
        jobs_list = []
        for jdata in fdata['jobs'].values():
            jobs_list.append({
                'job_id':           jdata['job_id'],
                'allocation_count': jdata['allocation_count'],
                'total_expected':   float(jdata['total_expected']),
                'total_actual':     float(jdata['total_actual']),
                'variance':         float(jdata['total_actual'] - jdata['total_expected']),
                'allocations':      jdata['allocations'],
            })
        by_farmer.append({
            'farmer_name':      fdata['farmer_name'],
            'allocation_count': fdata['allocation_count'],
            'total_expected':   float(fdata['total_expected']),
            'total_actual':     float(fdata['total_actual']),
            'variance':         float(fdata['total_actual'] - fdata['total_expected']),
            'jobs':             jobs_list,
        })

    return Response({
        'mukkadam_id':   mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'period': {
            'start_date': str(start),
            'end_date':   str(end),
        },
        'totals': {
            'allocation_count':   len(allocation_rows),
            'total_expected':     float(total_expected),
            'total_actual':       float(total_actual),
            'total_variance':     float(total_actual - total_expected),
        },
        'by_cluster':     by_cluster,
        'by_week':        by_week,
        'by_farmer':      by_farmer,
        'allocations':    allocation_rows,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SETTLEMENT HISTORY  (mirrors cluster_payment_dashboard mukkadam section exactly)
# ─────────────────────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_settlement_history(request, mukkadam_id):
    """
    GET /api/mukkadams/<id>/settlement-history/?cluster_id=<optional>

    Added in this version:
    ─ total_allocated_acres, total_actual_acres, total_effective_acres in every summary
    ─ payment_breakdown in every summary:
        advance_paid, weekly_paid, missed_weekly_paid, direct_settlement_paid, total_paid
    ─ Same breakdown added to: top-level summary, by_cluster, by_farmer, week_ledger
    """
    from decimal import Decimal
    from datetime import date, timedelta
    from django.db.models import Q
    from tender.utils import get_presigned_urls_batch

    today = date.today()

    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    # ── All active assignments (one per cluster) ──────────────────────
    cluster_id_param = request.query_params.get('cluster_id')
    all_assignments = list(
        ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam, is_active=True,
        ).select_related('cluster').order_by('-joined_at')
    )
    if cluster_id_param:
        assignment = next((a for a in all_assignments if str(a.cluster_id) == str(cluster_id_param)), None)
        if not assignment and all_assignments:
            assignment = all_assignments[0]
    else:
        assignment = all_assignments[0] if all_assignments else None

    # ── Settlements ───────────────────────────────────────────────────
    settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam,
    ).exclude(status='pending').select_related(
        'job', 'job__farmer', 'plot',
    ).order_by('calculated_at')

    # ── Weekly payments across ALL assignments ────────────────────────
    weekly_qs = list(
        MukkadamWeeklyPayment.objects.filter(
            assignment__in=all_assignments
        ).order_by('payment_date')
    ) if all_assignments else []

    weekly_proof_keys = [w.proof_s3_key for w in weekly_qs if getattr(w, 'proof_s3_key', None)]
    weekly_proof_map  = get_presigned_urls_batch(weekly_proof_keys) if weekly_proof_keys else {}

    # Separate: track which weekly payments were for missed dates
    # A payment is "missed-recovery" if its payment_date differs from the expected
    # scheduled day for that assignment. We tag them based on _missed_for_assignment.
    # We'll compute this after assignments are processed.

    # ── Settlement payments ───────────────────────────────────────────
    all_payments = list(
        MukkadamPayment.objects.filter(mukkadam=mukkadam)
        .select_related('settlement', 'settlement__job', 'settlement__job__farmer', 'settlement__plot')
        .order_by('paid_at')
    )
    settle_proof_keys = [p.proof_s3_key for p in all_payments if getattr(p, 'proof_s3_key', None)]
    settle_proof_map  = get_presigned_urls_batch(settle_proof_keys) if settle_proof_keys else {}

    payments_by_settlement = {}
    for p in all_payments:
        sid = p.settlement_id
        if sid not in payments_by_settlement:
            payments_by_settlement[sid] = []
        ps_key = getattr(p, 'proof_s3_key', None)
        payments_by_settlement[sid].append({
            'payment_id': p.payment_id,
            'amount':     float(p.amount),
            'mode':       getattr(p, 'mode', 'CASH'),
            'notes':      getattr(p, 'notes', ''),
            'paid_at':    str(p.paid_at.date()) if p.paid_at else None,
            'proof_url':  settle_proof_map.get(ps_key) if ps_key else None,
        })

    # ── Misc costs ────────────────────────────────────────────────────
    all_misc = list(
        MukkadamMiscCost.objects.filter(mukkadam=mukkadam)
        .select_related('job').order_by('created_at')
    )
    misc_proof_keys = [c.proof_s3_key for c in all_misc if getattr(c, 'proof_s3_key', None)]
    misc_proof_map  = get_presigned_urls_batch(misc_proof_keys) if misc_proof_keys else {}

    # ── Helpers ───────────────────────────────────────────────────────
    def effective_area_for(a):
        if getattr(a, 'admin_override_area', None) is not None:
            return Decimal(str(a.admin_override_area))
        if getattr(a, 'use_actual_for_settlement', False) and a.actual_area_done is not None:
            return Decimal(str(a.actual_area_done))
        if a.farmer_agreed is True and a.actual_area_done is not None:
            return Decimal(str(a.actual_area_done))
        return Decimal(str(a.allocated_area or 0))

    def is_billing_locked(a):
        return (
            (getattr(a, 'payment_status', None) == 'dispute'
             and not getattr(a, 'use_actual_for_settlement', False)
             and getattr(a, 'admin_override_area', None) is None)
            or (a.farmer_agreed is False
                and getattr(a, 'admin_override_area', None) is None
                and not getattr(a, 'use_actual_for_settlement', False))
        )

    def empty_payment_breakdown():
        """Standard payment breakdown dict used in every summary."""
        return {
            'advance_paid':          0.0,   # from ClusterMukkadamAssignment.advance_amount
            'weekly_paid':           0.0,   # on-time weekly payments
            'missed_weekly_paid':    0.0,   # recovered late weekly payments
            'direct_settlement_paid':0.0,   # MukkadamPayment (settlement pay button)
            'misc_deducted':         0.0,   # MukkadamMiscCost
            'total_paid':            0.0,   # sum of all above
        }

    def empty_acres():
        return {
            'total_allocated_acres': 0.0,
            'total_actual_acres':    0.0,   # mukkadam claimed / actual_area_done
            'total_effective_acres': 0.0,   # used for billing (after overrides)
        }

    # ── Missed weekly dates per assignment ────────────────────────────
    def _missed_dates_for(asgn):
        if asgn.weekly_payment_day is None or not asgn.joined_at:
            return set()
        start_dt   = asgn.joined_at.date()
        paid_dates = set(
            MukkadamWeeklyPayment.objects.filter(assignment=asgn)
            .values_list('payment_date', flat=True)
        )
        missed = set()
        cur = start_dt
        while cur <= today:
            if cur.weekday() == asgn.weekly_payment_day and cur < today:
                if cur not in paid_dates:
                    missed.add(cur)
            cur += timedelta(days=1)
        return missed

    # Pre-compute missed dates per assignment
    missed_by_assignment = {asgn.id: _missed_dates_for(asgn) for asgn in all_assignments}

    # Tag each weekly payment: on_time vs missed_recovery
    # A weekly payment is "missed_recovery" if payment_date is NOT the expected day
    # i.e. it was paid late (the date itself differs from the weekday schedule)
    # We identify this by checking if payment_date was in the missed set BEFORE this payment
    # Simpler approach: payment is missed_recovery if notes contain "late" or if payment_date
    # weekday != assignment.weekly_payment_day
    def is_missed_recovery(w):
        if w.assignment_id and w.assignment and w.assignment.weekly_payment_day is not None:
            return w.payment_date.weekday() != w.assignment.weekly_payment_day
        return False

    total_weekly_on_time = sum(
        float(w.amount) for w in weekly_qs if not is_missed_recovery(w)
    )
    total_weekly_missed_recovery = sum(
        float(w.amount) for w in weekly_qs if is_missed_recovery(w)
    )

    # ── BUILD SETTLEMENT ROWS ─────────────────────────────────────────
    settlement_rows = []

    for s in settlements:
        if s.plot is None:
            alloc_filter = Q(mukkadam=mukkadam, job_activity__job=s.job)
        else:
            alloc_filter = Q(mukkadam=mukkadam, job_activity__job=s.job, job_activity__plot=s.plot)

        allocations = Allocation.objects.filter(alloc_filter).select_related(
            'job_activity__activity', 'job_activity__plot', 'cluster',
        ).order_by('allocated_date')

        act_details  = []
        gross_amount = Decimal('0')
        alloc_acres  = Decimal('0')
        actual_acres = Decimal('0')
        eff_acres    = Decimal('0')

        for a in allocations:
            rate     = Decimal(str(a.mukkadam_rate or 0))
            eff_area = effective_area_for(a)
            locked   = is_billing_locked(a)
            gross    = Decimal('0') if locked else (eff_area * rate).quantize(Decimal('0.01'))
            gross_amount += gross

            alloc_acres  += Decimal(str(a.allocated_area or 0))
            act_raw       = a.mukkadam_claimed_area or a.actual_area_done
            actual_acres += Decimal(str(act_raw)) if act_raw is not None else Decimal(str(a.allocated_area or 0))
            eff_acres    += eff_area

            claimed = a.mukkadam_claimed_area or a.actual_area_done
            act_details.append({
                'allocation_id':         a.id,
                'allocated_date':        str(a.allocated_date) if a.allocated_date else None,
                'activity_name':         a.job_activity.activity.name,
                'plot_code':             a.job_activity.plot.plot_code if a.job_activity.plot else '—',
                'cluster_id':            a.cluster_id,
                'cluster_name':          a.cluster.name if a.cluster else '—',
                'allocated_area':        float(a.allocated_area or 0),
                'mukkadam_claimed_area': float(claimed) if claimed is not None else None,
                'admin_override_area':   float(a.admin_override_area) if getattr(a, 'admin_override_area', None) is not None else None,
                'actual_area_done':      float(a.actual_area_done) if a.actual_area_done is not None else None,
                'effective_area':        float(eff_area),
                'mukkadam_rate':         float(rate),
                'gross_amount':          float(gross),
                'allocated_workers':     a.allocated_workers or 0,
                'actual_crew_size':      a.actual_crew_size,
                'work_status':           getattr(a, 'work_status', 'work_not_started'),
                'payment_status':        getattr(a, 'payment_status', 'pending'),
                'report_submitted':      a.report_submitted,
                'farmer_agreed':         a.farmer_agreed,
                'billing_locked':        locked,
                'is_carry_forward':      getattr(a, 'is_carry_forward', False),
            })

        deposit_pct  = s.deposit_percent or Decimal('10')
        deposit_held = (s.gross_amount * deposit_pct / 100).quantize(Decimal('0.01'))
        all_done     = len(act_details) > 0 and all(d['work_status'] == 'completed' for d in act_details)

        payable_90 = s.payable_amount
        if payable_90 >= s.gross_amount and s.gross_amount > 0 and not all_done:
            payable_90 = s.gross_amount - deposit_held

        job_misc       = [c for c in all_misc if str(c.job_id) == str(s.job_id)]
        job_misc_total = sum(Decimal(str(c.amount)) for c in job_misc)
        job_misc_data  = [{
            'id':        c.id,
            'amount':    float(c.amount),
            'reason':    c.reason or '',
            'date':      str(c.created_at.date()),
            'proof_url': misc_proof_map.get(c.proof_s3_key) if getattr(c, 'proof_s3_key', None) else None,
        } for c in job_misc]

        settlement_payments  = payments_by_settlement.get(s.id, [])
        total_already_paid   = sum(p['amount'] for p in settlement_payments)
        remaining_payable    = float(s.net_payable) - total_already_paid

        settlement_rows.append({
            'job_id':                   str(s.job.job_id),
            'farmer_name':              s.job.farmer.farmer_name if s.job.farmer else '—',
            'plot_name':                s.plot.name if s.plot else '—',
            'plot_code':                s.plot.plot_code if s.plot else '—',
            'status':                   s.status,
            # Acres
            'acres': {
                'total_allocated_acres': float(alloc_acres),
                'total_actual_acres':    float(actual_acres),
                'total_effective_acres': float(eff_acres),
            },
            # Financials
            'gross_amount':             float(s.gross_amount),
            'deposit_percent':          float(deposit_pct),
            'deposit_held':             float(deposit_held),
            'deposit_released':         all_done,
            'payable_90pct':            float(payable_90),
            'deposit_carried_forward':  float(s.deposit_carried_forward or 0),
            'credit_carried_forward':   float(s.credit_carried_forward or 0),
            'advance_deducted':         float(s.advance_deducted),
            'weekly_payments_deducted': float(s.weekly_payments_deducted),
            'total_misc':               float(job_misc_total),
            'net_payable':              float(s.net_payable),
            'total_already_paid':       total_already_paid,
            'remaining_payable':        remaining_payable,
            # Payment breakdown for this job
            'payment_breakdown': {
                'advance_paid':           float(s.advance_deducted),
                'weekly_paid':            float(s.weekly_payments_deducted),
                'missed_weekly_paid':     0.0,   # can't split at job level without extra tracking
                'direct_settlement_paid': total_already_paid,
                'misc_deducted':          float(job_misc_total),
                'total_paid':             float(s.advance_deducted) + float(s.weekly_payments_deducted) + total_already_paid,
            },
            'calculated_at':  str(s.calculated_at.date()) if s.calculated_at else None,
            'paid_at':        str(s.paid_at.date()) if s.paid_at else None,
            'activities':     act_details,
            'misc_costs':     job_misc_data,
            'payments_made':  settlement_payments,
        })

    # ── All earned allocations ────────────────────────────────────────
    all_earned_allocs = Allocation.objects.filter(
        mukkadam=mukkadam,
        status__in=['scheduled', 'in_progress', 'completed'],
    ).filter(
        Q(allocated_date__lt=today)
        | Q(report_submitted=True)
        | Q(work_status__in=['completed', 'dispute'])
    ).distinct().select_related(
        'cluster', 'job_activity__activity', 'job_activity__plot',
        'job_activity__job', 'job_activity__job__farmer',
    ).order_by('allocated_date')

    # ── WEEK LEDGER ───────────────────────────────────────────────────
    weekly_by_week = {}
    for w in weekly_qs:
        pd       = w.payment_date
        wk_start = pd - timedelta(days=pd.weekday())
        wk_key   = str(wk_start)
        if wk_key not in weekly_by_week:
            weekly_by_week[wk_key] = []
        ps_key = getattr(w, 'proof_s3_key', None)
        weekly_by_week[wk_key].append({
            'payment_date':      str(w.payment_date),
            'amount':            float(w.amount),
            'mode':              getattr(w, 'mode', 'CASH'),
            'notes':             getattr(w, 'notes', ''),
            'proof_url':         weekly_proof_map.get(ps_key) if ps_key else None,
            'is_missed_recovery': is_missed_recovery(w),
        })

    week_alloc_map = {}
    for a in all_earned_allocs:
        alloc_date = a.allocated_date
        wk_start   = alloc_date - timedelta(days=alloc_date.weekday())
        wk_end     = wk_start + timedelta(days=6)
        wk_key     = str(wk_start)
        wk_label   = f"{wk_start.strftime('%d %b')} – {wk_end.strftime('%d %b %Y')}"

        if wk_key not in week_alloc_map:
            week_alloc_map[wk_key] = {
                'week_start':       wk_key,
                'week_end':         str(wk_end),
                'week_label':       wk_label,
                'allocations':      [],
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                # Acres accumulators
                'alloc_acres':      Decimal('0'),
                'actual_acres':     Decimal('0'),
                'eff_acres':        Decimal('0'),
            }

        rate     = Decimal(str(a.mukkadam_rate or 0))
        exp_area = Decimal(str(a.allocated_area or 0))
        has_submission = a.report_submitted or a.work_status in ('completed', 'dispute')
        if has_submission:
            claimed  = a.mukkadam_claimed_area or a.actual_area_done
            act_area = Decimal(str(claimed)) if claimed is not None else exp_area
        else:
            act_area = exp_area
        eff_area = effective_area_for(a)

        exp_amt = (exp_area * rate).quantize(Decimal('0.01'))
        act_amt = (act_area * rate).quantize(Decimal('0.01'))

        week_alloc_map[wk_key]['total_expected'] += exp_amt
        week_alloc_map[wk_key]['total_actual']   += act_amt
        week_alloc_map[wk_key]['alloc_acres']    += exp_area
        week_alloc_map[wk_key]['actual_acres']   += act_area
        week_alloc_map[wk_key]['eff_acres']      += eff_area
        week_alloc_map[wk_key]['allocations'].append({
            'allocation_id':    a.id,
            'allocated_date':   str(alloc_date),
            'activity_name':    a.job_activity.activity.name,
            'plot_code':        a.job_activity.plot.plot_code if a.job_activity.plot else '—',
            'cluster_id':       a.cluster_id,
            'cluster_name':     a.cluster.name if a.cluster else '—',
            'job_id':           a.job_activity.job.job_id,
            'farmer_id':        a.job_activity.job.farmer.farmer_id if a.job_activity.job.farmer else None,
            'farmer_name':      a.job_activity.job.farmer.farmer_name if a.job_activity.job.farmer else '—',
            'allocated_area':   float(exp_area),
            'actual_area':      float(act_area),
            'effective_area':   float(eff_area),
            'rate':             float(rate),
            'expected_amount':  float(exp_amt),
            'actual_amount':    float(act_amt),
            'work_status':      getattr(a, 'work_status', 'work_not_started'),
            'report_submitted': a.report_submitted,
        })

    # Weeks with only payments
    for wk_key in set(weekly_by_week.keys()) - set(week_alloc_map.keys()):
        wk_start_dt = date.fromisoformat(wk_key)
        wk_end_dt   = wk_start_dt + timedelta(days=6)
        week_alloc_map[wk_key] = {
            'week_start':     wk_key,
            'week_end':       str(wk_end_dt),
            'week_label':     f"{wk_start_dt.strftime('%d %b')} – {wk_end_dt.strftime('%d %b %Y')}",
            'allocations':    [],
            'total_expected': Decimal('0'),
            'total_actual':   Decimal('0'),
            'alloc_acres':    Decimal('0'),
            'actual_acres':   Decimal('0'),
            'eff_acres':      Decimal('0'),
        }

    advance_amount  = float(assignment.advance_amount or 0) if assignment else 0.0
    running_balance = -advance_amount

    week_ledger = []
    for wk_key in sorted(week_alloc_map.keys()):
        wk = week_alloc_map[wk_key]

        earned_this_week = float(wk['total_actual'])
        running_balance += earned_this_week

        week_payments   = weekly_by_week.get(wk_key, [])
        week_paid       = sum(p['amount'] for p in week_payments)
        week_paid_ontime  = sum(p['amount'] for p in week_payments if not p['is_missed_recovery'])
        week_paid_missed  = sum(p['amount'] for p in week_payments if p['is_missed_recovery'])
        running_balance -= week_paid

        wk_end_dt = date.fromisoformat(wk['week_end'])
        is_past   = wk_end_dt < today

        # Farmer breakdown within this week
        week_by_farmer = {}
        for alloc in wk['allocations']:
            fname = alloc['farmer_name']
            if fname not in week_by_farmer:
                week_by_farmer[fname] = {
                    'farmer_name':           fname,
                    'farmer_id':             alloc.get('farmer_id'),
                    'total_expected':        0.0,
                    'total_actual':          0.0,
                    'total_allocated_acres': 0.0,
                    'total_actual_acres':    0.0,
                    'total_effective_acres': 0.0,
                    'allocations':           [],
                }
            week_by_farmer[fname]['total_expected']        += alloc['expected_amount']
            week_by_farmer[fname]['total_actual']          += alloc['actual_amount']
            week_by_farmer[fname]['total_allocated_acres'] += alloc['allocated_area']
            week_by_farmer[fname]['total_actual_acres']    += alloc['actual_area']
            week_by_farmer[fname]['total_effective_acres'] += alloc['effective_area']
            week_by_farmer[fname]['allocations'].append(alloc)

        # Settlement financials scoped to this week
        week_start_dt = date.fromisoformat(wk['week_start'])
        week_gross = week_net = week_settlement_paid = week_misc = Decimal('0')
        week_deposit = Decimal('0')
        seen_sids = set()
        for s in settlement_rows:
            if s['job_id'] in seen_sids:
                continue
            has_alloc_this_week = any(
                act.get('allocated_date') and
                week_start_dt <= date.fromisoformat(act['allocated_date']) <= wk_end_dt
                for act in s.get('activities', [])
            )
            if has_alloc_this_week:
                seen_sids.add(s['job_id'])
                week_gross           += Decimal(str(s['gross_amount']))
                week_deposit         += Decimal(str(s['deposit_held'])) if not s['deposit_released'] else Decimal('0')
                week_net             += Decimal(str(s['net_payable'])) if s['status'] == 'calculated' else Decimal('0')
                week_settlement_paid += Decimal(str(s['total_already_paid']))
                week_misc            += Decimal(str(s['total_misc']))

        week_ledger.append({
            'week_start':         wk['week_start'],
            'week_end':           wk['week_end'],
            'week_label':         wk['week_label'],
            'is_past':            is_past,
            'total_expected':     float(wk['total_expected']),
            'total_actual':       float(wk['total_actual']),
            'allocation_count':   len(wk['allocations']),
            # ── Acres ────────────────────────────────────────
            'acres': {
                'total_allocated_acres': float(wk['alloc_acres']),
                'total_actual_acres':    float(wk['actual_acres']),
                'total_effective_acres': float(wk['eff_acres']),
            },
            'allocations':        wk['allocations'],
            'by_farmer':          list(week_by_farmer.values()),
            'weekly_payments':    week_payments,
            'total_weekly_paid':  week_paid,
            'running_balance':    round(running_balance, 2),
            # ── Summary + payment breakdown ───────────────────
            'summary': {
                'gross_earned':      float(week_gross),
                'deposit_held':      float(week_deposit),
                'total_weekly_paid': week_paid,
                'total_misc':        float(week_misc),
                'net_payable_now':   float(week_net),
                'total_paid_out':    float(week_settlement_paid),
                'remaining':         round(float(week_net) - float(week_settlement_paid), 2),
                'running_balance':   round(running_balance, 2),
            },
            'payment_breakdown': {
                'advance_paid':           0.0,  # advance is one-time, not per-week
                'weekly_paid':            week_paid_ontime,
                'missed_weekly_paid':     week_paid_missed,
                'direct_settlement_paid': float(week_settlement_paid),
                'misc_deducted':          float(week_misc),
                'total_paid':             week_paid + float(week_settlement_paid),
            },
        })

    # ── CLUSTER-WISE SUMMARY ──────────────────────────────────────────
    cluster_summary_map = {}
    for a in all_earned_allocs:
        cid   = a.cluster_id
        cname = a.cluster.name if a.cluster else '—'
        if cid not in cluster_summary_map:
            cluster_summary_map[cid] = {
                'cluster_id':       cid,
                'cluster_name':     cname,
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'alloc_acres':      Decimal('0'),
                'actual_acres':     Decimal('0'),
                'eff_acres':        Decimal('0'),
                'gross_earned':     Decimal('0'),
                'deposit_held':     Decimal('0'),
                'advance_given':    Decimal(str(assignment.advance_amount or 0)) if assignment else Decimal('0'),
                'total_weekly_paid':Decimal('0'),
                'total_misc':       Decimal('0'),
                'net_payable_now':  Decimal('0'),
                'total_paid_out':   Decimal('0'),
            }
        rate     = Decimal(str(a.mukkadam_rate or 0))
        exp_area = Decimal(str(a.allocated_area or 0))
        has_submission = a.report_submitted or a.work_status in ('completed', 'dispute')
        if has_submission:
            claimed  = a.mukkadam_claimed_area or a.actual_area_done
            act_area = Decimal(str(claimed)) if claimed is not None else exp_area
        else:
            act_area = exp_area
        eff_area = effective_area_for(a)

        cluster_summary_map[cid]['total_expected']   += (exp_area * rate).quantize(Decimal('0.01'))
        cluster_summary_map[cid]['total_actual']     += (act_area * rate).quantize(Decimal('0.01'))
        cluster_summary_map[cid]['allocation_count'] += 1
        cluster_summary_map[cid]['alloc_acres']      += exp_area
        cluster_summary_map[cid]['actual_acres']     += act_area
        cluster_summary_map[cid]['eff_acres']        += eff_area

    for s in settlement_rows:
        for act in s.get('activities', []):
            cid = act.get('cluster_id')
            if cid and cid in cluster_summary_map:
                cluster_summary_map[cid]['gross_earned']    += Decimal(str(s['gross_amount']))
                cluster_summary_map[cid]['deposit_held']    += Decimal(str(s['deposit_held'])) if not s['deposit_released'] else Decimal('0')
                cluster_summary_map[cid]['net_payable_now'] += Decimal(str(s['net_payable'])) if s['status'] == 'calculated' else Decimal('0')
                cluster_summary_map[cid]['total_paid_out']  += Decimal(str(s['total_already_paid']))
                cluster_summary_map[cid]['total_misc']      += Decimal(str(s['total_misc']))
                break

    total_actual_all = sum(v['total_actual'] for v in cluster_summary_map.values()) or Decimal('1')
    total_weekly_dec = Decimal(str(sum(float(w.amount) for w in weekly_qs)))
    total_weekly_missed_dec = Decimal(str(total_weekly_missed_recovery))

    by_cluster = []
    for cdata in cluster_summary_map.values():
        proportion       = cdata['total_actual'] / total_actual_all
        weekly_prop      = (total_weekly_dec * proportion).quantize(Decimal('0.01'))
        missed_prop      = (total_weekly_missed_dec * proportion).quantize(Decimal('0.01'))
        ontime_prop      = weekly_prop - missed_prop
        remaining        = float(cdata['net_payable_now']) - float(cdata['total_paid_out'])
        advance_prop     = (Decimal(str(advance_amount)) * proportion).quantize(Decimal('0.01'))

        by_cluster.append({
            'cluster_id':       cdata['cluster_id'],
            'cluster_name':     cdata['cluster_name'],
            'allocation_count': cdata['allocation_count'],
            'total_expected':   float(cdata['total_expected']),
            'total_actual':     float(cdata['total_actual']),
            'variance':         float(cdata['total_actual'] - cdata['total_expected']),
            'acres': {
                'total_allocated_acres': float(cdata['alloc_acres']),
                'total_actual_acres':    float(cdata['actual_acres']),
                'total_effective_acres': float(cdata['eff_acres']),
            },
            'summary': {
                'gross_earned':      float(cdata['gross_earned']),
                'deposit_held':      float(cdata['deposit_held']),
                'advance_given':     float(cdata['advance_given']),
                'total_weekly_paid': float(weekly_prop),
                'total_misc':        float(cdata['total_misc']),
                'net_payable_now':   float(cdata['net_payable_now']),
                'total_paid_out':    float(cdata['total_paid_out']),
                'remaining':         round(remaining, 2),
            },
            'payment_breakdown': {
                'advance_paid':           float(advance_prop),
                'weekly_paid':            float(ontime_prop),
                'missed_weekly_paid':     float(missed_prop),
                'direct_settlement_paid': float(cdata['total_paid_out']),
                'misc_deducted':          float(cdata['total_misc']),
                'total_paid':             float(advance_prop + weekly_prop + cdata['total_paid_out']),
            },
        })

    # ── FARMER-WISE SUMMARY ───────────────────────────────────────────
    farmer_summary_map = {}
    for a in all_earned_allocs:
        farmer = a.job_activity.job.farmer if a.job_activity.job else None
        fname  = farmer.farmer_name if farmer else '—'
        fid    = farmer.farmer_id   if farmer else None
        jid    = str(a.job_activity.job.job_id)

        if fname not in farmer_summary_map:
            farmer_summary_map[fname] = {
                'farmer_id':        fid,
                'farmer_name':      fname,
                'total_expected':   Decimal('0'),
                'total_actual':     Decimal('0'),
                'allocation_count': 0,
                'alloc_acres':      Decimal('0'),
                'actual_acres':     Decimal('0'),
                'eff_acres':        Decimal('0'),
                'jobs':             {},
            }

        rate     = Decimal(str(a.mukkadam_rate or 0))
        exp_area = Decimal(str(a.allocated_area or 0))
        has_submission = a.report_submitted or a.work_status in ('completed', 'dispute')
        if has_submission:
            claimed  = a.mukkadam_claimed_area or a.actual_area_done
            act_area = Decimal(str(claimed)) if claimed is not None else exp_area
        else:
            act_area = exp_area
        eff_area = effective_area_for(a)

        exp_amt = (exp_area * rate).quantize(Decimal('0.01'))
        act_amt = (act_area * rate).quantize(Decimal('0.01'))

        farmer_summary_map[fname]['total_expected']   += exp_amt
        farmer_summary_map[fname]['total_actual']     += act_amt
        farmer_summary_map[fname]['allocation_count'] += 1
        farmer_summary_map[fname]['alloc_acres']      += exp_area
        farmer_summary_map[fname]['actual_acres']     += act_area
        farmer_summary_map[fname]['eff_acres']        += eff_area

        if jid not in farmer_summary_map[fname]['jobs']:
            farmer_summary_map[fname]['jobs'][jid] = {
                'job_id':            jid,
                'total_expected':    Decimal('0'),
                'total_actual':      Decimal('0'),
                'allocation_count':  0,
                'alloc_acres':       Decimal('0'),
                'actual_acres':      Decimal('0'),
                'eff_acres':         Decimal('0'),
                'settlement_status': next((s['status'] for s in settlement_rows if s['job_id'] == jid), 'pending'),
                'net_payable':       next((s['net_payable'] for s in settlement_rows if s['job_id'] == jid), 0.0),
            }
        farmer_summary_map[fname]['jobs'][jid]['total_expected']   += exp_amt
        farmer_summary_map[fname]['jobs'][jid]['total_actual']     += act_amt
        farmer_summary_map[fname]['jobs'][jid]['allocation_count'] += 1
        farmer_summary_map[fname]['jobs'][jid]['alloc_acres']      += exp_area
        farmer_summary_map[fname]['jobs'][jid]['actual_acres']     += act_area
        farmer_summary_map[fname]['jobs'][jid]['eff_acres']        += eff_area

    total_actual_farmers = sum(
        float(fd['total_actual']) for fd in farmer_summary_map.values()
    ) or 1.0
    total_weekly_all = sum(float(w.amount) for w in weekly_qs)

    by_farmer = []
    for fdata in sorted(farmer_summary_map.values(), key=lambda x: x['farmer_name']):
        farmer_gross = farmer_deposit = farmer_net = farmer_paid = farmer_misc = Decimal('0')

        jobs_list = []
        for jdata in fdata['jobs'].values():
            jid = jdata['job_id']
            s   = next((sr for sr in settlement_rows if sr['job_id'] == jid), None)
            job_gross   = Decimal(str(s['gross_amount']))       if s else Decimal('0')
            job_deposit = Decimal(str(s['deposit_held']))       if (s and not s['deposit_released']) else Decimal('0')
            job_net     = Decimal(str(s['net_payable']))        if (s and s['status'] == 'calculated') else Decimal('0')
            job_paid    = Decimal(str(s['total_already_paid'])) if s else Decimal('0')
            job_misc    = Decimal(str(s['total_misc']))         if s else Decimal('0')
            job_adv     = Decimal(str(s['advance_deducted']))   if s else Decimal('0')
            job_wkly    = Decimal(str(s['weekly_payments_deducted'])) if s else Decimal('0')

            farmer_gross   += job_gross
            farmer_deposit += job_deposit
            farmer_net     += job_net
            farmer_paid    += job_paid
            farmer_misc    += job_misc

            jobs_list.append({
                'job_id':            jid,
                'allocation_count':  jdata['allocation_count'],
                'total_expected':    float(jdata['total_expected']),
                'total_actual':      float(jdata['total_actual']),
                'variance':          float(jdata['total_actual'] - jdata['total_expected']),
                'settlement_status': jdata['settlement_status'],
                'acres': {
                    'total_allocated_acres': float(jdata['alloc_acres']),
                    'total_actual_acres':    float(jdata['actual_acres']),
                    'total_effective_acres': float(jdata['eff_acres']),
                },
                'summary': {
                    'gross_earned':    float(job_gross),
                    'deposit_held':    float(job_deposit),
                    'net_payable_now': float(job_net),
                    'total_paid_out':  float(job_paid),
                    'total_misc':      float(job_misc),
                    'remaining':       round(float(job_net) - float(job_paid), 2),
                },
                'payment_breakdown': {
                    'advance_paid':           float(job_adv),
                    'weekly_paid':            float(job_wkly),
                    'missed_weekly_paid':     0.0,
                    'direct_settlement_paid': float(job_paid),
                    'misc_deducted':          float(job_misc),
                    'total_paid':             float(job_adv + job_wkly + job_paid),
                },
            })

        farmer_proportion   = float(fdata['total_actual']) / total_actual_farmers
        f_weekly_total      = Decimal(str(round(total_weekly_all * farmer_proportion, 2)))
        f_weekly_missed     = Decimal(str(round(total_weekly_missed_recovery * farmer_proportion, 2)))
        f_weekly_ontime     = f_weekly_total - f_weekly_missed
        f_advance           = Decimal(str(round(advance_amount * farmer_proportion, 2)))
        farmer_remaining    = float(farmer_net) - float(farmer_paid)

        by_farmer.append({
            'farmer_id':        fdata['farmer_id'],
            'farmer_name':      fdata['farmer_name'],
            'allocation_count': fdata['allocation_count'],
            'total_expected':   float(fdata['total_expected']),
            'total_actual':     float(fdata['total_actual']),
            'variance':         float(fdata['total_actual'] - fdata['total_expected']),
            'acres': {
                'total_allocated_acres': float(fdata['alloc_acres']),
                'total_actual_acres':    float(fdata['actual_acres']),
                'total_effective_acres': float(fdata['eff_acres']),
            },
            'summary': {
                'gross_earned':      float(farmer_gross),
                'deposit_held':      float(farmer_deposit),
                'advance_given':     float(assignment.advance_amount or 0) if assignment else 0,
                'total_weekly_paid': float(f_weekly_total),
                'total_misc':        float(farmer_misc),
                'net_payable_now':   float(farmer_net),
                'total_paid_out':    float(farmer_paid),
                'remaining':         round(farmer_remaining, 2),
            },
            'payment_breakdown': {
                'advance_paid':           float(f_advance),
                'weekly_paid':            float(f_weekly_ontime),
                'missed_weekly_paid':     float(f_weekly_missed),
                'direct_settlement_paid': float(farmer_paid),
                'misc_deducted':          float(farmer_misc),
                'total_paid':             float(f_advance + f_weekly_total + farmer_paid),
            },
            'jobs': jobs_list,
        })

    # ── TRANSACTION HISTORY ───────────────────────────────────────────
    txn_history = []
    if assignment and assignment.advance_amount and float(assignment.advance_amount) > 0:
        advance_date = str(assignment.joined_at.date()) if assignment.joined_at else str(today)
        txn_history.append({
            'type': 'advance', 'date': advance_date, 'label': 'Advance Given',
            'amount': -float(assignment.advance_amount), 'mode': 'CASH',
            'notes': '', 'proof_url': None, 'icon': '💰',
        })
    for w in weekly_qs:
        ps_key = getattr(w, 'proof_s3_key', None)
        missed = is_missed_recovery(w)
        txn_history.append({
            'type':               'weekly',
            'date':               str(w.payment_date),
            'label':              'Late Weekly Payment (Missed Recovery)' if missed else 'Weekly Payment',
            'amount':             -float(w.amount),
            'mode':               getattr(w, 'mode', 'CASH'),
            'notes':              getattr(w, 'notes', ''),
            'proof_url':          weekly_proof_map.get(ps_key) if ps_key else None,
            'icon':               '🔴📅' if missed else '📅',
            'is_missed_recovery': missed,
        })
    for p in all_payments:
        ps_key = getattr(p, 'proof_s3_key', None)
        if p.settlement and p.settlement.job:
            jid   = str(p.settlement.job.job_id)
            fname = p.settlement.job.farmer.farmer_name if p.settlement.job.farmer else ''
            pcode = p.settlement.plot.plot_code if p.settlement.plot else ''
            label = f"Settlement Paid — Job #{jid} {fname} {pcode}".strip()
        else:
            label = 'Settlement Payment'
        txn_history.append({
            'type': 'settlement_payment', 'date': str(p.paid_at.date()) if p.paid_at else str(today),
            'label': label, 'amount': float(p.amount),
            'mode': getattr(p, 'mode', 'CASH'), 'notes': getattr(p, 'notes', ''),
            'proof_url': settle_proof_map.get(ps_key) if ps_key else None, 'icon': '✅',
        })
    for c in all_misc:
        ps_key = getattr(c, 'proof_s3_key', None)
        txn_history.append({
            'type': 'misc_deduction', 'date': str(c.created_at.date()),
            'label': f"Misc Deduction — {c.reason or 'No reason'}",
            'amount': -float(c.amount), 'mode': '—',
            'notes': c.reason or '',
            'proof_url': misc_proof_map.get(ps_key) if ps_key else None, 'icon': '⚠️',
        })

    txn_history.sort(key=lambda x: x['date'])
    running = 0.0
    for txn in txn_history:
        running += txn['amount']
        txn['running_balance'] = round(running, 2)

    # ── SUMMARY GRID ──────────────────────────────────────────────────
    total_gross    = sum(float(s['gross_amount'])       for s in settlement_rows)
    total_net      = sum(float(s['net_payable'])        for s in settlement_rows if s['status'] == 'calculated')
    total_paid_out = sum(float(s['total_already_paid']) for s in settlement_rows)
    total_misc_all = sum(float(s['total_misc'])         for s in settlement_rows)
    total_weekly   = sum(float(w.amount)                for w in weekly_qs)
    deposit_held_total = sum(
        float(s['deposit_held']) for s in settlement_rows if not s['deposit_released']
    )
    # Overall acres
    all_alloc_acres  = sum(float(a.allocated_area or 0)                                          for a in all_earned_allocs)
    all_actual_acres = sum(float(a.mukkadam_claimed_area or a.actual_area_done or a.allocated_area) for a in all_earned_allocs)
    all_eff_acres    = sum(float(effective_area_for(a))                                           for a in all_earned_allocs)

    # Assignments array
    assignments_list = []
    for asgn in all_assignments:
        missed_dates = sorted(str(d) for d in _missed_dates_for(asgn))
        assignments_list.append({
            'assignment_id':            asgn.id,
            'cluster_id':               asgn.cluster_id,
            'cluster_name':             asgn.cluster.name if asgn.cluster else '—',
            'advance_amount':           float(asgn.advance_amount or 0),
            'weekly_amount':            float(asgn.weekly_amount or 0),
            'weekly_payment_day':       asgn.weekly_payment_day,
            'weekly_payment_day_label': asgn.get_weekly_payment_day_display() if asgn.weekly_payment_day is not None else None,
            'already_paid_today':       MukkadamWeeklyPayment.objects.filter(assignment=asgn, payment_date=today).exists(),
            'missed_weekly_dates':      missed_dates,
            'mukkadam_type':            asgn.mukkadam_type,
        })

    primary_assignment_data = next(
        (a for a in assignments_list if a['assignment_id'] == (assignment.id if assignment else None)),
        assignments_list[0] if assignments_list else None
    )

    return Response({
        'mukkadam_id':   mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'mobile':        mukkadam.mobile_numbers,
        'assignments':   assignments_list,
        # 'assignment':    primary_assignment_data,  # backward compat

        'summary': {
            'gross_earned':      total_gross,
            'deposit_held':      round(deposit_held_total, 2),
            'advance_given':     float(assignment.advance_amount or 0) if assignment else 0,
            'total_weekly_paid': total_weekly,
            'total_misc':        total_misc_all,
            'net_payable_now':   total_net,
            'total_paid_out':    total_paid_out,
            'remaining':         round(total_net - total_paid_out, 2),
            'closing_balance':   round(running, 2),
            'allocation_count':  all_earned_allocs.count(), 
            # Acres
            'acres': {
                'total_allocated_acres': round(all_alloc_acres, 2),
                'total_actual_acres':    round(all_actual_acres, 2),
                'total_effective_acres': round(all_eff_acres, 2),
            },
            # Payment breakdown
            'payment_breakdown': {
                'advance_paid':           float(assignment.advance_amount or 0) if assignment else 0,
                'weekly_paid':            total_weekly_on_time,
                'missed_weekly_paid':     total_weekly_missed_recovery,
                'direct_settlement_paid': total_paid_out,
                'misc_deducted':          total_misc_all,
                'total_paid':             (float(assignment.advance_amount or 0) if assignment else 0)
                                          + total_weekly + total_paid_out,
            },
        },

        'by_cluster':          by_cluster,
        'by_farmer':           by_farmer,
        'week_ledger':         week_ledger,
        'settlements':         settlement_rows,
        'transaction_history': txn_history,
    })