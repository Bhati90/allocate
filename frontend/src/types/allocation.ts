// ✅ Add these helper interfaces below
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
latitude: number;  // ✅ Change Number to number (primitive)
  longitude: number;
  

  // ✅ NEW: Point of Contact (assigned_to from the first visit)
  point_of_contact?: string | null;

  // ✅ NEW: Detailed Visits information
  visits?: Visit[];
  // ✅ FARMER DETAILS (enriched by backend)
  farmer?: {
    farmer_name: string;
    phone_number: string;
    village: string;
    taluka: string;
    district: string;
    location: string;  // Combined location string
  };
  
  title?: string;
  description?: string;
  status: 'pending' | 'partially_allocated' | 'fully_allocated';
  is_complex: boolean;
  total_activities: number;
  created_at: string;
  scheduled_date?: string;
  
  // ✅ BOOKING INFO
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
  lost_reason:string;
  
  // ✅ PRICING FROM API
  rate_per_acre: number;
  total_price: number;       // Revenue
  transport_cost: number;    // Expected transport cost
  other_cost: number;
  crop_bundles:string;
  subtotal: number;
  is_manually_edited:boolean;
  is_lost:boolean;
  
  is_fully_allocated: boolean;
  allocations?: any[];
}
export interface Allocation {
  id: number;
  farmer_work_id: string;
  activity_id:string;
  mukkadam_id: number;
  mukkadam_price: string ;
  transport_price: string ;
  allocated_at: string;
  completed_at: string;
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
  status?: string;
  notes?: string;
  job_activity?: string;
  job_id?: string;
  activity_name?: string;
  allocated_area?: number;
  work_date?: string;  // ✅ ADD THIS
  crew_size?: number;  // ✅ ADD THIS
  transport_type?: 'provider' | 'own' | 'none';
  transport_provider_id?: number;
  own_transport_price?: number;
  total_cost?: number;
}

export interface Mukkadam {
  id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  crew_size: string;
  is_permanent: boolean;
  paid_amount:number;

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
  paid_amount:number;
  allocations: Allocation[];
  total_price: number;
  job_count: number;
}

export interface TransportAllocation {
  provider: TransportProvider;
  paid_amount:number;
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
  transport_type: 'provider' | 'own' | 'none';  // ✅ ADD THIS
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
   farmer_name?: string;  // ✅ NEW
  farmer_work_id?: string;  // ✅ NEW
  activity_edit_details?: ActivityEditDetails;  // ✅ NEW
}

export interface DailyStat {
  date: string;
  total_allocations: number;
  total_area_allocated: number;
  total_mukkadam_price: number;
  total_transport_price: number;
  allocations_by_user: Record<string, number>;
}