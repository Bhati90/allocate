# # your_app/sheets_sync.py
"""
Bidirectional sync between Django DB ↔ Google Sheets.

Django → Sheet:  signals fire upsert/delete on JobActivity & Allocation changes.
Sheet  → Django: Apps Script onEdit → POST to /api/sync-from-sheet/ webhook.

The `_syncing` threading-local flag prevents infinite loops:
  - When Sheet→Django code saves a model, _syncing.active = True
  - The post_save signal checks _syncing.active and skips the Sheet push
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

# ── threading guard (shared with signals.py) ──────────────────────────────
_syncing = threading.local()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet column headers (A–K visible, L = hidden key)
HEADERS = [
    "Farmer name",       # A  (col 1)
    "Activity name",     # B  (col 2)
    "Plot Id",           # C  (col 3)
    "Acre",              # D  (col 4)
    "Price",             # E  (col 5)
    "Village",           # F  (col 6)
    "Actual date",       # G  (col 7)  = original_scheduled_date
    "Our date",          # H  (col 8)  = scheduled_date  ← EDITABLE
    "Status",            # I  (col 9)  = allocation_status ← EDITABLE
    "Mukadam team",      # J  (col 10) = allocated mukkadams ← EDITABLE
    "Cluster",           # K  (col 11)
]

_HEADERS_WITH_KEY = HEADERS + ["_job_activity_id"]  # L (col 12)

# Column index for the hidden key (1-based for gspread)
_KEY_COL = len(_HEADERS_WITH_KEY)  # = 12


# ═══════════════════════════════════════════════════════════════════════════
# SHEET CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

def get_sheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_SHEETS_CREDENTIALS, scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
    try:
        return sh.worksheet("Jobs")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Jobs", rows=2000, cols=len(_HEADERS_WITH_KEY))
        ws.append_row(_HEADERS_WITH_KEY)
        # Freeze header row
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


# ═══════════════════════════════════════════════════════════════════════════
# DJANGO → SHEET  (push)
# ═══════════════════════════════════════════════════════════════════════════

def _job_activity_to_row(ja):
    """Build a row list (cols A–L) from a JobActivity instance."""
    # Farmer name
    try:
        farmer_name = ja.job.farmer.farmer_name
    except Exception:
        farmer_name = ""

    # Activity name
    activity_name = ja.activity.name if ja.activity_id else ""

    # Plot id
    plot_id = ja.plot.name if ja.plot_id else ""

    # Acre
    acre = str(ja.total_area) if ja.total_area else "0"

    # Price
    price = str(ja.total_price) if ja.total_price else "0"

    # Village — first cluster's first village
    village = ""
    try:
        clusters = list(ja.job.clusters.all())
        if clusters and clusters[0].villages:
            village = clusters[0].villages[0]
    except Exception:
        pass

    # Actual date (original_scheduled_date)
    actual_date = (
        ja.original_scheduled_date.strftime("%Y-%m-%d")
        if ja.original_scheduled_date else ""
    )

    # Our date (current scheduled_date)
    our_date = (
        ja.scheduled_date.strftime("%Y-%m-%d")
        if ja.scheduled_date else ""
    )

    # Status
    status = ja.get_allocation_status_display()

    # Mukadam team — all mukkadams allocated to this activity
    try:
        mukkadam_names = list(
            ja.allocations.select_related("mukkadam")
            .values_list("mukkadam__mukkadam_name", flat=True)
            .distinct()
        )
        mukadam_team = ", ".join(mukkadam_names)
    except Exception:
        mukadam_team = ""

    # Cluster
    cluster = ""
    try:
        c = ja.job.clusters.first()
        if c:
            cluster = c.name
    except Exception:
        pass

    return [
        farmer_name,       # A
        activity_name,     # B
        plot_id,           # C
        acre,              # D
        price,             # E
        village,           # F
        actual_date,       # G
        our_date,          # H
        status,            # I
        mukadam_team,      # J
        cluster,           # K
        str(ja.pk),        # L  (hidden key)
    ]


def upsert_job_activity_to_sheet(ja_id):
    import time
    time.sleep(1)  # wait for allocation_status .update() to commit
    
    from .models import JobActivity
    try:
        ja = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("job__clusters", "allocations__mukkadam")
            .get(pk=ja_id)
        )

    except JobActivity.DoesNotExist:
        return

    # Skip if acre is 0 or null — delete from sheet if it was there
    if not ja.total_area or ja.total_area <= 0:
        delete_job_activity_from_sheet(ja_id)
        return

    try:
        ws = get_sheet()

        # Find existing row by _job_activity_id (column L = col 12)
        try:
            cell = ws.find(str(ja_id), in_column=_KEY_COL)
        except gspread.CellNotFound:
            cell = None

        new_row = _job_activity_to_row(ja)

        if cell:
            # Update all columns A–L on that row
            ws.update(f"A{cell.row}:L{cell.row}", [new_row])
            logger.info(f"[Sheets] Updated row {cell.row} for JA {ja_id}")
        else:
            ws.append_row(new_row)
            logger.info(f"[Sheets] Appended new row for JA {ja_id}")

    except Exception as e:
        logger.error(f"[Sheets] Failed to sync JobActivity {ja_id}: {e}")


def delete_job_activity_from_sheet(ja_id):
    """Remove a row from the sheet when a JobActivity is deleted."""
    try:
        ws = get_sheet()
        cell = ws.find(str(ja_id), in_column=_KEY_COL)
        if cell:
            ws.delete_rows(cell.row)
            logger.info(f"[Sheets] Deleted row for JA {ja_id}")
    except gspread.CellNotFound:
        pass
    except Exception as e:
        logger.error(f"[Sheets] Failed to delete JA {ja_id} from sheet: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SHEET → DJANGO  (pull / webhook handler)
# ═══════════════════════════════════════════════════════════════════════════

def apply_sheet_edit(payload):
    """
    Called by the sync_from_sheet webhook view.

    payload = {
        "job_activity_id": "123",
        "column": "Our date",          # header name of edited column
        "old_value": "2025-06-01",
        "new_value": "2025-06-05",
        "edited_by": "user@example.com",
    }

    Returns (success: bool, message: str)
    """
    from .models import JobActivity, Allocation, Mukkadam

    ja_id = payload.get("job_activity_id")
    column = payload.get("column", "").strip()
    new_value = (payload.get("new_value") or "").strip()
    old_value = (payload.get("old_value") or "").strip()
    edited_by = payload.get("edited_by", "sheet")

    if not ja_id:
        return False, "Missing job_activity_id"

    try:
        ja = (
            JobActivity.objects
            .select_related("job__farmer", "plot", "activity")
            .prefetch_related("allocations__mukkadam")
            .get(pk=int(ja_id))
        )
    except (JobActivity.DoesNotExist, ValueError):
        return False, f"JobActivity {ja_id} not found"

    # ── Set the syncing guard so post_save signals skip the sheet push ──
    _syncing.active = True
    try:
        if column == "Our date":
            return _apply_date_change(ja, new_value, edited_by)

        elif column == "Status":
            return _apply_status_change(ja, new_value, edited_by)

        elif column == "Mukadam team":
            return _apply_mukadam_change(ja, new_value, edited_by)

        elif column == "Acre":
            return _apply_acre_change(ja, new_value, edited_by)

        elif column == "_DELETE_":
            return _apply_delete(ja, edited_by)

        else:
            return False, f"Column '{column}' is not editable from sheet"
    finally:
        _syncing.active = False


# ── Individual field handlers ─────────────────────────────────────────────

def _apply_date_change(ja, new_date_str, edited_by):
    """Change scheduled_date on JobActivity + move all its allocations."""
    from .models import Allocation

    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, f"Invalid date format: {new_date_str}. Use YYYY-MM-DD."

    old_date = ja.scheduled_date

    with transaction.atomic():
        ja.scheduled_date = new_date
        ja.save(update_fields=["scheduled_date", "updated_at"])

        # Move all allocations to the new date
        moved = Allocation.objects.filter(job_activity=ja).update(
            allocated_date=new_date
        )

    logger.info(
        f"[Sheet→DB] Date changed JA {ja.pk}: {old_date} → {new_date} "
        f"({moved} allocations moved) by {edited_by}"
    )
    return True, f"Date updated to {new_date}, {moved} allocations moved"


def _apply_status_change(ja, new_status_display, edited_by):
    """Change allocation_status on JobActivity from the display label."""
    # Map display labels back to DB values
    STATUS_MAP = {
        "Pending": "pending",
        "Partially Allocated": "partially_allocated",
        "Fully Allocated": "fully_allocated",
        "In Progress": "in_progress",
        "Completed": "completed",
    }
    db_status = STATUS_MAP.get(new_status_display)
    if not db_status:
        # Also try the raw value directly
        valid = {v for v, _ in ja._meta.get_field("allocation_status").choices}
        if new_status_display.lower() in valid:
            db_status = new_status_display.lower()
        else:
            return False, f"Unknown status: '{new_status_display}'"

    old_status = ja.allocation_status
    ja.allocation_status = db_status
    ja.save(update_fields=["allocation_status", "updated_at"])

    logger.info(
        f"[Sheet→DB] Status changed JA {ja.pk}: {old_status} → {db_status} by {edited_by}"
    )
    return True, f"Status updated to {db_status}"


def _apply_mukadam_change(ja, new_mukadam_str, edited_by):
    """
    Update mukadam allocation from sheet.

    Strategy:
    - Parse comma-separated mukkadam names from the cell
    - Match against existing Mukkadam records (fuzzy by name)
    - If the JA already has allocations, update the mukkadam on existing ones
    - If no allocations exist, create new ones with sensible defaults
    """
    from .models import Allocation, Mukkadam

    if not new_mukadam_str:
        # Blank = remove all allocations? That's risky, just log it.
        logger.warning(f"[Sheet→DB] Mukadam team cleared for JA {ja.pk} — no action taken")
        return True, "Mukadam team cleared in sheet (no DB change — remove allocations from app)"

    new_names = [n.strip() for n in new_mukadam_str.split(",") if n.strip()]

    # Resolve names to Mukkadam objects
    resolved = []
    unresolved = []
    for name in new_names:
        mk = Mukkadam.objects.filter(mukkadam_name__iexact=name).first()
        if not mk:
            # Try partial/contains match
            mk = Mukkadam.objects.filter(mukkadam_name__icontains=name).first()
        if mk:
            resolved.append(mk)
        else:
            unresolved.append(name)

    if unresolved:
        logger.warning(f"[Sheet→DB] Could not resolve mukkadams: {unresolved}")

    if not resolved:
        return False, f"No matching mukkadams found for: {new_names}"

    existing_allocs = list(ja.allocations.all())

    with transaction.atomic():
        if existing_allocs:
            # ── Update existing allocations' mukkadam ──
            # Simple strategy: if 1 allocation and 1 new name → swap mukkadam
            # If counts differ, update what we can and log the rest
            for i, alloc in enumerate(existing_allocs):
                if i < len(resolved):
                    old_mk = alloc.mukkadam
                    alloc.mukkadam = resolved[i]
                    alloc.save(update_fields=["mukkadam"])
                    logger.info(
                        f"[Sheet→DB] Allocation {alloc.pk}: mukkadam "
                        f"{old_mk.mukkadam_name} → {resolved[i].mukkadam_name}"
                    )
            # If more new mukkadams than existing allocations, create new ones
            for mk in resolved[len(existing_allocs):]:
                _create_default_allocation(ja, mk)
        else:
            # ── No allocations — create new ones ──
            for mk in resolved:
                _create_default_allocation(ja, mk)

    msg = f"Mukadam updated to: {[m.mukkadam_name for m in resolved]}"
    if unresolved:
        msg += f" (unresolved: {unresolved})"
    return True, msg


def _create_default_allocation(ja, mukkadam):
    """Create a default allocation for a mukkadam from a sheet edit."""
    from .models import Allocation, MukkadamActivityRate, ClusterMukkadamActivityRate

    # Get rates
    farmer_rate = ja.rate_per_acre or Decimal("0")

    # Try mukkadam-specific rate, then cluster default, then 80% of farmer rate
    mukkadam_rate = Decimal("0")
    mk_rate = MukkadamActivityRate.objects.filter(
        mukkadam=mukkadam, activity=ja.activity
    ).first()
    if mk_rate:
        mukkadam_rate = mk_rate.rate_per_acre
    else:
        cluster = ja.job.clusters.first()
        if cluster:
            cr = ClusterMukkadamActivityRate.objects.filter(
                cluster=cluster, activity=ja.activity
            ).first()
            if cr:
                mukkadam_rate = cr.rate_per_acre
    if not mukkadam_rate:
        mukkadam_rate = (farmer_rate * Decimal("0.8")).quantize(Decimal("0.01"))

    area = ja.remaining_area if ja.remaining_area > 0 else ja.total_area
    workers = max(1, int(area * 10))  # rough estimate

    alloc = Allocation(
        job_activity=ja,
        mukkadam=mukkadam,
        cluster=ja.job.clusters.first(),
        allocated_date=ja.scheduled_date,
        allocated_area=area,
        allocated_workers=workers,
        farmer_rate=farmer_rate,
        mukkadam_rate=mukkadam_rate,
        farmer_amount=area * farmer_rate,
        mukkadam_amount=area * mukkadam_rate,
        profit=(area * farmer_rate) - (area * mukkadam_rate),
        status="scheduled",
    )
    alloc.save()
    logger.info(
        f"[Sheet→DB] Created allocation for JA {ja.pk}, "
        f"mukkadam={mukkadam.mukkadam_name}, area={area}"
    )


def _apply_acre_change(ja, new_acre_str, edited_by):
    """Change total_area on the JobActivity."""
    try:
        new_area = Decimal(new_acre_str)
    except Exception:
        return False, f"Invalid acre value: {new_acre_str}"

    if new_area < 0:
        return False, "Acre cannot be negative"

    old_area = ja.total_area
    ja.total_area = new_area
    ja.save()  # triggers the model's save() which recalculates price etc.

    logger.info(
        f"[Sheet→DB] Acre changed JA {ja.pk}: {old_area} → {new_area} by {edited_by}"
    )
    return True, f"Acre updated from {old_area} to {new_area}"


def _apply_delete(ja, edited_by):
    """Delete a JobActivity (when row is deleted from sheet)."""
    ja_id = ja.pk
    job_id = ja.job_id

    with transaction.atomic():
        ja.allocations.all().delete()
        ja.delete()

    logger.info(f"[Sheet→DB] Deleted JA {ja_id} (job {job_id}) by {edited_by}")
    return True, f"JobActivity {ja_id} deleted"


# ═══════════════════════════════════════════════════════════════════════════
# BULK SHEET REFRESH (admin utility)
# ═══════════════════════════════════════════════════════════════════════════

def full_sheet_refresh():
    """
    Wipe the sheet and re-push ALL JobActivities.
    Useful after a migration or data fix.
    Call from manage.py shell:
        from your_app.sheets_sync import full_sheet_refresh
        full_sheet_refresh()
    """
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
        # Batch update is much faster than append_row in a loop
        ws.update(f"A2:L{1 + len(rows)}", rows)

    logger.info(f"[Sheets] Full refresh: pushed {len(rows)} rows")
    return len(rows)
