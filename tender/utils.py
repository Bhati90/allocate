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


"""
Add this view to your tender/views.py (or a new file and wire it in urls.py).

URL: GET /api/sales-performance/?cluster_id=&date_from=&date_to=
"""

from datetime import datetime, timedelta
from collections import defaultdict
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# ── helpers ───────────────────────────────────────────────────────────

def _pct(n, d):
    return round(n / d * 100, 1) if d > 0 else 0


def _bucket_label(diff):
    if diff <= 0:   return 'on_time'
    if diff == 1:   return 'late_1d'
    if diff == 2:   return 'late_2d'
    if diff == 3:   return 'late_3d'
    if diff <= 6:   return 'late_4_6d'
    if diff <= 10:  return 'late_7_10d'
    if diff <= 15:  return 'late_11_15d'
    if diff <= 30:  return 'late_16_30d'
    return 'late_30p'


BUCKET_ORDER = [
    'on_time', 'late_1d', 'late_2d', 'late_3d',
    'late_4_6d', 'late_7_10d', 'late_11_15d', 'late_16_30d', 'late_30p',
]

BUCKET_META = {
    'on_time':      {'label': '✅ On Time (≤ 0d)',  'severity': 'green'},
    'late_1d':      {'label': '🟢 Late 1d',          'severity': 'lime'},
    'late_2d':      {'label': '🟡 Late 2d',          'severity': 'yellow'},
    'late_3d':      {'label': '🟡 Late 3d',          'severity': 'gold'},
    'late_4_6d':    {'label': '🟠 Late 4–6d',        'severity': 'orange'},
    'late_7_10d':   {'label': '🔶 Late 7–10d',       'severity': 'deep_orange'},
    'late_11_15d':  {'label': '🔴 Late 11–15d',      'severity': 'red'},
    'late_16_30d':  {'label': '🔴 Late 16–30d',      'severity': 'red'},
    'late_30p':     {'label': '💀 Late 30d+',         'severity': 'critical'},
}


@api_view(['GET'])
@permission_classes([AllowAny])
def sales_performance(request):
    from tender.models import JobActivity  # adjust import to your app

    cluster_id = request.query_params.get('cluster_id')
    date_from  = request.query_params.get('date_from')
    date_to    = request.query_params.get('date_to')

    qs = JobActivity.objects.filter(
        is_lost=False,
        total_area__gt=0,
        sales_date__isnull=False,
        allocations__work_status='completed',
    ).distinct().select_related(
        'activity', 'job__farmer', 'plot'
    ).prefetch_related('allocations', 'plot__clusters', 'job__clusters')

    if cluster_id:
        qs = qs.filter(
            Q(plot__clusters__id=cluster_id) |
            Q(job__clusters__id=cluster_id)
        ).distinct()

    if date_from:
        qs = qs.filter(sales_date__gte=date_from)
    if date_to:
        qs = qs.filter(sales_date__lte=date_to)

    # ── Build deduplicated item list ──────────────────────────────────
    seen = {}
    for ja in qs:
        completed_alloc = ja.allocations.filter(
            work_status='completed'
        ).order_by('allocated_date').first()
        if not completed_alloc:
            continue

        if completed_alloc.actual_end_time:
            completed_date = completed_alloc.actual_end_time.date()
        elif completed_alloc.report_submitted_at:
            completed_date = completed_alloc.report_submitted_at.date()
        elif completed_alloc.allocated_date:
            completed_date = completed_alloc.allocated_date
        else:
            continue

        sales_date = ja.sales_date
        diff       = (completed_date - sales_date).days

        cluster_name = (
            ja.plot.clusters.first().name if ja.plot and ja.plot.clusters.exists() else
            ja.job.clusters.first().name  if ja.job.clusters.exists() else '—'
        )

        item = {
            'ja_id':          ja.id,
            'job_id':         str(ja.job.job_id),
            'farmer':         ja.job.farmer.farmer_name,
            'activity':       ja.activity.name,
            'plot':           ja.plot.name if ja.plot else '—',
            'cluster':        cluster_name,
            'scheduled_date': str(ja.scheduled_date) if ja.scheduled_date else '—',
            'sales_date':     str(sales_date),
            'completed_date': str(completed_date),
            'diff_days':      diff,
            'total_area':     float(ja.total_area),
            'bucket':         _bucket_label(diff),
        }

        dedup_key = (str(ja.job.job_id), str(ja.plot_id or ''), ja.activity.name)
        if dedup_key not in seen or diff < seen[dedup_key]['diff_days']:
            seen[dedup_key] = item

    all_items = list(seen.values())
    counted   = len(all_items)
    if counted == 0:
        return Response({
            'counted': 0,
            'kpis': {},
            'buckets': [],
            'rollup': [],
            'weekly_trend': [],
            'cluster_breakdown': [],
            'activity_heatmap': [],
            'farmer_performance': [],
            'recent_items': [],
        })

    total_area = sum(i['total_area'] for i in all_items)

    # ── Bucket counts ─────────────────────────────────────────────────
    buckets: dict = defaultdict(list)
    for item in all_items:
        buckets[item['bucket']].append(item)

    on_time_items = buckets['on_time']
    late_1_3_items = buckets['late_1d'] + buckets['late_2d'] + buckets['late_3d']

    ot_count   = len(on_time_items)
    w3_count   = ot_count + len(late_1_3_items)
    ot_area    = sum(i['total_area'] for i in on_time_items)
    w3_area    = ot_area + sum(i['total_area'] for i in late_1_3_items)
    avg_days   = round(sum(i['diff_days'] for i in all_items) / counted, 1)

    # ── KPIs ──────────────────────────────────────────────────────────
    kpis = {
        'total_activities': counted,
        'total_area':       round(total_area, 1),
        'on_time_pct':      _pct(ot_count, counted),
        'within_3d_pct':    _pct(w3_count, counted),
        'on_time_area_pct': _pct(ot_area, total_area),
        'w3_area_pct':      _pct(w3_area, total_area),
        'avg_days_late':    avg_days,
    }

    # ── Bucket breakdown ──────────────────────────────────────────────
    bucket_rows = []
    for key in BUCKET_ORDER:
        items = buckets[key]
        n     = len(items)
        ac    = sum(i['total_area'] for i in items)
        avg_d = round(sum(i['diff_days'] for i in items) / n, 1) if n else 0
        area_wtd = round(
            sum(i['diff_days'] * i['total_area'] for i in items) / ac, 1
        ) if ac > 0 else 0
        bucket_rows.append({
            'key':        key,
            **BUCKET_META[key],
            'count':      n,
            'pct':        _pct(n, counted),
            'avg_days':   avg_d,
            'area_ac':    round(ac, 1),
            'area_wtd_avg': area_wtd,
        })

    # ── Rollup (grouped ranges) ───────────────────────────────────────
    rollup_groups = [
        ('on_time',    '✅ On Time (≤ 0d)',  'green',       ['on_time']),
        ('late_1_3d',  '🟢 Late 1–3d',       'lime',        ['late_1d', 'late_2d', 'late_3d']),
        ('late_4_6d',  '🟠 Late 4–6d',       'orange',      ['late_4_6d']),
        ('late_7_10d', '🔶 Late 7–10d',      'deep_orange', ['late_7_10d']),
        ('late_11_15d','🔴 Late 11–15d',     'red',         ['late_11_15d']),
        ('late_16_30d','🔴 Late 16–30d',     'red',         ['late_16_30d']),
        ('late_30p',   '💀 Late 30d+',        'critical',    ['late_30p']),
    ]
    rollup_rows = []
    for key, label, severity, bucket_keys in rollup_groups:
        items = [i for bk in bucket_keys for i in buckets[bk]]
        n     = len(items)
        ac    = sum(i['total_area'] for i in items)
        avg_d = round(sum(i['diff_days'] for i in items) / n, 1) if n else 0
        rollup_rows.append({
            'key': key, 'label': label, 'severity': severity,
            'count': n, 'pct': _pct(n, counted),
            'avg_days': avg_d, 'area_ac': round(ac, 1),
        })

    # ── Weekly trend ─────────────────────────────────────────────────
    week_stats: dict = defaultdict(lambda: {
        'total': 0, 'ot': 0, 'w3': 0,
        'area': 0.0, 'ot_area': 0.0, 'diff_sum': 0,
    })
    for item in all_items:
        sd = datetime.strptime(item['sales_date'], '%Y-%m-%d').date()
        wk = sd - timedelta(days=sd.weekday())
        week_stats[wk]['total'] += 1
        week_stats[wk]['area']  += item['total_area']
        week_stats[wk]['diff_sum'] += item['diff_days']
        if item['diff_days'] <= 0:
            week_stats[wk]['ot'] += 1
            week_stats[wk]['ot_area'] += item['total_area']
        if item['diff_days'] <= 3:
            week_stats[wk]['w3'] += 1

    weekly_trend = []
    prev_ot = prev_w3 = None
    for wk in sorted(week_stats.keys()):
        s    = week_stats[wk]
        ot_p = _pct(s['ot'], s['total'])
        w3_p = _pct(s['w3'], s['total'])
        ot_a = _pct(s['ot_area'], s['area']) if s['area'] else 0
        avg_d = round(s['diff_sum'] / s['total'], 1) if s['total'] else 0
        weekly_trend.append({
            'week_start': str(wk),
            'week_label': wk.strftime('%d %b'),
            'total':      s['total'],
            'on_time':    s['ot'],
            'within_3d':  s['w3'],
            'on_time_pct': ot_p,
            'within_3d_pct': w3_p,
            'on_time_area_pct': ot_a,
            'avg_days_late': avg_d,
            'area_ac': round(s['area'], 1),
            'wow_ot':  round(ot_p - prev_ot, 1) if prev_ot is not None else None,
            'wow_w3':  round(w3_p - prev_w3, 1) if prev_w3 is not None else None,
        })
        prev_ot, prev_w3 = ot_p, w3_p

    # ── Cluster breakdown ────────────────────────────────────────────
    cs: dict = defaultdict(lambda: {
        'ot': 0, 'l1_3': 0, 'l4_6': 0, 'l7_10': 0,
        'l11_15': 0, 'l16_30': 0, 'l30p': 0,
        'area': 0.0, 'ot_area': 0.0, 'w3_area': 0.0,
    })
    bucket_to_group = {
        'on_time': 'ot',
        'late_1d': 'l1_3', 'late_2d': 'l1_3', 'late_3d': 'l1_3',
        'late_4_6d': 'l4_6', 'late_7_10d': 'l7_10',
        'late_11_15d': 'l11_15', 'late_16_30d': 'l16_30', 'late_30p': 'l30p',
    }
    for item in all_items:
        cl  = item['cluster']
        grp = bucket_to_group[item['bucket']]
        cs[cl][grp] += 1
        cs[cl]['area'] += item['total_area']
        if grp == 'ot':
            cs[cl]['ot_area'] += item['total_area']
        if grp in ('ot', 'l1_3'):
            cs[cl]['w3_area'] += item['total_area']

    cluster_breakdown = []
    for cl, s in sorted(cs.items(), key=lambda x: -(
        sum(v for k, v in x[1].items() if k not in ('area','ot_area','w3_area'))
    )):
        tot   = sum(v for k, v in s.items() if k not in ('area','ot_area','w3_area'))
        ot_p  = _pct(s['ot'], tot)
        w3_p  = _pct(s['ot'] + s['l1_3'], tot)
        ot_a  = _pct(s['ot_area'], s['area']) if s['area'] else 0
        cluster_breakdown.append({
            'cluster': cl, 'total': tot,
            'on_time': s['ot'], 'late_1_3d': s['l1_3'],
            'late_4_6d': s['l4_6'], 'late_7_10d': s['l7_10'],
            'late_11_15d': s['l11_15'], 'late_16_30d': s['l16_30'],
            'late_30p': s['l30p'],
            'on_time_pct': ot_p, 'within_3d_pct': w3_p,
            'area_ac': round(s['area'], 1), 'on_time_area_pct': ot_a,
        })

    # ── Activity heatmap ─────────────────────────────────────────────
    ca: dict = defaultdict(lambda: defaultdict(
        lambda: {'total': 0, 'ot': 0, 'area': 0.0}))
    for item in all_items:
        ca[item['cluster']][item['activity']]['total'] += 1
        ca[item['cluster']][item['activity']]['area']  += item['total_area']
        if item['diff_days'] <= 0:
            ca[item['cluster']][item['activity']]['ot'] += 1

    activities_list = sorted({i['activity'] for i in all_items})
    heatmap_rows = []
    for cl in sorted(ca.keys()):
        row = {'cluster': cl, 'activities': {}}
        cl_total = cl_ot = 0
        for act in activities_list:
            s = ca[cl][act]
            cl_total += s['total']
            cl_ot    += s['ot']
            row['activities'][act] = {
                'total': s['total'],
                'ot': s['ot'],
                'pct': _pct(s['ot'], s['total']) if s['total'] else None,
            }
        row['overall_ot_pct'] = _pct(cl_ot, cl_total) if cl_total else 0
        heatmap_rows.append(row)

    # ── Farmer performance ───────────────────────────────────────────
    fs: dict = defaultdict(lambda: {
        'total': 0, 'ot': 0, 'w3': 0,
        'area': 0.0, 'ot_area': 0.0, 'diff_sum': 0, 'clusters': set(),
    })
    for item in all_items:
        f = item['farmer']
        fs[f]['total']    += 1
        fs[f]['area']     += item['total_area']
        fs[f]['diff_sum'] += item['diff_days']
        fs[f]['clusters'].add(item['cluster'])
        if item['diff_days'] <= 0:
            fs[f]['ot'] += 1
            fs[f]['ot_area'] += item['total_area']
        if item['diff_days'] <= 3:
            fs[f]['w3'] += 1

    farmer_performance = []
    for fname, s in sorted(fs.items(), key=lambda x: _pct(x[1]['ot'], x[1]['total'])):
        ot_p  = _pct(s['ot'], s['total'])
        w3_p  = _pct(s['w3'], s['total'])
        avg_d = round(s['diff_sum'] / s['total'], 1) if s['total'] else 0
        farmer_performance.append({
            'farmer': fname,
            'clusters': sorted(s['clusters']),
            'total': s['total'],
            'on_time': s['ot'],
            'on_time_pct': ot_p,
            'within_3d': s['w3'],
            'within_3d_pct': w3_p,
            'avg_days_late': avg_d,
            'area_ac': round(s['area'], 1),
            'late_area': round(s['area'] - s['ot_area'], 1),
        })

    return Response({
        'counted':            counted,
        'total_area':         round(total_area, 1),
        'kpis':               kpis,
        'buckets':            bucket_rows,
        'rollup':             rollup_rows,
        'weekly_trend':       weekly_trend,
        'cluster_breakdown':  cluster_breakdown,
        'activity_heatmap':   heatmap_rows,
        'activities_list':    activities_list,
        'farmer_performance': farmer_performance,
    })


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

# from .models import ClusterMukkadamAssignment
# def check_can_allocate(job_activity_id, mukkadam_id, date, area, workers,
#                        skip_strict_check=False, cluster_id=None,
#                        exclude_allocation_id=None):

#     area = Decimal(str(area))
#     workers = int(workers)

#     if isinstance(date, str):
#         date = date_type.fromisoformat(str(date))

#     try:
#         job_activity = JobActivity.objects.get(id=job_activity_id)
#         mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
#     except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist):
#         return False, "Job activity or mukkadam not found", {}

#     warnings = {}

#     # ── UPDOWN CHECK ──────────────────────────────────────────────────────────
#     check_date_str = str(date)
#     # ── UPDOWN CHECK ──────────────────────────────────────────────────────────
#     if cluster_id:
#         assignments = ClusterMukkadamAssignment.objects.filter(
#             mukkadam=mukkadam,
#             cluster_id=cluster_id,
#             is_active=True,
#         )
        
#         # If ANY assignment covers this date, they're available
#         updown_assignments = [a for a in assignments if a.mukkadam_type == 'updown']
        
#         if updown_assignments:
#             available = False
#             for assignment in updown_assignments:
#                 if assignment.updown_mode == 'range':
#                     if assignment.updown_from_date and assignment.updown_to_date:
#                         if assignment.updown_from_date <= date <= assignment.updown_to_date:
#                             available = True
#                             break
#                 elif assignment.updown_mode == 'specific':
#                     if check_date_str in (assignment.updown_specific_dates or []):
#                         available = True
#                         break
            
#             if not available:
#                 return (
#                     False,
#                     f"{mukkadam.mukkadam_name} is not available on {check_date_str} in this cluster",
#                     {},
#                 )
#     # ── REMAINING AREA CHECK ──────────────────────────────────────────────────
#     if not skip_strict_check and area > job_activity.remaining_area:
#         return False, f"Area exceeds remaining: {job_activity.remaining_area} acres still not allocated", {}

#     # ── GET CREW SIZE & LEAVES ────────────────────────────────────────────────
#     eff_crew = get_effective_crew_size(mukkadam, date)
#     if eff_crew == 0:
#         return False, f"Mukkadam not available on {date} (holiday or zero crew)", {}

#     # ── HALF-DAY COMBINED CAPACITY CHECK ─────────────────────────────────────
#     # Get any existing half-day allocations for this mukkadam on this date.
#     # These don't block the day but their *needed* workers must combine
#     # with this new job's workers to stay within crew_size.
#     # ── HALF-DAY COMBINED CAPACITY CHECK ─────────────────────────────────────
#     half_day_allocs = Allocation.objects.filter(
#         mukkadam=mukkadam,
#         allocated_date=date,
#         allows_second_job=True,
#         status__in=['scheduled', 'in_progress'],
#     )
#     if exclude_allocation_id:
#         half_day_allocs = half_day_allocs.exclude(pk=exclude_allocation_id)

#     if half_day_allocs.exists():
#         # ── Calculate NEEDED workers for each half-day job (not allocated_workers) ──
#         # "needed" = ceil(area / productivity), capped at crew_size
#         half_day_needed_total = 0
#         for hd_alloc in half_day_allocs:
#             try:
#                 hd_rate = hd_alloc.mukkadam.activity_rates.get(
#                     activity=hd_alloc.job_activity.activity,
#                     is_active=True,
#                 )
#                 hd_productivity = float(hd_rate.productivity_per_worker)
#                 if hd_productivity > 0:
#                     hd_needed = math.ceil(float(hd_alloc.job_activity.total_area) / hd_productivity)
#                 else:
#                     hd_needed = hd_alloc.allocated_workers  # fallback
#             except Exception:
#                 hd_needed = hd_alloc.allocated_workers  # fallback

#             half_day_needed_total += hd_needed

#         # "needed" for THIS job
#         try:
#             this_rate = mukkadam.activity_rates.get(
#                 activity=job_activity.activity,
#                 is_active=True,
#             )
#             this_productivity = float(this_rate.productivity_per_worker)
#             this_needed = math.ceil(float(area) / this_productivity) if this_productivity > 0 else workers
#         except Exception:
#             this_needed = workers  # fallback

#         on_leave = Leave.objects.filter(
#             leave_type='mukkadam',
#             mukkadam=mukkadam,
#             date=date,
#             is_active=True,
#         ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

#         available_crew = eff_crew - on_leave
#         combined_needed = half_day_needed_total + this_needed
#         available_crew = available_crew * 3.20

#         if combined_needed > available_crew:
#             return (
#                 False,
#                 f"Combined workers exceed crew capacity: "
#                 f"{half_day_needed_total} needed (½ day job) + {this_needed} needed (this job) "
#                 f"= {combined_needed} > {available_crew} available workers.",
#                 warnings,
#             )

#         # Also block if a full-day allocation already exists
#         normal_used_count = Allocation.objects.filter(
#             mukkadam=mukkadam,
#             allocated_date=date,
#             allows_second_job=False,
#             status__in=['scheduled', 'in_progress'],
#         ).exclude(pk=exclude_allocation_id or 0).aggregate(
#             total=models.Sum('allocated_workers')
#         )['total'] or 0

#         if normal_used_count > 0:
#             return (
#                 False,
#                 f"{mukkadam.mukkadam_name} already has a full-day allocation today.",
#                 warnings,
#             )

#         warnings['half_day_split'] = {
#             'severity': 'info',
#             'message': (
#                 f"2nd job for {mukkadam.mukkadam_name} today. "
#                 f"Day split: {half_day_needed_total}w (1st job) + {this_needed}w (this job) "
#                 f"= {combined_needed}/{available_crew} workers used."
#             ),
#         }

#     else:
#         # ── Standard capacity check (no half-day allocs) ──────────────────────
#         normal_workers_sum = Allocation.objects.filter(
#             mukkadam=mukkadam,
#             allocated_date=date,
#             allows_second_job=False,
#             status__in=['scheduled', 'in_progress'],
#         ).exclude(pk=exclude_allocation_id or 0).aggregate(
#             total=models.Sum('allocated_workers')
#         )['total'] or 0

#         on_leave = Leave.objects.filter(
#             leave_type='mukkadam',
#             mukkadam=mukkadam,
#             date=date,
#             is_active=True,
#         ).aggregate(total=models.Sum('crew_on_leave'))['total'] or 0

#         remaining_capacity = max(eff_crew - on_leave - normal_workers_sum, 0)
#         if workers > remaining_capacity:
#             return (
#                 False,
#                 f"Workers capacity exceeded: {remaining_capacity} workers available, "
#                 f"{workers} requested.",
#                 warnings,
#             )
#     # ── PRODUCTIVITY CHECK ────────────────────────────────────────────────────
#     try:
#         mukkadam_rate = mukkadam.activity_rates.get(
#             activity=job_activity.activity,
#             is_active=True,
#         )
#         productivity = Decimal(str(mukkadam_rate.productivity_per_worker))
#         max_capacity = workers * productivity
#         max_capacity = max_capacity*3

#         if area > max_capacity:
#             suggested_area = float(max_capacity)
#             required_workers = int(float(area) / float(productivity)) if productivity > 0 else workers
#             required_productivity = float(area) / workers if workers > 0 else float(productivity)

#             warnings['productivity_warning'] = {
#                 'severity': 'error',
#                 'message': f"Team cannot complete {area} acres in 1 day!",
#                 'details': {
#                     'workers': workers,
#                     'productivity_per_worker': f"{productivity} acres/worker/day",
#                     'max_capacity': f"{max_capacity} acres/day",
#                     'requested': f"{area} acres",
#                     'deficit': f"{area - max_capacity} acres short",
#                 },
#                 'suggestions': [
#                     {
#                         'option': 'reduce_area',
#                         'description': f"Allocate only {suggested_area:.2f} acres",
#                         'allocation': {'area': suggested_area, 'workers': workers, 'will_complete': True},
#                     },
#                     {
#                         'option': 'add_workers',
#                         'description': f"Increase workers to {required_workers}",
#                         'allocation': {'area': area, 'workers': required_workers, 'will_complete': True,
#                                        'note': f"Need {required_workers - workers} more workers"},
#                     },
#                     {
#                         'option': 'update_productivity',
#                         'description': f"Update productivity to {required_productivity:.3f} acres/worker/day",
#                         'allocation': {'area': area, 'workers': workers,
#                                        'new_productivity': required_productivity, 'will_complete': True},
#                     },
#                     {
#                         'option': 'split_days',
#                         'description': f"Split: {suggested_area:.2f} ac today + {float(area) - suggested_area:.2f} ac tomorrow",
#                         'allocations': [
#                             {'date': str(date), 'area': suggested_area, 'workers': workers},
#                             {'date': 'next_day', 'area': float(area) - suggested_area, 'workers': workers},
#                         ],
#                     },
#                 ],
#             }
#             return False, "Productivity set higher than real", warnings

#         elif area > (max_capacity * Decimal('0.9')):
#             warnings['productivity_warning'] = {
#                 'severity': 'warning',
#                 'message': f"Team will be at {(area / max_capacity) * 100:.1f}% capacity",
#                 'details': {
#                     'workers': workers,
#                     'productivity_per_worker': f"{productivity} acres/worker/day",
#                     'max_capacity': f"{max_capacity} acres/day",
#                     'requested': f"{area} acres",
#                     'utilization': f"{(area / max_capacity) * 100:.1f}%",
#                 },
#                 'note': "Near-maximum capacity",
#             }

#     except mukkadam.activity_rates.model.DoesNotExist:
#         warnings['no_rate_card'] = {
#             'severity': 'warning',
#             'message': "No productivity data for this mukkadam-activity combination",
#             'note': "Proceeding without productivity validation",
#         }

#     # ── STRICT ACTIVITY CHECK ─────────────────────────────────────────────────
#     if job_activity.activity.is_strict and not skip_strict_check:
#         scheduled_date = job_activity.scheduled_date
#         if scheduled_date and str(scheduled_date) != str(date):
#             if float(job_activity.allocated_area) == 0:
#                 return (
#                     False,
#                     f"Strict activity must start on its scheduled date: {scheduled_date}",
#                     warnings,
#                 )

#     return True, "OK", warnings
def check_can_allocate(job_activity_id, mukkadam_id, date, area, workers,
                       skip_strict_check=False, cluster_id=None,
                       exclude_allocation_id=None):

    area    = Decimal(str(area))
    workers = int(workers)

    if isinstance(date, str):
        date = date_type.fromisoformat(str(date))

    try:
        job_activity = JobActivity.objects.get(id=job_activity_id)
        mukkadam     = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except (JobActivity.DoesNotExist, Mukkadam.DoesNotExist):
        return False, "Job activity or mukkadam not found", {}

    warnings = {}

    # ── REMAINING AREA CHECK (keep only this hard block) ─────────────────────
    if not skip_strict_check and area > job_activity.remaining_area:
        return False, f"Area exceeds remaining: {job_activity.remaining_area} acres still not allocated", {}

    # ✅ Everything else — capacity, productivity, availability, crew — ALLOWED
    # No updown check, no crew reduction, no productivity block, no half-day block
    # Same mukkadam can be allocated multiple times on same day

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


# tender/utils.py
from datetime import timedelta
from .models import JobActivity

from datetime import timedelta, date
from .models import JobActivity

from datetime import timedelta, date
from .models import JobActivity

def cascade_gap_change_for_cluster(cluster, activity_catalog, new_gap_days: int):
    today = date.today()

    activities = JobActivity.objects.filter(
        activity=activity_catalog,
        is_lost=False,
        is_manually_moved=False,
        allocation_status='pending',
        job__clusters=cluster,
        scheduled_date__gte=today,   # only future activities
    ).select_related('plot').distinct()

    updated = []
    skipped = []

    for act in activities:
        plot = act.plot
        if not plot or not plot.pruning_date:
            skipped.append({
                'activity_id': act.id,
                'reason':      'No pruning date on plot',
            })
            continue

        new_date = plot.pruning_date + timedelta(days=new_gap_days)

        # Floor to today if computed date is in the past
        if new_date < today:
            new_date = today

        if act.scheduled_date == new_date:
            continue

        old_date           = act.scheduled_date
        act.scheduled_date = new_date
        act.save(update_fields=['scheduled_date'])

        updated.append({
            'activity_id': act.id,
            'plot_code':   plot.plot_code,
            'old_date':    str(old_date) if old_date else None,
            'new_date':    str(new_date),
        })

    return updated, skipped# ============================================================================
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

