# allocation_app/services.py

import logging
from django.utils import timezone
from django.db import transaction
from .models import Allocation, PaymentRequest, TransportPaymentRequest, ActivityLog
from django.conf import settings
import requests
# Setup logging (Hooks into Django's logging system)
logger = logging.getLogger(__name__)


class whatsappService:

    @classmethod
    def send_allocation_to_mukkadam(cls, allocation):
        """Notify Mukkadam about a new job allocation"""
        token = cls._get_token()
        if not token or not allocation.mukkadam_mobile: # Ensure mobile exists
            return False
        try:
            url = f"https://graph.facebook.com/v19.0/{settings.PHONE_NUMBER_ID}/messages"

            headers = {
                "Authorization": f"Bearer {settings.ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }

            payload = {
                "messaging_product": "whatsapp",
                "to": allocation.mukkadam_mobile,
                "type": "template",
                "template": {
                    "name": "job_allocated_template",
                    "language": {
                        "code": "en"
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": "+918047361465"
                                }
                            ]
                        }
                    ]
                }
            }

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise Exception(
                    f"WhatsApp API Error {response.status_code}: {response.text}"
                )

            return response.json()

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return False

    @classmethod
    def send_allocation_to_transporter(cls, allocation):
        """Notify Transporter about a new pickup/drop requirement"""
        # Only send if a transporter is actually assigned to this allocation
        if not hasattr(allocation, 'transporter') or not allocation.transporter:
            return False

        try:
            url = f"https://graph.facebook.com/v19.0/{settings.PHONE_NUMBER_ID}/messages"

            headers = {
                "Authorization": f"Bearer {settings.ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }

            payload = {
                "messaging_product": "whatsapp",
                "to": allocation.transporter.contact_number,
                "type": "template",
                "template": {
                    "name": "job_allocated_template",
                    "language": {
                        "code": "en"
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": "+918047361465"
                                }
                            ]
                        }
                    ]
                }
            }

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise Exception(
                    f"WhatsApp API Error {response.status_code}: {response.text}"
                )

            return True

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return False



def process_daily_payments():
    """
    Core logic to check past allocations and generate payments.
    Returns a summary dict.
    """
    today = timezone.now().date()
    logger.info(f"🔄 Starting automatic payment processing for date: {today}")

    # 1. Find eligible allocations (Past date, Active status)
    eligible_allocations = Allocation.objects.filter(
        work_date__lt=today,
        status__in=['allocated', 'in_progress']
    ).select_related('job_activity')

    stats = {
        'processed': 0,
        'mukkadam_created': 0,
        'transport_created': 0,
        'errors': 0
    }

    for allocation in eligible_allocations:
        try:
            with transaction.atomic():
                # --- A. Process Mukkadam Payment ---
                if not hasattr(allocation, 'payment_request'):
                    requested_amount = float(allocation.mukkadam_price) * float(allocation.allocated_area)

                    if requested_amount > 0:
                        pr = PaymentRequest.objects.create(
                            allocation=allocation,
                            mukkadam_id=allocation.mukkadam_id,
                            requested_amount=requested_amount,
                            status='pending',
                            notes="Auto-generated by system (Work date passed)"
                        )

                        ActivityLog.objects.create(
                            activity_type='payment_requested',
                            description=f"System auto-generated payment request for expired work date {allocation.work_date}",
                            payment_request=pr,
                            allocation=allocation,
                            job_id=allocation.job_activity.job_id,
                            mukkadam_id=allocation.mukkadam_id,
                            amount=requested_amount,
                            metadata={'auto_generated': True}
                        )
                        stats['mukkadam_created'] += 1

                # --- B. Process Transport Payment ---
                if (allocation.transport_type == 'provider' and
                    allocation.transport_provider_id and
                    not hasattr(allocation, 'transport_payment_request')):

                    transport_amount = float(allocation.transport_price or 0)

                    if transport_amount > 0:
                        tpr = TransportPaymentRequest.objects.create(
                            allocation=allocation,
                            transport_provider_id=allocation.transport_provider_id,
                            requested_amount=transport_amount,
                            status='pending',
                            notes="Auto-generated by system (Work date passed)"
                        )

                        ActivityLog.objects.create(
                            activity_type='transport_payment_requested',
                            description=f"System auto-generated transport payment for provider #{allocation.transport_provider_id}",
                            transport_payment_request=tpr,
                            allocation=allocation,
                            job_id=allocation.job_activity.job_id,
                            mukkadam_id=allocation.mukkadam_id,
                            transport_provider_id=allocation.transport_provider_id,
                            amount=transport_amount,
                            metadata={'auto_generated': True}
                        )
                        stats['transport_created'] += 1

                # --- C. Update Status ---
                if allocation.status != 'completed':
                    allocation.status = 'completed'
                    allocation.completed_at = timezone.now()
                    allocation.save()

                stats['processed'] += 1

        except Exception as e:
            # Catch errors for individual allocations so the whole batch doesn't fail
            logger.error(f"❌ Error processing allocation {allocation.id}: {str(e)}", exc_info=True)
            stats['errors'] += 1

    logger.info(f"✅ Payment processing complete: {stats}")
    return stats