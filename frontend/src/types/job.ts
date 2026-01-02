export interface Farmer {
  id: string;
  name: string;
  phone: string;
  village: string;
  created_at: string;
}

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


export interface Mukadam {
  id: string;
  name: string;
  phone: string;
  location: string;
  number_of_labourers: number;
  is_active: boolean;
}


export interface MukadamBid {
  id: string;
  job_id: string;
  bid_id: string;
  mukadam: Mukadam;
  status: 'pending' | 'interested' | 'declined' | 'cancelled';
  bid_price_per_acre?: number;
  estimated_duration_hours?: number;
  comments: string;
  responded_at?: string;
}

export interface JobAssignment {
  id: string;
  job_id: string;
  mukadam: Mukadam;
  assigned_at: string;
  notified_at?: string;
}