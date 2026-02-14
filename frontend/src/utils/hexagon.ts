// utils/hexagonUtils.ts
import dayjs from 'dayjs';

// Nashik district approximate boundaries
const NASHIK_BOUNDS = {
  north: 20.5,
  south: 19.5,
  east: 74.5,
  west: 73.5,
};

const HEXAGON_RADIUS_KM = 15;
const APPROX_TOTAL_ACRES_PER_CLUSTER = 10000;

// ✅ COMPLETE VILLAGE COORDINATES - Your operational villages
const VILLAGE_COORDINATES: Record<string, { lat: number; lng: number }> = {
  // Your operational villages
  'tembhe': { lat: 20.15, lng: 73.95 },
  'konambe': { lat: 20.12, lng: 73.92 },
  'sonambe': { lat: 20.18, lng: 73.88 },
  'sonari': { lat: 20.22, lng: 73.90 },
  'dubere': { lat: 20.10, lng: 73.85 },
  'nanegaon': { lat: 20.25, lng: 73.87 },
  'sawargaon': { lat: 20.08, lng: 73.82 },
  'khadak malegaon': { lat: 20.55, lng: 74.50 },
  'pimpalgaon': { lat: 20.30, lng: 74.10 },
  'umbarkhed': { lat: 20.20, lng: 74.05 },
  'mohadi': { lat: 20.17, lng: 74.02 },
  'sonjamb': { lat: 20.28, lng: 74.08 },
  'wani': { lat: 20.05, lng: 73.95 },
  'raanwad': { lat: 20.32, lng: 74.15 },
  'nilwandi': { lat: 20.35, lng: 74.12 },
  'dindori': { lat: 20.20, lng: 73.83 },
  'garudeshwar': { lat: 20.13, lng: 73.78 },
  'talegaon anjaneri': { lat: 20.02, lng: 73.70 },
  'mahiravani': { lat: 20.08, lng: 73.75 },
  'pathardi': { lat: 20.24, lng: 73.93 },
  'paade': { lat: 20.11, lng: 73.88 },
  'umrale': { lat: 20.16, lng: 73.82 },
  'bopegaon': { lat: 20.09, lng: 73.90 },
  'vadner bhairav': { lat: 20.14, lng: 73.97 },
  'vadner bhairao': { lat: 20.14, lng: 73.97 }, // Alternative spelling
  'pachore wani': { lat: 20.21, lng: 74.00 },
  'shirwade wani': { lat: 20.19, lng: 74.03 },
  
  // Major Nashik towns/talukas
  'nashik': { lat: 20.0, lng: 73.8 },
  'sinnar': { lat: 19.85, lng: 73.98 },
  'malegaon': { lat: 20.55, lng: 74.53 },
  'yeola': { lat: 20.04, lng: 74.48 },
  'niphad': { lat: 20.08, lng: 74.1 },
  'kalwan': { lat: 20.48, lng: 74.0 },
  'surgana': { lat: 20.56, lng: 73.63 },
  'peth': { lat: 20.28, lng: 73.98 },
  'chandwad': { lat: 20.33, lng: 74.23 },
  'igatpuri': { lat: 19.7, lng: 73.56 },
  'trimbakeshwar': { lat: 19.93, lng: 73.53 },
  'baglan': { lat: 20.8, lng: 73.75 },
  'deola': { lat: 20.03, lng: 74.47 },
  'satana': { lat: 20.6, lng: 74.2 },
};

// ✅ NORMALIZED VILLAGE NAME MATCHING
function normalizeVillageName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ') // normalize spaces
    .replace(/[^\w\s]/g, ''); // remove special characters
}

export function getVillageCoordinates(villageName: string): { lat: number; lng: number } | null {
  if (!villageName) return null;
  
  const normalized = normalizeVillageName(villageName);
  
  // 1. Check exact match
  if (VILLAGE_COORDINATES[normalized]) {
    return VILLAGE_COORDINATES[normalized];
  }
  
  // 2. Check partial match (contains)
  for (const [key, coords] of Object.entries(VILLAGE_COORDINATES)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return coords;
    }
  }
  
  // 3. Check word-by-word match (for multi-word villages)
  const words = normalized.split(' ');
  for (const [key, coords] of Object.entries(VILLAGE_COORDINATES)) {
    const keyWords = key.split(' ');
    const matchCount = words.filter(w => keyWords.includes(w)).length;
    if (matchCount >= Math.min(words.length, keyWords.length) / 2) {
      return coords;
    }
  }
  
  // 4. Return null if not found (we'll handle this in the calling code)
  return null;
}

// ✅ GET FALLBACK LOCATION FROM OPERATIONAL VILLAGES
export function getFallbackLocation(): { lat: number; lng: number } {
  // Return center of your operational area (roughly between your villages)
  return { lat: 20.15, lng: 73.92 };
}

// ✅ GET CLOSEST OPERATIONAL VILLAGE
export function getClosestOperationalVillage(lat: number, lng: number): string {
  let closestVillage = 'Nashik';
  let minDistance = Infinity;
  
  for (const [village, coords] of Object.entries(VILLAGE_COORDINATES)) {
    const distance = calculateDistance(lat, lng, coords.lat, coords.lng);
    if (distance < minDistance) {
      minDistance = distance;
      closestVillage = village;
    }
  }
  
  return closestVillage;
}

// utils/hexagonUtils.ts - Update the generateNashikHexagons function

export function generateNashikHexagons(): Array<{
  id: string;
  center_lat: number;
  center_lng: number;
  radius_km: number;
}> {
  const hexagons = [];
  
  // Nashik district bounds (expanded slightly)
  const bounds = {
    minLat: 19.4,
    maxLat: 20.6,
    minLng: 73.4,
    maxLng: 74.6,
  };
  
  // For 15km radius hexagons, we need proper hexagonal packing
  // Horizontal spacing: 1.5 * radius
  // Vertical spacing: sqrt(3) * radius
  const latSpacing = 0.234; // ~26km (sqrt(3) * 15km in degrees)
  const lngSpacing = 0.27;  // ~30km (1.5 * 15km in degrees)
  
  let id = 1;
  let row = 0;
  
  for (let lat = bounds.minLat; lat <= bounds.maxLat; lat += latSpacing) {
    const lngOffset = (row % 2) * (lngSpacing / 2); // Offset every other row
    for (let lng = bounds.minLng + lngOffset; lng <= bounds.maxLng; lng += lngSpacing) {
      hexagons.push({
        id: `NH-${String(id).padStart(2, '0')}`,
        center_lat: lat,
        center_lng: lng,
        radius_km: HEXAGON_RADIUS_KM,
      });
      id++;
    }
    row++;
  }
  
  return hexagons;
}
// Calculate distance between two points (Haversine formula)
export function calculateDistance(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Determine which hexagon a point belongs to
export function findHexagonForPoint(
  lat: number,
  lng: number,
  hexagons: Array<{ id: string; center_lat: number; center_lng: number; radius_km: number }>
): string | null {
  let closestHex = null;
  let minDistance = Infinity;
  
  for (const hex of hexagons) {
    const distance = calculateDistance(lat, lng, hex.center_lat, hex.center_lng);
    if (distance <= hex.radius_km && distance < minDistance) {
      minDistance = distance;
      closestHex = hex.id;
    }
  }
  
  return closestHex;
}

// Calculate available days for mukkadam
export function calculateAvailableDays(mukkadam: any): number {
  const today = dayjs();
  let totalDays = 0;
  
  if (mukkadam.start_date && mukkadam.end_date) {
    const start = dayjs(mukkadam.start_date);
    const end = dayjs(mukkadam.end_date);
    
    if (start.isBefore(today) && end.isAfter(today)) {
      totalDays += end.diff(today, 'day');
    }
  }
  
  if (mukkadam.team_availabilities && Array.isArray(mukkadam.team_availabilities)) {
    for (const avail of mukkadam.team_availabilities) {
      if (avail.status === 'Available' && avail.startDate && avail.endDate) {
        const start = dayjs(avail.startDate);
        const end = dayjs(avail.endDate);
        
        if (start.isBefore(today) && end.isAfter(today)) {
          totalDays += end.diff(today, 'day');
        }
      }
    }
  }
  
  return Math.max(totalDays, 0);
}

// ✅ EXTRACT LOCATION FROM JOB/ACTIVITY
export function extractLocationFromJob(job: any): { lat: number; lng: number; source: string } {
  // Priority 1: Farmer village
  if (job.farmer?.village) {
    const coords = getVillageCoordinates(job.farmer.village);
    if (coords) {
      return { ...coords, source: 'farmer_village' };
    }
  }
  
  // Priority 2: Activity location
  if (job.activities && job.activities.length > 0) {
    for (const activity of job.activities) {
      if (activity.location) {
        const coords = getVillageCoordinates(activity.location);
        if (coords) {
          return { ...coords, source: 'activity_location' };
        }
      }
    }
  }
  
  // Priority 3: Job latitude/longitude if available
  if (job.latitude && job.longitude) {
    return { lat: job.latitude, lng: job.longitude, source: 'job_coordinates' };
  }
  
  // Priority 4: Fallback to operational area center
  return { ...getFallbackLocation(), source: 'fallback' };
}

// ✅ EXTRACT LOCATION FROM ACTIVITY
export function extractLocationFromActivity(activity: any, job?: any): { lat: number; lng: number; source: string } {
  // Priority 1: Activity location
  if (activity.location) {
    const coords = getVillageCoordinates(activity.location);
    if (coords) {
      return { ...coords, source: 'activity_location' };
    }
  }
  
  // Priority 2: Job data if provided
  if (job) {
    return extractLocationFromJob(job);
  }
  
  // Priority 3: Fallback
  return { ...getFallbackLocation(), source: 'fallback' };
}