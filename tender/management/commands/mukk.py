# your_app/management/commands/sync_mukkadams.py
from django.core.management.base import BaseCommand
import requests
from tender.models import Mukkadam, MukkadamActivityRate, ActivityCatalog
from decimal import Decimal, InvalidOperation

def to_decimal(value, default=0):
    if value in (None, "", {}, []):
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)

class Command(BaseCommand):
    help = 'Sync mukkadams from external API'

    def handle(self, *args, **kwargs):
        API_URL = 'http://localhost:8000/api/mukkadam/minimal_list/'
        
        try:
            response = requests.get(API_URL)
            response.raise_for_status()
            mukkadams_data = response.json()
            
            synced = 0
            for mukkadam_data in mukkadams_data:
                # Create or update mukkadam
                mukkadam, created = Mukkadam.objects.update_or_create(
                    mukkadam_id=mukkadam_data['id'],
                    defaults={
                        'mukkadam_name': mukkadam_data['mukkadam_name'],
                        'mobile_numbers': mukkadam_data.get('mobile_numbers', ''),
                        'crew_size': mukkadam_data.get('crew_size', 10),
                        'district': mukkadam_data.get('district', ''),
                        'taluka': mukkadam_data.get('taluka', ''),
                        'village': mukkadam_data.get('village', ''),
                        'is_permanent': mukkadam_data.get('is_permanent', False),
                        'rate_card': mukkadam_data.get('rate_card', {}),
                        'tender_activities': mukkadam_data.get('tender_activities', [])
                    }
                )
                
                # Sync activity rates from rate_card
                rate_card = mukkadam_data.get("rate_card", {})
                tender_activities = mukkadam_data.get("tender_activities", {})

                # Example: dipping_activities
                for key, price in rate_card.get("dipping_activities", {}).items():
                    if not price:   # skip empty strings
                        continue

                    activity, _ = ActivityCatalog.objects.get_or_create(
                        name=key.replace("_", " ").title(),
                        defaults={"source": "api"},
                    )

                    MukkadamActivityRate.objects.update_or_create(
                        mukkadam=mukkadam,
                        activity=activity,
                        defaults={
                            "rate_per_acre": to_decimal(price),
                            "source": "api",
                        },
                    )

                # Example: tender_activities list
                for item in tender_activities.get("activities", []):
                    name = item.get("name")
                    price = item.get("price")

                    if not name or not price:
                        continue

                    activity, _ = ActivityCatalog.objects.get_or_create(
                        name=name,
                        defaults={"source": "api"},
                    )

                    MukkadamActivityRate.objects.update_or_create(
                        mukkadam=mukkadam,
                        activity=activity,
                        defaults={
                            "rate_per_acre": to_decimal(price),
                            "source": "api",
                        },
                    )

                synced += 1
                self.stdout.write(f'✓ Synced: {mukkadam.mukkadam_name}')
            
            self.stdout.write(self.style.SUCCESS(f'✅ Synced {synced} mukkadams'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))