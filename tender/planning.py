"""
planning_api_views.py
─────────────────────────────────────────────────────────────────
Serves the exact JSON shape that planning_app.js expects, but
sourced live from your Django DB per-cluster.

Mount in urls.py:
    path('api/planning/', include('your_app.planning_urls')),

Then planning_app.js replaces:
    fetch('full_season_data.json')
with:
    fetch(`/api/planning/clusters/${clusterId}/season-data/`)

Filters applied:
  - job__clusters = selected cluster
  - total_area   > 0          (exclude zero-acre activities)
  - is_lost      = False      (exclude lost activities)
  - scheduled_date is not null
"Completed" = any Allocation on that activity has work_status = 'completed'
"""
"""
original_api_views.py
─────────────────────────────────────────────────────────────────
Serves the exact JSON shapes that:
  • app.js          expects  (data.json)
  • optimised_app.js expects (optimised_data.json)

Mount in urls.py:
    path('api/planning/', include('your_app.original_urls')),

Endpoints:
  GET /api/planning/clusters/<cluster_id>/data/           → data.json shape
  GET /api/planning/clusters/<cluster_id>/optimised-data/ → optimised_data.json shape

Filters applied everywhere:
  - job__clusters = selected cluster
  - total_area   > 0
  - is_lost      = False
  - scheduled_date is not null

"Completed" = any Allocation on that activity has work_status = 'completed'
"""

import math
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.views import View

from tender.models import (
    Cluster, JobActivity, Allocation,
    ActivityCatalog, ClusterMukkadamActivityRate,
    JobBooking,
)

DEFAULT_PRODUCTIVITY = 0.14   # acres per worker per day


# ════════════════════════════════════════════════════════════════════
# HELPERS (shared)
# ════════════════════════════════════════════════════════════════════

def _productivity(cluster, activity_obj, _cache={}):
    key = (cluster.pk, activity_obj.pk)
    if key not in _cache:
        rate = ClusterMukkadamActivityRate.objects.filter(
            cluster=cluster, activity=activity_obj
        ).values_list('productivity_per_worker', flat=True).first()
        if rate:
            _cache[key] = float(rate)
        elif activity_obj.default_productivity_per_worker:
            _cache[key] = float(activity_obj.default_productivity_per_worker)
        else:
            _cache[key] = DEFAULT_PRODUCTIVITY
    return _cache[key]


def _workers_needed(total_area, productivity):
    if not productivity or productivity <= 0:
        return 0
    return math.ceil(float(total_area) / productivity)


def _activity_status(allocs):
    statuses = {a.work_status for a in allocs}
    if 'completed' in statuses:
        return 'completed'
    if 'in_progress' in statuses:
        return 'in_progress'
    if statuses:
        return 'allocated'
    return 'pending'


def _pay_label(ja):
    try:
        status = ja.job.booking.status
        return {
            'UNPAID': 'Yet to Pay',
            'PARTIALLY_PAID': 'Partial',
            'PAID': 'Paid',
        }.get(status, 'Yet to Pay')
    except Exception:
        return 'Yet to Pay'


def _base_qs(cluster):
    """Return the base JobActivity queryset for a cluster with all prefetches."""
    return (
        JobActivity.objects
        .filter(
            job__clusters=cluster,
            is_lost=False,
            scheduled_date__isnull=False,
            total_area__gt=0,
        )
        .select_related(
            'job', 'job__farmer', 'job__booking',
            'activity', 'plot',
        )
        .prefetch_related(
            Prefetch(
                'allocations',
                queryset=Allocation.objects.only(
                    'job_activity_id', 'work_status',
                    'allocated_workers', 'allocated_area',
                    'mukkadam_id', 'allocated_date',
                )
            )
        )
        .order_by('scheduled_date')
    )


# ════════════════════════════════════════════════════════════════════
# VIEW — data.json shape
# GET /api/planning/clusters/<cluster_id>/data/
# ════════════════════════════════════════════════════════════════════

class ClusterDataView(View):
    """
    Serves the JSON shape that app.js (index.html) expects.

    Top-level keys:
      clusterSummary, dailySummary, villageSummary, plots
    """

    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'Cluster not found'}, status=404)

        activities = list(_base_qs(cluster))

        if not activities:
            return JsonResponse(_empty_data(cluster))

        # ── Build flat records ─────────────────────────────────────
        records = []
        for ja in activities:
            prod    = _productivity(cluster, ja.activity)
            workers = _workers_needed(ja.total_area, prod)
            allocs  = list(ja.allocations.all())
            status  = _activity_status(allocs)
            village = (ja.job.farmer.location or '').strip() or cluster.name
            plot_id = (
                ja.plot.plot_code
                if ja.plot and ja.plot.plot_code
                else str(ja.plot_id or ja.pk)
            )
            records.append({
                'farmer':        ja.job.farmer.farmer_name,
                'village':       village,
                'variety':       ja.job.variety or ja.job.crop_name or '',
                'acre':          float(ja.total_area),
                'plotId':        plot_id,
                'activity':      ja.activity.name,
                'activityDate':  ja.scheduled_date.isoformat(),
                'workers':       workers,           # alias workersNeeded
                'workersNeeded': workers,
                'paymentStatus': _pay_label(ja),
                'status':        status,
            })

        all_dates = [ja.scheduled_date for ja in activities]
        season_start = min(all_dates)
        season_end   = max(all_dates)

        # ── clusterSummary ────────────────────────────────────────
        total_acres    = sum(r['acre'] for r in records)
        paid_acres     = sum(r['acre'] for r in records if r['paymentStatus'] == 'Paid')
        unpaid_acres   = total_acres - paid_acres
        paid_pct       = round(paid_acres / total_acres * 100, 1) if total_acres else 0

        # daily totals for peak
        daily_totals = defaultdict(int)
        for r in records:
            daily_totals[r['activityDate']] += r['workersNeeded']
        peak_daily = max(daily_totals.values()) if daily_totals else 0

        cluster_summary = {
            'totalAcres':       round(total_acres, 2),
            'totalPlots':       len({r['plotId'] for r in records}),
            'totalFarmers':     len({r['farmer'] for r in records}),
            'uniqueVillages':   len({r['village'] for r in records}),
            'peakDailyWorkers': peak_daily,
            'paidAcres':        round(paid_acres, 2),
            'unpaidAcres':      round(unpaid_acres, 2),
            'paidPercentage':   paid_pct,
            'dateRange': {
                'start': season_start.isoformat(),
                'end':   season_end.isoformat(),
            },
        }

        # ── dailySummary ──────────────────────────────────────────
        by_date = defaultdict(list)
        for r in records:
            by_date[r['activityDate']].append(r)

        daily_summary = []
        for d_str in sorted(by_date.keys()):
            day_recs = by_date[d_str]
            total_workers = sum(r['workersNeeded'] for r in day_recs)
            total_day_acres = round(sum(r['acre'] for r in day_recs), 2)

            # village breakdown
            vb_map = defaultdict(lambda: {
                'acres': 0.0, 'workersNeeded': 0,
                'plotCount': 0, 'farmers': [],
            })
            for r in day_recs:
                v = r['village']
                vb_map[v]['acres']          += r['acre']
                vb_map[v]['workersNeeded']  += r['workersNeeded']
                vb_map[v]['plotCount']      += 1
                if r['farmer'] not in vb_map[v]['farmers']:
                    vb_map[v]['farmers'].append(r['farmer'])

            village_breakdown = [
                {
                    'village':       v,
                    'acres':         round(d['acres'], 2),
                    'workersNeeded': d['workersNeeded'],
                    'plotCount':     d['plotCount'],
                    'farmers':       d['farmers'],
                }
                for v, d in vb_map.items()
            ]

            daily_summary.append({
                'date':               d_str,
                'totalAcres':         total_day_acres,
                'totalWorkersNeeded': total_workers,
                'plots':              [
                    {
                        'plotId':    r['plotId'],
                        'farmer':    r['farmer'],
                        'village':   r['village'],
                        'activity':  r['activity'],
                        'acre':      r['acre'],
                        'workers':   r['workersNeeded'],
                        'status':    r['status'],
                    }
                    for r in day_recs
                ],
                'villageBreakdown': village_breakdown,
            })

        # ── villageSummary ────────────────────────────────────────
        vsum_map = defaultdict(lambda: {
            'totalAcre': 0.0, 'paidAcre': 0.0, 'unpaidAcre': 0.0,
            'totalWorkersNeeded': 0, 'farmerSet': set(),
            'plotSet': set(), 'dates': [],
        })
        for r in records:
            v = r['village']
            vsum_map[v]['totalAcre']          += r['acre']
            vsum_map[v]['totalWorkersNeeded'] += r['workersNeeded']
            vsum_map[v]['farmerSet'].add(r['farmer'])
            vsum_map[v]['plotSet'].add(r['plotId'])
            vsum_map[v]['dates'].append(r['activityDate'])
            if r['paymentStatus'] == 'Paid':
                vsum_map[v]['paidAcre'] += r['acre']
            else:
                vsum_map[v]['unpaidAcre'] += r['acre']

        village_summary = []
        for v, d in vsum_map.items():
            dates_sorted = sorted(d['dates'])
            village_summary.append({
                'village':            v,
                'totalAcre':          round(d['totalAcre'], 2),
                'paidAcre':           round(d['paidAcre'], 2),
                'unpaidAcre':         round(d['unpaidAcre'], 2),
                'totalWorkersNeeded': d['totalWorkersNeeded'],
                'farmerCount':        len(d['farmerSet']),
                'plotCount':          len(d['plotSet']),
                'startDate':          dates_sorted[0],
                'endDate':            dates_sorted[-1],
            })

        # ── plots (flat list for Farmer Details tab) ──────────────
        plots = [
            {
                'farmer':        r['farmer'],
                'village':       r['village'],
                'variety':       r['variety'],
                'acre':          r['acre'],
                'plotId':        r['plotId'],
                'activity':      r['activity'],
                'activityDate':  r['activityDate'],
                'workersNeeded': r['workersNeeded'],
                'paymentStatus': r['paymentStatus'],
                'status':        r['status'],
            }
            for r in records
        ]

        return JsonResponse({
            'clusterSummary': cluster_summary,
            'dailySummary':   daily_summary,
            'villageSummary': village_summary,
            'plots':          plots,
        })


def _empty_data(cluster):
    return {
        'clusterSummary': {
            'totalAcres': 0, 'totalPlots': 0, 'totalFarmers': 0,
            'uniqueVillages': 0, 'peakDailyWorkers': 0,
            'paidAcres': 0, 'unpaidAcres': 0, 'paidPercentage': 0,
            'dateRange': {'start': None, 'end': None},
        },
        'dailySummary': [], 'villageSummary': [], 'plots': [],
    }


# ════════════════════════════════════════════════════════════════════
# VIEW — optimised_data.json shape
# GET /api/planning/clusters/<cluster_id>/optimised-data/
# ════════════════════════════════════════════════════════════════════

FLEX_DAYS  = 4    # ±4 day window for optimisation
TEAM_SIZE  = 5    # default team size

class ClusterOptimisedDataView(View):
    """
    Serves the JSON shape that optimised_app.js (optimised.html) expects.

    Algorithm:
      1. Build the "before" daily demand from scheduled_date
      2. Run a greedy levelling algorithm (±FLEX_DAYS):
         - Sort activities by area descending (move biggest first)
         - For each activity try all dates in window, pick the one
           with the lowest current total workers
      3. Return before/after daily totals, village breakdown, shift list

    Top-level keys:
      beforePeak, afterPeak, reductionPercent, teamSize, flexDays,
      activeDays, totalWorkerDays, pruningRate, shootSelectionRate,
      beforeDaily, afterDaily, villageDailyAfter,
      optimisedPlots
    """

    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'Cluster not found'}, status=404)

        activities = list(_base_qs(cluster))
        if not activities:
            return JsonResponse(_empty_optimised())

        # ── Build plot records ─────────────────────────────────────
        plots = []
        for ja in activities:
            prod    = _productivity(cluster, ja.activity)
            workers = _workers_needed(ja.total_area, prod)
            allocs  = list(ja.allocations.all())
            status  = _activity_status(allocs)
            village = (ja.job.farmer.location or '').strip() or cluster.name
            plot_id = (
                ja.plot.plot_code
                if ja.plot and ja.plot.plot_code
                else str(ja.plot_id or ja.pk)
            )
            is_strict = bool(ja.is_strict or ja.activity.is_strict)

            plots.append({
                '_jaId':     ja.pk,
                'farmer':    ja.job.farmer.farmer_name,
                'village':   village,
                'variety':   ja.job.variety or ja.job.crop_name or '',
                'acre':      float(ja.total_area),
                'plotId':    plot_id,
                'activity':  ja.activity.name,
                'origDate':  ja.scheduled_date.isoformat(),
                'newDate':   ja.scheduled_date.isoformat(),  # will be updated
                'workers':   workers,
                'productivity': prod,
                'paymentStatus': _pay_label(ja),
                'status':    status,
                'isStrict':  is_strict,
                'shift':     0,
            })

        # ── Before daily totals ────────────────────────────────────
        before_daily = defaultdict(int)
        for p in plots:
            before_daily[p['origDate']] += p['workers']

        # ── Greedy levelling ───────────────────────────────────────
        after_daily = dict(before_daily)   # mutable copy

        # Sort: strict first (cannot move), then by workers desc
        movable = [p for p in plots if not p['isStrict']]
        strict  = [p for p in plots if p['isStrict']]

        # Optimise: try to level workload
        for p in sorted(movable, key=lambda x: -x['workers']):
            orig_date = date.fromisoformat(p['origDate'])
            best_date  = orig_date
            best_total = after_daily.get(orig_date.isoformat(), 0)

            for delta in range(-FLEX_DAYS, FLEX_DAYS + 1):
                candidate = orig_date + timedelta(days=delta)
                cand_str  = candidate.isoformat()
                # Remove this plot's contribution to its current date first
                current_date_str = p['newDate']
                current_total = after_daily.get(cand_str, 0)
                if delta == 0:
                    continue
                if current_total < best_total:
                    best_total = current_total
                    best_date  = candidate

            # Apply the move
            old_str  = p['newDate']
            new_str  = best_date.isoformat()

            if new_str != old_str:
                after_daily[old_str]  = after_daily.get(old_str, 0) - p['workers']
                after_daily[new_str]  = after_daily.get(new_str, 0) + p['workers']
                p['newDate'] = new_str
                p['shift']   = (best_date - date.fromisoformat(p['origDate'])).days

        # Clean negatives (floating point safety)
        after_daily = {k: max(0, v) for k, v in after_daily.items() if v > 0}

        # ── Summary stats ──────────────────────────────────────────
        before_peak = max(before_daily.values()) if before_daily else 0
        after_peak  = max(after_daily.values())  if after_daily  else 0
        reduction   = round((before_peak - after_peak) / before_peak * 100, 1) if before_peak else 0
        active_days = len(after_daily)
        total_wdays = sum(after_daily.values())

        # ── villageDailyAfter ──────────────────────────────────────
        village_daily_after = defaultdict(lambda: defaultdict(int))
        for p in plots:
            village_daily_after[p['newDate']][p['village']] += p['workers']
        village_daily_after = {
            d: dict(v) for d, v in village_daily_after.items()
        }

        # ── Rate info (for hero display) ───────────────────────────
        # Try to surface the productivity rates for the most common activities
        pruning_rate = DEFAULT_PRODUCTIVITY
        shoot_rate   = DEFAULT_PRODUCTIVITY
        for ja in activities:
            name = ja.activity.name.lower()
            if 'prun' in name or 'छाटणी' in name:
                pruning_rate = _productivity(cluster, ja.activity)
            if 'shoot' in name or 'दिरव' in name:
                shoot_rate = _productivity(cluster, ja.activity)

        return JsonResponse({
            'beforePeak':          before_peak,
            'afterPeak':           after_peak,
            'reductionPercent':    reduction,
            'teamSize':            TEAM_SIZE,
            'flexDays':            FLEX_DAYS,
            'activeDays':          active_days,
            'totalWorkerDays':     total_wdays,
            'pruningRate':         pruning_rate,
            'shootSelectionRate':  shoot_rate,
            'beforeDaily':         dict(before_daily),
            'afterDaily':          after_daily,
            'villageDailyAfter':   village_daily_after,
            'optimisedPlots':      plots,
        })


def _empty_optimised():
    return {
        'beforePeak': 0, 'afterPeak': 0, 'reductionPercent': 0,
        'teamSize': TEAM_SIZE, 'flexDays': FLEX_DAYS,
        'activeDays': 0, 'totalWorkerDays': 0,
        'pruningRate': DEFAULT_PRODUCTIVITY,
        'shootSelectionRate': DEFAULT_PRODUCTIVITY,
        'beforeDaily': {}, 'afterDaily': {},
        'villageDailyAfter': {}, 'optimisedPlots': [],
    }
import math
from collections import defaultdict
from datetime import date

from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.views import View

# ── adjust this import to match your actual app name ──────────────
from tender.models import (
    Cluster, JobActivity, Allocation,
    ActivityCatalog, ClusterMukkadamActivityRate,
    Mukkadam, ClusterMukkadamAssignment,
)
# ──────────────────────────────────────────────────────────────────

DEFAULT_PRODUCTIVITY = 0.14   # acres per worker per day (fallback)


# ════════════════════════════════════════════════════════════════════
# HELPER: resolve productivity for (cluster, activity)
# Priority: ClusterMukkadamActivityRate → ActivityCatalog.default → 0.14
# ════════════════════════════════════════════════════════════════════
def _productivity(cluster, activity_obj, _cache={}):
    key = (cluster.pk, activity_obj.pk)
    if key not in _cache:
        rate = ClusterMukkadamActivityRate.objects.filter(
            cluster=cluster, activity=activity_obj
        ).values_list('productivity_per_worker', flat=True).first()
        if rate:
            _cache[key] = float(rate)
        elif activity_obj.default_productivity_per_worker:
            _cache[key] = float(activity_obj.default_productivity_per_worker)
        else:
            _cache[key] = DEFAULT_PRODUCTIVITY
    return _cache[key]


def _workers_needed(total_area, productivity):
    """Ceiling division: acres / (acres per worker per day)."""
    if not productivity or productivity <= 0:
        return 0
    return math.ceil(float(total_area) / productivity)


# ════════════════════════════════════════════════════════════════════
# HELPER: derive completion status from Allocation
# ════════════════════════════════════════════════════════════════════
def _activity_status(ja_allocs):
    """
    ja_allocs: queryset/list of Allocation objects for one JobActivity
    Returns: 'completed' | 'in_progress' | 'allocated' | 'pending'
    """
    statuses = {a.work_status for a in ja_allocs}
    if 'completed' in statuses:
        return 'completed'
    if 'in_progress' in statuses:
        return 'in_progress'
    if statuses:                   # has allocations but not started
        return 'allocated'
    return 'pending'


# ════════════════════════════════════════════════════════════════════
# VIEW 1 — List of clusters (for the cluster-switcher dropdown)
# GET /api/planning/clusters/
# ════════════════════════════════════════════════════════════════════
class ClusterListView(View):
    def get(self, request):
        clusters = Cluster.objects.values('id', 'name', 'districts', 'talukas', 'villages')
        return JsonResponse({'clusters': list(clusters)})


# ════════════════════════════════════════════════════════════════════
# VIEW 2 — Full season data for one cluster
# GET /api/planning/clusters/<cluster_id>/season-data/
# ════════════════════════════════════════════════════════════════════
class ClusterSeasonDataView(View):
    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'Cluster not found'}, status=404)

        # ── 1. Fetch all valid JobActivities for this cluster ──────────
        # Exclude: total_area=0, is_lost=True, no scheduled_date
        activities_qs = (
            JobActivity.objects
            .filter(
                job__clusters=cluster,
                is_lost=False,
                scheduled_date__isnull=False,
                total_area__gt=0,
            )
            .select_related(
                'job',
                'job__farmer',
                'job__booking',
                'activity',
                'plot',
            )
            .prefetch_related(
                Prefetch(
                    'allocations',
                    queryset=Allocation.objects.only(
                        'job_activity_id', 'work_status', 'allocated_workers',
                        'allocated_area', 'mukkadam_id', 'allocated_date',
                    )
                )
            )
            .order_by('scheduled_date')
        )

        activities = list(activities_qs)

        if not activities:
            return JsonResponse(_empty_response(cluster))

        # ── 2. Build intermediate records ──────────────────────────────
        records = []
        all_dates = []

        for ja in activities:
            prod  = _productivity(cluster, ja.activity)
            workers = _workers_needed(ja.total_area, prod)
            allocs  = list(ja.allocations.all())
            status  = _activity_status(allocs)

            # Village: use Farmer.location; fall back to cluster name
            village = (ja.job.farmer.location or '').strip() or cluster.name

            # Payment status
            try:
                pay_status = ja.job.booking.status  # UNPAID/PARTIALLY_PAID/PAID
                pay_label  = {
                    'UNPAID': 'Yet to Pay',
                    'PARTIALLY_PAID': 'Partial',
                    'PAID': 'Paid',
                }.get(pay_status, pay_status)
            except Exception:
                pay_label = 'Yet to Pay'

            records.append({
                'jaId':         ja.pk,
                'jobId':        ja.job.job_id,
                'plotId':       ja.plot.plot_code if ja.plot and ja.plot.plot_code else str(ja.plot_id or ja.pk),
                'plotName':     ja.plot.name if ja.plot else f'Plot-{ja.pk}',
                'farmer':       ja.job.farmer.farmer_name,
                'contact':      ja.job.farmer.phone_number or '',
                'village':      village,
                'variety':      ja.job.variety or ja.job.crop_name or '',
                'acre':         float(ja.total_area),
                'activity':     ja.activity.name,
                'date':         ja.scheduled_date.isoformat(),
                'workers':      workers,
                'productivity': prod,
                'paymentStatus': pay_label,
                'status':       status,
                'allocationStatus': ja.allocation_status,
                'isStrict':     ja.is_strict,
            })
            all_dates.append(ja.scheduled_date)

        season_start = min(all_dates)
        season_end   = max(all_dates)

        # ── 3. seasonSummary ───────────────────────────────────────────
        total_acres       = sum(r['acre'] for r in records)
        total_worker_days = sum(r['workers'] for r in records)
        unique_farmers    = len({r['farmer'] for r in records})
        unique_plots      = len({r['plotId'] for r in records})
        unique_villages   = len({r['village'] for r in records})
        unique_activities = len({r['activity'] for r in records})

        # Daily worker counts for peak calculation
        daily_totals = defaultdict(int)
        for r in records:
            daily_totals[r['date']] += r['workers']
        peak_daily = max(daily_totals.values()) if daily_totals else 0
        active_days = len(daily_totals)

        season_summary = {
            'cluster':               cluster.name,
            'clusterId':             cluster.pk,
            'totalPlots':            unique_plots,
            'totalFarmers':          unique_farmers,
            'totalAcres':            round(total_acres, 2),
            'totalVillages':         unique_villages,
            'totalActivities':       unique_activities,
            'seasonStart':           season_start.isoformat(),
            'seasonEnd':             season_end.isoformat(),
            'totalWorkerDays':       total_worker_days,
            'peakDailyWorkers':      peak_daily,
            'activeDays':            active_days,
            'totalActivityInstances': len(records),
        }

        # ── 4. dailyDemand ─────────────────────────────────────────────
        by_date = defaultdict(list)
        for r in records:
            by_date[r['date']].append(r)

        daily_demand = []
        for d_str in sorted(by_date.keys()):
            day_records = by_date[d_str]
            by_activity = defaultdict(int)
            by_village  = defaultdict(int)

            for r in day_records:
                by_activity[r['activity']] += r['workers']
                by_village[r['village']]   += r['workers']

            daily_demand.append({
                'date':         d_str,
                'totalWorkers': sum(r['workers'] for r in day_records),
                'byActivity':   dict(by_activity),
                'byVillage':    dict(by_village),
                'plotCount':    len(day_records),
                'plots': [{
                    'plotId':   r['plotId'],
                    'farmer':   r['farmer'],
                    'village':  r['village'],
                    'activity': r['activity'],
                    'acre':     r['acre'],
                    'workers':  r['workers'],
                    'status':   r['status'],
                } for r in day_records],
            })

        # ── 5. villageSummary ──────────────────────────────────────────
        village_data = defaultdict(lambda: {
            'totalAcres': 0.0, 'plotCount': 0,
            'totalWorkerDays': 0, 'farmerCount': set(),
            'dates': [],
        })
        for r in records:
            v = r['village']
            village_data[v]['totalAcres']      += r['acre']
            village_data[v]['plotCount']       += 1
            village_data[v]['totalWorkerDays'] += r['workers']
            village_data[v]['farmerCount'].add(r['farmer'])
            village_data[v]['dates'].append(r['date'])

        village_summary = {}
        for v, vd in village_data.items():
            dates = sorted(vd['dates'])
            village_summary[v] = {
                'totalAcres':      round(vd['totalAcres'], 2),
                'plotCount':       vd['plotCount'],
                'totalWorkerDays': vd['totalWorkerDays'],
                'farmerCount':     len(vd['farmerCount']),
                'dateRange':       {'start': dates[0], 'end': dates[-1]},
            }

        # ── 6. activityStats ──────────────────────────────────────────
        activity_data = defaultdict(lambda: {
            'totalWorkerDays': 0, 'totalAcres': 0.0,
            'plotCount': 0, 'completedCount': 0, 'dates': [],
        })
        for r in records:
            a = r['activity']
            activity_data[a]['totalWorkerDays'] += r['workers']
            activity_data[a]['totalAcres']      += r['acre']
            activity_data[a]['plotCount']       += 1
            activity_data[a]['dates'].append(r['date'])
            if r['status'] == 'completed':
                activity_data[a]['completedCount'] += 1

        activity_stats = {}
        for a, ad in activity_data.items():
            dates = sorted(ad['dates'])
            activity_stats[a] = {
                'totalWorkerDays': ad['totalWorkerDays'],
                'totalAcres':      round(ad['totalAcres'], 2),
                'plotCount':       ad['plotCount'],
                'completedCount':  ad['completedCount'],
                'dateRange':       {'start': dates[0], 'end': dates[-1]},
            }

        # ── 7. plots (flat list — for original index.html compatibility) ─
        plots_flat = [{
            'plotId':        r['plotId'],
            'farmer':        r['farmer'],
            'contact':       r['contact'],
            'village':       r['village'],
            'variety':       r['variety'],
            'acre':          r['acre'],
            'paymentStatus': r['paymentStatus'],
            'status':        r['status'],
        } for r in records]

        # ── 8. allActivities (flat — for farmer details table) ────────
        all_activities_flat = [{
            'jaId':           r['jaId'],
            'jobId':          r['jobId'],
            'plotId':         r['plotId'],
            'plotName':       r['plotName'],
            'farmer':         r['farmer'],
            'village':        r['village'],
            'variety':        r['variety'],
            'acre':           r['acre'],
            'activity':       r['activity'],
            'date':           r['date'],
            'workers':        r['workers'],
            'paymentStatus':  r['paymentStatus'],
            'status':         r['status'],
            'allocationStatus': r['allocationStatus'],
            'isStrict':       r['isStrict'],
        } for r in records]

        return JsonResponse({
            'seasonSummary':  season_summary,
            'dailyDemand':    daily_demand,
            'villageSummary': village_summary,
            'activityStats':  activity_stats,
            'plots':          plots_flat,
            'allActivities':  all_activities_flat,
            # labourCalendar kept for backward compat (same as dailyDemand)
            'labourCalendar': daily_demand,
        })


def _empty_response(cluster):
    return {
        'seasonSummary': {
            'cluster': cluster.name, 'clusterId': cluster.pk,
            'totalPlots': 0, 'totalFarmers': 0, 'totalAcres': 0,
            'totalVillages': 0, 'totalActivities': 0,
            'seasonStart': None, 'seasonEnd': None,
            'totalWorkerDays': 0, 'peakDailyWorkers': 0,
            'activeDays': 0, 'totalActivityInstances': 0,
        },
        'dailyDemand': [], 'villageSummary': {}, 'activityStats': {},
        'plots': [], 'allActivities': [], 'labourCalendar': [],
    }


# ════════════════════════════════════════════════════════════════════
# VIEW 3 — Mukkadam supply for a cluster (for Teams tab)
# GET /api/planning/clusters/<cluster_id>/supply/
# ════════════════════════════════════════════════════════════════════
class ClusterSupplyView(View):
    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'Cluster not found'}, status=404)

        assignments = (
            ClusterMukkadamAssignment.objects
            .filter(cluster=cluster, is_active=True)
            .select_related('mukkadam')
        )

        teams = []
        total_workers = 0
        for asgn in assignments:
            m = asgn.mukkadam
            crew = m.crew_size or 0
            total_workers += crew
            teams.append({
                'mukkadamId':    m.mukkadam_id,
                'name':          m.mukkadam_name,
                'mobile':        m.mobile_numbers,
                'crewSize':      crew,
                'village':       m.village or '',
                'type':          asgn.mukkadam_type,   # permanent / updown
                'joinedDate':    asgn.joined_date.isoformat() if asgn.joined_date else None,
                'weeklyAmount':  float(asgn.weekly_amount or 0),
                'efficiency':    float(m.efficiency or DEFAULT_PRODUCTIVITY),
                'workMode':      m.work_mode or '',
            })

        return JsonResponse({
            'clusterId':    cluster_id,
            'clusterName':  cluster.name,
            'totalWorkers': total_workers,
            'teamCount':    len(teams),
            'teams':        teams,
        })


# ════════════════════════════════════════════════════════════════════
# VIEW 4 — Completion status breakdown (for dashboard KPIs)
# GET /api/planning/clusters/<cluster_id>/completion-stats/
# ════════════════════════════════════════════════════════════════════
class ClusterCompletionStatsView(View):
    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'Cluster not found'}, status=404)

        base_qs = JobActivity.objects.filter(
            job__clusters=cluster,
            is_lost=False,
            scheduled_date__isnull=False,
            total_area__gt=0,
        )

        total = base_qs.count()

        # IDs of activities with at least one completed allocation
        completed_ids = set(
            Allocation.objects
            .filter(
                job_activity__job__clusters=cluster,
                job_activity__is_lost=False,
                job_activity__total_area__gt=0,
                work_status='completed',
            )
            .values_list('job_activity_id', flat=True)
        )

        in_progress_ids = set(
            Allocation.objects
            .filter(
                job_activity__job__clusters=cluster,
                job_activity__is_lost=False,
                job_activity__total_area__gt=0,
                work_status='in_progress',
            )
            .values_list('job_activity_id', flat=True)
        ) - completed_ids

        allocated_ids = set(
            Allocation.objects
            .filter(
                job_activity__job__clusters=cluster,
                job_activity__is_lost=False,
                job_activity__total_area__gt=0,
                work_status='work_not_started',
            )
            .values_list('job_activity_id', flat=True)
        ) - completed_ids - in_progress_ids

        completed   = len(completed_ids)
        in_progress = len(in_progress_ids)
        allocated   = len(allocated_ids)
        pending     = total - completed - in_progress - allocated

        return JsonResponse({
            'clusterId':    cluster_id,
            'total':        total,
            'completed':    completed,
            'inProgress':   in_progress,
            'allocated':    allocated,
            'pending':      max(pending, 0),
            'completionPct': round(completed / total * 100, 1) if total else 0,
        })