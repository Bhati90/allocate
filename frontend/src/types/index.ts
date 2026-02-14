// ============================================
// TEAM & WORKERS
// ============================================

export interface Team {
  id: string;
  name: string;
  mukkadam_name: string;
  mukkadam_contact: string;
  base_location: {
    lat: number;
    lng: number;
    village: string;
  };
  total_workers: number;
  monthly_salary_per_worker: number;
  specialization?: string[];
  efficiency_rating: {
    land_prep: number;
    sowing: number;
    fertilizing: number;
    weeding: number;
    spraying: number;
    harvesting: number;
  };
  rate_per_activity: {
    land_prep: number;
    sowing: number;
    fertilizing: number;
    weeding: number;
    spraying: number;
    harvesting: number;
  };
}

// ============================================
// FARM & LOCATION
// ============================================

export interface Farm {
  id: string;
  farmer_name: string;
  farmer_contact: string;
  location: {
    lat: number;
    lng: number;
    village: string;
  };
  total_acres: number;
  crop_type: string;
  hexagon_id: string;
}

// ============================================
// HEXAGON CLUSTER
// ============================================

export interface HexagonCluster {
  id: string;
  center: { lat: number; lng: number };
  radius_km: number;
  assigned_teams: string[];
  total_cultivable_acres: number;
  current_booked_acres: number;
  market_penetration: number;
  farms_in_cluster: string[];
  avg_demand_score: number;
}

// ============================================
// ACTIVITY DEFINITIONS
// ============================================

export type ActivityType =
  | 'land_prep'
  | 'sowing'
  | 'fertilizing'
  | 'weeding'
  | 'spraying'
  | 'harvesting';

export interface ActivityConfig {
  type: ActivityType;
  display_name: string;
  sequence_order: number;
  gap_days_after_previous: number;
  base_productivity: number;
  min_workers_required: number;
}

export const ACTIVITY_CONFIGS: ActivityConfig[] = [
  {
    type: 'land_prep',
    display_name: 'Land Preparation',
    sequence_order: 1,
    gap_days_after_previous: 0,
    base_productivity: 1.2,
    min_workers_required: 8,
  },
  {
    type: 'sowing',
    display_name: 'Sowing',
    sequence_order: 2,
    gap_days_after_previous: 3,
    base_productivity: 1.5,
    min_workers_required: 6,
  },
  {
    type: 'fertilizing',
    display_name: 'Fertilizing',
    sequence_order: 3,
    gap_days_after_previous: 12,
    base_productivity: 2.0,
    min_workers_required: 4,
  },
  {
    type: 'weeding',
    display_name: 'Weeding',
    sequence_order: 4,
    gap_days_after_previous: 15,
    base_productivity: 0.8,
    min_workers_required: 10,
  },
  {
    type: 'spraying',
    display_name: 'Spraying',
    sequence_order: 5,
    gap_days_after_previous: 10,
    base_productivity: 2.5,
    min_workers_required: 3,
  },
  {
    type: 'harvesting',
    display_name: 'Harvesting',
    sequence_order: 6,
    gap_days_after_previous: 20,
    base_productivity: 0.6,
    min_workers_required: 15,
  },
];

// ============================================
// BOOKING & ACTIVITIES
// ============================================

export interface Booking {
  id: string;
  farm_id: string;
  crop_type: string;
  total_acres: number;
  booking_date: string; // 'YYYY-MM-DD'
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  activities: BookingActivity[];
  total_cost: number;      // total cost across all activities
  total_revenue: number;   // total charged to farmer
  profit_margin: number;   // percentage (e.g. 22.4)
  notes: string;
}

export interface BookingActivity {
  id: string;
  booking_id: string;
  activity_type: ActivityType;
  sequence_order: number;

  // scheduling
  scheduled_start_date: string | null; // 'YYYY-MM-DD'
  scheduled_end_date: string | null;
  actual_start_date: string | null;
  actual_end_date: string | null;

  // work
  acres: number;
  assigned_team_id: string | null;
  assigned_workers: number;
  calculated_duration_days: number;

  // status
  status: 'not_started' | 'in_progress' | 'completed' | 'delayed' | 'blocked';
  completion_percentage: number;
  delay_reason: string | null; // "rain" | "emergency" | etc.

  // money
  team_cost: number;     // total for this activity
  travel_cost: number;
  other_costs: number;

  // optional per-activity analytics
  feedback: {
    mukkadam_rating: number;       // 1–5
    efficiency_achieved: number;   // 0.0–1.5 (actual vs expected speed)
    issues: string[];
  } | null;
}


// ============================================
// DAILY ALLOCATION
// ============================================

export interface DailyAllocation {
  date: string;
  team_id: string;
  activity_id: string;
  farm_id: string;
  workers_allocated: number;
  workers_available: number;
  workers_free: number;
  travel_distance_km: number;
  travel_cost: number;
  is_rain_day: boolean;
  conflicts: AllocationConflict[];
}

export interface AllocationConflict {
  type: 'double_booking' | 'worker_shortage' | 'travel_distance' | 'weather';
  severity: 'warning' | 'error' | 'critical';
  message: string;
  suggested_action: string;
}

// ============================================
// WEATHER & DISRUPTIONS
// ============================================

export interface DisruptionEvent {
  id: string;
  date: string;
  type: 'rain' | 'festival' | 'emergency' | 'equipment_breakdown';
  affected_entity: 'farm' | 'team' | 'district';
  entity_id: string | null;
  description: string;
  impact: 'full_day_lost' | 'half_day_lost' | 'delay_only';
}

export interface TeamScore {
  team_id: string;
  score: number;
  distance_km: number;
  cost: number;
  availability: number;
  reasons: string[];
}
