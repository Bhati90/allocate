import React, { useEffect, useState, useMemo } from 'react';
import { MonthTenderCalendar } from './MonthCalender';
import { Calendar, Filter, X, ChevronDown, Search, TrendingUp, DollarSign, Users, Briefcase } from 'lucide-react';
import dayjs from 'dayjs';

type JobsApiJob = any;

type FilterState = {
  bookingType: 'ALL' | 'TENDER' | 'ON_DEMAND';
  status: string;
  farmerName: string;
  mukkadamName: string;
  dateFrom: string;
  dateTo: string;
  amountMin: string;
  amountMax: string;
};

export const JobsCalendarPage: React.FC = () => {
  const [jobs, setJobs] = useState<JobsApiJob[]>([]);
  const [allJobs, setAllJobs] = useState<JobsApiJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  
  const [filters, setFilters] = useState<FilterState>({
    bookingType: 'ALL',
    status: '',
    farmerName: '',
    mukkadamName: '',
    dateFrom: '',
    dateTo: '',
    amountMin: '',
    amountMax: '',
  });

  // Fetch all jobs once
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        setLoading(true);
        setError(null);

        const res = await fetch(`http://localhost:8001/ap/jobs/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setAllJobs(data);
        setJobs(data);
      } catch (e: any) {
        setError(e.message || 'Failed to load jobs');
      } finally {
        setLoading(false);
      }
    };

    fetchJobs();
  }, []);

  // Apply filters client-side
  const filteredJobs = useMemo(() => {
    let filtered = [...allJobs];

    // Booking type filter
    if (filters.bookingType !== 'ALL') {
      filtered = filtered.filter(
        (job) => job.booking_type?.toUpperCase() === filters.bookingType
      );
    }

    // Status filter
    if (filters.status) {
      filtered = filtered.filter(
        (job) => job.status?.toLowerCase() === filters.status.toLowerCase()
      );
    }

    // Farmer name filter
    if (filters.farmerName.trim()) {
      const searchTerm = filters.farmerName.toLowerCase();
      filtered = filtered.filter(
        (job) =>
          job.farmer?.farmer_name?.toLowerCase().includes(searchTerm) ||
          job.farmer_id?.toLowerCase().includes(searchTerm)
      );
    }

    // Mukkadam name filter
    if (filters.mukkadamName.trim()) {
      const searchTerm = filters.mukkadamName.toLowerCase();
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          activity.allocations?.some((alloc: any) =>
            alloc.mukkadam_name?.toLowerCase().includes(searchTerm)
          )
        )
      );
    }

    // Date range filter
    if (filters.dateFrom) {
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          dayjs(activity.scheduled_date).isSameOrAfter(dayjs(filters.dateFrom), 'day')
        )
      );
    }

    if (filters.dateTo) {
      filtered = filtered.filter((job) =>
        job.activities?.some((activity: any) =>
          dayjs(activity.scheduled_date).isSameOrBefore(dayjs(filters.dateTo), 'day')
        )
      );
    }

    // Amount range filter
    if (filters.amountMin) {
      const minAmount = parseFloat(filters.amountMin);
      filtered = filtered.filter(
        (job) => (job.total_activities_amount || 0) >= minAmount
      );
    }

    if (filters.amountMax) {
      const maxAmount = parseFloat(filters.amountMax);
      filtered = filtered.filter(
        (job) => (job.total_activities_amount || 0) <= maxAmount
      );
    }

    return filtered;
  }, [allJobs, filters]);

  // Calculate statistics
  const stats = useMemo(() => {
    const totalJobs = filteredJobs.length;
    const tenderCount = filteredJobs.filter(
      (j) => j.booking_type === 'TENDER'
    ).length;
    const onDemandCount = filteredJobs.filter(
      (j) => j.booking_type === 'ON_DEMAND'
    ).length;

    const totalRevenue = filteredJobs.reduce(
      (sum, job) => sum + (job.total_activities_amount || 0),
      0
    );

    const totalMukkadamCost = filteredJobs.reduce((sum, job) => {
      return (
        sum +
        (job.activities || []).reduce((actSum: number, act: any) => {
          return (
            actSum +
            (act.allocations || []).reduce(
              (allocSum: number, alloc: any) => allocSum + (alloc.total_cost || 0),
              0
            )
          );
        }, 0)
      );
    }, 0);

    const totalAllocations = filteredJobs.reduce(
      (sum, job) =>
        sum +
        (job.activities || []).reduce(
          (actSum: number, act: any) => actSum + (act.allocations?.length || 0),
          0
        ),
      0
    );

    const statusCounts = {
      pending: filteredJobs.filter((j) => j.status === 'pending').length,
      partially_allocated: filteredJobs.filter(
        (j) => j.status === 'partially_allocated'
      ).length,
      fully_allocated: filteredJobs.filter((j) => j.status === 'fully_allocated')
        .length,
      in_progress: filteredJobs.filter((j) => j.status === 'in_progress').length,
      completed: filteredJobs.filter((j) => j.status === 'completed').length,
    };

    return {
      totalJobs,
      tenderCount,
      onDemandCount,
      totalRevenue,
      totalMukkadamCost,
      profit: totalRevenue - totalMukkadamCost,
      profitPercentage:
        totalRevenue > 0
          ? ((totalRevenue - totalMukkadamCost) / totalRevenue) * 100
          : 0,
      totalAllocations,
      statusCounts,
      tenderPercentage: totalJobs > 0 ? (tenderCount / totalJobs) * 100 : 0,
      onDemandPercentage: totalJobs > 0 ? (onDemandCount / totalJobs) * 100 : 0,
    };
  }, [filteredJobs]);

  const handleFilterChange = (key: keyof FilterState, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      bookingType: 'ALL',
      status: '',
      farmerName: '',
      mukkadamName: '',
      dateFrom: '',
      dateTo: '',
      amountMin: '',
      amountMax: '',
    });
  };

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.bookingType !== 'ALL') count++;
    if (filters.status) count++;
    if (filters.farmerName) count++;
    if (filters.mukkadamName) count++;
    if (filters.dateFrom) count++;
    if (filters.dateTo) count++;
    if (filters.amountMin) count++;
    if (filters.amountMax) count++;
    return count;
  }, [filters]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent mb-4"></div>
          <p className="text-lg text-gray-700 font-medium">Loading calendar data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-2xl p-10 max-w-md">
          <div className="text-red-600 text-center">
            <svg
              className="w-16 h-16 mx-auto mb-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-2xl font-bold mb-3">Error Loading Jobs</h3>
            <p className="text-gray-600">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-100">
      <div className="max-w-[1600px] mx-auto p-8 space-y-8">
       
        {/* <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
          <div className="flex items-start justify-between mb-8">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Calendar className="w-10 h-10 text-blue-600" />
                <h1 className="text-4xl font-bold text-gray-900">
                  Work Calendar
                </h1>
              </div>
              <p className="text-gray-600 text-lg">
                Manage job allocations, track progress, and monitor revenue
              </p>
            </div>

            
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-all shadow-lg hover:shadow-xl"
            >
              <Filter className="w-5 h-5" />
              Filters
              {activeFilterCount > 0 && (
                <span className="bg-white text-blue-600 rounded-full px-2.5 py-0.5 text-sm font-bold">
                  {activeFilterCount}
                </span>
              )}
              <ChevronDown
                className={`w-5 h-5 transition-transform ${
                  showFilters ? 'rotate-180' : ''
                }`}
              />
            </button>
          </div>

          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white shadow-lg">
              <div className="flex items-center justify-between mb-3">
                <Briefcase className="w-8 h-8 opacity-80" />
                <span className="text-3xl font-bold">{stats.totalJobs}</span>
              </div>
              <h3 className="text-sm font-medium opacity-90 mb-2">Total Jobs</h3>
              <div className="flex gap-4 text-xs">
                <div>
                  <span className="opacity-80">Tender: </span>
                  <span className="font-semibold">
                    {stats.tenderCount} ({stats.tenderPercentage.toFixed(1)}%)
                  </span>
                </div>
                <div>
                  <span className="opacity-80">On-demand: </span>
                  <span className="font-semibold">
                    {stats.onDemandCount} ({stats.onDemandPercentage.toFixed(1)}%)
                  </span>
                </div>
              </div>
            </div>

          
            <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-xl p-6 text-white shadow-lg">
              <div className="flex items-center justify-between mb-3">
                <DollarSign className="w-8 h-8 opacity-80" />
                <span className="text-3xl font-bold">
                  ₹{(stats.totalRevenue / 1000).toFixed(0)}K
                </span>
              </div>
              <h3 className="text-sm font-medium opacity-90 mb-2">
                Total Revenue
              </h3>
              <div className="text-xs opacity-90">
                Farmer payments expected
              </div>
            </div>

         
            <div className="bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl p-6 text-white shadow-lg">
              <div className="flex items-center justify-between mb-3">
                <TrendingUp className="w-8 h-8 opacity-80" />
                <span className="text-3xl font-bold">
                  ₹{(stats.totalMukkadamCost / 1000).toFixed(0)}K
                </span>
              </div>
              <h3 className="text-sm font-medium opacity-90 mb-2">
                Mukkadam Costs
              </h3>
              <div className="text-xs opacity-90">Total allocation costs</div>
            </div>

          
            <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white shadow-lg">
              <div className="flex items-center justify-between mb-3">
                <Users className="w-8 h-8 opacity-80" />
                <span className="text-3xl font-bold">
                  {stats.profitPercentage.toFixed(1)}%
                </span>
              </div>
              <h3 className="text-sm font-medium opacity-90 mb-2">
                Profit Margin
              </h3>
              <div className="text-xs opacity-90">
                ₹{(stats.profit / 1000).toFixed(0)}K profit
              </div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              Job Status Distribution
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-600">
                  {stats.statusCounts.pending}
                </div>
                <div className="text-xs text-gray-500 mt-1">Pending</div>
                <div className="text-xs text-gray-400">
                  (
                  {stats.totalJobs > 0
                    ? ((stats.statusCounts.pending / stats.totalJobs) * 100).toFixed(
                        1
                      )
                    : 0}
                  %)
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">
                  {stats.statusCounts.partially_allocated}
                </div>
                <div className="text-xs text-gray-500 mt-1">Partially Allocated</div>
                <div className="text-xs text-gray-400">
                  (
                  {stats.totalJobs > 0
                    ? (
                        (stats.statusCounts.partially_allocated / stats.totalJobs) *
                        100
                      ).toFixed(1)
                    : 0}
                  %)
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {stats.statusCounts.fully_allocated}
                </div>
                <div className="text-xs text-gray-500 mt-1">Fully Allocated</div>
                <div className="text-xs text-gray-400">
                  (
                  {stats.totalJobs > 0
                    ? (
                        (stats.statusCounts.fully_allocated / stats.totalJobs) *
                        100
                      ).toFixed(1)
                    : 0}
                  %)
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {stats.statusCounts.in_progress}
                </div>
                <div className="text-xs text-gray-500 mt-1">In Progress</div>
                <div className="text-xs text-gray-400">
                  (
                  {stats.totalJobs > 0
                    ? (
                        (stats.statusCounts.in_progress / stats.totalJobs) *
                        100
                      ).toFixed(1)
                    : 0}
                  %)
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-600">
                  {stats.statusCounts.completed}
                </div>
                <div className="text-xs text-gray-500 mt-1">Completed</div>
                <div className="text-xs text-gray-400">
                  (
                  {stats.totalJobs > 0
                    ? (
                        (stats.statusCounts.completed / stats.totalJobs) *
                        100
                      ).toFixed(1)
                    : 0}
                  %)
                </div>
              </div>
            </div>
          </div>

          {showFilters && (
            <div className="mt-8 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-8 border-2 border-blue-200">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-gray-900">
                  Advanced Filters
                </h3>
                {activeFilterCount > 0 && (
                  <button
                    onClick={clearFilters}
                    className="flex items-center gap-2 px-4 py-2 bg-white text-gray-700 rounded-lg hover:bg-gray-100 transition-all border border-gray-300 font-medium"
                  >
                    <X className="w-4 h-4" />
                    Clear All
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Booking Type
                  </label>
                  <select
                    value={filters.bookingType}
                    onChange={(e) =>
                      handleFilterChange(
                        'bookingType',
                        e.target.value as 'ALL' | 'TENDER' | 'ON_DEMAND'
                      )
                    }
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  >
                    <option value="ALL">All Types</option>
                    <option value="TENDER">Tender Only</option>
                    <option value="ON_DEMAND">On-Demand Only</option>
                  </select>
                </div>

   
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Job Status
                  </label>
                  <select
                    value={filters.status}
                    onChange={(e) => handleFilterChange('status', e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  >
                    <option value="">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="partially_allocated">Partially Allocated</option>
                    <option value="fully_allocated">Fully Allocated</option>
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>


                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Farmer Name
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={filters.farmerName}
                      onChange={(e) =>
                        handleFilterChange('farmerName', e.target.value)
                      }
                      placeholder="Search farmer..."
                      className="w-full pl-10 pr-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Mukkadam Name
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={filters.mukkadamName}
                      onChange={(e) =>
                        handleFilterChange('mukkadamName', e.target.value)
                      }
                      placeholder="Search mukkadam..."
                      className="w-full pl-10 pr-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Date From
                  </label>
                  <input
                    type="date"
                    value={filters.dateFrom}
                    onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  />
                </div>


                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Date To
                  </label>
                  <input
                    type="date"
                    value={filters.dateTo}
                    onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  />
                </div>


                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Min Amount (₹)
                  </label>
                  <input
                    type="number"
                    value={filters.amountMin}
                    onChange={(e) => handleFilterChange('amountMin', e.target.value)}
                    placeholder="0"
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  />
                </div>


                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Max Amount (₹)
                  </label>
                  <input
                    type="number"
                    value={filters.amountMax}
                    onChange={(e) => handleFilterChange('amountMax', e.target.value)}
                    placeholder="999999"
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white font-medium"
                  />
                </div>
              </div>

              {activeFilterCount > 0 && (
                <div className="mt-6 p-4 bg-white rounded-lg border border-blue-200">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="font-semibold">Active filters:</span>
                    {filters.bookingType !== 'ALL' && (
                      <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full font-medium">
                        {filters.bookingType}
                      </span>
                    )}
                    {filters.status && (
                      <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full font-medium">
                        {filters.status}
                      </span>
                    )}
                    {filters.farmerName && (
                      <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full font-medium">
                        Farmer: {filters.farmerName}
                      </span>
                    )}
                    {filters.mukkadamName && (
                      <span className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full font-medium">
                        Mukkadam: {filters.mukkadamName}
                      </span>
                    )}
                    {(filters.dateFrom || filters.dateTo) && (
                      <span className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full font-medium">
                        Date Range
                      </span>
                    )}
                    {(filters.amountMin || filters.amountMax) && (
                      <span className="px-3 py-1 bg-rose-100 text-rose-800 rounded-full font-medium">
                        Amount Range
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div> */}

        {/* Calendar Component */}
        <MonthTenderCalendar jobs={filteredJobs} />
      </div>
    </div>
  );
};