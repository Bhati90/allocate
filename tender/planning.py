

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
    queryset=Allocation.objects.select_related('mukkadam'),
),
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
                # After the existing fields in records.append({...})
'salesDate': ja.sales_date.isoformat() if ja.sales_date else None,
'allocatedDate': allocs[0].allocated_date.isoformat() if allocs and allocs[0].allocated_date else None,
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
# VIEW — Cluster-wise funnel
# GET /api/planning/clusters/funnel/
# Returns overview/completed/in_progress/pending for EVERY cluster
# ════════════════════════════════════════════════════════════════════
class ClusterFunnelView(View):
    def get(self, request):
        cluster_id = request.GET.get('cluster')
        if cluster_id:
            clusters = Cluster.objects.filter(pk=cluster_id)
        else:
            clusters = Cluster.objects.all() # adjust filter as needed
        result = []

        for cluster in clusters:
            activities_qs = (
                JobActivity.objects
                .filter(
                    job__clusters=cluster,
                    is_lost=False,
                    total_area__gt=0,
                    scheduled_date__isnull=False,
                )
                .select_related('job', 'job__farmer', 'job__booking', 'activity')
                .prefetch_related(
                    Prefetch('allocations', queryset=Allocation.objects.only('work_status', 'mukkadam_amount', 'job_activity_id'))
                )
            )

            activities = list(activities_qs)
            if not activities:
                result.append(_empty_cluster_funnel(cluster))
                continue

            seen_keys = set()
            job_act_classes = defaultdict(list)
            job_farmer = {}

            co = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}
            ip = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}
            pe = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}

            ov_pruning = 0.0
            ov_all = 0.0

            def is_pruning_act(name):
                n = (name or '').lower()
                return 'pruning' in n or 'छाटणी' in n

            for ja in activities:
                area = float(ja.total_area or 0)
                if area <= 0:
                    continue
                key = f"{ja.job_id}|{ja.plot_id}|{ja.activity.name}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                allocs = list(ja.allocations.all())
                price = float(ja.total_price or 0)
                pruning = is_pruning_act(ja.activity.name)
                status_val = ja.allocation_status or 'pending'

                ov_all += area
                if pruning:
                    ov_pruning += area

                all_done = len(allocs) > 0 and all(a.work_status == 'completed' for a in allocs)
                has_wip  = any(a.work_status == 'in_progress' for a in allocs)

                if status_val == 'fully_allocated' and all_done:
                    act_class = 'completed'
                elif status_val in ('fully_allocated', 'partially_allocated', 'in_progress') or has_wip:
                    act_class = 'in_progress'
                else:
                    act_class = 'pending'

                done_amt = sum(float(a.mukkadam_amount or 0) for a in allocs if a.work_status == 'completed')
                bucket = co if act_class == 'completed' else ip if act_class == 'in_progress' else pe
                bucket['activities'] += 1
                bucket['all_acres']  += area
                if pruning:
                    bucket['pruning_acres'] += area
                bucket['worth']        += price
                bucket['mukkadam_amt'] += done_amt

                job_act_classes[ja.job_id].append(act_class)
                job_farmer[ja.job_id] = ja.job.farmer_id

            # classify jobs & farmers
            co_jobs, ip_jobs, pe_jobs = set(), set(), set()
            farmer_done, farmer_wip, farmer_seen = set(), set(), set()
            for job_id, classes in job_act_classes.items():
                fid = job_farmer[job_id]
                farmer_seen.add(fid)
                if all(c == 'completed' for c in classes):
                    co_jobs.add(job_id); farmer_done.add(fid)
                elif any(c in ('completed', 'in_progress') for c in classes):
                    ip_jobs.add(job_id); farmer_wip.add(fid)
                else:
                    pe_jobs.add(job_id)

            co_farmers, ip_farmers, pe_farmers = set(), set(), set()
            for fid in farmer_seen:
                if fid in farmer_done and fid in farmer_wip:
                    co_farmers.add(fid)
                elif fid in farmer_wip:
                    ip_farmers.add(fid)
                elif fid in farmer_done:
                    co_farmers.add(fid)
                else:
                    pe_farmers.add(fid)

            # booking totals for this cluster's jobs
            from django.db.models import Sum
            from decimal import Decimal
            booking = (
                Job.objects.filter(clusters=cluster)
                .aggregate(
                    bv=Sum('booking__total_amount'),
                    col=Sum('booking__advance_paid'),
                    bal=Sum('booking__balance'),
                )
            )

            result.append({
                'clusterId':   cluster.pk,
                'clusterName': cluster.name,
                'overview': {
                    'farmers':       len(farmer_seen),
                    'jobs':          len(job_act_classes),
                    'activities':    len(seen_keys),
                    'acres_first':   round(ov_pruning, 1),
                    'acres_all':     round(ov_all, 1),
                    'booking_value': float(booking['bv'] or 0),
                    'collected':     float(booking['col'] or 0),
                    'balance_due':   float(booking['bal'] or 0),
                },
                'completed': {
                    'farmers':      len(co_farmers),
                    'jobs':         len(co_jobs),
                    'activities':   co['activities'],
                    'acres_first':  round(co['pruning_acres'], 1),
                    'acres_all':    round(co['all_acres'], 1),
                    'worth_of_work': round(co['worth'], 2),
                    'mukadam_paid': round(co['mukkadam_amt'], 2),
                },
                'in_progress': {
                    'farmers':      len(ip_farmers),
                    'jobs':         len(ip_jobs),
                    'activities':   ip['activities'],
                    'acres_first':  round(ip['pruning_acres'], 1),
                    'acres_all':    round(ip['all_acres'], 1),
                    'worth_of_work': round(ip['worth'], 2),
                    'mukadam_payable': round(ip['mukkadam_amt'], 2),
                },
                'pending': {
                    'farmers':      len(pe_farmers),
                    'jobs':         len(pe_jobs),
                    'activities':   pe['activities'],
                    'acres_first':  round(pe['pruning_acres'], 1),
                    'acres_all':    round(pe['all_acres'], 1),
                    'worth_pending': round(pe['worth'], 2),
                    'mukadam_earnings_pending': round(pe['mukkadam_amt'], 2),
                },
            })

        return JsonResponse({'clusters': result})


def _empty_cluster_funnel(cluster):
    empty = {'farmers': 0, 'jobs': 0, 'activities': 0, 'acres_first': 0.0, 'acres_all': 0.0}
    return {
        'clusterId': cluster.pk, 'clusterName': cluster.name,
        'overview':     {**empty, 'booking_value': 0, 'collected': 0, 'balance_due': 0},
        'completed':    {**empty, 'worth_of_work': 0, 'mukadam_paid': 0},
        'in_progress':  {**empty, 'worth_of_work': 0, 'mukadam_payable': 0},
        'pending':      {**empty, 'worth_pending': 0, 'mukadam_earnings_pending': 0},
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
            .select_related('job', 'job__farmer', 'job__booking', 'activity', 'plot')
            .prefetch_related(
                Prefetch(
            'allocations',
            queryset=Allocation.objects.select_related('mukkadam'),
        ),
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
            prod = _productivity(cluster, ja.activity)
            workers = _workers_needed(ja.total_area, prod)
            allocs = list(ja.allocations.all())
            status = _activity_status(allocs)

            # Village: use Farmer.location; fall back to cluster name
            village = (ja.job.farmer.location or '').strip() or cluster.name

            # Payment status
            try:
                pay_status = ja.job.booking.status  # UNPAID/PARTIALLY_PAID/PAID
                pay_label = {
                    'UNPAID': 'Yet to Pay',
                    'PARTIALLY_PAID': 'Partial',
                    'PAID': 'Paid',
                }.get(pay_status, pay_status)
            except Exception:
                pay_label = 'Yet to Pay'

            # NEW: serialise allocations for this JobActivity
            allocations_payload = []
            completed_allocations = []

            for a in allocs:
                item = {
                    'id': a.id,
                    'mukkadamId': a.mukkadam_id,
                    'mukkadamName': getattr(a.mukkadam, 'mukkadam_name', ''),
                    'mukkadamMobile': getattr(a.mukkadam, 'mobile_numbers', ''),
                    'allocatedDate': a.allocated_date.isoformat() if a.allocated_date else None,
                    'allocatedArea': float(a.allocated_area or 0),
                    'allocatedWorkers': a.allocated_workers,
                    'workStatus': a.work_status,
                }
                allocations_payload.append(item)
                if a.work_status == 'completed':
                    completed_allocations.append(item)

            records.append({
                'jaId': ja.pk,
                'jobId': ja.job.job_id,
                'plotId': ja.plot.plot_code if ja.plot and ja.plot.plot_code else str(ja.plot_id or ja.pk),
                'plotName': ja.plot.name if ja.plot else f'Plot-{ja.pk}',
                'farmer': ja.job.farmer.farmer_name,
                'contact': ja.job.farmer.phone_number or '',
                'village': village,
                'variety': ja.job.variety or ja.job.crop_name or '',
                'acre': float(ja.total_area),
                'activity': ja.activity.name,
                'date': ja.scheduled_date.isoformat(),
                'workers': workers,
                'productivity': prod,
                'paymentStatus': pay_label,
                'status': status,
                'allocationStatus': ja.allocation_status,
                'isStrict': ja.is_strict,
                # NEW
                    'salesDate': ja.sales_date.isoformat() if ja.sales_date else None,
    'allocatedDate': allocs[0].allocated_date.isoformat() if allocs and allocs[0].allocated_date else None,
                'allocations': allocations_payload,
                'completedAllocations': completed_allocations,
                'isCompleted': bool(completed_allocations),
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
                        'salesDate': r.get('salesDate'),
    'allocatedDate': r.get('allocatedDate'),
        'allocationStatus': r.get('allocationStatus'),
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
            'jaId': r['jaId'],
            'jobId': r['jobId'],
            'plotId': r['plotId'],
            'plotName': r['plotName'],
            'farmer': r['farmer'],
            'village': r['village'],
            'variety': r['variety'],
            'acre': r['acre'],
            'activity': r['activity'],
            'date': r['date'],
            'workers': r['workers'],
            'paymentStatus': r['paymentStatus'],
            'status': r['status'],
            'allocationStatus': r['allocationStatus'],
            'isStrict': r['isStrict'],
            # NEW
            'allocations': r['allocations'],
            'completedAllocations': r['completedAllocations'],
            'isCompleted': r['isCompleted'],
            'salesDate': r.get('salesDate'),
        'allocatedDate': r.get('allocatedDate'),
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

def _resolve_available_dates(asgn):
    """
    Returns a list of ISO date strings for which an updown mukkadam is available.
    Handles both 'range' mode (expands to daily list) and 'specific' mode (returns as-is).
    """
    from datetime import date, timedelta

    if asgn.updown_mode == 'specific':
        return [str(d) for d in (asgn.updown_specific_dates or [])]

    if asgn.updown_mode == 'range':
        start = asgn.updown_from_date
        end   = asgn.updown_to_date
        if not start or not end:
            return []
        dates = []
        cur = start
        while cur <= end:
            dates.append(cur.isoformat())
            cur += timedelta(days=1)
        return dates

    return []


# planning_api_views.py  ─  GET /tender/clustersp/<cluster_id>/overview/

import math
from collections import defaultdict
from django.http import JsonResponse
from django.views import View
from django.db.models import Prefetch, Sum, Q
from tender.models import (
    Cluster, Job, JobActivity, Allocation,
    JobBooking, FarmerPayment, MukkadamPayment,
    ClusterMukkadamAssignment,
)


class ClusterOverviewView(View):
    """
    Returns the 4-section overview card shown in index.html:
      - overview     (all farmers)
      - completed    (as of today)
      - in_progress  (allocated / in progress)
      - pending      (yet to start)
    """

    def get(self, request, cluster_id):
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse({'error': 'not found'}, status=404)

        # ── 1. Fetch all valid JobActivities for this cluster ──────────
        activities_qs = (
            JobActivity.objects
            .filter(
                job__clusters=cluster,
                is_lost=False,
                total_area__gt=0,
                scheduled_date__isnull=False,
            )
            .select_related('job', 'job__farmer', 'job__booking', 'activity', 'plot')
            .prefetch_related(
    Prefetch(
        'allocations',
        queryset=Allocation.objects.select_related('mukkadam'),
    ),
)
            .order_by('job_id', 'scheduled_date')
        )

        activities = list(activities_qs)

        if not activities:
            return JsonResponse(_empty_overview())

        # ── 2. Build per-job structures ────────────────────────────────
        # job_id → {
        #   farmer_id, farmer_name,
        #   first_activity_area (pruning/1st),
        #   total_area,
        #   booking_value, collected, balance,
        #   activity_statuses: set of activity-level statuses
        #   job_status: 'completed' | 'in_progress' | 'pending'
        #   mukadam_paid (sum of mukkadam_amount on completed allocs)
        # }

        job_map = {}         # job_id → job meta
        first_seen = {}      # job_id → True/False (first activity processed)

        for ja in activities:
            jid = ja.job_id
            if jid not in job_map:
                job = ja.job
                # booking
                try:
                    booking_value = float(job.booking.total_amount or 0)
                    collected = float(job.booking.advance_paid or 0)
                    balance = float(job.booking.balance or 0)
                except Exception:
                    booking_value = collected = balance = 0.0

                job_map[jid] = {
                    'farmer_id':          job.farmer_id,
                    'farmer_name':        job.farmer.farmer_name,
                    'first_area':         0.0,   # pruning / 1st activity
                    'total_area':         0.0,
                    'booking_value':      booking_value,
                    'collected':          collected,
                    'balance':            balance,
                    'act_statuses':       [],   # one entry per activity
                    'mukadam_paid':       0.0,
                }
                first_seen[jid] = False

            entry = job_map[jid]
            area = float(ja.total_area)
            entry['total_area'] += area

            # first activity = pruning/1st (activities ordered by scheduled_date)
            if not first_seen[jid]:
                entry['first_area'] += area
                first_seen[jid] = True

            # activity-level status
            allocs = list(ja.allocations.all())
            ws = {a.work_status for a in allocs}
            if 'completed' in ws:
                act_status = 'completed'
                # sum mukkadam payable for completed allocs
                entry['mukadam_paid'] += sum(
                    float(a.mukkadam_amount) for a in allocs
                    if a.work_status == 'completed'
                )
            elif 'in_progress' in ws:
                act_status = 'in_progress'
            elif allocs:
                act_status = 'allocated'
            else:
                act_status = 'pending'

            entry['act_statuses'].append(act_status)

        # ── 3. Classify each job ───────────────────────────────────────
        for jid, entry in job_map.items():
            statuses = set(entry['act_statuses'])
            if all(s == 'completed' for s in entry['act_statuses']):
                entry['job_status'] = 'completed'
            elif statuses & {'completed', 'in_progress', 'allocated'}:
                entry['job_status'] = 'in_progress'
            else:
                entry['job_status'] = 'pending'

        jobs = list(job_map.values())

        # ── 4. Per-farmer bucketing ────────────────────────────────────
        # A farmer is "completed" only if ALL their jobs are completed.
        # "in_progress" if any job is in_progress.
        # "pending" otherwise.

        farmer_jobs = defaultdict(list)
        for entry in jobs:
            farmer_jobs[entry['farmer_id']].append(entry)

        farmer_buckets = {}   # farmer_id → 'completed' | 'in_progress' | 'pending'
        for fid, fentries in farmer_jobs.items():
            job_statuses = {e['job_status'] for e in fentries}
            if all(s == 'completed' for s in [e['job_status'] for e in fentries]):
                farmer_buckets[fid] = 'completed'
            elif job_statuses & {'in_progress'}:
                farmer_buckets[fid] = 'in_progress'
            else:
                farmer_buckets[fid] = 'pending'

        # ── 5. Aggregate each section ──────────────────────────────────
        def _agg(entries):
            farmer_ids = {e['farmer_id'] for e in entries}
            job_ids    = set()  # only for distinct job count
            acts_total = 0
            first_area = 0.0
            total_area = 0.0
            booking_value = 0.0
            collected  = 0.0
            balance    = 0.0
            mukadam_paid = 0.0

            seen_jobs = set()
            for e in entries:
                jid = e.get('_jid')  # need to pass this — see below
                acts_total += len(e['act_statuses'])
                first_area += e['first_area']
                total_area += e['total_area']
                booking_value += e['booking_value']
                collected  += e['collected']
                balance    += e['balance']
                mukadam_paid += e['mukadam_paid']

            return {
                'farmers':       len(farmer_ids),
                'jobs':          len(entries),
                'activities':    acts_total,
                'acres_first':   round(first_area, 1),
                'acres_all':     round(total_area, 1),
                'booking_value': round(booking_value, 2),
                'collected':     round(collected, 2),
                'balance_due':   round(balance, 2),
                'mukadam_paid':  round(mukadam_paid, 2),
            }

        # Re-attach job_id to entries for counting
        job_entries_by_status = defaultdict(list)
        for jid, entry in job_map.items():
            entry['_jid'] = jid
            job_entries_by_status[entry['job_status']].append(entry)

        completed_entries   = job_entries_by_status['completed']
        in_progress_entries = job_entries_by_status['in_progress']
        pending_entries     = job_entries_by_status['pending']
        all_entries         = jobs

        # Attach _jid to all_entries too
        for e in all_entries:
            pass  # already set above

        # For the "completed" section: only activities that are completed
        # For "in_progress": only activities that are allocated/in_progress
        # For "pending": activities with no allocation

        def _count_activities_by_type(entries, target_statuses):
            return sum(
                sum(1 for s in e['act_statuses'] if s in target_statuses)
                for e in entries
            )

        # ── 6. Completed section specifics ────────────────────────────
        comp_farmers = {e['farmer_id'] for e in completed_entries}
        comp_acts    = _count_activities_by_type(
            completed_entries, {'completed'}
        )
        comp_first_area = sum(e['first_area'] for e in completed_entries)
        comp_all_area   = sum(e['total_area'] for e in completed_entries)
        comp_worth      = sum(
            sum(float(a.mukkadam_amount) for a in ja.allocations.all()
                if a.work_status == 'completed')
            for ja in activities
            if ja.job_id in {e['_jid'] for e in completed_entries}
        )

        # Simpler: just use pre-aggregated mukadam_paid
        comp_mukadam_paid = sum(e['mukadam_paid'] for e in completed_entries)

        # ── 7. In-progress section ────────────────────────────────────
        ip_farmers = {e['farmer_id'] for e in in_progress_entries}
        ip_acts    = _count_activities_by_type(
            in_progress_entries, {'allocated', 'in_progress', 'completed'}
        )
        ip_first_area = sum(e['first_area'] for e in in_progress_entries)
        ip_all_area   = sum(e['total_area'] for e in in_progress_entries)
        ip_mukadam    = sum(e['mukadam_paid'] for e in in_progress_entries)

        # ── 8. Pending section ────────────────────────────────────────
        pend_farmers = {e['farmer_id'] for e in pending_entries}
        pend_acts    = _count_activities_by_type(
            pending_entries, {'pending'}
        )
        pend_first_area = sum(e['first_area'] for e in pending_entries)
        pend_all_area   = sum(e['total_area'] for e in pending_entries)

        # ── 9. Overview totals ────────────────────────────────────────
        all_farmers     = set(farmer_jobs.keys())
        all_jobs_count  = len(job_map)
        all_acts_count  = sum(len(e['act_statuses']) for e in jobs)
        all_first_area  = sum(e['first_area'] for e in jobs)
        all_total_area  = sum(e['total_area'] for e in jobs)
        all_booking     = sum(e['booking_value'] for e in jobs)
        all_collected   = sum(e['collected'] for e in jobs)
        all_balance     = sum(e['balance'] for e in jobs)

        return JsonResponse({
            'overview': {
                'farmers':       len(all_farmers),
                'jobs':          all_jobs_count,
                'activities':    all_acts_count,
                'acres_first':   round(all_first_area, 1),
                'acres_all':     round(all_total_area, 1),
                'booking_value': round(all_booking, 2),
                'collected':     round(all_collected, 2),
                'balance_due':   round(all_balance, 2),
            },
            'completed': {
                'farmers':      len(comp_farmers),
                'jobs':         len(completed_entries),
                'activities':   comp_acts,
                'acres_first':  round(comp_first_area, 1),
                'acres_all':    round(comp_all_area, 1),
                'worth_of_work': round(comp_mukadam_paid, 2),
                'mukadam_paid': round(comp_mukadam_paid, 2),
                'transport':    None,
            },
            'in_progress': {
                'farmers':      len(ip_farmers),
                'jobs':         len(in_progress_entries),
                'activities':   ip_acts,
                'acres_first':  round(ip_first_area, 1),
                'acres_all':    round(ip_all_area, 1),
                'worth_of_work': round(ip_mukadam, 2),
                'mukadam_payable': round(ip_mukadam, 2),
            },
            'pending': {
                'farmers':      len(pend_farmers),
                'jobs':         len(pending_entries),
                'activities':   pend_acts,
                'acres_first':  round(pend_first_area, 1),
                'acres_all':    round(pend_all_area, 1),
                'worth_pending': 0,
                'mukadam_earnings_pending': 0,
            },
        })



# GET /tender/clustersp/overview/
from collections import defaultdict                          # ✅ FIX 1: was missing, crashed at runtime
from django.http import JsonResponse
from django.views import View
from django.db.models import Prefetch
from tender.models import JobActivity, Allocation


def _empty_overview():                                       # ✅ FIX 2: was called but never defined
    empty = {
        'jobs': 0, 'activities': 0, 'farmers': 0,
        'acres_first': 0.0, 'acres_all': 0.0,
        'booking_value': 0.0, 'collected': 0.0,
        'balance_due': 0.0, 'mukadam_paid': 0.0,
        'worth_of_work': 0.0,
    }
    return {
        'overview':     {**empty},
        'completed':    {**empty, 'transport': 0.0},
        'in_progress':  {**empty, 'mukadam_payable': 0.0},
        'pending':      {**empty, 'worth_pending': 0.0, 'mukadam_earnings_pending': 0.0},
    }

from decimal import Decimal
from collections import defaultdict
from django.http import JsonResponse
from django.views import View
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce

from tender.models import Farmer, Job, JobActivity, Allocation


def dec(v):
    return float(v or 0)

from decimal import Decimal
from collections import defaultdict
from django.http import JsonResponse
from django.views import View
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce

from tender.models import Farmer, Job, JobActivity, Allocation


def dec(v):
    return float(v or 0)


def is_pruning(name):
    """Match: Pruning (छाटणी), Pruning (छाटणी) 1, Pruning (छाटणी) 2, Pruning (छाटणी) 3"""
    n = (name or '').lower().strip()
    return 'pruning' in n or 'छाटणी' in n


class GlobalOverviewView(View):
    def get(self, request):

        # ── VALID ACTIVITIES ─────────────────────────────────
        valid_jas = (
            JobActivity.objects
            .filter(total_area__gt=0, is_lost=False)
            .select_related('activity', 'job', 'job__farmer')
            .prefetch_related('allocations')
        )

        jas_list = list(valid_jas)

        if not jas_list:
            empty = {
                'farmers': 0, 'jobs': 0, 'activities': 0,
                'acres_pruning': 0.0, 'acres_all': 0.0,
                'worth_of_work': 0.0, 'mukkadam_paid': 0.0,
            }
            return JsonResponse({
                'overview': {**empty, 'booking_value': 0, 'collected': 0, 'balance_due': 0},
                'completed': {**empty, 'transport_spend': 0},
                'in_progress': {**empty, 'mukkadam_payable': 0},
                'pending': {**empty, 'worth_pending': 0, 'mukkadam_earnings_pending': 0},
            })

        # ── BUCKETS ──────────────────────────────────────────
        co = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}
        ip = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}
        pe = {'activities': 0, 'pruning_acres': 0.0, 'all_acres': 0.0, 'worth': 0.0, 'mukkadam_amt': 0.0}

        ov_pruning_acres = 0.0
        ov_all_acres = 0.0

        # job_id -> list of activity classifications
        job_act_classes = defaultdict(list)
        # job_id -> farmer_id
        job_farmer = {}

        # Dedup: job_id | plot_id | activity_name
        seen_keys = set()

        for ja in jas_list:
            area = float(ja.total_area or 0)
            if area <= 0:
                continue

            key = f"{ja.job_id}|{ja.plot_id}|{ja.activity.name}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            allocs = list(ja.allocations.all())
            price = float(ja.total_price or 0)
            pruning = is_pruning(ja.activity.name)
            status_val = ja.allocation_status or 'pending'

            # ── Overview totals ──────────────────────────────
            ov_all_acres += area
            if pruning:
                ov_pruning_acres += area

            # ── Classify activity ────────────────────────────
            # Completed = fully_allocated + ALL allocations work_status='completed'
            all_allocs_complete = (
                len(allocs) > 0 and
                all(a.work_status == 'completed' for a in allocs)
            )
            has_wip_alloc = any(a.work_status == 'in_progress' for a in allocs)

            if status_val == 'fully_allocated' and all_allocs_complete:
                act_class = 'completed'
            elif status_val in ('fully_allocated', 'partially_allocated', 'in_progress') or has_wip_alloc:
                act_class = 'in_progress'
            else:
                act_class = 'pending'

            # ── Money ────────────────────────────────────────
            # Worth = total_price (farmer rate × area) from JobActivity
            # Mukkadam = sum of farmer_amount from completed allocations
            completed_alloc_amt = sum(
                float(a.farmer_amount or 0) for a in allocs if a.work_status == 'completed'
            )

            # ── Fill bucket ──────────────────────────────────
            bucket = co if act_class == 'completed' else ip if act_class == 'in_progress' else pe

            bucket['activities'] += 1
            bucket['all_acres'] += area
            if pruning:
                bucket['pruning_acres'] += area
            bucket['worth'] += price
            bucket['mukkadam_amt'] += completed_alloc_amt

            # ── Track for job/farmer classification ──────────
            job_act_classes[ja.job_id].append(act_class)
            job_farmer[ja.job_id] = ja.job.farmer_id

        # ── CLASSIFY JOBS ────────────────────────────────────
        # Job completed = ALL its valid activities (area>0) are completed
        # Job in_progress = any activity is completed or in_progress but not ALL completed
        # Job pending = all activities are pending
        co_jobs = set()
        ip_jobs = set()
        pe_jobs = set()

        farmer_done = set()
        farmer_wip = set()
        farmer_seen = set()

        for job_id, classes in job_act_classes.items():
            farmer_id = job_farmer[job_id]
            farmer_seen.add(farmer_id)

            all_done = all(c == 'completed' for c in classes)
            any_started = any(c in ('completed', 'in_progress') for c in classes)
            all_pending = all(c == 'pending' for c in classes)

            if all_done:
                co_jobs.add(job_id)
                farmer_done.add(farmer_id)
            elif any_started:
                ip_jobs.add(job_id)
                farmer_wip.add(farmer_id)
            else:
                pe_jobs.add(job_id)

        # ── CLASSIFY FARMERS ─────────────────────────────────
        # Has both done & wip → completed (attended)
        # Only wip → in_progress
        # Only done (no wip) → completed
        # Neither → pending
        co_farmers = set()
        ip_farmers = set()
        pe_farmers = set()

        for fid in farmer_seen:
            if fid in farmer_done and fid in farmer_wip:
                co_farmers.add(fid)
            elif fid in farmer_wip:
                ip_farmers.add(fid)
            elif fid in farmer_done:
                co_farmers.add(fid)
            else:
                pe_farmers.add(fid)

        # ── BOOKING DATA ────────────────────────────────────
        booking_data = Job.objects.aggregate(
            booking_value=Coalesce(Sum('booking__total_amount'), Value(Decimal('0.0')), output_field=DecimalField()),
            collected=Coalesce(Sum('booking__advance_paid'), Value(Decimal('0.0')), output_field=DecimalField()),
            balance_due=Coalesce(Sum('booking__balance'), Value(Decimal('0.0')), output_field=DecimalField()),
        )

        # ── RESPONSE ─────────────────────────────────────────
        return JsonResponse({
    "overview": {
        "farmers": Farmer.objects.count(),
        "jobs": Job.objects.count(),
        "activities": len(seen_keys),
        "acres_first": round(ov_pruning_acres, 1),       # was acres_pruning
        "acres_all": round(ov_all_acres, 1),
        "booking_value": dec(booking_data["booking_value"]),
        "collected": dec(booking_data["collected"]),
        "balance_due": dec(booking_data["balance_due"]),
    },
    "completed": {
        "farmers": len(co_farmers),
        "jobs": len(co_jobs),
        "activities": co['activities'],
        "acres_first": round(co['pruning_acres'], 1),     # was acres_pruning
        "acres_all": round(co['all_acres'], 1),
        "worth_of_work": round(co['worth'], 2),
        "mukadam_paid": round(co['mukkadam_amt'], 2),      # was mukkadam_paid
        "transport": 0.0,                                   # was transport_spend
    },
    "in_progress": {
        "farmers": len(ip_farmers),
        "jobs": len(ip_jobs),
        "activities": ip['activities'],
        "acres_first": round(ip['pruning_acres'], 1),     # was acres_pruning
        "acres_all": round(ip['all_acres'], 1),
        "worth_of_work": round(ip['worth'], 2),
        "mukadam_payable": round(ip['mukkadam_amt'], 2),   # was mukkadam_payable
    },
    "pending": {
        "farmers": len(pe_farmers),
        "jobs": len(pe_jobs),
        "activities": pe['activities'],
        "acres_first": round(pe['pruning_acres'], 1),     # was acres_pruning
        "acres_all": round(pe['all_acres'], 1),
        "worth_pending": round(pe['worth'], 2),
        "mukadam_earnings_pending": round(pe['mukkadam_amt'], 2),
    }
})
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
                'availableDates': _resolve_available_dates(asgn) if asgn.mukkadam_type == 'updown' else None,
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