import os
from datetime import date
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from tender.models import JobActivity   # ← adjust import


DATE_FROM = date(2026, 3, 23)
DATE_TO   = date(2026, 3, 29)


class Command(BaseCommand):
    help = 'Export farmers with 0 total_area activities scheduled Mar 23–29'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='zero_area_farmers_mar23_29.xlsx',
            help='Output Excel file path',
        )
        parser.add_argument(
            '--date-from', default='2026-03-23',
            help='Start date YYYY-MM-DD (default: 2026-03-23)',
        )
        parser.add_argument(
            '--date-to', default='2026-03-29',
            help='End date YYYY-MM-DD (default: 2026-03-29)',
        )

    def handle(self, *args, **options):
        date_from = date.fromisoformat(options['date_from'])
        date_to   = date.fromisoformat(options['date_to'])
        output    = options['output']

        # ── Query: activities in range with total_area = 0 ─────────────────────
        qs = (
            JobActivity.objects
            .filter(
                scheduled_date__range=(date_from, date_to),
                total_area__gt=0,
                is_lost=False,
            )
            .select_related(
                'job__farmer',
                'job__plot',
                'activity',
                'plot',
            )
            .prefetch_related('job__clusters')
            .order_by('job__farmer__farmer_name', 'scheduled_date')
        )

        total = qs.count()
        self.stdout.write(f'Found {total} zero-area activity records …')

        # ── Workbook ───────────────────────────────────────────────────────────
        wb = Workbook()
        ws = wb.active
        ws.title = 'Zero Area Activities'

        # ── Styles ─────────────────────────────────────────────────────────────
        H_FILL   = PatternFill('solid', fgColor='C00000')   # dark red
        H_FONT   = Font(bold=True, color='FFFFFF', size=11)
        ALT_FILL = PatternFill('solid', fgColor='FFF2F2')   # light red tint
        CENTER   = Alignment(horizontal='center', vertical='center')
        WRAP     = Alignment(wrap_text=False, vertical='center')
        BORDER   = Border(
            left=Side(style='thin', color='D0D0D0'),
            right=Side(style='thin', color='D0D0D0'),
            bottom=Side(style='thin', color='D0D0D0'),
        )

        # ── Columns ────────────────────────────────────────────────────────────
        HEADERS = [
            'Farmer ID',
            'Farmer Name',
            'Farmer Phone',
            'Job ID',
            'Crop Name',
            'Plot Name',
            'Plot Area (ac)',
            'Cluster(s)',
            'Activity Name',
            'Activity Type',
            'Scheduled Date',
            'Total Area',
            'Allocated Area',
            'Remaining Area',
            'Allocation Status',
            'Rate / Acre (₹)',
            'Transport Cost (₹)',
            'Other Cost (₹)',
            'Subtotal (₹)',
            'Source',
            'Is Strict',
            'Is Lost',
            'Move Reason',
            'API Activity ID',
            'Activity Created At',
        ]

        # ── Header row ─────────────────────────────────────────────────────────
        ws.row_dimensions[1].height = 28
        for ci, h in enumerate(HEADERS, 1):
            c = ws.cell(row=1, column=ci, value=h)
            c.font      = H_FONT
            c.fill      = H_FILL
            c.alignment = CENTER
            c.border    = BORDER

        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = f'A1:{get_column_letter(len(HEADERS))}1'

        # ── Data rows ──────────────────────────────────────────────────────────
        for ri, ja in enumerate(qs.iterator(), start=2):
            farmer   = ja.job.farmer
            clusters = ', '.join(c.name for c in ja.job.clusters.all())

            row = [
                farmer.farmer_id,
                farmer.farmer_name,
                farmer.phone_number or '',
                ja.job.job_id,
                ja.job.crop_name or '',
                ja.plot.name if ja.plot else (ja.job.plot.name if ja.job.plot else ''),
                float(ja.plot.area_acres) if ja.plot and ja.plot.area_acres else '',
                clusters,
                ja.activity.name,
                ja.activity.activity_type or '',
                str(ja.scheduled_date) if ja.scheduled_date else '',
                float(ja.total_area),
                float(ja.allocated_area),
                float(ja.remaining_area),
                ja.allocation_status,
                float(ja.rate_per_acre),
                float(ja.transport_cost),
                float(ja.other_cost),
                float(ja.subtotal),
                ja.source,
                'Yes' if ja.is_strict else 'No',
                'Yes' if ja.is_lost   else 'No',
                ja.move_reason or '',
                ja.api_activity_id or '',
                ja.created_at.strftime('%Y-%m-%d %H:%M') if ja.created_at else '',
            ]

            fill = ALT_FILL if ri % 2 == 0 else None
            for ci, val in enumerate(row, 1):
                c = ws.cell(row=ri, column=ci, value=val)
                c.border    = BORDER
                c.alignment = WRAP
                if fill:
                    c.fill = fill

        # ── Auto-fit widths ────────────────────────────────────────────────────
        for ci, header in enumerate(HEADERS, 1):
            col_letter = get_column_letter(ci)
            max_len = len(header)
            for ri in range(2, min(ws.max_row + 1, 202)):
                v = ws.cell(row=ri, column=ci).value
                if v:
                    max_len = max(max_len, min(len(str(v)), 50))
            ws.column_dimensions[col_letter].width = max_len + 3

        # ── Farmer summary sheet ───────────────────────────────────────────────
        ws2 = wb.create_sheet('By Farmer')
        SUM_HEADERS = [
            'Farmer ID', 'Farmer Name', 'Phone',
            'Zero-Area Activity Count', 'Clusters', 'Job IDs',
        ]
        for ci, h in enumerate(SUM_HEADERS, 1):
            c = ws2.cell(row=1, column=ci, value=h)
            c.font = Font(bold=True, color='FFFFFF')
            c.fill = H_FILL
            c.alignment = CENTER
            c.border = BORDER

        # Group by farmer
        from collections import defaultdict
        farmer_map = defaultdict(lambda: {
            'name': '', 'phone': '', 'count': 0,
            'clusters': set(), 'jobs': set()
        })
        for ja in qs:
            fid = ja.job.farmer.farmer_id
            farmer_map[fid]['name']  = ja.job.farmer.farmer_name
            farmer_map[fid]['phone'] = ja.job.farmer.phone_number or ''
            farmer_map[fid]['count'] += 1
            farmer_map[fid]['jobs'].add(ja.job.job_id)
            for cl in ja.job.clusters.all():
                farmer_map[fid]['clusters'].add(cl.name)

        for ri, (fid, info) in enumerate(
            sorted(farmer_map.items(), key=lambda x: x[1]['name']), start=2
        ):
            ws2_row = [
                fid,
                info['name'],
                info['phone'],
                info['count'],
                ', '.join(sorted(info['clusters'])),
                ', '.join(sorted(info['jobs'])),
            ]
            for ci, val in enumerate(ws2_row, 1):
                ws2.cell(row=ri, column=ci, value=val).border = BORDER

        for ci in range(1, len(SUM_HEADERS) + 1):
            ws2.column_dimensions[get_column_letter(ci)].width = 22

        ws2.freeze_panes = 'A2'
        ws2.auto_filter.ref = f'A1:{get_column_letter(len(SUM_HEADERS))}1'

        # ── Save ───────────────────────────────────────────────────────────────
        wb.save(output)
        self.stdout.write(
            self.style.SUCCESS(
                f'✅  {total} records | {len(farmer_map)} farmers → {os.path.abspath(output)}'
            )
        )
