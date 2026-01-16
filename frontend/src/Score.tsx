// src/pages/MukkadamScorecard.tsx
import React, { useState, useEffect } from 'react';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  Filter, 
  Download, 
  Eye,
  TrendingUp,
  Users,
  Briefcase,
  DollarSign,
  MapPin,
  Loader2
} from 'lucide-react';

// const API_BASE_URL = 'http://localhost:8001'; // ← Change to your Django backend URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_ALLOCATION;
interface MukkadamScorecard {
  id: number;
  potential_man_days: number;
  actual_man_days_worked: number;
  available_calendar_days: number;
  utilization_rate: number;
  avg_earning_per_worker_day: number;



  mukkadam_name: string;
  mobile_numbers: string;
  location_display: string;
  crew_size: string;
  created_by_name: string;
  created_at: string;
  is_active: boolean;
  first_allocation_date: string | null;
  days_to_first_job: number | null;
  total_allocations: number;
  total_unique_jobs: number;
  total_area_allocated: number;
  total_workers_supplied: number;
  total_earnings: number;
  total_paid: number;
  total_pending: number;
  allocations_by_status: {
    allocated: number;
    in_progress: number;
    completed: number;
    cancelled: number;
  };
  job_summary: Array<{
    allocation_id: number;
    job_id: string;
    activity_name: string;
    work_date: string;
    location: string;
    farmer_name: string;
    area: number;
    earnings: number;
    status: string;
    allocated_by: string;
  }>;
}

interface ScorecardSummary {
avg_utilization: number;         // NEW
  avg_worker_earning: number;      // NEW
  avg_days_to_first_job: number;
  total_mukkadams: number;
  active_mukkadams: number;
  inactive_mukkadams: number;
  total_allocations: number;
  total_unique_jobs: number;
  total_area_allocated: number;
  total_workers_supplied: number;
  total_earnings: number;
  total_paid: number;
  total_pending: number;
}

export default function MukkadamScorecard() {
  const [mukkadams, setMukkadams] = useState<MukkadamScorecard[]>([]);
  const [summary, setSummary] = useState<ScorecardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const [minUtilization, setMinUtilization] = useState(''); // NEW Filter
  const [geoCoverage, setGeoCoverage] = useState({ districts: 0, talukas: 0, villages: 0 });
  // Filters
  const [search, setSearch] = useState('');
  const [districtFilter, setDistrictFilter] = useState('');
  const [talukaFilter, setTalukaFilter] = useState('');
  const [hasJobsFilter, setHasJobsFilter] = useState('');
  const [isActiveFilter, setIsActiveFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [locationFilter, setLocationFilter] = useState('');


const fetchScorecard = async () => {
  setLoading(true);
  
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (hasJobsFilter && hasJobsFilter !== 'all') params.append('has_jobs', hasJobsFilter);
  if (isActiveFilter && isActiveFilter !== 'all') params.append('is_active', isActiveFilter);
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);

  try {
    const response = await fetch(`${API_BASE_URL}/ap/mukkadam-scorecard-summary/?${params.toString()}`);
    const data = await response.json();
    let mList = data.mukkadams || [];

    // --- 1. SINGLE LOCATION SEARCH (Village, Taluka, District) ---
    if (locationFilter) {
      const term = locationFilter.toLowerCase();
      mList = mList.filter((m: MukkadamScorecard) => 
        m.location_display?.toLowerCase().includes(term)
      );
    }

    // --- 2. MIN UTILIZATION FILTER ---
    if (minUtilization) {
      const minVal = parseFloat(minUtilization);
      if (!isNaN(minVal)) {
        mList = mList.filter((m: MukkadamScorecard) => m.utilization_rate >= minVal);
      }
    }

    // --- 3. CALCULATE GEOGRAPHIC COVERAGE ---
    const districts = new Set();
    const talukas = new Set();
    const villages = new Set();

    mList.forEach((m: MukkadamScorecard) => {
      const parts = m.location_display?.split(',').map(p => p.trim()) || [];
      if (parts[0]) villages.add(parts[0]); 
      if (parts[1]) talukas.add(parts[1]);  
      if (parts[2]) districts.add(parts[2]); 
    });

    setGeoCoverage({
      districts: districts.size,
      talukas: talukas.size,
      villages: villages.size
    });

    // --- 4. CALCULATE TOTALS FROM FILTERED LIST ---
    // This part ensures your 5 cards (Area, Jobs, Earnings, etc.) actually update!
    const calculatedSummary = mList.reduce((acc, curr) => {
      return {
        total_mukkadams: acc.total_mukkadams + 1,
        active_mukkadams: acc.active_mukkadams + (curr.is_active ? 1 : 0),
        total_unique_jobs: acc.total_unique_jobs + (curr.total_unique_jobs || 0),
        total_allocations: acc.total_allocations + (curr.total_allocations || 0),
        total_area_allocated: acc.total_area_allocated + (curr.total_area_allocated || 0),
        total_earnings: acc.total_earnings + (curr.total_earnings || 0),
        total_paid: acc.total_paid + (curr.total_paid || 0),
        total_pending: acc.total_pending + (curr.total_pending || 0),
        // For averages, we sum rates now and divide later
        sum_utilization: acc.sum_utilization + (curr.utilization_rate || 0),
        sum_worker_earning: acc.sum_worker_earning + (curr.avg_earning_per_worker_day || 0),
        sum_days_to_job: acc.sum_days_to_job + (curr.days_to_first_job || 0),
        count_days_to_job: acc.count_days_to_job + (curr.days_to_first_job !== null ? 1 : 0)
      };
    }, {
      total_mukkadams: 0, active_mukkadams: 0, total_unique_jobs: 0, total_allocations: 0,
      total_area_allocated: 0, total_earnings: 0, total_paid: 0, total_pending: 0,
      sum_utilization: 0, sum_worker_earning: 0, sum_days_to_job: 0, count_days_to_job: 0
    });

    // Final Average Calculations
    const finalSummary = {
      ...calculatedSummary,
      avg_utilization: mList.length ? (calculatedSummary.sum_utilization / mList.length) : 0,
      avg_worker_earning: mList.length ? (calculatedSummary.sum_worker_earning / mList.length) : 0,
      avg_days_to_first_job: calculatedSummary.count_days_to_job ? (calculatedSummary.sum_days_to_job / calculatedSummary.count_days_to_job) : 0
    };

    setMukkadams(mList);
    setSummary(finalSummary);
  } catch (error) {
    console.error('Error fetching/filtering scorecard:', error);
  } finally {
    setLoading(false);
  }
};
// Only trigger if you want real-time filtering as they type
useEffect(() => {
  const delayDebounceFn = setTimeout(() => {
    fetchScorecard();
  }, 500); // Wait 500ms after last keystroke

  return () => clearTimeout(delayDebounceFn);
}, [minUtilization]);
  
  const handleApplyFilters = () => {
    fetchScorecard();
  };
  
const handleResetFilters = () => {
  setSearch('');
  setDistrictFilter('');
  setTalukaFilter('');
  setHasJobsFilter('all');
  setIsActiveFilter('all');
  setDateFrom('');
  setDateTo('');
  setMinUtilization(''); // Added this line
  
  // Use a functional update or a slight timeout to ensure state is cleared before fetching
  setTimeout(() => fetchScorecard(), 10);
};
  
  const getStatusBadge = (isActive: boolean) => {
    return isActive ? (
      <Badge className="bg-green-500 hover:bg-green-600">Active</Badge>
    ) : (
      <Badge variant="secondary">Inactive</Badge>
    );
  };
  
  const handleViewDetails = (mukkadamId: number) => {
    // Navigate to details page
    window.location.href = `/mukkadam-details/${mukkadamId}`;
  };
  
  return (
    <div className="container mx-auto p-6 space-y-6 max-w-[1600px]">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Mukkadam Scorecard</h1>
          <p className="text-gray-600 mt-1">Track mukkadam performance and activity</p>
        </div>
        <Button variant="outline" disabled>
          <Download className="w-4 h-4 mr-2" />
          Export to Excel
        </Button>
      </div>
      
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card className="hover:shadow-lg transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Mukkadams</p>
                  <p className="text-2xl font-bold text-gray-900">{summary.total_mukkadams}</p>
                </div>
                <Users className="w-8 h-8 text-blue-500" />
              </div>
              <p className="text-xs text-green-600 mt-2 font-medium">
                {summary.active_mukkadams} active
              </p>
            </CardContent>
          </Card>
          
          <Card className="hover:shadow-lg transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Jobs</p>
                  <p className="text-2xl font-bold text-gray-900">{summary.total_unique_jobs}</p>
                </div>
                <Briefcase className="w-8 h-8 text-purple-500" />
              </div>
              <p className="text-xs text-gray-600 mt-2">
                {summary.total_allocations} allocations
              </p>
            </CardContent>
          </Card>
          
          <Card className="hover:shadow-lg transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Area</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {summary.total_area_allocated.toFixed(2)}
                  </p>
                </div>
                <MapPin className="w-8 h-8 text-green-500" />
              </div>
              <p className="text-xs text-gray-600 mt-2">acres allocated</p>
            </CardContent>
          </Card>

          <Card className="bg-blue-50 border-blue-100">
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-blue-600">Avg Utilization</p>
              <p className="text-2xl font-bold text-blue-900">{summary.avg_utilization.toFixed(1)}%</p>
              <p className="text-xs text-blue-500 mt-1">Capacity usage</p>
            </CardContent>
          </Card>

          <Card className="bg-green-50 border-green-100">
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-green-600">Avg Worker Wage</p>
              <p className="text-2xl font-bold text-green-900">₹{Math.round(summary.avg_worker_earning)}</p>
              <p className="text-xs text-green-500 mt-1">Per worker / day</p>
            </CardContent>
          </Card>

          <Card className="bg-purple-50 border-purple-100">
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-purple-600">Activation Time</p>
              <p className="text-2xl font-bold text-purple-900">{Math.round(summary.avg_days_to_first_job)} Days</p>
              <p className="text-xs text-purple-500 mt-1">Reg to first job</p>
            </CardContent>
          </Card>

          <Card className="bg-orange-50 border-orange-100 shadow-sm">
  <CardContent className="pt-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs font-semibold text-orange-600 uppercase tracking-wider">Geo Coverage</p>
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-orange-900">{geoCoverage.villages}</span>
          <span className="text-sm text-orange-700">Villages</span>
        </div>
      </div>
      <div className="p-3 bg-orange-100 rounded-full">
        <MapPin className="w-6 h-6 text-orange-600" />
      </div>
    </div>
    <div className="mt-4 pt-4 border-t border-orange-200/50 flex justify-between text-xs font-medium text-orange-800">
      <span>{geoCoverage.districts} Districts</span>
      <span className="text-orange-300">|</span>
      <span>{geoCoverage.talukas} Talukas</span>
    </div>
  </CardContent>
</Card>
          
          <Card className="hover:shadow-lg transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Earnings</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ₹{summary.total_earnings.toLocaleString('en-IN')}
                  </p>
                </div>
                <DollarSign className="w-8 h-8 text-yellow-500" />
              </div>
              <p className="text-xs text-green-600 mt-2 font-medium">
                ₹{summary.total_paid.toLocaleString('en-IN')} paid
              </p>
            </CardContent>
          </Card>
          
          <Card className="hover:shadow-lg transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Pending</p>
                  <p className="text-2xl font-bold text-orange-600">
                    ₹{summary.total_pending.toLocaleString('en-IN')}
                  </p>
                </div>
                <TrendingUp className="w-8 h-8 text-orange-500" />
              </div>
              <p className="text-xs text-gray-600 mt-2">awaiting payment</p>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center text-lg">
            <Filter className="w-5 h-5 mr-2" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <div>
              <label className="text-sm font-medium mb-1 block text-gray-700">Search</label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Name or mobile"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
            
           {/* Replace District and Taluka inputs with this one */}
<div className="md:col-span-2 lg:col-span-2">
  <label className="text-sm font-medium mb-1 block text-gray-700">Location</label>
  <div className="relative">
    <MapPin className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
    <Input
      placeholder="Search Village, Taluka or District..."
      value={locationFilter}
      onChange={(e) => setLocationFilter(e.target.value)}
      className="pl-8"
    />
  </div>
</div>
            
            {/* Change this section */}
<div>
  <label className="text-sm font-medium mb-1 block text-gray-700">Has Jobs</label>
  <Select value={hasJobsFilter} onValueChange={setHasJobsFilter}>
    <SelectTrigger>
      <SelectValue placeholder="All" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All</SelectItem> {/* Changed from "" to "all" */}
      <SelectItem value="true">Yes</SelectItem>
      <SelectItem value="false">No</SelectItem>
    </SelectContent>
  </Select>
</div>
            
            {/* Change this section */}
<div>
  <label className="text-sm font-medium mb-1 block text-gray-700">Active Status</label>
  <Select value={isActiveFilter} onValueChange={setIsActiveFilter}>
    <SelectTrigger>
      <SelectValue placeholder="All" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All</SelectItem> {/* Changed from "" to "all" */}
      <SelectItem value="true">Active</SelectItem>
      <SelectItem value="false">Inactive</SelectItem>
    </SelectContent>
  </Select>
</div>
            
            <div>
              <label className="text-sm font-medium mb-1 block text-gray-700">Date From</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1 block">Min Utilization %</label>
              <Input 
                type="number" 
                placeholder="e.g. 50" 
                value={minUtilization} 
                onChange={(e) => setMinUtilization(e.target.value)} 
              />
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block text-gray-700">Date To</label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
            
            <div className="flex items-end gap-2">
              <Button onClick={handleApplyFilters} className="flex-1">
                Apply
              </Button>
              <Button onClick={handleResetFilters} variant="outline">
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      
      
      {/* Mukkadam Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Mukkadam List ({mukkadams.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
              <span className="ml-2 text-gray-600">Loading scorecard...</span>
            </div>
          ) : mukkadams.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No mukkadams found matching your filters
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[200px]">Name</TableHead>
                    <TableHead>Mobile</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Jobs</TableHead>
                    <TableHead className="text-right">first Job in </TableHead>
                    <TableHead className="text-right">Area</TableHead>
                    <TableHead className="text-right">Workers</TableHead>
                    <TableHead className="text-right">Utilization</TableHead>
<TableHead className="text-right">Avg. Worker/Day</TableHead>
                    <TableHead className="text-right">Earnings</TableHead>
                    <TableHead className="text-right">Paid</TableHead>
                    <TableHead className="text-right">Pending</TableHead>
                    <TableHead className="text-center">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mukkadams.map((mukkadam) => (
                    <TableRow key={mukkadam.id} className="hover:bg-gray-50">
                      <TableCell className="font-medium">
                        <div>
                          <div className="font-semibold text-gray-900">
                            {mukkadam.mukkadam_name}
                          </div>
                          <div className="text-xs text-gray-500">
                            Crew: {mukkadam.crew_size}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-gray-700">
                        {mukkadam.mobile_numbers}
                      </TableCell>
                      <TableCell className="text-gray-700">
                        {mukkadam.location_display}
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(mukkadam.is_active)}
                      </TableCell>

                      
                      <TableCell className="text-right">
                        <div>
                          <div className="font-semibold text-gray-900">
                            {mukkadam.total_unique_jobs}
                          </div>
                          <div className="text-xs text-gray-500">
                            {mukkadam.total_allocations} alloc
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-gray-700">
                        {mukkadam.days_to_first_job !== null ? `${mukkadam.days_to_first_job} Days` : 'N/A'}
                      </TableCell>
                      <TableCell className="text-right font-medium text-gray-900">
                        {mukkadam.total_area_allocated.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right text-gray-700">
                        {mukkadam.total_workers_supplied}
                      </TableCell>

                      {/* Utilization Cell */}
<TableCell className="text-right">
  <div className="flex flex-col items-end">
    <span className="font-bold text-gray-900">{mukkadam.utilization_rate}%</span>
    <span className="text-[10px] text-gray-500 uppercase">
      {mukkadam.actual_man_days_worked} / {mukkadam.potential_man_days} MD
    </span>
  </div>
</TableCell>

{/* Avg Earning Cell */}
<TableCell className="text-right">
  <div className="flex flex-col items-end">
    <span className="font-bold text-blue-600">
      ₹{mukkadam.avg_earning_per_worker_day.toLocaleString('en-IN')}
    </span>
    <span className="text-[10px] text-gray-400">per man-day</span>
  </div>
</TableCell>
                      <TableCell className="text-right font-semibold text-gray-900">
                        ₹{mukkadam.total_earnings.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right font-medium text-green-600">
                        ₹{mukkadam.total_paid.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-right font-medium text-orange-600">
                        ₹{mukkadam.total_pending.toLocaleString('en-IN')}
                      </TableCell>
                      <TableCell className="text-center">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewDetails(mukkadam.id)}
                          className="hover:bg-blue-50 hover:text-blue-600 hover:border-blue-600"
                        >
                          <Eye className="w-4 h-4 mr-1" />
                          Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}