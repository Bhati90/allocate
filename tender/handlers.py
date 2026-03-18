# tender/handlers.py
from django.dispatch import receiver
from .signals import allocation_created,activity_cancelled, allocation_completed, allocation_deleted,job_cancelled,allocation_cancelled
from .task import push_to_sales_webhook, push_to_cancel_webhook
# tender/handlers.py
print("🔥 handlers.py imported")   # 👈 add this at the very top
import logging
...
@receiver(activity_cancelled)
def on_activity_cancelled(sender, payload, **kwargs):
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
    push_to_sales_webhook("completed", payload)

@receiver(allocation_cancelled)
def on_allocation_cancelled(sender, payload, **kwargs):
    push_to_cancel_webhook("allocation_cancelled", payload)  # 👈 cancel API


@receiver(allocation_deleted)
def on_allocation_deleted(sender, payload, **kwargs):
    # payload is pre-built in delete_allocation view
    # because allocation is already deleted by the time signal fires
    push_to_sales_webhook("deleted", payload)


@receiver(job_cancelled)
def on_job_cancelled(sender, payload, **kwargs):
    push_to_cancel_webhook("job_cancelled", payload)  # 👈 cancel API