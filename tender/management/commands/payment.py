# management/commands/check_activity_mismatches.py
# Run: python manage.py check_activity_mismatches --ops-token YOUR_TOKEN

import requests
from django.core.management.base import BaseCommand
from tender.models import Job  # ← change app name if needed

BOOKED_VISITS_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'


class Command(BaseCommand):
    help = 'Check activity names/plots, booking amounts, and payments against API'

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
            'booking__payments',
        ).all()

        for job in local_jobs:
            api = api_by_job.get(str(job.job_id))
            if not api:
                not_in_api += 1
                continue

            api_activities = api.get('activities') or []
            api_booking    = api.get('booking') or {}
            api_payments   = api_booking.get('payments') or []

            issues = []

            # ══════════════════════════════════════════════════
            # A — ACTIVITIES: name presence + plot_id match
            # ══════════════════════════════════════════════════

            # Skip 0.0 acres on API side
            api_activities = [
                aa for aa in api_activities
                if float(aa.get('acres') or 0) != 0.0
            ]

            # API: name → list of plot_ids
            api_name_plots = {}
            for aa in api_activities:
                name = (aa.get('activity_name') or '').strip()
                if not name:
                    continue
                plot_id = str(aa.get('plot_id') or '').strip()
                api_name_plots.setdefault(name, []).append(plot_id)

            # Local: name → list of plot_codes (skip 0.0 area)
            local_name_plots = {}
            for la in job.activities.all():
                if float(la.total_area or 0) == 0.0:
                    continue
                name = (la.activity.name if la.activity else '').strip()
                if not name:
                    continue
                plot_code = (la.plot.plot_code if la.plot else '') or ''
                local_name_plots.setdefault(name, []).append(plot_code.strip())

            for name in api_name_plots:
                if name not in local_name_plots:
                    plots = ', '.join(api_name_plots[name])
                    issues.append(
                        f'  [ACTIVITY] MISSING LOCALLY : "{name}" | api_plot_ids=[{plots}]'
                    )

            for name in local_name_plots:
                if name not in api_name_plots:
                    plots = ', '.join(local_name_plots[name])
                    issues.append(
                        f'  [ACTIVITY] EXTRA LOCALLY   : "{name}" | local_plot_codes=[{plots}]'
                    )

            for name in set(api_name_plots) & set(local_name_plots):
                api_plots   = sorted(api_name_plots[name])
                local_plots = sorted(local_name_plots[name])
                if api_plots != local_plots:
                    issues.append(
                        f'  [ACTIVITY] PLOT MISMATCH   : "{name}"'
                        f' | local=[{", ".join(local_plots)}]'
                        f' | api=[{", ".join(api_plots)}]'
                    )

            # ══════════════════════════════════════════════════
            # B — BOOKING: total_amount / advance_paid / balance
            # ══════════════════════════════════════════════════
            try:
                booking = job.booking

                checks = [
                    ('booking_id',   int(booking.booking_id),                     int(api_booking.get('id') or 0)),
                    ('total_amount', round(float(booking.total_amount  or 0), 2), round(float(api_booking.get('total_amount')  or 0), 2)),
                    ('advance_paid', round(float(booking.advance_paid  or 0), 2), round(float(api_booking.get('advance_paid')  or 0), 2)),
                    ('balance',      round(float(booking.balance       or 0), 2), round(float(api_booking.get('balance')       or 0), 2)),
                ]
                for field, lv, av in checks:
                    if lv != av:
                        issues.append(
                            f'  [BOOKING]  {field:20s}: local={lv} | api={av}'
                        )

                # ══════════════════════════════════════════════
                # C — PAYMENTS: presence + amount + mode
                # ══════════════════════════════════════════════
                local_pay_map = {int(p.payment_id): p for p in booking.payments.all()}
                api_pay_map   = {int(p['id']): p for p in api_payments if p.get('id')}

                # In API but missing locally
                for pid, ap in api_pay_map.items():
                    if pid not in local_pay_map:
                        issues.append(
                            f'  [PAYMENT]  MISSING LOCALLY : id={pid}'
                            f' amount={ap.get("amount")} mode={ap.get("mode")}'
                        )
                    else:
                        lp = local_pay_map[pid]
                        if round(float(lp.amount or 0), 2) != round(float(ap.get('amount') or 0), 2):
                            issues.append(
                                f'  [PAYMENT]  AMOUNT MISMATCH : id={pid}'
                                f' local={lp.amount} | api={ap.get("amount")}'
                            )
                        if (lp.mode or '').strip() != (ap.get('mode') or '').strip():
                            issues.append(
                                f'  [PAYMENT]  MODE MISMATCH   : id={pid}'
                                f' local={lp.mode} | api={ap.get("mode")}'
                            )

                # Locally but not in API
                for pid in local_pay_map:
                    if pid not in api_pay_map:
                        lp = local_pay_map[pid]
                        issues.append(
                            f'  [PAYMENT]  EXTRA LOCALLY   : id={pid}'
                            f' amount={lp.amount} mode={lp.mode}'
                        )

            except Exception:
                # No booking locally but API has one
                if api_booking.get('id'):
                    issues.append(
                        f'  [BOOKING]  MISSING LOCALLY : api_booking_id={api_booking.get("id")}'
                        f' total={api_booking.get("total_amount")}'
                    )

            # ── Collect ───────────────────────────────────────
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