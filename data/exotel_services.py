# core/services/exotel_service.py
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class ExotelService:
    BASE_URL = getattr(settings, 'EXOTEL_SERVICE_BASE_URL', "https://b5497a2f817f.ngrok-free.app/api/calls")
    
    def __init__(self):
        self.api_token = settings.EXOTEL_API_TOKEN
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_token}"
        }

    def make_call(self, from_number, to_number):
        """Connect two phone numbers"""
        try:
            payload = {
                "from_number": from_number,
                "to_number": to_number
            }
            
            logger.info(f"📞 Calling: {from_number} → {to_number}")
            
            response = requests.post(
                f"{self.BASE_URL}/make_call/",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'call_sid': data.get('call_sid') or data.get('response', {}).get('Sid'),
                    'status': data.get('status', 'queued')
                }
            
            logger.error(f"❌ Call failed: {response.text}")
            return {'success': False, 'error': response.text}
            
        except Exception as e:
            logger.error(f"❌ Exotel error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def get_call_status(self, call_sid):
        """Check call status"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/get_call_status/{call_sid}/",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return {'status': 'unknown'}
            
        except Exception as e:
            logger.error(f"Error fetching status: {str(e)}")
            return {'status': 'error'}