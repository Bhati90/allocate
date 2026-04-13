from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.db import transaction
from datetime import datetime, timedelta
from .models import *
from rest_framework.permissions import IsAuthenticated
from .nr import ops, err, ctx, ops_bg,err_bg

from .serializers import *
from .utils import check_can_allocate, get_mukkadam_availability, get_mukkadam_remaining_workers
# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Prefetch
from django.db import transaction
from datetime import datetime, timedelta
from .models import (
    ActivityCatalog, Job, JobActivity, JobBooking, FarmerPayment,
    Mukkadam, MukkadamActivityRate, MukkadamAvailability,
    Allocation, Farmer
)
from .serializers import (
    ActivityCatalogSerializer, JobSerializer, MukkadamSerializer,
    JobActivitySerializer, MukkadamAvailabilitySerializer,
    AllocationSerializer, MukkadamActivityRateSerializer,ClusterSerializer
)
from rest_framework.permissions import AllowAny
from .serializers import FarmerSerializer, JobSerializer
# tender/auth.py
from rest_framework.authentication import SessionAuthentication
import logging

logger = logging.getLogger(__name__)
import os
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # disable CSRF check
from rest_framework.permissions import IsAuthenticatedOrReadOnly
def about(request):
    return render(request,'tender/index.html')


# views.py - Update cluster_activity_calendar

from rest_framework import generics
from django.contrib.auth.models import User
from rest_framework.views import APIView
class UserListAPIView(generics.ListAPIView):
    # Use select_related to improve performance (joins the tables in 1 query)
    queryset = User.objects.select_related('profile').all()
    serializer_class = UserDetailSerializer


class UserProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user

        try:
            # ✅ Get UserProfile to check role
            profile = user.profile

            return Response({
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name,
                'mobile_number': profile.mobile_number,
                'role': profile.role,
                'is_admin': profile.role == 'admin',  # ✅ Check role field
                'is_verified': profile.is_mobile_verified
            })
        except UserProfile.DoesNotExist:
            return Response({
                'error': 'User profile not found'
            }, status=status.HTTP_404_NOT_FOUND)



# tender/views.py  — full cluster_activity_calendar

@api_view(['GET', 'POST'])
def cluster_activity_calendar(request, cluster_id):
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
    except Cluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)

    # ── GET ──────────────────────────────────────────────────────────────
    if request.method == 'GET':
        all_activities = ActivityCatalog.objects.all()

        cluster_rates = {
            r.activity_id: r
            for r in ClusterActivityRate.objects.filter(cluster=cluster)
        }
        cluster_gaps = {
            r.activity_id: r
            for r in ClusterActivityScheduleRule.objects.filter(cluster=cluster)
        }
        cluster_mukkadam_rates = {
            r.activity_id: r
            for r in ClusterMukkadamActivityRate.objects.filter(cluster=cluster)
        }
        global_rules = {
            r.activity_id: r
            for r in ActivityScheduleRule.objects.all()
        }

        calendar = []
        for activity in all_activities:
            cluster_rate = cluster_rates.get(activity.id)
            cluster_gap  = cluster_gaps.get(activity.id)
            global_rule  = global_rules.get(activity.id)
            mukkadam_cr  = cluster_mukkadam_rates.get(activity.id)

            # Farmer rate
            farmer_rate     = float(cluster_rate.rate_per_acre) if cluster_rate else float(activity.default_rate_per_acre)
            rate_overridden = bool(cluster_rate)

            # Gap days
            gap_days       = (
                cluster_gap.gap_days if cluster_gap
                else global_rule.gap_days if global_rule
                else activity.default_gap_days
            )
            gap_overridden = bool(cluster_gap)

            # Mukkadam rate
            mukkadam_rate             = float(mukkadam_cr.rate_per_acre) if mukkadam_cr else farmer_rate * 0.8
            mukkadam_rate_overridden  = bool(mukkadam_cr)

            # Productivity
            global_productivity = float(
                getattr(activity, 'default_productivity_per_worker', 0.150) or 0.150
            )
            if mukkadam_cr and mukkadam_cr.productivity_per_worker:
                mukkadam_productivity   = float(mukkadam_cr.productivity_per_worker)
                productivity_overridden = True
            else:
                mukkadam_productivity   = global_productivity
                productivity_overridden = False

            calendar.append({
                'activity_id':              activity.id,
                'activity_name':            activity.name,
                'activity_type':            activity.activity_type,
                'rate_per_acre':            farmer_rate,
                'rate_overridden':          rate_overridden,
                'gap_days':                 gap_days,
                'gap_overridden':           gap_overridden,
                'mukkadam_rate_per_acre':   mukkadam_rate,
                'mukkadam_rate_overridden': mukkadam_rate_overridden,
                'global_productivity':      global_productivity,
                'mukkadam_productivity':    mukkadam_productivity,
                'productivity_overridden':  productivity_overridden,
                'is_strict':                activity.is_strict,
                'phase_order':              global_rule.phase_order if global_rule else 0,
            })

        calendar.sort(key=lambda x: x['phase_order'])

        return Response({
            'cluster_id':   cluster.id,
            'cluster_name': cluster.name,
            'activities':   calendar,
        })

    # ── POST ─────────────────────────────────────────────────────────────
    elif request.method == 'POST':
        from .utils import cascade_gap_change_for_cluster

        rate_overrides              = request.data.get('rate_overrides', [])
        gap_overrides               = request.data.get('gap_overrides', [])
        mukkadam_rate_overrides     = request.data.get('mukkadam_rate_overrides', [])
        global_productivity_updates = request.data.get('global_productivity_updates', [])

        all_updated = []
        all_skipped = []

        # ── Farmer rates ──────────────────────────────────────────────
        for override in rate_overrides:
            activity_id = override.get('activity_id')
            rate        = override.get('rate_per_acre')
            if not activity_id or rate is None:
                continue
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)
                ClusterActivityRate.objects.update_or_create(
                    cluster=cluster, activity=activity,
                    defaults={'rate_per_acre': rate}
                )
            except ActivityCatalog.DoesNotExist:
                continue

        # ── Gap days + cascade ────────────────────────────────────────
        for override in gap_overrides:
            activity_id = override.get('activity_id')
            gap_days    = override.get('gap_days')
            if not activity_id or gap_days is None:
                continue
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)

                # 1. Save new gap override
                ClusterActivityScheduleRule.objects.update_or_create(
                    cluster=cluster, activity=activity,
                    defaults={'gap_days': gap_days}
                )

                # 2. Cascade to pending JobActivities
                updated, skipped = cascade_gap_change_for_cluster(
                    cluster, activity, int(gap_days)
                )
                all_updated.extend(updated)
                all_skipped.extend(skipped)

            except ActivityCatalog.DoesNotExist:
                continue

        # ── Mukkadam rates + productivity override ────────────────────
        for override in mukkadam_rate_overrides:
            activity_id  = override.get('activity_id')
            rate         = override.get('rate_per_acre')
            productivity = override.get('productivity_per_worker')
            if not activity_id or rate is None or productivity is None:
                continue
            try:
                activity = ActivityCatalog.objects.get(pk=activity_id)
                ClusterMukkadamActivityRate.objects.update_or_create(
                    cluster=cluster, activity=activity,
                    defaults={
                        'rate_per_acre':           rate,
                        'productivity_per_worker': productivity,
                    }
                )
            except ActivityCatalog.DoesNotExist:
                continue

        # ── Global productivity ───────────────────────────────────────
        for upd in global_productivity_updates:
            activity_id  = upd.get('activity_id')
            productivity = upd.get('default_productivity_per_worker')
            if not activity_id or productivity is None:
                continue
            try:
                ActivityCatalog.objects.filter(pk=activity_id).update(
                    default_productivity_per_worker=productivity
                )
            except Exception:
                continue

        return Response({
            'success':         True,
            'message':         'Calendar updated',
            'dates_updated':   len(all_updated),
            'dates_skipped':   len(all_skipped),
            'updated_details': all_updated,
            'skipped_details': all_skipped,
        }) 
@api_view(['GET', 'POST'])
def global_activity_catalog(request):
    if request.method == 'GET':
        activities = ActivityCatalog.objects.all()
        catalog_data = []
        
        for activity in activities:
            global_rule = ActivityScheduleRule.objects.filter(activity=activity).first()
            
            # 1. Use the actual model fields for the master defaults
            farmer_rate = float(activity.default_rate_per_acre)
            
            # Use estimated_workers_per_acre as the Global productivity default
            # Use a fallback only if the field is null
            mukkadam_productivity = float(activity.estimated_workers_per_acre) if activity.estimated_workers_per_acre else 0.150
            
            # Global Gap Days fallback logic
            gap_days = global_rule.gap_days if global_rule else activity.default_gap_days
            
            catalog_data.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'activity_type': activity.activity_type,
                'default_rate_per_acre': farmer_rate,
                'default_gap_days': gap_days,
                # For Global, we usually keep the 80% logic or 
                # you can add a 'default_mukkadam_rate' field to ActivityCatalog
                'mukkadam_default_rate': farmer_rate * 0.8, 
                'mukkadam_default_productivity': mukkadam_productivity, # <--- FIXED
                'is_strict': activity.is_strict,
                'phase_order': global_rule.phase_order if global_rule else 0,
            })

        catalog_data.sort(key=lambda x: x['phase_order'])
        return Response({'activities': catalog_data})

@api_view(['GET'])
def get_cluster_info(request, cluster_id):
    """
    GET: Get cluster details with location info
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        return Response({
            'id': cluster.id,
            'name': cluster.name,
            'district': cluster.district,
            'taluka': cluster.taluka,
            'village': cluster.village,
        })
    except Cluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)
@api_view(['GET'])
@permission_classes([AllowAny])
def cluster_insights(request):
    from datetime import date, timedelta
    from decimal import Decimal
    from collections import defaultdict

    # ── Accept optional start_date for week navigation ─────────────────────
    start_date_str = request.GET.get('start_date')
    if start_date_str:
        try:
            today = date.fromisoformat(start_date_str)
        except ValueError:
            today = date.today()
    else:
        today = date.today()

    actual_today = date.today()          # used for is_today flag
    tomorrow  = today + timedelta(days=1)
    week_days = [today + timedelta(days=i) for i in range(7)]

    def fmt_date(d):
        return d.strftime('%d %b').lstrip('0')
    
    from datetime import date
    import calendar

    # ── Week range (Mon–Sun of current actual week) ───────────────────────
    actual_today = date.today()
    week_start = actual_today - timedelta(days=actual_today.weekday())  # Monday
    week_end   = week_start + timedelta(days=6)                          # Sunday

    # ── Month range ───────────────────────────────────────────────────────
    month_start = actual_today.replace(day=1)
    month_end   = actual_today.replace(
        day=calendar.monthrange(actual_today.year, actual_today.month)[1]
    )

    # ── helper: canonical unalloc count (deduped, no lost, no zero-area) ───
    def unalloc_count_qs(base_filter: dict):
        return (
            JobActivity.objects
            .filter(
                allocation_status='pending',
                total_area__gt=0,
                is_lost=False,
                **base_filter,
            )
            .values('job', 'plot', 'api_activity_id')
            .distinct()
            .count()
        )

    clusters = Cluster.objects.all().order_by('name')
    # FIXED — matches activity-dashboard logic:
    activity_qs = JobActivity.objects.filter(
        job__booking_type__in=["tender", "ondemand"],
        total_area__gt=0,
        is_lost=False,
    )
    totalactivities = activity_qs.values("job", "plot", "api_activity_id").distinct().count()

    # ── Global KPIs ────────────────────────────────────────────────────────
    total_farmers  = Farmer.objects.count()
    total_area     = JobActivity.objects.filter(total_area__gt=0).aggregate(s=models.Sum('total_area'))['s'] or Decimal('0')
    allocated_area = JobActivity.objects.filter(total_area__gt=0).aggregate(s=models.Sum('allocated_area'))['s'] or Decimal('0')
    total_jobs     = Job.objects.count()
    total_plots    = Plot.objects.count()
    
    # ── Global daily unallocated + crew ────────────────────────────────────
    global_daily = []
    for d in week_days:
        unalloc = unalloc_count_qs({'scheduled_date': d})
        crew = Allocation.objects.filter(
            allocated_date=d,
        ).aggregate(s=models.Sum('allocated_workers'))['s'] or 0
        global_daily.append({
            'date':        str(d),
            'label':       fmt_date(d),
            'day_name':    d.strftime('%a'),
            'unallocated': unalloc,
            'crew':        int(crew),
        })

    # ── Per-cluster data ───────────────────────────────────────────────────
    cluster_data = []

    for c in clusters:
        c_total_area = JobActivity.objects.filter(
            plot__clusters=c, total_area__gt=0
        ).aggregate(s=models.Sum('total_area'))['s'] or Decimal('0')

        c_alloc_area = JobActivity.objects.filter(
            plot__clusters=c, total_area__gt=0
        ).aggregate(s=models.Sum('allocated_area'))['s'] or Decimal('0')

        # ── Activity-wise pending breakdown ───────────────────────────────
        activity_pending = (
            JobActivity.objects
            .filter(plot__clusters=c, total_area__gt=0, allocation_status='pending', is_lost=False)
            .values('activity__name')
            .annotate(pending_area=models.Sum('total_area'))
            .order_by('-pending_area')
        )
        activity_breakdown = [
            {'activity': row['activity__name'] or 'Unknown', 'pending_area': float(row['pending_area'])}
            for row in activity_pending
        ]

        # ── Weekly progress (Mon–Sun this week) ──────────────────────────────
        week_total = JobActivity.objects.filter(
            plot__clusters=c,
            scheduled_date__range=(week_start, week_end),
            total_area__gt=0,
            is_lost=False,
        ).aggregate(
            total=models.Sum('total_area'),
            allocated=models.Sum('allocated_area'),
        )
        week_total_area  = float(week_total['total']    or 0)
        week_alloc_area  = float(week_total['allocated'] or 0)
        week_pending     = round(week_total_area - week_alloc_area, 2)
        week_pct         = round((week_alloc_area / week_total_area * 100), 1) if week_total_area > 0 else 0

        # ── Monthly progress ──────────────────────────────────────────────────
        month_total = JobActivity.objects.filter(
            plot__clusters=c,
            scheduled_date__range=(month_start, month_end),
            total_area__gt=0,
            is_lost=False,
        ).aggregate(
            total=models.Sum('total_area'),
            allocated=models.Sum('allocated_area'),
        )
        month_total_area = float(month_total['total']    or 0)
        month_alloc_area = float(month_total['allocated'] or 0)
        month_pending    = round(month_total_area - month_alloc_area, 2)
        month_pct        = round((month_alloc_area / month_total_area * 100), 1) if month_total_area > 0 else 0

        c_farmers = Farmer.objects.filter(clusters=c).count()
        c_jobs    = Job.objects.filter(clusters=c).distinct().count()
        c_plots   = Plot.objects.filter(clusters=c).count()

        assigned_mukkadams = ClusterMukkadamAssignment.objects.filter(
            cluster=c, is_active=True,
        ).select_related('mukkadam')

        # ── Today status ──────────────────────────────────────────────────
        today_allocs = Allocation.objects.filter(cluster=c, allocated_date=today).select_related('mukkadam')
        has_today = today_allocs.exists()
        has_note  = bool(c.note)

        today_status = 'green' if has_today and not has_note else 'yellow' if has_today else 'red'
        today_teams  = ', '.join(set(f"{a.mukkadam.mukkadam_name} ({a.allocated_workers})" for a in today_allocs))
        today_msg    = c.note if has_note else (today_teams or 'Active today') if has_today else "No allocation — Assigned: "

        # ── Tomorrow status ───────────────────────────────────────────────
        tmrw_allocs  = Allocation.objects.filter(cluster=c, allocated_date=tomorrow).select_related('mukkadam')
        has_tmrw     = tmrw_allocs.exists()
        tmrw_status  = 'green' if has_tmrw and not has_note else 'yellow' if has_tmrw else 'red'
        tmrw_teams   = ', '.join(set(f"{a.mukkadam.mukkadam_name} ({a.allocated_workers})" for a in tmrw_allocs))
        tmrw_msg     = tmrw_teams or 'Active tomorrow' if has_tmrw else "No allocation — Assigned: " if assigned_mukkadams.exists() else 'No team scheduled'

        # ── 7-day week plan ───────────────────────────────────────────────
        week_plan = []
        for d in week_days:
            day_allocs   = Allocation.objects.filter(cluster=c, allocated_date=d).select_related('mukkadam', 'job_activity__activity').order_by('mukkadam_id')
            mukkadam_ids = list(day_allocs.values_list('mukkadam_id', flat=True).distinct())
            type_map     = {a['mukkadam_id']: a['mukkadam_type'] for a in ClusterMukkadamAssignment.objects.filter(cluster=c, mukkadam_id__in=mukkadam_ids, is_active=True).values('mukkadam_id', 'mukkadam_type')}

            seen_names = set()
            teams = []
            for a in day_allocs:
                mk_name = a.mukkadam.mukkadam_name
                if mk_name in seen_names:
                    continue
                seen_names.add(mk_name)
                mk_type = type_map.get(a.mukkadam_id, 'permanent')
                teams.append({
                    'mukkadam_id': a.mukkadam_id, 'name': mk_name,
                    'crew': a.allocated_workers,
                    'mukkadam_type': mk_type,
                    'type_tag': 'UP' if mk_type == 'updown' else 'P',
                    'status': 'confirmed',
                })

            available_teams = []
            if not teams:
                for a in assigned_mukkadams:
                    available_teams.append({
                        'mukkadam_id': a.mukkadam_id, 'name': a.mukkadam.mukkadam_name,
                        'crew': a.mukkadam.crew_size,
                        'mukkadam_type': a.mukkadam_type,
                        'type_tag': 'UP' if a.mukkadam_type == 'updown' else 'P',
                        'status': 'available',
                    })

            # ── FIX: use deduped job count, not area-as-int ────────────────
            unalloc_jobs = unalloc_count_qs({'plot__clusters': c, 'scheduled_date': d})

            unalloc_area = JobActivity.objects.filter(
                plot__clusters=c, scheduled_date=d,
                allocation_status='pending', total_area__gt=0, is_lost=False,
            ).aggregate(s=models.Sum('total_area'))['s'] or Decimal('0')

            alloc_area = JobActivity.objects.filter(
                plot__clusters=c, scheduled_date=d,
                allocation_status='allocated', total_area__gt=0,
            ).aggregate(s=models.Sum('total_area'))['s'] or Decimal('0')

            week_plan.append({
                'date':            str(d),
                'label':           fmt_date(d),
                'day_name':        d.strftime('%a'),
                'is_today':        d == actual_today,
                'teams':           teams,
                'available_teams': available_teams,
                'unallocated':     unalloc_jobs,       # ✅ now a real job count
                'total_area':      float(unalloc_area + alloc_area),
                'allocated_area':  float(alloc_area),
                'pending_area':    float(unalloc_area),
            })

        cluster_data.append({
            'id': c.id, 'name': c.name, 'note': c.note or '',
            'districts': c.districts or [],
            'farmers': c_farmers, 'plots': c_plots, 'jobs': c_jobs,
            'total_area':     float(c_total_area),
            'allocated_area': float(c_alloc_area),
            'week_progress': {
                'total_area':     week_total_area,
                'allocated_area': week_alloc_area,
                'pending_area':   week_pending,
                'pct':            week_pct,
                'label':          f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b')}",
            },
            'month_progress': {
                'total_area':     month_total_area,
                'allocated_area': month_alloc_area,
                'pending_area':   month_pending,
                'pct':            month_pct,
                'label':          actual_today.strftime('%B %Y'),
            },
            'pending_area':   float(c_total_area - c_alloc_area),
            'pct':            round(float(c_alloc_area / c_total_area * 100), 1) if c_total_area > 0 else 0,
            'activity_breakdown': activity_breakdown,
            'today':    {'status': today_status, 'msg': today_msg},
            'tomorrow': {'status': tmrw_status,  'msg': tmrw_msg},
            'week_plan': week_plan,
        })

    status_order = {'red': 0, 'yellow': 1, 'green': 2}
    cluster_data.sort(key=lambda c: status_order.get(c['today']['status'], 3))

    # ── No Cluster row ─────────────────────────────────────────────────────
    no_cluster_farmers = Farmer.objects.filter(clusters__isnull=True).count()
    no_cluster_plots   = Plot.objects.filter(clusters__isnull=True).count()
    no_cluster_jobs    = Job.objects.filter(clusters__isnull=True).distinct().count()
    no_cluster_area    = JobActivity.objects.filter(plot__clusters__isnull=True, total_area__gt=0).aggregate(s=models.Sum('total_area'))['s'] or Decimal('0')
    no_cluster_alloc   = JobActivity.objects.filter(plot__clusters__isnull=True, total_area__gt=0).aggregate(s=models.Sum('allocated_area'))['s'] or Decimal('0')

    nc_week_plan = []
    for d in week_days:
        # ✅ FIX: deduped count + is_lost + total_area > 0
        nc_unalloc = unalloc_count_qs({'plot__clusters__isnull': True, 'scheduled_date': d})
        nc_week_plan.append({
            'date': str(d), 'label': fmt_date(d), 'day_name': d.strftime('%a'),
            'is_today': d == actual_today,
            'teams': [], 'available_teams': [],
            'unallocated': nc_unalloc,
            'total_area': 0, 'allocated_area': 0, 'pending_area': 0,
        })

    no_cluster_row = {
        'id': 0, 'name': '— No Cluster', 'note': '', 'districts': [],
        'farmers': no_cluster_farmers, 'plots': no_cluster_plots, 'jobs': no_cluster_jobs,
        'total_area':     float(no_cluster_area),
        'allocated_area': float(no_cluster_alloc),
        'pending_area':   float(no_cluster_area - no_cluster_alloc),
        'pct':            round(float(no_cluster_alloc / no_cluster_area * 100), 1) if no_cluster_area > 0 else 0,
        'today':    {'status': 'yellow', 'msg': 'Not assigned to any cluster'},
        'tomorrow': {'status': 'yellow', 'msg': 'Not assigned to any cluster'},
        'week_plan': nc_week_plan,
    }

    return Response({
        'today':       str(actual_today),
        'tomorrow':    str(actual_today + timedelta(days=1)),
        'week_start':  str(today),           # ← so frontend knows which week is loaded
        'days':        [{'date': str(d), 'label': fmt_date(d), 'day_name': d.strftime('%a')} for d in week_days],
        'global_kpis': {
            'total_farmers': total_farmers, 'total_plots': total_plots,
            'total_area': float(total_area), 'allocated_area': float(allocated_area),
            'pending_area': float(total_area - allocated_area),
            'pct_complete': round(float(allocated_area / total_area * 100), 1) if total_area > 0 else 0,
            'total_jobs': total_jobs, 'total_activities': totalactivities,
        },
        'global_daily':   global_daily,
        'clusters':        cluster_data,
        'no_cluster_row':  no_cluster_row,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_timeline(request):
    from datetime import date, timedelta
    from collections import defaultdict

    today     = date.today()
    start_date = today - timedelta(days=10)
    end_date   = today + timedelta(days=9)
    all_days   = [start_date + timedelta(days=i) for i in range(20)]

    # All mukkadams
    mukkadams = Mukkadam.objects.prefetch_related(
        'cluster_assignments__cluster'
    ).order_by('mukkadam_name')

    # All allocations in range
    allocations = Allocation.objects.filter(
        allocated_date__range=(start_date, end_date)
    ).select_related('mukkadam', 'cluster').values(
        'mukkadam_id', 'cluster_id', 'cluster__name', 'allocated_date', 'allocated_workers'
    )

    # Build per mukkadam: { date_str -> { cluster_id, cluster_name, workers } }
    alloc_map = defaultdict(dict)
    for a in allocations:
        alloc_map[a['mukkadam_id']][str(a['allocated_date'])] = {
            'cluster_id':   a['cluster_id'],
            'cluster_name': a['cluster__name'] or '—',
            'workers':      a['allocated_workers'],
        }

    # All unique clusters for color mapping
    cluster_ids = list({a['cluster_id'] for a in allocations if a['cluster_id']})

    result = []
    for m in mukkadams:
        assignments = list(m.cluster_assignments.filter(is_active=True).values(
            'cluster_id', 'cluster__name', 'mukkadam_type'
        ))
        primary_type = assignments[0]['mukkadam_type'] if assignments else 'permanent'

        days_data = []
        for d in all_days:
            ds = str(d)
            alloc = alloc_map[m.mukkadam_id].get(ds)
            days_data.append({
                'date':         ds,
                'is_today':     d == today,
                'cluster_id':   alloc['cluster_id']   if alloc else None,
                'cluster_name': alloc['cluster_name'] if alloc else None,
                'workers':      alloc['workers']       if alloc else None,
            })

        result.append({
            'mukkadam_id':   m.mukkadam_id,
            'mukkadam_name': m.mukkadam_name,
            'crew_size':     m.crew_size,
            'mukkadam_type': primary_type,
            'days':          days_data,
        })

    return Response({
        'start_date':  str(start_date),
        'end_date':    str(end_date),
        'today':       str(today),
        'days':        [str(d) for d in all_days],
        'cluster_ids': cluster_ids,
        'mukkadams':   result,
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def payment_overview(request):
    from datetime import date, timedelta
    from decimal import Decimal
    from collections import defaultdict
    from django.db.models import Sum, Prefetch

    today    = date.today()
    week_ago = today - timedelta(days=7)

    # ── 1. Latest bill log per (farmer_id, job_id, activity_name) ────────
    sent_logs = FarmerBillWebhookLog.objects.only(
        'farmer_id', 'job_id', 'activity_name', 'sent_at',
        'balance_due', 'sent_by_name', 'webhook_status'
    ).order_by('-sent_at')

    latest_map = {}
    for log in sent_logs:
        key = (str(log.farmer_id), str(log.job_id or ''), log.activity_name or '')
        if key not in latest_map:
            latest_map[key] = log

    # ── 2. All JAs with prefetch (no N+1) ────────────────────────────────
    all_jas = (
        JobActivity.objects
        .filter(total_area__gt=0, is_lost=False)
        .select_related(
            'job__farmer',
            'activity',
            'plot',
            'job',
        )
        .prefetch_related(
            Prefetch(
                'allocations',
                queryset=Allocation.objects.select_related('mukkadam')
            ),
            'job__clusters',
            'plot__clusters',
        )
    )

    # ── 3. Group JAs by (farmer_id, job_id, activity_name) ───────────────
    groups = defaultdict(lambda: {
        'farmer_id':    None,
        'farmer_name':  None,
        'phone':        None,
        'job_id':       None,
        'booking_type': None,
        'cluster_id':   None,
        'cluster_name': None,
        'activity':     None,
        'rate':         0,
        'mukkadam':     None,
        'plot_rows':    [],   # keyed by plot_code internally
    })

    AREA_TOLERANCE = 0.05

    for ja in all_jas:
        farmer    = ja.job.farmer
        farmer_id = str(farmer.farmer_id)
        job_id    = str(ja.job.job_id)
        act_name  = ja.activity.name
        key       = (farmer_id, job_id, act_name)
        g         = groups[key]

        # Header fields
        g['farmer_id']    = farmer_id
        g['farmer_name']  = farmer.farmer_name
        g['phone']        = farmer.phone_number or ''
        g['job_id']       = ja.job.job_id
        g['booking_type'] = ja.job.booking_type or 'tender'
        g['activity']     = act_name
        g['rate']         = float(ja.rate_per_acre or 0)

        # Cluster — from prefetched job clusters
        if not g['cluster_id']:
            job_clusters = list(ja.job.clusters.all())
            if job_clusters:
                g['cluster_id']   = job_clusters[0].id
                g['cluster_name'] = job_clusters[0].name

        # Allocations — use prefetch cache
        all_allocs_list  = list(ja.allocations.all())
        completed_allocs = [a for a in all_allocs_list if a.work_status == 'completed']

        # Mukkadam
        if not g['mukkadam']:
            mukk_alloc = next(
                (a for a in completed_allocs if a.mukkadam_id), None
            ) or next(
                (a for a in all_allocs_list if a.mukkadam_id), None
            )
            if mukk_alloc:
                g['mukkadam'] = mukk_alloc.mukkadam.mukkadam_name

        # ── Plot identity — use plot_code as dedup key ──────────────────
        plot_code = (ja.plot.plot_code if ja.plot and ja.plot.plot_code else None) or f'JA-{ja.id}'
        plot_name = ja.plot.name if ja.plot else f'JA-{ja.id}'

        # Ground truth area = plot.area_acres (NEVER sum of JA total_area)
        plot_area = float(ja.plot.area_acres) if ja.plot and ja.plot.area_acres else float(ja.total_area or 0)

        # Completed area from this JA's allocations
        ja_completed_area = sum(
            float(a.admin_override_area or a.actual_area_done or a.allocated_area or 0)
            for a in completed_allocs
        )

        # Latest done date from this JA's completed allocations
        ja_latest_done_date = None
        for a in completed_allocs:
            if a.allocated_date and (not ja_latest_done_date or a.allocated_date > ja_latest_done_date):
                ja_latest_done_date = a.allocated_date

        # ── Find existing plot_row for this plot_code or create new ─────
        existing = next((r for r in g['plot_rows'] if r['plot_code'] == plot_code), None)

        if existing:
            # Accumulate completed area across split JAs — cap at plot_area
            existing['completed_area'] = min(
                existing['completed_area'] + ja_completed_area,
                plot_area,
            )
            # Update done date to latest
            if ja_latest_done_date and (
                not existing['done_date'] or
                str(ja_latest_done_date) > existing['done_date']
            ):
                existing['done_date'] = str(ja_latest_done_date)
            # Recompute ja_done and amount after merge
            existing['ja_done'] = (
                existing['completed_area'] >= plot_area - AREA_TOLERANCE or
                ja.allocation_status == 'completed'
            )
            existing['completed_amount'] = round(existing['completed_area'] * g['rate'], 2)
        else:
            # Cap completed area at plot_area even for a fresh row
            capped_completed = min(ja_completed_area, plot_area)
            ja_done = (
                capped_completed >= plot_area - AREA_TOLERANCE or
                ja.allocation_status == 'completed'
            )
            g['plot_rows'].append({
                'plot_name':        plot_name,
                'plot_code':        plot_code,
                'total_area':       plot_area,        # ← plot.area_acres, not JA total_area
                'completed_area':   capped_completed,
                'ja_done':          ja_done,
                'completed_amount': round(capped_completed * g['rate'], 2),
                'done_date':        str(ja_latest_done_date) if ja_latest_done_date else None,
            })

    # ── 4. Classify each group ────────────────────────────────────────────
    farmer_list = []

    for (farmer_id, job_id, act_name), g in groups.items():
        plot_rows       = g['plot_rows']
        total_expected  = sum(r['total_area'] for r in plot_rows)      # sum of plot.area_acres per unique plot
        total_completed = sum(r['completed_area'] for r in plot_rows)
        all_plots_done  = all(r['ja_done'] for r in plot_rows)
        any_plot_done   = any(r['ja_done'] for r in plot_rows)
        n_plots         = len(plot_rows)                                # unique plot count
        done_plots      = sum(1 for r in plot_rows if r['ja_done'])
        total_amount    = sum(r['completed_amount'] for r in plot_rows if r['ja_done'])
        latest_date     = max(
            (r['done_date'] for r in plot_rows if r['done_date']),
            default=None
        )
        full_job_amount = round(total_expected * g['rate'], 2)

        log = latest_map.get((farmer_id, str(job_id), act_name))

        all_plot_details = [
            {
                'plot_name':      r['plot_name'],
                'plot_code':      r['plot_code'],
                'total_area':     r['total_area'],
                'completed_area': r['completed_area'],
                'done':           r['ja_done'],
                'amount':         r['completed_amount'],
                'done_date':      r['done_date'],
            }
            for r in plot_rows
        ]
        plots_done_names = [r['plot_name'] for r in plot_rows if r['ja_done']]

        base = {
            'farmer_id':       farmer_id,
            'farmer_name':     g['farmer_name'],
            'phone':           g['phone'],
            'cluster_id':      g['cluster_id'],
            'cluster_name':    g['cluster_name'] or '—',
            'activity':        act_name,
            'rate':            g['rate'],
            'booking_type':    g['booking_type'],
            'plots':           plots_done_names,
            'all_plots':       all_plot_details,
            'n_plots':         n_plots,
            'completed_plots': done_plots,
            'acres':           total_completed,
            'amount':          total_amount,
            'job_value':       full_job_amount,
            'mukkadam':        g['mukkadam'] or '—',
            'job_id':          job_id,
            'completed_date':  latest_date,
        }

        if all_plots_done and total_amount > 0:
            if log:
                balance  = float(log.balance_due or 0)
                sent_at  = log.sent_at.date() if log.sent_at else today
                days_ago = (today - sent_at).days
                status = (
                    'collected' if balance <= 0.01 else
                    'overdue'   if days_ago > 7    else
                    'this_week' if sent_at >= week_ago else
                    'next_week'
                )
                farmer_list.append({**base,
                    'status':            'billed',
                    'bill_status':       'sent',
                    'expected_payment':  status,
                    'days_since_billed': days_ago,
                    'billed_date':       str(sent_at),
                    'balance_due':       balance,
                    'sent_by':           log.sent_by_name or '—',
                    'webhook_status':    log.webhook_status,
                })
            else:
                farmer_list.append({**base,
                    'status':            'ready_to_bill',
                    'bill_status':       None,
                    'expected_payment':  'ready_to_bill',
                    'days_since_billed': None,
                    'billed_date':       None,
                    'balance_due':       total_amount,
                    'sent_by':           None,
                    'webhook_status':    None,
                })
        elif any_plot_done:
            farmer_list.append({**base,
                'pending_plots':    n_plots - done_plots,
                'pending_amount':   round(full_job_amount - total_amount, 2),
                'completed_amount': total_amount,
                'status':            'partial',
                'bill_status':       None,
                'expected_payment':  None,
                'days_since_billed': None,
                'billed_date':       None,
                'balance_due':       0,
                'sent_by':           None,
                'webhook_status':    None,
            })

    # ── 5. Pipeline counts ────────────────────────────────────────────────
    ready_list    = [f for f in farmer_list if f['status'] == 'ready_to_bill']
    billed_list   = [f for f in farmer_list if f['status'] == 'billed']
    partial_list  = [f for f in farmer_list if f['status'] == 'partial']
    overdue_list  = [f for f in farmer_list if f.get('expected_payment') == 'overdue']
    thisweek_list = [f for f in farmer_list if f.get('expected_payment') == 'this_week']
    nextweek_list = [f for f in farmer_list if f.get('expected_payment') == 'next_week']

    # ── 6. Recent payments ────────────────────────────────────────────────
    recent_payments_qs = (
        FarmerPayment.objects
        .filter(paid_status=True, paid_at__date__gte=today - timedelta(days=30))
        .select_related('booking__job__farmer', 'booking__job')
        .prefetch_related('booking__job__clusters')
        .order_by('-paid_at')[:15]
    )

    recent_payments = []
    for p in recent_payments_qs:
        try:
            farmer_name  = p.booking.job.farmer.farmer_name
            job_id_      = p.booking.job.job_id
            cluster_obj  = list(p.booking.job.clusters.all())
            cluster_name = cluster_obj[0].name if cluster_obj else '—'
        except Exception:
            farmer_name = job_id_ = cluster_name = '—'
        recent_payments.append({
            'farmer':    farmer_name,
            'job_id':    job_id_,
            'cluster':   cluster_name,
            'amount':    float(p.amount),
            'paid_date': str(p.paid_at.date()),
            'method':    p.mode,
            'notes':     p.notes or '',
        })

    collected_7d = FarmerPayment.objects.filter(
        paid_status=True,
        paid_at__date__gte=week_ago,
    ).aggregate(s=Sum('amount'))['s'] or 0

    # ── 7. Cluster billing summary ────────────────────────────────────────
    cluster_farmer_map = defaultdict(list)
    for f in farmer_list:
        if f['cluster_id']:
            cluster_farmer_map[f['cluster_id']].append(f)

    from django.db.models import Prefetch as P2
    cluster_job_ids_map = defaultdict(list)
    for row in Job.objects.filter(
        clusters__isnull=False
    ).values('job_id', 'clusters'):
        cluster_job_ids_map[row['clusters']].append(row['job_id'])

    payment_agg = (
        FarmerPayment.objects
        .filter(paid_status=True)
        .values('booking__job_id')
        .annotate(total=Sum('amount'))
    )
    payment_by_job = {str(row['booking__job_id']): float(row['total']) for row in payment_agg}

    clusters = Cluster.objects.all().order_by('name')
    cluster_billing = []
    for c in clusters:
        c_farmers = cluster_farmer_map.get(c.id, [])
        job_ids   = cluster_job_ids_map.get(c.id, [])
        total_collected = sum(payment_by_job.get(str(jid), 0) for jid in job_ids)
        total_billed    = sum(f['amount'] for f in c_farmers if f['status'] == 'billed')

        cluster_billing.append({
            'cluster_id':     c.id,
            'cluster':        c.name,
            'farmers':        Farmer.objects.filter(clusters=c).count(),
            'billed':         total_billed,
            'collected':      total_collected,
            'due':            max(0, total_billed - total_collected),
            'bills_pending':  sum(1 for f in c_farmers if f['status'] == 'ready_to_bill'),
            'bills_sent':     sum(1 for f in c_farmers if f['status'] == 'billed'),
            'bills_awaiting': sum(1 for f in c_farmers if f.get('expected_payment') == 'overdue'),
            'total_job_value': sum(f['job_value'] for f in c_farmers),
        })

    return Response({
        'today': str(today),
        'pipeline': {
            'ready_to_bill': {'count': len(ready_list),   'amount': sum(f['amount'] for f in ready_list),   'plots': sum(f['n_plots'] for f in ready_list)},
            'partial':       {'count': len(partial_list), 'amount': sum(f.get('completed_amount', 0) for f in partial_list)},
            'bills_sent':    {'count': len(billed_list),  'amount': sum(f['balance_due'] for f in billed_list)},
            'overdue': {
                'count':    len(overdue_list),
                'amount':   sum(f['balance_due'] for f in overdue_list),
                'avg_days': round(sum(f['days_since_billed'] or 0 for f in overdue_list) / max(len(overdue_list), 1)),
            },
            'collected_7d':  {'count': len(recent_payments), 'amount': float(collected_7d)},
        },
        'forecast': {
            'this_week':    {'count': len(thisweek_list), 'amount': sum(f['balance_due'] for f in thisweek_list)},
            'next_week':    {'count': len(nextweek_list), 'amount': sum(f['balance_due'] for f in nextweek_list)},
            'ready_to_bill':{'count': len(ready_list),   'amount': sum(f['amount'] for f in ready_list)},
            'overdue':      {'count': len(overdue_list), 'amount': sum(f['balance_due'] for f in overdue_list)},
        },
        'farmer_list':     farmer_list,
        'recent_payments': recent_payments,
        'cluster_billing': cluster_billing,
    })

@api_view(['DELETE'])
def reset_cluster_activity_rate(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific rate override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityRate.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Rate override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)


@api_view(['DELETE'])
def reset_cluster_activity_gap(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific gap override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Gap override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

@api_view(['DELETE'])
def reset_cluster_activity_override(request, cluster_id, activity_id):
    """
    DELETE: Remove cluster-specific override for an activity
    """
    try:
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        
        ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=activity
        ).delete()
        
        return Response({'success': True, 'message': 'Override removed'})
    except (Cluster.DoesNotExist, ActivityCatalog.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)


import requests
from django.http import JsonResponse
from django.views.decorators.http import require_GET

EXTERNAL_API_URL = "https://ops.bharatintelligence.ai/ops/allocation_booked_visits/"
EXTERNAL_API_TOKEN = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"  # replace with your actual token

@require_GET
def tender_activity_count_from_api(request):
    all_activities = []
    url = EXTERNAL_API_URL
    page = 1

    try:
        # Paginate through all pages
        while url:
            response = requests.get(
                url,
                headers={"Authorization": f"Token {EXTERNAL_API_TOKEN}"},
                timeout=15
            )

            if response.status_code != 200:
                return JsonResponse({
                    "status": "error",
                    "message": f"External API returned {response.status_code}",
                }, status=502)

            payload = response.json()

            # Handle both paginated and non-paginated responses
            jobs = payload.get("data") or payload.get("results") or []

            for job in jobs:
                # Only process tender booking_type
                booking = job.get("booking") or {}
                booking_type = booking.get("booking_type", "")

                if booking_type.lower() != "tender":
                    continue

                activities = job.get("activities") or []
                for act in activities:
                    all_activities.append({
                        "job_id":        job.get("id"),
                        "farmer_id":     job.get("farmer_id"),
                        "activity_id":   act.get("id"),
                        "activity_name": act.get("activity_name"),
                        "status":        job.get("status"),
                        "scheduled_date": job.get("scheduled_date"),
                    })

            # Move to next page if paginated
            url = payload.get("next")  # None if no more pages
            page += 1

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            "status": "error",
            "message": str(e),
        }, status=502)

    return JsonResponse({
        "status": "success",
        "data": {
            "total_activity_count": len(all_activities),
            "activities": all_activities,
        }
    })

class FarmerViewSet(viewsets.ModelViewSet):
    queryset = Farmer.objects.all().prefetch_related('clusters')


    serializer_class = FarmerSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = Farmer.objects.all().prefetch_related(
            'clusters',
            'plots',       # ← needed for total_acres
        )

        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(clusters__id=cluster_id)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(farmer_name__icontains=search) |
                Q(phone_number__icontains=search)
            )

        return queryset.order_by('farmer_name')
    
    @action(detail=True, methods=['get'], url_path='profile')
    def farmer_profile(self, request, pk=None):
        try:
            farmer = (
                Farmer.objects
                .prefetch_related(
                    'clusters',
                    'plots__clusters',
                    'plots__activities__activity',               # ← ADD
                    'plots__activities__allocations__mukkadam',  # ← ADD
                    'jobs__clusters',
                    'jobs__plot',
                    'jobs__booking__payments',
                )
                .select_related('last_cluster_modified_by')
                .get(pk=pk)
            )
        except Farmer.DoesNotExist:
            return Response({'error': 'Farmer not found'}, status=404)

        serializer = FarmerProfileSerializer(farmer, context={'request': request})
        return Response(serializer.data)
@api_view(['GET'])
def get_cluster_plots(request, cluster_id):
    # ✅ M2M: filter plots where clusters contains this cluster
    plots = Plot.objects.filter(clusters__id=cluster_id).select_related('farmer')
    plot_list = [{
        'id': plot.id,
        'name': plot.name,
        'area_acres': float(plot.area_acres),
        'plot_code': plot.plot_code,
        'farmer_id': plot.farmer.farmer_id if plot.farmer else None,
        'farmer_name': plot.farmer.farmer_name if plot.farmer else None,
    } for plot in plots]
    return Response({'plots': plot_list})


class PlotViewSet(viewsets.ModelViewSet):
    queryset = Plot.objects.all().select_related('farmer').prefetch_related('clusters')
    serializer_class = PlotSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        qs = super().get_queryset()  # ✅ use 'qs' not 'queryset'
        
        farmer_id = self.request.query_params.get('farmer_id')
        if farmer_id:
            qs = qs.filter(farmer_id=farmer_id)
        
        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            qs = qs.filter(clusters__id=cluster_id)
        
        return qs.order_by('-created_at')


def load_location_data(filename):
    """
    Load location data from static JSON files and transform from 
    column-based format to row-based array of objects
    """
    file_path = os.path.join(settings.BASE_DIR, 'static', 'location_data', filename)
    
    logger.info(f"Attempting to load: {file_path}")
    logger.info(f"File exists: {os.path.exists(file_path)}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Loaded data type: {type(data)}")
        
        # ✅ Check if data is already an array (correct format)
        if isinstance(data, list):
            logger.info(f"Data is list with {len(data)} items")
            return data
        
        # ✅ Transform column-based JSON to row-based array
        if isinstance(data, dict):
            columns = list(data.keys())
            logger.info(f"Data is dict with columns: {columns}")
            
            if not columns:
                return []
            
            first_column = data[columns[0]]
            row_indices = sorted(first_column.keys(), key=lambda x: int(x))
            
            result = []
            for index in row_indices:
                row_obj = {}
                for column in columns:
                    value = data[column].get(index, '')
                    row_obj[column] = value.strip() if isinstance(value, str) else str(value).strip()
                result.append(row_obj)
            
            logger.info(f"Transformed to {len(result)} rows")
            return result
        
        return []
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error in {filename}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading {filename}: {str(e)}")
        return []


def normalize_field_name(d, *field_variations):
    """
    Get value from dict trying multiple field name variations
    Returns the first matching field value, or empty string if none found
    """
    for field in field_variations:
        if field in d:
            value = d[field]
            return value.strip() if isinstance(value, str) else str(value).strip()
    return ''


@api_view(['GET'])
@permission_classes([AllowAny])
def get_states(request):
    """Returns available states"""
    states = [
        {
            'state_code': 'MH',
            'state_name_english': 'Maharashtra',
            'state_name_local': 'महाराष्ट्र'
        },
        {
            'state_code': 'GJ',
            'state_name_english': 'Gujarat',
            'state_name_local': 'ગુજરાત'
        }
    ]
    return Response(states)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_districts(request):
    """Returns unique districts for a state"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    
    logger.info(f"📍 get_districts called with state_code: {state_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_districts.json',
        'GJ': 'gujarat_districts.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        logger.error(f"❌ Invalid state_code: {state_code}")
        return Response({'error': 'Invalid state_code'}, status=400)
    
    logger.info(f"📂 Loading file: {filename}")
    districts = load_location_data(filename)
    
    logger.info(f"✅ Loaded {len(districts)} districts for {state_code}")
    
    # ✅ Deduplicate and clean - handle multiple field name formats
    seen = set()
    unique_districts = []
    
    for d in districts:
        if not isinstance(d, dict):
            continue
        
        # Try multiple field name variations
        code = normalize_field_name(d, 'districtcode', 'District Code', 'District code')
        name_english = normalize_field_name(d, 'districtnameenglish', 'District Name', 'District name')
        name_local = normalize_field_name(d, 'districtlocalname', 'District Name', 'District name')
        
        if code and code not in seen:
            seen.add(code)
            unique_districts.append({
                'districtcode': code,
                'districtnameenglish': name_english,
                'districtlocalname': name_local
            })
    
    logger.info(f"✅ Returning {len(unique_districts)} unique districts")
    return Response(unique_districts)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_talukas(request):
    """Returns unique talukas for a district"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    district_code = request.query_params.get('district_code', '').strip()
    
    logger.info(f"📍 get_talukas called with state: {state_code}, district: {district_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    if not district_code:
        return Response({'error': 'district_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_talukas.json',
        'GJ': 'gujarat_talukas.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)
    
    all_talukas = load_location_data(filename)
    
    # Filter and deduplicate - handle multiple field name formats
    seen = set()
    unique_talukas = []
    
    for t in all_talukas:
        if not isinstance(t, dict):
            continue
        
        # Get district code with multiple field name variations
        t_district_code = normalize_field_name(t, 'districtcode', 'District Code', 'District code')
        
        if t_district_code == district_code:
            code = normalize_field_name(t, 'subdistrictcode', 'Subdistrict Code', 'Subdistrict code')
            name_english = normalize_field_name(t, 'subdistrictnameenglish', 'Subdistrict Name', 'Subdistrict Name  ')
            name_local = normalize_field_name(t, 'subdistrictlocalname', 'Subdistrict Name', 'Subdistrict Name  ')
            
            if code and code not in seen:
                seen.add(code)
                unique_talukas.append({
                    'districtcode': t_district_code,
                    'subdistrictcode': code,
                    'subdistrictnameenglish': name_english,
                    'subdistrictlocalname': name_local
                })
    
    logger.info(f"✅ Returning {len(unique_talukas)} talukas")
    return Response(unique_talukas)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_villages(request):
    """Returns unique villages for a taluka"""
    state_code = request.query_params.get('state_code', '').strip().upper()
    taluka_code = request.query_params.get('taluka_code', '').strip()
    
    logger.info(f"📍 get_villages called with state: {state_code}, taluka: {taluka_code}")
    
    if not state_code:
        return Response({'error': 'state_code is required'}, status=400)
    if not taluka_code:
        return Response({'error': 'taluka_code is required'}, status=400)
    
    # Map state codes to file names
    state_file_mapping = {
        'MH': 'maharashtra_villages.json',
        'GJ': 'gujarat_villages.json'
    }
    
    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)
    
    all_villages = load_location_data(filename)
    
    # Filter and deduplicate - handle multiple field name formats
    seen = set()
    unique_villages = []
    
    for v in all_villages:
        if not isinstance(v, dict):
            continue
        
        # ✅ FIXED: Added 'Sub-District Code' variation (with hyphen)
        v_taluka_code = normalize_field_name(
            v, 
            'subdistrictcode', 
            'Subdistrict Code', 
            'Subdistrict code',
            'Sub-District Code',  # ← Added this
            'Sub-district Code'
        )
        
        if v_taluka_code == taluka_code:
            # ✅ FIXED: Added hyphenated variations for all fields
            district_code = normalize_field_name(
                v, 
                'districtcode', 
                'District Code', 
                'District code'
            )
            
            code = normalize_field_name(
                v, 
                'villagecode', 
                'Village Code', 
                'Village code'
            )
            
            name_english = normalize_field_name(
                v, 
                'villagenameenglish', 
                'Village Name', 
                'Village name',
                'Village Name '  # ← Note trailing space in Gujarat data
            )
            
            name_local = normalize_field_name(
                v, 
                'villagelocalname', 
                'Village Name', 
                'Village name',
                'Village Name '  # ← Note trailing space
            )
            
            if code and code not in seen:
                seen.add(code)
                unique_villages.append({
                    'districtcode': district_code,
                    'subdistrictcode': v_taluka_code,
                    'villagecode': code,
                    'villagenameenglish': name_english,
                    'villagelocalname': name_local
                })
    
    logger.info(f"✅ Returning {len(unique_villages)} villages")
    return Response(unique_villages)

@api_view(['GET'])
@permission_classes([AllowAny])
def search_villages(request):
    """
    Search villages by name prefix across all talukas for a state.
    GET /locations/search_villages/?state_code=MH&q=sat
    """
    state_code = request.query_params.get('state_code', '').strip().upper()
    q = request.query_params.get('q', '').strip().lower()

    if not state_code or not q:
        return Response([])

    state_file_mapping = {
        'MH': 'maharashtra_villages.json',
        'GJ': 'gujarat_villages.json',
    }

    filename = state_file_mapping.get(state_code)
    if not filename:
        return Response({'error': 'Invalid state_code'}, status=400)

    all_villages = load_location_data(filename)

    results = []
    seen = set()

    for v in all_villages:
        if not isinstance(v, dict):
            continue

        name_en = normalize_field_name(v, 'villagenameenglish', 'Village Name', 'Village name', 'Village Name ')
        name_local = normalize_field_name(v, 'villagelocalname', 'Village Name', 'Village name', 'Village Name ')
        code = normalize_field_name(v, 'villagecode', 'Village Code', 'Village code')

        if not code or code in seen:
            continue

        if name_en.lower().startswith(q) or name_local.lower().startswith(q):
            seen.add(code)
            results.append({
                'villagecode': code,
                'villagenameenglish': name_en,
                'villagelocalname': name_local,
                'subdistrictcode': normalize_field_name(v, 'subdistrictcode', 'Subdistrict Code', 'Sub-District Code'),
                'districtcode': normalize_field_name(v, 'districtcode', 'District Code'),
            })

        if len(results) >= 30:
            break

    return Response(results)

# =============================================================================
# ACTIVITY CATALOG VIEWSET
# =============================================================================

# views.py

class ActivityCatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing activity catalog
    """
    queryset = ActivityCatalog.objects.all()
    serializer_class = ActivityCatalogSerializer
    permission_classes = [AllowAny]   
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by source (api/custom)
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)
        
        # Filter by is_strict
        is_strict = self.request.query_params.get('is_strict')
        if is_strict is not None:
            queryset = queryset.filter(is_strict=is_strict.lower() == 'true')
        
        # Search by name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')
    
    @action(detail=False, methods=['post'])
    def create_global_activity(self, request):
        """
        Create a new global activity with farmer and mukkadam defaults
        
        POST /api/activities/create_global_activity/
        Body: {
            "name": "New Activity",
            "activity_type": "pruning",
            "default_rate_per_acre": 1000,
            "default_gap_days": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150,
            "is_strict": false,
            "estimated_workers_per_acre": 10
        }
        """
        serializer = CreateActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
            return Response(
                {'error': f'Activity "{data["name"]}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create activity in catalog
        activity = ActivityCatalog.objects.create(
            name=data['name'],
            activity_type=data.get('activity_type', ''),
            default_rate_per_acre=data['default_rate_per_acre'],
            is_strict=data['is_strict'],
            estimated_workers_per_acre=data['estimated_workers_per_acre'],
            default_gap_days=data['default_gap_days'],
            source='custom'
        )
        
        # Create global schedule rule
        ActivityScheduleRule.objects.create(
            activity=activity,
            gap_days=data['default_gap_days'],
            phase_order=ActivityScheduleRule.objects.count() + 1
        )
        
        # Note: Mukkadam defaults are stored per cluster, not globally
        # They will be used when clusters are created or when adding to clusters
        
        return Response(
            {
                'success': True,
                'message': f'Activity "{data["name"]}" created successfully',
                'activity': ActivityCatalogDetailSerializer(activity).data,
                'mukkadam_defaults': {
                    'rate_per_acre': data['mukkadam_rate_per_acre'],
                    'productivity_per_worker': data['mukkadam_productivity_per_worker']
                }
            },
            status=status.HTTP_201_CREATED
        )
    @action(detail=False, methods=['post'])
    def add_custom_activity(self, request):
        """
        Add a custom activity from frontend
        
        POST /api/activities/add_custom_activity/
        Body: {
            "name": "Custom Activity Name",
            "activity_type": "pruning",
            "is_strict": false,
            "default_rate_per_acre": 500,
            "estimated_workers_per_acre": 10
        }
        """
        name = request.data.get('name')
        activity_type = request.data.get('activity_type', '')
        is_strict = request.data.get('is_strict', False)
        default_rate = request.data.get('default_rate_per_acre', 0)
        estimated_workers = request.data.get('estimated_workers_per_acre', 10)
        
        if not name:
            return Response(
                {'error': 'Activity name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=name).exists():
            return Response(
                {'error': f'Activity "{name}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activity = ActivityCatalog.objects.create(
            name=name,
            activity_type=activity_type,
            is_strict=is_strict,
            default_rate_per_acre=default_rate,
            estimated_workers_per_acre=estimated_workers,
            source='custom'
        )
        
        serializer = self.get_serializer(activity)
        return Response(
            {
                'success': True,
                'message': f'Activity "{name}" created successfully',
                'activity': serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['patch'])
    def update_strict_status(self, request, pk=None):
        """
        Update strict status of an activity
        
        PATCH /api/activities/{id}/update_strict_status/
        Body: { "is_strict": true }
        """
        activity = self.get_object()
        is_strict = request.data.get('is_strict')
        
        if is_strict is None:
            return Response(
                {'error': 'is_strict field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        activity.is_strict = is_strict
        activity.save()
        
        serializer = self.get_serializer(activity)
        return Response({
            'success': True,
            'message': f'Activity strict status updated',
            'activity': serializer.data
        })
    
# views.py - Inside ActivityCatalogViewSet class

    @action(detail=False, methods=['post'])
    def insert_between(self, request):  # ✅ Changed name and added 'self'
        """
        Insert a new activity between two existing activities in the lifecycle
        
        POST /api/activities/insert_between/
        Body: {
            "name": "New Activity Name",
            "activity_type": "pruning",
            "default_rate_per_acre": 1000,
            "gap_days_from_previous": 5,
            "insert_after_activity_id": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150,
            "is_strict": false,
            "estimated_workers_per_acre": 10
        }
        """
        serializer = InsertActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Check if activity already exists
        if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
            return Response(
                {'error': f'Activity "{data["name"]}" already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the activity we're inserting after
        try:
            previous_activity = ActivityCatalog.objects.get(id=data['insert_after_activity_id'])
        except ActivityCatalog.DoesNotExist:
            return Response(
                {'error': 'Previous activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get the previous activity's schedule rule
        try:
            previous_rule = ActivityScheduleRule.objects.get(activity=previous_activity)
            new_phase_order = previous_rule.phase_order + 1
        except ActivityScheduleRule.DoesNotExist:
            return Response(
                {'error': 'Previous activity has no schedule rule'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Create the new activity
            new_activity = ActivityCatalog.objects.create(
                name=data['name'],
                activity_type=data.get('activity_type', ''),
                default_rate_per_acre=data['default_rate_per_acre'],
                is_strict=data['is_strict'],
                estimated_workers_per_acre=data['estimated_workers_per_acre'],
                default_gap_days=data['gap_days_from_previous'],
                source='custom'
            )
            
            # Shift all activities after this one by +1 in phase_order
            ActivityScheduleRule.objects.filter(
                phase_order__gte=new_phase_order
            ).update(phase_order=models.F('phase_order') + 1)
            
            # Create schedule rule for new activity
            ActivityScheduleRule.objects.create(
                activity=new_activity,
                gap_days=data['gap_days_from_previous'],
                phase_order=new_phase_order
            )
            
            return Response({
                'success': True,
                'message': f'Activity "{data["name"]}" inserted after "{previous_activity.name}"',
                'activity': {
                    'id': new_activity.id,
                    'name': new_activity.name,
                    'phase_order': new_phase_order,
                    'gap_days': data['gap_days_from_previous'],
                    'inserted_after': previous_activity.name
                }
            }, status=status.HTTP_201_CREATED)


# =============================================================================
# JOB VIEWSET
# =============================================================================
class LeaveViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveSerializer

    def get_queryset(self):
        queryset = Leave.objects.all().select_related('mukkadam')

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        cluster_id = self.request.query_params.get('cluster_id')

        if cluster_id:
            queryset = queryset.filter(cluster__id=cluster_id).distinct()


        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        leave_type = self.request.query_params.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)

        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam_id=mukkadam_id)

        return queryset.filter(is_active=True).order_by('date')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        cluster_id = request.query_params.get('cluster_id')

        # ✅ For each general holiday, set crew_on_leave = total cluster crew
        for i, leave in enumerate(queryset):
            if leave.leave_type == 'general' and cluster_id:
                total_crew = Mukkadam.objects.filter(
                    clusters__id=cluster_id
                ).aggregate(
                    total=models.Sum('crew_size')
                )['total'] or 0

                data[i]['crew_on_leave'] = total_crew  # ✅ show total blocked workers
                data[i]['is_general_holiday'] = True   # ✅ flag for frontend

        return Response(data)

    @action(detail=False, methods=['get'])
    def check_availability(self, request):
        date = request.query_params.get('date')
        mukkadam_id = request.query_params.get('mukkadam_id')
        cluster_id = request.query_params.get('cluster_id')  # ⬅️ add

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_qs = Leave.objects.filter(
            date=date,
            is_active=True,
        )
        if cluster_id:
            base_qs = base_qs.filter(cluster_id=cluster_id)

        # 1) general holiday
        general_holiday = base_qs.filter(leave_type='general').first()
        if general_holiday:
            return Response({
                'available': False,
                'reason': 'holiday',
                'message': f'all team off: {general_holiday.reason}',
            })

        if mukkadam_id:
            from .models import Mukkadam

            try:
                mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            except Mukkadam.DoesNotExist:
                return Response(
                    {'error': 'Mukkadam not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            leave_qs = base_qs.filter(
                leave_type='mukkadam',
                mukkadam_id=mukkadam_id,
            )

            total_on_leave = leave_qs.aggregate(total=Sum('crew_on_leave'))['total'] or 0
            effective_crew = max(mukkadam.crew_size - total_on_leave, 0)

            return Response({
                'available': effective_crew > 0,
                'reason': 'mukkadam_partial_leave' if total_on_leave > 0 else 'no_leave',
                'message': (
                    f'{total_on_leave} workers on leave, {effective_crew} available'
                    if total_on_leave > 0
                    else 'No leave for this mukkadam'
                ),
                'crew_size': mukkadam.crew_size,
                'crew_on_leave': total_on_leave,
                'available_workers': effective_crew,
            })

        return Response({
            'available': True,
            'reason': 'no_leave',
            'message': 'Available for allocation',
        })

def _build_alloc_cancel_payload(alloc, activity, job, reason, user):
    return {
        "allocation_id":         alloc.id,
        "booking_id":            job.booking.booking_id if job.booking else None,
        "api_activity_id":       activity.api_activity_id or None,
        "activity_name":         activity.activity.name,
        "activity_status":       "cancelled",
        "allocated_area":        float(alloc.allocated_area),
        "allocated_date":        str(alloc.allocated_date),
        "mukkadam_id":           alloc.mukkadam.mukkadam_id,
        "mukkadam_name":         alloc.mukkadam.mukkadam_name,
        "farmer_rate":           float(alloc.farmer_rate),
        "mukkadam_rate":         float(alloc.mukkadam_rate),
        "job_id":                job.job_id,
        "farmer_id":             job.farmer.farmer_id,
        "farmer_name":           job.farmer.farmer_name,
        "plot_id":               activity.plot.id if activity.plot else None,
        "plot_code":             activity.plot.plot_code if activity.plot else None,
        "cancelled_at":          str(timezone.now()),
        "cancel_reason":         reason,
        "last_modified_by_id":   user.id if user.is_authenticated else None,
        "last_modified_by_name": user.get_full_name() or user.username if user.is_authenticated else None,
    }
from django.db.models import Prefetch
from decimal import Decimal
class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        plot_id = self.request.query_params.get('plot')
        cluster_id = self.request.query_params.get('cluster_id')

        # Build activities queryset based on what filter is active
        activities_qs = JobActivity.objects.filter(is_lost=False).exclude(
            allocation_status='pending',
            allocations__isnull=True,
        ).select_related('activity', 'plot').prefetch_related(
            Prefetch(
                'allocations',
                queryset=Allocation.objects.select_related('mukkadam').order_by('allocated_date')
            )
        ).order_by('scheduled_date')

        if plot_id:
            activities_qs = activities_qs.filter(plot_id=plot_id)
        elif cluster_id:
            activities_qs = activities_qs.filter(plot__clusters__id=cluster_id)

        queryset = Job.objects.all().select_related('farmer', 'plot').prefetch_related(
            'clusters',
            Prefetch('activities', queryset=activities_qs)
        )

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status__in=status_filter.split(','))

        if cluster_id:
            queryset = queryset.filter(clusters__id=cluster_id)

        if plot_id:
            queryset = queryset.filter(
                Q(plot_id=plot_id) | Q(activities__plot_id=plot_id)
            )

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        booking_type = self.request.query_params.get('booking_type')
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type)

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(scheduled_date__range=[start_date, end_date])

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(job_id__icontains=search) |
                Q(farmer__farmer_name__icontains=search)
            )

        farmer_id = self.request.query_params.get('farmer_id')
        if farmer_id:
            queryset = queryset.filter(farmer_id=farmer_id)

        return queryset.distinct().order_by('-created_at')
    @action(detail=True, methods=['get'])
    def activities_summary(self, request, pk=None):
        """
        Get detailed activities summary for a job
        
        GET /api/jobs/{job_id}/activities_summary/
        """
        job = self.get_object()
        activities = job.activities.all()
        
        summary = {
            'job_id': job.job_id,
            'farmer_name': job.farmer.farmer_name,
            'total_activities': activities.count(),
            'fully_allocated': activities.filter(is_fully_allocated=True).count(),
            'partially_allocated': activities.filter(
                allocated_area__gt=0,
                is_fully_allocated=False
            ).count(),
            'not_allocated': activities.filter(allocated_area=0).count(),
            'activities': []
        }
        
        for activity in activities:
            allocations = activity.allocations.all()
            
            activity_data = {
                'id': activity.id,
                'name': activity.activity.name,
                'is_strict': activity.activity.is_strict,
                'total_area': float(activity.total_area),
                'allocated_area': float(activity.allocated_area),
                'is_manually_moved': activity.is_manually_moved, 
                'remaining_area': float(activity.remaining_area),
                'allocation_percentage': (
                    (activity.allocated_area / activity.total_area * 100) 
                    if activity.total_area > 0 else 0
                ),
                'source': 'manual' if activity.is_manually_moved else 'ai',
                'scheduled_date': activity.scheduled_date,
                'allocation_count': allocations.count(),
                'status': activity.allocation_status
            }
            
            summary['activities'].append(activity_data)
        
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        job = self.get_object()
        data = request.data.copy()
        data['job'] = job.pk
        
        serializer = JobActivityCreateUpdateSerializer(
            data=data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        ja = serializer.save()
        
        return Response(
            JobActivitySerializer(ja).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Get financial summary for a job
        
        GET /api/jobs/{job_id}/financial_summary/
        """
        from .utils import calculate_job_financials
        
        job = self.get_object()
        financials = calculate_job_financials(job.job_id)
        
        if not financials:
            return Response(
                {'error': 'Unable to calculate financials'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(financials)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        ctx(flow="activity_cancel", ja_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        job           = self.get_object()
        reason        = request.data.get('reason', '').strip()
        cancel_allocs = bool(request.data.get('cancel_allocations', False))  # 👈 frontend decides

        if not reason:
            return Response({'error': 'reason is required'}, status=400)
        if job.status == 'cancelled':
            return Response({'error': 'Job is already cancelled'}, status=400)

        cancelled_activities  = []
        cancelled_allocations = []
        skipped_allocations   = []

        with transaction.atomic():
            activities = JobActivity.objects.filter(job=job, is_lost=False).select_related(
                'activity', 'plot'
            ).prefetch_related(
                Prefetch('allocations', queryset=Allocation.objects.select_related('mukkadam'))
            )

            for act in activities:
                if cancel_allocs:
                    for alloc in act.allocations.all():
                        if alloc.status == 'completed':
                            skipped_allocations.append({
                                'allocation_id': alloc.id,
                                'activity_name': act.activity.name,
                                'mukkadam_name': alloc.mukkadam.mukkadam_name,
                                'message':       'Skipped — already completed',
                            })
                            continue
                        cancelled_allocations.append(_build_alloc_cancel_payload(alloc, act, job=job, reason=reason, user=request.user))
                        alloc.status = 'cancelled'
                        alloc.save(update_fields=['status'])

                    # ── Reset JobActivity allocation fields after cancelling allocations ──
                    active_allocated = act.allocations.filter(
                        status__in=['scheduled', 'in_progress']
                    ).aggregate(total=models.Sum('allocated_area'))['total'] or Decimal('0')

                    if active_allocated <= 0:
                        act.allocated_area    = Decimal('0')
                        act.remaining_area    = act.total_area
                        act.allocation_status = 'pending'
                        act.is_fully_allocated = False
                    else:
                        act.allocated_area    = active_allocated
                        act.remaining_area    = max(Decimal('0'), act.total_area - active_allocated)
                        act.is_fully_allocated = active_allocated >= act.total_area
                        act.allocation_status  = 'fully_allocated' if act.is_fully_allocated else 'partially_allocated'

                    act.save(update_fields=[
                        'allocated_area', 'remaining_area',
                        'allocation_status', 'is_fully_allocated',
                    ])

                act.is_lost     = True
                act.lost_reason = reason
                if request.user.is_authenticated:
                    act.last_moved_by = request.user
                    act.last_moved_at = timezone.now()
                act.save(update_fields=['is_lost', 'lost_reason', 'last_moved_by', 'last_moved_at'])
                cancelled_activities.append({
                    'activity_id':    act.id,
                    'activity_name':  act.activity.name,
                    'scheduled_date': str(act.scheduled_date),
                })

            job.status = 'cancelled'
            job.save(update_fields=['status'])

        from .signals import allocation_cancelled, job_cancelled
        for payload in cancelled_allocations:
            allocation_cancelled.send(sender=None, payload=payload)

        job_cancelled.send(sender=None, payload={
            "job_id":            job.job_id,
            "booking_id":        job.booking.booking_id if job.booking else None,
            "farmer_id":         job.farmer.farmer_id,
            "farmer_name":       job.farmer.farmer_name,
            "cancel_reason":     reason,
            "cancelled_at":      str(timezone.now()),
            "cancelled_by_id":   request.user.id if request.user.is_authenticated else None,
            "cancelled_by_name": request.user.get_full_name() or request.user.username if request.user.is_authenticated else None,
            "allocations_cancelled":     cancel_allocs,
            "cancelled_activities":      cancelled_activities,
            "cancelled_allocations_count": len(cancelled_allocations),
            "skipped_allocations_count": len(skipped_allocations),
        })

        return Response({
            'success':               True,
            'message':               f'Job {job.job_id} cancelled',
            'cancel_reason':         reason,
            'allocations_cancelled': cancel_allocs,
            'cancelled_activities':  cancelled_activities,
            'cancelled_allocations': cancelled_allocations,
            'skipped_allocations':   skipped_allocations,
        }, status=200)
    
    
    
    @action(detail=False, methods=['get'])
    def pending_jobs(self, request):
        """
        Get all jobs with remaining work
        
        GET /api/jobs/pending_jobs/
        """
        jobs = self.get_queryset().filter(
            activities__is_fully_allocated=False
        ).distinct()
        
        serializer = self.get_serializer(jobs, many=True)
        return Response({
            'count': jobs.count(),
            'jobs': serializer.data
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def activity_dashboard(request):
    from datetime import date, timedelta
    from decimal import Decimal

    today = date.today()
    
    cluster_id    = request.query_params.get('cluster_id')
    status_filter = request.query_params.get('status')
    date_from     = request.query_params.get('date_from')
    date_to       = request.query_params.get('date_to')
    search        = request.query_params.get('search')
    upcoming      = request.query_params.get('upcoming')
    last10        = request.query_params.get('last10')

    qs = JobActivity.objects.filter(
        job__booking_type__in=['tender', 'ondemand'],  
        total_area__gt=0,
        is_lost=False,
    ).select_related(
        'job__farmer',
        'job__booking', 
        'activity',
        'plot',
    ).prefetch_related(
        'job__clusters',
        'plot__clusters',
        Prefetch(
            'allocations',
            queryset=Allocation.objects.select_related('mukkadam', 'cluster').order_by('allocated_date'),
        )
    ).order_by('scheduled_date', 'job__farmer__farmer_name')

    if cluster_id:
        qs = qs.filter(
            models.Q(plot__clusters__id=cluster_id) |
            models.Q(job__farmer__clusters__id=cluster_id)
        ).distinct()

    if status_filter:
        if status_filter == 'pending':
            qs = qs.filter(allocation_status='pending')

        elif status_filter == 'in_progress':
            qs = qs.filter(
                allocation_status__in=['partially_allocated', 'fully_allocated']
            ).exclude(
                id__in=JobActivity.objects.filter(
                    allocation_status__in=['partially_allocated', 'fully_allocated']
                ).annotate(
                    total_allocs=models.Count('allocations'),
                    done_allocs=models.Count(
                        'allocations',
                        filter=models.Q(allocations__work_status='completed')
                    )
                ).filter(
                    total_allocs__gt=0,
                    total_allocs=models.F('done_allocs')
                ).values_list('id', flat=True)
            )

        elif status_filter == 'completed':
            qs = qs.annotate(
                total_allocs=models.Count('allocations'),
                done_allocs=models.Count(
                    'allocations',
                    filter=models.Q(allocations__work_status='completed')
                )
            ).filter(
                total_allocs__gt=0,
                total_allocs=models.F('done_allocs')
            )

        else:
            qs = qs.filter(allocation_status=status_filter)

    if date_from:
        qs = qs.filter(scheduled_date__gte=date_from)
    if date_to:
        qs = qs.filter(scheduled_date__lte=date_to)
    if upcoming == '1':
        qs = qs.filter(
            scheduled_date__gte=today,
            scheduled_date__lte=today + timedelta(days=10),
        )
    if last10 == '1':
        qs = qs.filter(
            scheduled_date__gte=today - timedelta(days=10),
            scheduled_date__lte=today,
        )
    if search:
        qs = qs.filter(
            models.Q(job__farmer__farmer_name__icontains=search) |
            models.Q(job__job_id__icontains=search) |
            models.Q(activity__name__icontains=search) |
            models.Q(plot__name__icontains=search)
        )

    # ── Build data with dedup by (job_id, plot_id, api_activity_id) ──
    STATUS_PRIORITY = {
        'pending': 0,
        'partially_allocated': 1,
        'fully_allocated': 2,
        'in_progress': 3,
        'completed': 4,
    }

    # key → merged item
    merged: dict = {}

    for a in qs:
        job    = a.job
        farmer = job.farmer
        plot   = a.plot

        clusters = list(plot.clusters.all()) if plot else []
        if not clusters:
            clusters = list(job.clusters.all())
        if not clusters:
            clusters = list(farmer.clusters.all())

        allocations = list(a.allocations.all())

        alloc_data = []
        total_mukkadam_est = Decimal('0')
        for alloc in allocations:
            area = alloc.actual_area_done or alloc.allocated_area or Decimal('0')
            mukkadam_est = (area * Decimal(str(alloc.mukkadam_rate or 0))).quantize(Decimal('0.01'))
            total_mukkadam_est += mukkadam_est
            farmer_amount = (area * Decimal(str(alloc.farmer_rate or 0))).quantize(Decimal('0.01'))
            alloc_data.append({
                'allocation_id':     alloc.id,
                'farmer_amount': float(farmer_amount),
                'mukkadam_id':       alloc.mukkadam.mukkadam_id,
                'mukkadam_name':     alloc.mukkadam.mukkadam_name,
                'mukkadam_mobile':   alloc.mukkadam.mobile_numbers,
                'cluster_name':      alloc.cluster.name if alloc.cluster else None,
                'allocated_date':    str(alloc.allocated_date) if alloc.allocated_date else None,
                'allocated_area':    float(alloc.allocated_area or 0),
                'allocated_workers': alloc.allocated_workers or 0,
                'actual_area_done':  float(alloc.actual_area_done) if alloc.actual_area_done else None,
                'actual_crew_size':  alloc.actual_crew_size,
                'mukkadam_rate':     float(alloc.mukkadam_rate or 0),
                'farmer_rate':       float(alloc.farmer_rate or 0),
                'mukkadam_est':      float(mukkadam_est),
                'work_status':       alloc.work_status,
                'payment_status':    alloc.payment_status,
                'report_submitted':  alloc.report_submitted,
                'farmer_agreed':     alloc.farmer_agreed,
                # which split this allocation belongs to
                'split_activity_id': a.id,
            })

        days_until = (a.scheduled_date - today).days if a.scheduled_date else None

        # Dedup key — same logic as summary card
        dedup_key = f"{a.job.job_id}-{a.plot_id}-{a.api_activity_id}"

        if dedup_key not in merged:
            merged[dedup_key] = {
                # Primary activity id (first split)
                'activity_id':        a.id,
                'activity_name':      a.activity.name,
                'api_activity_id':    a.api_activity_id,
                'allocation_status':  a.allocation_status,
                'scheduled_date':     str(a.scheduled_date) if a.scheduled_date else None,
                'days_until':         days_until,
                'sales_date': str(a.sales_date) if a.sales_date else None,
                'total_area':         float(a.total_area),
                'allocated_area':     float(a.allocated_area),
                'remaining_area':     float(a.remaining_area),
                'rate_per_acre':      float(a.rate_per_acre or 0),
                'total_price':        float(a.total_price or 0),
                'total_mukkadam_est': float(total_mukkadam_est),
                # Job
                'job_id':             job.job_id,
                'job_status':         job.status,
                'booking_type':       job.booking_type,  
                'booking_id':         job.booking.booking_id if job.booking else None, 
                'crop_name':          job.crop_name,
                'variety':            getattr(plot, 'variety', '') if plot else getattr(job, 'variety', ''),
                # Farmer
                # Farmer
                'farmer_id':          farmer.farmer_id,
                'farmer_name':        farmer.farmer_name,
                'farmer_phone':       farmer.phone_number,
                'farmer_village':     clusters[0].village  if clusters else '',
                'farmer_taluka':      clusters[0].taluka   if clusters else '',
                'farmer_district':    clusters[0].district if clusters else '',
                # Plot
                'plot_id':            plot.id if plot else None,
                'plot_name':          plot.name if plot else '—',
                'plot_code':          plot.plot_code if plot else '—',
                'plot_area':          float(plot.area_acres) if plot else 0,
                # Clusters
                # Clusters (plot/job clusters — used for display)
                'clusters':           [{'id': c.id, 'name': c.name} for c in clusters],
                # Farmer's own clusters — used for capacity lookup
                'farmer_clusters':    [{'id': c.id, 'name': c.name} for c in farmer.clusters.all()],
                # Allocations (merged across splits)
                'allocations':        alloc_data,
                'allocation_count':   len(alloc_data),
                # Split tracking
                'is_split':           False,
                'splits': [{
                    'activity_id':       a.id,
                    'scheduled_date':    str(a.scheduled_date) if a.scheduled_date else None,
                    'total_area':        float(a.total_area),
                    'allocated_area':    float(a.allocated_area),
                    'remaining_area':    float(a.remaining_area),
                    'allocation_status': a.allocation_status,
                    'allocation_count':  len(alloc_data),
                }],
            }
        else:
            # ── Merge this split into existing entry ──
            existing = merged[dedup_key]
            existing['is_split']           = True
            existing['total_area']         += float(a.total_area)
            existing['allocated_area']     += float(a.allocated_area)
            existing['remaining_area']     += float(a.remaining_area)
            existing['total_price']        += float(a.total_price or 0)
            existing['total_mukkadam_est'] += float(total_mukkadam_est)
            existing['allocations']        += alloc_data
            existing['allocation_count']   += len(alloc_data)

            # Keep earliest scheduled_date
            if a.scheduled_date and (
                existing['scheduled_date'] is None or
                str(a.scheduled_date) < existing['scheduled_date']
            ):
                existing['scheduled_date'] = str(a.scheduled_date)
                existing['days_until']     = days_until

            # Keep worst (lowest priority) status
            if STATUS_PRIORITY.get(a.allocation_status, 0) < STATUS_PRIORITY.get(existing['allocation_status'], 0):
                existing['allocation_status'] = a.allocation_status

            # In the merge block, replace existing['splits'].append:
            existing['splits'].append({
                'id':                a.id,
                'activity_id':       a.id,
                'scheduled_date':    str(a.scheduled_date) if a.scheduled_date else None,
                'total_area':        float(a.total_area),
                'sales_date': str(a.sales_date) if a.sales_date else None,
                'allocated_area':    float(a.allocated_area),
                'remaining_area':    float(a.remaining_area),
                'allocation_status': a.allocation_status,
                'allocation_count':  len(alloc_data),
                'allocations':       alloc_data,  # ← add this
            })

    data = list(merged.values())

    return Response({
        'count': len(data),
        'activities': data,
    })

from rest_framework.decorators import api_view
from datetime import datetime, timedelta


# Add this constant at the top of your file (or in a constants.py)

ACTIVITY_SEQUENCE_ORDER = {
    # --- Phase 1: Initiation ---
    "Pruning (छाटणी)": 10,
    "Pruning (छाटणी) 1": 11,
    "Pruning (छाटणी) 2": 12,
    "Hand Pasting (पेस्टींग)": 13,
    # --- Phase 2: Early Shoot Management ---
    "Shoot Selection (विरळणी)": 20,
    "Shoot Selection (विरळणी) 1": 21,
    "Cordan Tying (ओलांढे बांधणे)": 22,
    "Full Cordan Tying": 23,
    "Full Cordan Tying (सरसकट ओलांढे बांधणे)": 24,
    "Cordan Tying (सुटलेले ओलांढे बांधणे)": 25,
    "Extra Leaf removal (पाने काढणे)": 26,
    "Extra Leaf Removal (पाने काढणे) 1": 27,
    "Extra Leaf Removal (पाने काढणे) 2": 28,
    "(Extra) Early Leaf Removal - Scissor": 29,
    # --- Phase 3: Primary Subcane & Cleaning ---
    "1st Subcane (पहिली सबकेन)": 30,
    "One Time Subcane (सबकेन)": 31,
    "One Time Subcane (एकदाच सबकेन करणे) 1": 32,
    "1st Lateral Removal (बगल काढणे)": 33,
    "1st Lateral Removal (बगल काढणे) 1": 34,
    "1st Round Extra Leaf removal": 35,
    # --- Phase 4: Secondary Subcane & Cleaning ---
    "2nd Subcane (दुसरी सबकेन)": 40,
    "Subcane (सबकेन) 1": 41,
    "2nd Laterals Removal & Tendrils Removal (दुसरी बगल बाळी काढणे)": 42,
    "2nd Lateral Removal & Tendrils Removal (दुसरी बगल बाळी काढणे) 1": 43,
    "2nd Laterals Removal & Tendrils Removal (दुसरी बगल बाळी काढणे) 1": 44,
    "2nd Round Extra Leaf removal": 45,
    # --- Phase 5: Tertiary Subcane & Maturation ---
    "3rd Subcane (तिसरी सबकेन)": 50,
    "Subcane (सबकेन) 2": 51,
    "Subcane (सबकेन) 3": 52,
    "3rd Round Extra Leaf removal": 53,
    "Shenda Stopping (शेंडा स्टॉपिंग)": 54,
    "Shenda Stopping (शेंडा स्टॉपिंग) 1": 55,
    # --- Phase 6: Final Selection & Support ---
    "Finger Thinning (बोटाळणी)": 60,
    "Cane Selection (काडी निवड)": 61,
    "Cane Tying with Clips (काढी बांधणे)": 62,
    "Cane Tying with Clips (काढी बांधणे) 1": 63,
    "Cane Tying with Clips (काडी बांधणे - क्लिप्स)": 64,
    "Cane Tying with Strings/Thread": 65,
    "Cane Tying with Strings/Thread (काडी बांधणे - सुतळी)": 66,
    "Cane Tying with Strings/Thread (काडी बांधणे - सुतळी) 1": 67,
}

def get_activity_sequence_order(job_activity):
    """Return the phase-based sequence order for sorting. Unknown activities go last."""
    return ACTIVITY_SEQUENCE_ORDER.get(job_activity.activity.name, 999)

@api_view(['GET'])
def suggest_activity_date(request):
    """
    GET /api/activity-schedule/suggest-date/?base_date=2026-02-10&cluster_id=1&activity_id=5
    Returns: {"suggested_date": "2026-02-13"}
    """
    base_date_str = request.query_params.get('base_date')
    cluster_id = request.query_params.get('cluster_id')
    activity_id = request.query_params.get('activity_id')
    
    if not (base_date_str and cluster_id and activity_id):
        return Response(
            {'error': 'base_date, cluster_id, activity_id required'}, 
            status=400
        )
    
    try:
        base_date = datetime.strptime(base_date_str, '%Y-%m-%d').date()
        cluster = Cluster.objects.get(pk=cluster_id)
        activity = ActivityCatalog.objects.get(pk=activity_id)
        gap = effective_gap_days(cluster, activity)
        suggested = base_date + timedelta(days=gap)
        return Response({'suggested_date': suggested.isoformat()})
    except Exception as e:
        return Response({'error': str(e)}, status=400)
import logging
logger = logging.getLogger(__name__)
from .utils import get_effective_crew_size 
from rest_framework.decorators import api_view

def _build_gap_map_and_cascade(
    subsequent_qs,          # queryset or list of activities to cascade
    exclude_ids,            # set of IDs to skip (original + new split)
    current_seq_order,      # get_activity_sequence_order of the moved activity
    reference_date,         # starting anchor (new_date_obj / new_date)
    reason_prefix,          # string for move_reason
    request,
):
    """
    Shared cascade logic for move, change_date, and delete_allocation.

    Returns (shifted_activities, warnings).
    """
    from datetime import date, timedelta

    # Sort the activities we'll actually walk
    subsequent = [a for a in subsequent_qs if a.id not in exclude_ids]
    subsequent.sort(key=lambda a: (
        get_activity_sequence_order(a),
        a.scheduled_date or date.min,
        a.id,
    ))

    # Build gap_map from the FILTERED + SORTED list, not the full all_activities list.
    # This ensures each gap is relative to the actual previous node in the cascade chain.
    gap_map = {}
    prev_act = None
    for act in subsequent:
        if get_activity_sequence_order(act) <= current_seq_order:
            prev_act = act  # track predecessors so first eligible successor gets right gap
            continue
        if prev_act is None:
            gap_map[act.id] = act.original_gap_days or 0
        elif act.original_gap_days is not None:
            gap_map[act.id] = act.original_gap_days
        elif act.scheduled_date and prev_act.scheduled_date:
            gap_map[act.id] = (act.scheduled_date - prev_act.scheduled_date).days
        else:
            gap_map[act.id] = 0
        prev_act = act

    shifted_activities = []
    warnings = []

    for act in subsequent:
        if get_activity_sequence_order(act) <= current_seq_order:
            continue

        # Allocated / completed → stays fixed, reset reference anchor
        if act.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
            reference_date = act.scheduled_date
            warnings.append({
                'activity_id':   act.id,
                'activity_name': act.activity.name,
                'old_date':      str(act.scheduled_date),
                'new_date':      str(act.scheduled_date),
                'message':       f'Skipped — already {act.allocation_status}. '
                                 f'Becomes new reference anchor ({act.scheduled_date}).',
            })
            continue

        # Manually moved → skip, but still advance reference so chain stays correct
        if act.is_manually_moved:
            # BUG FIX: advance reference_date even for skipped nodes
            if act.scheduled_date:
                reference_date = act.scheduled_date
            warnings.append({
                'activity_id':   act.id,
                'activity_name': act.activity.name,
                'old_date':      str(act.scheduled_date),
                'new_date':      str(act.scheduled_date),
                'message':       'Skipped — manually moved (reference advanced)',
            })
            continue

        # Zero area → skip (do NOT advance reference — this node has no date anchor)
        if not act.total_area or act.total_area <= 0:
            warnings.append({
                'activity_id':   act.id,
                'activity_name': act.activity.name,
                'old_date':      str(act.scheduled_date),
                'new_date':      str(act.scheduled_date),
                'message':       'Skipped — zero area',
            })
            continue

        # Unallocated → recalculate
        gap          = gap_map.get(act.id, 0)
        old_date     = act.scheduled_date
        new_act_date = reference_date + timedelta(days=gap)

        act.scheduled_date = new_act_date
        act.move_reason    = f'{reason_prefix} (cascade)'
        if request.user and request.user.is_authenticated:
            act.last_moved_by = request.user
            act.last_moved_at = timezone.now()
        act.save(update_fields=[
            'scheduled_date', 'move_reason',
            'last_moved_by', 'last_moved_at',
        ])

        reference_date = new_act_date  # advance anchor

        shifted_activities.append({
            'activity_id':   act.id,
            'activity_name': act.activity.name,
            'old_date':      str(old_date),
            'new_date':      str(new_act_date),
            'gap_used':      gap,
            'status':        act.allocation_status,
        })

    return shifted_activities, warnings


def _build_gap_map_and_cascade(
    subsequent_qs,
    exclude_ids,
    current_seq_order,
    reference_date,
    reason_prefix,
    request,
):
    from datetime import date, timedelta

    # Filter out zero-area and excluded activities immediately
    subsequent = [
        a for a in subsequent_qs
        if a.id not in exclude_ids
        and a.total_area
        and a.total_area > 0        # zero-area activities ignored entirely
        and not a.is_lost
    ]
    subsequent.sort(key=lambda a: (
        get_activity_sequence_order(a),
        a.scheduled_date or date.min,
        a.id,
    ))

    # Build gap_map walking only the filtered list.
    # Each gap is measured from the actual previous activity in this chain,
    # not from whatever happened to be before it in the full unfiltered list.
    gap_map = {}
    prev_act = None
    for act in subsequent:
        if get_activity_sequence_order(act) <= current_seq_order:
            prev_act = act  # still track predecessors so the first successor gets correct gap
            continue
        if prev_act is None:
            gap_map[act.id] = act.original_gap_days or 0
        elif act.original_gap_days is not None:
            gap_map[act.id] = act.original_gap_days
        elif act.scheduled_date and prev_act.scheduled_date:
            gap_map[act.id] = (act.scheduled_date - prev_act.scheduled_date).days
        else:
            gap_map[act.id] = 0
        prev_act = act

    shifted_activities = []
    warnings = []

    for act in subsequent:
        if get_activity_sequence_order(act) <= current_seq_order:
            continue

        # Allocated / completed → stays fixed, becomes new reference anchor
        if act.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
            reference_date = act.scheduled_date
            warnings.append({
                'activity_id':   act.id,
                'activity_name': act.activity.name,
                'old_date':      str(act.scheduled_date),
                'new_date':      str(act.scheduled_date),
                'message':       f'Skipped — already {act.allocation_status}. '
                                 f'Becomes new reference anchor ({act.scheduled_date}).',
            })
            continue

        # Manually moved → skip, but advance reference so the next activity
        # measures its gap from here, not from the moved activity before it
        if act.is_manually_moved:
            if act.scheduled_date:
                reference_date = act.scheduled_date
            warnings.append({
                'activity_id':   act.id,
                'activity_name': act.activity.name,
                'old_date':      str(act.scheduled_date),
                'new_date':      str(act.scheduled_date),
                'message':       'Skipped — manually moved (reference advanced)',
            })
            continue

        # Unallocated → recalculate date = reference_date + gap
        gap          = gap_map.get(act.id, 0)
        old_date     = act.scheduled_date
        new_act_date = reference_date + timedelta(days=gap)

        act.scheduled_date = new_act_date
        act.move_reason    = f'{reason_prefix} (cascade)'
        if request.user and request.user.is_authenticated:
            act.last_moved_by = request.user
            act.last_moved_at = timezone.now()
        act.save(update_fields=[
            'scheduled_date', 'move_reason',
            'last_moved_by', 'last_moved_at',
        ])

        reference_date = new_act_date  # advance anchor for next activity

        shifted_activities.append({
            'activity_id':   act.id,
            'activity_name': act.activity.name,
            'old_date':      str(old_date),
            'new_date':      str(new_act_date),
            'gap_used':      gap,
            'status':        act.allocation_status,
        })

    return shifted_activities, warnings
# =============================================================================
# MUKKADAM VIEWSET
# =============================================================================
class JobActivityViewSet(viewsets.ModelViewSet):
    queryset = JobActivity.objects.all().select_related('job', 'activity', 'plot')
    serializer_class = JobActivityCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return JobActivitySerializer
        return JobActivityCreateUpdateSerializer
    
    def update(self, request, *args, **kwargs):
        """Override update to add validation for total_area"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Validate total_area if it's being updated
        new_total_area = request.data.get('total_area')
        if new_total_area is not None:
            new_total_area = Decimal(str(new_total_area))
            if new_total_area < instance.allocated_area:
                return Response(
                    {
                        'error': 'Total area cannot be less than allocated area',
                        'allocated_area': float(instance.allocated_area),
                        'requested_area': float(new_total_area)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """PATCH method"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        ctx(flow="activity_move", ja_id=pk,
            user=str(request.user.id if request.user.is_authenticated else "anon"))

        from datetime import date, timedelta
        from decimal import Decimal

        activity = self.get_object()

        new_date = request.data.get('new_date')
        area     = request.data.get('area')
        reason   = request.data.get('reason', '').strip()

        # ── Basic input validation ────────────────────────────────────────────────
        if not new_date:
            return Response({'error': 'new_date is required'}, status=400)
        if not reason:
            return Response({'error': 'reason is required'}, status=400)

        try:
            new_date_obj = date.fromisoformat(new_date)
        except ValueError:
            return Response({'error': 'Invalid new_date format. Use YYYY-MM-DD'}, status=400)

        try:
            area = Decimal(str(area))
        except Exception:
            return Response({'error': 'Invalid area'}, status=400)

        if area <= 0:
            return Response({'error': 'Area must be greater than 0'}, status=400)

        if area > activity.remaining_area:
            ops("activity_move_blocked", ja_id=pk,
        reason="area_exceeds_remaining",
        requested=str(area), remaining=str(activity.remaining_area))
            return Response(
                {'error': f'Area ({area}) exceeds remaining area ({activity.remaining_area} ac)'},
                status=400,
            )

        all_activities = list(
            JobActivity.objects.filter(
                job=activity.job,
                plot=activity.plot,
                total_area__gt=0,
                is_lost=False,
            ).select_related('activity')
        )
        all_activities.sort(key=lambda a: (
            get_activity_sequence_order(a),
            a.scheduled_date or date.min,
            a.id,
        ))

        try:
            current_idx = next(i for i, a in enumerate(all_activities) if a.id == activity.id)
        except StopIteration:
            return Response({'error': 'Activity not found in job sequence'}, status=400)

        successors = all_activities[current_idx + 1:]

        # ── Snapshot gaps BEFORE any writes ──────────────────────────────────────
        gap_map = {}
        for i, act in enumerate(all_activities):
            if i == 0:
                gap_map[act.id] = 0
            else:
                prev = all_activities[i - 1]
                if act.original_gap_days is not None:
                    gap_map[act.id] = act.original_gap_days
                else:
                    if act.scheduled_date and prev.scheduled_date:
                        gap_map[act.id] = (act.scheduled_date - prev.scheduled_date).days
                    else:
                        gap_map[act.id] = 0

        original_date = activity.scheduled_date

        # ── Capture full before-state of the original activity ───────────────────
        original_snapshot = {
            'total_area':       float(activity.total_area),
            'allocated_area':   float(activity.allocated_area),
            'remaining_area':   float(activity.remaining_area),
            'scheduled_date':   str(activity.scheduled_date),
            'allocation_status': activity.allocation_status,
            'is_manually_moved': activity.is_manually_moved,
            'move_reason':      activity.move_reason,
        }

        # ── Atomic writes + logging ───────────────────────────────────────────────
        with transaction.atomic():

            # 1. Shrink original activity ─────────────────────────────────────────
            activity.total_area      = activity.total_area - area
            activity.move_reason     = reason
            activity.is_manually_moved = True
            if request.user and request.user.is_authenticated:
                activity.last_moved_by = request.user
                activity.last_moved_at = timezone.now()
            activity.save()
            ops("activity_move_shrunk", ja_id=activity.id,
    job_id=str(activity.job.job_id),
    area_split=str(area),
    from_date=str(original_date),
    to_date=new_date,
    reason=reason)

            ActivityLogTender.objects.create(
                action       = 'JOB_ACTIVITY_UPDATED',
                job          = activity.job,
                job_activity = activity,
                performed_by = request.user if request.user.is_authenticated else None,
                details      = {
                    'event':        'split_source_shrunk',
                    'description':  (
                        f'Activity "{activity.activity.name}" shrunk by {float(area)} ac '
                        f'due to manual move. {float(area)} ac split off to {new_date}.'
                    ),
                    'move_reason':  reason,
                    'before': original_snapshot,
                    'after': {
                        'total_area':        float(activity.total_area),
                        'allocated_area':    float(activity.allocated_area),
                        'remaining_area':    float(activity.remaining_area),
                        'scheduled_date':    str(activity.scheduled_date),
                        'is_manually_moved': activity.is_manually_moved,
                        'move_reason':       activity.move_reason,
                    },
                    'area_split_off':  float(area),
                    'split_to_date':   new_date,
                },
            )

            # 2. Create new split activity ─────────────────────────────────────────
            new_activity = JobActivity.objects.create(
                job                     = activity.job,
                activity                = activity.activity,
                plot                    = activity.plot,
                is_strict               = activity.is_strict,
                total_area              = area,
                allocated_area          = Decimal('0'),
                remaining_area          = area,
                scheduled_date          = new_date_obj,
                original_scheduled_date = activity.original_scheduled_date or original_date,
                original_gap_days       = gap_map.get(activity.id, 0),
                rate_per_acre           = activity.rate_per_acre,
                transport_cost          = activity.transport_cost,
                other_cost              = activity.other_cost,
                estimated_workers       = activity.estimated_workers,
                location                = activity.location,
                is_manually_moved       = True,
                moved_from_activity     = activity,
                source                  = 'manual',
                original_source         = activity.original_source,
                move_reason             = reason,
                api_activity_id         = activity.api_activity_id,
                created_by              = request.user if request.user.is_authenticated else None,
                last_moved_by           = request.user if request.user.is_authenticated else None,
                last_moved_at           = timezone.now() if request.user.is_authenticated else None,
            )
            ops("activity_move_split_created",
    parent_ja_id=activity.id,
    new_ja_id=new_activity.id,
    area=str(area),
    scheduled_date=new_date,
    job_id=str(activity.job.job_id))

            ActivityLogTender.objects.create(
                action       = 'JOB_ACTIVITY_CREATED',
                job          = activity.job,
                job_activity = new_activity,
                performed_by = request.user if request.user.is_authenticated else None,
                details      = {
                    'event':        'split_activity_created',
                    'description':  (
                        f'New activity "{new_activity.activity.name}" created as a split '
                        f'of activity #{activity.id}. {float(area)} ac scheduled on {new_date}.'
                    ),
                    'move_reason':        reason,
                    'source_activity_id': activity.id,
                    'source_date':        str(original_date),
                    'snapshot': {
                        'total_area':               float(new_activity.total_area),
                        'allocated_area':            float(new_activity.allocated_area),
                        'remaining_area':            float(new_activity.remaining_area),
                        'scheduled_date':            str(new_activity.scheduled_date),
                        'original_scheduled_date':   str(new_activity.original_scheduled_date),
                        'original_gap_days':         new_activity.original_gap_days,
                        'rate_per_acre':             float(new_activity.rate_per_acre or 0),
                        'transport_cost':            float(new_activity.transport_cost or 0),
                        'other_cost':                float(new_activity.other_cost or 0),
                        'estimated_workers':         new_activity.estimated_workers,
                        'is_manually_moved':         True,
                        'source':                    'manual',
                    },
                },
            )

                        # 3. Cascade subsequent activities ─────────────────────────────────────
                    # 3. Cascade — simple uniform shift
        shifted_activities = []
        warnings = []

        if original_date:
            shift_days = (new_date_obj - original_date).days

            if shift_days != 0:
                subsequent = list(
                    JobActivity.objects.filter(
                        job=activity.job,
                        plot=activity.plot,
                        is_lost=False,
                        total_area__gt=0,
                    )
                    .exclude(id=activity.id)
                    .exclude(id=new_activity.id)
                    .select_related('activity')
                )
                # Sort by date only — no sequence order
                subsequent.sort(key=lambda a: (a.scheduled_date or date.min, a.id))

                for act in subsequent:
                    if not act.scheduled_date:
                        continue
                    # Only shift activities on or after the original date
                    if act.scheduled_date < original_date:
                        continue

                    # Skip allocated/completed
                    if act.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
                        warnings.append({
                            'activity_id': act.id,
                            'activity_name': act.activity.name,
                            'old_date': str(act.scheduled_date),
                            'new_date': str(act.scheduled_date),
                            'message': f'Skipped: already {act.allocation_status}.',
                        })
                        continue

                    old_date = act.scheduled_date
                    new_act_date = old_date + timedelta(days=shift_days)
                    act.scheduled_date = new_act_date
                    act.move_reason = f'Cascade from activity {activity.id} move: {reason}'
                    if request.user and request.user.is_authenticated:
                        act.last_moved_by = request.user
                        act.last_moved_at = timezone.now()
                    act.save(update_fields=[
                        'scheduled_date', 'move_reason',
                        'last_moved_by', 'last_moved_at', 'updated_at',
                    ])
                    ops("activity_move_cascade_shifted",
    trigger_ja_id=activity.id,
    affected_ja_id=act.id,
    old_date=str(old_date),
    new_date=str(new_act_date),
    shift_days=shift_days)

                    Allocation.objects.filter(job_activity=act).update(allocated_date=new_act_date)

                    shifted_activities.append({
                        'activity_id': act.id,
                        'activity_name': act.activity.name,
                        'old_date': str(old_date),
                        'new_date': str(new_act_date),
                        'shift_days': shift_days,
                    })

        ops("activity_move_done",
    ja_id=activity.id,
    job_id=str(activity.job.job_id),
    area=str(area),
    from_date=str(original_date),
    to_date=new_date,
    cascaded=len(shifted_activities),
    warnings=len(warnings))

        return Response(
            {
                'message':              f'{area} ac moved to {new_date}',
                'reason':               reason,
                'original_date':        str(original_date),
                'new_date':             new_date,
                'original_activity_id': activity.id,
                'original_remaining':   float(activity.remaining_area),
                'new_activity_id':      new_activity.id,
                'new_area':             float(area),
                'shifted_activities':   shifted_activities,
                'warnings':             warnings,
            },
            status=200,
        )
    
    
    # @action(detail=True, methods=['post'])
    # def move(self, request, pk=None):
    #     """
    #     Move an unallocated (or partially unallocated) JobActivity to a new date.

    #     Rules enforced:
    #     Rule 1  — Cannot move if an unallocated predecessor exists (unless cancelled).
    #     Rule 4  — Cannot move before the nearest allocated predecessor.
    #     Rule 4  — Cannot move after the nearest allocated successor.
    #     Rule 3  — If all downstream are unallocated, shift by delta.
    #     Rule 4  — If a downstream allocated activity exists, it stays fixed and
    #                 becomes the new reference anchor; unallocated activities after it
    #                 recalculate from that anchor using their original_gap_days.
    #     """
    #     from datetime import date, timedelta
    #     from decimal import Decimal

    #     activity = self.get_object()

    #     new_date  = request.data.get('new_date')
    #     area      = request.data.get('area')
    #     reason    = request.data.get('reason', '').strip()

    #     # ── Basic input validation ────────────────────────────────────────────────
    #     if not new_date:
    #         return Response({'error': 'new_date is required'}, status=400)
    #     if not reason:
    #         return Response({'error': 'reason is required'}, status=400)

    #     try:
    #         new_date_obj = date.fromisoformat(new_date)
    #     except ValueError:
    #         return Response({'error': 'Invalid new_date format. Use YYYY-MM-DD'}, status=400)

    #     try:
    #         area = Decimal(str(area))
    #     except Exception:
    #         return Response({'error': 'Invalid area'}, status=400)

    #     if area <= 0:
    #         return Response({'error': 'Area must be greater than 0'}, status=400)

    #     if area > activity.remaining_area:
    #         return Response(
    #             {'error': f'Area ({area}) exceeds remaining area ({activity.remaining_area} ac)'},
    #             status=400,
    #         )

    #     original_date = activity.scheduled_date  # capture before any write

    #     # ── Atomic writes ─────────────────────────────────────────────────────────
    #     with transaction.atomic():

    #         # ── 1. Shrink original activity ──────────────────────────────────────
    #         activity.total_area  = activity.total_area - area
    #         activity.move_reason = reason
    #         activity.is_manually_moved = True
    #         if request.user and request.user.is_authenticated:
    #             activity.last_moved_by = request.user
    #             activity.last_moved_at = timezone.now()
    #         activity.save()

    #         # ── 2. Create new split activity on new_date ─────────────────────────
    #         new_activity = JobActivity.objects.create(
    #             job                     = activity.job,
    #             activity                = activity.activity,
    #             plot                    = activity.plot,
    #             is_strict               = activity.is_strict,
    #             total_area              = area,
    #             allocated_area          = Decimal('0'),
    #             remaining_area          = area,
    #             scheduled_date          = new_date_obj,
    #             original_scheduled_date = activity.original_scheduled_date or original_date,
    #             original_gap_days       = activity.original_gap_days,
    #             rate_per_acre           = activity.rate_per_acre,
    #             transport_cost          = activity.transport_cost,
    #             other_cost              = activity.other_cost,
    #             estimated_workers       = activity.estimated_workers,
    #             location                = activity.location,
    #             is_manually_moved       = True,
    #             moved_from_activity     = activity,
    #             source                  = 'manual',
    #             original_source         = activity.original_source,
    #             move_reason             = reason,
    #             api_activity_id         = activity.api_activity_id,
    #             created_by              = request.user if request.user.is_authenticated else None,
    #             last_moved_by           = request.user if request.user.is_authenticated else None,
    #             last_moved_at           = timezone.now() if request.user.is_authenticated else None,
    #         )

    #         # ── 3. Cascade subsequent activities ─────────────────────────────────
    #         shifted_activities = []
    #         warnings           = []

    #         if original_date:
    #             shifted_activities, warnings = _build_gap_map_and_cascade(
    #                 subsequent_qs=JobActivity.objects.filter(
    #                     job=activity.job,
    #                     plot=activity.plot,
    #                     is_lost=False,
    #                 ).exclude(id=activity.id).exclude(id=new_activity.id).select_related('activity'),
    #                 exclude_ids={activity.id, new_activity.id},
    #                 current_seq_order=get_activity_sequence_order(activity),
    #                 reference_date=new_date_obj,
    #                 reason_prefix=f'Cascade from activity {activity.id} move: {reason}',
    #                 request=request,
    #             )

    #     return Response(
    #         {
    #             'message':              f'{area} ac moved to {new_date}',
    #             'reason':               reason,
    #             'original_date':        str(original_date),
    #             'new_date':             new_date,
    #             'original_activity_id': activity.id,
    #             'original_remaining':   float(activity.remaining_area),
    #             'new_activity_id':      new_activity.id,
    #             'new_area':             float(area),
    #             'shifted_activities':   shifted_activities,
    #             'warnings':             warnings,
    #         },
    #         status=200,
    #     )
    
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        ctx(flow="activity_cancel", ja_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        activity = self.get_object()

        # ── Make sure all related objects are loaded ──
        activity = JobActivity.objects.select_related(
            'job__farmer',
            'job__booking',
            'activity',
            'plot',
        ).get(id=activity.id)

        reason        = request.data.get('reason', '').strip()
        cancel_allocs = bool(request.data.get('cancel_allocations', False))

        if not reason:
            return Response({'error': 'reason is required'}, status=400)
        if activity.is_lost:
            return Response({'error': 'Activity is already cancelled'}, status=400)

        cancelled_allocations = []
        skipped_allocations   = []

        with transaction.atomic():
            if cancel_allocs:
                for alloc in activity.allocations.filter(
                    status__in=['scheduled', 'in_progress']
                ).select_related('mukkadam'):
                    cancelled_allocations.append(
                        _build_alloc_cancel_payload(
                            alloc, activity, job=activity.job,
                            reason=reason, user=request.user
                        )
                    )
                    alloc.delete()
                    ops("activity_cancel_alloc_deleted",
    ja_id=activity.id,
    allocation_id=alloc.id,
    mukkadam=alloc.mukkadam.mukkadam_name,
    area=str(alloc.allocated_area))  # ← delete instead of cancel

                for alloc in activity.allocations.filter(
                    status='completed'
                ).select_related('mukkadam'):
                    skipped_allocations.append({
                        'allocation_id': alloc.id,
                        'mukkadam_name': alloc.mukkadam.mukkadam_name,
                        'message':       'Skipped — already completed',
                    })

                # ── Reset JA allocation fields ──
                active_allocated = activity.allocations.filter(
                    status__in=['scheduled', 'in_progress']
                ).aggregate(total=models.Sum('allocated_area'))['total'] or Decimal('0')

                if active_allocated <= 0:
                    activity.allocated_area     = Decimal('0')
                    activity.remaining_area     = activity.total_area
                    activity.allocation_status  = 'pending'
                    activity.is_fully_allocated = False
                else:
                    activity.allocated_area     = active_allocated
                    activity.remaining_area     = max(Decimal('0'), activity.total_area - active_allocated)
                    activity.is_fully_allocated = active_allocated >= activity.total_area
                    activity.allocation_status  = 'fully_allocated' if activity.is_fully_allocated else 'partially_allocated'

                activity.save(update_fields=[
                    'allocated_area', 'remaining_area',
                    'allocation_status', 'is_fully_allocated',
                ])

            activity.is_lost     = True
            activity.lost_reason = reason
            if request.user.is_authenticated:
                activity.last_moved_by = request.user
                activity.last_moved_at = timezone.now()
            activity.save(update_fields=['is_lost', 'lost_reason', 'last_moved_by', 'last_moved_at'])
            ops("activity_cancelled",
    ja_id=activity.id,
    job_id=str(activity.job.job_id),
    activity_name=activity.activity.name,
    cancel_allocs=cancel_allocs,
    allocs_cancelled=len(cancelled_allocations),
    skipped=len(skipped_allocations),
    reason=reason)
        # ── Fire signals outside transaction ──
        from .signals import allocation_cancelled, activity_cancelled

        # Fire per cancelled allocation
        for payload in cancelled_allocations:
            try:
                allocation_cancelled.send(sender=None, payload=payload)
            except Exception as e:
                logger.error(f"[SIGNAL] allocation_cancelled failed: {e}")
                err("activity_cancel_signal_fail",
        ja_id=activity.id, signal="allocation_cancelled")

        # Fire single activity-level cancel signal
        try:
            activity_cancelled.send(sender=None, payload={     # 👈 correct signal now
                "activity_id":     activity.id,
                "booking_id":      activity.job.booking.booking_id if activity.job.booking else None,
                "api_activity_id": activity.api_activity_id or None,
                "activity_name":   activity.activity.name,
                "job_id":          activity.job.job_id,
                "farmer_id":       activity.job.farmer.farmer_id,
                "farmer_name":     activity.job.farmer.farmer_name,
                "total_area":      float(activity.total_area),
                "scheduled_date":  str(activity.scheduled_date) if activity.scheduled_date else None,
                "cancel_reason":   reason,
                "cancelled_at":    str(timezone.now()),
                "cancelled_by_id":   request.user.id if request.user.is_authenticated else None,
                "cancelled_by_name": request.user.get_full_name() or request.user.username if request.user.is_authenticated else None,
                "allocations_cancelled": cancel_allocs,
                "cancelled_allocations_count": len(cancelled_allocations),
                "skipped_allocations_count":   len(skipped_allocations),
            })
        except Exception as e:
            logger.error(f"[SIGNAL] activity_cancelled failed: {e}")
            err("activity_cancel_signal_fail",
        ja_id=activity.id, signal="activity_cancelled")

        return Response({
            'success':               True,
            'message':               f'Activity {activity.id} cancelled',
            'cancel_reason':         reason,
            'allocations_cancelled': cancel_allocs,
            'cancelled_allocations': cancelled_allocations,
            'skipped_allocations':   skipped_allocations,
        }, status=200)


    @action(detail=True, methods=['delete'])
    def hard_delete(self, request, pk=None):
        ctx(flow="activity_hard_delete", ja_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        activity = JobActivity.objects.select_related(
            'job__farmer',
            'job__booking',
            'activity',
            'plot',
        ).get(id=pk)

        if activity.allocation_status == 'completed':
            ops("hard_delete_blocked", ja_id=pk,
        reason="completed_activity",
        job_id=str(activity.job.job_id))
            return Response({'error': 'Cannot delete a completed activity'}, status=400)

        reason = request.data.get('reason', '').strip()

        with transaction.atomic():
            # Cancel non-completed allocations first
            for alloc in activity.allocations.exclude(status='completed'):
                alloc.status = 'cancelled'
                alloc.save(update_fields=['status'])

            activity.delete()
            ops("activity_hard_deleted",
    ja_id=pk,
    job_id=str(activity.job.job_id),
    activity_name=activity.activity.name,
    reason=reason or "none",
    user=str(request.user))

        logger.info(
            f"[HARD DELETE] Activity {pk} ({activity.activity.name}) "
            f"on job {activity.job.job_id} deleted by {request.user} — reason: {reason or 'none'}"
        )

        return Response({
            'success':    True,
            'message':    f'Activity {pk} permanently deleted',
            'reason':     reason or None,
            'job_id':     activity.job.job_id,
            'activity':   activity.activity.name,
        }, status=200)


# views.py
import requests
from django.http import JsonResponse

def booking_map_proxy(request):
    resp = requests.get('https://ops.bharatintelligence.ai/ops/bookings/map/api/')
    return JsonResponse(resp.json())


@api_view(['POST'])
@permission_classes([AllowAny])
def mukkadam_misc_no_job(request, mukkadam_id):
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Mukkadam not found'}, status=404)

    amount  = request.data.get('amount')
    reason  = request.data.get('reason', '').strip()

    if not amount or float(amount) <= 0:
        return Response({'error': 'Invalid amount'}, status=400)
    if not reason:
        return Response({'error': 'Reason is required'}, status=400)

    cost = MukkadamMiscCost.objects.create(
        mukkadam=mukkadam,
        job=None,           # no job required
        amount=amount,
        reason=reason,
    )

    return Response({
        'id':         cost.id,
        'amount':     float(cost.amount),
        'reason':     cost.reason,
        'created_at': str(cost.created_at.date()),
        'verified':   cost.verified,
    }, status=201)
# views.py - Update MukkadamViewSet
# views.py - Add new viewset
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def mukkadam_misc_costs(request, mukkadam_id, job_id):
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
    except (Mukkadam.DoesNotExist, Job.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        costs = MukkadamMiscCost.objects.filter(mukkadam=mukkadam, job=job)
        return Response([{
            'id':         c.id,
            'amount':     float(c.amount),
            'reason':     c.reason,
            'created_at': str(c.created_at.date()),
            'verified':   c.verified,             # ← add this
        } for c in costs])

    # POST
    amount       = request.data.get('amount')
    reason       = request.data.get('reason', '').strip()
    proof_s3_key = request.data.get('proof_s3_key', None)   # ← optional

    if not amount or float(amount) <= 0:
        return Response({'error': 'Invalid amount'}, status=400)
    if not reason:
        return Response({'error': 'Reason is required'}, status=400)

    cost = MukkadamMiscCost.objects.create(
        mukkadam=mukkadam, job=job,
        amount=amount, reason=reason,
        proof_s3_key=proof_s3_key,   # ← None if not provided, that's fine
    )

    _recalculate_settlement_misc(mukkadam, job)

    return Response({
        'id':         cost.id,
        'amount':     float(cost.amount),
        'reason':     cost.reason,
        'created_at': str(cost.created_at.date()),
        'verified':   cost.verified,              # ← add this
    }, status=201)
@api_view(['DELETE'])
@permission_classes([AllowAny])
def mukkadam_misc_cost_delete(request, mukkadam_id, job_id, cost_id):
    """DELETE /api/mukkadam/<id>/job/<job_id>/misc/<cost_id>/"""
    try:
        cost = MukkadamMiscCost.objects.get(
            pk=cost_id, mukkadam_id=mukkadam_id, job__job_id=job_id
        )
    except MukkadamMiscCost.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    cost.delete()

    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
        _recalculate_settlement_misc(mukkadam, job)
    except Exception:
        pass

    return Response({'success': True})


def _recalculate_settlement_misc(mukkadam, job):
    """Update settlement net_payable after misc cost change."""
    from decimal import Decimal
    try:
        settlement = MukkadamJobSettlement.objects.get(mukkadam=mukkadam, job=job)
        total_misc = MukkadamMiscCost.objects.filter(
            mukkadam=mukkadam, job=job
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # net = payable + deposit_carried_forward - advance - weekly - misc
        settlement.net_payable = (
            settlement.payable_amount
            + settlement.deposit_carried_forward
            - settlement.advance_deducted
            - settlement.weekly_payments_deducted
            - total_misc
        )
        settlement.save()
    except MukkadamJobSettlement.DoesNotExist:
        pass


from .utils import get_presigned_url, get_presigned_urls_batch


class MukkadamActivityRateViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for mukkadam activity rates
    """
    queryset = MukkadamActivityRate.objects.all().select_related('mukkadam', 'activity')
    serializer_class = MukkadamActivityRateSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        mukkadam_id = self.request.query_params.get('mukkadam_id')
        if mukkadam_id:
            queryset = queryset.filter(mukkadam__mukkadam_id=mukkadam_id)
        
        return queryset.filter(is_active=True).order_by('activity__name')
# views.py - Update MukkadamViewSet
from .serializers import FarmerProfileSerializer, MukkadamProfileSerializer
class MukkadamViewSet(viewsets.ModelViewSet):
    qqueryset             = Mukkadam.objects.all().prefetch_related('clusters')
    serializer_class     = MukkadamSerializer
    permission_classes   = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        queryset = Mukkadam.objects.all().prefetch_related('clusters')  # ← directly, no super()

        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            queryset = queryset.filter(clusters__id=cluster_id).distinct()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(mukkadam_name__icontains=search) |
                Q(mobile_numbers__icontains=search)
            )
        return queryset.order_by('mukkadam_name')
    

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Pass selected date so serializer can compute allocated_on_date
        date = self.request.query_params.get('date')
        if date:
            ctx['selected_date'] = date
        return ctx
    
    @action(detail=True, methods=['get'], url_path='profile')
    def mukkadam_profile(self, request, pk=None):
        """
        GET /api/mukkadams/<mukkadam_id>/profile/
        Returns full denormalized profile: mukkadam + cluster assignments +
        activity rates + availability + allocations (last 30 days) +
        payments + weekly payments + leaves + extra workers + OTP requests.
        """
        try:
            mukkadam = (
                Mukkadam.objects
                .prefetch_related(
                    'clusters',
                    'activity_rates__activity',
                )
                .get(pk=pk)
            )
        except Mukkadam.DoesNotExist:
            return Response({'error': 'Mukkadam not found'}, status=404)
 
        serializer = MukkadamProfileSerializer(mukkadam, context={'request': request})
        return Response(serializer.data)

    # ── Set manual status ─────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def set_status(self, request, pk=None):
        from django.utils import timezone
        mukkadam   = self.get_object()
        new_status = request.data.get('status') or None
        note       = request.data.get('note', '')

        set_by = None
        try:
            from rest_framework.authtoken.models import Token
            token_key = request.headers.get('Authorization', '').replace('Token ', '').strip()
            if token_key:
                tok = Token.objects.select_related('user').filter(key=token_key).first()
                if tok:
                    set_by = tok.user.get_full_name() or tok.user.username
        except Exception:
            pass

        mukkadam.manual_status        = new_status
        mukkadam.manual_status_note   = note if new_status else ''
        mukkadam.manual_status_set_at = timezone.now() if new_status else None
        mukkadam.manual_status_set_by = set_by if new_status else None

        # Save only these fields
        mukkadam.save(update_fields=[
            'manual_status',
            'manual_status_note',
            'manual_status_set_at',
            'manual_status_set_by',
        ])

        return Response({
            'success':       True,
            'manual_status': mukkadam.manual_status,
        })
    @action(detail=True, methods=['post'])
    def add_activity_rate(self, request, pk=None):
        """
        Add or update activity rate for mukkadam
        POST /api/mukkadams/{mukkadam_id}/add_activity_rate/
        
        Body: {
            "activity_id": 1,
            "rate_per_acre": 1000,
            "productivity_per_worker": 0.15
        }
        """
        mukkadam = self.get_object()
        activity_id = request.data.get('activity_id')
        rate_per_acre = request.data.get('rate_per_acre')
        productivity_per_worker = request.data.get('productivity_per_worker', 0.150)
        
        if not activity_id or not rate_per_acre:
            return Response(
                {'error': 'activity_id and rate_per_acre required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            activity = ActivityCatalog.objects.get(id=activity_id)
            
            rate_obj, created = MukkadamActivityRate.objects.update_or_create(
                mukkadam=mukkadam,
                activity=activity,
                defaults={
                    'rate_per_acre': rate_per_acre,
                    'productivity_per_worker': productivity_per_worker,
                    'is_active': True
                }
            )
            
            return Response({
                'success': True,
                'message': 'Activity rate added' if created else 'Activity rate updated',
                'rate': MukkadamActivityRateSerializer(rate_obj).data
            })
        except ActivityCatalog.DoesNotExist:
            return Response(
                {'error': 'Activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def activity_rates_with_fallback(self, request, pk=None):
        """
        Get all activities with rates (mukkadam-specific → cluster → global)
        GET /api/mukkadams/{mukkadam_id}/activity_rates_with_fallback/?cluster_id={cluster_id}
        """
        mukkadam = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = ActivityCatalog.objects.all().order_by('name')
        result = []
        
        for activity in activities:
            # 1. Try mukkadam-specific rate
            mukkadam_rate = MukkadamActivityRate.objects.filter(
                mukkadam=mukkadam,
                activity=activity,
                is_active=True
            ).first()
            
            if mukkadam_rate:
                rate = float(mukkadam_rate.rate_per_acre)
                productivity = float(mukkadam_rate.productivity_per_worker)
                source = 'mukkadam'
            else:
                # 2. Try cluster rate
                cluster_rate = ClusterActivityRate.objects.filter(
                    cluster=cluster,
                    activity=activity
                ).first()
                
                if cluster_rate:
                    rate = float(cluster_rate.rate_per_acre)
                    source = 'cluster'
                else:
                    # 3. Use global default
                    rate = float(activity.default_rate_per_acre)
                    source = 'global'
                
                productivity = 0.150  # Default productivity
            
            result.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'rate_per_acre': rate,
                'productivity_per_worker': productivity,
                'rate_source': source,
                'is_strict': activity.is_strict
            })
        
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """
        Get mukkadam availability for date range
        
        GET /api/mukkadams/{id}/availability/?start_date=2026-02-01&end_date=2026-02-28
        """
        mukkadam = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create availability for date range
        from datetime import datetime, timedelta
        
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        availabilities = []
        current = start
         # or wherever you put it

        while current <= end:
            availability, created = MukkadamAvailability.objects.get_or_create(
                mukkadam=mukkadam,
                date=current,
                defaults={
                    'available_crew_size': get_effective_crew_size(mukkadam, current),
                    'is_available': True,
                    'allocated_workers': 0
                }
            )
            availability.available_crew_size = get_effective_crew_size(mukkadam, current)
            availability.save()
            
            serializer = MukkadamAvailabilitySerializer(availability)
            availabilities.append(serializer.data)
            
            current += timedelta(days=1)
        
        return Response(availabilities)
    
    @action(detail=True, methods=['post'])
    def update_availability(self, request, pk=None):
        """
        Update mukkadam availability for a specific date
        
        POST /api/mukkadams/{id}/update_availability/
        Body: {
            "date": "2026-02-15",
            "available_crew_size": 8,
            "is_available": true,
            "is_on_leave": false
        }
        """
        mukkadam = self.get_object()
        date = request.data.get('date')
        
        if not date:
            return Response(
                {'error': 'date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available_crew_size = request.data.get('available_crew_size', mukkadam.crew_size)
        is_available = request.data.get('is_available', True)
        is_on_leave = request.data.get('is_on_leave', False)
        
        availability, created = MukkadamAvailability.objects.update_or_create(
            mukkadam=mukkadam,
            date=date,
            defaults={
                'available_crew_size': get_effective_crew_size(mukkadam, date),
                'is_available': is_available,
                'is_on_leave': is_on_leave,
                'is_manually_set': True  # Mark as manually updated
            }
        )
        availability.available_crew_size = get_effective_crew_size(mukkadam, date)
        availability.save()
        
        serializer = MukkadamAvailabilitySerializer(availability)
        return Response({
            'success': True,
            'message': f'Availability updated for {date}',
            'availability': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def activity_rates(self, request, pk=None):
        """
        Get all activity rates for a mukkadam
        
        GET /api/mukkadams/{id}/activity_rates/
        """
        mukkadam = self.get_object()
        rates = mukkadam.activity_rates.filter(is_active=True).select_related('activity')
        
        serializer = MukkadamActivityRateSerializer(rates, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def daily_capacity(self, request, pk=None):
        mukkadam = self.get_object()
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        availability = get_mukkadam_availability(mukkadam.mukkadam_id, date)
        if not availability:
            return Response(
                {'error': 'Unable to fetch availability'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(availability)
    @action(detail=True, methods=['get'])
    def remaining_capacity(self, request, pk=None):
        """
        GET /tender/api/mukkadams/{id}/remaining_capacity/?date=2026-02-09
        """
        mukkadam = self.get_object()
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        info = get_mukkadam_remaining_workers(mukkadam.mukkadam_id, date)

        return Response({
            'effective_crew_size': info['effective_crew'],
            'used_workers': info['used_workers'],
            'available_crew_size': info['remaining_workers'],
        })
    
    
    @action(detail=False, methods=['get'])
    def available_on_date(self, request):
        """
        Get all mukkadams available on a specific date
        
        GET /api/mukkadams/available_on_date/?date=2026-02-15&min_workers=5
        """
        from .utils import get_available_mukkadams
        
        date = request.query_params.get('date')
        min_workers = int(request.query_params.get('min_workers', 1))
        activity_id = request.query_params.get('activity_id')
        
        if not date:
            return Response(
                {'error': 'date parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available = get_available_mukkadams(date, min_workers, activity_id)
        
        return Response({
            'date': date,
            'count': len(available),
            'mukkadams': available
        })
    
    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Get financial summary for mukkadam
        
        GET /api/mukkadams/{id}/financial_summary/?start_date=2026-02-01&end_date=2026-02-28
        """
        from .utils import calculate_mukkadam_financials
        
        mukkadam = self.get_object()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        financials = calculate_mukkadam_financials(
            mukkadam.mukkadam_id,
            start_date,
            end_date
        )
        
        if not financials:
            return Response(
                {'error': 'Unable to calculate financials'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(financials)
    @action(detail=False, methods=['get'])
    def daily_capacity_all(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date is required'}, status=400)

        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        cluster_id = request.query_params.get('cluster_id')

        # General holiday for this cluster → zero capacity
        if cluster_id:
            general = Leave.objects.filter(
                date=date,
                is_active=True,
                leave_type='general',
                cluster_id=cluster_id,
            ).first()
            if general:
                return Response({'date': date_str, 'total_capacity': 0})

        assignments = ClusterMukkadamAssignment.objects.filter(
            is_active=True,
            **({"cluster_id": cluster_id} if cluster_id else {})
        ).select_related('mukkadam')

        data = []
        for assignment in assignments:
            # 🔹 updown check
            if assignment.mukkadam_type == 'updown':
                available = False
                if assignment.updown_mode == 'range':
                    if assignment.updown_from_date and assignment.updown_to_date:
                        available = assignment.updown_from_date <= date <= assignment.updown_to_date
                elif assignment.updown_mode == 'specific':
                    available = date_str in (assignment.updown_specific_dates or [])
                if not available:
                    continue

            mukkadam = assignment.mukkadam
            crew = mukkadam.crew_size or 0

            used_across_all = Allocation.objects.filter(
                mukkadam=mukkadam,
                allocated_date=date,
                allows_second_job=False,          # ✅ skip half-day allocations
                status__in=['scheduled', 'in_progress'],
            ).aggregate(total=models.Sum('allocated_workers'))['total'] or 0

            on_leave = Leave.objects.filter(
                leave_type='mukkadam',
                mukkadam=mukkadam,
                date=date,
                is_active=True,
            ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

            remaining = max(crew - used_across_all - on_leave, 0)

            data.append({
                'mukkadam_id': mukkadam.mukkadam_id,
                'available_crew_size': remaining,
            })

        return Response(data)

    @action(detail=False, methods=['get'])
    def day_total_capacity(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'date is required'}, status=400)

        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        cluster_id = request.query_params.get('cluster_id')

        if not cluster_id:
            return Response({'error': 'cluster_id is required'}, status=400)

        # General holiday → zero for this cluster
        general = Leave.objects.filter(
            date=date,
            is_active=True,
            leave_type='general',
            cluster_id=cluster_id,
        ).first()
        if general:
            return Response({'date': date_str, 'total_capacity': 0})

        assignments = ClusterMukkadamAssignment.objects.filter(
            cluster_id=cluster_id,
            is_active=True,
        ).select_related('mukkadam')

        total = 0
        for assignment in assignments:
            # 🔹 updown check
            if assignment.mukkadam_type == 'updown':
                available = False
                if assignment.updown_mode == 'range':
                    if assignment.updown_from_date and assignment.updown_to_date:
                        available = assignment.updown_from_date <= date <= assignment.updown_to_date
                elif assignment.updown_mode == 'specific':
                    available = date_str in (assignment.updown_specific_dates or [])
                if not available:
                    continue

            mukkadam = assignment.mukkadam
            crew = mukkadam.crew_size or 0

            used_across_all = Allocation.objects.filter(
                mukkadam=mukkadam,
                allocated_date=date,
                allows_second_job=False,          # ✅ skip half-day allocations
                status__in=['scheduled', 'in_progress'],
            ).aggregate(total=models.Sum('allocated_workers'))['total'] or 0

            on_leave = Leave.objects.filter(
                leave_type='mukkadam',
                mukkadam=mukkadam,
                date=date,
                is_active=True,
            ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

            remaining = max(crew - used_across_all - on_leave, 0)
            total += remaining

        return Response({'date': date_str, 'total_capacity': total})
    @action(detail=True, methods=['get'])
    def available_activities(self, request, pk=None):
        """
        Get all activities with rates (mukkadam-specific, cluster, or global)
        GET /api/mukkadams/{id}/available_activities/?cluster_id={cluster_id}
        """
        mukkadam = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = ActivityCatalog.objects.all().order_by('name')
        result = []
        
        for activity in activities:
            # Try mukkadam-specific rate first
            mukkadam_rate = MukkadamActivityRate.objects.filter(
                mukkadam=mukkadam,
                activity=activity,
                is_active=True
            ).first()
            
            if mukkadam_rate:
                rate = float(mukkadam_rate.rate_per_acre)
                productivity = float(mukkadam_rate.productivity_per_worker)
                source = 'mukkadam'
            else:
                # Try cluster rate
                cluster_rate = ClusterActivityRate.objects.filter(
                    cluster=cluster,
                    activity=activity
                ).first()
                
                if cluster_rate:
                    rate = float(cluster_rate.rate_per_acre)
                    source = 'cluster'
                else:
                    rate = float(activity.default_rate_per_acre)
                    source = 'global'
                
                productivity = 0.150  # Default
            
            result.append({
                'activity_id': activity.id,
                'activity_name': activity.name,
                'rate_per_acre': rate,
                'productivity_per_worker': productivity,
                'rate_source': source,
                'is_strict': activity.is_strict
            })
        
        return Response(result)


    @action(detail=False, methods=['patch'])
    def add_day_crew(self, request):
        """
        Add extra workers to a mukkadam's base crew for a specific date.
        PATCH /api/mukkadams/add_day_crew/
        Body: {
            "mukkadam_id": 123,
            "date": "2026-02-18",
            "extra_crew": 5,
            "cluster_id": 1
        }
        """
        mukkadam_id = request.data.get('mukkadam_id')
        date_str = request.data.get('date')
        extra_crew = request.data.get('extra_crew', 0)

        if not mukkadam_id or not date_str:
            return Response(
                {'error': 'mukkadam_id and date are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
            
            # Use update_or_create to store the manual adjustment
            # Assuming your MukkadamAvailability model has an 'extra_workers' field
            availability, created = MukkadamAvailability.objects.update_or_create(
                mukkadam=mukkadam,
                date=date_str,
                defaults={
                    'extra_workers': int(extra_crew),
                    'is_manually_set': True
                }
            )

            # Recalculate total effective crew for that day
            # This logic should be shared with your get_effective_crew_size util
            effective_size = get_effective_crew_size(mukkadam, date_str)
            availability.available_crew_size = effective_size
            availability.save()

            return Response({
                'success': True,
                'message': f'Added {extra_crew} extra workers for {mukkadam.mukkadam_name}',
                'new_total_capacity': effective_size
            })

        except Mukkadam.DoesNotExist:
            return Response({'error': 'Mukkadam not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime

class PlanningViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def by_activity_date(self, request):
        """
        For each activity in a cluster, check if remaining area on its
        scheduled_date can be done by all mukkadams of that cluster on that date.

        GET /tender/api/planning/by_activity_date/?cluster_id=1
        """
        cluster_id = request.query_params.get('cluster_id')
        if not cluster_id:
            return Response({'error': 'cluster_id is required'}, status=400)

        from .models import JobActivity, Mukkadam, MukkadamActivityRate

        # activities with a scheduled date and some remaining area
        activities = JobActivity.objects.filter(
            job__clusters__id=cluster_id,
            plot__clusters__id=cluster_id,  # ✅ only activities whose plot belongs to this cluster
            remaining_area__gt=0,
            scheduled_date__isnull=False,
        ).select_related("job__farmer", "activity", "plot").distinct()

        mukkadams = Mukkadam.objects.filter(clusters__id=cluster_id)

        results = []

        for ja in activities:
            remaining = float(ja.remaining_area or 0)
            if remaining <= 0:
                continue

            day = ja.scheduled_date
            if day is None:
                continue  # or handle missing date

            date_str = day.isoformat()

            # 3) capacity on that date only
            total_capacity_area = 0.0

            for m in mukkadams:
                # workers remaining for that mukkadam on that day
                info = get_mukkadam_remaining_workers(m.mukkadam_id, date_str)
                remaining_workers = info['remaining_workers']

                # activity-specific productivity for that mukkadam
                try:
                    rate = MukkadamActivityRate.objects.get(
                        mukkadam=m,
                        activity_id=ja.activity_id,
                        is_active=True,
                    )
                    prod = float(rate.productivity_per_worker)
                except MukkadamActivityRate.DoesNotExist:
                    prod = 0.0

                total_capacity_area += remaining_workers * prod

            deficit = max(remaining - total_capacity_area, 0.0)
            overloaded = deficit > 0

            results.append({
                'job_id': ja.job.job_id,
                'plot_name': ja.plot.name if ja.plot else '',
                'farmer_id': ja.job.farmer.farmer_id,
                'farmer_name': ja.job.farmer.farmer_name, 
                  'crop_name': ja.job.crop_name,
                  'variety_name': ja.job.variety,   
                'activity_id': ja.activity_id,
                'activity_name': ja.activity.name,
                'scheduled_date': date_str,
                'remaining_area': round(remaining, 2),
                'available_capacity_area': round(total_capacity_area, 2),
                'deficit': round(deficit, 2),
                'overloaded': overloaded,
            })


        return Response(results)

@api_view(['POST'])
def insert_activity_between(request):
    """
    Insert a new activity between two existing activities in the lifecycle
    
    POST /api/activities/insert_between/
    Body: {
        "name": "New Activity Name",
        "activity_type": "pruning",
        "default_rate_per_acre": 1000,
        "gap_days_from_previous": 5,
        "insert_after_activity_id": 7,  // Insert after this activity (e.g., after Pruning)
        "mukkadam_rate_per_acre": 800,
        "mukkadam_productivity_per_worker": 0.150,
        "is_strict": false,
        "estimated_workers_per_acre": 10
    }
    """
    serializer = InsertActivitySerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Check if activity already exists
    if ActivityCatalog.objects.filter(name__iexact=data['name']).exists():
        return Response(
            {'error': f'Activity "{data["name"]}" already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get the activity we're inserting after
    try:
        previous_activity = ActivityCatalog.objects.get(id=data['insert_after_activity_id'])
    except ActivityCatalog.DoesNotExist:
        return Response(
            {'error': 'Previous activity not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get the previous activity's schedule rule to find its phase_order
    try:
        previous_rule = ActivityScheduleRule.objects.get(activity=previous_activity)
        new_phase_order = previous_rule.phase_order + 1
    except ActivityScheduleRule.DoesNotExist:
        return Response(
            {'error': 'Previous activity has no schedule rule'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    with transaction.atomic():
        # Create the new activity
        new_activity = ActivityCatalog.objects.create(
            name=data['name'],
            activity_type=data.get('activity_type', ''),
            default_rate_per_acre=data['default_rate_per_acre'],
            is_strict=data['is_strict'],
            estimated_workers_per_acre=data['estimated_workers_per_acre'],
            default_gap_days=data['gap_days_from_previous'],
            source='custom'
        )
        
        # Shift all activities after this one by +1 in phase_order
        ActivityScheduleRule.objects.filter(
            phase_order__gte=new_phase_order
        ).update(phase_order=models.F('phase_order') + 1)
        
        # Create schedule rule for new activity
        ActivityScheduleRule.objects.create(
            activity=new_activity,
            gap_days=data['gap_days_from_previous'],
            phase_order=new_phase_order
        )
        
        return Response({
            'success': True,
            'message': f'Activity "{data["name"]}" inserted after "{previous_activity.name}"',
            'activity': {
                'id': new_activity.id,
                'name': new_activity.name,
                'phase_order': new_phase_order,
                'gap_days': data['gap_days_from_previous'],
                'inserted_after': previous_activity.name
            }
        }, status=status.HTTP_201_CREATED)


# views.py
class ExtraWorkerViewSet(viewsets.ModelViewSet):
    queryset = ExtraWorker.objects.all()
    serializer_class = ExtraWorkerSerializer

    def create(self, request, *args, **kwargs):
        mukkadam_id = request.data.get('mukkadam')
        date_str = request.data.get('date')
        workers = int(request.data.get('workers', 0))

        if not mukkadam_id or not date_str:
            return Response(
                {'detail': 'mukkadam and date are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        extra, _ = ExtraWorker.objects.update_or_create(
            mukkadam=mukkadam,
            date=date,
            defaults={'workers': workers},
        )

        serializer = self.get_serializer(extra)
        return Response(serializer.data, status=status.HTTP_200_OK)

# =============================================================================
# HELPER FUNCTIONS (if needed in views)
# =============================================================================

def generate_unique_payment_id():
    """Generate unique payment ID"""
    from django.utils import timezone
    timestamp = int(timezone.now().timestamp() * 1000)
    return timestamp

from decimal import Decimal
from django.db import transaction
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
# views.py
from rest_framework import viewsets, permissions
from .models import Cluster
from .serializers import ClusterSerializer
from datetime import date, timedelta, datetime as dt

from django.db.models import Q

from django.db.models import (
    Count, Min, Max, Q, OuterRef, Subquery, IntegerField
)
from django.db.models import (
    OuterRef, Subquery, Count, IntegerField, Q,
    DecimalField  # ← ADD
)
from django.db.models.functions import Coalesce
from rest_framework import viewsets, filters

from django.db.models import Value
from decimal import Decimal
class ClusterViewSet(viewsets.ModelViewSet):
    serializer_class = ClusterSerializer

    def get_queryset(self):

        activity_sq = JobActivity.objects.filter(
            job__clusters__id=OuterRef('pk')
        ).order_by().values('job__clusters__id').annotate(
            c=models.Count('id')
        ).values('c')

        # ── allocation count ──────────────────────────────────────────────────
        # Allocation has cluster FK directly — use that, much simpler & correct
        allocation_sq = Allocation.objects.filter(
            cluster_id=OuterRef('pk')
        ).order_by().values('cluster_id').annotate(
            c=models.Count('id')
        ).values('c')

        # ── bills sent count per cluster ─────────────────────────────────────────
        bills_sent_sq = FarmerBillWebhookLog.objects.filter(
            cluster_id=OuterRef('pk'),
        ).order_by().values('cluster_id').annotate(
            c=models.Count('id')
        ).values('c')

        # ── farmer count ──────────────────────────────────────────────────────
        # Farmer.clusters is M2M
        farmer_sq = Farmer.objects.filter(
            clusters__id=OuterRef('pk')
        ).order_by().values('clusters__id').annotate(
            c=models.Count('farmer_id')
        ).values('c')

        # ── mukkadam count (active assignments) ──────────────────────────────
        mukkadam_sq = ClusterMukkadamAssignment.objects.filter(
            cluster_id=OuterRef('pk'),
            is_active=True,
        ).order_by().values('cluster_id').annotate(
            c=models.Count('id')
        ).values('c')

        # ── total area (sum of all JobActivity.total_area in cluster) ─────────────
        total_area_sq = JobActivity.objects.filter(
            plot__clusters__id=OuterRef('pk'),
            total_area__gt=0,
        ).order_by().values('plot__clusters__id').annotate(
            s=models.Sum('total_area')
        ).values('s')

        # ── allocated area (sum of JobActivity.allocated_area in cluster) ─────────
        allocated_area_sq = JobActivity.objects.filter(
            plot__clusters__id=OuterRef('pk'),
            total_area__gt=0,
        ).order_by().values('plot__clusters__id').annotate(
            s=models.Sum('allocated_area')
        ).values('s')

        # ── date range ────────────────────────────────────────────────────────
        date_start_sq = JobActivity.objects.filter(
            job__clusters__id=OuterRef('pk'),
            scheduled_date__isnull=False,
        ).order_by('scheduled_date').values('scheduled_date')[:1]

        date_end_sq = JobActivity.objects.filter(
            job__clusters__id=OuterRef('pk'),
            scheduled_date__isnull=False,
        ).order_by('-scheduled_date').values('scheduled_date')[:1]

        qs = Cluster.objects.annotate(
            farmer_count     = Coalesce(Subquery(farmer_sq,        output_field=IntegerField()), 0),
            mukkadam_count   = Coalesce(Subquery(mukkadam_sq,      output_field=IntegerField()), 0),
            activity_count   = Coalesce(Subquery(activity_sq,      output_field=IntegerField()), 0),
            allocation_count = Coalesce(Subquery(allocation_sq,    output_field=IntegerField()), 0),
            activity_start   = Subquery(date_start_sq),
            activity_end     = Subquery(date_end_sq),

            bills_sent_count = Coalesce(
                Subquery(bills_sent_sq, output_field=IntegerField()), 0
            ),
            # ── ADD THESE TWO ──
            total_area     = Coalesce(
                Subquery(total_area_sq,     output_field=DecimalField(max_digits=10, decimal_places=2)),
                Value(Decimal('0'),         output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
            allocated_area = Coalesce(
                Subquery(allocated_area_sq, output_field=DecimalField(max_digits=10, decimal_places=2)),
                Value(Decimal('0'),         output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
        ).order_by('name')

        # ── optional ?q= filter ───────────────────────────────────────────────
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(farmers__farmer_name__icontains=q) |
                Q(mukkadams__mukkadam_name__icontains=q)
            ).distinct()

        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'available_activities']:
            return [AllowAny()]
        # create / update / custom actions → auth
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user, last_modified_by=user)
        ops("cluster_created",                          # ADD
        cluster_id=str(serializer.instance.id),
        cluster_name=serializer.instance.name,
        created_by=str(user.id if user else "anon"))

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(last_modified_by=user)
        ops("cluster_updated",                          # ADD
        cluster_id=str(serializer.instance.id),
        cluster_name=serializer.instance.name,
        updated_by=str(user.id if user else "anon"))

    @action(detail=True, methods=['post'], url_path='remove_farmer')
    def remove_farmer(self, request, pk=None):
        ctx(flow="cluster_remove_farmer",
        cluster_id=pk,
        user=str(request.user.id))
        """
        POST /api/clusters/{id}/remove_farmer/
        Body: { "farmer_id": "F001" }
        Admin only. Removes farmer + their plots + their jobs from this cluster.
        """
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=401)

        try:
            if request.user.profile.role != 'admin':
                return Response({'error': 'Admin access required'}, status=403)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Admin access required'}, status=403)

        cluster = self.get_object()
        farmer_id = request.data.get('farmer_id')
        if not farmer_id:
            return Response({'error': 'farmer_id required'}, status=400)

        try:
            farmer = Farmer.objects.get(farmer_id=farmer_id)
        except Farmer.DoesNotExist:
            ops("cluster_remove_farmer_not_found",          # ADD
        cluster_id=pk, farmer_id=farmer_id)
            return Response({'error': 'Farmer not found'}, status=404)

        now = timezone.now()

        # 1. Remove farmer from cluster + record who did it
        cluster.farmers.remove(farmer)
        Farmer.objects.filter(farmer_id=farmer_id).update(
            last_cluster_modified_by=request.user,
        )

        # 2. Remove farmer's plots from this cluster + record who did it
        farmer_plots = Plot.objects.filter(farmer=farmer, clusters=cluster)
        plots_count = farmer_plots.count()
        for plot in farmer_plots:
            plot.clusters.remove(cluster)
        Plot.objects.filter(farmer=farmer).update(
            last_cluster_modified_by=request.user,
            last_cluster_modified_at=now,
        )

        # 3. Remove farmer's jobs from this cluster + record who did it
        farmer_jobs = Job.objects.filter(farmer=farmer, clusters=cluster)
        jobs_count = farmer_jobs.count()
        for job in farmer_jobs:
            job.clusters.remove(cluster)
            ops("cluster_farmer_removed",                       # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    farmer_id=farmer_id,
    farmer_name=farmer.farmer_name,
    plots_removed=plots_count,
    jobs_removed=jobs_count,
    by=request.user.username)

        # 4. Log the action
        logger.info(
            f"[CLUSTER REMOVE] user='{request.user.username}' (id={request.user.id}) "
            f"removed farmer='{farmer.farmer_name}' ({farmer_id}) "
            f"from cluster='{cluster.name}' (id={cluster.id}) "
            f"| plots_removed={plots_count} jobs_removed={jobs_count} "
            f"| at={now.isoformat()}"
        )

        return Response({
            'success': True,
            'message': f'{farmer.farmer_name} removed from {cluster.name}',
            'removed_by': request.user.username,
            'removed_at': now.isoformat(),
            'plots_removed': plots_count,
            'jobs_removed': jobs_count,
        })
    
    
    @action(detail=True, methods=['post'], url_path='remove_mukkadam')
    def remove_mukkadam(self, request, pk=None):
        ctx(flow="cluster_remove_mukkadam",
        cluster_id=pk,
        user=str(request.user.id))
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=401)

        try:
            if request.user.profile.role != 'admin':
                return Response({'error': 'Admin access required'}, status=403)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Admin access required'}, status=403)

        cluster = self.get_object()
        mukkadam_id = request.data.get('mukkadam_id')
        if not mukkadam_id:
            return Response({'error': 'mukkadam_id required'}, status=400)

        now = timezone.now()

        updated = ClusterMukkadamAssignment.objects.filter(
            cluster=cluster,
            mukkadam__mukkadam_id=mukkadam_id,
            is_active=True,
        ).update(
            is_active=False,
            last_modified_by=request.user,  # ← keep this
            # last_modified_at=now,         # ← remove this, updated_at auto_now handles it
        )

        if not updated:
            ops("cluster_remove_mukkadam_not_found",        # ADD
        cluster_id=pk, mukkadam_id=mukkadam_id)
            return Response({'error': 'Active assignment not found'}, status=404)

        # Log the action
        logger.info(
            f"[CLUSTER REMOVE] user='{request.user.username}' (id={request.user.id}) "
            f"removed mukkadam='{mukkadam_id}' "
            f"from cluster='{cluster.name}' (id={cluster.id}) "
            f"| at={now.isoformat()}"
        )

        ops("cluster_mukkadam_removed",                     # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    mukkadam_id=mukkadam_id,
    by=request.user.username)

        return Response({
            'success': True,
            'message': f'Mukkadam removed from {cluster.name}',
            'removed_by': request.user.username,
            'removed_at': now.isoformat(),
        })
    
    @action(detail=True, methods=['get'], url_path='members')
    def members(self, request, pk=None):
        """
        GET /api/clusters/{id}/members/
        Returns farmers + mukkadams in this cluster.
        """
        cluster = self.get_object()

        farmers = cluster.farmers.values('farmer_id', 'farmer_name', 'phone_number', 'location')
        
        mukkadams = ClusterMukkadamAssignment.objects.filter(
            cluster=cluster, is_active=True
        ).select_related('mukkadam').values(
            mukkadam_id=models.F('mukkadam__mukkadam_id'),
            mukkadam_name=models.F('mukkadam__mukkadam_name'),
            mukkadam_type=models.F('mukkadam_type'),
        )

        return Response({
            'farmers': list(farmers),
            'mukkadams': list(mukkadams),
        })
        

    def list(self, request, *args, **kwargs):
        ctx(flow="cluster_list",
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        from datetime import date
        from django.db.models import Sum
        from decimal import Decimal

        qs = self.get_queryset()
        result = []

        for c in qs:
            serialized = self.get_serializer(c).data

            # ── Financial summary ─────────────────────────────────────────
            # Get all jobs in this cluster
            job_ids = list(
                Job.objects.filter(clusters=c).values_list('job_id', flat=True)
            )

            # ── Financial summary — mirrors cluster_payment_dashboard logic ──────────
            from decimal import Decimal

            cluster_jobs = Job.objects.filter(clusters=c).prefetch_related('booking')

            total_billed    = Decimal('0')
            total_collected = Decimal('0')

            for job in cluster_jobs:
                # Billed = sum of completed allocation area × rate for this job
                job_allocs = Allocation.objects.filter(
                    cluster=c,
                    job_activity__job=job,
                    work_status='completed',
                ).select_related('job_activity')

                for a in job_allocs:
                    total_billed += (
                        Decimal(str(a.allocated_area or 0)) *
                        Decimal(str(a.job_activity.rate_per_acre or 0))
                    ).quantize(Decimal('0.01'))

                # Collected = confirmed FarmerPayments for this job's booking
                try:
                    booking = job.booking
                    fps = FarmerPayment.objects.filter(
                        booking=booking,
                        paid_status=True,
                    )
                    total_collected += sum(Decimal(str(p.amount)) for p in fps)
                except Exception:
                    err("cluster_list_payment_fail",                # ADD
        cluster_id=str(c.id),
        job_id=str(job.job_id))
                    pass

            total_due = total_billed - total_collected
            

            serialized['total_billed']    = float(total_billed)
            serialized['total_collected'] = float(total_collected)
            serialized['farmer_due']      = float(max(Decimal('0'), total_due))
            # ── Bill counts — derived from farmer billing data ────────────────────

            # Get all farmers in this cluster
            cluster_farmers = Farmer.objects.filter(clusters=c)
            cluster_farmer_ids = [str(f.farmer_id) for f in cluster_farmers]

            # SENT = distinct farmer+activity combos with a webhook log for this cluster
            sent_combos = set(
                FarmerBillWebhookLog.objects.filter(
                    cluster=c,
                ).values_list('farmer_id', 'activity_name').distinct()
            )
            bills_sent = len(sent_combos)

            # AWAITING = sent bills where latest log still has balance_due > 0
            response_pending = 0
            for farmer_id, act_name in sent_combos:
                latest_log = FarmerBillWebhookLog.objects.filter(
                    cluster=c,
                    farmer_id=farmer_id,
                    activity_name=act_name,
                ).order_by('-sent_at').first()
                if latest_log and latest_log.balance_due and float(latest_log.balance_due) > 0.01:
                    response_pending += 1

            # PENDING = farmer+activity where ALL allocations are work_status='completed'
            # but no bill has been sent yet
            #
            # Step 1: find all farmer+activity combos in this cluster
            # that have at least one allocation with work_status='completed'
            from collections import defaultdict

            cluster_allocs = Allocation.objects.filter(
                cluster=c,
            ).select_related(
                'job_activity__activity',
                'job_activity__job__farmer',
            ).values(
                'job_activity__job__farmer__farmer_id',
                'job_activity__activity__name',
                'work_status',
            )

            # Group by farmer_id + activity_name → collect all statuses
            grouped = defaultdict(list)
            for row in cluster_allocs:
                key = (
                    str(row['job_activity__job__farmer__farmer_id']),
                    row['job_activity__activity__name'],
                )
                grouped[key].append(row['work_status'])

            # PENDING = all statuses are 'completed' AND combo not in sent_combos
            bills_pending = sum(
                1
                for (farmer_id, act_name), statuses in grouped.items()
                if len(statuses) > 0
                and all(s == 'completed' for s in statuses)
                and (farmer_id, act_name) not in sent_combos
            )

            # response_pending = bills sent but balance still due
            response_pending = FarmerBillWebhookLog.objects.filter(
                cluster=c,
                balance_due__gt=0,
            ).values('farmer_id', 'activity_name').distinct().count()
            ops("cluster_financials_computed",                  # ADD
    cluster_id=str(c.id),
    cluster_name=c.name,
    total_billed=str(total_billed),
    total_collected=str(total_collected),
    total_due=str(total_due),
    bills_sent=bills_sent,
    bills_pending=bills_pending,
    response_pending=response_pending)

            
            serialized['mukkadam_due']     = '0'
            
            serialized['bills_sent']       = bills_sent
            serialized['bills_pending']    = bills_pending
            serialized['response_pending'] = response_pending
            serialized['farmer_count']     = c.farmer_count
            serialized['mukkadam_count']   = c.mukkadam_count

            result.append(serialized)

        return Response(result)
    
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        ctx(flow="cluster_add_activity",
        cluster_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        """
        Add an activity to this cluster with custom rates
        Can either use existing activity_id or create new one with activity_name
        
        POST /api/clusters/{id}/add_activity/
        Body: {
            "activity_id": 5,  // OR "activity_name": "New Activity"
            "farmer_rate_per_acre": 1000,
            "gap_days": 7,
            "mukkadam_rate_per_acre": 800,
            "mukkadam_productivity_per_worker": 0.150
        }
        """
        cluster = self.get_object()
        serializer = AddClusterActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get or create activity
        if 'activity_id' in data:
            try:
                activity = ActivityCatalog.objects.get(id=data['activity_id'])
            except ActivityCatalog.DoesNotExist:
                ops("cluster_add_activity_not_found",           # ADD
        cluster_id=pk,
        activity_id=str(data.get('activity_id')))
                return Response(
                    {'error': 'Activity not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif 'activity_name' in data:
            # Create new activity if doesn't exist
            activity, created = ActivityCatalog.objects.get_or_create(
                name=data['activity_name'],
                defaults={
                    'source': 'custom',
                    'default_rate_per_acre': data['farmer_rate_per_acre'],
                    'default_gap_days': data['gap_days'],
                    'estimated_workers_per_acre': 10,
                }
            )
            
            if created:
                # Create global schedule rule
                ActivityScheduleRule.objects.create(
                    activity=activity,
                    gap_days=data['gap_days'],
                    phase_order=ActivityScheduleRule.objects.count() + 1
                )
                ops("cluster_activity_catalog_created",         # ADD
        cluster_id=pk,
        activity_name=data['activity_name'],
        gap_days=data['gap_days'])
        else:
            return Response(
                {'error': 'Either activity_id or activity_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add/Update farmer rate for cluster
        farmer_rate, created = ClusterActivityRate.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={'rate_per_acre': data['farmer_rate_per_acre']}
        )
        
        # Add/Update schedule rule for cluster
        schedule_rule, _ = ClusterActivityScheduleRule.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={'gap_days': data['gap_days']}
        )
        
        # Add/Update mukkadam default rate for cluster
        mukkadam_rate, _ = ClusterMukkadamActivityRate.objects.update_or_create(
            cluster=cluster,
            activity=activity,
            defaults={
                'rate_per_acre': data['mukkadam_rate_per_acre'],
                'productivity_per_worker': data['mukkadam_productivity_per_worker']
            }
        )

        ops("cluster_activity_added",                       # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    activity_id=str(activity.id),
    activity_name=activity.name,
    farmer_rate=str(data['farmer_rate_per_acre']),
    mukkadam_rate=str(data['mukkadam_rate_per_acre']),
    gap_days=data['gap_days'],
    new_activity_created=created)
        
        return Response({
            'success': True,
            'message': f'Activity "{activity.name}" {"created and " if created else ""}added to cluster "{cluster.name}"',
            'activity': {
                'id': activity.id,
                'name': activity.name,
                'farmer_rate': float(farmer_rate.rate_per_acre),
                'gap_days': schedule_rule.gap_days,
                'mukkadam_rate': float(mukkadam_rate.rate_per_acre),
                'mukkadam_productivity': float(mukkadam_rate.productivity_per_worker),
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def available_activities(self, request, pk=None):
        """
        Get all activities that can be added to this cluster
        
        GET /api/clusters/{id}/available_activities/
        """
        cluster = self.get_object()
        
        # Get activities already in cluster
        existing_activity_ids = ClusterActivityRate.objects.filter(
            cluster=cluster
        ).values_list('activity_id', flat=True)
        
        # Get all activities not yet in cluster
        available = ActivityCatalog.objects.exclude(
            id__in=existing_activity_ids
        ).values('id', 'name', 'activity_type', 'default_rate_per_acre', 'default_gap_days')
        
        return Response({
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'available_activities': list(available)
        })
    
    @action(detail=True, methods=['post'], url_path='set_weekly_payment_day')
    def set_weekly_payment_day(self, request, pk=None):
        ctx(flow="cluster_set_payment_day",
        cluster_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        """
        Set the weekly payment day for a specific mukkadam in this cluster.
        
        POST /api/clusters/{id}/set_weekly_payment_day/
        Body: {
            "mukkadam_id": 123,
            "weekly_payment_day": 0   // 0=Monday ... 6=Sunday
        }
        """
        cluster = self.get_object()
        mukkadam_id = request.data.get('mukkadam_id')
        weekly_payment_day = request.data.get('weekly_payment_day')

        if mukkadam_id is None or weekly_payment_day is None:
            return Response(
                {'error': 'mukkadam_id and weekly_payment_day are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if weekly_payment_day not in range(7):
            return Response(
                {'error': 'weekly_payment_day must be between 0 (Monday) and 6 (Sunday)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            assignment = ClusterMukkadamAssignment.objects.get(
                cluster=cluster,
                mukkadam_id=mukkadam_id,
                is_active=True
            )
        except ClusterMukkadamAssignment.DoesNotExist:
            ops("cluster_payment_day_not_found",            # ADD
        cluster_id=pk,
        mukkadam_id=str(mukkadam_id))
            return Response(
                {'error': 'Mukkadam is not assigned to this cluster'},
                status=status.HTTP_404_NOT_FOUND
            )

        assignment.weekly_payment_day = weekly_payment_day
        assignment.save()
        ops("cluster_payment_day_set",                      # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    mukkadam_id=str(mukkadam_id),
    mukkadam_name=assignment.mukkadam.mukkadam_name,
    day=weekly_payment_day,
    day_name=day_name)

        day_name = dict(ClusterMukkadamAssignment.WEEKDAY_CHOICES)[weekly_payment_day]

        return Response({
            'success': True,
            'message': f'Weekly payment day set to {day_name} for {assignment.mukkadam.mukkadam_name} in {cluster.name}',
            'mukkadam_id': mukkadam_id,
            'cluster_id': cluster.id,
            'weekly_payment_day': weekly_payment_day,
            'weekly_payment_day_name': day_name,
            'weekly_payment_amount': float(assignment.get_weekly_payment_amount()),
        })

    @action(detail=True, methods=['patch'], url_path='update_mukkadam')
    def update_mukkadam(self, request, pk=None):
        ctx(flow="cluster_update_mukkadam",
        cluster_id=pk,
        mukkadam_id=str(mukkadam_id) if mukkadam_id else "unknown",
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        cluster = self.get_object()

        mukkadam_id        = request.data.get('mukkadam_id')
        transport_price    = request.data.get('transport_price')
        weekly_payment_day = request.data.get('weekly_payment_day')
        advance_amount     = request.data.get('advance_amount')
        weekly_amount      = request.data.get('weekly_amount')  # optional, only use if you add field

        # Updown fields
        mukkadam_type         = request.data.get('mukkadam_type')      # may be None -> keep old
        updown_mode           = request.data.get('updown_mode')
        updown_from_date      = request.data.get('updown_from_date')
        updown_to_date        = request.data.get('updown_to_date')
        updown_specific_dates = request.data.get('updown_specific_dates')

        if not mukkadam_id:
            return Response({'error': 'mukkadam_id required'}, status=400)

        try:
            assignment = ClusterMukkadamAssignment.objects.filter(
                cluster=cluster,
                mukkadam__mukkadam_id=mukkadam_id,
                is_active=True,
            ).order_by('id').last()  # gets the most recently created one

            if not assignment:
                ops("cluster_update_mukkadam_not_found",        # ADD
        cluster_id=pk, mukkadam_id=str(mukkadam_id))
                return Response({'error': 'Assignment not found'}, status=404)
        except ClusterMukkadamAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=404)

        mukkadam = assignment.mukkadam

        # Fallback to existing values where not provided
        if mukkadam_type is None:
            mukkadam_type = assignment.mukkadam_type
        if updown_mode is None:
            updown_mode = assignment.updown_mode
        if updown_from_date is None:
            updown_from_date = assignment.updown_from_date
        if updown_to_date is None:
            updown_to_date = assignment.updown_to_date
        if updown_specific_dates is None:
            updown_specific_dates = assignment.updown_specific_dates

        # Validate weekly_payment_day
        if weekly_payment_day is not None:
            try:
                weekly_payment_day = int(weekly_payment_day)
            except (TypeError, ValueError):
                return Response({'error': 'weekly_payment_day must be 0–6'}, status=400)
            if weekly_payment_day not in range(7):
                return Response({'error': 'weekly_payment_day must be 0–6'}, status=400)

        # Validate updown fields (same as add)
        if mukkadam_type == 'updown':
            if not updown_mode:
                return Response({'error': 'updown_mode required for updown type'}, status=400)
            if updown_mode == 'range':
                if not updown_from_date or not updown_to_date:
                    return Response(
                        {'error': 'updown_from_date and updown_to_date required for range mode'},
                        status=400,
                    )
            elif updown_mode == 'specific':
                if not updown_specific_dates:
                    return Response(
                        {'error': 'updown_specific_dates required for specific mode'},
                        status=400,
                    )

        # ---------- ALLOCATION-SAFETY CHECK ----------
        def expand_availability(assign_type, mode, d_from, d_to, specific_list):
            days = set()
            today = date.today()
            horizon = today + timedelta(days=90)

            if assign_type == 'permanent':
                cur = today
                while cur <= horizon:
                    days.add(cur)
                    cur += timedelta(days=1)

            elif assign_type == 'updown':
                if mode == 'range' and d_from and d_to:
                    # ensure dates
                    if isinstance(d_from, str):
                        d_from_local = dt.strptime(d_from, "%Y-%m-%d").date()
                    else:
                        d_from_local = d_from
                    if isinstance(d_to, str):
                        d_to_local = dt.strptime(d_to, "%Y-%m-%d").date()
                    else:
                        d_to_local = d_to

                    cur = max(d_from_local, today)
                    while cur <= d_to_local and cur <= horizon:
                        days.add(cur)
                        cur += timedelta(days=1)

                elif mode == 'specific' and specific_list:
                    for s in specific_list:
                        d_local = None
                        if isinstance(s, str):
                            try:
                                d_local = dt.strptime(s, "%Y-%m-%d").date()
                            except ValueError:
                                continue
                        else:
                            d_local = s
                        if d_local and today <= d_local <= horizon:
                            days.add(d_local)

            return days

        before_days = expand_availability(
            assignment.mukkadam_type,
            assignment.updown_mode,
            assignment.updown_from_date,
            assignment.updown_to_date,
            assignment.updown_specific_dates,
        )

        after_days = expand_availability(
            mukkadam_type,
            updown_mode,
            updown_from_date,
            updown_to_date,
            updown_specific_dates,
        )

        removed_days = before_days - after_days

        if removed_days:
            conflict = Allocation.objects.filter(
                mukkadam=mukkadam,
                cluster=cluster,
                allocated_date__in=removed_days,
                status__in=['scheduled', 'in_progress'],
            ).order_by('allocated_date').first()

            if conflict:
                ops("cluster_update_mukkadam_conflict",         # ADD
        cluster_id=pk,
        mukkadam_id=str(mukkadam_id),
        conflict_date=str(conflict.allocated_date),
        allocation_id=conflict.id)
                return Response(
                    {
                        'error': 'Cannot change availability',
                        'detail': f"There is an allocation on {conflict.allocated_date} for this mukkadam in this cluster. Keep that date included or move/cancel the allocation first.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # ---------- END CHECK ----------

        # Apply simple fields
        if transport_price is not None:
            assignment.transport_price = Decimal(str(transport_price))

        if weekly_payment_day is not None:
            assignment.weekly_payment_day = weekly_payment_day

        # Advance override
        if advance_amount is not None:
            assignment.advance_amount = Decimal(str(advance_amount))
            assignment.advance_is_manual = True

        weekly_amount = request.data.get('weekly_amount')

        # later, when applying fields:
        if weekly_amount is not None:
            assignment.weekly_amount = Decimal(str(weekly_amount)) 

        # Updown config
        assignment.mukkadam_type = mukkadam_type
        if mukkadam_type == 'updown':
            assignment.updown_mode = updown_mode
            if updown_mode == 'range':
                assignment.updown_from_date = updown_from_date
                assignment.updown_to_date = updown_to_date
                assignment.updown_specific_dates = []
            elif updown_mode == 'specific':
                assignment.updown_from_date = None
                assignment.updown_to_date = None
                assignment.updown_specific_dates = updown_specific_dates
        else:
            assignment.updown_mode = None
            assignment.updown_from_date = None
            assignment.updown_to_date = None
            assignment.updown_specific_dates = []

        assignment.save()
        ops("cluster_mukkadam_updated",                     # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    mukkadam_id=str(mukkadam_id),
    mukkadam_name=assignment.mukkadam.mukkadam_name,
    mukkadam_type=assignment.mukkadam_type,
    transport_price=str(transport_price or ""),
    weekly_payment_day=str(weekly_payment_day or ""),
    advance_amount=str(advance_amount or ""))

        if request.user and request.user.is_authenticated:
            assignment.last_modified_by = request.user
            assignment.save(update_fields=['last_modified_by'])

        return Response(
            {
                'success': True,
                'message': 'Mukkadam assignment updated',
                'mukkadam_name': assignment.mukkadam.mukkadam_name,
                'cluster_name': cluster.name,
                'mukkadam_type': assignment.mukkadam_type,
            },
            status=status.HTTP_200_OK,
        )
    
    
    @action(detail=True, methods=['patch'], url_path='update_locations')
    def update_locations(self, request, pk=None):
        ctx(flow="cluster_update_locations",
        cluster_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        """
        PATCH /api/clusters/{id}/update_locations/
        Body: {
            "name": "Satana",
            "district_codes": ["123"],
            "taluka_codes": ["456"],
            "village_codes": ["789"],
            "districts": ["Nashik"],
            "talukas": ["Satana"],
            "villages": ["Satana Village"]
        }
        """
        cluster = self.get_object()

        if 'name' in request.data:
            cluster.name = request.data['name']
        if 'district_codes' in request.data:
            cluster.district_codes = request.data['district_codes']
        if 'taluka_codes' in request.data:
            cluster.taluka_codes = request.data['taluka_codes']
        if 'village_codes' in request.data:
            cluster.village_codes = request.data['village_codes']
        if 'districts' in request.data:
            cluster.districts = request.data['districts']
        if 'talukas' in request.data:
            cluster.talukas = request.data['talukas']
        if 'villages' in request.data:
            cluster.villages = request.data['villages']

        if request.user and request.user.is_authenticated:
            cluster.last_modified_by = request.user

        cluster.save()
        ops("cluster_locations_updated",                    # ADD
    cluster_id=pk,
    cluster_name=cluster.name,
    fields_updated=str([
        f for f in ['name','district_codes','taluka_codes',
                    'village_codes','districts','talukas','villages']
        if f in request.data
    ]),
    by=str(request.user.id if request.user.is_authenticated else "anon"))
        return Response(ClusterSerializer(cluster).data)

from decimal import Decimal, ROUND_HALF_UP

from .notification import notify_mukkadam
from rest_framework.permissions import IsAuthenticated


class AllocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = Allocation.objects.all().select_related(
            'job_activity__job__farmer',
            'job_activity__activity',
            'mukkadam',
        )

        cluster_id = self.request.query_params.get('cluster_id')
        if cluster_id:
            qs = qs.filter(cluster_id=cluster_id)

        return qs
    serializer_class = AllocationSerializer


    # @action(detail=False, methods=['post'])
    # def create_allocation(self, request):
    #     """
    #     Create allocation with:
    #     - Productivity + availability validation (existing)
    #     - Remaining-area guard (existing)
    #     - Rule 1: Block if unallocated predecessor exists
    #     - Rule 4: Block if allocated_date violates sequence ordering
    #     - Rule 5: Block if activity is in-progress or completed+paid
    #     - Rule 2: After first allocation, cascade downstream unallocated
    #                 activities using reference + original_gap
    #     """
    #     from datetime import date as date_type, timedelta
    #     from django.db.models import Sum

    #     job_activity_id   = request.data.get('job_activity_id')
    #     mukkadam_id       = request.data.get('mukkadam_id')
    #     allocated_date    = request.data.get('allocated_date')
    #     cluster_id        = request.data.get('cluster_id')

    #     allocated_area    = Decimal(str(request.data.get('allocated_area', '0')))
    #     allocated_workers = int(request.data.get('allocated_workers', 0))
    #     farmer_rate       = Decimal(str(request.data.get('farmer_rate', '0')))
    #     mukkadam_rate     = Decimal(str(request.data.get('mukkadam_rate', '0')))
    #     force             = bool(request.data.get('force', False))
    #     skip_strict_check = bool(request.data.get('skip_strict_check', False))
    #     allows_second_job = bool(request.data.get('allows_second_job', False))

    #     if not cluster_id:
    #         return Response({'error': 'cluster_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    #     if not allocated_date:
    #         return Response({'error': 'allocated_date is required'}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         allocated_date_obj = date_type.fromisoformat(str(allocated_date))
    #     except ValueError:
    #         return Response({'error': 'Invalid allocated_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

    #     # ── 1) Business validation (productivity, availability etc.) ──────────────
    #     can_allocate, message, warnings = check_can_allocate(
    #         job_activity_id,
    #         mukkadam_id,
    #         allocated_date,
    #         float(allocated_area),
    #         allocated_workers,
    #         skip_strict_check=skip_strict_check,
    #         cluster_id=cluster_id,
    #     )

    #     if not can_allocate:
    #         productivity_warning = warnings.get('productivity_warning', {})
    #         if not (force and productivity_warning.get('severity') == 'error'):
    #             return Response(
    #                 {'error': message, 'warnings': warnings},
    #                 status=status.HTTP_400_BAD_REQUEST,
    #             )

    #     try:
    #         with transaction.atomic():

    #             # ── 2) Load objects with row lock on JobActivity ──────────────────
    #             try:
    #                 job_activity = JobActivity.objects.select_related(
    #                     'job__farmer',
    #                     'job__booking',
    #                     'activity',
    #                     'plot',
    #                 ).select_for_update(of=('self',)).get(id=job_activity_id)
    #                 mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    #                 cluster  = Cluster.objects.get(id=cluster_id)
    #             except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist, Cluster.DoesNotExist) as e:
    #                 return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    #             # ── 3) Rule 5: Block if in-progress ──────────────────────────────
    #             if job_activity.allocation_status == 'in_progress':
    #                 return Response(
    #                     {'error': 'Activity is in-progress and cannot be allocated.'},
    #                     status=status.HTTP_400_BAD_REQUEST,
    #                 )

    #             # ── 4) Rule 5: Block if completed + paid ─────────────────────────
    #             has_paid_completion = job_activity.allocations.filter(
    #                 work_status='completed',
    #                 payment_status__in=['done', 'settled'],
    #             ).exists()

    #             if job_activity.allocation_status == 'completed' and has_paid_completion:
    #                 return Response(
    #                     {'error': 'Activity is completed and paid — no further allocations allowed.'},
    #                     status=status.HTTP_400_BAD_REQUEST,
    #                 )

    #             # ── 5) Load full job sequence for sequencing rules ────────────────
    #             all_activities = list(
    #                 JobActivity.objects.filter(
    #                     job=job_activity.job,
    #                     plot=job_activity.plot,
    #                     total_area__gt=0,
    #                     is_lost=False,
    #                 ).select_related('activity')
    #             )
    #             all_activities.sort(key=lambda a: (
    #                 get_activity_sequence_order(a),
    #                 a.scheduled_date or date.min,
    #                 a.id,
    #             ))

    #             try:
    #                 current_idx = next(i for i, a in enumerate(all_activities) if a.id == job_activity.id)
    #             except StopIteration:
    #                 return Response({'error': 'Activity not found in job sequence'}, status=status.HTTP_400_BAD_REQUEST)

    #             successors = all_activities[current_idx + 1:]

    #             # ── 6) Remaining-area guard ───────────────────────────────────────
    #             remaining = (job_activity.total_area - job_activity.allocated_area).quantize(
    #                 Decimal('0.0001'), rounding=ROUND_HALF_UP,
    #             )

    #             if remaining <= Decimal('0'):
    #                 return Response(
    #                     {
    #                         'error': 'This activity is already fully allocated.',
    #                         'remaining_area': float(remaining),
    #                     },
    #                     status=status.HTTP_400_BAD_REQUEST,
    #                 )

    #             if allocated_area > remaining and not force:
    #                 return Response(
    #                     {
    #                         'error': 'Allocated area exceeds remaining area.',
    #                         'remaining_area': float(remaining),
    #                     },
    #                     status=status.HTTP_400_BAD_REQUEST,
    #                 )

    #             # ── 7) Determine if this is the FIRST allocation on this activity ─
    #             is_first_allocation = job_activity.allocation_status == 'pending'

    #             # ── 8) Create the Allocation ──────────────────────────────────────
    #             allocation = Allocation.objects.create(
    #                 job_activity      = job_activity,
    #                 mukkadam          = mukkadam,
    #                 allocated_date    = allocated_date,
    #                 allocated_area    = allocated_area,
    #                 allocated_workers = allocated_workers,
    #                 farmer_rate       = farmer_rate,
    #                 mukkadam_rate     = mukkadam_rate,
    #                 status            = 'scheduled',
    #                 cluster           = cluster,
    #                 allows_second_job = allows_second_job,
    #                 created_by        = request.user,
    #                 last_modified_by  = request.user if request.user.is_authenticated else None,
    #                 last_modified_at  = timezone.now() if request.user.is_authenticated else None,
    #             )

    #             # ── 9) Update JobActivity.allocated_area ──────────────────────────
    #             total_allocated = Allocation.objects.filter(
    #                 job_activity=job_activity,
    #                 status__in=['scheduled', 'in_progress', 'completed'],
    #             ).aggregate(total=Sum('allocated_area'))['total'] or 0

    #             job_activity.allocated_area = total_allocated
    #             if is_first_allocation:
    #                 job_activity.scheduled_date = allocated_date_obj
    #             job_activity.save()

    #             # ── 10) Rule 2: Cascade downstream on FIRST allocation ────────────
    #             cascade_shifted  = []
    #             cascade_warnings = []

    #             if is_first_allocation:
    #                 cascade_shifted, cascade_warnings = _build_gap_map_and_cascade(
    #                     subsequent_qs=successors,
    #                     exclude_ids={job_activity.id},
    #                     current_seq_order=get_activity_sequence_order(job_activity),
    #                     reference_date=allocated_date_obj,
    #                     reason_prefix=(
    #                         f'Cascade from first allocation of {job_activity.activity.name} '
    #                         f'on {allocated_date_obj}'
    #                     ),
    #                     request=request,
    #                 )

    #             # ── 11) Notify mukkadam ───────────────────────────────────────────
    #             notify_mukkadam(
    #                 mobile_number=mukkadam.mobile_numbers,
    #                 title="नवीन काम मिळाले",
    #                 body=f"{job_activity.activity.name} - {allocation.allocated_date}",
    #                 data={
    #                     "type":          "job_detail",
    #                     "allocation_id": str(allocation.id),
    #                     "date":          str(allocation.allocated_date),
    #                 },
    #             )

    #             # ── 12) Fire signal ───────────────────────────────────────────────
    #             from .signals import allocation_created
    #             allocation_created.send(sender=Allocation, allocation=allocation)

    #             # ── 13) Build response ────────────────────────────────────────────
    #             serializer = self.get_serializer(allocation)

    #             response_data = {
    #                 'success':    True,
    #                 'allocation': serializer.data,
    #                 'message':    'Allocation created successfully',
    #             }

    #             if force:
    #                 response_data['message'] = 'Allocation created with productivity override'

    #             if warnings:
    #                 response_data['warnings'] = warnings

    #             if cascade_shifted:
    #                 response_data['cascade_shifted']  = cascade_shifted
    #                 response_data['cascade_warnings'] = cascade_warnings

    #             return Response(response_data, status=status.HTTP_201_CREATED)

    #     except Exception as e:
    #         return Response(
    #             {'error': f'Failed to create allocation: {str(e)}'},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         )
    
    @action(detail=False, methods=['post'])
    def create_allocation(self, request):
        ctx(flow="create_allocation",
        ja_id=str(request.data.get('job_activity_id')),
        mukkadam_id=str(request.data.get('mukkadam_id')),
        cluster_id=str(request.data.get('cluster_id')))
        """
        Create allocation with:
        - Productivity + availability validation (existing)
        - Remaining-area guard (existing)
        - Rule 1: Block if unallocated predecessor exists
        - Rule 4: Block if allocated_date violates sequence ordering
        - Rule 5: Block if activity is in-progress or completed+paid
        - Rule 2: After first allocation, cascade downstream unallocated
                    activities using reference + original_gap
        """
        from datetime import date as date_type, timedelta
        from django.db.models import Sum

        job_activity_id   = request.data.get('job_activity_id')
        mukkadam_id       = request.data.get('mukkadam_id')
        allocated_date    = request.data.get('allocated_date')
        cluster_id        = request.data.get('cluster_id')

        allocated_area    = Decimal(str(request.data.get('allocated_area', '0')))
        allocated_workers = int(request.data.get('allocated_workers', 0))
        farmer_rate       = Decimal(str(request.data.get('farmer_rate', '0')))
        mukkadam_rate     = Decimal(str(request.data.get('mukkadam_rate', '0')))
        force             = bool(request.data.get('force', False))
        skip_strict_check = bool(request.data.get('skip_strict_check', False))
        allows_second_job = bool(request.data.get('allows_second_job', False))

        if not cluster_id:
            return Response({'error': 'cluster_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not allocated_date:
            return Response({'error': 'allocated_date is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            allocated_date_obj = date_type.fromisoformat(str(allocated_date))
        except ValueError:
            return Response({'error': 'Invalid allocated_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        # ── 1) Business validation — only check remaining area ───────────────────
        can_allocate, message, warnings = check_can_allocate(
            job_activity_id,
            mukkadam_id,
            allocated_date,
            float(allocated_area),
            allocated_workers,
            skip_strict_check=skip_strict_check,
            cluster_id=cluster_id,
        )

        if not can_allocate:
            # ✅ Only hard-block on remaining area error — ignore all else
            if 'exceeds remaining' in message:
                return Response(
                    {'error': message, 'warnings': warnings},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # All other "errors" become warnings only — don't block
            warnings['soft_warning'] = message
            ops("allocation_soft_warning",
    ja_id=job_activity_id,
    mukkadam_id=mukkadam_id,
    warning=message)

        try:
            with transaction.atomic():

                # ── 2) Load objects with row lock on JobActivity ──────────────────
                try:
                    job_activity = JobActivity.objects.select_related(
                        'job__farmer',
                        'job__booking',
                        'activity',
                        'plot',
                    ).select_for_update(of=('self',)).get(id=job_activity_id)
                    mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
                    cluster  = Cluster.objects.get(id=cluster_id)
                except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist, Cluster.DoesNotExist) as e:
                    return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

                # ── 3) Rule 5: Block if in-progress ──────────────────────────────
                if job_activity.allocation_status == 'in_progress':
                    ops("create_allocation_blocked",
        ja_id=job_activity_id, reason="in_progress")
                    return Response(
                        {'error': 'Activity is in-progress and cannot be allocated.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ── 4) Rule 5: Block if completed + paid ─────────────────────────
                # Check if any allocation on this activity has payment triggered.
                # We use work_status='completed' + payment_status in ('done','settled')
                # as the "paid" signal.
                has_paid_completion = job_activity.allocations.filter(
                    work_status='completed',
                    payment_status__in=['done', 'settled'],
                ).exists()

                if job_activity.allocation_status == 'completed' and has_paid_completion:
                    ops("create_allocation_blocked",
        ja_id=job_activity_id, reason="completed_and_paid")
                    return Response(
                        {'error': 'Activity is completed and paid — no further allocations allowed.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ── 5) Load full job sequence for sequencing rules ────────────────
                # Done inside the transaction so we see the locked state.
                all_activities = list(
                    JobActivity.objects.filter(
                        job=job_activity.job,
                        plot=job_activity.plot,
                        total_area__gt=0,
                        is_lost=False,
                    ).select_related('activity')
                )
                all_activities.sort(key=lambda a: (
                    get_activity_sequence_order(a),
                    a.scheduled_date or date.min,
                    a.id,
                ))
                try:
                    current_idx = next(i for i, a in enumerate(all_activities) if a.id == job_activity.id)
                except StopIteration:
                    return Response({'error': 'Activity not found in job sequence'}, status=status.HTTP_400_BAD_REQUEST)

                predecessors = all_activities[:current_idx]
                successors   = all_activities[current_idx + 1:]

                # ── 6) Rule 1: Block if any unallocated predecessor exists ────────
                # for pred in predecessors:
                #     if pred.allocation_status == 'pending' and not pred.is_lost:
                #         return Response(
                #             {
                #                 'error': (
                #                     f'Cannot allocate "{job_activity.activity.name}" — '
                #                     f'"{pred.activity.name}" (scheduled {pred.scheduled_date}) '
                #                     f'is not yet allocated or cancelled. '
                #                     f'Allocate or cancel it first.'
                #                 )
                #             },
                #             status=status.HTTP_400_BAD_REQUEST,
                #         )

                # ── 7) Rule 4: Block if allocated_date before nearest alloc predecessor ──
                # nearest_alloc_pred = None
                # for pred in reversed(predecessors):
                #     if pred.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
                #         nearest_alloc_pred = pred
                #         break

                # if nearest_alloc_pred and allocated_date_obj <= nearest_alloc_pred.scheduled_date:
                #     return Response(
                #         {
                #             'error': (
                #                 f'Allocated date {allocated_date_obj} is on or before '
                #                 f'"{nearest_alloc_pred.activity.name}" '
                #                 f'(allocated on {nearest_alloc_pred.scheduled_date}). '
                #                 f'Move or cancel that allocation first.'
                #             )
                #         },
                #         status=status.HTTP_400_BAD_REQUEST,
                #     )

                # ── 8) Rule 4: Block if allocated_date after nearest alloc successor ──
                # nearest_alloc_succ = None
                # for succ in successors:
                #     if succ.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
                #         nearest_alloc_succ = succ
                #         break

                # if nearest_alloc_succ and allocated_date_obj >= nearest_alloc_succ.scheduled_date:
                #     return Response(
                #         {
                #             'error': (
                #                 f'Allocated date {allocated_date_obj} is on or after '
                #                 f'"{nearest_alloc_succ.activity.name}" '
                #                 f'(allocated on {nearest_alloc_succ.scheduled_date}). '
                #                 f'Move that allocation further first.'
                #             )
                #         },
                #         status=status.HTTP_400_BAD_REQUEST,
                #     )

                # ── 9) Remaining-area guard ───────────────────────────────────────
                remaining = (job_activity.total_area - job_activity.allocated_area).quantize(
                    Decimal('0.0001'), rounding=ROUND_HALF_UP,
                )

                if remaining <= Decimal('0'):
                    return Response(
                        {
                            'error': 'This activity is already fully allocated.',
                            'remaining_area': float(remaining),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if allocated_area > remaining and not force:
                    return Response(
                        {
                            'error': 'Allocated area exceeds remaining area.',
                            'remaining_area': float(remaining),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ── 10) Determine if this is the FIRST allocation on this activity ─
                # We need this to decide whether to trigger Rule 2 cascade.
                is_first_allocation = job_activity.allocation_status == 'pending'

                # ── 11) Create the Allocation ─────────────────────────────────────
                allocation = Allocation.objects.create(
                    job_activity      = job_activity,
                    mukkadam          = mukkadam,
                    allocated_date    = allocated_date,
                    allocated_area    = allocated_area,
                    allocated_workers = allocated_workers,
                    farmer_rate       = farmer_rate,
                    mukkadam_rate     = mukkadam_rate,
                    status            = 'scheduled',
                    cluster           = cluster,
                    allows_second_job = allows_second_job,
                    created_by        = request.user,
                    last_modified_by  = request.user if request.user.is_authenticated else None,
                    last_modified_at  = timezone.now() if request.user.is_authenticated else None,
                )
                ops("allocation_created_view",
    allocation_id=allocation.id,
    ja_id=job_activity_id,
    mukkadam_id=mukkadam_id,
    area=str(allocated_area),
    date=str(allocated_date),
    is_first=is_first_allocation,
    force=force,
    cluster_id=cluster_id)

                # ── 12) Update JobActivity.allocated_area (aggregate as source of truth) ──
                total_allocated = Allocation.objects.filter(
                    job_activity=job_activity,
                    status__in=['scheduled', 'in_progress', 'completed'],
                ).aggregate(total=Sum('allocated_area'))['total'] or 0

                job_activity.allocated_area = total_allocated
                # Also stamp the scheduled_date to allocated_date if this is first allocation
                # (Rule 2 — downstream gap recalc uses this as the reference)
                if is_first_allocation:
                    job_activity.scheduled_date = allocated_date_obj
                job_activity.save()  # remaining_area + allocation_status auto-calc in save()

                # ── 13) Rule 2: Cascade downstream unallocated after FIRST allocation ──
                #
                # When Act 1 is allocated for the first time, all downstream UNALLOCATED
                # activities recalculate their scheduled_date using:
                #   new_date = reference_date + original_gap_days
                #
                # Reference starts at allocated_date_obj and advances after each unallocated
                # activity. Allocated successors become the new anchor (Rule 4).
                cascade_shifted  = []
                cascade_warnings = []

                if is_first_allocation:
                    # Build gap_map for all activities in the job
                    gap_map = {}
                    for i, act in enumerate(all_activities):
                        if i == 0:
                            gap_map[act.id] = 0
                        else:
                            prev = all_activities[i - 1]
                            if act.original_gap_days is not None:
                                gap_map[act.id] = act.original_gap_days
                            else:
                                # Fallback: compute from current scheduled_dates
                                if act.scheduled_date and prev.scheduled_date:
                                    gap_map[act.id] = (act.scheduled_date - prev.scheduled_date).days
                                else:
                                    gap_map[act.id] = 0

                    reference_date = allocated_date_obj  # start from the newly allocated date

                    for succ in successors:
                        # Already allocated → stays fixed, reset reference anchor
                        if succ.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
                            reference_date = succ.scheduled_date
                            cascade_warnings.append({
                                'activity_id':   succ.id,
                                'activity_name': succ.activity.name,
                                'old_date':      str(succ.scheduled_date),
                                'new_date':      str(succ.scheduled_date),
                                'message':       f'Skipped — already {succ.allocation_status}. '
                                                f'Becomes new reference anchor.',
                            })
                            continue

                        # Manually moved → skip, do NOT update reference
                        if succ.is_manually_moved:
                            cascade_warnings.append({
                                'activity_id':   succ.id,
                                'activity_name': succ.activity.name,
                                'old_date':      str(succ.scheduled_date),
                                'new_date':      str(succ.scheduled_date),
                                'message':       'Skipped — manually moved',
                            })
                            continue

                        # Zero area → skip
                        if not succ.total_area or succ.total_area <= 0:
                            cascade_warnings.append({
                                'activity_id':   succ.id,
                                'activity_name': succ.activity.name,
                                'old_date':      str(succ.scheduled_date),
                                'new_date':      str(succ.scheduled_date),
                                'message':       'Skipped — zero area',
                            })
                            continue

                        # Unallocated → recalculate
                        gap      = gap_map.get(succ.id, 0)
                        old_date = succ.scheduled_date
                        new_succ_date = reference_date + timedelta(days=gap)

                        succ.scheduled_date = new_succ_date
                        succ.move_reason    = (
                            f'Cascade from first allocation of {job_activity.activity.name} '
                            f'on {allocated_date_obj}'
                        )
                        if request.user and request.user.is_authenticated:
                            succ.last_moved_by = request.user
                            succ.last_moved_at = timezone.now()
                        succ.save(update_fields=[
                            'scheduled_date', 'move_reason',
                            'last_moved_by', 'last_moved_at',
                        ])

                        reference_date = new_succ_date  # advance reference

                        cascade_shifted.append({
                            'activity_id':   succ.id,
                            'activity_name': succ.activity.name,
                            'old_date':      str(old_date),
                            'new_date':      str(new_succ_date),
                            'gap_used':      gap,
                        })
                ops("allocation_cascade_done",
    allocation_id=allocation.id,
    ja_id=job_activity_id,
    cascaded=len(cascade_shifted),
    warnings=len(cascade_warnings),
    is_first=is_first_allocation)
                # ── 14) Notify mukkadam ───────────────────────────────────────────
                notify_mukkadam(
                    mobile_number=mukkadam.mobile_numbers,
                    title="नवीन काम मिळाले",
                    body=f"{job_activity.activity.name} - {allocation.allocated_date}",
                    data={
                        "type":          "job_detail",
                        "allocation_id": str(allocation.id),
                        "date":          str(allocation.allocated_date),
                    },
                )

                # ── 15) Fire signal ───────────────────────────────────────────────
                from .signals import allocation_created
                allocation_created.send(sender=Allocation, allocation=allocation)

                # ── 16) Build response ────────────────────────────────────────────
                serializer = self.get_serializer(allocation)

                response_data = {
                    'success':    True,
                    'allocation': serializer.data,
                    'message':    'Allocation created successfully',
                }

                if force:
                    response_data['message'] = 'Allocation created with productivity override'

                if warnings:
                    response_data['warnings'] = warnings

                if cascade_shifted:
                    response_data['cascade_shifted']  = cascade_shifted
                    response_data['cascade_warnings'] = cascade_warnings

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            err("create_allocation_fail",
        ja_id=job_activity_id,
        mukkadam_id=mukkadam_id,
        error=str(e)[:100])
            return Response(
                {'error': f'Failed to create allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    
    @action(detail=False, methods=['post'])
    def validate_allocation(self, request):
        """
        Validate allocation BEFORE creating it.
        Returns detailed warnings about productivity, capacity, remaining area, etc.
        Frontend calls this FIRST to check if allocation is possible.
        """

        job_activity_id = request.data.get('job_activity_id')
        mukkadam_id = request.data.get('mukkadam_id')
        allocated_area = float(request.data.get('allocated_area', 0))
        allocated_workers = int(request.data.get('allocated_workers', 0))
        skip_strict_check = bool(request.data.get('skip_strict_check', False))

        allocated_date_str = request.data.get('allocated_date')

        try:
            allocated_date = datetime.strptime(allocated_date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"can_allocate": False, "error": "Invalid allocated_date", "warnings": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cluster_id = request.data.get('cluster_id')

        # First do the same business validation
        result = check_can_allocate(
            job_activity_id,
            mukkadam_id,
            allocated_date,
            allocated_area,
            allocated_workers,
            skip_strict_check=skip_strict_check,
            cluster_id=cluster_id,
        )

        if not result or len(result) != 3:
            return Response(
                {
                    "can_allocate": False,
                    "error": "Internal validation error",
                    "warnings": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        can_allocate, message, warnings = result

        # Extra: Remaining-area validation for preview
        try:
            job_activity = JobActivity.objects.get(id=job_activity_id)

            remaining = float(job_activity.total_area - job_activity.allocated_area)
            if remaining <= 0:
                return Response(
                    {
                        'can_allocate': False,
                        'error': 'This activity is already fully allocated.',
                        'warnings': {
                            **warnings,
                            'remaining_area': {'value': remaining, 'severity': 'error'},
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if allocated_area > remaining:
                return Response(
                    {
                        'can_allocate': False,
                        'error': 'Allocated area exceeds remaining area.',
                        'warnings': {
                            **warnings,
                            'remaining_area': {
                                'value': remaining,
                                'severity': 'error',
                                'message': 'Requested area is more than remaining area.',
                            },
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except JobActivity.DoesNotExist:
            return Response(
                {
                    'can_allocate': False,
                    'error': 'JobActivity not found',
                    'warnings': {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # If validation failed earlier
        if not can_allocate:
            return Response({
                'can_allocate': False,
                'error': message,
                'warnings': warnings
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get rate information for preview
        try:
            mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)

            mukkadam_rate_obj = mukkadam.activity_rates.get(
                activity=job_activity.activity,
                is_active=True
            )

            farmer_rate = float(job_activity.rate_per_acre)
            mukkadam_rate = float(mukkadam_rate_obj.rate_per_acre)

            farmer_amount = allocated_area * farmer_rate
            mukkadam_amount = allocated_area * mukkadam_rate
            profit = farmer_amount - mukkadam_amount

            return Response({
                'can_allocate': True,
                'message': message,
                'warnings': warnings,
                'preview': {
                    'job_id': job_activity.job.job_id,
                    'farmer_name': job_activity.job.farmer.farmer_name,
                    'activity': job_activity.activity.name,
                    'mukkadam': mukkadam.mukkadam_name,
                    'date': allocated_date,
                    'area': allocated_area,
                    'workers': allocated_workers,
                    'productivity': float(mukkadam_rate_obj.productivity_per_worker),
                    'max_capacity': allocated_workers * float(mukkadam_rate_obj.productivity_per_worker),
                    'pricing': {
                        'farmer_rate': farmer_rate,
                        'mukkadam_rate': mukkadam_rate,
                        'farmer_amount': farmer_amount,
                        'mukkadam_amount': mukkadam_amount,
                        'profit': profit,
                        'profit_margin': f"{(profit/farmer_amount)*100:.1f}%" if farmer_amount > 0 else "0%"
                    }
                }
            })

        except Exception as e:
            # Even if preview fails, main validation passed
            return Response({
                'can_allocate': True,
                'message': message,
                'warnings': warnings,
                'note': str(e)
            })
    
    
    @action(detail=True, methods=['post'])
    def update_productivity_and_reallocate(self, request, pk=None):
        """
        Update mukkadam's productivity for an activity and re-validate allocation
        
        Use case: User decides to update productivity instead of reducing area
        """
        allocation = self.get_object()
        new_productivity = float(request.data.get('productivity_per_worker'))
        
        try:
            # Update productivity
            mukkadam_rate = allocation.mukkadam.activity_rates.get(
                activity=allocation.job_activity.activity,
                is_active=True
            )
            
            old_productivity = float(mukkadam_rate.productivity_per_worker)
            mukkadam_rate.productivity_per_worker = new_productivity
            mukkadam_rate.save()
            
            # Re-validate with new productivity
            new_capacity = allocation.allocated_workers * new_productivity
            
            return Response({
                'success': True,
                'message': 'Productivity updated',
                'changes': {
                    'old_productivity': old_productivity,
                    'new_productivity': new_productivity,
                    'old_capacity': allocation.allocated_workers * old_productivity,
                    'new_capacity': new_capacity,
                    'allocated_area': float(allocation.allocated_area),
                    'can_complete': new_capacity >= float(allocation.allocated_area)
                }
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def productivity_report(self, request):
        """
        Get productivity report for all mukkadams
        Shows efficiency for each activity
        """
        mukkadam_id = request.query_params.get('mukkadam_id')
        
        if mukkadam_id:
            mukkadams = Mukkadam.objects.filter(mukkadam_id=mukkadam_id)
        else:
            mukkadams = Mukkadam.objects.all()
        
        report = []


        
        for mukkadam in mukkadams:
            rates = mukkadam.activity_rates.filter(is_active=True)
            
            mukkadam_data = {
                'mukkadam_id': mukkadam.mukkadam_id,
                'mukkadam_name': mukkadam.mukkadam_name,
                'crew_size': mukkadam.crew_size,
                'activities': []
            }
            
            for rate in rates:
                productivity = float(rate.productivity_per_worker)
                daily_capacity = mukkadam.crew_size * productivity
                
                mukkadam_data['activities'].append({
                    'activity': rate.activity.name,
                    'rate_per_acre': float(rate.rate_per_acre),
                    'productivity_per_worker': productivity,
                    'daily_capacity_with_full_crew': daily_capacity,
                    'efficiency_rating': (
                        'Excellent' if productivity >= 0.20 else
                        'Good' if productivity >= 0.15 else
                        'Average' if productivity >= 0.10 else
                        'Below Average'
                    )
                })
            
            report.append(mukkadam_data)
        
        return Response({'report': report})
    # @action(detail=True, methods=['post'])
    # def change_date(self, request, pk=None):
    #     """
    #     Move an existing Allocation to a new date (full or partial area).

    #     Rules enforced:
    #     Rule 5  — Block if work_status=in_progress or completed+paid
    #     Rule 4  — Block if new_date violates sequence ordering vs allocated neighbours
    #     Rule 3  — If all downstream unallocated, cascade shifts by delta
    #     Rule 4  — If a downstream allocated activity exists, it anchors; unallocated
    #                 activities after it recalculate via reference + original_gap
    #     """
    #     from datetime import timedelta
    #     from django.db.models import Sum

    #     allocation = self.get_object()
    #     date_str   = request.data.get('allocated_date')
    #     new_area   = request.data.get('allocated_area')

    #     if not date_str:
    #         return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    #     except ValueError:
    #         return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

    #     if new_area is not None:
    #         new_area = Decimal(str(new_area))
    #         if new_area <= 0:
    #             return Response({"error": "allocated_area must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
    #         if new_area > allocation.allocated_area:
    #             return Response(
    #                 {"error": f"Cannot move more than allocated area ({allocation.allocated_area} ac)"},
    #                 status=status.HTTP_400_BAD_REQUEST,
    #             )
    #     else:
    #         new_area = allocation.allocated_area

    #     # ── Rule 5: Block if in-progress ─────────────────────────────────────────
    #     if allocation.work_status == 'in_progress':
    #         return Response(
    #             {"error": "Allocation is in-progress and cannot be moved."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # ── Rule 5: Block if completed + paid ────────────────────────────────────
    #     if allocation.work_status == 'completed' and allocation.payment_status in ('done', 'settled'):
    #         return Response(
    #             {"error": "Allocation is completed and paid — no changes allowed."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     try:
    #         with transaction.atomic():
    #             # Re-fetch job_act with lock inside transaction
    #             job_act  = JobActivity.objects.select_for_update(of=('self',)).get(
    #                 id=allocation.job_activity.id
    #             )
    #             mukkadam = allocation.mukkadam

    #             # ---------- 0) Compute workers_needed ----------
    #             is_full_move = new_area >= allocation.allocated_area

    #             if is_full_move:
    #                 workers_needed = allocation.allocated_workers
    #             else:
    #                 try:
    #                     rate_obj     = mukkadam.activity_rates.get(activity=job_act.activity, is_active=True)
    #                     productivity = Decimal(str(rate_obj.productivity_per_worker))
    #                 except Exception:
    #                     productivity = Decimal('0')

    #                 if productivity > 0:
    #                     workers_needed = max(1, int(
    #                         (new_area / productivity).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    #                     ))
    #                 else:
    #                     workers_needed = max(1, int(
    #                         allocation.allocated_workers * float(new_area / allocation.allocated_area)
    #                     ))

    #             # ---------- 0b) Capacity check ----------
    #             crew = mukkadam.crew_size or 0

    #             used_across_all = Allocation.objects.filter(
    #                 mukkadam=mukkadam,
    #                 allocated_date=new_date,
    #                 status__in=['scheduled', 'in_progress'],
    #             ).exclude(pk=allocation.pk).aggregate(
    #                 total=models.Sum('allocated_workers')
    #             )['total'] or 0

    #             on_leave = Leave.objects.filter(
    #                 leave_type='mukkadam',
    #                 mukkadam=mukkadam,
    #                 date=new_date,
    #                 is_active=True,
    #             ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

    #             remaining_capacity = max(crew - used_across_all - on_leave, 0)

    #             # ---------- 0c) Holiday check ----------
    #             is_holiday = Leave.objects.filter(
    #                 date=new_date, is_active=True
    #             ).filter(
    #                 Q(leave_type='general') |
    #                 Q(leave_type='mukkadam', mukkadam=mukkadam)
    #             ).exists()

    #             if is_holiday:
    #                 return Response(
    #                     {'error': f'{new_date} is a holiday for this mukkadam'},
    #                     status=status.HTTP_400_BAD_REQUEST,
    #                 )

    #             # ---------- 1) Capture original date for cascade ----------
    #             original_date = job_act.scheduled_date
    #             day_delta     = (new_date - original_date).days if original_date else 0

    #             # ---------- 2) Update allocation ----------
    #             remaining_area_alloc = allocation.allocated_area - new_area

    #             if remaining_area_alloc > Decimal('0.01'):
    #                 # Partial move — shrink original allocation, create new on new_date
    #                 allocation.allocated_area   = remaining_area_alloc
    #                 allocation.last_modified_by = request.user if request.user.is_authenticated else None
    #                 allocation.last_modified_at = timezone.now()
    #                 allocation.save()

    #                 new_allocation = Allocation.objects.create(
    #                     job_activity      = job_act,
    #                     mukkadam          = mukkadam,
    #                     allocated_date    = new_date,
    #                     allocated_area    = new_area,
    #                     allocated_workers = workers_needed,
    #                     farmer_rate       = allocation.farmer_rate,
    #                     mukkadam_rate     = allocation.mukkadam_rate,
    #                     cluster           = allocation.cluster,
    #                     status            = 'scheduled',
    #                     created_by        = request.user if request.user.is_authenticated else None,
    #                     last_modified_by  = request.user if request.user.is_authenticated else None,
    #                     last_modified_at  = timezone.now(),
    #                 )
    #             else:
    #                 # Full move — update existing allocation in place
    #                 allocation.allocated_date    = new_date
    #                 allocation.allocated_area    = new_area
    #                 allocation.allocated_workers = workers_needed
    #                 allocation.last_modified_by  = request.user if request.user.is_authenticated else None
    #                 allocation.last_modified_at  = timezone.now()
    #                 allocation.save()
    #                 new_allocation = None

    #             # ---------- 3) If date actually changed — split JobActivity + cascade ----------
    #             shifted_activities = []
    #             warnings           = []
    #             new_job_activity   = None

    #             if day_delta != 0 and original_date:

    #                 # ── Shrink original JobActivity ──
    #                 job_act.total_area     = max(Decimal('0'), job_act.total_area - new_area)
    #                 job_act.allocated_area = max(Decimal('0'), job_act.allocated_area - new_area)
    #                 job_act.remaining_area = max(Decimal('0'), job_act.total_area - job_act.allocated_area)
    #                 job_act.move_reason    = f'Allocation split — {new_area}ac moved to {new_date}'
    #                 if request.user and request.user.is_authenticated:
    #                     job_act.last_moved_by = request.user
    #                     job_act.last_moved_at = timezone.now()
    #                 job_act.save(update_fields=[
    #                     'total_area', 'allocated_area', 'remaining_area',
    #                     'move_reason', 'last_moved_by', 'last_moved_at',
    #                 ])

    #                 # ── Create new JobActivity on new_date ──
    #                 new_job_activity = JobActivity.objects.create(
    #                     job                     = job_act.job,
    #                     activity                = job_act.activity,
    #                     plot                    = job_act.plot,
    #                     is_strict               = job_act.is_strict,
    #                     total_area              = new_area,
    #                     allocated_area          = new_area,
    #                     remaining_area          = Decimal('0'),
    #                     scheduled_date          = new_date,
    #                     original_scheduled_date = job_act.original_scheduled_date or original_date,
    #                     original_gap_days       = job_act.original_gap_days,
    #                     rate_per_acre           = job_act.rate_per_acre,
    #                     transport_cost          = job_act.transport_cost,
    #                     other_cost              = job_act.other_cost,
    #                     estimated_workers       = job_act.estimated_workers,
    #                     location                = job_act.location,
    #                     is_manually_moved       = True,
    #                     moved_from_activity     = job_act,
    #                     source                  = 'manual',
    #                     original_source         = job_act.original_source,
    #                     move_reason             = f'Allocation moved from {original_date} via change_date',
    #                     api_activity_id         = job_act.api_activity_id,
    #                     allocation_status       = 'fully_allocated',
    #                     is_fully_allocated      = True,
    #                     created_by              = request.user if request.user.is_authenticated else None,
    #                     last_moved_by           = request.user if request.user.is_authenticated else None,
    #                     last_moved_at           = timezone.now() if request.user.is_authenticated else None,
    #                 )

    #                 # ── Re-point allocation to new JobActivity ──
    #                 if new_allocation:
    #                     new_allocation.job_activity = new_job_activity
    #                     new_allocation.save(update_fields=['job_activity'])
    #                 else:
    #                     allocation.job_activity = new_job_activity
    #                     allocation.save(update_fields=['job_activity'])

    #                 # ── Cascade subsequent activities ──
    #                 shifted_activities, warnings = _build_gap_map_and_cascade(
    #                     subsequent_qs=JobActivity.objects.filter(
    #                         job=job_act.job,
    #                         plot=job_act.plot,
    #                         is_lost=False,
    #                     ).exclude(id__in={job_act.id, new_job_activity.id}).select_related('activity'),
    #                     exclude_ids={job_act.id, new_job_activity.id},
    #                     current_seq_order=get_activity_sequence_order(job_act),
    #                     reference_date=new_date,
    #                     reason_prefix=f'Cascade from allocation change_date — activity {job_act.id}',
    #                     request=request,
    #                 )

    #             else:
    #                 # Same date — no JobActivity split needed.
    #                 # If it was a partial allocation move, adjust job_act.allocated_area.
    #                 if new_allocation:
    #                     job_act.allocated_area = max(
    #                         Decimal('0'),
    #                         job_act.allocated_area - new_area,
    #                     )
    #                     job_act.save(update_fields=['allocated_area'])

    #         return Response({
    #             'success':             True,
    #             'message':             'Moved successfully',
    #             'day_delta':           day_delta,
    #             'new_job_activity_id': new_job_activity.id if new_job_activity else None,
    #             'shifted_activities':  shifted_activities,
    #             'warnings':            warnings,
    #             'remaining_capacity':  remaining_capacity,
    #             'workers_needed':      workers_needed,
    #         })

    #     except Exception as e:
    #         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def change_date(self, request, pk=None):
        ctx(flow="change_date",
        allocation_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        from datetime import timedelta
        from django.db.models import Sum

        allocation = self.get_object()
        date_str   = request.data.get('allocated_date')
        new_area   = request.data.get('allocated_area')

        if not date_str:
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        if new_area is not None:
            new_area = Decimal(str(new_area))
            if new_area <= 0:
                return Response({"error": "allocated_area must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
            if new_area > allocation.allocated_area:
                return Response(
                    {"error": f"Cannot move more than allocated area ({allocation.allocated_area} ac)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            new_area = allocation.allocated_area

        # ── Rule 5: Block if in-progress ─────────────────────────────────────
        if allocation.work_status == 'in_progress':
            return Response(
                {"error": "Allocation is in-progress and cannot be moved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rule 5: Block if completed + paid ────────────────────────────────
        if allocation.work_status == 'completed' and allocation.payment_status in ('done', 'settled'):
            return Response(
                {"error": "Allocation is completed and paid — no changes allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_act = allocation.job_activity

        all_activities = list(
            JobActivity.objects.filter(
                job=job_act.job,
                plot=job_act.plot,
                is_lost=False,
                total_area__gt=0,
            ).select_related('activity')
        )
        all_activities.sort(key=lambda a: (
            get_activity_sequence_order(a),
            a.scheduled_date or date.min,
            a.id,
        ))

        try:
            current_idx = next(i for i, a in enumerate(all_activities) if a.id == job_act.id)
        except StopIteration:
            return Response({"error": "Job activity not found in sequence"}, status=status.HTTP_400_BAD_REQUEST)

        successors = all_activities[current_idx + 1:]

        try:
            with transaction.atomic():
                job_act  = JobActivity.objects.select_for_update(of=('self',)).get(id=job_act.id)
                mukkadam = allocation.mukkadam

                # ---------- 0) Compute workers_needed ----------
                is_full_move = new_area >= allocation.allocated_area

                if is_full_move:
                    workers_needed = allocation.allocated_workers
                else:
                    try:
                        rate_obj     = mukkadam.activity_rates.get(activity=job_act.activity, is_active=True)
                        productivity = Decimal(str(rate_obj.productivity_per_worker))
                    except Exception:
                        productivity = Decimal('0')

                    if productivity > 0:
                        workers_needed = max(1, int(
                            (new_area / productivity).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                        ))
                    else:
                        workers_needed = max(1, int(
                            allocation.allocated_workers * float(new_area / allocation.allocated_area)
                        ))

                # ---------- 0b) Capacity check ----------
                crew = mukkadam.crew_size or 0

                used_across_all = Allocation.objects.filter(
                    mukkadam=mukkadam,
                    allocated_date=new_date,
                    status__in=['scheduled', 'in_progress'],
                ).exclude(pk=allocation.pk).aggregate(
                    total=models.Sum('allocated_workers')
                )['total'] or 0

                on_leave = Leave.objects.filter(
                    leave_type='mukkadam',
                    mukkadam=mukkadam,
                    date=new_date,
                    is_active=True,
                ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

                remaining_capacity = max(crew - used_across_all - on_leave, 0)

                # ---------- 0c) Holiday check ----------
                is_holiday = Leave.objects.filter(
                    date=new_date, is_active=True
                ).filter(
                    Q(leave_type='general') |
                    Q(leave_type='mukkadam', mukkadam=mukkadam)
                ).exists()

                if is_holiday:
                    ops("change_date_blocked",
        allocation_id=pk, reason="holiday",
        date=str(new_date),
        mukkadam_id=str(mukkadam.mukkadam_id))
                    return Response(
                        {'error': f'{new_date} is a holiday for this mukkadam'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ---------- 1) Capture original date ----------
                original_date = job_act.scheduled_date
                day_delta     = (new_date - original_date).days if original_date else 0

                # ---------- 2) Update allocation ----------
                remaining_area_alloc = allocation.allocated_area - new_area

                if remaining_area_alloc > Decimal('0.01'):
                    # Partial move — shrink original, create new
                    allocation.allocated_area   = remaining_area_alloc
                    allocation.last_modified_by = request.user if request.user.is_authenticated else None
                    allocation.last_modified_at = timezone.now()
                    allocation.save()

                    new_allocation = Allocation.objects.create(
                        job_activity      = job_act,
                        mukkadam          = mukkadam,
                        allocated_date    = new_date,
                        allocated_area    = new_area,
                        allocated_workers = workers_needed,
                        farmer_rate       = allocation.farmer_rate,
                        mukkadam_rate     = allocation.mukkadam_rate,
                        cluster           = allocation.cluster,
                        status            = 'scheduled',
                        created_by        = request.user if request.user.is_authenticated else None,
                        last_modified_by  = request.user if request.user.is_authenticated else None,
                        last_modified_at  = timezone.now(),
                    )
                    ops("change_date_partial_move",
    allocation_id=pk,
    new_allocation_id=new_allocation.id,
    area=str(new_area),
    old_date=str(original_date),
    new_date=str(new_date))
                else:
                    # Full move — update in place
                    allocation.allocated_date    = new_date
                    allocation.allocated_area    = new_area
                    allocation.allocated_workers = workers_needed
                    allocation.last_modified_by  = request.user if request.user.is_authenticated else None
                    allocation.last_modified_at  = timezone.now()
                    allocation.save()
                    ops("change_date_full_move",
    allocation_id=pk,
    area=str(new_area),
    old_date=str(original_date),
    new_date=str(new_date),
    day_delta=day_delta)
                    new_allocation = None

                # ---------- 3) If date changed — split JobActivity + cascade ----------
                shifted_activities = []
                warnings           = []
                new_job_activity   = None

                if day_delta != 0 and original_date:

                    # ── Shrink original JobActivity (raw update, no signals) ──
                    # ── Shrink original JobActivity (raw update, no signals) ──
                    JobActivity.objects.filter(pk=job_act.pk).update(
                        total_area=models.F('total_area') - new_area,
                        allocated_area=models.F('allocated_area') - new_area,
                        move_reason=f'Allocation split — {new_area}ac moved to {new_date}',
                    )
                    job_act.refresh_from_db()

                    # Fix remaining_area
                    JobActivity.objects.filter(pk=job_act.pk).update(
                        remaining_area=models.F('total_area') - models.F('allocated_area'),
                    )
                    job_act.refresh_from_db()

                    # ── Fix allocation_status + is_fully_allocated on original JA ──
                    if job_act.allocated_area <= 0:
                        new_status = 'pending'
                        is_fully = False
                    elif job_act.allocated_area >= job_act.total_area:
                        new_status = 'fully_allocated'
                        is_fully = True
                    else:
                        new_status = 'partially_allocated'
                        is_fully = False

                    JobActivity.objects.filter(pk=job_act.pk).update(
                        allocation_status=new_status,
                        is_fully_allocated=is_fully,
                    )

                    # ── Create new JobActivity on new_date ──
                    new_job_activity = JobActivity.objects.create(
                        job                     = job_act.job,
                        activity                = job_act.activity,
                        plot                    = job_act.plot,
                        is_strict               = job_act.is_strict,
                        total_area              = new_area,
                        allocated_area          = new_area,
                        remaining_area          = Decimal('0'),
                        scheduled_date          = new_date,
                        original_scheduled_date = job_act.original_scheduled_date or original_date,
                        original_gap_days       = 0,
                        rate_per_acre           = job_act.rate_per_acre,
                        transport_cost          = job_act.transport_cost,
                        other_cost              = job_act.other_cost,
                        estimated_workers       = job_act.estimated_workers,
                        location                = job_act.location,
                        is_manually_moved       = True,
                        moved_from_activity     = job_act,
                        source                  = 'manual',
                        original_source         = job_act.original_source,
                        move_reason             = f'Allocation moved from {original_date} via change_date',
                        api_activity_id         = job_act.api_activity_id,
                        allocation_status       = 'fully_allocated',
                        is_fully_allocated      = True,
                        created_by              = request.user if request.user.is_authenticated else None,
                        last_moved_by           = request.user if request.user.is_authenticated else None,
                        last_moved_at           = timezone.now() if request.user.is_authenticated else None,
                    )
                    ops("change_date_ja_split",
    original_ja_id=job_act.id,
    new_ja_id=new_job_activity.id,
    area=str(new_area),
    from_date=str(original_date),
    to_date=str(new_date),
    job_id=str(job_act.job.job_id))

                    # ── Re-point allocation to new JobActivity ──
                    if new_allocation:
                        new_allocation.job_activity = new_job_activity
                        new_allocation.save(update_fields=['job_activity'])
                    else:
                        allocation.job_activity = new_job_activity
                        allocation.save(update_fields=['job_activity'])

                    # ── Cascade: shift all subsequent by same day_delta ──
                    current_seq_order = get_activity_sequence_order(job_act)
                    exclude_ids = {job_act.id, new_job_activity.id}

                    for act in successors:
                        if act.id in exclude_ids:
                            continue
                        if get_activity_sequence_order(act) <= current_seq_order:
                            continue

                        # Allocated/completed → skip
                        if act.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
                            warnings.append({
                                'activity_id':   act.id,
                                'activity_name': act.activity.name,
                                'old_date':      str(act.scheduled_date),
                                'new_date':      str(act.scheduled_date),
                                'message':       f'Skipped — already {act.allocation_status}.',
                            })
                            continue

                        # Manually moved → skip
                        if act.is_manually_moved:
                            warnings.append({
                                'activity_id':   act.id,
                                'activity_name': act.activity.name,
                                'old_date':      str(act.scheduled_date),
                                'new_date':      str(act.scheduled_date),
                                'message':       'Skipped — manually moved',
                            })
                            continue

                        # Zero area → skip
                        if not act.total_area or act.total_area <= 0:
                            warnings.append({
                                'activity_id':   act.id,
                                'activity_name': act.activity.name,
                                'old_date':      str(act.scheduled_date),
                                'new_date':      str(act.scheduled_date),
                                'message':       'Skipped — zero area',
                            })
                            continue

                        # ── Simple shift by same day_delta ──
                        old_date     = act.scheduled_date
                        new_act_date = old_date + timedelta(days=day_delta)

                        JobActivity.objects.filter(pk=act.pk).update(
                            scheduled_date=new_act_date,
                            move_reason=f'Cascade from allocation change_date — activity {job_act.id}',
                        )

                        shifted_activities.append({
                            'activity_id':   act.id,
                            'activity_name': act.activity.name,
                            'old_date':      str(old_date),
                            'new_date':      str(new_act_date),
                            'shift_days':    day_delta,
                        })
                        ops("change_date_cascade_shifted",
    trigger_ja_id=job_act.id,
    affected_ja_id=act.id,
    old_date=str(old_date),
    new_date=str(new_act_date),
    shift_days=day_delta)

                else:
                    # Same date — partial allocation move only
                    if new_allocation:
                        JobActivity.objects.filter(pk=job_act.pk).update(
                            allocated_area=models.F('allocated_area') - new_area,
                        )

            ops("change_date_done",
    allocation_id=pk,
    day_delta=day_delta,
    new_ja_id=new_job_activity.id if new_job_activity else None,
    cascaded=len(shifted_activities),
    warnings=len(warnings))

            return Response({
                'success':             True,
                'message':             'Moved successfully',
                'day_delta':           day_delta,
                'new_job_activity_id': new_job_activity.id if new_job_activity else None,
                'shifted_activities':  shifted_activities,
                'warnings':            warnings,
                'remaining_capacity':  remaining_capacity,
                'workers_needed':      workers_needed,
            })

        except Exception as e:
            err("change_date_fail",
        allocation_id=pk,
        error=str(e)[:100])
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        cluster_id = request.query_params.get('cluster_id')

        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date parameters required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        allocations = self.get_queryset().filter(
            allocated_date__range=[start_date, end_date]
        )

        if cluster_id:
            allocations = allocations.filter(
                Q(job_activity__plot__clusters__id=cluster_id) |
                Q(cluster_id=cluster_id)  # fallback for allocations without plot
            ).distinct()
        allocations = allocations.order_by('allocated_date')

        calendar_data = {}
        for allocation in allocations:
            date_str = str(allocation.allocated_date)
            if date_str not in calendar_data:
                calendar_data[date_str] = []
            serializer = self.get_serializer(allocation)
            calendar_data[date_str].append(serializer.data)

        return Response(calendar_data)
    
    
    
    # views.py - Add to AllocationViewSet
# views.py - Add to AllocationViewSet

    @action(detail=True, methods=['patch'])
    def update_allocation(self, request, pk=None):
        ctx(flow="update_allocation",
        allocation_id=pk,
        cluster_id=str(cluster_id))
        """
        Update an existing allocation
        PATCH /api/allocations/{id}/update_allocation/?cluster_id={cluster_id}
        
        Editable: mukkadam, date, workers, area
        NOT editable: activity, job
        
        Reuses the same validation logic as create_allocation
        """
        allocation = self.get_object()
        cluster_id = request.query_params.get('cluster_id')
        
        if not cluster_id:
            return Response(
                {'error': 'cluster_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new values (or keep existing)
        mukkadam_id = request.data.get('mukkadam_id', allocation.mukkadam.mukkadam_id)
        allocated_date_str = request.data.get('allocated_date', str(allocation.allocated_date))
        allocated_workers = int(request.data.get('allocated_workers', allocation.allocated_workers))
        allocated_area = Decimal(str(request.data.get('allocated_area', allocation.allocated_area)))
        
        try:
            allocated_date = datetime.strptime(allocated_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # 1) TEMPORARILY ROLLBACK the old allocation impact
                old_job_activity = allocation.job_activity
                old_job_activity.allocated_area -= allocation.allocated_area
                old_job_activity.save()
                
                old_avail = MukkadamAvailability.objects.filter(
                    mukkadam=allocation.mukkadam,
                    date=allocation.allocated_date
                ).first()
                if old_avail:
                    old_avail.allocated_workers -= allocation.allocated_workers
                    old_avail.save()
                
                can_allocate, message, warnings = check_can_allocate(
                    old_job_activity.id,
                    mukkadam_id,
                    allocated_date,
                    float(allocated_area),
                    allocated_workers,
                    skip_strict_check=False,
                    cluster_id=cluster_id,  # ← ADD (already in query_params)
                )
                
                if not can_allocate:
                    ops("update_allocation_blocked",
        allocation_id=pk,
        reason=message[:80],
        mukkadam_id=str(mukkadam_id))
                    # ROLLBACK: Restore old values if validation fails
                    old_job_activity.allocated_area += allocation.allocated_area
                    old_job_activity.save()
                    if old_avail:
                        old_avail.allocated_workers += allocation.allocated_workers
                        old_avail.save()
                    
                    return Response(
                        {'error': message, 'warnings': warnings},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 3) Get new mukkadam and rates
                new_mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
                cluster = Cluster.objects.get(id=cluster_id)
                
                try:
                    mukkadam_rate_obj = new_mukkadam.activity_rates.get(
                        activity=old_job_activity.activity,
                        is_active=True
                    )
                    new_mukkadam_rate = mukkadam_rate_obj.rate_per_acre
                except MukkadamRate.DoesNotExist:
                    ops("update_allocation_blocked",
        allocation_id=pk,
        reason="mukkadam_rate_missing",
        mukkadam_id=str(mukkadam_id))
                    # ROLLBACK
                    old_job_activity.allocated_area += allocation.allocated_area
                    old_job_activity.save()
                    if old_avail:
                        old_avail.allocated_workers += allocation.allocated_workers
                        old_avail.save()
                    
                    return Response(
                        {'error': f'Mukkadam {new_mukkadam.mukkadam_name} does not have rate for {old_job_activity.activity.name}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 4) Apply new values
                allocation.mukkadam = new_mukkadam
                allocation.allocated_date = allocated_date
                allocation.allocated_workers = allocated_workers
                allocation.allocated_area = allocated_area
                allocation.mukkadam_rate = new_mukkadam_rate
                allocation.cluster = cluster
                # farmer_rate stays the same
                allocation.save()
                ops("allocation_updated_view",
    allocation_id=pk,
    ja_id=old_job_activity.id,
    new_mukkadam_id=str(mukkadam_id),
    area=str(allocated_area),
    date=str(allocated_date),
    cluster_id=str(cluster_id))
                
                # 5) Update job activity with new area
                old_job_activity.allocated_area += allocated_area
                old_job_activity.save()
                
                # 6) Update new mukkadam availability
                new_avail, _ = MukkadamAvailability.objects.get_or_create(
                    mukkadam=new_mukkadam,
                    date=allocated_date,
                    defaults={
                        'available_crew_size': new_mukkadam.crew_size,
                        'is_available': True,
                        'allocated_workers': 0
                    }
                )
                new_avail.allocated_workers += allocated_workers
                new_avail.save()
                
                serializer = self.get_serializer(allocation)
                
                response_data = {
                    'success': True,
                    'allocation': serializer.data,
                    'message': 'Allocation updated successfully'
                }
                
                if warnings:
                    response_data['warnings'] = warnings
                
                return Response(response_data)
                
        except Mukkadam.DoesNotExist:
            err("update_allocation_fail",
        allocation_id=pk,
        error=str(e)[:100])
            return Response(
                {'error': 'Mukkadam not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Cluster not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to update allocation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    # @action(detail=True, methods=['delete'])
    # def delete_allocation(self, request, pk=None):
    #     """
    #     Delete an allocation with:
    #     Rule 5  — Block if in-progress or completed+paid
    #     Rule 6  — After deletion, downstream unallocated activities recalculate
    #                 using nearest remaining allocated predecessor as reference,
    #                 or original sales_date / original_scheduled_date as fallback.
    #     """
    #     from datetime import timedelta
    #     from django.db.models import Sum

    #     allocation = self.get_object()

    #     # ── Rule 5: Block if in-progress ─────────────────────────────────────────
    #     if allocation.work_status == 'in_progress':
    #         return Response(
    #             {'error': 'Allocation is in-progress and cannot be deleted.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # ── Rule 5: Block if completed + paid ────────────────────────────────────
    #     if allocation.work_status == 'completed' and allocation.payment_status in ('done', 'settled'):
    #         return Response(
    #             {'error': 'Allocation is completed and paid — deletion not allowed.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     with transaction.atomic():
    #         job_activity = allocation.job_activity

    #         # ── Load full job sequence BEFORE delete, for Rule 6 cascade ─────────
    #         all_activities = list(
    #             JobActivity.objects.filter(
    #                 job=job_activity.job,
    #                 plot=job_activity.plot,
    #                 total_area__gt=0,
    #                 is_lost=False,
    #             ).select_related('activity')
    #         )
    #         all_activities.sort(key=lambda a: (
    #             get_activity_sequence_order(a),
    #             a.scheduled_date or date.min,
    #             a.id,
    #         ))

    #         try:
    #             current_idx = next(i for i, a in enumerate(all_activities) if a.id == job_activity.id)
    #         except StopIteration:
    #             return Response({'error': 'Job activity not found in sequence'}, status=status.HTTP_400_BAD_REQUEST)

    #         predecessors = all_activities[:current_idx]
    #         successors   = all_activities[current_idx + 1:]

    #         # ── Log BEFORE deleting ───────────────────────────────────────────────
    #         AllocationAuditLog.objects.create(
    #             action            = 'deleted',
    #             allocation_id     = allocation.id,
    #             job_activity_id   = job_activity.id,
    #             job_id            = job_activity.job.job_id,
    #             mukkadam_id       = allocation.mukkadam.mukkadam_id,
    #             mukkadam_name     = allocation.mukkadam.mukkadam_name,
    #             farmer_name       = job_activity.job.farmer.farmer_name,
    #             activity_name     = job_activity.activity.name,
    #             allocated_date    = allocation.allocated_date,
    #             allocated_area    = allocation.allocated_area,
    #             allocated_workers = allocation.allocated_workers,
    #             snapshot          = {
    #                 'allocated_area':    str(allocation.allocated_area),
    #                 'allocated_workers': allocation.allocated_workers,
    #                 'allocated_date':    str(allocation.allocated_date),
    #                 'mukkadam_rate':     str(allocation.mukkadam_rate),
    #                 'farmer_rate':       str(allocation.farmer_rate),
    #                 'work_status':       allocation.work_status,
    #                 'payment_status':    allocation.payment_status,
    #                 'notes':             allocation.notes,
    #             },
    #             changed_by = request.user if request.user.is_authenticated else None,
    #             notes      = (
    #                 f"Deleted via dashboard — restored {allocation.allocated_area}ac "
    #                 f"to activity #{job_activity.id}"
    #             ),
    #         )

    #         # ── Build payload before delete ───────────────────────────────────────
    #         deleted_payload = {
    #             "allocation_id":         allocation.id,
    #             "booking_id":            job_activity.job.booking.booking_id if job_activity.job.booking else None,
    #             "api_activity_id":       job_activity.api_activity_id or None,
    #             "activity_name":         job_activity.activity.name,
    #             "allocated_area":        float(allocation.allocated_area),
    #             "allocated_date":        str(allocation.allocated_date),
    #             "mukkadam_id":           allocation.mukkadam.mukkadam_id,
    #             "mukkadam_name":         allocation.mukkadam.mukkadam_name,
    #             "farmer_rate":           float(allocation.farmer_rate),
    #             "mukkadam_rate":         float(allocation.mukkadam_rate),
    #             "job_id":                job_activity.job.job_id,
    #             "farmer_id":             job_activity.job.farmer.farmer_id,
    #             "farmer_name":           job_activity.job.farmer.farmer_name,
    #             "plot_id":               job_activity.plot.id if job_activity.plot else None,
    #             "plot_code":             job_activity.plot.plot_code if job_activity.plot else None,
    #             "last_modified_by_id":   allocation.last_modified_by.id if allocation.last_modified_by else None,
    #             "last_modified_by_name": allocation.last_modified_by.get_full_name() if allocation.last_modified_by else None,
    #             "deleted_by_id":         request.user.id if request.user.is_authenticated else None,
    #             "deleted_by_name":       request.user.get_full_name() or request.user.username if request.user.is_authenticated else None,
    #             "deleted_at":            str(timezone.now()),
    #         }

    #         # ── Delete the allocation ─────────────────────────────────────────────
    #         allocation.delete()

    #         # ── Fire signal ───────────────────────────────────────────────────────
    #         from .signals import allocation_deleted
    #         allocation_deleted.send(sender=None, payload=deleted_payload)

    #         # ── Recalculate job_activity.allocated_area from remaining allocations ─
    #         total_still_allocated = Allocation.objects.filter(
    #             job_activity=job_activity,
    #             status__in=['scheduled', 'in_progress', 'completed'],
    #         ).aggregate(total=Sum('allocated_area'))['total'] or Decimal('0')

    #         job_activity.allocated_area = total_still_allocated
    #         job_activity.save()

    #         # ── Find fallback reference for cascade ───────────────────────────────
    #         fallback_reference = None

    #         # Check nearest still-allocated predecessor
    #         for pred in reversed(predecessors):
    #             pred_fresh = JobActivity.objects.get(id=pred.id)
    #             if pred_fresh.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
    #                 fallback_reference = pred_fresh.scheduled_date
    #                 break

    #         # If this activity itself still has allocations (partial delete)
    #         if total_still_allocated > Decimal('0'):
    #             fallback_reference = job_activity.scheduled_date

    #         # Final fallback: original sales/calendar date
    #         if fallback_reference is None:
    #             fallback_reference = (
    #                 job_activity.sales_date
    #                 or job_activity.original_scheduled_date
    #                 or job_activity.scheduled_date
    #             )

    #         # ── Cascade downstream unallocated activities ─────────────────────────
    #         cascade_shifted, cascade_warnings = _build_gap_map_and_cascade(
    #             subsequent_qs=successors,
    #             exclude_ids={job_activity.id},
    #             current_seq_order=get_activity_sequence_order(job_activity),
    #             reference_date=fallback_reference,
    #             reason_prefix=(
    #                 f'Cascade from deletion of allocation on '
    #                 f'{job_activity.activity.name} (activity #{job_activity.id})'
    #             ),
    #             request=request,
    #         )

    #     return Response(
    #         {
    #             'success':            True,
    #             'message':            'Allocation deleted',
    #             'fallback_reference': str(fallback_reference),
    #             'cascade_shifted':    cascade_shifted,
    #             'cascade_warnings':   cascade_warnings,
    #         },
    #         status=status.HTTP_200_OK,
    #     )
    @action(detail=True, methods=['delete'])
    def delete_allocation(self, request, pk=None):
        ctx(flow="delete_allocation",
        allocation_id=pk,
        user=str(request.user.id if request.user.is_authenticated else "anon"))
        from datetime import timedelta
        from django.db.models import Sum

        allocation = self.get_object()

        # ── Rule 5: Block if in-progress ─────────────────────────────────────
        if allocation.work_status == 'in_progress':
            ops("delete_allocation_blocked",
        allocation_id=pk, reason="in_progress")
            return Response(
                {'error': 'Allocation is in-progress and cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rule 5: Block if completed + paid ────────────────────────────────
        if allocation.work_status == 'completed' and allocation.payment_status in ('done', 'settled'):
            ops("delete_allocation_blocked",
        allocation_id=pk, reason="completed_and_paid")
            return Response(
                {'error': 'Allocation is completed and paid — deletion not allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            job_activity = allocation.job_activity

            # ── Log BEFORE deleting ───────────────────────────────────────────
            AllocationAuditLog.objects.create(
                action            = 'deleted',
                allocation_id     = allocation.id,
                job_activity_id   = job_activity.id,
                job_id            = job_activity.job.job_id,
                mukkadam_id       = allocation.mukkadam.mukkadam_id,
                mukkadam_name     = allocation.mukkadam.mukkadam_name,
                farmer_name       = job_activity.job.farmer.farmer_name,
                activity_name     = job_activity.activity.name,
                allocated_date    = allocation.allocated_date,
                allocated_area    = allocation.allocated_area,
                allocated_workers = allocation.allocated_workers,
                snapshot          = {
                    'allocated_area':    str(allocation.allocated_area),
                    'allocated_workers': allocation.allocated_workers,
                    'allocated_date':    str(allocation.allocated_date),
                    'mukkadam_rate':     str(allocation.mukkadam_rate),
                    'farmer_rate':       str(allocation.farmer_rate),
                    'work_status':       allocation.work_status,
                    'payment_status':    allocation.payment_status,
                    'notes':             allocation.notes,
                },
                changed_by = request.user if request.user.is_authenticated else None,
                notes      = (
                    f"Deleted via dashboard — restored {allocation.allocated_area}ac "
                    f"to activity #{job_activity.id}"
                ),
            )

            # ── Build payload before delete ───────────────────────────────────
            deleted_payload = {
                "allocation_id":         allocation.id,
                "booking_id":            job_activity.job.booking.booking_id if job_activity.job.booking else None,
                "api_activity_id":       job_activity.api_activity_id or None,
                "activity_name":         job_activity.activity.name,
                "allocated_area":        float(allocation.allocated_area),
                "allocated_date":        str(allocation.allocated_date),
                "mukkadam_id":           allocation.mukkadam.mukkadam_id,
                "mukkadam_name":         allocation.mukkadam.mukkadam_name,
                "farmer_rate":           float(allocation.farmer_rate),
                "mukkadam_rate":         float(allocation.mukkadam_rate),
                "job_id":                job_activity.job.job_id,
                "farmer_id":             job_activity.job.farmer.farmer_id,
                "farmer_name":           job_activity.job.farmer.farmer_name,
                "plot_id":               job_activity.plot.id if job_activity.plot else None,
                "plot_code":             job_activity.plot.plot_code if job_activity.plot else None,
                "last_modified_by_id":   allocation.last_modified_by.id if allocation.last_modified_by else None,
                "last_modified_by_name": allocation.last_modified_by.get_full_name() if allocation.last_modified_by else None,
                "deleted_by_id":         request.user.id if request.user.is_authenticated else None,
                "deleted_by_name":       request.user.get_full_name() or request.user.username if request.user.is_authenticated else None,
                "deleted_at":            str(timezone.now()),
            }

            # ── Delete the allocation ─────────────────────────────────────────
            allocation.delete()
            ops("allocation_deleted_view",
    allocation_id=pk,
    ja_id=job_activity.id,
    job_id=str(job_activity.job.job_id),
    mukkadam_id=str(deleted_payload['mukkadam_id']),
    area=str(deleted_payload['allocated_area']),
    date=str(deleted_payload['allocated_date']))

            # ── Fire custom signal ────────────────────────────────────────────
            from .signals import allocation_deleted
            allocation_deleted.send(sender=None, payload=deleted_payload)

        return Response(
            {
                'success':  True,
                'message':  'Allocation deleted',
            },
            status=status.HTTP_200_OK,
        )
   
    # @action(detail=True, methods=['delete'])
    # def delete_allocation(self, request, pk=None):
    #     """
    #     Delete an allocation with:
    #     Rule 5  — Block if in-progress or completed+paid
    #     Rule 6  — After deletion, downstream unallocated activities recalculate
    #                 using nearest remaining allocated predecessor as reference,
    #                 or original sales_date / original_scheduled_date as fallback.
    #     """
    #     from datetime import timedelta
    #     from django.db.models import Sum

    #     allocation = self.get_object()

    #     # ── Rule 5: Block if in-progress ─────────────────────────────────────────
    #     if allocation.work_status == 'in_progress':
    #         return Response(
    #             {'error': 'Allocation is in-progress and cannot be deleted.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # ── Rule 5: Block if completed + paid ────────────────────────────────────
    #     if allocation.work_status == 'completed' and allocation.payment_status in ('done', 'settled'):
    #         return Response(
    #             {'error': 'Allocation is completed and paid — deletion not allowed.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     with transaction.atomic():
    #         job_activity = allocation.job_activity

    #         # ── Load full job sequence BEFORE delete, for Rule 6 cascade ─────────
    #         all_activities = list(
    #             JobActivity.objects.filter(
    #                 job=job_activity.job,
    #                 plot=job_activity.plot,
    #                 total_area__gt=0,
    #                 is_lost=False,
    #             ).select_related('activity')
    #         )
    #         all_activities.sort(key=lambda a: (
    #             get_activity_sequence_order(a),
    #             a.scheduled_date or date.min,
    #             a.id,
    #         ))

    #         try:
    #             current_idx = next(i for i, a in enumerate(all_activities) if a.id == job_activity.id)
    #         except StopIteration:
    #             return Response({'error': 'Job activity not found in sequence'}, status=status.HTTP_400_BAD_REQUEST)

    #         predecessors = all_activities[:current_idx]
    #         successors   = all_activities[current_idx + 1:]

    #         # ── Snapshot gap_map before any writes ───────────────────────────────
    #         gap_map = {}
    #         for i, act in enumerate(all_activities):
    #             if i == 0:
    #                 gap_map[act.id] = 0
    #             else:
    #                 prev = all_activities[i - 1]
    #                 if act.original_gap_days is not None:
    #                     gap_map[act.id] = act.original_gap_days
    #                 else:
    #                     if act.scheduled_date and prev.scheduled_date:
    #                         gap_map[act.id] = (act.scheduled_date - prev.scheduled_date).days
    #                     else:
    #                         gap_map[act.id] = 0

    #         # ── Log BEFORE deleting ───────────────────────────────────────────────
    #         AllocationAuditLog.objects.create(
    #             action            = 'deleted',
    #             allocation_id     = allocation.id,
    #             job_activity_id   = job_activity.id,
    #             job_id            = job_activity.job.job_id,
    #             mukkadam_id       = allocation.mukkadam.mukkadam_id,
    #             mukkadam_name     = allocation.mukkadam.mukkadam_name,
    #             farmer_name       = job_activity.job.farmer.farmer_name,
    #             activity_name     = job_activity.activity.name,
    #             allocated_date    = allocation.allocated_date,
    #             allocated_area    = allocation.allocated_area,
    #             allocated_workers = allocation.allocated_workers,
    #             snapshot          = {
    #                 'allocated_area':    str(allocation.allocated_area),
    #                 'allocated_workers': allocation.allocated_workers,
    #                 'allocated_date':    str(allocation.allocated_date),
    #                 'mukkadam_rate':     str(allocation.mukkadam_rate),
    #                 'farmer_rate':       str(allocation.farmer_rate),
    #                 'work_status':       allocation.work_status,
    #                 'payment_status':    allocation.payment_status,
    #                 'notes':             allocation.notes,
    #             },
    #             changed_by = request.user if request.user.is_authenticated else None,
    #             notes      = (
    #                 f"Deleted via dashboard — restored {allocation.allocated_area}ac "
    #                 f"to activity #{job_activity.id}"
    #             ),
    #         )

    #         # ── Build payload before delete ───────────────────────────────────────
    #         deleted_payload = {
    #             "allocation_id":         allocation.id,
    #             "booking_id":            job_activity.job.booking.booking_id if job_activity.job.booking else None,
    #             "api_activity_id":       job_activity.api_activity_id or None,
    #             "activity_name":         job_activity.activity.name,
    #             "allocated_area":        float(allocation.allocated_area),
    #             "allocated_date":        str(allocation.allocated_date),
    #             "mukkadam_id":           allocation.mukkadam.mukkadam_id,
    #             "mukkadam_name":         allocation.mukkadam.mukkadam_name,
    #             "farmer_rate":           float(allocation.farmer_rate),
    #             "mukkadam_rate":         float(allocation.mukkadam_rate),
    #             "job_id":                job_activity.job.job_id,
    #             "farmer_id":             job_activity.job.farmer.farmer_id,
    #             "farmer_name":           job_activity.job.farmer.farmer_name,
    #             "plot_id":               job_activity.plot.id if job_activity.plot else None,
    #             "plot_code":             job_activity.plot.plot_code if job_activity.plot else None,
    #             "last_modified_by_id":   allocation.last_modified_by.id if allocation.last_modified_by else None,
    #             "last_modified_by_name": allocation.last_modified_by.get_full_name() if allocation.last_modified_by else None,
    #             "deleted_by_id":         request.user.id if request.user.is_authenticated else None,
    #             "deleted_by_name":       request.user.get_full_name() or request.user.username if request.user.is_authenticated else None,
    #             "deleted_at":            str(timezone.now()),
    #         }

    #         # ── Delete the allocation ─────────────────────────────────────────────
    #         allocation.delete()

    #         # ── Fire signal (area + mukkadam availability restore happens here) ───
    #         from .signals import allocation_deleted
    #         allocation_deleted.send(sender=None, payload=deleted_payload)

    #         # ── Recalculate job_activity.allocated_area from remaining allocations ─
    #         # Do NOT hard-reset to 0 — other allocations may still exist on this activity.
    #         total_still_allocated = Allocation.objects.filter(
    #             job_activity=job_activity,
    #             status__in=['scheduled', 'in_progress', 'completed'],
    #         ).aggregate(total=Sum('allocated_area'))['total'] or Decimal('0')

    #         job_activity.allocated_area = total_still_allocated
    #         # remaining_area + allocation_status are auto-recalculated in save()
    #         job_activity.save()

    #         # ── Rule 6: Cascade downstream unallocated activities ────────────────
    #         #
    #         # Now that this allocation is deleted, we need to find the correct
    #         # fallback reference for downstream activities:
    #         #
    #         # Case E  (spec): Another allocated predecessor still exists →
    #         #                 reference = that predecessor's scheduled_date
    #         # Case E2 (spec): No allocated predecessor at all →
    #         #                 reference = job_activity.sales_date
    #         #                             or original_scheduled_date
    #         #                             (the original sales/calendar date)
    #         #
    #         # Then cascade each subsequent unallocated activity:
    #         #   new_date = reference_date + original_gap

    #         # Find fallback reference: nearest still-allocated predecessor
    #         # (after deletion, re-check by scanning predecessors in reverse)
    #         # fallback_reference = None
    #         # for pred in reversed(predecessors):
    #         #     # Re-fetch to get latest state (allocation may have changed above)
    #         #     pred_fresh = JobActivity.objects.get(id=pred.id)
    #         #     if pred_fresh.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
    #         #         fallback_reference = pred_fresh.scheduled_date
    #         #         break

    #         # # Also check if job_activity itself still has allocations (partial delete)
    #         # if total_still_allocated > Decimal('0'):
    #         #     # This activity is still (partially) allocated — it remains as reference
    #         #     fallback_reference = job_activity.scheduled_date

    #         # # Final fallback: original sales/calendar date (Rule 6 / E2)
    #         # if fallback_reference is None:
    #         #     fallback_reference = (
    #         #         job_activity.sales_date
    #         #         or job_activity.original_scheduled_date
    #         #         or job_activity.scheduled_date
    #         #     )

    #         #           # ── Rule 6: Cascade only if activity became fully unallocated ────────
    #         # cascade_shifted  = []
    #         # cascade_warnings = []

    #         # # Only cascade if this activity went from allocated → fully unallocated
    #         # if total_still_allocated <= Decimal('0') and job_activity.scheduled_date != job_activity.original_scheduled_date:
    #         #     # Revert this activity to its original date
    #         #     old_date = job_activity.scheduled_date
    #         #     original_date = (
    #         #         job_activity.original_scheduled_date
    #         #         or job_activity.sales_date
    #         #         or job_activity.scheduled_date
    #         #     )
    #         #     shift_days = (original_date - old_date).days

    #         #     if shift_days != 0:
    #         #         job_activity.scheduled_date = original_date
    #         #         job_activity.save(update_fields=['scheduled_date'])

    #         #         # Shift all subsequent unallocated activities by the same amount
    #         #         for succ in successors:
    #         #             if succ.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
    #         #                 cascade_warnings.append({
    #         #                     'activity_id':   succ.id,
    #         #                     'activity_name': succ.activity.name,
    #         #                     'old_date':      str(succ.scheduled_date),
    #         #                     'new_date':      str(succ.scheduled_date),
    #         #                     'message':       f'Skipped — already {succ.allocation_status}.',
    #         #                 })
    #         #                 continue

    #         #             if succ.is_manually_moved:
    #         #                 cascade_warnings.append({
    #         #                     'activity_id':   succ.id,
    #         #                     'activity_name': succ.activity.name,
    #         #                     'old_date':      str(succ.scheduled_date),
    #         #                     'new_date':      str(succ.scheduled_date),
    #         #                     'message':       'Skipped — manually moved',
    #         #                 })
    #         #                 continue

    #         #             if not succ.total_area or succ.total_area <= 0:
    #         #                 cascade_warnings.append({
    #         #                     'activity_id':   succ.id,
    #         #                     'activity_name': succ.activity.name,
    #         #                     'old_date':      str(succ.scheduled_date),
    #         #                     'new_date':      str(succ.scheduled_date),
    #         #                     'message':       'Skipped — zero area',
    #         #                 })
    #         #                 continue

    #         #             # Simple shift by same days
    #         #             succ_old = succ.scheduled_date
    #         #             succ.scheduled_date = succ_old + timedelta(days=shift_days)
    #         #             succ.move_reason = (
    #         #                 f'Cascade from deletion of allocation on '
    #         #                 f'{job_activity.activity.name} (activity #{job_activity.id})'
    #         #             )
    #         #             if request.user and request.user.is_authenticated:
    #         #                 succ.last_moved_by = request.user
    #         #                 succ.last_moved_at = timezone.now()
    #         #             succ.save(update_fields=[
    #         #                 'scheduled_date', 'move_reason',
    #         #                 'last_moved_by', 'last_moved_at',
    #         #             ])

    #         #             cascade_shifted.append({
    #         #                 'activity_id':   succ.id,
    #         #                 'activity_name': succ.activity.name,
    #         #                 'old_date':      str(succ_old),
    #         #                 'new_date':      str(succ.scheduled_date),
    #         #                 'shift_days':    shift_days,
    #         #             })

    #     return Response(
    #         {
    #             'success':  True,
    #             'message':  'Allocation deleted',
    #         },
    #         status=status.HTTP_200_OK,
    #     )



from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Cluster
from .ervices.potential import compute_cluster_potential
@api_view(["GET"])
def cluster_potential_jobs(request, cluster_id: int):
    cluster = Cluster.objects.get(id=cluster_id)
    potential_map = compute_cluster_potential(cluster)
    
    out = {}
    for date_str, items in potential_map.items():
        out[date_str] = [
            {
                "date": p.date,
                "activityId": p.activity_id,
                "activityName": p.activity_name,
                "status": p.status, 
                "cropName": p.crop_name,
                "variety": p.variety,
                "unbookedArea": p.area,
                "clusterRate": p.cluster_rate,
                "potentialRevenue": p.potential_revenue,
                "farmerId": p.farmer_id,
                "farmerName": p.farmer_name,
                "plotId": p.plot_id,
                "plotName": p.plot_name,
                "jobId": p.job_id,
            }
            for p in items
        ]
    return Response(out)

# tender/views.py — ADD THESE

@api_view(['GET'])
@permission_classes([AllowAny])
def search_farmers_for_cluster(request, cluster_id):
    """
    Search farmers with their plots + cluster membership info.
    GET /api/clusters/<id>/search_farmers/?q=hemant
    """
    q = request.query_params.get('q', '').strip()
    
    farmers_qs = Farmer.objects.prefetch_related(
        'clusters',
        Prefetch('plots', queryset=Plot.objects.prefetch_related('clusters'))
    )
    if q:
        farmers_qs = farmers_qs.filter(
            Q(farmer_name__icontains=q) |
            Q(farmer_id__icontains=q) |
            Q(phone_number__icontains=q)
        )
    
    farmers_qs = farmers_qs[:20]
    
    result = []
    for farmer in farmers_qs:
        farmer_clusters = list(farmer.clusters.all())
        plots_data = []
        for plot in farmer.plots.all():
            plot_clusters = list(plot.clusters.all())
            in_this_cluster = any(pc.id == cluster_id for pc in plot_clusters)
            plots_data.append({
                'plot_id': plot.id,
                'plot_code': plot.plot_code,
                'name': plot.name,
                'area_acres': float(plot.area_acres),
                'crop_name': plot.crop_name,
                'in_this_cluster': in_this_cluster,
                'other_clusters': [
                    {'id': pc.id, 'name': pc.name}
                    for pc in plot_clusters if pc.id != cluster_id
                ],
            })
        
        result.append({
            'farmer_id': farmer.farmer_id,
            'farmer_name': farmer.farmer_name,
            'phone_number': farmer.phone_number,
            'location': farmer.location,
            'in_this_cluster': any(fc.id == cluster_id for fc in farmer_clusters),
            'other_clusters': [
                {'id': fc.id, 'name': fc.name}
                for fc in farmer_clusters if fc.id != cluster_id
            ],
            'plots': plots_data,
        })
    
    return Response(result)

from datetime import timedelta
from datetime import timedelta

def get_activity_gap_days(activity: ActivityCatalog, cluster: Cluster | None) -> int:
    # 1) Cluster-specific override
    if cluster is not None:
        override = ClusterActivityScheduleRule.objects.filter(
            cluster=cluster,
            activity=activity,
        ).first()
        if override:
            return override.gap_days

    # 2) Global default
    global_rule = ActivityScheduleRule.objects.filter(
        activity=activity
    ).first()
    if global_rule:
        return global_rule.gap_days

    # 3) Fallback (do not shift)
    return 0
from datetime import timedelta

def get_pruning_base_date(job: Job, plot: Plot | None):
    """
    For this job/plot, find pruning JobActivity and use its scheduled_date as base.
    Adjust PRUNING_ACTIVITY_NAME to match your catalog.
    """
    PRUNING_ACTIVITY_NAME = "Pruning (छाटणी)"  # <- change if needed

    pruning_act = ActivityCatalog.objects.filter(
        name=PRUNING_ACTIVITY_NAME
    ).first()
    if not pruning_act:
        return None

    qs = JobActivity.objects.filter(
        job=job,
        plot=plot,
        activity=pruning_act,
        scheduled_date__isnull=False,
    ).order_by("scheduled_date")

    pruning_ja = qs.first()
    return pruning_ja.scheduled_date if pruning_ja else None


def adjust_job_activities_for_cluster(job: Job, cluster: Cluster):
    """
    Called when job is newly attached to cluster.
    For each JobActivity:
      - Base date = pruning.scheduled_date for that job+plot
      - scheduled_date = pruning_date + gap_days (cluster/global)
    """

    # cache pruning base per plot
    base_date_cache: dict[int | None, date | None] = {}

    for ja in job.activities.all():
        plot = ja.plot  # may be None
        plot_key = plot.id if plot else None

        if plot_key not in base_date_cache:
            base_date_cache[plot_key] = get_pruning_base_date(job, plot)

        pruning_date = base_date_cache[plot_key]
        if not pruning_date:
            # no pruning base for this job/plot
            continue

        gap_days = get_activity_gap_days(ja.activity, cluster)
        if gap_days == 0:
            continue  # no rule -> keep as is

        new_date = pruning_date + timedelta(days=gap_days)
        if ja.scheduled_date == new_date:
            continue  # already correct

        ja.scheduled_date = new_date
        ja.save(update_fields=["scheduled_date"])

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone



from rest_framework.decorators import action
from rest_framework.response   import Response
from rest_framework            import status, viewsets
from rest_framework.views      import APIView
from django.contrib.auth.models import User
from .models    import JobNote, Job
from .serializers import JobNoteSerializer, NoteAuthorSerializer


class JobNoteViewSet(viewsets.ModelViewSet):
    """
    CRUD for notes on a job.

    GET  /api/job-notes/?date=YYYY-MM-DD&cluster_id=X
         → all notes for jobs scheduled on that date in that cluster
         → sorted: unresolved first, then resolved; within each group newest first

    POST /api/job-notes/
         body: { job_id, text, tags, mention_ids, note_date }

    POST /api/job-notes/{id}/resolve/
         body: { resolution_note }
    """
    serializer_class = JobNoteSerializer

    def get_queryset(self):
        qs = JobNote.objects.select_related('author', 'resolved_by') \
                            .prefetch_related('mentions')

        date            = self.request.query_params.get('date')
        cluster_id      = self.request.query_params.get('cluster_id')
        job_ids         = self.request.query_params.getlist('job_id')
        job_activity_id = self.request.query_params.get('job_activity_id')  # ← NEW

        if date:
            qs = qs.filter(note_date=date)
        if cluster_id:
            qs = qs.filter(job__clusters__id=cluster_id)
        if job_ids:
            qs = qs.filter(job_id__in=job_ids)
        if job_activity_id:  # ← NEW
            qs = qs.filter(job_activity_id=job_activity_id)

        from django.db.models import Case, When, IntegerField
        qs = qs.annotate(
            sort_order=Case(
                When(is_resolved=False, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('sort_order', '-created_at')

        return qs
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        note            = self.get_object()
        resolution_note = request.data.get('resolution_note', '')
        if not resolution_note.strip():
            return Response(
                {'error': 'resolution_note is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        note.resolve(user=request.user, resolution_note=resolution_note)
        return Response(JobNoteSerializer(note).data)

    @action(detail=True, methods=['post'], url_path='unresolve')
    def unresolve(self, request, pk=None):
        note = self.get_object()
        note.is_resolved     = False
        note.resolved_by     = None
        note.resolved_at     = None
        note.resolution_note = ''
        note.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at',
                                 'resolution_note', 'updated_at'])
        return Response(JobNoteSerializer(note).data)


class UserSearchView(APIView):
    """
    GET /api/users/search/?q=john
    → returns app users matching the query (for @mention autocomplete)
    """
    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 1:
            return Response([])
        users = User.objects.filter(
            models.Q(username__icontains=q) |
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q)
        ).exclude(id=request.user.id)[:10]
        return Response(NoteAuthorSerializer(users, many=True).data)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_farmer_plots_to_cluster(request, cluster_id):
    ctx(flow="add_farmer_plots_to_cluster",
        cluster_id=str(cluster_id),
        user=str(request.user.id if request.user.is_authenticated else "anon"))
    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        ops("add_farmer_plots_cluster_not_found", cluster_id=str(cluster_id))
        return Response({'error': 'Cluster not found'}, status=404)

    farmer_id = request.data.get('farmer_id')
    plot_ids = request.data.get('plot_ids', [])

    if not farmer_id:
        return Response({'error': 'farmer_id is required'}, status=400)
    if not isinstance(plot_ids, list) or not plot_ids:
        return Response({'error': 'plot_ids must be a non-empty list'}, status=400)

    try:
        farmer = Farmer.objects.get(farmer_id=farmer_id)
    except Farmer.DoesNotExist:
        ops("add_farmer_plots_farmer_not_found",
        cluster_id=str(cluster_id), farmer_id=str(farmer_id))
        return Response({'error': 'Farmer not found'}, status=404)

    with transaction.atomic():
        # Link farmer to cluster + audit
        farmer.clusters.add(cluster)
        if hasattr(farmer, 'last_cluster_modified_by'):
            farmer.last_cluster_modified_by = request.user
            farmer.save(update_fields=['last_cluster_modified_by'])

        added_plots = []
        jobs_fixed = 0

        # Use a set of job_ids (string PK) to avoid duplicates
        jobs_to_fix_ids = set()

        for plot_id in plot_ids:
            try:
                plot = Plot.objects.get(id=plot_id, farmer=farmer)
            except Plot.DoesNotExist:
                continue

            plot.clusters.add(cluster)
            added_plots.append(plot.name)

            if hasattr(plot, 'last_cluster_modified_by'):
                plot.last_cluster_modified_by = request.user
                plot.last_cluster_modified_at = timezone.now()
                plot.save(update_fields=['last_cluster_modified_by', 'last_cluster_modified_at'])

            for job in Job.objects.filter(plot=plot):
                jobs_to_fix_ids.add(job.job_id)  # 👈 use job.job_id, not job.id

        # Now process each unique job once
        for job_pk in jobs_to_fix_ids:
            job = Job.objects.get(pk=job_pk)  # pk == job_id
            job.clusters.add(cluster)
            adjust_job_activities_for_cluster(job, cluster)
            ops("job_activities_adjusted_for_cluster",    # ADD
    job_id=str(job_pk),
    cluster_id=str(cluster_id))
            jobs_fixed += 1
    ops("farmer_plots_added_to_cluster",
    cluster_id=str(cluster_id),
    cluster_name=cluster.name,
    farmer_id=str(farmer_id),
    farmer_name=farmer.farmer_name,
    plots_added=len(added_plots),
    jobs_fixed=jobs_fixed,
    by=str(request.user.id))
    return Response({
        'success': True,
        'farmer_name': farmer.farmer_name,
        'cluster_name': cluster.name,
        'plots_added': added_plots,
        'jobs_fixed': jobs_fixed,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def search_mukkadams_for_cluster(request, cluster_id):
    q = request.query_params.get('q', '').strip()
    
    mukkadams_qs = Mukkadam.objects.prefetch_related(
        'clusters',
        'activity_rates__activity'  # ✅ prefetch rates
    )
    if q:
        mukkadams_qs = mukkadams_qs.filter(
            Q(mukkadam_name__icontains=q) |
            Q(mobile_numbers__icontains=q)
        )
    
    mukkadams_qs = mukkadams_qs[:20]
    
    result = []
    for m in mukkadams_qs:
        m_clusters = list(m.clusters.all())

        # ✅ Use activity_rates (has real ID) instead of tender_activities JSON
        activities = [
            {
                'id': rate.id,
                'name': rate.activity.name,
                'price': float(rate.rate_per_acre or 0),
                'productivity': float(rate.productivity_per_worker or 0.15),
            }
            for rate in m.activity_rates.all()
        ]

        result.append({
            'id': m.mukkadam_id,
            'name': m.mukkadam_name,
            'mobile': m.mobile_numbers,
            'crew_size': m.crew_size,
            'max_crew_capacity': m.max_crew_capacity,
            'village': m.village,
            'district': m.district,
            'activities': activities,
            'in_this_cluster': any(mc.id == cluster_id for mc in m_clusters),
            'other_clusters': [
                {'id': mc.id, 'name': mc.name}
                for mc in m_clusters if mc.id != cluster_id
            ],
        })
    
    return Response(result)


@api_view(['POST'])
@permission_classes([AllowAny])
def add_mukkadam_to_cluster(request, cluster_id):
    ctx(flow="add_mukkadam_to_cluster",
        cluster_id=str(cluster_id),
        mukkadam_id=str(request.data.get('mukkadam_id', '')))
    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        ops("add_mukkadam_cluster_not_found", cluster_id=str(cluster_id))
        return Response({'error': 'Cluster not found'}, status=404)

    mukkadam_id       = request.data.get('mukkadam_id')
    transport_price   = request.data.get('transport_price')
    weekly_payment_day = request.data.get('weekly_payment_day')
    advance_amount    = request.data.get('advance_amount')
    weekly_amount     = request.data.get('weekly_amount')

    # ── Updown fields ──
    mukkadam_type         = request.data.get('mukkadam_type', 'permanent')
    updown_mode           = request.data.get('updown_mode')          # 'range' | 'specific'
    updown_from_date      = request.data.get('updown_from_date')     # "YYYY-MM-DD"
    updown_to_date        = request.data.get('updown_to_date')       # "YYYY-MM-DD"
    updown_specific_dates = request.data.get('updown_specific_dates', [])  # ["YYYY-MM-DD", ...]

    if not mukkadam_id:
        return Response({'error': 'mukkadam_id required'}, status=400)
    if transport_price is None:
        return Response({'error': 'transport_price is required'}, status=400)

    # Validate updown fields
    if mukkadam_type == 'updown':
        if not updown_mode:
            return Response({'error': 'updown_mode required for updown type'}, status=400)
        if updown_mode == 'range':
            if not updown_from_date or not updown_to_date:
                return Response({'error': 'updown_from_date and updown_to_date required for range mode'}, status=400)
        elif updown_mode == 'specific':
            if not updown_specific_dates:
                return Response({'error': 'updown_specific_dates required for specific mode'}, status=400)

    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except Mukkadam.DoesNotExist:
        ops("add_mukkadam_not_found",
        cluster_id=str(cluster_id), mukkadam_id=str(mukkadam_id))
        return Response({'error': 'Mukkadam not found'}, status=404)

    # Permanent mukkadams can only be in a cluster once
    if mukkadam_type == 'permanent':
        if ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam, cluster=cluster, is_active=True, mukkadam_type='permanent'
        ).exists():
            ops("add_mukkadam_blocked_duplicate",
        cluster_id=str(cluster_id),
        mukkadam_id=str(mukkadam_id),
        reason="already_permanent")
            return Response({'error': 'Mukkadam is already permanently assigned to this cluster'}, status=400)

    # Updown mukkadams — check date overlap to prevent duplicate periods
    if mukkadam_type == 'updown':
        existing = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam, cluster=cluster, is_active=True, mukkadam_type='updown'
        )
        if updown_mode == 'range' and updown_from_date and updown_to_date:
            # Check if any existing updown assignment overlaps with new dates
            for ex in existing:
                if ex.updown_mode == 'range' and ex.updown_from_date and ex.updown_to_date:
                    # Overlap check
                    if not (updown_to_date < str(ex.updown_from_date) or updown_from_date > str(ex.updown_to_date)):
                        return Response({
                            'error': f'Overlapping updown period already exists ({ex.updown_from_date} → {ex.updown_to_date})'
                        }, status=400)
        if updown_mode == 'specific' and updown_specific_dates:
            for ex in existing:
                if ex.updown_mode == 'specific':
                    overlap = set(updown_specific_dates) & set(ex.updown_specific_dates or [])
                    if overlap:
                        ops("add_mukkadam_blocked_overlap",
    cluster_id=str(cluster_id),
    mukkadam_id=str(mukkadam_id),
    reason="updown_overlap",
    mode=updown_mode)
                        return Response({
                            'error': f'Overlapping dates already exist: {", ".join(sorted(overlap))}'
                        }, status=400)
    if weekly_payment_day is not None and weekly_payment_day not in range(7):
        return Response({'error': 'weekly_payment_day must be 0–6'}, status=400)

    assignment = ClusterMukkadamAssignment.objects.create(
        mukkadam=mukkadam,
        cluster=cluster,
        transport_price=transport_price,
        weekly_payment_day=weekly_payment_day,
        is_active=True,
        mukkadam_type=mukkadam_type,
        updown_mode=updown_mode if mukkadam_type == 'updown' else None,
        updown_from_date=updown_from_date if mukkadam_type == 'updown' and updown_mode == 'range' else None,
        updown_to_date=updown_to_date if mukkadam_type == 'updown' and updown_mode == 'range' else None,
        updown_specific_dates=updown_specific_dates if mukkadam_type == 'updown' and updown_mode == 'specific' else [],

        created_by=request.user if request.user.is_authenticated else None,
        last_modified_by=request.user if request.user.is_authenticated else None,
    
    )
    ops("mukkadam_added_to_cluster",
    cluster_id=str(cluster_id),
    cluster_name=cluster.name,
    mukkadam_id=str(mukkadam_id),
    mukkadam_name=mukkadam.mukkadam_name,
    mukkadam_type=mukkadam_type,
    transport_price=str(transport_price),
    updown_mode=str(updown_mode or ""))

    if advance_amount is not None:
        assignment.advance_amount = Decimal(str(advance_amount))
    if weekly_amount is not None:
        assignment.weekly_amount = Decimal(str(weekly_amount)) 
    if advance_amount is not None or weekly_amount is not None:
        assignment.save()

    day_name = (
        dict(ClusterMukkadamAssignment.WEEKDAY_CHOICES)[weekly_payment_day]
        if weekly_payment_day is not None else None
    )

    return Response({
        'success': True,
        'mukkadam_name': mukkadam.mukkadam_name,
        'cluster_name': cluster.name,
        'mukkadam_type': mukkadam_type,
        'message': (
            f'{mukkadam.mukkadam_name} added to {cluster.name} as {mukkadam_type}.'
        )
    }, status=201)


# tender/views.py - ADD THIS
# models.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Prefetch, Sum
@api_view(['GET'])
@permission_classes([AllowAny])
def tender_dashboard(request):
    from datetime import date, timedelta

    cluster_id     = request.query_params.get('cluster_id')
    cluster_id_int = int(cluster_id) if cluster_id else None
    selected_date  = request.query_params.get('date')

    # ── NEW: Activity-based filters ──────────────────────────────────
    activity_filters = request.query_params.getlist('activity_filters')

    ctx(flow="tender_dashboard",
        cluster_id=str(cluster_id or "all"),
        date=str(selected_date or "today"),
        filters=str(activity_filters))
    # Possible values: completed, in_progress, due_today, due_tomorrow, 
    #                  overdue_3plus, overdue_4_6, overdue_7_10

    # ============ MUKKADAMS ============
    mukkadams_qs = Mukkadam.objects.all().prefetch_related(
        'clusters',
        'cluster_assignments__cluster',
        Prefetch(
            'activity_rates',
            queryset=MukkadamActivityRate.objects.filter(
                is_active=True
            ).select_related('activity'),
            to_attr='prefetched_rates'
        )
    )

    if cluster_id_int:
        mukkadams_qs = mukkadams_qs.filter(
            cluster_assignments__cluster_id=cluster_id_int,
            cluster_assignments__is_active=True,
        ).distinct()

    # ── Batch allocation check — ONE query for all mukkadams ──────────
    allocated_mukkadam_ids = set()
    if selected_date:
        allocated_mukkadam_ids = set(
            Allocation.objects.filter(
                allocated_date=selected_date,
                mukkadam__in=mukkadams_qs,
            ).values_list('mukkadam_id', flat=True).distinct()
        )

    # ── Batch last allocation per mukkadam — ONE query ────────────────
    from django.db.models import Max

    last_alloc_ids = (
        Allocation.objects.filter(mukkadam__in=mukkadams_qs)
        .values('mukkadam_id')
        .annotate(last_id=Max('id'))
        .values_list('last_id', flat=True)
    )

    last_allocs = Allocation.objects.filter(
        id__in=last_alloc_ids
    ).select_related(
        'mukkadam',
        'job_activity__plot',
        'job_activity__job__farmer',
        'cluster',
    )

    last_alloc_map: dict = {a.mukkadam_id: a for a in last_allocs}

    # ── Batch TODAY's job per mukkadam (if selected_date is today) ────────
    today_alloc_map: dict = {}
    from datetime import date as _date
    _today_str = str(_date.today())
    _lookup_date = selected_date if selected_date else _today_str
    today_allocs = Allocation.objects.filter(
        mukkadam__in=mukkadams_qs,
        allocated_date=_lookup_date,
    ).select_related(
        'mukkadam',
        'job_activity__activity',
        'job_activity__plot',
        'job_activity__job__farmer',
        'cluster',
    ).order_by('mukkadam_id', '-id')

    for ta in today_allocs:
        mid = ta.mukkadam_id
        if mid not in today_alloc_map:   # keep first (latest) per mukkadam
            today_alloc_map[mid] = ta

    mukkadams_data = []
    for m in mukkadams_qs:
        rates = m.prefetched_rates

        activity_rates = [
            {
                'rate_id':                  rate.id,
                'activity_id':              rate.activity.id,
                'activity_name':            rate.activity.name,
                'rate_per_acre':            float(rate.rate_per_acre),
                'productivity_per_worker':  float(rate.productivity_per_worker),
                'is_active':                rate.is_active,
            }
            for rate in rates
        ]

        total_price = 0
        try:
            total_price = float((m.tender_activities or {}).get('total_price', 0) or 0)
        except (ValueError, TypeError):
            pass

        active_assignments = m.cluster_assignments.filter(is_active=True).select_related('cluster')

        clusters_list = []
        for a in active_assignments:
            if cluster_id_int and a.cluster.id != cluster_id_int:
                continue
            clusters_list.append({
                'id':                   a.cluster.id,
                'name':                 a.cluster.name,
                'mukkadam_type':        a.mukkadam_type,
                'updown_mode':          a.updown_mode,
                'updown_from_date':     str(a.updown_from_date) if a.updown_from_date else None,
                'updown_to_date':       str(a.updown_to_date) if a.updown_to_date else None,
                'updown_specific_dates': a.updown_specific_dates or [],
                'transport_price':      float(a.transport_price),
                'advance_amount':       float(a.advance_amount),
                'weekly_payment_day':   a.weekly_payment_day,
                'weekly_amount':        float(a.weekly_amount),
            })

        primary_assignment = next(
            (a for a in active_assignments if cluster_id_int and a.cluster.id == cluster_id_int),
            active_assignments.first() if active_assignments else None
        )

        # ── Status resolution ──────────────────────────────────────────
        allocated_on_date = m.mukkadam_id in allocated_mukkadam_ids
        resolved_status   = (
            m.manual_status if m.manual_status in ('on_hold', 'inactive')
            else 'active' if allocated_on_date
            else 'idle'
        )

        # ── Last allocation location ──────────────────────────────────────
        last_alloc   = last_alloc_map.get(m.mukkadam_id)
        last_location = None
        if last_alloc:
            plot   = last_alloc.job_activity.plot   if last_alloc.job_activity else None
            farmer = last_alloc.job_activity.job.farmer if (last_alloc.job_activity and last_alloc.job_activity.job) else None
            # activity from job_activity relation
            last_act = last_alloc.job_activity.activity if last_alloc.job_activity and hasattr(last_alloc.job_activity, 'activity') else None
            last_location = {
                'date':           str(last_alloc.allocated_date) if last_alloc.allocated_date else None,
                'farmer_name':    farmer.farmer_name if farmer else None,
                # Farmer location from cluster (most accurate work location)
                'farmer_village':  last_alloc.cluster.village  if last_alloc.cluster else None,
                'farmer_taluka':   last_alloc.cluster.taluka   if last_alloc.cluster else None,
                'farmer_district': last_alloc.cluster.district if last_alloc.cluster else None,
                'plot_name':      plot.name       if plot else None,
                'plot_code':      plot.plot_code  if plot else None,
                'cluster_name':   last_alloc.cluster.name if last_alloc.cluster else None,
                'village':        getattr(plot, 'village', None) if plot else None,
                'taluka':         getattr(plot, 'taluka',  None) if plot else None,
                'activity_name':  last_act.name if last_act else None,  # NEW
            }

        # ── Build today_job ───────────────────────────────────────────────
        today_alloc = today_alloc_map.get(m.mukkadam_id)
        today_job = None
        if today_alloc:
            ta_ja     = today_alloc.job_activity
            ta_plot   = ta_ja.plot   if ta_ja else None
            ta_farmer = ta_ja.job.farmer if (ta_ja and ta_ja.job) else None
            ta_act    = ta_ja.activity   if ta_ja and hasattr(ta_ja, 'activity') else None
            today_job = {
                'date':             str(today_alloc.allocated_date),
                'farmer_name':      ta_farmer.farmer_name if ta_farmer else None,
                'farmer_village':   today_alloc.cluster.village  if today_alloc.cluster else None,
                'farmer_taluka':    today_alloc.cluster.taluka   if today_alloc.cluster else None,
                'farmer_district':  today_alloc.cluster.district if today_alloc.cluster else None,
                'plot_code':        ta_plot.plot_code if ta_plot else None,
                'cluster_name':     today_alloc.cluster.name if today_alloc.cluster else None,
                'activity_name':    ta_act.name if ta_act else None,
            }

        mukkadams_data.append({
            'id':               m.mukkadam_id,
            'name':             m.mukkadam_name,
            'mobile':           m.mobile_numbers,
            'crew_size':        m.crew_size,
            'last_location':    last_location,
            'today_job':        today_job,  # NEW
            'max_crew_capacity': m.max_crew_capacity,
            'location': {
                'state':    m.state,
                'district': m.district,
                'taluka':   m.taluka,
                'village':  m.village,
            },
            'availability': {
                'start_date': str(m.start_date) if m.start_date else None,
                'end_date':   str(m.end_date)   if m.end_date   else None,
            },
            'activities':          activity_rates,
            'total_price':         total_price,
            'reference_image_url': (m.tender_activities or {}).get('reference_image_url', ''),
            'efficiency':          float(m.efficiency),
            'clusters':            clusters_list,

            # ── Cluster-scoped payment fields ──────────────────────────
            'weekly_amount':      float(primary_assignment.weekly_amount)    if primary_assignment else 0,
            'weekly_payment_day': primary_assignment.weekly_payment_day      if primary_assignment else None,
            'advance_amount':     float(primary_assignment.advance_amount)   if primary_assignment else 0,
            'transport_price':    float(primary_assignment.transport_price)  if primary_assignment else 0,

            # ── Status fields ──────────────────────────────────────────
            'manual_status':        m.manual_status,
            'manual_status_note':   m.manual_status_note,
            'manual_status_set_at': m.manual_status_set_at.isoformat() if m.manual_status_set_at else None,
            'manual_status_set_by': m.manual_status_set_by,
            'allocated_on_date':    allocated_on_date,
            'resolved_status':      resolved_status,
        })


    ops("tender_dashboard_mukkadams_built",
    cluster_id=str(cluster_id or "all"),
    count=len(mukkadams_data),
    date=str(selected_date or "today"))
    # ============ FARMERS ============
    farmers_qs = Farmer.objects.prefetch_related(
        'clusters',
        Prefetch(
            'plots',
            queryset=Plot.objects.prefetch_related('clusters')
        ),
        Prefetch(
            'jobs',
            queryset=Job.objects.filter(booking_type__in=['tender', 'ondemand']).prefetch_related(
                Prefetch(
                    'activities',
                    queryset=JobActivity.objects.select_related('activity', 'plot').prefetch_related(
                        Prefetch(
                            'allocations',
                            queryset=Allocation.objects.filter(
                                status__in=['scheduled', 'in_progress', 'completed']
                            ).select_related('mukkadam')
                        )
                    )
                ),
                'booking__payments'
            )
        )
    )

    if cluster_id:
        farmers_qs = farmers_qs.filter(clusters__id=cluster_id)

    # ── NEW: Apply activity filters ──────────────────────────────────
    if activity_filters:
        from django.db.models import Q
        today = date.today()
        
        filter_q = Q()
        
        for filter_type in activity_filters:
            if filter_type == 'completed':
                # Farmers with at least one completed activity
                filter_q |= Q(
                    jobs__activities__allocation_status='completed'
                )
            
            elif filter_type == 'in_progress':
                # Farmers with at least one activity that has in_progress allocations
                filter_q |= Q(
                    jobs__activities__allocations__work_status='in_progress'
                )
            
            elif filter_type == 'due_today':
                filter_q |= Q(
                    jobs__activities__scheduled_date=today
                )
            
            elif filter_type == 'due_tomorrow':
                filter_q |= Q(
                    jobs__activities__scheduled_date=today + timedelta(days=1)
                )
            
            elif filter_type == 'overdue_3plus':
                # 3 or more days overdue
                cutoff_date = today - timedelta(days=3)
                filter_q |= Q(
                    jobs__activities__scheduled_date__lte=cutoff_date,
                    jobs__activities__allocation_status__in=['not_allocated', 'partially_allocated']
                )
            
            elif filter_type == 'overdue_4_6':
                # 4-6 days overdue
                start_date = today - timedelta(days=6)
                end_date = today - timedelta(days=4)
                filter_q |= Q(
                    jobs__activities__scheduled_date__range=(start_date, end_date),
                    jobs__activities__allocation_status__in=['not_allocated', 'partially_allocated']
                )
            
            elif filter_type == 'overdue_7_10':
                # 7-10 days overdue
                start_date = today - timedelta(days=10)
                end_date = today - timedelta(days=7)
                filter_q |= Q(
                    jobs__activities__scheduled_date__range=(start_date, end_date),
                    jobs__activities__allocation_status__in=['not_allocated', 'partially_allocated']
                )
        
        if filter_q:
            farmers_qs = farmers_qs.filter(filter_q).distinct()

    farmers_data = []
    for farmer in farmers_qs:
        farmer_clusters = list(farmer.clusters.all())
        all_plots       = list(farmer.plots.all())
        all_jobs        = list(farmer.jobs.all())

        plots_by_cluster = {}
        for plot in all_plots:
            plot_clusters = list(plot.clusters.all())

            if plot_clusters:
                cluster_groups = [(str(pc.id), pc.id, pc.name) for pc in plot_clusters]
            else:
                cluster_groups = [('none', None, 'No Cluster')]

            plot_jobs = [
                j for j in all_jobs
                if j.plot_id == plot.id or
                any(a.plot_id == plot.id for a in j.activities.all())
            ]

            total_amount = sum(float(j.booking.total_amount) for j in plot_jobs if hasattr(j, 'booking'))
            advance_paid = sum(float(j.booking.advance_paid) for j in plot_jobs if hasattr(j, 'booking'))
            balance      = total_amount - advance_paid

            plot_entry = {
                'plot_id':   plot.id,
                'plot_code': plot.plot_code,
                'name':      plot.name,
                'area_acres': float(plot.area_acres),
                'crop_name': getattr(plot, 'crop_name', ''),
                'variety':   getattr(plot, 'variety', ''),
                'pruning_date': str(plot.pruning_date) if getattr(plot, 'pruning_date', None) else None,
                'jobs_count': len(plot_jobs),
                'payment_summary': {
                    'total_amount':  total_amount,
                    'advance_paid':  advance_paid,
                    'balance':       balance,
                    'is_fully_paid': balance <= 0,
                },
                'jobs': [
                    {
                        'job_id':        j.job_id,
                        'status':        j.status,
                        'priority':      j.priority,
                        'booking_type':  j.booking_type,   # ← ADD THIS
                        'scheduled_date':          str(j.scheduled_date) if j.scheduled_date else None,
                        'total_activities_amount': float(j.total_activities_amount),
                        'activities': [
                            {
                                'id':               a.id,
                                'name':             a.activity.name,
                                'total_area':       float(a.total_area),
                                'allocated_area':   float(a.allocated_area),
                                'remaining_area':   float(a.remaining_area),
                                'scheduled_date':   str(a.scheduled_date) if a.scheduled_date else None,
                                'total_price':      float(a.total_price),
                                'allocation_status': a.allocation_status,
                                # ✅ Include allocation details
                                'allocations': [
                                    {
                                        'allocation_id':    alloc.id,
                                        'allocated_date':   str(alloc.allocated_date),
                                        'allocated_area':   float(alloc.allocated_area),
                                        'mukkadam_name':    alloc.mukkadam.mukkadam_name,
                                        'mukkadam_id':      alloc.mukkadam.mukkadam_id,
                                        'work_status':      alloc.work_status,
                                        'farmer_amount':    float(alloc.farmer_amount),
                                    }
                                    for alloc in a.allocations.all()
                                ],
                            }
                            for a in j.activities.all()
                            if a.plot_id == plot.id
                        ],
                        'booking': {
                            'booking_id':  j.booking.booking_id,
                            'status':      j.booking.status,
                            'total_amount': float(j.booking.total_amount),
                            'advance_paid': float(j.booking.advance_paid),
                            'balance':      float(j.booking.balance),
                            'payments': [
                                {
                                    'payment_id':  p.payment_id,
                                    'amount':      float(p.amount),
                                    'mode':        p.mode,
                                    'paid_at':     str(p.paid_at),
                                    'paid_status': p.paid_status,
                                    'notes':       p.notes,
                                }
                                for p in j.booking.payments.all()
                            ]
                        } if hasattr(j, 'booking') else None,
                    }
                    for j in plot_jobs
                ]
            }

            for cluster_key, cluster_id_val, cluster_name in cluster_groups:
                if cluster_key not in plots_by_cluster:
                    plots_by_cluster[cluster_key] = {
                        'cluster_id':   cluster_id_val,
                        'cluster_name': cluster_name,
                        'plots':        []
                    }
                plots_by_cluster[cluster_key]['plots'].append(plot_entry)

        farmer_total   = sum(float(j.booking.total_amount) for j in all_jobs if hasattr(j, 'booking'))
        farmer_advance = sum(float(j.booking.advance_paid) for j in all_jobs if hasattr(j, 'booking'))

        farmers_data.append({
            'farmer_id':    farmer.farmer_id,
            'farmer_name':  farmer.farmer_name,
            'phone_number': farmer.phone_number,
            'location':     farmer.location,
            'clusters':     [{'id': c.id, 'name': c.name} for c in farmer_clusters],
            'total_plots':  len(all_plots),
            'total_jobs':   len(all_jobs),
            'payment_summary': {
                'total_amount': farmer_total,
                'advance_paid': farmer_advance,
                'balance':      farmer_total - farmer_advance,
            },
            'plots_by_cluster': list(plots_by_cluster.values()),
            'newest_job_date':  str(max((j.created_at for j in all_jobs), default=None)) if all_jobs else None,
        })

    ops("tender_dashboard_farmers_built",
    cluster_id=str(cluster_id or "all"),
    count=len(farmers_data),
    filters=str(activity_filters))
    # ============ SUMMARY STATS ============
    from django.db.models import Sum, Q

    activity_qs = JobActivity.objects.filter(
        job__booking_type__in=["tender", "ondemand"],
    is_lost=False,
    total_area__gt=0,

       
    )
    if cluster_id_int:
        activity_qs = activity_qs.filter(
            Q(plot__clusters__id=cluster_id_int) |
            Q(job__farmer__clusters__id=cluster_id_int)
        ).distinct()

    job_filter = {'booking_type': 'tender'}
    if cluster_id_int:
        job_filter['farmer__clusters__id'] = cluster_id_int
    jobs_qs = Job.objects.filter(**job_filter).distinct()

    booking_qs = JobBooking.objects.filter(job__booking_type='tender')
    if cluster_id_int:
        booking_qs = booking_qs.filter(
            Q(job__farmer__clusters__id=cluster_id_int) |
            Q(job__activities__plot__clusters__id=cluster_id_int)
        ).distinct()

    total_activities = activity_qs.values('job', 'plot', 'api_activity_id').distinct().count()
    total_plots      = activity_qs.values('plot').distinct().count()
    total_acres      = activity_qs.values('plot').distinct().aggregate(
                           total=Sum('plot__area_acres')
                       )['total'] or 0

    booking_stats        = booking_qs.aggregate(
                               total_booking_value=Sum('total_amount'),
                               total_advance_paid=Sum('advance_paid'),
                           )
    total_booking_value  = booking_stats['total_booking_value'] or 0
    total_advance_paid   = booking_stats['total_advance_paid']  or 0
    paid_count           = booking_qs.filter(status='PAID').count()
    partial_paid_count   = booking_qs.filter(status='PARTIALLY_PAID').count()


    ops("tender_dashboard_served",
    cluster_id=str(cluster_id or "all"),
    mukkadams=len(mukkadams_data),
    farmers=len(farmers_data),
    total_jobs=str(jobs_qs.count()),
    total_acres=str(float(total_acres)))

    return Response({
        'summary': {
            'total_mukkadams':     len(mukkadams_data),
            'total_farmers':       len(farmers_data),
            'total_tender_jobs':   jobs_qs.count(),
            'total_activities':    total_activities,
            'total_plots':         total_plots,
            'total_acres':         float(total_acres),
            'total_booking_value': float(total_booking_value),
            'total_advance_paid':  float(total_advance_paid),
            'total_balance':       float(total_booking_value - total_advance_paid),
            'paid_jobs':           paid_count,
            'partial_paid_jobs':   partial_paid_count,
        },
        'mukkadams': mukkadams_data,
        'farmers':   farmers_data,
    })




@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_payout_summary(request):
    """
    GET /api/mukkadam-payout-summary/
    
    Returns completed allocations grouped by mukkadam with full detail:
    - what work they did, for whom, when
    - who allocated it
    - amount to pay (allocated_area * mukkadam_rate)
    - payment status
    
    Query params:
      cluster_id  — filter by cluster
      date_from   — filter from date (allocated_date)
      date_to     — filter to date
      mukkadam_id — filter single mukkadam
    """
    cluster_id  = request.query_params.get('cluster_id')
    date_from   = request.query_params.get('date_from')
    date_to     = request.query_params.get('date_to')
    mukkadam_id = request.query_params.get('mukkadam_id')

    # ── Base queryset — only completed work ──────────────────────────────────
    allocs = Allocation.objects.filter(
        work_status='completed',
    ).select_related(
        'mukkadam',
        'cluster',
        'job_activity__activity',
        'job_activity__plot',
        'job_activity__job__farmer',
        'created_by__profile',
        'last_modified_by__profile',
    ).order_by('mukkadam_id', '-allocated_date')

    if cluster_id:
        allocs = allocs.filter(cluster_id=cluster_id)
    if date_from:
        allocs = allocs.filter(allocated_date__gte=date_from)
    if date_to:
        allocs = allocs.filter(allocated_date__lte=date_to)
    if mukkadam_id:
        allocs = allocs.filter(mukkadam_id=mukkadam_id)

    # ── Group by mukkadam ────────────────────────────────────────────────────
    mukkadam_map: dict = {}

    for al in allocs:
        mid = al.mukkadam_id
        if mid not in mukkadam_map:
            mukkadam_map[mid] = {
                'mukkadam_id':   al.mukkadam_id,
                'mukkadam_name': al.mukkadam.mukkadam_name,
                'mobile':        al.mukkadam.mobile_numbers,
                'total_area':    0,
                'total_payout':  0,
                'total_jobs':    0,
                'jobs': [],
            }

        ja      = al.job_activity
        act     = ja.activity  if ja else None
        plot    = ja.plot      if ja else None
        farmer  = ja.job.farmer if ja and ja.job else None

        area    = float(al.allocated_area  or 0)
        rate    = float(al.mukkadam_rate   or 0)
        amount  = area * rate

        # Who allocated this
        allocated_by = None
        if al.created_by:
            p = getattr(al.created_by, 'profile', None)
            allocated_by = (p.full_name if p and p.full_name else None) or al.created_by.get_full_name() or al.created_by.username

        mukkadam_map[mid]['total_area']   += area
        mukkadam_map[mid]['total_payout'] += amount
        mukkadam_map[mid]['total_jobs']   += 1

        # farmer_amount = area × farmer_rate (what farmer owes for this work)
        farmer_rate   = float(al.farmer_rate or 0)
        farmer_amount = round(area * farmer_rate, 2)

        mukkadam_map[mid]['jobs'].append({
            'allocation_id':   al.id,
            'allocated_date':  str(al.allocated_date),
            'sales_date':      str(ja.sales_date) if ja and ja.sales_date else None,
            'job_id':          ja.job.job_id      if ja and ja.job  else None,
            'farmer_id':       str(farmer.farmer_id) if farmer       else None,   # NEW
            'farmer_name':     farmer.farmer_name if farmer          else None,
            'farmer_phone':    farmer.phone_number if farmer         else None,
            'activity_name':   act.name            if act            else None,
            'plot_name':       plot.name           if plot           else None,
            'plot_code':       plot.plot_code      if plot           else None,
            'cluster_name':    al.cluster.name     if al.cluster     else None,
            'area':            area,
            'rate':            rate,
            'amount':          round(amount, 2),
            'farmer_amount':   farmer_amount,                                      # NEW
            'payment_status':  al.payment_status,
            'work_status':     al.work_status,
            'actual_area_done': float(al.actual_area_done) if al.actual_area_done else None,
            'actual_crew_size': al.actual_crew_size,
            'report_submitted': al.report_submitted,
            'farmer_agreed':   al.farmer_agreed,
            'allocated_by':    allocated_by,
            'allocated_by_id': al.created_by_id,
            'notes':           al.notes or '',
        })

    # ── Totals ───────────────────────────────────────────────────────────────
    result = list(mukkadam_map.values())
    for m in result:
        m['total_area']   = round(m['total_area'],   2)
        m['total_payout'] = round(m['total_payout'], 2)

    result.sort(key=lambda x: x['total_payout'], reverse=True)

    total_area    = round(sum(m['total_area']   for m in result), 2)
    total_payout  = round(sum(m['total_payout'] for m in result), 2)
    total_jobs    = sum(m['total_jobs'] for m in result)

    return Response({
        'summary': {
            'total_mukkadams': len(result),
            'total_jobs':      total_jobs,
            'total_area':      total_area,
            'total_payout':    total_payout,
        },
        'mukkadams': result,
    })
# views.py
from .ervices.settlement import is_settlement_triggered,create_or_update_settlement

from django.utils import timezone



@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_settlement_detail(request, mukkadam_id, job_id):
    """
    GET /api/mukkadam/<id>/settlement/<job_id>/
    Returns full breakdown for frontend display.
    """
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        job = Job.objects.get(job_id=job_id)
    except (Mukkadam.DoesNotExist, Job.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if not is_settlement_triggered(job):
        return Response({'triggered': False, 'message': 'Shoot selection not yet completed'})

    settlement = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam, job=job
    ).first()

    if not settlement:
        cluster = job.clusters.first()
        settlement = create_or_update_settlement(mukkadam, job, cluster)

    # Build activity breakdown
    today = timezone.localdate()
    allocations = Allocation.objects.filter(
        mukkadam=mukkadam,
        job_activity__job=job,
        job_activity__scheduled_date__lte=today,
    ).select_related('job_activity__activity', 'job_activity__plot')

    breakdown = []
    for a in allocations:
        breakdown.append({
            'activity_name': a.job_activity.activity.name,
            'plot_code': a.job_activity.plot.plot_code if a.job_activity.plot else '—',
            'scheduled_date': a.job_activity.scheduled_date,
            'allocated_area': float(a.allocated_area),
            'mukkadam_rate': float(a.mukkadam_rate),
            'gross_amount': float(a.mukkadam_amount),
        })

    weekly_applied = settlement.weekly_payments_applied.all().values(
        'payment_date', 'amount', 'crew_size_on_date'
    )

    return Response({
        'triggered': True,
        'mukkadam_name': mukkadam.mukkadam_name,
        'job_id': job.job_id,
        'farmer_name': job.farmer.farmer_name,
        'settlement_status': settlement.status,
        'breakdown': {
            'activities': breakdown,
            'gross_amount': float(settlement.gross_amount),
            'deposit_held_10pct': float(
                settlement.gross_amount * Decimal('10') / Decimal('100')
            ),
            'payable_90pct': float(settlement.payable_amount),
            'deposit_from_prev_job': float(settlement.deposit_carried_forward),
            'advance_deducted': float(settlement.advance_deducted),
            'weekly_payments': list(weekly_applied),
            'weekly_payments_total': float(settlement.weekly_payments_deducted),
            'net_payable': float(settlement.net_payable),
        },
        'show_raise_payment': settlement.net_payable > 0 and settlement.status == 'calculated',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def raise_mukkadam_payment(request, mukkadam_id, job_id):
    """
    POST /api/mukkadam/<id>/settlement/<job_id>/pay/
    Marks as paid in one click.
    """
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
        settlement = MukkadamJobSettlement.objects.get(
            mukkadam=mukkadam, job__job_id=job_id
        )
    except (Mukkadam.DoesNotExist, MukkadamJobSettlement.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    if settlement.net_payable <= 0:
        return Response({'error': 'No payment needed'}, status=400)

    if settlement.status == 'paid':
        return Response({'error': 'Already paid'}, status=400)

    with transaction.atomic():
        # Create MukkadamPayment record
        payment = MukkadamPayment.objects.create(
            mukkadam=mukkadam,
            payment_id=f"SETTLE-{job_id}-{mukkadam_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            amount=settlement.net_payable,
            mode='CASH',
            paid_at=timezone.now(),
            notes=f'Auto settlement for job {job_id}',
        )
        settlement.status = 'paid'
        settlement.paid_at = timezone.now()
        settlement.save(update_fields=['status', 'paid_at'])

    return Response({
        'success': True,
        'paid_amount': float(settlement.net_payable),
        'payment_id': payment.payment_id,
        'message': f'₹{settlement.net_payable} paid to {mukkadam.mukkadam_name}',
    })


# views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_all_settlements(request, mukkadam_id):
    try:
        mukkadam = Mukkadam.objects.get(pk=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    today = timezone.localdate()

    settlements = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam
    ).select_related(
        'job', 'job__farmer', 'cluster'
    ).prefetch_related(
        'weekly_payments_applied'
    ).order_by('-created_at')

    data = []
    for s in settlements:

        # ── Activity breakdown for this settlement ──
        allocations = Allocation.objects.filter(
            mukkadam=mukkadam,
            job_activity__job=s.job,
            job_activity__scheduled_date__lte=today,
        ).select_related(
            'job_activity__activity',
            'job_activity__plot',
        ).order_by('job_activity__scheduled_date')

        activity_rows = []
        for a in allocations:
            ja = a.job_activity
            activity_rows.append({
                'activity_name': ja.activity.name,
                'plot_code': ja.plot.plot_code if ja.plot else '—',
                'plot_name': ja.plot.name if ja.plot else '—',
                'scheduled_date': str(ja.scheduled_date) if ja.scheduled_date else '—',
                'allocated_area': float(a.allocated_area),
                'mukkadam_rate': float(a.mukkadam_rate),
                'gross_amount': float(a.mukkadam_amount),
                'allocation_status': a.status,
            })

        # ── Weekly payments breakdown ──
        weekly_rows = []
        for w in s.weekly_payments_applied.all().order_by('payment_date'):
            weekly_rows.append({
                'payment_date': str(w.payment_date),
                'amount': float(w.amount),
                'crew_size': w.crew_size_on_date,
            })

        deposit_held = round(float(s.gross_amount) * 0.10, 2)

        data.append({
            'job_id': s.job.job_id,
            'farmer_name': s.job.farmer.farmer_name,
            'farmer_id': s.job.farmer.farmer_id,
            'cluster_name': s.cluster.name if s.cluster else '—',
            'status': s.status,
            'calculated_at': s.calculated_at,
            'paid_at': s.paid_at,

            # Financials
            'gross_amount': float(s.gross_amount),
            'deposit_held_10pct': deposit_held,
            'payable_90pct': float(s.payable_amount),
            'deposit_carried_forward': float(s.deposit_carried_forward),
            'advance_deducted': float(s.advance_deducted),
            'weekly_payments_deducted': float(s.weekly_payments_deducted),
            'net_payable': float(s.net_payable),

            # Breakdowns
            'activity_breakdown': activity_rows,
            'weekly_breakdown': weekly_rows,
        })

    total_gross = sum(s.gross_amount for s in settlements)
    total_paid = sum(
        s.net_payable for s in settlements
        if s.status == 'paid' and s.net_payable > 0
    )
    total_pending = sum(
        s.net_payable for s in settlements
        if s.status == 'calculated' and s.net_payable > 0
    )

    return Response({
        'mukkadam_name': mukkadam.mukkadam_name,
        'summary': {
            'total_jobs': len(data),
            'total_gross': float(total_gross),
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
        },
        'settlements': data,
    })

# views.py

@api_view(['GET'])
@permission_classes([AllowAny])
def list_all_settlements(request):
    """
    GET /api/settlements/
    All settlements across all mukkadams — for the Payments tab.
    Supports: ?cluster_id=, ?status=, ?search=
    """
    qs = MukkadamJobSettlement.objects.select_related(
        'mukkadam', 'job', 'job__farmer', 'cluster'
    ).order_by('-created_at')

    # Filters
    cluster_id = request.query_params.get('cluster_id')
    status = request.query_params.get('status')
    search = request.query_params.get('search', '').strip()

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            models.Q(mukkadam__mukkadam_name__icontains=search) |
            models.Q(job__farmer__farmer_name__icontains=search) |
            models.Q(job__job_id__icontains=search)
        )

    data = []
    for s in qs:
        data.append({
            'mukkadam_id': s.mukkadam.pk,
            'mukkadam_name': s.mukkadam.mukkadam_name,
            'crew_size': s.mukkadam.crew_size,
            'job_id': s.job.job_id,
            'farmer_name': s.job.farmer.farmer_name,
            'farmer_id': s.job.farmer.farmer_id,
            'cluster_name': s.cluster.name if s.cluster else '—',
            'gross_amount': float(s.gross_amount),
            'advance_deducted': float(s.advance_deducted),
            'weekly_payments_deducted': float(s.weekly_payments_deducted),
            'net_payable': float(s.net_payable),
            'status': s.status,
            'calculated_at': s.calculated_at,
            'paid_at': s.paid_at,
        })

    return Response(data)



from tender.ervices.farmerbill import get_farmer_billing_for_job
from django.utils import timezone

@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_job_billing(request, farmer_id, job_id):
    """GET /api/farmer/<farmer_id>/job/<job_id>/billing/"""
    data = get_farmer_billing_for_job(job_id)
    if not data:
        return Response({'error': 'Job not found'}, status=404)
    if data['farmer_id'] != farmer_id:
        return Response({'error': 'Job does not belong to this farmer'}, status=400)
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_all_jobs_billing(request, farmer_id):
    """GET /api/farmer/<farmer_id>/billing/  — all jobs for this farmer"""
    jobs = Job.objects.filter(farmer_id=farmer_id).values_list('job_id', flat=True)
    results = []
    for job_id in jobs:
        billing = get_farmer_billing_for_job(job_id)
        if billing:
            results.append(billing)
    return Response(results)

from django.utils import timezone

@api_view(['POST'])
@permission_classes([AllowAny])
def record_farmer_payment(request, farmer_id, job_id):
    amount       = request.data.get('amount')
    mode         = request.data.get('mode', 'CASH')
    notes        = request.data.get('notes', '')
    proof_s3_key = request.data.get('proof_s3_key')

    if not amount or float(amount) <= 0:
        return Response({'error': 'Valid amount required'}, status=400)

    if not proof_s3_key:
        return Response({'error': 'Payment proof is required'}, status=400)

    try:
        job     = Job.objects.get(job_id=job_id, farmer__farmer_id=farmer_id)
        booking = job.booking
    except Exception:
        return Response({'error': 'Job or booking not found'}, status=404)

    from decimal import Decimal
    import time

    # Generate unique payment_id from timestamp (milliseconds)
    payment_id = int(time.time() * 1000)

    payment = FarmerPayment.objects.create(
        booking      = booking,
        payment_id   = payment_id,          # ← required unique BigInt
        amount       = Decimal(str(amount)),
        mode         = mode,
        notes        = notes,
        proof_s3_key = proof_s3_key,
        paid_status  = True,
        paid_at      = timezone.now(),      # ← required, no auto_now_add
    )

    return Response({
        'message':      f'Payment of ₹{amount} recorded successfully',
        'payment_id':   payment.id,
        'mode':         mode,
        'proof_s3_key': proof_s3_key,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def cluster_payment_dashboard(request, cluster_id):
    ctx(flow="cluster_payment_dashboard", cluster_id=str(cluster_id))
    from datetime import date, timedelta
    from decimal import Decimal
    from collections import defaultdict
    from django.db.models import Prefetch, Sum

    today = date.today()

    # ─────────────────────────────────────────────────────────────
    # BATCH PREFETCH EVERYTHING UPFRONT — zero N+1 queries
    # ─────────────────────────────────────────────────────────────

    # 1. Bill logs for entire cluster — ONE query
    all_bill_logs = FarmerBillWebhookLog.objects.filter(
        cluster_id=cluster_id
    ).order_by('-sent_at').values(
        'farmer_id', 'job_id', 'activity_name', 'sent_at', 'sent_by_name',
        'webhook_status', 'total_billed', 'total_paid', 'balance_due', 'full_payload'
    )
    bill_log_map = defaultdict(dict)
    for log in all_bill_logs:
        fid     = str(log['farmer_id'] or '')
        job_id  = str(log['job_id'] or '')
        act_key = log['activity_name'] or ''
        map_key = f"{fid}__{job_id}"
        if act_key and act_key not in bill_log_map[map_key]:
            bill_log_map[map_key][act_key] = {
                'sent':           True,
                'sent_at':        log['sent_at'].isoformat() if log['sent_at'] else None,
                'sent_by':        log['sent_by_name'] or '—',
                'webhook_status': log['webhook_status'],
                'total_billed':   float(log['total_billed'] or 0),
                'total_paid':     float(log['total_paid'] or 0),
                'balance_due':    float(log['balance_due'] or 0),
                'full_payload':   log['full_payload'] or {},
            }

    # 2. Allocations prefetch
    allocations_qs = Allocation.objects.select_related('mukkadam').order_by('allocated_date')

    # 3. Activities prefetch — exclude lost, require positive area
    activities_qs = JobActivity.objects.filter(
        is_lost=False,
        total_area__gt=0,
    ).select_related('activity', 'plot').prefetch_related(
        Prefetch('allocations', queryset=allocations_qs)
    )

    # 4. Payments prefetch
    payments_qs = FarmerPayment.objects.filter(paid_status=True).order_by('paid_at')

    # 5. Jobs prefetch
    jobs_qs = Job.objects.filter(
        activities__plot__clusters__id=cluster_id,
        booking_type__in=['tender', 'ondemand'],
    ).distinct().select_related('plot', 'farmer').prefetch_related(
        Prefetch('activities', queryset=activities_qs),
        Prefetch('booking', queryset=JobBooking.objects.prefetch_related(
            Prefetch('payments', queryset=payments_qs)
        )),
    )

    # 6. Farmers with prefetched jobs
    farmers_in_cluster = Farmer.objects.filter(
        clusters__id=cluster_id
    ).distinct().prefetch_related(
        Prefetch('jobs', queryset=jobs_qs)
    )

    # ─────────────────────────────────────────────────────────────
    # COLLECT ALL S3 KEYS UPFRONT — one batch presign call
    # ─────────────────────────────────────────────────────────────
    all_s3_keys = []
    for farmer in farmers_in_cluster:
        for job in farmer.jobs.all():
            try:
                for p in job.booking.payments.all():
                    if getattr(p, 'proof_s3_key', None):
                        all_s3_keys.append(p.proof_s3_key)
            except Exception:
                err("payment_dashboard_payment_fail",
        cluster_id=str(cluster_id),
        farmer_id=str(farmer.farmer_id),
        job_id=str(job.job_id))
                pass

    all_assignments = ClusterMukkadamAssignment.objects.filter(
        cluster_id=cluster_id, is_active=True,
    ).select_related('mukkadam').order_by('joined_at')

    mukkadam_ids = list({a.mukkadam_id for a in all_assignments})

    weekly_qs_all = MukkadamWeeklyPayment.objects.filter(
        assignment__mukkadam_id__in=mukkadam_ids,
        assignment__cluster_id=cluster_id,
    ).select_related('assignment').order_by('payment_date')

    settle_payments_all = MukkadamPayment.objects.filter(
        mukkadam_id__in=mukkadam_ids,
    ).select_related('settlement__job__farmer').order_by('paid_at')

    misc_costs_all = MukkadamMiscCost.objects.filter(
        mukkadam_id__in=mukkadam_ids,
    ).select_related('job').order_by('created_at')

    settlements_all = MukkadamJobSettlement.objects.filter(
        mukkadam_id__in=mukkadam_ids,
    ).select_related('job__farmer').prefetch_related(
        Prefetch('job__activities',
            queryset=JobActivity.objects.select_related('activity', 'plot').prefetch_related(
                Prefetch('allocations',
                    queryset=Allocation.objects.select_related('mukkadam').order_by('allocated_date')
                )
            )
        )
    ).order_by('-calculated_at')

    for w in weekly_qs_all:
        if getattr(w, 'proof_s3_key', None):
            all_s3_keys.append(w.proof_s3_key)
    for p in settle_payments_all:
        if getattr(p, 'proof_s3_key', None):
            all_s3_keys.append(p.proof_s3_key)
    for c in misc_costs_all:
        if getattr(c, 'proof_s3_key', None):
            all_s3_keys.append(c.proof_s3_key)

    global_proof_map = get_presigned_urls_batch(list(set(all_s3_keys))) if all_s3_keys else {}
    ops("payment_dashboard_s3_batch",
    cluster_id=str(cluster_id),
    keys_count=len(all_s3_keys))

    weekly_by_mukkadam          = defaultdict(list)
    settle_payments_by_mukkadam = defaultdict(list)
    misc_by_mukkadam            = defaultdict(list)
    settlements_by_mukkadam     = defaultdict(list)

    for w in weekly_qs_all:
        weekly_by_mukkadam[w.assignment.mukkadam_id].append(w)
    for p in settle_payments_all:
        settle_payments_by_mukkadam[p.mukkadam_id].append(p)
    for c in misc_costs_all:
        misc_by_mukkadam[c.mukkadam_id].append(c)
    for s in settlements_all:
        settlements_by_mukkadam[s.mukkadam_id].append(s)

    # ─────────────────────────────────────────────────────────────
    # FARMERS
    # ─────────────────────────────────────────────────────────────
    farmer_data = []

    for farmer in farmers_in_cluster:
        jobs = list(farmer.jobs.all())
        if not jobs:
            continue

        job_rows = []

        for job in jobs:
            job_map_key          = f"{str(farmer.farmer_id)}__{str(job.job_id)}"
            farmer_bill_sent_map = bill_log_map.get(job_map_key, {})
            try:
                booking = job.booking
            except JobBooking.DoesNotExist:
                booking = None

            # Use prefetched activities (already filtered: is_lost=False, total_area__gt=0)
            activities = list(job.activities.all())

            activity_rows  = []
            total_billable = Decimal('0')
            all_past       = True
            first_date     = None
            last_date      = None

            job_mukkadam_name   = '—'
            job_mukkadam_mobile = '—'

            for act in activities:
                # Defensive: skip lost (already filtered in queryset, belt-and-suspenders)
                if getattr(act, 'is_lost', False):
                    continue

                is_past = bool(act.scheduled_date and act.scheduled_date <= today)
                if not is_past:
                    all_past = False
                if act.scheduled_date:
                    if first_date is None or act.scheduled_date < first_date:
                        first_date = act.scheduled_date
                    if last_date is None or act.scheduled_date > last_date:
                        last_date = act.scheduled_date

                # Effective total area: prefer JA's own total_area, fallback to plot.area_acres
                effective_total_area = (
                    act.total_area if act.total_area and act.total_area > 0
                    else (act.plot.area_acres if act.plot and act.plot.area_acres else None)
                )
                # Already filtered total_area__gt=0 in queryset, but keep guard
                if not effective_total_area or effective_total_area <= 0:
                    continue

                act_allocations = list(act.allocations.all())

                # Skip truly empty rows: pending, zero allocations, zero area
                if act.allocation_status == 'pending' and len(act_allocations) == 0 and (
                    not effective_total_area or effective_total_area <= 0
                ):
                    continue

                # Set mukkadam from first allocation found
                if job_mukkadam_name == '—' and act_allocations:
                    first_alloc = act_allocations[0]
                    if first_alloc.mukkadam:
                        job_mukkadam_name   = first_alloc.mukkadam.mukkadam_name or '—'
                        job_mukkadam_mobile = first_alloc.mukkadam.mobile_numbers or '—'

                alloc_details = []
                for a in act_allocations:
                    if a.admin_override_area is not None:
                        a_effective = a.admin_override_area
                    elif getattr(a, 'use_actual_for_settlement', False) and a.actual_area_done is not None:
                        a_effective = a.actual_area_done
                    else:
                        a_effective = a.allocated_area

                    billing_locked = (
                        getattr(a, 'payment_status', None) == 'dispute'
                        and not getattr(a, 'use_actual_for_settlement', False)
                        and a.admin_override_area is None
                    )
                    rate_dec = Decimal(str(act.rate_per_acre or 0))
                    area_dec = Decimal(str(a_effective or 0))
                    farmer_amount   = float((area_dec * rate_dec).quantize(Decimal('0.01'))) if not billing_locked else 0.0
                    mukkadam_amount = float((area_dec * Decimal(str(a.mukkadam_rate or 0))).quantize(Decimal('0.01'))) if not billing_locked else 0.0

                    alloc_details.append({
                        'allocation_id':             a.id,
                        'allocated_date':            str(a.allocated_date) if a.allocated_date else None,
                        'allocated_workers':         a.allocated_workers or 0,
                        'allocated_area':            float(a.allocated_area or 0),
                        'mukkadam_claimed_area':     float(a.mukkadam_claimed_area) if getattr(a, 'mukkadam_claimed_area', None) is not None else None,
                        'admin_override_area':       float(a.admin_override_area) if getattr(a, 'admin_override_area', None) is not None else None,
                        'actual_area_done':          float(a.actual_area_done) if a.actual_area_done is not None else None,
                        'actual_crew_size':          a.actual_crew_size,
                        'actual_start_time':         a.actual_start_time.isoformat() if a.actual_start_time else None,
                        'actual_end_time':           a.actual_end_time.isoformat() if a.actual_end_time else None,
                        'report_submitted':          a.report_submitted,
                        'report_submitted_at':       a.report_submitted_at.isoformat() if a.report_submitted_at else None,
                        'work_status':               getattr(a, 'work_status', 'work_not_started'),
                        'payment_status':            getattr(a, 'payment_status', 'pending'),
                        'farmer_agreed':             a.farmer_agreed,
                        'farmer_response_at':        a.farmer_response_at.isoformat() if a.farmer_response_at else None,
                        'farmer_dispute_reason':     getattr(a, 'farmer_dispute_reason', None),
                        'dispute_reason':            getattr(a, 'dispute_reason', None),
                        'use_actual_for_settlement': bool(getattr(a, 'use_actual_for_settlement', False)),
                        'billing_locked':            billing_locked,
                        'mukkadam_rate':             float(a.mukkadam_rate or 0),
                        'rate_per_acre':             float(act.rate_per_acre or 0),
                        'farmer_amount':             farmer_amount,
                        'mukkadam_amount':           mukkadam_amount,
                        'job_id':                    job.job_id,
                        'is_carry_forward':          getattr(a, 'is_carry_forward', False),
                    })

                actual_area_values = [Decimal(str(a.actual_area_done)) for a in act_allocations if a.actual_area_done is not None]
                actual_area  = sum(actual_area_values) if actual_area_values else None
                crew_values  = [a.actual_crew_size for a in act_allocations if a.actual_crew_size is not None]
                actual_crew  = sum(crew_values) if crew_values else None
                agreed_values = [a.farmer_agreed for a in act_allocations if a.report_submitted]
                if not agreed_values:
                    farmer_agreed = None
                elif all(v is True for v in agreed_values):
                    farmer_agreed = True
                elif any(v is False for v in agreed_values):
                    farmer_agreed = False
                else:
                    farmer_agreed = None
                report_submitted = any(a.report_submitted for a in act_allocations)

                act_billable = Decimal('0')
                act_estimate = Decimal('0')
                for a in act_allocations:
                    area = Decimal(str(a.allocated_area or 0))
                    rate = Decimal(str(act.rate_per_acre or 0))
                    if a.work_status == 'completed':
                        act_billable += (area * rate).quantize(Decimal('0.01'))
                    else:
                        act_estimate += (area * rate).quantize(Decimal('0.01'))

                if not act_allocations and act.rate_per_acre:
                    act_estimate = (
                        Decimal(str(effective_total_area)) * Decimal(str(act.rate_per_acre))
                    ).quantize(Decimal('0.01'))

                total_billable += act_billable

                activity_rows.append({
                    'activity_id':       act.id,
                    'activity_name':     act.activity.name,
                    'plot_code':         act.plot.plot_code if act.plot else '—',
                    'plot_name':         act.plot.name if act.plot else '—',
                    'scheduled_date':    str(act.scheduled_date) if act.scheduled_date else None,
                    'is_past':           is_past,
                    'allocated_area':    float(act.allocated_area or 0),
                    'total_area':        float(effective_total_area),
                    'rate_per_acre':     float(act.rate_per_acre or 0),
                    'billable_amount':   float(act_billable),
                    'estimated_amount':  float(act_estimate),
                    'allocation_status': act.allocation_status,
                    'actual_area_done':  float(actual_area) if actual_area is not None else None,
                    'actual_crew_size':  actual_crew,
                    'farmer_agreed':     farmer_agreed,
                    'report_submitted':  report_submitted,
                    'allocation_count':  len(act_allocations),
                    'allocations':       alloc_details,
                    'mukkadam_name':     (
                        act_allocations[0].mukkadam.mukkadam_name
                        if act_allocations and act_allocations[0].mukkadam else None
                    ),
                })

            # ── Merge split activities: same (plot_code, activity_name) → one row ──
            merged_rows_map = {}
            for row in activity_rows:
                key = (row['plot_code'], row['activity_name'])
                if key not in merged_rows_map:
                    merged_rows_map[key] = dict(row)
                    merged_rows_map[key]['allocations'] = list(row['allocations'])
                else:
                    existing = merged_rows_map[key]
                    existing['total_area']       += row['total_area']
                    existing['allocated_area']   += row['allocated_area']
                    existing['billable_amount']  += row['billable_amount']
                    existing['estimated_amount'] += row['estimated_amount']
                    existing['allocation_count'] += row['allocation_count']
                    existing['allocations'].extend(row['allocations'])
                    if row['actual_area_done'] is not None:
                        existing['actual_area_done'] = (
                            (existing['actual_area_done'] or 0) + row['actual_area_done']
                        )
                    if row['actual_crew_size'] is not None:
                        existing['actual_crew_size'] = (
                            (existing['actual_crew_size'] or 0) + row['actual_crew_size']
                        )
                    existing['is_past'] = existing['is_past'] and row['is_past']
                    STATUS_RANK = {
                        'pending': 0, 'not_allocated': 0,
                        'partially_allocated': 1, 'fully_allocated': 2,
                        'in_progress': 3, 'completed': 4,
                    }
                    if STATUS_RANK.get(row['allocation_status'], 0) < STATUS_RANK.get(existing['allocation_status'], 0):
                        existing['allocation_status'] = row['allocation_status']
                    if row['farmer_agreed'] is False:
                        existing['farmer_agreed'] = False
                    elif row['farmer_agreed'] is None and existing['farmer_agreed'] is True:
                        existing['farmer_agreed'] = None
                    existing['report_submitted'] = existing['report_submitted'] or row['report_submitted']
                    if not existing['mukkadam_name'] and row['mukkadam_name']:
                        existing['mukkadam_name'] = row['mukkadam_name']
                    if row['scheduled_date'] and (
                        not existing['scheduled_date'] or row['scheduled_date'] < existing['scheduled_date']
                    ):
                        existing['scheduled_date'] = row['scheduled_date']

            activity_rows  = list(merged_rows_map.values())
            total_billable = sum(Decimal(str(r['billable_amount'])) for r in activity_rows)

            # ── Payment history ──────────────────────────────────────────
            advance_paid    = Decimal(str(booking.advance_paid)) if booking else Decimal('0')
            additional_paid = Decimal('0')
            payment_history = []

            if booking:
                fps = list(booking.payments.all())
                confirmed_fps   = [p for p in fps if getattr(p, 'paid_status', True) is not False]
                additional_paid = sum(Decimal(str(p.amount)) for p in confirmed_fps)

                if advance_paid > 0 and len(confirmed_fps) == 0:
                    payment_history.append({
                        'type': 'advance', 'date': str(booking.created_at.date()),
                        'amount': float(advance_paid), 'mode': 'Advance',
                        'notes': 'Initial advance', 'paid_status': True,
                        'proof_url': None, 'payment_id': None, 'job_id': job.job_id,
                    })
                for p in fps:
                    if getattr(p, 'paid_status', True) is False:
                        continue
                    proof_s3_key = getattr(p, 'proof_s3_key', None)
                    payment_history.append({
                        'type':         'payment',
                        'date':         str(p.paid_at.date()),
                        'amount':       float(p.amount),
                        'mode':         p.mode,
                        'notes':        getattr(p, 'notes', ''),
                        'paid_status':  True,
                        'proof_url':    global_proof_map.get(proof_s3_key) if proof_s3_key else None,
                        'proof_s3_key': proof_s3_key,
                        'payment_id':   p.id,
                        'job_id':       job.job_id,
                    })

            total_paid    = additional_paid if additional_paid > 0 else advance_paid
            balance_due   = total_billable - total_paid
            booking_total = Decimal(str(booking.total_amount)) if booking else Decimal('0')
            final_gap     = (booking_total - total_paid) if all_past and booking else Decimal('0')

            job_rows.append({
                'job_id':              job.job_id,
                'booking_type':        job.booking_type,
                'crop_name':           job.crop_name,
                'variety':             getattr(job, 'variety', ''),
                'plot_name':           activities[0].plot.name if activities and activities[0].plot else '—',
                'mukkadam_name':       job_mukkadam_name,
                'mukkadam_mobile':     job_mukkadam_mobile,
                'job_status':          job.status,
                'first_activity_date': str(first_date) if first_date else None,
                'last_activity_date':  str(last_date) if last_date else None,
                'booking_id':          booking.booking_id if booking else None,
                'total_job_amount':    float(booking_total),
                'bill_sent_map':       farmer_bill_sent_map,
                'activities':          activity_rows,
                'summary': {
                    'total_billable_so_far': float(total_billable),
                    'advance_paid':          float(advance_paid),
                    'additional_paid':       float(total_paid),
                    'total_paid':            float(total_paid),
                    'balance_due':           float(balance_due),
                    'all_activities_past':   all_past,
                    'final_gap':             float(final_gap),
                    'show_collect_button':   balance_due > Decimal('0.01'),
                    'show_final_collection': all_past and final_gap > Decimal('0.01'),
                },
                'payment_history': payment_history,
            })

        if not job_rows:
            continue

        # ── FIX: total_acres — unique plots by plot_code using plot.area_acres ──
        # activity total_area is activity-scoped (partial acres), NOT the full plot area.
        # We must use plot.area_acres for each unique plot the farmer has in this job set.
        # We collect from the prefetched job activities (zero extra queries).
        plot_area_map = {}  # plot_code → area_acres (from Plot model)
        for job in jobs:
            for act in job.activities.all():
                if (
                    act.plot
                    and act.plot.plot_code
                    and not getattr(act, 'is_lost', False)
                    and act.plot.area_acres
                    and float(act.plot.area_acres) > 0
                ):
                    # Use the plot's actual area — same value for all activities on same plot
                    plot_area_map[act.plot.plot_code] = float(act.plot.area_acres)

        total_acres = float(sum(Decimal(str(a)) for a in plot_area_map.values()))

        # ── FIX: total_plots — count unique plot_codes, not plot_name strings ──
        unique_plot_codes = set(
            act['plot_code']
            for j in job_rows
            for act in j['activities']
            if act['plot_code'] and act['plot_code'] != '—'
        )

        total_balance = sum(Decimal(str(j['summary']['balance_due'])) for j in job_rows)
        total_amount  = sum(Decimal(str(j['total_job_amount'])) for j in job_rows)

        farmer_data.append({
            'farmer_id':       farmer.farmer_id,
            'farmer_name':     farmer.farmer_name,
            'mobile_number':   getattr(farmer, 'phone_number', '') or getattr(farmer, 'mobile_number', ''),
            'total_acres':     total_acres,                  # ← FIXED
            'total_job_value': float(sum(Decimal(str(j['total_job_amount'])) for j in job_rows)),
            'total_plots':     len(unique_plot_codes),       # ← FIXED
            'total_amount':    float(total_amount),
            'total_balance':   float(total_balance),
            'jobs':            job_rows,
        })
        ops("payment_dashboard_farmer_built",
    cluster_id=str(cluster_id),
    farmer_id=str(farmer.farmer_id),
    job_count=len(job_rows),
    total_balance=str(float(total_balance)))

    # ─────────────────────────────────────────────────────────────
    # MUKKADAMS — using pre-fetched data
    # ─────────────────────────────────────────────────────────────
    mukkadam_data = []
    seen_mukkadams = set()

    for _assignment in all_assignments:
        mukkadam = _assignment.mukkadam
        if mukkadam.mukkadam_id in seen_mukkadams:
            continue
        seen_mukkadams.add(mukkadam.mukkadam_id)

        assignment = max(
            [a for a in all_assignments if a.mukkadam_id == mukkadam.mukkadam_id],
            key=lambda a: a.joined_at or date.min,
        )

        has_updown_history = any(
            a.mukkadam_id == mukkadam.mukkadam_id and a.mukkadam_type == 'updown'
            for a in all_assignments
        )

        settlements   = settlements_by_mukkadam[mukkadam.mukkadam_id]
        weekly_list   = weekly_by_mukkadam[mukkadam.mukkadam_id]
        misc_list     = misc_by_mukkadam[mukkadam.mukkadam_id]
        sp_list       = settle_payments_by_mukkadam[mukkadam.mukkadam_id]

        sp_by_settlement = defaultdict(list)
        for sp in sp_list:
            if sp.settlement_id:
                sp_by_settlement[sp.settlement_id].append(sp)

        settlement_rows = []
        for s in settlements:
            alloc_list = []
            for act in s.job.activities.all():
                for a in act.allocations.all():
                    if a.mukkadam_id == mukkadam.mukkadam_id:
                        alloc_list.append((act, a))

            act_details = []
            for act, a in alloc_list:
                mukkadam_rate = Decimal(str(a.mukkadam_rate or 0))
                farmer_rate   = Decimal(str(act.rate_per_acre or 0))

                if getattr(a, 'admin_override_area', None) is not None:
                    effective_area = Decimal(str(a.admin_override_area))
                elif getattr(a, 'use_actual_for_settlement', False) and a.actual_area_done is not None:
                    effective_area = Decimal(str(a.actual_area_done))
                elif a.farmer_agreed is True and a.actual_area_done is not None:
                    effective_area = Decimal(str(a.actual_area_done))
                else:
                    effective_area = Decimal(str(a.allocated_area or 0))

                billing_locked = (
                    (getattr(a, 'payment_status', None) == 'dispute'
                     and not getattr(a, 'use_actual_for_settlement', False)
                     and getattr(a, 'admin_override_area', None) is None)
                    or (a.farmer_agreed is False
                        and getattr(a, 'admin_override_area', None) is None
                        and not getattr(a, 'use_actual_for_settlement', False))
                )
                gross = Decimal('0') if billing_locked else (effective_area * mukkadam_rate).quantize(Decimal('0.01'))

                act_details.append({
                    'allocation_id':             a.id,
                    'activity_name':             act.activity.name,
                    'plot_code':                 act.plot.plot_code if act.plot else '—',
                    'scheduled_date':            str(act.scheduled_date) if act.scheduled_date else None,
                    'allocated_date':            str(a.allocated_date) if a.allocated_date else None,
                    'allocated_area':            float(a.allocated_area or 0),
                    'allocated_workers':         a.allocated_workers or 0,
                    'mukkadam_claimed_area':     float(a.mukkadam_claimed_area) if getattr(a, 'mukkadam_claimed_area', None) is not None else None,
                    'admin_override_area':       float(a.admin_override_area) if getattr(a, 'admin_override_area', None) is not None else None,
                    'actual_area_done':          float(a.actual_area_done) if a.actual_area_done is not None else None,
                    'actual_crew_size':          a.actual_crew_size,
                    'actual_start_time':         a.actual_start_time.isoformat() if a.actual_start_time else None,
                    'actual_end_time':           a.actual_end_time.isoformat() if a.actual_end_time else None,
                    'report_submitted':          a.report_submitted,
                    'report_submitted_at':       a.report_submitted_at.isoformat() if a.report_submitted_at else None,
                    'work_status':               getattr(a, 'work_status', 'work_not_started'),
                    'payment_status':            getattr(a, 'payment_status', 'pending'),
                    'farmer_agreed':             a.farmer_agreed,
                    'farmer_response_at':        a.farmer_response_at.isoformat() if a.farmer_response_at else None,
                    'farmer_dispute_reason':     getattr(a, 'farmer_dispute_reason', None),
                    'dispute_reason':            getattr(a, 'dispute_reason', None),
                    'use_actual_for_settlement': bool(getattr(a, 'use_actual_for_settlement', False)),
                    'billing_locked':            billing_locked,
                    'mukkadam_rate':             float(mukkadam_rate),
                    'rate_per_acre':             float(farmer_rate),
                    'gross_amount':              float(gross),
                    'is_carry_forward':          getattr(a, 'is_carry_forward', False),
                })

            misc_for_job    = [c for c in misc_list if c.job_id == s.job_id]
            total_misc      = sum(Decimal(str(c.amount)) for c in misc_for_job)
            misc_costs_data = [{
                'id':         c.id,
                'amount':     float(c.amount),
                'reason':     c.reason,
                'created_at': str(c.created_at.date()),
                'proof_url':  global_proof_map.get(c.proof_s3_key) if getattr(c, 'proof_s3_key', None) else None,
            } for c in misc_for_job]

            weekly_payments_data = [{
                'payment_date':      str(w.payment_date),
                'amount':            float(w.amount),
                'crew_size_on_date': w.crew_size_on_date,
                'mode':              getattr(w, 'mode', 'CASH'),
                'notes':             getattr(w, 'notes', ''),
                'proof_url':         global_proof_map.get(w.proof_s3_key) if getattr(w, 'proof_s3_key', None) else None,
            } for w in weekly_list]

            settlement_payments      = sp_by_settlement.get(s.id, [])
            settlement_payments_data = [{
                'payment_id': sp.payment_id,
                'amount':     float(sp.amount),
                'mode':       getattr(sp, 'mode', 'CASH'),
                'notes':      getattr(sp, 'notes', ''),
                'paid_at':    str(sp.paid_at.date()) if sp.paid_at else None,
                'proof_url':  global_proof_map.get(sp.proof_s3_key) if getattr(sp, 'proof_s3_key', None) else None,
            } for sp in settlement_payments]

            total_already_paid       = sum(float(sp.amount) for sp in settlement_payments)
            settlement_proof_url     = settlement_payments_data[-1]['proof_url'] if settlement_payments_data else None
            settlement_mukkadam_type = s.mukkadam_type if hasattr(s, 'mukkadam_type') else assignment.mukkadam_type

            settlement_rows.append({
                'job_id':                   s.job.job_id,
                'job_title':                f"{s.job.crop_name} — {s.job.farmer.farmer_name}",
                'farmer_name':              s.job.farmer.farmer_name,
                'farmer_id':                s.job.farmer.farmer_id,
                'status':                   s.status,
                'gross_amount':             float(s.gross_amount),
                'deposit_held':             float((s.gross_amount * (s.deposit_percent or Decimal('10')) / 100).quantize(Decimal('0.01'))),
                'payable_90pct':            float(s.payable_amount),
                'deposit_carried_forward':  float(s.deposit_carried_forward) if s.deposit_carried_forward else 0.0,
                'credit_carried_forward':   float(s.credit_carried_forward) if s.credit_carried_forward else 0.0,
                'advance_deducted':         float(s.advance_deducted),
                'weekly_payments_deducted': float(s.weekly_payments_deducted),
                'misc_costs':               misc_costs_data,
                'mukkadam_type':            settlement_mukkadam_type,
                'transport_deducted':       float(s.transport_deducted) if hasattr(s, 'transport_deducted') else 0.0,
                'total_misc':               float(total_misc),
                'net_payable':              float(s.net_payable),
                'calculated_at':            str(s.calculated_at.date()) if s.calculated_at else None,
                'paid_at':                  str(s.paid_at.date()) if s.paid_at else None,
                'proof_url':                settlement_proof_url,
                'payments_made':            settlement_payments_data,
                'total_already_paid':       total_already_paid,
                'show_raise_payment':       s.status == 'calculated' and s.net_payable > 0,
                'activities':               act_details,
                'weekly_payments':          weekly_payments_data,
                'weekly_breakdown':         [{'payment_date': w['payment_date'], 'amount': w['amount'], 'crew_size': w['crew_size_on_date']} for w in weekly_payments_data],
            })

        total_weekly_paid = sum(float(w.amount) for w in weekly_list)
        total_net         = sum(Decimal(str(s['net_payable'])) for s in settlement_rows if s['status'] == 'calculated')
        total_paid_out    = sum(Decimal(str(s['net_payable'])) for s in settlement_rows if s['status'] == 'paid')

        settled_job_ids = {s['job_id'] for s in settlement_rows}
        jobs_with_allocs = Job.objects.filter(
            activities__allocations__mukkadam=mukkadam,
            activities__plot__clusters__id=cluster_id,
        ).distinct()
        unsettled_jobs = []
        for j in jobs_with_allocs:
            if j.job_id not in settled_job_ids:
                alloc_count = Allocation.objects.filter(mukkadam=mukkadam, job_activity__job=j).count()
                if alloc_count > 0:
                    unsettled_jobs.append({
                        'job_id':           j.job_id,
                        'crop_name':        getattr(j, 'crop_name', ''),
                        'farmer_name':      j.farmer.farmer_name if hasattr(j, 'farmer') and j.farmer else '—',
                        'allocation_count': alloc_count,
                    })

        try:
            from .ervices.settlement import build_week_ledger
            ledger_data    = build_week_ledger(mukkadam, assignment)
            week_ledger    = ledger_data['week_ledger']
            pending_work   = ledger_data['pending_work']
            ledger_summary = ledger_data['summary']
        except Exception:
            err("payment_dashboard_ledger_fail",
        cluster_id=str(cluster_id),
        mukkadam_id=str(mukkadam.mukkadam_id))
            week_ledger    = []
            pending_work   = []
            ledger_summary = {}

        txn_history = []

        if assignment.advance_amount and float(assignment.advance_amount) > 0:
            txn_history.append({
                'type': 'advance', 'date': str(assignment.joined_at.date()) if assignment.joined_at else str(today),
                'label': 'Advance Given', 'amount': -float(assignment.advance_amount),
                'mode': 'CASH', 'notes': '', 'proof_url': None, 'job_id': None, 'color': 'red', 'icon': '💰',
            })

        for w in weekly_list:
            txn_history.append({
                'type': 'weekly', 'date': str(w.payment_date), 'label': 'Weekly Payment',
                'amount': -float(w.amount), 'mode': getattr(w, 'mode', 'CASH'),
                'notes': getattr(w, 'notes', ''),
                'proof_url': global_proof_map.get(w.proof_s3_key) if getattr(w, 'proof_s3_key', None) else None,
                'job_id': None, 'color': 'orange', 'icon': '📅',
            })

        for p in sp_list:
            job_id      = p.settlement.job.job_id if p.settlement and p.settlement.job else None
            farmer_name = p.settlement.job.farmer.farmer_name if p.settlement and p.settlement.job and p.settlement.job.farmer else ''
            txn_history.append({
                'type': 'settlement_payment', 'date': str(p.paid_at.date()) if p.paid_at else str(today),
                'label': f'Settlement Paid — Job #{job_id} {farmer_name}',
                'amount': float(p.amount), 'mode': getattr(p, 'mode', 'CASH'),
                'notes': getattr(p, 'notes', ''),
                'proof_url': global_proof_map.get(p.proof_s3_key) if getattr(p, 'proof_s3_key', None) else None,
                'job_id': job_id, 'color': 'green', 'icon': '✅',
            })

        for c in misc_list:
            txn_history.append({
                'type': 'misc_deduction', 'date': str(c.created_at.date()),
                'label': f'Misc Deduction — {c.reason or "No reason"}',
                'amount': -float(c.amount), 'mode': '—', 'notes': c.reason or '',
                'proof_url': global_proof_map.get(c.proof_s3_key) if getattr(c, 'proof_s3_key', None) else None,
                'job_id': c.job.job_id if c.job else None, 'color': 'purple', 'icon': '⚠️',
            })

        txn_history.sort(key=lambda x: x['date'])
        running = 0.0
        for txn in txn_history:
            running += txn['amount']
            txn['running_balance'] = round(running, 2)

        updown_allocations = []
        if has_updown_history:
            all_updown_allocs = Allocation.objects.filter(
                mukkadam=mukkadam,
            ).select_related(
                'job_activity__activity', 'job_activity__plot',
                'job_activity__job', 'job_activity__job__farmer', 'cluster',
            ).order_by('allocated_date')

            all_mukkadam_assignments_updown = [
                a for a in all_assignments
                if a.mukkadam_id == mukkadam.mukkadam_id and a.mukkadam_type == 'updown'
            ]
            settled_map = {str(sr['job_id']): sr for sr in settlement_rows}

            for a in all_updown_allocs:
                ja     = a.job_activity
                job_   = ja.job
                plot   = ja.plot
                farmer = job_.farmer if job_ else None

                area      = Decimal(str(a.actual_area_done or a.allocated_area or 0))
                rate      = Decimal(str(a.mukkadam_rate or 0))
                gross_est = (area * rate).quantize(Decimal('0.01'))

                transport_est = Decimal('0')
                if a.allocated_date:
                    for asgn in sorted(all_mukkadam_assignments_updown, key=lambda x: x.joined_at or date.min):
                        if asgn.joined_at and asgn.joined_at.date() <= a.allocated_date:
                            transport_est = Decimal(str(asgn.transport_price or 0))

                net_est    = gross_est + transport_est
                job_id_str = str(job_.job_id) if job_ else None
                sr         = settled_map.get(job_id_str)

                updown_allocations.append({
                    'allocation_id':      a.id,
                    'allocated_date':     str(a.allocated_date) if a.allocated_date else None,
                    'job_id':             job_id_str,
                    'farmer_name':        farmer.farmer_name if farmer else '—',
                    'farmer_id':          str(farmer.farmer_id) if farmer else None,
                    'activity_name':      ja.activity.name if ja.activity else '—',
                    'plot_code':          plot.plot_code if plot else '—',
                    'plot_name':          plot.name if plot else '—',
                    'allocated_area':     float(a.allocated_area or 0),
                    'actual_area_done':   float(a.actual_area_done) if a.actual_area_done is not None else None,
                    'mukkadam_rate':      float(rate),
                    'work_status':        a.work_status or 'work_not_started',
                    'report_submitted':   a.report_submitted,
                    'allocated_workers':  a.allocated_workers or 0,
                    'actual_crew_size':   a.actual_crew_size,
                    'cluster_id':         a.cluster_id,
                    'cluster_name':       a.cluster.name if a.cluster else '—',
                    'gross_estimate':     float(gross_est),
                    'transport_estimate': float(transport_est),
                    'net_estimate':       float(net_est),
                    'is_completed':       a.work_status == 'completed',
                    'settlement_status':  sr['status'] if sr else None,
                    'actual_gross':       sr['gross_amount'] if sr else None,
                    'actual_transport':   sr['transport_deducted'] if sr else None,
                    'actual_net':         sr['net_payable'] if sr else None,
                    'settlement_id':      None,
                })

        missed_weekly = []
        if assignment.weekly_payment_day is not None and assignment.joined_at:
            start      = assignment.joined_at.date()
            current    = start
            paid_dates = {w.payment_date for w in weekly_list}
            while current <= today:
                if current.weekday() == assignment.weekly_payment_day and current < today:
                    if current not in paid_dates:
                        missed_weekly.append(str(current))
                current += timedelta(days=1)

        mukkadam_data.append({
            'mukkadam_id':              mukkadam.mukkadam_id,
            'mukkadam_name':            mukkadam.mukkadam_name,
            'mobile_numbers':           mukkadam.mobile_numbers,
            'crew_size':                mukkadam.crew_size,
            'advance_amount':           float(assignment.advance_amount or 0),
            'transport_price':          float(assignment.transport_price or 0),
            'total_weekly_paid':        float(total_weekly_paid),
            'weekly_payment_amount':    float(assignment.weekly_amount),
            'weekly_payment_day_value': assignment.weekly_payment_day,
            'weekly_payment_day_label': assignment.get_weekly_payment_day_display() if assignment.weekly_payment_day is not None else None,
            'missed_weekly_dates':      missed_weekly,
            'already_paid_today':       any(w.payment_date == today for w in weekly_list),
            'assignment_id':            assignment.id,
            'settlements':              settlement_rows,
            'updown_allocations':       updown_allocations,
            'mukkadam_type':            assignment.mukkadam_type,
            'has_updown_history':       has_updown_history,
            'unsettled_jobs':           unsettled_jobs,
            'week_ledger':              week_ledger,
            'transaction_history':      txn_history,
            'pending_work':             pending_work,
            'ledger_summary':           ledger_summary,
            'summary': {
                'total_jobs':      len(settlement_rows),
                'pending_payment': float(total_net),
                'total_paid_out':  float(total_paid_out),
            },
        })
        ops("payment_dashboard_mukkadam_built",
    cluster_id=str(cluster_id),
    mukkadam_id=str(mukkadam.mukkadam_id),
    settlements=len(settlement_rows),
    weekly_paid=str(total_weekly_paid),
    pending=str(float(total_net)))

    total_farmer_due   = sum(max(0, f['total_balance']) for f in farmer_data)
    total_mukkadam_due = sum(max(0, m['summary']['pending_payment']) for m in mukkadam_data)


    ops("payment_dashboard_served",
    cluster_id=str(cluster_id),
    farmers=len(farmer_data),
    mukkadams=len(mukkadam_data),
    farmer_due=str(float(total_farmer_due)),
    mukkadam_due=str(float(total_mukkadam_due)))
    return Response({
        'cluster_id':         cluster_id,
        'farmer_count':       len(farmer_data),
        'mukkadam_count':     len(mukkadam_data),
        'total_farmer_due':   float(total_farmer_due),
        'total_mukkadam_due': float(total_mukkadam_due),
        'farmers':            farmer_data,
        'mukkadams':          mukkadam_data,
    })



@api_view(['GET'])
@permission_classes([AllowAny])
def mukkadam_payment_overview(request):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.db.models import Sum

    today    = date.today()
    week_ago = today - timedelta(days=7)

    # ── 1. All active assignments ──────────────────────────────────────────
    active_assignments = ClusterMukkadamAssignment.objects.filter(
        is_active=True
    ).select_related('mukkadam', 'cluster')

    active_count = active_assignments.values('mukkadam_id').distinct().count()

    # ── 2. Weekly due ──────────────────────────────────────────────────────
    # Mukkadams whose weekly_payment_day matches today's weekday
    # and haven't been paid today
    weekly_due_list = []
    for asgn in active_assignments:
        if asgn.weekly_payment_day is None:
            continue
        already_paid = MukkadamWeeklyPayment.objects.filter(
            assignment=asgn,
            payment_date=today,
        ).exists()
        if not already_paid:
            # Check if today is their payment day OR overdue
            days_since_last = None
            last_payment = MukkadamWeeklyPayment.objects.filter(
                assignment=asgn,
            ).order_by('-payment_date').first()

            if last_payment:
                days_since_last = (today - last_payment.payment_date).days
            
            is_due_today   = today.weekday() == asgn.weekly_payment_day
            is_overdue     = last_payment and days_since_last and days_since_last > 7

            if is_due_today or is_overdue:
                weekly_due_list.append({
                    'mukkadam_id':   asgn.mukkadam.mukkadam_id,
                    'mukkadam_name': asgn.mukkadam.mukkadam_name,
                    'cluster_id':    asgn.cluster.id,
                    'cluster_name':  asgn.cluster.name,
                    'assignment_id': asgn.id,
                    'weekly_amount': float(asgn.weekly_amount),
                    'days_overdue':  days_since_last - 7 if is_overdue else 0,
                    'mukkadam_type': asgn.mukkadam_type,
                })

    weekly_due_amount = sum(x['weekly_amount'] for x in weekly_due_list)

    pending_settlements = MukkadamJobSettlement.objects.filter(
        status='calculated',
        net_payable__gt=0,
    ).select_related('mukkadam', 'job', 'cluster').prefetch_related('job__clusters')

    settlement_list = []
    for s in pending_settlements:
        cluster_obj = s.cluster or (s.job.clusters.first() if s.job else None)
        settlement_list.append({
            'mukkadam_id':   s.mukkadam.mukkadam_id,
            'mukkadam_name': s.mukkadam.mukkadam_name,
            'cluster_id':    cluster_obj.id if cluster_obj else None,
            'cluster_name':  cluster_obj.name if cluster_obj else '—',
            'job_id':        s.job.job_id,
            'net_payable':   float(s.net_payable),
            'gross_amount':  float(s.gross_amount),
            'calculated_at': str(s.calculated_at.date()) if s.calculated_at else None,
            'mukkadam_type': s.mukkadam_type if hasattr(s, 'mukkadam_type') else 'permanent',
        })

    settlement_pending_amount = sum(x['net_payable'] for x in settlement_list)

    # ── 4. Total paid out ──────────────────────────────────────────────────
    total_mukkadam_payments = MukkadamPayment.objects.aggregate(
        s=Sum('amount')
    )['s'] or Decimal('0')

    total_weekly_payments = MukkadamWeeklyPayment.objects.aggregate(
        s=Sum('amount')
    )['s'] or Decimal('0')

    total_paid_out = float(total_mukkadam_payments + total_weekly_payments)

    # ── 5. Unverified misc costs (verification queue) ─────────────────────
    unverified_misc = MukkadamMiscCost.objects.filter(
        verified=False,
    ).select_related('mukkadam', 'job')

    verification_queue = []
    for cost in unverified_misc:
        cluster_obj = cost.job.clusters.first() if cost.job else None
        verification_queue.append({
            'cost_id':       cost.id,
            'mukkadam_id':   cost.mukkadam.mukkadam_id,
            'mukkadam_name': cost.mukkadam.mukkadam_name,
            'cluster_name':  cluster_obj.name if cluster_obj else '—',
            'cluster_id':    cluster_obj.id if cluster_obj else None,
            'job_id':        cost.job.job_id if cost.job else None,
            'amount':        float(cost.amount),
            'reason':        cost.reason,
            'created_at':    str(cost.created_at.date()),
        })

    # ── 6. Per-cluster billing summary ────────────────────────────────────
    clusters = Cluster.objects.filter(
        mukkadam_assignments__is_active=True
    ).distinct()

    cluster_billing = []
    for c in clusters:
        c_assignments = ClusterMukkadamAssignment.objects.filter(
            cluster=c, is_active=True
        ).select_related('mukkadam')

        c_mukkadam_ids = list(
            c_assignments.values_list('mukkadam__mukkadam_id', flat=True).distinct()
        )

        # Weekly paid for this cluster
        c_weekly_paid = MukkadamWeeklyPayment.objects.filter(
            assignment__cluster=c,
        ).aggregate(s=Sum('amount'))['s'] or 0

        # Settlement paid
        c_settled = MukkadamJobSettlement.objects.filter(
            cluster=c, status='paid'
        ).aggregate(s=Sum('net_payable'))['s'] or 0

        # Settlement pending
        c_pending = MukkadamJobSettlement.objects.filter(
            cluster=c, status='calculated', net_payable__gt=0
        ).aggregate(s=Sum('net_payable'))['s'] or 0

        # Weekly due today
        c_weekly_due = sum(
            x['weekly_amount'] for x in weekly_due_list
            if x['cluster_id'] == c.id
        )

        cluster_billing.append({
            'cluster_id':        c.id,
            'cluster_name':      c.name,
            'mukkadams':         len(c_mukkadam_ids),
            'weekly_paid':       float(c_weekly_paid),
            'settlement_paid':   float(c_settled),
            'settlement_pending': float(c_pending or 0),
            'weekly_due':        c_weekly_due,
            'total_outflow':     float(c_weekly_paid) + float(c_settled),
        })

    # ── 7. Recent weekly payments (last 15) ───────────────────────────────
    recent_weekly = MukkadamWeeklyPayment.objects.select_related(
        'assignment__mukkadam', 'assignment__cluster'
    ).order_by('-payment_date')[:15]

    recent_payments = []
    for w in recent_weekly:
        recent_payments.append({
            'mukkadam_name': w.assignment.mukkadam.mukkadam_name,
            'cluster_name':  w.assignment.cluster.name,
            'amount':        float(w.amount),
            'payment_date':  str(w.payment_date),
            'mode':          w.mode,
            'crew_size':     w.crew_size_on_date,
        })

    return Response({
        'today': str(today),
        'pipeline': {
            'weekly_due':           {'count': len(weekly_due_list),    'amount': weekly_due_amount},
            'settlement_pending':   {'count': len(settlement_list),    'amount': settlement_pending_amount},
            'total_paid_out':       {'count': active_count,            'amount': total_paid_out},
            'mukkadams_active':     {'count': active_count,            'amount': 0},
        },
        'weekly_due_list':      weekly_due_list,
        'settlement_list':      settlement_list,
        'verification_queue':   verification_queue,
        'cluster_billing':      cluster_billing,
        'recent_payments':      recent_payments,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def add_weekly_payment(request):
    from decimal import Decimal

    assignment_id = request.data.get('assignment_id')
    amount        = request.data.get('amount')
    payment_date  = request.data.get('payment_date')
    mode          = request.data.get('mode', 'CASH')
    notes         = request.data.get('notes', '')

    if not assignment_id or not amount or not payment_date:
        return Response({'error': 'assignment_id, amount and payment_date are required'}, status=400)

    try:
        assignment = ClusterMukkadamAssignment.objects.get(id=assignment_id)
    except ClusterMukkadamAssignment.DoesNotExist:
        return Response({'error': 'Assignment not found'}, status=404)

    weekly_payment, created = MukkadamWeeklyPayment.objects.get_or_create(
        assignment   = assignment,
        payment_date = payment_date,
        defaults={
            'amount':            Decimal(str(amount)),
            'crew_size_on_date': assignment.mukkadam.crew_size or 0,
            'is_auto_generated': False,
            'notes':             notes,
            'mode':              mode,
        }
    )

    if not created:
        return Response({'error': 'Weekly payment already recorded for this date'}, status=400)

    return Response({
        'success':      True,
        'message':      'Weekly payment recorded',
        'payment_date': str(weekly_payment.payment_date),
        'amount':       float(weekly_payment.amount),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_misc_cost(request, cost_id):
    from django.utils import timezone

    # Check admin role
    user = request.user
    if not user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=401)

    try:
        profile = user.profile
        if profile.role != 'admin':
            return Response({'error': 'Only admins can verify misc costs'}, status=403)
    except Exception:
        return Response({'error': 'User profile not found'}, status=403)

    try:
        cost = MukkadamMiscCost.objects.get(id=cost_id)
    except MukkadamMiscCost.DoesNotExist:
        return Response({'error': 'Misc cost not found'}, status=404)

    cost.verified    = True
    cost.verified_by = user
    cost.verified_at = timezone.now()
    cost.save(update_fields=['verified', 'verified_by', 'verified_at'])

    return Response({'success': True, 'message': 'Misc cost verified'})

import uuid
import boto3
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import requests

DEMAND_HEADERS = {
    'Authorization': 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704',
    'Content-Type':  'application/json',
}

# ── Helper: normalize phone ────────────────────────────────────────────────
def normalize_phone(phone):
    return phone if phone.startswith('91') else f'91{phone}'


def send_otp_to_phone(phone_normalized):
    """Fire OTP to given phone. Returns (success, error_msg)."""
    try:
        resp = requests.post(
            'https://demand.bharatintelligence.ai/otp/test/api/send-otp/',
            json={'phone_number': phone_normalized},
            headers=DEMAND_HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)


def verify_otp_with_demand(phone_normalized, otp):
    """Verify OTP with demand API. Returns (success, error_msg)."""
    try:
        resp = requests.post(
            'https://demand.bharatintelligence.ai/otp/test/api/verify-otp/',
            json={'phone_number': phone_normalized, 'otp': otp},
            headers=DEMAND_HEADERS,
            timeout=10
        )
        data = resp.json()
        if resp.status_code == 200 and data.get('success'):
            return True, None
        return False, data
    except Exception as e:
        return False, str(e)


# ── START OF WORK: OTP sent to FARMER's phone ─────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def send_start_otp(request):
    ctx(flow="send_start_otp",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    POST /api/attendance/send-start-otp/
    Mukkadam taps "Start Work" in app.
    OTP goes to FARMER's phone.
    Body: {
        "allocation_id": 456,
        "crew_size": 12
    }
    """
    allocation_id = request.data.get('allocation_id')
    crew_size     = request.data.get('crew_size')

    if not allocation_id or not crew_size:
        return Response({'error': 'allocation_id and crew_size required'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'mukkadam', 'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    if allocation.work_status == 'in_progress':
        return Response({'error': 'Work already in progress'}, status=400)

    # Get farmer's phone
    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))
    if not farmer_phone or farmer_phone == '91':
        return Response({'error': 'Farmer phone not found'}, status=400)

    ok, err = send_otp_to_phone(farmer_phone)
    if not ok:
        err("otp_send_fail",
        allocation_id=str(allocation_id),
        phone_hint=f"XXXXXX{str(farmer.phone_number)[-4:]}",
        error=str(err))
        return Response({'error': f'OTP service failed: {err}'}, status=503)

    # Store OTP request — phone is FARMER's phone
    MukkadamOTPRequest.objects.create(
        mukkadam   = allocation.mukkadam,
        phone      = farmer_phone,
        crew_size  = crew_size,
        allocation = allocation,
        otp_type   = 'start',   # ADD otp_type field to MukkadamOTPRequest
    )
    ops("start_otp_sent",
    allocation_id=str(allocation_id),
    mukkadam_name=allocation.mukkadam.mukkadam_name,
    farmer_name=farmer.farmer_name,
    phone_hint=f"XXXXXX{str(farmer.phone_number)[-4:]}")

    return Response({
        'success':        True,
        'message':        f'OTP sent to farmer ({farmer.farmer_name})',
        'allocation_id':  allocation_id,
        'mukkadam_name':  allocation.mukkadam.mukkadam_name,
        'farmer_name':    farmer.farmer_name,
        'farmer_phone_hint': f'XXXXXX{str(farmer.phone_number)[-4:]}',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_start_otp(request):
    ctx(flow="verify_start_otp",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    POST /api/attendance/verify-start-otp/
    Farmer shares OTP → mukkadam enters in app.
    Body: {
        "allocation_id": 456,
        "otp": "1234"
    }
    Work status → in_progress
    """
    allocation_id = request.data.get('allocation_id')
    otp           = request.data.get('otp', '').strip()

    if not allocation_id or not otp:
        return Response({'error': 'allocation_id and otp required'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))

    # Get latest unused start OTP request for this allocation
    otp_request = MukkadamOTPRequest.objects.filter(
        allocation = allocation,
        is_used    = False,
        otp_type   = 'start',
    ).order_by('-requested_at').first()

    if not otp_request:
        return Response({'error': 'No OTP request found. Please send OTP first.'}, status=400)

    if otp_request.is_expired():
        return Response({'error': 'OTP expired, please request again'}, status=400)

    ok, err = verify_otp_with_demand(farmer_phone, otp)
    if not ok:
        ops("start_otp_verify_failed",
        allocation_id=str(allocation_id),
        detail=str(err))
        return Response({'error': 'Invalid OTP', 'detail': err}, status=400)

    # Mark used
    otp_request.is_used = True
    otp_request.save(update_fields=['is_used'])

    # Update allocation — WORK STARTED
    allocation.actual_start_time = timezone.now()
    allocation.actual_crew_size  = otp_request.crew_size
    allocation.work_status       = 'in_progress'
    allocation.status            = 'in_progress'
    allocation.save(update_fields=['actual_start_time', 'actual_crew_size', 'work_status', 'status'])
    ops("work_started",
    allocation_id=str(allocation.id),
    mukkadam_name=allocation.mukkadam.mukkadam_name,
    start_time=allocation.actual_start_time.isoformat(),
    crew_size=str(allocation.actual_crew_size))

    return Response({
        'success':           True,
        'allocation_id':     allocation.id,
        'mukkadam_name':     allocation.mukkadam.mukkadam_name,
        'actual_start_time': allocation.actual_start_time.isoformat(),
        'actual_crew_size':  allocation.actual_crew_size,
        'work_status':       'in_progress',
    })


# ── END OF WORK: Mukkadam submits report + OTP goes to FARMER ────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def mark_allocation_complete(request, allocation_id):
    ctx(flow="mark_allocation_complete",
        allocation_id=str(allocation_id))
    try:
        allocation = Allocation.objects.select_related(
            'job_activity__activity',
            'job_activity__plot',
            'job_activity__job',
            'job_activity__job__farmer',
            'cluster',
            'mukkadam',
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    # ── Idempotent — already completed ───────────────────────────────
    if allocation.work_status == 'completed':
        return Response({'already_completed': True, 'allocation_id': allocation.id})

    mukkadam   = allocation.mukkadam
    actual_area = request.data.get('actual_area_done')
    actual_crew = request.data.get('actual_crew_size')

    from .updown import create_updown_settlement, _get_updown_assignment

    with transaction.atomic():
        update_fields = ['work_status', 'status']
        allocation.work_status = 'completed'
        allocation.status      = 'completed'

        if actual_area is not None:
            allocation.actual_area_done = Decimal(str(actual_area))
            update_fields.append('actual_area_done')
        if actual_crew is not None:
            allocation.actual_crew_size = int(actual_crew)
            update_fields.append('actual_crew_size')

        allocation.save(update_fields=update_fields)
        ops("allocation_marked_complete",
    allocation_id=str(allocation_id),
    mukkadam_name=mukkadam.mukkadam_name if mukkadam else "unknown",
    actual_area=str(actual_area or ""),
    actual_crew=str(actual_crew or ""),
    is_updown=str(bool(updown_assignment)))

        # ── Updown check via assignment (mukkadam_type is on assignment, not mukkadam model) ──
        updown_assignment = (
            _get_updown_assignment(mukkadam, cluster_id=allocation.cluster_id)
            if mukkadam else None
        )

        if updown_assignment:
            # Updown — create settlement directly, bypass signal
            settlement = create_updown_settlement(mukkadam, allocation, updown_assignment)
        elif mukkadam:
            # Permanent — set farmer_agreed to fire signal chain
            allocation.farmer_agreed = True
            allocation.save(update_fields=['farmer_agreed'])

    from .signals import allocation_completed

    # at the end of the with transaction.atomic() block:
    allocation_completed.send(sender=Allocation, allocation=allocation)
    return Response({'success': True, 'allocation_id': allocation.id})

@api_view(['POST'])
@permission_classes([AllowAny])
def submit_day_end_report(request):
    ctx(flow="submit_day_end_report",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    POST /api/attendance/submit-day-end-report/
    Mukkadam submits end-of-day data + triggers OTP to farmer.
    Body: {
        "allocation_id": 456,
        "actual_area_done": 2.5,
        "actual_crew_size": 12,
        "actual_end_time": "2025-03-01T17:30:00"   (optional, defaults to now)
    }
    work_status → completed (always)
    payment_status → dispute (until farmer verifies)
    """
    allocation_id    = request.data.get('allocation_id')
    actual_area_done = request.data.get('actual_area_done')
    actual_crew_size = request.data.get('actual_crew_size')
    actual_end_time  = request.data.get('actual_end_time')

    if not allocation_id or actual_area_done is None:
        return Response({'error': 'allocation_id and actual_area_done required'}, status=400)

    try:
        from decimal import Decimal
        allocation = Allocation.objects.select_related(
            'mukkadam', 'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    if allocation.work_status == 'work_not_started':
        return Response({'error': 'Work has not started yet'}, status=400)

    # Save mukkadam's claim
    from decimal import Decimal
    allocation.mukkadam_claimed_area = Decimal(str(actual_area_done))
    allocation.actual_area_done      = Decimal(str(actual_area_done))  # also set actual
    allocation.actual_crew_size      = actual_crew_size or allocation.actual_crew_size
    allocation.actual_end_time       = actual_end_time or timezone.now()
    allocation.report_submitted      = True
    allocation.report_submitted_at   = timezone.now()
    allocation.work_status           = 'completed'      # always completed
    allocation.payment_status        = 'dispute'        # until farmer verifies
    allocation.status                = 'completed'
    allocation.save(update_fields=[
        'mukkadam_claimed_area', 'actual_area_done', 'actual_crew_size',
        'actual_end_time', 'report_submitted', 'report_submitted_at',
        'work_status', 'payment_status', 'status'
    ])
    ops("day_end_report_submitted",
    allocation_id=str(allocation_id),
    mukkadam_name=allocation.mukkadam.mukkadam_name,
    actual_area=str(actual_area_done),
    actual_crew=str(actual_crew_size),
    work_status="completed",
    payment_status="dispute")

    # Send OTP to farmer's phone for end verification
    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))

    otp_sent = False
    if farmer_phone and farmer_phone != '91':
        ok, _ = send_otp_to_phone(farmer_phone)
        if ok:
            MukkadamOTPRequest.objects.create(
                mukkadam   = allocation.mukkadam,
                phone      = farmer_phone,
                crew_size  = allocation.actual_crew_size,
                allocation = allocation,
                otp_type   = 'end',
            )
            otp_sent = True
        ops("end_otp_sent" if otp_sent else "end_otp_send_skipped",
allocation_id=str(allocation_id),
farmer_name=farmer.farmer_name,
otp_sent=str(otp_sent))

    return Response({
        'success':             True,
        'allocation_id':       allocation.id,
        'work_status':         'completed',
        'payment_status':      'dispute',
        'mukkadam_claimed_area': float(allocation.mukkadam_claimed_area),
        'otp_sent_to_farmer':  otp_sent,
        'message': 'Report submitted. Work marked complete. OTP sent to farmer for verification.',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_end_otp(request):
    ctx(flow="verify_end_otp",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    POST /api/attendance/verify-end-otp/
    Farmer shares end-of-day OTP → mukkadam enters → payment_status = done
    Body: {
        "allocation_id": 456,
        "otp": "1234"
    }
    """
    allocation_id = request.data.get('allocation_id')
    otp           = request.data.get('otp', '').strip()

    if not allocation_id or not otp:
        return Response({'error': 'allocation_id and otp required'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    if allocation.work_status != 'completed':
        return Response({'error': 'Day-end report not submitted yet'}, status=400)

    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))

    otp_request = MukkadamOTPRequest.objects.filter(
        allocation = allocation,
        is_used    = False,
        otp_type   = 'end',
    ).order_by('-requested_at').first()

    if not otp_request:
        return Response({'error': 'No end OTP request found'}, status=400)

    if otp_request.is_expired():
        return Response({'error': 'OTP expired, please request again'}, status=400)

    ok, err = verify_otp_with_demand(farmer_phone, otp)
    if not ok:
        ops("end_otp_verify_failed",
        allocation_id=str(allocation_id),
        detail=str(err))
        return Response({'error': 'Invalid OTP', 'detail': err}, status=400)

    # Mark used
    otp_request.is_used = True
    otp_request.save(update_fields=['is_used'])

    # FARMER AGREED — payment_status = done
    allocation.farmer_agreed         = True
    allocation.farmer_response_at    = timezone.now()
    allocation.use_actual_for_settlement = True
    allocation.payment_status        = 'done'
    allocation.save(update_fields=[
        'farmer_agreed', 'farmer_response_at',
        'use_actual_for_settlement', 'payment_status'
    ])
    ops("farmer_verified_end",
    allocation_id=str(allocation_id),
    payment_status="done",
    area_used=str(float(allocation.actual_area_done or allocation.allocated_area)))

    # Trigger settlement recalculation
    try:
        from .ervices.settlement import create_or_update_settlement
        job     = allocation.job_activity.job
        cluster = allocation.cluster
        create_or_update_settlement(allocation.mukkadam, job, cluster)
    except Exception:
        err("end_otp_settlement_fail",
        allocation_id=str(allocation_id))
        pass  # Don't fail the response if settlement calc fails

    return Response({
        'success':        True,
        'allocation_id':  allocation.id,
        'payment_status': 'done',
        'message':        'Farmer verified. Payment status marked as done.',
    })


# ── DISPUTE OVERRIDE: Team fills farmer's actual claim ────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])  # Add IsAuthenticated in production
def resolve_dispute(request):
    """
    POST /api/attendance/resolve-dispute/
    Team calls farmer, fills what farmer says, unlocks billing.
    Body: {
        "allocation_id": 456,
        "farmer_claimed_area": 2.0,
        "dispute_reason": "Farmer says only 2 acres were done due to water logging"
    }
    Sets admin_override_area → billing uses this for both farmer + mukkadam.
    payment_status stays dispute (for tracking) but billing is unlocked.
    """
    allocation_id       = request.data.get('allocation_id')
    farmer_claimed_area = request.data.get('farmer_claimed_area')
    dispute_reason      = request.data.get('dispute_reason', '')

    if not allocation_id or farmer_claimed_area is None:
        return Response({'error': 'allocation_id and farmer_claimed_area required'}, status=400)

    try:
        from decimal import Decimal
        allocation = Allocation.objects.select_related(
            'job_activity__job', 'mukkadam'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    from decimal import Decimal
    allocation.admin_override_area = Decimal(str(farmer_claimed_area))
    allocation.actual_area_done    = Decimal(str(farmer_claimed_area))  # use override for billing
    allocation.dispute_reason      = dispute_reason
    allocation.dispute_resolved_at = timezone.now()
    allocation.farmer_agreed       = False   # still marked as farmer did not directly verify
    allocation.use_actual_for_settlement = True   # unlock billing with override area
    # payment_status stays 'dispute' — clearly shows it was a dispute case
    allocation.save(update_fields=[
        'admin_override_area', 'actual_area_done', 'dispute_reason',
        'dispute_resolved_at', 'farmer_agreed', 'use_actual_for_settlement'
    ])

    # Recalculate settlement
    try:
        from .ervices.settlement import create_or_update_settlement
        job     = allocation.job_activity.job
        cluster = allocation.cluster
        create_or_update_settlement(allocation.mukkadam, job, cluster)
    except Exception:
        pass

    return Response({
        'success':            True,
        'allocation_id':      allocation.id,
        'admin_override_area': float(allocation.admin_override_area),
        'payment_status':     'dispute',
        'message':            'Dispute resolved. Billing unlocked with farmer-claimed area.',
    })


# ── PRESIGN URL for payment proof upload ──────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])  # Add auth in production
def get_payment_proof_presign(request):
    """
    POST /api/payments/proof-presign/
    Body: {
        "file_name": "payment_receipt.jpg",
        "proof_type": "farmer",   // farmer | mukkadam | weekly
        "reference_id": 123
    }
    Returns presigned PUT URL + the S3 key to store.
    """
    file_name    = request.data.get('file_name', '').strip()
    proof_type   = request.data.get('proof_type', 'farmer')
    reference_id = request.data.get('reference_id')

    if not file_name:
        return Response({'error': 'file_name required'}, status=400)

    ext    = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else 'jpg'
    key    = f"payment_proofs/{proof_type}/{reference_id or 'unknown'}/{uuid.uuid4()}.{ext}"

    CONTENT_TYPE_MAP = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'pdf': 'application/pdf',
        'webp': 'image/webp',
    }
    content_type = CONTENT_TYPE_MAP.get(ext, 'application/octet-stream')

    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id     = settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY,
            region_name           = settings.AWS_S3_REGION_NAME,
        )
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket':      settings.AWS_STORAGE_BUCKET_NAME,
                'Key':         key,
                'ContentType': content_type,
            },
            ExpiresIn=300,  # 5 minutes
        )
    except Exception as e:
        return Response({'error': f'S3 error: {str(e)}'}, status=500)

    return Response({
        'presigned_url': presigned_url,
        's3_key':        key,
        'content_type':  content_type,
        'expires_in':    300,
    })

# Add these 2 views to your attendance/views.py (or wherever your attendance APIs live)
# URLs go in tender/urls.py:
#   path('api/attendance/send-farmer-otp/', send_farmer_otp, name='send_farmer_otp'),
#   path('api/attendance/verify-farmer-otp/', verify_farmer_otp, name='verify_farmer_otp'),

import random
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

# Add to tender/urls.py:
#   path('api/attendance/send-farmer-otp/', send_farmer_otp),
#   path('api/attendance/verify-farmer-otp/', verify_farmer_otp),


@api_view(['POST'])
@permission_classes([AllowAny])
def send_farmer_otp(request):
    ctx(flow="send_farmer_otp",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    BI team resends end-OTP to farmer from the dashboard.
    Uses the exact same flow as submit_day_end_report.
    POST: { allocation_id: int }
    """
    allocation_id = request.data.get('allocation_id')
    if not allocation_id:
        return Response({'error': 'allocation_id required'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'mukkadam', 'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))

    if not farmer_phone or farmer_phone == '91':
        return Response({'error': 'Farmer has no valid phone number'}, status=400)

    # Send OTP using existing function — same as submit_day_end_report
    ok, err = send_otp_to_phone(farmer_phone)
    if not ok:
        err("farmer_otp_send_fail",
        allocation_id=str(allocation_id),
        error=str(err))
        return Response({'error': f'OTP send failed: {err}'}, status=500)

    # Create OTP request record — same as submit_day_end_report
    MukkadamOTPRequest.objects.create(
        mukkadam   = allocation.mukkadam,
        phone      = farmer_phone,
        crew_size  = allocation.actual_crew_size or allocation.allocated_workers,
        allocation = allocation,
        otp_type   = 'end',
    )
    ops("farmer_otp_sent",
    allocation_id=str(allocation_id),
    farmer_name=farmer.farmer_name,
    phone_hint=f"******{farmer_phone[-4:]}")

    return Response({
        'success': True,
        'message': f'OTP sent to farmer {farmer.farmer_name}',
        'phone_masked': f'******{farmer_phone[-4:]}',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_farmer_otp(request):
    ctx(flow="verify_farmer_otp",
        allocation_id=str(request.data.get('allocation_id', '')))
    """
    BI team enters OTP that farmer shared verbally — same verification as verify_end_otp.
    On success: farmer_agreed=True, payment_status=done, triggers settlement.
    POST: { allocation_id: int, otp: str, farmer_id: str }
    """
    allocation_id = request.data.get('allocation_id')
    otp           = str(request.data.get('otp', '')).strip()

    if not allocation_id or not otp:
        return Response({'error': 'allocation_id and otp required'}, status=400)

    try:
        allocation = Allocation.objects.select_related(
            'mukkadam', 'job_activity__job__farmer'
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return Response({'error': 'Allocation not found'}, status=404)

    farmer = allocation.job_activity.job.farmer
    farmer_phone = normalize_phone(str(farmer.phone_number or ''))

    # Find latest unused end OTP — same as verify_end_otp
    otp_request = MukkadamOTPRequest.objects.filter(
        allocation = allocation,
        is_used    = False,
        otp_type   = 'end',
    ).order_by('-requested_at').first()

    if not otp_request:
        return Response({'error': 'No OTP found. Please send OTP first.'}, status=400)

    if otp_request.is_expired():
        return Response({'error': 'OTP expired. Please resend.'}, status=400)

    # Verify using existing function — same as verify_end_otp
    ok, err = verify_otp_with_demand(farmer_phone, otp)
    if not ok:
        ops("farmer_otp_verify_failed",
        allocation_id=str(allocation_id),
        detail=str(err))
        return Response({'error': 'Invalid OTP', 'detail': err}, status=400)

    # Mark OTP used
    otp_request.is_used = True
    otp_request.save(update_fields=['is_used'])

    # Mark farmer agreed — exactly same as verify_end_otp
    allocation.farmer_agreed             = True
    allocation.farmer_response_at        = timezone.now()
    allocation.use_actual_for_settlement = True
    allocation.payment_status            = 'done'
    allocation.save(update_fields=[
        'farmer_agreed', 'farmer_response_at',
        'use_actual_for_settlement', 'payment_status',
    ])
    ops("farmer_otp_verified",
    allocation_id=str(allocation_id),
    payment_status="done",
    area_used=str(float(allocation.actual_area_done or allocation.allocated_area)))

    # Trigger settlement recalculation — same as verify_end_otp
    try:
        from .ervices.settlement import create_or_update_settlement
        job     = allocation.job_activity.job
        cluster = allocation.cluster
        create_or_update_settlement(allocation.mukkadam, job, cluster)
    except Exception:
        err("farmer_otp_settlement_fail",
        allocation_id=str(allocation_id))
        pass

    return Response({
        'success':        True,
        'allocation_id':  allocation_id,
        'payment_status': 'done',
        'area_used':      float(allocation.actual_area_done or allocation.allocated_area),
        'message':        'Farmer verified. Payment status marked as done.',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def save_payment_proof(request):
    """
    POST /api/payments/save-proof/
    After S3 upload completes, save the reference.
    Body: {
        "proof_type": "farmer",
        "reference_id": 123,
        "s3_key": "payment_proofs/farmer/123/uuid.jpg",
        "file_name": "receipt.jpg"
    }
    """
    proof_type   = request.data.get('proof_type')
    reference_id = request.data.get('reference_id')
    s3_key       = request.data.get('s3_key')
    file_name    = request.data.get('file_name', '')

    if not all([proof_type, reference_id, s3_key]):
        return Response({'error': 'proof_type, reference_id, s3_key required'}, status=400)

    # Build public/presigned URL for display
    s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{s3_key}"

    proof = PaymentProof.objects.create(
        proof_type   = proof_type,
        reference_id = reference_id,
        s3_key       = s3_key,
        s3_url       = s3_url,
        file_name    = file_name,
        uploaded_by  = request.user if request.user.is_authenticated else None,
    )

    return Response({
        'success':  True,
        'proof_id': proof.id,
        's3_url':   s3_url,
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def farmer_work_verification_detail(request):
    """
    GET /api/farmer/verify-work/?farmer_id=F-001&job_id=JOB-001

    Farmer sees all mukkadam day-end reports for their job,
    with current verification status, so they can agree or dispute.
    """
    farmer_id = request.query_params.get('farmer_id', '').strip()
    job_id = request.query_params.get('job_id', '').strip()

    if not farmer_id or not job_id:
        return Response(
            {'error': 'farmer_id and job_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify job belongs to farmer
    try:
        job = Job.objects.select_related(
            'farmer', 'plot'
        ).get(
            job_id=job_id,
            farmer__farmer_id=farmer_id
        )
    except Job.DoesNotExist:
        return Response(
            {'error': 'Job not found or does not belong to this farmer'},
            status=status.HTTP_404_NOT_FOUND
        )

    # All allocations for this job
    allocations = Allocation.objects.filter(
        job_activity__job=job
    ).select_related(
        'mukkadam',
        'job_activity__activity',
        'job_activity__plot',
    ).order_by('allocated_date')

    pending_count = 0
    agreed_count = 0
    disputed_count = 0
    not_submitted_count = 0

    reports = []
    for alloc in allocations:
        ja = alloc.job_activity

        # Verification status label
        if not alloc.report_submitted:
            verify_status = 'not_submitted'
            not_submitted_count += 1
        elif alloc.farmer_agreed is None:
            verify_status = 'pending_your_response'
            pending_count += 1
        elif alloc.farmer_agreed:
            verify_status = 'agreed'
            agreed_count += 1
        else:
            verify_status = 'disputed'
            disputed_count += 1

        # Area comparison for farmer to see
        area_diff = None
        area_diff_pct = None
        if alloc.report_submitted and alloc.actual_area_done:
            area_diff = round(
                float(alloc.actual_area_done) - float(alloc.allocated_area), 2
            )
            if float(alloc.allocated_area) > 0:
                area_diff_pct = round(
                    (area_diff / float(alloc.allocated_area)) * 100, 1
                )

        reports.append({
            'allocation_id': alloc.id,

            # What was planned
            'planned': {
                'activity_name': ja.activity.name,
                'plot_name': ja.plot.name if ja.plot else None,
                'plot_code': ja.plot.plot_code if ja.plot else None,
                'allocated_date': str(alloc.allocated_date),
                'allocated_area': float(alloc.allocated_area),
                'allocated_workers': alloc.allocated_workers,
                'farmer_rate': float(alloc.farmer_rate),
                'planned_farmer_amount': float(alloc.farmer_amount),
            },

            # What mukkadam reported
            'mukkadam_report': {
                'submitted': alloc.report_submitted,
                'submitted_at': alloc.report_submitted_at.isoformat() if alloc.report_submitted_at else None,
                'mukkadam_name': alloc.mukkadam.mukkadam_name,
                'mukkadam_mobile': alloc.mukkadam.mobile_numbers,
                'actual_start_time': alloc.actual_start_time.isoformat() if alloc.actual_start_time else None,
                'actual_end_time': alloc.actual_end_time.isoformat() if alloc.actual_end_time else None,
                'actual_crew_size': alloc.actual_crew_size,
                'actual_area_done': float(alloc.actual_area_done) if alloc.actual_area_done else None,
            },

            # Difference — so farmer can spot discrepancy
            'comparison': {
                'area_planned': float(alloc.allocated_area),
                'area_done': float(alloc.actual_area_done) if alloc.actual_area_done else None,
                'area_difference': area_diff,          # negative = less done
                'area_difference_pct': area_diff_pct,  # negative = underdelivered
                'crew_planned': alloc.allocated_workers,
                'crew_actual': alloc.actual_crew_size,
                # Recalculated farmer amount based on actual area
                'revised_farmer_amount': round(
                    float(alloc.actual_area_done) * float(alloc.farmer_rate), 2
                ) if alloc.actual_area_done else None,
                'original_farmer_amount': float(alloc.farmer_amount),
                'amount_difference': round(
                    float(alloc.actual_area_done) * float(alloc.farmer_rate)
                    - float(alloc.farmer_amount), 2
                ) if alloc.actual_area_done else None,
            },

            # Farmer's response
            'farmer_response': {
                'status': verify_status,
                'agreed': alloc.farmer_agreed,
                'responded_at': alloc.farmer_response_at.isoformat() if alloc.farmer_response_at else None,
                'dispute_reason': alloc.farmer_dispute_reason or None,
                'use_actual_for_settlement': alloc.use_actual_for_settlement,
            },

            # Action hint for frontend
            'action_required': verify_status == 'pending_your_response',
        })

    # Job level summary
    total_planned_amount = sum(r['planned']['planned_farmer_amount'] for r in reports)
    total_revised_amount = sum(
        r['comparison']['revised_farmer_amount']
        for r in reports
        if r['comparison']['revised_farmer_amount'] is not None
    )

    return Response({
        'job': {
            'job_id': job.job_id,
            'farmer_name': job.farmer.farmer_name,
            'farmer_id': job.farmer.farmer_id,
            'crop_name': job.crop_name,
            'variety': job.variety,
            'plot_name': job.plot.name if job.plot else None,
            'job_status': job.status,
        },

        'summary': {
            'total_allocations': len(reports),
            'not_submitted': not_submitted_count,
            'pending_your_response': pending_count,
            'agreed': agreed_count,
            'disputed': disputed_count,
            'total_planned_farmer_amount': round(total_planned_amount, 2),
            'total_revised_farmer_amount': round(total_revised_amount, 2),
            'net_amount_difference': round(total_revised_amount - total_planned_amount, 2),
        },

        'reports': reports,
    })



from rest_framework.decorators import api_view
from datetime import datetime, timedelta
from .exotel_services import ExotelService

from rest_framework.views import APIView
class MakeCallViews(APIView):
    """
    Web dialpad - Call any number using central Exotel number
    """
    permission_classes = [AllowAny]
    
    CENTRAL_PHONE = '+918047361465'

    
    def post(self, request):
        ctx(flow="make_call",
        user_id=str(request.data.get('user_id', 'anon')),
        purpose=str(request.data.get('purpose', 'web_dialpad')))
        to_number = request.data.get('to_number')
        from_number = request.data.get('from_number') or self.CENTRAL_PHONE

        user_id = request.data.get('user_id')
        username = request.data.get('username', 'web_dialpad')
        purpose = request.data.get('purpose', 'web_dialpad')
        notes = request.data.get('notes', '')
        
        if not to_number:
            return Response({
                'success': False,
                'message': 'Phone number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ Clean and add +91 if missing
        to_number = to_number.replace(' ', '').replace('-', '')
        if not to_number.startswith('+'):
            to_number = f'+91{to_number}'  # Add +91 prefix
        
        from_number = from_number.replace(' ', '').replace('-', '')
        if not from_number.startswith('+'):
            from_number = f'+91{from_number}'

        try:
            # 1️⃣ Make the call via Exotel
            exotel = ExotelService()
            call_result = exotel.make_call(
                    from_number='8209818471',  # ← not self.CENTRAL_PHONE
                    to_number=to_number,
                )

            
            if not call_result['success']:
                err("exotel_call_fail",
        to_number=to_number,
        user_id=str(user_id),
        error=str(call_result.get('error', '')))
                return Response({
                    'success': False,
                    'message': 'Failed to initiate call',
                    'error': call_result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 2️⃣ Save call record
            call_data = {
                'call_sid': call_result['call_sid'],
                'mobile_number': to_number,
                'from_number': from_number,
                'purpose': purpose,
                'status': call_result.get('status', 'pending'),
                'notes': notes,
                'direction': 'outbound',
                'user_id': user_id or 'anonymous',
                'created_by': request.user if request.user.is_authenticated else None,
                
            }
            
            call = FarmerCall.objects.create(**call_data)
            ops("call_initiated",
    call_sid=call_result['call_sid'],
    call_id=str(call.id),
    to_number=to_number,
    from_number=from_number,
    purpose=purpose,
    user_id=str(user_id or 'anon'))
            
            logger.info(f"✅ Web dialpad call by user {user_id}: {call.call_sid} → {to_number}")
            logger.info(f"   S3 Key stored: {call.s3_key}")
            
            return Response({
                'success': True,
                'message': 'Calling...',
                'call_sid': call_result['call_sid'],
                'call_id': call.id,
                'to': to_number,
               
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ Error making call: {str(e)}", exc_info=True)
            err("make_call_fail",
        to_number=to_number,
        user_id=str(user_id or 'anon'),
        error=str(e)[:100])
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def pay_mukkadam_settlement(request, mukkadam_id, job_id):
    mode  = request.data.get('mode', 'CASH')
    notes = request.data.get('notes', '')

    # Support updown mukkadams: multiple settlements per job — pay first unpaid one
    try:
        settlement = MukkadamJobSettlement.objects.filter(
            mukkadam_id=mukkadam_id, job__job_id=job_id, status='calculated'
        ).first()
        if not settlement:
            # Check if already paid
            already = MukkadamJobSettlement.objects.filter(
                mukkadam_id=mukkadam_id, job__job_id=job_id, status='paid'
            ).exists()
            if already:
                return Response({'error': 'Already paid'}, status=400)
            return Response({'error': 'Settlement not found'}, status=404)
    except Exception:
        return Response({'error': 'Settlement not found'}, status=404)

    import time
    from django.utils import timezone

    payment = MukkadamPayment.objects.create(
        mukkadam   = settlement.mukkadam,
        settlement = settlement,
        payment_id = str(int(time.time() * 1000)),
        mode       = mode,
        amount     = settlement.net_payable,
        notes      = notes,
        paid_at    = timezone.now(),
    )

    settlement.status  = 'paid'
    settlement.paid_at = timezone.now()
    settlement.save(update_fields=['status', 'paid_at'])

    return Response({
        'message':    f'Payment of ₹{settlement.net_payable} recorded for {settlement.mukkadam.mukkadam_name}',
        'payment_id': payment.id,
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def add_misc_cost(request, mukkadam_id, job_id):
    amount       = request.data.get('amount')
    reason       = request.data.get('reason', '').strip()
    proof_s3_key = request.data.get('proof_s3_key')

    if not amount or float(amount) <= 0:
        return Response({'error': 'Valid amount required'}, status=400)
    if not reason:
        return Response({'error': 'Reason is required'}, status=400)
    try:
        mukkadam = Mukkadam.objects.get(id=mukkadam_id)
        job      = Job.objects.get(job_id=job_id)
    except (Mukkadam.DoesNotExist, Job.DoesNotExist):
        return Response({'error': 'Mukkadam or Job not found'}, status=404)

    from decimal import Decimal
    cost = MukkadamMiscCost.objects.create(
        mukkadam     = mukkadam,
        job          = job,
        amount       = Decimal(str(amount)),
        reason       = reason,
        proof_s3_key = proof_s3_key or None,
    )

    _recalculate_settlement_misc(mukkadam, job)

    return Response({
        'id':         cost.id,
        'amount':     float(cost.amount),
        'reason':     cost.reason,
        'created_at': str(cost.created_at),
    })




from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
import django.db.models as models


def get_effective_area_for_mukkadam(allocation):
    """Get the area to use for mukkadam billing."""
    if (allocation.payment_status == 'dispute'
            and not allocation.admin_override_area
            and not allocation.use_actual_for_settlement):
        return Decimal('0')
    if allocation.admin_override_area:
        return allocation.admin_override_area
    elif allocation.use_actual_for_settlement and allocation.actual_area_done:
        return allocation.actual_area_done
    return allocation.allocated_area


def is_shoot_selection_activity(activity_name):
    name = (activity_name or '').lower()
    return 'shoot' in name and ('select' in name or 'विरळणी' in name)


@transaction.atomic
def recalculate_settlement_for_allocation(allocation):
    """
    Called whenever an allocation is verified by farmer (farmer_agreed=True set).
    
    Checks:
    1. Is this the shoot selection activity? → trigger shoot billing
    2. Are ALL activities now done? → trigger deposit release + post-shoot billing
    3. Neither → just update gross on existing settlement if it exists
    
    Returns: (settlement, event_type)
    """
    from tender.models import (
        MukkadamJobSettlement, MukkadamWeeklyPayment,
        MukkadamAssignment, Allocation
    )

    job         = allocation.job_activity.job
    mukkadam    = allocation.mukkadam
    assignment  = MukkadamAssignment.objects.filter(
        mukkadam=mukkadam,
        cluster=job.cluster,
        is_active=True
    ).first()

    if not assignment:
        return None, 'no_assignment'

    activity_name = allocation.job_activity.activity_name or ''
    is_shoot = is_shoot_selection_activity(activity_name)

    # Get ALL completed + verified allocations for this job/mukkadam
    completed_allocs = Allocation.objects.filter(
        job_activity__job=job,
        mukkadam=mukkadam,
        work_status='completed',
    ).filter(
        models.Q(farmer_agreed=True) | models.Q(admin_override_area__isnull=False)
    )

    # Are ALL allocations for this job done?
    all_allocs = Allocation.objects.filter(
        job_activity__job=job,
        mukkadam=mukkadam,
    )
    all_done = all_allocs.exists() and all(
        a.work_status == 'completed' for a in all_allocs
    )

    # Total gross now
    current_gross = sum(
        get_effective_area_for_mukkadam(a) * a.mukkadam_rate
        for a in completed_allocs
    ).quantize(Decimal('0.01'))

    # Get or create settlement
    settlement = MukkadamJobSettlement.objects.filter(
        job=job, mukkadam=mukkadam, assignment=assignment
    ).first()

    # ── CASE 1: Shoot selection just completed ─────────────────────────────
    if is_shoot:
        if settlement and settlement.status not in ('pending', None):
            # Already calculated — do nothing (shoot happened before)
            pass
        else:
            # First billing event
            settlement, _ = MukkadamJobSettlement.objects.get_or_create(
                job=job, mukkadam=mukkadam, assignment=assignment,
                defaults={'status': 'pending', 'gross_amount': Decimal('0')}
            )

            deposit = (current_gross * Decimal('0.1')).quantize(Decimal('0.01'))
            payable_90 = current_gross - deposit

            advance_deduct, weekly_deduct, credit_prev, deposit_prev = \
                _get_cross_job_deductions(mukkadam, assignment, job)

            net = payable_90 + deposit_prev - advance_deduct - weekly_deduct - credit_prev

            settlement.gross_amount              = current_gross
            settlement.gross_at_shoot_selection  = current_gross
            settlement.post_shoot_gross          = Decimal('0')
            settlement.deposit_held              = deposit
            settlement.payable_amount            = payable_90
            settlement.advance_deducted          = advance_deduct
            settlement.weekly_payments_deducted  = weekly_deduct
            settlement.deposit_carried_forward   = deposit_prev
            settlement.credit_carried_forward    = Decimal('0')
            settlement.net_payable               = net
            settlement.status                    = 'calculated' if net > Decimal('0') else 'no_payment_needed'
            settlement.calculated_at             = timezone.now()
            settlement.save()

            return settlement, 'shoot_billing'

    # ── CASE 2: All activities done (deposit release + post-shoot billing) ──
    if all_done and settlement and settlement.status not in ('pending', None):
        old_deposit   = settlement.deposit_held
        old_gross     = settlement.gross_at_shoot_selection or settlement.gross_amount
        post_shoot    = current_gross - old_gross

        if old_deposit == Decimal('0') and post_shoot == Decimal('0'):
            return settlement, 'no_change'   # Already processed

        additional_payable = post_shoot + old_deposit  # post-shoot work (100%) + released deposit

        settlement.gross_amount        = current_gross
        settlement.post_shoot_gross    = post_shoot
        settlement.deposit_held        = Decimal('0')        # released
        settlement.payable_amount     += additional_payable
        settlement.net_payable        += additional_payable
        settlement.all_activities_done_at = timezone.now()

        if settlement.net_payable > Decimal('0'):
            settlement.status = 'calculated'

        settlement.save()
        return settlement, 'deposit_release'

    # ── CASE 3: Non-shoot activity done, settlement exists — update gross ──
    if settlement and settlement.status not in ('pending', None):
        # Update gross but don't change payable yet (shoot selection is the trigger)
        settlement.gross_amount = current_gross
        settlement.save()
        return settlement, 'gross_updated'

    return settlement, 'no_change'


def _get_cross_job_deductions(mukkadam, assignment, current_job):
    """
    Returns (advance_to_deduct, weekly_to_deduct, credit_from_prev, deposit_from_prev)
    after accounting for amounts already absorbed by previous settlements.
    """
    from tender.models import MukkadamJobSettlement, MukkadamWeeklyPayment

    total_advance = Decimal(str(assignment.advance_amount or 0))
    total_weekly = MukkadamWeeklyPayment.objects.filter(
        assignment=assignment
    ).aggregate(t=models.Sum('amount'))['t'] or Decimal('0')

    prev = MukkadamJobSettlement.objects.filter(
        assignment=assignment
    ).exclude(job=current_job).exclude(status='pending').order_by('calculated_at')

    adv_used    = sum(Decimal(str(s.advance_deducted or 0)) for s in prev)
    weekly_used = sum(Decimal(str(s.weekly_payments_deducted or 0)) for s in prev)

    last = prev.last()
    credit_prev  = Decimal(str(last.credit_carried_forward or 0)) if last else Decimal('0')
    deposit_prev = Decimal(str(last.deposit_carried_forward or 0)) if last else Decimal('0')

    advance_to_deduct = max(Decimal('0'), total_advance - adv_used)
    weekly_to_deduct  = max(Decimal('0'), total_weekly - weekly_used)

    return advance_to_deduct, weekly_to_deduct, credit_prev, deposit_prev


# views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json, hmac, hashlib

# ============================================================================
# GOOGLE SHEETS → DJANGO WEBHOOK
# ============================================================================
# Add this to your views.py (REPLACE the old sync_from_sheet view)
# Also add to urls.py:
#     path('api/sync-from-sheet/', sync_from_sheet, name='sync_from_sheet'),
# ============================================================================

import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


@csrf_exempt
def sync_from_sheet(request):
    """
    Webhook endpoint called by Google Apps Script when a cell is edited.

    Expects POST with JSON body:
    {
        "secret": "your_shared_secret",
        "event": "edit" | "delete",
        "job_activity_id": "123",
        "column": "Our date",
        "old_value": "2025-06-01",
        "new_value": "2025-06-05",
        "edited_by": "user@example.com"
    }

    For row deletion:
    {
        "secret": "your_shared_secret",
        "event": "delete",
        "job_activity_id": "123",
        "edited_by": "user@example.com"
    }

    For bulk edits (multiple columns changed at once):
    {
        "secret": "your_shared_secret",
        "event": "bulk_edit",
        "job_activity_id": "123",
        "changes": {
            "Our date": "2025-06-05",
            "Mukadam team": "Raju, Shyam"
        },
        "edited_by": "user@example.com"
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    # ── Auth ──
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    
    # ── Route by event type ──
    event = data.get("event", "edit")

    try:
        from .sheets_sync import apply_sheet_edit

        if event == "delete":
            payload = {
                "job_activity_id": data.get("job_activity_id"),
                "column": "_DELETE_",
                "new_value": "",
                "old_value": "",
                "edited_by": data.get("edited_by", "sheet"),
            }
            ok, msg = apply_sheet_edit(payload)
            return JsonResponse({"success": ok, "message": msg},
                                status=200 if ok else 400)

        elif event == "bulk_edit":
            changes = data.get("changes", {})
            results = []
            for col, new_val in changes.items():
                payload = {
                    "job_activity_id": data.get("job_activity_id"),
                    "column": col,
                    "new_value": new_val,
                    "old_value": "",
                    "edited_by": data.get("edited_by", "sheet"),
                }
                ok, msg = apply_sheet_edit(payload)
                results.append({"column": col, "success": ok, "message": msg})
            all_ok = all(r["success"] for r in results)
            return JsonResponse({"success": all_ok, "results": results},
                                status=200 if all_ok else 207)
        elif event == "split":
            # new_value = split_acres, split_date is a separate field
            payload = {
                "event": "split",
                "job_activity_id": data.get("job_activity_id"),
                "column": "Acre",           # for logging clarity
                "new_value": data.get("split_acres", ""),
                "old_value": "",
                "split_date": data.get("split_date", ""),
                "edited_by": data.get("edited_by", "sheet"),
            }
            ok, msg = apply_sheet_edit(payload)
            return JsonResponse({"success": ok, "message": msg},
                                status=200 if ok else 400)
        else:  # single "edit"
            payload = {
                "job_activity_id": data.get("job_activity_id"),
                "column": data.get("column", ""),
                "new_value": data.get("new_value", ""),
                "old_value": data.get("old_value", ""),
                "edited_by": data.get("edited_by", "sheet"),
            }
            ok, msg = apply_sheet_edit(payload)
            return JsonResponse({"success": ok, "message": msg},
                                status=200 if ok else 400)

    except Exception as e:
        logger.error(f"[Sheet→DB webhook] Unhandled error: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def _update_from_sheet(row):
    """
    Sheet can update: Our date, Status, notes on JobActivity.
    Looks up by _job_activity_id (hidden column O in sheet).
    """
    from .models import JobActivity
    import threading

    ja_id = row.get("_job_activity_id")
    if not ja_id:
        logger.warning("[Webhook] No _job_activity_id in row, skipping")
        return

    try:
        ja = JobActivity.objects.get(pk=ja_id)
    except JobActivity.DoesNotExist:
        logger.warning(f"[Webhook] JobActivity {ja_id} not found")
        return

    updated_fields = []

    # Our date → scheduled_date
    our_date = row.get("Our date", "").strip()
    if our_date:
        from datetime import date
        try:
            ja.scheduled_date = date.fromisoformat(our_date)
            updated_fields.append("scheduled_date")
        except ValueError:
            pass

    if updated_fields:
        # Set flag to prevent signal loop
        import tender.signals as sig
        sig._syncing.active = True
        try:
            ja.save(update_fields=updated_fields + ["updated_at"])
        finally:
            sig._syncing.active = False

        logger.info(f"[Webhook] Updated JA {ja_id} fields: {updated_fields}")
def _update_job_from_sheet(row):
    from .models import Job
    job_id = row.get("job_id")
    if not job_id:
        return
    Job.objects.filter(job_id=job_id).update(
        status=row.get("status", "pending"),
        priority=row.get("priority", "MEDIUM"),
        payment_status=row.get("payment_status", "pending"),
    )

def _update_farmer_from_sheet(row):
    from .models import Farmer
    Farmer.objects.filter(farmer_id=row.get("farmer_id")).update(
        farmer_name=row.get("farmer_name", ""),
        phone_number=row.get("phone_number", ""),
    )


@csrf_exempt
def split_from_sheet(request):
    """
    Called by Apps Script to split a JobActivity into two.
    Delegates entirely to the existing JobActivityViewSet.move() logic.

    POST body:
    {
        "job_activity_id": "42",
        "split_acres":     "1",
        "split_date":      "2025-07-02",
        "reason":          "Split via sheet by user@gmail.com",
        "edited_by":       "user@gmail.com"
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    secret = request.headers.get("X-Webhook-Secret", "")
    if secret != settings.SHEETS_WEBHOOK_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    ja_id       = data.get("job_activity_id")
    split_acres = data.get("split_acres", "")
    split_date  = data.get("split_date", "")
    edited_by   = data.get("edited_by", "sheet")
    reason      = data.get("reason") or f"Split via Google Sheet by {edited_by}"

    if not ja_id or not split_acres or not split_date:
        return JsonResponse({"error": "job_activity_id, split_acres and split_date are required"}, status=400)

    # ── Reuse the move() logic directly ──────────────────────────────────────
    from .models import JobActivity
    from decimal import Decimal
    from datetime import date
    from django.db import transaction
    from django.utils import timezone

    try:
        activity = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters")
            .get(pk=int(ja_id))
        )
    except (JobActivity.DoesNotExist, ValueError):
        return JsonResponse({"error": f"JobActivity {ja_id} not found"}, status=404)

    try:
        area = Decimal(str(split_acres).strip())
    except Exception:
        return JsonResponse({"error": f"Invalid split_acres: {split_acres}"}, status=400)

    if area <= 0:
        return JsonResponse({"error": "split_acres must be > 0"}, status=400)

    if area >= activity.total_area:
        return JsonResponse({
            "error": f"split_acres ({area}) must be less than total_area ({activity.total_area})"
        }, status=400)

    try:
        new_date_obj = date.fromisoformat(str(split_date).strip())
    except ValueError:
        return JsonResponse({"error": f"Invalid split_date: {split_date}. Use YYYY-MM-DD"}, status=400)

    # ── Build a fake request object the move() helper can work with ──────────
    # Instead of duplicating all the move() code, we call it via a mock request.
    # Simpler: just inline the core logic (no cascade needed from sheet split).

    original_date    = activity.scheduled_date
    parent_new_area  = activity.total_area - area

    try:
        with transaction.atomic():
            # Shrink parent
            old_total            = activity.total_area
            activity.total_area  = parent_new_area
            activity.move_reason = reason
            activity.is_manually_moved = True
            activity.save()

            # Create child
            from .models import ActivityLogTender
            child = JobActivity.objects.create(
                job                     = activity.job,
                activity                = activity.activity,
                plot                    = activity.plot,
                is_strict               = activity.is_strict,
                total_area              = area,
                allocated_area          = Decimal('0'),
                remaining_area          = area,
                scheduled_date          = new_date_obj,
                original_scheduled_date = activity.original_scheduled_date or original_date,
                original_gap_days       = activity.original_gap_days,
                rate_per_acre           = activity.rate_per_acre,
                transport_cost          = activity.transport_cost,
                other_cost              = activity.other_cost,
                estimated_workers       = max(1, int(float(area) * 10)),
                location                = activity.location,
                is_manually_moved       = True,
                moved_from_activity     = activity,
                source                  = 'manual',
                original_source         = activity.original_source,
                move_reason             = reason,
                api_activity_id         = activity.api_activity_id,
            )

            # Log both
            ActivityLogTender.objects.create(
                action       = 'JOB_ACTIVITY_UPDATED',
                job          = activity.job,
                job_activity = activity,
                performed_by = None,
                details      = {
                    'event':         'split_source_shrunk',
                    'description':   f'Shrunk {old_total} → {parent_new_area} ac. {area} ac split to {split_date}.',
                    'split_to_date': split_date,
                    'edited_by':     edited_by,
                    'move_reason':   reason,
                },
            )
            ActivityLogTender.objects.create(
                action       = 'JOB_ACTIVITY_CREATED',
                job          = child.job,
                job_activity = child,
                performed_by = None,
                details      = {
                    'event':              'split_activity_created',
                    'description':        f'{area} ac on {split_date} split from JA#{activity.pk}.',
                    'source_activity_id': activity.pk,
                    'edited_by':          edited_by,
                    'move_reason':        reason,
                },
            )

        # Sync both rows to sheet in background
        try:
            import threading
            from .sheets_sync import upsert_job_activity_to_sheet
            threading.Thread(target=upsert_job_activity_to_sheet, args=(activity.pk,), daemon=True).start()
            threading.Thread(target=upsert_job_activity_to_sheet, args=(child.pk,),    daemon=True).start()
        except Exception as e:
            logger.warning(f"[split_from_sheet] sheet sync thread error: {e}")

        return JsonResponse({
            "success":           True,
            "message":           f"{area} ac split to {split_date}. Parent JA#{activity.pk} now {parent_new_area} ac.",
            "parent_ja_id":      activity.pk,
            "parent_area":       float(parent_new_area),
            "child_ja_id":       child.pk,
            "child_area":        float(area),
            "child_date":        split_date,
        })

    except Exception as e:
        logger.error(f"[split_from_sheet] Error: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)