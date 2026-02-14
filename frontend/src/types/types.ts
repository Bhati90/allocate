// types.ts
export interface Job {
  job_id: string;
  plot_name: string;
  crop_name: string;
  variety: string;
 plot: number;
  work_id: string;
  farmer_id: string;
  farmer_name: string;
  status: 'pending' | 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  scheduled_date?: string;
  booking_type: string;
  activities: JobActivity[];
  total_activities_amount: number;
  is_field_verified: boolean;
  latitude?: number;
  longitude?: number;
}

export interface JobActivity {
  id: number;
  activity_id: number;
  activity_name: string;
  activity_type?: string;
  is_strict: boolean;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  scheduled_date?: string;
  estimated_workers: number;
  rate_per_acre: number;
  total_price: number;
  allocation_status: string;
  is_fully_allocated: boolean;
}



export interface Mukkadam {
  mukkadam_id: number;
  available_crew_size?: number;
  mukkadam_name: string;
  mobile_numbers: string;
  is_permanent: boolean;
  district: string;
  taluka: string;
  village: string;
  crew_size: number;
  start_date?: string;
  end_date?: string;
  work_mode: string;
  has_smartphone: string;
  activity_rates: MukkadamActivityRate[];
}

export interface MukkadamActivityRate {
  id: number;
  mukkadam: number;
  mukkadam_name: string;
  activity: number;
  activity_name: string;
  rate_per_acre: number;
  productivity_per_worker: number;
  daily_capacity: number;
  source: 'api' | 'custom';
  is_active: boolean;
}

export interface MukkadamAvailability {
  id: number;
  mukkadam: number;
  mukkadam_name: string;
  date: string;
  is_available: boolean;
  is_on_leave: boolean;
  available_crew_size: number;
  allocated_workers: number;
  remaining_capacity: number;
  is_manually_set: boolean;
}

export interface Allocation {
  id: number;
  job_activity: number;
  job_id: string;
  activity_name: string;
  farmer_name: string;
  mukkadam: number;
  mukkadam_name: string;
  allocated_date: string;
  allocated_area: number;
  allocated_workers: number;
  farmer_rate: number;
  mukkadam_rate: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
  actual_workers?: number;
  actual_area_completed?: number;
  efficiency_score?: number;
}

export interface ValidationResult {
  can_allocate: boolean;
  message?: string;
  error?: string;
  warnings?: {
    productivity_warning?: ProductivityWarning;
    [key: string]: any;
  };
  preview?: AllocationPreview;
}

export interface ProductivityWarning {
  severity: 'error' | 'warning';
  message: string;
  details: {
    workers: number;
    productivity_per_worker: string;
    max_capacity: string;
    requested: string;
    deficit?: string;
    utilization?: string;
  };
  suggestions?: Suggestion[];
  note?: string;
}

export interface Suggestion {
  option: 'reduce_area' | 'add_workers' | 'update_productivity' | 'split_days';
  description: string;
  allocation?: any;
  allocations?: any[];
}

export interface AllocationPreview {
  job_id: string;
  farmer_name: string;
  activity: string;
  mukkadam: string;
  date: string;
  area: number;
  workers: number;
  productivity: number;
  max_capacity: number;
  pricing: {
    farmer_rate: number;
    mukkadam_rate: number;
    farmer_amount: number;
    mukkadam_amount: number;
    profit: number;
    profit_margin: string;
  };
}

export interface ActivityCatalog {
  id: number;
  name: string;
  activity_type?: string;
  default_rate_per_acre: number;
  is_strict: boolean;
  estimated_workers_per_acre: number;
  source: 'api' | 'custom';
}