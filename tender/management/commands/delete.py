# management/commands/delete_missing_jobs.py
# Run: python manage.py delete_missing_jobs --input missing_from_tendered.txt
# Dry run first: python manage.py delete_missing_jobs --input missing_from_tendered.txt --dry-run

import json
from django.core.management.base import BaseCommand
from django.db import transaction
from tender.models import (  # ← change 'tender' to your app name
    Job, JobActivity, JobBooking, FarmerPayment,
    Allocation, Plot, Farmer, FarmerBillWebhookLog,
    WebhookLog, ActivityLogTender, AllocationChangeLogTender,
    MukkadamJobSettlement, MukkadamMiscCost, MukkadamPayment,
    JobNote,
)


class Command(BaseCommand):
    help = 'Delete jobs and all related data for job IDs not in TenderedJob'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Path to missing_from_tendered.txt (one job_id per line, or raw list)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--delete-farmers',
            action='store_true',
            help='Also delete Farmer if they have NO other jobs after deletion',
        )

    def handle(self, *args, **options):
        infile      = options['input']
        dry_run     = options['dry_run']
        del_farmers = options['delete_farmers']

        # ── 1. Load job IDs from file ─────────────────────────
        job_ids = []
        with open(infile, 'r') as f:
            content = f.read().strip()

        # Handle both formats:
        # Format 1: raw Python list  ['866', '875', ...]
        # Format 2: one ID per line
        if content.startswith('['):
            try:
                job_ids = [str(jid) for jid in json.loads(content.replace("'", '"'))]
            except Exception:
                # Try ast.literal_eval as fallback
                import ast
                job_ids = [str(jid) for jid in ast.literal_eval(content)]
        else:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('=') \
                        and not line.startswith('Missing') and not line.startswith('Raw'):
                    job_ids.append(line)

        job_ids = list(set(job_ids))  # deduplicate
        self.stdout.write(self.style.NOTICE(f'\nLoaded {len(job_ids)} job IDs to delete'))

        if not job_ids:
            self.stdout.write(self.style.ERROR('No job IDs found in file. Exiting.'))
            return

        # ── 2. Find jobs that actually exist in DB ────────────
        existing_jobs = Job.objects.filter(job_id__in=job_ids).select_related('farmer')
        existing_ids  = [j.job_id for j in existing_jobs]
        missing_ids   = [jid for jid in job_ids if jid not in existing_ids]

        self.stdout.write(f'Found in DB        : {len(existing_ids)}')
        self.stdout.write(f'Not found in DB    : {len(missing_ids)} (already deleted or never existed)')

        if missing_ids:
            self.stdout.write(f'  Not found IDs: {missing_ids}')

        if not existing_jobs:
            self.stdout.write(self.style.SUCCESS('\nNothing to delete.'))
            return

        # ── 3. Count related records ──────────────────────────
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.NOTICE('RECORDS TO BE DELETED:'))
        self.stdout.write('='*60)

        total_counts = {
            'jobs':                 0,
            'job_activities':       0,
            'allocations':          0,
            'job_bookings':         0,
            'farmer_payments':      0,
            'job_notes':            0,
            'webhook_logs':         0,
            'activity_logs':        0,
            'allocation_logs':      0,
            'mukkadam_settlements': 0,
            'mukkadam_misc_costs':  0,
            'farmer_bill_logs':     0,
        }

        farmer_ids_affected = set()

        for job in existing_jobs:
            farmer_ids_affected.add(job.farmer.farmer_id)

            activities    = JobActivity.objects.filter(job=job)
            activity_ids  = list(activities.values_list('id', flat=True))
            allocations   = Allocation.objects.filter(job_activity__in=activity_ids)

            try:
                booking         = job.booking
                booking_exists  = True
                payment_count   = FarmerPayment.objects.filter(booking=booking).count()
            except JobBooking.DoesNotExist:
                booking_exists  = False
                payment_count   = 0

            act_log_count    = ActivityLogTender.objects.filter(job=job).count()
            alloc_log_count  = AllocationChangeLogTender.objects.filter(
                allocation__job_activity__job=job
            ).count()
            settlement_count = MukkadamJobSettlement.objects.filter(job=job).count()
            misc_count       = MukkadamMiscCost.objects.filter(job=job).count()
            note_count       = JobNote.objects.filter(job=job).count()
            webhook_count    = WebhookLog.objects.filter(job_id=str(job.job_id)).count()
            bill_log_count   = FarmerBillWebhookLog.objects.filter(
                job_id=str(job.job_id)
            ).count()

            self.stdout.write(
                f'\n  Job {job.job_id} | Farmer: {job.farmer.farmer_name} ({job.farmer.farmer_id})'
            )
            self.stdout.write(f'    Activities        : {activities.count()}')
            self.stdout.write(f'    Allocations       : {allocations.count()}')
            self.stdout.write(f'    Booking           : {"Yes" if booking_exists else "No"}')
            self.stdout.write(f'    Farmer Payments   : {payment_count}')
            self.stdout.write(f'    Job Notes         : {note_count}')
            self.stdout.write(f'    Settlements       : {settlement_count}')
            self.stdout.write(f'    Misc Costs        : {misc_count}')
            self.stdout.write(f'    Webhook Logs      : {webhook_count}')
            self.stdout.write(f'    Activity Logs     : {act_log_count}')
            self.stdout.write(f'    Allocation Logs   : {alloc_log_count}')
            self.stdout.write(f'    Bill Webhook Logs : {bill_log_count}')

            total_counts['jobs']                 += 1
            total_counts['job_activities']       += activities.count()
            total_counts['allocations']          += allocations.count()
            total_counts['job_bookings']         += 1 if booking_exists else 0
            total_counts['farmer_payments']      += payment_count
            total_counts['job_notes']            += note_count
            total_counts['mukkadam_settlements'] += settlement_count
            total_counts['mukkadam_misc_costs']  += misc_count
            total_counts['webhook_logs']         += webhook_count
            total_counts['activity_logs']        += act_log_count
            total_counts['allocation_logs']      += alloc_log_count
            total_counts['farmer_bill_logs']     += bill_log_count

        # ── Farmer deletion check ─────────────────────────────
        farmers_to_delete = []
        if del_farmers:
            for fid in farmer_ids_affected:
                farmer = Farmer.objects.get(farmer_id=fid)
                remaining = Job.objects.filter(farmer=farmer).exclude(
                    job_id__in=existing_ids
                ).count()
                if remaining == 0:
                    farmers_to_delete.append(farmer)

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('TOTALS:'))
        for key, val in total_counts.items():
            self.stdout.write(f'  {key:<25} : {val}')
        if del_farmers:
            self.stdout.write(
                f'  {"farmers_to_delete":<25} : {len(farmers_to_delete)}'
            )
            for f in farmers_to_delete:
                self.stdout.write(f'    → {f.farmer_name} ({f.farmer_id})')
        self.stdout.write('='*60)

        # ── 4. Dry run or real delete ─────────────────────────
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    '\n💡 DRY RUN — nothing deleted. Remove --dry-run to actually delete.'
                )
            )
            return

        # ── Confirm before deleting ───────────────────────────
        confirm = input(
            f'\n⚠️  About to delete {total_counts["jobs"]} jobs and all related data. '
            f'Type YES to confirm: '
        )
        if confirm.strip() != 'YES':
            self.stdout.write(self.style.ERROR('Aborted.'))
            return

        # ── 5. Delete inside a transaction ───────────────────
        self.stdout.write(self.style.NOTICE('\nDeleting...'))

        with transaction.atomic():
            for job in existing_jobs:
                try:
                    # Delete in correct FK order
                    # 1. Allocation change logs
                    AllocationChangeLogTender.objects.filter(
                        allocation__job_activity__job=job
                    ).delete()

                    # 2. Allocations
                    Allocation.objects.filter(job_activity__job=job).delete()

                    # 3. Activity logs
                    ActivityLogTender.objects.filter(job=job).delete()

                    # 4. Job activities
                    JobActivity.objects.filter(job=job).delete()

                    # 5. Farmer payments + booking
                    try:
                        booking = job.booking
                        FarmerPayment.objects.filter(booking=booking).delete()
                        booking.delete()
                    except JobBooking.DoesNotExist:
                        pass

                    # 6. Settlements + misc costs
                    MukkadamJobSettlement.objects.filter(job=job).delete()
                    MukkadamMiscCost.objects.filter(job=job).delete()

                    # 7. Job notes
                    JobNote.objects.filter(job=job).delete()

                    # 8. Webhook logs
                    WebhookLog.objects.filter(job_id=str(job.job_id)).delete()
                    FarmerBillWebhookLog.objects.filter(job_id=str(job.job_id)).delete()

                    # 9. Finally delete the job
                    job_id_str = job.job_id
                    job.delete()

                    self.stdout.write(self.style.SUCCESS(f'  ✅ Deleted Job {job_id_str}'))

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Failed to delete Job {job.job_id}: {e}')
                    )
                    raise  # rolls back transaction

            # 10. Delete farmers if flag passed
            if del_farmers and farmers_to_delete:
                for farmer in farmers_to_delete:
                    fname = farmer.farmer_name
                    fid   = farmer.farmer_id
                    # Delete their plots first
                    Plot.objects.filter(farmer=farmer).delete()
                    farmer.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ Deleted Farmer {fname} ({fid}) + plots')
                    )

        self.stdout.write(self.style.SUCCESS(f'\n✅ Done. Deleted {len(existing_ids)} jobs.'))