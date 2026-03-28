# Save as: tender/management/commands/backfill_note_activities.py

from django.core.management.base import BaseCommand
from tender.models import JobNote, JobActivity


class Command(BaseCommand):
    help = 'Backfill job_activity on JobNotes missing it, using oldest unassigned activity'

    def handle(self, *args, **options):
        notes_without = JobNote.objects.filter(job_activity__isnull=True).select_related('job')
        total = notes_without.count()
        self.stdout.write(f"Found {total} notes without job_activity")

        updated = 0
        skipped = 0

        for note in notes_without.iterator():
            # Already assigned activity IDs for this job's notes
            already_used = set(
                JobNote.objects
                .filter(job_id=note.job_id, job_activity__isnull=False)
                .values_list('job_activity_id', flat=True)
            )

            # Oldest unassigned valid activity (by scheduled_date, then id)
            chosen = (
                JobActivity.objects
                .filter(job_id=note.job_id, total_area__gt=0, is_lost=False)
                .exclude(id__in=already_used)
                .order_by('scheduled_date', 'id')
                .first()
            )

            # Fallback: oldest valid activity even if already used
            if not chosen:
                chosen = (
                    JobActivity.objects
                    .filter(job_id=note.job_id, total_area__gt=0, is_lost=False)
                    .order_by('scheduled_date', 'id')
                    .first()
                )

            if chosen:
                note.job_activity = chosen
                note.save(update_fields=['job_activity'])
                updated += 1
                self.stdout.write(
                    f"  Note #{note.id} (Job {note.job_id}) → "
                    f"Activity #{chosen.id} {chosen.activity.name} "
                    f"({chosen.total_area} ac, sched: {chosen.scheduled_date})"
                )
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  Note #{note.id} (Job {note.job_id}) → SKIPPED (no valid activity)"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Updated: {updated}, Skipped: {skipped}, Total: {total}"
        ))