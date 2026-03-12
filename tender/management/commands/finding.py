# management/commands/export_job_ids.py
# Run: python manage.py export_job_ids

import json
from django.core.management.base import BaseCommand
from tender.models import Job  # ← your app name with Job model


class Command(BaseCommand):
    help = 'Export all Job IDs to a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='all_job_ids.json')

    def handle(self, *args, **options):
        outfile = options['output']

        all_job_ids = list(
            Job.objects.values_list('job_id', flat=True)
        )

        # Convert all to string for consistent comparison
        all_job_ids = [str(jid) for jid in all_job_ids]

        with open(outfile, 'w') as f:
            json.dump(all_job_ids, f)

        self.stdout.write(self.style.SUCCESS(
            f'✅ Exported {len(all_job_ids)} Job IDs to {outfile}'
        ))