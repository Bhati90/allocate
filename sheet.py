# Activity Scheduling Sheet Generator
# Run:    python sheet.py
# Output: activity_schedule.xlsx
#
# CASCADE RULE — pure Excel formulas, zero VBA:
#
#   A hidden sheet "_Offsets" holds one row per Plot ID:
#       Plot ID  |  Date Shift (days)
#
#   The "Projected Date" column on the main sheet is a formula:
#       IF row is Pending  →  base_projected_date + VLOOKUP(plot_id, _Offsets, 2, 0)
#       IF row is Allocated/Completed/etc  →  base_projected_date  (locked, unchanged)
#
#   To cascade a plot's pending dates:
#       1. Open the "📅 Date Adjustments" sheet (visible, user-facing)
#       2. Find the plot row — type a positive or negative number in "Shift Days"
#       3. ALL pending rows on that plot instantly shift by that many days
#       4. Reset to 0 to undo
#
#   The base projected date is stored in a hidden column ("_Base Projected Date")
#   so the formula always offsets from the original Python-calculated value.

import os, sys, django
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")
django.setup()

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from tender.models import (
    Plot, JobActivity, ActivityScheduleRule,
    ClusterActivityScheduleRule, Allocation, ActivityCatalog,
    Mukkadam,
)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_gap_days(activity, clusters):
    for c in clusters:
        rule = ClusterActivityScheduleRule.objects.filter(cluster=c, activity=activity).first()
        if rule:
            return rule.gap_days
    rule = ActivityScheduleRule.objects.filter(activity=activity).first()
    if rule:
        return rule.gap_days
    return activity.default_gap_days or 3


def phase_order(activity):
    rule = ActivityScheduleRule.objects.filter(activity=activity).first()
    return rule.phase_order if rule else 0


def best_alloc(ja):
    allocs = list(ja.allocations.all())
    if not allocs:
        return None
    completed = [a for a in allocs if a.work_status == "completed"]
    if completed:
        return max(completed, key=lambda a: a.allocated_date)
    return max(allocs, key=lambda a: a.allocated_date)


def work_status_label(ja):
    if ja.is_lost:
        return "Lost"
    alloc = best_alloc(ja)
    if not alloc:
        return ja.allocation_status.replace("_", " ").title()
    ws = alloc.work_status
    if ws == "completed":   return "Completed"
    if ws == "in_progress": return "In Progress"
    return ws.replace("_", " ").title()


def determine_anchor(jas):
    candidates = []
    for ja in jas:
        allocs = list(ja.allocations.all())
        if allocs:
            best = max(allocs, key=lambda a: a.allocated_date)
            candidates.append((ja, best.allocated_date))
        elif ja.is_lost:
            lost_date = ja.updated_at.date() if ja.updated_at else ja.scheduled_date
            if lost_date:
                candidates.append((ja, lost_date))
    if candidates:
        bj, bd = max(candidates, key=lambda x: x[1])
        return bj, bd, bj.activity
    scheduled = [(ja, ja.scheduled_date) for ja in jas if ja.scheduled_date]
    if scheduled:
        fj, fd = min(scheduled, key=lambda x: phase_order(x[0].activity))
        return fj, fd, fj.activity
    return None, None, None


# ─────────────────────────────────────────────────────────────────────────────
# ROW BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_rows(plot):
    clusters = list(plot.clusters.all())
    jas = list(
        JobActivity.objects
        .filter(plot=plot)
        .select_related("activity", "job", "job__farmer")
        .prefetch_related("allocations", "allocations__mukkadam")
    )
    jas = [ja for ja in jas if ja.total_area and ja.total_area > 0]
    if not jas:
        return []

    anchor_ja, anchor_date, anchor_activity = determine_anchor(jas)
    unique_acts = sorted({ja.activity for ja in jas}, key=phase_order)
    cum_days   = {act.pk: get_gap_days(act, clusters) for act in unique_acts}
    anchor_cum = cum_days.get(anchor_activity.pk, 0) if anchor_activity else 0

    rows = []
    for ja in sorted(jas, key=lambda x: phase_order(x.activity)):
        alloc     = best_alloc(ja)
        wsl       = work_status_label(ja)
        is_anchor = (ja == anchor_ja)

        actual_date = None
        if alloc and alloc.work_status == "completed":
            actual_date = alloc.allocated_date

        this_cum   = cum_days.get(ja.activity.pk, 0)
        delta_days = this_cum - anchor_cum
        sched      = ja.scheduled_date

        if is_anchor:
            projected = anchor_date
            is_before = False
        elif anchor_date and sched and sched < anchor_date:
            projected = sched
            is_before = True
        else:
            projected = anchor_date + timedelta(days=delta_days) if anchor_date else sched
            is_before = False

        if anchor_ja:
            _allocs = list(anchor_ja.allocations.all())
            if any(a.work_status == "completed" for a in _allocs): anchor_tier = "Completed"
            elif _allocs and anchor_ja.allocation_status == "fully_allocated": anchor_tier = "Fully Allocated"
            elif _allocs:       anchor_tier = "Allocated"
            elif anchor_ja.is_lost: anchor_tier = "Lost"
            else:               anchor_tier = "Scheduled"
        else:
            anchor_tier = "None"

        if is_anchor:
            reason = (f"ANCHOR [{anchor_tier}] | Anchor date: {anchor_date} | "
                      f"Projected = {anchor_date} + 0d = {projected}")
        elif is_before:
            reason = f"Before anchor date ({anchor_date}) — original date kept: {sched}"
        else:
            lost_suffix = f" | Lost reason: {ja.lost_reason or 'N/A'}" if ja.is_lost else ""
            reason = (f"Projected = Anchor ({anchor_activity.name} [{anchor_tier}] on {anchor_date}) "
                      f"+ {delta_days}d = {projected}{lost_suffix}")

        job    = ja.job
        farmer = job.farmer if job else None
        mukadam_name = alloc.mukkadam.mukkadam_name if alloc else ""
        crew_size    = alloc.allocated_workers       if alloc else ""
        is_pending   = (ja.allocation_status == "pending" and not ja.is_lost)

        rows.append({
            "Plot ID":              plot.pk,
            "Plot Name":            plot.name,
            "Plot Full Acres":      float(plot.area_acres),
            "Farmer ID":            farmer.farmer_id   if farmer else "",
            "Farmer Name":          farmer.farmer_name if farmer else "",
            "Farmer Location":      farmer.location    if farmer else "",
            "Job ID":               job.job_id         if job    else "",
            "Activity":             ja.activity.name,
            "Activity Order":       phase_order(ja.activity),
            "Is Lost":              "Yes" if ja.is_lost else "No",
            "Scheduled Date":       ja.scheduled_date,
            "Projected Date":       projected,      # will be replaced with formula below
            "_base_projected":      projected,      # raw value stored in hidden col
            "_is_pending":          is_pending,
            "Actual/Anchor Date":   actual_date if not is_anchor else (actual_date or anchor_date),
            "Sales Date":           ja.sales_date,
            "Work Status":          wsl,
            "Allocation Status":    ja.allocation_status.replace("_", " ").title(),
            "Mukadam Name":         mukadam_name,
            "Crew Size":            crew_size,
            "Total Area (ac)":      float(ja.total_area),
            "Allocated Area (ac)":  float(ja.allocated_area),
            "Is Anchor":            "YES" if is_anchor else "",
            "Reason / Note":        reason,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Visible columns on main sheet
HEADERS = [
    "Plot ID", "Plot Name", "Plot Full Acres",
    "Farmer ID", "Farmer Name", "Farmer Location",
    "Job ID",
    "Activity", "Activity Order",
    "Is Lost", "Scheduled Date", "Projected Date",
    "Actual/Anchor Date", "Sales Date",
    "Work Status", "Allocation Status",
    "Mukadam Name", "Crew Size",
    "Total Area (ac)", "Allocated Area (ac)",
    "Is Anchor", "Reason / Note",
]

# One hidden column appended AFTER visible ones — stores the original base date
# so the formula can always offset from it (even after multiple adjustments).
HIDDEN_BASE_COL_NAME = "_BaseDate"

TOTAL_COLS       = len(HEADERS) + 1                          # +1 hidden
BASE_DATE_COL_IDX = len(HEADERS) + 1                         # 1-based, last col
PROJ_DATE_COL_IDX = HEADERS.index("Projected Date") + 1     # 1-based
ALLOC_STATUS_COL_IDX = HEADERS.index("Allocation Status") + 1
PLOT_ID_COL_IDX  = HEADERS.index("Plot ID") + 1

BASE_DATE_COL_LETTER = get_column_letter(BASE_DATE_COL_IDX)
PROJ_DATE_COL_LETTER = get_column_letter(PROJ_DATE_COL_IDX)
ALLOC_STATUS_COL_LETTER = get_column_letter(ALLOC_STATUS_COL_IDX)
PLOT_ID_COL_LETTER = get_column_letter(PLOT_ID_COL_IDX)

DATE_COLS = {"Scheduled Date", "Projected Date", "Actual/Anchor Date", "Sales Date"}
LEFT_COLS = {"Farmer Name", "Farmer Location", "Plot Name",
             "Activity", "Reason / Note", "Mukadam Name"}

thin = Side(border_style="thin", color="BFBFBF")
BDR  = Border(left=thin, right=thin, top=thin, bottom=thin)

BG = {
    "header":    "1F4E79",
    "anchor":    "FFF2CC",
    "completed": "E2EFDA",
    "lost":      "FCE4D6",
    "cancelled": "F0E6FF",
    "alt":       "F5F5F5",
    "white":     "FFFFFF",
}

COL_WIDTHS = {
    "Plot ID": 12, "Plot Name": 18, "Plot Full Acres": 14,
    "Farmer ID": 14, "Farmer Name": 22, "Farmer Location": 26,
    "Job ID": 20,
    "Activity": 22, "Activity Order": 13,
    "Is Lost": 9, "Scheduled Date": 15, "Projected Date": 15,
    "Actual/Anchor Date": 16, "Sales Date": 13,
    "Work Status": 20, "Allocation Status": 18,
    "Mukadam Name": 24, "Crew Size": 12,
    "Total Area (ac)": 14, "Allocated Area (ac)": 16,
    "Is Anchor": 10, "Reason / Note": 58,
}


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_excel(output_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Activity Schedule"

    # ── 1. Mukkadam hidden list for dropdown ──────────────────────────────────
    print("⏳ Loading mukkadams...")
    all_mukkadams = list(
        Mukkadam.objects.order_by("mukkadam_name").values_list("mukkadam_name", flat=True)
    )
    muk_ws = wb.create_sheet("_Mukkadams")
    muk_ws.sheet_state = "hidden"
    for i, name in enumerate(all_mukkadams, 1):
        muk_ws.cell(row=i, column=1, value=name)
    muk_count = len(all_mukkadams)

    muk_col_idx    = HEADERS.index("Mukadam Name") + 1
    muk_col_letter = get_column_letter(muk_col_idx)

    # ── 2. Build data rows ────────────────────────────────────────────────────
    print("⏳ Fetching plots...")
    plots    = list(Plot.objects.prefetch_related("clusters").all())
    all_rows = []
    for i, plot in enumerate(plots, 1):
        print(f"   Plot {i}/{len(plots)}: {plot.name}", end="\r")
        all_rows.extend(build_rows(plot))
    print(f"\n✅ {len(all_rows)} rows across {len(plots)} plots")

    if not all_rows:
        ws["A1"] = "No data found."
        wb.save(output_path)
        return

    total_data_rows = len(all_rows)

    # ── 3. "📅 Date Adjustments" sheet — user types shift here ───────────────
    # Columns: Plot ID | Plot Name | Shift Days
    # One row per unique plot. User types a number in "Shift Days".
    # The Projected Date formula on the main sheet VLOOKUPs here.
    adj_ws = wb.create_sheet("📅 Date Adjustments")

    ADJ_HDR_FILL  = PatternFill("solid", fgColor="1F4E79")
    ADJ_INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")   # yellow = editable

    for ci, h in enumerate(["Plot ID", "Plot Name", "Shift Days (+ or -)"], 1):
        c = adj_ws.cell(1, ci, h)
        c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill      = ADJ_HDR_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border    = BDR
    adj_ws.row_dimensions[1].height = 28

    # Collect unique plots in the order they appear
    seen_plots   = {}   # plot_id → (plot_name, adj_row_number)
    adj_row      = 2
    for row in all_rows:
        pid = row["Plot ID"]
        if pid not in seen_plots:
            seen_plots[pid] = (row["Plot Name"], adj_row)
            adj_ws.cell(adj_row, 1, pid).border   = BDR
            adj_ws.cell(adj_row, 2, row["Plot Name"]).border = BDR
            # Shift Days — default 0, yellow background so user knows it's editable
            sc = adj_ws.cell(adj_row, 3, 0)
            sc.fill      = ADJ_INPUT_FILL
            sc.font      = Font(name="Arial", size=10, bold=True, color="7030A0")
            sc.alignment = Alignment(horizontal="center")
            sc.border    = BDR
            sc.number_format = '+0;-0;0'   # show +3 or -2 style
            adj_row += 1

    adj_ws.column_dimensions["A"].width = 14
    adj_ws.column_dimensions["B"].width = 22
    adj_ws.column_dimensions["C"].width = 20
    adj_ws.freeze_panes = "A2"

    # Named range for VLOOKUP: the whole Plot ID + Shift Days table
    # Columns A:C on adj_ws, rows 2 to adj_row-1
    adj_table_end = adj_row - 1
    # We'll reference it directly by sheet name in formulas (no named range needed)

    # ── 4. Header row on main sheet ───────────────────────────────────────────
    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill      = PatternFill("solid", fgColor=BG["header"])
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border    = BDR
    ws.row_dimensions[1].height = 36

    # Hidden column header
    hc = ws.cell(1, BASE_DATE_COL_IDX, HIDDEN_BASE_COL_NAME)
    hc.font = Font(name="Arial", size=9, color="FFFFFF")
    hc.fill = PatternFill("solid", fgColor=BG["header"])

    ws.freeze_panes = "A2"

    # ── 5. Data rows ──────────────────────────────────────────────────────────
    for ri, row in enumerate(all_rows, 2):
        is_anchor    = row["Is Anchor"] == "YES"
        is_completed = row["Work Status"] == "Completed"
        is_lost      = row["Is Lost"] == "Yes"
        is_cancelled = "Cancelled" in row["Work Status"]
        is_pending   = row["_is_pending"]

        if is_anchor:      bg = BG["anchor"]
        elif is_completed: bg = BG["completed"]
        elif is_lost:      bg = BG["lost"]
        elif is_cancelled: bg = BG["cancelled"]
        elif ri % 2 == 0:  bg = BG["alt"]
        else:              bg = BG["white"]

        txt_color = "C00000" if is_lost else ("7030A0" if is_cancelled else "000000")

        for ci, col in enumerate(HEADERS, 1):
            if col == "Projected Date":
                # ── THE CASCADE FORMULA ──────────────────────────────────────
                # Logic:
                #   base  = hidden column this row (original Python date)
                #   shift = IFERROR(VLOOKUP(PlotID, Adjustments!A:C, 3, 0), 0)
                #         → looks up this row's Plot ID in the Date Adjustments sheet
                #
                #   IF row is Pending  →  base + shift
                #   ELSE               →  base  (allocated/completed/lost = never moved)
                #
                base_ref   = f"{BASE_DATE_COL_LETTER}{ri}"
                plot_ref   = f"{PLOT_ID_COL_LETTER}{ri}"
                status_ref = f"{ALLOC_STATUS_COL_LETTER}{ri}"
                adj_range  = f"'📅 Date Adjustments'!$A:$C"

                formula = (
                    f'=IF(LOWER(TRIM({status_ref}))="pending",'
                    f'{base_ref}+IFERROR(VLOOKUP({plot_ref},{adj_range},3,0),0),'
                    f'{base_ref})'
                )
                c = ws.cell(row=ri, column=ci, value=formula)
                c.number_format = "DD-MMM-YYYY"
            else:
                val = row.get(col)
                c   = ws.cell(row=ri, column=ci, value=val)
                if col in DATE_COLS and isinstance(val, date):
                    c.number_format = "DD-MMM-YYYY"

            c.fill      = PatternFill("solid", fgColor=bg)
            c.font      = Font(name="Arial", size=9, bold=is_anchor, color=txt_color)
            c.alignment = Alignment(
                horizontal="left" if col in LEFT_COLS else "center",
                vertical="center", wrap_text=True
            )
            c.border = BDR

        # Hidden base-date column (raw date value, never shown to user)
        base_val = row["_base_projected"]
        bc = ws.cell(row=ri, column=BASE_DATE_COL_IDX, value=base_val)
        bc.number_format = "DD-MMM-YYYY"
        # Make it invisible: white text on white background
        bc.font      = Font(name="Arial", size=9, color="FFFFFF")
        bc.fill      = PatternFill("solid", fgColor="FFFFFF")
        bc.alignment = Alignment(horizontal="center")

        ws.row_dimensions[ri].height = 18

    # ── 6. Hide the base-date column ─────────────────────────────────────────
    ws.column_dimensions[BASE_DATE_COL_LETTER].hidden = True
    ws.column_dimensions[BASE_DATE_COL_LETTER].width  = 14

    # ── 7. Mukadam dropdown ───────────────────────────────────────────────────
    if muk_count > 0:
        dv = DataValidation(
            type="list",
            formula1=f"_Mukkadams!$A$1:$A${muk_count}",
            allow_blank=True,
            showDropDown=False,
        )
        dv.sqref = f"{muk_col_letter}2:{muk_col_letter}{total_data_rows + 1}"
        ws.add_data_validation(dv)

    # ── 8. Column widths + autofilter ─────────────────────────────────────────
    for ci, h in enumerate(HEADERS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = COL_WIDTHS.get(h, 15)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{total_data_rows + 1}"

    # ── 9. Instructions box at the top of the Date Adjustments sheet ──────────
    # Insert 8 rows at top for instructions
    adj_ws.insert_rows(1, amount=8)

    inst = [
        ("HOW TO SHIFT PENDING DATES FOR A PLOT", None, None),
        (None, None, None),
        ("1. Find the plot you want to adjust in the table below.", None, None),
        ('2. Type a number in the yellow "Shift Days" column:',    None, None),
        ("   • Positive number (+3) → moves all pending dates forward 3 days", None, None),
        ("   • Negative number (-2) → moves all pending dates back 2 days",   None, None),
        ("3. Go back to 'Activity Schedule' sheet — Projected Dates auto-update.", None, None),
        ("   Only PENDING rows are moved. Allocated/Completed rows never change.", None, None),
    ]
    for ri, (a, b, c_) in enumerate(inst, 1):
        cell = adj_ws.cell(ri, 1, a or "")
        cell.font      = Font(name="Arial",
                              size=12 if ri == 1 else 10,
                              bold=(ri == 1 or ri in (3, 4, 7, 8)),
                              color="1F4E79" if ri == 1 else "000000")
        cell.alignment = Alignment(wrap_text=True)
    adj_ws.row_dimensions[1].height = 22
    adj_ws.merge_cells("A1:C1")

    # Re-style the header row (now shifted to row 9)
    for ci, h in enumerate(["Plot ID", "Plot Name", "Shift Days (+ or -)"], 1):
        c = adj_ws.cell(9, ci, h)
        c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill      = ADJ_HDR_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border    = BDR
    adj_ws.row_dimensions[9].height = 28
    adj_ws.freeze_panes = "A10"

    # ── 10. Legend ────────────────────────────────────────────────────────────
    ls = wb.create_sheet("Legend")
    for ri, (a, b) in enumerate([
        ("Color",                "Meaning"),
        ("🟡 Yellow (bold)",     "ANCHOR — this activity's date is the scheduling origin"),
        ("🟢 Green",             "Completed activity"),
        ("🟠 Orange (red text)", "Lost activity (farmer used another contractor)"),
        ("🟣 Purple",            "Cancelled / Not Done activity"),
        ("⚪ White / Grey",      "Pending future activities"),
    ], 1):
        ls.cell(ri, 1, a).font = Font(bold=(ri == 1), name="Arial", size=10)
        ls.cell(ri, 2, b).font = Font(name="Arial", size=10)
    ls.column_dimensions["A"].width = 25
    ls.column_dimensions["B"].width = 65

    # ── 11. Scheduling Rules ──────────────────────────────────────────────────
    rs = wb.create_sheet("Scheduling Rules")
    for ri, (a, b) in enumerate([
        ("Rule",                  "Description"),
        ("Anchor Priority",       "Completed date > Lost date > Latest scheduled date"),
        ("Gap Calculation",       "Relative gap from anchor activity"),
        ("Future Projection",     "anchor_date + cumulative_gap_to_this_activity"),
        ("Historical Activities", "Shown as-is — before anchor, already history"),
        ("Lost Activity",         "Shown as Lost. If it is the latest → becomes anchor"),
        ("Date Cascade",          "Type a number in '📅 Date Adjustments' sheet → all Pending rows on that plot shift"),
        ("Allocated rows",        "Never moved by cascade — only Pending status rows are affected"),
    ], 1):
        rs.cell(ri, 1, a).font = Font(bold=(ri == 1), name="Arial", size=10)
        rs.cell(ri, 2, b).font = Font(name="Arial", size=10)
    rs.column_dimensions["A"].width = 25
    rs.column_dimensions["B"].width = 72

    # ── 12. Save ──────────────────────────────────────────────────────────────
    wb.save(output_path)
    print(f"💾 Saved: {output_path}")
    print()
    print("📋 HOW TO USE THE CASCADE:")
    print(f"   Open '{output_path}' → go to '📅 Date Adjustments' sheet")
    print("   Type +3 or -2 in the yellow Shift Days cell for any plot")
    print("   Switch back to 'Activity Schedule' — all Pending dates updated instantly")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    default_out = os.path.join(BASE_DIR, "activity_schedule.xlsx")
    out = sys.argv[1] if len(sys.argv) > 1 else default_out
    build_excel(out)