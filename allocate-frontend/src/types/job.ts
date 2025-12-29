export interface Farmer {
  id: string;
  name: string;
  phone: string;
  village: string;
  created_at: string;
}

export interface Activity {
  id: string;
  name: string;
  description: string;
  days_after_pruning: number;
}

export interface Mukadam {
  id: string;
  name: string;
  phone: string;
  location: string;
  number_of_labourers: number;
  is_active: boolean;
}

export interface Job {
  id: string;
  farmer: Farmer;
  activity: Activity;
  farm_size_acres: number;
  location: string;
  requested_date: string;
  requested_time: string;
  farmer_price_per_acre: number;
  status: 'confirmed' | 'assigned' | 'bidding' | 'finalized' | 'in_progress' | 'completed' | 'cancelled';
  finalized_mukadam?: Mukadam;
  finalized_price?: number;
  confirmed_at: string;
  finalized_at?: string;
  notes: string;
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