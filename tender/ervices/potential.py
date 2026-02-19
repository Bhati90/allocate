from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict
import datetime

from rest_framework.decorators import api_view
from rest_framework.response import Response

from tender.models import (
    Cluster, Job, Plot,
    ClusterActivityRate, ActivityCatalog, effective_gap_days,
)
from django.db.models import Q


@dataclass
class PotentialJobDTO:
    date: str
    activity_id: int
    activity_name: str
    status: str           # 'NONE'
    area: float
    cluster_rate: float
    potential_revenue: float
    crop_name: str
    variety: str
    farmer_id: str
    farmer_name: str
    plot_id: int
    plot_name: str
    job_id: str

def compute_cluster_potential(cluster: Cluster) -> Dict[str, List[PotentialJobDTO]]:
    result: Dict[str, List[PotentialJobDTO]] = defaultdict(list)

    plots = Plot.objects.filter(clusters=cluster).select_related("farmer")
    jobs = (
    Job.objects.filter(
        Q(clusters=cluster) | Q(plot__clusters=cluster)
    )
    .select_related("farmer", "plot")
    .prefetch_related("activities", "activities__activity")
    .distinct()
)
    
    jobs_by_plot: Dict[int, List[Job]] = defaultdict(list)
    for job in jobs:
        if job.plot_id:
            jobs_by_plot[job.plot_id].append(job)

    # ✅ Get cluster-specific rates
    cluster_rates_qs = ClusterActivityRate.objects.filter(cluster=cluster).select_related("activity")
    cluster_rates: Dict[int, float] = {
        car.activity_id: float(car.rate_per_acre or 0)
        for car in cluster_rates_qs
    }
    
    # ✅ Get ALL activities from ActivityScheduleRule (lifecycle order)
    from tender.models import ActivityScheduleRule
    all_schedule_rules = ActivityScheduleRule.objects.all().select_related('activity').order_by('phase_order')
    catalog_acts: List[ActivityCatalog] = [rule.activity for rule in all_schedule_rules]

    today = datetime.date.today()

    for plot in plots:
        if not plot.area_acres:
            continue

        plot_area = float(plot.area_acres)
        plot_jobs = jobs_by_plot.get(plot.id, [])
        if not plot_jobs:
            continue

        from tender.models import JobActivity
        
        acts_on_plot = (
            JobActivity.objects.filter(job__in=plot_jobs, plot=plot)
            .select_related("activity", "job")
        )

        per_activity = {}
        for ja in acts_on_plot:
            aid = ja.activity_id
            total = float(ja.total_area or 0)
            
            if aid not in per_activity:
                per_activity[aid] = {
                    "booked": total,
                    "rate": float(ja.rate_per_acre or 0),
                    "job": ja.job,
                    "farmer": ja.job.farmer,
                    "activity": ja.activity,
                    "date": ja.scheduled_date,
                }
            else:
                per_activity[aid]["booked"] += total
                if ja.scheduled_date and (
                    per_activity[aid]["date"] is None
                    or ja.scheduled_date < per_activity[aid]["date"]
                ):
                    per_activity[aid]["date"] = ja.scheduled_date

        booked_ids = set(per_activity.keys())

        # AFTER
        # pruning_date = None
        # for act in catalog_acts:
        #     if act.id in booked_ids and per_activity[act.id]["date"]:
        #         pruning_date = per_activity[act.id]["date"]
        #         break

        # if pruning_date is None:
        #     pruning_date = today

        pruning_date = plot.pruning_date if plot.pruning_date else today

        default_job = plot_jobs[0]
        default_farmer = plot.farmer or default_job.farmer

        # Process ALL activities
        for idx, act in enumerate(catalog_acts):
            activity_id = act.id

            if activity_id in cluster_rates:
                rate = cluster_rates[activity_id]
            else:
                rate = float(act.default_rate_per_acre)

            if rate <= 0:
                continue

            if activity_id in booked_ids:
                info = per_activity[activity_id]
                booked_area = info["booked"]
                remaining_area = plot_area - booked_area
                actual_date = info["date"] or pruning_date  # ✅ use pruning_date as fallback

                # ✅ REMOVED: current_date = info["date"]

                if remaining_area > 0:
                    booked_rate = info["rate"] or rate
                    potential_revenue = remaining_area * booked_rate

                    result[actual_date.isoformat()].append(
                        PotentialJobDTO(
                            date=actual_date.isoformat(),
                            activity_id=activity_id,
                            activity_name=act.name,
                            status="PARTIAL",
                            area=remaining_area,
                            cluster_rate=booked_rate,
                            potential_revenue=potential_revenue,
                            farmer_id=info["farmer"].farmer_id,
                            crop_name=info["job"].crop_name,
                            variety=info["job"].variety,
                            farmer_name=info["farmer"].farmer_name,
                            plot_id=plot.id,
                            plot_name=plot.name,
                            job_id=info["job"].job_id,
                        )
                    )
            else:
                gap_days = effective_gap_days(cluster, act)
                potential_date = pruning_date + datetime.timedelta(days=gap_days)  # ✅ always from pruning
                # ✅ REMOVED: current_date = potential_date

                unbooked_area = plot_area
                potential_revenue = unbooked_area * rate

                result[potential_date.isoformat()].append(
                    PotentialJobDTO(
                        date=potential_date.isoformat(),
                        activity_id=activity_id,
                        activity_name=act.name,
                        status="NONE",
                        area=unbooked_area,
                        cluster_rate=rate,
                        potential_revenue=potential_revenue,
                        farmer_id=default_farmer.farmer_id,
                        farmer_name=default_farmer.farmer_name,
                        plot_id=plot.id,
                        plot_name=plot.name,
                        job_id=default_job.job_id,
                        crop_name=default_job.crop_name,
                        variety=default_job.variety,
                    )
                )
    return result