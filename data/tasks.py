# allocation_app/tasks.py

from celery import shared_task
from .services import process_daily_payments
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    max_retries=3, 
    soft_time_limit=300 # 5 minutes max
)
def run_daily_payment_processing(self):
    """
    Celery task wrapper for payment processing.
    Includes retries in case of DB locks or transient issues.
    """
    try:
        logger.info("🚀 Starting Daily Payment Task")
        stats = process_daily_payments()
        return f"Completed: {stats}"
    except Exception as e:
        logger.error(f"Task Failed: {e}")
        # Retry in 5 minutes if it crashes completely
        raise self.retry(exc=e, countdown=60 * 5)