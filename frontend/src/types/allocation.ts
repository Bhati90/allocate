// ✅ UPDATED INTERFACES TO MATCH NEW API STRUCTURE

export interface Visit {
  visit_id: number;
  status: string;
  assigned_to: string;
  media_locations: MediaLocation[];
}

export interface MediaLocation {
  media_id: number;
  media_type: 'image' | 'video';
  location: {
    latitude: number;
    longitude: number;
    address: string;
    is_field_location: boolean;
  };
}

export interface Job {
  id: number;
  work_id: string;
  farmer_id?: string;
  latitude: number;
  longitude: number;
  
  point_of_contact?: string | null;
  visits?: Visit[];
  
  farmer?: {
    farmer_name: string;
    phone_number: string;
    village: string;
    taluka: string;
    district: string;
    location: string;
  };
  
  title?: string;
  description?: string;
  status: 'pending' | 'partially_allocated' | 'fully_allocated';
  is_complex: boolean;
  total_activities: number;
  created_at: string;
  scheduled_date?: string;
  
  booking?: {
    id: number;
    total_amount: number;
    advance_paid: number;
    balance: number;
    status: 'BOOKED' | 'PARTIAL' | 'PAID';
    payments?: any[];
  };
  
  activities?: Activity[];
}

export interface Activity {
  id: string;
  activity_id: string;
  activity_name: string;
  activity_type: string;
  location: string;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  scheduled_date: string;
  estimated_workers: number;
  lost_reason: string;
  
  rate_per_acre: number;
  total_price: number;
  transport_cost: number;
  other_cost: number;
  crop_bundles: string;
  subtotal: number;
  is_manually_edited: boolean;
  is_lost: boolean;
  
  is_fully_allocated: boolean;
  allocations?: any[];
}

// ✅ NEW: Simplified Farmer interface matching API response
export interface Farmer {
  farmer_id: string;
  farmer_name: string;
  phone_number: string;
  location: string;
}

// ✅ NEW: Simplified Job info matching API response
export interface JobInfo {
  job_id: string;
  job_name: string;
  scheduled_date: string;
  location: string;
  central_team_phone: string;
}

// ✅ NEW: Simplified Activity info matching API response
export interface ActivityInfo {
  activity_id: string;
  activity_name: string;
  activity_type: string;
  total_area: number;
  scheduled_date: string;
  scheduled_time: string;
}

// ✅ UPDATED: Main Allocation interface matching new API structure
export interface Allocation {
  // Core identification
  allocation_id: number;
  farmer_id: string;
  
  // ✅ Nested objects (simplified from API)
  farmer: Farmer | null;
  job: JobInfo;
  activity: ActivityInfo;
  
  // ✅ Direct fields matching required format
  mukkadam_id: number;
  allocated_area: number;
  work_date: string;
  mukkadam_price: number;
  transport_type: 'provider' | 'own' | 'none';
  transport_provider_id?: number | null;
  transport_price: number;
  status: 'allocated' | 'in_progress' | 'completed';
  
  is_carry_forward?: boolean;
  carry_forward_from?: number | null;
  report_submitted?: boolean;
  actual_area_done?: number | null;
  farmer_agreed?: boolean | null;
  // Additional fields
  crew_size?: number;
  notes?: string;
  allocated_at?: string;
  completed_at?: string;
  
  // ✅ Full nested objects for frontend use
  mukkadam?: Mukkadam;
  transport_provider?: TransportProvider;
  
  // Legacy fields for backward compatibility
  id?: number;
  farmer_work_id?: string;
  activity_id?: string;
  job_id?: string;
  activity_name?: string;
  job_activity?: string;
  total_cost?: number;
  created_by?: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
  };
  allocated_by?: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
  };
  own_transport_price?: number;
}

export interface Mukkadam {
  id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  crew_size: string;
  is_permanent: boolean;
  paid_amount: number;

  price_metrics?: {
    asking_price: number | null;
    is_base_price: boolean;
    historical_price_per_acre: number | null;
    historical_jobs_count: number;
    price_display: string;
  };
}

export interface TransportProvider {
  id: number;
  name: string;
  contact_number: string;
  base_location: string;
  max_distance: number;
}

export interface MukkadamAllocation {
  mukkadam: Mukkadam;
  paid_amount: number;
  allocations: Allocation[];
  total_price: number;
  job_count: number;
}

export interface TransportAllocation {
  provider: TransportProvider;
  paid_amount: number;
  allocations: Allocation[];
  total_price: number;
  job_count: number;
}

interface ActivityEditDetails {
  edited_by: string;
  edited_at: string;
  reason: string;
  changes: Record<string, {
    old_value: any;
    new_value: any;
  }>;
}

export interface ActivityLog {
  id: number;
  allocation_id: number;
  job_id: string;
  mukkadam_id: number;
  mukkadam_name: string;
  transport_type: 'provider' | 'own' | 'none';
  transport_provider_id?: number;
  transport_name: string;
  mukkadam_price: number;
  transport_price: number;
  total_price: number;
  user_name: string;
  timestamp: string;
  work_date?: string;
  allocated_area?: number;
  crew_size?: number;
  activity_name?: string;
  farmer_name?: string;
  farmer_work_id?: string;
  activity_edit_details?: ActivityEditDetails;
}

export interface DailyStat {
  date: string;
  total_allocations: number;
  total_area_allocated: number;
  total_mukkadam_price: number;
  total_transport_price: number;
  allocations_by_user: Record<string, number>;
}

// ✅ NEW: API Response interface
export interface AllocationListResponse {
  count: number;
  allocations: Allocation[];
  summary: {
    total_allocations: number;
    total_area_allocated: number;
    total_cost: number;
    active_allocations: number;
    completed_allocations: number;
    in_progress_allocations: number;
  };
  performance: {
    total_time: string;
    batch_fetch_time: string;
  };
}