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
    Returns only upcoming/future jobs assigned to the mukkadam.
    Includes IDs for Farmer, Mukkadam, and specific Allocations + Farmer contact.
    """
    mobile = request.query_params.get('mobile', '').strip()
    if not mobile:
        return Response({'error': 'mobile required'}, status=status.HTTP_400_BAD_REQUEST)

    mukkadam = Mukkadam.objects.filter(mobile_numbers__icontains=mobile).first()
    if not mukkadam:
        return Response({'error': 'Mukkadam not found'}, status=status.HTTP_404_NOT_FOUND)

    today = date.today()
    
    # Filter for allocations scheduled for today or later
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
            # Lat/Lng priority for navigation
            plot = alloc.job_activity.plot or job.plot
            
            jobs_map[jid] = {
                'job_id': jid,
                'farmer_id': job.farmer.farmer_id,
                'farmer_name': job.farmer.farmer_name,
                'farmer_phone': job.farmer.phone_number,  # ✅ Added Farmer Phone
                'scheduled_date': str(job.scheduled_date),
                'crop': f"{job.crop_name} ({job.variety})",
                'location': {
                    'address': job.farmer.location,
                    'lat': float(plot.latitude) if plot and plot.latitude else float(job.latitude) if job.latitude else None,
                    'lng': float(plot.longitude) if plot and plot.longitude else float(job.longitude) if job.longitude else None,
                },
                'activities': [],
                'projected_earnings': 0.0
            }
        
        projected = float(alloc.allocated_area * alloc.mukkadam_rate)
        jobs_map[jid]['projected_earnings'] += round(projected, 2)
        
        jobs_map[jid]['activities'].append({
            'allocation_id': alloc.id,
            'name': alloc.job_activity.activity.name,
            'date': str(alloc.allocated_date),
            'area': float(alloc.allocated_area),
            'rate': float(alloc.mukkadam_rate),
            'earning': round(projected, 2),
        })

    return Response({
        'mukkadam_id': mukkadam.mukkadam_id,
        'mukkadam_name': mukkadam.mukkadam_name,
        'total_future_jobs': len(jobs_map),
        'total_projected_earning': round(sum(j['projected_earnings'] for j in jobs_map.values()), 2),
        'jobs': list(jobs_map.values())
    })
from decimal import Decimal
from django.db.models import Sum
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from tender.models import Mukkadam, MukkadamJobSettlement, Allocation, MukkadamMiscCost

@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_settlement_history(request):
    """
    Continuous Balance Chain Logic:
    Each job's calculation releases the PREVIOUS job's deposit and 
    incorporates the PREVIOUS running balance.
    Includes Global Advance deduction total at the top level.
    """
    mobile = request.query_params.get('mobile', '').strip()
    mukkadam = Mukkadam.objects.filter(mobile_numbers__icontains=mobile).first()
    if not mukkadam:
        return Response({'error': 'Mukkadam not found'}, status=404)

    # 1. Fetch settlements in order of creation/completion
    settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam
    ).select_related('job', 'job__farmer').order_by('created_at')

    history_data = []
    
    # --- ACCOUNT CHAIN VARIABLES ---
    running_balance = Decimal('0')
    previous_job_deposit = Decimal('0')

    # --- GLOBAL AGGREGATORS ---
    total_activities_all_time = 0
    total_acres_all_time = Decimal('0')
    total_gross_earned_all_time = Decimal('0')
    total_weekly_received_all_time = Decimal('0')
    total_misc_deducted_all_time = Decimal('0')
    total_advance_deducted_all_time = Decimal('0')  # ✅ Added aggregator for advance

    for s in settlements:
        # 2. Get Work Details for the current job
        allocations = Allocation.objects.filter(
            mukkadam=mukkadam,
            job_activity__job=s.job,
        ).select_related('job_activity__activity', 'job_activity__plot')

        work_details = []
        job_acres = Decimal('0')
        job_activity_count = allocations.count()

        for alloc in allocations:
            effective_area = Decimal(str(alloc.actual_area_done)) if (alloc.farmer_agreed and alloc.actual_area_done is not None) else Decimal(str(alloc.allocated_area or 0))
            
            gross_act = (effective_area * Decimal(str(alloc.mukkadam_rate or 0))).quantize(Decimal('0.01'))
            job_acres += effective_area
            
            work_details.append({
                'activity_name': alloc.job_activity.activity.name,
                'plot_code': alloc.job_activity.plot.plot_code if alloc.job_activity.plot else '—',
                'allocated_date': str(alloc.allocated_date),
                'area': float(effective_area),
                'rate': float(alloc.mukkadam_rate),
                'amount': float(gross_act),
            })

        # 3. Handle Misc Costs
        misc_total = MukkadamMiscCost.objects.filter(
            mukkadam=mukkadam, 
            job=s.job
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # 4. THE CONTINUOUS CALCULATION
        current_payable_90pct = s.payable_amount 
        current_deposit_held = s.gross_amount * (s.deposit_percent / 100)
        
        # Money In = Current 90% + Released Previous Deposit + Previous Running Balance
        money_in = current_payable_90pct + previous_job_deposit + running_balance
        
        # Deduct current liabilities
        current_deductions = s.advance_deducted + s.weekly_payments_deducted + misc_total
        
        final_net_for_this_job = money_in - current_deductions

        # 5. Update Global Totals
        total_activities_all_time += job_activity_count
        total_acres_all_time += job_acres
        total_gross_earned_all_time += s.gross_amount
        total_weekly_received_all_time += s.weekly_payments_deducted
        total_misc_deducted_all_time += misc_total
        total_advance_deducted_all_time += s.advance_deducted # ✅ Added to global aggregator

        history_data.append({
            'job_id': s.job.job_id,
            'farmer_name': s.job.farmer.farmer_name,
            'status': s.status,
            'work_summary': {
                'total_acres': float(job_acres),
                'activity_count': job_activity_count,
                'details': work_details
            },
            'financials': {
                'gross_100pct': float(s.gross_amount),
                'payable_90pct': float(current_payable_90pct),
                'deposit_held_this_job': float(current_deposit_held),
                'adjustments': {
                    'carry_forward_balance': float(running_balance),
                    'released_prev_deposit': float(previous_job_deposit),
                },
                'deductions': {
                    'advance': float(s.advance_deducted),
                    'weekly': float(s.weekly_payments_deducted),
                    'misc': float(misc_total),
                },
                'final_net_payable': float(final_net_for_this_job)
            },
            'dates': {
                'calculated_at': str(s.calculated_at.date()) if s.calculated_at else None,
                'paid_at': str(s.paid_at.date()) if s.paid_at else None,
            }
        })

        # 6. PASS VARIABLES TO NEXT LOOP
        running_balance = final_net_for_this_job
        previous_job_deposit = current_deposit_held

    # 7. Final Response
    return Response({
        'mukkadam_name': mukkadam.mukkadam_name,
        'global_work_summary': {
            'total_activities_done': total_activities_all_time,
            'total_acres_completed': float(total_acres_all_time.quantize(Decimal('0.01'))),
            'total_gross_earnings': float(total_gross_earned_all_time.quantize(Decimal('0.01'))),
            'current_active_deposit': float(previous_job_deposit.quantize(Decimal('0.01'))),
            'total_advance_deducted': float(total_advance_deducted_all_time.quantize(Decimal('0.01'))), # ✅ Added at top
            'total_weekly_payments_received': float(total_weekly_received_all_time.quantize(Decimal('0.01'))),
            'total_miscellaneous_payments': float(total_misc_deducted_all_time.quantize(Decimal('0.01'))),
            'final_closing_balance': float(running_balance.quantize(Decimal('0.01')))
        },
        'history': history_data
    })

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from decimal import Decimal


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