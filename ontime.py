import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from datetime import date
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime

from tender.models import JobActivity

print("Fetching data...")

qs = JobActivity.objects.filter(
    is_lost=False,
    total_area__gt=0,
    sales_date__isnull=False,
    allocations__work_status='completed',
).distinct().select_related(
    'activity', 'job__farmer', 'plot'
).prefetch_related('allocations', 'plot__clusters', 'job__clusters')

on_time    = []
late_1_7   = []
late_7_15  = []
late_15_30 = []
late_30p   = []

for ja in qs:
    completed_alloc = ja.allocations.filter(
        work_status='completed'
    ).order_by('-allocated_date').first()
    if not completed_alloc or not completed_alloc.allocated_date:
        continue

    completed_date = completed_alloc.allocated_date
    sales_date     = ja.sales_date
    diff           = (completed_date - sales_date).days

    cluster = (
        ja.plot.clusters.first().name if ja.plot and ja.plot.clusters.exists() else
        ja.job.clusters.first().name  if ja.job.clusters.exists() else '—'
    )

    item = {
        'ja_id':          ja.id,
        'job_id':         ja.job.job_id,
        'farmer':         ja.job.farmer.farmer_name,
        'activity':       ja.activity.name,
        'plot':           ja.plot.name if ja.plot else '—',
        'cluster':        cluster,
        'scheduled_date': str(ja.scheduled_date) if ja.scheduled_date else '—',
        'sales_date':     str(sales_date),
        'completed_date': str(completed_date),
        'diff_days':      diff,
        'total_area':     float(ja.total_area),
    }

    if diff <= 0:
        on_time.append(item)
    elif diff <= 7:
        late_1_7.append(item)
    elif diff <= 15:
        late_7_15.append(item)
    elif diff <= 30:
        late_15_30.append(item)
    else:
        late_30p.append(item)

counted = len(on_time) + len(late_1_7) + len(late_7_15) + len(late_15_30) + len(late_30p)
print(f"Analysed {counted} activities")

# ── Styles ───────────────────────────────────────────────────────────
def pct(n):
    return round(n / counted * 100, 1) if counted > 0 else 0

HEADER_FILL  = PatternFill('solid', start_color='1F3864')
GREEN_FILL   = PatternFill('solid', start_color='C6EFCE')
YELLOW_FILL  = PatternFill('solid', start_color='FFEB9C')
ORANGE_FILL  = PatternFill('solid', start_color='FFCC99')
RED_FILL     = PatternFill('solid', start_color='FFC7CE')
DARK_RED_FILL= PatternFill('solid', start_color='FF0000')
ALT_FILL     = PatternFill('solid', start_color='F5F5F5')

HEADER_FONT  = Font(bold=True, color='FFFFFF', name='Arial', size=10)
BOLD_FONT    = Font(bold=True, name='Arial', size=10)
NORMAL_FONT  = Font(name='Arial', size=9)
WHITE_BOLD   = Font(bold=True, color='FFFFFF', name='Arial', size=11)

thin = Side(style='thin', color='CCCCCC')
BORDER  = Border(left=thin, right=thin, top=thin, bottom=thin)
CENTER  = Alignment(horizontal='center', vertical='center')
LEFT    = Alignment(horizontal='left',   vertical='center')
RIGHT   = Alignment(horizontal='right',  vertical='center')

BUCKET_STYLES = [
    ('✅ On Time (≤ 0d)',  on_time,    '375623', 'C6EFCE', GREEN_FILL),
    ('🟡 Late 1–7d',       late_1_7,   '7D6608', 'FFEB9C', YELLOW_FILL),
    ('🟠 Late 7–15d',      late_7_15,  '833C00', 'FFCC99', ORANGE_FILL),
    ('🔴 Late 15–30d',     late_15_30, '9C0006', 'FFC7CE', RED_FILL),
    ('💀 Late 30d+',       late_30p,   'FFFFFF', 'FF0000', DARK_RED_FILL),
]

def style_header(cell):
    cell.font      = HEADER_FONT
    cell.fill      = HEADER_FILL
    cell.alignment = CENTER
    cell.border    = BORDER

def style_cell(cell, fill=None, font=None, align=None):
    cell.font      = font  or NORMAL_FONT
    cell.fill      = fill  or PatternFill()
    cell.alignment = align or LEFT
    cell.border    = BORDER

wb = Workbook()

# ═══════════════════════════════════════════════════════
# SHEET 1 — Summary Dashboard
# ═══════════════════════════════════════════════════════
ws1 = wb.active
ws1.title = 'Summary'

ws1.merge_cells('A1:F1')
ws1['A1'] = '📊 Sales Date Performance Report'
ws1['A1'].font      = Font(bold=True, size=16, name='Arial', color='1F3864')
ws1['A1'].alignment = CENTER

ws1['A2'] = f'Generated: {datetime.now().strftime("%d %b %Y %H:%M")}  |  Total Analysed: {counted}'
ws1['A2'].font      = Font(italic=True, size=9, name='Arial', color='666666')
ws1['A2'].alignment = LEFT

ws1.append([])

# Bucket summary table
headers = ['Bucket', 'Count', '% Share', 'Avg Days Late', 'Total Area (ac)']
ws1.row_dimensions[4].height = 22
for col, h in enumerate(headers, 1):
    c = ws1.cell(row=4, column=col, value=h)
    style_header(c)

row = 5
all_items = on_time + late_1_7 + late_7_15 + late_15_30 + late_30p
for label, items, text_color, bg_color, fill in BUCKET_STYLES:
    ws1.row_dimensions[row].height = 20
    n        = len(items)
    avg_diff = round(sum(i['diff_days'] for i in items) / n, 1) if n else 0
    total_ac = round(sum(i['total_area'] for i in items), 2)
    vals     = [label, n, f'{pct(n)}%', avg_diff, total_ac]
    for col, val in enumerate(vals, 1):
        c = ws1.cell(row=row, column=col, value=val)
        txt_font = Font(bold=True, color=text_color, name='Arial', size=10) if text_color != '1F3864' else BOLD_FONT
        if label == '💀 Late 30d+':
            txt_font = Font(bold=True, color='FFFFFF', name='Arial', size=10)
        style_cell(c, fill=fill, font=txt_font,
                   align=CENTER if col > 1 else LEFT)
    row += 1

# Totals row
ws1.row_dimensions[row].height = 22
tot_vals = ['TOTAL', counted, '100%',
            round(sum(i['diff_days'] for i in all_items) / counted, 1) if counted else 0,
            round(sum(i['total_area'] for i in all_items), 2)]
for col, val in enumerate(tot_vals, 1):
    c = ws1.cell(row=row, column=col, value=val)
    c.font      = Font(bold=True, name='Arial', size=10)
    c.fill      = PatternFill('solid', start_color='D9D9D9')
    c.alignment = CENTER if col > 1 else LEFT
    c.border    = BORDER

ws1.append([])
row += 2

# Per-cluster breakdown
ws1.cell(row=row, column=1, value='PER-CLUSTER BREAKDOWN').font = Font(bold=True, size=12, name='Arial', color='1F3864')
row += 1

cluster_headers = ['Cluster', 'Total', 'On Time', 'Late 1-7d', 'Late 7-15d', 'Late 15-30d', 'Late 30d+', 'On Time %']
ws1.row_dimensions[row].height = 22
for col, h in enumerate(cluster_headers, 1):
    c = ws1.cell(row=row, column=col, value=h)
    style_header(c)
row += 1

cluster_stats = defaultdict(lambda: {'on_time': 0, 'l1': 0, 'l2': 0, 'l3': 0, 'l4': 0, 'area': 0.0})
for label, items, *_ in BUCKET_STYLES:
    key = 'on_time' if 'On Time' in label else 'l1' if '1–7' in label else 'l2' if '7–15' in label else 'l3' if '15–30' in label else 'l4'
    for item in items:
        cluster_stats[item['cluster']][key] += 1
        cluster_stats[item['cluster']]['area'] += item['total_area']

for ri, (cluster, s) in enumerate(sorted(cluster_stats.items(), key=lambda x: -(sum(v for k, v in x[1].items() if k != 'area')))):
    ws1.row_dimensions[row].height = 18
    tot     = s['on_time'] + s['l1'] + s['l2'] + s['l3'] + s['l4']
    ot_pct  = round(s['on_time'] / tot * 100, 1) if tot else 0
    ot_fill = GREEN_FILL if ot_pct >= 70 else YELLOW_FILL if ot_pct >= 40 else RED_FILL
    fill    = ALT_FILL if ri % 2 == 0 else PatternFill()

    row_vals = [cluster, tot, s['on_time'], s['l1'], s['l2'], s['l3'], s['l4'], f'{ot_pct}%']
    for col, val in enumerate(row_vals, 1):
        c = ws1.cell(row=row, column=col, value=val)
        style_cell(c,
            fill=ot_fill if col == 8 else fill,
            font=BOLD_FONT if col in [1, 2, 8] else NORMAL_FONT,
            align=CENTER if col > 1 else LEFT)
    row += 1

col_widths = [30, 10, 12, 14, 14, 14, 12, 12]
for i, w in enumerate(col_widths, 1):
    ws1.column_dimensions[get_column_letter(i)].width = w

ws1.freeze_panes = 'A5'

# ═══════════════════════════════════════════════════════
# SHEETS 2-6 — Detail per bucket
# ═══════════════════════════════════════════════════════
detail_headers = [
    'JA ID', 'Job ID', 'Farmer', 'Activity', 'Plot', 'Cluster',
    'Scheduled Date', 'Sales Date', 'Completed Date', 'Days Diff', 'Area (ac)'
]

col_widths_detail = [8, 10, 28, 35, 18, 20, 14, 14, 14, 10, 10]

for label, items, text_color, bg_color, fill in BUCKET_STYLES:
    sheet_name = label.split(' ', 1)[1][:28]
    ws = wb.create_sheet(sheet_name)

    # Header
    ws.merge_cells(f'A1:{get_column_letter(len(detail_headers))}1')
    ws['A1'] = f'{label} — {len(items)} jobs ({pct(len(items))}%)'
    ws['A1'].font      = Font(bold=True, size=13, name='Arial',
                              color='FFFFFF' if text_color == 'FFFFFF' else text_color)
    ws['A1'].fill      = PatternFill('solid', start_color=bg_color)
    ws['A1'].alignment = CENTER

    ws.row_dimensions[2].height = 22
    for col, h in enumerate(detail_headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        style_header(c)

    for ri, item in enumerate(sorted(items, key=lambda x: x['diff_days'], reverse=True), 3):
        ws.row_dimensions[ri].height = 18
        row_fill = ALT_FILL if ri % 2 == 0 else PatternFill()
        vals = [
            item['ja_id'], item['job_id'], item['farmer'], item['activity'],
            item['plot'], item['cluster'], item['scheduled_date'],
            item['sales_date'], item['completed_date'],
            item['diff_days'], item['total_area']
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=ri, column=col, value=val)
            is_diff = col == 10
            diff_fill = (GREEN_FILL if item['diff_days'] <= 0 else
                         YELLOW_FILL if item['diff_days'] <= 7 else
                         ORANGE_FILL if item['diff_days'] <= 15 else
                         RED_FILL    if item['diff_days'] <= 30 else
                         DARK_RED_FILL)
            style_cell(c,
                fill=diff_fill if is_diff else row_fill,
                font=Font(bold=True, name='Arial', size=9,
                          color='FFFFFF' if item['diff_days'] > 30 and is_diff else '000000')
                     if is_diff else NORMAL_FONT,
                align=CENTER if col in [1, 2, 7, 8, 9, 10, 11] else LEFT)

    for i, w in enumerate(col_widths_detail, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = 'A3'
    ws.auto_filter.ref = f'A2:{get_column_letter(len(detail_headers))}2'

# ═══════════════════════════════════════════════════════
# SHEET 7 — All Data
# ═══════════════════════════════════════════════════════
ws_all = wb.create_sheet('All Data')
ws_all.row_dimensions[1].height = 22
for col, h in enumerate(detail_headers + ['Bucket'], 1):
    c = ws_all.cell(row=1, column=col, value=h)
    style_header(c)

ri = 2
for label, items, *_ in BUCKET_STYLES:
    bucket_name = label.split(' ', 1)[1]
    for item in sorted(items, key=lambda x: x['diff_days'], reverse=True):
        ws_all.row_dimensions[ri].height = 18
        fill = ALT_FILL if ri % 2 == 0 else PatternFill()
        vals = [
            item['ja_id'], item['job_id'], item['farmer'], item['activity'],
            item['plot'], item['cluster'], item['scheduled_date'],
            item['sales_date'], item['completed_date'],
            item['diff_days'], item['total_area'], bucket_name
        ]
        for col, val in enumerate(vals, 1):
            c = ws_all.cell(row=ri, column=col, value=val)
            style_cell(c, fill=fill, align=CENTER if col in [1,2,7,8,9,10,11] else LEFT)
        ri += 1

for i, w in enumerate(col_widths_detail + [18], 1):
    ws_all.column_dimensions[get_column_letter(i)].width = w
ws_all.freeze_panes = 'A2'
ws_all.auto_filter.ref = f'A1:{get_column_letter(len(detail_headers)+1)}1'

# ── Save ─────────────────────────────────────────────
import os
out = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f'sales_performance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
)
wb.save(out)
print(f'\n✅ Saved: {out}')
print(f'\nSummary:')
for label, items, *_ in BUCKET_STYLES:
    print(f'  {label:<25} {len(items):>5}  ({pct(len(items))}%)')