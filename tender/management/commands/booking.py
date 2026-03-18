# management/commands/sync_bookings_payments.py

import requests
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime
from tender.models import Job, JobBooking, FarmerPayment

BOOKED_VISITS_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'

STATUS_MAP = {
    'PAID':    'PAID',
    'PARTIAL': 'PARTIALLY_PAID',
    'PENDING': 'UNPAID',
}


class Command(BaseCommand):
    help = 'Sync JobBooking and FarmerPayment from API'

    def add_arguments(self, parser):
        parser.add_argument('--ops-token', type=str, required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        headers = {'Authorization': f'Token {options["ops_token"]}'}
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN — nothing will be saved\n'))

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
                    # key by item['id'] which IS the job_id
                    api_by_job[str(item['id'])] = item
                    # also key by any merged job ids if present
                    for jid in (item.get('_merged_job_ids') or []):
                        api_by_job[str(jid)] = item

                self.stdout.write(f'  Page {page}: {len(results)} records')
                if not (data.get('next') or data.get('has_next')):
                    break
                page += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Page {page}: {e}')); break

        self.stdout.write(self.style.SUCCESS(f'✅ {len(api_by_job)} jobs fetched\n'))

        # ── Counters ──────────────────────────────────────────────────
        booking_updated = 0
        booking_created = 0
        jobs_skipped    = 0
        skipped_job_ids = []

        local_jobs = Job.objects.prefetch_related('booking').all()

        for job in local_jobs:
            api = api_by_job.get(str(job.job_id))
            if not api:
                jobs_skipped += 1
                skipped_job_ids.append(str(job.job_id))
                continue

            # ── API shape: job object directly, no nested booking ──
            # id          = job_id  (this IS the booking reference)
            # status      = PENDING / PAID / PARTIAL
            # total_activities_amount = total amount
            # No advance_paid / balance / payments in this API

            api_book_id = int(api['id'])
            api_status  = STATUS_MAP.get((api.get('status') or '').upper(), 'UNPAID')
            api_total   = round(float(api.get('total_activities_amount') or 0), 2)

            # payments not in this API — skip payment sync
            # if your API has a booking sub-object on some records, handle here:
            api_booking_obj = api.get('booking') or {}
            api_advance = round(float(api_booking_obj.get('advance_paid') or 0), 2)
            api_balance = round(float(api_booking_obj.get('balance')      or 0), 2)
            api_assignee = api_booking_obj.get('assignee_number') or ''

            with transaction.atomic():
                try:
                    booking = job.booking
                    booking_fields = []

                    if round(float(booking.total_amount or 0), 2) != api_total:
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} total_amount: {booking.total_amount} → {api_total}')
                        booking.total_amount = api_total
                        booking_fields.append('total_amount')

                    if booking.status != api_status:
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} status: {booking.status} → {api_status}')
                        booking.status = api_status
                        booking_fields.append('status')

                    if api_advance and round(float(booking.advance_paid or 0), 2) != api_advance:
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} advance_paid: {booking.advance_paid} → {api_advance}')
                        booking.advance_paid = api_advance
                        booking_fields.append('advance_paid')

                    if api_balance and round(float(booking.balance or 0), 2) != api_balance:
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} balance: {booking.balance} → {api_balance}')
                        booking.balance = api_balance
                        booking_fields.append('balance')

                    if booking_fields:
                        if not dry_run:
                            booking.save(update_fields=booking_fields)
                        booking_updated += 1

                except JobBooking.DoesNotExist:
                    self.stdout.write(f'  [BOOKING] Job {job.job_id} — CREATE booking_id={api_book_id} total={api_total} status={api_status}')
                    if not dry_run:
                        JobBooking.objects.create(
                            job          = job,
                            booking_id   = api_book_id,
                            total_amount = api_total,
                            advance_paid = api_advance,
                            balance      = api_balance,
                            status       = api_status,
                            assignee_number = api_assignee,
                        )
                    booking_created += 1

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write('\n' + '=' * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes saved'))
        self.stdout.write(self.style.SUCCESS(f'Bookings updated : {booking_updated}'))
        self.stdout.write(self.style.SUCCESS(f'Bookings created : {booking_created}'))
        self.stdout.write(                   f'Jobs not in API  : {jobs_skipped}')

        if skipped_job_ids:
            self.stdout.write(self.style.WARNING(f'\nJob IDs not found in API ({len(skipped_job_ids)}):'))
            for i in range(0, len(skipped_job_ids), 10):
                self.stdout.write('  ' + ', '.join(skipped_job_ids[i:i+10]))

        self.stdout.write('=' * 50)