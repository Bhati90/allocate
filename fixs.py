"""
Schedule Date Correction Preview
=================================
Run from your Django project root:
    python compute_schedule_corrections.py

Or with env override:
    DATABASE_URL=postgres://... python compute_schedule_corrections.py

Produces: schedule_corrections_preview.xlsx
"""

import os
import sys
import django
from datetime import date, timedelta

# ── Django setup ─────────────────────────────────────────────────────────────
# Adjust the settings module path to match your project
DJANGO_SETTINGS = os.environ.get("DJANGO_SETTINGS_MODULE", "allocate.settings")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS)

try:
    django.setup()
except Exception as e:
    print(f"[ERROR] Django setup failed: {e}")
    print("Run this script from your Django project root, or set DJANGO_SETTINGS_MODULE.")
    sys.exit(1)

# ── Imports (after django setup) ──────────────────────────────────────────────
from django.db.models import Prefetch, Min
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# Import your models
from tender.models import (   # ← change app name if different
    Plot, JobActivity, ActivityScheduleRule,
    ClusterActivityScheduleRule, Allocation
)

PRUNING_NAME = "Pruning (छाटणी)"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Build gap_days lookup
#   gap_days[(cluster_id, activity_id)] = N   (cluster override)
#   gap_days[(None, activity_id)]       = N   (global rule)
# ─────────────────────────────────────────────────────────────────────────────
def build_gap_lookup():
    global_rules = {r.activity_id: r.gap_days
                    for r in ActivityScheduleRule.objects.select_related('activity')}
    cluster_rules = {}
    for r in ClusterActivityScheduleRule.objects.select_related('cluster', 'activity'):
        cluster_rules[(r.cluster_id, r.activity_id)] = r.gap_days
    return global_rules, cluster_rules


def get_gap(activity_id, cluster_ids, global_rules, cluster_rules, default_gap):
    """Cluster rule first, then global, then activity default."""
    for cid in cluster_ids:
        if (cid, activity_id) in cluster_rules:
            return cluster_rules[(cid, activity_id)]
    if activity_id in global_rules:
        return global_rules[activity_id]
    return default_gap


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: For each plot, compute corrected dates
# ─────────────────────────────────────────────────────────────────────────────
def compute_corrections():
    global_rules, cluster_rules = build_gap_lookup()

    # Fetch all relevant activities with allocations prefetched
    activities_qs = (
        JobActivity.objects
        .filter(is_lost=False)
        .exclude(total_area=0)
        .select_related('activity', 'plot', 'job')
        .prefetch_related(
            'plot__clusters',
            Prefetch(
                'allocations',
                queryset=Allocation.objects.order_by('allocated_date'),
                to_attr='all_allocations'
            )
        )
        .order_by('plot_id', 'activity__global_schedule__phase_order', 'scheduled_date')
    )

    # Group by plot
    from collections import defaultdict
    plots_activities = defaultdict(list)
    for ja in activities_qs:
        if ja.plot_id:
            plots_activities[ja.plot_id].append(ja)

    rows = []

    for plot_id, activities in plots_activities.items():
        plot = activities[0].plot
        cluster_ids = list(plot.clusters.values_list('id', flat=True))

        # Sort by phase_order, fallback to scheduled_date
        def sort_key(ja):
            try:
                return (ja.activity.global_schedule.phase_order, ja.scheduled_date or date.max)
            except AttributeError:
                return (999, ja.scheduled_date or date.max)

        activities.sort(key=sort_key)

        # Find Pruning activity
        pruning_ja = next(
            (ja for ja in activities if ja.activity.name == PRUNING_NAME), None
        )

        # Determine Pruning's effective base date
        # If Pruning has allocations → use earliest allocated_date as base
        # If Pruning unallocated and scheduled_date is before sales_date → base = sales_date
        # If Pruning unallocated otherwise → base = scheduled_date (or None)

        if pruning_ja is None:
            # No pruning on this plot — skip (can't anchor)
            continue

        pruning_allocs = pruning_ja.all_allocations
        pruning_is_allocated = bool(pruning_allocs)

        pruning_scheduled = pruning_ja.scheduled_date
        pruning_sales     = pruning_ja.sales_date

        if pruning_is_allocated:
            # Allocated → use earliest allocated_date as anchor
            pruning_base           = min(a.allocated_date for a in pruning_allocs)
            pruning_corrected_date = None   # no change to pruning row
        else:
            # Unallocated:
            #   - scheduled < sales_date → push to sales_date (date change)
            #   - scheduled >= sales_date (future) → keep as-is, just cascade downstream
            if pruning_scheduled and pruning_sales and pruning_scheduled < pruning_sales:
                pruning_base           = pruning_sales
                pruning_corrected_date = pruning_sales   # DATE CHANGE row
            else:
                pruning_base           = pruning_scheduled   # already fine
                pruning_corrected_date = None                # no change

        if pruning_base is None:
            continue  # no date at all — can't anchor

        pruning_gap = get_gap(
            pruning_ja.activity_id, cluster_ids,
            global_rules, cluster_rules,
            pruning_ja.activity.default_gap_days
        )

        # Always anchor cascade from Pruning (whether allocated or not).
        # If a later activity is also allocated, it will override this tracker.
        last_allocated_ja   = pruning_ja
        last_allocated_gap  = pruning_gap
        last_allocated_date = pruning_base

        for ja in activities:
            activity_name = ja.activity.name
            current_date = ja.scheduled_date
            allocated_date_display = None
            reason = ""

            ja_allocs = ja.all_allocations
            ja_is_allocated = bool(ja_allocs)

            # Skip fully allocated
            if ja.allocation_status == 'fully_allocated':
                rows.append({
                    'plot': f"{plot.farmer.farmer_name} — {plot.name}",
                    'activity': activity_name,
                    'acres': float(ja.total_area),
                    'allocated': 'YES (Full)',
                    'current_date': current_date,
                    'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': 'Fully allocated — skipped',
                })
                if ja_is_allocated:
                    last_allocated_ja = ja
                    last_allocated_gap = get_gap(
                        ja.activity_id, cluster_ids,
                        global_rules, cluster_rules,
                        ja.activity.default_gap_days
                    )
                    last_allocated_date = min(a.allocated_date for a in ja_allocs)
                continue

            # This is Pruning itself
            if activity_name == PRUNING_NAME:
                if pruning_corrected_date:
                    reason_text = (
                        f'Unallocated & scheduled {current_date} is before '
                        f'sales date {ja.sales_date} → moved to sales date'
                    )
                    new_d  = pruning_corrected_date
                    change = 'DATE CHANGE'
                elif pruning_is_allocated:
                    reason_text = f'Allocated (base date: {pruning_base})'
                    new_d  = current_date
                    change = 'NO CHANGE'
                else:
                    reason_text = (
                        f'Unallocated but scheduled {current_date} >= '
                        f'sales {ja.sales_date} — date already future, used as base'
                    )
                    new_d  = current_date
                    change = 'NO CHANGE'

                rows.append({
                    'plot': f"{plot.farmer.farmer_name} — {plot.name}",
                    'activity': activity_name,
                    'acres': float(ja.total_area),
                    'allocated': 'YES' if pruning_is_allocated else 'NO',
                    'current_date': current_date,
                    'new_date': new_d,
                    'change': change,
                    'reason': reason_text,
                })
                continue

            # For all other activities
            this_gap = get_gap(
                ja.activity_id, cluster_ids,
                global_rules, cluster_rules,
                ja.activity.default_gap_days
            )

            if ja_is_allocated:
                # Already allocated — no date change, but update last allocated tracker
                alloc_date = min(a.allocated_date for a in ja_allocs)
                last_allocated_ja = ja
                last_allocated_gap = this_gap
                last_allocated_date = alloc_date
                rows.append({
                    'plot': f"{plot.farmer.farmer_name} — {plot.name}",
                    'activity': activity_name,
                    'acres': float(ja.total_area),
                    'allocated': 'YES',
                    'current_date': current_date,
                    'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': f'Already allocated on {alloc_date}',
                })
                continue

            # Unallocated — cascade from last allocated (always set, minimum = Pruning)
            gap_delta = this_gap - last_allocated_gap
            new_date  = last_allocated_date + timedelta(days=gap_delta)
            reason    = (
                f'Anchor: "{last_allocated_ja.activity.name}" '
                f'on {last_allocated_date} + ({this_gap}−{last_allocated_gap})={gap_delta}d'
            )

            changed = (new_date != current_date)
            rows.append({
                'plot': f"{plot.farmer.farmer_name} — {plot.name}",
                'activity': activity_name,
                'acres': float(ja.total_area),
                'allocated': 'NO',
                'current_date': current_date,
                'new_date': new_date,
                'change': 'DATE CHANGE' if changed else 'NO CHANGE',
                'reason': reason,
            })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Write Excel
# ─────────────────────────────────────────────────────────────────────────────
def write_excel(rows, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule Corrections"

    # ── Styles ─────────────────────────────────────────────────────────────
    HEADER_FILL   = PatternFill("solid", fgColor="1F4E79")
    HEADER_FONT   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    CHANGED_FILL  = PatternFill("solid", fgColor="FFF2CC")   # yellow
    NOCHANGE_FILL = PatternFill("solid", fgColor="E2EFDA")   # light green
    ALLOC_FILL    = PatternFill("solid", fgColor="DDEBF7")   # light blue
    SKIP_FILL     = PatternFill("solid", fgColor="F2F2F2")   # grey
    RED_FONT      = Font(name="Arial", bold=True, color="C00000", size=10)
    GREEN_FONT    = Font(name="Arial", color="375623", size=10)
    NORMAL_FONT   = Font(name="Arial", size=10)
    CENTER        = Alignment(horizontal="center", vertical="center")
    LEFT          = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    thin_side     = Side(style="thin", color="BFBFBF")
    BORDER        = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # ── Headers ─────────────────────────────────────────────────────────────
    headers = [
        "Plot (Farmer — Plot Name)",
        "Activity",
        "Acres",
        "Allocated?",
        "Current Scheduled Date",
        "New Scheduled Date",
        "Change?",
        "Reason / Logic",
    ]
    col_widths = [38, 30, 8, 12, 22, 22, 14, 60]

    ws.row_dimensions[1].height = 28
    for ci, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = CENTER
        cell.border    = BORDER
        ws.column_dimensions[get_column_letter(ci)].width = w

    # ── Freeze header ───────────────────────────────────────────────────────
    ws.freeze_panes = "A2"

    # ── Data rows ───────────────────────────────────────────────────────────
    for ri, row in enumerate(rows, start=2):
        change   = row['change']
        alloc    = row['allocated']

        if change == 'DATE CHANGE':
            row_fill = CHANGED_FILL
        elif 'Full' in alloc or 'YES' in alloc:
            row_fill = ALLOC_FILL
        elif 'skipped' in row['reason'].lower() or 'lost' in row['reason'].lower():
            row_fill = SKIP_FILL
        else:
            row_fill = NOCHANGE_FILL

        values = [
            row['plot'],
            row['activity'],
            row['acres'],
            alloc,
            row['current_date'],
            row['new_date'],
            change,
            row['reason'],
        ]
        ws.row_dimensions[ri].height = 18
        for ci, val in enumerate(values, start=1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill   = row_fill
            cell.border = BORDER

            if ci in (5, 6) and isinstance(val, date):
                cell.number_format = "DD-MMM-YYYY"
                cell.alignment = CENTER
            elif ci in (3, 4):
                cell.alignment = CENTER
            elif ci in (7,):
                cell.alignment = CENTER
                if change == 'DATE CHANGE':
                    cell.font = RED_FONT
                else:
                    cell.font = GREEN_FONT
            else:
                cell.alignment = LEFT
                cell.font = NORMAL_FONT

    # ── Summary block (top right) ────────────────────────────────────────────
    total       = len(rows)
    changed     = sum(1 for r in rows if r['change'] == 'DATE CHANGE')
    no_change   = total - changed

    ws.cell(row=1,  column=10, value="Summary").font = Font(name="Arial", bold=True, size=11)
    ws.cell(row=2,  column=10, value="Total activities").font = NORMAL_FONT
    ws.cell(row=2,  column=11, value=total)
    ws.cell(row=3,  column=10, value="Date changes").font = Font(name="Arial", bold=True, color="C00000")
    ws.cell(row=3,  column=11, value=changed).font = Font(name="Arial", bold=True, color="C00000")
    ws.cell(row=4,  column=10, value="No change").font = Font(name="Arial", color="375623")
    ws.cell(row=4,  column=11, value=no_change).font = Font(name="Arial", color="375623")
    ws.column_dimensions['J'].width = 22
    ws.column_dimensions['K'].width = 10

    # ── Legend ───────────────────────────────────────────────────────────────
    legend = [
        ("DATE CHANGE",    CHANGED_FILL,  "Yellow — scheduled date will change"),
        ("Allocated",       ALLOC_FILL,   "Blue — already allocated, no touch"),
        ("No change",       NOCHANGE_FILL, "Green — date already correct"),
    ]
    for li, (label, fill, desc) in enumerate(legend, start=6):
        c1 = ws.cell(row=li, column=10, value=label)
        c1.fill = fill
        c1.font = NORMAL_FONT
        c1.border = BORDER
        c2 = ws.cell(row=li, column=11, value=desc)
        c2.font = NORMAL_FONT

    wb.save(path)
    print(f"[OK] Saved: {path}  ({total} rows, {changed} date changes)")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Computing schedule corrections...")
    rows = compute_corrections()
    out_path = os.path.join(os.path.dirname(__file__), "schedule_corrections_preview.xlsx")
    write_excel(rows, out_path)