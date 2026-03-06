from datetime import date, datetime, timedelta
from collections import defaultdict

from django.db.models import Sum, Avg, Count, Q, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # or IsAuthenticated

from .models import Allocation, Job, JobActivity, Cluster, Mukkadam
from .utils import get_effective_crew_size_for_cluster, get_effective_crew_size
# ^ adjust if these live in different modules
# e.g. from .utils.cluster_insights import get_effective_crew_size_for_cluster
#      from .capacity import get_effective_crew_size


class ClusterInsightsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, cluster_id):
        cluster = Cluster.objects.get(pk=cluster_id)

        # parse dates
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        today = date.today()
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = today  # or today - timedelta(days=7)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today

        # allocations for this cluster in range
        alloc_qs = Allocation.objects.filter(
            cluster=cluster,
            allocated_date__range=[start_date, end_date]
        )

        # summary aggregates
        summary_agg = alloc_qs.aggregate(
            total_area_allocated=Sum('allocated_area'),
            total_area_completed=Sum('actual_area_completed'),
            total_allocated_workers=Sum('allocated_workers'),
            farmer_amount=Sum('farmer_amount'),
            mukkadam_amount=Sum('mukkadam_amount'),
            avg_efficiency_score=Avg('efficiency_score'),
            loss_allocations=Count('id', filter=Q(profit__lt=0)),
            dispute_count=Count('id', filter=Q(payment_status='dispute')),
        )

        # jobs / activities in this cluster
        jobs_qs = Job.objects.filter(
            clusters=cluster,
            activities__scheduled_date__range=[start_date, end_date]
        ).distinct()

        total_jobs = jobs_qs.count()
        total_activities = JobActivity.objects.filter(
            job__clusters=cluster,
            scheduled_date__range=[start_date, end_date]
        ).count()

        # capacity + slots per day
        capacity_by_day = get_effective_crew_size_for_cluster(cluster, start_date, end_date)

        effective_capacity_workers = sum(v["capacity_workers"] for v in capacity_by_day.values())
        total_slots = sum(v["total_slots"] for v in capacity_by_day.values())
        used_slots = sum(v["used_slots"] for v in capacity_by_day.values())

        total_alloc_workers = summary_agg['total_allocated_workers'] or 0
        crew_util_percent = (total_alloc_workers / effective_capacity_workers * 100) if effective_capacity_workers else 0
        slot_util_percent = (used_slots / total_slots * 100) if total_slots else 0

        farmer_amount = summary_agg['farmer_amount'] or 0
        mukkadam_amount = summary_agg['mukkadam_amount'] or 0
        profit = farmer_amount - mukkadam_amount
        total_area_allocated = summary_agg['total_area_allocated'] or 0
        profit_per_acre = float(profit) / float(total_area_allocated) if total_area_allocated else 0

        dispute_count = summary_agg['dispute_count'] or 0
        base_for_dispute = alloc_qs.filter(status='completed').count() or 1
        dispute_rate_percent = dispute_count / base_for_dispute * 100

        # ---- by day (per date) ----
        by_day = []
        current = start_date
        while current <= end_date:
            day_allocs = alloc_qs.filter(allocated_date=current)
            agg = day_allocs.aggregate(
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                allocated_workers=Sum('allocated_workers'),
                profit=Sum(F('farmer_amount') - F('mukkadam_amount')),
                disputes=Count('id', filter=Q(payment_status='dispute')),
            )
            cap_info = capacity_by_day.get(current, {"capacity_workers": 0, "total_slots": 0, "used_slots": 0})
            eff_cap = cap_info["capacity_workers"]
            used_slots_day = cap_info["used_slots"]
            total_slots_day = cap_info["total_slots"]

            jobs_scheduled = jobs_qs.filter(
                activities__scheduled_date=current
            ).distinct().count()
            jobs_completed = jobs_qs.filter(
                status='completed',
                completed_date=current
            ).distinct().count()

            by_day.append({
                "date": current.isoformat(),
                "total_area_allocated": float(agg['total_area_allocated'] or 0),
                "total_area_completed": float(agg['total_area_completed'] or 0),
                "allocated_workers": agg['allocated_workers'] or 0,
                "effective_capacity_workers": eff_cap,
                "crew_utilization_percent": (agg['allocated_workers'] or 0) / eff_cap * 100 if eff_cap else 0,
                "slot_utilization_percent": used_slots_day / total_slots_day * 100 if total_slots_day else 0,
                "profit": float(agg['profit'] or 0),
                "jobs_scheduled": jobs_scheduled,
                "jobs_completed": jobs_completed,
                "disputes": agg['disputes'] or 0,
            })
            current += timedelta(days=1)

        # ---- by mukkadam (summary per mukkadam in this cluster) ----
        by_mukkadam = []
        for m in Mukkadam.objects.filter(clusters=cluster).distinct():
            m_allocs = alloc_qs.filter(mukkadam=m)
            m_agg = m_allocs.aggregate(
                allocations=Count('id'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                allocated_workers_total=Sum('allocated_workers'),
                avg_efficiency_score=Avg('efficiency_score'),
                profit=Sum(F('farmer_amount') - F('mukkadam_amount')),
                disputes=Count('id', filter=Q(payment_status='dispute')),
            )
            cap_sum = 0
            current = start_date
            while current <= end_date:
                cap_sum += get_effective_crew_size(m, current)
                current += timedelta(days=1)
            alloc_workers = m_agg['allocated_workers_total'] or 0
            crew_util = alloc_workers / cap_sum * 100 if cap_sum else 0

            by_mukkadam.append({
                "mukkadam_id": m.mukkadam_id,
                "name": m.mukkadam_name,
                "crew_size": m.crew_size,
                "max_crew_capacity": m.max_crew_capacity,
                "allocations": m_agg['allocations'] or 0,
                "allocated_workers_total": alloc_workers,
                "effective_capacity_workers": cap_sum,
                "crew_utilization_percent": crew_util,
                "total_area_allocated": float(m_agg['total_area_allocated'] or 0),
                "total_area_completed": float(m_agg['total_area_completed'] or 0),
                "avg_efficiency_score": float(m_agg['avg_efficiency_score'] or 0),
                "profit": float(m_agg['profit'] or 0),
                "disputes": m_agg['disputes'] or 0,
            })

        # ---- by activity (within this cluster) ----
        activity_qs = JobActivity.objects.filter(
            job__clusters=cluster,
            allocations__allocated_date__range=[start_date, end_date]
        ).distinct()

        by_activity = []
        for act in activity_qs:
            a_allocs = alloc_qs.filter(job_activity=act)
            a_agg = a_allocs.aggregate(
                allocations=Count('id'),
                total_area_allocated=Sum('allocated_area'),
                total_area_completed=Sum('actual_area_completed'),
                farmer_amount=Sum('farmer_amount'),
                mukkadam_amount=Sum('mukkadam_amount'),
                loss_allocations=Count('id', filter=Q(profit__lt=0)),
            )
            ta = a_agg['total_area_allocated'] or 0
            fa = a_agg['farmer_amount'] or 0
            ma = a_agg['mukkadam_amount'] or 0
            profit_a = fa - ma
            avg_farmer_rate = float(fa) / float(ta) if ta else 0
            avg_mukkadam_rate = float(ma) / float(ta) if ta else 0
            avg_profit_per_acre = float(profit_a) / float(ta) if ta else 0

            by_activity.append({
                "activity_id": act.id,
                "activity_name": act.activity.name,
                "allocations": a_agg['allocations'] or 0,
                "total_area_allocated": float(ta),
                "total_area_completed": float(a_agg['total_area_completed'] or 0),
                "avg_farmer_rate": avg_farmer_rate,
                "avg_mukkadam_rate": avg_mukkadam_rate,
                "avg_profit_per_acre": avg_profit_per_acre,
                "profit": float(profit_a),
                "loss_allocations": a_agg['loss_allocations'] or 0,
            })

        # ---- Mukkadam-wise detailed work ----
        mukkadam_work = defaultdict(list)

        alloc_detailed = (
            alloc_qs
            .select_related(
                'mukkadam',
                'job_activity__job__farmer',
                'job_activity__activity',
                'job_activity__plot',
            )
        )

        for a in alloc_detailed:
            ja = a.job_activity
            job = ja.job
            farmer = job.farmer
            plot = ja.plot

            mukkadam_work[a.mukkadam.mukkadam_id].append({
                "allocation_id": a.id,
                "date": a.allocated_date.isoformat(),
                "job_id": job.job_id,
                "farmer_id": farmer.farmer_id,
                "farmer_name": farmer.farmer_name,
                "plot_name": plot.name if plot else None,
                "activity_id": ja.activity.id,
                "activity_name": ja.activity.name,
                "allocated_area": float(a.allocated_area),
                "actual_area_completed": float(a.actual_area_completed or 0),
                "allocated_workers": a.allocated_workers,
                "work_status": a.work_status,
                "payment_status": a.payment_status,
                "profit": float(a.profit),
                "allows_second_job": a.allows_second_job,
                "is_carry_forward": a.is_carry_forward,
                "is_auto_allocated": a.is_auto_allocated,
            })

        mukkadam_work_list = []
        for m in Mukkadam.objects.filter(clusters=cluster).distinct():
            mukkadam_work_list.append({
                "mukkadam_id": m.mukkadam_id,
                "name": m.mukkadam_name,
                "allocations": mukkadam_work.get(m.mukkadam_id, []),
            })

        # ---- Farmer-wise work + allocation status ----
        farmer_work_map = defaultdict(lambda: {
            "farmer_id": None,
            "farmer_name": None,
            "activities": [],
        })

        farmer_activities = JobActivity.objects.filter(
            job__clusters=cluster,
            scheduled_date__range=[start_date, end_date]
        ).select_related(
            'job__farmer',
            'activity',
            'plot',
        ).prefetch_related('allocations__mukkadam')

        for ja in farmer_activities:
            job = ja.job
            farmer = job.farmer
            plot = ja.plot
            f_entry = farmer_work_map[farmer.farmer_id]
            f_entry["farmer_id"] = farmer.farmer_id
            f_entry["farmer_name"] = farmer.farmer_name

            ja_allocs = [
                {
                    "allocation_id": a.id,
                    "date": a.allocated_date.isoformat(),
                    "mukkadam_id": a.mukkadam.mukkadam_id,
                    "mukkadam_name": a.mukkadam.mukkadam_name,
                    "allocated_area": float(a.allocated_area),
                    "allocated_workers": a.allocated_workers,
                    "work_status": a.work_status,
                    "payment_status": a.payment_status,
                    "profit": float(a.profit),
                }
                for a in ja.allocations.all()
                if start_date <= a.allocated_date <= end_date and a.cluster_id == cluster.id
            ]

            f_entry["activities"].append({
                "job_id": job.job_id,
                "plot_name": plot.name if plot else None,
                "activity_id": ja.activity.id,
                "activity_name": ja.activity.name,
                "scheduled_date": ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                "total_area": float(ja.total_area),
                "allocated_area": float(ja.allocated_area),
                "remaining_area": float(ja.remaining_area),
                "allocation_status": ja.allocation_status,
                "allocations": ja_allocs,
            })

        farmer_work = list(farmer_work_map.values())

        # ---- Capacity vs demand per day ----
        capacity_demand = []
        current = start_date
        while current <= end_date:
            cap_info = capacity_by_day.get(current, {"capacity_workers": 0, "total_slots": 0, "used_slots": 0})
            capacity_workers = cap_info["capacity_workers"]

            day_allocs = alloc_qs.filter(allocated_date=current)
            demand_workers = day_allocs.aggregate(
                total_workers=Sum('allocated_workers')
            )['total_workers'] or 0

            shortage_workers = max(demand_workers - capacity_workers, 0)
            is_overbooked = shortage_workers > 0

            capacity_demand.append({
                "date": current.isoformat(),
                "capacity_workers": capacity_workers,
                "demand_workers": demand_workers,
                "shortage_workers": shortage_workers,
                "is_overbooked": is_overbooked,
            })
            current += timedelta(days=1)

        # ---- Smart move suggestions ----
        cap_dem_by_date = {d["date"]: d for d in capacity_demand}
        move_suggestions = []
        FREE_THRESHOLD = 5          # min free workers on target day
        SEARCH_WINDOW_DAYS = 5      # how many days around to search

        for cd in capacity_demand:
            if not cd["is_overbooked"]:
                continue
            day = datetime.strptime(cd["date"], "%Y-%m-%d").date()

            candidate_days = []
            for delta in range(1, SEARCH_WINDOW_DAYS + 1):
                for sign in (-1, 1):
                    target = day + timedelta(days=sign * delta)
                    if target < start_date or target > end_date:
                        continue
                    key = target.isoformat()
                    info = cap_dem_by_date.get(key)
                    if not info:
                        continue
                    free = info["capacity_workers"] - info["demand_workers"]
                    if free >= FREE_THRESHOLD:
                        candidate_days.append((target, free))

            if not candidate_days:
                continue

            candidate_days.sort(key=lambda x: (-x[1], abs((x[0] - day).days)))
            best_day, best_free = candidate_days[0]

            flex_activities = JobActivity.objects.filter(
                job__clusters=cluster,
                scheduled_date=day,
                is_strict=False,
                remaining_area__gt=0,
            )

            activities_list = []
            for ja in flex_activities:
                activities_list.append({
                    "job_id": ja.job.job_id,
                    "farmer_id": ja.job.farmer.farmer_id,
                    "farmer_name": ja.job.farmer.farmer_name,
                    "activity_id": ja.activity.id,
                    "activity_name": ja.activity.name,
                    "scheduled_date": ja.scheduled_date.isoformat() if ja.scheduled_date else None,
                    "remaining_area": float(ja.remaining_area),
                })

            if not activities_list:
                continue

            move_suggestions.append({
                "overbooked_date": day.isoformat(),
                "target_date": best_day.isoformat(),
                "free_workers_on_target": best_free,
                "flexible_activities": activities_list,
            })

        data = {
            "cluster": {"id": cluster.id, "name": cluster.name},
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_jobs": total_jobs,
                "total_activities": total_activities,
                "total_area_allocated": float(total_area_allocated),
                "total_area_completed": float(summary_agg['total_area_completed'] or 0),
                "total_allocated_workers": total_alloc_workers,
                "effective_capacity_workers": effective_capacity_workers,
                "crew_utilization_percent": crew_util_percent,
                "slot_utilization_percent": slot_util_percent,
                "farmer_amount": float(farmer_amount),
                "mukkadam_amount": float(mukkadam_amount),
                "profit": float(profit),
                "profit_per_acre": profit_per_acre,
                "loss_allocations": summary_agg['loss_allocations'] or 0,
                "dispute_count": dispute_count,
                "dispute_rate_percent": dispute_rate_percent,
                "avg_efficiency_score": float(summary_agg['avg_efficiency_score'] or 0),
            },
            "by_day": by_day,
            "by_mukkadam": by_mukkadam,
            "by_activity": by_activity,
            "mukkadam_work": mukkadam_work_list,
            "farmer_work": farmer_work,
            "capacity_demand": capacity_demand,
            "move_suggestions": move_suggestions,
        }
        return Response(data)
