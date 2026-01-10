# allocation_app/utils.py

import requests
from django.core.cache import cache
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# API URLs
SUPPLY_API_URL = getattr(settings, 'SUPPLY_API_URL', 'http://localhost:8000')
FARMER_API_BASE = 'https://demand.bharatintelligence.ai/fir/api'
FARMER_TOKEN = 'Token e8fa8310c9af344ca22ec6bd23960d609b09c704'

# Cache timeouts
MUKKADAM_CACHE_TIMEOUT = getattr(settings, 'CACHE_MUKKADAM_TIMEOUT', 3600)
FARMER_CACHE_TIMEOUT = getattr(settings, 'CACHE_FARMER_TIMEOUT', 3600)
TRANSPORT_CACHE_TIMEOUT = getattr(settings, 'CACHE_TRANSPORT_TIMEOUT', 21600)


# ============================================
# SESSION WITH RETRY LOGIC
# ============================================

def get_requests_session():
    """
    Create a requests session with automatic retry logic
    """
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )

    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


# ============================================
# CACHING FUNCTIONS WITH RETRY
# ============================================

def get_mukkadam_cached(mukkadam_id: int) -> Optional[Dict]:
    """Get mukkadam details with caching and retry logic"""
    cache_key = f'mukkadam_{mukkadam_id}'
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Fetch from API with retry
    session = get_requests_session()
    
    try:
        response = session.get(
            f'{SUPPLY_API_URL}/api/mukkadam/{mukkadam_id}/',
            timeout=10  # ✅ Increased from 3 to 10 seconds
        )
        
        if response.status_code == 200:
            mukkadam_data = response.json()
            result = {
                'mukkadam_id': mukkadam_id,
                'mukkadam_name': mukkadam_data.get('mukkadam_name', 'Unknown'),
                'mobile_numbers': mukkadam_data.get('mobile_numbers', 'N/A'),
                'village': mukkadam_data.get('village', 'N/A'),
                'crew_size': mukkadam_data.get('crew_size', 'N/A'),
                'has_smartphone': mukkadam_data.get('has_smartphone', 'no'),
                'transport_mode': mukkadam_data.get('transport_mode', 'N/A')
            }
            
            # Cache for 1 hour
            cache.set(cache_key, result, MUKKADAM_CACHE_TIMEOUT)
            return result
        else:
            # Cache negative result for 5 minutes
            result = {
                'mukkadam_id': mukkadam_id,
                'mukkadam_name': f'Mukkadam #{mukkadam_id}',
                'mobile_numbers': 'N/A',
                'village': 'N/A',
                'crew_size': 'N/A',
                'has_smartphone': 'no',
                'transport_mode': 'N/A'
            }
            cache.set(cache_key, result, 300)  # 5 min
            return result
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching mukkadam {mukkadam_id} - using fallback")
        result = {
            'mukkadam_id': mukkadam_id,
            'mukkadam_name': f'Mukkadam #{mukkadam_id}',
            'mobile_numbers': 'N/A',
            'village': 'N/A',
            'crew_size': 'N/A',
            'has_smartphone': 'no',
            'transport_mode': 'N/A'
        }
        # Cache timeout fallback for 2 minutes
        cache.set(cache_key, result, 120)
        return result
        
    except Exception as e:
        print(f"❌ Error fetching mukkadam {mukkadam_id}: {str(e)}")
        return {
            'mukkadam_id': mukkadam_id,
            'mukkadam_name': f'Mukkadam #{mukkadam_id}',
            'mobile_numbers': 'N/A',
            'village': 'N/A',
            'crew_size': 'N/A',
            'has_smartphone': 'no',
            'transport_mode': 'N/A'
        }
    finally:
        session.close()


def get_farmer_cached(farmer_id: str) -> Optional[Dict]:
    """Get farmer details with caching and retry logic"""
    cache_key = f'farmer_{farmer_id}'
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Fetch from API with retry
    session = get_requests_session()
    
    try:
        response = session.get(
            f'{FARMER_API_BASE}/get_farmer_details/{farmer_id}/',
            headers={'Authorization': FARMER_TOKEN},
            timeout=15  # ✅ Increased from 3 to 15 seconds (external API is slower)
        )
        
        if response.status_code == 200:
            farmer_data = response.json()
            result = {
                'farmer_id': farmer_id,
                'farmer_name': farmer_data.get('farmer_name', 'Unknown'),
                'phone_number': farmer_data.get('phone_number', 'N/A'),
                'village': farmer_data.get('village', 'N/A'),
                'taluka': farmer_data.get('taluka', 'N/A'),
                'district': farmer_data.get('district', 'N/A'),
                'location': f"{farmer_data.get('village', 'N/A')}, {farmer_data.get('taluka', 'N/A')}, {farmer_data.get('district', 'N/A')}"
            }
            
            # Cache for 1 hour
            cache.set(cache_key, result, FARMER_CACHE_TIMEOUT)
            return result
        else:
            return None
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching farmer {farmer_id} - returning None")
        # Don't cache timeout failures for farmers (we want to retry next time)
        return None
        
    except Exception as e:
        print(f"❌ Error fetching farmer {farmer_id}: {str(e)}")
        return None
    finally:
        session.close()


def get_transport_provider_cached(provider_id: int) -> Optional[Dict]:
    """Get transport provider details with caching and retry logic"""
    cache_key = f'transport_provider_{provider_id}'
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Fetch from API with retry
    session = get_requests_session()
    
    try:
        response = session.get(
            f'{SUPPLY_API_URL}/api/transport-provider/{provider_id}/',
            timeout=10  # ✅ Increased from 3 to 10 seconds
        )
        
        if response.status_code == 200:
            provider_json = response.json()
            
            if provider_json.get('found'):
                provider_data = provider_json.get('provider', {})
                result = {
                    'id': provider_data.get('id'),
                    'name': provider_data.get('name', 'Unknown'),
                    'contact_number': provider_data.get('contact_number', 'N/A'),
                    'base_location': provider_data.get('base_location', 'N/A'),
                    'district': provider_data.get('district', 'N/A'),
                    'taluka': provider_data.get('taluka', 'N/A'),
                    'village': provider_data.get('village', 'N/A'),
                    'max_distance': provider_data.get('max_distance'),
                    'vehicle_type': provider_data.get('vehicle_type', 'N/A'),
                    'is_active': provider_data.get('is_active', True),
                    'capacity': provider_data.get('capacity'),
                }
                
                # Cache for 6 hours
                cache.set(cache_key, result, TRANSPORT_CACHE_TIMEOUT)
                return result
            else:
                result = {
                    'id': provider_id,
                    'name': f'Provider #{provider_id}',
                    'contact_number': 'N/A',
                    'base_location': 'N/A',
                    'vehicle_type': 'N/A',
                }
                cache.set(cache_key, result, 300)  # 5 min
                return result
                
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching transport provider {provider_id} - using fallback")
        result = {
            'id': provider_id,
            'name': f'Provider #{provider_id}',
            'contact_number': 'N/A',
            'base_location': 'N/A',
            'vehicle_type': 'N/A',
        }
        cache.set(cache_key, result, 120)  # Cache for 2 min
        return result
        
    except Exception as e:
        print(f"❌ Error fetching transport provider {provider_id}: {str(e)}")
        return {
            'id': provider_id,
            'name': f'Provider #{provider_id}',
            'contact_number': 'N/A',
            'base_location': 'N/A',
            'vehicle_type': 'N/A',
        }
    finally:
        session.close()


# ============================================
# ASYNC BATCH FETCHING WITH ADAPTIVE WORKERS
# ============================================

def batch_fetch_mukkadams(mukkadam_ids: List[int], max_workers: int = 5) -> Dict[int, Dict]:
    """
    Fetch multiple mukkadams in parallel
    ✅ Reduced max_workers from 10 to 5 to avoid overwhelming localhost API
    """
    print(f"🔄 Batch fetching {len(mukkadam_ids)} mukkadams with {max_workers} workers...")
    start_time = time.time()
    
    results = {}
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_id = {
            executor.submit(get_mukkadam_cached, mukkadam_id): mukkadam_id 
            for mukkadam_id in mukkadam_ids
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_id):
            mukkadam_id = future_to_id[future]
            try:
                result = future.result()
                if result:
                    results[mukkadam_id] = result
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Error fetching mukkadam {mukkadam_id}: {str(e)}")
                failed += 1
                results[mukkadam_id] = {
                    'mukkadam_id': mukkadam_id,
                    'mukkadam_name': f'Mukkadam #{mukkadam_id}',
                    'mobile_numbers': 'N/A',
                }
    
    elapsed = time.time() - start_time
    print(f"✅ Fetched {successful} mukkadams ({failed} failed) in {elapsed:.2f}s")
    
    return results


def batch_fetch_farmers(farmer_ids: List[str], max_workers: int = 5) -> Dict[str, Dict]:
    """
    Fetch multiple farmers in parallel
    ✅ Reduced max_workers from 10 to 5 to avoid overwhelming external API
    """
    print(f"🔄 Batch fetching {len(farmer_ids)} farmers with {max_workers} workers...")
    start_time = time.time()
    
    results = {}
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_id = {
            executor.submit(get_farmer_cached, farmer_id): farmer_id 
            for farmer_id in farmer_ids
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_id):
            farmer_id = future_to_id[future]
            try:
                result = future.result()
                if result:
                    results[farmer_id] = result
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Error fetching farmer {farmer_id}: {str(e)}")
                failed += 1
    
    elapsed = time.time() - start_time
    print(f"✅ Fetched {successful} farmers ({failed} failed/timeout) in {elapsed:.2f}s")
    
    return results


def batch_fetch_transport_providers(provider_ids: List[int], max_workers: int = 5) -> Dict[int, Dict]:
    """
    Fetch multiple transport providers in parallel
    ✅ Reduced max_workers from 10 to 5
    """
    print(f"🔄 Batch fetching {len(provider_ids)} transport providers with {max_workers} workers...")
    start_time = time.time()
    
    results = {}
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_id = {
            executor.submit(get_transport_provider_cached, provider_id): provider_id 
            for provider_id in provider_ids
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_id):
            provider_id = future_to_id[future]
            try:
                result = future.result()
                if result:
                    results[provider_id] = result
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Error fetching provider {provider_id}: {str(e)}")
                failed += 1
    
    elapsed = time.time() - start_time
    print(f"✅ Fetched {successful} providers ({failed} failed) in {elapsed:.2f}s")
    
    return results


# ============================================
# CACHE MANAGEMENT
# ============================================


# allocation_app/utils.py

# ... existing imports ...

# ============================================
# FETCH ALL MUKKADAMS & TRANSPORTERS VIA API
# ============================================

def get_all_mukkadams_from_api() -> List[Dict]:
    """
    Fetch ALL mukkadams from Supply API
    Returns list of mukkadam dictionaries
    """
    cache_key = 'all_mukkadams_list'
    
    # Try cache first (cache for 5 minutes since this list changes)
    cached_data = cache.get(cache_key)
    if cached_data:
        print(f"✅ Using cached mukkadams list ({len(cached_data)} mukkadams)")
        return cached_data
    
    session = get_requests_session()
    
    try:
        print("📡 Fetching all mukkadams from Supply API...")
        response = session.get(
            f'{SUPPLY_API_URL}/api/mukkadam/',
            timeout=30
        )
        
        if response.status_code == 200:
            mukkadams_data = response.json()
            
            # Handle both list and paginated response
            if isinstance(mukkadams_data, dict) and 'results' in mukkadams_data:
                # Paginated response
                mukkadams = mukkadams_data['results']
            elif isinstance(mukkadams_data, list):
                # Direct list
                mukkadams = mukkadams_data
            else:
                print(f"⚠️ Unexpected response format from mukkadam API")
                return []
            
            print(f"✅ Fetched {len(mukkadams)} mukkadams from API")
            
            # Cache for 5 minutes
            cache.set(cache_key, mukkadams, 300)
            return mukkadams
        else:
            print(f"❌ Failed to fetch mukkadams: {response.status_code}")
            return []
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching all mukkadams")
        return []
        
    except Exception as e:
        print(f"❌ Error fetching all mukkadams: {str(e)}")
        return []
    finally:
        session.close()


def get_all_transport_providers_from_api() -> List[Dict]:
    """
    Fetch ALL transport providers from Supply API
    Returns list of transport provider dictionaries
    """
    cache_key = 'all_transport_providers_list'
    
    # Try cache first (cache for 10 minutes since this list changes less frequently)
    cached_data = cache.get(cache_key)
    if cached_data:
        print(f"✅ Using cached transport providers list ({len(cached_data)} providers)")
        return cached_data
    
    session = get_requests_session()
    
    try:
        print("📡 Fetching all transport providers from Supply API...")
        response = session.get(
            f'{SUPPLY_API_URL}/api/transport-providers/',
            timeout=30
        )
        
        if response.status_code == 200:
            providers_data = response.json()
            
            # Handle both list and paginated response
            if isinstance(providers_data, dict) and 'results' in providers_data:
                # Paginated response
                providers = providers_data['results']
            elif isinstance(providers_data, list):
                # Direct list
                providers = providers_data
            else:
                print(f"⚠️ Unexpected response format from transport provider API")
                return []
            
            print(f"✅ Fetched {len(providers)} transport providers from API")
            
            # Cache for 10 minutes
            cache.set(cache_key, providers, 600)
            return providers
        else:
            print(f"❌ Failed to fetch transport providers: {response.status_code}")
            return []
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching all transport providers")
        return []
        
    except Exception as e:
        print(f"❌ Error fetching all transport providers: {str(e)}")
        return []
    finally:
        session.close()


def clear_mukkadam_list_cache():
    """Clear the cached list of all mukkadams"""
    cache.delete('all_mukkadams_list')


def clear_transport_provider_list_cache():
    """Clear the cached list of all transport providers"""
    cache.delete('all_transport_providers_list')

def clear_mukkadam_cache(mukkadam_id: int):
    """Clear cache for specific mukkadam (call when mukkadam is updated)"""
    cache_key = f'mukkadam_{mukkadam_id}'
    cache.delete(cache_key)


def clear_farmer_cache(farmer_id: str):
    """Clear cache for specific farmer"""
    cache_key = f'farmer_{farmer_id}'
    cache.delete(cache_key)


def clear_transport_provider_cache(provider_id: int):
    """Clear cache for specific transport provider"""
    cache_key = f'transport_provider_{provider_id}'
    cache.delete(cache_key)


def clear_all_allocation_caches():
    """Clear all allocation-related caches"""
    cache.clear()