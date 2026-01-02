// types.ts - TypeScript type definitions

export interface Mukkadam {
  id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  crew_size: string;
  max_crew_capacity: string;
  has_smartphone: string;
  team_members: TeamMember[];
}

export interface TeamMember {
  name: string;
  mobile?: string;
}

export interface Job {
  id: number;
  title: string;
  start_date: string;
  plot_name?: string;
  plot_area?: number;
  plot_crop?: string;
  farmer_name?: string;
  farmer_phone?: string;
  farmer_id?: string;
  location?: string;
  village?: string;
  taluka?: string;
  district?: string;
  fir_id?: number;
  notes?: string;
  class_name?: string;
  workers_required: number;
  status: JobStatus;
  all_day: boolean;
  created_at: string;
  updated_at: string;
  created_by?: number;
  created_by_name?: string;
  assignments: JobAssignment[];
  total_assigned_workers: number;
  is_fully_assigned: boolean;
}

export type JobStatus = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'cancelled';

export interface JobAssignment {
  id: number;
  job: number;
  mukkadam_id?: number;
  mukkadam_details: Mukkadam;
  workers_count: number;
  team_members: string[];
  status: AssignmentStatus;
  agreed_rate?: number;
  payment_status: PaymentStatus;
  notes?: string;
  assigned_at: string;
  assigned_by?: number;
  assigned_by_name?: string;
  confirmed_at?: string;
  completed_at?: string;
}

export type AssignmentStatus = 'assigned' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled';
export type PaymentStatus = 'pending' | 'partial' | 'completed';

export interface AssignmentFormData {
  mukkadam_id: number;
  workers_count: number;
  team_members: string[];
  agreed_rate?: number;
  notes?: string;
}

export interface DashboardStats {
  total_jobs: number;
  pending_jobs: number;
  assigned_jobs: number;
  in_progress_jobs: number;
  completed_jobs: number;
  total_workers_needed: number;
  total_workers_assigned: number;
}