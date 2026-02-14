

// TotalJobsView.tsx

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Filter, Search, TrendingUp, CheckCircle, Clock, 
  XCircle, RefreshCw, ChevronDown, ChevronUp, Users, 
  MapPin, Phone, DollarSign, X, Calendar, Download,Eye,
  ArrowUpRight, ArrowDownRight, Wallet, TrendingDown,
  User, Truck, UserCheck, AlertCircle,Briefcase,Maximize2,Minimize2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getAuthConfig } from './utils/auth';
import {
  BarChart, Bar, PieChart, Pie, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts';
import LinkFarmerPaymentModal from './LinkPaymentFarmer';
import { Allocation } from './types/allocation';
// import LinkFarmerPaymentModal from './LinkFarmerPaymentModal';

const API_BASE_URL_A = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

interface Job {
  work_id: string;
  status: string;
  is_fully_lost?: boolean;
  farmer: {
    farmer_name: string;
    phone_number: string;
    location: string;
  };
  total_activities: number;
  scheduled_date?: string;
  activities: Allocation[];
}


interface PaymentSummary {
  total_revenue: number;
  total_cost: number;
  total_profit: number;
  farmer_payments_expected: number;
  farmer_payments_paid: number;
  farmer_payments_pending: number;
  mukkadam_payments_expected: number;
  mukkadam_payments_paid: number;
  mukkadam_payments_pending: number;
  transport_payments_expected: number;
  transport_payments_paid: number;
  transport_payments_pending: number;
}

const COLORS = {
  paid: '#10b981',
  pending: '#f59e0b',
  revenue: '#3b82f6',
  cost: '#ef4444',
  profit: '#8b5cf6',
};

const TotalJobsView: React.FC = () => {
  // State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    partial: 0,
    allocated: 0,
    completed: 0,
    lost: 0,
  });

  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Date range filters
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  
  // Name filters
  const [farmerNameFilter, setFarmerNameFilter] = useState('');
  const [mukkadamNameFilter, setMukkadamNameFilter] = useState('');
  const [transporterNameFilter, setTransporterNameFilter] = useState('');
  
  // Payment filters
  const [paymentTypeFilter, setPaymentTypeFilter] = useState('all');
  const [paymentStatusFilter, setPaymentStatusFilter] = useState('all');
  
  // Detail modal state
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  
  // Payment summary
  const [paymentSummary, setPaymentSummary] = useState<PaymentSummary | null>(null);
  const [showPaymentDashboard, setShowPaymentDashboard] = useState(false);
  
  // Link payment modal
  const [showLinkPaymentModal, setShowLinkPaymentModal] = useState(false);
  const [selectedActivityForLink, setSelectedActivityForLink] = useState<any>(null);
  
  // Fetch jobs
  const fetchJobs = async () => {
    setLoading(true);
    try {
      const config = getAuthConfig();
      const params = new URLSearchParams();
      
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (searchQuery) params.append('search', searchQuery);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      if (farmerNameFilter) params.append('farmer_name', farmerNameFilter);
      if (mukkadamNameFilter) params.append('mukkadam_name', mukkadamNameFilter);
      if (transporterNameFilter) params.append('transporter_name', transporterNameFilter);
      if (paymentTypeFilter !== 'all') params.append('payment_type', paymentTypeFilter);
      if (paymentStatusFilter !== 'all') params.append('payment_status', paymentStatusFilter);
      
      const response = await axios.get(
        `${API_BASE_URL_A}/ap/total-jobs/?${params.toString()}`,
        config
      );
      
      console.log('API Response Stats:', response.data.stats);
      
      setStats(response.data.stats);
      setJobs(response.data.jobs || []);
      setPaymentSummary(response.data.payment_summary);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setLoading(false);
    }
  };
  
const fetchJobDetails = async (jobId: string) => {
  // Clear previous data
  setJobDetail(null);
  setSelectedJobId(jobId);
  setShowDetailModal(true);
  setLoadingDetail(true);
  
  try {
    const config = getAuthConfig();
    const response = await axios.get(
      `${API_BASE_URL_A}/ap/job-details/${jobId}/`,
      config
    );
    
    // ✅ Check if response has error
    if (response.data?.error) {
      console.error('Job not found:', response.data.error);
      setJobDetail(null);
    } else {
      setJobDetail(response.data);
    }
  } catch (error: any) {
    console.error('Error fetching job details:', error);
    
    // ✅ Don't show error to user for 404s - just show "no data" state
    if (error.response?.status === 404) {
      console.log(`Job ${jobId} not found locally`);
    }
    setJobDetail(null);
  } finally {
    setLoadingDetail(false);
  }
};
  
  useEffect(() => {
    fetchJobs();
  }, [statusFilter]);
  
  // Clear all filters
  const clearAllFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setDateFrom('');
    setDateTo('');
    setFarmerNameFilter('');
    setMukkadamNameFilter('');
    setTransporterNameFilter('');
    setPaymentTypeFilter('all');
    setPaymentStatusFilter('all');
  };
  
  // Status badge
  const StatusBadge = ({ status, isFullyLost }: { status: string; isFullyLost?: boolean }) => {
    if (isFullyLost) {
      return (
        <span className="px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300">
          Lost
        </span>
      );
    }
    
    const statusLower = status.toLowerCase();
    let color = 'gray';
    let label = status;
    
    if (statusLower === 'completed') {
      color = 'purple';
      label = 'Completed';
    } else if (statusLower.includes('partial')) {
      color = 'orange';
      label = 'Partial';
    } else if (statusLower.includes('allocated')) {
      color = 'green';
      label = 'Allocated';
    } else {
      color = 'yellow';
      label = 'Pending';
    }
    
    return (
      <span className={`px-3 py-1 rounded-full text-xs font-bold bg-${color}-100 text-${color}-800 border border-${color}-300`}>
        {label}
      </span>
    );
  };
  
  // Prepare chart data
  const prepareChartData = () => {
    if (!paymentSummary) return null;
    
    const paymentBreakdown = [
      {
        name: 'Farmer Payments',
        paid: paymentSummary.farmer_payments_paid,
        pending: paymentSummary.farmer_payments_pending,
        total: paymentSummary.farmer_payments_expected,
      },
      {
        name: 'Mukkadam Payments',
        paid: paymentSummary.mukkadam_payments_paid,
        pending: paymentSummary.mukkadam_payments_pending,
        total: paymentSummary.mukkadam_payments_expected,
      },
      {
        name: 'Transport Payments',
        paid: paymentSummary.transport_payments_paid,
        pending: paymentSummary.transport_payments_pending,
        total: paymentSummary.transport_payments_expected,
      },
    ];
    
    const cashFlowData = [
      { name: 'Revenue (Inflow)', value: paymentSummary.total_revenue, color: COLORS.revenue },
      { name: 'Cost (Outflow)', value: paymentSummary.total_cost, color: COLORS.cost },
    ];
    
    const profitData = [
      { name: 'Profit', value: Math.max(0, paymentSummary.total_profit), color: COLORS.profit },
      { name: 'Loss', value: Math.abs(Math.min(0, paymentSummary.total_profit)), color: COLORS.cost },
    ];
    
    return { paymentBreakdown, cashFlowData, profitData };
  };
  
  const chartData = prepareChartData();
  
  const hasActiveFilters = searchQuery || statusFilter !== 'all' || dateFrom || dateTo || 
    farmerNameFilter || mukkadamNameFilter || transporterNameFilter || 
    paymentTypeFilter !== 'all' || paymentStatusFilter !== 'all';
  
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Total Jobs & Payments</h1>
              <p className="text-gray-600 mt-1">
                Showing {jobs.length} job{jobs.length !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="flex gap-3">
              {/* <button
                onClick={() => setShowPaymentDashboard(!showPaymentDashboard)}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition flex items-center gap-2"
              >
                <TrendingUp size={16} />
                {showPaymentDashboard ? 'Hide' : 'Show'} Payment Dashboard
              </button> */}
              <button
                onClick={fetchJobs}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
        </div>
        
        {/* Payment Dashboard */}
        {showPaymentDashboard && paymentSummary && chartData && (
          <div className="mb-6 space-y-6">
            {/* ... Payment Dashboard Code (same as before) ... */}
          </div>
        )}
        
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'all' ? 'border-2 border-blue-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('all')}
          >
            <p className="text-sm text-gray-600">Total Jobs</p>
            <p className="text-2xl font-bold text-blue-600">{stats.total}</p>
          </div>
          
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'pending' ? 'border-2 border-yellow-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('pending')}
          >
            <p className="text-sm text-gray-600">Pending</p>
            <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
          </div>
          
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'partially_allocated' ? 'border-2 border-orange-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('partially_allocated')}
          >
            <p className="text-sm text-gray-600">Partial</p>
            <p className="text-2xl font-bold text-orange-600">{stats.partial}</p>
          </div>
          
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'fully_allocated' ? 'border-2 border-green-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('fully_allocated')}
          >
            <p className="text-sm text-gray-600">Allocated</p>
            <p className="text-2xl font-bold text-green-600">{stats.allocated}</p>
          </div>
          
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'completed' ? 'border-2 border-purple-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('completed')}
          >
            <p className="text-sm text-gray-600">Completed</p>
            <p className="text-2xl font-bold text-purple-600">{stats.completed}</p>
          </div>
          
          {/* ✅ LOST CARD - CORRECTED */}
          <div 
            className={`bg-white p-4 rounded-xl shadow cursor-pointer hover:shadow-lg transition ${statusFilter === 'fully_lost' ? 'border-2 border-red-500' : 'border border-gray-200'}`}
            onClick={() => setStatusFilter('fully_lost')}
          >
            <p className="text-sm text-gray-600">Lost</p>
            <p className="text-2xl font-bold text-red-600">{stats.lost}</p>
          </div>
        </div>
        
        {/* Advanced Filters */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <Filter size={20} />
              Advanced Filters
            </h3>
            {hasActiveFilters && (
              <button
                onClick={clearAllFilters}
                className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition flex items-center gap-2"
              >
                <X size={16} />
                Clear All Filters
              </button>
            )}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Job ID Search */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Job ID / Search
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="text"
                  placeholder="Search Job ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Date From */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date From
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Date To */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date To
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Farmer Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Farmer Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="text"
                  placeholder="Filter by farmer..."
                  value={farmerNameFilter}
                  onChange={(e) => setFarmerNameFilter(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Mukkadam Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mukkadam Name
              </label>
              <div className="relative">
                <UserCheck className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="text"
                  placeholder="Filter by mukkadam..."
                  value={mukkadamNameFilter}
                  onChange={(e) => setMukkadamNameFilter(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Transporter Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Transporter Name
              </label>
              <div className="relative">
                <Truck className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input
                  type="text"
                  placeholder="Filter by transporter..."
                  value={transporterNameFilter}
                  onChange={(e) => setTransporterNameFilter(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            {/* Payment Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Payment Type
              </label>
              <select
                value={paymentTypeFilter}
                onChange={(e) => setPaymentTypeFilter(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Payment Types</option>
                <option value="farmer">Farmer Payments</option>
                <option value="mukkadam">Mukkadam Payments</option>
                <option value="transport">Transport Payments</option>
              </select>
            </div>
            
            {/* Payment Status */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Payment Status
              </label>
              <select
                value={paymentStatusFilter}
                onChange={(e) => setPaymentStatusFilter(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Statuses</option>
                <option value="paid">Paid Only</option>
                <option value="pending">Pending Only</option>
              </select>
            </div>
            
            {/* Search Button */}
            <div className="flex items-end">
              <button
                onClick={fetchJobs}
                className="w-full px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium flex items-center justify-center gap-2"
              >
                <Search size={16} />
                Apply Filters
              </button>
            </div>
          </div>
        </div>
        
        {/* Jobs List */}
        {loading ? (
          <div className="text-center py-12">
            <RefreshCw size={48} className="mx-auto text-gray-400 mb-4 animate-spin" />
            <p className="text-gray-600">Loading jobs...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border">
            <p className="text-gray-600">No jobs found matching your filters</p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map(job => (
              <div
                key={job.work_id}
                className="bg-white rounded-xl border-2 border-gray-200 hover:border-blue-300 transition shadow-sm p-4 cursor-pointer"
                onClick={() => fetchJobDetails(job.work_id)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="text-lg font-mono font-bold text-blue-600">
                        #{job.work_id}
                      </span>
                      <StatusBadge status={job.status} isFullyLost={job.is_fully_lost} />
                    </div>
                    
{job.farmer && (
  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
    {/* Farmer Info */}
    <div className="flex items-center gap-2">
      <User size={14} className="text-blue-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Farmer</p>
        <p className="font-medium text-gray-900 truncate">{job.farmer.farmer_name}</p>
      </div>
    </div>

    {/* Phone */}
    <div className="flex items-center gap-2">
      <Phone size={14} className="text-green-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Phone</p>
        <p className="font-medium text-gray-900 truncate">{job.farmer.phone_number || 'N/A'}</p>
      </div>
    </div>

    {/* Location */}
    <div className="flex items-center gap-2">
      <MapPin size={14} className="text-red-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Location</p>
        <p className="font-medium text-gray-900 truncate">{job.farmer.location || 'N/A'}</p>
      </div>
    </div>

    {/* Mukkadam */}
    <div className="flex items-center gap-2">
      <UserCheck size={14} className="text-purple-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Mukkadam</p>
        <p className="font-medium text-gray-900 truncate">
          {(() => {
            const allMukkadams = Array.from(
              new Set(
                job.activities
                  ?.flatMap(activity => activity.allocations || [])
                  .map(alloc => alloc.mukkadam_name)
                  .filter(Boolean)
              )
            );
            
            if (allMukkadams.length === 0) return 'Not Assigned';
            if (allMukkadams.length === 1) return allMukkadams[0];
            return (
              <span title={allMukkadams.join(', ')}>
                {allMukkadams[0]} <span className="text-gray-500">+{allMukkadams.length - 1}</span>
              </span>
            );
          })()}
        </p>
      </div>
    </div>

    {/* Activity Name */}
    <div className="flex items-center gap-2">
      <Briefcase size={14} className="text-orange-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Activity</p>
        <p className="font-medium text-gray-900 truncate">
          {job.activities?.[0]?.activity_name || 'No Activity'}
        </p>
      </div>
    </div>

    {/* Scheduled Date */}
    <div className="flex items-center gap-2">
      <Calendar size={14} className="text-indigo-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Scheduled</p>
        <p className="font-medium text-gray-900">
          {job.activities?.[0]?.scheduled_date 
            ? new Date(job.activities[0].scheduled_date).toLocaleDateString('en-IN', {
                day: '2-digit',
                month: 'short'
              })
            : 'Not Set'}
        </p>
      </div>
    </div>

    {/* Total Area */}
    <div className="flex items-center gap-2">
      <Maximize2 size={14} className="text-teal-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Total Area</p>
        <p className="font-medium text-gray-900">
          {job.activities?.[0]?.total_area 
            ? `${job.activities[0].total_area} acres`
            : 'N/A'}
        </p>
      </div>
    </div>

    {/* Allocated Area */}
    <div className="flex items-center gap-2">
      <CheckCircle size={14} className="text-green-600 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">Allocated</p>
        <p className="font-medium text-gray-900">
          {job.activities?.[0]?.allocated_area 
            ? `${job.activities[0].allocated_area} acres`
            : '0 acres'}
        </p>
      </div>
    </div>
  </div>
)}


                  </div>
                  
                  <div className="text-right">
                    <p className="text-xs text-gray-500">Activities</p>
                    <p className="text-lg font-bold text-gray-700">{job.total_activities}</p>
                    {job.scheduled_date && (
                      <p className="text-xs text-gray-600 mt-1">
                        {new Date(job.scheduled_date).toLocaleDateString('en-IN')}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Detail Modal - Better Layout */}
{/* Detail Modal - Better Layout */}
{showDetailModal && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div className="bg-white rounded-xl shadow-2xl max-w-7xl w-full max-h-[90vh] overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-6 text-white flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Job: {selectedJobId}</h2>
          {jobDetail?.farmer && (
            <p className="text-sm mt-1 opacity-90">
              {jobDetail.farmer.farmer_name} • {jobDetail.farmer.contact_no || 'No contact'}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowDetailModal(false)}
          className="text-white hover:bg-white hover:bg-opacity-20 rounded-full p-2"
        >
          <X size={24} />
        </button>
      </div>

      <div className="p-6 overflow-y-auto max-h-[calc(90vh-100px)]">
        {loadingDetail ? (
          <div className="text-center py-12">
            <RefreshCw size={48} className="mx-auto text-gray-400 mb-4 animate-spin" />
            <p>Loading details...</p>
          </div>
        ) : jobDetail ? (
          <div className="space-y-6">
            {/* Financial Summary */}
            <div className="bg-gradient-to-r from-green-50 to-blue-50 p-6 rounded-xl border-2 border-green-200">
              <h3 className="font-bold text-lg mb-4 flex items-center">
                <DollarSign className="mr-2 text-green-600" />
                Financial Summary
              </h3>
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-white p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Revenue</p>
                  <p className="text-2xl font-bold text-green-600">
                    ₹{jobDetail.summary.total_revenue.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {jobDetail.summary.total_activities} activities
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Cost</p>
                  <p className="text-2xl font-bold text-red-600">
                    ₹{jobDetail.summary.total_cost.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {jobDetail.summary.total_allocations} allocations
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Profit</p>
                  <p className={`text-2xl font-bold ${jobDetail.summary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {jobDetail.summary.total_profit >= 0 ? '+' : ''}₹{jobDetail.summary.total_profit.toLocaleString()}
                  </p>
                </div>
                <div className="bg-white p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Margin</p>
                  <p className={`text-2xl font-bold ${jobDetail.summary.profit_margin >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {jobDetail.summary.profit_margin.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Activities */}
            <div>
              <h3 className="font-bold text-xl mb-4">Activities ({jobDetail.activities.length})</h3>
              {jobDetail.activities.map((activity: any, idx: number) => (
                <div key={idx} className="border-2 border-gray-200 rounded-xl p-6 mb-4 hover:border-blue-300 transition">
                  {/* Activity Header */}
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex-1">
                      <h4 className="font-bold text-lg text-gray-900">{activity.activity_name}</h4>
                      <p className="text-sm text-gray-600 mt-1">
                        <span className="font-medium">{activity.total_area} acres</span>
                        {activity.rate_per_acre > 0 && (
                          <> • ₹{activity.rate_per_acre.toLocaleString()}/acre</>
                        )}
                        {activity.scheduled_datetime && (
                          <> • {new Date(activity.scheduled_datetime).toLocaleDateString('en-IN')}</>
                        )}
                      </p>
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-sm text-gray-600">Revenue</p>
                      <p className="text-xl font-bold text-green-600">
                        ₹{activity.total_price.toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-600 mt-2">Profit</p>
                      <p className={`text-lg font-bold ${activity.activity_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {activity.activity_profit >= 0 ? '+' : ''}₹{activity.activity_profit.toLocaleString()}
                      </p>
                    </div>
                  </div>

                  {/* ✅ Farmer Payments Section - WITH LINK BUTTON */}
                  {activity.farmer_payments.payment_count > 0 ? (
                    <div className="bg-blue-50 p-4 rounded-lg mb-4">
                      <div className="flex justify-between items-center mb-2">
                        <h5 className="font-semibold text-sm flex items-center">
                          <CheckCircle className="mr-2 text-blue-600" size={16} />
                          Farmer Payments ({activity.farmer_payments.payment_count})
                        </h5>
                        
                        {/* ✅ LINK MORE PAYMENTS BUTTON */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedActivityForLink(activity);
                            setShowLinkPaymentModal(true);
                          }}
                          className="px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-xs font-semibold flex items-center gap-1"
                        >
                          <TrendingUp size={14} />
                          Link More Payments
                        </button>
                      </div>
                      
                      <div className="grid grid-cols-4 gap-4 text-sm mb-3">
                        <div>
                          <p className="text-gray-600">Expected</p>
                          <p className="font-bold">₹{activity.farmer_payments.total_expected.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Paid</p>
                          <p className="font-bold text-green-600">₹{activity.farmer_payments.total_paid.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Pending</p>
                          <p className="font-bold text-orange-600">₹{activity.farmer_payments.total_pending.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Completion</p>
                          <p className="font-bold text-blue-600">{activity.farmer_payments.completion_percentage}%</p>
                        </div>
                      </div>

                      {/* Payment Details */}
                      {activity.farmer_payments.payments.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {activity.farmer_payments.payments.map((payment: any, pidx: number) => (
                            <div key={pidx} className="bg-white p-3 rounded text-xs">
                              <div className="flex justify-between items-center">
                                <div>
                                  <span className={`px-2 py-1 rounded font-semibold ${
                                    payment.payment_status === 'paid' 
                                      ? 'bg-green-100 text-green-700' 
                                      : 'bg-orange-100 text-orange-700'
                                  }`}>
                                    {payment.payment_status}
                                  </span>
                                  <span className="ml-2 text-gray-600">
                                    {payment.payment_route} • {payment.village}
                                  </span>
                                </div>
                                <div className="text-right">
                                  <p className="font-bold">₹{payment.booking_value.toLocaleString()}</p>
                                  <p className="text-gray-500">{payment.date_of_payment || 'Not paid'}</p>
                                </div>
                              </div>
                              {payment.description && (
                                <p className="text-gray-600 mt-1">{payment.description}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* ✅ NO PAYMENTS - SHOW PROMINENT LINK BUTTON */
                    <div className="bg-yellow-50 border-2 border-yellow-200 rounded-lg p-4 mb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <AlertCircle className="text-yellow-600" size={24} />
                          <div>
                            <p className="font-semibold text-gray-900">No farmer payments linked</p>
                            <p className="text-sm text-gray-600">Link existing payments to track revenue</p>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedActivityForLink(activity);
                            setShowLinkPaymentModal(true);
                          }}
                          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-semibold flex items-center gap-2"
                        >
                          <TrendingUp size={16} />
                          Link Payments
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Allocations */}
                  {/* Allocations */}
{activity.allocations.length > 0 && (
  <div>
    <h5 className="font-semibold mb-3 flex items-center">
      <Users className="mr-2 text-purple-600" size={16} />
      Allocations ({activity.allocations.length})
    </h5>
    <div className="space-y-3">
      {activity.allocations.map((alloc: any, aidx: number) => (
        <div key={aidx} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <div className="grid grid-cols-3 gap-4 mb-3">
            {/* Mukkadam */}
            <div>
              <p className="text-xs text-gray-600 uppercase font-semibold mb-1">Mukkadam</p>
              <p className="font-semibold text-gray-900">{alloc.mukkadam_name}</p>
              {alloc.mukkadam_contact && (
                <p className="text-xs text-gray-600">{alloc.mukkadam_contact}</p>
              )}
              <div className="mt-2">
                <p className="text-xs text-gray-600">Cost</p>
                <p className="font-bold text-blue-600">₹{alloc.mukkadam_price.toLocaleString()}</p>
              </div>
            </div>

            {/* Transporter */}
            <div>
              <p className="text-xs text-gray-600 uppercase font-semibold mb-1">Transport</p>
              <p className="font-semibold text-gray-900">{alloc.transporter_name || 'Own Transport'}</p>
              {alloc.transporter_contact && (
                <p className="text-xs text-gray-600">{alloc.transporter_contact}</p>
              )}
              <div className="mt-2">
                <p className="text-xs text-gray-600">Cost</p>
                <p className="font-bold text-orange-600">₹{alloc.transport_price.toLocaleString()}</p>
              </div>
            </div>

            {/* Details */}
            <div>
              <p className="text-xs text-gray-600 uppercase font-semibold mb-1">Details</p>
              <div className="space-y-1 text-sm">
                <p><span className="text-gray-600">Area:</span> <span className="font-semibold">{alloc.allocated_area} acres</span></p>
                <p><span className="text-gray-600">Crew:</span> <span className="font-semibold">{alloc.crew_size} workers</span></p>
                <p><span className="text-gray-600">Date:</span> <span className="font-semibold">{alloc.work_date}</span></p>
                <p>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    alloc.status === 'completed' 
                      ? 'bg-green-100 text-green-700' 
                      : alloc.status === 'in_progress'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {alloc.status}
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* Total Cost & View Details Button */}
          <div className="pt-3 border-t border-gray-300">
            <div className="flex justify-between items-center">
              <div>
                <span className="text-sm font-semibold text-gray-700">Total Allocation Cost</span>
                <span className="text-lg font-bold text-red-600 ml-3">₹{alloc.total_cost.toLocaleString()}</span>
              </div>
              
              {/* ✅ VIEW DETAILS BUTTON */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/allocations/${alloc.allocation_id}`);
                }}
                className="text-blue-600 hover:text-blue-900 font-bold flex items-center text-xs hover:bg-blue-50 px-3 py-2 rounded-lg transition"
              >
                <Eye size={14} className="mr-1" /> 
                View Details
              </button>
            </div>
          </div>

          {/* Notes */}
          {alloc.notes && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-xs text-gray-600 font-semibold mb-1">Notes</p>
              <p className="text-sm text-gray-700">{alloc.notes}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
)}

                  {/* No Allocations Message */}
                  {activity.allocations.length === 0 && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                      <p className="text-sm text-yellow-800">No allocations for this activity yet</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  </div>
)}

{/* ✅ LINK PAYMENT MODAL - FALLBACK SOLUTION */}
{showLinkPaymentModal && selectedActivityForLink && jobDetail && (
  <LinkFarmerPaymentModal
    isOpen={showLinkPaymentModal}
    onClose={() => {
      setShowLinkPaymentModal(false);
      setSelectedActivityForLink(null);
    }}
    jobActivityId={
      selectedActivityForLink.id || 
      selectedActivityForLink.activity_id || 
      0  // ✅ Fallback to 0 if both are missing
    }
    jobId={jobDetail.work_id}
    activityName={selectedActivityForLink.activity_name}
    onPaymentLinked={() => {
      fetchJobDetails(jobDetail.work_id);
    }}
  />
)}

      </div>
    </div>
  );
};

export default TotalJobsView;