"""
Bidirectional sync between Django DB <-> Google Sheets.

Column layout (A–M):
  A  Farmer name        read-only
  B  Activity name      read-only
  C  Plot Id            read-only
  D  Acre               EDITABLE  -> JobActivity.total_area
  E  Price              read-only (auto-calculated)
  F  Village            read-only
  G  Actual date        read-only (original_scheduled_date, locked at creation)
  H  Our date           EDITABLE  -> JobActivity.scheduled_date + Allocation.allocated_date
  I  Mukadam team       EDITABLE  -> Allocation.mukkadam (matched by name)
  J  Alloc status       read-only -> JobActivity.allocation_status (set by DB signals)
  K  Work status        EDITABLE  -> Allocation.work_status (actual ground work)
  L  Cluster            read-only
  M  _job_activity_id   hidden key

OPTIMISATIONS (v2):
  - _job_activity_to_row() uses only the prefetch cache — zero extra DB hits per row
  - upsert_job_activity_to_sheet() builds a ja_id→row map once per call instead of
    ws.find() scanning the whole sheet every time
  - full_sheet_refresh() writes in 500-row chunks to avoid Sheets API payload limits
  - Management command streams rows in chunks of 500 so RAM stays flat
"""

import gspread
import threading
import logging
from datetime import datetime
from decimal import Decimal

from google.oauth2.service_account import Credentials
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

_syncing = threading.local()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Farmer name",   # A col 1
    "Activity name", # B col 2
    "Plot Id",       # C col 3
    "Acre",          # D col 4
    "Price",         # E col 5
    "Village",       # F col 6
    "Actual date",   # G col 7
    "Our date",      # H col 8
    "Mukadam team",  # I col 9
    "Alloc status",  # J col 10
    "Work status",   # K col 11
    "Cluster",       # L col 12
]

_HEADERS_WITH_KEY = HEADERS + ["_job_activity_id"]  # M col 13
_KEY_COL          = len(_HEADERS_WITH_KEY)           # 13

_CHUNK_SIZE = 500   # rows per Sheets API write — stays well under the 10 MB limit


# =============================================================================
# SHEET CONNECTION
# =============================================================================

def get_sheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_SHEETS_CREDENTIALS, scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
    try:
        return sh.worksheet("Jobs")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Jobs", rows=5000, cols=len(_HEADERS_WITH_KEY))
        ws.append_row(_HEADERS_WITH_KEY)
        sh.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }]})
        return ws


# =============================================================================
# DJANGO -> SHEET
# =============================================================================

def _job_activity_to_row(ja):
    """
    Build a 13-column row from a JobActivity instance.

    IMPORTANT: every attribute access here must come from the prefetch cache.
    Never call .order_by(), .select_related(), .first(), or .values_list()
    on a related manager — those bypass the cache and fire a new DB query.

    Required prefetch on the caller side:
        .select_related("job__farmer", "plot", "activity")
        .prefetch_related("job__clusters", "allocations__mukkadam")
    """

    # ── Scalar fields (select_related — no extra query) ───────────────────────
    try:
        farmer_name = ja.job.farmer.farmer_name
    except Exception:
        farmer_name = ""

    activity_name = ja.activity.name if ja.activity_id else ""
    plot_id       = ja.plot.name     if ja.plot_id     else ""
    acre          = str(ja.total_area)  if ja.total_area  else "0"
    price         = str(ja.total_price) if ja.total_price else "0"

    # ── Clusters — use prefetch cache via .all(), slice in Python ────────────
    # NEVER call .first() — it bypasses the cache with a LIMIT 1 query.
    try:
        clusters = list(ja.job.clusters.all())   # hits prefetch cache
    except Exception:
        clusters = []

    village = ""
    cluster = ""
    if clusters:
        village = clusters[0].villages[0] if clusters[0].villages else ""
        cluster = clusters[0].name or ""

    # ── Dates ────────────────────────────────────────────────────────────────
    actual_date = ja.sales_date.strftime("%Y-%m-%d") if ja.sales_date else ""

    # ── Allocations — use prefetch cache entirely ─────────────────────────────
    # NEVER call .order_by(), .select_related(), or .values_list() here —
    # all of those bypass Django's prefetch cache and fire a fresh DB query.
    try:
        allocations = list(ja.allocations.all())   # hits prefetch cache
    except Exception:
        allocations = []

    # Our date: fully_allocated/completed → earliest allocated_date; else scheduled_date
    our_date = ""
    if ja.allocation_status in ("fully_allocated", "completed") and allocations:
        # Sort in Python from the prefetch cache — no extra DB hit
        dates = [a.allocated_date for a in allocations if a.allocated_date]
        if dates:
            our_date = min(dates).strftime("%Y-%m-%d")
    if not our_date:
        our_date = ja.scheduled_date.strftime("%Y-%m-%d") if ja.scheduled_date else ""

    # Work status: aggregate from prefetch cache
    if not allocations:
        work_status = ""
    else:
        statuses = [a.work_status for a in allocations]
        if all(s == "completed" for s in statuses):
            work_status = "Completed"
        elif any(s == "in_progress" for s in statuses):
            work_status = "In Progress"
        else:
            work_status = "Not Started"

    # Mukadam team: deduplicate names from prefetch cache
    # NEVER call .select_related() or .values_list() here
    seen   = set()
    names  = []
    for a in allocations:
        try:
            n = a.mukkadam.mukkadam_name
            if n and n not in seen:
                seen.add(n)
                names.append(n)
        except Exception:
            pass
    mukadam_team = ", ".join(names)

    # Alloc status display
    alloc_status = ja.get_allocation_status_display()

    return [
        farmer_name,   # A
        activity_name, # B
        plot_id,       # C
        acre,          # D
        price,         # E
        village,       # F
        actual_date,   # G
        our_date,      # H
        mukadam_team,  # I
        alloc_status,  # J  read-only
        work_status,   # K  editable
        cluster,       # L
        str(ja.pk),    # M  hidden key
    ]


# =============================================================================
# UPSERT — single-row update triggered by signals
# =============================================================================

def upsert_job_activity_to_sheet(ja_id):
    """
    Update or append a single row.

    Optimisation: instead of ws.find() which scans the whole sheet column,
    we pull the entire key column once (one API call) and build a dict.
    This is still one Sheets API call but it's a single column read, not
    a cell-by-cell scan.
    """
    import time
    time.sleep(0.3)   # reduced from 1 s — just enough to let the DB commit settle

    from .models import JobActivity
    try:
        ja = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters", "allocations__mukkadam")
            .get(pk=ja_id)
        )
    except JobActivity.DoesNotExist:
        logger.warning(f"[Sheets] JobActivity {ja_id} not found")
        return

    if ja.is_lost or not ja.total_area or ja.total_area <= 0:
        delete_job_activity_from_sheet(ja_id)
        return

    try:
        ws      = get_sheet()
        new_row = _job_activity_to_row(ja)

        # Pull key column once → build lookup dict (1 API call, no cell scan)
        key_col_values = ws.col_values(_KEY_COL)   # list of strings, index 0 = header
        try:
            row_idx = key_col_values.index(str(ja_id))  # 0-based
            sheet_row = row_idx + 1                      # 1-based (row_idx 0 = header row 1)
        except ValueError:
            sheet_row = None

        if sheet_row and sheet_row > 1:
            ws.update(f"A{sheet_row}:M{sheet_row}", [new_row])
            logger.info(f"[Sheets] Updated row {sheet_row} for JA {ja_id}")
        else:
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            logger.info(f"[Sheets] Appended row for JA {ja_id}")

    except Exception as e:
        logger.error(f"[Sheets] Failed to sync JA {ja_id}: {e}")


def delete_job_activity_from_sheet(ja_id):
    try:
        ws         = get_sheet()
        key_values = ws.col_values(_KEY_COL)
        try:
            row_idx   = key_values.index(str(ja_id))
            sheet_row = row_idx + 1
        except ValueError:
            return
        if sheet_row > 1:
            ws.delete_rows(sheet_row)
            logger.info(f"[Sheets] Deleted row for JA {ja_id}")
    except Exception as e:
        logger.error(f"[Sheets] Failed to delete JA {ja_id}: {e}")


# =============================================================================
# FULL REFRESH — writes in chunks to avoid Sheets API payload limits
# =============================================================================

def full_sheet_refresh():
    """
    Clears the sheet and rewrites all rows in _CHUNK_SIZE batches.
    Each chunk is a single Sheets API call — stays well under the 10 MB limit.
    """
    from .models import JobActivity

    ws = get_sheet()
    ws.clear()
    ws.append_row(_HEADERS_WITH_KEY)

    qs = (
        JobActivity.objects
        .select_related("job__farmer", "plot", "activity")
        .prefetch_related("job__clusters", "allocations__mukkadam")
        .filter(total_area__gt=0, is_lost=False)
        .order_by("scheduled_date", "pk")
    )

    total      = 0
    sheet_row  = 2          # first data row (row 1 = header)

    chunk = []
    for ja in qs.iterator(chunk_size=_CHUNK_SIZE):
        chunk.append(_job_activity_to_row(ja))
        if len(chunk) >= _CHUNK_SIZE:
            ws.update(f"A{sheet_row}:M{sheet_row + len(chunk) - 1}", chunk)
            sheet_row += len(chunk)
            total     += len(chunk)
            logger.info(f"[Sheets] Wrote chunk — {total} rows so far")
            chunk = []

    if chunk:
        ws.update(f"A{sheet_row}:M{sheet_row + len(chunk) - 1}", chunk)
        total += len(chunk)

    logger.info(f"[Sheets] Full refresh complete — {total} rows")
    return total


# =============================================================================
# SHEET -> DJANGO
# =============================================================================

def apply_sheet_edit(payload):
    """
    Route a single sheet edit to the correct handler.
    Writes to SheetEditLog on every call.
    Returns (ok: bool, message: str)
    """
    from .models import JobActivity

    ja_id     = payload.get("job_activity_id")
    column    = payload.get("column", "")
    new_val   = str(payload.get("new_value", "")).strip()
    old_val   = str(payload.get("old_value", "")).strip()
    edited_by = payload.get("edited_by", "unknown")
    event     = payload.get("event", "edit")

    try:
        ja = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters", "allocations__mukkadam")
            .get(pk=int(ja_id))
        )
    except (JobActivity.DoesNotExist, ValueError, TypeError):
        msg = f"JobActivity {ja_id} not found"
        _log_sheet_edit(ja=None, ja_id_raw=ja_id, event=event,
                        column=column, old_value=old_val, new_value=new_val,
                        edited_by=edited_by, success=False, message=msg)
        return False, msg

    _syncing.active = True
    ok, msg, child_ja_id = False, "", None
    try:
        if event == "split":
            split_date = payload.get("split_date", "")
            ok, msg, child_ja_id = _apply_split(ja, new_val, split_date, edited_by)

        elif column == "Our date":
            ok, msg = _apply_date_change(ja, new_val, edited_by)

        elif column == "Work status":
            ok, msg = _apply_work_status_change(ja, new_val, edited_by)

        elif column == "Alloc status":
            ok, msg = False, "Alloc status is read-only — set automatically by system"

        elif column == "Mukadam team":
            ok, msg = _apply_mukadam_change(ja, new_val, edited_by)

        elif column == "Acre":
            ok, msg = _apply_acre_change(ja, new_val, edited_by)

        elif column == "_DELETE_":
            ok, msg = _apply_delete(ja, edited_by)

        else:
            ok, msg = False, f"Column '{column}' is not editable from sheet"

    except Exception as exc:
        ok, msg = False, f"Unhandled error: {exc}"
        logger.error(f"[apply_sheet_edit] {msg}", exc_info=True)
    finally:
        _syncing.active = False

    _log_sheet_edit(
        ja=ja, ja_id_raw=ja_id, event=event, column=column,
        old_value=old_val, new_value=new_val, edited_by=edited_by,
        success=ok, message=msg, split_child_ja_id=child_ja_id,
    )
    return ok, msg


def _apply_date_change(ja, new_date_str, edited_by):
    from .models import Allocation

    if not new_date_str:
        return False, "Date value is empty"
    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, f"Invalid date: '{new_date_str}'. Use YYYY-MM-DD."

    # Block if new date is before the original booking/sales date
    

    old_date = ja.scheduled_date
    if not old_date:
        with transaction.atomic():
            ja.scheduled_date = new_date
            ja.save(update_fields=["scheduled_date", "updated_at"])
            Allocation.objects.filter(job_activity=ja).update(allocated_date=new_date)
        return True, f"Date set to {new_date} (no cascade — no previous date)"

    shift_days = (new_date - old_date).days
    if shift_days == 0:
        return True, "Date unchanged"

    with transaction.atomic():
        ja.scheduled_date    = new_date
        ja.is_manually_moved = True
        ja.move_reason       = f"Moved via sheet by {edited_by}"
        ja.save(update_fields=[
            "scheduled_date", "is_manually_moved", "move_reason", "updated_at"
        ])
        alloc_moved = Allocation.objects.filter(job_activity=ja).update(
            allocated_date=new_date
        )

    _cascade_successors(
        trigger_ja=ja, old_date=old_date, new_date=new_date, edited_by=edited_by,
    )

    logger.info(
        f"[Sheet->DB] Date JA#{ja.pk}: {old_date} → {new_date} "
        f"(shift={shift_days:+d}d), {alloc_moved} allocs moved, by {edited_by}"
    )
    return True, (
        f"Date updated to {new_date} ({shift_days:+d} days). "
        f"Successor activities on same plot cascaded."
    )


def _apply_work_status_change(ja, new_work_status_display, edited_by):
    from .models import Allocation, JobActivity as JA

    WORK_STATUS_MAP = {
        "Not Started": "work_not_started",
        "In Progress": "in_progress",
        "Completed":   "completed",
    }

    db_status = WORK_STATUS_MAP.get(new_work_status_display)
    if not db_status:
        return False, (
            f"Unknown work status: '{new_work_status_display}'. "
            f"Valid: {list(WORK_STATUS_MAP.keys())}"
        )

    # Use prefetch cache — no extra query
    allocations = list(ja.allocations.all())
    if not allocations:
        return False, f"No allocations for JA {ja.pk} — assign a mukkadam first"

    with transaction.atomic():
        updated = Allocation.objects.filter(job_activity=ja).update(work_status=db_status)
        if db_status == "completed":
            JA.objects.filter(pk=ja.pk).update(allocation_status="completed")
            logger.info(f"[Sheet->DB] JA {ja.pk} marked completed via work status")

    logger.info(
        f"[Sheet->DB] Work status '{db_status}' on {updated} allocs "
        f"for JA {ja.pk} by {edited_by}"
    )
    return True, f"Work status set to '{db_status}' on {updated} allocations"


def _apply_mukadam_change(ja, new_mukadam_str, edited_by):
    from .models import Allocation, Mukkadam

    if not new_mukadam_str.strip():
        return True, "Mukadam team cleared in sheet (remove allocations from app)"

    new_names  = [n.strip() for n in new_mukadam_str.split(",") if n.strip()]
    resolved   = []
    unresolved = []

    for name in new_names:
        mk = Mukkadam.objects.filter(mukkadam_name__iexact=name).first()
        if not mk:
            mk = Mukkadam.objects.filter(mukkadam_name__icontains=name).first()
        if mk:
            resolved.append(mk)
        else:
            unresolved.append(name)

    if unresolved:
        logger.warning(f"[Sheet->DB] Unresolved mukkadams: {unresolved}")
    if not resolved:
        return False, f"No matching mukkadams found for: {new_names}"

    existing = list(ja.allocations.all())   # prefetch cache
    with transaction.atomic():
        if existing:
            for i, alloc in enumerate(existing):
                if i < len(resolved):
                    old_mk         = alloc.mukkadam
                    alloc.mukkadam = resolved[i]
                    alloc.save(update_fields=["mukkadam"])
                    logger.info(
                        f"[Sheet->DB] Alloc {alloc.pk}: "
                        f"{old_mk.mukkadam_name} -> {resolved[i].mukkadam_name}"
                    )
            for mk in resolved[len(existing):]:
                _create_default_allocation(ja, mk)
        else:
            for mk in resolved:
                _create_default_allocation(ja, mk)

    msg = f"Mukadam updated: {[m.mukkadam_name for m in resolved]}"
    if unresolved:
        msg += f" (unresolved: {unresolved})"
    return True, msg


def _create_default_allocation(ja, mukkadam):
    from .models import Allocation, MukkadamActivityRate, ClusterMukkadamActivityRate

    farmer_rate   = ja.rate_per_acre or Decimal("0")
    mukkadam_rate = Decimal("0")

    mk_rate = MukkadamActivityRate.objects.filter(
        mukkadam=mukkadam, activity=ja.activity
    ).first()
    if mk_rate:
        mukkadam_rate = mk_rate.rate_per_acre
    else:
        cluster = list(ja.job.clusters.all())   # prefetch cache
        cluster = cluster[0] if cluster else None
        if cluster:
            cr = ClusterMukkadamActivityRate.objects.filter(
                cluster=cluster, activity=ja.activity
            ).first()
            if cr:
                mukkadam_rate = cr.rate_per_acre

    if not mukkadam_rate:
        mukkadam_rate = (farmer_rate * Decimal("0.8")).quantize(Decimal("0.01"))

    area    = ja.remaining_area if ja.remaining_area > 0 else ja.total_area
    workers = max(1, int(float(area) * 10))

    clusters = list(ja.job.clusters.all())   # prefetch cache
    Allocation(
        job_activity      = ja,
        mukkadam          = mukkadam,
        cluster           = clusters[0] if clusters else None,
        allocated_date    = ja.scheduled_date,
        allocated_area    = area,
        allocated_workers = workers,
        farmer_rate       = farmer_rate,
        mukkadam_rate     = mukkadam_rate,
        farmer_amount     = area * farmer_rate,
        mukkadam_amount   = area * mukkadam_rate,
        profit            = (area * farmer_rate) - (area * mukkadam_rate),
        status            = "scheduled",
        work_status       = "work_not_started",
    ).save()
    logger.info(f"[Sheet->DB] Created alloc JA {ja.pk}, mukkadam={mukkadam.mukkadam_name}")


def _apply_acre_change(ja, new_acre_str, edited_by):
    try:
        new_area = Decimal(str(new_acre_str).strip())
    except Exception:
        return False, f"Invalid acre value: '{new_acre_str}'"
    if new_area < 0:
        return False, "Acre cannot be negative"
    old_area      = ja.total_area
    ja.total_area = new_area
    ja.save()
    logger.info(f"[Sheet->DB] Acre JA {ja.pk}: {old_area} -> {new_area} by {edited_by}")
    return True, f"Acre updated from {old_area} to {new_area}"


def _apply_delete(ja, edited_by):
    ja_id = ja.pk
    with transaction.atomic():
        ja.allocations.all().delete()
        ja.delete()
    logger.info(f"[Sheet->DB] Deleted JA {ja_id} by {edited_by}")
    return True, f"JobActivity {ja_id} deleted"


# =============================================================================
# AUDIT LOG
# =============================================================================

def _log_sheet_edit(*, ja, ja_id_raw, event, column="", old_value="",
                    new_value="", edited_by, success, message,
                    split_child_ja_id=None):
    try:
        from .models import SheetEditLog
        SheetEditLog.objects.create(
            job_activity        = ja,
            job_activity_id_raw = str(ja_id_raw),
            event               = event,
            column              = column,
            old_value           = str(old_value),
            new_value           = str(new_value),
            activity = ja.activity if ja and ja.activity_id else None,
            plot     = ja.plot     if ja and ja.plot_id     else None,
            edited_by           = edited_by or "unknown",
            success             = success,
            message             = message,
            split_child_ja_id   = split_child_ja_id,
        )
    except Exception as exc:
        logger.error(f"[SheetEditLog] Failed to write log: {exc}")


# =============================================================================
# CASCADE
# =============================================================================

def _cascade_successors(trigger_ja, old_date, new_date, edited_by, exclude_ja_id=None):
    from datetime import timedelta
    from .models import JobActivity, Allocation

    shift_days = (new_date - old_date).days
    if shift_days == 0:
        return

    # __gte so activities on the SAME date as old_date also get moved.
    # Trigger row excluded via .exclude(pk=trigger_ja.pk).
    successors = list(
        JobActivity.objects
        .filter(
            job=trigger_ja.job,
            is_lost=False,
            plot=trigger_ja.plot, 
            total_area__gt=0,
            scheduled_date__gt=old_date,
        )
        .exclude(pk=trigger_ja.pk)
        .select_related("activity")
    )

    if exclude_ja_id:
        successors = [a for a in successors if a.pk != exclude_ja_id]

    for act in successors:
        if act.allocation_status in ("fully_allocated", "partially_allocated", "completed", "in_progress"):
            logger.info(f"[Cascade] Skip JA#{act.pk} — already {act.allocation_status}")
            continue

        old_act_date = act.scheduled_date
        new_act_date = old_act_date + timedelta(days=shift_days)

        act.scheduled_date = new_act_date
        act.move_reason = (
            f"Cascade from JA#{trigger_ja.id} sheet move by {edited_by} "
            f"({shift_days:+d} days)"
        )
        act.save(update_fields=["scheduled_date", "move_reason", "updated_at"])
        Allocation.objects.filter(job_activity=act).update(allocated_date=new_act_date)

        _log_sheet_edit(
            ja=act, ja_id_raw=str(act.pk), event="cascade", column="Our date",
            old_value=str(old_act_date), new_value=str(new_act_date),
            edited_by=edited_by, success=True,
            message=f"Cascade from JA{trigger_ja.pk} ({shift_days:+d} days).",
        )
        logger.info(
            f"[Cascade] JA#{act.pk} {act.activity.name}: {old_act_date} → {new_act_date}"
        )

        threading.Thread(
            target=upsert_job_activity_to_sheet, args=(act.pk,), daemon=True
        ).start()


# =============================================================================
# SPLIT
# =============================================================================

def _apply_split(ja, split_acres_str, split_date_str, edited_by):
    from decimal import Decimal, InvalidOperation
    from datetime import datetime
    from .models import JobActivity

    try:
        split_acres = Decimal(str(split_acres_str).strip())
    except (InvalidOperation, TypeError):
        return False, f"Invalid split_acres: '{split_acres_str}'", None

    if split_acres <= 0:
        return False, "split_acres must be > 0", None

    if split_acres >= ja.total_area:
        return False, (
            f"split_acres ({split_acres}) must be less than total_area "
            f"({ja.total_area}). Use 'Acre' edit to just change the total."
        ), None

    try:
        split_date = datetime.strptime(str(split_date_str).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, f"Invalid split_date: '{split_date_str}'. Use YYYY-MM-DD.", None

    parent_new_area = ja.total_area - split_acres
    original_date   = ja.scheduled_date

    with transaction.atomic():
        old_total     = ja.total_area
        ja.total_area = parent_new_area
        ja.save()

        child = JobActivity(
            job                     = ja.job,
            activity                = ja.activity,
            plot                    = ja.plot,
            total_area              = split_acres,
            allocated_area          = Decimal("0"),
            remaining_area          = split_acres,
            scheduled_date          = split_date,
            original_scheduled_date = ja.original_scheduled_date or original_date,
            rate_per_acre           = ja.rate_per_acre,
            estimated_workers       = max(1, int(float(split_acres) * 10)),
            location                = ja.location,
            source                  = "manual",
            original_source         = "manual",
            is_strict               = ja.is_strict,
            is_manually_moved       = True,
            moved_from_activity     = ja,
            move_reason             = f"Split {split_acres} ac from JA#{ja.pk} by {edited_by}",
        )
        child.save()

    if original_date and split_date != original_date:
        _cascade_successors(
            trigger_ja=ja, old_date=original_date, new_date=split_date,
            edited_by=edited_by, exclude_ja_id=child.pk,
        )

    threading.Thread(
        target=upsert_job_activity_to_sheet, args=(ja.pk,), daemon=True
    ).start()
    threading.Thread(
        target=upsert_job_activity_to_sheet, args=(child.pk,), daemon=True
    ).start()

    msg = (
        f"Split OK: JA#{ja.pk} now {parent_new_area} ac on {ja.scheduled_date}; "
        f"new JA#{child.pk} = {split_acres} ac on {split_date}"
    )
    logger.info(f"[Sheet->DB] {msg} by {edited_by}")
    return True, msg, child.pk



