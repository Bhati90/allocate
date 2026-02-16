# Save as: data/management/commands/import_all_allocations.py

from decimal import Decimal
from datetime import datetime, time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from data.models import (
    ImportedJobSheet, ImportedFarmer, ImportedMukkadam, ImportedTransporter,
    JobActivity, Allocation, PaymentRequest, TransportPaymentRequest
)
from django.db import models

class Command(BaseCommand):
    help = 'Import ALL allocations - creates missing Mukkadams and JobActivities automatically'

    def handle(self, *args, **options):
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*100))
        self.stdout.write(self.style.SUCCESS('⚡ IMPORTING ALL ALLOCATIONS (Creates Missing Data)'))
        self.stdout.write(self.style.SUCCESS('='*100 + '\n'))
        
        # ============================================================================
        # STEP 1: LOAD ALL DATA INTO MEMORY
        # ============================================================================
        self.stdout.write("📦 Step 1: Loading data into memory...")
        
        # Load JobSheets (only those with labour team AND has payment/acres/farmer)
        sheets = list(ImportedJobSheet.objects.filter(
            import_status='pending',
            labour_team_name__isnull=False,
            farmer_name__isnull=False
        ).exclude(labour_team_name='').exclude(farmer_name=''))
        
        # Load ALL data into dicts for fast lookup
        job_activities_dict = {ja.job_id: ja for ja in JobActivity.objects.all()}
        farmers_dict = {f.name: f for f in ImportedFarmer.objects.all()}
        mukkadams_dict = {m.team_name: m for m in ImportedMukkadam.objects.all()}
        transporters_dict = {t.name: t for t in ImportedTransporter.objects.all()}
        
        # Get existing allocations to avoid duplicates
        existing_allocations = set()
        for alloc in Allocation.objects.select_related('job_activity').all():
            if alloc.job_activity:
                existing_allocations.add(alloc.job_activity.job_id)
        
        self.stdout.write(f"  ✓ Loaded {len(sheets)} JobSheets")
        self.stdout.write(f"  ✓ Loaded {len(job_activities_dict)} JobActivities")
        self.stdout.write(f"  ✓ Loaded {len(farmers_dict)} Farmers")
        self.stdout.write(f"  ✓ Loaded {len(mukkadams_dict)} Mukkadams")
        self.stdout.write(f"  ✓ Loaded {len(transporters_dict)} Transporters")
        self.stdout.write(f"  ✓ Found {len(existing_allocations)} existing allocations\n")
        # ============================================================================
        # STEP 2: CREATE & FIX MUKKADAMS (FIXED - Use integers)
        # ============================================================================
        self.stdout.write("👥 Step 2: Creating/fixing Mukkadams...")

        # Get max existing external_mukkadam_id
        max_id = ImportedMukkadam.objects.filter(
            external_mukkadam_id__isnull=False
        ).aggregate(models.Max('external_mukkadam_id'))['external_mukkadam_id__max']

        mukkadam_counter = (max_id or 9000) + 1  # Start from 9001 or next available

        # Fix existing mukkadams without ID
        mukkadams_without_id = ImportedMukkadam.objects.filter(external_mukkadam_id__isnull=True)
        fixed_count = 0

        for mukkadam in mukkadams_without_id:
            mukkadam.external_mukkadam_id = mukkadam_counter  # ✅ Integer, not string
            mukkadam.save()
            mukkadams_dict[mukkadam.team_name] = mukkadam
            mukkadam_counter += 1
            fixed_count += 1

        if fixed_count > 0:
            self.stdout.write(f"  ✓ Fixed {fixed_count} existing Mukkadams")

        # Create missing mukkadams
        new_mukkadams = []
        for sheet in sheets:
            if sheet.labour_team_name and sheet.labour_team_name not in mukkadams_dict:
                new_mukkadam = ImportedMukkadam(
                    team_name=sheet.labour_team_name,
                    external_mukkadam_id=mukkadam_counter,  # ✅ Integer
                    contact_no='',
                    location=''
                )
                new_mukkadams.append(new_mukkadam)
                mukkadams_dict[sheet.labour_team_name] = new_mukkadam
                mukkadam_counter += 1

        if new_mukkadams:
            ImportedMukkadam.objects.bulk_create(new_mukkadams, batch_size=100)
            self.stdout.write(f"  ✓ Created {len(new_mukkadams)} new Mukkadams")

        self.stdout.write()

        # ============================================================================
        # STEP 3: CREATE MISSING JOB ACTIVITIES
        # ============================================================================
        self.stdout.write("💼 Step 3: Creating missing JobActivities...")
        
        new_job_activities = []
        
        for sheet in sheets:
            if sheet.generated_job_id not in job_activities_dict:
                parsed_acres = self._parse_acres(sheet.acres)
                
                if sheet.activity_start_date:
                    scheduled_datetime = timezone.make_aware(
                        datetime.combine(sheet.activity_start_date, time(8, 0))
                    )
                else:
                    scheduled_datetime = timezone.now()
                
                activity_type = sheet.activity_name.split(',')[0].strip() if sheet.activity_name else 'Unknown'
                
                new_job_activity = JobActivity(
                    job_id=sheet.generated_job_id,
                    farmer_work_id=sheet.generated_farmer_id or None,
                    activity_id=f"ACT_{sheet.id}",
                    activity_name=sheet.activity_name or 'Unknown',
                    activity_type=activity_type,
                    scheduled_datetime=scheduled_datetime,
                    total_area=parsed_acres,
                    total_price=sheet.booking_value or Decimal('0'),
                    transport_cost=sheet.transport_cost or Decimal('0'),
                    other_cost=Decimal('0'),
                    subtotal=sheet.total_booking_value or Decimal('0'),
                    allocated_area=Decimal('0'),
                    rate_per_acre=sheet.finalised_rate_per_acre or Decimal('0'),
                    location=sheet.location or '',
                    is_manually_edited=False,
                )
                
                new_job_activities.append(new_job_activity)
                job_activities_dict[sheet.generated_job_id] = new_job_activity
        
        if new_job_activities:
            created_jobs = JobActivity.objects.bulk_create(new_job_activities, batch_size=100)
            self.stdout.write(f"  ✓ Created {len(created_jobs)} new JobActivities")
            
            # Update dict with saved objects (they now have IDs)
            for ja in created_jobs:
                job_activities_dict[ja.job_id] = ja
        else:
            self.stdout.write(f"  ✓ No new JobActivities needed")
        
        self.stdout.write()
        
        # ============================================================================
        # STEP 4: PREPARE ALLOCATIONS
        # ============================================================================
        self.stdout.write("⚙️  Step 4: Preparing allocations...")
        
        allocations_to_create = []
        skipped = 0
        errors = []
        
        for idx, sheet in enumerate(sheets, 1):
            try:
                # Fast lookup JobActivity (should exist now)
                job_activity = job_activities_dict.get(sheet.generated_job_id)
                if not job_activity:
                    skipped += 1
                    errors.append(f"Sheet {sheet.id}: Still no JobActivity for {sheet.generated_job_id}")
                    continue
                
                # Skip if allocation already exists
                if sheet.generated_job_id in existing_allocations:
                    skipped += 1
                    continue
                
                # Fast lookup Mukkadam (should exist now)
                imported_mukkadam = mukkadams_dict.get(sheet.labour_team_name)
                if not imported_mukkadam:
                    skipped += 1
                    errors.append(f"Sheet {sheet.id}: Still no Mukkadam for {sheet.labour_team_name}")
                    continue
                
                mukkadam_id = imported_mukkadam.external_mukkadam_id
                
                # Fast lookup Farmer
                imported_farmer = farmers_dict.get(sheet.farmer_name) if sheet.farmer_name else None
                
                # Parse acres
                parsed_acres = self._parse_acres(sheet.acres)
                
                # Parse transport
                transport_data = self._parse_transport(sheet, transporters_dict)
                
                # Determine status
                alloc_status = 'completed' if sheet.allocation_status and 'completed' in sheet.allocation_status.lower() else 'allocated'
                work_date = sheet.activity_start_date or timezone.now().date()
                
                # Create Allocation object
                allocation = Allocation(
                    job_activity=job_activity,
                    farmer_name=sheet.farmer_name or '',
                    farmer_contact=sheet.farmer_contact or '',
                    imported_farmer=imported_farmer,
                    farmer_poc=sheet.farmer_poc or '',
                    farmer_poc_id=None,
                    labour_poc=sheet.labour_poc or '',
                    labour_poc_id=None,
                    field_poc=sheet.field_poc or '',
                    field_poc_id=None,
                    mukkadam_id=mukkadam_id,
                    imported_mukkadam=imported_mukkadam,
                    imported_transporter=transport_data['imported_transporter'],
                    allocated_area=parsed_acres,
                    work_date=work_date,
                    crew_size=sheet.team_count or 10,
                    mukkadam_price=sheet.labour_rates or Decimal('0'),
                    transport_type=transport_data['transport_type'],
                    transport_provider_id=transport_data['transport_provider_id'],
                    own_transport_price=transport_data['own_transport_price'],
                    transport_price=transport_data['transport_price'],
                    status=alloc_status,
                    allocated_at=timezone.now(),
                    completed_at=timezone.now() if alloc_status == 'completed' else None,
                    notes=f"Imported from sheet {sheet.id}"
                )
                
                allocations_to_create.append(allocation)
                
                # Progress indicator
                if idx % 100 == 0:
                    self.stdout.write(f"  ⚙️  Prepared {idx}/{len(sheets)}...")
            
            except Exception as e:
                skipped += 1
                errors.append(f"Sheet {sheet.id}: {str(e)}")
        
        self.stdout.write(f"  ✓ Prepared {len(allocations_to_create)} allocations")
        self.stdout.write(f"  ⚠️  Skipped {skipped} sheets\n")
        
        if errors and len(errors) <= 10:
            self.stdout.write("  ⚠️  Errors:")
            for error in errors[:10]:
                self.stdout.write(f"    - {error}")
            self.stdout.write()
        
        # ============================================================================
        # STEP 5: BULK CREATE ALLOCATIONS
        # ============================================================================
        self.stdout.write("💾 Step 5: Bulk creating allocations...")
        
        with transaction.atomic():
            created_allocations = Allocation.objects.bulk_create(
                allocations_to_create,
                batch_size=500
            )
            self.stdout.write(f"  ✓ Created {len(created_allocations)} allocations\n")
        
        # ============================================================================
        # STEP 6: BULK CREATE PAYMENT REQUESTS
        # ============================================================================
        self.stdout.write("💰 Step 6: Bulk creating payment requests...")
        
        payment_requests = []
        for alloc in created_allocations:
            payment_requests.append(
                PaymentRequest(
                    allocation=alloc,
                    mukkadam_id=alloc.mukkadam_id,
                    requested_amount=alloc.mukkadam_price,
                    status='paid',
                    requested_at=alloc.allocated_at,
                    paid_at=alloc.completed_at,
                    requested_by=None,
                    paid_by=None,
                    notes="Auto-created from allocation import"
                )
            )
        
        with transaction.atomic():
            PaymentRequest.objects.bulk_create(payment_requests, batch_size=500)
            self.stdout.write(f"  ✓ Created {len(payment_requests)} payment requests\n")
        
        # ============================================================================
        # STEP 7: BULK CREATE TRANSPORT PAYMENTS
        # ============================================================================
        self.stdout.write("🚚 Step 7: Bulk creating transport payment requests...")
        
        transport_payments = []
        for alloc in created_allocations:
            if alloc.transport_type in ['own', 'provider'] and alloc.transport_price > 0:
                provider_id = alloc.mukkadam_id if alloc.transport_type == 'own' else alloc.transport_provider_id
                notes = "Own transport" if alloc.transport_type == 'own' else "Provider transport"
                
                transport_payments.append(
                    TransportPaymentRequest(
                        allocation=alloc,
                        transport_provider_id=provider_id,
                        requested_amount=alloc.transport_price,
                        status='paid',
                        requested_at=alloc.allocated_at,
                        paid_at=alloc.completed_at,
                        requested_by=None,
                        paid_by=None,
                        notes=notes
                    )
                )
        
        with transaction.atomic():
            TransportPaymentRequest.objects.bulk_create(transport_payments, batch_size=500)
            self.stdout.write(f"  ✓ Created {len(transport_payments)} transport payments\n")
        
        # ============================================================================
        # FINAL SUMMARY
        # ============================================================================
        self.stdout.write(self.style.SUCCESS('\n' + '='*100))
        self.stdout.write(self.style.SUCCESS('✅ IMPORT COMPLETED'))
        self.stdout.write(self.style.SUCCESS('='*100))
        self.stdout.write(f"📊 Final Summary:")
        self.stdout.write(f"  • New Mukkadams Created: {len(new_mukkadams)}")
        self.stdout.write(f"  • New JobActivities Created: {len(new_job_activities) if new_job_activities else 0}")
        self.stdout.write(f"  • JobSheets Processed: {len(sheets)}")
        self.stdout.write(f"  • Allocations Created: {len(created_allocations)}")
        self.stdout.write(f"  • Payment Requests Created: {len(payment_requests)}")
        self.stdout.write(f"  • Transport Payments Created: {len(transport_payments)}")
        self.stdout.write(f"  • Skipped: {skipped}")
        self.stdout.write(self.style.SUCCESS('='*100 + '\n'))

    def _parse_acres(self, acres_str):
        """Parse acres field"""
        if not acres_str:
            return Decimal('0.0')
        
        acres_str = str(acres_str).strip().upper()
        
        if acres_str == 'NA' or 'LABOUR' in acres_str:
            return Decimal('0.0')
        
        try:
            return Decimal(acres_str)
        except:
            return Decimal('0.0')

    def _parse_transport(self, sheet, transporters_dict):
        """Parse transport data"""
        result = {
            'imported_transporter': None,
            'transport_type': 'none',
            'transport_provider_id': None,
            'own_transport_price': None,
            'transport_price': Decimal('0')
        }
        
        if not sheet.transporter_name:
            return result
        
        if sheet.transporter_name.lower() == "self":
            result['transport_type'] = 'own'
            result['own_transport_price'] = sheet.transport_rates or Decimal('0')
            result['transport_price'] = sheet.transport_rates or Decimal('0')
        else:
            imported_transporter = transporters_dict.get(sheet.transporter_name)
            if imported_transporter and imported_transporter.external_transporter_id:
                result['transport_type'] = 'provider'
                result['imported_transporter'] = imported_transporter
                result['transport_provider_id'] = imported_transporter.external_transporter_id
                result['transport_price'] = sheet.transport_rates or Decimal('0')
            else:
                result['transport_type'] = 'own'
                result['transport_price'] = sheet.transport_rates or Decimal('0')
        
        return result


"""
Management command to UPDATE farmer_work_id in JobActivity records

This command:
1. Finds all JobActivity records
2. Matches them with ImportedJobSheet to get farmer names
3. Updates farmer_work_id with correct external farmer ID
"""

# from django.core.management.base import BaseCommand
# from django.db import transaction
# from data.models import (
#     ImportedJobSheet, ImportedFarmer, JobActivity
# )


# class Command(BaseCommand):
#     help = 'Update farmer_work_id in JobActivity records with correct IDs'

#     def add_arguments(self, parser):
#         parser.add_argument('--batch-id', type=str, help='Specific batch ID to update (optional)')
#         parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without actually updating')

#     def handle(self, *args, **options):
#         batch_id = options.get('batch_id')
#         dry_run = options.get('dry_run', False)
        
#         if dry_run:
#             self.stdout.write(self.style.WARNING('\n🔍 DRY RUN MODE - No changes will be made\n'))
        
#         self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
#         self.stdout.write(self.style.SUCCESS('🔄 UPDATING FARMER_WORK_ID IN JOBACTIVITY'))
#         self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        
#         # Build query
#         if batch_id:
#             self.stdout.write(f"📦 Processing Batch: {batch_id}\n")
#             job_sheets = ImportedJobSheet.objects.filter(
#                 import_batch__batch_id=batch_id,
#                 job_activity__isnull=False
#             ).select_related('job_activity')
#         else:
#             self.stdout.write(f"📦 Processing ALL batches\n")
#             job_sheets = ImportedJobSheet.objects.filter(
#                 job_activity__isnull=False
#             ).select_related('job_activity')
        
#         total_count = job_sheets.count()
#         self.stdout.write(f"📊 Found {total_count} JobActivity records to check\n")
        
#         if total_count == 0:
#             self.stdout.write(self.style.WARNING('⚠️  No records to update'))
#             return
        
#         # Counters
#         updated = 0
#         unchanged = 0
#         not_found = 0
#         duplicates = 0
#         errors = 0
        
#         self.stdout.write("🔄 Processing records...\n")
        
#         for idx, sheet_record in enumerate(job_sheets, start=1):
#             job_activity = sheet_record.job_activity
#             farmer_name = sheet_record.farmer_name
            
#             if not job_activity or not farmer_name:
#                 continue
            
#             try:
#                 # Find farmer in ImportedFarmer table
#                 imported_farmers = ImportedFarmer.objects.filter(
#                     name__iexact=farmer_name.strip()
#                 )
                
#                 count = imported_farmers.count()
                
#                 if count == 0:
#                     if not_found < 10:  # Only show first 10
#                         self.stdout.write(f"  ⚠️  Farmer not found: '{farmer_name}'")
#                     not_found += 1
#                     continue
                
#                 if count > 1:
#                     # Multiple matches - take the one with external_id
#                     imported_farmer = imported_farmers.filter(
#                         external_farmer_id__isnull=False
#                     ).first()
                    
#                     if not imported_farmer:
#                         imported_farmer = imported_farmers.first()
                    
#                     if duplicates < 10:  # Only show first 10
#                         self.stdout.write(f"  🔀 Multiple farmers for '{farmer_name}' - using ID: {imported_farmer.external_farmer_id}")
#                     duplicates += 1
#                 else:
#                     imported_farmer = imported_farmers.first()
                
#                 new_farmer_id = imported_farmer.external_farmer_id
#                 old_farmer_id = job_activity.farmer_work_id
                
#                 if new_farmer_id:
#                     if str(old_farmer_id) != str(new_farmer_id):
#                         self.stdout.write(f"  🔄 [{idx}/{total_count}] '{farmer_name}'")
#                         self.stdout.write(f"     JobActivity ID: {job_activity.id}")
#                         self.stdout.write(f"     Old: {old_farmer_id} → New: {new_farmer_id}")
                        
#                         if not dry_run:
#                             job_activity.farmer_work_id = new_farmer_id
#                             job_activity.save(update_fields=['farmer_work_id'])
                        
#                         updated += 1
#                     else:
#                         unchanged += 1
#                 else:
#                     if not_found < 10:  # Only show first 10
#                         self.stdout.write(f"  ⚠️  No external ID for: '{farmer_name}'")
#                     not_found += 1
                
#                 # Progress indicator every 100 records
#                 if idx % 100 == 0:
#                     self.stdout.write(f"\n  ✓ Processed {idx}/{total_count} records...")
#                     self.stdout.write(f"    Updated: {updated}, Unchanged: {unchanged}, Not Found: {not_found}\n")
            
#             except Exception as e:
#                 errors += 1
#                 if errors < 10:  # Only show first 10 errors
#                     self.stdout.write(self.style.ERROR(f"  ❌ Error with '{farmer_name}': {str(e)}"))
        
#         # Final Summary
#         self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
#         self.stdout.write(self.style.SUCCESS('✅ UPDATE COMPLETED'))
#         self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        
#         self.stdout.write(f"Total Records Processed: {total_count}\n")
#         self.stdout.write(f"📊 Summary:")
#         self.stdout.write(f"  • Updated: {updated}")
#         self.stdout.write(f"  • Unchanged (already correct): {unchanged}")
#         self.stdout.write(f"  • Not Found (no external ID): {not_found}")
#         self.stdout.write(f"  • Duplicates Handled: {duplicates}")
#         self.stdout.write(f"  • Errors: {errors}\n")
        
#         if dry_run:
#             self.stdout.write(self.style.WARNING('\n⚠️  This was a DRY RUN - no changes were made'))
#             self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes\n'))
# from django.core.management.base import BaseCommand
# from django.db import transaction
# from django.utils import timezone
# from data.models import (
#     ImportBatch, ImportedJobSheet, ImportedFarmer, 
#     ImportedMukkadam, ImportedTransporter,
#     JobActivity, Allocation, PaymentRequest, TransportPaymentRequest
# )


# class Command(BaseCommand):
#     help = 'Update existing records with correct mukkadam/farmer/transporter IDs'

#     def add_arguments(self, parser):
#         parser.add_argument('--batch-id', type=str, required=True, help='Import batch ID to update')
#         parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without actually updating')

#     def handle(self, *args, **options):
#         batch_id = options['batch_id']
#         dry_run = options.get('dry_run', False)
        
#         if dry_run:
#             self.stdout.write(self.style.WARNING('\n🔍 DRY RUN MODE - No changes will be made\n'))
        
#         self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
#         self.stdout.write(self.style.SUCCESS('🔄 UPDATING IDs IN EXISTING RECORDS'))
#         self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        
#         try:
#             import_batch = ImportBatch.objects.get(batch_id=batch_id)
#         except ImportBatch.DoesNotExist:
#             self.stdout.write(self.style.ERROR(f'❌ Batch {batch_id} not found!'))
#             return
        
#         self.stdout.write(f"📦 Processing Batch: {batch_id}\n")
        
#         # Get imported records (only those already processed)
#         imported_records = ImportedJobSheet.objects.filter(
#             import_batch=import_batch,
#             import_status='imported',
#             job_activity__isnull=False  # Only records with JobActivity
#         ).select_related('job_activity', 'allocation')
        
#         total_count = imported_records.count()
#         self.stdout.write(f"📊 Found {total_count} imported records\n")
        
#         if total_count == 0:
#             self.stdout.write(self.style.WARNING('⚠️  No imported records to update'))
#             return
        
#         # Counters
#         farmer_ids_updated = 0
#         farmer_ids_unchanged = 0
#         farmer_ids_not_found = 0
#         farmer_duplicates = 0
        
#         mukkadam_ids_updated = 0
#         mukkadam_ids_unchanged = 0
#         mukkadam_ids_not_found = 0
#         mukkadam_duplicates = 0
        
#         transporter_ids_updated = 0
#         transporter_ids_unchanged = 0
#         transporter_ids_not_found = 0
#         transporter_duplicates = 0
        
#         payment_mukkadam_updated = 0
#         payment_transporter_updated = 0
        
#         # ============================================
#         # STEP 1: UPDATE FARMER_WORK_ID IN JOBACTIVITY
#         # ============================================
#         self.stdout.write("📋 Step 1: Updating farmer_work_id in JobActivity records...\n")
        
#         for sheet_record in imported_records:
#             job_activity = sheet_record.job_activity
            
#             if not job_activity:
#                 continue
            
#             try:
#                 # ✅ Use filter() + first() to handle duplicates
#                 imported_farmers = ImportedFarmer.objects.filter(
#                     name__iexact=sheet_record.farmer_name
#                 )
                
#                 count = imported_farmers.count()
                
#                 if count == 0:
#                     self.stdout.write(f"  ⚠️  Farmer not in ImportedFarmer table: '{sheet_record.farmer_name}'")
#                     farmer_ids_not_found += 1
#                     continue
                
#                 if count > 1:
#                     # Multiple matches - take the one with external_id
#                     imported_farmer = imported_farmers.filter(
#                         external_farmer_id__isnull=False
#                     ).first()
                    
#                     if not imported_farmer:
#                         # None have external_id, take first one
#                         imported_farmer = imported_farmers.first()
                    
#                     self.stdout.write(f"  ⚠️  Multiple farmers found for '{sheet_record.farmer_name}' - using ID: {imported_farmer.external_farmer_id}")
#                     farmer_duplicates += 1
#                 else:
#                     imported_farmer = imported_farmers.first()
                
#                 new_farmer_id = imported_farmer.external_farmer_id
#                 old_farmer_id = job_activity.farmer_work_id
                
#                 if new_farmer_id:
#                     if old_farmer_id != new_farmer_id:
#                         self.stdout.write(f"  🔄 Updating farmer ID: '{sheet_record.farmer_name}'")
#                         self.stdout.write(f"     Old: {old_farmer_id} → New: {new_farmer_id}")
                        
#                         if not dry_run:
#                             job_activity.farmer_work_id = new_farmer_id
#                             job_activity.save(update_fields=['farmer_work_id'])
                        
#                         farmer_ids_updated += 1
#                     else:
#                         farmer_ids_unchanged += 1
#                 else:
#                     self.stdout.write(f"  ⚠️  No external ID for farmer: '{sheet_record.farmer_name}'")
#                     farmer_ids_not_found += 1
            
#             except Exception as e:
#                 self.stdout.write(self.style.ERROR(f"  ❌ Error with farmer '{sheet_record.farmer_name}': {str(e)}"))
#                 farmer_ids_not_found += 1
        
#         self.stdout.write(f"\n  ✅ Farmer IDs Updated: {farmer_ids_updated}")
#         self.stdout.write(f"  ➖ Unchanged (already correct): {farmer_ids_unchanged}")
#         self.stdout.write(f"  ⚠️  Not found: {farmer_ids_not_found}")
#         self.stdout.write(f"  🔀 Duplicates handled: {farmer_duplicates}\n")
        
#         # ============================================
#         # STEP 2: UPDATE MUKKADAM_ID IN ALLOCATIONS
#         # ============================================
#         self.stdout.write("📋 Step 2: Updating mukkadam_id in Allocation records...\n")
        
#         allocations_to_update = imported_records.filter(
#             allocation__isnull=False
#         )
        
#         for sheet_record in allocations_to_update:
#             allocation = sheet_record.allocation
            
#             if not allocation or not sheet_record.labour_team_name:
#                 continue
            
#             try:
#                 # ✅ Use filter() + first() to handle duplicates
#                 imported_mukkadams = ImportedMukkadam.objects.filter(
#                     team_name__iexact=sheet_record.labour_team_name
#                 )
                
#                 count = imported_mukkadams.count()
                
#                 if count == 0:
#                     self.stdout.write(f"  ⚠️  Mukkadam not in ImportedMukkadam table: '{sheet_record.labour_team_name}'")
#                     mukkadam_ids_not_found += 1
#                     continue
                
#                 if count > 1:
#                     # Multiple matches - take the one with external_id
#                     imported_mukkadam = imported_mukkadams.filter(
#                         external_mukkadam_id__isnull=False
#                     ).first()
                    
#                     if not imported_mukkadam:
#                         # None have external_id, take first one
#                         imported_mukkadam = imported_mukkadams.first()
                    
#                     self.stdout.write(f"  ⚠️  Multiple mukkadams found for '{sheet_record.labour_team_name}' - using ID: {imported_mukkadam.external_mukkadam_id}")
#                     mukkadam_duplicates += 1
#                 else:
#                     imported_mukkadam = imported_mukkadams.first()
                
#                 new_mukkadam_id = imported_mukkadam.external_mukkadam_id
#                 old_mukkadam_id = allocation.mukkadam_id
                
#                 if new_mukkadam_id:
#                     if old_mukkadam_id != new_mukkadam_id:
#                         self.stdout.write(f"  🔄 Updating mukkadam ID: '{sheet_record.labour_team_name}'")
#                         self.stdout.write(f"     Old: {old_mukkadam_id} → New: {new_mukkadam_id}")
                        
#                         if not dry_run:
#                             allocation.mukkadam_id = new_mukkadam_id
#                             allocation.imported_mukkadam = imported_mukkadam
#                             allocation.save(update_fields=['mukkadam_id', 'imported_mukkadam'])
                            
#                             # Update related payment requests
#                             payment_count = PaymentRequest.objects.filter(
#                                 allocation=allocation
#                             ).update(mukkadam_id=new_mukkadam_id)
                            
#                             if payment_count > 0:
#                                 payment_mukkadam_updated += payment_count
#                                 self.stdout.write(f"     ✓ Updated {payment_count} payment request(s)")
                        
#                         mukkadam_ids_updated += 1
#                     else:
#                         mukkadam_ids_unchanged += 1
#                 else:
#                     self.stdout.write(f"  ⚠️  No external ID for mukkadam: '{sheet_record.labour_team_name}'")
#                     mukkadam_ids_not_found += 1
            
#             except Exception as e:
#                 self.stdout.write(self.style.ERROR(f"  ❌ Error with mukkadam '{sheet_record.labour_team_name}': {str(e)}"))
#                 mukkadam_ids_not_found += 1
        
#         self.stdout.write(f"\n  ✅ Mukkadam IDs Updated: {mukkadam_ids_updated}")
#         self.stdout.write(f"  ➖ Unchanged (already correct): {mukkadam_ids_unchanged}")
#         self.stdout.write(f"  ⚠️  Not found: {mukkadam_ids_not_found}")
#         self.stdout.write(f"  🔀 Duplicates handled: {mukkadam_duplicates}")
#         self.stdout.write(f"  💰 Payment Requests Updated: {payment_mukkadam_updated}\n")
        
#         # ============================================
#         # STEP 3: UPDATE TRANSPORT_PROVIDER_ID IN ALLOCATIONS
#         # ============================================
#         self.stdout.write("📋 Step 3: Updating transport_provider_id in Allocation records...\n")
        
#         for sheet_record in allocations_to_update:
#             allocation = sheet_record.allocation
            
#             if not allocation or not sheet_record.transporter_name:
#                 continue
            
#             # Skip 'self' transport
#             if sheet_record.transporter_name.lower() == 'self':
#                 continue
            
#             # Skip if transport_type is not 'provider'
#             if allocation.transport_type != 'provider':
#                 continue
            
#             try:
#                 # ✅ Use filter() + first() to handle duplicates
#                 imported_transporters = ImportedTransporter.objects.filter(
#                     name__iexact=sheet_record.transporter_name
#                 )
                
#                 count = imported_transporters.count()
                
#                 if count == 0:
#                     self.stdout.write(f"  ⚠️  Transporter not in ImportedTransporter table: '{sheet_record.transporter_name}'")
#                     transporter_ids_not_found += 1
#                     continue
                
#                 if count > 1:
#                     # Multiple matches - take the one with external_id
#                     imported_transporter = imported_transporters.filter(
#                         external_transporter_id__isnull=False
#                     ).first()
                    
#                     if not imported_transporter:
#                         # None have external_id, take first one
#                         imported_transporter = imported_transporters.first()
                    
#                     self.stdout.write(f"  ⚠️  Multiple transporters found for '{sheet_record.transporter_name}' - using ID: {imported_transporter.external_transporter_id}")
#                     transporter_duplicates += 1
#                 else:
#                     imported_transporter = imported_transporters.first()
                
#                 new_transporter_id = imported_transporter.external_transporter_id
#                 old_transporter_id = allocation.transport_provider_id
                
#                 if new_transporter_id:
#                     if old_transporter_id != new_transporter_id:
#                         self.stdout.write(f"  🔄 Updating transporter ID: '{sheet_record.transporter_name}'")
#                         self.stdout.write(f"     Old: {old_transporter_id} → New: {new_transporter_id}")
                        
#                         if not dry_run:
#                             allocation.transport_provider_id = new_transporter_id
#                             allocation.imported_transporter = imported_transporter
#                             allocation.save(update_fields=['transport_provider_id', 'imported_transporter'])
                            
#                             # Update related transport payment requests
#                             tpr_count = TransportPaymentRequest.objects.filter(
#                                 allocation=allocation,
#                                 transport_provider_id__isnull=False  # Only update provider transport
#                             ).update(transport_provider_id=new_transporter_id)
                            
#                             if tpr_count > 0:
#                                 payment_transporter_updated += tpr_count
#                                 self.stdout.write(f"     ✓ Updated {tpr_count} transport payment request(s)")
                        
#                         transporter_ids_updated += 1
#                     else:
#                         transporter_ids_unchanged += 1
#                 else:
#                     self.stdout.write(f"  ⚠️  No external ID for transporter: '{sheet_record.transporter_name}'")
#                     transporter_ids_not_found += 1
            
#             except Exception as e:
#                 self.stdout.write(self.style.ERROR(f"  ❌ Error with transporter '{sheet_record.transporter_name}': {str(e)}"))
#                 transporter_ids_not_found += 1
        
#         self.stdout.write(f"\n  ✅ Transporter IDs Updated: {transporter_ids_updated}")
#         self.stdout.write(f"  ➖ Unchanged (already correct): {transporter_ids_unchanged}")
#         self.stdout.write(f"  ⚠️  Not found: {transporter_ids_not_found}")
#         self.stdout.write(f"  🔀 Duplicates handled: {transporter_duplicates}")
#         self.stdout.write(f"  💰 Transport Payment Requests Updated: {payment_transporter_updated}\n")
        
#         # ============================================
#         # FINAL SUMMARY
#         # ============================================
#         self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
#         self.stdout.write(self.style.SUCCESS('✅ UPDATE COMPLETED'))
#         self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
#         self.stdout.write(f"Batch ID: {batch_id}")
#         self.stdout.write(f"Total Records Processed: {total_count}")
#         self.stdout.write(f"\n📊 Summary:")
#         self.stdout.write(f"\n  Farmer IDs:")
#         self.stdout.write(f"    • Updated: {farmer_ids_updated}")
#         self.stdout.write(f"    • Unchanged: {farmer_ids_unchanged}")
#         self.stdout.write(f"    • Not Found: {farmer_ids_not_found}")
#         self.stdout.write(f"    • Duplicates: {farmer_duplicates}")
#         self.stdout.write(f"\n  Mukkadam IDs:")
#         self.stdout.write(f"    • Updated: {mukkadam_ids_updated}")
#         self.stdout.write(f"    • Unchanged: {mukkadam_ids_unchanged}")
#         self.stdout.write(f"    • Not Found: {mukkadam_ids_not_found}")
#         self.stdout.write(f"    • Duplicates: {mukkadam_duplicates}")
#         self.stdout.write(f"\n  Transporter IDs:")
#         self.stdout.write(f"    • Updated: {transporter_ids_updated}")
#         self.stdout.write(f"    • Unchanged: {transporter_ids_unchanged}")
#         self.stdout.write(f"    • Not Found: {transporter_ids_not_found}")
#         self.stdout.write(f"    • Duplicates: {transporter_duplicates}")
#         self.stdout.write(f"\n  Payment Requests:")
#         self.stdout.write(f"    • Mukkadam Payments Updated: {payment_mukkadam_updated}")
#         self.stdout.write(f"    • Transport Payments Updated: {payment_transporter_updated}\n")
        
#         if dry_run:
#             self.stdout.write(self.style.WARNING('\n⚠️  This was a DRY RUN - no changes were made'))
#             self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes\n'))