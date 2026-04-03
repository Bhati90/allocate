# payment.py
# Place in your Django app folder (same folder as models.py)
# Endpoints:
#   GET  /api/sheet/allocations/     → Sheet pulls all allocations
#   POST /api/sheet/update-ledger/   → Sheet pushes payment updates back

import json
from decimal import Decimal
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Allocation, MukkadamLedgerEntry


SHEET_TO_ALLOC_STATUS = {
    "pending":        "pending",
    "paid":           "settled",
    "partially_paid": "done",
    "dispute":        "dispute",
}

ALLOC_TO_SHEET_STATUS = {
    "pending":  "pending",
    "done":     "partially_paid",
    "settled":  "paid",
    "dispute":  "dispute",
}


# ═══════════════════════════════════════════════════════════════════
# GET /api/sheet/allocations/
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["GET"])
def sheet_get_allocations(request):
    try:
        allocations = (
            Allocation.objects
            .select_related(
                "mukkadam",
                "cluster",
                "job_activity",
                "job_activity__job",
                "job_activity__job__farmer",
                "job_activity__activity",
                "job_activity__plot",
            )
            .order_by("-allocated_date", "mukkadam__mukkadam_name")
        )

        rows = []

        for alloc in allocations:
            ja  = alloc.job_activity
            job = ja.job if ja else None

            farmer_name   = ""
            job_id        = ""
            activity_name = ""
            plot_name     = ""

            try:
                farmer_name = job.farmer.farmer_name if (job and job.farmer_id) else ""
            except Exception:
                pass
            try:
                job_id = job.job_id if job else ""
            except Exception:
                pass
            try:
                activity_name = ja.activity.name if (ja and ja.activity_id) else ""
            except Exception:
                pass
            try:
                plot_name = ja.plot.name if (ja and ja.plot_id) else ""
            except Exception:
                pass

            expected_amount = float(alloc.mukkadam_amount or 0)

            # ── Find ledger entries linked by allocation_id (most reliable) ──
            # We store allocation_id in remark as "alloc:{id}" as a fallback key
            # Primary: filter by allocation FK if it exists, else by job_activity+mukkadam+type
            per_acre_ledger = MukkadamLedgerEntry.objects.filter(
                job_activity=ja,
                mukkadam=alloc.mukkadam,
                payment_type="per_acre",
                remark__startswith=f"alloc:{alloc.id}|",
            ).first()

            # Fallback: any per_acre entry for this ja+mukkadam (old records)
            if not per_acre_ledger:
                per_acre_ledger = MukkadamLedgerEntry.objects.filter(
                    job_activity=ja,
                    mukkadam=alloc.mukkadam,
                    payment_type="per_acre",
                ).first()

            transport_ledger = MukkadamLedgerEntry.objects.filter(
                job_activity=ja,
                mukkadam=alloc.mukkadam,
                payment_type="transport",
                remark__startswith=f"alloc:{alloc.id}|",
            ).first()

            if not transport_ledger:
                transport_ledger = MukkadamLedgerEntry.objects.filter(
                    job_activity=ja,
                    mukkadam=alloc.mukkadam,
                    payment_type="transport",
                ).first()

            stored_amount = float(per_acre_ledger.amount) if per_acre_ledger else expected_amount
            adjustment    = round(stored_amount - expected_amount, 2)

            # Extract user remark (strip the alloc: prefix we store internally)
            user_remark = ""
            if per_acre_ledger and per_acre_ledger.remark:
                r = per_acre_ledger.remark
                if "|" in r and r.startswith("alloc:"):
                    user_remark = r.split("|", 1)[1]
                else:
                    user_remark = r

            rows.append({
                # ── DB auto-fill (read-only in sheet) ─────────────────
                "allocation_id":   alloc.id,
                "mukkadam_name":   alloc.mukkadam.mukkadam_name,
                "cluster":         alloc.cluster.name if alloc.cluster_id else "",
                "farmer_name":     farmer_name,
                "job_id":          job_id,
                "plot_name":       plot_name,
                "activity":        activity_name,
                "allocated_date":  str(alloc.allocated_date) if alloc.allocated_date else "",
                "acres":           float(alloc.allocated_area or 0),
                "mukkadam_rate":   float(alloc.mukkadam_rate or 0),
                "expected_amount": expected_amount,
                "work_status":     alloc.work_status,

                # ── Team-editable (pre-filled from ledger if exists) ───
                "transport_cost":  float(transport_ledger.amount) if transport_ledger else 0,
                "adjustment":      adjustment,
                "payment_status":  ALLOC_TO_SHEET_STATUS.get(alloc.payment_status, "pending"),
                "payment_date":    str(per_acre_ledger.payment_date) if (per_acre_ledger and per_acre_ledger.payment_date) else "",
                "remark":          user_remark,
            })

        return JsonResponse({"rows": rows, "total": len(rows)})

    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


# ═══════════════════════════════════════════════════════════════════
# POST /api/sheet/update-ledger/
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["POST"])
def sheet_update_ledger(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    allocation_id    = data.get("allocation_id")
    transport_cost   = Decimal(str(data.get("transport_cost", 0) or 0))
    adjustment       = Decimal(str(data.get("adjustment", 0) or 0))
    sheet_status     = data.get("payment_status", "pending")
    payment_date_str = data.get("payment_date", "")
    user_remark      = data.get("remark", "")

    if not allocation_id:
        return JsonResponse({"error": "allocation_id is required"}, status=400)

    try:
        alloc = Allocation.objects.select_related(
            "mukkadam",
            "cluster",
            "job_activity",
            "job_activity__job",
            "job_activity__job__farmer",
            "job_activity__activity",
        ).get(id=allocation_id)
    except Allocation.DoesNotExist:
        return JsonResponse({"error": f"Allocation {allocation_id} not found"}, status=404)

    ja            = alloc.job_activity
    job           = ja.job if ja else None
    farmer_name   = ""
    activity_name = ""

    try:
        farmer_name = job.farmer.farmer_name if (job and job.farmer_id) else ""
    except Exception:
        pass
    try:
        activity_name = ja.activity.name if (ja and ja.activity_id) else ""
    except Exception:
        pass

    # Parse payment date
    payment_date = None
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Map sheet status → Allocation.payment_status
    alloc_payment_status = SHEET_TO_ALLOC_STATUS.get(sheet_status, "pending")

    # ── 1. Update Allocation.payment_status ───────────────────────
    alloc.payment_status = alloc_payment_status
    alloc.save(update_fields=["payment_status", "updated_at"])

    # ── Internal remark stores alloc_id as prefix so we can
    #    uniquely find this ledger entry later even without unique_together
    internal_remark = f"alloc:{allocation_id}|{user_remark}"

    final_amount      = alloc.mukkadam_amount + adjustment
    ledger_pay_status = "paid" if alloc_payment_status == "settled" else alloc_payment_status

    # ── 2. Create/update per_acre ledger entry ────────────────────
    # First try to find existing entry for THIS allocation
    per_acre_qs = MukkadamLedgerEntry.objects.filter(
        job_activity=ja,
        mukkadam=alloc.mukkadam,
        payment_type="per_acre",
        remark__startswith=f"alloc:{allocation_id}|",
    )

    if per_acre_qs.exists():
        per_acre_qs.update(
            cluster        = alloc.cluster,
            farmer_name    = farmer_name,
            activity_name  = activity_name,
            acres          = alloc.allocated_area,
            amount         = final_amount,
            job_date       = alloc.allocated_date,
            payment_date   = payment_date,
            payment_status = ledger_pay_status,
            remark         = internal_remark,
            job            = job,
        )
        per_acre_entry = per_acre_qs.first()
    else:
        per_acre_entry = MukkadamLedgerEntry.objects.create(
            mukkadam       = alloc.mukkadam,
            cluster        = alloc.cluster,
            farmer_name    = farmer_name,
            activity_name  = activity_name,
            acres          = alloc.allocated_area,
            amount         = final_amount,
            job_date       = alloc.allocated_date,
            payment_date   = payment_date,
            payment_status = ledger_pay_status,
            payment_type   = "per_acre",
            remark         = internal_remark,
            job            = job,
            job_activity   = ja,
        )

    # ── 3. Create/update transport ledger entry ───────────────────
    transport_qs = MukkadamLedgerEntry.objects.filter(
        job_activity=ja,
        mukkadam=alloc.mukkadam,
        payment_type="transport",
        remark__startswith=f"alloc:{allocation_id}|",
    )

    if transport_cost > 0:
        if transport_qs.exists():
            transport_qs.update(
                cluster        = alloc.cluster,
                farmer_name    = farmer_name,
                activity_name  = activity_name,
                amount         = transport_cost,
                job_date       = alloc.allocated_date,
                payment_date   = payment_date,
                payment_status = ledger_pay_status,
                remark         = internal_remark,
                job            = job,
            )
        else:
            MukkadamLedgerEntry.objects.create(
                mukkadam       = alloc.mukkadam,
                cluster        = alloc.cluster,
                farmer_name    = farmer_name,
                activity_name  = activity_name,
                amount         = transport_cost,
                job_date       = alloc.allocated_date,
                payment_date   = payment_date,
                payment_status = ledger_pay_status,
                payment_type   = "transport",
                remark         = internal_remark,
                job            = job,
                job_activity   = ja,
            )
    else:
        # Team cleared transport to 0 — delete any existing transport entry
        transport_qs.delete()

    return JsonResponse({
        "success":           True,
        "allocation_id":     alloc.id,
        "allocation_status": alloc.payment_status,
        "ledger_id":         per_acre_entry.id,
        "final_amount":      float(final_amount),
        "transport_cost":    float(transport_cost),
    })



# sheet_views.py
# New Django endpoints for Tabs 2-5
# Add to urls.py:
#   path("api/sheet/settlements/",    sheet_views.sheet_get_settlements),
#   path("api/sheet/update-settlement/", sheet_views.sheet_update_settlement),
#   path("api/sheet/weekly-payments/",   sheet_views.sheet_get_weekly),
#   path("api/sheet/save-weekly/",       sheet_views.sheet_save_weekly),
#   path("api/sheet/other-payments/",    sheet_views.sheet_get_other),
#   path("api/sheet/save-other/",        sheet_views.sheet_save_other),
#   path("api/sheet/summary/",           sheet_views.sheet_get_summary),

import json
from decimal import Decimal
from datetime import datetime, date

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Q

from .models import (
    Mukkadam, Cluster, Job,
    MukkadamJobSettlement,
    MukkadamWeeklyPayment,
    ClusterMukkadamAssignment,
    MukkadamMiscCost,
    MukkadamLedgerEntry,
    Allocation,
)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _fmt_date(d):
    return str(d) if d else ""


# ═══════════════════════════════════════════════════════════════════
# GET /api/sheet/settlements/
# Tab 2 — reads MukkadamJobSettlement
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["GET"])
def sheet_get_settlements(request):
    try:
        settlements = (
            MukkadamJobSettlement.objects
            .select_related("mukkadam", "cluster", "job")
            .order_by("-created_at")
        )

        rows = []
        for s in settlements:
            rows.append({
                "settlement_id":            s.id,
                "mukkadam_name":            s.mukkadam.mukkadam_name,
                "cluster":                  s.cluster.name if s.cluster_id else "",
                "job_id":                   s.job.job_id if s.job_id else "",
                # From ClusterMukkadamAssignment — find type
                "mukkadam_type":            _get_mukkadam_type(s.mukkadam, s.cluster),
                "gross_amount":             float(s.gross_amount or 0),
                "deposit_percent":          float(s.deposit_percent or 10),
                "deposit_held":             float(s.deposit_held or 0),
                "payable_amount":           float(s.payable_amount or 0),
                "weekly_payments_deducted": float(s.weekly_payments_deducted or 0),
                "advance_deducted":         float(s.advance_deducted or 0),
                "credit_carried_forward":   float(s.credit_carried_forward or 0),
                "net_payable":              float(s.net_payable or 0),
                "transport_deducted":       float(s.transport_deducted or 0),
                "status":                   s.status,
                "paid_at":                  _fmt_date(s.paid_at.date() if s.paid_at else None),
                "notes":                    s.notes or "",
                "calculated_at":            _fmt_date(s.calculated_at.date() if s.calculated_at else None),
            })

        return JsonResponse({"rows": rows, "total": len(rows)})

    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


def _get_mukkadam_type(mukkadam, cluster):
    """Return 'permanent' or 'updown' from ClusterMukkadamAssignment."""
    try:
        assign = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam, cluster=cluster
        ).first()
        return assign.mukkadam_type if assign else "permanent"
    except Exception:
        return "permanent"


# ═══════════════════════════════════════════════════════════════════
# POST /api/sheet/update-settlement/
# Tab 2 — team updates transport, status, paid_date, notes
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["POST"])
def sheet_update_settlement(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    sid = data.get("settlement_id")
    if not sid:
        return JsonResponse({"error": "settlement_id required"}, status=400)

    try:
        s = MukkadamJobSettlement.objects.get(id=sid)
    except MukkadamJobSettlement.DoesNotExist:
        return JsonResponse({"error": f"Settlement {sid} not found"}, status=404)

    transport = Decimal(str(data.get("transport_deducted", 0) or 0))
    status    = data.get("status", "pending")
    paid_date = _parse_date(data.get("paid_date", ""))
    notes     = data.get("notes", "")

    s.transport_deducted = transport
    s.status = status
    s.notes  = notes

    if paid_date and status == "paid":
        from django.utils import timezone
        s.paid_at = timezone.make_aware(datetime.combine(paid_date, datetime.min.time()))

    # Recalculate net_payable with updated transport
    s.net_payable = (
        (s.payable_amount or 0)
        + (s.transport_deducted or 0)
        + (s.credit_carried_forward or 0)
        - (s.advance_deducted or 0)
        - (s.weekly_payments_deducted or 0)
    )

    s.save(update_fields=[
        "transport_deducted", "status", "notes",
        "paid_at", "net_payable", "updated_at"
    ])

    return JsonResponse({
        "success":     True,
        "settlement_id": s.id,
        "status":      s.status,
        "net_payable": float(s.net_payable),
    })


# ═══════════════════════════════════════════════════════════════════
# GET /api/sheet/weekly-payments/
# Tab 3 — reads MukkadamWeeklyPayment
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["GET"])
def sheet_get_weekly(request):
    try:
        payments = (
            MukkadamWeeklyPayment.objects
            .select_related("assignment", "assignment__mukkadam", "assignment__cluster")
            .order_by("-payment_date", "assignment__mukkadam__mukkadam_name")
        )

        rows = []
        for p in payments:
            assign     = p.assignment
            weekly_amt = float(assign.weekly_amount or 0)
            crew       = p.crew_size_on_date or 0
            auto_amt   = crew * weekly_amt

            rows.append({
                "weekly_id":     p.id,
                "assignment_id": assign.id,
                "mukkadam_name": assign.mukkadam.mukkadam_name,
                "cluster":       assign.cluster.name,
                "payment_date":  _fmt_date(p.payment_date),
                "crew_size":     crew,
                "auto_amount":   auto_amt,
                "amount":        float(p.amount or 0),
                "mode":          p.mode or "CASH",
                "notes":         p.notes or "",
            })

        return JsonResponse({"rows": rows, "total": len(rows)})

    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


# ═══════════════════════════════════════════════════════════════════
# POST /api/sheet/save-weekly/
# Tab 3 — create new or update existing MukkadamWeeklyPayment
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["POST"])
def sheet_save_weekly(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    weekly_id    = data.get("weekly_id")
    assignment_id = data.get("assignment_id")
    amount       = Decimal(str(data.get("amount", 0) or 0))
    mode         = data.get("mode", "CASH")
    notes        = data.get("notes", "")
    pay_date     = _parse_date(data.get("payment_date", ""))
    crew_size    = int(data.get("crew_size", 0) or 0)

    if not pay_date:
        return JsonResponse({"error": "payment_date required"}, status=400)

    # UPDATE existing
    if weekly_id:
        try:
            p = MukkadamWeeklyPayment.objects.select_related(
                "assignment", "assignment__mukkadam", "assignment__cluster"
            ).get(id=weekly_id)
        except MukkadamWeeklyPayment.DoesNotExist:
            return JsonResponse({"error": f"WeeklyPayment {weekly_id} not found"}, status=404)

        if amount > 0:
            p.amount = amount
        p.mode   = mode
        p.notes  = notes
        p.is_auto_generated = False  # team edited it
        p.save(update_fields=["amount", "mode", "notes", "is_auto_generated"])

        assign = p.assignment
        weekly_amt = float(assign.weekly_amount or 0)
        auto_amt   = (p.crew_size_on_date or 0) * weekly_amt

        return JsonResponse({
            "success":       True,
            "weekly_id":     p.id,
            "assignment_id": assign.id,
            "auto_amount":   auto_amt,
            "crew_size":     p.crew_size_on_date or 0,
        })

    # CREATE new — resolve assignment by assignment_id or by mukkadam+cluster names
    if assignment_id:
        try:
            assign = ClusterMukkadamAssignment.objects.select_related(
                "mukkadam", "cluster"
            ).get(id=assignment_id)
        except ClusterMukkadamAssignment.DoesNotExist:
            assign = None
    else:
        assign = None

    if not assign:
        # Try to find by names
        mukk_name = data.get("mukkadam_name", "")
        clus_name = data.get("cluster", "")
        assign = ClusterMukkadamAssignment.objects.filter(
            mukkadam__mukkadam_name__iexact=mukk_name,
            cluster__name__iexact=clus_name,
            is_active=True,
        ).first()

    if not assign:
        return JsonResponse({
            "error": f"No active assignment found for {data.get('mukkadam_name')} / {data.get('cluster')}"
        }, status=404)

    weekly_amt = float(assign.weekly_amount or 0)
    if crew_size == 0:
        # Try to infer crew size from a recent payment or default to 0
        crew_size = 0
    auto_amt = crew_size * weekly_amt
    final_amount = amount if amount > 0 else Decimal(str(auto_amt))

    try:
        p, created = MukkadamWeeklyPayment.objects.get_or_create(
            assignment=assign,
            payment_date=pay_date,
            defaults={
                "amount":            final_amount,
                "crew_size_on_date": crew_size,
                "mode":              mode,
                "notes":             notes,
                "is_auto_generated": False,
            }
        )
        if not created:
            p.amount = final_amount
            p.mode   = mode
            p.notes  = notes
            p.is_auto_generated = False
            p.save(update_fields=["amount", "mode", "notes", "is_auto_generated"])
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    # Update running total on assignment
    total = MukkadamWeeklyPayment.objects.filter(assignment=assign).aggregate(
        t=Sum("amount")
    )["t"] or 0
    ClusterMukkadamAssignment.objects.filter(id=assign.id).update(
        total_weekly_payments=total
    )

    return JsonResponse({
        "success":       True,
        "weekly_id":     p.id,
        "assignment_id": assign.id,
        "auto_amount":   auto_amt,
        "crew_size":     crew_size,
    })


# ═══════════════════════════════════════════════════════════════════
# GET /api/sheet/other-payments/
# Tab 4 — reads MukkadamMiscCost + MukkadamLedgerEntry(type=advance)
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["GET"])
def sheet_get_other(request):
    try:
        rows = []

        # ── Misc costs (includes standalone transport) ─────────────
        misc_qs = (
            MukkadamMiscCost.objects
            .select_related("mukkadam", "job")
            .order_by("-created_at")
        )
        for m in misc_qs:
            # Detect if the reason string starts with "Transport" → display as transport type
            reason_lower = (m.reason or "").strip().lower()
            if reason_lower.startswith("transport"):
                display_type = "transport"
            else:
                display_type = "misc"

            # Try to find cluster from mukkadam's active assignment
            cluster_name = _get_mukkadam_cluster(m.mukkadam)

            rows.append({
                "record_id":            m.id,
                "record_type":          "misc_cost",
                "payment_type_display": display_type,
                "mukkadam_name":        m.mukkadam.mukkadam_name,
                "cluster":              cluster_name,
                "amount":               float(m.amount or 0),
                "reason":               m.reason or "",
                "job_id":               m.job.job_id if m.job_id else "",
                "payment_date":         "",   # MiscCost has no payment_date field — uses created_at
                "verified_str":         "verified" if m.verified else "unverified",
                "notes":                "",
                "created_at":           _fmt_date(m.created_at.date() if m.created_at else None),
            })

        # ── Advance ledger entries ─────────────────────────────────
        advance_qs = (
            MukkadamLedgerEntry.objects
            .select_related("mukkadam", "cluster", "job")
            .filter(payment_type="advance")
            .order_by("-job_date")
        )
        for a in advance_qs:
            rows.append({
                "record_id":            a.id,
                "record_type":          "ledger_advance",
                "payment_type_display": "advance",
                "mukkadam_name":        a.mukkadam.mukkadam_name,
                "cluster":              a.cluster.name if a.cluster_id else "",
                "amount":               float(a.amount or 0),
                "reason":               a.remark or "",
                "job_id":               a.job.job_id if a.job_id else "",
                "payment_date":         _fmt_date(a.payment_date),
                "verified_str":         "verified" if a.payment_status == "paid" else "unverified",
                "notes":                "",
                "created_at":           _fmt_date(a.job_date),
            })

        return JsonResponse({"rows": rows, "total": len(rows)})

    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


def _get_mukkadam_cluster(mukkadam):
    try:
        assign = ClusterMukkadamAssignment.objects.filter(
            mukkadam=mukkadam, is_active=True
        ).select_related("cluster").first()
        return assign.cluster.name if assign else ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════
# POST /api/sheet/save-other/
# Tab 4 — create new or update existing misc cost / advance
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["POST"])
def sheet_save_other(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    record_id   = data.get("record_id")
    record_type = data.get("record_type")
    ptype       = data.get("type", "misc").lower()
    amount      = Decimal(str(data.get("amount", 0) or 0))
    reason      = data.get("reason", "")
    verified_s  = data.get("verified", "unverified").lower()
    job_id_str  = data.get("job_id", "")
    pay_date    = _parse_date(data.get("payment_date", ""))
    notes       = data.get("notes", "")
    mukk_name   = data.get("mukkadam_name", "")
    clus_name   = data.get("cluster", "")

    # ── UPDATE existing ─────────────────────────────────────────────
    if record_id and record_type:
        if record_type == "misc_cost":
            try:
                m = MukkadamMiscCost.objects.get(id=record_id)
            except MukkadamMiscCost.DoesNotExist:
                return JsonResponse({"error": f"MiscCost {record_id} not found"}, status=404)
            m.amount   = amount
            m.reason   = reason
            m.verified = (verified_s == "verified")
            m.save(update_fields=["amount", "reason", "verified"])
            return JsonResponse({"success": True, "record_id": m.id, "record_type": "misc_cost"})

        elif record_type == "ledger_advance":
            try:
                a = MukkadamLedgerEntry.objects.get(id=record_id)
            except MukkadamLedgerEntry.DoesNotExist:
                return JsonResponse({"error": f"LedgerEntry {record_id} not found"}, status=404)
            a.amount         = amount
            a.remark         = reason
            a.payment_date   = pay_date
            a.payment_status = "paid" if verified_s == "verified" else "pending"
            a.save(update_fields=["amount", "remark", "payment_date", "payment_status"])
            return JsonResponse({"success": True, "record_id": a.id, "record_type": "ledger_advance"})

    # ── CREATE new ──────────────────────────────────────────────────
    # Resolve mukkadam
    try:
        mukkadam = Mukkadam.objects.get(mukkadam_name__iexact=mukk_name)
    except Mukkadam.DoesNotExist:
        return JsonResponse({"error": f"Mukkadam '{mukk_name}' not found"}, status=404)

    # Resolve cluster
    cluster = None
    if clus_name:
        cluster = Cluster.objects.filter(name__iexact=clus_name).first()

    # Resolve job (optional)
    job = None
    if job_id_str:
        from .models import Job
        job = Job.objects.filter(job_id=job_id_str).first()

    if ptype in ("misc", "transport"):
        # Both go into MukkadamMiscCost
        # Prefix reason with "Transport:" for transport type
        full_reason = f"Transport: {reason}" if ptype == "transport" and not reason.lower().startswith("transport") else reason
        m = MukkadamMiscCost.objects.create(
            mukkadam=mukkadam,
            job=job,
            amount=amount,
            reason=full_reason,
            verified=(verified_s == "verified"),
        )
        return JsonResponse({"success": True, "record_id": m.id, "record_type": "misc_cost"})

    elif ptype == "advance":
        # Advance goes into MukkadamLedgerEntry
        a = MukkadamLedgerEntry.objects.create(
            mukkadam=mukkadam,
            cluster=cluster,
            amount=amount,
            payment_type="advance",
            remark=reason or "Advance",
            job_date=pay_date or date.today(),
            payment_date=pay_date,
            payment_status="paid" if verified_s == "verified" else "pending",
            job=job,
            farmer_name="",
            activity_name="",
        )
        return JsonResponse({"success": True, "record_id": a.id, "record_type": "ledger_advance"})

    return JsonResponse({"error": f"Unknown type '{ptype}'"}, status=400)


# ═══════════════════════════════════════════════════════════════════
# GET /api/sheet/summary/
# Tab 5 — aggregated per-mukkadam balance from all models
# ═══════════════════════════════════════════════════════════════════
@csrf_exempt
@require_http_methods(["GET"])
def sheet_get_summary(request):
    try:
        rows = []

        # Get all active cluster-mukkadam assignments
        assignments = (
            ClusterMukkadamAssignment.objects
            .filter(is_active=True)
            .select_related("mukkadam", "cluster")
            .order_by("cluster__name", "mukkadam__mukkadam_name")
        )

        for assign in assignments:
            mukkadam = assign.mukkadam
            cluster  = assign.cluster

            # Gross earned = sum of all allocation expected amounts for this mukkadam+cluster
            gross = Allocation.objects.filter(
                mukkadam=mukkadam, cluster=cluster
            ).aggregate(t=Sum("mukkadam_amount"))["t"] or 0

            # Weekly paid
            weekly_paid = MukkadamWeeklyPayment.objects.filter(
                assignment=assign
            ).aggregate(t=Sum("amount"))["t"] or 0

            # Advances given
            advances = MukkadamLedgerEntry.objects.filter(
                mukkadam=mukkadam, cluster=cluster, payment_type="advance"
            ).aggregate(t=Sum("amount"))["t"] or 0

            # Misc + standalone transport
            misc_trans = MukkadamMiscCost.objects.filter(
                mukkadam=mukkadam
            ).aggregate(t=Sum("amount"))["t"] or 0

            # Deposit held (sum across all open settlements)
            deposit_held = MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, cluster=cluster,
                status__in=["pending", "calculated", "payment_raised"]
            ).aggregate(t=Sum("payable_amount"))["t"] or 0
            # Actually deposit_held is a property — use gross * deposit_pct approach
            deposit_held_real = MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, cluster=cluster
            ).aggregate(t=Sum("gross_amount"))
            all_gross = deposit_held_real["t"] or 0
            all_payable = MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, cluster=cluster
            ).aggregate(t=Sum("payable_amount"))["t"] or 0
            deposit_held = float(all_gross) - float(all_payable)

            # Settled = sum of paid settlements
            settled = MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, cluster=cluster, status="paid"
            ).aggregate(t=Sum("net_payable"))["t"] or 0

            # Net outstanding = sum of net_payable across non-paid settlements
            net_outstanding = MukkadamJobSettlement.objects.filter(
                mukkadam=mukkadam, cluster=cluster,
                status__in=["pending", "calculated", "payment_raised"]
            ).aggregate(t=Sum("net_payable"))["t"] or 0

            rows.append({
                "mukkadam_name":   mukkadam.mukkadam_name,
                "cluster":         cluster.name,
                "mukkadam_type":   assign.mukkadam_type,
                "gross_earned":    float(gross),
                "weekly_paid":     float(weekly_paid),
                "advances":        float(advances),
                "misc_transport":  float(misc_trans),
                "deposit_held":    float(max(deposit_held, 0)),
                "settled_amount":  float(settled),
                "net_outstanding": float(net_outstanding),
            })

        return JsonResponse({"rows": rows, "total": len(rows)})

    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)