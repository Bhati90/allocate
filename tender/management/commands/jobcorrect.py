# management/commands/fix_job_amounts.py
# Run: python manage.py fix_job_amounts --ops-token YOUR_OPS_TOKEN

import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from tender.models import Job, JobActivity  # ← change app name if needed

BOOKED_VISITS_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'


class Command(BaseCommand):
    help = 'Fix job scheduled_date, total_activities_amount and booking_amount from API'

    def add_arguments(self, parser):
        parser.add_argument('--ops-token', type=str, required=True)
        parser.add_argument('--dry-run',   action='store_true', help='Print changes without saving')

    def handle(self, *args, **options):
        headers = {'Authorization': f'Token {options["ops_token"]}'}
        dry_run = options['dry_run']

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
                    # Index by merged job ids + top-level id
                    for jid in (item.get('_merged_job_ids') or []):
                        api_by_job[str(jid)] = item
                    api_by_job[str(item.get('id'))] = item

                self.stdout.write(f'  Page {page}: {len(results)} records')
                if not (data.get('next') or data.get('has_next')):
                    break
                page += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Page {page} error: {e}')); break

        self.stdout.write(self.style.SUCCESS(f'✅ Fetched {len(api_by_job)} job entries'))

        # ── Process each local job ────────────────────────────────────
        jobs = Job.objects.all()
        self.stdout.write(f'\n🔍 Processing {jobs.count()} local jobs...\n')

        updated   = 0
        skipped   = 0
        not_found = 0

        for job in jobs:
            api = api_by_job.get(str(job.job_id))
            if not api:
                not_found += 1
                continue

            api_activities = api.get('activities') or []
            api_booking    = api.get('booking') or {}
            changed_fields = []

            # ── 1. scheduled_date — from activity date_time ───────────
            # Take the earliest activity date_time as the job scheduled date
            new_scheduled_date = None
            for act in api_activities:
                dt_str = act.get('date_time')
                if dt_str:
                    try:
                        dt = parse_datetime(dt_str)
                        if dt:
                            act_date = dt.date()
                            if new_scheduled_date is None or act_date < new_scheduled_date:
                                new_scheduled_date = act_date
                    except Exception:
                        pass

            if new_scheduled_date and job.scheduled_date != new_scheduled_date:
                changed_fields.append(
                    f'  scheduled_date : {job.scheduled_date} → {new_scheduled_date}'
                )
                job.scheduled_date = new_scheduled_date

            # ── 2. total_activities_amount — from api top-level ───────
            api_total = api.get('total_activities_amount')
            if api_total is not None:
                from decimal import Decimal
                api_total_dec = Decimal(str(api_total))
                if job.total_activities_amount != api_total_dec:
                    changed_fields.append(
                        f'  total_activities_amount : {job.total_activities_amount} → {api_total_dec}'
                    )
                    job.total_activities_amount = api_total_dec

            # ── 3. booking_amount — from booking.total_amount ─────────
            api_booking_amount = api_booking.get('total_amount')
            if api_booking_amount is not None:
                from decimal import Decimal
                api_booking_dec = Decimal(str(api_booking_amount))
                if job.booking_amount != api_booking_dec:
                    changed_fields.append(
                        f'  booking_amount : {job.booking_amount} → {api_booking_dec}'
                    )
                    job.booking_amount = api_booking_dec

            # ── Save / report ─────────────────────────────────────────
            if changed_fields:
                self.stdout.write(f'Job {job.job_id} ({job.farmer.farmer_name}):')
                for line in changed_fields:
                    self.stdout.write(line)

                if not dry_run:
                    job.save(update_fields=[
                        'scheduled_date',
                        'total_activities_amount',
                        'booking_amount',
                    ])
                updated += 1
            else:
                skipped += 1

        # ── Also fix JobActivity scheduled_date per activity ─────────
        self.stdout.write('\n🔍 Fixing JobActivity scheduled dates...\n')

        act_updated   = 0
        act_not_found = 0

        for job in Job.objects.prefetch_related('activities__activity').all():
            api = api_by_job.get(str(job.job_id))
            if not api:
                continue

            api_activities = api.get('activities') or []
            # Build map: activity_name → date_time
            api_act_date_map = {}
            for aa in api_activities:
                name    = (aa.get('activity_name') or '').strip()
                dt_str  = aa.get('date_time')
                api_id  = str(aa.get('id') or '')
                if dt_str:
                    try:
                        dt = parse_datetime(dt_str)
                        if dt:
                            api_act_date_map[api_id]  = dt.date()
                            api_act_date_map[name]     = dt.date()  # fallback by name
                    except Exception:
                        pass

            for local_act in job.activities.all():
                api_id_key   = str(local_act.api_activity_id or '')
                name_key     = (local_act.activity.name if local_act.activity else '').strip()

                new_date = api_act_date_map.get(api_id_key) or api_act_date_map.get(name_key)
                if not new_date:
                    act_not_found += 1
                    continue

                if local_act.scheduled_date != new_date:
                    self.stdout.write(
                        f'  Activity {local_act.id} ({name_key}): '
                        f'{local_act.scheduled_date} → {new_date}'
                    )
                    local_act.scheduled_date = new_date
                    if not dry_run:
                        local_act.save(update_fields=['scheduled_date'])
                    act_updated += 1

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write('\n' + '=' * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes saved'))
        self.stdout.write(self.style.SUCCESS(f'Jobs updated        : {updated}'))
        self.stdout.write(                   f'Jobs unchanged      : {skipped}')
        self.stdout.write(                   f'Jobs not in API     : {not_found}')
        self.stdout.write(self.style.SUCCESS(f'Activities updated  : {act_updated}'))
        self.stdout.write(                   f'Activities no match : {act_not_found}')
        self.stdout.write('=' * 50)