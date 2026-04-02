# Activity Scheduling Sheet Generator
# Run:    python sheet.py
# Output: activity_schedule.xlsx  (same folder as this file)

import os, sys, django
from datetime import date, timedelta

# ── Django setup ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")
django.setup()

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from tender.models import (          # ← adjust app name if needed
    Plot, JobActivity, ActivityScheduleRule,
    ClusterActivityScheduleRule, Allocation, ActivityCatalog,
)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_gap_days(activity, clusters):
    """Cluster override → global rule → catalog default."""
    for c in clusters:
        rule = ClusterActivityScheduleRule.objects.filter(
            cluster=c, activity=activity
        ).first()
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
    """
    Return best Allocation for a JA using Python sorting
    (avoids queryset .order_by() conflict with prefetch_related).
    """
    allocs = list(ja.allocations.all())          # already cached via prefetch
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
    if ws == "completed":
        return "Completed"
    if ws == "in_progress":
        return "In Progress"
    return ws.replace("_", " ").title()


def determine_anchor(jas):
    """
    Anchor = the LAST activity by date that has been acted on.
    Acted on = has any allocation (completed/fully_allocated/partial) OR is_lost=True.
    Among all acted-on JAs pick the one with the LATEST date.
    Fallback: latest scheduled_date (duplicate activity names -> pick later one).
    Returns (anchor_ja, anchor_date, anchor_activity).
    """
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
        best_ja, best_date = max(candidates, key=lambda x: x[1])
        return best_ja, best_date, best_ja.activity

    # Fallback: no allocations, no lost
    # → anchor = FIRST activity by phase_order, project all others from it
    scheduled = [(ja, ja.scheduled_date) for ja in jas if ja.scheduled_date]
    if scheduled:
        first_ja, first_date = min(scheduled, key=lambda x: phase_order(x[0].activity))
        return first_ja, first_date, first_ja.activity

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
        .prefetch_related("allocations")
    )
    jas = [ja for ja in jas if ja.total_area and ja.total_area > 0]
    if not jas:
        return []

    anchor_ja, anchor_date, anchor_activity = determine_anchor(jas)

    # Sort all activities for this plot by phase_order
    unique_acts = sorted(
        {ja.activity for ja in jas},
        key=phase_order
    )

    # Precompute cumulative gap days from Pruning (phase_order=0 or 1)
    cum_days = {}
    for act in unique_acts:
        cum_days[act.pk] = get_gap_days(act, clusters)

    anchor_cum = cum_days.get(anchor_activity.pk, 0) if anchor_activity else 0

    rows = []
    for ja in sorted(jas, key=lambda x: phase_order(x.activity)):
        alloc     = best_alloc(ja)
        wsl       = work_status_label(ja)
        is_anchor = (ja == anchor_ja)

        # Actual date (only if completed)
        actual_date = None
        if alloc and alloc.work_status == "completed":
            actual_date = alloc.allocated_date

        this_cum   = cum_days.get(ja.activity.pk, 0)
        delta_days = this_cum - anchor_cum

        # Key rule: compare by SCHEDULED DATE vs ANCHOR DATE
        # Before anchor date → keep original scheduled date, no change
        # Same date OR after anchor date → recalculate using gap from anchor
        sched = ja.scheduled_date

        if is_anchor:
            projected = anchor_date
            is_before = False
        elif anchor_date and sched and sched < anchor_date:
            # Strictly before anchor date → untouched
            projected = sched
            is_before = True
        else:
            # Same date as anchor OR after anchor date → recalculate
            projected = anchor_date + timedelta(days=delta_days) if anchor_date else sched
            is_before = False

        # Anchor tier label
        if anchor_ja:
            _allocs = list(anchor_ja.allocations.all())
            if any(a.work_status == "completed" for a in _allocs):
                anchor_tier = "Completed"
            elif _allocs and anchor_ja.allocation_status == "fully_allocated":
                anchor_tier = "Fully Allocated"
            elif _allocs:
                anchor_tier = "Allocated"
            elif anchor_ja.is_lost:
                anchor_tier = "Lost"
            else:
                anchor_tier = "Scheduled"
        else:
            anchor_tier = "None"

        if is_anchor:
            reason = (
                f"ANCHOR [{anchor_tier}] | "
                f"Anchor date: {anchor_date} | "
                f"Projected = {anchor_date} + 0d = {projected}"
            )
        elif is_before:
            reason = (
                f"Before anchor date ({anchor_date}) — original date kept: {sched}"
            )
        else:
            lost_suffix = f" | Lost reason: {ja.lost_reason or 'N/A'}" if ja.is_lost else ""
            reason = (
                f"Projected = Anchor ({anchor_activity.name} [{anchor_tier}] on {anchor_date}) "
                f"+ {delta_days}d = {projected}"
                f"{lost_suffix}"
            )

        job = ja.job
        rows.append({
            "Plot ID":             plot.pk,
            "Plot Name":           plot.name,
            "Plot Full Acres":     float(plot.area_acres),
            "Farmer ID":           job.farmer.farmer_id if job else "",
            "Farmer Name":         job.farmer.farmer_name if job else "",
            "Job ID":              job.job_id if job else "",
            "Activity":            ja.activity.name,
            "Activity Order":      phase_order(ja.activity),
            "Is Lost":             "Yes" if ja.is_lost else "No",
            "Scheduled Date":      ja.scheduled_date,
            "Projected Date":      projected,
            "Actual/Anchor Date":  actual_date if not is_anchor else (actual_date or anchor_date),
            "Sales Date":          ja.sales_date,
            "Work Status":         wsl,
            "Allocation Status":   ja.allocation_status.replace("_", " ").title(),
            "Total Area (ac)":     float(ja.total_area),
            "Allocated Area (ac)": float(ja.allocated_area),
            "Is Anchor":           "YES" if is_anchor else "",
            "Reason / Note":       reason,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL BUILDER
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = [
    "Plot ID", "Plot Name", "Plot Full Acres",
    "Farmer ID", "Farmer Name", "Job ID",
    "Activity", "Activity Order",
    "Is Lost", "Scheduled Date", "Projected Date",
    "Actual/Anchor Date", "Sales Date",
    "Work Status", "Allocation Status",
    "Total Area (ac)", "Allocated Area (ac)",
    "Is Anchor", "Reason / Note",
]

DATE_COLS = {"Scheduled Date", "Projected Date", "Actual/Anchor Date", "Sales Date"}
LEFT_COLS  = {"Farmer Name", "Plot Name", "Activity", "Reason / Note"}

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
    "Farmer ID": 14, "Farmer Name": 22, "Job ID": 20,
    "Activity": 22, "Activity Order": 13,
    "Is Lost": 9, "Scheduled Date": 15, "Projected Date": 15,
    "Actual/Anchor Date": 16, "Sales Date": 13,
    "Work Status": 20, "Allocation Status": 18,
    "Total Area (ac)": 14, "Allocated Area (ac)": 16,
    "Is Anchor": 10, "Reason / Note": 58,
}


def build_excel(output_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Activity Schedule"

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

    # Header row
    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill      = PatternFill("solid", fgColor=BG["header"])
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border    = BDR
    ws.row_dimensions[1].height = 36
    ws.freeze_panes = "A2"

    # Data rows
    for ri, row in enumerate(all_rows, 2):
        is_anchor    = row["Is Anchor"] == "YES"
        is_completed = row["Work Status"] == "Completed"
        is_lost      = row["Is Lost"] == "Yes"
        is_cancelled = "Cancelled" in row["Work Status"]

        if is_anchor:
            bg = BG["anchor"]
        elif is_completed:
            bg = BG["completed"]
        elif is_lost:
            bg = BG["lost"]
        elif is_cancelled:
            bg = BG["cancelled"]
        elif ri % 2 == 0:
            bg = BG["alt"]
        else:
            bg = BG["white"]

        txt_color = "C00000" if is_lost else ("7030A0" if is_cancelled else "000000")

        for ci, col in enumerate(HEADERS, 1):
            val = row.get(col)
            c   = ws.cell(row=ri, column=ci, value=val)
            c.fill      = PatternFill("solid", fgColor=bg)
            c.font      = Font(name="Arial", size=9, bold=is_anchor, color=txt_color)
            c.alignment = Alignment(
                horizontal="left" if col in LEFT_COLS else "center",
                vertical="center", wrap_text=True
            )
            c.border = BDR
            if col in DATE_COLS and isinstance(val, date):
                c.number_format = "DD-MMM-YYYY"
        ws.row_dimensions[ri].height = 18

    # Column widths + autofilter
    for ci, h in enumerate(HEADERS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = COL_WIDTHS.get(h, 15)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{len(all_rows)+1}"

    # Legend sheet
    ls = wb.create_sheet("Legend")
    legend = [
        ("Color",                "Meaning"),
        ("🟡 Yellow (bold)",     "ANCHOR — this activity's date is the scheduling origin"),
        ("🟢 Green",             "Completed activity"),
        ("🟠 Orange (red text)", "Lost activity (farmer used another contractor)"),
        ("🟣 Purple",            "Cancelled / Not Done activity"),
        ("⚪ White / Grey",      "Pending future activities"),
    ]
    for ri, (a, b) in enumerate(legend, 1):
        ls.cell(ri, 1, a).font = Font(bold=(ri == 1), name="Arial", size=10)
        ls.cell(ri, 2, b).font = Font(name="Arial", size=10)
    ls.column_dimensions["A"].width = 25
    ls.column_dimensions["B"].width = 65

    # Rules sheet
    rs = wb.create_sheet("Scheduling Rules")
    rules = [
        ("Rule",                  "Description"),
        ("Anchor Priority",       "Completed date > Lost date > Latest scheduled date"),
        ("Gap Calculation",       "Relative gap from anchor activity (NOT always from Pruning)"),
        ("Future Projection",     "anchor_date + cumulative_gap_to_this_activity"),
        ("Historical Activities", "Shown as-is — before anchor, already history"),
        ("Lost Activity",         "Shown as Lost. If it is the latest → becomes anchor"),
        ("Cancelled Pruning",     "Still used as anchor; status = Cancelled/Not Done"),
        ("Sales Date",            "From JobActivity.sales_date (auto-set on save)"),
    ]
    for ri, (a, b) in enumerate(rules, 1):
        rs.cell(ri, 1, a).font = Font(bold=(ri == 1), name="Arial", size=10)
        rs.cell(ri, 2, b).font = Font(name="Arial", size=10)
    rs.column_dimensions["A"].width = 25
    rs.column_dimensions["B"].width = 72

    wb.save(output_path)
    print(f"💾 Saved: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    default_out = os.path.join(BASE_DIR, "activity_schedule4.xlsx")
    out = sys.argv[1] if len(sys.argv) > 1 else default_out
    build_excel(out)