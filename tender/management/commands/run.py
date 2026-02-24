from django.core.management.base import BaseCommand
from django.utils import timezone
from tender.ervices.settlement import process_all_completed_settlements


class Command(BaseCommand):
    help = 'Settle all past allocations as completed — show full billing summary'

    def handle(self, *args, **options):
        self.stdout.write(f'\n[{timezone.now()}] Running full settlement...\n')

        results, summary = process_all_completed_settlements()

        self.stdout.write('=' * 70)
        self.stdout.write(f'{"TYPE":<10} {"NAME":<20} {"JOB":<12} {"STATUS":<10} {"AMOUNT":>12}')
        self.stdout.write('=' * 70)

        mukkadam_pending = []
        farmer_pending = []

        for row in summary:
            if row['type'] == 'mukkadam':
                amount = row['net_payable']
                self.stdout.write(
                    f'{"MUKKADAM":<10} {row["name"]:<20} {row["job_id"]:<12} '
                    f'{row["status"]:<10} ₹{amount:>10.2f}'
                )
                if row['status'] == 'PENDING':
                    mukkadam_pending.append(row)

            elif row['type'] == 'farmer':
                amount = row['balance_due']
                self.stdout.write(
                    f'{"FARMER":<10} {row["name"]:<20} {row["job_id"]:<12} '
                    f'{row["status"]:<10} ₹{amount:>10.2f}'
                )
                if row['status'] == 'PENDING':
                    farmer_pending.append(row)

        self.stdout.write('=' * 70)
        self.stdout.write(f'\n{len(results)} settlements saved.\n')

        if mukkadam_pending:
            self.stdout.write(self.style.WARNING('\n⚠ MUKKADAM PAYMENTS DUE:'))
            for row in mukkadam_pending:
                self.stdout.write(
                    f'  → {row["name"]} | Job {row["job_id"]} '
                    f'| Farmer: {row["farmer"]} | ₹{row["net_payable"]:.2f}'
                )

        if farmer_pending:
            self.stdout.write(self.style.WARNING('\n⚠ FARMER BALANCE DUE:'))
            for row in farmer_pending:
                self.stdout.write(
                    f'  → {row["name"]} | Job {row["job_id"]} '
                    f'| ₹{row["balance_due"]:.2f}'
                )

        total_mukkadam = sum(r['net_payable'] for r in mukkadam_pending)
        total_farmer = sum(r['balance_due'] for r in farmer_pending)

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal pending to mukkadams : ₹{total_mukkadam:.2f}'
            f'\nTotal pending from farmers : ₹{total_farmer:.2f}'
        ))