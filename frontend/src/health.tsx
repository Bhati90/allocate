// src/pages/SupplyHealthDashboard.tsx

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, TrendingUp, Users, DollarSign, Truck,
  Calendar, CheckCircle, XCircle, AlertTriangle,
  Activity, Target, Award, Clock, ChevronDown, ChevronUp
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getAuthConfig } from './utils/auth';

// Types
interface HealthMetric {
  this_week: number;
  overall_avg: number;
  status: string;
}

interface DayBreakdown {
  date: string;
  day_name: string;
  has_work: boolean;
  allocations: any[];
  status: string;
}

interface MukkadamDetail {
  mukkadam_id: number;
  mukkadam_name: string;
  village: string;
  mobile_numbers: string;
  crew_size: number;
  available_days_this_week: number;
  work_days_this_week: number;
  idle_days_this_week: number;
  utilization_this_week: number;
  utilization_status: string;
  earnings_this_week: number;
  day_breakdown: DayBreakdown[];
}

interface SupplyHealthData {
  success: boolean;
  reference_date: string;
  week_range: {
    start: string;
    end: string;
  };
  section_1_supply_health_snapshot: {
    active_teams: HealthMetric;
    available_team_days: HealthMetric & { mukkadam_breakdown: MukkadamDetail[] };
    avg_utilization: HealthMetric;
    idle_teams: HealthMetric & { idle_team_list: MukkadamDetail[] };
    avg_earnings_per_person_day: HealthMetric;
    transport_cost_pct: HealthMetric;
  };
  section_2_supply_inflow: {
    teams_registered: number;
    transporters_registered: number;
    teams_confirmed: number;
    teams_allocated: number;
    activation_pct: number;
    avg_days_to_first_job: number;
    teams_rejected: number;
  };
  section_3_utilization_distribution: Array<{
    bucket: string;
    count: number;
    percentage: number;
    teams: MukkadamDetail[];
  }>;
}

const SupplyHealthDashboard: React.FC = () => {
  const navigate = useNavigate();
  
  const [data, setData] = useState<SupplyHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [referenceDate, setReferenceDate] = useState<string>(
    format(new Date(), 'yyyy-MM-dd')
  );
  
  const [expandedMukkadam, setExpandedMukkadam] = useState<number | null>(null);
  const [expandedBucket, setExpandedBucket] = useState<string | null>(null);
  const [showIdleTeams, setShowIdleTeams] = useState(false);
  
  useEffect(() => {
    fetchData();
  }, [referenceDate]);
  
  const fetchData = async () => {
    setLoading(true);
    try {
      const config = getAuthConfig();
      const response = await axios.get(
        `http://localhost:8001/ap/supply-health/?reference_date=${referenceDate}`,
        config
      );
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch supply health data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 font-semibold">Loading Supply Health...</p>
        </div>
      </div>
    );
  }
  
  if (!data || !data.success) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-100">
        <div className="text-center bg-white p-8 rounded-lg shadow-lg">
          <XCircle className="mx-auto text-red-500 mb-4" size={48} />
          <p className="text-gray-700 font-semibold">Failed to load data</p>
          <button 
            onClick={() => navigate('/dashboard')}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }
  
  const snapshot = data.section_1_supply_health_snapshot;
  const inflow = data.section_2_supply_inflow;
  const distribution = data.section_3_utilization_distribution;
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-teal-700 text-white shadow-xl">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center text-green-100 hover:text-white mb-4 transition"
          >
            <ArrowLeft size={18} className="mr-2" /> Back to Dashboard
          </button>
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center mb-2">
                <Activity className="mr-3" size={36} />
                Supply Health Dashboard
              </h1>
              <p className="text-green-100">
                Week: {format(parseISO(data.week_range.start), 'MMM dd')} - {format(parseISO(data.week_range.end), 'MMM dd, yyyy')}
              </p>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4">
              <label className="block text-xs text-green-100 mb-1">Reference Date</label>
              <input
                type="date"
                value={referenceDate}
                onChange={(e) => setReferenceDate(e.target.value)}
                className="px-3 py-1.5 rounded bg-white/20 text-white border border-white/30"
              />
            </div>
          </div>
        </div>
      </div>
      
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        
        {/* SECTION 1: SUPPLY HEALTH SNAPSHOT */}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <Target className="mr-2" size={24} />
              1. Supply Health Snapshot
            </h2>
          </div>
          
          <div className="p-6">
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-bold text-gray-700">Metric</th>
                    <th className="px-4 py-3 text-center text-sm font-bold text-gray-700">This Week</th>
                    <th className="px-4 py-3 text-center text-sm font-bold text-gray-700">Overall Avg</th>
                    <th className="px-4 py-3 text-center text-sm font-bold text-gray-700">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">Active Teams</td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-blue-600">
                      {snapshot.active_teams.this_week}
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      {snapshot.active_teams.overall_avg}
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.active_teams.status}
                    </td>
                  </tr>
                  
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-900">Available Team Days</div>
                      <button
                        onClick={() => setShowIdleTeams(!showIdleTeams)}
                        className="text-xs text-blue-600 hover:underline flex items-center mt-1"
                      >
                        {showIdleTeams ? 'Hide' : 'Show'} Mukkadam Details
                        {showIdleTeams ? <ChevronUp size={14} className="ml-1" /> : <ChevronDown size={14} className="ml-1" />}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-blue-600">
                      {snapshot.available_team_days.this_week}
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      {snapshot.available_team_days.overall_avg}
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.available_team_days.status}
                    </td>
                  </tr>
                  
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">Avg Utilization %</td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-green-600">
                      {snapshot.avg_utilization.this_week}%
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      {snapshot.avg_utilization.overall_avg}%
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.avg_utilization.status}
                    </td>
                  </tr>
                  
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">Idle Teams</td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-red-600">
                      {snapshot.idle_teams.this_week}
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      {snapshot.idle_teams.overall_avg}
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.idle_teams.status}
                    </td>
                  </tr>
                  
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">Avg ₹ / Person / Day</td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-purple-600">
                      ₹{snapshot.avg_earnings_per_person_day.this_week}
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      ₹{snapshot.avg_earnings_per_person_day.overall_avg}
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.avg_earnings_per_person_day.status}
                    </td>
                  </tr>
                  
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">Transport Cost %</td>
                    <td className="px-4 py-3 text-center text-xl font-bold text-orange-600">
                      {snapshot.transport_cost_pct.this_week}%
                    </td>
                    <td className="px-4 py-3 text-center text-lg font-semibold text-gray-600">
                      {snapshot.transport_cost_pct.overall_avg}%
                    </td>
                    <td className="px-4 py-3 text-center text-2xl">
                      {snapshot.transport_cost_pct.status}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            
            {/* Mukkadam Day-by-Day Breakdown */}
            {showIdleTeams && (
              <div className="mt-6 space-y-4">
                <h3 className="text-lg font-bold text-gray-900 border-b pb-2">
                  Mukkadam Availability Details (This Week)
                </h3>
                
                {snapshot.available_team_days.mukkadam_breakdown
                  .sort((a, b) => b.utilization_this_week - a.utilization_this_week)
                  .map(mukkadam => (
                    <div
                      key={mukkadam.mukkadam_id}
                      className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden"
                    >
                      <div
                        className="p-4 cursor-pointer hover:bg-gray-100 transition"
                        onClick={() => setExpandedMukkadam(
                          expandedMukkadam === mukkadam.mukkadam_id ? null : mukkadam.mukkadam_id
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold ${
                              mukkadam.utilization_status === '🟢' ? 'bg-green-500 text-white' :
                              mukkadam.utilization_status === '🟠' ? 'bg-yellow-500 text-white' :
                              'bg-red-500 text-white'
                            }`}>
                              {mukkadam.utilization_this_week.toFixed(0)}%
                            </div>
                            <div>
                              <h4 className="font-bold text-gray-900">{mukkadam.mukkadam_name}</h4>
                              <p className="text-sm text-gray-600">{mukkadam.village}</p>
                              <p className="text-xs text-gray-500">{mukkadam.mobile_numbers}</p>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-4 gap-4 text-center">
                            <div>
                              <p className="text-xs text-gray-500">Available</p>
                              <p className="font-bold text-blue-600">{mukkadam.available_days_this_week}d</p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Work Days</p>
                              <p className="font-bold text-green-600">{mukkadam.work_days_this_week}d</p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Idle Days</p>
                              <p className="font-bold text-red-600">{mukkadam.idle_days_this_week}d</p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Earnings</p>
                              <p className="font-bold text-purple-600">₹{(mukkadam.earnings_this_week / 1000).toFixed(1)}K</p>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {expandedMukkadam === mukkadam.mukkadam_id && (
                        <div className="px-4 pb-4 bg-white border-t border-gray-200">
                          <h5 className="font-bold text-gray-700 mt-4 mb-3">Day-by-Day Breakdown:</h5>
                          <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
                            {mukkadam.day_breakdown.map(day => (
                              <div
                                key={day.date}
                                className={`p-3 rounded-lg border-2 ${
                                  day.has_work 
                                    ? 'border-green-500 bg-green-50' 
                                    : 'border-red-300 bg-red-50'
                                }`}
                              >
                                <div className="text-xs font-bold text-gray-700 mb-1">
                                  {format(parseISO(day.date), 'EEE')}
                                </div>
                                <div className="text-xs text-gray-600 mb-2">
                                  {format(parseISO(day.date), 'MMM dd')}
                                </div>
                                <div className={`text-xs font-bold ${day.has_work ? 'text-green-700' : 'text-red-700'}`}>
                                  {day.status}
                                </div>
                                
                                {day.has_work && day.allocations.length > 0 && (
                                  <div className="mt-2 space-y-1">
                                    {day.allocations.map((alloc, idx) => (
                                      <div key={idx} className="text-xs bg-white p-1.5 rounded border border-green-200">
                                        <div className="font-semibold text-gray-800">{alloc.job_activity__activity_name}</div>
                                        <div className="text-gray-600">{alloc.allocated_area} acres</div>
                                        <div className="text-green-600 font-bold">₹{alloc.mukkadam_price}</div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
        
        {/* SECTION 2: SUPPLY INFLOW */}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-purple-600 to-purple-700 px-6 py-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <TrendingUp className="mr-2" size={24} />
              2. Supply Inflow (This Week)
            </h2>
          </div>
          
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
                <p className="text-xs text-blue-700 font-bold mb-1">Teams Registered</p>
                <p className="text-3xl font-bold text-blue-800">{inflow.teams_registered}</p>
              </div>
              
              <div className="bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
                <p className="text-xs text-green-700 font-bold mb-1">Transporters Registered</p>
                <p className="text-3xl font-bold text-green-800">{inflow.transporters_registered}</p>
              </div>
              
              <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 p-4 rounded-lg border border-yellow-200">
                <p className="text-xs text-yellow-700 font-bold mb-1">Teams Confirmed</p>
                <p className="text-3xl font-bold text-yellow-800">{inflow.teams_confirmed}</p>
              </div>
              
              <div className="bg-gradient-to-br from-teal-50 to-teal-100 p-4 rounded-lg border border-teal-200">
                <p className="text-xs text-teal-700 font-bold mb-1">Teams Allocated</p>
                <p className="text-3xl font-bold text-teal-800">{inflow.teams_allocated}</p>
              </div>
              
              <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
                <p className="text-xs text-purple-700 font-bold mb-1">Activation %</p>
                <p className="text-3xl font-bold text-purple-800">{inflow.activation_pct}%</p>
              </div>
              
              <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 p-4 rounded-lg border border-indigo-200">
                <p className="text-xs text-indigo-700 font-bold mb-1">Avg Days to First Job</p>
                <p className="text-3xl font-bold text-indigo-800">{inflow.avg_days_to_first_job}</p>
              </div>
              
              <div className="bg-gradient-to-br from-red-50 to-red-100 p-4 rounded-lg border border-red-200 col-span-2">
                <p className="text-xs text-red-700 font-bold mb-1">Teams Rejected (30+ days, no job)</p>
                <p className="text-3xl font-bold text-red-800">{inflow.teams_rejected}</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* SECTION 3: UTILIZATION DISTRIBUTION */}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-orange-600 to-orange-700 px-6 py-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <Award className="mr-2" size={24} />
              3. Utilization & Idle Risk
            </h2>
          </div>
          
          <div className="p-6">
            <div className="overflow-x-auto mb-6">
              <table className="min-w-full">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-bold text-gray-700">Bucket</th>
                    <th className="px-4 py-3 text-center text-sm font-bold text-gray-700"># Teams</th>
                    <th className="px-4 py-3 text-center text-sm font-bold text-gray-700">% of Teams</th>
                    <th className="px-4 py-3 text-left text-sm font-bold text-gray-700">Visual</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {distribution.map((bucket, idx) => {
                    const colorClass = 
                      bucket.bucket === '90%+' ? 'bg-green-500' :
                      bucket.bucket === '75-90%' ? 'bg-teal-500' :
                      bucket.bucket === '50-75%' ? 'bg-yellow-500' :
                      bucket.bucket === '25-50%' ? 'bg-orange-500' :
                      'bg-red-500';
                    
                    return (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <button
                            onClick={() => setExpandedBucket(expandedBucket === bucket.bucket ? null : bucket.bucket)}
                            className="font-bold text-gray-900 hover:text-blue-600 flex items-center"
                          >
                            {bucket.bucket}
                            {expandedBucket === bucket.bucket ? <ChevronUp size={16} className="ml-2" /> : <ChevronDown size={16} className="ml-2" />}
                          </button>
                        </td>
                        <td className="px-4 py-3 text-center text-xl font-bold text-blue-600">
                          {bucket.count}
                        </td>
                        <td className="px-4 py-3 text-center text-lg font-semibold text-gray-700">
                          {bucket.percentage}%
                        </td>
                        <td className="px-4 py-3">
                          <div className="bg-gray-200 rounded-full h-8 overflow-hidden">
                            <div
                              className={`${colorClass} h-full flex items-center px-3 text-white font-bold text-sm`}
                              style={{ width: `${bucket.percentage}%`, minWidth: bucket.count > 0 ? '40px' : '0px' }}
                            >
                              {bucket.count > 0 && bucket.count}
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            
            {/* Expanded Bucket Details */}
            {expandedBucket && (
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h4 className="font-bold text-gray-900 mb-3">
                  Teams in {expandedBucket} Utilization
                </h4>
                <div className="space-y-2">
                  {distribution
                    .find(b => b.bucket === expandedBucket)?.teams
                    .slice(0, 10)
                    .map(team => (
                      <div key={team.mukkadam_id} className="bg-white p-3 rounded border border-gray-200 flex items-center justify-between">
                        <div>
                          <p className="font-semibold text-gray-900">{team.mukkadam_name}</p>
                          <p className="text-sm text-gray-600">{team.village}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-lg text-blue-600">{team.utilization_this_week}%</p>
                          <p className="text-xs text-gray-500">
                            {team.work_days_this_week}/{team.available_days_this_week} days
                          </p>
                        </div>
                      </div>
                    ))}
                  {distribution.find(b => b.bucket === expandedBucket)!.teams.length > 10 && (
                    <p className="text-sm text-gray-500 text-center">
                      ...and {distribution.find(b => b.bucket === expandedBucket)!.teams.length - 10} more
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
        
      </div>
    </div>
  );
};

export default SupplyHealthDashboard;