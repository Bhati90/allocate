// components/MapView/HexagonDetails.tsx - Compact horizontal layout
import React from 'react';
import { MapPin, Users, TrendingUp, DollarSign, Briefcase, Calendar, X } from 'lucide-react';
import type { HexagonCluster, MukkadamPosition } from '../../types/map';

type Props = {
  hexagon: HexagonCluster;
  jobs: any[];
  mukkadams: MukkadamPosition[];
  compact?: boolean; // ✅ Add compact mode
};

export function HexagonDetails({ hexagon, jobs, mukkadams, compact = true }: Props) {
  const mukkadamsInCluster = mukkadams.filter((m) => m.cluster_id === hexagon.id);
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-300';
      case 'in_progress': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'fully_allocated': return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'partially_allocated': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Section - Key Info */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Villages */}
        <div className="bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
          <div className="flex items-center gap-2 mb-3">
            <MapPin className="w-5 h-5 text-gray-700" />
            <h3 className="text-sm font-bold text-gray-900">Coverage</h3>
          </div>
          <div className="text-3xl font-bold text-gray-900 mb-2">
            {hexagon.villages.length}
          </div>
          <div className="text-xs text-gray-600">
            {hexagon.villages.length === 0 ? 'No villages' : 
             hexagon.villages.length === 1 ? 'village' : 'villages'}
          </div>
          {hexagon.villages.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {hexagon.villages.slice(0, 3).map((village) => (
                <span key={village} className="px-2 py-1 bg-white text-gray-700 rounded text-xs border border-gray-300">
                  {village}
                </span>
              ))}
              {hexagon.villages.length > 3 && (
                <span className="px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs">
                  +{hexagon.villages.length - 3} more
                </span>
              )}
            </div>
          )}
        </div>

        {/* Financial Summary */}
        <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-xl p-4 border-2 border-emerald-200">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-emerald-700" />
              <span className="text-xs font-semibold text-emerald-700">Revenue</span>
            </div>
            <div className="text-3xl font-bold text-emerald-900">
              ₹{(hexagon.total_revenue / 1000).toFixed(0)}K
            </div>
          </div> */}

          {/* <div className="bg-gradient-to-br from-rose-50 to-rose-100 rounded-xl p-4 border-2 border-rose-200">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-rose-700" />
              <span className="text-xs font-semibold text-rose-700">Cost</span>
            </div>
            <div className="text-3xl font-bold text-rose-900">
              ₹{(hexagon.total_cost / 1000).toFixed(0)}K
            </div>
          </div> */}

          {/* <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border-2 border-purple-200">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-purple-700" />
              <span className="text-xs font-semibold text-purple-700">Profit</span>
            </div>
            <div className="text-3xl font-bold text-purple-900">
              ₹{(hexagon.profit / 1000).toFixed(0)}K
            </div>
            <div className="text-xs text-purple-600 mt-1">
              {hexagon.profit_margin.toFixed(1)}% margin
            </div>
          </div> */}

          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border-2 border-blue-200">
            <div className="flex items-center gap-2 mb-2">
              <MapPin className="w-4 h-4 text-blue-700" />
              <span className="text-xs font-semibold text-blue-700">Area</span>
            </div>
            <div className="text-3xl font-bold text-blue-900">
              {hexagon.booked_acres.toFixed(0)}
            </div>
            <div className="text-xs text-blue-600 mt-1">
              of {hexagon.total_cultivable_acres} acres
            </div>
          </div>
        </div>
      </div>

      {/* Middle Section - Jobs & Teams */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Jobs Overview */}
        <div className="bg-gray-50 rounded-xl p-5 border-2 border-gray-200">
          <div className="flex items-center gap-2 mb-4">
            <Briefcase className="w-5 h-5 text-gray-700" />
            <h3 className="text-base font-bold text-gray-900">Jobs Overview</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white rounded-lg p-3 border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Total Jobs</div>
              <div className="text-2xl font-bold text-gray-900">{hexagon.total_jobs}</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Activities</div>
              <div className="text-2xl font-bold text-gray-900">{hexagon.total_activities}</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Allocations</div>
              <div className="text-2xl font-bold text-gray-900">{hexagon.total_allocations}</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-gray-200">
              <div className="text-xs text-gray-600 mb-1">Pending</div>
              <div className="text-2xl font-bold text-orange-600">{hexagon.pending_jobs}</div>
            </div>
          </div>

          {/* Status Breakdown */}
          <div className="mt-4 pt-4 border-t border-gray-300">
            <h4 className="text-sm font-bold text-gray-700 mb-3">Status Breakdown</h4>
            <div className="space-y-2">
              {Object.entries(hexagon.status_counts).map(([status, count]) => (
                count > 0 && (
                  <div key={status} className="flex items-center justify-between">
                    <span className={`px-2 py-1 rounded text-xs font-semibold border ${getStatusColor(status)}`}>
                      {status.replace('_', ' ')}
                    </span>
                    <span className="text-sm font-bold text-gray-900">{count}</span>
                  </div>
                )
              ))}
            </div>
          </div>

          {/* Booking Types */}
          <div className="mt-4 pt-4 border-t border-gray-300 grid grid-cols-2 gap-3">
            <div className="bg-purple-50 rounded-lg p-3 border border-purple-200">
              <div className="text-xs text-purple-700 font-semibold mb-1">Tender</div>
              <div className="text-xl font-bold text-purple-900">{hexagon.tender_count}</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
              <div className="text-xs text-blue-700 font-semibold mb-1">On-demand</div>
              <div className="text-xl font-bold text-blue-900">{hexagon.ondemand_count}</div>
            </div>
          </div>
        </div>

        {/* Team Capacity & Teams */}
        <div className="space-y-4">
          {/* Capacity */}
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-5 border-2 border-indigo-200">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-5 h-5 text-indigo-700" />
              <h3 className="text-base font-bold text-indigo-900">Team Capacity</h3>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <div className="text-xs text-indigo-700 mb-1">Available Workers</div>
                <div className="text-2xl font-bold text-indigo-900">
                  {Math.round(hexagon.available_workers)}
                </div>
              </div>
              <div>
                <div className="text-xs text-indigo-700 mb-1">Needed Workers</div>
                <div className="text-2xl font-bold text-indigo-900">
                  {hexagon.needed_workers}
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-indigo-200">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-gray-600 font-semibold">Capacity Utilization</span>
                <span className="font-bold text-gray-900">
                  {hexagon.capacity_utilization.toFixed(0)}%
                </span>
              </div>
              <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    hexagon.capacity_utilization > 90
                      ? 'bg-red-600'
                      : hexagon.capacity_utilization > 60
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(hexagon.capacity_utilization, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Teams List */}
          {mukkadamsInCluster.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-5 border-2 border-gray-200 max-h-64 overflow-y-auto">
              <h3 className="text-sm font-bold text-gray-900 mb-3">
                Teams in Cluster ({mukkadamsInCluster.length})
              </h3>
              <div className="space-y-2">
                {mukkadamsInCluster.map((mukkadam) => (
                  <div
                    key={mukkadam.id}
                    className="bg-white rounded-lg p-3 border border-gray-200 hover:border-blue-300 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${mukkadam.is_live_location ? 'bg-green-500' : 'bg-gray-400'}`} />
                        <span className="text-sm font-bold text-gray-900">{mukkadam.name}</span>
                      </div>
                      <span className="text-xs font-semibold text-gray-600">
                        {mukkadam.crew_size} workers
                      </span>
                    </div>
                    {mukkadam.current_allocation && (
                      <div className="text-xs text-gray-600 bg-blue-50 rounded px-2 py-1 border border-blue-200">
                        Working: {mukkadam.current_allocation.activity_name} @ {mukkadam.current_allocation.location}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Future Predictions */}
      {(hexagon.future_booked_acres > 0 || hexagon.upcoming_activities_week > 0) && (
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-5 border-2 border-amber-200">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-5 h-5 text-amber-700" />
            <h3 className="text-base font-bold text-amber-900">Future Predictions</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-white rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-gray-600 mb-1">This Week</div>
              <div className="text-xl font-bold text-gray-900">
                {hexagon.upcoming_activities_week}
              </div>
              <div className="text-xs text-gray-500">activities</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-gray-600 mb-1">This Month</div>
              <div className="text-xl font-bold text-gray-900">
                {hexagon.upcoming_activities_month}
              </div>
              <div className="text-xs text-gray-500">activities</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-gray-600 mb-1">Future Area</div>
              <div className="text-xl font-bold text-gray-900">
                {hexagon.future_booked_acres.toFixed(0)}
              </div>
              <div className="text-xs text-gray-500">acres</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-gray-600 mb-1">Workers Needed</div>
              <div className="text-xl font-bold text-gray-900">
                {hexagon.future_needed_workers}
              </div>
              <div className="text-xs text-gray-500">workers</div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-gray-600 mb-1">Revenue Potential</div>
              <div className="text-xl font-bold text-emerald-600">
                ₹{(hexagon.future_revenue / 1000).toFixed(0)}K
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}