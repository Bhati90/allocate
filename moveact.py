import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')
django.setup()

from collections import defaultdict
from tender.models import JobActivity
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

EXPECTED_ORDER = ['pruning', 'hand_pasting', 'cordan_tying', 'shoot_selection']

GROUP_LABELS = {
    'pruning':       'Pruning',
    'hand_pasting':  'Hand Pasting',
    'cordan_tying':  'Cordan Tying',
    'shoot_selection': 'Shoot Selection',
}

def get_group(name: str):
    n = name.strip()
    if n in ("Pruning (छाटणी)", "Pruning (छाटणी) 1", "Pruning (छाटणी) 2"):
        return 'pruning'
    if n in ("Hand Pasting (पेस्टींग)",):
        return 'hand_pasting'
    if n in ("Cordan Tying (ओलांढे बांधणे)", "Cordan Tying (सुटलेले ओलांढे बांधणे)",
             "Full Cordan Tying", "Full Cordan Tying (सरसकट ओलांढे बांधणे)"):
        return 'cordan_tying'
    if n in ("Shoot Selection (विरळणी)", "Shoot Selection (विरळणी) 1"):
        return 'shoot_selection'
    return None

# ── Fetch ─────────────────────────────────────────────────────────────────────
activities = JobActivity.objects.filter(
    is_lost=False,
    total_area__gt=0,
    scheduled_date__isnull=False,
).select_related('job__farmer', 'activity', 'plot', 'job').order_by('job_id', 'scheduled_date')

job_map = defaultdict(lambda: defaultdict(list))
for ja in activities:
    grp = get_group(ja.activity.name)
    if grp:
        job_map[ja.job_id][grp].append(ja)

# ── Find violations ───────────────────────────────────────────────────────────
violations = []
for job_id, groups in job_map.items():
    present = [g for g in EXPECTED_ORDER if g in groups]
    if len(present) < 2:
        continue
    for i in range(len(present) - 1):
        curr_grp = present[i]
        next_grp = present[i + 1]
        curr_max = max(ja.scheduled_date for ja in groups[curr_grp])
        next_min = min(ja.scheduled_date for ja in groups[next_grp])
        if curr_max >= next_min:
            first_ja = groups[curr_grp][0]
            violations.append({
                'job_id':        job_id,
                'farmer':        first_ja.job.farmer.farmer_name,
                'farmer_phone':  first_ja.job.farmer.phone_number,
                'plot':          first_ja.plot.plot_code if first_ja.plot else '—',
                'curr_grp':      curr_grp,
                'curr_max':      curr_max,
                'next_grp':      next_grp,
                'next_min':      next_min,
                'curr_acts':     sorted(groups[curr_grp], key=lambda x: x.scheduled_date),
                'next_acts':     sorted(groups[next_grp], key=lambda x: x.scheduled_date),
            })

print(f"Found {len(violations)} violations across {len(set(v['job_id'] for v in violations))} jobs")

# ── Excel ─────────────────────────────────────────────────────────────────────
wb = Workbook()

# ── Styles ────────────────────────────────────────────────────────────────────
RED_BG    = PatternFill('solid', start_color='FFF2F2')
RED_HDR   = PatternFill('solid', start_color='DC2626')
AMBER_BG  = PatternFill('solid', start_color='FEF3C7')
AMBER_HDR = PatternFill('solid', start_color='D97706')
GREEN_HDR = PatternFill('solid', start_color='15803D')
GRAY_BG   = PatternFill('solid', start_color='F9FAFB')
GRAY_HDR  = PatternFill('solid', start_color='374151')

WHITE_BOLD  = Font(name='Arial', bold=True, color='FFFFFF', size=11)
BLACK_BOLD  = Font(name='Arial', bold=True, color='000000', size=10)
BLACK_NORM  = Font(name='Arial', color='000000', size=10)
RED_BOLD    = Font(name='Arial', bold=True, color='DC2626', size=10)
AMBER_BOLD  = Font(name='Arial', bold=True, color='92400E', size=10)

CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT   = Alignment(horizontal='left',   vertical='center', wrap_text=True)

thin = Side(style='thin', color='E5E7EB')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def hdr(ws, row, col, val, fill, font=None, align=CENTER):
    c = ws.cell(row=row, column=col, value=val)
    c.fill = fill
    c.font = font or WHITE_BOLD
    c.alignment = align
    c.border = BORDER
    return c

def cell(ws, row, col, val, font=None, fill=None, align=LEFT):
    c = ws.cell(row=row, column=col, value=val)
    c.font = font or BLACK_NORM
    if fill: c.fill = fill
    c.alignment = align
    c.border = BORDER
    return c

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 1 — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
ws = wb.active
ws.title = 'Summary'
ws.sheet_view.showGridLines = False
ws.column_dimensions['A'].width = 35
ws.column_dimensions['B'].width = 18
ws.column_dimensions['C'].width = 18
ws.row_dimensions[1].height = 36

# Title
ws.merge_cells('A1:C1')
c = ws['A1']
c.value = '⚠ Activity Order Violations Report'
c.font = Font(name='Arial', bold=True, color='FFFFFF', size=14)
c.fill = RED_HDR
c.alignment = CENTER

# Summary stats by violation type
by_type = defaultdict(list)
for v in violations:
    key = f"{GROUP_LABELS[v['curr_grp']]}  →  {GROUP_LABELS[v['next_grp']]}"
    by_type[key].append(v)

hdr(ws, 2, 1, 'Violation Type',  GRAY_HDR)
hdr(ws, 2, 2, 'Jobs Affected',   GRAY_HDR)
hdr(ws, 2, 3, '% of Total',      GRAY_HDR)

total_jobs = len(set(v['job_id'] for v in violations))
r = 3
for vtype, items in sorted(by_type.items(), key=lambda x: -len(x[1])):
    cell(ws, r, 1, vtype,                    font=BLACK_BOLD)
    cell(ws, r, 2, len(items),               font=BLACK_BOLD, align=CENTER)
    cell(ws, r, 3, f"{len(items)/max(total_jobs,1)*100:.0f}%", align=CENTER)
    ws.row_dimensions[r].height = 22
    r += 1

# Totals
cell(ws, r, 1, 'TOTAL',          font=Font(name='Arial', bold=True, size=10), fill=AMBER_BG)
cell(ws, r, 2, len(violations),  font=Font(name='Arial', bold=True, size=10), fill=AMBER_BG, align=CENTER)
cell(ws, r, 3, total_jobs,       font=Font(name='Arial', bold=True, size=10), fill=AMBER_BG, align=CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 2 — ALL VIOLATIONS FLAT TABLE
# ═══════════════════════════════════════════════════════════════════════════════
ws2 = wb.create_sheet('All Violations')
ws2.sheet_view.showGridLines = False
ws2.freeze_panes = 'A3'

cols = [
    ('Job ID',              15),
    ('Farmer',              28),
    ('Phone',               16),
    ('Plot Code',           12),
    ('Violation',           40),
    ('Current Group',       18),
    ('Current Last Date',   18),
    ('Activities (Current)',50),
    ('Next Group',          18),
    ('Next First Date',     18),
    ('Activities (Next)',   50),
    ('Days Overlap',        14),
]

# Title row
ws2.merge_cells(f'A1:{get_column_letter(len(cols))}1')
c = ws2['A1']
c.value = f'All Violations — {len(violations)} issues found across {total_jobs} jobs'
c.font = Font(name='Arial', bold=True, color='FFFFFF', size=12)
c.fill = RED_HDR
c.alignment = CENTER
ws2.row_dimensions[1].height = 30

for i, (title, width) in enumerate(cols, 1):
    hdr(ws2, 2, i, title, GRAY_HDR)
    ws2.column_dimensions[get_column_letter(i)].width = width
ws2.row_dimensions[2].height = 28

r = 3
for v in sorted(violations, key=lambda x: (x['curr_grp'], x['next_grp'], x['job_id'])):
    overlap_days = (v['curr_max'] - v['next_min']).days

    curr_detail = ' | '.join(
        f"{ja.activity.name} [{ja.scheduled_date}] {float(ja.total_area)}ac"
        for ja in v['curr_acts']
    )
    next_detail = ' | '.join(
        f"{ja.activity.name} [{ja.scheduled_date}] {float(ja.total_area)}ac"
        for ja in v['next_acts']
    )

    row_fill = RED_BG if overlap_days > 3 else AMBER_BG

    cell(ws2, r, 1,  v['job_id'],                                          fill=row_fill, font=Font(name='Arial', bold=True, color='1D4ED8', size=10))
    cell(ws2, r, 2,  v['farmer'],                                          fill=row_fill, font=BLACK_BOLD)
    cell(ws2, r, 3,  v['farmer_phone'],                                    fill=row_fill)
    cell(ws2, r, 4,  v['plot'],                                            fill=row_fill, align=CENTER)
    cell(ws2, r, 5,  f"{GROUP_LABELS[v['curr_grp']]} → {GROUP_LABELS[v['next_grp']]}", fill=row_fill, font=RED_BOLD)
    cell(ws2, r, 6,  GROUP_LABELS[v['curr_grp']],                         fill=row_fill, align=CENTER)
    cell(ws2, r, 7,  str(v['curr_max']),                                   fill=row_fill, align=CENTER)
    cell(ws2, r, 8,  curr_detail,                                          fill=row_fill)
    cell(ws2, r, 9,  GROUP_LABELS[v['next_grp']],                         fill=row_fill, align=CENTER)
    cell(ws2, r, 10, str(v['next_min']),                                   fill=row_fill, align=CENTER)
    cell(ws2, r, 11, next_detail,                                          fill=row_fill)
    cell(ws2, r, 12, overlap_days,                                         fill=row_fill, align=CENTER,
         font=Font(name='Arial', bold=True, color='DC2626', size=10))

    ws2.row_dimensions[r].height = 32
    r += 1

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 3+ — One sheet per violation type
# ═══════════════════════════════════════════════════════════════════════════════
sheet_fills = [RED_HDR, AMBER_HDR, PatternFill('solid', start_color='7C3AED'), GREEN_HDR]

for idx, (vtype, items) in enumerate(sorted(by_type.items(), key=lambda x: -len(x[1]))):
    safe_name = vtype.replace('→', 'to').replace('  ', ' ')[:31]
    ws3 = wb.create_sheet(safe_name)
    ws3.sheet_view.showGridLines = False
    ws3.freeze_panes = 'A3'

    fill = sheet_fills[idx % len(sheet_fills)]

    ws3.merge_cells(f'A1:{get_column_letter(len(cols))}1')
    c = ws3['A1']
    c.value = f'{vtype}  —  {len(items)} jobs'
    c.font = Font(name='Arial', bold=True, color='FFFFFF', size=12)
    c.fill = fill
    c.alignment = CENTER
    ws3.row_dimensions[1].height = 30

    for i, (title, width) in enumerate(cols, 1):
        hdr(ws3, 2, i, title, GRAY_HDR)
        ws3.column_dimensions[get_column_letter(i)].width = width
    ws3.row_dimensions[2].height = 28

    r = 3
    for v in sorted(items, key=lambda x: x['job_id']):
        overlap_days = (v['curr_max'] - v['next_min']).days
        curr_detail = ' | '.join(
            f"{ja.activity.name} [{ja.scheduled_date}] {float(ja.total_area)}ac"
            for ja in v['curr_acts']
        )
        next_detail = ' | '.join(
            f"{ja.activity.name} [{ja.scheduled_date}] {float(ja.total_area)}ac"
            for ja in v['next_acts']
        )
        row_fill = RED_BG if overlap_days > 3 else AMBER_BG

        cell(ws3, r, 1,  v['job_id'],   fill=row_fill, font=Font(name='Arial', bold=True, color='1D4ED8', size=10))
        cell(ws3, r, 2,  v['farmer'],   fill=row_fill, font=BLACK_BOLD)
        cell(ws3, r, 3,  v['farmer_phone'], fill=row_fill)
        cell(ws3, r, 4,  v['plot'],     fill=row_fill, align=CENTER)
        cell(ws3, r, 5,  f"{GROUP_LABELS[v['curr_grp']]} → {GROUP_LABELS[v['next_grp']]}", fill=row_fill, font=RED_BOLD)
        cell(ws3, r, 6,  GROUP_LABELS[v['curr_grp']], fill=row_fill, align=CENTER)
        cell(ws3, r, 7,  str(v['curr_max']), fill=row_fill, align=CENTER)
        cell(ws3, r, 8,  curr_detail,   fill=row_fill)
        cell(ws3, r, 9,  GROUP_LABELS[v['next_grp']], fill=row_fill, align=CENTER)
        cell(ws3, r, 10, str(v['next_min']), fill=row_fill, align=CENTER)
        cell(ws3, r, 11, next_detail,   fill=row_fill)
        cell(ws3, r, 12, overlap_days,  fill=row_fill, align=CENTER,
             font=Font(name='Arial', bold=True, color='DC2626', size=10))

        ws3.row_dimensions[r].height = 32
        r += 1

# ── Save ──────────────────────────────────────────────────────────────────────
out = 'activity_order_violations.xlsx'
wb.save(out)
print(f"Saved → {out}")