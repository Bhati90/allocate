import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_headers():
    token = getattr(settings, 'SALES_WEBHOOK_TOKEN', None)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Token {token}'
    return headers


def push_to_sales_webhook(event: str, payload: dict):
    url = getattr(settings, 'SALES_WEBHOOK_URL', None)
    if not url:
        logger.warning("[SALES] SALES_WEBHOOK_URL not set in settings")
        return
    try:
        res = requests.post(url, json={"event": event, **payload}, headers=_get_headers(), timeout=10)
        res.raise_for_status()
        logger.info(f"[SALES] '{event}' sent OK — allocation_id: {payload.get('allocation_id')}")
    except Exception as e:
        logger.error(f"[SALES] '{event}' failed: {e} | payload: {payload}")


def push_to_cancel_webhook(event: str, payload: dict):
    url = getattr(settings, 'SALES_CANCEL_WEBHOOK_URL', None)
    if not url:
        logger.warning("[SALES] SALES_CANCEL_WEBHOOK_URL not set in settings")
        return
    try:
        res = requests.post(url, json={"event": event, **payload}, headers=_get_headers(), timeout=10)
        res.raise_for_status()
        logger.info(f"[SALES CANCEL] '{event}' sent OK — id: {payload.get('allocation_id') or payload.get('job_id')}")
    except Exception as e:
        logger.error(f"[SALES CANCEL] '{event}' failed: {e} | payload: {payload}")