# tender/notifications.py

import requests

NOTIFICATION_API = "http://localhost:8001/ap/push/send/"
# NOTIFICATION_API = "https://allocation.bharatintelligence.ai/ap/push/send/"

def notify_farmer(mobile_number, title, body, data=None):
    """Send push notification to farmer"""
    try:
        requests.post(NOTIFICATION_API, json={
            "mobile_number": str(mobile_number).replace('+91', '').replace('91', '')[-10:],
            "title": title,
            "body": body,
            "data": data or {}
        }, timeout=5)
    except Exception:
        pass  # Don't fail the main operation if notification fails

def notify_mukkadam(mobile_number, title, body, data=None):
    notify_farmer(mobile_number, title, body, data)