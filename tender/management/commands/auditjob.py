"""
Management command: audit_jobs
Usage:
    python manage.py audit_jobs \
        --api-url "https://your-api.com/api/endpoint/" \
        --token "your_token_here" \
        --output "/tmp/audit_report.xlsx"

What it checks:
  1. Job IDs  - in API but not in DB, in DB but not in API
  2. Activities - matched by api_activity_id first, then name+plot+date
  3. Plot       - does DB job-activity plot match API plot_id?
  4. Acres      - DB side can be split; sum per (activity_name, plot_id) vs API
  5. Rate       - DB rate_per_acre vs API (total_price / acres)
  6. Booking type - DB booking_type vs API booking_type
  7. Lost tag   - DB is_lost activities shown & matched / flagged separately
"""

import os
import sys
import django
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from datetime import datetime

# ── Allow running standalone: python audit_jobs.py ──────────────────────────
if __name__ == "__main__":
    # adjust this path to your Django project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "allocate.settings")  # ← CHANGE THIS
    django.setup()

from django.core.management.base import BaseCommand, CommandError

# ── colours ─────────────────────────────────────────────────────────────────
C_HEADER   = "1F4E79"   # dark blue  – header row
C_MATCH    = "E2EFDA"   # light green
C_MISMATCH = "FFE0B2"   # light orange
C_MISSING  = "FCE4EC"   # light red   – in API not in DB
C_EXTRA    = "E8EAF6"   # light purple – in DB not in API
C_LOST     = "FFF9C4"   # light yellow – is_lost rows
C_SECTION  = "BBDEFB"   # light blue   – section headers inside sheet

def _hex(c): return PatternFill("solid", start_color=c, fgColor=c)
def _bold(size=10, white=False):
    return Font(bold=True, size=size, color="FFFFFF" if white else "000000")


# ── helpers ──────────────────────────────────────────────────────────────────
def _round2(v):
    try:
        return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return v


def _api_rate(act):
    """Derive rate-per-acre from API activity dict."""
    try:
        acres = float(act["acres"])
        price = float(act["total_price"])
        if acres and acres > 0:
            return _round2(price / acres)
    except Exception:
        pass
    return None


def fetch_all_pages(base_url, token):
    """Fetch paginated API – keeps calling ?page=N until no more data."""
    headers = {"Authorization": f"Token {token}"}
    all_data = []
    url = base_url
    page = 1
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        # support both { data: [...] } and plain list
        if isinstance(body, list):
            chunk = body
            url = None
        elif isinstance(body, dict):
            chunk = body.get("data") or body.get("results") or []
            url   = body.get("next")          # DRF pagination
            if not url and body.get("count"):
                # manual page param style
                if len(chunk) > 0 and len(all_data) + len(chunk) < body["count"]:
                    page += 1
                    sep = "&" if "?" in base_url else "?"
                    url = f"{base_url}{sep}page={page}"
                else:
                    url = None
        else:
            break

        all_data.extend(chunk)
        if not url:
            break

    return all_data


# ── DB query helpers ─────────────────────────────────────────────────────────
def load_db_jobs(job_ids=None):
    """Return dict  job_id → Job instance."""
    from tender.models import Job   # adjust app name if different
    qs = Job.objects.all()
    if job_ids:
        qs = qs.filter(job_id__in=job_ids)
    return {j.job_id: j for j in qs}


def load_db_activities(job_ids):
    """
    Return nested dict:
        job_id → list of JobActivity dicts (with relevant fields)
    """
    from tender.models import JobActivity   # adjust app name
    qs = JobActivity.objects.filter(
        job_id__in=job_ids
    ).select_related("activity", "plot").values(
        "id",
        "job_id",
        "api_activity_id",
        "activity__name",
        "plot__plot_code",       # matches API plot_id
        "plot_id",               # DB plot FK id
        "total_area",
        "allocated_area",
        "rate_per_acre",
        "total_price",
        "scheduled_date",
        "allocation_status",
        "is_lost",
        "lost_reason",
        "source",
    )
    result = defaultdict(list)
    for row in qs:
        result[row["job_id"]].append(dict(row))
    return result


def load_db_bookings(job_ids):
    """Return  job_id → JobBooking dict."""
    from tender.models import JobBooking   # adjust app name
    qs = JobBooking.objects.filter(job__job_id__in=job_ids).values(
        "job__job_id", "booking_id", "status", "total_amount", "balance"
    )
    return {r["job__job_id"]: r for r in qs}


# ── matching logic ────────────────────────────────────────────────────────────
def match_activities(api_activities, db_activities):
    """
    Returns list of comparison rows.
    Each row: dict with keys used for Excel output.
    """
    rows = []

    # ── index DB activities ───────────────────────────────────────────────────
    # by api_activity_id (string)
    db_by_api_id   = {}
    # by (activity_name_normalised, plot_code)
    db_by_name_plot = defaultdict(list)

    unmatched_db = []

    for dba in db_activities:
        api_id = str(dba["api_activity_id"]).strip() if dba["api_activity_id"] else ""
        if api_id and api_id not in ("", "0", "None"):
            db_by_api_id[api_id] = dba
        name_key = (
            _norm(dba["activity__name"]),
            str(dba["plot__plot_code"] or "").strip(),
        )
        db_by_name_plot[name_key].append(dba)

    matched_db_ids = set()

    # ── match each API activity ───────────────────────────────────────────────
    # group API by (activity_name, plot_id) so we can sum split acres
    api_groups = defaultdict(list)
    for act in api_activities:
        key = (_norm(act["activity_name"]), str(act.get("plot_id", "") or ""))
        api_groups[key].append(act)

    for (api_name_norm, api_plot_id), grp in api_groups.items():
        api_total_acres = sum(float(a["acres"] or 0) for a in grp)
        api_total_price = sum(float(a["total_price"] or 0) for a in grp)
        api_rate        = _round2(api_total_price / api_total_acres) if api_total_acres else None
        api_ids_str     = ", ".join(str(a["id"]) for a in grp)
        api_name        = grp[0]["activity_name"]
        api_date        = grp[0].get("date_time", "")[:10] if grp[0].get("date_time") else ""

        # --- find DB match ---
        matched_dbs = []

        # try api_activity_id first
        for act in grp:
            aid = str(act["id"])
            if aid in db_by_api_id:
                dba = db_by_api_id[aid]
                if dba["id"] not in matched_db_ids:
                    matched_dbs.append(dba)
                    matched_db_ids.add(dba["id"])

        # fallback: name + plot_code
        if not matched_dbs:
            key = (api_name_norm, api_plot_id)
            candidates = [d for d in db_by_name_plot.get(key, [])
                          if d["id"] not in matched_db_ids]
            if candidates:
                matched_dbs = candidates
                for d in candidates:
                    matched_db_ids.add(d["id"])

        if not matched_dbs:
            # IN API, NOT IN DB
            rows.append({
                "status":           "IN_API_NOT_IN_DB",
                "api_activity_ids": api_ids_str,
                "api_activity_name":api_name,
                "api_plot_id":      api_plot_id,
                "api_date":         api_date,
                "api_acres":        api_total_acres,
                "api_rate":         api_rate,
                "api_total_price":  api_total_price,
                "db_ja_ids":        "",
                "db_activity_name": "",
                "db_plot_code":     "",
                "db_acres":         "",
                "db_rate":          "",
                "db_total_price":   "",
                "is_lost":          False,
                "lost_reason":      "",
                "plot_match":       "N/A",
                "acres_match":      "N/A",
                "rate_match":       "N/A",
                "notes":            "",
            })
            continue

        # --- we have DB matches ---
        db_total_acres = sum(float(d["total_area"] or 0) for d in matched_dbs)
        db_total_price = sum(float(d["total_price"] or 0) for d in matched_dbs)
        db_rate_values = list({_round2(float(d["rate_per_acre"] or 0)) for d in matched_dbs})
        db_rate_str    = " / ".join(str(r) for r in db_rate_values)
        db_ja_ids      = ", ".join(str(d["id"]) for d in matched_dbs)
        db_plot_codes  = ", ".join(str(d["plot__plot_code"] or d["plot_id"] or "") for d in matched_dbs)
        any_lost       = any(d["is_lost"] for d in matched_dbs)
        lost_reasons   = "; ".join(d["lost_reason"] or "" for d in matched_dbs if d["is_lost"])

        # plot match
        db_plot_set = set(str(d["plot__plot_code"] or "").strip() for d in matched_dbs)
        plot_match  = "✓" if api_plot_id in db_plot_set else "✗ MISMATCH"

        # acres match (within 0.01 tolerance for float comparison)
        acres_match = "✓" if abs(db_total_acres - api_total_acres) < 0.01 else "✗ MISMATCH"

        # rate match
        if api_rate is not None and len(db_rate_values) == 1:
            rate_match = "✓" if abs(db_rate_values[0] - api_rate) < 0.5 else "✗ MISMATCH"
        elif api_rate is None:
            rate_match = "N/A"
        else:
            rate_match = "SPLIT RATES"

        notes_parts = []
        if any_lost:
            notes_parts.append("IS_LOST")
        if len(matched_dbs) > 1:
            notes_parts.append(f"SPLIT into {len(matched_dbs)} DB rows")

        rows.append({
            "status":           "MATCHED" if (plot_match == "✓" and acres_match == "✓" and rate_match == "✓") else "MATCHED_WITH_ISSUES",
            "api_activity_ids": api_ids_str,
            "api_activity_name":api_name,
            "api_plot_id":      api_plot_id,
            "api_date":         api_date,
            "api_acres":        api_total_acres,
            "api_rate":         api_rate,
            "api_total_price":  api_total_price,
            "db_ja_ids":        db_ja_ids,
            "db_activity_name": matched_dbs[0]["activity__name"],
            "db_plot_code":     db_plot_codes,
            "db_acres":         db_total_acres,
            "db_rate":          db_rate_str,
            "db_total_price":   db_total_price,
            "is_lost":          any_lost,
            "lost_reason":      lost_reasons,
            "plot_match":       plot_match,
            "acres_match":      acres_match,
            "rate_match":       rate_match,
            "notes":            " | ".join(notes_parts),
        })

    # ── DB activities NOT matched to any API activity ─────────────────────────
    for dba in db_activities:
        if dba["id"] not in matched_db_ids:
            tag = "IN_DB_NOT_IN_API"
            if dba["is_lost"]:
                tag = "IN_DB_NOT_IN_API (LOST)"
            rows.append({
                "status":           tag,
                "api_activity_ids": "",
                "api_activity_name":"",
                "api_plot_id":      "",
                "api_date":         "",
                "api_acres":        "",
                "api_rate":         "",
                "api_total_price":  "",
                "db_ja_ids":        dba["id"],
                "db_activity_name": dba["activity__name"],
                "db_plot_code":     dba["plot__plot_code"] or dba["plot_id"] or "",
                "db_acres":         float(dba["total_area"] or 0),
                "db_rate":          _round2(float(dba["rate_per_acre"] or 0)),
                "db_total_price":   float(dba["total_price"] or 0),
                "is_lost":          dba["is_lost"],
                "lost_reason":      dba["lost_reason"] or "",
                "plot_match":       "N/A",
                "acres_match":      "N/A",
                "rate_match":       "N/A",
                "notes":            "IS_LOST" if dba["is_lost"] else "",
            })

    return rows


def _norm(s):
    """Normalise activity name for loose matching."""
    if not s:
        return ""
    return s.strip().lower().split("(")[0].strip()


# ── Excel builder ─────────────────────────────────────────────────────────────
ACTIVITY_COLS = [
    ("Status",               "status",            22),
    ("API Act IDs",          "api_activity_ids",  18),
    ("API Activity",         "api_activity_name", 35),
    ("API Plot ID",          "api_plot_id",       14),
    ("API Date",             "api_date",          14),
    ("API Acres",            "api_acres",         12),
    ("API Rate/Acre",        "api_rate",          14),
    ("API Total Price",      "api_total_price",   16),
    ("DB JA IDs",            "db_ja_ids",         14),
    ("DB Activity",          "db_activity_name",  35),
    ("DB Plot Code",         "db_plot_code",      14),
    ("DB Acres (sum)",       "db_acres",          14),
    ("DB Rate/Acre",         "db_rate",           14),
    ("DB Total Price",       "db_total_price",    16),
    ("Plot Match",           "plot_match",        14),
    ("Acres Match",          "acres_match",       14),
    ("Rate Match",           "rate_match",        14),
    ("Is Lost",              "is_lost",           10),
    ("Lost Reason",          "lost_reason",       25),
    ("Notes",                "notes",             30),
]


def _row_fill(status, is_lost):
    if is_lost:
        return _hex(C_LOST)
    if status == "IN_API_NOT_IN_DB":
        return _hex(C_MISSING)
    if "IN_DB_NOT_IN_API" in status:
        return _hex(C_EXTRA)
    if status == "MATCHED_WITH_ISSUES":
        return _hex(C_MISMATCH)
    if status == "MATCHED":
        return _hex(C_MATCH)
    return None


def build_excel(job_results, output_path):
    """
    job_results: list of dicts, each with keys:
        job_id, db_job_found, api_booking_type, db_booking_type,
        booking_type_match, activity_rows
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)   # remove default sheet

    # ── SUMMARY sheet ────────────────────────────────────────────────────────
    ws_sum = wb.create_sheet("Summary")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    sum_headers = [
        "Job ID", "Job in DB?", "API Booking Type", "DB Booking Type",
        "Booking Type Match", "Total API Acts", "Matched", "Matched w/ Issues",
        "In API Not DB", "In DB Not API", "Lost Acts in DB",
    ]
    for ci, h in enumerate(sum_headers, 1):
        c = ws_sum.cell(1, ci, h)
        c.font = _bold(10, white=True)
        c.fill = _hex(C_HEADER)
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = border

    ws_sum.row_dimensions[1].height = 28

    for ri, jr in enumerate(job_results, 2):
        acts = jr["activity_rows"]
        vals = [
            jr["job_id"],
            "Yes" if jr["db_job_found"] else "No",
            jr["api_booking_type"],
            jr["db_booking_type"],
            "✓" if jr["booking_type_match"] else "✗ MISMATCH",
            sum(1 for a in acts if a["api_activity_ids"]),
            sum(1 for a in acts if a["status"] == "MATCHED"),
            sum(1 for a in acts if a["status"] == "MATCHED_WITH_ISSUES"),
            sum(1 for a in acts if a["status"] == "IN_API_NOT_IN_DB"),
            sum(1 for a in acts if "IN_DB_NOT_IN_API" in a["status"]),
            sum(1 for a in acts if a["is_lost"]),
        ]
        for ci, v in enumerate(vals, 1):
            c = ws_sum.cell(ri, ci, v)
            c.border = border
            c.alignment = Alignment(horizontal="center")
            if ci == 5 and v == "✗ MISMATCH":
                c.fill = _hex(C_MISMATCH)
                c.font = Font(bold=True)
            if not jr["db_job_found"] and ci == 2:
                c.fill = _hex(C_MISSING)
                c.font = Font(bold=True)

    for ci, h in enumerate(sum_headers, 1):
        ws_sum.column_dimensions[get_column_letter(ci)].width = max(14, len(h) + 2)

    # ── Per-job detail sheets ─────────────────────────────────────────────────
    for jr in job_results:
        safe_name = str(jr["job_id"])[:31]   # sheet name max 31 chars
        ws = wb.create_sheet(safe_name)

        # job meta header band
        meta_info = [
            ("Job ID", jr["job_id"]),
            ("DB Found", "Yes" if jr["db_job_found"] else "No"),
            ("API Booking Type", jr["api_booking_type"]),
            ("DB Booking Type",  jr["db_booking_type"]),
            ("Booking Type Match", "✓" if jr["booking_type_match"] else "✗ MISMATCH"),
        ]
        for ri, (k, v) in enumerate(meta_info, 1):
            ws.cell(ri, 1, k).font = Font(bold=True)
            c = ws.cell(ri, 2, str(v))
            if k == "Booking Type Match" and v == "✗ MISMATCH":
                c.fill = _hex(C_MISMATCH)
                c.font = Font(bold=True)

        # column headers
        header_row = len(meta_info) + 2
        for ci, (hdr, _, width) in enumerate(ACTIVITY_COLS, 1):
            c = ws.cell(header_row, ci, hdr)
            c.font = _bold(10, white=True)
            c.fill = _hex(C_HEADER)
            c.alignment = Alignment(horizontal="center", wrap_text=True)
            c.border = border
            ws.column_dimensions[get_column_letter(ci)].width = width
        ws.row_dimensions[header_row].height = 28

        # data rows
        for ri2, act in enumerate(jr["activity_rows"], header_row + 1):
            fill = _row_fill(act["status"], act["is_lost"])
            for ci, (_, key, _) in enumerate(ACTIVITY_COLS, 1):
                v = act.get(key, "")
                if isinstance(v, bool):
                    v = "Yes" if v else "No"
                c = ws.cell(ri2, ci, v)
                c.border = border
                c.alignment = Alignment(horizontal="center" if ci > 2 else "left",
                                         wrap_text=False)
                if fill:
                    c.fill = fill
                # highlight individual mismatch cells
                if key in ("plot_match", "acres_match", "rate_match") and str(v).startswith("✗"):
                    c.fill = _hex("FF5252")
                    c.font = Font(bold=True, color="FFFFFF")
                elif key in ("plot_match", "acres_match", "rate_match") and str(v) == "✓":
                    c.fill = _hex("388E3C")
                    c.font = Font(bold=True, color="FFFFFF")

        ws.freeze_panes = f"A{header_row + 1}"

    # ── Legend sheet ─────────────────────────────────────────────────────────
    ws_leg = wb.create_sheet("Legend")
    legend = [
        (C_MATCH,    "MATCHED",              "All fields match"),
        (C_MISMATCH, "MATCHED_WITH_ISSUES",  "Matched but plot/acres/rate mismatch"),
        (C_MISSING,  "IN_API_NOT_IN_DB",     "Activity in API but not found in DB"),
        (C_EXTRA,    "IN_DB_NOT_IN_API",     "Activity in DB but not found in API"),
        (C_LOST,     "IS_LOST",              "Activity flagged is_lost=True in DB"),
    ]
    ws_leg.cell(1, 1, "Legend").font = _bold(12)
    for ri, (colour, label, desc) in enumerate(legend, 3):
        c = ws_leg.cell(ri, 1)
        c.fill = _hex(colour)
        c.value = label
        c.font = Font(bold=True)
        ws_leg.cell(ri, 2, desc)
    ws_leg.column_dimensions["A"].width = 28
    ws_leg.column_dimensions["B"].width = 50

    wb.save(output_path)
    return output_path


# ── Django Management Command ─────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Audit API jobs vs DB: matches job-activities, plots, acres, rates → Excel"

    def add_arguments(self, parser):
        parser.add_argument("--api-url",  required=True,
                            help="Full API endpoint URL (paginated list of jobs/works)")
        parser.add_argument("--token",    required=True,
                            help="API auth token")
        parser.add_argument("--output",   default="audit_report.xlsx",
                            help="Output Excel file path (default: audit_report.xlsx)")
        parser.add_argument("--job-ids",  nargs="*",
                            help="Optional: limit to specific job IDs (work_id or job_id)")

    def handle(self, *args, **options):
        api_url    = options["api_url"]
        token      = options["token"]
        output     = options["output"]
        filter_ids = set(options.get("job_ids") or [])

        self.stdout.write("Fetching API data…")
        api_jobs = fetch_all_pages(api_url, token)
        self.stdout.write(f"  → {len(api_jobs)} jobs from API")

        if filter_ids:
            api_jobs = [j for j in api_jobs
                        if str(j.get("id")) in filter_ids
                        or str(j.get("work_id","")) in filter_ids]
            self.stdout.write(f"  → filtered to {len(api_jobs)} jobs")

        # map api job id → api job
        api_job_map = {}
        for j in api_jobs:
            # API uses numeric id as the work/job identifier
            api_job_map[str(j["id"])] = j

        api_job_ids = set(api_job_map.keys())

        self.stdout.write("Loading DB data…")
        db_jobs     = load_db_jobs(api_job_ids)
        db_acts_map = load_db_activities(api_job_ids)
        db_bookings = load_db_bookings(api_job_ids)

        db_job_ids  = set(db_jobs.keys())

        # jobs in DB not in API (outside scope, just informational)
        # (we only look at jobs present in API response)

        job_results = []

        for api_id, api_job in api_job_map.items():
            db_job_found = api_id in db_jobs
            db_job       = db_jobs.get(api_id)

            api_booking_type = ""
            if api_job.get("booking"):
                api_booking_type = api_job["booking"].get("booking_type", "")

            db_booking_type  = ""
            if db_job:
                db_booking_type = db_job.booking_type or ""

            booking_type_match = (
                api_booking_type.lower().strip() == db_booking_type.lower().strip()
                if api_booking_type and db_booking_type else False
            )

            # activities
            api_activities = api_job.get("activities", [])
            # filter out 0-acre API activities
            api_activities = [a for a in api_activities if float(a.get("acres") or 0) > 0]

            db_activities = db_acts_map.get(api_id, [])

            activity_rows = match_activities(api_activities, db_activities)

            job_results.append({
                "job_id":             api_id,
                "db_job_found":       db_job_found,
                "api_booking_type":   api_booking_type,
                "db_booking_type":    db_booking_type,
                "booking_type_match": booking_type_match,
                "activity_rows":      activity_rows,
            })

        # jobs in API not found in DB → add summary entries for them
        missing_jobs = [r for r in job_results if not r["db_job_found"]]
        if missing_jobs:
            self.stdout.write(
                self.style.WARNING(f"  ⚠  {len(missing_jobs)} API job(s) not found in DB: "
                                   f"{[r['job_id'] for r in missing_jobs]}")
            )

        self.stdout.write(f"Building Excel report → {output}")
        build_excel(job_results, output)

        # quick console summary
        total_acts   = sum(len(r["activity_rows"]) for r in job_results)
        matched      = sum(1 for r in job_results for a in r["activity_rows"] if a["status"] == "MATCHED")
        issues       = sum(1 for r in job_results for a in r["activity_rows"] if a["status"] == "MATCHED_WITH_ISSUES")
        missing_acts = sum(1 for r in job_results for a in r["activity_rows"] if a["status"] == "IN_API_NOT_IN_DB")
        extra_acts   = sum(1 for r in job_results for a in r["activity_rows"] if "IN_DB_NOT_IN_API" in a["status"])
        lost_acts    = sum(1 for r in job_results for a in r["activity_rows"] if a["is_lost"])

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Report saved: {output}\n"
            f"   Jobs processed      : {len(job_results)}\n"
            f"   Jobs not in DB      : {len(missing_jobs)}\n"
            f"   Total activity rows : {total_acts}\n"
            f"     Matched OK        : {matched}\n"
            f"     Matched w/ issues : {issues}\n"
            f"     In API not in DB  : {missing_acts}\n"
            f"     In DB not in API  : {extra_acts}\n"
            f"     Is Lost (DB)      : {lost_acts}\n"
        ))


# ── standalone entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit API vs DB job activities")
    parser.add_argument("--api-url",  required=True)
    parser.add_argument("--token",    required=True)
    parser.add_argument("--output",   default="audit_report.xlsx")
    parser.add_argument("--job-ids",  nargs="*")
    args = parser.parse_args()

    cmd = Command()
    cmd.stdout = type("S", (), {"write": lambda self, s: print(s)})()
    cmd.style  = type("S", (), {
        "SUCCESS": lambda self, s: s,
        "WARNING": lambda self, s: s,
    })()
    cmd.handle(
        api_url=args.api_url,
        token=args.token,
        output=args.output,
        job_ids=args.job_ids,
    )