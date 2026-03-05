from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from tender.models import (
    Cluster,
    ActivityCatalog,
    ActivityScheduleRule,
    ClusterActivityScheduleRule,
    Job,
    JobActivity,
)


# TODO: adjust this to match your pruning catalog row exactly
PRUNING_ACTIVITY_NAME = "Pruning (छाटणी)"


def get_activity_gap_days(activity, cluster):
    """
    1) ClusterActivityScheduleRule if exists
    2) else ActivityScheduleRule (global)
    3) else 0 (no change)
    """
    if cluster is not None:
        override = ClusterActivityScheduleRule.objects.filter(
            cluster=cluster,
            activity=activity,
        ).first()
        if override:
            return override.gap_days

    global_rule = ActivityScheduleRule.objects.filter(
        activity=activity
    ).first()
    if global_rule:
        return global_rule.gap_days

    return 0


def get_pruning_base_date(job, plot):
    """
    For this job/plot, find pruning JobActivity and use its scheduled_date as base.
    Returns date or None.
    """
    pruning_act = ActivityCatalog.objects.filter(name=PRUNING_ACTIVITY_NAME).first()
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


def adjust_job_activities_for_cluster(job, cluster, dry_run=True):
    """
    For an existing job already linked to cluster:
    for each JobActivity on that job/plot,
    set scheduled_date = pruning_date + gap_days
    (if pruning exists and gap_days > 0).
    Returns (total_activities, changed_activities).
    """
    total = 0
    changed = 0

    # We may have multiple plots per job; cache base per plot
    base_date_cache = {}

    for ja in job.activities.all():
        total += 1
        plot = ja.plot  # may be None

        # identify cache key per plot
        plot_key = plot.id if plot else None
        if plot_key not in base_date_cache:
            base_date_cache[plot_key] = get_pruning_base_date(job, plot)

        pruning_date = base_date_cache[plot_key]
        if not pruning_date:
            # no pruning base date for this job/plot -> skip
            continue

        gap_days = get_activity_gap_days(ja.activity, cluster)
        if gap_days == 0:
            # no rule for this activity -> keep its existing date
            continue

        old_date = ja.scheduled_date
        new_date = pruning_date + timedelta(days=gap_days)

        # If there is already a date and it's the same, skip
        if old_date == new_date:
            continue

        print(
            f"[ADJUST] Job {job.job_id} act {ja.id} ({ja.activity.name}) "
            f"base pruning {pruning_date} + {gap_days}d -> {new_date} "
            f"(cluster {cluster.id})"
        )

        if not dry_run:
            ja.scheduled_date = new_date
            ja.save(update_fields=["scheduled_date"])

        changed += 1

    return total, changed


class Command(BaseCommand):
    help = "Adjust JobActivity.scheduled_date based on pruning date and cluster/global gap rules"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print changes, do not save",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_jobs = 0
        total_acts = 0
        total_changed = 0

        jobs = Job.objects.filter(clusters__isnull=False).distinct()

        for job in jobs:
            clusters = list(job.clusters.all())
            if not clusters:
                continue

            total_jobs += 1
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\n=== Job {job.job_id} ({job.farmer.farmer_name}) ==="
                )
            )
            self.stdout.write(
                f"Clusters: {[f'{c.id}:{c.name}' for c in clusters]}"
            )

            # Apply rules for each cluster separately
            for cluster in clusters:
                acts, changed = adjust_job_activities_for_cluster(
                    job, cluster, dry_run=dry_run
                )
                total_acts += acts
                total_changed += changed

        self.stdout.write("\nSUMMARY")
        self.stdout.write(f"Jobs processed: {total_jobs}")
        self.stdout.write(f"Activities seen: {total_acts}")
        self.stdout.write(f"Activities with date changed: {total_changed}")
        self.stdout.write(f"Dry run: {dry_run}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Nothing was saved. Run again without --dry-run to apply changes."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Changes saved."))
