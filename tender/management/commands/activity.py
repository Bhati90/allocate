# management/commands/check_activity_mismatches.py
# Run: python manage.py check_activity_mismatches --ops-token YOUR_TOKEN

import requests
from django.core.management.base import BaseCommand
from tender.models import Job  # ← change app name if needed

BOOKED_VISITS_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'


class Command(BaseCommand):
    help = 'Find jobs where activity names are missing/extra, or plot_id mismatches'

    def add_arguments(self, parser):
        parser.add_argument('--ops-token', type=str, required=True)
        parser.add_argument('--output',    type=str, default='activity_mismatches.txt')

    def handle(self, *args, **options):
        headers = {'Authorization': f'Token {options["ops_token"]}'}
        outfile  = options['output']

        # ── Fetch all pages ───────────────────────────────────────────
        self.stdout.write('📡 Fetching booked visits...')
        api_by_job = {}
        page = 1

        while True:
            try:
                res = requests.get(
                    BOOKED_VISITS_URL,
                    params={'page': page},
                    timeout=15,
                    headers=headers,
                )
                if res.status_code == 401:
                    self.stdout.write(self.style.ERROR('❌ Unauthorized')); return
                if res.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'❌ HTTP {res.status_code}')); break

                data    = res.json()
                results = data.get('data') or data.get('results') or []
                if not results:
                    break

                for item in results:
                    for jid in (item.get('_merged_job_ids') or []):
                        api_by_job[str(jid)] = item
                    api_by_job[str(item.get('id'))] = item

                self.stdout.write(f'  Page {page}: {len(results)} records')
                if not (data.get('next') or data.get('has_next')):
                    break
                page += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Page {page}: {e}')); break

        self.stdout.write(self.style.SUCCESS(f'✅ {len(api_by_job)} jobs fetched\n'))

        # ── Compare ───────────────────────────────────────────────────
        problem_jobs = []
        jobs_ok      = 0
        not_in_api   = 0

        local_jobs = Job.objects.prefetch_related(
            'activities__activity',
            'activities__plot',
        ).all()

        for job in local_jobs:
            api = api_by_job.get(str(job.job_id))
            if not api:
                not_in_api += 1
                continue

            api_activities = api.get('activities') or []

            # Skip activities with 0.0 acres on API side
            api_activities = [
                aa for aa in api_activities
                if float(aa.get('acres') or 0) != 0.0
            ]

            # API: name → list of plot_ids (same name can repeat)
            api_name_plots = {}
            for aa in api_activities:
                name = (aa.get('activity_name') or '').strip()
                if not name:
                    continue
                plot_id = str(aa.get('plot_id') or '').strip()
                api_name_plots.setdefault(name, []).append(plot_id)

            # Local: name → list of plot_codes (same name can repeat)
            local_name_plots = {}
            for la in job.activities.all():
                # Skip 0.0 total_area
                if float(la.total_area or 0) == 0.0:
                    continue
                name = (la.activity.name if la.activity else '').strip()
                if not name:
                    continue
                plot_code = (la.plot.plot_code if la.plot else '') or ''
                local_name_plots.setdefault(name, []).append(plot_code.strip())

            issues = []

            # ── Activity names in API but not local ───────────────────
            for name in api_name_plots:
                if name not in local_name_plots:
                    plots = ', '.join(api_name_plots[name])
                    issues.append(
                        f'  MISSING LOCALLY : "{name}" | api_plot_ids=[{plots}]'
                    )

            # ── Activity names local but not in API ───────────────────
            for name in local_name_plots:
                if name not in api_name_plots:
                    plots = ', '.join(local_name_plots[name])
                    issues.append(
                        f'  EXTRA LOCALLY   : "{name}" | local_plot_codes=[{plots}]'
                    )

            # ── Same name exists both sides — check plot_id match ─────
            for name in set(api_name_plots) & set(local_name_plots):
                api_plots   = sorted(api_name_plots[name])
                local_plots = sorted(local_name_plots[name])

                if api_plots != local_plots:
                    issues.append(
                        f'  PLOT MISMATCH   : "{name}"'
                        f' | local=[{", ".join(local_plots)}]'
                        f' | api=[{", ".join(api_plots)}]'
                    )

            if issues:
                problem_jobs.append({
                    'job_id':      job.job_id,
                    'farmer_name': job.farmer.farmer_name if job.farmer else '—',
                    'issues':      issues,
                })
            else:
                jobs_ok += 1

        # ── Print ─────────────────────────────────────────────────────
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS(f'✅ Jobs OK          : {jobs_ok}'))
        self.stdout.write(self.style.ERROR(  f'❌ Jobs with issues : {len(problem_jobs)}'))
        self.stdout.write(                   f'   Not in API      : {not_in_api}')
        self.stdout.write('=' * 60 + '\n')

        problem_job_ids = []
        for entry in problem_jobs:
            problem_job_ids.append(entry['job_id'])
            self.stdout.write(f"Job {entry['job_id']} | {entry['farmer_name']}")
            for line in entry['issues']:
                self.stdout.write(line)
            self.stdout.write('')

        self.stdout.write('── Problem Job IDs ──')
        self.stdout.write(str(problem_job_ids))

        # ── Save to file ──────────────────────────────────────────────
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(f'Jobs OK          : {jobs_ok}\n')
            f.write(f'Jobs with issues : {len(problem_jobs)}\n')
            f.write(f'Not in API       : {not_in_api}\n')
            f.write('=' * 60 + '\n\n')
            for entry in problem_jobs:
                f.write(f"Job {entry['job_id']} | {entry['farmer_name']}\n")
                for line in entry['issues']:
                    f.write(line + '\n')
                f.write('\n')
            f.write(f'\nProblem Job IDs: {problem_job_ids}\n')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Saved to {outfile}'))