// api.ts - API service functions

import axios from 'axios';
import { Job, JobAssignment, Mukkadam, AssignmentFormData, DashboardStats } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;


const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// Jobs API
export const jobsApi = {
  // Get all jobs
  getJobs: async (params?: any) => {
    const response = await api.get<Job[]>('/jobs/', { params });
    return response.data;
  },

  // Get single job
  getJob: async (id: number) => {
    const response = await api.get<Job>(`/jobs/${id}/`);
    return response.data;
  },

  // Create job
  createJob: async (data: Partial<Job>) => {
    const response = await api.post<Job>('/jobs/', data);
    return response.data;
  },

  // Update job
  updateJob: async (id: number, data: Partial<Job>) => {
    const response = await api.put<Job>(`/jobs/${id}/`, data);
    return response.data;
  },

  // Delete job
  deleteJob: async (id: number) => {
    await api.delete(`/jobs/${id}/`);
  },

  // Assign mukkadam to job
  assignMukkadam: async (jobId: number, data: AssignmentFormData) => {
    const response = await api.post(`/jobs/${jobId}/assign_mukkadam/`, data);
    return response.data;
  },

  // Get available mukkadams for job
  getAvailableMukkadams: async (jobId: number) => {
    const response = await api.get<Mukkadam[]>(`/jobs/${jobId}/available_mukkadams/`);
    return response.data;
  },

  // Update job status
  updateJobStatus: async (jobId: number, status: string) => {
    const response = await api.patch<Job>(`/jobs/${jobId}/update_status/`, { status });
    return response.data;
  },

  // Get dashboard stats
  getDashboardStats: async () => {
    const response = await api.get<DashboardStats>('/jobs/dashboard_stats/');
    return response.data;
  },
};

// Assignments API
export const assignmentsApi = {
  // Get all assignments
  getAssignments: async (params?: any) => {
    const response = await api.get<JobAssignment[]>('/assignments/', { params });
    return response.data;
  },

  // Get single assignment
  getAssignment: async (id: number) => {
    const response = await api.get<JobAssignment>(`/assignments/${id}/`);
    return response.data;
  },

  // Create assignment
  createAssignment: async (data: AssignmentFormData & { job: number }) => {
    const response = await api.post<JobAssignment>('/assignments/', data);
    return response.data;
  },

  // Update assignment
  updateAssignment: async (id: number, data: Partial<JobAssignment>) => {
    const response = await api.put<JobAssignment>(`/assignments/${id}/`, data);
    return response.data;
  },

  // Delete assignment
  deleteAssignment: async (id: number) => {
    await api.delete(`/assignments/${id}/`);
  },

  // Update assignment status
  updateAssignmentStatus: async (id: number, status: string) => {
    const response = await api.patch<JobAssignment>(`/assignments/${id}/update_status/`, { status });
    return response.data;
  },

  // Get assignment logs
  getAssignmentLogs: async (id: number) => {
    const response = await api.get(`/assignments/${id}/logs/`);
    return response.data;
  },

  // Get assignments by mukkadam
  getAssignmentsByMukkadam: async (mukkadamId: number) => {
    const response = await api.get<JobAssignment[]>('/assignments/by_mukkadam/', {
      params: { mukkadam_id: mukkadamId }
    });
    return response.data;
  },
};

// Mukkadams API
export const mukkadamsApi = {
  // Get all mukkadams
  getMukkadams: async (params?: any) => {
    const response = await api.get<Mukkadam[]>('/mukkadams/', { params });
    return response.data;
  },

  // Get single mukkadam
  getMukkadam: async (id: number) => {
    const response = await api.get<Mukkadam>(`/mukkadams/${id}/`);
    return response.data;
  },

  // Get mukkadam assignments
  getMukkadamAssignments: async (id: number) => {
    const response = await api.get<JobAssignment[]>(`/mukkadams/${id}/assignments/`);
    return response.data;
  },

  // Check mukkadam availability
  checkAvailability: async (id: number, startDate: string, endDate?: string) => {
    const response = await api.get(`/mukkadams/${id}/availability_check/`, {
      params: { start_date: startDate, end_date: endDate }
    });
    return response.data;
  },
};

export default api;