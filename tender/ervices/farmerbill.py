from datetime import date
from decimal import Decimal
from django.db.models import Sum
from tender.models import Job, JobActivity, JobBooking, FarmerPayment


def get_farmer_billing_for_job(job_id: str) -> dict:
    """
    Calculate farmer billing state for a single job.
    Only activities where scheduled_date has passed are billable.
    """
    try:
        job = Job.objects.select_related('farmer', 'booking').get(job_id=job_id)
    except Job.DoesNotExist:
        return None

    try:
        booking = job.booking
    except JobBooking.DoesNotExist:
        booking = None

    today = date.today()
    activities = JobActivity.objects.filter(
        job=job
    ).select_related('activity', 'plot').order_by('scheduled_date')

    activity_rows = []
    total_billable = Decimal('0')
    all_activities_past = True

    for act in activities:
        is_past = act.scheduled_date and act.scheduled_date <= today
        if not is_past:
            all_activities_past = False

        billable_amount = Decimal('0')
        if is_past and act.allocated_area and act.rate_per_acre:
            billable_amount = (act.allocated_area * act.rate_per_acre).quantize(Decimal('0.01'))
            total_billable += billable_amount

        activity_rows.append({
            'activity_id': act.id,
            'activity_name': act.activity.name,
            'plot_code': act.plot.plot_code if act.plot else '—',
            'plot_name': act.plot.name if act.plot else '—',
            'scheduled_date': str(act.scheduled_date) if act.scheduled_date else None,
            'is_past': is_past,
            'allocated_area': float(act.allocated_area or 0),
            'total_area': float(act.total_area or 0),
            'rate_per_acre': float(act.rate_per_acre or 0),
            'billable_amount': float(billable_amount),
            'allocation_status': act.allocation_status,
        })

    # Payments received
    advance_paid = Decimal(str(booking.advance_paid)) if booking else Decimal('0')
    farmer_payments = FarmerPayment.objects.filter(
        booking=booking
    ).order_by('paid_at') if booking else []

    additional_paid = sum(Decimal(str(p.amount)) for p in farmer_payments)
    total_paid = advance_paid + additional_paid

    balance_due = total_billable - total_paid
    booking_total = Decimal(str(booking.total_amount)) if booking else Decimal('0')

    # Final check: all activities done, does total_billable match booking total_amount?
    final_gap = Decimal('0')
    show_final_collection = False
    if all_activities_past and booking:
        final_gap = booking_total - total_paid
        show_final_collection = final_gap > Decimal('0.01')

    payment_history = []
    if booking:
        if advance_paid > 0:
            payment_history.append({
                'type': 'advance',
                'date': str(booking.created_at.date()),
                'amount': float(advance_paid),
                'mode': 'Advance',
                'notes': 'Initial advance',
            })
        for p in farmer_payments:
            payment_history.append({
                'type': 'payment',
                'date': str(p.paid_at.date()),
                'amount': float(p.amount),
                'mode': p.mode,
                'notes': p.notes,
            })

    return {
        'job_id': job.job_id,
        'farmer_name': job.farmer.farmer_name,
        'farmer_id': job.farmer.farmer_id,
        'booking_id': booking.booking_id if booking else None,
        'booking_total': float(booking_total),
        'activities': activity_rows,
        'summary': {
            'total_billable_so_far': float(total_billable),
            'advance_paid': float(advance_paid),
            'additional_paid': float(additional_paid),
            'total_paid': float(total_paid),
            'balance_due': float(balance_due),
            'all_activities_past': all_activities_past,
            'final_gap': float(final_gap),
            'show_collect_button': balance_due > Decimal('0.01'),
            'show_final_collection': show_final_collection,
        },
        'payment_history': payment_history,
    }