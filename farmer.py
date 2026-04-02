# Farmer & Mukkadam Activity Profile Sheet Generator
# Chunked processing — fetches DB rows in batches of CHUNK_SIZE (default 200)
# Run:    python profiles_sheet.py
# Output: profiles_sheet.xlsx

import os, sys, django, gc
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")
django.setup()

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.db import connection, reset_queries
from tender.models import JobActivity, Allocation, ActivityScheduleRule

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

CHUNK_SIZE = 200   # rows fetched from DB per iteration

# ─────────────────────────────────────────────────────────────────────────────
# STYLE CONSTANTS  (built once, reused for every cell)
# ─────────────────────────────────────────────────────────────────────────────

thin = Side(border_style="thin", color="BFBFBF")
BDR  = Border(left=thin, right=thin, top=thin, bottom=thin)

BG = {
    "header":    "1F4E79",
    "section":   "2E75B6",
    "completed": "E2EFDA",
    "allocated": "DEEAF1",
    "partial":   "FFF2CC",
    "lost":      "FCE4D6",
    "pending":   "FFFFFF",
    "alt":       "F5F5F5",
    "carry_fwd": "E8D5F5",
    "dispute":   "FCE4D6",
}

# Pre-build Fill/Font objects so openpyxl doesn't recreate them every cell
_FILLS  = {k: PatternFill("solid", fgColor=v) for k, v in BG.items()}
_HDR_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=10)
_SEC_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=9)
_DATA_FONT = Font(name="Arial", size=9)
_RED_FONT  = Font(name="Arial", size=9, color="C00000")
_PUR_FONT  = Font(name="Arial", size=9, color="7030A0")
_AL_C = Alignment(horizontal="center", vertical="center", wrap_text=False)
_AL_L = Alignment(horizontal="left",   vertical="center", wrap_text=True)
_AL_CH= Alignment(horizontal="center", vertical="center", wrap_text=True)
_DATE_FMT  = "DD-MMM-YYYY"
_MONEY_FMT = "#,##0.00"


# ─────────────────────────────────────────────────────────────────────────────
# CELL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _write_header_row(ws, row_num, headers, height=36):
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=row_num, column=ci, value=h)
        c.font      = _HDR_FONT
        c.fill      = _FILLS["header"]
        c.alignment = _AL_CH
        c.border    = BDR
    ws.row_dimensions[row_num].height = height


def _write_group_row(ws, groups, row_num=1, height=18):
    for label, start, end in groups:
        c = ws.cell(row=row_num, column=start, value=label)
        c.font      = _SEC_FONT
        c.fill      = _FILLS["section"]
        c.alignment = _AL_CH
        c.border    = BDR
        if end > start:
            ws.merge_cells(
                start_row=row_num, start_column=start,
                end_row=row_num,   end_column=end,
            )
    ws.row_dimensions[row_num].height = height


def _write_data_row(ws, ri, values, bg_key, left_cols, date_cols, money_cols,
                    font_override=None):
    fill = _FILLS.get(bg_key, _FILLS["pending"])
    font = font_override or _DATA_FONT
    for ci, (col, val) in enumerate(values, 1):
        c = ws.cell(row=ri, column=ci, value=val)
        c.font   = font
        c.fill   = fill
        c.border = BDR
        c.alignment = _AL_L if col in left_cols else _AL_C
        if col in date_cols and isinstance(val, date):
            c.number_format = _DATE_FMT
        elif col in money_cols and val not in ("", None):
            c.number_format = _MONEY_FMT
    ws.row_dimensions[ri].height = 20


# ─────────────────────────────────────────────────────────────────────────────
# SHARED LOGIC
# ─────────────────────────────────────────────────────────────────────────────

# Cache phase_order lookups — avoids one DB hit per activity per row
_PHASE_CACHE: dict = {}

def phase_order(activity_id, activity_obj):
    if activity_id not in _PHASE_CACHE:
        rule = ActivityScheduleRule.objects.filter(activity_id=activity_id).only("phase_order").first()
        _PHASE_CACHE[activity_id] = rule.phase_order if rule else 0
    return _PHASE_CACHE[activity_id]


def best_alloc_from_list(allocs):
    if not allocs:
        return None
    completed = [a for a in allocs if a.work_status == "completed"]
    pool = completed if completed else allocs
    return max(pool, key=lambda a: a.allocated_date)


def overall_work_status(ja, allocs):
    if ja.is_lost:
        return "Lost"
    if not allocs:
        return ja.allocation_status.replace("_", " ").title()
    if any(a.work_status == "completed" for a in allocs):
        return "Completed"
    if any(a.work_status == "in_progress" for a in allocs):
        return "In Progress"
    return "Allocated – Not Started"


def fmt_dt(d):
    if d is None:
        return ""
    return d.date() if hasattr(d, "date") else d


def _effective_status(m):
    if m.manual_status:
        return m.manual_status.replace("_", " ").title()
    return "Active"


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# SHEET 1 — FARMER ACTIVITY VIEW  (1 row per JobActivity)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

FARMER_HEADERS = [
    # FARMER PROFILE
    "Farmer ID", "Farmer Name", "Farmer Phone",
    "Farmer Clusters", "Farmer Location",
    # PLOT
    "Plot ID", "Plot Name", "Plot Area (ac)",
    "Crop", "Variety", "Pruning Date",
    # JOB
    "Job ID", "Job Status", "Job Priority",
    "Farmer Payment Status", "Booking Amount (INR)",
    # ACTIVITY
    "Activity", "Activity Order", "Is Strict",
    # AREA & DATES
    "Total Area (ac)", "Allocated Area (ac)", "Remaining Area (ac)",
    "Scheduled Date", "Sales Date",
    # STATUS
    "Allocation Status", "Work Status",
    "Is Lost", "Lost Reason",
    # ALLOCATION SUMMARY
    "# Allocations", "Mukkadams Assigned", "Allocation Dates",
    # COMPLETED ALLOCATION
    "Completed By (Mukkadam)", "Completed Mukkadam ID",
    "Completed Mukkadam Mobile", "Completion Date",
    "Actual Area Done (ac)", "Actual Crew Used",
    # RATES & AMOUNTS
    "Farmer Rate (INR/ac)", "Mukkadam Rate (INR/ac)",
    "Farmer Amount (INR)", "Mukkadam Amount (INR)", "Profit (INR)",
    # PAYMENT & VERIFICATION
    "Alloc Work Status", "Alloc Payment Status",
    "Report Submitted", "Farmer Agreed?", "Farmer Disputed Reason",
]

FARMER_GROUPS = [
    ("FARMER PROFILE",          1,  5),
    ("PLOT",                    6, 11),
    ("JOB",                    12, 16),
    ("ACTIVITY",               17, 19),
    ("AREA & DATES",           20, 24),
    ("STATUS",                 25, 28),
    ("ALLOCATION SUMMARY",     29, 31),
    ("COMPLETED ALLOCATION",   32, 37),
    ("RATES & AMOUNTS",        38, 42),
    ("PAYMENT & VERIFICATION", 43, 47),
]

FARMER_WIDTHS = [
    14, 22, 14, 28, 22,
    10, 18, 13, 16, 16, 13,
    18, 14, 12, 18, 16,
    22, 13, 10,
    13, 15, 14, 14, 13,
    18, 22,  9, 28,
    12, 36, 28,
    26, 16, 20, 14, 14, 13,
    15, 16, 15, 16, 12,
    18, 18, 14, 14, 30,
]

FARMER_LEFT  = {
    "Farmer Name","Farmer Clusters","Farmer Location","Plot Name",
    "Crop","Variety","Activity","Lost Reason",
    "Mukkadams Assigned","Allocation Dates",
    "Completed By (Mukkadam)","Completed Mukkadam Mobile",
    "Farmer Disputed Reason",
}
FARMER_DATE  = {"Pruning Date","Scheduled Date","Sales Date","Completion Date"}
FARMER_MONEY = {
    "Booking Amount (INR)","Farmer Rate (INR/ac)","Mukkadam Rate (INR/ac)",
    "Farmer Amount (INR)","Mukkadam Amount (INR)","Profit (INR)",
}


def _farmer_bg_key(work_status, is_lost, alloc_status):
    if is_lost:
        return "lost"
    ws = work_status.lower()
    if "completed" in ws:
        return "completed"
    if "in progress" in ws:
        return "allocated"
    if alloc_status in ("fully_allocated", "partially_allocated"):
        return "partial"
    return None   # use alt/pending alternating


def _ja_to_row(ja):
    """Convert a single JobActivity ORM object into a flat dict. Called inside chunks."""
    job    = ja.job
    farmer = job.farmer
    plot   = ja.plot
    allocs = list(ja.allocations.all())   # already prefetched

    farmer_clusters = ", ".join(c.name for c in farmer.clusters.all()) or "—"

    plot_id   = plot.pk                   if plot else ""
    plot_name = plot.name                 if plot else "—"
    plot_area = float(plot.area_acres)    if plot else ""
    crop      = (plot.crop_name if plot else "") or job.crop_name or "—"
    variety   = (plot.variety   if plot else "") or job.variety   or "—"
    pruning   = plot.pruning_date         if plot else None

    n_alloc = len(allocs)
    mukkadams_names = " | ".join(sorted({a.mukkadam.mukkadam_name for a in allocs})) or "—"
    alloc_dates     = " | ".join(
        str(a.allocated_date)
        for a in sorted(allocs, key=lambda a: a.allocated_date)
    ) or "—"

    ba = best_alloc_from_list(allocs)
    ca = next((a for a in allocs if a.work_status == "completed"), None) or ba

    wsl = overall_work_status(ja, allocs)
    po  = phase_order(ja.activity_id, ja.activity)

    return {
        "Farmer ID":              farmer.farmer_id,
        "Farmer Name":            farmer.farmer_name,
        "Farmer Phone":           farmer.phone_number or "—",
        "Farmer Clusters":        farmer_clusters,
        "Farmer Location":        farmer.location or "—",
        "Plot ID":                plot_id,
        "Plot Name":              plot_name,
        "Plot Area (ac)":         plot_area,
        "Crop":                   crop,
        "Variety":                variety,
        "Pruning Date":           pruning or "",
        "Job ID":                 job.job_id,
        "Job Status":             job.status.replace("_"," ").title(),
        "Job Priority":           job.priority,
        "Farmer Payment Status":  job.payment_status.title(),
        "Booking Amount (INR)":   float(job.booking_amount) if job.booking_amount else "",
        "Activity":               ja.activity.name,
        "Activity Order":         po,
        "Is Strict":              "Yes" if ja.is_strict else "No",
        "Total Area (ac)":        float(ja.total_area),
        "Allocated Area (ac)":    float(ja.allocated_area),
        "Remaining Area (ac)":    float(max(ja.total_area - ja.allocated_area, 0)),
        "Scheduled Date":         ja.scheduled_date or "",
        "Sales Date":             ja.sales_date     or "",
        "Allocation Status":      ja.allocation_status.replace("_"," ").title(),
        "Work Status":            wsl,
        "Is Lost":                "Yes" if ja.is_lost else "No",
        "Lost Reason":            (ja.lost_reason or "—") if ja.is_lost else "—",
        "# Allocations":          n_alloc,
        "Mukkadams Assigned":     mukkadams_names,
        "Allocation Dates":       alloc_dates,
        "Completed By (Mukkadam)":ca.mukkadam.mukkadam_name  if ca else "—",
        "Completed Mukkadam ID":  ca.mukkadam.mukkadam_id    if ca else "",
        "Completed Mukkadam Mobile": ca.mukkadam.mobile_numbers if ca else "—",
        "Completion Date":        ca.allocated_date if (ca and ca.work_status == "completed") else "",
        "Actual Area Done (ac)":  float(ca.actual_area_done)  if ca and ca.actual_area_done  else "",
        "Actual Crew Used":       ca.actual_crew_size          if ca and ca.actual_crew_size  else "",
        "Farmer Rate (INR/ac)":   float(ca.farmer_rate)     if ca else "",
        "Mukkadam Rate (INR/ac)": float(ca.mukkadam_rate)   if ca else "",
        "Farmer Amount (INR)":    float(ca.farmer_amount)   if ca else "",
        "Mukkadam Amount (INR)":  float(ca.mukkadam_amount) if ca else "",
        "Profit (INR)":           float(ca.profit)          if ca else "",
        "Alloc Work Status":      ca.work_status.replace("_"," ").title()    if ca else "—",
        "Alloc Payment Status":   ca.payment_status.replace("_"," ").title() if ca else "—",
        "Report Submitted":       "Yes" if (ca and ca.report_submitted) else "No",
        "Farmer Agreed?":         (
            "Agreed"   if ca and ca.farmer_agreed is True  else
            "Disputed" if ca and ca.farmer_agreed is False else
            "Pending"
        ) if ca else "—",
        "Farmer Disputed Reason": (ca.farmer_dispute_reason if ca else "") or "—",
        # internal
        "_is_lost":      ja.is_lost,
        "_work_status":  wsl,
        "_alloc_status": ja.allocation_status,
    }


def _ja_base_qs():
    return (
        JobActivity.objects
        .filter(total_area__gt=0)
        .select_related("activity", "job", "job__farmer", "plot")
        .prefetch_related(
            "allocations",
            "allocations__mukkadam",
            "job__farmer__clusters",
        )
        .order_by("job__farmer__farmer_name", "job__job_id", "scheduled_date")
    )


def write_farmer_sheet(wb):
    ws = wb.create_sheet("Farmer Activity View")
    print("  Building Farmer Activity View (chunked)...")

    _write_group_row(ws, FARMER_GROUPS, row_num=1)
    _write_header_row(ws, 2, FARMER_HEADERS)
    ws.freeze_panes = "A3"

    total = _ja_base_qs().count()
    print(f"     Total JobActivities: {total}")

    ri        = 3       # Excel row counter (row 1=groups, row 2=headers)
    processed = 0

    for offset in range(0, total, CHUNK_SIZE):
        chunk = list(_ja_base_qs()[offset : offset + CHUNK_SIZE])

        for ja in chunk:
            row = _ja_to_row(ja)
            bg_key = _farmer_bg_key(row["_work_status"], row["_is_lost"], row["_alloc_status"]) \
                     or ("alt" if ri % 2 == 0 else "pending")

            font = _RED_FONT if row["_is_lost"] else _DATA_FONT
            values = [(h, row.get(h)) for h in FARMER_HEADERS]
            _write_data_row(ws, ri, values, bg_key,
                            FARMER_LEFT, FARMER_DATE, FARMER_MONEY, font)
            ri += 1

        processed += len(chunk)
        print(f"     Farmer rows written: {processed}/{total}", end="\r")
        gc.collect()
        reset_queries()   # prevent Django from accumulating query log in DEBUG

    print()
    # Column widths & autofilter (rows 1+2 are headers, data starts row 3)
    for ci, w in enumerate(FARMER_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.auto_filter.ref = f"A2:{get_column_letter(len(FARMER_HEADERS))}{ri - 1}"


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# SHEET 2 — MUKKADAM ACTIVITY VIEW  (1 row per Allocation)
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

MUKKADAM_HEADERS = [
    # MUKKADAM PROFILE
    "Mukkadam ID","Mukkadam Name","Mobile Numbers",
    "Status","Is Permanent","Clusters",
    "State","District","Taluka","Village",
    "Crew Size","Efficiency",
    # FARMER
    "Farmer ID","Farmer Name","Farmer Phone","Farmer Location",
    # PLOT
    "Plot ID","Plot Name","Plot Area (ac)","Crop","Variety",
    # JOB
    "Job ID","Job Status","Job Payment Status",
    # ACTIVITY & JA
    "Activity","Activity Order","Is Strict",
    "JA Total Area (ac)","JA Allocated Area (ac)","JA Alloc Status",
    "JA Is Lost","JA Lost Reason","Scheduled Date","Sales Date",
    # THIS ALLOCATION
    "Allocated Date","Allocated Area (ac)","Allocated Workers",
    "Allows 2nd Job","Is Carry Forward","Is Auto Allocated",
    # RATES & MONEY
    "Farmer Rate (INR/ac)","Mukkadam Rate (INR/ac)",
    "Farmer Amount (INR)","Mukkadam Amount (INR)","Profit (INR)",
    # WORK STATUS
    "Work Status","Allocation Status","Payment Status",
    # DAY-END REPORT
    "Actual Start Time","Actual End Time",
    "Actual Crew Size","Actual Area Done (ac)",
    "Report Submitted","Report Submitted At",
    # FARMER VERIFICATION
    "Farmer Agreed?","Farmer Response At",
    "Farmer Dispute Reason","Admin Override Area (ac)",
    "Dispute Resolved By","Dispute Resolved At",
    # AUDIT
    "Created By","Created At","Last Modified By","Last Modified At",
]

MUKKADAM_GROUPS = [
    ("MUKKADAM PROFILE",      1,  12),
    ("FARMER",               13,  16),
    ("PLOT",                 17,  21),
    ("JOB",                  22,  24),
    ("ACTIVITY & JA",        25,  34),
    ("THIS ALLOCATION",      35,  40),
    ("RATES & MONEY",        41,  45),
    ("WORK STATUS",          46,  48),
    ("DAY-END REPORT",       49,  54),
    ("FARMER VERIFICATION",  55,  60),
    ("AUDIT",                61,  64),
]

MUKKADAM_WIDTHS = [
    14, 24, 18, 12, 12, 30,
    14, 16, 16, 16, 11, 10,
    14, 22, 14, 22,
    10, 18, 12, 16, 16,
    18, 14, 16,
    22, 13, 10, 14, 15, 18, 9, 26, 14, 13,
    14, 15, 16, 13, 14, 15,
    15, 16, 15, 16, 12,
    18, 18, 16,
    18, 18, 14, 15, 14, 18,
    14, 18, 28, 16, 20, 18,
    16, 15, 20, 15,
]

MUKKADAM_LEFT  = {
    "Mukkadam Name","Mobile Numbers","Clusters",
    "Farmer Name","Farmer Location","Plot Name",
    "Crop","Variety","Activity",
    "JA Lost Reason","Farmer Dispute Reason",
}
MUKKADAM_DATE  = {
    "Scheduled Date","Sales Date","Allocated Date",
    "Actual Start Time","Actual End Time","Report Submitted At",
    "Farmer Response At","Dispute Resolved At",
    "Created At","Last Modified At",
}
MUKKADAM_MONEY = {
    "Farmer Rate (INR/ac)","Mukkadam Rate (INR/ac)",
    "Farmer Amount (INR)","Mukkadam Amount (INR)","Profit (INR)",
}


def _mk_bg_key(alloc, ja_lost):
    if alloc.is_carry_forward:
        return "carry_fwd"
    ws = alloc.work_status
    if ws == "completed":
        return "completed"
    if ws == "in_progress":
        return "allocated"
    if alloc.payment_status == "dispute":
        return "dispute"
    if ja_lost:
        return "lost"
    return None


def _alloc_to_row(alloc):
    """Convert a single Allocation ORM object into a flat dict."""
    m      = alloc.mukkadam
    ja     = alloc.job_activity
    job    = ja.job
    farmer = job.farmer
    plot   = ja.plot

    mk_clusters     = ", ".join(c.name for c in m.clusters.all())      or "—"
    farmer_clusters = ", ".join(c.name for c in farmer.clusters.all()) or "—"

    fa = (
        "Agreed"   if alloc.farmer_agreed is True  else
        "Disputed" if alloc.farmer_agreed is False else
        "Pending"
    )

    return {
        "Mukkadam ID":          m.mukkadam_id,
        "Mukkadam Name":        m.mukkadam_name,
        "Mobile Numbers":       m.mobile_numbers or "—",
        "Status":               _effective_status(m),
        "Is Permanent":         "Yes" if m.is_permanent else "No",
        "Clusters":             mk_clusters,
        "State":                m.state    or "—",
        "District":             m.district or "—",
        "Taluka":               m.taluka   or "—",
        "Village":              m.village  or "—",
        "Crew Size":            m.crew_size,
        "Efficiency":           float(m.efficiency),
        "Farmer ID":            farmer.farmer_id,
        "Farmer Name":          farmer.farmer_name,
        "Farmer Phone":         farmer.phone_number or "—",
        "Farmer Location":      farmer.location     or "—",
        "Plot ID":              plot.pk              if plot else "",
        "Plot Name":            plot.name            if plot else "—",
        "Plot Area (ac)":       float(plot.area_acres) if plot else "",
        "Crop":                 (plot.crop_name if plot else "") or job.crop_name or "—",
        "Variety":              (plot.variety   if plot else "") or job.variety   or "—",
        "Job ID":               job.job_id,
        "Job Status":           job.status.replace("_"," ").title(),
        "Job Payment Status":   job.payment_status.title(),
        "Activity":             ja.activity.name,
        "Activity Order":       phase_order(ja.activity_id, ja.activity),
        "Is Strict":            "Yes" if ja.is_strict else "No",
        "JA Total Area (ac)":   float(ja.total_area),
        "JA Allocated Area (ac)": float(ja.allocated_area),
        "JA Alloc Status":      ja.allocation_status.replace("_"," ").title(),
        "JA Is Lost":           "Yes" if ja.is_lost else "No",
        "JA Lost Reason":       (ja.lost_reason or "—") if ja.is_lost else "—",
        "Scheduled Date":       ja.scheduled_date or "",
        "Sales Date":           ja.sales_date     or "",
        "Allocated Date":       alloc.allocated_date,
        "Allocated Area (ac)":  float(alloc.allocated_area),
        "Allocated Workers":    alloc.allocated_workers,
        "Allows 2nd Job":       "Yes" if alloc.allows_second_job  else "No",
        "Is Carry Forward":     "Yes" if alloc.is_carry_forward   else "No",
        "Is Auto Allocated":    "Yes" if alloc.is_auto_allocated  else "No",
        "Farmer Rate (INR/ac)":  float(alloc.farmer_rate),
        "Mukkadam Rate (INR/ac)":float(alloc.mukkadam_rate),
        "Farmer Amount (INR)":   float(alloc.farmer_amount),
        "Mukkadam Amount (INR)": float(alloc.mukkadam_amount),
        "Profit (INR)":          float(alloc.profit),
        "Work Status":           alloc.work_status.replace("_"," ").title(),
        "Allocation Status":     alloc.status.replace("_"," ").title(),
        "Payment Status":        alloc.payment_status.replace("_"," ").title(),
        "Actual Start Time":     fmt_dt(alloc.actual_start_time),
        "Actual End Time":       fmt_dt(alloc.actual_end_time),
        "Actual Crew Size":      alloc.actual_crew_size    or "",
        "Actual Area Done (ac)": float(alloc.actual_area_done) if alloc.actual_area_done else "",
        "Report Submitted":      "Yes" if alloc.report_submitted else "No",
        "Report Submitted At":   fmt_dt(alloc.report_submitted_at),
        "Farmer Agreed?":        fa,
        "Farmer Response At":    fmt_dt(alloc.farmer_response_at),
        "Farmer Dispute Reason": alloc.farmer_dispute_reason or "—",
        "Admin Override Area (ac)": float(alloc.admin_override_area) if alloc.admin_override_area else "",
        "Dispute Resolved By":   alloc.dispute_resolved_by.get_full_name() if alloc.dispute_resolved_by else "—",
        "Dispute Resolved At":   fmt_dt(alloc.dispute_resolved_at),
        "Created By":            alloc.created_by.get_full_name()       if alloc.created_by       else "—",
        "Created At":            fmt_dt(alloc.created_at),
        "Last Modified By":      alloc.last_modified_by.get_full_name() if alloc.last_modified_by else "—",
        "Last Modified At":      fmt_dt(alloc.last_modified_at),
        # internal
        "_alloc":     alloc,
        "_ja_lost":   ja.is_lost,
        "_carry_fwd": alloc.is_carry_forward,
    }


def _alloc_base_qs():
    return (
        Allocation.objects
        .select_related(
            "mukkadam",
            "job_activity", "job_activity__activity",
            "job_activity__job", "job_activity__job__farmer",
            "job_activity__plot",
            "created_by", "last_modified_by", "dispute_resolved_by",
        )
        .prefetch_related(
            "mukkadam__clusters",
            "job_activity__job__farmer__clusters",
        )
        .order_by("mukkadam__mukkadam_name", "allocated_date")
    )


def write_mukkadam_sheet(wb):
    ws = wb.create_sheet("Mukkadam Activity View")
    print("  Building Mukkadam Activity View (chunked)...")

    _write_group_row(ws, MUKKADAM_GROUPS, row_num=1)
    _write_header_row(ws, 2, MUKKADAM_HEADERS)
    ws.freeze_panes = "A3"

    total = _alloc_base_qs().count()
    print(f"     Total Allocations: {total}")

    ri        = 3
    processed = 0

    for offset in range(0, total, CHUNK_SIZE):
        chunk = list(_alloc_base_qs()[offset : offset + CHUNK_SIZE])

        for alloc in chunk:
            row = _alloc_to_row(alloc)
            bg_key = _mk_bg_key(row["_alloc"], row["_ja_lost"]) \
                     or ("alt" if ri % 2 == 0 else "pending")

            font = (
                _RED_FONT if row["_ja_lost"]     else
                _PUR_FONT if row["_carry_fwd"]   else
                _DATA_FONT
            )
            values = [(h, row.get(h)) for h in MUKKADAM_HEADERS]
            _write_data_row(ws, ri, values, bg_key,
                            MUKKADAM_LEFT, MUKKADAM_DATE, MUKKADAM_MONEY, font)
            ri += 1

        processed += len(chunk)
        print(f"     Mukkadam rows written: {processed}/{total}", end="\r")
        gc.collect()
        reset_queries()

    print()
    for ci, w in enumerate(MUKKADAM_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.auto_filter.ref = f"A2:{get_column_letter(len(MUKKADAM_HEADERS))}{ri - 1}"


# ─────────────────────────────────────────────────────────────────────────────
# LEGEND
# ─────────────────────────────────────────────────────────────────────────────

def write_legend(wb):
    ls = wb.create_sheet("Legend")
    entries = [
        ("COLOUR KEY (both sheets)", "",                                              True),
        ("Green",     "Completed work",                                               False),
        ("Light Blue","Allocated but not yet completed",                              False),
        ("Yellow",    "Partially allocated or On Hold",                               False),
        ("Orange",    "Lost activity or Disputed payment",                            False),
        ("Lilac",     "Carry-forward allocation (mukkadam sheet)",                    False),
        ("White/Grey","Pending — nothing allocated yet",                              False),
        ("",          "",                                                             False),
        ("FARMER ACTIVITY VIEW",  "1 row = 1 JobActivity",                           True),
        ("Work Status",           "Derived from all allocations on the activity",     False),
        ("Completed By",          "Mukkadam who completed (or best allocation)",      False),
        ("Actual Area Done",      "Area mukkadam reported at day-end",                False),
        ("Farmer Agreed?",        "Agreed / Disputed / Pending from OTP step",        False),
        ("Mukkadams Assigned",    "All mukkadams on this activity (pipe-separated)",  False),
        ("",          "",                                                             False),
        ("MUKKADAM ACTIVITY VIEW","1 row = 1 Allocation",                            True),
        ("Allows 2nd Job",        "Worker capacity NOT subtracted from daily limit",  False),
        ("Is Carry Forward",      "Auto-created when farmer reported < allocated",    False),
        ("Is Auto Allocated",     "Created by AI auto-allocation engine",             False),
        ("Admin Override Area",   "Team override after dispute resolution",           False),
        ("Profit (INR)",          "Farmer Amount minus Mukkadam Amount",              False),
        ("",          "",                                                             False),
        ("PERFORMANCE",           "",                                                 True),
        ("Chunk size",            f"{CHUNK_SIZE} rows fetched per DB round-trip",     False),
        ("Phase cache",           "phase_order() lookups cached in-process",          False),
        ("Style objects",         "Font/Fill/Alignment built once, reused every cell",False),
    ]
    for ri, (a, b, section) in enumerate(entries, 1):
        ca = ls.cell(ri, 1, a)
        cb = ls.cell(ri, 2, b)
        for c in (ca, cb):
            c.font = Font(
                name="Arial", bold=section, size=10,
                color="FFFFFF" if section else "000000",
            )
            if section:
                c.fill = _FILLS["section"]
    ls.column_dimensions["A"].width = 28
    ls.column_dimensions["B"].width = 62


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def build_excel(output_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    write_farmer_sheet(wb)
    write_mukkadam_sheet(wb)
    write_legend(wb)

    print(f"  Saving workbook...")
    wb.save(output_path)
    print(f"  Done -> {output_path}")


if __name__ == "__main__":
    # Optional: override chunk size via env var
    if "CHUNK_SIZE" in os.environ:
        CHUNK_SIZE = int(os.environ["CHUNK_SIZE"])

    default_out = os.path.join(BASE_DIR, "profiles_sheet.xlsx")
    out = sys.argv[1] if len(sys.argv) > 1 else default_out
    build_excel(out)