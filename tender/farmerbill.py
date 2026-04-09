# utils/google_sheets_sync.py
import gspread
from google.oauth2.service_account import Credentials
from django.conf import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ID = settings.FARMER_BILLING_SHEET_ID  # Add this to your settings.py

def get_sheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("Farmer Billing")
# utils/google_sheets_sync.py
import requests
from django.conf import settings
from django.utils.timezone import localtime


def sync_farmer_bill_to_sheet(log):
    """
    Called after a FarmerBillWebhookLog is saved.
    POSTs to the Apps Script webhook — same payload format as the billsheet command.
    """
    webhook_url = getattr(settings, "GOOGLE_SHEET_WEBHOOK_URL", None)
    if not webhook_url:
        print("[Sheet sync] ⚠️  GOOGLE_SHEET_WEBHOOK_URL not set — skipping")
        return

    # ── Generated At ──────────────────────────────────────────
    generated_at = ""
    if log.created_at:
        generated_at = localtime(log.created_at).strftime("%d %b %Y, %I:%M %p")

    # ── Plots / Acres from full_payload ───────────────────────
    plots_done     = ""
    total_acres    = 0.0
    activity_acres = 0.0   # ← NEW
    try:
        work_done = (log.full_payload or {}).get("work_done", [])
        all_plots = set()
        for w in work_done:
            plot = w.get("plot_name", "").strip()
            if plot:
                all_plots.add(plot)
            acres = w.get("acres_done", 0)
            if acres:
                total_acres    += float(acres)
                activity_acres += float(acres)   # ← NEW (single log = single activity)
        if all_plots:
            plots_done = f"{len(all_plots)}/{len(all_plots)}"
    except Exception:
        pass

    payload = {
        "farmer_id"      : str(log.farmer_id),
        "farmer_name"    : log.farmer_name or "",
        "job_id"         : str(log.job_id or ""),
        "poc"            : log.sent_by_name or "",
        "plots_done"     : plots_done,
        "total_acres"    : round(total_acres, 2),
        "activity_name"  : log.activity_name or "Unknown Activity",
        "activity_acres" : round(activity_acres, 2),   # ← NEW
        "total_billed"   : float(log.total_billed or 0),
        "total_paid"     : float(log.total_paid or 0),
        "balance_due"    : float(log.balance_due or 0),
        "status"         : "✅ Paid" if float(log.balance_due or 0) <= 0 else "Generated",
        "generated_at"   : generated_at,
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") != "ok":
            print(f"[Sheet sync] ❌ Farmer {log.farmer_id}: {result.get('message')}")
        else:
            print(f"[Sheet sync] ✅ Farmer {log.farmer_id} Job {log.job_id} "
                  f"→ {result.get('action')} row {result.get('row')}")
    except Exception as e:
        print(f"[Sheet sync] ❌ Failed for farmer {log.farmer_id}: {e}")