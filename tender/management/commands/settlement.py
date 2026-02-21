# tender/management/commands/process_settlements.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from tender.ervices.settlement import process_all_triggered_settlements


class Command(BaseCommand):
    help = 'Calculate settlements for jobs where shoot selection date has passed'

    def handle(self, *args, **options):
        self.stdout.write(f'[{timezone.now()}] Processing settlements...')
        results = process_all_triggered_settlements()
        self.stdout.write(
            self.style.SUCCESS(f'Done. {len(results)} settlements created/updated.')
        )