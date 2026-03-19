from datetime import timedelta
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ClusterActivityScheduleRule,ActivityScheduleRule,JobActivity

def get_gap_days(cluster, activity):
    """
    Returns gap_days for an activity:
    Cluster override → ActivityScheduleRule global → ActivityCatalog.default_gap_days → 3
    """
    if cluster:
        override = ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=activity
        ).first()
        if override:
            return override.gap_days

    global_rule = ActivityScheduleRule.objects.filter(activity=activity).first()
    if global_rule:
        return global_rule.gap_days

    # Final fallback: the catalog's own default_gap_days
    return activity.default_gap_days or 3


def reschedule_pending_activities(cluster_id=None, dry_run=False):
    """
    Reschedules only truly pending activities (not moved, not allocated, not completed).
    new scheduled_date = plot.pruning_date + gap_days

    Returns a summary dict.
    """
    # ── Which activities are eligible ──────────────────────────────────────
    # Skip if: manually moved, any allocation, in_progress/completed/fully_allocated
    SKIP_STATUSES = {'partially_allocated', 'fully_allocated', 'in_progress', 'completed'}

    qs = JobActivity.objects.filter(
        is_manually_moved=False,
        is_lost=False,
        allocation_status='pending',
        allocated_area=0,
        plot__isnull=False,
        plot__pruning_date__isnull=False,   # need pruning date to compute
    ).select_related(
        'activity', 'plot', 'job'
    ).prefetch_related(
        'plot__clusters'
    )

    if cluster_id:
        qs = qs.filter(plot__clusters__id=cluster_id)

    updated   = []
    skipped   = []
    no_rule   = []

    with transaction.atomic():
        for act in qs:
            plot    = act.plot
            cluster = plot.clusters.first()   # first cluster wins

            gap = get_gap_days(cluster, act.activity)
            new_date = plot.pruning_date + timedelta(days=gap)

            if act.scheduled_date == new_date:
                skipped.append({
                    'id':       act.id,
                    'reason':   'date_unchanged',
                    'job':      act.job.job_id,
                    'activity': act.activity.name,
                    'plot':     plot.name,
                })
                continue

            old_date = act.scheduled_date
            if not dry_run:
                act.scheduled_date = new_date
                # use update() to bypass save() signal overhead
                # but we want save() for status recalc — call it directly
                JobActivity.objects.filter(pk=act.pk).update(
                    scheduled_date=new_date
                )

            updated.append({
                'id':         act.id,
                'job':        act.job.job_id,
                'activity':   act.activity.name,
                'plot':       plot.name,
                'cluster':    cluster.name if cluster else '—',
                'pruning':    str(plot.pruning_date),
                'gap_days':   gap,
                'old_date':   str(old_date) if old_date else None,
                'new_date':   str(new_date),
            })

    return {
        'updated_count': len(updated),
        'skipped_count': len(skipped),
        'dry_run':       dry_run,
        'updated':       updated,
        'skipped':       skipped,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reschedule_activities_view(request):
    """
    POST /api/reschedule-activities/
    Body (optional): { "cluster_id": 3, "dry_run": true }

    dry_run=true → shows what WOULD change without saving.
    """
    cluster_id = request.data.get('cluster_id')   # None = all clusters
    dry_run    = bool(request.data.get('dry_run', False))

    result = reschedule_pending_activities(
        cluster_id=cluster_id,
        dry_run=dry_run,
    )
    return Response(result, status=200)