# Create file: your_app/management/commands/create_test_data.py
from django.core.management.base import BaseCommand
from tender.models import (
    ActivityCatalog, Farmer, Job, JobActivity, 
    Mukkadam, MukkadamActivityRate
)
from datetime import date

class Command(BaseCommand):
    help = 'Create test data for farm scheduling'

    def handle(self, *args, **kwargs):
        # 1. Create Activities
        activities = [
            {'name': 'Paper Wrapping', 'rate': 1000, 'strict': False, 'workers': 10},
            {'name': 'Pruning', 'rate': 4000, 'strict': True, 'workers': 8},
            {'name': 'Harvesting', 'rate': 1500, 'strict': False, 'workers': 15},
            {'name': 'Fertilizing', 'rate': 800, 'strict': False, 'workers': 5},
        ]
        
        for act in activities:
            ActivityCatalog.objects.get_or_create(
                name=act['name'],
                defaults={
                    'default_rate_per_acre': act['rate'],
                    'is_strict': act['strict'],
                    'estimated_workers_per_acre': act['workers'],
                    'source': 'custom'
                }
            )
        self.stdout.write(self.style.SUCCESS('✅ Created activities'))

        # 2. Create Farmers
        farmer, _ = Farmer.objects.get_or_create(
            farmer_id='235',
            defaults={
                'farmer_name': 'Nilesh Chavan',
                'phone_number': '9876543210',
                'village': 'Ojhar',
                'taluka': 'Nashik',
                'district': 'Nashik'
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Created farmer'))

        # 3. Create Job
        job, _ = Job.objects.get_or_create(
            job_id='JOB-11927',
            defaults={
                'work_id': 'WORK-001',
                'farmer': farmer,
                'status': 'scheduled',
                'priority': 'HIGH',
                'scheduled_date': date(2026, 2, 15),
                'booking_type': 'Tender'
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Created job'))

        # 4. Create Job Activities
        paper_wrap = ActivityCatalog.objects.get(name='Paper Wrapping')
        JobActivity.objects.get_or_create(
            job=job,
            activity=paper_wrap,
            defaults={
                'total_area': 2.0,
                'rate_per_acre': 1000,
                'estimated_workers': 10
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Created job activities'))

        # 5. Create Mukkadams
        mukkadam, _ = Mukkadam.objects.get_or_create(
            mukkadam_id=278,
            defaults={
                'mukkadam_name': 'Hemant Pithe',
                'mobile_numbers': '9988776655',
                'crew_size': 12,
                'district': 'Nashik',
                'taluka': 'Nashik',
                'village': 'Ojhar',
                'is_permanent': True
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Created mukkadam'))

        # 6. Create Mukkadam Rates
        MukkadamActivityRate.objects.get_or_create(
            mukkadam=mukkadam,
            activity=paper_wrap,
            defaults={
                'rate_per_acre': 800,
                'productivity_per_worker': 0.15,
                'source': 'custom'
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Created mukkadam rates'))

        self.stdout.write(self.style.SUCCESS('🎉 Test data created successfully!'))