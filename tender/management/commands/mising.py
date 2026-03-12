# management/commands/sync_bookings_payments.py
# Run: python manage.py sync_bookings_payments --ops-token YOUR_TOKEN
# Dry run: python manage.py sync_bookings_payments --ops-token YOUR_TOKEN --dry-run

import requests
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from tender.models import Job, JobBooking, FarmerPayment  # ← change app name if needed

BOOKED_VISITS_URL = 'https://ops.bharatintelligence.ai/ops/allocation_booked_visits/'

STATUS_MAP = {
    'PAID':    'PAID',
    'PARTIAL': 'PARTIALLY_PAID',
    'PENDING': 'UNPAID',
}


class Command(BaseCommand):
    help = 'Sync JobBooking and FarmerPayment from API — update wrong, create missing, delete extra'

    def add_arguments(self, parser):
        parser.add_argument('--ops-token', type=str, required=True)
        parser.add_argument('--dry-run',   action='store_true')

    def handle(self, *args, **options):
        headers = {'Authorization': f'Token {options["ops_token"]}'}
        dry_run  = options['dry_run']

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

        # ── Counters ──────────────────────────────────────────────────
        booking_updated = 0
        booking_created = 0
        payment_updated = 0
        payment_created = 0
        payment_deleted = 0
        jobs_skipped    = 0

        local_jobs = Job.objects.prefetch_related('booking__payments').all()

        for job in local_jobs:
            api = api_by_job.get(str(job.job_id))
            if not api:
                jobs_skipped += 1
                continue

            api_booking  = api.get('booking') or {}
            api_payments = api_booking.get('payments') or []

            if not api_booking.get('id'):
                continue

            with transaction.atomic():

                # ══════════════════════════════════════════════
                # BOOKING — update or create
                # ══════════════════════════════════════════════
                api_total    = Decimal(str(api_booking.get('total_amount') or 0))
                api_advance  = Decimal(str(api_booking.get('advance_paid') or 0))
                api_balance  = Decimal(str(api_booking.get('balance')      or 0))
                api_status   = STATUS_MAP.get(api_booking.get('status', '').upper(), 'UNPAID')
                api_assignee = api_booking.get('assignee_number') or ''
                api_book_id  = int(api_booking['id'])

                try:
                    booking = job.booking
                    booking_fields = []

                    if Decimal(str(booking.total_amount or 0)).quantize(Decimal('0.01')) != api_total.quantize(Decimal('0.01')):
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} total_amount: {booking.total_amount} → {api_total}')
                        booking.total_amount = api_total
                        booking_fields.append('total_amount')

                    if Decimal(str(booking.advance_paid or 0)).quantize(Decimal('0.01')) != api_advance.quantize(Decimal('0.01')):
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} advance_paid: {booking.advance_paid} → {api_advance}')
                        booking.advance_paid = api_advance
                        booking_fields.append('advance_paid')

                    if Decimal(str(booking.balance or 0)).quantize(Decimal('0.01')) != api_balance.quantize(Decimal('0.01')):
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} balance: {booking.balance} → {api_balance}')
                        booking.balance = api_balance
                        booking_fields.append('balance')

                    if booking.status != api_status:
                        self.stdout.write(f'  [BOOKING] Job {job.job_id} status: {booking.status} → {api_status}')
                        booking.status = api_status
                        booking_fields.append('status')

                    if booking_fields:
                        if not dry_run:
                            booking.save(update_fields=booking_fields)
                        booking_updated += 1

                except JobBooking.DoesNotExist:
                    self.stdout.write(f'  [BOOKING] Job {job.job_id} — CREATE booking id={api_book_id} total={api_total}')
                    if not dry_run:
                        booking = JobBooking.objects.create(
                            job             = job,
                            booking_id      = api_book_id,
                            total_amount    = api_total,
                            advance_paid    = api_advance,
                            balance         = api_balance,
                            status          = api_status,
                            assignee_number = api_assignee,
                        )
                    else:
                        booking = JobBooking(
                            job             = job,
                            booking_id      = api_book_id,
                            total_amount    = api_total,
                            advance_paid    = api_advance,
                            balance         = api_balance,
                            status          = api_status,
                            assignee_number = api_assignee,
                        )
                    booking_created += 1

                # ══════════════════════════════════════════════
                # PAYMENTS — update wrong, create missing, delete extra
                # ══════════════════════════════════════════════
                if dry_run or booking.pk:
                    local_pay_qs  = FarmerPayment.objects.filter(booking=booking) if booking.pk else FarmerPayment.objects.none()
                    local_pay_map = {int(p.payment_id): p for p in local_pay_qs}
                    api_pay_map   = {int(p['id']): p for p in api_payments if p.get('id')}

                    # Update or create
                    for pid, ap in api_pay_map.items():
                        api_amount     = Decimal(str(ap.get('amount') or 0))
                        api_mode       = (ap.get('mode') or 'CASH').strip()
                        api_paid_at    = parse_datetime(ap['paid_at']) if ap.get('paid_at') else timezone.now()
                        api_notes      = ap.get('notes') or ''
                        api_paid_status = ap.get('paid_status', True)

                        if pid in local_pay_map:
                            lp = local_pay_map[pid]
                            pay_fields = []

                            if Decimal(str(lp.amount or 0)).quantize(Decimal('0.01')) != api_amount.quantize(Decimal('0.01')):
                                self.stdout.write(f'    [PAYMENT] id={pid} amount: {lp.amount} → {api_amount}')
                                lp.amount = api_amount
                                pay_fields.append('amount')

                            if (lp.mode or '').strip() != api_mode:
                                self.stdout.write(f'    [PAYMENT] id={pid} mode: {lp.mode} → {api_mode}')
                                lp.mode = api_mode
                                pay_fields.append('mode')

                            # ← NEW: sync paid_status
                            if lp.paid_status != api_paid_status:
                                self.stdout.write(f'    [PAYMENT] id={pid} paid_status: {lp.paid_status} → {api_paid_status}')
                                lp.paid_status = api_paid_status
                                pay_fields.append('paid_status')

                            if pay_fields:
                                if not dry_run:
                                    lp.save(update_fields=pay_fields)
                                payment_updated += 1

                        else:
                            self.stdout.write(
                                f'    [PAYMENT] CREATE id={pid} amount={api_amount} mode={api_mode} paid_status={api_paid_status}'
                            )
                            if not dry_run:
                                FarmerPayment.objects.create(
                                    booking     = booking,
                                    payment_id  = pid,
                                    amount      = api_amount,
                                    mode        = api_mode,
                                    notes       = api_notes,
                                    paid_at     = api_paid_at,
                                    paid_status = api_paid_status,
                                )
                            payment_created += 1

                    # Delete extra local payments not in API
                    for pid in list(local_pay_map.keys()):
                        if pid not in api_pay_map:
                            lp = local_pay_map[pid]
                            self.stdout.write(
                                f'    [PAYMENT] DELETE id={pid} amount={lp.amount} mode={lp.mode}'
                            )
                            if not dry_run:
                                lp.delete()
                            payment_deleted += 1

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write('\n' + '=' * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes saved'))
        self.stdout.write(self.style.SUCCESS(f'Bookings updated : {booking_updated}'))
        self.stdout.write(self.style.SUCCESS(f'Bookings created : {booking_created}'))
        self.stdout.write(self.style.SUCCESS(f'Payments updated : {payment_updated}'))
        self.stdout.write(self.style.SUCCESS(f'Payments created : {payment_created}'))
        self.stdout.write(self.style.SUCCESS(f'Payments deleted : {payment_deleted}'))
        self.stdout.write(                   f'Jobs not in API  : {jobs_skipped}')
        self.stdout.write('=' * 50)