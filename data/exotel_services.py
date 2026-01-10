# core/services/exotel_service.py
import requests
import logging
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger(__name__)

class ExotelService:
    BASE_URL = getattr(settings, 'EXOTEL_SERVICE_BASE_URL')
    
    def __init__(self):
        # We no longer set self.headers here because the token changes
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
                # Cache the token. Subtract 30 seconds from 'expires_in' for safety.
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
            "X-Client-Id": settings.EXOTEL_CLIENT_ID  # Required as per your doc
        }

    def make_call(self, from_number, to_number):
        """Connect two phone numbers using Bearer Token"""
        try:
            payload = {
                "from_number": from_number,
                "to_number": to_number,
                "side":"ALLOCATION"
            }
            
            # Dynamically get headers with valid token
            headers = self.get_headers()
            if not headers.get("Authorization"):
                return {'success': False, 'error': 'Auth failed'}

            response = requests.post(
                f"{self.BASE_URL}/api/calls/make/",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # If 401, clear cache and try once more (Optional retry logic)
            if response.status_code == 401:
                cache.delete("exotel_oauth_token")
                # ... optionally retry the call once ...

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'call_sid': data.get('call_sid') or data.get('response', {}).get('Sid'),
                    'status': data.get('status', 'queued')
                }
            
            return {'success': False, 'error': response.text}
            
        except Exception as e:
            logger.error(f"❌ Exotel error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
