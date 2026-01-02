export interface Job {
  id: number;
  work_id: string;
  farmer_id?: string;
  
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
  
  // ✅ PRICING FROM API
  rate_per_acre: number;
  total_price: number;       // Revenue
  transport_cost: number;    // Expected transport cost
  other_cost: number;
  subtotal: number;
  
  is_fully_allocated: boolean;
  allocations?: any[];
}
export interface Allocation {
  id: number;
  farmer_work_id: string;
  mukkadam_id: number;
  mukkadam_price: number ;
  transport_price: number ;
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
  job_activity?: number;
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
  allocations: Allocation[];
  total_price: number;
  job_count: number;
}

export interface TransportAllocation {
  provider: TransportProvider;
  allocations: Allocation[];
  total_price: number;
  job_count: number;
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
}

export interface DailyStat {
  date: string;
  total_allocations: number;
  total_area_allocated: number;
  total_mukkadam_price: number;
  total_transport_price: number;
  allocations_by_user: Record<string, number>;
}