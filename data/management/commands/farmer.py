# management/commands/import_demand_sheet.py
from decimal import Decimal
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from data.models import ImportedFarmer, FarmerPayment, JobActivity
from datetime import datetime


class Command(BaseCommand):
    help = 'Import demand sheet and match with job activities'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to demand sheet Excel file')
        parser.add_argument('--match', action='store_true', help='Auto-match with job activities')

    def handle(self, *args, **options):
        file_path = options['file']
        auto_match = options.get('match', False)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('📄 IMPORTING DEMAND SHEET'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        self.stdout.write(f"📂 Reading file: {file_path}\n")
        
        # Read Excel file with openpyxl engine
        try:
            # Try with openpyxl first
            df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')
            self.stdout.write(f"📊 Found {len(df)} records in demand sheet\n")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error reading file with openpyxl: {str(e)}"))
            
            # Try with xlrd as fallback
            try:
                df = pd.read_excel(file_path, sheet_name='Sheet1', engine='xlrd')
                self.stdout.write(f"📊 Found {len(df)} records in demand sheet\n")
            except Exception as e2:
                self.stdout.write(self.style.ERROR(f"❌ Error reading file: {str(e2)}"))
                self.stdout.write(self.style.ERROR("\nPlease install openpyxl: pip install openpyxl"))
                return
        
        # Print column names for debugging
        self.stdout.write(f"📋 Columns found: {list(df.columns)}\n")
        
        # Step 1: Extract unique farmers and create/update ImportedFarmer
        self.stdout.write("👥 Step 1: Processing farmers...")
        self._process_farmers(df)
        
        # Step 2: Import payment records
        self.stdout.write("\n💰 Step 2: Importing payment records...")
        imported_count, failed_count = self._import_payments(df)
        
        # Step 3: Match with job activities
        if auto_match:
            self.stdout.write("\n🔗 Step 3: Matching with job activities...")
            matched_count = self._match_job_activities()
        else:
            matched_count = 0
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('✅ IMPORT COMPLETED'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(f"📊 Summary:")
        self.stdout.write(f"  • Payment Records Imported: {imported_count}")
        self.stdout.write(f"  • Failed: {failed_count}")
        self.stdout.write(f"  • Matched with Jobs: {matched_count}\n")

    def _process_farmers(self, df):
        """Extract farmers and assign IDs"""
        
        # Get unique farmer names
        unique_farmers = df['Farmer'].dropna().unique()
        
        # Get existing farmers in ImportedFarmer
        existing_farmers = set(ImportedFarmer.objects.values_list('name', flat=True))
        
        # Get highest dummy ID number
        max_dummy_id = ImportedFarmer.objects.filter(
            is_dummy_id=True
        ).aggregate(Max('dummy_id_number'))['dummy_id_number__max'] or 1000
        
        new_farmers = []
        for farmer_name in unique_farmers:
            farmer_name = str(farmer_name).strip()
            
            if farmer_name not in existing_farmers:
                # Create new farmer with dummy ID
                max_dummy_id += 1
                new_farmers.append(ImportedFarmer(
                    name=farmer_name,
                    external_farmer_id=f"DUMMY_{max_dummy_id}",
                    is_dummy_id=True,
                    dummy_id_number=max_dummy_id,
                    created_from_import=True
                ))
        
        if new_farmers:
            ImportedFarmer.objects.bulk_create(new_farmers)
            self.stdout.write(f"  ✓ Added {len(new_farmers)} new farmers with dummy IDs")
        
        self.stdout.write(f"  ✓ Total farmers in system: {ImportedFarmer.objects.count()}")

    def _import_payments(self, df):
        """Import all payment records from demand sheet"""
        
        imported = 0
        failed = 0
        
        for idx, row in df.iterrows():
            try:
                with transaction.atomic():
                    # Skip empty rows
                    if pd.isna(row.get('Farmer')) or pd.isna(row.get('Activity Date')):
                        continue
                    
                    # Parse data
                    farmer_name = str(row['Farmer']).strip()
                    activity_date = pd.to_datetime(row['Activity Date']).date()
                    
                    # Get or create farmer
                    imported_farmer, _ = ImportedFarmer.objects.get_or_create(
                        name=farmer_name
                    )
                    
                    # Parse payment status
                    payment_status = 'pending'
                    if pd.notna(row.get('Payment Status')):
                        status_str = str(row['Payment Status']).lower()
                        if 'paid' in status_str:
                            payment_status = 'paid'
                    
                    # Parse payment route
                    payment_route = ''
                    if pd.notna(row.get('Payment Route')):
                        route_str = str(row['Payment Route']).lower()
                        if 'cheque' in route_str:
                            payment_route = 'cheque'
                        elif 'upi' in route_str:
                            payment_route = 'upi'
                        elif 'cash' in route_str:
                            payment_route = 'cash'
                        elif 'bank' in route_str or 'transfer' in route_str:
                            payment_route = 'bank_transfer'
                        elif 'zoho' in route_str:
                            payment_route = 'zoho'
                        else:
                            payment_route = 'other'
                    
                    # Parse amounts
                    booking_value = self._parse_decimal(row.get('Booking Value', 0))
                    transportation_cost = self._parse_decimal(row.get('Transportation', 0))
                    total_value = self._parse_decimal(row.get('Total Value', 0))
                    
                    # Date of payment
                    date_of_payment = None
                    if pd.notna(row.get('Date of Payment')):
                        try:
                            date_of_payment = pd.to_datetime(row['Date of Payment']).date()
                        except:
                            pass
                    
                    # Create payment record
                    FarmerPayment.objects.create(
                        imported_farmer=imported_farmer,
                        activity_date=activity_date,
                        village=str(row.get('Village', '')),
                        farmer_name=farmer_name,
                        activity_name=str(row.get('Activity', '')),
                        acres=str(row.get('Acre', '')),
                        booking_rate_per_acre=self._parse_decimal(row.get('Booking Rate/Acre')),
                        exact_bundles_used=str(row.get('Exact Bundles Used', '')),
                        booking_value=booking_value,
                        transportation_cost=transportation_cost,
                        total_value=total_value,
                        payment_status=payment_status,
                        payment_route=payment_route,
                        date_of_payment=date_of_payment,
                        description=str(row.get('Description', '')),
                        reference_no=str(row.get('Reference No.', ''))
                    )
                    
                    imported += 1
                    if (idx + 1) % 100 == 0:
                        self.stdout.write(f"  ✓ Processed {idx + 1} records...")
                    
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ✗ Row {idx + 1} failed: {str(e)}"))
                continue
        
        return imported, failed

    def _match_job_activities(self):
        """Match payments with job activities"""
        from django.db.models import Q
        
        unmatched_payments = FarmerPayment.objects.filter(is_matched=False)
        matched_count = 0
        
        for payment in unmatched_payments:
            # Try to find matching JobActivity
            # Match criteria: same date, farmer name, and similar booking value
            
            potential_matches = JobActivity.objects.filter(
                scheduled_datetime__date=payment.activity_date,
            )
            
            # Filter by farmer name (through ImportedFarmer)
            if payment.imported_farmer:
                potential_matches = potential_matches.filter(
                    Q(farmer_work_id=payment.imported_farmer.external_farmer_id)
                )
            
            # Find exact match by booking value
            for job in potential_matches:
                # Check if booking values match (within 1% tolerance)
                if job.total_price and abs(job.total_price - payment.booking_value) <= (payment.booking_value * Decimal('0.01')):
                    payment.job_activity = job
                    payment.is_matched = True
                    payment.match_notes = f"Auto-matched: Date + Farmer + Amount"
                    payment.save()
                    matched_count += 1
                    break
        
        self.stdout.write(f"  ✓ Matched {matched_count} payments with job activities")
        return matched_count

    def _parse_decimal(self, value):
        """Parse decimal value safely"""
        if pd.isna(value) or value == '':
            return Decimal('0')
        try:
            return Decimal(str(value))
        except:
            return Decimal('0')
