"""
Schedule Date Correction Preview  (optimised — 3 bulk queries)
===============================================================
Run from your Django project root:
    python compute_schedule_corrections.py           # preview only
    python compute_schedule_corrections.py --apply   # preview + write to DB

Produces: schedule_corrections_preview.xlsx

Fixes applied:
  1. Plots with no Pruning row are no longer skipped —
     the first activity (lowest phase_order) is used as the anchor instead.
  2. Suggested dates are never moved BACKWARD —
     if new_date < current_date the row is kept as-is with a clear reason.
  3. Reason column distinguishes "not moved backward" from genuine no-changes.
"""

import os, sys, django
from datetime import date, timedelta
from collections import defaultdict

DJANGO_SETTINGS = os.environ.get("DJANGO_SETTINGS_MODULE", "allocate.settings")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS)
try:
    django.setup()
except Exception as e:
    print(f"[ERROR] Django setup failed: {e}")
    sys.exit(1)

from django.db import connection
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

PRUNING_NAME = "Pruning (छाटणी)"

# ─────────────────────────────────────────────────────────────────────────────
# BULK QUERY 1 — all activities we care about
# ─────────────────────────────────────────────────────────────────────────────
ACTIVITIES_SQL = """
SELECT
    ja.id,
    ja.plot_id,
    ja.scheduled_date,
    ja.sales_date,
    ja.total_area,
    ja.allocation_status,
    ac.id                          AS activity_id,
    ac.name                        AS activity_name,
    ac.default_gap_days,
    COALESCE(asr.phase_order, 999) AS phase_order,
    p.name                         AS plot_name,
    f.farmer_name
FROM job_activities ja
JOIN activity_catalog ac
     ON ac.id = ja.activity_id
JOIN plots p
     ON p.id = ja.plot_id
JOIN farmers f
     ON f.farmer_id = p.farmer_id
LEFT JOIN tender_activityschedulerule asr
     ON asr.activity_id = ac.id
WHERE ja.plot_id IS NOT NULL
  AND ja.is_lost  = FALSE
  AND CAST(ja.total_area AS NUMERIC) > 0
ORDER BY ja.plot_id, COALESCE(asr.phase_order, 999), ja.scheduled_date
"""

# ─────────────────────────────────────────────────────────────────────────────
# BULK QUERY 2 — earliest allocation date per job_activity
# ─────────────────────────────────────────────────────────────────────────────
ALLOCATIONS_SQL = """
SELECT al.job_activity_id, MIN(al.allocated_date)
FROM   allocations al
JOIN   job_activities ja ON ja.id = al.job_activity_id
WHERE  ja.plot_id IS NOT NULL
  AND  ja.is_lost = FALSE
  AND  CAST(ja.total_area AS NUMERIC) > 0
GROUP BY al.job_activity_id
"""

# ─────────────────────────────────────────────────────────────────────────────
# BULK QUERY 3 — gap rules
# ─────────────────────────────────────────────────────────────────────────────
GLOBAL_GAP_SQL = "SELECT activity_id, gap_days FROM tender_activityschedulerule"

CLUSTER_GAP_SQL = """
SELECT pc.plot_id, casr.activity_id, casr.gap_days
FROM   tender_clusteractivityschedulerule casr
JOIN   plots_clusters pc ON pc.cluster_id = casr.cluster_id
"""


def fetch_all():
    with connection.cursor() as cur:
        cur.execute(ACTIVITIES_SQL)
        cols = [c[0] for c in cur.description]
        activities_raw = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute(ALLOCATIONS_SQL)
        alloc_map = {ja_id: d for ja_id, d in cur.fetchall()}

        cur.execute(GLOBAL_GAP_SQL)
        global_gap = {act_id: gap for act_id, gap in cur.fetchall()}

    cluster_gap = {}   # (plot_id, activity_id) -> gap_days
    try:
        with connection.cursor() as cur:
            cur.execute(CLUSTER_GAP_SQL)
            for plot_id, activity_id, gap_days in cur.fetchall():
                key = (plot_id, activity_id)
                # take smallest (most restrictive) if multiple clusters overlap
                if key not in cluster_gap or gap_days < cluster_gap[key]:
                    cluster_gap[key] = gap_days
    except Exception as e:
        print(f"[WARN] Cluster gap query failed ({e}) — using global rules only")

    return activities_raw, alloc_map, global_gap, cluster_gap


def get_gap(plot_id, activity_id, default_gap, global_gap, cluster_gap):
    # Explicit None checks — gap of 0 is valid, 'or' would skip it
    v = cluster_gap.get((plot_id, activity_id))
    if v is not None:
        return v
    v = global_gap.get(activity_id)
    if v is not None:
        return v
    return default_gap if default_gap is not None else 3


# ─────────────────────────────────────────────────────────────────────────────
# CORE LOGIC — pure Python, zero extra DB hits
# ─────────────────────────────────────────────────────────────────────────────
def compute_corrections(activities_raw, alloc_map, global_gap, cluster_gap):
    plots = defaultdict(list)
    for row in activities_raw:
        plots[row['plot_id']].append(row)

    rows_out = []
    _debug_printed = False   # print gap table for first plot only
    skipped_no_base = 0

    for plot_id, activities in plots.items():
        first      = activities[0]
        plot_label = f"{first['farmer_name']} — {first['plot_name']}"

        # ── Determine anchor ─────────────────────────────────────────────────
        # Prefer Pruning; fall back to first activity if no Pruning exists.
        all_prunings = [a for a in activities if a['activity_name'] == PRUNING_NAME]

        if all_prunings:
            # Use the latest Pruning row (highest id = most recently created/moved)
            pruning          = max(all_prunings, key=lambda a: a['id'])
            pruning_ids_skip = {a['id'] for a in all_prunings if a['id'] != pruning['id']}
            anchor_label     = "Pruning"
        else:
            # No Pruning — use the first activity (lowest phase_order) as anchor
            pruning          = activities[0]
            pruning_ids_skip = set()
            anchor_label     = f"First activity ({pruning['activity_name']})"

        pruning_alloc_date   = alloc_map.get(pruning['id'])
        pruning_is_allocated = pruning_alloc_date is not None
        pruning_gap          = get_gap(plot_id, pruning['activity_id'],
                                       pruning['default_gap_days'],
                                       global_gap, cluster_gap)

        # Determine anchor base date
        if pruning_is_allocated:
            pruning_base           = pruning_alloc_date
            pruning_corrected_date = None
        else:
            sched = pruning['scheduled_date']
            sales = pruning['sales_date']
            if sched and sales and sched < sales:
                pruning_base           = sales
                pruning_corrected_date = sales   # DATE CHANGE — anchor is behind sales date
            else:
                pruning_base           = sched   # already future — keep
                pruning_corrected_date = None

        if not pruning_base:
            skipped_no_base += 1
            continue

        # Cascade anchor starts at the anchor activity
        anchor_name = pruning['activity_name']
        anchor_gap  = pruning_gap
        anchor_date = pruning_base

        # DEBUG — print gap table for first plot only
        if not _debug_printed:
            _debug_printed = True
            print(f"\n[DEBUG] Plot: {plot_label}")
            print(f"  Anchor: {anchor_label}")
            print(f"  Anchor base={pruning_base}  anchor_gap={pruning_gap}  allocated={pruning_is_allocated}")
            for a in activities:
                g  = get_gap(plot_id, a['activity_id'], a['default_gap_days'], global_gap, cluster_gap)
                al = alloc_map.get(a['id'])
                marker = " <-- ANCHOR" if a["id"] == pruning["id"] else ""
                print(f"  id={a['id']:6d}  phase={a['phase_order']:3d}  gap={g:3d}  alloc={str(al):12s}  {a['activity_name']}{marker}")
            print()

        for a in activities:
            ja_id         = a['id']
            activity_name = a['activity_name']
            current_date  = a['scheduled_date']
            is_fully      = a['allocation_status'] == 'fully_allocated'
            alloc_date    = alloc_map.get(ja_id)
            is_allocated  = alloc_date is not None
            this_gap      = get_gap(plot_id, a['activity_id'],
                                    a['default_gap_days'], global_gap, cluster_gap)

            # ── Skip duplicate pruning rows ───────────────────────────────────
            if activity_name == PRUNING_NAME and ja_id in pruning_ids_skip:
                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'YES' if is_allocated else 'NO',
                    'current_date': current_date, 'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': 'Duplicate Pruning row — skipped (not anchor)',
                })
                continue

            # ── Fully allocated ───────────────────────────────────────────────
            if is_fully:
                if is_allocated:
                    anchor_name = activity_name
                    anchor_gap  = this_gap
                    anchor_date = alloc_date
                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'YES (Full)',
                    'current_date': current_date, 'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': f'Fully allocated on {alloc_date}',
                })
                continue

            # ── Anchor row itself ─────────────────────────────────────────────
            if ja_id == pruning['id']:
                if pruning_corrected_date:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'NO',
                        'current_date': current_date, 'new_date': pruning_corrected_date,
                        'change': 'DATE CHANGE',
                        'reason': (f'Unallocated & {current_date} < '
                                   f'sales {a["sales_date"]} → moved to sales date'),
                    })
                elif pruning_is_allocated:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': f'Allocated on {pruning_base} — anchor ({anchor_label})',
                    })
                else:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'NO',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': (f'Unallocated, {current_date} >= '
                                   f'sales {a["sales_date"]} — future, used as anchor ({anchor_label})'),
                    })
                continue

            # ── Partially allocated — no date change, update anchor ───────────
            if is_allocated:
                anchor_name = activity_name
                anchor_gap  = this_gap
                anchor_date = alloc_date
                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'YES',
                    'current_date': current_date, 'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': f'Allocated on {alloc_date}',
                })
                continue

            # ── Unallocated — compute correct date ────────────────────────────
            gap_delta    = this_gap - anchor_gap
            new_date     = anchor_date + timedelta(days=gap_delta)
            base_reason  = (f'Anchor: "{anchor_name}" {anchor_date} '
                            f'+ ({this_gap}−{anchor_gap})={gap_delta}d')

            # Never move a date BACKWARD — if suggested date < current, skip
            if current_date and new_date < current_date:
                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'NO',
                    'current_date': current_date, 'new_date': current_date,
                    'change': 'NO CHANGE',
                    'reason': (f'Suggested {new_date} < current {current_date} '
                               f'— not moved backward. ({base_reason})'),
                })
                continue

            changed = new_date != current_date
            rows_out.append({
                'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                'acres': float(a['total_area']), 'allocated': 'NO',
                'current_date': current_date, 'new_date': new_date,
                'change': 'DATE CHANGE' if changed else 'NO CHANGE',
                'reason': base_reason,
            })

    if skipped_no_base:
        print(f"[WARN] {skipped_no_base} plots skipped — no base date available (no scheduled_date and no sales_date)")

    return rows_out


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
def write_excel(rows, path):
    wb  = Workbook()
    ws  = wb.active
    ws.title = "Schedule Corrections"

    H_FILL  = PatternFill("solid", fgColor="1F4E79")
    H_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    C_FILL  = PatternFill("solid", fgColor="FFF2CC")   # yellow  = change
    N_FILL  = PatternFill("solid", fgColor="E2EFDA")   # green   = no change
    A_FILL  = PatternFill("solid", fgColor="DDEBF7")   # blue    = allocated
    B_FILL  = PatternFill("solid", fgColor="FCE4D6")   # orange  = not moved backward
    R_FONT  = Font(name="Arial", bold=True, color="C00000", size=10)
    G_FONT  = Font(name="Arial", color="375623", size=10)
    O_FONT  = Font(name="Arial", color="833C00", size=10)
    NRM     = Font(name="Arial", size=10)
    CTR     = Alignment(horizontal="center", vertical="center")
    LFT     = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    thin    = Side(style="thin", color="BFBFBF")
    BDR     = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers    = ["JA ID", "Plot", "Activity", "Acres", "Allocated?",
                  "Current Date", "New Date", "Change?", "Reason"]
    col_widths = [9, 36, 28, 8, 12, 18, 18, 15, 70]

    ws.row_dimensions[1].height = 26
    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = H_FONT; c.fill = H_FILL; c.alignment = CTR; c.border = BDR
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.freeze_panes = "A2"

    for ri, row in enumerate(rows, 2):
        change  = row['change']
        alloc   = row['allocated']
        reason  = row.get('reason', '')
        is_back = 'not moved backward' in reason

        fill = (C_FILL if change == 'DATE CHANGE' else
                B_FILL if is_back else
                A_FILL if 'YES' in alloc else N_FILL)

        vals = [row.get('ja_id', ''), row['plot'], row['activity'],
                row['acres'], alloc,
                row['current_date'], row['new_date'], change, reason]
        ws.row_dimensions[ri].height = 16

        for ci, val in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill = fill; c.border = BDR
            if ci in (6, 7) and isinstance(val, date):
                c.number_format = "DD-MMM-YYYY"; c.alignment = CTR
            elif ci in (1, 4, 5):
                c.alignment = CTR; c.font = NRM
            elif ci == 8:
                c.alignment = CTR
                if change == 'DATE CHANGE':
                    c.font = R_FONT
                elif is_back:
                    c.font = O_FONT
                else:
                    c.font = G_FONT
            else:
                c.alignment = LFT; c.font = NRM

    total    = len(rows)
    changed  = sum(1 for r in rows if r['change'] == 'DATE CHANGE')
    backward = sum(1 for r in rows if 'not moved backward' in (r.get('reason') or ''))
    no_chg   = total - changed

    summary = [
        ("Total",            total,    "000000"),
        ("Date Changes",     changed,  "C00000"),
        ("Not moved back",   backward, "833C00"),
        ("No change",        no_chg,   "375623"),
    ]
    for r, (label, val, color) in enumerate(summary, 1):
        ws.cell(row=r, column=11, value=label).font = Font(name="Arial", bold=True, color=color)
        ws.cell(row=r, column=12, value=val).font   = Font(name="Arial", bold=True, color=color)
    ws.column_dimensions['K'].width = 18
    ws.column_dimensions['L'].width = 8

    wb.save(path)
    print(f"[OK] {path}")
    print(f"     {total} rows  |  {changed} date changes  |  "
          f"{backward} not moved backward  |  {no_chg - backward} genuine no-changes")


# ─────────────────────────────────────────────────────────────────────────────
# APPLY TO DB
# ─────────────────────────────────────────────────────────────────────────────
def apply_corrections(rows):
    """
    Bulk update scheduled_date for all DATE CHANGE rows.
    Single transaction — rolls back everything on any error.
    """
    to_update = [
        (r['new_date'], r['ja_id'])
        for r in rows
        if r['change'] == 'DATE CHANGE'
        and r.get('ja_id')
        and r.get('new_date')
    ]

    if not to_update:
        print("Nothing to update.")
        return

    print(f"Updating {len(to_update)} job_activities...")
    try:
        with connection.cursor() as cur:
            cur.executemany(
                "UPDATE job_activities SET scheduled_date = %s, updated_at = NOW() WHERE id = %s",
                to_update,
            )
        print(f"[OK] {len(to_update)} rows updated successfully.")
    except Exception as e:
        print(f"[ERROR] Update failed, rolled back: {e}")
        connection.rollback()
        raise


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Schedule date correction tool")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply date corrections to DB. Without this flag only preview XL is generated.",
    )
    args = parser.parse_args()

    CHECK_TABLES = [
        "job_activities", "activity_catalog", "plots", "farmers",
        "allocations", "tender_activityschedulerule",
        "tender_clusteractivityschedulerule", "plots_clusters",
    ]
    print("Checking table names...")
    all_ok = True
    with connection.cursor() as cur:
        for t in CHECK_TABLES:
            try:
                cur.execute(f"SELECT 1 FROM {t} LIMIT 1")
                print(f"  OK  {t}")
            except Exception:
                connection.rollback()
                print(f"  FAIL {t}  <- wrong name, fix in SQL constants above")
                all_ok = False
    if not all_ok:
        print("Fix table names above then re-run.")
        sys.exit(1)

    print("\nFetching data (3 queries)...")
    activities_raw, alloc_map, global_gap, cluster_gap = fetch_all()
    total_plots = len(set(r['plot_id'] for r in activities_raw))
    no_pruning  = sum(
        1 for plot_acts in defaultdict(list, {
            r['plot_id']: [] for r in activities_raw
        }).values()
    )
    # Recount properly
    plot_buckets = defaultdict(list)
    for r in activities_raw:
        plot_buckets[r['plot_id']].append(r)
    plots_no_pruning = sum(
        1 for acts in plot_buckets.values()
        if not any(a['activity_name'] == PRUNING_NAME for a in acts)
    )
    print(f"  {len(activities_raw)} activities  |  {total_plots} plots loaded")
    print(f"  {total_plots - plots_no_pruning} plots have Pruning  |  "
          f"{plots_no_pruning} plots use first-activity fallback anchor")

    print("\nComputing corrections (pure Python)...")
    rows = compute_corrections(activities_raw, alloc_map, global_gap, cluster_gap)

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "schedule_corrections_preview.xlsx",
    )
    write_excel(rows, out)

    if args.apply:
        print()
        changed_count = sum(1 for r in rows if r['change'] == 'DATE CHANGE')
        confirm = input(
            f"Apply {changed_count} date changes to DB? (yes/no): "
        ).strip().lower()
        if confirm == "yes":
            apply_corrections(rows)
        else:
            print("Aborted — no changes made.")
    else:
        changed_count = sum(1 for r in rows if r['change'] == 'DATE CHANGE')
        print(f"\nPreview only. Review the XL ({changed_count} changes). "
              f"Run with --apply to update DB.")