import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Users, Truck,Edit2, DollarSign,ChevronDown,ChevronUp, FileText, CheckCircle, CheckSquare,Ban,
  XCircle, TrendingUp,TrendingDown, Calendar, Filter, Search,Activity,AlertCircle,ExternalLink,
  Eye, Edit, Plus, X, MapPin, BarChart3, Clock, Layers
} from 'lucide-react';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_SUPPLY;
const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

import EditActivityModal from './UpdateEditActivity';

import { useNavigate } from 'react-router-dom';
import { getAuthToken, getAuthConfig } from './utils/auth';
import ComplexAllocationModal from './Complex';
const DEMAND_API_BASE_URL = 'https://ops.bharatintelligence.ai';
import { useAuth } from './context/auth';
import type {
  Job,

  Allocation,
  Mukkadam,
  TransportProvider,
  MukkadamAllocation,
  TransportAllocation,
  ActivityLog,
  DailyStat
} from './types/allocation';
interface Activity {
  id: string;
  is_lost:boolean;
  activity_type: string;
  activity_name: string;
  location: string;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  scheduled_date: string;
  estimated_workers: number;
  rate_per_acre: number;
  is_fully_allocated: boolean;
  allocations?: any[];
}

const AllocationDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  
// Add these state variables at the top of your component
const [editingActivity, setEditingActivity] = useState(null);
// Add these near line 25-30 where other state is defined
const [showEditActivityModal, setShowEditActivityModal] = useState(false);
const [showMarkLostModal, setShowMarkLostModal] = useState(false);
const [selectedActivityForEdit, setSelectedActivityForEdit] = useState<any>(null);
const [selectedJobForEdit, setSelectedJobForEdit] = useState<any>(null);
const [editReason, setEditReason] = useState('');
const [lostReason, setLostReason] = useState('');
const [editingJobId, setEditingJobId] = useState(null);
const [isEditModalOpen, setIsEditModalOpen] = useState(false);
// ADD these new state variables:
const [editFormData, setEditFormData] = useState({
  activity_name: '',
  total_area: 0,
  scheduled_date: '',
  total_price: 0,
   transport_cost: 0,     // ✅ NEW
  other_cost: 0,    
  rate_per_acre: 0
});
// Expandable card states
const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set());
const [expandedActivities, setExpandedActivities] = useState<Set<string>>(new Set());
const [expandedMukkadams, setExpandedMukkadams] = useState<Set<number>>(new Set());
const [expandedTransporters, setExpandedTransporters] = useState<Set<number>>(new Set());


const [selectedActivityName, setSelectedActivityName] = useState('');
const [dateSortOrder, setDateSortOrder] = useState('desc'); // 'asc' or 'desc'


// Search states
const [searchQuery, setSearchQuery] = useState('');
const [partialSearchQuery, setPartialSearchQuery] = useState('');
const [mukkadamSearchQuery, setMukkadamSearchQuery] = useState('');
const [transportSearchQuery, setTransportSearchQuery] = useState('');

const [selectedFilterDate, setSelectedFilterDate] = useState(''); // Format: YYYY-MM-DD

// Toggle functions
const toggleJob = (jobId: string) => {
  setExpandedJobs(prev => {
    const newSet = new Set(prev);
    if (newSet.has(jobId)) {
      newSet.delete(jobId);
    } else {
      newSet.add(jobId);
    }
    return newSet;
  });
};

const toggleActivity = (activityId: string) => {
  setExpandedActivities(prev => {
    const newSet = new Set(prev);
    if (newSet.has(activityId)) {
      newSet.delete(activityId);
    } else {
      newSet.add(activityId);
    }
    return newSet;
  });
};

// Helper to get the actual list of data for the table
const getAllocatedList = () => {
  return allocations.filter(allocation => {
    // Find the job for this allocation
    const job = jobs.find(j => j.work_id === allocation.farmer_work_id);
    if (!job) return false;
    
    // Check the job's status based on remaining area
    const jobStatus = calculateJobStatus(job);
    
    // Only include if job is FULLY allocated (all activities have 0 remaining area)
    if (jobStatus !== 'fully_allocated') return false;
    
    // Get payment request
    const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
    
    // ✅ EXCLUDE: If there's a payment request with pending or paid status, it belongs in Completed tab
    if (mukkadamPayment && mukkadamPayment.status === 'paid') {
      return false;
    }
    
    // ✅ INCLUDE: If status is 'allocated' and no payment request
    if (allocation.status === 'allocated' && !mukkadamPayment) {
      return true;
    }
    
    // ✅ INCLUDE: If status is 'completed' but payment was rejected (work needs to be redone)
    if (allocation.status === 'completed' && mukkadamPayment?.status === 'rejected') {
      return true;
    }
    
    // ✅ EXCLUDE: If status is 'completed' and no payment issues
    if (allocation.status === 'completed') {
      return false;
    }
    
    // Default: Include if status is 'allocated'
    return allocation.status === 'allocated';
  });
};

const getCompletedList = () => {
  return allocations.filter(allocation => {
    // Get payment request
    const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
    
    // ✅ INCLUDE: If payment request exists with pending or paid status
    if (mukkadamPayment && (mukkadamPayment.status === 'pending' || mukkadamPayment.status === 'paid')) {
      return true;
    }
    
    // ✅ INCLUDE: If status is 'completed' and payment is not rejected
    if (allocation.status === 'completed' && mukkadamPayment?.status !== 'rejected') {
      return true;
    }
    
    return false;
  });
};
// ✅ FIXED: Calculate Counts based on Unique Job IDs
const getAllocatedUniqueJobCount = () => {
  const list = getAllocatedList();
  const uniqueIds = new Set(list.map(a => a.farmer_work_id)); // Counts Job 600 only once
  return uniqueIds.size;
};

const getCompletedUniqueJobCount = () => {
  const list = getCompletedList();
  const uniqueIds = new Set(list.map(a => a.farmer_work_id));
  return uniqueIds.size;
};

const toggleMukkadam = (mukkadamId: number) => {
  setExpandedMukkadams(prev => {
    const newSet = new Set(prev);
    if (newSet.has(mukkadamId)) {
      newSet.delete(mukkadamId);
    } else {
      newSet.add(mukkadamId);
    }
    return newSet;
  });
};
// ✅ ADD: Reject payment request functions
const handleRejectMukkadamPayment = async (paymentRequestId: number) => {
  if (!confirm('Reject this payment request? The allocation will move back to Allocated tab.')) return;

  try {
    const config = getAuthConfig();
    await axios.post(
      `${API_BASE_URL_A}/ap/payment-requests/${paymentRequestId}/reject/`,
      {},
      config
    );
    alert('✅ Payment request rejected');
    // await fetchPaymentRequests();
    await refreshAllocations(); // Refresh allocations
  } catch (error) {
    console.error('Error rejecting payment:', error);
    alert('❌ Failed to reject payment request');
  }
};

const handleRejectTransportPayment = async (paymentRequestId: number) => {
  if (!confirm('Reject this transport payment request?')) return;

  try {
    const config = getAuthConfig();
    await axios.post(
      `${API_BASE_URL_A}/ap/transport-payment-requests/${paymentRequestId}/reject/`,
      {},
      config
    );
    alert('✅ Transport payment request rejected');
    // await fetchPaymentRequests();
    await refreshAllocations();
  } catch (error) {
    console.error('Error rejecting transport payment:', error);
    alert('❌ Failed to reject transport payment request');
  }
};


// ✅ FIXED: Filter based on Allocation Status or Payment Existence
const getCompletedAllocations = () => {
  return allocations.filter(allocation => {
    // 1. If the API says it's completed, show it here
    if (allocation.status === 'completed') {
      // BUT: If payment was rejected, DON'T show it here (it goes back to Allocated)
      const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
      if (mukkadamPayment?.status === 'rejected') {
        return false;
      }
      return true;
    }

    // 2. OR if a payment request exists with pending/paid status (implies work is done)
    const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
    return mukkadamPayment && (mukkadamPayment.status === 'pending' || mukkadamPayment.status === 'paid');
  });
};


// ✅ FIXED: Only show allocations for FULLY allocated jobs
// ✅ FIXED: Only show allocations for FULLY allocated jobs (0 remaining area)
const getAllocatedAllocations = () => {
  return allocations.filter(allocation => {
    // Find the job for this allocation
    const job = jobs.find(j => j.work_id === allocation.farmer_work_id);
    if (!job) return false;
    
    // Check the job's status based on remaining area
    const jobStatus = calculateJobStatus(job);
    
    // Only include if job is FULLY allocated (all activities have 0 remaining area)
    if (jobStatus !== 'fully_allocated') return false;
    
    // 1. If the allocation itself says it's allocated, show it here
    if (allocation.status === 'allocated') return true;

    // 2. Edge Case: If it's completed but the payment was rejected, move it back here
    const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
    if (allocation.status === 'completed' && mukkadamPayment?.status === 'rejected') {
        return true;
    }

    return false;
  });
};


// ✅ FIXED: Filter based on Allocation Status or Payment Existence

const toggleTransporter = (transporterId: number) => {
  setExpandedTransporters(prev => {
    const newSet = new Set(prev);
    if (newSet.has(transporterId)) {
      newSet.delete(transporterId);
    } else {
      newSet.add(transporterId);
    }
    return newSet;
  });
};
const [showEditModal, setShowEditModal] = useState(false);
const [allocationToEdit, setAllocationToEdit] = useState<Allocation | null>(null);

const [reallocating, setReallocating] = useState(false);





const [expandedSections, setExpandedSections] = useState({
  complexJobs: false,
  activityTypes: false,
  crewDistribution: false
});

const toggleSection = (section: 'complexJobs' | 'activityTypes' | 'crewDistribution') => {
  setExpandedSections(prev => ({
    ...prev,
    [section]: !prev[section]
  }));
};



  const [activeTab, setActiveTab] = useState<'overview' | 'allocated' |'completed'| 'pending' | 'partially' | 'mukkadams' | 'transport' | 'activity'| 'lost' >('overview');
  // State declarations - USE ONLY Job type (which now includes all properties)
  const [jobs, setJobs] = useState<Job[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [transportProviders, setTransportProviders] = useState<TransportProvider[]>([]);
  // const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showActiveWorkersModal, setShowActiveWorkersModal] = useState(false);
  // New metrics
  const [totalMukkadamsRegistered, setTotalMukkadamsRegistered] = useState(0);
  const [totalTransportersRegistered, setTotalTransportersRegistered] = useState(0);

  // Modal states - updated types
  const [showAllocationModal, setShowAllocationModal] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [allocating, setAllocating] = useState(false);
  const [allocationForm, setAllocationForm] = useState({
    mukkadam_id: '',
    transport_provider_id: '',
    mukkadam_price: '',
    transport_price: ''
  });

// Update your refreshAllocations to also fetch activity logs
const [activityLogs, setActivityLogs] = useState<any[]>([]);

  // Complex allocation modal states
  const [showComplexAllocationModal, setShowComplexAllocationModal] = useState(false);
  const [selectedComplexJob, setSelectedComplexJob] = useState<Job | null>(null);

  const [mukkadamAllocations, setMukkadamAllocations] = useState<MukkadamAllocation[]>([]);
  const [transportAllocations, setTransportAllocations] = useState<TransportAllocation[]>([]);


// ✅ NEW: Handle Mark Complete (Creates Payment Request)
const handleMarkComplete = async (allocationId: number) => {
  if (!confirm('Mark this work as complete? This will create a payment request and move it to the Completed tab.')) return;

  try {
    const config = getAuthConfig();
    // Your backend create method expects 'allocation_id'
    await axios.post(
      `${API_BASE_URL_A}/ap/payment-requests/`, 
      { 
        allocation_id: allocationId,
        notes: "Work completed from dashboard" 
      }, 
      config
    );
    
    alert('✅ Work marked as complete! Payment request created.');
    await refreshAllocations(); // Refresh to update the tabs
  } catch (error: any) {
    console.error('Error completing work:', error);
    const errorMsg = error.response?.data?.error || 'Failed to mark complete';
    alert(`❌ ${errorMsg}`);
  }
};

  // ✅ 1. INITIAL FETCH (Runs Once)
  useEffect(() => {
    const fetchStaticData = async () => {
      setLoading(true);
      const config = getAuthConfig();
      try {
        // Fetch SLOW static data (Jobs, Mukkadams, Providers)
        const [jobsRes, mukkadamRes, transportRes] = await Promise.all([
          axios.get(`${API_BASE_URL_A}/ap/jobs/`, config),
          axios.get(`${API_BASE_URL}/api/mukkadam/minimal_list/`),
          axios.get(`${API_BASE_URL}/api/transport-providers/dropdown_list/`)
        ]);

        setJobs(jobsRes.data);
        setMukkadams(mukkadamRes.data);
        setTransportProviders(transportRes.data);
        setTotalMukkadamsRegistered(mukkadamRes.data.length);
        setTotalTransportersRegistered(transportRes.data.length);

        // Immediately fetch dynamic data using the newly fetched static data
        await refreshAllocations(mukkadamRes.data, transportRes.data);

      } catch (error) {
        console.error('Error fetching static data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStaticData();
  }, []); // Empty dependency array = runs once

  // ✅ COMPLETE SAFE VERSION

// ✅ FIXED VERSION - Extract 'logs' from response

const refreshAllocations = async (
  currentMukkadams = mukkadams, 
  currentProviders = transportProviders
) => {
  const config = getAuthConfig();
  try {
    const [allocationsRes, activityRes, mukkadamPayRes, transportPayRes] = await Promise.all([
      axios.get(`${API_BASE_URL_A}/ap/allocations/`, config),
      axios.get(`${API_BASE_URL_A}/ap/activity-logs/`, config),
      axios.get(`${API_BASE_URL_A}/ap/payment-requests/`, config),
      axios.get(`${API_BASE_URL_A}/ap/transport-payment-requests/`, config)
    ]);

    // ✅ FIX: Extract 'logs' array from the response object
    const activityLogsArray = activityRes.data.logs || [];  // ✅ CHANGED
    
    // Safe data extraction for others
    const newAllocations = Array.isArray(allocationsRes.data) 
      ? allocationsRes.data 
      : allocationsRes.data.results || [];

    const mukkadamPayments = Array.isArray(mukkadamPayRes.data)
      ? mukkadamPayRes.data
      : mukkadamPayRes.data.results || [];

    const transportPayments = Array.isArray(transportPayRes.data)
      ? transportPayRes.data
      : transportPayRes.data.results || [];

    // Update State - All guaranteed to be arrays
    setAllocations(newAllocations);
    setActivityLogs(activityLogsArray);  // ✅ Now this is an array
    setMukkadamPaymentRequests(mukkadamPayments);
    setTransportPaymentRequests(transportPayments);

    // Re-calculate derived stats
    if (currentMukkadams.length > 0) processMukkadamAllocations(newAllocations, currentMukkadams);
    if (currentProviders.length > 0) processTransportAllocations(newAllocations, currentProviders);
    buildDailyStats(newAllocations);

  } catch (error) {
    console.error('Error refreshing allocations:', error);
    
    // ✅ Set all to empty arrays on error
    setActivityLogs([]);
    setMukkadamPaymentRequests([]);
    setTransportPaymentRequests([]);
  }
};
const [activityFilter, setActivityFilter] = useState<string>('all');

// Add to refreshAllocations



// Filter activity logs
// Filter activity logs - add safety check
const filteredActivityLogs = (Array.isArray(activityLogs) ? activityLogs : []).filter(log => {
  const searchLower = searchTerm.toLowerCase();
  const matchesSearch = 
    String(log.job_id || '').toLowerCase().includes(searchLower) ||
    String(log.mukkadam_name || '').toLowerCase().includes(searchLower) ||
    String(log.transport_name || '').toLowerCase().includes(searchLower) ||
    String(log.performed_by_name || '').toLowerCase().includes(searchLower) ||
    String(log.description || '').toLowerCase().includes(searchLower);
  
  if (!matchesSearch) return false;
  
  if (activityFilter === 'all') return true;
  if (activityFilter === 'payment') {
    return log.activity_type.includes('payment');
  }
  return log.activity_type === activityFilter;
});
 const openComplexAllocationModal = (job: Job) => {
    setSelectedComplexJob(job);
    setShowComplexAllocationModal(true);
  };

  const closeComplexAllocationModal = () => {
    setShowComplexAllocationModal(false);
    setSelectedComplexJob(null);
  };

  const handleComplexAllocationSuccess = () => {
    refreshAllocations(); // Refresh data
  };



const processMukkadamAllocations = (allocs: Allocation[], mukks: Mukkadam[]) => {
  try {
    const mukkadamMap = new Map<number, any>(); // Changed type to allow extra fields
    mukks.forEach(mukkadam => {
      const mukkadamAllocs = allocs.filter(a => a.mukkadam_id === mukkadam.id);
      
      const totalPrice = mukkadamAllocs.reduce((sum, a) => {
        const price = a.mukkadam_price ? parseFloat(String(a.mukkadam_price)) : 0;
        return sum + price;
      }, 0);

      // ✅ NEW: Calculate Paid Amount
      const paidAmount = mukkadamAllocs.reduce((sum, a) => {
        const payment = getMukkadamPaymentRequest(a.id);
        if (payment && payment.status === 'paid') {
            return sum + (a.mukkadam_price ? parseFloat(String(a.mukkadam_price)) : 0);
        }
        return sum;
      }, 0);

      mukkadamMap.set(mukkadam.id, {
        mukkadam,
        allocations: mukkadamAllocs,
        total_price: totalPrice,
        paid_amount: paidAmount, // Store it here
        job_count: mukkadamAllocs.length
      });
    });
    setMukkadamAllocations(Array.from(mukkadamMap.values()));
  } catch (error) {
    console.error('Error processing mukkadam allocations:', error);
    setMukkadamAllocations([]);
  }
};


const processTransportAllocations = (allocs: Allocation[], providers: TransportProvider[]) => {
  try {
    const transportMap = new Map<number, any>();
    providers.forEach(provider => {
      const providerAllocs = allocs.filter(a => a.transport_provider_id === provider.id);
      
      const totalPrice = providerAllocs.reduce((sum, a) => {
        const price = a.transport_price ? parseFloat(String(a.transport_price)) : 0;
        return sum + price;
      }, 0);

      // ✅ NEW: Calculate Paid Amount
      const paidAmount = providerAllocs.reduce((sum, a) => {
        const payment = getTransportPaymentRequest(a.id);
        if (payment && payment.status === 'paid') {
            return sum + (a.transport_price ? parseFloat(String(a.transport_price)) : 0);
        }
        return sum;
      }, 0);

      transportMap.set(provider.id, {
        provider,
        allocations: providerAllocs,
        total_price: totalPrice,
        paid_amount: paidAmount, // Store it here
        job_count: providerAllocs.length
      });
    });
    setTransportAllocations(Array.from(transportMap.values()));
  } catch (error) {
    console.error('Error processing transport allocations:', error);
    setTransportAllocations([]);
  }
};

const buildDailyStats = (allocs: Allocation[]) => {
  try {
    const statsByDate = new Map<string, DailyStat>();
    
    allocs.forEach(allocation => {
      // Skip if no valid date
      if (!allocation.completed_at) return;
      
      try {
        const dateObj = new Date(allocation.completed_at);
        // Check if date is valid
        if (isNaN(dateObj.getTime())) return;
        
        const date = dateObj.toISOString().split('T')[0];
        
        if (!statsByDate.has(date)) {
          statsByDate.set(date, {
            date,
            total_allocations: 0,
            total_area_allocated: 0,
            total_mukkadam_price: 0,
            total_transport_price: 0,
            allocations_by_user: {}
          });
        }
        
        const stat = statsByDate.get(date)!;
        stat.total_allocations += 1;
        
        const mukkadamPrice = allocation.mukkadam_price ? parseFloat(String(allocation.mukkadam_price)) : 0;
        const transportPrice = allocation.transport_price ? parseFloat(String(allocation.transport_price)) : 0;
        
        stat.total_mukkadam_price += mukkadamPrice;
        stat.total_transport_price += transportPrice;
        
        const userName = allocation.created_by?.username || 'Unknown';
        stat.allocations_by_user[userName] = (stat.allocations_by_user[userName] || 0) + 1;
      } catch (dateError) {
        console.error('Error processing date for allocation:', allocation.id, dateError);
      }
    });
    
    const stats = Array.from(statsByDate.values()).sort((a, b) => 
      new Date(b.date).getTime() - new Date(a.date).getTime()
    );
    setDailyStats(stats);
  } catch (error) {
    console.error('Error building daily stats:', error);
    setDailyStats([]);
  }
};

const [showJobStatusModal, setShowJobStatusModal] = useState(false);




const handleReallocate = async (allocationId: number) => {
  if (!confirm('Are you sure you want to reallocate this job? The current allocation will be deleted.')) {
    return;
  }

  setReallocating(true);
  try {
    const config = getAuthConfig();
    await axios.delete(`${API_BASE_URL_A}/ap/allocations/${allocationId}/`, config);
    
    alert('✅ Allocation removed successfully! You can now reallocate this job.');
    setAllocationToEdit(null);
  setShowEditModal(true);
    await refreshAllocations();
    
  } catch (error: any) {
    console.error('Reallocate error:', error);
    alert('Failed to reallocate: ' + (error.response?.data?.message || error.message));
  } finally {
    setReallocating(false);
  }
};




// ✅ NEW: Payment request states
  const [mukkadamPaymentRequests, setMukkadamPaymentRequests] = useState<any[]>([]);
  const [transportPaymentRequests, setTransportPaymentRequests] = useState<any[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(false);



  // ✅ NEW: Mark mukkadam payment as paid
  const handleMarkMukkadamPaid = async (paymentRequestId: number) => {
    if (!confirm('Mark this payment as PAID?')) return;

    try {
      const config = getAuthConfig();
      await axios.post(
        `${API_BASE_URL_A}/ap/payment-requests/${paymentRequestId}/mark_paid/`,
        {},
        config
      );
      alert('✅ Payment marked as PAID');
      await refreshAllocations();
      // await fetchPaymentRequests();
    } catch (error) {
      console.error('Error marking payment as paid:', error);
      alert('❌ Failed to mark payment as paid');
    }
  };

  // ✅ NEW: Mark transport payment as paid
  const handleMarkTransportPaid = async (paymentRequestId: number) => {
    if (!confirm('Mark this transport payment as PAID?')) return;

    try {
      const config = getAuthConfig();
      await axios.post(
        `${API_BASE_URL_A}/ap/transport-payment-requests/${paymentRequestId}/mark_paid/`,
        {},
        config
      );
      alert('✅ Transport payment marked as PAID');
      await refreshAllocations();
      // await fetchPaymentRequests();
    } catch (error) {
      console.error('Error marking transport payment as paid:', error);
      alert('❌ Failed to mark transport payment as paid');
    }
  };

  // ✅ NEW: Get payment request for allocation
  const getMukkadamPaymentRequest = (allocationId: number) => {
    return mukkadamPaymentRequests.find(pr => pr.allocation === allocationId);
  };

  const getTransportPaymentRequest = (allocationId: number) => {
    return transportPaymentRequests.find(pr => pr.allocation === allocationId);
  };

  // ✅ NEW: Get completed allocations (work_date < today)
  // const getCompletedAllocations = () => {
  //   const today = new Date();
  //   today.setHours(0, 0, 0, 0);

  //   return allocations.filter(allocation => {
  //     if (!allocation.work_date) return false;
  //     const workDate = new Date(allocation.work_date);
  //     return workDate < today;
  //   });
  // };


// ✅ Helper to get real-time stats for an activity
const getActivityStats = (jobId: string, activityName: string, totalArea: number) => {
  // Find all allocations for this specific job and activity
  const activityAllocations = allocations.filter(a => 
    (a.farmer_work_id === jobId || a.job_id === jobId) && 
    a.activity_name === activityName
  );

  // Sum up the allocated area
  const allocated = activityAllocations.reduce((sum, a) => sum + Number(a.allocated_area), 0);
  const remaining = totalArea - allocated;
  
  // Check if fully allocated (allow for small decimal differences)
  const isFullyAllocated = remaining <= 0.05; 

  return { allocated, remaining, isFullyAllocated, count: activityAllocations.length };
};

// ✅ IMPROVED: Calculate job status dynamically
// REPLACE WITH:
const calculateJobStatus = (job: Job): 'fully_allocated' | 'partially_allocated' | 'pending' => {
  // ✅ FILTER OUT LOST ACTIVITIES
  const activeActivities = job.activities?.filter(a => !a.is_lost) || [];
  
  if (activeActivities.length === 0) {
    return 'pending';
  }

  const totalActivities = activeActivities.length;
  let fullyAllocatedCount = 0;
  let hasAnyAllocation = false;

  activeActivities.forEach(activity => {
    const { isFullyAllocated, allocated } = getActivityStats(job.work_id, activity.activity_name, activity.total_area);
    
    if (isFullyAllocated) fullyAllocatedCount++;
    if (allocated > 0) hasAnyAllocation = true;
  });

  if (fullyAllocatedCount === totalActivities) return 'fully_allocated';
  if (hasAnyAllocation) return 'partially_allocated';
  return 'pending';
};

// ✅ UPDATE: Use calculated status instead of job.status
const allocatedJobs = jobs.filter(j => calculateJobStatus(j) === 'fully_allocated');
const partiallyAllocatedJobs = jobs.filter(j => calculateJobStatus(j) === 'partially_allocated');
const pendingJobs = jobs.filter(j => calculateJobStatus(j) === 'pending');

// ✅ ADD: Enhanced Revenue & Payment Stats
const calculateRevenueStats = () => {
  let totalRevenue = 0;
  let profitableCount = 0;
  let lossCount = 0;
  let lowMarginCount = 0;

  // New variables for actual payments
  let paidMukkadamAmount = 0;
  let paidTransportAmount = 0;

allocations.forEach(allocation => {
  // 1. Calculate Revenue & Profitability
  const job = jobs.find((j: any) => j.work_id === allocation.farmer_work_id);
  if (job) {
    const activity = job.activities?.find((a: any) => 
      a.activity_name === allocation.activity_name
    );
    
    if (activity) {
      // ✅ SKIP IF ACTIVITY IS LOST
      if (activity.is_lost) {
        return; // Don't include in revenue calculations
      }
      
      const revenue = activity.total_price || 0;
      totalRevenue += revenue;

      const cost = parseFloat(String(allocation.mukkadam_price || '0')) + 
                   parseFloat(String(allocation.transport_price || '0'));
      const profit = revenue - cost;
      const margin = revenue > 0 ? (profit / revenue) * 100 : 0;

      if (profit > 0) profitableCount++;
      if (profit < 0) lossCount++;
      if (profit >= 0 && margin < 20) lowMarginCount++;
    }
  }

  // 2. Calculate Actual Paid Amounts (existing logic - keep as is)
  const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
  if (mukkadamPayment && mukkadamPayment.status === 'paid') {
    paidMukkadamAmount += parseFloat(String(allocation.mukkadam_price || '0'));
  }

  const transportPayment = getTransportPaymentRequest(allocation.id);
  if (transportPayment && transportPayment.status === 'paid') {
    paidTransportAmount += parseFloat(String(allocation.transport_price || '0'));
  }
});

  const totalAllocatedMukkadam = allocations.reduce((sum, a) => sum + parseFloat(String(a.mukkadam_price || '0')), 0);
  const totalAllocatedTransport = allocations.reduce((sum, a) => sum + parseFloat(String(a.transport_price || '0')), 0);
  const totalCosts = totalAllocatedMukkadam + totalAllocatedTransport;
  
  const netProfit = totalRevenue - totalCosts;
  const profitMargin = totalRevenue > 0 ? (netProfit / totalRevenue) * 100 : 0;

  return {
    totalRevenue,
    netProfit,
    profitMargin,
    profitableAllocations: profitableCount,
    lossAllocations: lossCount,
    lowMarginAllocations: lowMarginCount,
    // New stats
    paidMukkadamAmount,
    paidTransportAmount
  };
};

// ✅ Calculate all stats
const revenueStats = calculateRevenueStats();
const stats = {
  totalJobs: jobs.length,
  allocatedJobs: getAllocatedUniqueJobCount(),  // ✅ Count unique jobs
  completedJobs: getCompletedUniqueJobCount(),  // ✅ Count unique jobs
  partiallyAllocatedJobs: partiallyAllocatedJobs.length,
  pendingJobs: pendingJobs.filter(job => {
    const nonLostActivities = job.activities?.filter(a => !a.is_lost) || [];
    return nonLostActivities.length > 0;
  }).length,
  totalMukkadamPayout: allocations.reduce((sum, a) => 
    sum + parseFloat(String(a.mukkadam_price || '0')), 0
  ),
  totalTransportPayout: allocations.reduce((sum, a) => 
    sum + parseFloat(String(a.transport_price || '0')), 0
  ),
  totalPayout: allocations.reduce((sum, a) => 
    sum + parseFloat(String(a.mukkadam_price || '0')) + parseFloat(String(a.transport_price || '0')), 0
  ),
  // ✅ Add revenue stats
  totalRevenue: revenueStats.totalRevenue,
  netProfit: revenueStats.netProfit,
  profitMargin: revenueStats.profitMargin,
  profitableAllocations: revenueStats.profitableAllocations,
  lossAllocations: revenueStats.lossAllocations,
  lowMarginAllocations: revenueStats.lowMarginAllocations,
  // ✅ NEW: Actual Paid Amounts
  paidMukkadamAmount: revenueStats.paidMukkadamAmount,
  paidTransportAmount: revenueStats.paidTransportAmount,
};

const getActivePendingJobsCount = () => {
  return pendingJobs.filter(job => {
    const nonLostActivities = job.activities?.filter(a => !a.is_lost) || [];
    return nonLostActivities.length > 0;
  }).length;
};
// const filteredActivityLogs = activityLogs.filter(log => {
//   const searchLower = searchTerm.toLowerCase();
//   return (
//     String(log.job_id || '').toLowerCase().includes(searchLower) ||
//     String(log.mukkadam_name || '').toLowerCase().includes(searchLower) ||
//     String(log.transport_name || '').toLowerCase().includes(searchLower) ||
//     String(log.user_name || '').toLowerCase().includes(searchLower)
//   );
// });



  const closeAllocationModal = () => {
    setShowAllocationModal(false);
    setSelectedJob(null);
    setAllocationForm({
      mukkadam_id: '',
      transport_provider_id: '',
      mukkadam_price: '',
      transport_price: ''
    });
  };

  const handleAllocationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJob) return;

    if (!allocationForm.mukkadam_id || !allocationForm.transport_provider_id) {
      alert('Please select both mukkadam and transport provider');
      return;
    }
    if (!allocationForm.mukkadam_price || !allocationForm.transport_price) {
      alert('Please enter both prices');
      return;
    }

    setAllocating(true);

    try {
      const payload = {
        farmer_work_id: selectedJob.work_id,
        mukkadam_id: parseInt(allocationForm.mukkadam_id),
        transport_provider_id: parseInt(allocationForm.transport_provider_id),
        mukkadam_price: parseFloat(allocationForm.mukkadam_price),
        transport_price: parseFloat(allocationForm.transport_price)
      };
      const config = getAuthConfig();
      await axios.post(`${API_BASE_URL_A}/ap/allocations/`, payload, config);
      
      alert('Job allocated successfully! ✅');
      closeAllocationModal();
      await refreshAllocations();
      
    } catch (error: any) {
      console.error('Allocation error:', error);
      alert('Failed to allocate job: ' + (error.response?.data?.message || error.message));
    } finally {
      setAllocating(false);
    }
  };

  const selectedMukkadam = mukkadams.find(m => m.id === parseInt(allocationForm.mukkadam_id));
  const selectedProvider = transportProviders.find(p => p.id === parseInt(allocationForm.transport_provider_id));

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // Calculate active workers (only count allocations where work_date >= today)
const today = new Date();
today.setHours(0, 0, 0, 0); // Reset time to start of day

const activeAllocations = allocations.filter(a => {
  if (!a.work_date) return false;
  const workDate = new Date(a.work_date);
  workDate.setHours(0, 0, 0, 0);
  return workDate >= today;
});

const totalActiveWorkers = activeAllocations.reduce((sum, a) => {
  return sum + (a.crew_size || 0);
}, 0);

// Group by mukkadam for detailed view
const workersByMukkadam = activeAllocations.reduce((acc, allocation) => {
  const mukkadamId = allocation.mukkadam_id;
  if (!acc[mukkadamId]) {
    const mukkadam = mukkadams.find(m => m.id === mukkadamId);
    acc[mukkadamId] = {
      mukkadam: mukkadam,
      allocations: [],
      totalWorkers: 0
    };
  }
  acc[mukkadamId].allocations.push(allocation);
  acc[mukkadamId].totalWorkers += (allocation.crew_size || 0);
  return acc;
}, {} as Record<number, {mukkadam: Mukkadam | undefined, allocations: Allocation[], totalWorkers: number}>);

const workerDetails = Object.values(workersByMukkadam).sort((a, b) => b.totalWorkers - a.totalWorkers);


// Filter partially allocated jobs
const filteredPartiallyAllocatedJobs = partiallyAllocatedJobs.filter(job => {
  const searchLower = partialSearchQuery.toLowerCase();
  
  const matchesJob = String(job.work_id || '').toLowerCase().includes(searchLower) ||
                     String(job.title || '').toLowerCase().includes(searchLower) ||
                     String(job.description || '').toLowerCase().includes(searchLower);
  
  const matchesActivity = job.activities?.some(activity => 
    String(activity.activity_name || '').toLowerCase().includes(searchLower) ||
    String(activity.location || '').toLowerCase().includes(searchLower)
  );
  
  const matchesMukkadam = job.activities?.some(activity =>
    activity.allocations?.some((alloc: any) =>
      String(alloc.mukkadam_name || '').toLowerCase().includes(searchLower)
    )
  );
  
  return matchesJob || matchesActivity || matchesMukkadam;
});

// Filter mukkadams
const filteredMukkadamAllocations = mukkadamAllocations.filter(ma => {
  const searchLower = mukkadamSearchQuery.toLowerCase();
  
  // 1. Permanent Check
  const isPermanent = ma.mukkadam.is_permanent === true;
  if (!isPermanent) return false; // Immediately exclude if not permanent

  // 2. Search Logic
  const matchesSearch = 
    String(ma.mukkadam.mukkadam_name || '').toLowerCase().includes(searchLower) ||
    String(ma.mukkadam.village || '').toLowerCase().includes(searchLower) ||
    String(ma.mukkadam.mobile_numbers || '').includes(searchLower) ||
    ma.allocations.some(a => String(a.farmer_work_id || '').toLowerCase().includes(searchLower));

  return matchesSearch;
});

// Filter transport providers
const filteredTransportAllocations = transportAllocations.filter(ta => {
  const searchLower = transportSearchQuery.toLowerCase();
  
  return String(ta.provider.name || '').toLowerCase().includes(searchLower) ||
         String(ta.provider.base_location || '').toLowerCase().includes(searchLower) ||
         String(ta.provider.contact_number || '').includes(searchLower) ||
         ta.allocations.some(a => String(a.farmer_work_id || '').toLowerCase().includes(searchLower));
});


// Add this function to handle opening the edit modal
// REPLACE the entire handleEditActivity function with this:
const handleEditActivity = async (activity: any, jobId: string) => {
  if (!editReason.trim()) {
    alert('❌ Please provide a reason for editing');
    return;
  }

  try {
    const config = getAuthConfig();
    await axios.patch(
      `${API_BASE_URL_A}/ap/edit-activity/`,
      {
        job_id: jobId,
        activity_id: activity.activity_id,
        reason: editReason,
        updates: {
          activity_name: editFormData.activity_name,
          total_area: editFormData.total_area,
          transport_cost:editFormData.transport_cost,
          other_cost :editFormData.transport_cost,
          scheduled_datetime: editFormData.scheduled_date,
          total_price: editFormData.total_price,
          rate_per_acre: editFormData.rate_per_acre
        }
      },
      config
    );
    
    alert('✅ Activity updated successfully!');
    setShowEditActivityModal(false);
    setEditReason('');
    setSelectedActivityForEdit(null);
    setEditFormData({
      activity_name: '',
      total_area: 0,
      scheduled_date: '',
      total_price: 0,
      transport_cost:0,
      other_cost:0,
      rate_per_acre: 0
    });
    await refreshAllocations();
  } catch (error: any) {
    console.error('Error editing activity:', error);
    alert(`❌ ${error.response?.data?.error || 'Failed to edit activity'}`);
  }
};
// ✅ NEW: Mark Activity Lost
// UPDATE handleMarkActivityLost function (around line 470):

const handleMarkActivityLost = async (activity: any, jobId: string) => {
  if (!lostReason.trim()) {
    alert('❌ Please provide a reason for marking as lost');
    return;
  }

  if (!confirm(`Mark "${activity.activity_name}" as LOST? This will exclude it from revenue calculations.`)) {
    return;
  }

  try {
    const config = getAuthConfig();
    await axios.post(
      `${API_BASE_URL_A}/ap/mark-activity-lost/`,
      {
        job_id: jobId,
        activity_id: activity.activity_id,
        reason: lostReason,
        // ✅ PASS ACTIVITY DATA for DB creation if missing
        activity_name: activity.activity_name,
        total_area: activity.total_area,
        total_price: activity.total_price
      },
      config
    );
    
    alert('✅ Activity marked as lost');
    setShowMarkLostModal(false);
    setLostReason('');
    setSelectedActivityForEdit(null);
    await refreshAllocations();
  } catch (error: any) {
    console.error('Error marking lost:', error);
    alert(`❌ ${error.response?.data?.error || 'Failed to mark as lost'}`);
  }
};
// ✅ NEW: Unmark Activity Lost
const handleUnmarkActivityLost = async (activity: any, jobId: string) => {
  const reason = prompt('Reason for restoring this activity:');
  if (!reason?.trim()) {
    alert('❌ Reason is required');
    return;
  }

  try {
    const config = getAuthConfig();
    await axios.post(
      `${API_BASE_URL_A}/ap/unmark-activity-lost/`,
      {
        job_id: jobId,
        activity_id: activity.activity_id,
        reason: reason
      },
      config
    );
    
    alert('✅ Activity restored successfully');
    await refreshAllocations();
  } catch (error: any) {
    console.error('Error unmarking lost:', error);
    alert(`❌ ${error.response?.data?.error || 'Failed to restore activity'}`);
  }
};

// Add this function to handle successful save and refresh
const handleSaveSuccess = async () => {
  console.log('✅ Activity updated, refreshing jobs...');
  // Refetch jobs from API
   getAllocatedAllocations(); // Call your existing function that fetches jobs
  
  // Optional: Show success toast
  // toast.success('Activity updated successfully!');
};


  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Allocation Dashboard</h1>
          <p className="text-gray-600 mt-1">Manage work allocations, mukkadams, and transport providers</p>
        </div>


        {/* Tabs */}
        <div className="bg-white rounded-xl shadow-lg mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px overflow-x-auto">
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === 'overview'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <FileText className="inline-block mr-2" size={18} />
                Overview
              </button>
      <button
    onClick={() => setActiveTab('allocated')}
    className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
      activeTab === 'allocated'
        ? 'border-green-500 text-green-600'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
    }`}
  >
    <CheckCircle className="inline-block mr-2" size={18} />
    {/* ✅ Shows Unique Jobs Count (2) */}
    Allocated ({getAllocatedUniqueJobCount()}) 
  </button>

  <button
    onClick={() => setActiveTab('completed')}
    className={`px-6 py-4 font-medium transition flex items-center ${
      activeTab === 'completed'
        ? 'border-b-2 border-purple-600 text-purple-600'
        : 'text-gray-600 hover:text-gray-900'
    }`}
  >
    <CheckSquare size={18} className="mr-2" />
    {/* ✅ Shows Unique Jobs Count (1) */}
    Completed ({getCompletedUniqueJobCount()}) 
  </button>
<button
  onClick={() => setActiveTab('partially')}
  className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
    activeTab === 'partially'
      ? 'border-orange-500 text-orange-600'
      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
  }`}
>
  <TrendingUp className="inline-block mr-2" size={18} />
  Partially Allocated ({stats.partiallyAllocatedJobs})
</button>
              <button
  onClick={() => setActiveTab('pending')}
  className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
    activeTab === 'pending'
      ? 'border-yellow-500 text-yellow-600'
      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
  }`}
>
  <XCircle className="inline-block mr-2" size={18} />
  Pending ({getActivePendingJobsCount()})
</button>

              <button
  onClick={() => setActiveTab('lost')}
  className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
    activeTab === 'lost'
      ? 'border-red-500 text-red-600'
      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
  }`}
>
  <Ban className="inline-block mr-2" size={18} />
  Lost Jobs ({jobs.filter(j => j.activities?.some(a => a.is_lost)).length})
</button>
              <button
                onClick={() => setActiveTab('mukkadams')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === 'mukkadams'
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Users className="inline-block mr-2" size={18} />
                Mukkadams ({mukkadams.filter(m => m.is_permanent).length})
              </button>
              <button
                onClick={() => setActiveTab('transport')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === 'transport'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Truck className="inline-block mr-2" size={18} />
                Transport ({transportProviders.length})
              </button>
              <button
                onClick={() => setActiveTab('activity')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === 'activity'
                    ? 'border-pink-500 text-pink-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Activity className="inline-block mr-2" size={18} />
                Activity Log ({activityLogs.length})
              </button>

              {/* <button
                onClick={() => setActiveTab('analytics')}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === 'analytics'
                    ? 'border-teal-500 text-teal-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <BarChart3 className="inline-block mr-2" size={18} />
                Analytics
              </button> */}
            </nav>
          </div>

          {/* Search Bar */}
          {/* {( activeTab === 'activity') && (
            <div className="p-4 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute left-3 top-3 text-gray-400" size={20} />
                <input
                  type="text"
                  placeholder={
                    activeTab === 'activity' 
                      ? "Search by job ID, mukkadam, transport, or user..." 
                      : "Search by job ID or title..."
                  }
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          )} */}

          {/* Tab Content */}
          <div className="p-6">
            {/* Tab Content */}


            

  
                {activeTab === 'overview' && (
                <div className="space-y-6">
                    
                    {/* Top Alert Banner */}
                    {pendingJobs.length > 0 && (
                    <div className="bg-gradient-to-r from-yellow-50 to-orange-50 border-l-4 border-yellow-500 p-4 rounded-lg">
                        <div className="flex items-center justify-between">
                        <div className="flex items-center">
                            <AlertCircle className="text-yellow-600 mr-3" size={24} />
                            <div>
                            <h3 className="font-bold text-gray-900">Action Required</h3>
                            <p className="text-sm text-gray-700">
                                You have <strong>{pendingJobs.length} pending job{pendingJobs.length > 1 ? 's' : ''}</strong> and{' '}
                                <strong>{partiallyAllocatedJobs.length} partially allocated job{partiallyAllocatedJobs.length !== 1 ? 's' : ''}</strong> waiting for allocation
                            </p>
                            </div>
                        </div>
                        <button
                            onClick={() => setActiveTab('pending')}
                            className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 font-medium transition"
                        >
                            View Pending Jobs
                        </button>
                        </div>
                    </div>
                    )}

                    {/* Quick Stats Grid - 6 Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">

                        {/* Total Mukkadams */}
                <div 
                    className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white p-4 rounded-xl shadow-lg hover:shadow-2xl transition cursor-pointer"
                    onClick={() => setActiveTab('mukkadams')}
                >
                    <div className="flex items-center justify-between mb-2">
                    <Users size={24} className="opacity-90" />
                    <span className="text-2xl font-bold">{totalMukkadamsRegistered}</span>
                    </div>
                    <p className="text-xs font-medium opacity-90">Total Mukkadams</p>
                    <p className="text-xs opacity-75 mt-1">
                    {workerDetails.length} active
                    </p>
                </div>

                {/* Job Status Modal */}
                {showJobStatusModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                    {/* Modal Header */}
                    <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
                        <div>
                        <h2 className="text-2xl font-bold text-white">All Jobs Status</h2>
                        <p className="text-white text-sm opacity-90">{jobs.length} total jobs</p>
                        </div>
                        <button
                        onClick={() => setShowJobStatusModal(false)}
                        className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-full transition"
                        >
                        <X size={24} />
                        </button>
                    </div>

                    {/* Modal Content */}
                    <div className="p-6">
                        {/* Summary Cards */}
                        <div className="grid grid-cols-4 gap-4 mb-6">
                        <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                            <p className="text-sm text-gray-600">Allocated</p>
                            <p className="text-3xl font-bold text-green-600">{allocatedJobs.length}</p>
                        </div>
                        <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                            <p className="text-sm text-gray-600">Partial</p>
                            <p className="text-3xl font-bold text-orange-600">{partiallyAllocatedJobs.length}</p>
                        </div>
                        <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                            <p className="text-sm text-gray-600">Pending</p>
                            <p className="text-3xl font-bold text-yellow-600">{pendingJobs.length}</p>
                        </div>
                        <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                            <p className="text-sm text-gray-600">Complex</p>
                            <p className="text-3xl font-bold text-blue-600">{jobs.filter(j => j.is_complex).length}</p>
                        </div>
                        </div>

                        {/* Jobs List */}
                        <div className="space-y-3">
                        {jobs.map(job => {
                            const statusColor = 
                            job.status === 'fully_allocated' || allocations.some(a => a.farmer_work_id === job.work_id)
                                ? 'green' :
                            job.status === 'partially_allocated' 
                                ? 'orange' : 
                                'yellow';
                            
                            const statusText = 
                            job.status === 'fully_allocated' || (!job.is_complex && allocations.some(a => a.farmer_work_id === job.work_id))
                                ? 'Allocated' :
                            job.status === 'partially_allocated' 
                                ? 'Partially Allocated' : 
                                'Pending';

                            return (
                            <div key={job.id} className={`p-4 rounded-lg border-2 border-${statusColor}-200 bg-${statusColor}-50`}>
                                <div className="flex justify-between items-start">
                                <div className="flex-1">
                                    <div className="flex items-center space-x-2 mb-2">
                                    <span className="font-mono text-sm font-bold text-blue-600">{job.work_id}</span>
                                    <span className={`px-2 py-1 bg-${statusColor}-500 text-white rounded-full text-xs font-bold`}>
                                        {statusText}
                                    </span>
                                    {job.is_complex && (
                                        <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-semibold">
                                        Complex
                                        </span>
                                    )}
                                    </div>
                                    <p className="text-sm font-semibold text-gray-900">{job.title}</p>
                                    {job.is_complex && job.activities && (
                                    <p className="text-xs text-gray-600 mt-1">
                                        {job.activities.filter(a => a.is_fully_allocated).length} of {job.activities.length} activities allocated
                                    </p>
                                    )}
                                </div>
                                <button
                                    onClick={() => {
                                    setShowJobStatusModal(false);
                                    if (statusText === 'Pending') setActiveTab('pending');
                                    else if (statusText === 'Partially Allocated') setActiveTab('partially');
                                    else setActiveTab('allocated');
                                    }}
                                    className="ml-4 px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 text-xs font-medium"
                                >
                                    View Details
                                </button>
                                </div>
                            </div>
                            );
                        })}
                        </div>
                    </div>

                    {/* Modal Footer */}
                    <div className="bg-gray-50 px-6 py-4 border-t sticky bottom-0">
                        <button
                        onClick={() => setShowJobStatusModal(false)}
                        className="w-full px-6 py-3 bg-gray-600 text-white rounded-lg font-semibold hover:bg-gray-700 transition"
                        >
                        Close
                        </button>
                    </div>
                    </div>
                </div>
                )}

                {/* Total Transporters */}
                <div 
                    className="bg-gradient-to-br from-orange-500 to-red-600 text-white p-4 rounded-xl shadow-lg hover:shadow-2xl transition cursor-pointer"
                    onClick={() => setActiveTab('transport')}
                >
                    <div className="flex items-center justify-between mb-2">
                    <Truck size={24} className="opacity-90" />
                    <span className="text-2xl font-bold">{totalTransportersRegistered}</span>
                    </div>
                    <p className="text-xs font-medium opacity-90">Total Transporters</p>
                    <p className="text-xs opacity-75 mt-1">
                    {transportAllocations.filter(t => t.job_count > 0).length} active
                    </p>
                </div>

                {/* Total Jobs - with modal */}
                <div 
                    className="bg-white p-4 rounded-xl shadow-md border-l-4 border-blue-500 hover:shadow-lg transition cursor-pointer" 
                    onClick={() => setShowJobStatusModal(true)}
                >
                    <div className="flex items-center justify-between mb-2">
                    <FileText className="text-blue-600" size={24} />
                    <span className="text-2xl font-bold text-gray-900">{jobs.length}</span>
                    </div>
                    <p className="text-xs text-gray-600 font-medium">Total Jobs</p>
                    <p className="text-xs text-blue-600 mt-1">
                    {jobs.filter(j => j.is_complex).length} complex
                    </p>
                </div>
                    {/* Total Jobs
                    <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-blue-500 hover:shadow-lg transition cursor-pointer" onClick={() => setActiveTab('pending')}>
                        <div className="flex items-center justify-between mb-2">
                        <FileText className="text-blue-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">{jobs.length}</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Total Jobs</p>
                        <p className="text-xs text-blue-600 mt-1">
                        {jobs.filter(j => j.is_complex).length} complex
                        </p>
                    </div> */}

                    {/* Allocated */}
                    <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-green-500 hover:shadow-lg transition cursor-pointer" onClick={() => setActiveTab('allocated')}>
                        <div className="flex items-center justify-between mb-2">
                        <CheckCircle className="text-green-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">{allocatedJobs.length}</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Allocated</p>
                        <p className="text-xs text-green-600 mt-1">
                        {jobs.length > 0 ? ((allocatedJobs.length / jobs.length) * 100).toFixed(0) : 0}% complete
                        </p>
                    </div>

                    {/* Partially Allocated */}
                    <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-orange-500 hover:shadow-lg transition cursor-pointer" onClick={() => setActiveTab('partially')}>
                        <div className="flex items-center justify-between mb-2">
                        <TrendingUp className="text-orange-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">{partiallyAllocatedJobs.length}</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Partially allocated</p>
                        <p className="text-xs text-orange-600 mt-1">Need attention</p>
                    </div>

                    {/* Pending */}
                    <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-yellow-500 hover:shadow-lg transition cursor-pointer" onClick={() => setActiveTab('pending')}>
                        <div className="flex items-center justify-between mb-2">
                        <Clock className="text-yellow-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">{pendingJobs.length}</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Pending</p>
                        <p className="text-xs text-yellow-600 mt-1">
                        {jobs.length > 0 ? ((pendingJobs.length / jobs.length) * 100).toFixed(0) : 0}% remaining
                        </p>
                    </div>

                    {/* Active Workers */}
                    {/* <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-teal-500 hover:shadow-lg transition cursor-pointer" onClick={() => setShowActiveWorkersModal(true)}>
                        <div className="flex items-center justify-between mb-2">
                        <Users className="text-teal-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">{totalActiveWorkers}</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Active Workers</p>
                        <p className="text-xs text-teal-600 mt-1">
                        {activeAllocations.length} jobs
                        </p>
                    </div>

                   
                    <div className="bg-white p-4 rounded-xl shadow-md border-l-4 border-purple-500 hover:shadow-lg transition">
                        <div className="flex items-center justify-between mb-2">
                        <DollarSign className="text-purple-600" size={24} />
                        <span className="text-2xl font-bold text-gray-900">₹{(stats.totalPayout / 1000).toFixed(0)}K</span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium">Total Payout</p>
                        <p className="text-xs text-purple-600 mt-1">
                        {allocations.length} allocations
                        </p>
                    </div> */}
                    </div>

                    {/* Main Content Grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    
                    {/* Left Column - 2/3 width */}
                    <div className="lg:col-span-2 space-y-6">
                        
                        {/* Allocation Progress Chart */}
                        <div className="bg-white rounded-xl shadow-lg p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                            <BarChart3 className="mr-2 text-blue-600" />
                            Allocation Progress
                        </h3>
                        
                        {/* Progress Bar */}
                        <div className="mb-6">
                            <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-600">Overall Completion</span>
                            <span className="font-bold text-blue-600">
                                {jobs.length > 0 ? ((allocatedJobs.length / jobs.length) * 100).toFixed(1) : 0}%
                            </span>
                            </div>
                            <div className="bg-gray-200 rounded-full h-6 overflow-hidden">
                            <div className="h-full flex">
                                <div 
                                className="bg-green-500 flex items-center justify-center text-xs text-white font-semibold transition-all"
                                style={{ width: `${jobs.length > 0 ? (allocatedJobs.length / jobs.length) * 100 : 0}%` }}
                                >
                                {allocatedJobs.length > 0 && `${allocatedJobs.length} Allocated`}
                                </div>
                                <div 
                                className="bg-orange-500 flex items-center justify-center text-xs text-white font-semibold transition-all"
                                style={{ width: `${jobs.length > 0 ? (partiallyAllocatedJobs.length / jobs.length) * 100 : 0}%` }}
                                >
                                {partiallyAllocatedJobs.length > 0 && `${partiallyAllocatedJobs.length} Partial`}
                                </div>
                                <div 
                                className="bg-yellow-400 flex items-center justify-center text-xs text-white font-semibold transition-all"
                                style={{ width: `${jobs.length > 0 ? (pendingJobs.length / jobs.length) * 100 : 0}%` }}
                                >
                                {pendingJobs.length > 0 && `${pendingJobs.length} Pending`}
                                </div>
                            </div>
                            </div>
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-3 gap-4">
                            <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                            <p className="text-xs text-gray-600 mb-1">Completed</p>
                            <p className="text-2xl font-bold text-green-600">{allocatedJobs.length}</p>
                            <p className="text-xs text-green-600 mt-1">
                                {jobs.length > 0 ? ((allocatedJobs.length / jobs.length) * 100).toFixed(0) : 0}%
                            </p>
                            </div>
                            <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                            <p className="text-xs text-gray-600 mb-1">In Progress</p>
                            <p className="text-2xl font-bold text-orange-600">{partiallyAllocatedJobs.length}</p>
                            <p className="text-xs text-orange-600 mt-1">
                                {jobs.length > 0 ? ((partiallyAllocatedJobs.length / jobs.length) * 100).toFixed(0) : 0}%
                            </p>
                            </div>
                            <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                            <p className="text-xs text-gray-600 mb-1">Pending</p>
                            <p className="text-2xl font-bold text-yellow-600">{pendingJobs.length}</p>
                            <p className="text-xs text-yellow-600 mt-1">
                                {jobs.length > 0 ? ((pendingJobs.length / jobs.length) * 100).toFixed(0) : 0}%
                            </p>
                            </div>
                        </div>
                        </div>

{/* Recent Activity Feed - FIXED */}
<div className="bg-white rounded-xl shadow-lg p-6">
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-lg font-bold text-gray-900 flex items-center">
      <Activity className="mr-2 text-pink-600" />
      Recent Activity
    </h3>
    <button
      onClick={() => setActiveTab('activity')}
      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
    >
      View All →
    </button>
  </div>
  
  <div className="space-y-3">
    {activityLogs.slice(0, 5).map((log, index) => {
      // 1. Safe Price Calculation
      const mukkadamPrice = Number(log.mukkadam_price ?? log.metadata?.mukkadam_price ?? 0);
      const transportPrice = Number(log.transport_price ?? log.metadata?.transport_price ?? 0);
      
      // Use 'amount' if available (for payments), otherwise calculated total
      const displayAmount = Number(log.amount ?? (mukkadamPrice + transportPrice));

      // 2. Determine Transport Name safely
      let transportName = 'Unknown';
      const transportType = log.transport_type ?? log.metadata?.transport_type;
      
      if (transportType === 'none') {
        transportName = 'No Transport';
      } else if (transportType === 'own') {
        transportName = 'Own Transport';
      } else {
        transportName = log.transport_name || 'Unknown Provider';
      }

      // 3. Determine Icon Color
      let iconColorClass = 'bg-gray-100 text-gray-600';
      if (index === 0) iconColorClass = 'bg-green-100 text-green-600';
      else if (index === 1) iconColorClass = 'bg-blue-100 text-blue-600';
      else if (index === 2) iconColorClass = 'bg-purple-100 text-purple-600';

      return (
        <div 
          key={log.id} 
          className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition cursor-pointer"
          onClick={() => {
             // Optional: Navigate to detail on click
             if (log.allocation_id) navigate(`/allocations/${log.allocation_id}`);
          }}
        >
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${iconColorClass}`}>
            <CheckCircle size={16} />
          </div>
          
          <div className="flex-1 min-w-0">
            {/* Title Line */}
            <p className="text-sm font-semibold text-gray-900 truncate">
              {log.activity_type_display || log.activity_type?.replace(/_/g, ' ') || 'Activity'} 
              <span className="font-normal text-gray-500 ml-1">
                 - {log.job_id}
              </span>
            </p>

            {/* Subtitle / Description */}
            <p className="text-xs text-gray-600 mt-1 truncate">
              {log.description || (
                 <>
                   Allocated to <span className="font-semibold">{log.mukkadam_name || 'Unknown'}</span> • 
                   Transport: <span className="font-semibold">{transportName}</span>
                 </>
              )}
            </p>

            {/* Footer Line: Date & Price */}
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-gray-500">
                {log.timestamp || log.performed_at 
                  ? new Date(log.timestamp || log.performed_at).toLocaleDateString('en-IN', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : 'Just now'}
              </span>
              
              {/* ✅ Safe Price Display */}
              {displayAmount > 0 && (
                <span className="text-xs font-bold text-purple-600">
                  ₹{displayAmount.toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
      );
    })}
    
    {activityLogs.length === 0 && (
      <p className="text-center text-gray-500 py-8">No recent activity</p>
    )}
  </div>
</div>
                        {/* ✅ Enhanced Financial Summary with Revenue & P/L */}
<div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl shadow-lg p-6 border border-purple-200">
  <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
    <DollarSign className="mr-2 text-purple-600" />
    Financial Summary & P/L Analysis
  </h3>
  
  {/* Revenue & Costs Row */}
  <div className="grid grid-cols-3 gap-4 mb-4">
    {/* Total Revenue */}
    <div className="bg-white p-4 rounded-lg border-2 border-green-300">
      <p className="text-sm text-gray-600 mb-2 flex items-center">
        <TrendingUp size={16} className="mr-1 text-green-600" />
        Total Revenue
      </p>
      <p className="text-2xl font-bold text-green-600">
        ₹{stats.totalRevenue.toLocaleString()}
      </p>
      <p className="text-xs text-gray-500 mt-1">
        From {allocations.length} jobs
      </p>
    </div>

    {/* Mukkadam Costs */}
    <div className="bg-white p-4 rounded-lg border border-gray-200 relative">
      <p className="text-sm text-gray-600 mb-2">Mukkadam Costs</p>
      <div className="flex items-baseline space-x-2">
        <p className="text-2xl font-bold text-blue-600">
            ₹{stats.totalMukkadamPayout.toLocaleString()}
        </p>
        <span className="text-xs font-medium text-gray-400">allocated</span>
      </div>
      
      {/* ✅ Paid Amount Badge */}
      <div className="mt-2 flex items-center bg-blue-50 px-2 py-1 rounded text-xs">
        <CheckCircle size={12} className="text-blue-600 mr-1" />
        <span className="font-semibold text-blue-700">
            ₹{stats.paidMukkadamAmount.toLocaleString()} Paid
        </span>
      </div>
    </div>

    {/* Transport Costs */}
    <div className="bg-white p-4 rounded-lg border border-gray-200 relative">
      <p className="text-sm text-gray-600 mb-2">Transport Costs</p>
      <div className="flex items-baseline space-x-2">
        <p className="text-2xl font-bold text-orange-600">
            ₹{stats.totalTransportPayout.toLocaleString()}
        </p>
        <span className="text-xs font-medium text-gray-400">allocated</span>
      </div>

      {/* ✅ Paid Amount Badge */}
      <div className="mt-2 flex items-center bg-orange-50 px-2 py-1 rounded text-xs">
        <CheckCircle size={12} className="text-orange-600 mr-1" />
        <span className="font-semibold text-orange-700">
            ₹{stats.paidTransportAmount.toLocaleString()} Paid
        </span>
      </div>
    </div>
  </div>

  {/* Profit/Loss Summary (Unchanged) */}
  <div className="mb-4">
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <p className="text-sm text-gray-600 mb-2">Total Allocated Costs</p>
        <p className="text-2xl font-bold text-purple-600">
          ₹{stats.totalPayout.toLocaleString()}
        </p>
        <div className="mt-1 flex items-center text-xs text-purple-600">
            <CheckSquare size={12} className="mr-1" />
            Total Paid: ₹{(stats.paidMukkadamAmount + stats.paidTransportAmount).toLocaleString()}
        </div>
      </div>

      <div className={`p-4 rounded-lg border-2 ${
        stats.netProfit >= 0 
          ? 'bg-green-100 border-green-400' 
          : 'bg-red-100 border-red-400'
      }`}>
        <p className="text-sm text-gray-700 font-semibold mb-2 flex items-center">
          {stats.netProfit >= 0 ? (
            <TrendingUp size={16} className="mr-1 text-green-700" />
          ) : (
            <TrendingDown size={16} className="mr-1 text-red-700" />
          )}
          Net Projected Profit
        </p>
        <p className={`text-3xl font-bold ${
          stats.netProfit >= 0 ? 'text-green-700' : 'text-red-700'
        }`}>
          {stats.netProfit >= 0 ? '+' : ''}₹{stats.netProfit.toLocaleString()}
        </p>
        <p className={`text-sm font-semibold mt-1 ${
          stats.netProfit >= 0 ? 'text-green-600' : 'text-red-600'
        }`}>
          {stats.profitMargin.toFixed(1)}% margin
        </p>
      </div>
    </div>
  </div>

  {/* Detailed Metrics */}
  <div className="pt-4 border-t border-purple-300">
    <div className="grid grid-cols-4 gap-2 text-xs">
      <div className="bg-white p-2 rounded">
        <span className="text-gray-600">Avg Revenue/Job:</span>
        <span className="font-bold text-green-600 ml-2">
          ₹{allocations.length > 0 ? (stats.totalRevenue / allocations.length).toFixed(0) : 0}
        </span>
      </div>
      
      <div className="bg-white p-2 rounded">
        <span className="text-gray-600">Avg Cost/Job:</span>
        <span className="font-bold text-purple-600 ml-2">
          ₹{allocations.length > 0 ? (stats.totalPayout / allocations.length).toFixed(0) : 0}
        </span>
      </div>

      <div className="bg-white p-2 rounded">
        <span className="text-gray-600">Avg Profit/Job:</span>
        <span className={`font-bold ml-2 ${stats.netProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          ₹{allocations.length > 0 ? (stats.netProfit / allocations.length).toFixed(0) : 0}
        </span>
      </div>

      <div className="bg-white p-2 rounded">
        <span className="text-gray-600">Cost Ratio (M/T):</span>
        <span className="font-bold text-purple-600 ml-2">
          {stats.totalPayout > 0 
            ? `${((stats.totalMukkadamPayout / stats.totalPayout) * 100).toFixed(0)}/${((stats.totalTransportPayout / stats.totalPayout) * 100).toFixed(0)}`
            : '0/0'}
        </span>
      </div>
    </div>
  </div>

  {/* Performance Breakdown */}
  <div className="pt-4 border-t border-purple-300 mt-4">
    <div className="flex justify-between items-center mb-2">
      <span className="text-sm font-semibold text-gray-700">Allocation Performance</span>
      <span className="text-xs text-gray-500">
        {stats.profitableAllocations}/{allocations.length} profitable
      </span>
    </div>
    
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="bg-green-50 p-2 rounded border border-green-200">
        <div className="flex justify-between items-center">
          <span className="text-gray-700">Profitable:</span>
          <span className="font-bold text-green-700">{stats.profitableAllocations}</span>
        </div>
      </div>
      
      <div className="bg-red-50 p-2 rounded border border-red-200">
        <div className="flex justify-between items-center">
          <span className="text-gray-700">Loss Making:</span>
          <span className="font-bold text-red-700">{stats.lossAllocations}</span>
        </div>
      </div>

      <div className="bg-yellow-50 p-2 rounded border border-yellow-200">
        <div className="flex justify-between items-center">
          <span className="text-gray-700">Low Margin:</span>
          <span className="font-bold text-yellow-700">{stats.lowMarginAllocations}</span>
        </div>
      </div>
    </div>
  </div>
</div>
                    </div>

                    {/* Right Column - 1/3 width */}
                    <div className="space-y-6">
                        
                        {/* Top Performers */}
                        <div className="bg-white rounded-xl shadow-lg p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-gray-900 flex items-center">
                            <Users className="mr-2 text-indigo-600" />
                            Top Mukkadams
                            </h3>
                            <button
                            onClick={() => setActiveTab('mukkadams')}
                            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                            View All →
                            </button>
                        </div>
                        <div className="space-y-3">
                            {mukkadamAllocations
                            .sort((a, b) => b.total_price - a.total_price)
                            .slice(0, 5)
                            .map((ma, index) => (
                                <div key={ma.mukkadam.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg hover:bg-indigo-50 transition cursor-pointer">
                                <div className="flex items-center space-x-3 flex-1 min-w-0">
                                    <span className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                                    index === 0 ? 'bg-yellow-100 text-yellow-700' :
                                    index === 1 ? 'bg-gray-200 text-gray-700' :
                                    index === 2 ? 'bg-orange-100 text-orange-700' :
                                    'bg-blue-100 text-blue-700'
                                    }`}>
                                    {index + 1}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-gray-900 truncate">
                                        {ma.mukkadam.mukkadam_name}
                                    </p>
                                    <p className="text-xs text-gray-500">{ma.job_count} jobs</p>
                                    </div>
                                </div>
                                <div className="text-right ml-2">
                                    <p className="text-sm font-bold text-indigo-600">
                                    ₹{(ma.total_price / 1000).toFixed(1)}K
                                    </p>

                                    
                                </div>
                                
                                </div>
                            ))}
                            {mukkadamAllocations.length === 0 && (
                            <p className="text-center text-gray-500 py-4 text-sm">No data available</p>
                            )}
                        </div>
                        </div>

                        {/* Top Transport Providers */}
                        <div className="bg-white rounded-xl shadow-lg p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-gray-900 flex items-center">
                            <Truck className="mr-2 text-orange-600" />
                            Top Transporters
                            </h3>
                            <button
                            onClick={() => setActiveTab('transport')}
                            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                            View All →
                            </button>
                        </div>
                        <div className="space-y-3">
                            {transportAllocations
                            .sort((a, b) => b.total_price - a.total_price)
                            .slice(0, 5)
                            .map((ta, index) => (
                                <div key={ta.provider.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg hover:bg-orange-50 transition cursor-pointer">
                                <div className="flex items-center space-x-3 flex-1 min-w-0">
                                    <span className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                                    index === 0 ? 'bg-yellow-100 text-yellow-700' :
                                    index === 1 ? 'bg-gray-200 text-gray-700' :
                                    index === 2 ? 'bg-orange-100 text-orange-700' :
                                    'bg-blue-100 text-blue-700'
                                    }`}>
                                    {index + 1}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-gray-900 truncate">
                                        {ta.provider.name}
                                    </p>
                                    <p className="text-xs text-gray-500">{ta.job_count} jobs</p>
                                    </div>
                                </div>
                                <div className="text-right ml-2">
                                    <p className="text-sm font-bold text-orange-600">
                                    ₹{(ta.total_price / 1000).toFixed(1)}K
                                    </p>
                                </div>
                                </div>
                            ))}
                            {transportAllocations.length === 0 && (
                            <p className="text-center text-gray-500 py-4 text-sm">No data available</p>
                            )}
                        </div>
                        </div>

                        {/* Quick Actions */}
                        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl shadow-lg p-6 border border-blue-200">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Quick Actions</h3>
                        <div className="space-y-2">
                            <button
                            onClick={() => setActiveTab('pending')}
                            className="w-full px-4 py-3 bg-white border-2 border-blue-300 text-gray-900 rounded-lg hover:bg-blue-50 font-medium text-sm flex items-center justify-between transition"
                            >
                            <span className="flex items-center">
                                <Plus size={18} className="mr-2 text-blue-600" />
                                Allocate Pending Jobs
                            </span>
                            {pendingJobs.length > 0 && (
                                <span className="px-2 py-1 bg-yellow-500 text-white rounded-full text-xs font-bold">
                                {pendingJobs.length}
                                </span>
                            )}
                            </button>
                            
                            <button
                            onClick={() => setActiveTab('partially')}
                            className="w-full px-4 py-3 bg-white border-2 border-orange-300 text-gray-900 rounded-lg hover:bg-orange-50 font-medium text-sm flex items-center justify-between transition"
                            >
                            <span className="flex items-center">
                                <TrendingUp size={18} className="mr-2 text-orange-600" />
                                Continue Partial Jobs
                            </span>
                            {partiallyAllocatedJobs.length > 0 && (
                                <span className="px-2 py-1 bg-orange-500 text-white rounded-full text-xs font-bold">
                                {partiallyAllocatedJobs.length}
                                </span>
                            )}
                            </button>

                            {/* <button
                            onClick={() => setShowActiveWorkersModal(true)}
                            className="w-full px-4 py-3 bg-white border-2 border-teal-300 text-gray-900 rounded-lg hover:bg-teal-50 font-medium text-sm flex items-center justify-between transition"
                            >
                            <span className="flex items-center">
                                <Users size={18} className="mr-2 text-teal-600" />
                                View Active Workers
                            </span>
                            <span className="px-2 py-1 bg-teal-500 text-white rounded-full text-xs font-bold">
                                {totalActiveWorkers}
                            </span>
                            </button>

                            <button
                            onClick={() => setActiveTab('analytics')}
                            className="w-full px-4 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 font-medium text-sm flex items-center justify-center transition shadow-md"
                            >
                            <BarChart3 size={18} className="mr-2" />
                            View Full Analytics
                            </button> */}
                        </div>
                        </div>

                        {/* Capacity Alert */}
                        {(() => {
                        const utilizationRate = totalMukkadamsRegistered > 0 
                            ? (workerDetails.length / totalMukkadamsRegistered) * 100 
                            : 0;
                        
                        return (
                            <div className={`rounded-xl shadow-lg p-4 ${
                            utilizationRate > 80 ? 'bg-red-50 border border-red-200' :
                            utilizationRate > 60 ? 'bg-yellow-50 border border-yellow-200' :
                            'bg-green-50 border border-green-200'
                            }`}>
                            <div className="flex items-start space-x-3">
                                <div className={`mt-1 ${
                                utilizationRate > 80 ? 'text-red-600' :
                                utilizationRate > 60 ? 'text-yellow-600' :
                                'text-green-600'
                                }`}>
                                {utilizationRate > 80 ? <AlertCircle size={24} /> :
                                utilizationRate > 60 ? <TrendingUp size={24} /> :
                                <CheckCircle size={24} />}
                                </div>
                                <div>
                                <h4 className={`font-bold text-sm ${
                                    utilizationRate > 80 ? 'text-red-900' :
                                    utilizationRate > 60 ? 'text-yellow-900' :
                                    'text-green-900'
                                }`}>
                                    Capacity Status
                                </h4>
                                <p className="text-xs text-gray-700 mt-1">
                                    {utilizationRate.toFixed(0)}% mukkadam utilization
                                </p>
                                <p className="text-xs text-gray-600 mt-1">
                                    {workerDetails.length} of {totalMukkadamsRegistered} mukkadams active
                                </p>
                                </div>
                            </div>
                            </div>
                        );
                        })()}
                    </div>
                    </div>
                </div>
                )}

{activeTab === 'allocated' && (
  <div>
    {/* --- Filter Bar Section --- */}
    <div className="flex flex-col lg:flex-row gap-4 mb-6 items-end bg-white p-4 rounded-xl shadow-sm border border-gray-200">
      
      {/* 1. Keyword Search */}
      <div className="flex-1 w-full">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Search Keywords</label>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input 
            type="text" 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search ID, Farmer, or Mukkadam..."
            className="w-full p-2 pl-10 border rounded-lg focus:ring-2 focus:ring-green-500"
          />
        </div>
      </div>

      {/* 2. Activity Name Text Search */}
      <div className="w-full lg:w-48">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Activity Name</label>
        <div className="relative">
          <Layers className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            value={selectedActivityName}
            onChange={(e) => setSelectedActivityName(e.target.value)}
            placeholder="e.g. Wrapping..."
            className="w-full p-2 pl-10 border rounded-lg focus:ring-2 focus:ring-green-500"
          />
        </div>
      </div>
      
      {/* 3. Filter by Specific Date */}
      <div className="w-full lg:w-44">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Filter Date</label>
        <input 
          type="date" 
          value={selectedFilterDate}
          onChange={(e) => setSelectedFilterDate(e.target.value)}
          className="w-full p-2 border rounded-lg focus:ring-2 focus:ring-green-500"
        />
      </div>

      {/* Reset Button */}
      {(searchTerm || selectedFilterDate || selectedActivityName) && (
        <button 
          onClick={() => {setSearchTerm(''); setSelectedFilterDate(''); setSelectedActivityName('');}} 
          className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-bold transition text-sm whitespace-nowrap"
        >
          Reset All
        </button>
      )}
    </div>

    {(() => {
      // Helper function to get the same date used for display
      const getEffectiveJobDate = (job) => {
        if (!job) return 0;
        let dStr = job.scheduled_date;
        if (!dStr && job.activities?.length > 0) {
          const sorted = job.activities
            .map(a => a.scheduled_date)
            .filter(Boolean)
            .sort();
          if (sorted.length > 0) dStr = sorted[0];
        }
        return dStr ? new Date(dStr).getTime() : 0;
      };

      // Group allocations by job ID
      const allocationsByJob = getAllocatedAllocations().reduce((acc, allocation) => {
        const jobId = allocation.farmer_work_id;
        if (!acc[jobId]) { acc[jobId] = []; }
        acc[jobId].push(allocation);
        return acc;
      }, {} as Record<string, Allocation[]>);

      // --- Filter & Sort Logic ---
      const filteredAndSortedJobIds = Object.keys(allocationsByJob)
        .filter(jobId => {
          const job = jobs.find(j => j.work_id === jobId);
          const jobAllocations = allocationsByJob[jobId];
          
          // Date Filter Logic
          const jobTime = getEffectiveJobDate(job);
          if (selectedFilterDate) {
            const filterTime = new Date(selectedFilterDate).setHours(0,0,0,0);
            const actualJobTime = new Date(jobTime).setHours(0,0,0,0);
            if (filterTime !== actualJobTime) return false;
          }

          // Activity Text Search Logic
          if (selectedActivityName) {
            const actSearch = selectedActivityName.toLowerCase();
            const hasMatch = jobAllocations.some(a => 
              String(a.activity_name || '').toLowerCase().includes(actSearch)
            );
            if (!hasMatch) return false;
          }

          // General Text Search Logic
          if (!searchTerm) return true;
          const searchLower = searchTerm.toLowerCase();
          return (
            String(jobId).toLowerCase().includes(searchLower) ||
            String(job?.title || '').toLowerCase().includes(searchLower) ||
            String(job?.farmer?.farmer_name || '').toLowerCase().includes(searchLower) ||
            jobAllocations.some(a => {
              const mukkadam = mukkadams.find(m => m.id === a.mukkadam_id);
              return String(mukkadam?.mukkadam_name || '').toLowerCase().includes(searchLower);
            })
          );
        })
        .sort((idA, idB) => {
          const jobA = jobs.find(j => j.work_id === idA);
          const jobB = jobs.find(j => j.work_id === idB);
          
          // Sort by the calculated effective date (Oldest to Newest)
          return getEffectiveJobDate(jobA) - getEffectiveJobDate(jobB);
        });

      if (filteredAndSortedJobIds.length === 0) {
        return (
          <div className="text-center py-12 bg-white rounded-xl border border-dashed border-gray-300">
            <Search size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-600 font-medium">No allocated jobs match your current filters</p>
          </div>
        );
      }

      return (
        <div className="space-y-3">
          {filteredAndSortedJobIds.map(jobId => {
            const jobAllocations = allocationsByJob[jobId];
            const job = jobs.find(j => j.work_id === jobId);
            const isExpanded = expandedJobs.has(jobId);
            const farmer = job?.farmer;

            const totalMukkadamCost = jobAllocations.reduce((sum, a) => sum + (parseFloat(String(a.mukkadam_price)) || 0), 0);
            const totalTransportCost = jobAllocations.reduce((sum, a) => sum + (parseFloat(String(a.transport_price)) || 0), 0);
            const totalArea = jobAllocations.reduce((sum, a) => sum + (parseFloat(String(a.allocated_area)) || 0), 0);

            return (
              <div key={jobId} className="border-2 border-green-300 bg-green-50 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 cursor-pointer hover:bg-green-100 transition" onClick={() => toggleJob(jobId)}>
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <span className="text-lg font-mono font-bold text-blue-600">{jobId}</span>
                        <span className="px-2 py-1 bg-green-500 text-white rounded-full text-xs font-bold">ALLOCATED</span>
                        <span className="text-sm font-medium text-gray-700">{job?.title}</span>
                      </div>
                      {farmer && (
                        <div className="flex items-center space-x-2 text-sm">
                          <span className="font-bold text-gray-900">{farmer.farmer_name}</span>
                          <span className="text-gray-500">• {farmer.phone_number}</span>
                          <span className="text-gray-500">• {farmer.village}</span>
                          <span className="text-gray-500">• {farmer.district}</span>
                          <span className="text-gray-500">• {farmer.taluka}</span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center space-x-6 mr-4">
                      <div className="text-right">
                        <p className="text-xs text-gray-500 uppercase font-bold">Scheduled</p>
                        <p className="text-sm font-semibold text-gray-700">
                          {(() => {
                            const time = getEffectiveJobDate(job);
                            return time > 0 ? new Date(time).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : 'N/A';
                          })()}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Total Area</p>
                        <p className="text-lg font-bold text-gray-700">{totalArea.toFixed(1)} ac</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Total Cost</p>
                        <p className="text-2xl font-bold text-purple-600">₹{(totalMukkadamCost + totalTransportCost).toLocaleString()}</p>
                      </div>
                      {isExpanded ? <ChevronUp className="text-green-600" /> : <ChevronDown className="text-green-600" />}
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-green-200 bg-white">
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr className="text-xs text-gray-500 uppercase">
                            <th className="px-4 py-3 text-left">Activity</th>
                            <th className="px-4 py-3 text-left">Mukkadam</th>
                            <th className="px-4 py-3 text-left">Area</th>
                            <th className="px-4 py-3 text-left">Crew</th>
                            <th className="px-4 py-3 text-left">T Cost</th>
                            <th className="px-4 py-3 text-left">M Cost</th>
                            <th className="px-4 py-3 text-left">Total Cost</th>
                            <th className="px-4 py-3 text-left">Work Date</th>
                            <th className="px-4 py-3 text-left">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {jobAllocations.map(allocation => (
                            <tr key={allocation.id} className="text-sm hover:bg-gray-50">
                              <td className="px-4 py-3 font-medium">{allocation.activity_name}</td>
                              <td className="px-4 py-3">{mukkadams.find(m => m.id === allocation.mukkadam_id)?.mukkadam_name}</td>
                              <td className="px-4 py-3">{allocation.allocated_area} ac</td>
                                <td className="px-4 py-3 font-bold text-teal-600">{allocation.crew_size}</td>
                                <td className="px-4 py-3 text-orange-600 font-medium">₹{parseFloat(allocation.transport_price).toLocaleString()}</td>
                                <td className="px-4 py-3 text-orange-600 font-medium">₹{parseFloat(allocation.mukkadam_price).toLocaleString()}</td>
                                <td className="px-4 py-3 font-bold text-purple-600">₹{(parseFloat(allocation.mukkadam_price) + parseFloat(allocation.transport_price)).toLocaleString()}</td>
                              <td className="px-4 py-3">{allocation.work_date ? new Date(allocation.work_date).toLocaleDateString('en-IN') : 'N/A'}</td>
                              <td className="px-4 py-3">
                                <div className="flex items-center space-x-3">
                                  <button onClick={() => navigate(`/allocations/${allocation.id}`)} className="text-blue-600 hover:text-blue-800 transition flex items-center" title="View Detail">
                                    <Eye size={16} className="mr-1" /> View
                                  </button>
                                  <button onClick={() => handleMarkComplete(allocation.id)} className="text-green-600 hover:text-green-800 transition flex items-center font-bold" title="Mark Complete">
                                    <CheckCircle size={16} className="mr-1" /> Complete
                                  </button>
                                  <button onClick={() => { setAllocationToEdit(allocation); setShowEditModal(true); }} className="text-orange-600 hover:text-orange-800 transition flex items-center" title="Edit Allocation">
                                    <Edit size={16} className="mr-1" /> Edit
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    })()}
  </div>
)}
{/* ✅ COMPLETED TAB - NEW */}
{activeTab === 'completed' && (
  <div className="p-6">
    <div className="mb-4 flex items-center justify-between">
      <h2 className="text-xl font-bold text-gray-800">Completed Allocations</h2>
      <button
        onClick={() => refreshAllocations()}
        className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
        disabled={loadingPayments}
      >
        {loadingPayments ? 'Refreshing...' : '🔄 Refresh Payments'}
      </button>
    </div>

    {/* Filter Bar Section */}
    <div className="flex flex-col md:flex-row gap-4 mb-6 items-end bg-white p-4 rounded-xl shadow-sm border border-gray-200">
      <div className="flex-1">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Search Keywords</label>
        <div className="relative">
          <input 
            type="text" 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search Job ID, Farmer, Mukkadam, or Activity..."
            className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
        </div>
      </div>
      
      <div className="w-full md:w-64">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Filter by Work Date</label>
        <div className="flex gap-2">
          <input 
            type="date" 
            value={selectedFilterDate}
            onChange={(e) => setSelectedFilterDate(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          {selectedFilterDate && (
            <button 
              onClick={() => setSelectedFilterDate('')}
              className="px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-bold transition"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>

    {(() => {
        const filteredCompletedList = getCompletedAllocations()
            .filter(allocation => {
                const job = jobs.find(j => j.work_id === allocation.farmer_work_id);
                const farmerName = job?.farmer?.farmer_name || '';
                const searchLower = searchTerm.toLowerCase();

                if (selectedFilterDate) {
                  if (!allocation.work_date || !allocation.work_date.startsWith(selectedFilterDate)) {
                    return false;
                  }
                }

                if (!searchTerm) return true;
                const mukkadam = mukkadams.find(m => m.id === allocation.mukkadam_id);
                const provider = transportProviders.find(t => t.id === allocation.transport_provider_id);

                return (
                    String(allocation.farmer_work_id || '').toLowerCase().includes(searchLower) ||
                    String(allocation.activity_name || '').toLowerCase().includes(searchLower) ||
                    farmerName.toLowerCase().includes(searchLower) ||
                    String(mukkadam?.mukkadam_name || '').toLowerCase().includes(searchLower) ||
                    String(provider?.name || '').toLowerCase().includes(searchLower)
                );
            })
            .sort((a, b) => {
                // Sort by work_date descending (newest first)
                const dateA = new Date(a.work_date);
                const dateB = new Date(b.work_date);
                return dateB - dateA;
            });

        if (filteredCompletedList.length === 0) {
            return (
                <div className="text-center py-12">
                    <CheckSquare size={48} className="mx-auto text-gray-400 mb-4" />
                    <p className="text-gray-600">
                        {searchTerm || selectedFilterDate ? `No results match your filters` : "No completed allocations found"}
                    </p>
                </div>
            );
        }

        return (
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">Farmer Info</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mukkadam</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Activity</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Area</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Work Date</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mukkadam Payment</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Transport Payment</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {filteredCompletedList.map(allocation => {
                            const mukkadam = mukkadams.find(m => m.id === allocation.mukkadam_id);
                            const provider = transportProviders.find(t => t.id === allocation.transport_provider_id);
                            const job = jobs.find(j => j.work_id === allocation.farmer_work_id);
                            
                            const mukkadamPayment = getMukkadamPaymentRequest(allocation.id);
                            const transportPayment = getTransportPaymentRequest(allocation.id);

                            const mukkadamAmount = parseFloat(String(allocation.mukkadam_price || '0'));
                            const transportAmount = parseFloat(String(allocation.transport_price || '0'));

                            return (
                                <tr key={allocation.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-4">
                                      <div className="text-sm">
                                        <div className="font-bold text-indigo-600">{job?.farmer?.farmer_name || 'N/A'}</div>
                                        <div className="font-bold text-indigo-600">{job?.farmer?.phone_number || 'N/A'}</div>
                                        <div className="text-gray-400 text-xs flex items-center mt-1">
                                          <MapPin size={10} className="mr-1" /> {job?.farmer?.location || 'No Location'}
                                        </div>
                                      </div>
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="text-sm">
                                            <div className="font-medium text-gray-900">{mukkadam?.mukkadam_name || 'Unknown'}</div>
                                            <div className="text-gray-500 text-xs">ID: {allocation.mukkadam_id}</div>
                                        </div>
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="text-sm">
                                            <div className="font-medium text-gray-900">{allocation.activity_name || 'N/A'}</div>
                                            <div className="text-gray-500 text-xs">Job: {allocation.farmer_work_id}</div>
                                        </div>
                                    </td>

                                    <td className="px-4 py-4 text-sm text-gray-700">{allocation.allocated_area} acres</td>

                                    <td className="px-4 py-4 text-sm text-gray-700">
                                        {new Date(allocation.work_date).toLocaleDateString('en-IN')}
                                    </td>

                                    {/* --- Mukkadam Payment Column --- */}
<td className="px-4 py-4">
  <div className="space-y-2">
    <div className="font-bold text-green-600">₹{mukkadamAmount.toLocaleString()}</div>
    {mukkadamPayment ? (
      <div>
        {mukkadamPayment.status === 'paid' ? (
          <div className="flex items-center">
            <CheckCircle size={16} className="text-green-600 mr-1" />
            <span className="text-xs font-semibold text-green-700">PAID</span>
          </div>
        ) : mukkadamPayment.status === 'pending' ? (
          // ✅ LOGIC UPDATE: Check isAdmin before showing buttons
          isAdmin ? (
            <div className="flex flex-col space-y-1">
              <button
                onClick={() => handleMarkMukkadamPaid(mukkadamPayment.id)}
                className="px-3 py-1 bg-green-500 text-white text-xs rounded hover:bg-green-600 transition flex items-center justify-center"
              >
                <CheckCircle size={14} className="mr-1" /> Mark Paid
              </button>
              <button
                onClick={() => handleRejectMukkadamPayment(mukkadamPayment.id)}
                className="px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition flex items-center justify-center"
              >
                <XCircle size={14} className="mr-1" /> Reject
              </button>
            </div>
          ) : (
            // Non-Admins see a simple status badge
            <div className="flex items-center bg-yellow-100 px-2 py-1 rounded w-fit">
              <Clock size={14} className="text-yellow-600 mr-1" />
              <span className="text-xs font-semibold text-yellow-700">PENDING</span>
            </div>
          )
        ) : (
          <div className="flex items-center">
            <Ban size={16} className="text-red-600 mr-1" />
            <span className="text-xs font-semibold text-red-700">REJECTED</span>
          </div>
        )}
      </div>
    ) : (
      <span className="text-xs text-gray-500 italic">Not requested</span>
    )}
  </div>
</td>

{/* --- Transport Payment Column --- */}
<td className="px-4 py-4">
  {allocation.transport_type === 'provider' && allocation.transport_provider_id ? (
    <div className="space-y-2">
      <div className="font-bold text-orange-600">₹{transportAmount.toLocaleString()}</div>
      <div className="text-xs text-gray-600">{provider?.name || 'Unknown'}</div>
      
      {transportPayment ? (
        <div>
          {transportPayment.status === 'paid' ? (
            <div className="flex items-center">
              <CheckCircle size={16} className="text-green-600 mr-1" />
              <span className="text-xs font-semibold text-green-700">PAID</span>
            </div>
          ) : transportPayment.status === 'pending' ? (
            // ✅ LOGIC UPDATE: Check isAdmin before showing buttons
            isAdmin ? (
              <div className="flex flex-col space-y-1">
                <button
                  onClick={() => handleMarkTransportPaid(transportPayment.id)}
                  className="px-3 py-1 bg-green-500 text-white text-xs rounded hover:bg-green-600 transition flex items-center justify-center"
                >
                  <CheckCircle size={14} className="mr-1" /> Mark Paid
                </button>
                <button
                  onClick={() => handleRejectTransportPayment(transportPayment.id)}
                  className="px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition flex items-center justify-center"
                >
                  <XCircle size={14} className="mr-1" /> Reject
                </button>
              </div>
            ) : (
              // Non-Admins see a simple status badge
              <div className="flex items-center bg-yellow-100 px-2 py-1 rounded w-fit">
                <Clock size={14} className="text-yellow-600 mr-1" />
                <span className="text-xs font-semibold text-yellow-700">PENDING</span>
              </div>
            )
          ) : (
            <div className="flex items-center">
              <Ban size={16} className="text-red-600 mr-1" />
              <span className="text-xs font-semibold text-red-700">REJECTED</span>
            </div>
          )}
        </div>
      ) : (
        <span className="text-xs text-gray-500 italic">Not requested</span>
      )}
    </div>
  ) : allocation.transport_type === 'own' ? (
    <div className="space-y-2">
      <div className="font-bold text-blue-600">₹{transportAmount.toLocaleString()}</div>
      <div className="text-xs text-gray-600">Own Transport</div>
    </div>
  ) : (
    <div className="text-xs text-gray-500">No Transport</div>
  )}
</td>

                                    
                           
                                            <td className="px-4 py-4">
  <div className="flex flex-col space-y-2">
    {/* View Detail - Visible to Everyone */}
    <button
      onClick={() => navigate(`/allocations/${allocation.id}`)}
      className="text-blue-600 hover:text-blue-900 font-bold flex items-center text-xs"
    >
      <Eye size={14} className="mr-1" /> View Detail
    </button>
    
    {/* ✅ EDIT BUTTON: Visible ONLY if (User is Admin) AND (Not Paid) */}
    {isAdmin && !(mukkadamPayment?.status === 'paid' || transportPayment?.status === 'paid') && (
      <button 
        onClick={() => {
          setAllocationToEdit(allocation); 
          setShowEditModal(true);
        }}
        className="text-orange-600 hover:text-orange-800 font-bold flex items-center text-xs"
      >
        <Edit size={14} className="mr-1" /> Edit/Reallocate
      </button>
    )}
  </div>
</td>
                                   
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        );
    })()}
  </div>
)}
{activeTab === 'pending' && (
  <div>
    {/* --- Filter Bar Section (Synced with Allocated Tab) --- */}
    <div className="flex flex-col lg:flex-row gap-4 mb-6 items-end bg-white p-4 rounded-xl shadow-sm border border-gray-200">
      
      {/* 1. Keyword Search */}
      <div className="flex-1 w-full">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Search Keywords</label>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input 
            type="text" 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search ID, Farmer, or Title..."
            className="w-full p-2 pl-10 border rounded-lg focus:ring-2 focus:ring-yellow-500"
          />
        </div>
      </div>

      {/* 2. Activity Name Text Search */}
      <div className="w-full lg:w-48">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Activity Name</label>
        <div className="relative">
          <Layers className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            value={selectedActivityName}
            onChange={(e) => setSelectedActivityName(e.target.value)}
            placeholder="e.g. Wrapping..."
            className="w-full p-2 pl-10 border rounded-lg focus:ring-2 focus:ring-yellow-500"
          />
        </div>
      </div>
      
      {/* 3. Filter by Specific Date */}
      <div className="w-full lg:w-44">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Filter Date</label>
        <input 
          type="date" 
          value={selectedFilterDate}
          onChange={(e) => setSelectedFilterDate(e.target.value)}
          className="w-full p-2 border rounded-lg focus:ring-2 focus:ring-yellow-500"
        />
      </div>

      {/* Reset Button */}
      {(searchTerm || selectedFilterDate || selectedActivityName) && (
        <button 
          onClick={() => {setSearchTerm(''); setSelectedFilterDate(''); setSelectedActivityName('');}} 
          className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-bold transition text-sm whitespace-nowrap"
        >
          Reset All
        </button>
      )}
    </div>

    {(() => {
      // Helper function to get the same date used for display
      const getEffectiveJobDate = (job) => {
        if (!job) return 0;
        let dStr = job.scheduled_date;
        if (!dStr && job.activities?.length > 0) {
          const sorted = job.activities
            .map(a => a.scheduled_date)
            .filter(Boolean)
            .sort();
          if (sorted.length > 0) dStr = sorted[0];
        }
        return dStr ? new Date(dStr).getTime() : 0;
      };

      // 1. FILTER & SORT LOGIC
      // 1. FILTER & SORT LOGIC
      const filteredAndSortedPendingJobs = pendingJobs
        .filter(job => {
          // ✅ CRITICAL FIX: Exclude jobs where all activities are lost
          const nonLostActivities = job.activities?.filter(a => !a.is_lost) || [];
          if (nonLostActivities.length === 0) return false;

          const jobTime = getEffectiveJobDate(job);
          const jobDateString = jobTime > 0 ? new Date(jobTime).toISOString().split('T')[0] : '';

          // A. Date Filter
          if (selectedFilterDate && jobDateString !== selectedFilterDate) return false;

          // B. Activity Text Search Filter
          if (selectedActivityName) {
            const actSearch = selectedActivityName.toLowerCase();
            const hasMatch = nonLostActivities.some(a =>  // ✅ Use nonLostActivities
              String(a.activity_name || '').toLowerCase().includes(actSearch)
            );
            if (!hasMatch) return false;
          }

          // C. General Text Search Filter
          if (!searchTerm) return true;
          const searchLower = searchTerm.toLowerCase();
          return (
            job.work_id?.toLowerCase().includes(searchLower) ||
            job.title?.toLowerCase().includes(searchLower) ||
            job.farmer?.farmer_name?.toLowerCase().includes(searchLower) ||
            job.farmer?.location?.toLowerCase().includes(searchLower) ||
            job.farmer?.phone_number?.includes(searchLower)
          );
        })
        .sort((a, b) => {
          return getEffectiveJobDate(a) - getEffectiveJobDate(b);
        });

      // 2. EMPTY STATE
      if (filteredAndSortedPendingJobs.length === 0) {
        return (
          <div className="text-center py-12 bg-white rounded-xl border border-dashed border-gray-300">
            <Clock size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-600 font-medium">
              No pending jobs match your current filters
            </p>
          </div>
        );
      }

      // 3. RENDER LIST
      return (
        <div className="space-y-3">
          {filteredAndSortedPendingJobs.map(job => {
            const isExpanded = expandedJobs.has(job.work_id);
            const farmer = job.farmer;
            
            return (
              <div 
                key={job.id} 
                className="border-2 border-yellow-300 bg-yellow-50 rounded-xl overflow-hidden transition-all shadow-sm"
              >
                <div 
                  className="p-4 cursor-pointer hover:bg-yellow-100 transition"
                  onClick={() => toggleJob(job.work_id)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <span className="text-lg font-mono font-bold text-blue-600">{job.work_id}</span>
                        <span className="px-2 py-1 bg-yellow-500 text-white rounded-full text-xs font-bold">PENDING</span>
                        <span className="px-2 py-1 bg-purple-500 text-white rounded-full text-xs font-bold">
                          {job.total_activities} {job.total_activities === 1 ? 'activity' : 'activities'}
                        </span>
                      </div>

                      {farmer && (
                        <div className="mb-2">
                          <div className="flex items-center space-x-2">
                            <Users size={16} className="text-indigo-600" />
                            <span className="font-semibold text-gray-900">{farmer.farmer_name}</span>
                            <span className="text-sm text-gray-600">• {farmer.phone_number}</span>
                            <span className="text-gray-500">• {farmer.village}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <p className="text-xs text-gray-500 uppercase font-bold">Scheduled</p>
                        <p className="text-sm font-semibold text-gray-700">
                          {(() => {
                            const time = getEffectiveJobDate(job);
                            return time > 0 ? new Date(time).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : 'N/A';
                          })()}
                        </p>
                      </div>
                      
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openComplexAllocationModal(job);
                        }}
                        className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 font-medium flex items-center shadow-sm transition"
                      >
                        <Plus size={16} className="mr-1" /> 
                        Allocate
                      </button>
                      
                      {isExpanded ? <ChevronUp className="text-yellow-600" /> : <ChevronDown className="text-yellow-600" />}
                    </div>
                  </div>
                </div>

{isExpanded && (
  <div className="p-4 bg-gray-50 border-t">
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {job.activities?.map((activity) => (
      <div 
  key={activity.activity_id || activity.id}
  className="bg-white p-4 rounded-xl border border-gray-200 hover:border-yellow-400 transition shadow-sm relative"
>
  {/* Activity Header with Close Icon */}
  <div className="flex items-start justify-between mb-4">
    <h4 className="font-semibold text-gray-800 text-base">
      {activity.activity_name}
    </h4>
    
  </div>
          
          {/* ✨ NEW: Edit Button */}
          {/* <button
            onClick={(e) => {
              e.stopPropagation();
              handleEditActivity(activity, job.work_id);
            }}
            className="ml-3 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition flex items-center gap-2 font-medium text-sm"
            title="Edit activity details"
          >
            <Edit2 size={14} />
            Edit
          </button> */}
        {/* </div> */}

        {/* Activity Details */}

  {/* Activity Details - Compact */}
  <div className="space-y-2 text-sm">
    <div className="flex justify-between">
      <span className="text-gray-500">Area:</span>
      <span className="font-medium text-gray-900">{activity.total_area} acres</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Rate:</span>
      <span className="font-medium text-gray-900">₹{activity.rate_per_acre}/acre</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Total Price:</span>
      <span className="font-medium text-gray-900">₹{activity.total_price}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-500">Scheduled:</span>
      <span className="font-medium text-gray-900">{activity.scheduled_date || 'Not set'}</span>
    </div>



  </div>

  {isAdmin && !activity.is_lost && (
  <div className="mt-3 pt-3 border-t border-gray-200 flex gap-2">
<button
  onClick={(e) => {
    e.stopPropagation();
    setSelectedActivityForEdit(activity);
    setSelectedJobForEdit(job);
    // ✅ POPULATE ALL FORM DATA INCLUDING NEW COST FIELDS
    setEditFormData({
      activity_name: activity.activity_name,
      total_area: activity.total_area,
      scheduled_date: activity.scheduled_date || '',
      total_price: activity.total_price,
      transport_cost: activity.transport_cost || 0,  // ✅ NEW
      other_cost: activity.other_cost || 0,          // ✅ NEW
      rate_per_acre: activity.rate_per_acre
    });
    setShowEditActivityModal(true);
  }}
  className="flex-1 px-3 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition flex items-center justify-center gap-1 text-sm font-medium"
>
  <Edit2 size={14} />
  Edit
</button>
    <button
  onClick={(e) => {
    e.stopPropagation();
    setSelectedActivityForEdit(activity);
    setSelectedJobForEdit(job);
    setShowMarkLostModal(true);
  }}
      className="flex-1 px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition flex items-center justify-center gap-1 text-sm font-medium"
    >
      <Ban size={14} />
      Mark Lost
    </button>
  </div>
)}

{activity.is_lost && (
  <div className="mt-3 pt-3 border-t border-red-200">
    <div className="px-3 py-2 bg-red-100 border border-red-300 rounded text-xs text-red-800">
      <Ban size={12} className="inline mr-1" />
      <strong>LOST:</strong> {activity.lost_reason}
    </div>
    {isAdmin && (
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleUnmarkActivityLost(activity, job.work_id);
        }}
        className="mt-2 w-full px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 text-xs font-bold"
      >
        Restore Activity
      </button>
    )}
  </div>
)}
</div>
      // </div>
    ))}
    </div>
  </div>)}
              </div>
            );
          })}
        </div>
      );
    })()}
  </div>
)}

<EditActivityModal
  activity={editingActivity}
  jobId={editingJobId}
  isOpen={isEditModalOpen}
  onClose={() => {
    setIsEditModalOpen(false);
    setEditingActivity(null);
    setEditingJobId(null);
  }}
  onSaveSuccess={handleSaveSuccess}
/>
            {/* Partially Allocated Jobs Tab */}
{activeTab === 'partially' && (
  <div>
    {/* --- Filter Bar Section --- */}
    <div className="flex flex-col md:flex-row gap-4 mb-6 items-end bg-white p-4 rounded-xl shadow-sm border border-gray-200">
      <div className="flex-1">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Search Keywords</label>
        <div className="relative">
          <input 
            type="text" 
            value={partialSearchQuery}
            onChange={(e) => setPartialSearchQuery(e.target.value)}
            placeholder="Search ID, Farmer, or Activity..."
            className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
          />
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
        </div>
      </div>
      
      <div className="w-full md:w-64">
        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Filter by Scheduled Date</label>
        <div className="flex gap-2">
          <input 
            type="date" 
            value={selectedFilterDate}
            onChange={(e) => setSelectedFilterDate(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
          />
          {selectedFilterDate && (
            <button 
              onClick={() => setSelectedFilterDate('')}
              className="px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-bold transition"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>

    {(() => {
      // Helper function for uniform date calculation
      const getEffectiveJobDate = (job) => {
        if (!job) return 0;
        let dStr = job.scheduled_date;
        if (!dStr && job.activities?.length > 0) {
          const sortedDates = job.activities
            .map(a => a.scheduled_date)
            .filter(Boolean)
            .sort();
          if (sortedDates.length > 0) dStr = sortedDates[0];
        }
        return dStr ? new Date(dStr).getTime() : 0;
      };

      // --- REFINED FILTER & SORT LOGIC ---
      const finalFilteredJobs = partiallyAllocatedJobs
        .filter(job => {
          const jobTime = getEffectiveJobDate(job);
          const jobDateString = jobTime > 0 ? new Date(jobTime).toISOString().split('T')[0] : '';

          // A. Filter by Date
          if (selectedFilterDate && jobDateString !== selectedFilterDate) return false;

          // B. Filter by Search Query
          if (!partialSearchQuery) return true;
          const searchLower = partialSearchQuery.toLowerCase();
          return (
            job.work_id?.toLowerCase().includes(searchLower) ||
            job.title?.toLowerCase().includes(searchLower) ||
            job.farmer?.farmer_name?.toLowerCase().includes(searchLower) ||
            job.farmer?.location?.toLowerCase().includes(searchLower) ||
            job.activities?.some(a => a.activity_name?.toLowerCase().includes(searchLower))
          );
        })
        .sort((a, b) => {
          // --- FORCED ASCENDING SORT (History to Future) ---
          return getEffectiveJobDate(a) - getEffectiveJobDate(b);
        });

      if (finalFilteredJobs.length === 0) {
        return (
          <div className="text-center py-12 bg-white rounded-xl border border-dashed border-gray-300">
            <TrendingUp size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-600 font-medium">
              {partialSearchQuery || selectedFilterDate 
                ? 'No partially allocated jobs match your filters' 
                : 'No partially allocated jobs available'}
            </p>
            {(partialSearchQuery || selectedFilterDate) && (
               <button 
                 onClick={() => {setPartialSearchQuery(''); setSelectedFilterDate('');}}
                 className="mt-4 text-blue-600 hover:text-blue-800 underline text-sm"
               >
                 Reset all filters
               </button>
            )}
          </div>
        );
      }

      return (
        <div className="space-y-3">
          {finalFilteredJobs.map(job => {
            const isExpanded = expandedJobs.has(job.work_id);
            const completedActivities = job.activities?.filter(a => a.is_fully_allocated).length || 0;
            const farmer = job.farmer;
            
            return (
              <div 
                key={job.id} 
                className="border-2 border-orange-300 bg-orange-50 rounded-xl overflow-hidden shadow-sm"
              >
                <div 
                  className="p-4 cursor-pointer hover:bg-orange-100 transition"
                  onClick={() => toggleJob(job.work_id)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <span className="text-lg font-mono font-bold text-blue-600">{job.work_id}</span>
                        <span className="px-2 py-1 bg-orange-500 text-white rounded-full text-xs font-bold flex items-center">
                          <TrendingUp size={14} className="mr-1" />
                          {completedActivities}/{job.total_activities} DONE
                        </span>
                        <span className="text-sm font-medium text-gray-700">{job.title}</span>
                      </div>

                      {farmer && (
                        <div className="mb-1">
                          <div className="flex items-center space-x-2 text-sm">
                            <Users size={14} className="text-indigo-600" />
                            <span className="font-bold text-gray-900">{farmer.farmer_name}</span>
                            <span className="text-gray-500">• {farmer.phone_number}</span>
                            <span className="text-gray-500">• {farmer.location}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center space-x-6 mr-4">
                      <div className="text-right">
                        <p className="text-xs text-gray-500 uppercase font-bold">Scheduled</p>
                        <p className="text-sm font-semibold text-gray-700">
                          {(() => {
                            const time = getEffectiveJobDate(job);
                            return time > 0 ? new Date(time).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : 'N/A';
                          })()}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openComplexAllocationModal(job);
                        }}
                        className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 font-medium flex items-center shadow-md"
                      >
                        <Plus size={16} className="mr-1" /> Continue
                      </button>
                      {isExpanded ? <ChevronUp className="text-orange-600" /> : <ChevronDown className="text-orange-600" />}
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-orange-300 animate-fadeIn bg-white">
                    <div className="mt-4">
                      <h4 className="font-semibold text-gray-900 mb-3 flex items-center">
                        <Layers size={18} className="mr-2 text-orange-600" />
                        Activities Progress
                      </h4>

                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {job.activities.map((activity) => {
                          const { allocated, remaining, isFullyAllocated } = getActivityStats(
                            job.work_id,
                            activity.activity_name,
                            activity.total_area
                          );

                          return (
                            <div
                              key={activity.id}
                              className={`p-4 rounded-lg border-2 ${
                                isFullyAllocated
                                  ? 'border-green-300 bg-green-50'
                                  : allocated > 0
                                  ? 'border-yellow-300 bg-yellow-50'
                                  : 'border-gray-200 bg-gray-50'
                              }`}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <span className="font-semibold text-sm text-gray-900">
                                  {activity.activity_name}
                                </span>
                                {isFullyAllocated ? (
                                  <CheckCircle size={16} className="text-green-600" />
                                ) : allocated > 0 ? (
                                  <TrendingUp size={16} className="text-yellow-600" />
                                ) : (
                                  <XCircle size={16} className="text-gray-400" />
                                )}
                              </div>

                              <div className="space-y-1 text-xs text-gray-600 mb-2">
                                <div className="flex items-center">
                                  <Calendar size={12} className="mr-1" />
                                  {new Date(activity.scheduled_date).toLocaleDateString()}
                                </div>
                                <div className="flex items-center justify-between">
                                  <span>Area:</span>
                                  <span className="font-semibold">
                                    {allocated.toFixed(2)}/{activity.total_area} acres
                                  </span>
                                </div>
                              </div>

                              {!isFullyAllocated && (
                                <div>
                                  <div className="bg-gray-200 rounded-full h-2 mb-1">
                                    <div
                                      className={`h-2 rounded-full transition-all ${
                                        allocated > 0 ? 'bg-yellow-500' : 'bg-gray-400'
                                      }`}
                                      style={{
                                        width: `${Math.min((allocated / activity.total_area) * 100, 100)}%`,
                                      }}
                                    />
                                  </div>
                                  <p className="text-xs font-semibold text-orange-600">
                                    {remaining.toFixed(2)} acres remaining
                                  </p>
                                </div>
                              )}

                              {activity.allocations && activity.allocations.length > 0 && (
                                <div className="mt-2 pt-2 border-t border-gray-300">
                                  <p className="text-xs text-gray-600 mb-1">Allocated to:</p>
                                  {activity.allocations.map((alloc, idx) => (
                                    <div key={idx} className="text-xs bg-white p-2 rounded mb-1">
                                      <div className="flex justify-between items-start">
                                        <div className="flex-1">
                                          <div className="font-semibold text-gray-800">{alloc.mukkadam_name}</div>
                                          <div className="text-gray-600 flex justify-between">
                                            <span>{alloc.allocated_area} acres</span>
                                            {alloc.crew_size && (
                                              <span className="text-indigo-600 font-semibold">👥 {alloc.crew_size}</span>
                                            )}
                                          </div>
                                        </div>
                                        <button
                                          onClick={() => {
                                            const fullAllocation = allocations.find(
                                              (a) => a.mukkadam_id === alloc.mukkadam_id && a.farmer_work_id === job.work_id
                                            );
                                            if (fullAllocation) {
                                              setAllocationToEdit(fullAllocation);
                                              setShowEditModal(true);
                                            }
                                          }}
                                          className="ml-2 p-1 text-orange-600 hover:bg-orange-100 rounded"
                                          title="Reallocate"
                                        >
                                          <Edit size={14} />
                                        </button>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    })()}
  </div>
)}


{/* Mukkadams Tab */}
{activeTab === 'mukkadams' && (
  <div>
    {/* Search Input */}
    <div className="mb-4">
      <div className="relative">
        <input
          type="text"
          placeholder="Search by name, village, mobile, or job ID..."
          value={mukkadamSearchQuery}
          onChange={(e) => setMukkadamSearchQuery(e.target.value)}
          className="w-full px-4 py-3 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        />
        <Search className="absolute left-3 top-3.5 text-gray-400" size={20} />
        {mukkadamSearchQuery && (
          <button
            onClick={() => setMukkadamSearchQuery('')}
            className="absolute right-3 top-3 text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        )}
      </div>
      {mukkadamSearchQuery && (
        <p className="text-sm text-gray-600 mt-2">
          Found {filteredMukkadamAllocations.length} of {mukkadamAllocations.length} mukkadams
        </p>
      )}
    </div>

    {filteredMukkadamAllocations.length === 0 ? (
      <div className="text-center py-12">
        <Users size={48} className="mx-auto text-gray-400 mb-4" />
        <p className="text-gray-600">
          {mukkadamSearchQuery ? 'No mukkadams match your search' : 'No mukkadam allocations found'}
        </p>
        {mukkadamSearchQuery && (
          <button
            onClick={() => setMukkadamSearchQuery('')}
            className="mt-4 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
          >
            Clear Search
          </button>
        )}
      </div>
    ) : (
      <div className="space-y-3">
        {filteredMukkadamAllocations
          .filter((ma) => ma.mukkadam.is_permanent === true)
          // ✅ UPDATED: Alphabetical Sorting (A to Z)
          .sort((a, b) => a.mukkadam.mukkadam_name.localeCompare(b.mukkadam.mukkadam_name))
          .map((ma) => {
            const isExpanded = expandedMukkadams.has(ma.mukkadam.id);
            
            return (
              <div 
                key={ma.mukkadam.id}
                className="bg-white rounded-xl shadow-md border border-indigo-200 overflow-hidden"
              >
                {/* Compact Header */}
                <div
                  className="p-4 cursor-pointer hover:bg-indigo-50 transition"
                  onClick={() => toggleMukkadam(ma.mukkadam.id)}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-4 flex-1">
                      <div className="w-12 h-12 bg-indigo-500 rounded-full flex items-center justify-center text-white text-xl font-bold">
                        {ma.mukkadam.mukkadam_name.charAt(0)}
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-gray-900">{ma.mukkadam.mukkadam_name}</h3>
                        <p className="text-sm text-gray-600">
                          {ma.mukkadam.village} • Crew: {ma.mukkadam.crew_size}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-6">
                      <div className="text-right">
                        <p className="text-sm text-gray-600">{ma.job_count} jobs</p>
                        <p className="text-2xl font-bold text-indigo-600">
                          ₹{(ma.total_price / 1000).toFixed(1)}K
                        </p>

                        {/* Paid Amount Badge */}
                        <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          <CheckCircle size={10} className="mr-1" />
                          Paid: ₹{(ma.paid_amount / 1000).toFixed(1)}K
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="text-indigo-600" size={24} />
                      ) : (
                        <ChevronDown className="text-indigo-600" size={24} />
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-indigo-200 animate-fadeIn">
                    <div className="mt-4">
                      <h4 className="font-semibold text-gray-900 mb-3">Recent Jobs</h4>
                      <div className="space-y-2">
                        {ma.allocations.map((allocation) => (
                          <div 
                            key={allocation.id}
                            className="p-3 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 transition"
                          >
                            <div className="flex justify-between items-center">
                              <div className="flex-1">
                                <div className="flex items-center space-x-2 mb-1">
                                  <span className="font-mono text-sm font-bold text-blue-600">
                                    {allocation.farmer_work_id}
                                  </span>
                                  {allocation.work_date && (
                                    <span className="text-xs text-gray-500">
                                      {new Date(allocation.work_date).toLocaleDateString()}
                                    </span>
                                  )}
                                </div>
                                {allocation.allocated_area && (
                                  <p className="text-xs text-gray-600">
                                    {allocation.allocated_area} acres • {allocation.crew_size || ma.mukkadam.crew_size} workers
                                  </p>
                                )}
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-bold text-green-600">
                                  ₹{(parseFloat(allocation.mukkadam_price?.toString() || '0')).toLocaleString()}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    )}
  </div>
)}

{/* Transport Tab */}
{activeTab === 'transport' && (
  <div>
    {/* Search Input */}
    <div className="mb-4">
      <div className="relative">
        <input
          type="text"
          placeholder="Search by name, location, mobile, or job ID..."
          value={transportSearchQuery}
          onChange={(e) => setTransportSearchQuery(e.target.value)}
          className="w-full px-4 py-3 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
        />
        <Search className="absolute left-3 top-3.5 text-gray-400" size={20} />
        {transportSearchQuery && (
          <button
            onClick={() => setTransportSearchQuery('')}
            className="absolute right-3 top-3 text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        )}
      </div>
      {transportSearchQuery && (
        <p className="text-sm text-gray-600 mt-2">
          Found {filteredTransportAllocations.length} of {transportAllocations.length} transport providers
        </p>
      )}
    </div>

    {filteredTransportAllocations.length === 0 ? (
      <div className="text-center py-12">
        <Truck size={48} className="mx-auto text-gray-400 mb-4" />
        <p className="text-gray-600">
          {transportSearchQuery ? 'No transport providers match your search' : 'No transport allocations found'}
        </p>
        {transportSearchQuery && (
          <button
            onClick={() => setTransportSearchQuery('')}
            className="mt-4 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
          >
            Clear Search
          </button>
        )}
      </div>
    ) : (
      <div className="space-y-3">
        {filteredTransportAllocations
          // ✅ UPDATED: Alphabetical Sorting (A to Z) based on provider name
          .sort((a, b) => a.provider.name.localeCompare(b.provider.name))
          .map((ta) => {
            const isExpanded = expandedTransporters.has(ta.provider.id);
            
            return (
              <div 
                key={ta.provider.id}
                className="bg-white rounded-xl shadow-md border border-orange-200 overflow-hidden"
              >
                {/* Compact Header */}
                <div
                  className="p-4 cursor-pointer hover:bg-orange-50 transition"
                  onClick={() => toggleTransporter(ta.provider.id)}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-4 flex-1">
                      <div className="w-12 h-12 bg-orange-500 rounded-full flex items-center justify-center text-white text-xl font-bold">
                        <Truck size={24} />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-gray-900">{ta.provider.name}</h3>
                        <p className="text-sm text-gray-600">
                          {ta.provider.base_location} • Max: {ta.provider.max_distance}km
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-6">
                      <div className="text-right">
                        <p className="text-sm text-gray-600">{ta.job_count} jobs</p>
                        <p className="text-2xl font-bold text-orange-600">
                          ₹{(ta.total_price / 1000).toFixed(1)}K
                        </p>
                        {/* Paid Amount Badge */}
                        <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            <CheckCircle size={10} className="mr-1" />
                            Paid: ₹{(ta.paid_amount / 1000).toFixed(1)}K
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="text-orange-600" size={24} />
                      ) : (
                        <ChevronDown className="text-orange-600" size={24} />
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-orange-200 animate-fadeIn">
                    <div className="mt-4">
                      <h4 className="font-semibold text-gray-900 mb-3">Recent Jobs</h4>
                      <div className="space-y-2">
                        {ta.allocations.map((allocation) => (
                          <div 
                            key={allocation.id}
                            className="p-3 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 transition"
                          >
                            <div className="flex justify-between items-center">
                              <div className="flex-1">
                                <div className="flex items-center space-x-2 mb-1">
                                  <span className="font-mono text-sm font-bold text-blue-600">
                                    {allocation.farmer_work_id}
                                  </span>
                                  {allocation.work_date && (
                                    <span className="text-xs text-gray-500">
                                      {new Date(allocation.work_date).toLocaleDateString()}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-bold text-orange-600">
                                  ₹{(parseFloat(allocation.transport_price?.toString() || '0')).toLocaleString()}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    )}
  </div>
)}

{activeTab === 'activity' && (
  <div>
    {/* ✅ ENHANCED FILTER BAR WITH DATE */}
    <div className="mb-6 space-y-4">
      {/* Row 1: Activity Type Filter Buttons */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => setActivityFilter('all')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activityFilter === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All Activities
        </button>
        <button
          onClick={() => setActivityFilter('allocation_created')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activityFilter === 'allocation_created'
              ? 'bg-green-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          <Plus size={16} className="inline mr-1" />
          Allocations
        </button>
        <button
          onClick={() => setActivityFilter('allocation_updated')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activityFilter === 'allocation_updated'
              ? 'bg-orange-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          <Edit size={16} className="inline mr-1" />
          Updates
        </button>
        <button
          onClick={() => setActivityFilter('payment')}
          className={`px-4 py-2 rounded-lg font-medium transition ${
            activityFilter === 'payment'
              ? 'bg-purple-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          <DollarSign size={16} className="inline mr-1" />
          Payments
        </button>
      </div>

      {/* Row 2: Search + Date Filter */}
      <div className="flex gap-4">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search by job ID, mukkadam, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Date Filter */}
        <div className="flex gap-2">
          <input
            type="date"
            value={selectedFilterDate}
            onChange={(e) => setSelectedFilterDate(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          {selectedFilterDate && (
            <button
              onClick={() => setSelectedFilterDate('')}
              className="px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 font-medium"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>

    {/* ✅ ACTIVITY LOGS LIST WITH EXPANDABLE CARDS */}
    {(() => {
      // Filter logs
      const filtered = (Array.isArray(activityLogs) ? activityLogs : []).filter(log => {
        // Date Filter
        if (selectedFilterDate) {
          const logDate = new Date(log.performed_at || log.timestamp).toISOString().split('T')[0];
          if (logDate !== selectedFilterDate) return false;
        }

        // Search Filter
        const searchLower = searchTerm.toLowerCase();
        const matchesSearch = 
          String(log.job_id || '').toLowerCase().includes(searchLower) ||
          String(log.mukkadam_name || '').toLowerCase().includes(searchLower) ||
          String(log.transport_name || '').toLowerCase().includes(searchLower) ||
          String(log.performed_by_name || '').toLowerCase().includes(searchLower) ||
          String(log.description || '').toLowerCase().includes(searchLower);
        
        if (!matchesSearch) return false;
        
        // Activity Type Filter
        if (activityFilter === 'all') return true;
        if (activityFilter === 'payment') {
          return log.activity_type.includes('payment');
        }
        return log.activity_type === activityFilter;
      });

      if (filtered.length === 0) {
        return (
          <div className="text-center py-12">
            <Activity size={48} className="mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">No activity logs found</p>
          </div>
        );
      }

      return (
        <div className="space-y-3">
          {filtered.map((log) => {
            const isExpanded = expandedActivities.has(log.id.toString());
            
            // Determine icon and colors
            let icon, bgColor, borderColor, iconColor;
            
            switch (log.activity_type) {
              case 'allocation_created':
                icon = <Plus size={20} />;
                bgColor = 'bg-green-50';
                borderColor = 'border-green-500';
                iconColor = 'text-green-600';
                break;
              case 'allocation_updated':
              case 'activity_marked_edited':
                icon = <Edit size={20} />;
                bgColor = 'bg-orange-50';
                borderColor = 'border-orange-500';
                iconColor = 'text-orange-600';
                break;
              case 'activity_marked_lost':
                icon = <Ban size={20} />;
                bgColor = 'bg-red-50';
                borderColor = 'border-red-500';
                iconColor = 'text-red-600';
                break;
              case 'activity_marked_restored':
                icon = <CheckCircle size={20} />;
                bgColor = 'bg-green-50';
                borderColor = 'border-green-500';
                iconColor = 'text-green-600';
                break;
              case 'payment_requested':
                icon = <DollarSign size={20} />;
                bgColor = 'bg-yellow-50';
                borderColor = 'border-yellow-500';
                iconColor = 'text-yellow-600';
                break;
              case 'payment_paid':
              case 'transport_payment_paid':
                icon = <CheckCircle size={20} />;
                bgColor = 'bg-green-50';
                borderColor = 'border-green-500';
                iconColor = 'text-green-600';
                break;
              case 'payment_rejected':
              case 'transport_payment_rejected':
                icon = <Ban size={20} />;
                bgColor = 'bg-red-50';
                borderColor = 'border-red-500';
                iconColor = 'text-red-600';
                break;
              default:
                icon = <Activity size={20} />;
                bgColor = 'bg-gray-50';
                borderColor = 'border-gray-500';
                iconColor = 'text-gray-600';
            }

            // Extract changes for display
            const hasChanges = log.changes && Object.keys(log.changes).length > 0;
            const changedFields = hasChanges ? Object.keys(log.changes) : [];

            return (
              <div
                key={log.id}
                className={`${bgColor} rounded-xl border-l-4 ${borderColor} hover:shadow-md transition cursor-pointer`}
                onClick={() => toggleActivity(log.id.toString())}
              >
                {/* ✅ COLLAPSED VIEW - Always Visible */}
                <div className="p-4">
                  <div className="flex items-start space-x-4">
                    {/* Icon */}
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${bgColor} ${iconColor} border-2 ${borderColor}`}>
                      {icon}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      {/* Header Row */}
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center space-x-2 flex-wrap">
                          <span className={`px-2 py-1 ${bgColor} ${iconColor} rounded-full text-xs font-bold border ${borderColor}`}>
                            {log.activity_type_display || log.activity_type?.replace(/_/g, ' ')}
                          </span>
                          <span className="font-mono text-sm font-bold text-blue-600">
                            {log.job_id}
                          </span>
                          {log.metadata?.activity_name && (
                            <span className="text-sm text-gray-600">
                              • {log.metadata.activity_name}
                            </span>
                          )}
                        </div>
                        
                        {/* Date + Expand Icon */}
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-500">
                            {new Date(log.timestamp || log.performed_at).toLocaleDateString('en-IN', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </span>
                          {isExpanded ? (
                            <ChevronUp size={20} className={iconColor} />
                          ) : (
                            <ChevronDown size={20} className={iconColor} />
                          )}
                        </div>
                      </div>

                      {/* Description */}
                      <p className="text-sm text-gray-700 mb-2">{log.description}</p>

                      {/* Quick Info Row */}
                      <div className="flex items-center gap-4 text-xs text-gray-600">
                        <span>👤 {log.performed_by_name || 'System'}</span>
                        {log.mukkadam_name && log.mukkadam_name !== 'N/A (Job-level)' && (
                          <span>🔧 {log.mukkadam_name}</span>
                        )}
                        {log.amount && (
                          <span className={`font-bold ${iconColor}`}>
                            ₹{log.amount.toLocaleString()}
                          </span>
                        )}
                        {hasChanges && (
                          <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-medium">
                            {changedFields.length} field{changedFields.length > 1 ? 's' : ''} changed
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* ✅ EXPANDED VIEW - Details Section */}
                {isExpanded && (
                  <div className="px-4 pb-4 border-t border-gray-200 pt-4 bg-white">
                    {/* Admin: Show Reason */}
                    {isAdmin && log.reason && (
                      <div className="mb-4 p-3 bg-yellow-50 border-2 border-yellow-300 rounded-lg">
                        <p className="text-xs font-bold text-yellow-800 mb-1 flex items-center">
                          <AlertCircle size={14} className="mr-1" />
                          Reason for Change (Admin Only)
                        </p>
                        <p className="text-sm text-yellow-900 font-medium">
                          {log.reason}
                        </p>
                      </div>
                    )}

                    {/* Changes Section */}
                    {hasChanges && (
                      <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                        <p className="text-sm font-bold text-gray-800 mb-3 flex items-center">
                          <Edit size={14} className="mr-2" />
                          Changes Made ({changedFields.length})
                        </p>

                        <div className="space-y-3">
                          {Object.entries(log.changes).map(([field, changeData]: [string, any]) => {
                            const fieldLabel = field
                              .replace(/_/g, ' ')
                              .replace(/\b\w/g, (l) => l.toUpperCase());

                            return (
                              <div key={field} className="bg-white p-3 rounded border border-gray-200">
                                {/* Admin: Show Full Details */}
                                {isAdmin ? (
                                  <>
                                    <p className="text-xs font-semibold text-gray-700 mb-2">
                                      {fieldLabel}
                                    </p>
                                    <div className="flex items-center gap-2 text-xs">
                                      <span className="px-2 py-1 bg-red-100 text-red-700 rounded font-mono line-through">
                                        {changeData.old_value || changeData.old || 'Not set'}
                                      </span>
                                      <span className="text-gray-400">→</span>
                                      <span className="px-2 py-1 bg-green-100 text-green-700 rounded font-mono font-semibold">
                                        {changeData.new_value || changeData.new}
                                      </span>
                                    </div>
                                  </>
                                ) : (
                                  /* Non-Admin: Only Show Field Name */
                                  <p className="text-sm font-medium text-gray-700">
                                    {fieldLabel} was updated
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Full Details Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-gray-50 p-3 rounded">
                      <div>
                        <p className="text-gray-500 font-medium">Mukkadam</p>
                        <p className="font-semibold text-gray-900">{log.mukkadam_name}</p>
                      </div>
                      {log.transport_name && (
                        <div>
                          <p className="text-gray-500 font-medium">Transport</p>
                          <p className="font-semibold text-gray-900">{log.transport_name}</p>
                        </div>
                      )}
                      {log.amount && (
                        <div>
                          <p className="text-gray-500 font-medium">Amount</p>
                          <p className={`font-bold ${iconColor}`}>
                            ₹{log.amount.toLocaleString()}
                          </p>
                        </div>
                      )}
                      <div>
                        <p className="text-gray-500 font-medium">Performed By</p>
                        <p className="font-semibold text-gray-900">
                          {log.performed_by_name || 'System'}
                        </p>
                      </div>
                    </div>

                    {/* View Allocation Link */}
                    {log.allocation_id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/allocations/${log.allocation_id}`);
                        }}
                        className="mt-3 text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center"
                      >
                        <Eye size={12} className="mr-1" />
                        View Allocation Details
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    })()}
  </div>
)}
{activeTab === 'lost' && (
  <div>
    <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
      <p className="text-sm text-red-800">
        <Ban className="inline mr-2" size={16} />
        These jobs have at least one activity marked as <strong>LOST</strong>. 
        Lost activities are excluded from revenue calculations.
      </p>
    </div>

    {(() => {
      const lostJobs = jobs.filter(job => 
        job.activities?.some(a => a.is_lost)
      );

      if (lostJobs.length === 0) {
        return (
          <div className="text-center py-12 bg-white rounded-xl border border-dashed">
            <Ban size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-600">No lost jobs</p>
          </div>
        );
      }

      return (
        <div className="space-y-3">
          {lostJobs.map(job => {
            const lostActivities = job.activities.filter(a => a.is_lost);
            
            return (
              <div key={job.work_id} className="border-2 border-red-300 bg-red-50 rounded-xl p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center space-x-2 mb-2">
                      <span className="font-mono font-bold text-blue-600">{job.work_id}</span>
                      <span className="px-2 py-1 bg-red-500 text-white rounded-full text-xs font-bold">
                        {lostActivities.length} LOST
                      </span>
                    </div>
                    {job.farmer && (
                      <p className="text-sm text-gray-700">
                        {job.farmer.farmer_name} • {job.farmer.phone_number}
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-semibold text-gray-800 text-sm">Lost Activities:</h4>
                  {lostActivities.map(activity => (
                    <div key={activity.activity_id} className="bg-white border-2 border-red-200 rounded-lg p-3">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <Ban size={14} className="text-red-600" />
                            <span className="font-semibold text-gray-800 line-through">
                              {activity.activity_name}
                            </span>
                          </div>
                          <p className="text-xs text-gray-600">
                            Area: {activity.total_area} acres • Price: ₹{activity.total_price}
                          </p>
                          <div className="mt-2 bg-red-100 border border-red-300 rounded p-2">
                            <p className="text-xs text-red-800">
                              <strong>Reason:</strong> {activity.lost_reason}
                            </p>
                          </div>
                        </div>
                        
                        {isAdmin && (
                          <button
                            onClick={() => handleUnmarkActivityLost(activity, job.work_id)}
                            className="ml-3 px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 text-xs font-bold"
                          >
                            Restore
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      );
    })()}
  </div>
)}

{/* ✅ ENHANCED EDIT ACTIVITY MODAL - WITH INDIVIDUAL COSTS */}
{showEditActivityModal && selectedActivityForEdit && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div className="bg-white rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-gray-900">Edit Activity</h3>
        <button onClick={() => {
          setShowEditActivityModal(false);
          setEditReason('');
          setEditFormData({
            activity_name: '',
            total_area: 0,
            scheduled_date: '',
            total_price: 0,
            transport_cost: 0,
            other_cost: 0,
            rate_per_acre: 0
          });
        }} className="text-gray-400 hover:text-gray-600">
          <X size={20} />
        </button>
      </div>
      
      {/* Job Info */}
      <div className="mb-4 bg-blue-50 border border-blue-200 rounded p-3">
        <p className="text-sm text-gray-700">
          <strong>Job ID:</strong> {selectedJobForEdit?.work_id}
        </p>
      </div>

      {/* Editable Fields */}
      <div className="space-y-4 mb-4">
        {/* Activity Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Activity Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={editFormData.activity_name}
            onChange={(e) => setEditFormData({...editFormData, activity_name: e.target.value})}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="e.g., Pasting, Pruning"
          />
        </div>

        {/* Total Area */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Total Area (acres) <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={editFormData.total_area}
            onChange={(e) => {
              const newArea = parseFloat(e.target.value) || 0;
              const subtotal = editFormData.total_price + editFormData.transport_cost + editFormData.other_cost;
              const newRatePerAcre = newArea > 0 ? subtotal / newArea : 0;
              setEditFormData({
                ...editFormData, 
                total_area: newArea,
                rate_per_acre: newRatePerAcre
              });
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="14.00"
          />
        </div>

        {/* Scheduled Date */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Scheduled Date <span className="text-red-500">*</span>
          </label>
          <input
            type="date"
            value={editFormData.scheduled_date}
            onChange={(e) => setEditFormData({...editFormData, scheduled_date: e.target.value})}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* ✅ COST BREAKDOWN SECTION */}
        <div className="border-t-2 border-purple-200 pt-4">
          <h4 className="font-semibold text-gray-800 mb-3 flex items-center">
            <DollarSign size={18} className="mr-2 text-purple-600" />
            Cost Breakdown
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Mukkadam Price */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Mukkadam Price (₹) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={editFormData.total_price}
                onChange={(e) => {
                  const newMukkadamPrice = parseFloat(e.target.value) || 0;
                  const subtotal = newMukkadamPrice + editFormData.transport_cost + editFormData.other_cost;
                  const newRatePerAcre = editFormData.total_area > 0 ? subtotal / editFormData.total_area : 0;
                  setEditFormData({
                    ...editFormData, 
                    total_price: newMukkadamPrice,
                    rate_per_acre: newRatePerAcre
                  });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                placeholder="100.00"
              />
            </div>

            {/* Transport Cost */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Transport Cost (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={editFormData.transport_cost}
                onChange={(e) => {
                  const newTransportCost = parseFloat(e.target.value) || 0;
                  const subtotal = editFormData.total_price + newTransportCost + editFormData.other_cost;
                  const newRatePerAcre = editFormData.total_area > 0 ? subtotal / editFormData.total_area : 0;
                  setEditFormData({
                    ...editFormData, 
                    transport_cost: newTransportCost,
                    rate_per_acre: newRatePerAcre
                  });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500"
                placeholder="100.00"
              />
            </div>

            {/* Other Cost */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Other Cost (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={editFormData.other_cost}
                onChange={(e) => {
                  const newOtherCost = parseFloat(e.target.value) || 0;
                  const subtotal = editFormData.total_price + editFormData.transport_cost + newOtherCost;
                  const newRatePerAcre = editFormData.total_area > 0 ? subtotal / editFormData.total_area : 0;
                  setEditFormData({
                    ...editFormData, 
                    other_cost: newOtherCost,
                    rate_per_acre: newRatePerAcre
                  });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="100.00"
              />
            </div>
          </div>

          {/* Subtotal Display */}
          <div className="mt-4 bg-purple-50 border-2 border-purple-300 rounded-lg p-3">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-gray-700">Subtotal (Auto-calculated):</span>
              <span className="text-2xl font-bold text-purple-600">
                ₹{(editFormData.total_price + editFormData.transport_cost + editFormData.other_cost).toFixed(2)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Mukkadam (₹{editFormData.total_price.toFixed(2)}) + Transport (₹{editFormData.transport_cost.toFixed(2)}) + Other (₹{editFormData.other_cost.toFixed(2)})
            </p>
          </div>
        </div>

        {/* Rate Per Acre (Auto-calculated, Read-only) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Rate Per Acre (₹) <span className="text-gray-500">(Auto-calculated)</span>
          </label>
          <input
            type="text"
            value={`₹${editFormData.rate_per_acre.toFixed(2)}`}
            readOnly
            className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600 cursor-not-allowed"
          />
          <p className="text-xs text-gray-500 mt-1">
            Calculated as: Subtotal ÷ Total Area
          </p>
        </div>
      </div>

      {/* Reason for Editing */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Reason for Editing <span className="text-red-500">*</span>
        </label>
        <textarea
          value={editReason}
          onChange={(e) => setEditReason(e.target.value)}
          placeholder="e.g., Updated cost breakdown after negotiation with farmer"
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Summary Box */}
      <div className="mb-4 bg-green-50 border border-green-200 rounded p-3">
        <h4 className="font-semibold text-sm text-gray-800 mb-2">Summary of Changes:</h4>
        <div className="space-y-1 text-xs text-gray-700">
          {editFormData.activity_name !== selectedActivityForEdit.activity_name && (
            <p>• Name: <span className="line-through text-red-600">{selectedActivityForEdit.activity_name}</span> → <span className="font-bold text-green-600">{editFormData.activity_name}</span></p>
          )}
          {editFormData.total_area !== selectedActivityForEdit.total_area && (
            <p>• Area: <span className="line-through text-red-600">{selectedActivityForEdit.total_area} acres</span> → <span className="font-bold text-green-600">{editFormData.total_area} acres</span></p>
          )}
          {editFormData.scheduled_date !== selectedActivityForEdit.scheduled_date && (
            <p>• Date: <span className="line-through text-red-600">{selectedActivityForEdit.scheduled_date || 'Not set'}</span> → <span className="font-bold text-green-600">{editFormData.scheduled_date}</span></p>
          )}
          {editFormData.total_price !== selectedActivityForEdit.total_price && (
            <p>• Mukkadam Price: <span className="line-through text-red-600">₹{selectedActivityForEdit.total_price}</span> → <span className="font-bold text-green-600">₹{editFormData.total_price}</span></p>
          )}
          {editFormData.transport_cost !== (selectedActivityForEdit.transport_cost || 0) && (
            <p>• Transport Cost: <span className="line-through text-red-600">₹{selectedActivityForEdit.transport_cost || 0}</span> → <span className="font-bold text-green-600">₹{editFormData.transport_cost}</span></p>
          )}
          {editFormData.other_cost !== (selectedActivityForEdit.other_cost || 0) && (
            <p>• Other Cost: <span className="line-through text-red-600">₹{selectedActivityForEdit.other_cost || 0}</span> → <span className="font-bold text-green-600">₹{editFormData.other_cost}</span></p>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <button
          onClick={() => {
            setShowEditActivityModal(false);
            setEditReason('');
            setEditFormData({
              activity_name: '',
              total_area: 0,
              scheduled_date: '',
              total_price: 0,
              transport_cost: 0,
              other_cost: 0,
              rate_per_acre: 0
            });
          }}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
        >
          Cancel
        </button>
        <button
          onClick={() => handleEditActivity(selectedActivityForEdit, selectedJobForEdit.work_id)}
          disabled={!editReason.trim() || !editFormData.activity_name || editFormData.total_area <= 0 || editFormData.total_price < 0}
          className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
        >
          Save Changes
        </button>
      </div>
    </div>
  </div>
)}
{/* ✅ MARK LOST MODAL */}
{showMarkLostModal && selectedActivityForEdit && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div className="bg-white rounded-xl p-6 max-w-md w-full">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-red-600 flex items-center">
          <Ban size={20} className="mr-2" />
          Mark Activity as Lost
        </h3>
        <button onClick={() => {
          setShowMarkLostModal(false);
          setLostReason('');
        }} className="text-gray-400 hover:text-gray-600">
          <X size={20} />
        </button>
      </div>
      
      <div className="mb-4 bg-red-50 border border-red-200 rounded p-3">
        <p className="text-sm text-red-800">
          <AlertCircle size={16} className="inline mr-1" />
          This activity will be excluded from revenue calculations
        </p>
      </div>

      <div className="mb-4">
        <p className="text-sm text-gray-600 mb-2">
          <strong>Job:</strong> {selectedJobForEdit?.work_id}
        </p>
        <p className="text-sm text-gray-600 mb-2">
          <strong>Activity:</strong> {selectedActivityForEdit.activity_name}
        </p>
        <p className="text-sm text-gray-600">
          <strong>Revenue Loss:</strong> ₹{selectedActivityForEdit.total_price}
        </p>
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Reason for Marking as Lost <span className="text-red-500">*</span>
        </label>
        <textarea
          value={lostReason}
          onChange={(e) => setLostReason(e.target.value)}
          placeholder="e.g., Farmer cancelled the work"
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
        />
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => {
            setShowMarkLostModal(false);
            setLostReason('');
          }}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={() => handleMarkActivityLost(selectedActivityForEdit, selectedJobForEdit.work_id)}
          disabled={!lostReason.trim()}
          className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          Mark as Lost
        </button>
      </div>
    </div>
  </div>
)}

                           
          </div>
        </div>

        {/* Active Workers Modal */}
{showActiveWorkersModal && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto">
      {/* Modal Header */}
      <div className="bg-gradient-to-r from-teal-600 to-cyan-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
        <div>
          <h2 className="text-2xl font-bold text-white">Active Workers</h2>
          <p className="text-white text-sm opacity-90">
            {totalActiveWorkers} workers on {activeAllocations.length} jobs
          </p>
        </div>
        <button
          onClick={() => setShowActiveWorkersModal(false)}
          className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-full transition"
        >
          <X size={24} />
        </button>
      </div>

      {/* Modal Content */}
      <div className="p-6">
        {workerDetails.length === 0 ? (
          <div className="text-center py-12">
            <Users size={48} className="mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">No active workers at the moment</p>
            <p className="text-sm text-gray-500 mt-2">
              Workers are considered active if their work date is today or in the future
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-teal-50 p-4 rounded-lg border border-teal-200">
                <p className="text-sm text-gray-600">Total Active Workers</p>
                <p className="text-3xl font-bold text-teal-600">{totalActiveWorkers}</p>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <p className="text-sm text-gray-600">Active Mukkadams</p>
                <p className="text-3xl font-bold text-blue-600">{workerDetails.length}</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
                <p className="text-sm text-gray-600">Active Jobs</p>
                <p className="text-3xl font-bold text-purple-600">{activeAllocations.length}</p>
              </div>
            </div>

            {/* Workers by Mukkadam */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-gray-900 border-b pb-2">
                Workers by Mukkadam
              </h3>
              
              {workerDetails.map((detail, index) => (
                <div 
                  key={detail.mukkadam?.id || index} 
                  className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl p-6 border border-gray-200"
                >
                  {/* Mukkadam Header */}
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center space-x-4">
                      <div className="w-12 h-12 bg-teal-500 rounded-full flex items-center justify-center text-white text-xl font-bold">
                        {detail.mukkadam?.mukkadam_name?.charAt(0) || '?'}
                      </div>
                      <div>
                        <h4 className="text-lg font-bold text-gray-900">
                          {detail.mukkadam?.mukkadam_name || 'Unknown Mukkadam'}
                        </h4>
                        <p className="text-sm text-gray-600">
                          {detail.mukkadam?.mobile_numbers} • {detail.mukkadam?.village}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-600">Total Workers</p>
                      <p className="text-3xl font-bold text-teal-600">{detail.totalWorkers}</p>
                      <p className="text-xs text-gray-500">{detail.allocations.length} jobs</p>
                    </div>
                  </div>

                  {/* Jobs List */}
                  <div className="mt-4 space-y-2">
                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Active Jobs:</h5>
                    {detail.allocations
                      .sort((a, b) => new Date(a.work_date!).getTime() - new Date(b.work_date!).getTime())
                      .map(allocation => {
                        const workDate = new Date(allocation.work_date!);
                        const isToday = workDate.toDateString() === today.toDateString();
                        const daysUntil = Math.ceil((workDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
                        
                        return (
                          <div 
                            key={allocation.id} 
                            className={`bg-white p-4 rounded-lg border-2 ${
                              isToday ? 'border-green-400 bg-green-50' : 'border-gray-200'
                            }`}
                          >
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <div className="flex items-center space-x-2 mb-2">
                                  <span className="font-mono text-sm font-bold text-blue-600">
                                    {allocation.farmer_work_id}
                                  </span>
                                  {isToday && (
                                    <span className="px-2 py-1 bg-green-500 text-white rounded text-xs font-bold">
                                      TODAY
                                    </span>
                                  )}
                                  {daysUntil > 0 && !isToday && (
                                    <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                                      In {daysUntil} day{daysUntil > 1 ? 's' : ''}
                                    </span>
                                  )}
                                </div>
                                
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                  <div>
                                    <p className="text-gray-500 text-xs">Work Date</p>
                                    <p className="font-semibold text-gray-900">
                                      {workDate.toLocaleDateString('en-IN', {
                                        month: 'short',
                                        day: 'numeric',
                                        year: 'numeric'
                                      })}
                                    </p>
                                  </div>
                                  <div>
                                    <p className="text-gray-500 text-xs">Workers</p>
                                    <p className="font-bold text-teal-600 flex items-center">
                                      <Users size={14} className="mr-1" />
                                      {allocation.crew_size || 'N/A'}
                                    </p>
                                  </div>
                                  <div>
                                    <p className="text-gray-500 text-xs">Area</p>
                                    <p className="font-semibold text-gray-900">
                                      {allocation.allocated_area || 'N/A'} acres
                                    </p>
                                  </div>
                                  <div>
                                    <p className="text-gray-500 text-xs">Total Cost</p>
                                    <p className="font-bold text-purple-600">
                                      ₹{((allocation.mukkadam_price || 0) + (allocation.transport_price || 0)).toLocaleString()}
                                    </p>
                                  </div>
                                </div>

                                {allocation.notes && allocation.notes.includes('Activity ID:') && (
                                  <div className="mt-2 text-xs text-gray-600">
                                    📋 {allocation.notes.split('\n')[1]?.replace('Activity ID: ', 'Activity: ') || 'Complex job'}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              ))}
            </div>

            {/* Timeline View */}
            <div className="mt-8">
              <h3 className="text-lg font-bold text-gray-900 border-b pb-2 mb-4">
                Timeline (Next 14 Days)
              </h3>
              <div className="space-y-2">
                {Array.from({ length: 14 }, (_, i) => {
                  const date = new Date(today);
                  date.setDate(date.getDate() + i);
                  const dateStr = date.toISOString().split('T')[0];
                  
                  const dayAllocations = activeAllocations.filter(a => 
                    a.work_date && a.work_date.split('T')[0] === dateStr
                  );
                  
                  const dayWorkers = dayAllocations.reduce((sum, a) => sum + (a.crew_size || 0), 0);
                  
                  if (dayWorkers === 0) return null;
                  
                  return (
                    <div key={dateStr} className="flex items-center">
                      <div className="w-32 flex-shrink-0">
                        <p className="text-sm font-semibold text-gray-700">
                          {date.toLocaleDateString('en-IN', { 
                            weekday: 'short', 
                            month: 'short', 
                            day: 'numeric' 
                          })}
                        </p>
                        {i === 0 && (
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                            Today
                          </span>
                        )}
                      </div>
                      <div className="flex-1 ml-4">
                        <div className="bg-gray-200 rounded-full h-8 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-teal-500 to-cyan-600 h-full flex items-center justify-end pr-3"
                            style={{ 
                              width: `${(dayWorkers / totalActiveWorkers) * 100}%`,
                              minWidth: '60px'
                            }}
                          >
                            <span className="text-white text-sm font-bold flex items-center">
                              <Users size={14} className="mr-1" />
                              {dayWorkers}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="ml-4 w-20 text-right">
                        <span className="text-sm text-gray-600">
                          {dayAllocations.length} job{dayAllocations.length > 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                  );
                }).filter(Boolean)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal Footer */}
      <div className="bg-gray-50 px-6 py-4 border-t sticky bottom-0">
        <button
          onClick={() => setShowActiveWorkersModal(false)}
          className="w-full px-6 py-3 bg-gray-600 text-white rounded-lg font-semibold hover:bg-gray-700 transition"
        >
          Close
        </button>
      </div>
    </div>
  </div>
)}


{/* ✅ EDIT ALLOCATION MODAL - REPLACE OLD REALLOCATE MODAL */}
{showEditModal && allocationToEdit && (() => {
  const jobForEdit = jobs.find(j => j.work_id === allocationToEdit.farmer_work_id);
  
  // ✅ ADD: Check if job exists before rendering modal
  if (!jobForEdit) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-xl p-6 max-w-md">
          <h3 className="text-lg font-bold text-red-600 mb-4">Job Not Found</h3>
          <p className="text-gray-700 mb-4">
            Could not find job {allocationToEdit.farmer_work_id} in the current list.
            This might happen if the job data hasn't fully loaded yet.
          </p>
          <button
            onClick={() => {
              setShowEditModal(false);
              setAllocationToEdit(null);
              refreshAllocations(); // Refresh data
            }}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Close & Refresh
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <ComplexAllocationModal
      job={jobForEdit}
      onClose={() => {
        setShowEditModal(false);
        setAllocationToEdit(null);
      }}
      onSuccess={() => {
        refreshAllocations();
        setShowEditModal(false);
        setAllocationToEdit(null);
      }}
      mukkadams={mukkadams}
      transportProviders={transportProviders}
      editMode={true}
      existingAllocation={allocationToEdit}
    />
  );
})()}
        
      </div>

    
      {/* Allocation Modal */}
      {showAllocationModal && selectedJob && !selectedJob.is_complex && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
              <h2 className="text-2xl font-bold text-white">Allocate Job</h2>
              <button
                onClick={closeAllocationModal}
                className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-full transition"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Content */}
            <form onSubmit={handleAllocationSubmit} className="p-6 space-y-6">
              
              {/* Job Info */}
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <p className="text-sm text-gray-600 mb-1">Job ID</p>
                <p className="text-2xl font-bold font-mono text-blue-600">{selectedJob.work_id}</p>
                {selectedJob.title && (
                  <p className="text-sm text-gray-700 mt-2">{selectedJob.title}</p>
                )}
              </div>

              {/* Mukkadam Selection */}
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-gray-900 flex items-center border-b-2 border-indigo-200 pb-2">
                  <Users className="mr-2 text-indigo-500" /> Mukkadam Details
                </h3>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Mukkadam <span className="text-red-500">*</span>
                  </label>
                  <select
                    required
                    value={allocationForm.mukkadam_id}
                    onChange={(e) => setAllocationForm({...allocationForm, mukkadam_id: e.target.value})}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value="">-- Select Mukkadam --</option>
                    {mukkadams.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.mukkadam_name} - {m.mobile_numbers} - {m.village} (Crew: {m.crew_size})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedMukkadam && (
                  <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200">
                    <h4 className="font-semibold text-gray-700 mb-2">Selected Mukkadam:</h4>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-gray-600">Name:</span>
                        <span className="font-semibold ml-2">{selectedMukkadam.mukkadam_name}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Mobile:</span>
                        <span className="font-semibold ml-2">{selectedMukkadam.mobile_numbers}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Village:</span>
                        <span className="font-semibold ml-2">{selectedMukkadam.village}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Crew Size:</span>
                        <span className="font-semibold ml-2">{selectedMukkadam.crew_size}</span>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Mukkadam Price (₹) <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
                    <input
                      required
                      type="number"
                      step="0.01"
                      min="0"
                      value={allocationForm.mukkadam_price}
                      onChange={(e) => setAllocationForm({...allocationForm, mukkadam_price: e.target.value})}
                      className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="5000.00"
                    />
                  </div>
                </div>
              </div>

              {/* Transport Provider Selection */}
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-gray-900 flex items-center border-b-2 border-orange-200 pb-2">
                  <Truck className="mr-2 text-orange-500" /> Transport Provider Details
                </h3>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Transport Provider <span className="text-red-500">*</span>
                  </label>
                  <select
                    required
                    value={allocationForm.transport_provider_id}
                    onChange={(e) => setAllocationForm({...allocationForm, transport_provider_id: e.target.value})}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                  >
                    <option value="">-- Select Transport Provider --</option>
                    {transportProviders.map(t => (
                      <option key={t.id} value={t.id}>
                        {t.name} - {t.contact_number} - {t.base_location} (Max: {t.max_distance}km)
                      </option>
                    ))}
                  </select>
                </div>

                {selectedProvider && (
                  <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                    <h4 className="font-semibold text-gray-700 mb-2">Selected Provider:</h4>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-gray-600">Name:</span>
                        <span className="font-semibold ml-2">{selectedProvider.name}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Contact:</span>
                        <span className="font-semibold ml-2">{selectedProvider.contact_number}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Base Location:</span>
                        <span className="font-semibold ml-2">{selectedProvider.base_location}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Max Distance:</span>
                        <span className="font-semibold ml-2">{selectedProvider.max_distance} km</span>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Transport Price (₹) <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-3 text-gray-500 font-semibold">₹</span>
                    <input
                      required
                      type="number"
                      step="0.01"
                      min="0"
                      value={allocationForm.transport_price}
                      onChange={(e) => setAllocationForm({...allocationForm, transport_price: e.target.value})}
                      className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                      placeholder="1500.00"
                    />
                  </div>
                </div>
              </div>

              {/* Summary */}
              {allocationForm.mukkadam_price && allocationForm.transport_price && (
                <div className="bg-green-50 p-6 rounded-lg border-2 border-green-200">
                  <h3 className="font-bold text-gray-800 mb-3">Allocation Summary</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-600">Mukkadam Price</p>
                      <p className="text-2xl font-bold text-indigo-600">₹{parseFloat(allocationForm.mukkadam_price).toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Transport Price</p>
                      <p className="text-2xl font-bold text-orange-600">₹{parseFloat(allocationForm.transport_price).toFixed(2)}</p>
                    </div>
                    <div className="col-span-2 pt-3 border-t-2 border-green-300">
                      <p className="text-sm text-gray-600">Total Cost</p>
                      <p className="text-3xl font-bold text-green-600">
                        ₹{(parseFloat(allocationForm.mukkadam_price) + parseFloat(allocationForm.transport_price)).toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex space-x-3 pt-4">
                <button
                  type="button"
                  onClick={closeAllocationModal}
                  className="flex-1 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={allocating}
                  className={`flex-1 px-6 py-3 rounded-lg font-semibold text-white transition shadow-lg ${
                    allocating
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700'
                  }`}
                >
                  {allocating ? 'Allocating...' : 'Confirm Allocation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showComplexAllocationModal && selectedComplexJob && (
        <ComplexAllocationModal
          job={selectedComplexJob}
          onClose={closeComplexAllocationModal}
          onSuccess={handleComplexAllocationSuccess}
          mukkadams={mukkadams}
          transportProviders={transportProviders}
        />
      )}
    </div>
  );
};

export default AllocationDashboard;