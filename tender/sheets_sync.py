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
  I  Alloc status       read-only -> JobActivity.allocation_status (set by DB signals)
  J  Work status        EDITABLE  -> Allocation.work_status (actual ground work)
  K  Mukadam team       EDITABLE  -> Allocation.mukkadam (matched by name)
  L  Cluster            read-only
  M  _job_activity_id   hidden key

WHY TWO STATUS COLUMNS:
  Alloc status (I) = how much area has been ASSIGNED to a mukkadam
    pending / partially_allocated / fully_allocated / in_progress / completed
    Controlled by DB signals automatically. Sheet cannot change this.

  Work status (J) = what actually happened ON THE GROUND
    Not Started / In Progress / Completed
    This IS editable from the sheet -> updates Allocation.work_status.
    When all allocations are Completed, JobActivity.allocation_status
    is also set to 'completed'.
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
    "Farmer name",      # A col 1
    "Activity name",    # B col 2
    "Plot Id",          # C col 3
    "Acre",             # D col 4
    "Price",            # E col 5
    "Village",          # F col 6
    "Actual date",      # G col 7
    "Our date",         # H col 8
    "Mukadam team",     # I col 9  ← was Alloc status
    "Alloc status",     # J col 10 ← was Work status
    "Work status",      # K col 11 ← was Mukadam team
    "Cluster",          # L col 12
]

_HEADERS_WITH_KEY = HEADERS + ["_job_activity_id"]  # M  col 13
_KEY_COL = len(_HEADERS_WITH_KEY)  # 13


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
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        }]})
        return ws


# =============================================================================
# DJANGO -> SHEET
# =============================================================================

def _job_activity_to_row(ja):
    """Build a 13-column row from a JobActivity instance."""

    try:
        farmer_name = ja.job.farmer.farmer_name
    except Exception:
        farmer_name = ""

    activity_name = ja.activity.name if ja.activity_id else ""
    plot_id = ja.plot.name if ja.plot_id else ""
    acre = str(ja.total_area) if ja.total_area else "0"
    price = str(ja.total_price) if ja.total_price else "0"

    village = ""
    try:
        clusters = list(ja.job.clusters.all())
        if clusters and clusters[0].villages:
            village = clusters[0].villages[0]
    except Exception:
        pass

    actual_date = (
    ja.sales_date.strftime("%Y-%m-%d")
    if ja.sales_date else ""
)
    our_date = (
        ja.scheduled_date.strftime("%Y-%m-%d")
        if ja.scheduled_date else ""
    )

    # Col I — Alloc status: how much area is allocated (read-only from sheet)
    alloc_status = ja.get_allocation_status_display()

    # Col J — Work status: what happened on the ground (editable from sheet)
    # Aggregated from all Allocations on this JobActivity:
    #   All completed  -> "Completed"
    #   Any in_progress -> "In Progress"
    #   Otherwise      -> "Not Started" (or "" if no allocations)
    try:
        allocations = list(ja.allocations.all())
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
    except Exception:
        work_status = ""

    try:
        mukkadam_names = list(
            ja.allocations.select_related("mukkadam")
            .values_list("mukkadam__mukkadam_name", flat=True)
            .distinct()
        )
        mukadam_team = ", ".join(mukkadam_names)
    except Exception:
        mukadam_team = ""

    cluster = ""
    try:
        c = ja.job.clusters.first()
        if c:
            cluster = c.name
    except Exception:
        pass

    return [
        farmer_name,    # A
        activity_name,  # B
        plot_id,        # C
        acre,           # D
        price,          # E
        village,        # F
        actual_date,    # G
        our_date,  
        mukadam_team,     # H
        alloc_status,   # I  read-only
        work_status,    # J  editable
           # K  editable
        cluster,        # L
        str(ja.pk),     # M  hidden key
    ]


def upsert_job_activity_to_sheet(ja_id):
    import time
    time.sleep(1)

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

    if not ja.total_area or ja.total_area <= 0:
        delete_job_activity_from_sheet(ja_id)
        return

    try:
        ws = get_sheet()
        try:
            cell = ws.find(str(ja_id), in_column=_KEY_COL)
        except gspread.exceptions.CellNotFound:
            cell = None

        new_row = _job_activity_to_row(ja)

        if cell:
            ws.update(f"A{cell.row}:M{cell.row}", [new_row])
            logger.info(f"[Sheets] Updated row {cell.row} for JA {ja_id}")
        else:
            ws.append_row(new_row)
            logger.info(f"[Sheets] Appended row for JA {ja_id}")

    except Exception as e:
        logger.error(f"[Sheets] Failed to sync JA {ja_id}: {e}")


def delete_job_activity_from_sheet(ja_id):
    try:
        ws = get_sheet()
        try:
            cell = ws.find(str(ja_id), in_column=_KEY_COL)
        except gspread.exceptions.CellNotFound:
            return
        if cell:
            ws.delete_rows(cell.row)
            logger.info(f"[Sheets] Deleted row for JA {ja_id}")
    except Exception as e:
        logger.error(f"[Sheets] Failed to delete JA {ja_id}: {e}")


# =============================================================================
# SHEET -> DJANGO
# =============================================================================

def apply_sheet_edit(payload):
    """
    Route a single sheet edit to the correct handler.
    Now also writes to SheetEditLog on every call.
    Returns (ok: bool, message: str)
    """
    from .models import JobActivity

    ja_id      = payload.get("job_activity_id")
    column     = payload.get("column", "")
    new_val    = str(payload.get("new_value", "")).strip()
    old_val    = str(payload.get("old_value", "")).strip()
    edited_by  = payload.get("edited_by", "unknown")
    event      = payload.get("event", "edit")

    # ── Load JA ──────────────────────────────────────────────────────────────
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
        # ── SPLIT ─────────────────────────────────────────────────────────────
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

    # ── Always log ────────────────────────────────────────────────────────────
    _log_sheet_edit(
        ja=ja,
        ja_id_raw=ja_id,
        event=event,
        column=column,
        old_value=old_val,
        new_value=new_val,
        edited_by=edited_by,
        success=ok,
        message=msg,
        split_child_ja_id=child_ja_id,
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

    # Cascade successors on same plot (outside the atomic block — each
    # successor gets its own save + sheet sync thread)
    _cascade_successors(
        trigger_ja = ja,
        old_date   = old_date,
        new_date   = new_date,
        edited_by  = edited_by,
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
    """
    Updates Allocation.work_status on ALL allocations for this JobActivity.

    Sheet label  -> DB value
    Not Started  -> work_not_started
    In Progress  -> in_progress
    Completed    -> completed  (also sets JobActivity.allocation_status='completed')
    """
    from .models import Allocation
    from .models import JobActivity

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

    allocations = list(ja.allocations.all())
    if not allocations:
        return False, f"No allocations for JA {ja.pk} — assign a mukkadam first"

    with transaction.atomic():
        updated = Allocation.objects.filter(job_activity=ja).update(
            work_status=db_status
        )
        # When all work is done, also close the JobActivity allocation_status
        if db_status == "completed":
            JobActivity.objects.filter(pk=ja.pk).update(allocation_status="completed")
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

    existing = list(ja.allocations.all())
    with transaction.atomic():
        if existing:
            for i, alloc in enumerate(existing):
                if i < len(resolved):
                    old_mk = alloc.mukkadam
                    alloc.mukkadam = resolved[i]
                    alloc.save(update_fields=["mukkadam"])
                    logger.info(f"[Sheet->DB] Alloc {alloc.pk}: {old_mk.mukkadam_name} -> {resolved[i].mukkadam_name}")
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

    mk_rate = MukkadamActivityRate.objects.filter(mukkadam=mukkadam, activity=ja.activity).first()
    if mk_rate:
        mukkadam_rate = mk_rate.rate_per_acre
    else:
        cluster = ja.job.clusters.first()
        if cluster:
            cr = ClusterMukkadamActivityRate.objects.filter(cluster=cluster, activity=ja.activity).first()
            if cr:
                mukkadam_rate = cr.rate_per_acre
    if not mukkadam_rate:
        mukkadam_rate = (farmer_rate * Decimal("0.8")).quantize(Decimal("0.01"))

    area    = ja.remaining_area if ja.remaining_area > 0 else ja.total_area
    workers = max(1, int(float(area) * 10))

    Allocation(
        job_activity      = ja,
        mukkadam          = mukkadam,
        cluster           = ja.job.clusters.first(),
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
    old_area = ja.total_area
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
# BULK REFRESH
# =============================================================================

def full_sheet_refresh():
    from .models import JobActivity
    ws = get_sheet()
    ws.clear()
    ws.append_row(_HEADERS_WITH_KEY)

    qs = (
        JobActivity.objects
        .select_related("job__farmer", "plot", "activity")
        .prefetch_related("job__clusters", "allocations__mukkadam")
        .filter(total_area__gt=0)
        .order_by("scheduled_date", "pk")
    )
    rows = [_job_activity_to_row(ja) for ja in qs]
    if rows:
        ws.update(f"A2:M{1 + len(rows)}", rows)

    logger.info(f"[Sheets] Full refresh: {len(rows)} rows")
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _log_sheet_edit(*, ja, ja_id_raw, event, column="", old_value="",
                    new_value="", edited_by, success, message,
                    split_child_ja_id=None):
    """
    Write one row to SheetEditLog. Never raises — logging must not break
    the main request flow.
    """
    try:
        from .models import SheetEditLog
        SheetEditLog.objects.create(
            job_activity=ja,
            job_activity_id_raw=str(ja_id_raw),
            event=event,
            column=column,
            old_value=str(old_value),
            new_value=str(new_value),
            edited_by=edited_by or "unknown",
            success=success,
            message=message,
            split_child_ja_id=split_child_ja_id,
        )
    except Exception as exc:
        logger.error(f"[SheetEditLog] Failed to write log: {exc}")

def _cascade_successors(trigger_ja, old_date, new_date, edited_by, exclude_ja_id=None):
    """
    Shift all successor JobActivities on the same job+plot by the same
    number of days as (new_date - old_date).

    Skips:
      - already allocated / completed
      - zero area
      - the exclude_ja_id (used by split to exclude the newly created child)

    NOTE: Does NOT skip is_manually_moved activities — same behaviour as the
    app's JobActivity move action, which always cascades all unallocated
    successors regardless of how they were previously moved.
    """
    from datetime import date, timedelta
    from .models import JobActivity, Allocation

    shift_days = (new_date - old_date).days
    if shift_days == 0:
        return

    from .utils import get_activity_sequence_order

    all_on_plot = list(
        JobActivity.objects
        .filter(job=trigger_ja.job, plot=trigger_ja.plot, is_lost=False, total_area__gt=0)
        .exclude(pk=trigger_ja.pk)
        .select_related("activity")
    )
    if exclude_ja_id:
        all_on_plot = [a for a in all_on_plot if a.pk != exclude_ja_id]

    all_on_plot.sort(key=lambda a: (
        get_activity_sequence_order(a),
        a.scheduled_date or date.min,
        a.id,
    ))

    current_seq = get_activity_sequence_order(trigger_ja)

    for act in all_on_plot:
        if get_activity_sequence_order(act) <= current_seq:
            continue
        if act.allocation_status in ('fully_allocated', 'partially_allocated', 'completed'):
            logger.info(f"[Cascade] Skip JA#{act.pk} — {act.allocation_status}")
            continue
        # NOTE: is_manually_moved is intentionally NOT skipped here.
        # The app's move action cascades all unallocated successors regardless,
        # so the sheet should behave identically.
        if not act.scheduled_date:
            continue

        old_act_date = act.scheduled_date
        new_act_date = old_act_date + timedelta(days=shift_days)

        act.scheduled_date = new_act_date
        act.move_reason    = (
            f"Cascade from JA#{trigger_ja.id} sheet move by {edited_by} "
            f"({shift_days:+d} days)"
        )
        act.save(update_fields=["scheduled_date", "move_reason", "updated_at"])
        Allocation.objects.filter(job_activity=act).update(allocated_date=new_act_date)

        logger.info(
            f"[Cascade] JA#{act.pk} {act.activity.name}: "
            f"{old_act_date} → {new_act_date}"
        )

        try:
            import threading
            threading.Thread(
                target=upsert_job_activity_to_sheet,
                args=(act.pk,),
                daemon=True,
            ).start()
        except Exception:
            pass
# ─────────────────────────────────────────────────────────────────────────────
# SPLIT
# ─────────────────────────────────────────────────────────────────────────────

def _apply_split(ja, split_acres_str, split_date_str, edited_by):
    """
    Split a JobActivity into two:
      - Parent JA: total_area reduced by split_acres, keeps original date
      - Child  JA: new row with split_acres on split_date

    Returns (ok: bool, message: str, child_ja_id: int | None)
    """
    from decimal import Decimal, InvalidOperation
    from datetime import datetime
    from .models import JobActivity

    # ── Validate inputs ──────────────────────────────────────────────────────
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
        # Shrink parent
        old_total     = ja.total_area
        ja.total_area = parent_new_area
        ja.save()

        # Create child
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

    # Cascade successors from the CHILD's date perspective
    # (same as a date change — shift everything after ja on same plot)
    if original_date and split_date != original_date:
        _cascade_successors(
            trigger_ja    = ja,
            old_date      = original_date,
            new_date      = split_date,
            edited_by     = edited_by,
            exclude_ja_id = child.pk,   # don't cascade the child we just made
        )

    # Sync both rows to sheet
    try:
        import threading
        threading.Thread(
            target=upsert_job_activity_to_sheet, args=(ja.pk,),    daemon=True
        ).start()
        threading.Thread(
            target=upsert_job_activity_to_sheet, args=(child.pk,), daemon=True
        ).start()
    except Exception as e:
        logger.warning(f"[Split] Sheet sync thread error: {e}")

    msg = (
        f"Split OK: JA#{ja.pk} now {parent_new_area} ac on {ja.scheduled_date}; "
        f"new JA#{child.pk} = {split_acres} ac on {split_date}"
    )
    logger.info(f"[Sheet->DB] {msg} by {edited_by}")
    return True, msg, child.pk