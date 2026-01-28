# core/services/exotel_service.py
import requests
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

class ExotelService:
    BASE_URL = getattr(settings, 'EXOTEL_SERVICE_BASE_URL')
    WEBHOOK_URL = "https://call.bharatintelligence.ai/api/calls/recordings/process/"
    
    def __init__(self):
        pass

    def _get_access_token(self):
        """Fetches token from cache or requests a new one from OAuth API"""
        cache_key = "exotel_oauth_token"
        token = cache.get(cache_key)

        if not token:
            logger.info("Fetching new OAuth token...")
            payload = {
                "client_id": "kishan_localhost",
                "client_secret": "bi_M-n87nBu4a1QAs6ve7-o4FMrvm9hOMZ5npqVB-lhS-Q",
                "scope": "call:create"
            }
            headers = {"Content-Type": "application/json"}
            
            try:
                response = requests.post(
                    settings.EXOTEL_TOKEN_URL, 
                    json=payload, 
                    headers=headers, 
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                
                token = data.get("access_token")
                expires_in = data.get("expires_in", 300) - 30 
                cache.set(cache_key, token, timeout=expires_in)
                
            except Exception as e:
                logger.error(f"Failed to obtain OAuth token: {str(e)}")
                return None
        
        return token

    def get_headers(self):
        """Constructs headers with the Bearer token"""
        token = self._get_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Client-Id": settings.EXOTEL_CLIENT_ID
        }

# core/services/exotel_service.py

    def post_to_recording_webhook(self, call_sid):  # ✅ Renamed: removed underscore to make it public
        """
        ✅ POST call_sid to webhook for recording processing
        Called AFTER call ends (from ExotelWebhookView)
        Returns s3_key from response
        """
        try:
            webhook_payload = {
                "tech_side_name": "ALLOCATION",
                "call_sid": call_sid
            }
            
            logger.info(f"📤 Posting to recording webhook: {self.WEBHOOK_URL}")
            logger.info(f"   Payload: {webhook_payload}")
            
            webhook_response = requests.post(
                self.WEBHOOK_URL,
                json=webhook_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if webhook_response.status_code in [200, 201, 202]: 
                response_data = webhook_response.json()
                s3_key = response_data.get('s3_key')
                
                logger.info(f"✅ Recording webhook posted successfully for call_sid: {call_sid}")
                logger.info(f"   S3 Key received: {s3_key}")
                
                return {
                    'success': True,
                    's3_key': s3_key,
                    'data': response_data
                }
            else:
                logger.warning(f"⚠️ Recording webhook returned status {webhook_response.status_code}: {webhook_response.text}")
                return {
                    'success': False,
                    's3_key': None
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to post to recording webhook: {str(e)}", exc_info=True)
            return {
                'success': False,
                's3_key': None
            }

    def make_call(self, from_number, to_number):
        """Connect two phone numbers using Bearer Token"""
        try:
            payload = {
                "from_number": from_number,
                "to_number": to_number,
                "side": "ALLOCATION"
            }
            
            headers = self.get_headers()
            if not headers.get("Authorization"):
                return {'success': False, 'error': 'Auth failed'}

            logger.info(f"📞 Making call: {from_number} -> {to_number}")
            
            response = requests.post(
                f"{self.BASE_URL}/api/calls/make/",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 401:
                logger.warning("🔄 Got 401, clearing token cache and retrying...")
                cache.delete("exotel_oauth_token")
                headers = self.get_headers()
                
                response = requests.post(
                    f"{self.BASE_URL}/api/calls/make/",
                    headers=headers,
                    json=payload,
                    timeout=30
                )

            if response.status_code == 200:
                data = response.json()
                call_sid = data.get('call_sid') or data.get('response', {}).get('Sid')
                
                logger.info(f"✅ Call initiated successfully. SID: {call_sid}")
                
                # ✅ REMOVED: No longer post to webhook here
                # Webhook will be called when call ends via ExotelWebhookView
                
                return {
                    'success': True,
                    'call_sid': call_sid,
                    'status': data.get('status', 'queued'),
                }
            
            logger.error(f"❌ Call failed with status {response.status_code}: {response.text}")
            return {'success': False, 'error': response.text}
            
        except Exception as e:
            logger.error(f"❌ Exotel error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}