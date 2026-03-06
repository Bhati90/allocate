// types/insights.ts or at top of your component file

export interface ClusterInsightsSummary {
  total_jobs: number;
  total_activities: number;
  total_area_allocated: number;
  total_area_completed: number;
  total_allocated_workers: number;
  effective_capacity_workers: number;
  crew_utilization_percent: number;
  slot_utilization_percent: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
  loss_allocations: number;
  dispute_count: number;
  dispute_rate_percent: number;
  avg_efficiency_score: number;
}

export interface InsightsByDay {
  date: string;
  total_area_allocated: number;
  total_area_completed: number;
  allocated_workers: number;
  effective_capacity_workers: number;
  crew_utilization_percent: number;
  slot_utilization_percent: number;
  profit: number;
  jobs_scheduled: number;
  jobs_completed: number;
  disputes: number;
}

export interface InsightsByMukkadam {
  mukkadam_id: number;
  name: string;
  crew_size: number;
  max_crew_capacity: number;
  allocations: number;
  allocated_workers_total: number;
  effective_capacity_workers: number;
  crew_utilization_percent: number;
  total_area_allocated: number;
  total_area_completed: number;
  avg_efficiency_score: number;
  profit: number;
  disputes: number;
}

export interface InsightsByActivity {
  activity_id: number;
  activity_name: string;
  allocations: number;
  total_area_allocated: number;
  total_area_completed: number;
  avg_farmer_rate: number;
  avg_mukkadam_rate: number;
  avg_profit_per_acre: number;
  profit: number;
  loss_allocations: number;
}

export interface MukkadamAllocation {
  allocation_id: number;
  date: string;
  job_id: string;
  farmer_id: string;
  farmer_name: string;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  allocated_area: number;
  actual_area_completed: number;
  allocated_workers: string;
  work_status: string;
  payment_status: string;
  profit: number;
  allows_second_job: boolean;
  is_carry_forward: boolean;
  is_auto_allocated: boolean;
}

export interface MukkadamWork {
  mukkadam_id: string;
  name: string;
  allocations: MukkadamAllocation[];
}

export interface FarmerActivityAllocation {
  allocation_id: number;
  date: string;
  mukkadam_id: number;
  mukkadam_name: string;
  allocated_area: number;
  allocated_workers: string;
  work_status: string;
  payment_status: string;
  profit: number;
}

export interface FarmerActivity {
  job_id: string;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  scheduled_date: string | null;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  allocation_status: string;
  allocations: FarmerActivityAllocation[];
}

export interface FarmerWork {
  farmer_id: string;
  farmer_name: string;
  activities: FarmerActivity[];
}

export interface CapacityDemand {
  date: string;
  capacity_workers: number;
  demand_workers: number;
  shortage_workers: number;
  is_overbooked: boolean;
}

export interface MoveSuggestion {
  overbooked_date: string;
  target_date: string;
  free_workers_on_target: string;
  flexible_activities: Array<{
    job_id: string;
    farmer_id: string;
    farmer_name: string;
    activity_id: number;
    activity_name: string;
    scheduled_date: string | null;
    remaining_area: number;
  }>;
}

export interface ClusterInsightsResponse {
  cluster: { id: number; name: string };
  date_range: { start: string; end: string };
  summary: ClusterInsightsSummary;
  by_day: InsightsByDay[];
  by_mukkadam: InsightsByMukkadam[];
  by_activity: InsightsByActivity[];
  mukkadam_work: MukkadamWork[];
  farmer_work: FarmerWork[];
  capacity_demand: CapacityDemand[];
  move_suggestions: MoveSuggestion[];
}
