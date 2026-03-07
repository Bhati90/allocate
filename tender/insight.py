from datetime import date, datetime, timedelta
from collections import defaultdict

from django.db.models import Sum, Avg, Count, Q, F
from django.db.models.functions import TruncWeek
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date, datetime, timedelta
from collections import defaultdict

from django.db.models import Sum, Avg, Count, Q, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Allocation, Job, JobActivity, Cluster, Mukkadam
from .utils import get_effective_crew_size


def calculate_used_slots_for_day(day_allocs):
    used_slots_per_mukkadam = defaultdict(int)
    for a in day_allocs:
        increment = 1 if a.allows_second_job else 2
        used_slots_per_mukkadam[a.mukkadam_id] += increment

    total_used = 0
    for slots in used_slots_per_mukkadam.values():
        total_used += min(slots, 2)
    return total_used


def get_effective_crew_size_for_cluster(cluster, start_date, end_date):
    result = {}
    mukkadams = list(Mukkadam.objects.filter(clusters=cluster).distinct())

    allocs = Allocation.objects.filter(
        cluster=cluster,
        allocated_date__range=[start_date, end_date],
    ).select_related('mukkadam')

    allocs_by_day = defaultdict(list)
    for a in allocs:
        allocs_by_day[a.allocated_date].append(a)

    current = start_date
    while current <= end_date:
        capacity_workers = 0
        for m in mukkadams:
            capacity_workers += get_effective_crew_size(m, current)

        day_allocs = allocs_by_day.get(current, [])
        used_slots = calculate_used_slots_for_day(day_allocs)
        total_slots = len(mukkadams) * 2

        result[current] = {
            "capacity_workers": capacity_workers,
            "total_slots": total_slots,
            "used_slots": min(used_slots, total_slots),
        }
        current += timedelta(days=1)

    return result


class ClusterInsightsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, cluster_id):
        cluster = Cluster.objects.get(pk=cluster_id)

        # ── date range ──────────────────────────────────────────────────────
        start_date_str = request.query_params.get('start_date')
        end_date_str   = request.query_params.get('end_date')

        today = date.today()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
        end_date   = datetime.strptime(end_date_str,   "%Y-%m-%d").date() if end_date_str   else today

        # ── base querysets ──────────────────────────────────────────────────
        alloc_qs = Allocation.objects.filter(
            cluster=cluster,
            allocated_date__range=[start_date, end_date],
        )

        # ── summary aggregation ─────────────────────────────────────────────
        summary_agg = alloc_qs.aggregate(
            total_farmer_amount=Sum('farmer_amount'),
            total_mukkadam_amount=Sum('mukkadam_amount'),
            total_profit=Sum('profit'),
            total_area_allocated=Sum('allocated_area'),
            total_area_completed=Sum('actual_area_completed'),
            total_allocated_workers=Sum('allocated_workers'),
            avg_efficiency_score=Avg('efficiency_score'),
            dispute_count=Count('id', filter=Q(payment_status='dispute')),
            loss_allocations=Count('id', filter=Q(profit__lt=0)),
            completed_count=Count('id', filter=Q(work_status='completed')),
        )

        jobs_qs = Job.objects.filter(
            clusters=cluster,
            activities__scheduled_date__range=[start_date, end_date],
        ).distinct()

        total_jobs = jobs_qs.count()
        total_activities = JobActivity.objects.filter(
            job__clusters=cluster,
            scheduled_date__range=[start_date, end_date],
        ).count()

        # ── capacity ────────────────────────────────────────────────────────
        capacity_by_day = get_effective_crew_size_for_cluster(cluster, start_date, end_date)

        effective_capacity_workers = sum(v["capacity_workers"] for v in capacity_by_day.values())
        total_slots  = sum(v["total_slots"]  for v in capacity_by_day.values())
        used_slots   = sum(v["used_slots"]   for v in capacity_by_day.values())

        total_alloc_workers = summary_agg['total_allocated_workers'] or 0
        crew_util_percent   = (total_alloc_workers / effective_capacity_workers * 100) if effective_capacity_workers else 0
        slot_util_percent   = (used_slots / total_slots * 100) if total_slots else 0

        farmer_amount  = float(summary_agg['total_farmer_amount']  or 0)
        mukkadam_amount = float(summary_agg['total_mukkadam_amount'] or 0)
        profit          = farmer_amount - mukkadam_amount

        total_area_allocated = summary_agg['total_area_allocated'] or 0
        profit_per_acre = float(profit) / float(total_area_allocated) if total_area_allocated else 0

        dispute_count = summary_agg['dispute_count'] or 0
        base_for_dispute = alloc_qs.filter(status='completed').count() or 1
        dispute_rate_percent = dispute_count / base_for_dispute * 100

        # ── by_day ──────────────────────────────────────────────────────────
        by_day = []
        current = start_date
        while current <= end_date:
            day_allocs = alloc_qs.filter(allocated_date=current)
            day_agg = day_allocs.aggregate(
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                total_farmer_amount=Sum('farmer_amount'),
                total_mukkadam_amount=Sum('mukkadam_amount'),
                allocated_workers=Sum('allocated_workers'),
                disputes=Count('id', filter=Q(payment_status='dispute')),
            )
            cap_info = capacity_by_day.get(current, {"capacity_workers": 0, "total_slots": 0, "used_slots": 0})
            eff_cap         = cap_info["capacity_workers"]
            used_slots_day  = cap_info["used_slots"]
            total_slots_day = cap_info["total_slots"]

            day_profit = (day_agg['total_farmer_amount'] or 0) - (day_agg['total_mukkadam_amount'] or 0)

            jobs_scheduled = jobs_qs.filter(activities__scheduled_date=current).distinct().count()
            jobs_completed = jobs_qs.filter(status='completed', completed_date=current).distinct().count()

            by_day.append({
                "date":                     current.isoformat(),
                "total_area_allocated":     float(day_agg['total_area_allocated']    or 0),
                "total_area_completed":     float(day_agg['total_area_completed']    or 0),
                "allocated_workers":        day_agg['allocated_workers']             or 0,
                "effective_capacity_workers": eff_cap,
                "crew_utilization_percent": (day_agg['allocated_workers'] or 0) / eff_cap * 100 if eff_cap else 0,
                "slot_utilization_percent": used_slots_day / total_slots_day * 100 if total_slots_day else 0,
                "profit":                   float(day_profit),
                "jobs_scheduled":           jobs_scheduled,
                "jobs_completed":           jobs_completed,
                "disputes":                 day_agg['disputes'] or 0,
            })
            current += timedelta(days=1)

        # ── by_mukkadam ─────────────────────────────────────────────────────
        by_mukkadam = []
        mukkadams_qs = Mukkadam.objects.filter(clusters=cluster).distinct()

        for m in mukkadams_qs:
            m_allocs = alloc_qs.filter(mukkadam=m)
            m_agg = m_allocs.aggregate(
                allocations=Count('id'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                allocated_workers_total=Sum('allocated_workers'),
                avg_efficiency_score=Avg('efficiency_score'),
                farmer_amount=Sum('farmer_amount'),
                mukkadam_amount=Sum('mukkadam_amount'),
                disputes=Count('id', filter=Q(payment_status='dispute')),
            )
            cap_sum = 0
            cur = start_date
            while cur <= end_date:
                cap_sum += get_effective_crew_size(m, cur)
                cur += timedelta(days=1)

            alloc_workers = m_agg['allocated_workers_total'] or 0
            crew_util     = alloc_workers / cap_sum * 100 if cap_sum else 0
            m_profit      = (m_agg['farmer_amount'] or 0) - (m_agg['mukkadam_amount'] or 0)

            by_mukkadam.append({
                "mukkadam_id":               m.mukkadam_id,
                "name":                      m.mukkadam_name,
                "crew_size":                 m.crew_size,
                "max_crew_capacity":         m.max_crew_capacity,
                "allocations":               m_agg['allocations']           or 0,
                "allocated_workers_total":   alloc_workers,
                "effective_capacity_workers": cap_sum,
                "crew_utilization_percent":  crew_util,
                "total_area_allocated":      float(m_agg['total_area_allocated']  or 0),
                "total_area_completed":      float(m_agg['total_area_completed']  or 0),
                "avg_efficiency_score":      float(m_agg['avg_efficiency_score']  or 0),
                "profit":                    float(m_profit),
                "disputes":                  m_agg['disputes'] or 0,
            })

        # ── by_activity ─────────────────────────────────────────────────────
        activity_qs = JobActivity.objects.filter(
            job__clusters=cluster,
            allocations__allocated_date__range=[start_date, end_date],
        ).distinct()

        by_activity = []
        for act in activity_qs:
            a_allocs = alloc_qs.filter(job_activity=act)
            a_agg = a_allocs.aggregate(
                allocations=Count('id'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                total_farmer_amount=Sum('farmer_amount'),
                total_mukkadam_amount=Sum('mukkadam_amount'),
                loss_allocations=Count('id', filter=Q(farmer_amount__lt=F('mukkadam_amount'))),
            )
            ta = a_agg['total_area_allocated'] or 0
            fa = a_agg['total_farmer_amount']  or 0
            ma = a_agg['total_mukkadam_amount'] or 0
            profit_a = fa - ma

            by_activity.append({
                "activity_id":        act.id,
                "activity_name":      act.activity.name,
                "allocations":        a_agg['allocations']        or 0,
                "total_area_allocated": float(ta),
                "total_area_completed": float(a_agg['total_area_completed'] or 0),
                "avg_farmer_rate":    float(fa) / float(ta) if ta else 0,
                "avg_mukkadam_rate":  float(ma) / float(ta) if ta else 0,
                "avg_profit_per_acre": float(profit_a) / float(ta) if ta else 0,
                "profit":             float(profit_a),
                "loss_allocations":   a_agg['loss_allocations'] or 0,
            })

        # ── mukkadam_work  ───────────────────────────────────────────────────
        # KEY FIX: select_related includes job_activity so we can read
        # job_activity.is_manually_moved to determine AI vs H
        mukkadam_work_map = defaultdict(list)

        alloc_detailed = alloc_qs.select_related(
            'mukkadam',
            'job_activity__job__farmer',
            'job_activity__activity',
            'job_activity__plot',
        )

        for a in alloc_detailed:
            ja      = a.job_activity
            job     = ja.job
            farmer  = job.farmer
            plot    = ja.plot

            # ── AI vs H logic ──────────────────────────────────────────────
            # If the JobActivity was manually moved → "H" (Human decision)
            # If it was NOT moved (original AI-scheduled) → "AI"
            allocation_source = "H" if ja.is_manually_moved else "AI"

            mukkadam_work_map[a.mukkadam.mukkadam_id].append({
                "allocation_id":        a.id,
                "date":                 a.allocated_date.isoformat(),
                "job_id":               job.job_id,
                "farmer_id":            farmer.farmer_id,
                "farmer_name":          farmer.farmer_name,
                "plot_name":            plot.name if plot else None,
                "activity_id":          ja.activity.id,
                "activity_name":        ja.activity.name,
                # Area fields
                "allocated_area":       float(a.allocated_area),
                "actual_area_completed": float(a.actual_area_completed or 0),
                # Workers
                "allocated_workers":    a.allocated_workers,
                # Financial
                "farmer_amount":        float(a.farmer_amount or 0),
                "mukkadam_amount":      float(a.mukkadam_amount or 0),
                "profit":               float((a.farmer_amount or 0) - (a.mukkadam_amount or 0)),
                # Status
                "work_status":          a.work_status,
                "payment_status":       a.payment_status,
                # Flags
                "allows_second_job":    a.allows_second_job,
                "is_carry_forward":     a.is_carry_forward,
                "is_auto_allocated":    a.is_auto_allocated,
                # ✅ THE CORRECT AI/H FIELD
                # True if this JobActivity was manually moved → Human decision
                "is_manually_moved":    ja.is_manually_moved,
                # Derived label for direct use in frontend / export
                "allocation_source":    allocation_source,  # "AI" or "H"
            })

        mukkadam_work_list = [
            {
                "mukkadam_id":  m.mukkadam_id,
                "name":         m.mukkadam_name,
                "allocations":  mukkadam_work_map.get(m.mukkadam_id, []),
            }
            for m in mukkadams_qs
        ]

        # ── farmer_work ─────────────────────────────────────────────────────
        farmer_work_map = defaultdict(lambda: {
            "farmer_id":   None,
            "farmer_name": None,
            "activities":  [],
        })

        farmer_activities = JobActivity.objects.filter(
            job__clusters=cluster,
            scheduled_date__range=[start_date, end_date],
        ).select_related(
            'job__farmer',
            'activity',
            'plot',
        ).prefetch_related('allocations__mukkadam')

        for ja in farmer_activities:
            job    = ja.job
            farmer = job.farmer
            plot   = ja.plot

            f_entry = farmer_work_map[farmer.farmer_id]
            f_entry["farmer_id"]   = farmer.farmer_id
            f_entry["farmer_name"] = farmer.farmer_name

            ja_allocs = [
                {
                    "allocation_id":   a.id,
                    "date":            a.allocated_date.isoformat(),
                    "mukkadam_id":     a.mukkadam.mukkadam_id,
                    "mukkadam_name":   a.mukkadam.mukkadam_name,
                    "allocated_area":  float(a.allocated_area),
                    "allocated_workers": a.allocated_workers,
                    "work_status":     a.work_status,
                    "payment_status":  a.payment_status,
                    "profit":          float((a.farmer_amount or 0) - (a.mukkadam_amount or 0)),
                }
                for a in ja.allocations.all()
                if start_date <= a.allocated_date <= end_date
                and a.cluster_id == cluster.id
            ]

            f_entry["activities"].append({
                "job_id":           job.job_id,
                "plot_name":        plot.name if plot else None,
                "activity_id":      ja.activity.id,
                "activity_name":    ja.activity.name,
                "scheduled_date":   ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                "total_area":       float(ja.total_area),
                "allocated_area":   float(ja.allocated_area),
                "remaining_area":   float(ja.remaining_area),
                "allocation_status": ja.allocation_status,
                # ✅ expose move info for farmer tab too
                "is_manually_moved": ja.is_manually_moved,
                "allocation_source": "H" if ja.is_manually_moved else "AI",
                "allocations":      ja_allocs,
            })

        farmer_work = list(farmer_work_map.values())

        # ── capacity_demand ─────────────────────────────────────────────────
        capacity_demand = []
        current = start_date
        while current <= end_date:
            cap_info = capacity_by_day.get(current, {"capacity_workers": 0, "total_slots": 0, "used_slots": 0})
            capacity_workers = cap_info["capacity_workers"]

            demand_workers = alloc_qs.filter(allocated_date=current).aggregate(
                total_workers=Sum('allocated_workers')
            )['total_workers'] or 0

            shortage_workers = max(demand_workers - capacity_workers, 0)

            capacity_demand.append({
                "date":             current.isoformat(),
                "capacity_workers": capacity_workers,
                "demand_workers":   demand_workers,
                "shortage_workers": shortage_workers,
                "is_overbooked":    shortage_workers > 0,
            })
            current += timedelta(days=1)

        # ── move_suggestions ────────────────────────────────────────────────
        cap_dem_by_date = {d["date"]: d for d in capacity_demand}
        move_suggestions = []
        FREE_THRESHOLD    = 5
        SEARCH_WINDOW_DAYS = 5

        for cd in capacity_demand:
            if not cd["is_overbooked"]:
                continue

            day      = datetime.strptime(cd["date"], "%Y-%m-%d").date()
            shortage = cd["shortage_workers"]

            candidate_days = []
            for delta in range(1, SEARCH_WINDOW_DAYS + 1):
                for sign in (-1, 1):
                    target = day + timedelta(days=sign * delta)
                    if target < start_date or target > end_date:
                        continue
                    key  = target.isoformat()
                    info = cap_dem_by_date.get(key)
                    if not info:
                        continue
                    free = info["capacity_workers"] - info["demand_workers"]
                    if free >= FREE_THRESHOLD:
                        candidate_days.append((target, free))

            flex_activities = JobActivity.objects.filter(
                job__clusters=cluster,
                scheduled_date=day,
                remaining_area__gt=0,
                is_strict=False,
            ).select_related('job__farmer', 'activity')

            activities_list = [
                {
                    "job_id":          ja.job.job_id,
                    "farmer_id":       ja.job.farmer.farmer_id,
                    "farmer_name":     ja.job.farmer.farmer_name,
                    "activity_id":     ja.activity.id,
                    "activity_name":   ja.activity.name,
                    "scheduled_date":  ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                    "remaining_area":  float(ja.remaining_area),
                    "is_manually_moved": ja.is_manually_moved,
                }
                for ja in flex_activities
            ]

            if candidate_days:
                candidate_days.sort(key=lambda x: (-x[1], abs((x[0] - day).days)))
                best_day, best_free = candidate_days[0]
                target_date            = best_day.isoformat()
                free_workers_on_target = best_free
                can_fully_move         = best_free >= shortage
            else:
                target_date            = None
                free_workers_on_target = 0
                can_fully_move         = False

            move_suggestions.append({
                "overbooked_date":        day.isoformat(),
                "shortage_workers":       shortage,
                "target_date":            target_date,
                "free_workers_on_target": free_workers_on_target,
                "can_fully_move":         can_fully_move,
                "flexible_activities":    activities_list,
            })

        # ── response ────────────────────────────────────────────────────────
        data = {
            "cluster":    {"id": cluster.id, "name": cluster.name},
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "total_jobs":                total_jobs,
                "total_activities":          total_activities,
                "total_area_allocated":      float(total_area_allocated),
                "total_area_completed":      float(summary_agg['total_area_completed'] or 0),
                "total_allocated_workers":   total_alloc_workers,
                "effective_capacity_workers": effective_capacity_workers,
                "crew_utilization_percent":  crew_util_percent,
                "slot_utilization_percent":  slot_util_percent,
                "farmer_amount":             float(farmer_amount),
                "mukkadam_amount":           float(mukkadam_amount),
                "profit":                    float(profit),
                "profit_per_acre":           profit_per_acre,
                "loss_allocations":          summary_agg['loss_allocations'] or 0,
                "dispute_count":             dispute_count,
                "dispute_rate_percent":      dispute_rate_percent,
                "avg_efficiency_score":      float(summary_agg['avg_efficiency_score'] or 0),
            },
            "by_day":          by_day,
            "by_mukkadam":     by_mukkadam,
            "by_activity":     by_activity,
            "mukkadam_work":   mukkadam_work_list,
            "farmer_work":     farmer_work,
            "capacity_demand": capacity_demand,
            "move_suggestions": move_suggestions,
        }
        return Response(data)
# tender/insight.py (or similar)

from collections import defaultdict
from datetime import date, datetime

from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncWeek
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Allocation, Job, JobActivity, Cluster, Mukkadam, Farmer


class GlobalInsightsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # ---- 1. Date range ----
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        today = date.today()
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            # default: current month
            start_date = today.replace(day=1)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today

        clusters = list(Cluster.objects.all())

        # ---- 2. Base querysets ----
        alloc_qs = (
            Allocation.objects.filter(
                allocated_date__range=[start_date, end_date]
            )
            .select_related(
                'cluster',
                'mukkadam',
                'job_activity__job__farmer',
                'job_activity__activity',
                'job_activity__plot',
            )
        )

        jobs_qs = (
            Job.objects.filter(
                clusters__isnull=False,
                activities__scheduled_date__range=[start_date, end_date],
            )
            .distinct()
        )

        # ---- 3. Overall summary ----
        summary_agg = alloc_qs.aggregate(
            total_farmer_amount=Sum('farmer_amount'),
            total_mukkadam_amount=Sum('mukkadam_amount'),
            total_area_allocated=Sum('allocated_area'),
            total_area_completed=Sum('actual_area_completed'),
            total_allocated_workers=Sum('allocated_workers'),
            loss_allocations=Count('id', filter=Q(profit__lt=0)),
            dispute_count=Count('id', filter=Q(payment_status='dispute')),
            avg_efficiency_score=Avg('efficiency_score'),
        )

        total_jobs = jobs_qs.count()
        total_activities = JobActivity.objects.filter(
            job__in=jobs_qs,
            scheduled_date__range=[start_date, end_date],
        ).count()

        farmer_amount = float(summary_agg['total_farmer_amount'] or 0)
        mukkadam_amount = float(summary_agg['total_mukkadam_amount'] or 0)
        total_area_allocated = float(summary_agg['total_area_allocated'] or 0)
        profit = farmer_amount - mukkadam_amount
        profit_per_acre = profit / total_area_allocated if total_area_allocated else 0

        overall_summary = {
            "total_jobs": total_jobs,
            "total_activities": total_activities,
            "total_area_allocated": total_area_allocated,
            "total_area_completed": float(summary_agg['total_area_completed'] or 0),
            "total_allocated_workers": summary_agg['total_allocated_workers'] or 0,
            "farmer_amount": farmer_amount,
            "mukkadam_amount": mukkadam_amount,
            "profit": profit,
            "profit_per_acre": profit_per_acre,
            "loss_allocations": summary_agg['loss_allocations'] or 0,
            "dispute_count": summary_agg['dispute_count'] or 0,
            "avg_efficiency_score": float(summary_agg['avg_efficiency_score'] or 0),
        }

        # ---- 4. Cluster summary (KPI per cluster) ----
        cluster_rows = []
        for c in clusters:
            c_allocs = alloc_qs.filter(cluster=c)
            if not c_allocs.exists():
                continue

            c_agg = c_allocs.aggregate(
                total_farmer_amount=Sum('farmer_amount'),
                total_mukkadam_amount=Sum('mukkadam_amount'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                total_allocated_workers=Sum('allocated_workers'),
                loss_allocations=Count('id', filter=Q(profit__lt=0)),
                dispute_count=Count('id', filter=Q(payment_status='dispute')),
            )

            fa = float(c_agg['total_farmer_amount'] or 0)
            ma = float(c_agg['total_mukkadam_amount'] or 0)
            ta = float(c_agg['total_area_allocated'] or 0)
            pr = fa - ma

            jobs_in_cluster = jobs_qs.filter(clusters=c).distinct().count()

            cluster_rows.append({
                "cluster_id": c.id,
                "cluster_name": c.name,
                "jobs": jobs_in_cluster,
                "total_area_allocated": ta,
                "total_area_completed": float(c_agg['total_area_completed'] or 0),
                "farmer_amount": fa,
                "mukkadam_amount": ma,
                "profit": pr,
                "profit_per_acre": pr / ta if ta else 0,
                "allocated_workers": c_agg['total_allocated_workers'] or 0,
                "loss_allocations": c_agg['loss_allocations'] or 0,
                "dispute_count": c_agg['dispute_count'] or 0,
            })

        # ---- 5. Cluster jobs + allocation status detail ----
        cluster_jobs = defaultdict(list)

        job_acts = (
            JobActivity.objects.filter(job__in=jobs_qs)
            .select_related('job__farmer', 'activity', 'plot')
            .prefetch_related('allocations', 'job__clusters')
        )

        for ja in job_acts:
            job = ja.job
            farmer = job.farmer
            plot = ja.plot
            # allocations summary
            alloc_list = list(ja.allocations.all())
            alloc_count = len(alloc_list)
            alloc_area_sum = sum(float(a.allocated_area or 0) for a in alloc_list)
            alloc_workers_sum = sum(a.allocated_workers or 0 for a in alloc_list)

            for c in job.clusters.all():
                cluster_jobs[c.id].append({
                    "job_id": job.job_id,
                    "cluster_id": c.id,
                    "cluster_name": c.name,
                    "farmer_id": farmer.farmer_id,
                    "farmer_name": farmer.farmer_name,
                    "plot_name": plot.name if plot else None,
                    "activity_id": ja.activity.id,
                    "activity_name": ja.activity.name,
                    "scheduled_date": ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                    "total_area": float(ja.total_area),
                    "allocated_area": float(ja.allocated_area),
                    "remaining_area": float(ja.remaining_area),
                    "estimated_workers": ja.estimated_workers or 0,
                    "allocation_status": ja.allocation_status,
                    "allocations_count": alloc_count,
                    "allocated_workers": alloc_workers_sum,
                    "allocated_area_sum": alloc_area_sum,
                })

        cluster_job_list = []
        for c in clusters:
            if c.id not in cluster_jobs:
                continue
            cluster_job_list.append({
                "cluster_id": c.id,
                "cluster_name": c.name,
                "jobs": cluster_jobs[c.id],
            })

        # ---- 6. Mukkadam summary (global + per cluster) ----
        mukkadam_cluster_map = defaultdict(
            lambda: defaultdict(lambda: {
                "allocations": 0,
                "area_alloc": 0.0,
                "area_done": 0.0,
                "farmer_amount": 0.0,
                "mukkadam_amount": 0.0,
            })
        )

        for a in alloc_qs:
            m = a.mukkadam
            c = a.cluster
            if not m or not c:
                continue
            key = (m.mukkadam_id, m.mukkadam_name)
            bucket = mukkadam_cluster_map[key][c.id]
            bucket["allocations"] += 1
            bucket["area_alloc"] += float(a.allocated_area or 0)
            bucket["area_done"] += float(a.actual_area_completed or 0)
            bucket["farmer_amount"] += float(a.farmer_amount or 0)
            bucket["mukkadam_amount"] += float(a.mukkadam_amount or 0)

        mukkadam_summary = []
        cluster_name_cache = {c.id: c.name for c in clusters}

        for (m_id, m_name), clusters_map in mukkadam_cluster_map.items():
            total_area_alloc = sum(v["area_alloc"] for v in clusters_map.values())
            total_farmer_amount = sum(v["farmer_amount"] for v in clusters_map.values())
            total_mukkadam_amount = sum(v["mukkadam_amount"] for v in clusters_map.values())
            pr = total_farmer_amount - total_mukkadam_amount
            profit_per_acre_m = pr / total_area_alloc if total_area_alloc else 0

            mukkadam_summary.append({
                "mukkadam_id": m_id,
                "mukkadam_name": m_name,
                "total_area_allocated": total_area_alloc,
                "total_farmer_amount": total_farmer_amount,
                "total_mukkadam_amount": total_mukkadam_amount,
                "profit": pr,
                "profit_per_acre": profit_per_acre_m,
                "clusters": [
                    {
                        "cluster_id": cid,
                        "cluster_name": cluster_name_cache.get(cid, ""),
                        "allocations": v["allocations"],
                        "area_alloc": v["area_alloc"],
                        "area_done": v["area_done"],
                        "farmer_amount": v["farmer_amount"],
                        "mukkadam_amount": v["mukkadam_amount"],
                        "profit": v["farmer_amount"] - v["mukkadam_amount"],
                    }
                    for cid, v in clusters_map.items()
                ],
            })

        # ---- 7. Farmer summary (global + per cluster) ----
        farmer_cluster_map = defaultdict(
            lambda: defaultdict(lambda: {
                "allocations": 0,
                "area_alloc": 0.0,
                "area_done": 0.0,
                "farmer_amount": 0.0,
                "mukkadam_amount": 0.0,
            })
        )

        for a in alloc_qs:
            f = a.job_activity.job.farmer
            c = a.cluster
            key = (f.farmer_id, f.farmer_name)
            bucket = farmer_cluster_map[key][c.id]
            bucket["allocations"] += 1
            bucket["area_alloc"] += float(a.allocated_area or 0)
            bucket["area_done"] += float(a.actual_area_completed or 0)
            bucket["farmer_amount"] += float(a.farmer_amount or 0)
            bucket["mukkadam_amount"] += float(a.mukkadam_amount or 0)

        farmer_summary = []
        for (f_id, f_name), clusters_map in farmer_cluster_map.items():
            total_area_alloc = sum(v["area_alloc"] for v in clusters_map.values())
            total_farmer_amount = sum(v["farmer_amount"] for v in clusters_map.values())
            total_mukkadam_amount = sum(v["mukkadam_amount"] for v in clusters_map.values())
            pr = total_farmer_amount - total_mukkadam_amount
            profit_per_acre_f = pr / total_area_alloc if total_area_alloc else 0

            farmer_summary.append({
                "farmer_id": f_id,
                "farmer_name": f_name,
                "total_area_allocated": total_area_alloc,
                "total_farmer_amount": total_farmer_amount,
                "total_mukkadam_amount": total_mukkadam_amount,
                "profit": pr,
                "profit_per_acre": profit_per_acre_f,
                "clusters": [
                    {
                        "cluster_id": cid,
                        "cluster_name": cluster_name_cache.get(cid, ""),
                        "allocations": v["allocations"],
                        "area_alloc": v["area_alloc"],
                        "area_done": v["area_done"],
                        "farmer_amount": v["farmer_amount"],
                        "mukkadam_amount": v["mukkadam_amount"],
                        "profit": v["farmer_amount"] - v["mukkadam_amount"],
                    }
                    for cid, v in clusters_map.items()
                ],
            })

        # ---- 8. Week summary ----
        week_rows = []
        alloc_by_week = (
            alloc_qs
            .annotate(week=TruncWeek('allocated_date'))
            .values('week')
            .annotate(
                total_farmer_amount=Sum('farmer_amount'),
                total_mukkadam_amount=Sum('mukkadam_amount'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                alloc_count=Count('id'),
            )
            .order_by('week')
        )

        for w in alloc_by_week:
            fa = float(w['total_farmer_amount'] or 0)
            ma = float(w['total_mukkadam_amount'] or 0)
            ta = float(w['total_area_allocated'] or 0)
            pr = fa - ma
            week_rows.append({
                "week_start": w['week'].isoformat(),
                "allocations": w['alloc_count'] or 0,
                "total_area_allocated": ta,
                "total_area_completed": float(w['total_area_completed'] or 0),
                "farmer_amount": fa,
                "mukkadam_amount": ma,
                "profit": pr,
                "profit_per_acre": pr / ta if ta else 0,
            })

        # ---- 9. Response ----
        data = {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "overall_summary": overall_summary,
            "cluster_summary": cluster_rows,
            "cluster_jobs": cluster_job_list,
            "mukkadam_summary": mukkadam_summary,
            "farmer_summary": farmer_summary,
            "week_summary": week_rows,
        }
        return Response(data)


# tender/insight.py

from collections import defaultdict
from datetime import datetime, date

from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Allocation, Job, JobActivity, Cluster, Mukkadam, Farmer


class GlobalDayInsightsView(APIView):
    """
    /tender/api/tender-global-day-insights/?date=2026-03-09&farmer_id=F123&mukkadam_id=129&activity_id=14

    Returns:
    - overall summary for that day (all clusters)
    - per-cluster summary for that day
    - per-job rows (booking-level) with farmer + mukkadam + prices
    """

    permission_classes = [AllowAny]

    def get(self, request):
        # ---- 1. parse date ----
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "date query param is required (YYYY-MM-DD)"}, status=400)

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "invalid date format, expected YYYY-MM-DD"}, status=400)

        # optional filters
        farmer_id = request.query_params.get('farmer_id')
        mukkadam_id = request.query_params.get('mukkadam_id')
        activity_id = request.query_params.get('activity_id')
        cluster_id = request.query_params.get('cluster_id')  # optional: limit to one cluster

        # ---- 2. base allocations for that day ----
        alloc_qs = Allocation.objects.filter(
            allocated_date=target_date
        ).select_related(
            'cluster',
            'mukkadam',
            'job_activity__job__farmer',
            'job_activity__activity',
            'job_activity__plot',
        )

        if cluster_id:
            alloc_qs = alloc_qs.filter(cluster_id=cluster_id)
        if mukkadam_id:
            alloc_qs = alloc_qs.filter(mukkadam__mukkadam_id=mukkadam_id)

        # ---- 3. base job activities for that day (bookings) ----
        ja_qs = JobActivity.objects.filter(
            scheduled_date=target_date,
            job__clusters__isnull=False,
        ).select_related(
            'job__farmer',
            'activity',
            'plot',
        ).prefetch_related('job__clusters', 'allocations')

        if cluster_id:
            ja_qs = ja_qs.filter(job__clusters__id=cluster_id)
        if farmer_id:
            ja_qs = ja_qs.filter(job__farmer__farmer_id=farmer_id)
        if activity_id:
            ja_qs = ja_qs.filter(activity_id=activity_id)

        ja_qs = ja_qs.distinct()

        # ---- 4. overall summary for the day ----
        overall_alloc_agg = alloc_qs.aggregate(
            total_farmer_amount=Sum('farmer_amount'),
            total_mukkadam_amount=Sum('mukkadam_amount'),
            total_area_allocated=Sum('allocated_area'),
            total_area_completed=Sum('actual_area_completed'),
            total_allocated_workers=Sum('allocated_workers'),
        )

        overall_activity_agg = ja_qs.aggregate(
            total_activities=Count('id', distinct=True),
            total_area_scheduled=Sum('total_area'),
            total_area_remaining=Sum('remaining_area'),
        )

        overall_farmer_amount = float(overall_alloc_agg['total_farmer_amount'] or 0)
        overall_mukkadam_amount = float(overall_alloc_agg['total_mukkadam_amount'] or 0)
        overall_profit = overall_farmer_amount - overall_mukkadam_amount

        # crude capacity: sum of mukkadams' crew_size in affected clusters
        clusters = Cluster.objects.filter(jobs__activities__in=ja_qs).distinct()
        total_available_capacity = 0
        for c in clusters:
            # you can plug your real daily capacity helper here
            muks = Mukkadam.objects.filter(cluster_assignments__cluster=c,
                                           cluster_assignments__is_active=True).distinct()
            for m in muks:
                total_available_capacity += m.crew_size or 0

        overall = {
            "date": target_date.isoformat(),
            "total_clusters": clusters.count(),
            "total_activities": overall_activity_agg["total_activities"] or 0,
            "total_area_scheduled": float(overall_activity_agg["total_area_scheduled"] or 0),
            "total_area_allocated": float(overall_alloc_agg["total_area_allocated"] or 0),
            "total_area_remaining": float(overall_activity_agg["total_area_remaining"] or 0),
            "total_allocated_workers": overall_alloc_agg["total_allocated_workers"] or 0,
            "total_available_capacity_workers": total_available_capacity,
            "farmer_amount": overall_farmer_amount,
            "mukkadam_amount": overall_mukkadam_amount,
            "profit": overall_profit,
        }

        # ---- 5. per-cluster summary for that day ----
        cluster_summary_map = defaultdict(lambda: {
            "cluster_id": None,
            "cluster_name": None,
            "activities": 0,
            "area_scheduled": 0.0,
            "area_allocated": 0.0,
            "area_remaining": 0.0,
            "allocated_workers": 0,
            "available_capacity_workers": 0,
            "farmer_amount": 0.0,
            "mukkadam_amount": 0.0,
            "profit": 0.0,
        })

        # from bookings
        for ja in ja_qs:
            job = ja.job
            for c in job.clusters.all():
                if cluster_id and c.id != int(cluster_id):
                    continue
                row = cluster_summary_map[c.id]
                row["cluster_id"] = c.id
                row["cluster_name"] = c.name
                row["activities"] += 1
                row["area_scheduled"] += float(ja.total_area or 0)
                row["area_remaining"] += float(ja.remaining_area or 0)

        # from allocations
        for a in alloc_qs:
            c = a.cluster
            if not c:
                continue
            row = cluster_summary_map[c.id]
            row["cluster_id"] = c.id
            row["cluster_name"] = c.name
            row["area_allocated"] += float(a.allocated_area or 0)
            row["allocated_workers"] += a.allocated_workers or 0
            row["farmer_amount"] += float(a.farmer_amount or 0)
            row["mukkadam_amount"] += float(a.mukkadam_amount or 0)

        # capacity per cluster (again, plug real helper if you have)
        for cid, row in cluster_summary_map.items():
            muks = Mukkadam.objects.filter(
                cluster_assignments__cluster_id=cid,
                cluster_assignments__is_active=True
            ).distinct()
            cap = 0
            for m in muks:
                cap += m.crew_size or 0
            row["available_capacity_workers"] = cap
            row["profit"] = row["farmer_amount"] - row["mukkadam_amount"]

        cluster_summary = list(cluster_summary_map.values())

        # ---- 6. per-job detail rows (booking level) ----
        day_jobs = []
        for ja in ja_qs:
            job = ja.job
            farmer = job.farmer
            plot = ja.plot
            activity = ja.activity

            # allocations for this activity on that day (any cluster)
            ja_allocs = [a for a in ja.allocations.all() if a.allocated_date == target_date]

            for c in job.clusters.all():
                if cluster_id and c.id != int(cluster_id):
                    continue

                # split allocs per cluster+mukkadam
                for a in ja_allocs:
                    if a.cluster_id != c.id:
                        continue
                    m = a.mukkadam
                    day_jobs.append({
                        "cluster_id": c.id,
                        "cluster_name": c.name,
                        "booking_id": job.job_id,  # your booking reference
                        "job_id": job.job_id,
                        "farmer_id": farmer.farmer_id,
                        "farmer_name": farmer.farmer_name,
                        "farmer_price": float(a.farmer_amount or 0),
                        "mukkadam_id": m.mukkadam_id if m else None,
                        "mukkadam_name": m.mukkadam_name if m else None,
                        "mukkadam_price": float(a.mukkadam_amount or 0),
                        "profit": float((a.farmer_amount or 0) - (a.mukkadam_amount or 0)),
                        "plot_name": plot.name if plot else None,
                        "activity_id": activity.id,
                        "activity_name": activity.name,
                        "scheduled_date": ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                        "total_area": float(ja.total_area or 0),
                        "allocated_area": float(a.allocated_area or 0),
                        "remaining_area": float(ja.remaining_area or 0),
                        "estimated_workers": ja.estimated_workers or 0,
                        "allocated_workers": a.allocated_workers or 0,
                        "allocation_status": ja.allocation_status,
                    })

                # if no allocation in this cluster, still add one row for visibility
                if not any(a.cluster_id == c.id for a in ja_allocs):
                    day_jobs.append({
                        "cluster_id": c.id,
                        "cluster_name": c.name,
                        "booking_id": job.job_id,
                        "job_id": job.job_id,
                        "farmer_id": farmer.farmer_id,
                        "farmer_name": farmer.farmer_name,
                        "farmer_price": 0.0,
                        "mukkadam_id": None,
                        "mukkadam_name": None,
                        "mukkadam_price": 0.0,
                        "profit": 0.0,
                        "plot_name": plot.name if plot else None,
                        "activity_id": activity.id,
                        "activity_name": activity.name,
                        "scheduled_date": ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                        "total_area": float(ja.total_area or 0),
                        "allocated_area": float(ja.allocated_area or 0),
                        "remaining_area": float(ja.remaining_area or 0),
                        "estimated_workers": ja.estimated_workers or 0,
                        "allocated_workers": 0,
                        "allocation_status": ja.allocation_status,
                    })

        # optional: filters applied on farmer/mukkadam/activity already via ja_qs/alloc_qs

        data = {
            "date": target_date.isoformat(),
            "filters": {
                "farmer_id": farmer_id,
                "mukkadam_id": mukkadam_id,
                "activity_id": activity_id,
                "cluster_id": cluster_id,
            },
            "overall": overall,
            "clusters": cluster_summary,
            "jobs": day_jobs,
        }
        return Response(data)



# from datetime import date, datetime, timedelta
# from collections import defaultdict
# from decimal import Decimal

# from django.db.models import Sum, Avg, Count, Q, F, ExpressionWrapper, DecimalField
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny

# from .models import (
#     Allocation, Job, JobActivity, Cluster, Mukkadam,
#     ClusterMukkadamAssignment, Leave, ExtraWorker,
# )
# from .utils import get_effective_crew_size_for_cluster, get_effective_crew_size


# class ClusterInsightsView(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request, cluster_id):
#         try:
#             cluster = Cluster.objects.get(pk=cluster_id)
#         except Cluster.DoesNotExist:
#             return Response({'error': 'Cluster not found'}, status=404)

#         # ── Date range ────────────────────────────────────────────────
#         today = date.today()
#         start_date_str = request.query_params.get('start_date')
#         end_date_str   = request.query_params.get('end_date')

#         start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
#         end_date   = datetime.strptime(end_date_str,   "%Y-%m-%d").date() if end_date_str   else today

#         if start_date > end_date:
#             return Response({'error': 'start_date must be <= end_date'}, status=400)

#         # ── Base allocation queryset for this cluster + date range ────
#         alloc_qs = Allocation.objects.filter(
#             cluster=cluster,
#             allocated_date__range=[start_date, end_date],
#         )

#         # ── Active mukkadams in this cluster ──────────────────────────
#         # FIX: use ClusterMukkadamAssignment (is_active=True) instead of
#         # Mukkadam.objects.filter(clusters=cluster) which may include inactive ones
#         active_assignments = ClusterMukkadamAssignment.objects.filter(
#             cluster=cluster,
#             is_active=True,
#         ).select_related('mukkadam', 'cluster')

#         active_mukkadams = [a.mukkadam for a in active_assignments]
#         assignment_by_mukkadam = {a.mukkadam_id: a for a in active_assignments}

#         # ── Capacity per day (single DB-efficient call) ───────────────
#         # FIX: pass only active mukkadams so capacity is not inflated by
#         # mukkadams that left the cluster
#         capacity_by_day = _get_capacity_for_cluster(
#             cluster, active_mukkadams, start_date, end_date
#         )

#         # ── Summary aggregates ────────────────────────────────────────
#         # FIX: annotate profit inline instead of relying on a stored 'profit' field
#         summary_agg = alloc_qs.aggregate(
#             total_farmer_amount      = Sum('farmer_amount'),
#             total_mukkadam_amount    = Sum('mukkadam_amount'),
#             total_profit             = Sum('profit'),
#             total_area_allocated     = Sum('allocated_area'),
#             total_area_completed     = Sum('actual_area_done'),
#             total_allocated_workers  = Sum('allocated_workers'),
#             avg_efficiency           = Avg('efficiency_score'),
#             dispute_count            = Count('id', filter=Q(payment_status='dispute')),
#             loss_allocations         = Count('id', filter=Q(profit__lt=0)),
#             completed_count          = Count('id', filter=Q(work_status='completed')),
#         )

#         total_alloc_workers = summary_agg['total_allocated_workers'] or 0


#         # ── Jobs / activities in this cluster in range ────────────────
#         # FIX: was filtering on activities__scheduled_date which may miss allocations
#         # done on different dates; filter on allocations instead
#         job_ids_in_range = alloc_qs.values_list(
#             'job_activity__job_id', flat=True
#         ).distinct()

#         total_jobs       = Job.objects.filter(job_id__in=job_ids_in_range).count()
#         total_activities = alloc_qs.values('job_activity_id').distinct().count()

#         # ── Capacity totals ───────────────────────────────────────────
#         effective_capacity_workers = sum(
#             v['capacity_workers'] for v in capacity_by_day.values()
#         )
#         total_slots = sum(v['total_slots'] for v in capacity_by_day.values())
#         used_slots  = sum(v['used_slots']  for v in capacity_by_day.values())

#         total_alloc_workers = summary_agg['total_allocated_workers'] or 0
#         # FIX: crew_util uses per-day-cumulative capacity, not a single day value
#         crew_util_pct  = (total_alloc_workers / effective_capacity_workers * 100) if effective_capacity_workers else 0
#         slot_util_pct  = (used_slots / total_slots * 100) if total_slots else 0

#         farmer_amount   = float(summary_agg['total_farmer_amount'] or 0)
#         mukkadam_amount = float(summary_agg['total_mukkadam_amount'] or 0)

#         profit              = farmer_amount - mukkadam_amount
#         total_area_alloc    = float(summary_agg['total_area_allocated'] or 0)
#         profit_per_acre     = profit / total_area_alloc if total_area_alloc else 0

#         dispute_count       = summary_agg['dispute_count']   or 0
#         completed_count     = summary_agg['completed_count'] or 1  # avoid div/0
#         dispute_rate_pct    = dispute_count / completed_count * 100

#         # ── BY DAY ────────────────────────────────────────────────────
#         # FIX: batch all per-day DB queries instead of N queries in a loop
#         # Pre-aggregate allocs by date
#         day_agg_map = {}
#         for row in alloc_qs.values('allocated_date').annotate(
#             total_area_allocated=Sum('allocated_area'),
#             total_area_completed=Sum('actual_area_done'),
#             allocated_workers=Sum('allocated_workers'),
#             farmer_amt=Sum('farmer_amount'),
#             mukkadam_amt=Sum('mukkadam_amount'),
#             disputes=Count('id', filter=Q(payment_status='dispute')),
#         ):
#             day_agg_map[row['allocated_date']] = row

#         # Pre-count jobs scheduled per day via allocations
#         jobs_per_day = defaultdict(set)
#         for row in alloc_qs.values('allocated_date', 'job_activity__job_id'):
#             jobs_per_day[row['allocated_date']].add(row['job_activity__job_id'])

#         by_day = []
#         current = start_date
#         while current <= end_date:
#             cap   = capacity_by_day.get(current, {'capacity_workers': 0, 'total_slots': 0, 'used_slots': 0})
#             agg   = day_agg_map.get(current, {})
#             alloc_w    = agg.get('allocated_workers') or 0
#             eff_cap    = cap['capacity_workers']
#             used_s     = cap['used_slots']
#             total_s    = cap['total_slots']
#             day_profit = float((agg.get('farmer_amt') or 0)) - float((agg.get('mukkadam_amt') or 0))

#             by_day.append({
#                 'date':                      current.isoformat(),
#                 'total_area_allocated':      float(agg.get('total_area_allocated') or 0),
#                 'total_area_completed':      float(agg.get('total_area_completed') or 0),
#                 'allocated_workers':         alloc_w,
#                 'effective_capacity_workers': eff_cap,
#                 'free_workers':              max(eff_cap - alloc_w, 0),
#                 'crew_utilization_percent':  round(alloc_w / eff_cap * 100, 1) if eff_cap else 0,
#                 'slot_utilization_percent':  round(used_s  / total_s  * 100, 1) if total_s  else 0,
#                 'profit':                    round(day_profit, 2),
#                 'jobs_active':               len(jobs_per_day.get(current, set())),
#                 'disputes':                  agg.get('disputes') or 0,
#                 'is_overbooked':             alloc_w > eff_cap,
#             })
#             current += timedelta(days=1)

#         # ── BY MUKKADAM ───────────────────────────────────────────────
#         # FIX: compute capacity by summing get_effective_crew_size per day,
#         # respecting leaves/extras — but do it efficiently by pre-fetching leaves
#         # FIX: also handle updown mukkadams (only available on specific dates)
#         by_mukkadam = []
#         for m in active_mukkadams:
#             asgn     = assignment_by_mukkadam.get(m.mukkadam_id)
#             m_allocs = alloc_qs.filter(mukkadam=m)
#             m_agg    = m_allocs.aggregate(
#                 allocations=Count('id'),
#                 total_area_allocated=Sum('allocated_area'),
#                 total_area_completed=Sum('actual_area_done'),
#                 allocated_workers_total=Sum('allocated_workers'),
#                 farmer_amt=Sum('farmer_amount'),
#                 mukkadam_amt=Sum('mukkadam_amount'),
#                 disputes=Count('id', filter=Q(payment_status='dispute')),
#                 completed=Count('id', filter=Q(work_status='completed')),
#             )

#             # Capacity: sum effective crew over each day (respects leaves + updown)
#             cap_sum = 0
#             cur     = start_date
#             while cur <= end_date:
#                 cap_sum += _effective_crew_for_mukkadam_on_date(m, asgn, cur)
#                 cur += timedelta(days=1)

#             alloc_w  = m_agg['allocated_workers_total'] or 0
#             m_profit = float(m_agg['farmer_amt'] or 0) - float(m_agg['mukkadam_amt'] or 0)
#             m_area   = float(m_agg['total_area_allocated'] or 0)

#             by_mukkadam.append({
#                 'mukkadam_id':               m.mukkadam_id,
#                 'name':                      m.mukkadam_name,
#                 'mukkadam_type':             asgn.mukkadam_type if asgn else None,
#                 'crew_size':                 m.crew_size,
#                 'allocations':               m_agg['allocations'] or 0,
#                 'allocated_workers_total':   alloc_w,
#                 'effective_capacity_workers': cap_sum,
#                 'crew_utilization_percent':  round(alloc_w / cap_sum * 100, 1) if cap_sum else 0,
#                 'total_area_allocated':      m_area,
#                 'total_area_completed':      float(m_agg['total_area_completed'] or 0),
#                 'profit':                    round(m_profit, 2),
#                 'profit_per_acre':           round(m_profit / m_area, 2) if m_area else 0,
#                 'disputes':                  m_agg['disputes'] or 0,
#                 'completed':                 m_agg['completed'] or 0,
#             })

#         # Sort by allocated workers desc
#         by_mukkadam.sort(key=lambda x: x['allocated_workers_total'], reverse=True)

#         # ── BY ACTIVITY ───────────────────────────────────────────────
#         # FIX: aggregate at DB level, not per-activity Python loop with repeated queries
#         act_agg_rows = alloc_qs.values(
#             'job_activity__activity__id',
#             'job_activity__activity__name',
#         ).annotate(
#             allocations=Count('id'),
#             total_area_allocated=Sum('allocated_area'),
#             total_area_completed=Sum('actual_area_done'),
#             farmer_amt=Sum('farmer_amount'),
#             mukkadam_amt=Sum('mukkadam_amount'),
#             disputes=Count('id', filter=Q(payment_status='dispute')),
#             loss_allocations=Count(
#                 'id', filter=Q(farmer_amount__lt=F('mukkadam_amount'))
#             ),
#         ).order_by('-total_area_allocated')

#         by_activity = []
#         for row in act_agg_rows:
#             ta  = float(row['total_area_allocated'] or 0)
#             fa  = float(row['farmer_amt']  or 0)
#             ma  = float(row['mukkadam_amt'] or 0)
#             pa  = fa - ma
#             by_activity.append({
#                 'activity_id':          row['job_activity__activity__id'],
#                 'activity_name':        row['job_activity__activity__name'],
#                 'allocations':          row['allocations'],
#                 'total_area_allocated': ta,
#                 'total_area_completed': float(row['total_area_completed'] or 0),
#                 'completion_pct':       round(float(row['total_area_completed'] or 0) / ta * 100, 1) if ta else 0,
#                 'avg_farmer_rate':      round(fa / ta, 2) if ta else 0,
#                 'avg_mukkadam_rate':    round(ma / ta, 2) if ta else 0,
#                 'avg_profit_per_acre':  round(pa / ta, 2) if ta else 0,
#                 'profit':               round(pa, 2),
#                 'loss_allocations':     row['loss_allocations'],
#                 'disputes':             row['disputes'],
#             })

#         # ── MUKKADAM DETAILED WORK ────────────────────────────────────
#         alloc_detailed = alloc_qs.select_related(
#             'mukkadam',
#             'job_activity__job__farmer',
#             'job_activity__activity',
#             'job_activity__plot',
#         ).order_by('mukkadam_id', 'allocated_date')

#         mukkadam_work_map = defaultdict(list)
#         for a in alloc_detailed:
#             ja     = a.job_activity
#             job    = ja.job
#             farmer = job.farmer
#             plot   = ja.plot
#             mukkadam_work_map[a.mukkadam.mukkadam_id].append({
#                 'allocation_id':        a.id,
#                 'date':                 a.allocated_date.isoformat(),
#                 'job_id':               str(job.job_id),
#                 'farmer_id':            farmer.farmer_id,
#                 'farmer_name':          farmer.farmer_name,
#                 'plot_name':            plot.name if plot else None,
#                 'plot_code':            plot.plot_code if plot else None,
#                 'activity_id':          ja.activity.id,
#                 'activity_name':        ja.activity.name,
#                 'allocated_area':       float(a.allocated_area),
#                 'actual_area_done':     float(a.actual_area_done or 0),
#                 'allocated_workers':    a.allocated_workers,
#                 'work_status':          a.work_status,
#                 'payment_status':       a.payment_status,
#                 'farmer_amount':        float(a.farmer_amount or 0),
#                 'mukkadam_amount':      float(a.mukkadam_amount or 0),
#                 'profit':               float((a.farmer_amount or 0) - (a.mukkadam_amount or 0)),
#                 'allows_second_job':    a.allows_second_job,
#                 'is_carry_forward':     getattr(a, 'is_carry_forward', False),
#             })

#         mukkadam_work_list = []
#         for m in active_mukkadams:
#             works = mukkadam_work_map.get(m.mukkadam_id, [])
#             mukkadam_work_list.append({
#                 'mukkadam_id': m.mukkadam_id,
#                 'name':        m.mukkadam_name,
#                 'total_profit': round(sum(w['profit'] for w in works), 2),
#                 'allocations': works,
#             })

#         # ── FARMER WORK ───────────────────────────────────────────────
#         # FIX: batch with prefetch instead of per-farmer queries
#         farmer_activities = JobActivity.objects.filter(
#             allocations__cluster=cluster,
#             allocations__allocated_date__range=[start_date, end_date],
#         ).select_related(
#             'job__farmer', 'activity', 'plot',
#         ).prefetch_related(
#             'allocations__mukkadam',
#         ).distinct()

#         farmer_work_map = defaultdict(lambda: {
#             'farmer_id':   None,
#             'farmer_name': None,
#             'activities':  [],
#         })

#         for ja in farmer_activities:
#             farmer = ja.job.farmer
#             fe     = farmer_work_map[farmer.farmer_id]
#             fe['farmer_id']   = farmer.farmer_id
#             fe['farmer_name'] = farmer.farmer_name

#             ja_allocs = [
#                 {
#                     'allocation_id':   a.id,
#                     'date':            a.allocated_date.isoformat(),
#                     'mukkadam_id':     a.mukkadam.mukkadam_id,
#                     'mukkadam_name':   a.mukkadam.mukkadam_name,
#                     'allocated_area':  float(a.allocated_area),
#                     'allocated_workers': a.allocated_workers,
#                     'work_status':     a.work_status,
#                     'payment_status':  a.payment_status,
#                     'profit':          float((a.farmer_amount or 0) - (a.mukkadam_amount or 0)),
#                 }
#                 for a in ja.allocations.all()
#                 if start_date <= a.allocated_date <= end_date
#                 and a.cluster_id == cluster.id
#             ]

#             fe['activities'].append({
#                 'job_id':            str(ja.job.job_id),
#                 'plot_name':         ja.plot.name if ja.plot else None,
#                 'plot_code':         ja.plot.plot_code if ja.plot else None,
#                 'activity_id':       ja.activity.id,
#                 'activity_name':     ja.activity.name,
#                 'scheduled_date':    ja.scheduled_date.isoformat() if ja.scheduled_date else None,
#                 'total_area':        float(ja.total_area),
#                 'allocated_area':    float(ja.allocated_area),
#                 'remaining_area':    float(ja.remaining_area),
#                 'allocation_status': ja.allocation_status,
#                 'allocations':       ja_allocs,
#             })

#         farmer_work = sorted(farmer_work_map.values(), key=lambda x: x['farmer_name'] or '')

#         # ── CAPACITY vs DEMAND ────────────────────────────────────────
#         # FIX: use already-computed day_agg_map instead of re-querying per day
#         capacity_demand = []
#         current = start_date
#         while current <= end_date:
#             cap_info        = capacity_by_day.get(current, {'capacity_workers': 0, 'total_slots': 0, 'used_slots': 0})
#             capacity_workers = cap_info['capacity_workers']
#             demand_workers   = day_agg_map.get(current, {}).get('allocated_workers') or 0
#             shortage         = max(demand_workers - capacity_workers, 0)
#             free             = max(capacity_workers - demand_workers, 0)

#             capacity_demand.append({
#                 'date':              current.isoformat(),
#                 'capacity_workers':  capacity_workers,
#                 'demand_workers':    demand_workers,
#                 'free_workers':      free,
#                 'shortage_workers':  shortage,
#                 'is_overbooked':     shortage > 0,
#                 'total_slots':       cap_info['total_slots'],
#                 'used_slots':        cap_info['used_slots'],
#                 'slot_utilization_percent': round(
#                     cap_info['used_slots'] / cap_info['total_slots'] * 100, 1
#                 ) if cap_info['total_slots'] else 0,
#             })
#             current += timedelta(days=1)

#         # ── SMART MOVE SUGGESTIONS ────────────────────────────────────
#         cap_dem_by_date   = {d['date']: d for d in capacity_demand}
#         move_suggestions  = []
#         FREE_THRESHOLD    = 5
#         SEARCH_WINDOW     = 5

#         for cd in capacity_demand:
#             if not cd['is_overbooked']:
#                 continue
#             day = date.fromisoformat(cd['date'])

#             # Find best target day with enough free capacity
#             candidates = []
#             for delta in range(1, SEARCH_WINDOW + 1):
#                 for sign in (-1, 1):
#                     target = day + timedelta(days=sign * delta)
#                     if not (start_date <= target <= end_date):
#                         continue
#                     info = cap_dem_by_date.get(target.isoformat())
#                     if not info:
#                         continue
#                     free = info['free_workers']
#                     if free >= FREE_THRESHOLD:
#                         candidates.append((target, free))

#             if not candidates:
#                 continue

#             candidates.sort(key=lambda x: (-x[1], abs((x[0] - day).days)))
#             best_day, best_free = candidates[0]

#             # FIX: select_related to avoid N+1 on farmer
#             flex_activities = JobActivity.objects.filter(
#                 allocations__cluster=cluster,
#                 scheduled_date=day,
#                 is_strict=False,
#                 remaining_area__gt=0,
#             ).select_related('job__farmer', 'activity').distinct()

#             acts_list = [{
#                 'job_id':         str(ja.job.job_id),
#                 'farmer_id':      ja.job.farmer.farmer_id,
#                 'farmer_name':    ja.job.farmer.farmer_name,
#                 'activity_id':    ja.activity.id,
#                 'activity_name':  ja.activity.name,
#                 'scheduled_date': ja.scheduled_date.isoformat() if ja.scheduled_date else None,
#                 'remaining_area': float(ja.remaining_area),
#             } for ja in flex_activities]

#             if not acts_list:
#                 continue

#             move_suggestions.append({
#                 'overbooked_date':          day.isoformat(),
#                 'shortage_workers':         cd['shortage_workers'],
#                 'target_date':              best_day.isoformat(),
#                 'free_workers_on_target':   best_free,
#                 'flexible_activities':      acts_list,
#             })

#         # ── TOP INSIGHTS (new) ────────────────────────────────────────
#         insights = _build_insights(
#             by_day, by_mukkadam, by_activity,
#             capacity_demand, profit, total_area_alloc,
#             dispute_rate_pct, crew_util_pct,
#         )

#         return Response({
#             'cluster': {'id': cluster.id, 'name': cluster.name},
#             'date_range': {
#                 'start': start_date.isoformat(),
#                 'end':   end_date.isoformat(),
#                 'days':  (end_date - start_date).days + 1,
#             },
#             'summary': {
#                 'total_jobs':                  total_jobs,
#                 'total_activities':            total_activities,
#                 'total_area_allocated':        round(total_area_alloc, 2),
#                 'total_area_completed':        round(float(summary_agg['total_area_completed'] or 0), 2),
#                 'completion_pct':              round(
#                     float(summary_agg['total_area_completed'] or 0) / total_area_alloc * 100, 1
#                 ) if total_area_alloc else 0,
#                 'total_allocated_workers':     total_alloc_workers,
#                 'effective_capacity_workers':  effective_capacity_workers,
#                 'crew_utilization_percent':    round(crew_util_pct, 1),
#                 'slot_utilization_percent':    round(slot_util_pct, 1),
#                 'farmer_amount':               round(farmer_amount, 2),
#                 'mukkadam_amount':             round(mukkadam_amount, 2),
#                 'profit':                      round(profit, 2),
#                 'profit_per_acre':             round(profit_per_acre, 2),
#                 'loss_allocations':            summary_agg['loss_allocations'] or 0,
#                 'dispute_count':               dispute_count,
#                 'dispute_rate_percent':        round(dispute_rate_pct, 1),
#                 'active_mukkadam_count':       len(active_mukkadams),
#             },
#             'by_day':          by_day,
#             'by_mukkadam':     by_mukkadam,
#             'by_activity':     by_activity,
#             'mukkadam_work':   mukkadam_work_list,
#             'farmer_work':     farmer_work,
#             'capacity_demand': capacity_demand,
#             'move_suggestions': move_suggestions,
#             'insights':        insights,
#         })


# # ─────────────────────────────────────────────────────────────────────────────
# # HELPERS
# # ─────────────────────────────────────────────────────────────────────────────

# def _effective_crew_for_mukkadam_on_date(mukkadam, assignment, target_date):
#     """
#     Returns effective crew size for a mukkadam on a specific date,
#     accounting for:
#     1. Updown mukkadams (only available on specific dates/ranges)
#     2. Leaves (general + per-mukkadam)
#     3. Extra workers
#     """
#     if assignment and assignment.mukkadam_type == 'updown':
#         available = False
#         if assignment.updown_mode == 'range':
#             if assignment.updown_from_date and assignment.updown_to_date:
#                 available = assignment.updown_from_date <= target_date <= assignment.updown_to_date
#         elif assignment.updown_mode == 'specific':
#             available = str(target_date) in (assignment.updown_specific_dates or [])
#         if not available:
#             return 0  # updown mukkadam not scheduled this day → 0 capacity

#     return get_effective_crew_size(mukkadam, target_date)


# def _get_capacity_for_cluster(cluster, active_mukkadams, start_date, end_date):
#     """
#     FIX over original get_effective_crew_size_for_cluster:
#     - Only counts active mukkadams (passed in, not re-queried)
#     - Respects updown availability per day
#     - Efficiently pre-fetches assignments
#     Returns: { date_obj: { capacity_workers, total_slots, used_slots } }
#     """
#     assignments = ClusterMukkadamAssignment.objects.filter(
#         cluster=cluster, is_active=True
#     ).select_related('mukkadam')
#     assignment_map = {a.mukkadam_id: a for a in assignments}

#     allocs = Allocation.objects.filter(
#         cluster=cluster,
#         allocated_date__range=[start_date, end_date],
#     ).only('allocated_date', 'allows_second_job', 'mukkadam_id')

#     allocs_by_day = defaultdict(list)
#     for a in allocs:
#         allocs_by_day[a.allocated_date].append(a)

#     result = {}
#     current = start_date
#     while current <= end_date:
#         capacity_workers = 0
#         for m in active_mukkadams:
#             asgn = assignment_map.get(m.mukkadam_id)
#             capacity_workers += _effective_crew_for_mukkadam_on_date(m, asgn, current)

#         day_allocs = allocs_by_day.get(current, [])

#         # Slots: each mukkadam has 2 slots/day
#         # An allocation uses 1 slot if allows_second_job=True (half-day), else 2 (full-day)
#         used_slots  = sum(1 if a.allows_second_job else 2 for a in day_allocs)
#         total_slots = len(active_mukkadams) * 2

#         result[current] = {
#             'capacity_workers': capacity_workers,
#             'total_slots':      total_slots,
#             'used_slots':       min(used_slots, total_slots),  # cap at max
#         }
#         current += timedelta(days=1)

#     return result


# def _build_insights(by_day, by_mukkadam, by_activity,
#                     capacity_demand, total_profit, total_area,
#                     dispute_rate, crew_util):
#     """
#     Build a list of actionable insight cards for the dashboard.
#     """
#     insights = []

#     # ── Overbooked days ──────────────────────────────────────────────
#     overbooked_days = [d for d in capacity_demand if d['is_overbooked']]
#     if overbooked_days:
#         insights.append({
#             'type':     'warning',
#             'title':    f"{len(overbooked_days)} Overbooked Day(s)",
#             'message':  f"Demand exceeds capacity on {', '.join(d['date'] for d in overbooked_days[:3])}"
#                         + (' and more.' if len(overbooked_days) > 3 else '.'),
#             'action':   'Check move_suggestions to rebalance.',
#             'dates':    [d['date'] for d in overbooked_days],
#         })

#     # ── Low utilization days ─────────────────────────────────────────
#     low_util_days = [
#         d for d in by_day
#         if d['effective_capacity_workers'] > 0 and d['crew_utilization_percent'] < 40
#     ]
#     if low_util_days:
#         insights.append({
#             'type':    'info',
#             'title':   f"{len(low_util_days)} Under-Utilised Day(s)",
#             'message': f"Crew utilisation below 40% on {len(low_util_days)} day(s). "
#                        f"Average free workers: {round(sum(d['free_workers'] for d in low_util_days) / len(low_util_days), 1)}.",
#             'action':  'Consider scheduling pending activities on these days.',
#             'dates':   [d['date'] for d in low_util_days],
#         })

#     # ── Dispute rate alert ───────────────────────────────────────────
#     if dispute_rate > 10:
#         insights.append({
#             'type':    'error',
#             'title':   'High Dispute Rate',
#             'message': f"Dispute rate is {round(dispute_rate, 1)}% — above the 10% threshold.",
#             'action':  'Review disputed allocations and resolve payment disagreements.',
#         })

#     # ── Profit margin ────────────────────────────────────────────────
#     if total_area > 0:
#         profit_per_acre = total_profit / total_area
#         if profit_per_acre < 0:
#             insights.append({
#                 'type':    'error',
#                 'title':   'Negative Profit',
#                 'message': f"Loss of ₹{abs(round(profit_per_acre, 2))}/acre across the period.",
#                 'action':  'Check mukkadam rates vs farmer rates for loss-making activities.',
#             })
#         elif profit_per_acre < 200:
#             insights.append({
#                 'type':    'warning',
#                 'title':   'Low Profit Margin',
#                 'message': f"Profit is only ₹{round(profit_per_acre, 2)}/acre.",
#                 'action':  'Review rate cards for improvement opportunities.',
#             })

#     # ── Top performing mukkadam ──────────────────────────────────────
#     if by_mukkadam:
#         top_m = max(by_mukkadam, key=lambda x: x['profit'])
#         if top_m['profit'] > 0:
#             insights.append({
#                 'type':    'success',
#                 'title':   f"Top Mukkadam: {top_m['name']}",
#                 'message': f"Generated ₹{round(top_m['profit'], 2)} profit on "
#                            f"{round(top_m['total_area_allocated'], 2)} acres "
#                            f"({top_m['crew_utilization_percent']}% crew utilisation).",
#             })

#     # ── Loss-making mukkadams ────────────────────────────────────────
#     loss_mukkadams = [m for m in by_mukkadam if m['profit'] < 0]
#     if loss_mukkadams:
#         insights.append({
#             'type':    'warning',
#             'title':   f"{len(loss_mukkadams)} Loss-Making Mukkadam(s)",
#             'message': ', '.join(m['name'] for m in loss_mukkadams) + ' are operating at a loss.',
#             'action':  'Review their mukkadam rate cards.',
#         })

#     # ── Most disputed activity ───────────────────────────────────────
#     disputed_acts = [a for a in by_activity if a['disputes'] > 0]
#     if disputed_acts:
#         worst = max(disputed_acts, key=lambda x: x['disputes'])
#         insights.append({
#             'type':    'warning',
#             'title':   f"Most Disputed Activity: {worst['activity_name']}",
#             'message': f"{worst['disputes']} dispute(s) on {worst['allocations']} allocations "
#                        f"({round(worst['disputes'] / worst['allocations'] * 100, 1)}% rate).",
#             'action':  'Investigate measurement or payment issues for this activity.',
#         })

#     # ── Overall crew utilisation ─────────────────────────────────────
#     if crew_util < 50:
#         insights.append({
#             'type':    'info',
#             'title':   'Low Overall Crew Utilisation',
#             'message': f"Only {round(crew_util, 1)}% of available crew capacity was used.",
#             'action':  'More work can be scheduled without hiring additional mukkadams.',
#         })
#     elif crew_util > 90:
#         insights.append({
#             'type':    'warning',
#             'title':   'Near-Maximum Crew Utilisation',
#             'message': f"Crew utilisation at {round(crew_util, 1)}% — very little buffer.",
#             'action':  'Consider onboarding additional mukkadams for this cluster.',
#         })

#     return insights