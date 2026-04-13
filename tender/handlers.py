# tender/handlers.py
from django.dispatch import receiver
from .signals import allocation_created,activity_cancelled, allocation_completed, allocation_deleted,job_cancelled,allocation_cancelled
from .task import push_to_sales_webhook, push_to_cancel_webhook
# tender/handlers.py
print("🔥 handlers.py imported")   # 👈 add this at the very top
import logging
from .nr import ops, err, ctx
...
@receiver(activity_cancelled)
def on_activity_cancelled(sender, payload, **kwargs):
    ops("handler_activity_cancelled",
        activity_id=str(payload.get('activity_id', '')),
        job_id=str(payload.get('job_id', '')),
        farmer_id=str(payload.get('farmer_id', '')),
        activity_name=str(payload.get('activity_name', '')),
        cancel_reason=str(payload.get('cancel_reason', ''))[:80],
        allocs_cancelled=str(payload.get('cancelled_allocations_count', 0)))
    push_to_cancel_webhook("activity_cancelled", payload)  

def _base_payload(allocation):
    """Fields common to all three events."""
    ja  = allocation.job_activity
    job = ja.job
    return {
        "allocation_id":   allocation.id,
        "booking_id":      job.booking.booking_id if job.booking else None,
        "api_activity_id": ja.api_activity_id or None,
        "activity_name":   ja.activity.name,
        "activity_status": ja.allocation_status,
        "allocated_area":  float(allocation.allocated_area),
        "allocated_date":  str(allocation.allocated_date),
        "mukkadam_id":     allocation.mukkadam.mukkadam_id,
        "mukkadam_name":   allocation.mukkadam.mukkadam_name,
        "farmer_rate":     float(allocation.farmer_rate),
        "mukkadam_rate":   float(allocation.mukkadam_rate),
        "job_id":          job.job_id,
        "farmer_id":       job.farmer.farmer_id,
        "farmer_name":     job.farmer.farmer_name,
        "plot_id":         ja.plot.id if ja.plot else None,
        "plot_code":       ja.plot.plot_code if ja.plot else None,
        "last_modified_by_id":   allocation.last_modified_by.id if allocation.last_modified_by else None,
        "last_modified_by_name": allocation.last_modified_by.get_full_name() or allocation.last_modified_by.username if allocation.last_modified_by else None,
        "last_modified_at":      str(allocation.last_modified_at) if allocation.last_modified_at else None,
        "created_by_id":         allocation.created_by.id if allocation.created_by else None,
        "created_by_name":       allocation.created_by.get_full_name() or allocation.created_by.username if allocation.created_by else None,
 
    }


@receiver(allocation_created)
def on_allocation_created(sender, allocation, **kwargs):
    payload = {
        **_base_payload(allocation),
        "allocated_at": str(allocation.created_at),
    }
    ops("handler_allocation_created",
        allocation_id=str(allocation.id),
        job_id=str(payload.get('job_id', '')),
        mukkadam_id=str(payload.get('mukkadam_id', '')),
        area=str(payload.get('allocated_area', '')),
        date=str(payload.get('allocated_date', '')))
    push_to_sales_webhook("allocated", payload)


@receiver(allocation_completed)
def on_allocation_completed(sender, allocation, **kwargs):
    payload = {
        **_base_payload(allocation),
        "allocated_at":    str(allocation.created_at),
        "completed_at":    str(allocation.updated_at),
        "actual_area_done": float(allocation.actual_area_done) if allocation.actual_area_done else None,
        "actual_crew_size": allocation.actual_crew_size,
        "work_status":      allocation.work_status,
    }
    ops("handler_allocation_completed",
        allocation_id=str(allocation.id),
        job_id=str(payload.get('job_id', '')),
        mukkadam_id=str(payload.get('mukkadam_id', '')),
        actual_area=str(payload.get('actual_area_done', '')),
        work_status=str(allocation.work_status))
    push_to_sales_webhook("completed", payload)

@receiver(allocation_cancelled)
def on_allocation_cancelled(sender, payload, **kwargs):
    ops("handler_allocation_cancelled",
        allocation_id=str(payload.get('allocation_id', '')),
        job_id=str(payload.get('job_id', '')),
        mukkadam_id=str(payload.get('mukkadam_id', '')),
        area=str(payload.get('allocated_area', '')),
        cancel_reason=str(payload.get('cancel_reason', ''))[:80])
    push_to_cancel_webhook("allocation_cancelled", payload)  # 👈 cancel API


@receiver(allocation_deleted)
def on_allocation_deleted(sender, payload, **kwargs):
    ops("handler_allocation_deleted",
        allocation_id=str(payload.get('allocation_id', '')),
        job_id=str(payload.get('job_id', '')),
        mukkadam_id=str(payload.get('mukkadam_id', '')),
        area=str(payload.get('allocated_area', '')),
        date=str(payload.get('allocated_date', '')),
        deleted_by=str(payload.get('deleted_by_name', '')))
    # payload is pre-built in delete_allocation view
    # because allocation is already deleted by the time signal fires
    push_to_sales_webhook("deleted", payload)


@receiver(job_cancelled)
def on_job_cancelled(sender, payload, **kwargs):
    ops("handler_job_cancelled",
        job_id=str(payload.get('job_id', '')),
        farmer_id=str(payload.get('farmer_id', '')),
        farmer_name=str(payload.get('farmer_name', '')),
        cancel_reason=str(payload.get('cancel_reason', ''))[:80],
        activities_cancelled=str(payload.get('cancelled_activities', '')),
        allocs_cancelled=str(payload.get('cancelled_allocations_count', 0)),
        cancel_allocs=str(payload.get('allocations_cancelled', False)))
    push_to_cancel_webhook("job_cancelled", payload)  # 👈 cancel API