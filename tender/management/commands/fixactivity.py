# management/commands/fix_duplicate_activity_names.py

from django.core.management.base import BaseCommand
from collections import defaultdict
from tender.models import Job, ActivityCatalog
import re


def strip_suffix(name):
    return re.sub(r'(?<=[\w\)]) \d+$', '', name.strip())


def get_or_create_catalog(name):
    catalog, _ = ActivityCatalog.objects.get_or_create(
        name=name,
        defaults={
            'source': 'webhook',
            'default_rate_per_acre': 0,
            'estimated_workers_per_acre': 10,
            'default_gap_days': 3,
        }
    )
    return catalog


class Command(BaseCommand):
    help = 'Fix duplicate activity names per plot per job'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--job-id', type=str)

    def handle(self, *args, **options):
        apply = options['apply']
        job_id_filter = options.get('job_id')

        jobs = Job.objects.prefetch_related('activities__activity', 'activities__plot')
        if job_id_filter:
            jobs = jobs.filter(job_id=job_id_filter)

        total_fixed = 0

        for job in jobs:
            activities = list(
                job.activities.select_related('activity', 'plot').order_by('id')
            )

            groups = defaultdict(list)

            for act in activities:
                # Skip zero or null area
                if not act.total_area or act.total_area == 0:
                    continue

                # Skip area mismatch
                if act.plot and act.total_area != act.plot.area_acres:
                    continue

                plot_key = act.plot_id if act.plot_id is not None else '__no_plot__'
                base_name = strip_suffix(act.activity.name)
                groups[(plot_key, base_name)].append(act)

            for (plot_key, base_name), acts in groups.items():

                # Single activity → don't touch
                if len(acts) == 1:
                    continue

                # 2+ → fix suffixes
                for i, act in enumerate(acts):
                    correct_name = base_name if i == 0 else f"{base_name} {i}"

                    if act.activity.name == correct_name:
                        continue

                    correct_catalog = get_or_create_catalog(correct_name)
                    plot_display = (
                        act.plot.plot_code or f"plot_id={act.plot_id}"
                    ) if act.plot else 'no_plot'

                    self.stdout.write(
                        f"  job={job.job_id} | plot={plot_display} | "
                        f"'{act.activity.name}' → '{correct_name}' "
                        f"(activity_id={act.id})"
                    )

                    if apply:
                        act.activity = correct_catalog
                        act.save(update_fields=['activity'])

                    total_fixed += 1

        mode = "APPLIED" if apply else "DRY RUN"
        self.stdout.write(
            self.style.SUCCESS(f"\n[{mode}] Total fixes: {total_fixed}")
        )
        if not apply:
            self.stdout.write(
                self.style.WARNING("Run with --apply to apply changes")
            )