"""
Django Management Command: fillsales
=====================================
Place at: tender/management/commands/fillsales.py

Purpose: Fill sales_date for JobActivities that have NO sales_date.
- Fetch all jobs from API (get_allocated_jobs)
- Match API activity.id with JobActivity.api_activity_id
- For each plot in API, find the Pruning (छाटणी) date
- For non-pruning activities with no sales_date:
    sales_date = pruning_date_from_api + gap_days
- For pruning activities with no sales_date:
    sales_date = scheduled_date (same as pruning date)

Usage:
    python manage.py fillsales              # dry run
    python manage.py fillsales --apply      # update DB
"""

import csv
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from tender.models import (
    JobActivity,
    ClusterActivityScheduleRule, ActivityScheduleRule,
)

API_URL = "https://ops.bharatintelligence.ai/ops/api/get_allocated_jobs/"
API_TOKEN = "Token 89b9fd0698faed6c12c1a8e714fca12c86ee2000"


class Command(BaseCommand):
    help = "Fill sales_date for activities that have no sales_date, using API pruning data"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False)
        parser.add_argument('--csv-output', type=str, default='fillsales_report.csv')

    def handle(self, *args, **options):
        apply = options['apply']
        csv_path = options['csv_output']

        if apply:
            self.stdout.write(self.style.WARNING("⚠️  APPLY MODE"))
        else:
            self.stdout.write(self.style.NOTICE("🔍 DRY RUN"))

        # ── Step 1: Get all JobActivities with no sales_date ──
        no_sales = (
            JobActivity.objects
            .filter(sales_date__isnull=True)
            .exclude(total_area=0)   
            .exclude(api_activity_id='')
            .exclude(api_activity_id__isnull=True)
            .select_related('activity', 'job', 'plot')
            .prefetch_related('plot__clusters', 'allocations')
        )

        if not no_sales.exists():
            self.stdout.write(self.style.SUCCESS("✅ All activities already have sales_date."))
            return

        self.stdout.write(f"Found {no_sales.count()} activities with no sales_date")

        # ── Step 2: Fetch API data ──
        api_activity_map, pruning_by_plot = self._fetch_api()

        if not api_activity_map:
            self.stdout.write(self.style.ERROR("❌ No API data fetched. Aborting."))
            return

        # ── Step 3: Process each ──
        results = []
        update_count = 0

        for ja in no_sales:
            api_act_id = ja.api_activity_id.strip()

            # Match with API
            api_act = api_activity_map.get(api_act_id)
            if not api_act:
                results.append(self._row(ja, None, None, None, "NO API MATCH"))
                continue

            api_plot_id = api_act['plot_id']
            is_pruning = self._is_pruning_name(api_act['activity_name'])

            if is_pruning:
                # Pruning itself: sales_date = its own date
                new_sales = api_act['date']
                gap_used = 0
                gap_src = "Pruning → own date"
            else:
                # Find pruning date for this plot from API
                pruning_date = pruning_by_plot.get(api_plot_id)
                if not pruning_date:
                    results.append(self._row(ja, api_act, None, None, "NO PRUNING IN API FOR PLOT"))
                    continue

                gap_used, gap_src = self._get_gap_days(ja)
                new_sales = pruning_date + timedelta(days=gap_used)

            results.append(self._row(ja, api_act, new_sales, gap_used, "FILL sales_date", gap_src))

            if apply and new_sales:
                ja.sales_date = new_sales
                ja.save(update_fields=['sales_date', 'updated_at'])
                update_count += 1

        # ── CSV ──
        fieldnames = [
            'ja_id', 'api_activity_id', 'activity_name', 'plot',
            'scheduled_date', 'api_date', 'api_plot_id',
            'gap_days', 'gap_source', 'new_sales_date', 'action',
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: v for k, v in r.items() if k in fieldnames})

        # ── Summary ──
        actions = Counter(r['action'] for r in results)
        self.stdout.write(f"\nTotal checked: {len(results)}")
        for act, cnt in actions.most_common():
            self.stdout.write(f"  {act}: {cnt}")
        self.stdout.write(f"CSV: {csv_path}")

        if apply:
            self.stdout.write(self.style.SUCCESS(f"✅ Filled sales_date for {update_count} activities."))
        else:
            fills = sum(1 for r in results if r['action'] == 'FILL sales_date')
            self.stdout.write(self.style.WARNING(f"⏳ {fills} to fill. Re-run with --apply"))

    # ──────────────────────────────────────────
    # API
    # ──────────────────────────────────────────

    def _fetch_api(self):
        """
        Returns:
            activity_map: {str(api_activity_id): {activity_name, plot_id, date}}
            pruning_by_plot: {str(plot_id): date}  (earliest pruning per plot)
        """
        self.stdout.write("📡 Fetching from API...")
        activity_map = {}
        pruning_by_plot = {}

        try:
            resp = requests.get(API_URL, headers={"Authorization": API_TOKEN}, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') != 'success':
                self.stdout.write(self.style.ERROR(f"API returned: {data.get('status')}"))
                return activity_map, pruning_by_plot

            jobs = data.get('data', [])
            self.stdout.write(f"  Fetched {len(jobs)} jobs, parsing activities...")

            for job in jobs:
                for act in job.get('activities', []):
                    act_id = str(act.get('id', ''))
                    plot_id = str(act.get('plot_id') or '')
                    act_name = act.get('activity_name', '')
                    date_str = act.get('date_time')

                    act_date = None
                    if date_str:
                        try:
                            act_date = datetime.fromisoformat(date_str).date()
                        except (ValueError, TypeError):
                            pass

                    activity_map[act_id] = {
                        'activity_name': act_name,
                        'plot_id': plot_id,
                        'date': act_date,
                    }

                    # Track pruning per plot
                    if act_date and self._is_pruning_name(act_name):
                        existing = pruning_by_plot.get(plot_id)
                        if existing is None or act_date < existing:
                            pruning_by_plot[plot_id] = act_date

            self.stdout.write(f"  {len(activity_map)} activities, {len(pruning_by_plot)} plots with pruning")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"API error: {e}"))

        return activity_map, pruning_by_plot

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _is_pruning_name(name):
        return 'pruning' in name.lower() or 'छाटणी' in name

    @staticmethod
    def _get_gap_days(ja):
        """Get gap from cluster rule → global rule → catalog default → 3"""
        plot = ja.plot
        activity = ja.activity

        if plot:
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

    @staticmethod
    def _row(ja, api_act, new_sales, gap_used, action, gap_src=""):
        farmer = getattr(ja.plot, 'farmer', None) if ja.plot else None
        farmer_name = getattr(farmer, 'farmer_name', '?') if farmer else '?'
        plot_name = ja.plot.name if ja.plot else '?'

        return {
            'ja_id': ja.pk,
            'api_activity_id': ja.api_activity_id,
            'activity_name': ja.activity.name,
            'plot': f"{farmer_name} - {plot_name}",
            'scheduled_date': str(ja.scheduled_date),
            'api_date': str(api_act['date']) if api_act else '',
            'api_plot_id': str(api_act['plot_id']) if api_act else '',
            'gap_days': gap_used,
            'gap_source': gap_src,
            'new_sales_date': str(new_sales) if new_sales else '',
            'action': action,
        }
