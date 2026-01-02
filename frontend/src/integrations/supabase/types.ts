export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  __InternalSupabase: {
    PostgrestVersion: "13.0.5"
  }
  public: {
    Tables: {
      activity_allocations: {
        Row: {
          activity_type_id: string
          created_at: string
          id: string
          labour_team_id: string | null
          notes: string | null
          plot_id: string
          scheduled_date: string
          status: string | null
          updated_at: string
        }
        Insert: {
          activity_type_id: string
          created_at?: string
          id?: string
          labour_team_id?: string | null
          notes?: string | null
          plot_id: string
          scheduled_date: string
          status?: string | null
          updated_at?: string
        }
        Update: {
          activity_type_id?: string
          created_at?: string
          id?: string
          labour_team_id?: string | null
          notes?: string | null
          plot_id?: string
          scheduled_date?: string
          status?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "activity_allocations_activity_type_id_fkey"
            columns: ["activity_type_id"]
            isOneToOne: false
            referencedRelation: "activity_types"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "activity_allocations_labour_team_id_fkey"
            columns: ["labour_team_id"]
            isOneToOne: false
            referencedRelation: "labour_teams"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "activity_allocations_plot_id_fkey"
            columns: ["plot_id"]
            isOneToOne: false
            referencedRelation: "plots"
            referencedColumns: ["id"]
          },
        ]
      }
      activity_types: {
        Row: {
          created_at: string
          days_after_pruning: number
          description: string | null
          id: string
          name: string
        }
        Insert: {
          created_at?: string
          days_after_pruning: number
          description?: string | null
          id?: string
          name: string
        }
        Update: {
          created_at?: string
          days_after_pruning?: number
          description?: string | null
          id?: string
          name?: string
        }
        Relationships: []
      }
      // NEW: Bookings table
      bookings: {
        Row: {
          id: string
          farmer_id: string
          call_date: string
          call_notes: string | null
          activity_type_id: string
          requested_date: string
          area_acres: number
          quoted_price: number | null
          advance_amount: number
          advance_date: string | null
          status: 'pending' | 'assigned' | 'allocated' | 'in_progress' | 'completed' | 'invoiced' | 'reviewed' | 'cancelled'
          assigned_to: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          farmer_id: string
          call_date?: string
          call_notes?: string | null
          activity_type_id: string
          requested_date: string
          area_acres: number
          quoted_price?: number | null
          advance_amount?: number
          advance_date?: string | null
          status?: 'pending' | 'assigned' | 'allocated' | 'in_progress' | 'completed' | 'invoiced' | 'reviewed' | 'cancelled'
          assigned_to?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          farmer_id?: string
          call_date?: string
          call_notes?: string | null
          activity_type_id?: string
          requested_date?: string
          area_acres?: number
          quoted_price?: number | null
          advance_amount?: number
          advance_date?: string | null
          status?: 'pending' | 'assigned' | 'allocated' | 'in_progress' | 'completed' | 'invoiced' | 'reviewed' | 'cancelled'
          assigned_to?: string | null
          created_at?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "bookings_farmer_id_fkey"
            columns: ["farmer_id"]
            isOneToOne: false
            referencedRelation: "farmers"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "bookings_activity_type_id_fkey"
            columns: ["activity_type_id"]
            isOneToOne: false
            referencedRelation: "activity_types"
            referencedColumns: ["id"]
          },
        ]
      }
      // NEW: Job Assignments table
      job_assignments: {
        Row: {
          id: string
          booking_id: string
          coordinator_id: string | null
          labour_team_id: string | null
          status: 'finding_labor' | 'allocated' | 'in_progress' | 'completed'
          estimated_start: string | null
          actual_start: string | null
          actual_end: string | null
          notes: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          booking_id: string
          coordinator_id?: string | null
          labour_team_id?: string | null
          status?: 'finding_labor' | 'allocated' | 'in_progress' | 'completed'
          estimated_start?: string | null
          actual_start?: string | null
          actual_end?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          booking_id?: string
          coordinator_id?: string | null
          labour_team_id?: string | null
          status?: 'finding_labor' | 'allocated' | 'in_progress' | 'completed'
          estimated_start?: string | null
          actual_start?: string | null
          actual_end?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "job_assignments_booking_id_fkey"
            columns: ["booking_id"]
            isOneToOne: false
            referencedRelation: "bookings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "job_assignments_labour_team_id_fkey"
            columns: ["labour_team_id"]
            isOneToOne: false
            referencedRelation: "labour_teams"
            referencedColumns: ["id"]
          },
        ]
      }
      // NEW: Payment Records table
      payment_records: {
        Row: {
          id: string
          job_assignment_id: string
          advance_amount: number
          advance_date: string | null
          balance_amount: number
          payment_method: 'cash' | 'upi' | 'cheque' | 'bank_transfer' | null
          payment_date: string | null
          proof_image_url: string | null
          labor_cost: number | null
          transport_cost: number | null
          accommodation_cost: number | null
          other_cost: number | null
          notes: string | null
          collected_by: string | null
          verified_by: string | null
          verified_at: string | null
          created_at: string
        }
        Insert: {
          id?: string
          job_assignment_id: string
          advance_amount?: number
          advance_date?: string | null
          balance_amount: number
          payment_method?: 'cash' | 'upi' | 'cheque' | 'bank_transfer' | null
          payment_date?: string | null
          proof_image_url?: string | null
          labor_cost?: number | null
          transport_cost?: number | null
          accommodation_cost?: number | null
          other_cost?: number | null
          notes?: string | null
          collected_by?: string | null
          verified_by?: string | null
          verified_at?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          job_assignment_id?: string
          advance_amount?: number
          advance_date?: string | null
          balance_amount?: number
          payment_method?: 'cash' | 'upi' | 'cheque' | 'bank_transfer' | null
          payment_date?: string | null
          proof_image_url?: string | null
          labor_cost?: number | null
          transport_cost?: number | null
          accommodation_cost?: number | null
          other_cost?: number | null
          notes?: string | null
          collected_by?: string | null
          verified_by?: string | null
          verified_at?: string | null
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "payment_records_job_assignment_id_fkey"
            columns: ["job_assignment_id"]
            isOneToOne: false
            referencedRelation: "job_assignments"
            referencedColumns: ["id"]
          },
        ]
      }
      // NEW: Farmer Reviews table
      farmer_reviews: {
        Row: {
          id: string
          farmer_id: string
          job_assignment_id: string
          rating: number
          review_text: string | null
          review_date: string
          created_at: string
        }
        Insert: {
          id?: string
          farmer_id: string
          job_assignment_id: string
          rating: number
          review_text?: string | null
          review_date?: string
          created_at?: string
        }
        Update: {
          id?: string
          farmer_id?: string
          job_assignment_id?: string
          rating?: number
          review_text?: string | null
          review_date?: string
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "farmer_reviews_farmer_id_fkey"
            columns: ["farmer_id"]
            isOneToOne: false
            referencedRelation: "farmers"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "farmer_reviews_job_assignment_id_fkey"
            columns: ["job_assignment_id"]
            isOneToOne: false
            referencedRelation: "job_assignments"
            referencedColumns: ["id"]
          },
        ]
      }
      // NEW: User Roles table
      user_roles: {
        Row: {
          id: string
          user_id: string
          role: 'founder' | 'operations_head' | 'coordinator' | 'ground_team' | 'accounts'
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          role: 'founder' | 'operations_head' | 'coordinator' | 'ground_team' | 'accounts'
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          role?: 'founder' | 'operations_head' | 'coordinator' | 'ground_team' | 'accounts'
          created_at?: string
        }
        Relationships: []
      }
      // NEW: Notifications table
      notifications: {
        Row: {
          id: string
          user_id: string
          type: 'booking' | 'assignment' | 'completion' | 'payment' | 'review'
          title: string
          message: string
          booking_id: string | null
          read: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          type: 'booking' | 'assignment' | 'completion' | 'payment' | 'review'
          title: string
          message: string
          booking_id?: string | null
          read?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          type?: 'booking' | 'assignment' | 'completion' | 'payment' | 'review'
          title?: string
          message?: string
          booking_id?: string | null
          read?: boolean
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "notifications_booking_id_fkey"
            columns: ["booking_id"]
            isOneToOne: false
            referencedRelation: "bookings"
            referencedColumns: ["id"]
          },
        ]
      }
      farmers: {
        Row: {
          color: string | null
          contact: string | null
          created_at: string
          id: string
          name: string
          updated_at: string
          village: string | null
        }
        Insert: {
          color?: string | null
          contact?: string | null
          created_at?: string
          id?: string
          name: string
          updated_at?: string
          village?: string | null
        }
        Update: {
          color?: string | null
          contact?: string | null
          created_at?: string
          id?: string
          name?: string
          updated_at?: string
          village?: string | null
        }
        Relationships: []
      }
      labour_teams: {
        Row: {
          contact: string | null
          created_at: string
          id: string
          location: string | null
          mukkadam_name: string
          number_of_labourers: number
          transport_situation: string | null
          updated_at: string
        }
        Insert: {
          contact?: string | null
          created_at?: string
          id?: string
          location?: string | null
          mukkadam_name: string
          number_of_labourers: number
          transport_situation?: string | null
          updated_at?: string
        }
        Update: {
          contact?: string | null
          created_at?: string
          id?: string
          location?: string | null
          mukkadam_name?: string
          number_of_labourers?: number
          transport_situation?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      plot_activities: {
        Row: {
          activity_type_id: string
          created_at: string
          id: string
          plot_id: string
        }
        Insert: {
          activity_type_id: string
          created_at?: string
          id?: string
          plot_id: string
        }
        Update: {
          activity_type_id?: string
          created_at?: string
          id?: string
          plot_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "plot_activities_activity_type_id_fkey"
            columns: ["activity_type_id"]
            isOneToOne: false
            referencedRelation: "activity_types"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "plot_activities_plot_id_fkey"
            columns: ["plot_id"]
            isOneToOne: false
            referencedRelation: "plots"
            referencedColumns: ["id"]
          },
        ]
      }
      plots: {
        Row: {
          acres: number
          created_at: string
          farmer_id: string
          id: string
          pruning_date: string
          updated_at: string
          variety: string | null
        }
        Insert: {
          acres: number
          created_at?: string
          farmer_id: string
          id?: string
          pruning_date: string
          updated_at?: string
          variety?: string | null
        }
        Update: {
          acres?: number
          created_at?: string
          farmer_id?: string
          id?: string
          pruning_date?: string
          updated_at?: string
          variety?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "plots_farmer_id_fkey"
            columns: ["farmer_id"]
            isOneToOne: false
            referencedRelation: "farmers"
            referencedColumns: ["id"]
          },
        ]
      }
      team_activity_rates: {
        Row: {
          activity_type_id: string
          created_at: string
          id: string
          labour_team_id: string
          rate: number
        }
        Insert: {
          activity_type_id: string
          created_at?: string
          id?: string
          labour_team_id: string
          rate: number
        }
        Update: {
          activity_type_id?: string
          created_at?: string
          id?: string
          labour_team_id?: string
          rate?: number
        }
        Relationships: [
          {
            foreignKeyName: "team_activity_rates_activity_type_id_fkey"
            columns: ["activity_type_id"]
            isOneToOne: false
            referencedRelation: "activity_types"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "team_activity_rates_labour_team_id_fkey"
            columns: ["labour_team_id"]
            isOneToOne: false
            referencedRelation: "labour_teams"
            referencedColumns: ["id"]
          },
        ]
      }
      team_availability: {
        Row: {
          created_at: string
          end_date: string
          id: string
          labour_team_id: string
          start_date: string
        }
        Insert: {
          created_at?: string
          end_date: string
          id?: string
          labour_team_id: string
          start_date: string
        }
        Update: {
          created_at?: string
          end_date?: string
          id?: string
          labour_team_id?: string
          start_date?: string
        }
        Relationships: [
          {
            foreignKeyName: "team_availability_labour_team_id_fkey"
            columns: ["labour_team_id"]
            isOneToOne: false
            referencedRelation: "labour_teams"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      allocated_activities: {
        Row: {
          acres: number | null
          activity_name: string | null
          activity_type_id: string | null
          description: string | null
          farmer_color: string | null
          farmer_name: string | null
          id: string | null
          labour_team_id: string | null
          mukkadam_name: string | null
          notes: string | null
          number_of_labourers: number | null
          plot_id: string | null
          rate: number | null
          scheduled_date: string | null
          status: string | null
          variety: string | null
        }
        Relationships: []
      }
      scheduled_activities: {
        Row: {
          acres: number | null
          activity_name: string | null
          activity_type_id: string | null
          days_after_pruning: number | null
          description: string | null
          farmer_color: string | null
          farmer_id: string | null
          farmer_name: string | null
          plot_id: string | null
          pruning_date: string | null
          scheduled_date: string | null
          variety: string | null
        }
        Relationships: []
      }
      // NEW VIEWS
      bookings_with_details: {
        Row: {
          id: string | null
          farmer_id: string | null
          call_date: string | null
          call_notes: string | null
          activity_type_id: string | null
          requested_date: string | null
          area_acres: number | null
          quoted_price: number | null
          advance_amount: number | null
          advance_date: string | null
          status: string | null
          assigned_to: string | null
          created_at: string | null
          updated_at: string | null
          farmer_name: string | null
          farmer_color: string | null
          farmer_contact: string | null
          farmer_village: string | null
          activity_name: string | null
          activity_description: string | null
          days_after_pruning: number | null
          job_assignment_id: string | null
          coordinator_id: string | null
          labour_team_id: string | null
          job_status: string | null
          actual_start: string | null
          actual_end: string | null
          mukkadam_name: string | null
          number_of_labourers: number | null
          mukkadam_contact: string | null
          assigned_to_email: string | null
        }
        Relationships: []
      }
      jobs_with_payment: {
        Row: {
          id: string | null
          booking_id: string | null
          coordinator_id: string | null
          labour_team_id: string | null
          status: string | null
          farmer_id: string | null
          requested_date: string | null
          area_acres: number | null
          quoted_price: number | null
          farmer_name: string | null
          activity_name: string | null
          mukkadam_name: string | null
          balance_amount: number | null
          payment_method: string | null
          payment_date: string | null
          verified_at: string | null
          total_cost: number | null
        }
        Relationships: []
      }
      farmer_history: {
        Row: {
          farmer_id: string | null
          farmer_name: string | null
          village: string | null
          contact: string | null
          total_bookings: number | null
          completed_jobs: number | null
          total_revenue: number | null
          average_rating: number | null
          total_reviews: number | null
          last_booking_date: string | null
          customer_since: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
