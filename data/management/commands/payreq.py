# allocation_app/management/commands/process_auto_payments.py

from django.core.management.base import BaseCommand
from data.services import process_daily_payments

class Command(BaseCommand):
    help = 'Manually trigger payment processing'

    def handle(self, *args, **options):
        self.stdout.write("⏳ Starting manual processing...")
        stats = process_daily_payments()
        self.stdout.write(self.style.SUCCESS(f"✅ Done: {stats}"))