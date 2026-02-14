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

    # 1) all plots in this cluster
    plots = (
        Plot.objects.filter(cluster=cluster)
        .select_related("farmer")
    )

    # 2) jobs with activities, grouped by plot
    jobs = (
        Job.objects.filter(cluster=cluster)
        .select_related("farmer", "plot")
        .prefetch_related("activities", "activities__activity")
    )
    jobs_by_plot: Dict[int, List[Job]] = defaultdict(list)
    for job in jobs:
        if job.plot_id:
            jobs_by_plot[job.plot_id].append(job)

    # 3) cluster activity lifecycle
    cluster_rates_qs = ClusterActivityRate.objects.filter(cluster=cluster).select_related("activity")
    cluster_rates: Dict[int, float] = {
        car.activity_id: float(car.rate_per_acre or 0)
        for car in cluster_rates_qs
    }
    catalog_acts: List[ActivityCatalog] = [car.activity for car in cluster_rates_qs]

    today = datetime.date.today()

    for plot in plots:
        if not plot.area_acres:
            continue

        plot_area = float(plot.area_acres)
        plot_jobs = jobs_by_plot.get(plot.id, [])
        if not plot_jobs:
            continue

        # all activities already booked on this plot (any job)
        booked_ids = {
            act.activity_id
            for job in plot_jobs
            for act in job.activities.all()
            if act.plot_id == plot.id
        }

        # choose base date: earliest existing activity on this plot
        booked_dates = [
            act.scheduled_date
            for job in plot_jobs
            for act in job.activities.all()
            if act.plot_id == plot.id and act.scheduled_date
        ]
        base_date = min(booked_dates) if booked_dates else today



    # 1) Existing code: missing catalog activities => status NONE, full plot area
        cumulative_days = 0
        for act in catalog_acts:
            if act.id in booked_ids:
                cumulative_days += effective_gap_days(cluster, act)
                continue

            cluster_rate = cluster_rates.get(act.id, 0.0)
            if cluster_rate <= 0:
                cumulative_days += effective_gap_days(cluster, act)
                continue

            gap_days = effective_gap_days(cluster, act)
            potential_date = base_date + datetime.timedelta(days=cumulative_days)
            potential_date_str = potential_date.isoformat()
            cumulative_days += gap_days

            unbooked_area = plot_area
            potential_revenue = unbooked_area * cluster_rate

            job = plot_jobs[0]
            farmer = plot.farmer or job.farmer

            result[potential_date_str].append(
                PotentialJobDTO(
                    date=potential_date_str,
                    activity_id=act.id,
                    activity_name=act.name,
                    status="NONE",
                    area=unbooked_area,
                    cluster_rate=cluster_rate,
                    potential_revenue=potential_revenue,
                    farmer_id=farmer.farmer_id,
                    farmer_name=farmer.farmer_name,
                    plot_id=plot.id,
                    plot_name=plot.name,
                    job_id=job.job_id,
                    crop_name=job.crop_name,
                    variety=job.variety,
                )
            )

        # 2) NEW: partially booked activities on this plot => status PARTIAL, remaining area
        #    Collect per activity_id the total booked area and booked rate.
        from tender.models import JobActivity  # if not already imported

        acts_on_plot = (
            JobActivity.objects.filter(job__in=plot_jobs, plot=plot)
            .select_related("activity", "job")
        )

        per_activity = {}  # activity_id -> dict(total_booked_area, rate_per_acre, job, farmer, earliest_date)
        for ja in acts_on_plot:
            aid = ja.activity_id
            total = float(ja.total_area or 0)
            if aid not in per_activity:
                per_activity[aid] = {
                    "booked": 0.0,
                    "rate": float(ja.rate_per_acre or 0),
                    "job": ja.job,
                    "farmer": ja.job.farmer,
                    "activity": ja.activity,
                    "date": ja.scheduled_date,
                }
            per_activity[aid]["booked"] += total
            # keep earliest scheduled_date
            if ja.scheduled_date and (
                per_activity[aid]["date"] is None
                or ja.scheduled_date < per_activity[aid]["date"]
            ):
                per_activity[aid]["date"] = ja.scheduled_date

        for aid, info in per_activity.items():
            booked_area = info["booked"]
            if booked_area >= plot_area:
                continue  # fully booked, no yellow

            # remaining area on this plot for this activity
            remaining_area = max(plot_area - booked_area, 0.0)
            if remaining_area <= 0:
                continue

            booked_rate = info["rate"] or cluster_rates.get(aid, 0.0)
            if booked_rate <= 0:
                continue

            potential_revenue = remaining_area * booked_rate

            # date: use earliest booked date for that activity on this plot
            base_date_act = info["date"] or base_date
            potential_date_str = base_date_act.isoformat()

            activity_obj = info["activity"]
            job = info["job"]
            farmer = info["farmer"]

            result[potential_date_str].append(
                PotentialJobDTO(
                    date=potential_date_str,
                    activity_id=aid,
                    activity_name=activity_obj.name,
                    status="PARTIAL",
                    area=remaining_area,
                    cluster_rate=booked_rate,          # use booked rate
                    potential_revenue=potential_revenue,
                    farmer_id=farmer.farmer_id,
                    crop_name=job.crop_name,
                    variety=job.variety,
                    farmer_name=farmer.farmer_name,
                    plot_id=plot.id,
                    plot_name=plot.name,
                    job_id=job.job_id,
                )
            )

    return result
