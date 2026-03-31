"""
Django Management Command: fixsales
====================================
Place at: tender/management/commands/fixsales.py

Rules:
1. Allocated → NEVER touch
2. Unallocated + scheduled_date is MORE than 5 days before sales_date → Apply pruning + gap
3. All other cases → No change

Usage:
    python manage.py fixsales              # dry run
    python manage.py fixsales --apply      # update DB
    python manage.py fixsales --cluster=Nashik
"""

import csv
from datetime import timedelta
from collections import Counter

from django.core.management.base import BaseCommand

from tender.models import (
    Plot, JobActivity,
    ClusterActivityScheduleRule, ActivityScheduleRule,
)


class Command(BaseCommand):
    help = "Fix scheduled_date based on Pruning base + gap days"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False)
        parser.add_argument('--cluster', type=str, default=None)
        parser.add_argument('--plot-id', type=int, default=None)
        parser.add_argument('--csv-output', type=str, default='schedule_fix_report.csv')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        csv_path = options['csv_output']

        if apply_changes:
            self.stdout.write(self.style.WARNING("⚠️  APPLY MODE"))
        else:
            self.stdout.write(self.style.NOTICE("🔍 DRY RUN"))

        plots_qs = Plot.objects.all().prefetch_related(
            'activities__activity', 'activities__allocations', 'clusters',
        ).select_related('farmer')

        if options['plot_id']:
            plots_qs = plots_qs.filter(id=options['plot_id'])
        if options['cluster']:
            plots_qs = plots_qs.filter(clusters__name=options['cluster']).distinct()

        results = []
        update_count = 0

        for plot in plots_qs.iterator():
            job_activities = (
                JobActivity.objects
                .filter(plot=plot)
                .select_related('activity', 'job')
                .order_by('scheduled_date')
            )

            # Find Pruning → BASE DATE
            pruning_ja = None
            for ja in job_activities:
                if self._is_pruning(ja.activity):
                    pruning_ja = ja
                    break

            base_date = pruning_ja.scheduled_date if pruning_ja and pruning_ja.scheduled_date else None

            for ja in job_activities:
                row = self._evaluate(ja, plot, base_date)
                results.append(row)

                if apply_changes and row['action'] == 'UPDATE scheduled_date':
                    new_date = row['_new_date_raw']
                    if new_date:
                        ja.scheduled_date = new_date
                        ja.save(update_fields=['scheduled_date', 'updated_at'])
                        update_count += 1

        # CSV
        fieldnames = [
            'plot', 'activity', 'current_scheduled_date', 'sales_date',
            'diff_days', 'is_allocated', 'gap_days_used', 'gap_source',
            'new_scheduled_date', 'action',
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: v for k, v in r.items() if k in fieldnames})

        # Summary
        actions = Counter(r['action'] for r in results)
        self.stdout.write(f"\nTotal: {len(results)}")
        for act, cnt in actions.most_common():
            self.stdout.write(f"  {act}: {cnt}")
        self.stdout.write(f"\nCSV: {csv_path}")

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"✅ Updated {update_count} scheduled_dates."))
        else:
            needs = sum(1 for r in results if r['action'] == 'UPDATE scheduled_date')
            self.stdout.write(self.style.WARNING(f"⏳ {needs} need updating. Re-run with --apply"))

    @staticmethod
    def _is_pruning(activity):
        name_lower = activity.name.lower()
        return 'pruning' in name_lower or 'छाटणी' in activity.name

    @staticmethod
    def _get_gap_days(plot, activity):
        for cluster in plot.clusters.all():
            rule = ClusterActivityScheduleRule.objects.filter(
                cluster=cluster, activity=activity,
            ).first()
            if rule:
                return rule.gap_days, f"Cluster: {cluster.name}"

        global_rule = ActivityScheduleRule.objects.filter(activity=activity).first()
        if global_rule:
            return global_rule.gap_days, "Global Rule"

        default = activity.default_gap_days or 3
        return default, "Catalog Default" if activity.default_gap_days else "Fallback (3)"

    def _evaluate(self, ja, plot, base_date):
        current_sched = ja.scheduled_date
        current_sales = ja.sales_date
        is_alloc = ja.allocation_status in ('fully_allocated', 'completed', 'in_progress')

        gap_days_used = None
        gap_source = ""
        new_sched = current_sched
        action = "NO CHANGE"

        # Calculate what scheduled_date SHOULD be (pruning + gap)
        if self._is_pruning(ja.activity):
            expected = current_sched
            gap_days_used = 0
            gap_source = "BASE (Pruning)"
        elif base_date is None:
            expected = current_sched
            gap_source = "No Pruning in plot"
        else:
            gap_days_used, gap_source = self._get_gap_days(plot, ja.activity)
            expected = base_date + timedelta(days=gap_days_used)

        # ── RULE 1: Allocated → NEVER touch ──
        if is_alloc:
            action = "SKIP (allocated)"

        # ── RULE 2 & 3 & 4: Unallocated ──
        elif current_sched and current_sales:
            diff = (current_sched - current_sales).days  # negative = sched is before sales

            if diff < -5:
                # scheduled_date is MORE than 5 days before sales_date → FIX IT
                action = "UPDATE scheduled_date"
                new_sched = expected
            else:
                # diff is -5 to 0 (within range) or positive (sched after sales) → no change
                action = f"OK (diff={diff}d, within tolerance)"

        elif current_sched and not current_sales:
            action = "OK (no sales_date to compare)"
        else:
            action = "OK (no scheduled_date)"

        diff_days = (current_sched - current_sales).days if current_sched and current_sales else None
        farmer_name = getattr(plot.farmer, 'farmer_name', '?')

        return {
            'plot': f"{farmer_name} - {plot.name}",
            'activity': ja.activity.name,
            'current_scheduled_date': str(current_sched),
            'sales_date': str(current_sales),
            'diff_days': diff_days,
            'is_allocated': is_alloc,
            'gap_days_used': gap_days_used,
            'gap_source': gap_source,
            'new_scheduled_date': str(new_sched),
            'action': action,
            '_new_date_raw': new_sched,
        }
