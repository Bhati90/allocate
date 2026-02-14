import csv
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from data.models import (
    ImportBatch, ImportedJobSheet, 
    ImportedFarmer, ImportedMukkadam, ImportedTransporter
)


class Command(BaseCommand):
    help = 'Import job sheet CSV into staging tables'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS('🚀 STARTING JOB SHEET IMPORT'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        
        # Generate batch ID
        batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create import batch
        import_batch = ImportBatch.objects.create(
            batch_id=batch_id,
            filename=csv_file_path.split('/')[-1],
            status='processing'
        )
        
        self.stdout.write(f"📦 Created Import Batch: {batch_id}\n")
        
        try:
            # Read CSV
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            self.stdout.write(f"📄 Found {len(rows)} rows in CSV\n")
            
            # Process rows
            imported_count = 0
            failed_count = 0
            
            # Process rows (each row in its own transaction)
            for idx, row in enumerate(rows, start=1):
                try:
                    with transaction.atomic():
                        # Parse data
                        sheet_record = self._create_sheet_record(
                            import_batch, 
                            row, 
                            idx
                        )
                        imported_count += 1
                        
                        if idx % 100 == 0:
                            self.stdout.write(f"  ✓ Processed {idx}/{len(rows)} rows...")
                
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Row {idx} failed: {str(e)}")
                    )
                    continue

            # Extract and create master data
            self.stdout.write(f"\n📊 Creating master lookup tables...")
            with transaction.atomic():
                self._create_master_data()
            # Update batch
            import_batch.total_records = len(rows)
            import_batch.successful_imports = imported_count
            import_batch.failed_imports = failed_count
            import_batch.status = 'completed'
            import_batch.save()
            
            # Print summary
            self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
            self.stdout.write(self.style.SUCCESS('✅ IMPORT COMPLETED'))
            self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
            self.stdout.write(f"Batch ID: {batch_id}")
            self.stdout.write(f"Total Rows: {len(rows)}")
            self.stdout.write(f"✓ Imported: {imported_count}")
            self.stdout.write(f"✗ Failed: {failed_count}")
            
            # Master data summary
            farmer_count = ImportedFarmer.objects.count()
            mukkadam_count = ImportedMukkadam.objects.count()
            transporter_count = ImportedTransporter.objects.count()
            
            self.stdout.write(f"\n📚 Master Data Created:")
            self.stdout.write(f"  • Farmers: {farmer_count}")
            self.stdout.write(f"  • Mukkadams: {mukkadam_count}")
            self.stdout.write(f"  • Transporters: {transporter_count}")
            
            self.stdout.write(self.style.SUCCESS(f'\n🎯 Next Step:'))
            self.stdout.write(f"Run: python manage.py process_imports --batch-id {batch_id}\n")
        
        except Exception as e:
            import_batch.status = 'failed'
            import_batch.save()
            self.stdout.write(self.style.ERROR(f'\n❌ Import failed: {str(e)}\n'))
            raise

    def _create_sheet_record(self, import_batch, row, row_number):
        """Create ImportedJobSheet record from CSV row"""
        
        # Generate job ID
        generated_job_id = f"SHEET_2025_{row_number:04d}"
        
        # Parse date (DD/MM/YYYY)
        date_str = row.get('Activity Start Date', '').strip()
        if date_str:
            try:
                activity_date = datetime.strptime(date_str, '%d/%m/%Y').date()
            except ValueError:
                # Try other formats
                try:
                    activity_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    activity_date = None
        else:
            activity_date = None
        
        # Parse currency fields
        def parse_currency(value):
            if not value:
                return None
            # Remove ₹, commas, spaces
            cleaned = value.replace('₹', '').replace(',', '').strip()
            if cleaned:
                try:
                    return Decimal(cleaned)
                except:
                    return None
            return None
        
        # Parse integer fields
        def parse_int(value):
            if not value:
                return None
            try:
                return int(value)
            except:
                return None
        
        # Create record
        return ImportedJobSheet.objects.create(
            import_batch=import_batch,
            generated_job_id=generated_job_id,
            
            # Job details
            activity_start_date=activity_date,
            farmer_name=row.get('Farmer Name', '').strip(),
            farmer_contact=row.get('Contact No', '').strip(),
            activity_name=row.get('Activity', '').strip(),
            acres=row.get('Acres', '').strip(),
            
            # Pricing
            finalised_rate_per_acre=parse_currency(row.get('Finalised Rate/Acre', '')),
            booking_value=parse_currency(row.get('Booking Value', '')),
            transport_cost=parse_currency(row.get('Transportation Cost', '')),
            total_booking_value=parse_currency(row.get('Total Booking Value', '')),
            
            # Farm details
            variety=row.get('Variety', '').strip(),
            location=row.get('Location', '').strip(),
            google_maps_link=row.get('Google Maps link', '').strip(),
            
            # Allocation details
            labour_team_name=row.get('Labour Team Name', '').strip(),
            team_count=parse_int(row.get('Team Count', '')),
            allocation_status=row.get('Allocation Status', '').strip(),
            labour_rates=parse_currency(row.get('Labour Rates', '')),
            
            # Transport details
            transporter_name=row.get('Transporter', '').strip(),
            transport_rates=parse_currency(row.get('Transport Rates', '')),
            
            # POC details
            farmer_poc=row.get('Farmer POC', '').strip(),
            labour_poc=row.get('Labour POC', '').strip(),
            field_poc=row.get('Field POC', '').strip(),
            bi_poc_assigned=row.get('BI POC assigned', '').strip(),
            
            # Remarks
            allocation_team_remarks=row.get('AllocationTeam Remarks', '').strip(),
            field_team_remarks=row.get('Field Team Remarks', '').strip(),
            
            # Status
            import_status='pending'
        )
    
    def _create_master_data(self):
        """Extract unique names and create master lookup tables"""
        
        # Get all sheet records
        sheet_records = ImportedJobSheet.objects.all()
        
        # Extract unique farmers
        unique_farmers = set(
            record.farmer_name 
            for record in sheet_records 
            if record.farmer_name
        )
        
        for farmer_name in unique_farmers:
            ImportedFarmer.objects.get_or_create(name=farmer_name)
        
        self.stdout.write(f"  ✓ Created {len(unique_farmers)} farmers")
        
        # Extract unique mukkadams
        unique_mukkadams = set(
            record.labour_team_name 
            for record in sheet_records 
            if record.labour_team_name
        )
        
        for mukkadam_name in unique_mukkadams:
            ImportedMukkadam.objects.get_or_create(team_name=mukkadam_name)
        
        self.stdout.write(f"  ✓ Created {len(unique_mukkadams)} mukkadams")
        
        # Extract unique transporters
        unique_transporters = set(
            record.transporter_name 
            for record in sheet_records 
            if record.transporter_name
        )
        
        for transporter_name in unique_transporters:
            ImportedTransporter.objects.get_or_create(name=transporter_name)
        
        self.stdout.write(f"  ✓ Created {len(unique_transporters)} transporters")