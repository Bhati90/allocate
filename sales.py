# backfill_sales_date.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from datetime import timedelta
from tender.models import JobActivity, ClusterActivityScheduleRule, ActivityScheduleRule

def get_gap_days(ja):
    clusters = list(ja.plot.clusters.all()) if ja.plot_id else []
    if not clusters:
        clusters = list(ja.job.clusters.all())

    for cluster in clusters:
        rule = ClusterActivityScheduleRule.objects.filter(
            cluster=cluster, activity=ja.activity
        ).first()
        if rule:
            return rule.gap_days

    global_rule = ActivityScheduleRule.objects.filter(activity=ja.activity).first()
    if global_rule:
        return global_rule.gap_days

    return ja.activity.default_gap_days or 3

qs = JobActivity.objects.filter(
    is_lost=False,
    total_area__gt=0,
    job__scheduled_date__isnull=False,
).select_related('activity', 'plot', 'job').prefetch_related(
    'plot__clusters', 'job__clusters'
)

print(f"Processing {qs.count()} activities...")

updated = 0
failed  = 0

for ja in qs:
    try:
        pruning_date = ja.job.scheduled_date  # ← pruning date stored here
        gap_days     = get_gap_days(ja)
        sales_date   = pruning_date + timedelta(days=gap_days)

        if ja.sales_date != sales_date:
            ja.sales_date = sales_date
            ja.save(update_fields=['sales_date'])
            updated += 1

    except Exception as e:
        print(f"  ❌ JA {ja.id}: {e}")
        failed += 1

print(f"\n✅ Updated: {updated} | ❌ Failed: {failed}")