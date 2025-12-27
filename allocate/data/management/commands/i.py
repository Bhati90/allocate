from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import random
from decimal import Decimal
from data.models import Job, JobActivity

class Command(BaseCommand):
    help = 'Import sample jobs from API format'

    def handle(self, *args, **kwargs):
        # Sample activity names (can be anything from API)
        activity_names = [
            'Pruning', 'April Pruning', 'Pasting', 'First Fail Fut Removal',
            'Second Fail Fut Removal', 'Bagal Bali Fut Removal', 'First Dipping',
            'Second Dipping', 'Third Dipping', 'Bunch Thinning', 'Finger Thinning',
            'Berry Thinning', 'Shoot Tying', 'Bunch Selection', 'Bunch Tying',
            'Shenda Topping', 'Paper Wrapping', 'Paper Removal', 'Harvesting',
            'New Plantation', 'Soil Testing', 'Crop Health Assessment',
            'Fertilizer Application', 'Pest Control', 'Irrigation Setup'
        ]
        
        locations = [
            'Plot A - Nashik Road', 'Plot B - Ojhar', 'Plot C - Dindori',
            'Plot D - Manmad', 'Plot E - Sinnar', 'Plot F - Niphad'
        ]
        
        priorities = ['LOW', 'MEDIUM', 'HIGH', 'URGENT']
        statuses = ['PENDING', 'IN_PROGRESS']
        
        # Clear existing data
        Job.objects.all().delete()
        JobActivity.objects.all().delete()
        
        self.stdout.write('Creating 15 sample jobs...')
        
        for i in range(1, 16):
            # Create Job
            job_id = f"FV{2025000 + i}"
            farmer_id = f"F{str(i).zfill(3)}"
            plot_id = f"P{str(i).zfill(3)}"
            
            num_activities = random.randint(2, 5)
            total_amount = 0
            
            scheduled_date = timezone.now() + timedelta(days=random.randint(0, 30))
            
            job = Job.objects.create(
                job_id=job_id,
                farmer_id=farmer_id,
                plot_id=plot_id,
                title=f"Grape Farm Work - {farmer_id}",
                description=f"Scheduled farm visit for plot {plot_id}",
                status=random.choice(statuses),
                priority=random.choice(priorities),
                scheduled_date=scheduled_date,
                activity_notes=f"Season work for {farmer_id}",
                internal_notes=f"Farmer requested quality work",
                booking_id=f"BK{str(i).zfill(3)}",
                booking_total_amount=Decimal('0'),  # Will update after activities
                booking_advance_paid=Decimal('0'),
                booking_balance=Decimal('0')
            )
            
            # Create Activities
            for j in range(num_activities):
                activity_id = f"ACT{i}{j+1}"
                activity_name = random.choice(activity_names)
                
                acres = round(random.uniform(1.0, 15.0), 1)
                rate = random.choice([800, 1000, 1200, 1500, 2000])
                base_price = Decimal(str(acres * rate))
                transport = Decimal(str(round(random.uniform(100, 500), 2)))
                other = Decimal(str(round(random.uniform(50, 200), 2)))
                subtotal = base_price + transport + other
                
                total_amount += float(subtotal)
                
                activity_datetime = scheduled_date + timedelta(hours=random.randint(0, 8))
                
                JobActivity.objects.create(
                    job=job,
                    activity_id=activity_id,
                    activity_name=activity_name,
                    activity_type=activity_name.lower().replace(' ', '_'),
                    scheduled_datetime=activity_datetime,
                    total_area=Decimal(str(acres)),
                    total_price=base_price,
                    transport_cost=transport,
                    other_cost=other,
                    subtotal=subtotal,
                    allocated_area=Decimal('0'),
                    remaining_area=Decimal(str(acres)),
                    estimated_workers=int(acres * random.uniform(1.5, 2.5)),
                    rate_per_acre=Decimal(str(rate)),
                    location=random.choice(locations)
                )
            
            # Update job financial info
            job.total_activities_amount = Decimal(str(total_amount))
            job.booking_total_amount = Decimal(str(total_amount * 1.1))  # Add 10%
            job.booking_advance_paid = Decimal(str(total_amount * 0.3))  # 30% advance
            job.booking_balance = job.booking_total_amount - job.booking_advance_paid
            job.save()
            
            self.stdout.write(self.style.SUCCESS(f'Created {job_id} with {num_activities} activities'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully created 15 jobs with activities!'))