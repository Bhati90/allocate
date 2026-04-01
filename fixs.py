"""
Schedule Date Correction Preview  (optimised — 3 bulk queries)
===============================================================
Run from your Django project root:
    python compute_schedule_corrections.py           # preview only
    python compute_schedule_corrections.py --apply   # preview + write to DB

Produces: schedule_corrections_preview.xlsx

Logic:
  ┌─────────────────────────────────────────────────────────────────┐
  │  gap_days in ActivityScheduleRule is ABSOLUTE FROM PRUNING DATE │
  │  i.e. "this activity happens gap_days after pruning"            │
  └─────────────────────────────────────────────────────────────────┘

  PRUNING PRESENT:
    - Anchor base = pruning alloc_date (if allocated) OR scheduled_date
    - Pruning scheduled_date is NEVER moved backward, no matter what
    - For each other activity:
        new_date = pruning_base + gap_days  (absolute, not relative)
    - Backward movement IS allowed for non-pruning activities when the
      suggested date is earlier than current (dates moved too far forward)

  PRUNING NOT PRESENT:
    - First activity on the plot (lowest phase_order) becomes the anchor
    - base_date = its alloc_date if allocated, else its scheduled_date
    - For each subsequent unallocated activity:
        rel_gap  = this_activity.gap_days - anchor.gap_days
        new_date = base_date + rel_gap
    - This correctly chains: Corden(gap=3) → Shoot(gap=10) = Corden + 7d
    - Anchor row itself is never moved backward

  ALLOCATED (any status):
    - Use earliest alloc_date as the real "when it happened" base
    - Never change its scheduled_date
    - Update cascade anchor to alloc_date so downstream is correct
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
    COALESCE(asr.gap_days, ac.default_gap_days, 3) AS rule_gap_days,
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
                if key not in cluster_gap or gap_days < cluster_gap[key]:
                    cluster_gap[key] = gap_days
    except Exception as e:
        print(f"[WARN] Cluster gap query failed ({e}) — using global rules only")

    return activities_raw, alloc_map, global_gap, cluster_gap


def get_gap(plot_id, activity_id, default_gap, global_gap, cluster_gap):
    """
    Returns the absolute gap_days from pruning date for this activity.
    Explicit None checks — gap of 0 is valid.
    """
    v = cluster_gap.get((plot_id, activity_id))
    if v is not None:
        return v
    v = global_gap.get(activity_id)
    if v is not None:
        return v
    return default_gap if default_gap is not None else 3


# ─────────────────────────────────────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def compute_corrections(activities_raw, alloc_map, global_gap, cluster_gap):
    plots = defaultdict(list)
    for row in activities_raw:
        plots[row['plot_id']].append(row)

    rows_out = []
    _debug_printed = False
    skipped_no_base = 0

    for plot_id, activities in plots.items():
        first      = activities[0]
        plot_label = f"{first['farmer_name']} — {first['plot_name']}"

        # ── Identify pruning rows ────────────────────────────────────────────
        all_prunings = [a for a in activities if a['activity_name'] == PRUNING_NAME]
        has_pruning  = bool(all_prunings)

        # ── CASE A: Pruning exists ───────────────────────────────────────────
        if has_pruning:
            # Anchor = pruning row with the LATEST alloc_date (most recent work done).
            # If none are allocated, fall back to the pruning with the highest ID.
            allocated_prunings = [a for a in all_prunings if alloc_map.get(a['id']) is not None]
            if allocated_prunings:
                pruning = max(allocated_prunings, key=lambda a: alloc_map[a['id']])
            else:
                pruning = max(all_prunings, key=lambda a: a['id'])

            pruning_ids_skip = {a['id'] for a in all_prunings if a['id'] != pruning['id']}

            pruning_alloc_date   = alloc_map.get(pruning['id'])
            pruning_is_allocated = pruning_alloc_date is not None

            # Pruning base: prefer alloc_date over scheduled_date
            if pruning_is_allocated:
                pruning_base = pruning_alloc_date
            else:
                pruning_base = pruning['scheduled_date']

            if not pruning_base:
                skipped_no_base += 1
                continue

            # DEBUG for first plot
            if not _debug_printed:
                _debug_printed = True
                print(f"\n[DEBUG] Plot: {plot_label}  (Pruning present)")
                print(f"  Pruning base={pruning_base}  allocated={pruning_is_allocated}")
                for a in activities:
                    g  = get_gap(plot_id, a['activity_id'], a['default_gap_days'], global_gap, cluster_gap)
                    al = alloc_map.get(a['id'])
                    marker = " <-- PRUNING ANCHOR" if a["id"] == pruning["id"] else ""
                    print(f"  id={a['id']:6d}  phase={a['phase_order']:3d}  abs_gap={g:3d}d  alloc={str(al):12s}  {a['activity_name']}{marker}")
                print()

            for a in activities:
                ja_id         = a['id']
                activity_name = a['activity_name']
                current_date  = a['scheduled_date']
                is_fully      = a['allocation_status'] == 'fully_allocated'
                alloc_date    = alloc_map.get(ja_id)
                is_allocated  = alloc_date is not None
                abs_gap       = get_gap(plot_id, a['activity_id'],
                                        a['default_gap_days'], global_gap, cluster_gap)

                # ── Skip duplicate pruning rows ──────────────────────────────
                if activity_name == PRUNING_NAME and ja_id in pruning_ids_skip:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES' if is_allocated else 'NO',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': 'Duplicate Pruning row — skipped (not anchor)',
                    })
                    continue

                # ── Fully allocated — never touch ────────────────────────────
                if is_fully:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES (Full)',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': f'Fully allocated on {alloc_date}',
                    })
                    continue

                # ── Partially allocated — use alloc_date, no date change ─────
                if is_allocated:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': f'Allocated on {alloc_date} — date preserved, used as cascade reference',
                    })
                    continue

                # ── Pruning anchor row itself (unallocated) ──────────────────
                if ja_id == pruning['id']:
                    # NEVER move pruning backward — lock it as-is
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'NO',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': 'Pruning anchor — never moved backward (locked)',
                    })
                    continue

                # ── Unallocated non-pruning: absolute gap from pruning base ──
                new_date    = pruning_base + timedelta(days=abs_gap)
                changed     = new_date != current_date
                base_reason = (f'Pruning base {pruning_base} + abs_gap {abs_gap}d '
                               f'= {new_date}')

                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'NO',
                    'current_date': current_date, 'new_date': new_date,
                    'change': 'DATE CHANGE' if changed else 'NO CHANGE',
                    'reason': base_reason,
                })

        # ── CASE B: No pruning — relative cascade from first activity ────────
        else:
            # Anchor = first activity on the plot (lowest phase_order / earliest in list)
            # activities list is already sorted by phase_order, scheduled_date
            base_act          = activities[0]
            base_alloc_date   = alloc_map.get(base_act['id'])
            base_is_allocated = base_alloc_date is not None

            # Prefer alloc_date over scheduled_date for anchor
            base_date  = base_alloc_date if base_is_allocated else base_act['scheduled_date']
            base_label = (
                f"first activity ({base_act['activity_name']}) alloc={base_alloc_date}"
                if base_is_allocated
                else f"first activity ({base_act['activity_name']}) sched={base_act['scheduled_date']}"
            )

            if not base_date:
                skipped_no_base += 1
                continue

            # gap_days of the anchor activity (the "pseudo-pruning" offset)
            # rel_gap for any activity = its gap_days - anchor's gap_days
            # e.g. Corden gap=3, Shoot gap=10 → Shoot = Corden_date + (10-3) = +7d
            base_gap = get_gap(
                plot_id, base_act['activity_id'],
                base_act['default_gap_days'], global_gap, cluster_gap
            )

            if not _debug_printed:
                _debug_printed = True
                print(f"\n[DEBUG] Plot: {plot_label}  (NO Pruning — first-activity anchor)")
                print(f"  Base: {base_label}  base_gap={base_gap}d")
                for a in activities:
                    al = alloc_map.get(a['id'])
                    g  = get_gap(plot_id, a['activity_id'],
                                 a['default_gap_days'], global_gap, cluster_gap)
                    rel = g - base_gap
                    marker = " <-- ANCHOR" if a['id'] == base_act['id'] else ""
                    print(f"  id={a['id']:6d}  phase={a['phase_order']:3d}  "
                          f"abs_gap={g:3d}d  rel_gap={rel:+d}d  alloc={str(al):12s}  "
                          f"{a['activity_name']}{marker}")
                print()

            for a in activities:
                ja_id         = a['id']
                activity_name = a['activity_name']
                current_date  = a['scheduled_date']
                is_fully      = a['allocation_status'] == 'fully_allocated'
                alloc_date    = alloc_map.get(ja_id)
                is_allocated  = alloc_date is not None
                abs_gap       = get_gap(plot_id, a['activity_id'],
                                        a['default_gap_days'], global_gap, cluster_gap)

                # ── Fully allocated — no touch ───────────────────────────────
                if is_fully:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES (Full)',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': f'Fully allocated on {alloc_date}',
                    })
                    continue

                # ── Partially allocated — no date change, note it ────────────
                if is_allocated:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'YES',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': f'Allocated on {alloc_date} — date preserved, used as cascade reference',
                    })
                    continue

                # ── Anchor row itself (unallocated) — never move backward ────
                if ja_id == base_act['id']:
                    rows_out.append({
                        'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                        'acres': float(a['total_area']), 'allocated': 'NO',
                        'current_date': current_date, 'new_date': current_date,
                        'change': 'NO CHANGE',
                        'reason': 'First-activity anchor — date locked (no pruning fallback)',
                    })
                    continue

                # ── Unallocated non-anchor: relative gap from base ───────────
                # rel_gap = this activity's abs gap minus anchor's abs gap
                # → gives actual days between anchor and this activity
                rel_gap     = abs_gap - base_gap
                new_date    = base_date + timedelta(days=rel_gap)
                changed     = new_date != current_date
                base_reason = (
                    f'No-pruning relative: base={base_date} '
                    f'+ (abs_gap {abs_gap} - base_gap {base_gap}) '
                    f'= +{rel_gap}d → {new_date}'
                )

                rows_out.append({
                    'ja_id': ja_id, 'plot': plot_label, 'activity': activity_name,
                    'acres': float(a['total_area']), 'allocated': 'NO',
                    'current_date': current_date, 'new_date': new_date,
                    'change': 'DATE CHANGE' if changed else 'NO CHANGE',
                    'reason': base_reason,
                })

    if skipped_no_base:
        print(f"[WARN] {skipped_no_base} plots skipped — no base date available")

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
    BK_FILL = PatternFill("solid", fgColor="FCE4D6")   # orange  = moved backward
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
    col_widths = [9, 36, 28, 8, 12, 18, 18, 15, 80]

    ws.row_dimensions[1].height = 26
    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = H_FONT; c.fill = H_FILL; c.alignment = CTR; c.border = BDR
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.freeze_panes = "A2"

    for ri, row in enumerate(rows, 2):
        change   = row['change']
        alloc    = row['allocated']
        cur_dt   = row.get('current_date')
        new_dt   = row.get('new_date')
        moved_bk = (change == 'DATE CHANGE'
                    and isinstance(cur_dt, date) and isinstance(new_dt, date)
                    and new_dt < cur_dt)

        fill = (BK_FILL if moved_bk else
                C_FILL  if change == 'DATE CHANGE' else
                A_FILL  if 'YES' in alloc else N_FILL)

        vals = [row.get('ja_id', ''), row['plot'], row['activity'],
                row['acres'], alloc,
                cur_dt, new_dt, change, row.get('reason', '')]
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
                    c.font = O_FONT if moved_bk else R_FONT
                else:
                    c.font = G_FONT
            else:
                c.alignment = LFT; c.font = NRM

    total    = len(rows)
    changed  = sum(1 for r in rows if r['change'] == 'DATE CHANGE')
    moved_bk = sum(
        1 for r in rows
        if r['change'] == 'DATE CHANGE'
        and isinstance(r.get('current_date'), date)
        and isinstance(r.get('new_date'), date)
        and r['new_date'] < r['current_date']
    )
    moved_fw = changed - moved_bk
    no_chg   = total - changed

    summary = [
        ("Total",              total,    "000000"),
        ("Date Changes",       changed,  "C00000"),
        ("  → Moved forward",  moved_fw, "C00000"),
        ("  → Moved backward", moved_bk, "833C00"),
        ("No change",          no_chg,   "375623"),
    ]
    for r, (label, val, color) in enumerate(summary, 1):
        ws.cell(row=r, column=11, value=label).font = Font(name="Arial", bold=True, color=color)
        ws.cell(row=r, column=12, value=val).font   = Font(name="Arial", bold=True, color=color)
    ws.column_dimensions['K'].width = 22
    ws.column_dimensions['L'].width = 8

    wb.save(path)
    print(f"[OK] {path}")
    print(f"     {total} rows  |  {changed} date changes  "
          f"({moved_fw} forward / {moved_bk} backward)  |  {no_chg} no-change")


# ─────────────────────────────────────────────────────────────────────────────
# APPLY TO DB
# ─────────────────────────────────────────────────────────────────────────────
def apply_corrections(rows):
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

    plot_buckets = defaultdict(list)
    for r in activities_raw:
        plot_buckets[r['plot_id']].append(r)
    plots_no_pruning = sum(
        1 for acts in plot_buckets.values()
        if not any(a['activity_name'] == PRUNING_NAME for a in acts)
    )
    print(f"  {len(activities_raw)} activities  |  {total_plots} plots loaded")
    print(f"  {total_plots - plots_no_pruning} plots have Pruning  |  "
          f"{plots_no_pruning} plots use relative-cascade fallback (no pruning)")

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