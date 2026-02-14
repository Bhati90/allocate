# your_app/management/commands/sync_jobs.py
from django.core.management.base import BaseCommand
import requests
from tender.models import Job, JobActivity, Farmer, ActivityCatalog


class Command(BaseCommand):
    help = 'Sync jobs from external API'

    def handle(self, *args, **kwargs):
        API_URL = 'http://localhost:8001/ap/jobs/?booking_type=Tender'

        try:
            response = requests.get(API_URL)
            response.raise_for_status()
            jobs_data = response.json()

            synced = 0
            for job_data in jobs_data:
                # 1) Farmer
                farmer_info = job_data.get('farmer', {})
                farmer, _ = Farmer.objects.get_or_create(
                    farmer_id=job_data['farmer_id'],
                    defaults={
                        'farmer_name': farmer_info.get('farmer_name', 'Unknown'),
                        'phone_number': farmer_info.get('phone_number', ''),
                        'village': farmer_info.get('village', ''),
                        'taluka': farmer_info.get('taluka', ''),
                        'district': farmer_info.get('district', ''),
                    },
                )

                # 2) Job (API uses "id" → our "job_id")
                job, created = Job.objects.update_or_create(
                    job_id=job_data['id'],           # <-- was job_data['job_id']
                    defaults={
                        'work_id': job_data.get('work_id', ''),
                        'farmer': farmer,
                        'plot_id': job_data.get('plot_id', ''),
                        'status': job_data.get('status', 'pending'),
                        'priority': job_data.get('priority', 'MEDIUM'),
                        'scheduled_date': job_data.get('scheduled_date'),
                        'booking_type': job_data.get('booking_type', 'Tender'),
                        'activity_notes': job_data.get('activity_notes', ''),
                        'internal_notes': job_data.get('internal_notes', ''),
                        'total_activities_amount': job_data.get('total_activities_amount', 0),
                        'is_field_verified': job_data.get('is_field_verified', False),
                        'is_complex': job_data.get('is_complex', False),
                        'point_of_contact': job_data.get('point_of_contact', ''),
                        'latitude': job_data.get('latitude'),
                        'longitude': job_data.get('longitude'),
                        'api_raw_data': job_data,     # optional: keep full payload
                    },
                )

                # 3) Activities
                for activity_data in job_data.get('activities', []):
                    activity, _ = ActivityCatalog.objects.get_or_create(
                        name=activity_data['activity_name'],
                        defaults={
                            'default_rate_per_acre': activity_data.get('rate_per_acre', 0),
                            'is_strict': activity_data.get('is_strict', False),
                            'source': 'api',
                        },
                    )

                    JobActivity.objects.update_or_create(
                        job=job,
                        activity=activity,
                        defaults={
                            'total_area': activity_data.get('total_area', 0),
                            'allocated_area': activity_data.get('allocated_area', 0),
                            'rate_per_acre': activity_data.get('rate_per_acre', 0),
                            'estimated_workers': activity_data.get('estimated_workers', 10),
                            'scheduled_date': activity_data.get('scheduled_date'),
                        },
                    )

                synced += 1
                self.stdout.write(f'✓ Synced: {job.job_id}')

            self.stdout.write(self.style.SUCCESS(f'✅ Synced {synced} jobs'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
