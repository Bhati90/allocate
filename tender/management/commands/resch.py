from django.core.management.base import BaseCommand
from tender.datechange import reschedule_pending_activities

class Command(BaseCommand):
    help = 'Reschedule pending job activities based on pruning date + gap days'

    def add_arguments(self, parser):
        parser.add_argument('--cluster-id', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        result = reschedule_pending_activities(
            cluster_id=options['cluster_id'],
            dry_run=options['dry_run'],
        )
        self.stdout.write(f"\n{'DRY RUN — ' if result['dry_run'] else ''}Reschedule complete")
        self.stdout.write(f"  Updated : {result['updated_count']}")
        self.stdout.write(f"  Skipped : {result['skipped_count']}")
        if result['updated']:
            self.stdout.write("\nChanged:")
            for r in result['updated']:
                self.stdout.write(
                    f"  [{r['job']}] {r['activity']} / {r['plot']} "
                    f"({r['old_date']} → {r['new_date']}, "
                    f"pruning={r['pruning']} + {r['gap_days']}d, cluster={r['cluster']})"
                )