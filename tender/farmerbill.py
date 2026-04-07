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
def sync_farmer_bill_to_sheet(log):
    """
    Called after a FarmerBillWebhookLog is saved.
    Updates or creates the farmer's row in Google Sheet.
    """
    sheet = get_sheet()
    all_rows = sheet.get_all_values()
    headers = all_rows[0]

    # ── FIX: use created_at instead of sent_at ──
    generated_at = ""
    if log.created_at:
        generated_at = log.created_at.strftime("%d %b %Y, %I:%M %p")  # e.g. "07 Apr 2026, 06:09 PM"

    # Find bill columns (Bill 1 .. Bill 6)
    bill_cols = [h for h in headers if h.startswith("Bill ")]

    # Find farmer row by Farmer ID
    farmer_id_str = str(log.farmer_id)
    row_index = None
    for i, row in enumerate(all_rows[1:], start=2):
        if row[0] == farmer_id_str:
            row_index = i
            break

    if row_index is None:
        new_row = [
            log.farmer_id,
            log.farmer_name,
            log.sent_by_name or "",
            "",          # Plots Done
            *[""] * len(bill_cols),
            "",          # Total Pending
            "Generated",
            generated_at,  # Generated At
        ]
        sheet.append_row(new_row)
        row_index = len(all_rows) + 1
        all_rows.append(new_row)
    else:
        # Write Generated At only if not already set
        if "Generated At" in headers:
            gen_col = headers.index("Generated At") + 1
            existing = all_rows[row_index - 1][headers.index("Generated At")]
            if not existing or existing == "-":
                sheet.update_cell(row_index, gen_col, generated_at)

    farmer_row = all_rows[row_index - 1]

    # Find next empty Bill column
    bill_start_col = headers.index("Bill 1")
    assigned_col_index = None
    for i, bill_col in enumerate(bill_cols):
        col_index = headers.index(bill_col)
        if not farmer_row[col_index] or farmer_row[col_index] == "-":
            assigned_col_index = col_index
            break

    if assigned_col_index is None:
        print(f"Warning: No empty bill slot for farmer {log.farmer_id}")
        return

    sheet.update_cell(row_index, assigned_col_index + 1, float(log.total_billed or 0))

    total_pending_col = headers.index("Total Pending (₹)") + 1
    sheet.update_cell(row_index, total_pending_col, float(log.balance_due or 0))

    status_col = headers.index("Status") + 1
    status = "✅ Paid" if float(log.balance_due or 0) == 0 else "Generated"
    sheet.update_cell(row_index, status_col, status)