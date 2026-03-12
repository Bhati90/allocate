# management/commands/verify_all_data.py
# Run: python manage.py verify_all_data --token YOUR_TOKEN_HERE

import requests
from django.core.management.base import BaseCommand
from tender.models import (  # ← change to your app name
    Job, JobActivity, JobBooking, FarmerPayment, Plot, Farmer
)

BOOKED_VISITS_URL  = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'
FARMER_DETAILS_URL = 'https://demand.bharatintelligence.ai/fir/api/get_farmer_details/{}/'


class Command(BaseCommand):
    help = 'Verify all local data against external APIs and report mismatches'

    def add_arguments(self, parser):
        parser.add_argument('--ops-token',    type=str, required=True, help='Token for ops.bharatintelligence.ai')
        parser.add_argument('--demand-token', type=str, required=True, help='Token for demand.bharatintelligence.ai')
        parser.add_argument('--output',       type=str, default='verify_mismatches.txt')

    def handle(self, *args, **options):
        ops_headers    = {'Authorization': f'Token {options["ops_token"]}'}
        outfile = options['output']
        demand_headers = {'Authorization': f'Token {options["demand_token"]}'}

        # ══════════════════════════════════════════════════════
        # STEP 1 — Fetch all booked visits from API
        # ══════════════════════════════════════════════════════
        self.stdout.write(self.style.NOTICE('\n📡 Fetching booked visits from API...'))
        api_visits = {}   # keyed by booking_id
        api_by_job = {}   # keyed by job id (from _merged_job_ids)
        page = 1

        while True:
            try:
                res = requests.get(BOOKED_VISITS_URL, params={'page': page}, timeout=15, headers=ops_headers)
                if res.status_code == 401:
                    self.stdout.write(self.style.ERROR('❌ Unauthorized')); return
                if res.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'❌ HTTP {res.status_code}')); break

                data    = res.json()
                results = data.get('data') or data.get('results') or []
                if not results:
                    break

                for item in results:
                    booking = item.get('booking') or {}
                    bid     = booking.get('id')
                    if bid:
                        api_visits[str(bid)] = item
                    # also index by each merged job id
                    for jid in (item.get('_merged_job_ids') or []):
                        api_by_job[str(jid)] = item
                    # index by top-level id too
                    api_by_job[str(item.get('id'))] = item

                self.stdout.write(f'  Page {page}: {len(results)} records')
                if not (data.get('next') or data.get('has_next')):
                    break
                page += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error page {page}: {e}')); break

        self.stdout.write(self.style.SUCCESS(f'✅ Fetched {len(api_visits)} visits from API'))

        # ══════════════════════════════════════════════════════
        # STEP 2 — Fetch farmer details cache
        # ══════════════════════════════════════════════════════
        farmer_api_cache = {}  # farmer_id → api farmer data

        def get_farmer_api(farmer_id):
            fid = str(farmer_id)
            if fid not in farmer_api_cache:
                try:
                    r = requests.get(FARMER_DETAILS_URL.format(fid), timeout=10, headers=demand_headers)
                    farmer_api_cache[fid] = r.json() if r.status_code == 200 else None
                except Exception:
                    farmer_api_cache[fid] = None
            return farmer_api_cache[fid]

        # ══════════════════════════════════════════════════════
        # STEP 3 — Compare every local Job
        # ══════════════════════════════════════════════════════
        self.stdout.write(self.style.NOTICE('\n🔍 Comparing local Jobs against API...'))

        all_issues  = []   # list of {job_id, issues[]}
        jobs_ok     = 0

        local_jobs = Job.objects.select_related('farmer', 'plot').prefetch_related('activities').all()
        self.stdout.write(f'Local jobs to check: {local_jobs.count()}')

        for job in local_jobs:
            issues = []

            # ── Find matching API record ───────────────────────
            api = api_by_job.get(str(job.job_id))
            if not api:
                issues.append({
                    'section': 'JOB',
                    'field':   'job_id',
                    'local':   job.job_id,
                    'api':     'NOT FOUND IN API',
                })
                all_issues.append({'job_id': job.job_id, 'farmer': str(job.farmer), 'issues': issues})
                continue

            api_book       = api.get('booking') or {}
            api_activities = api.get('activities') or []
            api_payments   = api_book.get('payments') or []

            # ══════════════════════════════════════════════════
            # A — FARMER comparison
            # ══════════════════════════════════════════════════
            farmer_api = get_farmer_api(job.farmer.farmer_id)
            if farmer_api:
                checks = [
                    ('farmer_name',   job.farmer.farmer_name,   farmer_api.get('farmer_name')),
                    ('phone_number',  job.farmer.phone_number,  farmer_api.get('phone_number')),
                ]
                for field, local_val, api_val in checks:
                    if str(local_val or '').strip() != str(api_val or '').strip():
                        issues.append({
                            'section': 'FARMER',
                            'field':   field,
                            'local':   local_val,
                            'api':     api_val,
                        })

                # ── PLOT comparison ────────────────────────────
                api_plots = {str(p['plot_id']): p for p in (farmer_api.get('plots') or [])}
                local_plots = Plot.objects.filter(farmer=job.farmer)

                for lplot in local_plots:
                    pc = str(lplot.plot_code or lplot.id)
                    ap = api_plots.get(pc)
                    if not ap:
                        issues.append({
                            'section': 'PLOT',
                            'field':   'plot_id',
                            'local':   pc,
                            'api':     'NOT FOUND IN API',
                        })
                        continue
                    plot_checks = [
                        ('area_acres', float(lplot.area_acres or 0),   float(ap.get('acre') or 0)),
                        ('crop_name',  (lplot.crop_name or '').strip(), (ap.get('crop') or '').strip()),
                        ('variety',    (lplot.variety or '').strip(),   (ap.get('variety') or '').strip()),
                    ]
                    for field, lv, av in plot_checks:
                        if lv != av:
                            issues.append({
                                'section': f'PLOT {pc}',
                                'field':   field,
                                'local':   lv,
                                'api':     av,
                            })

            # ══════════════════════════════════════════════════
            # B — JOB comparison
            # ══════════════════════════════════════════════════
            job_checks = [
                ('farmer_id',              str(job.farmer.farmer_id),         str(api.get('farmer_id') or '')),
                ('total_activities_amount', round(float(job.total_activities_amount or 0), 2),
                                            round(float(api.get('total_activities_amount') or 0), 2)),
            ]
            for field, lv, av in job_checks:
                if str(lv) != str(av):
                    issues.append({'section': 'JOB', 'field': field, 'local': lv, 'api': av})

            # ══════════════════════════════════════════════════
            # C — JOB BOOKING comparison
            # ══════════════════════════════════════════════════
            try:
                booking = job.booking
                booking_checks = [
                    ('booking_id',   int(booking.booking_id),                    int(api_book.get('id') or 0)),
                    ('total_amount', round(float(booking.total_amount or 0), 2), round(float(api_book.get('total_amount') or 0), 2)),
                    ('advance_paid', round(float(booking.advance_paid or 0), 2), round(float(api_book.get('advance_paid') or 0), 2)),
                    ('balance',      round(float(booking.balance or 0), 2),      round(float(api_book.get('balance') or 0), 2)),
                ]
                for field, lv, av in booking_checks:
                    if lv != av:
                        issues.append({'section': 'BOOKING', 'field': field, 'local': lv, 'api': av})

                # ══════════════════════════════════════════════
                # D — FARMER PAYMENT comparison
                # ══════════════════════════════════════════════
                local_payments  = FarmerPayment.objects.filter(booking=booking)
                local_pay_map   = {int(p.payment_id): p for p in local_payments}
                api_pay_map     = {int(p['id']): p for p in api_payments if p.get('id')}

                # Payments in API but not locally
                for pid, ap in api_pay_map.items():
                    if pid not in local_pay_map:
                        issues.append({
                            'section': 'PAYMENT',
                            'field':   'payment_id',
                            'local':   'MISSING',
                            'api':     f"id={pid} amount={ap.get('amount')} mode={ap.get('mode')}",
                        })
                    else:
                        lp = local_pay_map[pid]
                        pay_checks = [
                            ('amount', round(float(lp.amount or 0), 2), round(float(ap.get('amount') or 0), 2)),
                            ('mode',   (lp.mode or '').strip(),          (ap.get('mode') or '').strip()),
                        ]
                        for field, lv, av in pay_checks:
                            if lv != av:
                                issues.append({
                                    'section': f'PAYMENT id={pid}',
                                    'field':   field,
                                    'local':   lv,
                                    'api':     av,
                                })

                # Payments locally but not in API
                for pid in local_pay_map:
                    if pid not in api_pay_map:
                        lp = local_pay_map[pid]
                        issues.append({
                            'section': 'PAYMENT',
                            'field':   'payment_id',
                            'local':   f"id={pid} amount={lp.amount} mode={lp.mode}",
                            'api':     'NOT IN API',
                        })

            except JobBooking.DoesNotExist:
                if api_book.get('id'):
                    issues.append({
                        'section': 'BOOKING',
                        'field':   'booking',
                        'local':   'NO BOOKING IN DB',
                        'api':     f"id={api_book.get('id')}",
                    })

            # ══════════════════════════════════════════════════
            # E — JOB ACTIVITY comparison
            # ══════════════════════════════════════════════════
            local_acts   = list(job.activities.select_related('activity').all())
            local_act_map = {}
            for la in local_acts:
                key = str(la.api_activity_id or la.id)
                local_act_map[key] = la

            api_act_map = {}
            for aa in api_activities:
                key = str(aa.get('id') or '')
                api_act_map[key] = aa

            # Activities in API but not locally
            for aid, aa in api_act_map.items():
                if aid not in local_act_map:
                    issues.append({
                        'section': 'ACTIVITY',
                        'field':   'activity_id',
                        'local':   'MISSING',
                        'api':     f"id={aid} name={aa.get('activity_name')}",
                    })
                else:
                    la = local_act_map[aid]
                    act_checks = [
                        ('activity_name', la.activity.name.strip(),              (aa.get('activity_name') or '').strip()),
                        ('acres',         round(float(la.total_area or 0), 2),   round(float(aa.get('acres') or 0), 2)),
                        ('total_price',   round(float(la.total_price or 0), 2),  round(float(aa.get('total_price') or 0), 2)),
                        ('transport_cost',round(float(la.transport_cost or 0),2),round(float(aa.get('transport_cost') or 0), 2)),
                        ('subtotal',      round(float(la.subtotal or 0), 2),     round(float(aa.get('subtotal') or 0), 2)),
                    ]
                    for field, lv, av in act_checks:
                        if lv != av:
                            issues.append({
                                'section': f'ACTIVITY id={aid} ({la.activity.name})',
                                'field':   field,
                                'local':   lv,
                                'api':     av,
                            })

            # Activities locally but not in API
            for aid in local_act_map:
                if aid not in api_act_map:
                    la = local_act_map[aid]
                    issues.append({
                        'section': 'ACTIVITY',
                        'field':   'activity_id',
                        'local':   f"id={aid} name={la.activity.name}",
                        'api':     'NOT IN API',
                    })

            # ── Collect ────────────────────────────────────────
            if issues:
                all_issues.append({
                    'job_id':  job.job_id,
                    'farmer':  str(job.farmer),
                    'issues':  issues,
                })
            else:
                jobs_ok += 1

        # ══════════════════════════════════════════════════════
        # STEP 4 — Print results
        # ══════════════════════════════════════════════════════
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Jobs fully matched  : {jobs_ok}'))
        self.stdout.write(self.style.ERROR(  f'❌ Jobs with issues    : {len(all_issues)}'))
        self.stdout.write('='*60)

        problem_job_ids = []

        for entry in all_issues:
            problem_job_ids.append(entry['job_id'])
            self.stdout.write(
                f"\n  Job ID : {entry['job_id']} | {entry['farmer']}"
            )
            for iss in entry['issues']:
                self.stdout.write(f"    ├─ [{iss['section']}] {iss['field']}")
                self.stdout.write(f"    │    LOCAL : {iss['local']}")
                self.stdout.write(f"    │    API   : {iss['api']}")

        self.stdout.write('\n── Problem Job IDs (copy-paste) ──')
        self.stdout.write(str(problem_job_ids))

        # ══════════════════════════════════════════════════════
        # STEP 5 — Save to file
        # ══════════════════════════════════════════════════════
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(f'Jobs OK      : {jobs_ok}\n')
            f.write(f'Jobs Issues  : {len(all_issues)}\n')
            f.write('='*60 + '\n')
            for entry in all_issues:
                f.write(f"\nJob ID: {entry['job_id']} | {entry['farmer']}\n")
                for iss in entry['issues']:
                    f.write(f"  [{iss['section']}] {iss['field']}\n")
                    f.write(f"    LOCAL : {iss['local']}\n")
                    f.write(f"    API   : {iss['api']}\n")
            f.write(f'\nProblem Job IDs: {problem_job_ids}\n')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Results saved to: {outfile}'))