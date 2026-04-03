"""
sheet_views.py — All Django API endpoints consumed by the Google Sheet.
Field names corrected to match actual model snake_case fields.
"""

from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    ClusterMukkadamAssignment,
    Mukkadam,
    MukkadamWeeklyPayment,
    MukkadamLedgerEntry,
    MukkadamJobSettlement,
    MukkadamPayment,
    MukkadamMiscCost,
    Allocation,
    JobActivity,
    Cluster,
    Job,
)

# ---------------------------------------------------------------------------
# AUTH HELPER
# ---------------------------------------------------------------------------

def _sheet_auth(request):
    from django.conf import settings
    token = getattr(settings, "SHEET_API_TOKEN", None)
    if not token:
        return True
    auth_header = request.headers.get("Authorization", "")
    return auth_header == f"Bearer {token}"


def _type_display(mukkadam_type):
    mapping = {
        "permanent": "Permanent",
        "updown":    "Updown",
        "dual":      "Permanent + Updown",
    }
    return mapping.get(str(mukkadam_type).lower(), mukkadam_type or "Unknown")


# ---------------------------------------------------------------------------
# 1. VALIDATE TOKEN
# ---------------------------------------------------------------------------

@api_view(["GET"])
def validate_token(request):
    if not _sheet_auth(request):
        return Response({"valid": False, "error": "Unauthorized"}, status=401)
    return Response({"valid": True, "message": "Token OK"})


# ---------------------------------------------------------------------------
# 2. MUKKADAM MASTER
# Correct field names from error log:
#   mukkadam_type (not mukkadamtype)
#   weekly_payment_day (not weeklypaymentday)
#   joined_date (not joineddate)
#   total_weekly_payments (not totalweeklypayments)
#   advance_is_manual (not advanceismanual)
#   updown_from_date, updown_to_date, updown_mode, updown_specific_dates ✓
# ---------------------------------------------------------------------------

@api_view(["GET"])
def mukkadam_master_list_v2(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id = request.query_params.get("cluster_id")
    qs = ClusterMukkadamAssignment.objects.select_related(
        "mukkadam", "cluster"
    ).filter(is_active=True)
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    # Build dual-type map
    types_by_mukkadam = defaultdict(set)
    for a in qs:
        types_by_mukkadam[a.mukkadam_id].add(a.mukkadam_type)

    rows = []
    for a in qs.order_by("cluster__name", "mukkadam__mukkadam_name"):
        m = a.mukkadam
        all_types = types_by_mukkadam[m.mukkadam_id]
        if "permanent" in all_types and "updown" in all_types:
            type_display = "Permanent + Updown (Dual)"
        else:
            type_display = _type_display(a.mukkadam_type)

        # weekly_payment_day display
        wpd_label = ""
        if a.weekly_payment_day is not None:
            day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            try:
                wpd_label = day_names[int(a.weekly_payment_day)]
            except (ValueError, IndexError):
                wpd_label = str(a.weekly_payment_day)

        rows.append({
            "mukkadam_id":            m.mukkadam_id,
            "mukkadam_name":          m.mukkadam_name,
            "mobile":                 m.mobile_numbers,
            "cluster_name":           a.cluster.name,
            "cluster_id":             a.cluster_id,
            "mukkadam_type":          a.mukkadam_type,
            "mukkadam_type_display":  type_display,
            "updown_mode":            a.updown_mode or "",
            "updown_from_date":       str(a.updown_from_date or ""),
            "updown_to_date":         str(a.updown_to_date or ""),
            "updown_specific_dates":  a.updown_specific_dates or "",
            "crew_size":              m.crew_size,
            "max_crew_capacity":      m.max_crew_capacity,
            "has_smartphone":         m.has_smartphone,
            "state":                  m.state,
            "district":               m.district,
            "taluka":                 m.taluka,
            "village":                m.village,
            "weekly_amount":          float(a.weekly_amount),
            "weekly_payment_day":     a.weekly_payment_day,
            "weekly_payment_day_label": wpd_label,
            "transport_price":        float(a.transport_price),
            "advance_amount":         float(a.advance_amount),
            "advance_is_manual":      a.advance_is_manual,
            "joined_date":            str(a.joined_date) if a.joined_date else None,
            "is_active":              a.is_active,
            "efficiency":             float(m.efficiency) if m.efficiency else 0,
            "manual_status":          m.manual_status or "",
            "status_note":            m.manual_status_note or "",
            "assignment_id":          a.id,
            "total_weekly_paid":      float(a.total_weekly_payments or 0),
        })
    return Response({"count": len(rows), "results": rows})


@api_view(["POST"])
def mukkadam_master_update(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    assignment_id = request.data.get("assignment_id")
    if not assignment_id:
        return Response({"error": "assignment_id required"}, status=400)

    try:
        a = ClusterMukkadamAssignment.objects.get(id=assignment_id)
    except ClusterMukkadamAssignment.DoesNotExist:
        return Response({"error": "Assignment not found"}, status=404)

    fields_to_update = []

    if "weekly_amount" in request.data:
        a.weekly_amount = Decimal(str(request.data["weekly_amount"]))
        fields_to_update.append("weekly_amount")

    if "weekly_payment_day" in request.data:
        val = request.data["weekly_payment_day"]
        a.weekly_payment_day = int(val) if val not in ("", None) else None
        fields_to_update.append("weekly_payment_day")

    if "transport_price" in request.data:
        a.transport_price = Decimal(str(request.data["transport_price"]))
        fields_to_update.append("transport_price")

    if "advance_amount" in request.data:
        a.advance_amount = Decimal(str(request.data["advance_amount"]))
        fields_to_update.append("advance_amount")

    if "mukkadam_type" in request.data:
        a.mukkadam_type = request.data["mukkadam_type"]
        fields_to_update.append("mukkadam_type")

    for field_name in ["updown_mode", "updown_from_date", "updown_to_date", "updown_specific_dates"]:
        if field_name in request.data and hasattr(a, field_name):
            setattr(a, field_name, request.data[field_name] or None)
            fields_to_update.append(field_name)

    if fields_to_update:
        fields_to_update.append("updated_at")
        a.save(update_fields=fields_to_update)

    return Response({
        "success": True,
        "assignment_id": a.id,
        "updated_fields": fields_to_update,
    })


# ---------------------------------------------------------------------------
# 3. WEEKLY PAYMENTS
# Correct field names from error log:
#   payment_date (not paymentdate)
#   crew_size_on_date (not crewsizeondate)
#   is_auto_generated (not isautogenerated)
#   proof_s3_key ✓
# ---------------------------------------------------------------------------

@api_view(["GET"])
def weekly_payments_list(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id = request.query_params.get("cluster_id")
    limit = int(request.query_params.get("limit", 200))

    qs = MukkadamWeeklyPayment.objects.select_related(
        "assignment__mukkadam", "assignment__cluster"
    ).order_by("-payment_date")

    if cluster_id:
        qs = qs.filter(assignment__cluster_id=cluster_id)

    rows = []
    for w in qs[:limit]:
        a = w.assignment
        rows.append({
            "db_id":             w.id,
            "assignment_id":     a.id,
            "mukkadam_id":       a.mukkadam.mukkadam_id,
            "mukkadam_name":     a.mukkadam.mukkadam_name,
            "cluster_name":      a.cluster.name,
            "cluster_id":        a.cluster_id,
            "mukkadam_type":     a.mukkadam_type,
            "mukkadam_type_display": _type_display(a.mukkadam_type),
            "payment_date":      str(w.payment_date),
            "crew_size_on_date": w.crew_size_on_date,
            "amount":            float(w.amount),
            "mode":              w.mode,
            "notes":             w.notes or "",
            "proof_s3_key":      w.proof_s3_key or "",
            "is_autogenerated":  w.is_auto_generated,
        })
    return Response({"count": len(rows), "results": rows})


@api_view(["POST"])
def add_weekly_payment(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    for field in ["assignment_id", "payment_date", "amount"]:
        if not request.data.get(field):
            return Response({"error": f"{field} is required"}, status=400)

    try:
        assignment = ClusterMukkadamAssignment.objects.select_related(
            "mukkadam", "cluster"
        ).get(id=request.data["assignment_id"])
    except ClusterMukkadamAssignment.DoesNotExist:
        return Response({"error": "Assignment not found"}, status=404)

    if assignment.mukkadam_type == "updown":
        return Response({
            "error": "Updown mukkadams do not receive weekly payments.",
            "mukkadam_type": "updown",
        }, status=400)

    payment_date = request.data["payment_date"]
    amount = Decimal(str(request.data["amount"]))
    mode = request.data.get("mode", "CASH")
    notes = request.data.get("notes", "")
    crew_size = request.data.get("crew_size_on_date") or assignment.mukkadam.crew_size or 0

    weekly_payment, created = MukkadamWeeklyPayment.objects.get_or_create(
        assignment=assignment,
        payment_date=payment_date,
        defaults={
            "amount":           amount,
            "crew_size_on_date": int(crew_size),
            "mode":             mode,
            "is_auto_generated": False,
            "notes":            notes,
        }
    )

    if not created:
        return Response({
            "error": f"Weekly payment already recorded for {payment_date}",
            "existing_id": weekly_payment.id,
            "existing_amount": float(weekly_payment.amount),
        }, status=400)

    # Ledger entry
    MukkadamLedgerEntry.objects.create(
        mukkadam=assignment.mukkadam,
        cluster=assignment.cluster,
        payment_type="weeklypayment",
        payment_date=payment_date,
        amount=amount,
        payment_status="paid",
        remark=notes,
    )

    # Update running total
    assignment.total_weekly_payments = (
        assignment.total_weekly_payments or Decimal(0)
    ) + amount
    assignment.save(update_fields=["total_weekly_payments", "updated_at"])

    return Response({
        "success":      True,
        "id":           weekly_payment.id,
        "payment_date": str(weekly_payment.payment_date),
        "amount":       float(weekly_payment.amount),
        "mukkadam":     assignment.mukkadam.mukkadam_name,
        "cluster":      assignment.cluster.name,
    })


# ---------------------------------------------------------------------------
# 4. TRANSPORT EVENTS
# Correct field names from error log:
#   payment_type (not paymenttype)
#   payment_date (not paymentdate)
#   payment_status (not paymentstatus)
#   proof_s3_key ✓
# ---------------------------------------------------------------------------

@api_view(["GET"])
def transport_events_list(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id = request.query_params.get("cluster_id")
    qs = MukkadamLedgerEntry.objects.select_related(
        "mukkadam", "cluster", "job"
    ).filter(payment_type="transport").order_by("-payment_date")

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    rows = []
    for e in qs[:300]:
        remark = e.remark or ""
        parts = [p.strip() for p in remark.split("|")]
        rows.append({
            "ledger_id":      e.id,
            "mukkadam_id":    e.mukkadam.mukkadam_id,
            "mukkadam_name":  e.mukkadam.mukkadam_name,
            "cluster_name":   e.cluster.name if e.cluster else "",
            "cluster_id":     e.cluster_id,
            "event_date":     str(e.payment_date) if e.payment_date else "",
            "direction":      parts[0] if len(parts) > 0 else "",
            "from_location":  parts[1] if len(parts) > 1 else "",
            "to_location":    parts[2] if len(parts) > 2 else "",
            "vehicle_type":   parts[3] if len(parts) > 3 else "",
            "transport_cost": float(e.amount),
            "job_id":         e.job.job_id if e.job else "",
            "paid_by":        parts[4] if len(parts) > 4 else "",
            "notes":          e.remark or "",
            "proof_s3_key":   e.proof_s3_key or "",
            "payment_status": e.payment_status,
        })
    return Response({"count": len(rows), "results": rows})


@api_view(["POST"])
def add_transport_event(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    for field in ["mukkadam_id", "event_date", "transport_cost"]:
        if request.data.get(field) in (None, ""):
            return Response({"error": f"{field} is required"}, status=400)

    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=request.data["mukkadam_id"])
    except Mukkadam.DoesNotExist:
        return Response({"error": "Mukkadam not found"}, status=404)

    cluster = None
    if request.data.get("cluster_id"):
        try:
            cluster = Cluster.objects.get(id=request.data["cluster_id"])
        except Cluster.DoesNotExist:
            pass

    assignment = ClusterMukkadamAssignment.objects.filter(
        mukkadam=mukkadam, is_active=True
    ).order_by("-joined_at").first()

    warning = None
    if assignment and assignment.mukkadam_type == "permanent":
        warning = "Permanent mukkadams usually have transport_price=0. Entry saved but please verify."

    job = None
    if request.data.get("job_id"):
        try:
            job = Job.objects.get(jobid=request.data["job_id"])
        except Job.DoesNotExist:
            pass

    direction = request.data.get("direction", "arrival")
    from_loc  = request.data.get("from_location", "")
    to_loc    = request.data.get("to_location", "")
    vehicle   = request.data.get("vehicle_type", "")
    paid_by   = request.data.get("paid_by", "")
    notes     = request.data.get("notes", "")
    remark_combined = f"{direction} | {from_loc} | {to_loc} | {vehicle} | {paid_by} | {notes}"

    entry = MukkadamLedgerEntry.objects.create(
        mukkadam=mukkadam,
        cluster=cluster,
        job=job,
        payment_type="transport",
        payment_date=request.data["event_date"],
        amount=Decimal(str(request.data["transport_cost"])),
        payment_status="paid",
        remark=remark_combined,
        proof_s3_key=request.data.get("proof_s3_key") or None,
    )

    return Response({
        "success":    True,
        "ledger_id":  entry.id,
        "warning":    warning,
        "mukkadam":   mukkadam.mukkadam_name,
        "amount":     float(entry.amount),
        "event_date": str(entry.payment_date),
    })


# ---------------------------------------------------------------------------
# 5. ALLOCATIONS VIEW
# Correct field names from error log:
#   allocated_date (not allocateddate)
#   allocated_area (not allocatedarea)
#   allocated_workers (not allocatedworkers)
#   mukkadam_rate (not mukkadamrate)
#   farmer_rate (not farmerrate)
#   admin_override_area (not adminoverridearea)
#   use_actual_for_settlement (not useactualforsettlement)
#   actual_area_done (not actualareadone)
#   actual_crew_size (not actualcrewsize)
#   report_submitted (not reportsubmitted)
#   work_status ✓
#   payment_status ✓
#   farmer_agreed (not farmeragreed)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def allocations_view(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id  = request.query_params.get("cluster_id")
    mukkadam_id = request.query_params.get("mukkadam_id")

    qs = Allocation.objects.select_related(
        "mukkadam", "cluster",
        "job_activity__activity", "job_activity__plot",
        "job_activity__job__farmer",
    ).order_by("-allocated_date")

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if mukkadam_id:
        qs = qs.filter(mukkadam__mukkadam_id=mukkadam_id)

    today = date.today()

    assignment_map = {
        a.mukkadam_id: a
        for a in ClusterMukkadamAssignment.objects.filter(is_active=True)
    }

    rows = []
    for a in qs[:500]:
        ja     = a.job_activity
        plot   = ja.plot if ja else None
        job    = ja.job if ja else None
        farmer = job.farmer if job else None
        act    = ja.activity if ja else None
        asgn   = assignment_map.get(a.mukkadam_id)

        if a.admin_override_area is not None:
            effective_area = float(a.admin_override_area)
            area_source = "admin_override"
        elif getattr(a, "use_actual_for_settlement", False) and a.actual_area_done:
            effective_area = float(a.actual_area_done)
            area_source = "actual_done"
        elif a.farmer_agreed and a.actual_area_done:
            effective_area = float(a.actual_area_done)
            area_source = "farmer_agreed_actual"
        else:
            effective_area = float(a.allocated_area or 0)
            area_source = "allocated"

        rows.append({
            "allocation_id":     a.id,
            "mukkadam_id":       a.mukkadam.mukkadam_id,
            "mukkadam_name":     a.mukkadam.mukkadam_name,
            "cluster_name":      a.cluster.name if a.cluster else "",
            "mukkadam_type":     asgn.mukkadam_type if asgn else "",
            "mukkadam_type_display": _type_display(asgn.mukkadam_type) if asgn else "",
            "job_id":            job.job_id if job else "",
            "farmer_name":       farmer.farmer_name if farmer else "",
            "farmer_id":         str(farmer.farmer_id) if farmer else "",
            "activity_name":     act.name if act else "",
            "plot_code":         plot.plot_code if plot else "",
            "plot_name":         plot.name if plot else "",
            "allocated_date":    str(a.allocated_date),
            "allocated_area":    float(a.allocated_area or 0),
            "allocated_workers": a.allocated_workers or 0,
            "mukkadam_rate":     float(a.mukkadam_rate or 0),
            "farmer_rate":       float(a.farmer_rate or 0),
            "effective_area":    effective_area,
            "area_source":       area_source,
            "gross_mukkadam_amt":round(effective_area * float(a.mukkadam_rate or 0), 2),
            "actual_area_done":  float(a.actual_area_done) if a.actual_area_done else None,
            "actual_crew_size":  a.actual_crew_size,
            "work_status":       a.work_status or "",
            "payment_status":    a.payment_status or "",
            "farmer_agreed":     a.farmer_agreed,
            "report_submitted":  a.report_submitted,
            "is_past":           a.allocated_date <= today,
        })
    return Response({"count": len(rows), "results": rows})


# ---------------------------------------------------------------------------
# 6. JOB SETTLEMENTS
# Correct field names from error log:
#   created_at (not createdat)
#   calculated_at (not calculatedat) ✓
#   paid_at (not paidat) ✓
#   weekly_payments_applied (not weeklypaymentsapplied)
#   weekly_payments_deducted (not weeklypaymentsdeducted)
#   advance_deducted (not advancededucted) ✓
#   transport_deducted ✓
#   deposit_carried_forward (not depositcarriedforward) ✓
#   credit_carried_forward ✓
#   gross_amount (not grossamount) ✓
#   deposit_percent (not depositpercent) ✓
#   payable_amount (not payableamount) ✓
#   net_payable (not netpayable) ✓
# ---------------------------------------------------------------------------

@api_view(["GET"])
def job_settlements_list(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id  = request.query_params.get("cluster_id")
    status      = request.query_params.get("status")
    mukkadam_id = request.query_params.get("mukkadam_id")

    qs = MukkadamJobSettlement.objects.select_related(
        "mukkadam", "job__farmer", "cluster"
    ).prefetch_related("weekly_payments_applied").order_by("-created_at")

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if status:
        qs = qs.filter(status=status)
    if mukkadam_id:
        qs = qs.filter(mukkadam__mukkadam_id=mukkadam_id)

    assignment_map = {
        a.mukkadam_id: a
        for a in ClusterMukkadamAssignment.objects.filter(is_active=True)
    }

    rows = []
    for s in qs[:300]:
        asgn = assignment_map.get(s.mukkadam_id)

        weekly_applied = list(s.weekly_payments_applied.values(
            "id", "payment_date", "amount", "crew_size_on_date", "mode"
        ))

        misc_costs = MukkadamMiscCost.objects.filter(
            mukkadam=s.mukkadam, job=s.job
        ).values("id", "amount", "reason", "verified", "created_at")
        total_misc = sum(float(m["amount"]) for m in misc_costs)

        deposit_held = round(
            float(s.gross_amount) * float(s.deposit_percent or 10) / 100, 2
        )

        rows.append({
            "settlement_id":       s.id,
            "mukkadam_id":         s.mukkadam.mukkadam_id,
            "mukkadam_name":       s.mukkadam.mukkadam_name,
            "mukkadam_type":       asgn.mukkadam_type if asgn else "",
            "mukkadam_type_display": _type_display(asgn.mukkadam_type) if asgn else "",
            "job_id":              s.job.job_id,
            "farmer_name":         s.job.farmer.farmer_name,
            "farmer_id":           str(s.job.farmer.farmer_id),
            "cluster_name":        s.cluster.name if s.cluster else "",
            "cluster_id":          s.cluster_id,
            "gross_amount":        float(s.gross_amount),
            "deposit_percent":     float(s.deposit_percent or 10),
            "deposit_held":        deposit_held,
            "payable_90pct":       float(s.payable_amount),
            "advance_deducted":    float(s.advance_deducted),
            "weekly_deducted":     float(s.weekly_payments_deducted),
            "transport_deducted":  float(s.transport_deducted or 0),
            "misc_total":          total_misc,
            "deposit_carried_fwd": float(s.deposit_carried_forward or 0),
            "credit_carried_fwd":  float(s.credit_carried_forward or 0),
            "net_payable":         float(s.net_payable),
            "status":              s.status,
            "calculated_at":       str(s.calculated_at.date()) if s.calculated_at else "",
            "paid_at":             str(s.paid_at.date()) if s.paid_at else "",
            "weekly_applied_count": len(weekly_applied),
            "weekly_applied": [
                {
                    "id":     w["id"],
                    "date":   str(w["payment_date"]),
                    "amount": float(w["amount"]),
                    "crew":   w["crew_size_on_date"],
                    "mode":   w["mode"],
                }
                for w in weekly_applied
            ],
            "misc_costs": [
                {
                    "id":       m["id"],
                    "amount":   float(m["amount"]),
                    "reason":   m["reason"],
                    "verified": m["verified"],
                }
                for m in misc_costs
            ],
            "can_pay": s.status == "calculated" and float(s.net_payable) > 0,
        })
    return Response({"count": len(rows), "results": rows})


@api_view(["POST"])
def mark_settlement_paid(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    settlement_id = request.data.get("settlement_id")
    if not settlement_id:
        return Response({"error": "settlement_id required"}, status=400)

    try:
        settlement = MukkadamJobSettlement.objects.select_related(
            "mukkadam", "job"
        ).get(id=settlement_id)
    except MukkadamJobSettlement.DoesNotExist:
        return Response({"error": "Settlement not found"}, status=404)

    if settlement.status == "paid":
        return Response({
            "error":       "Already paid",
            "paid_at":     str(settlement.paid_at),
            "net_payable": float(settlement.net_payable),
        }, status=400)

    if float(settlement.net_payable) <= 0:
        return Response({"error": "No payment needed — net payable is 0 or negative"}, status=400)

    mode         = request.data.get("mode", "CASH")
    notes        = request.data.get("notes", "")
    proof_s3_key = request.data.get("proof_s3_key") or None

    with transaction.atomic():
        payment = MukkadamPayment.objects.create(
            mukkadam=settlement.mukkadam,
            settlement=settlement,
            payment_id=f"SETTLE-{settlement.job.job_id}-{settlement.mukkadam.mukkadam_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            amount=settlement.net_payable,
            mode=mode,
            notes=f"Sheet settlement pay: {notes}" if notes else "Marked paid via sheet",
            paid_at=timezone.now(),
            proof_s3_key=proof_s3_key,
        )
        settlement.status = "paid"
        settlement.paid_at = timezone.now()
        settlement.save(update_fields=["status", "paid_at"])

    return Response({
        "success":     True,
        "payment_id":  payment.id,
        "paid_amount": float(settlement.net_payable),
        "mukkadam":    settlement.mukkadam.mukkadam_name,
        "job_id":      settlement.job.job_id,
        "mode":        mode,
    })


# ---------------------------------------------------------------------------
# 7. LEDGER ALL
# Correct field names from error log:
#   payment_date (not paymentdate)
#   payment_type (not paymenttype)
#   payment_status (not paymentstatus)
#   created_at (not createdat)
#   proof_s3_key ✓
#   activity_name ✓
#   job_activity (not jobactivity)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def ledger_all(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id   = request.query_params.get("cluster_id")
    mukkadam_id  = request.query_params.get("mukkadam_id")
    payment_type = request.query_params.get("payment_type")
    limit        = int(request.query_params.get("limit", 500))

    qs = MukkadamLedgerEntry.objects.select_related(
        "mukkadam", "cluster", "job__farmer", "job_activity__activity"
    ).order_by("-payment_date", "-created_at")

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if mukkadam_id:
        qs = qs.filter(mukkadam__mukkadam_id=mukkadam_id)
    if payment_type:
        qs = qs.filter(payment_type=payment_type)

    rows = []
    for e in qs[:limit]:
        rows.append({
            "ledger_id":            e.id,
            "mukkadam_id":          e.mukkadam.mukkadam_id,
            "mukkadam_name":        e.mukkadam.mukkadam_name,
            "cluster_name":         e.cluster.name if e.cluster else "",
            "cluster_id":           e.cluster_id,
            "payment_type":         e.payment_type,
            "payment_type_display": e.get_payment_type_display(),
            "job_id":               e.job.job_id if e.job else "",
            "farmer_name":          e.job.farmer.farmer_name if e.job and e.job.farmer else "",
            "activity_name":        e.activity_name or (
                e.job_activity.activity.name if e.job_activity else ""
            ),
            "job_date":             str(e.job_date) if e.job_date else "",
            "payment_date":         str(e.payment_date) if e.payment_date else "",
            "amount":               float(e.amount),
            "acres":                float(e.acres) if e.acres else None,
            "payment_status":       e.payment_status,
            "remark":               e.remark or "",
            "proof_s3_key":         e.proof_s3_key or "",
            "created_at":           str(e.created_at.date()),
        })
    return Response({"count": len(rows), "results": rows})


@api_view(["POST"])
def add_ledger_entry(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    for field in ["mukkadam_id", "payment_type", "payment_date", "amount"]:
        if request.data.get(field) in (None, ""):
            return Response({"error": f"{field} is required"}, status=400)

    valid_types = ["advance", "transport", "weeklypayment", "peracre", "misc"]
    if request.data["payment_type"] not in valid_types:
        return Response({"error": f"payment_type must be one of: {valid_types}"}, status=400)

    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=request.data["mukkadam_id"])
    except Mukkadam.DoesNotExist:
        return Response({"error": "Mukkadam not found"}, status=404)

    cluster = None
    if request.data.get("cluster_id"):
        try:
            cluster = Cluster.objects.get(id=request.data["cluster_id"])
        except Cluster.DoesNotExist:
            pass

    job = None
    if request.data.get("job_id"):
        try:
            job = Job.objects.get(jobid=request.data["job_id"])
        except Job.DoesNotExist:
            pass

    entry = MukkadamLedgerEntry.objects.create(
        mukkadam=mukkadam,
        cluster=cluster,
        job=job,
        payment_type=request.data["payment_type"],
        activity_name=request.data.get("activity_name", ""),
        payment_date=request.data["payment_date"],
        amount=Decimal(str(request.data["amount"])),
        acres=Decimal(str(request.data["acres"])) if request.data.get("acres") else None,
        payment_status=request.data.get("payment_status", "paid"),
        remark=request.data.get("remark", ""),
        proof_s3_key=request.data.get("proof_s3_key") or None,
    )

    return Response({
        "success":      True,
        "ledger_id":    entry.id,
        "mukkadam":     mukkadam.mukkadam_name,
        "payment_type": entry.payment_type,
        "amount":       float(entry.amount),
        "payment_date": str(entry.payment_date),
    })


# ---------------------------------------------------------------------------
# 8. WEEKLY DUE TODAY
# Correct field names from error log:
#   weekly_payment_day (not weeklypaymentday)
#   mukkadam_type (not mukkadamtype)
#   joined_date (not joineddate)
#   payment_date (not paymentdate) for MukkadamWeeklyPayment
#   total_weekly_payments (not totalweeklypayments)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def weekly_due_today_v2(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    cluster_id = request.query_params.get("cluster_id")
    today = date.today()

    qs = ClusterMukkadamAssignment.objects.select_related(
        "mukkadam", "cluster"
    ).filter(is_active=True, weekly_payment_day__isnull=False)

    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

    due_list = []

    for asgn in qs:
        if asgn.mukkadam_type == "updown":
            continue

        also_updown = ClusterMukkadamAssignment.objects.filter(
            mukkadam=asgn.mukkadam, mukkadam_type="updown", is_active=True
        ).exists()
        type_display = "Permanent + Updown (Dual)" if also_updown else "Permanent"

        already_paid_today = MukkadamWeeklyPayment.objects.filter(
            assignment=asgn, payment_date=today
        ).exists()

        last_payment = MukkadamWeeklyPayment.objects.filter(
            assignment=asgn
        ).order_by("-payment_date").first()

        days_since_last = (today - last_payment.payment_date).days if last_payment else None
        is_due_today = today.weekday() == asgn.weekly_payment_day
        is_overdue   = last_payment and days_since_last and days_since_last > 7

        missed_dates = []
        if asgn.joined_date and not already_paid_today:
            paid_dates = set(
                MukkadamWeeklyPayment.objects.filter(assignment=asgn)
                .values_list("payment_date", flat=True)
            )
            current = asgn.joined_date
            while current <= today:
                if current.weekday() == asgn.weekly_payment_day and current < today:
                    if current not in paid_dates:
                        missed_dates.append(str(current))
                current += timedelta(days=1)

        if is_due_today or is_overdue or missed_dates:
            # weekly_payment_day display
            day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            try:
                wpd_label = day_names[int(asgn.weekly_payment_day)]
            except (ValueError, IndexError):
                wpd_label = str(asgn.weekly_payment_day)

            due_list.append({
                "assignment_id":         asgn.id,
                "mukkadam_id":           asgn.mukkadam.mukkadam_id,
                "mukkadam_name":         asgn.mukkadam.mukkadam_name,
                "mobile":                asgn.mukkadam.mobile_numbers,
                "cluster_id":            asgn.cluster_id,
                "cluster_name":          asgn.cluster.name,
                "mukkadam_type":         asgn.mukkadam_type,
                "mukkadam_type_display": type_display,
                "weekly_amount":         float(asgn.weekly_amount),
                "weekly_payment_day":    wpd_label,
                "crew_size":             asgn.mukkadam.crew_size,
                "is_due_today":          is_due_today,
                "is_overdue":            bool(is_overdue),
                "days_overdue":          max(0, days_since_last - 7) if days_since_last else 0,
                "last_paid_date":        str(last_payment.payment_date) if last_payment else None,
                "already_paid_today":    already_paid_today,
                "missed_dates":          missed_dates,
                "missed_count":          len(missed_dates),
            })

    due_list.sort(key=lambda x: (-x["days_overdue"], -x["is_due_today"]))
    total_due = sum(d["weekly_amount"] for d in due_list if not d["already_paid_today"])

    return Response({
        "today":            str(today),
        "total_count":      len(due_list),
        "total_amount_due": total_due,
        "due_list":         due_list,
    })


# ---------------------------------------------------------------------------
# 9. TEAM PROFILE
# ---------------------------------------------------------------------------

@api_view(["GET"])
def team_profile(request):
    if not _sheet_auth(request):
        return Response({"error": "Unauthorized"}, status=401)

    mukkadam_id = request.query_params.get("mukkadam_id")
    if not mukkadam_id:
        return Response({"error": "mukkadam_id required"}, status=400)

    try:
        mukkadam = Mukkadam.objects.get(mukkadam_id=mukkadam_id)
    except Mukkadam.DoesNotExist:
        return Response({"error": "Mukkadam not found"}, status=404)

    profile = {
        "mukkadam_id":       mukkadam.mukkadam_id,
        "mukkadam_name":     mukkadam.mukkadam_name,
        "mobile":            mukkadam.mobile_numbers,
        "state":             mukkadam.state,
        "district":          mukkadam.district,
        "taluka":            mukkadam.taluka,
        "village":           mukkadam.village,
        "crew_size":         mukkadam.crew_size,
        "max_crew_capacity": mukkadam.max_crew_capacity,
        "has_smartphone":    mukkadam.has_smartphone,
        "efficiency":        float(mukkadam.efficiency) if mukkadam.efficiency else 0,
        "is_active":         mukkadam.is_active,
        "joined_date":       None,
    }

    assignments_qs = ClusterMukkadamAssignment.objects.filter(
        mukkadam=mukkadam
    ).select_related("cluster").order_by("cluster__name")

    assignments = []
    earliest_join = None
    mukkadam_types_seen = set()

    for a in assignments_qs:
        mukkadam_types_seen.add(a.mukkadam_type)
        if earliest_join is None or (a.joined_date and a.joined_date < earliest_join):
            earliest_join = a.joined_date

        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        try:
            wpd_label = day_names[int(a.weekly_payment_day)] if a.weekly_payment_day is not None else ""
        except (ValueError, IndexError):
            wpd_label = str(a.weekly_payment_day) if a.weekly_payment_day is not None else ""

        assignments.append({
            "assignment_id":          a.id,
            "cluster_id":             a.cluster_id,
            "cluster_name":           a.cluster.name,
            "mukkadam_type":          a.mukkadam_type,
            "mukkadam_type_display":  _type_display(a.mukkadam_type),
            "weekly_amount":          float(a.weekly_amount),
            "weekly_payment_day":     a.weekly_payment_day,
            "weekly_payment_day_label": wpd_label,
            "transport_price":        float(a.transport_price),
            "advance_amount":         float(a.advance_amount),
            "updown_mode":            a.updown_mode or "",
            "updown_from_date":       str(a.updown_from_date or ""),
            "updown_to_date":         str(a.updown_to_date or ""),
            "is_active":              a.is_active,
            "joined_date":            str(a.joined_date) if a.joined_date else "",
            "total_weekly_paid":      float(a.total_weekly_payments or 0),
        })

    if "permanent" in mukkadam_types_seen and "updown" in mukkadam_types_seen:
        overall_type = "dual"
        overall_type_display = "Permanent + Updown (Dual)"
    elif "permanent" in mukkadam_types_seen:
        overall_type = "permanent"
        overall_type_display = "Permanent"
    elif "updown" in mukkadam_types_seen:
        overall_type = "updown"
        overall_type_display = "Updown"
    else:
        overall_type = "unknown"
        overall_type_display = "Unknown"

    profile["joined_date"]          = str(earliest_join) if earliest_join else None
    profile["overall_type"]         = overall_type
    profile["overall_type_display"] = overall_type_display

    # Weekly payments
    weekly_qs = MukkadamWeeklyPayment.objects.filter(
        assignment__mukkadam=mukkadam
    ).select_related("assignment__cluster").order_by("-payment_date")[:100]

    weekly_payments = [{
        "db_id":             w.id,
        "cluster_name":      w.assignment.cluster.name,
        "payment_date":      str(w.payment_date),
        "crew_size_on_date": w.crew_size_on_date,
        "amount":            float(w.amount),
        "mode":              w.mode,
        "notes":             w.notes or "",
    } for w in weekly_qs]

    # Transport events
    transport_qs = MukkadamLedgerEntry.objects.filter(
        mukkadam=mukkadam, payment_type="transport"
    ).select_related("cluster", "job").order_by("-payment_date")[:100]

    transport_events = []
    for e in transport_qs:
        parts = [p.strip() for p in (e.remark or "").split("|")]
        transport_events.append({
            "ledger_id":      e.id,
            "cluster_name":   e.cluster.name if e.cluster else "",
            "event_date":     str(e.payment_date) if e.payment_date else "",
            "direction":      parts[0] if len(parts) > 0 else "",
            "from_location":  parts[1] if len(parts) > 1 else "",
            "to_location":    parts[2] if len(parts) > 2 else "",
            "vehicle_type":   parts[3] if len(parts) > 3 else "",
            "transport_cost": float(e.amount),
            "job_id":         e.job.job_id if e.job else "",
        })

    # Settlements
    settlements_qs = MukkadamJobSettlement.objects.filter(
        mukkadam=mukkadam
    ).select_related("job__farmer", "cluster").order_by("-created_at")[:50]

    settlements = [{
        "settlement_id": s.id,
        "job_id":        s.job.job_id,
        "farmer_name":   s.job.farmer.farmer_name,
        "cluster_name":  s.cluster.name if s.cluster else "",
        "gross_amount":  float(s.gross_amount),
        "net_payable":   float(s.net_payable),
        "status":        s.status,
        "paid_at":       str(s.paid_at.date()) if s.paid_at else "",
        "mukkadam_type": "",
    } for s in settlements_qs]

    # Allocations
    alloc_qs = Allocation.objects.filter(
        mukkadam=mukkadam
    ).select_related(
        "cluster", "job_activity__activity",
        "job_activity__plot", "job_activity__job__farmer"
    ).order_by("-allocated_date")[:50]

    allocations = []
    for a in alloc_qs:
        ja     = a.job_activity
        plot   = ja.plot if ja else None
        job    = ja.job if ja else None
        farmer = job.farmer if job else None
        act    = ja.activity if ja else None

        if a.admin_override_area is not None:
            effective_area = float(a.admin_override_area)
        elif getattr(a, "use_actual_for_settlement", False) and a.actual_area_done:
            effective_area = float(a.actual_area_done)
        elif a.farmer_agreed and a.actual_area_done:
            effective_area = float(a.actual_area_done)
        else:
            effective_area = float(a.allocated_area or 0)

        allocations.append({
            "allocation_id":      a.id,
            "job_id":             job.job_id if job else "",
            "farmer_name":        farmer.farmer_name if farmer else "",
            "activity_name":      act.name if act else "",
            "plot_code":          plot.plotcode if plot else "",
            "allocated_date":     str(a.allocated_date),
            "effective_area":     effective_area,
            "gross_mukkadam_amt": round(effective_area * float(a.mukkadam_rate or 0), 2),
            "work_status":        a.work_status or "",
        })

    # Ledger
    ledger_qs = MukkadamLedgerEntry.objects.filter(
        mukkadam=mukkadam
    ).select_related("cluster", "job__farmer").order_by("-payment_date")[:200]

    ledger = [{
        "ledger_id":            e.id,
        "payment_type":         e.payment_type,
        "payment_type_display": e.get_payment_type_display(),
        "payment_date":         str(e.payment_date) if e.payment_date else "",
        "amount":               float(e.amount),
        "job_id":               e.job.job_id if e.job else "",
        "payment_status":       e.payment_status,
        "remark":               e.remark or "",
    } for e in ledger_qs]

    return Response({
        "mukkadam_id":     mukkadam.mukkadam_id,
        "profile":         profile,
        "assignments":     assignments,
        "weekly_payments": weekly_payments,
        "transport_events":transport_events,
        "settlements":     settlements,
        "allocations":     allocations,
        "ledger":          ledger,
        "summary": {
            "total_clusters":       len(assignments),
            "permanent_clusters":   sum(1 for a in assignments if a["mukkadam_type"] == "permanent"),
            "updown_clusters":      sum(1 for a in assignments if a["mukkadam_type"] == "updown"),
            "is_dual_type":         overall_type == "dual",
            "total_weekly_paid":    sum(w["amount"] for w in weekly_payments),
            "total_transport_cost": sum(t["transport_cost"] for t in transport_events),
            "total_net_settled":    sum(s["net_payable"] for s in settlements if s["status"] == "paid"),
        }
    })