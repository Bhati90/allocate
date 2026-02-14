// types/map.types.ts
export type HexagonCluster = {
  id: string;
  center_lat: number;
  center_lng: number;
  radius_km: number;
  villages: string[];
  
  // Job Metrics
  total_jobs: number;
  total_activities: number;
  total_allocations: number;
  
  // Financial
  total_revenue: number;
  total_cost: number;
  profit: number;
  profit_margin: number;
  
  // People
  unique_farmers: number;
  unique_mukkadams: number;
  
  // Area
  total_cultivable_acres: number;
  booked_acres: number;
  allocated_acres: number;
  pending_acres: number;
  
  // Market Penetration
  market_penetration: number; // (booked_acres / total_cultivable_acres) * 100
  
  // Capacity
  available_workers: number;
  needed_workers: number;
  capacity_utilization: number;
  
  // Demand
  pending_jobs: number;
  upcoming_activities_week: number;
  upcoming_activities_month: number;
  demand_score: number;
  
  // Status breakdown
  status_counts: {
    pending: number;
    partially_allocated: number;
    fully_allocated: number;
    in_progress: number;
    completed: number;
  };
  
  // Booking type
  tender_count: number;
  ondemand_count: number;
  
  // Future predictions
  future_booked_acres: number;
  future_needed_workers: number;
  future_revenue: number;
};

export type MukkadamPosition = {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  crew_size: number;
  cluster_id: string | null;
  is_live_location: boolean;
  current_allocation?: {
    job_id: string;
    activity_name: string;
    location: string;
  };
  availability: {
    is_available: boolean;
    available_days: number;
    start_date: string | null;
    end_date: string | null;
  };
};