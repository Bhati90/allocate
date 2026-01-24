from datetime import datetime, timedelta

# supply/services/data_loader.py
import requests
from datetime import datetime, date
from .models import Allocation
from .views import get_all_mukkadams_from_supply, get_supply_users_mapping
from datetime import datetime, timedelta, date
import requests
from django.conf import settings

# allocation/services/recommendation_engine.py

def normalize_activity_name(activity_name):
    """
    Convert display name to rate_card key format
    'Paper Wrapping' -> 'paperWrapping'
    'First Dipping' -> 'firstDipping'
    'Bunch Tying' -> 'bunchTying'
    """
    if not activity_name:
        return ''
    
    # Clean and split
    words = activity_name.strip().split()
    if not words:
        return ''
    
    # camelCase: first word lowercase, rest capitalized
    result = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    return result

from math import radians, sin, cos, sqrt, atan2

def geocode_location(village, taluka, district):
    """
    Geocode location using village/taluka/district
    Returns approximate center coordinates
    
    NOTE: This uses approximate coordinates. For production, integrate Google Maps Geocoding API
    """
    # For now, return district-level approximate coordinates
    # You can replace this with actual geocoding API call
    
    district_coords = {
        # 'nashik': (19.9975, 73.7898),
        # 'pune': (18.5204, 73.8567),
        # 'mumbai': (19.0760, 72.8777),
        # 'satara': (17.6805, 74.0183),
        # 'sangli': (16.8524, 74.5815),
        # 'ahmednagar': (19.0948, 74.7489),
        # 'solapur': (17.6599, 75.9064),
        # 'kolhapur': (16.7050, 74.2433),
    }
    
    district_lower = (district or '').lower().strip()
    
    if district_lower in district_coords:
        return district_coords[district_lower]
    
    # Default to Nashik if unknown
    return (19.9975, 73.7898)


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    Returns distance in kilometers
    """
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    # Earth radius in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return round(distance, 2)


def calculate_transport_cost(mukkadam, job_lat, job_lon):
    """
    Calculate transport cost based on distance and transport mode
    """
    result = {
        'distance_km': None,
        'transport_mode': None,
        'one_way_distance': None,
        'round_trip_distance': None,
        'rate_per_km': None,
        'free_km': 0,
        'billable_km': None,
        'estimated_cost': None,
        'calculation_breakdown': 'N/A',
        'station_location': None
    }
    
    # Get mukkadam location
    muk_lat = mukkadam.get('current_latitude')
    muk_lon = mukkadam.get('current_longitude')
    
    # ✅ CONVERT TO FLOAT IF STRING
    if muk_lat:
        try:
            muk_lat = float(muk_lat)
        except (ValueError, TypeError):
            muk_lat = None
    
    if muk_lon:
        try:
            muk_lon = float(muk_lon)
        except (ValueError, TypeError):
            muk_lon = None
    
    # If no current location, geocode from village/taluka/district
    if not muk_lat or not muk_lon:
        muk_lat, muk_lon = geocode_location(
            mukkadam.get('village'),
            mukkadam.get('taluka'),
            mukkadam.get('district')
        )
    
    # Calculate distance
    one_way_km = calculate_distance_km(muk_lat, muk_lon, job_lat, job_lon)
    
# ✅ FIXED LINE: Only stop if calculation failed (None)
    if one_way_km is None:
        return result
    
    # ... rest of the function stays the same
    
    round_trip_km = one_way_km * 2
    
    result['one_way_distance'] = one_way_km
    result['round_trip_distance'] = round_trip_km
    result['distance_km'] = one_way_km
    
    # Get transport details
    transport_mode = (mukkadam.get('transport_mode') or 'no_vehicle').lower()
    transport_charges = mukkadam.get('transport_charges') or {}
    
    result['transport_mode'] = transport_mode
    result['station_location'] = transport_charges.get('currentlyStationedAt')
    
    # Calculate cost based on mode
    if transport_mode == 'bike':
        # Bike with free km allowance
        free_km_str = transport_charges.get('bikeBeyondKm', '0').strip()
        free_km = float(free_km_str) if free_km_str and free_km_str.replace('.', '').isdigit() else 0
        
        rate_str = transport_charges.get('bikeChargePerBike', '0').strip()
        rate = float(rate_str) if rate_str and rate_str.replace('.', '').isdigit() else 0
        
        billable_km = max(0, round_trip_km - free_km)
        cost = billable_km * rate
        
        result['free_km'] = free_km
        result['rate_per_km'] = rate
        result['billable_km'] = billable_km
        # result['estimated_cost'] = round(cost, 2)
        result['estimated_cost'] = 100.0
        
        if free_km > 0:
            result['calculation_breakdown'] = f"{one_way_km}km × 2 (round-trip) = {round_trip_km}km | Free: {free_km}km | Billable: {billable_km}km × ₹{rate}/km = ₹{cost:.0f}"
        else:
            result['calculation_breakdown'] = f"{one_way_km}km × 2 (round-trip) = {round_trip_km}km × ₹{rate}/km = ₹{cost:.0f}"
    
    elif transport_mode == 'pickup':
        # Pickup with per-km rate
        pickup_details = transport_charges.get('pickupChargeDetails', '').strip()
        
        # Parse "20/km" format
        rate = 20.0  # Default
        if '/km' in pickup_details:
            rate_str = pickup_details.split('/')[0].strip()
            if rate_str.replace('.', '').isdigit():
                rate = float(rate_str)
        
        cost = round_trip_km * rate
        
        result['rate_per_km'] = rate
        result['billable_km'] = round_trip_km
        # result['estimated_cost'] = round(cost, 2)
        result['estimated_cost'] = 100.0
        result['calculation_breakdown'] = f"{one_way_km}km × 2 (round-trip) = {round_trip_km}km × ₹{rate}/km = ₹{cost:.0f}"
    
    else:  # no_vehicle or other
        # Default rate: ₹10/km
        rate = 10.0
        cost = round_trip_km * rate
        
        result['rate_per_km'] = rate
        result['billable_km'] = round_trip_km
        # result['estimated_cost'] = round(cost, 2)
        result['estimated_cost'] = 100.0
        result['calculation_breakdown'] = f"{one_way_km}km × 2 (round-trip) = {round_trip_km}km × ₹{rate}/km (default) = ₹{cost:.0f}"
    
    return result
# def get_mukkadam_scorecard(mukkadam_id):
#     """
#     Fetch mukkadam scorecard details from allocation API
#     Returns breakdown with by_activity pricing data
#     """
#     ALLOCATION_API_BASE = getattr(settings, 'ALLOCATION_API_BASE', 'http://localhost:8001')
    
#     try:
#         response = requests.get(
#             f'{ALLOCATION_API_BASE}/ap/mukkadam-scorecard-details/{mukkadam_id}/',
#             timeout=30
#         )
        
#         if response.status_code == 200:
#             return response.json()
#         else:
#             return None
            
#     except Exception as e:
#         print(f"Error fetching scorecard for mukkadam {mukkadam_id}: {e}")
#         return None


def calculate_price_metrics(mukkadam, target_activity):
    """
    Calculate pricing metrics for a mukkadam and activity
    ✅ NOW USES job_summary INSTEAD OF scorecard API
    """
    result = {
        'asking_price': None,
        'is_base_price': False,
        'historical_price_per_acre': None,
        'historical_jobs_count': 0,
        'price_display': 'N/A'
    }
    
    # ========================================
    # 1. GET ASKING PRICE FROM RATE CARD
    # ========================================
    rate_card = mukkadam.get('rate_card', {})
    
    if rate_card:
        normalized_activity = normalize_activity_name(target_activity)
        asking_price_str = rate_card.get(normalized_activity, '').strip()
        
        if asking_price_str and asking_price_str.replace('.', '').isdigit():
            result['asking_price'] = float(asking_price_str)
            result['is_base_price'] = False
        else:
            base_price_str = rate_card.get('other', '').strip()
            if base_price_str and base_price_str.replace('.', '').isdigit():
                result['asking_price'] = float(base_price_str)
                result['is_base_price'] = True
    
    # ========================================
    # 2. GET HISTORICAL PRICE FROM job_summary
    # ========================================
    job_summary = mukkadam.get('job_summary', [])
    target_lower = target_activity.lower().strip()
    
    matching_jobs = []
    
    for job in job_summary:
        activity = job.get('activity', {})
        activity_name = (activity.get('activity_name') or '').lower().strip()
        
        if activity_name == target_lower:
            payment = job.get('payment', {})
            price_per_acre = payment.get('mukkadam_price_per_acre')
            
            if price_per_acre and price_per_acre > 0:
                matching_jobs.append(price_per_acre)
    
    if matching_jobs:
        # Use average of historical prices
        avg_price = sum(matching_jobs) / len(matching_jobs)
        result['historical_price_per_acre'] = round(avg_price, 2)
        result['historical_jobs_count'] = len(matching_jobs)
    
    # ========================================
    # 3. FORMAT DISPLAY STRING
    # ========================================
    parts = []
    
    if result['asking_price']:
        if result['is_base_price']:
            parts.append(f"₹{result['asking_price']:.0f} (Base)")
        else:
            parts.append(f"₹{result['asking_price']:.0f} (Asked)")
    
    if result['historical_price_per_acre']:
        parts.append(f"₹{result['historical_price_per_acre']:.0f}/acre (Hist)")
    
    if parts:
        result['price_display'] = ' | '.join(parts)
    
    return result


def calculate_proximity_score(muk_village, muk_taluka, muk_district, target_village, target_taluka, target_district):
    """
    Calculate proximity score based on administrative hierarchy
    
    Returns:
        - 100: Same village (0-5 km)
        - 50: Same taluka (5-25 km)
        - 20: Same district (25-60 km)
        - 0: Different district (60+ km)
    """
    
    # Normalize strings (lowercase, strip)
    def normalize(s):
        return (s or '').lower().strip()
    
    muk_v = normalize(muk_village)
    muk_t = normalize(muk_taluka)
    muk_d = normalize(muk_district)
    
    target_v = normalize(target_village)
    target_t = normalize(target_taluka)
    target_d = normalize(target_district)
    
    # Level 1: Same Village (Most precise)
    if muk_v and target_v and muk_v == target_v:
        return 100
    
    # Level 2: Same Taluka (Nearby)
    if muk_t and target_t and muk_t == target_t:
        return 50
    
    # Level 3: Same District (Medium distance)
    if muk_d and target_d and muk_d == target_d:
        return 20
    
    # Level 4: Different District (Far)
    return 0


def parse_location_string(location_str):
    """
    Parse location string into components
    
    Example: "pachore vani, niphad, nashik" -> {village: "pachore vani", taluka: "niphad", district: "nashik"}
    """
    parts = [p.strip() for p in location_str.split(',')]
    
    if len(parts) >= 3:
        return {
            'village': parts[0],
            'taluka': parts[1],
            'district': parts[2]
        }
    elif len(parts) == 2:
        return {
            'village': '',
            'taluka': parts[0],
            'district': parts[1]
        }
    elif len(parts) == 1:
        return {
            'village': '',
            'taluka': '',
            'district': parts[0]
        }
    
    return {'village': '', 'taluka': '', 'district': ''}

# allocation/services/data_loader.py

def fetch_enriched_mukkadam_data():
    """
    Fetches Mukkadams + Allocations and returns the fully enriched list 
    ✅ FILTERS: Only returns Mukkadams where is_permanent is True
    ✅ INCLUDES: rate_card and scorecard_data for pricing
    """
    
    # 1. Fetch ALL Mukkadams (includes rate_card)
    raw_mukkadams = get_all_mukkadams_from_supply()
    if not raw_mukkadams:
        return []
    
    # =========================================================
    # ✅ FILTER: KEEP ONLY PERMANENT MUKKADAMS
    # =========================================================
    all_mukkadams = [
        m for m in raw_mukkadams 
        if m.get('is_permanent') is True
    ]
    
    print(f"✅ Loaded {len(all_mukkadams)} Permanent Mukkadams (Filtered from {len(raw_mukkadams)} total)")
    
    # If no permanent mukkadams found, return empty
    if not all_mukkadams:
        return []

    mukkadam_ids = [m['id'] for m in all_mukkadams]
    
    # 2. Fetch Allocations
    ALLOCATION_API_BASE = getattr(settings, 'ALLOCATION_API_BASE', 'http://localhost:8001')
    # ALLOCATION_API_BASE = 'https://allocation.bharatintelligence.ai'
    
    try:
        allocations_response = requests.get(
            f'{ALLOCATION_API_BASE}/ap/allocations/by-mobile/main/',
            timeout=60
        )
        if allocations_response.status_code == 200:
            all_allocations = allocations_response.json().get('allocations', [])
        else:
            all_allocations = []
    except Exception as e:
        print(f"Error fetching allocations: {e}")
        all_allocations = []

    # =========================================================
    # 3. FETCH SCORECARD DATA FOR EACH MUKKADAM


    # 4. Calculate Stats
    mukkadam_stats = {}
    
    for alloc_data in all_allocations:
        mid = alloc_data['mukkadam']['mukkadam_id']
        
        # Optimization: Skip stats for mukkadams we already filtered out
        if mid not in mukkadam_ids:
            continue
        
        if mid not in mukkadam_stats:
            mukkadam_stats[mid] = {
                'allocations': [],
                'total_earnings': 0,
                'total_man_days_worked': 0,
                'activity_counts': {},
                'farmer_history': set(),
                'location_dates': []
            }
        
        stats = mukkadam_stats[mid]
        stats['allocations'].append(alloc_data)
        
        crew = alloc_data.get('crew_size') or 0
        stats['total_man_days_worked'] += crew
        
        payment = alloc_data.get('payment') or {}
        stats['total_earnings'] += payment.get('mukkadam_total_payment', 0)
        
        activity = alloc_data.get('activity') or {}
        activity_name = (activity.get('activity_name') or '').lower()
        if activity_name:
            stats['activity_counts'][activity_name] = stats['activity_counts'].get(activity_name, 0) + 1
        
        farmer = alloc_data.get('farmer') or {}
        farmer_id = farmer.get('farmer_id')
        if farmer_id:
            stats['farmer_history'].add(str(farmer_id))
        
        work_date = alloc_data.get('work_date')
        location = farmer.get('location', '')
        if work_date and location:
            stats['location_dates'].append({
                'date': work_date,
                'location': location.lower()
            })

    # 5. Build Final List
    final_list = []

    for mukkadam in all_mukkadams:
        mid = mukkadam['id']
        stats = mukkadam_stats.get(mid, {
            'allocations': [],
            'total_earnings': 0,
            'total_man_days_worked': 0,
            'activity_counts': {},
            'farmer_history': set(),
            'location_dates': []
        })
        
        # Availability Parsing
        start_date = mukkadam.get('start_date')
        end_date = mukkadam.get('end_date')
        all_periods = []
        
        if start_date:
            try:
                s = datetime.strptime(start_date, '%Y-%m-%d').date()
                e = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
                if e is None or e >= s:
                    all_periods.append({
                        'start_date': start_date,
                        'end_date': end_date,
                        'type': 'main'
                    })
            except: pass
        
        for team in mukkadam.get('team_availabilities', []):
            if team.get('status') == 'Available':
                try:
                    ts = datetime.strptime(team.get('startDate'), '%Y-%m-%d').date()
                    te = datetime.strptime(team.get('endDate'), '%Y-%m-%d').date() if team.get('endDate') else None
                    if te is None or te >= ts:
                        all_periods.append({
                            'start_date': team.get('startDate'),
                            'end_date': team.get('endDate'),
                            'type': 'team',
                            'team_name': team.get('teamName', 'Unknown')
                        })
                except: pass

        obj = {
            'id': mid,
            'mukkadam_name': mukkadam.get('mukkadam_name'),
            'mobile_numbers': mukkadam.get('mobile_numbers'),
            'village': mukkadam.get('village'),
            'taluka': mukkadam.get('taluka'),
            'district': mukkadam.get('district'),
            'crew_size': int(mukkadam.get('crew_size') or 0),
            'is_permanent': True,
            'created_at': mukkadam.get('created_at'),
            
            # ✅ ADD PRICING DATA
            'rate_card': mukkadam.get('rate_card', {}),
            # ✅ ADD PRICING DATA

    
    # ✅ ADD TRANSPORT DATA (MISSING!)
    'current_latitude': mukkadam.get('current_latitude'),
    'current_longitude': mukkadam.get('current_longitude'),
    'transport_mode': mukkadam.get('transport_mode'),
    'transport_charges': mukkadam.get('transport_charges', {}),
    
            
            'availability_periods': all_periods,
            
            'job_summary': stats['allocations'],
            'total_allocations': len(stats['allocations']),
            'total_earnings': stats['total_earnings'],
            'total_man_days_worked': stats['total_man_days_worked'],
            
            'activity_counts': stats['activity_counts'],
            'farmer_history': list(stats['farmer_history']),
            'location_dates': stats['location_dates']
        }
        
        final_list.append(obj)

    return final_list

from datetime import datetime, timedelta

def is_available_on_date(mukkadam, target_date):
    """
    Check if mukkadam is actually available on the target date
    
    Args:
        mukkadam: Mukkadam dict with 'availability_periods'
        target_date: date object to check
        
    Returns:
        bool: True if available on that date
    """
    availability_periods = mukkadam.get('availability_periods', [])
    
    if not availability_periods:
        return False
    
    for period in availability_periods:
        try:
            start_str = period.get('start_date')
            end_str = period.get('end_date')
            
            if not start_str:
                continue
            
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            
            # Handle open-ended availability (no end date)
            if end_str:
                end = datetime.strptime(end_str, '%Y-%m-%d').date()
            else:
                end = date.max
            
            # Check if target_date falls within this period
            if start <= target_date <= end:
                return True
                
        except Exception as e:
            print(f"Error parsing availability period: {e}")
            continue
    
    return False


def process_mukkadam_recommendations(all_mukkadams, target_req):
    """
    Returns categorized recommendations + ALL mukkadams
    ✅ NOW INCLUDES PRICING METRICS FOR TARGET ACTIVITY
    """
    
    buckets = {
        "all": [],
        "overall_best": [],
        "available_on_date": [],
        "nearby_logistics": [],
        "farmer_history": [],
        "activity_experts": [],
        "high_volume": [],
        "new_local_recruits": [],
        "cost_effective": [],  # ✅ ADD THIS
        "transport_cost": []  # ✅ NEW BUCKET
    }
    
    if not all_mukkadams:
        return buckets

    target_date = target_req['date']
    target_date_str = target_date.strftime('%Y-%m-%d')
    target_farmer_id = str(target_req.get('farmer_id') or '')
    target_activity = (target_req.get('activity_name') or '').lower()
    target_loc_str = (target_req.get('location_str') or '').lower()
    # ✅ NEW: Get job coordinates
    job_lat = target_req.get('job_latitude')
    job_lon = target_req.get('job_longitude')
    
    target_location = parse_location_string(target_loc_str)
    
    nearby_start = target_date - timedelta(days=3)
    nearby_end = target_date + timedelta(days=3)

    for muk in all_mukkadams:
        mid = muk['id']
        
        # ========================================
        # 0. CHECK IF BLOCKED
        # ========================================
        is_blocked = False
        for job in (muk.get('job_summary') or []):
            job_date = job.get('work_date')
            job_status = job.get('status', '')
            
            if job_date == target_date_str and job_status in ['allocated', 'in_progress']:
                is_blocked = True
                break
        
        muk['is_blocked'] = is_blocked
        
        # ========================================
        # 0.5. CALCULATE PRICING METRICS
        # ========================================
        price_metrics = calculate_price_metrics(muk, target_activity)
        muk['price_metrics'] = price_metrics

        # ✅ ADD THIS: Add to cost_effective bucket if has pricing
        if price_metrics['asking_price'] or price_metrics['historical_price_per_acre']:
            buckets["cost_effective"].append(muk)

# ========================================
        # 0.6. CALCULATE TRANSPORT COST
        # ========================================
        transport_cost = None
        if job_lat and job_lon:
            transport_cost = calculate_transport_cost(muk, job_lat, job_lon)
            muk['transport_cost'] = transport_cost
            # muk['transport_cost'] = 0
            
            # ✅ This works for 0, because 0 is not None. 
            # If it was "if transport_cost['estimated_cost']:" it would fail for 0.
            if transport_cost['estimated_cost'] is not None:
                buckets["transport_cost"].append(muk)
        
        # ========================================
        # 1. AVAILABILITY CHECK
        # ========================================
        is_available = is_available_on_date(muk, target_date)
        
        if is_available:
            buckets["available_on_date"].append(muk)
        
        # ========================================
        # 2. LOCATION LOGISTICS
        # ========================================
        home_proximity_score = calculate_proximity_score(
            muk.get('village'),
            muk.get('taluka'),
            muk.get('district'),
            target_location['village'],
            target_location['taluka'],
            target_location['district']
        )
        
        work_history_proximity_score = 0
        best_work_location = None
        
        for loc_date in muk.get('location_dates', []):
            try:
                job_date = datetime.strptime(loc_date['date'], '%Y-%m-%d').date()
                
                if nearby_start <= job_date <= nearby_end:
                    job_loc_str = loc_date['location']
                    job_location = parse_location_string(job_loc_str)
                    
                    proximity = calculate_proximity_score(
                        job_location['village'],
                        job_location['taluka'],
                        job_location['district'],
                        target_location['village'],
                        target_location['taluka'],
                        target_location['district']
                    )
                    
                    if proximity > work_history_proximity_score:
                        work_history_proximity_score = proximity
                        best_work_location = job_loc_str
                        
            except:
                continue
        
        max_proximity_score = max(home_proximity_score, work_history_proximity_score)
        
        muk['home_proximity_score'] = home_proximity_score
        muk['work_proximity_score'] = work_history_proximity_score
        muk['best_work_location'] = best_work_location
        
        if max_proximity_score > 0:
            buckets["nearby_logistics"].append(muk)
        
        # ========================================
        # 3. FARMER HISTORY
        # ========================================
        worked_with_farmer = target_farmer_id in muk.get('farmer_history', [])
        
        if worked_with_farmer:
            buckets["farmer_history"].append(muk)
        
        # ========================================
        # 4. ACTIVITY EXPERTISE
        # ========================================
        activity_counts = muk.get('activity_counts', {})
        activity_count = activity_counts.get(target_activity, 0)
        
        muk['temp_activity_count'] = activity_count
        
        if activity_count > 0:
            buckets["activity_experts"].append(muk)
        
        # ========================================
        # 5. HIGH VOLUME
        # ========================================
        total_jobs = muk.get('total_allocations', 0)
        muk['temp_total_jobs'] = total_jobs
        
        if total_jobs > 5:
            buckets["high_volume"].append(muk)
        
        # ========================================
        # 6. NEW LOCAL RECRUIT
        # ========================================
        created_at_str = muk.get('created_at')
        is_new = False
        
        if created_at_str:
            try:
                c_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).date()
                days_old = (date.today() - c_date).days
                is_new = days_old < 90
            except:
                pass
        
        is_local = home_proximity_score >= 20
        
        if is_new and is_local:
            buckets["new_local_recruits"].append(muk)


        # buckets["cost_effective"].sort(
        #     key=lambda x: (
        #         x.get('price_metrics', {}).get('asking_price') or 
        #         x.get('price_metrics', {}).get('historical_price_per_acre') or 
        #         float('inf')
        #     )
        # )
        
        # ========================================
        # 7. OVERALL SCORING
        # ========================================
        score = 0
        reasons = []

        # ✅ ADD TRANSPORT COST TO REASONS
        if transport_cost and transport_cost['estimated_cost'] is not None:
            reasons.append(f"🚗 Transport: ₹{transport_cost['estimated_cost']:.0f} ({transport_cost['distance_km']}km)")
        
        
        if is_blocked:
            score -= 50
            reasons.append("⛔ Already Booked")
        
        if is_available:
            score += 100
            reasons.append("✅ Available")
        else:
            score -= 30
            reasons.append("⚠️ Not Available")
        
        # Home location proximity
        if home_proximity_score == 100:
            score += 60
            reasons.append(f"🏠 From {muk.get('village')} (Same Village)")
        elif home_proximity_score == 50:
            score += 40
            reasons.append(f"🏠 From {muk.get('taluka')} (Same Taluka)")
        elif home_proximity_score == 20:
            score += 15
            reasons.append(f"🏠 From {muk.get('district')} (Same District)")
        
        # Work history proximity
        if work_history_proximity_score == 100:
            score += 50
            reasons.append("🚚 Worked Here Recently")
        elif work_history_proximity_score == 50:
            score += 35
            reasons.append("🚚 Nearby Work")
        elif work_history_proximity_score == 20:
            score += 10
            reasons.append("🚚 Regional Work")
        
        if worked_with_farmer:
            score += 40
            reasons.append("🤝 Knows Farmer")
        
        if activity_count > 10:
            score += 40
            reasons.append(f"⭐ Expert ({activity_count}x)")
        elif activity_count > 5:
            score += 25
            reasons.append(f"⭐ Experienced ({activity_count}x)")
        elif activity_count > 0:
            score += 10
            reasons.append(f"Done {activity_count}x")
        
        # ✅ ADD PRICING TO REASONS
        if price_metrics['price_display'] != 'N/A':
            reasons.append(f"💰 {price_metrics['price_display']}")
        
        if is_new and is_local:
            score += 20
            reasons.append("🌱 New Local")
        
        volume_bonus = min(total_jobs * 2, 30)
        score += volume_bonus
        
        if muk.get('total_earnings', 0) > 50000:
            score += 15
            reasons.append("💰 High Earner")
        
        muk_with_score = {
            **muk,
            'recommendation_score': score,
            'recommendation_reasons': reasons
        }
        
        buckets["overall_best"].append(muk_with_score)
        buckets["all"].append(muk_with_score)
    
    # ========================================
    # SORT ALL BUCKETS
    # ========================================
    buckets["activity_experts"].sort(
        key=lambda x: x.get('temp_activity_count', 0),
        reverse=True
    )
    
    buckets["high_volume"].sort(
        key=lambda x: x.get('temp_total_jobs', 0),
        reverse=True
    )
    
    buckets["overall_best"].sort(
        key=lambda x: x.get('recommendation_score', 0),
        reverse=True
    )
    
    buckets["all"].sort(
        key=lambda x: x.get('mukkadam_name', '').lower()
    )

    # ✅ MOVE HERE (OUTSIDE LOOP)
    buckets["cost_effective"].sort(
        key=lambda x: (
            x.get('price_metrics', {}).get('asking_price') or 
            x.get('price_metrics', {}).get('historical_price_per_acre') or 
            float('inf')
        )
    )

# ✅ SORT TRANSPORT_COST BY LOWEST COST
    # We use a conditional expression because "0 or float('inf')" evaluates to infinity
    buckets["transport_cost"].sort(
        key=lambda x: (
            x.get('transport_cost', {}).get('estimated_cost') 
            if x.get('transport_cost', {}).get('estimated_cost') is not None 
            else float('inf')
        )
    )
    for key in buckets:
        if key != 'all' and len(buckets[key]) > 20:
            buckets[key] = buckets[key][:20]
    
    return buckets