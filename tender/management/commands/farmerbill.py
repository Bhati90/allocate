import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.timezone import localtime
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

from tender.models import FarmerBillWebhookLog   # ← adjust import


# ── Column definitions: (header label, model field/callable) ──────────────────
COLUMNS = [
    ('ID',                  'id'),
    ('Sent At',             'sent_at'),
    ('Sent By Name',        'sent_by_name'),
    ('Sent By Email',       'sent_by_email'),
    ('Sent By ID',          'sent_by_id'),
    ('Auth Token',          'auth_token'),
    ('Activity Name',       'activity_name'),

    # Farmer
    ('Farmer ID',           'farmer_id'),
    ('Farmer Name',         'farmer_name'),
    ('Farmer Phone',        'farmer_phone'),

    # Job
    ('Job ID',              'job_id'),
    ('Crop Name',           'crop_name'),
    ('Plot Name',           'plot_name'),
    ('Cluster',             'cluster'),          # FK → str via __str__

    # Mukkadam
    ('Mukkadam Name',       'mukkadam_name'),
    ('Mukkadam Mobile',     'mukkadam_mobile'),

    # Bill
    ('Total Billed (₹)',    'total_billed'),
    ('Total Paid (₹)',      'total_paid'),
    ('Balance Due (₹)',     'balance_due'),

    # Webhook outcome
    ('Webhook Status',      'webhook_status'),
    ('Webhook Success',     'webhook_success'),
    ('Webhook Booking ID',  'webhook_booking_id'),
    ('Booking Status',      'webhook_booking_status'),
    ('Webhook Detail',      'webhook_detail'),
    ('Webhook Response',    'webhook_response'),

    # Payload & meta
    ('Full Payload',        'full_payload'),
    ('Created At',          'created_at'),
]


def _get_value(obj, field):
    """Resolve a field name to a cell-safe value."""
    val = getattr(obj, field, None)

    # FK → readable string
    if hasattr(val, '__str__') and not isinstance(val, (str, int, float, bool, Decimal, type(None))):
        val = str(val)

    # datetimes → localtime string
    if hasattr(val, 'tzinfo') and val is not None:
        try:
            val = localtime(val).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            val = str(val)

    # dicts / lists (JSONField) → compact string
    if isinstance(val, (dict, list)):
        import json
        val = json.dumps(val, ensure_ascii=False)

    # Decimal → float so Excel treats it as a number
    if isinstance(val, Decimal):
        val = float(val)

    return val


class Command(BaseCommand):
    help = 'Export all FarmerBillWebhookLog records to an Excel file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='farmer_bill_webhook_logs.xlsx',
            help='Output file path (default: farmer_bill_webhook_logs.xlsx)',
        )
        parser.add_argument(
            '--cluster',
            type=int,
            default=None,
            help='Filter by cluster ID (optional)',
        )
        parser.add_argument(
            '--success-only',
            action='store_true',
            help='Export only successful webhook records',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        qs = FarmerBillWebhookLog.objects.select_related('cluster').order_by('-created_at')

        # ── Optional filters ──────────────────────────────────────────────────
        if options['cluster']:
            qs = qs.filter(cluster_id=options['cluster'])
        if options['success_only']:
            qs = qs.filter(webhook_success=True)

        total = qs.count()
        self.stdout.write(f'Exporting {total} records …')

        # ── Workbook setup ────────────────────────────────────────────────────
        wb = Workbook()
        ws = wb.active
        ws.title = 'Webhook Logs'

        # ── Styles ────────────────────────────────────────────────────────────
        HEADER_FILL   = PatternFill('solid', fgColor='1F4E79')   # dark blue
        HEADER_FONT   = Font(bold=True, color='FFFFFF', size=11)
        ALT_FILL      = PatternFill('solid', fgColor='EEF3FB')   # light blue
        CENTER        = Alignment(horizontal='center', vertical='center', wrap_text=False)
        WRAP          = Alignment(wrap_text=True, vertical='top')
        THIN_BORDER   = Border(
            left=Side(style='thin', color='C0C0C0'),
            right=Side(style='thin', color='C0C0C0'),
            bottom=Side(style='thin', color='C0C0C0'),
        )

        headers = [col[0] for col in COLUMNS]

        # ── Header row ────────────────────────────────────────────────────────
        ws.row_dimensions[1].height = 30
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font      = HEADER_FONT
            cell.fill      = HEADER_FILL
            cell.alignment = CENTER
            cell.border    = THIN_BORDER

        # ── Freeze header row ─────────────────────────────────────────────────
        ws.freeze_panes = 'A2'

        # ── Data rows ─────────────────────────────────────────────────────────
        for row_idx, obj in enumerate(qs.iterator(), start=2):
            fill = ALT_FILL if row_idx % 2 == 0 else None
            for col_idx, (_, field) in enumerate(COLUMNS, start=1):
                val  = _get_value(obj, field)
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border    = THIN_BORDER
                cell.alignment = WRAP
                if fill:
                    cell.fill = fill

        # ── Auto-fit column widths ─────────────────────────────────────────────
        for col_idx, header in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            # Sample first 200 rows for width estimation
            max_len = len(header)
            for row_idx in range(2, min(ws.max_row + 1, 202)):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val:
                    max_len = max(max_len, min(len(str(cell_val)), 60))
            ws.column_dimensions[col_letter].width = max_len + 4

        # Long text columns → cap width + enable wrap
        LONG_TEXT_COLS = {'Full Payload', 'Webhook Response', 'Webhook Detail', 'Auth Token'}
        for col_idx, (header, _) in enumerate(COLUMNS, start=1):
            if header in LONG_TEXT_COLS:
                ws.column_dimensions[get_column_letter(col_idx)].width = 50

        # ── Auto-filter on header row ─────────────────────────────────────────
        ws.auto_filter.ref = ws.dimensions

        # ── Summary sheet ─────────────────────────────────────────────────────
        ws_sum = wb.create_sheet('Summary')
        from django.db.models import Sum, Count
        summary_data = [
            ('Total Records',      total),
            ('Successful',         qs.filter(webhook_success=True).count()),
            ('Failed',             qs.filter(webhook_success=False).count()),
            ('Total Billed (₹)',   float(qs.aggregate(s=Sum('total_billed'))['s'] or 0)),
            ('Total Paid (₹)',     float(qs.aggregate(s=Sum('total_paid'))['s'] or 0)),
            ('Balance Due (₹)',    float(qs.aggregate(s=Sum('balance_due'))['s'] or 0)),
        ]
        ws_sum.column_dimensions['A'].width = 25
        ws_sum.column_dimensions['B'].width = 20
        for r, (label, value) in enumerate(summary_data, start=1):
            ws_sum.cell(row=r, column=1, value=label).font = Font(bold=True)
            ws_sum.cell(row=r, column=2, value=value)

        # ── Save ──────────────────────────────────────────────────────────────
        wb.save(output_path)
        self.stdout.write(
            self.style.SUCCESS(f'✅  Saved {total} rows → {os.path.abspath(output_path)}')
        )
