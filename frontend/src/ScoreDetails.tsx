// src/pages/MukkadamDetails.tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  User,
  Phone,
  MapPin,
  Users,
  Calendar,
  Briefcase,
  DollarSign,
  TrendingUp,
  Activity,
  Building2,
  Loader2,
  Clock
} from 'lucide-react';

// const API_BASE_URL = 'http://localhost:8001';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL_ALLOCATION;

interface MukkadamData {
  id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  days_to_first_job: number | null;
  crew_size: string;
  is_permanent: boolean;
  has_smartphone: string;
  work_mode: string;
  transport_mode: string;
  created_at: string;
  team_availabilities: Array<{
    teamName: string;
    startDate: string;
    endDate: string;
    status: string;
  }>;
}

interface Summary {
  total_allocations: number;
  days_to_first_job: number | null;
  total_unique_jobs: number;
  total_area: number;
  total_workers: number;
  total_earnings: number;
  total_paid: number;
  total_pending: number;
  avg_area_per_allocation: number;
  avg_earnings_per_allocation: number;
}

interface Allocation {
  allocation_id: number;
  work_date: string;
  allocated_area: number;
  crew_size: number;
  status: string;
  allocated_by: string;
  allocated_at: string;
  job: {
    job_id: string;
    location: string;
  };
  activity: {
    activity_name: string;
    activity_type: string;
  };
  farmer: {
    farmer_name: string;
    phone: string;
    village: string;
  };
  payment: {
    mukkadam_price: number;
    total_earnings: number;
    payment_status: string;
    paid_amount: number;
    pending_amount: number;
  };
}

interface Breakdown {
  by_activity: Array<{ activity_name: string; count: number; area: number; earnings: number }>;
  by_status: Array<{ status: string; count: number }>;
  by_month: Array<{ month: string; count: number; area: number; earnings: number }>;
  by_location: Array<{ location: string; count: number; area: number; earnings: number }>;
  by_allocated_by: Array<{ allocated_by: string; count: number; area: number; earnings: number }>;
}

export default function MukkadamDetails() {
  const { mukkadamId } = useParams<{ mukkadamId: string }>();
  const navigate = useNavigate();
  
  const [mukkadam, setMukkadam] = useState<MukkadamData | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [breakdowns, setBreakdowns] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchDetails();
  }, [mukkadamId]);
  
  const fetchDetails = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/ap/mukkadam-scorecard-details/${mukkadamId}/`
      );
      const data = await response.json();
      
      setMukkadam(data.mukkadam);
      setSummary(data.summary);
      setAllocations(data.allocations);
      setBreakdowns(data.breakdowns);
    } catch (error) {
      console.error('Error fetching mukkadam details:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const getStatusBadge = (status: string) => {
    const statusColors: Record<string, string> = {
      allocated: 'bg-blue-500',
      in_progress: 'bg-yellow-500',
      completed: 'bg-green-500',
      cancelled: 'bg-red-500',
    };
    
    return (
      <Badge className={statusColors[status] || 'bg-gray-500'}>
        {status.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };
  
  const getPaymentStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      paid: 'bg-green-500',
      pending: 'bg-orange-500',
      unpaid: 'bg-red-500',
    };
    
    return (
      <Badge className={colors[status] || 'bg-gray-500'}>
        {status.toUpperCase()}
      </Badge>
    );
  };
  
  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <span className="ml-2 text-gray-600">Loading details...</span>
        </div>
      </div>
    );
  }
  
  if (!mukkadam || !summary) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12 text-gray-500">
          Mukkadam not found
        </div>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto p-6 space-y-6 max-w-[1600px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={() => navigate('/mukkadam-scorecard')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{mukkadam.mukkadam_name}</h1>
            <p className="text-gray-600 mt-1">Mukkadam Details & Performance</p>
          </div>
        </div>
      </div>
      
      {/* Basic Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <User className="w-5 h-5 mr-2" />
            Basic Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-600 mb-1">Mobile Number</p>
              <div className="flex items-center">
                <Phone className="w-4 h-4 mr-2 text-gray-400" />
                <p className="font-medium text-gray-900">{mukkadam.mobile_numbers}</p>
              </div>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Location</p>
              <div className="flex items-center">
                <MapPin className="w-4 h-4 mr-2 text-gray-400" />
                <p className="font-medium text-gray-900">{mukkadam.village || 'Not specified'}</p>
              </div>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Crew Size</p>
              <div className="flex items-center">
                <Users className="w-4 h-4 mr-2 text-gray-400" />
                <p className="font-medium text-gray-900">{mukkadam.crew_size} workers</p>
              </div>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Work Mode</p>
              <div className="flex items-center">
                <Briefcase className="w-4 h-4 mr-2 text-gray-400" />
                <p className="font-medium text-gray-900">
                  {mukkadam.work_mode.replace('_', ' ')}
                </p>
              </div>
            </div>

<div>
              <p className="text-sm text-gray-600 mb-1">days to first</p>
              <div className="flex items-center">
                {summary.days_to_first_job !== null ? `${summary.days_to_first_job} Days` : 'N/A'}

              </div>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Has Smartphone</p>
              <Badge className={mukkadam.has_smartphone === 'yes' ? 'bg-green-500' : 'bg-red-500'}>
                {mukkadam.has_smartphone.toUpperCase()}
              </Badge>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Permanent</p>
              <Badge className={mukkadam.is_permanent ? 'bg-green-500' : 'bg-gray-500'}>
                {mukkadam.is_permanent ? 'YES' : 'NO'}
              </Badge>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Transport</p>
              <p className="font-medium text-gray-900">
                {mukkadam.transport_mode.replace('_', ' ')}
              </p>
            </div>
            
            <div>
              <p className="text-sm text-gray-600 mb-1">Registered On</p>
              <div className="flex items-center">
                <Calendar className="w-4 h-4 mr-2 text-gray-400" />
                <p className="font-medium text-gray-900">
                  {new Date(mukkadam.created_at).toLocaleDateString('en-IN')}
                </p>
              </div>
            </div>
          </div>
          
          {/* Team Availabilities */}
          {mukkadam.team_availabilities && mukkadam.team_availabilities.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold text-gray-900 mb-3">Team Availability</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {mukkadam.team_availabilities.map((avail, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-medium text-gray-900">{avail.teamName}</p>
                      <Badge className="bg-green-500">{avail.status}</Badge>
                    </div>
                    <p className="text-sm text-gray-600">
                      {new Date(avail.startDate).toLocaleDateString('en-IN')} - {' '}
                      {new Date(avail.endDate).toLocaleDateString('en-IN')}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Jobs</p>
                <p className="text-2xl font-bold text-gray-900">{summary.total_unique_jobs}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {summary.total_allocations} allocations
                </p>
              </div>
              <Briefcase className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Area</p>
                <p className="text-2xl font-bold text-gray-900">{summary.total_area.toFixed(2)}</p>
                <p className="text-xs text-gray-500 mt-1">acres allocated</p>
              </div>
              <MapPin className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Earnings</p>
                <p className="text-2xl font-bold text-gray-900">
                  ₹{summary.total_earnings.toLocaleString('en-IN')}
                </p>
                <p className="text-xs text-green-600 mt-1 font-medium">
                  ₹{summary.total_paid.toLocaleString('en-IN')} paid
                </p>
              </div>
              <DollarSign className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Workers Supplied</p>
                <p className="text-2xl font-bold text-gray-900">{summary.total_workers}</p>
                <p className="text-xs text-gray-500 mt-1">total workers</p>
              </div>
              <Users className="w-8 h-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Breakdowns */}
      {breakdowns && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* By Activity */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center text-lg">
                <Activity className="w-5 h-5 mr-2" />
                By Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakdowns.by_activity.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-900">{item.activity_name}</p>
                      <p className="text-sm text-gray-600">
                        {item.count} jobs • {item.area.toFixed(2)} acres
                      </p>
                    </div>
                    <p className="font-semibold text-gray-900">
                      ₹{item.earnings.toLocaleString('en-IN')}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          
          {/* By Location */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center text-lg">
                <MapPin className="w-5 h-5 mr-2" />
                By Location
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakdowns.by_location.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-900">{item.location}</p>
                      <p className="text-sm text-gray-600">
                        {item.count} jobs • {item.area.toFixed(2)} acres
                      </p>
                    </div>
                    <p className="font-semibold text-gray-900">
                      ₹{item.earnings.toLocaleString('en-IN')}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          
          {/* By Month */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center text-lg">
                <Calendar className="w-5 h-5 mr-2" />
                By Month
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakdowns.by_month.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-900">
                        {new Date(item.month + '-01').toLocaleDateString('en-IN', { 
                          month: 'long', 
                          year: 'numeric' 
                        })}
                      </p>
                      <p className="text-sm text-gray-600">
                        {item.count} jobs • {item.area.toFixed(2)} acres
                      </p>
                    </div>
                    <p className="font-semibold text-gray-900">
                      ₹{item.earnings.toLocaleString('en-IN')}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          
          {/* By Allocated By */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center text-lg">
                <User className="w-5 h-5 mr-2" />
                By Allocated By
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakdowns.by_allocated_by.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-900">{item.allocated_by}</p>
                      <p className="text-sm text-gray-600">
                        {item.count} jobs • {item.area.toFixed(2)} acres
                      </p>
                    </div>
                    <p className="font-semibold text-gray-900">
                      ₹{item.earnings.toLocaleString('en-IN')}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Allocations Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">All Allocations ({allocations.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Activity</TableHead>
                  <TableHead>Farmer</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead className="text-right">Area</TableHead>
                  <TableHead className="text-right">Workers</TableHead>
                  <TableHead className="text-right">Earnings</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Allocated By</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {allocations.map((alloc) => (
                  <TableRow key={alloc.allocation_id}>
                    <TableCell>
                      <div className="flex items-center">
                        <Clock className="w-4 h-4 mr-2 text-gray-400" />
                        {new Date(alloc.work_date).toLocaleDateString('en-IN')}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{alloc.job.job_id}</TableCell>
                    <TableCell>{alloc.activity.activity_name}</TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium text-gray-900">{alloc.farmer.farmer_name}</p>
                        <p className="text-xs text-gray-500">{alloc.farmer.phone}</p>
                      </div>
                    </TableCell>
                    <TableCell>{alloc.job.location}</TableCell>
                    <TableCell className="text-right font-medium">
                      {alloc.allocated_area.toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right">{alloc.crew_size}</TableCell>
                    <TableCell className="text-right font-semibold text-gray-900">
                      ₹{alloc.payment.total_earnings.toLocaleString('en-IN')}
                    </TableCell>
                    <TableCell>{getStatusBadge(alloc.status)}</TableCell>
                    <TableCell>{getPaymentStatusBadge(alloc.payment.payment_status)}</TableCell>
                    <TableCell className="text-gray-700">{alloc.allocated_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}