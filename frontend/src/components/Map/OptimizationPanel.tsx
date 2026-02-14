// components/MapView/OptimizationPanel.tsx - Complete rewrite with actions
import React, { useState } from 'react';
import { AlertTriangle, TrendingUp, Users, ArrowRight, X, CheckCircle, Info } from 'lucide-react';
import type { HexagonCluster, MukkadamPosition } from '../../types/map';

type Props = {
  hexagons: HexagonCluster[];
  mukkadams: MukkadamPosition[];
  onSelectHex?: (hexId: string) => void;
};

type OptimizationType = 'warning' | 'opportunity' | 'suggestion';

type Optimization = {
  type: OptimizationType;
  title: string;
  description: string;
  hexId: string;
  metric: string;
  impact: {
    workers_needed?: number;
    revenue_potential?: number;
    cost_saving?: number;
    workers_idle?: number;
  };
  actions: Action[];
};

type Action = {
  id: string;
  label: string;
  description: string;
  impact: string;
  type: 'primary' | 'secondary';
};

export function OptimizationPanel({ hexagons, mukkadams, onSelectHex }: Props) {
  const [selectedOptimization, setSelectedOptimization] = useState<Optimization | null>(null);
  const [showActionModal, setShowActionModal] = useState(false);

  const optimizations: Optimization[] = [];

  // Analyze each hexagon
  for (const hex of hexagons) {
    // 🔴 Critical: High demand, low capacity
    if (hex.demand_score > 70 && hex.capacity_utilization > 90) {
      const workersShort = hex.needed_workers - Math.round(hex.available_workers);
      optimizations.push({
        type: 'warning',
        title: `${hex.id}: Critical Capacity Shortage`,
        description: `High demand (${hex.demand_score.toFixed(0)}/100) with ${hex.capacity_utilization.toFixed(0)}% capacity utilization.`,
        hexId: hex.id,
        metric: `${workersShort} workers short`,
        impact: {
          workers_needed: workersShort,
          revenue_potential: hex.future_revenue,
        },
        actions: [
          {
            id: 'redistribute',
            label: 'Redistribute Teams',
            description: `Move ${Math.ceil(workersShort / 15)} teams from low-demand clusters to ${hex.id}`,
            impact: `Will increase capacity to ${(hex.available_workers + workersShort).toFixed(0)} workers, reducing utilization to ~60%`,
            type: 'primary',
          },
          {
            id: 'hire',
            label: 'Hire New Teams',
            description: `Recruit ${Math.ceil(workersShort / 15)} new mukkadam teams for this cluster`,
            impact: `Permanently increase capacity by ${workersShort} workers. Estimated cost: ₹${(workersShort * 500).toLocaleString('en-IN')}/day`,
            type: 'secondary',
          },
          {
            id: 'defer',
            label: 'Defer Low-Priority Jobs',
            description: `Reschedule ${Math.ceil(hex.pending_jobs * 0.3)} pending jobs to next week`,
            impact: `Reduce immediate demand by ${Math.ceil(workersShort * 0.3)} workers`,
            type: 'secondary',
          },
        ],
      });
    }

    // 🟢 Opportunity: Low penetration, high potential
    if (hex.market_penetration < 30 && hex.total_cultivable_acres > 5000) {
      const potentialAcres = hex.total_cultivable_acres - hex.booked_acres;
      const potentialRevenue = potentialAcres * 3000;
      optimizations.push({
        type: 'opportunity',
        title: `${hex.id}: Growth Opportunity`,
        description: `Only ${hex.market_penetration.toFixed(0)}% market penetration with ${potentialAcres.toFixed(0)} acres available.`,
        hexId: hex.id,
        metric: `₹${(potentialRevenue / 100000).toFixed(0)}L revenue potential`,
        impact: {
          revenue_potential: potentialRevenue,
        },
        actions: [
          {
            id: 'sales_push',
            label: 'Intensive Sales Campaign',
            description: `Deploy 2 field agents to ${hex.villages.join(', ')} for 2 weeks`,
            impact: `Target 30% increase in bookings (${(potentialAcres * 0.3).toFixed(0)} acres). Expected revenue: ₹${((potentialAcres * 0.3 * 3000) / 1000).toFixed(0)}K`,
            type: 'primary',
          },
          {
            id: 'demo',
            label: 'Organize Demo Days',
            description: `Conduct 3 farmer demo events showcasing service quality`,
            impact: `Build trust, expected 20% conversion rate from attendees`,
            type: 'secondary',
          },
          {
            id: 'referral',
            label: 'Farmer Referral Program',
            description: `Offer ₹500 referral bonus to existing ${hex.unique_farmers} farmers`,
            impact: `Each farmer refers 2-3 neighbors, potential ${(hex.unique_farmers * 2.5).toFixed(0)} new bookings`,
            type: 'secondary',
          },
        ],
      });
    }

    // ⚠️ Warning: Future capacity crunch
    if (hex.upcoming_activities_week > 5 && hex.future_needed_workers > hex.available_workers * 1.5) {
      const futureShortage = hex.future_needed_workers - Math.round(hex.available_workers);
      optimizations.push({
        type: 'warning',
        title: `${hex.id}: Upcoming Capacity Crunch`,
        description: `${hex.upcoming_activities_week} activities next week need ${hex.future_needed_workers} workers.`,
        hexId: hex.id,
        metric: `${futureShortage} workers needed by next week`,
        impact: {
          workers_needed: futureShortage,
          revenue_potential: hex.future_revenue,
        },
        actions: [
          {
            id: 'advance_booking',
            label: 'Pre-Book Teams Now',
            description: `Reserve ${Math.ceil(futureShortage / 15)} teams from neighboring clusters for next week`,
            impact: `Secure capacity before demand spike. Lock in current rates.`,
            type: 'primary',
          },
          {
            id: 'extend_hours',
            label: 'Extend Working Hours',
            description: `Request teams work 10-hour days instead of 8 during peak week`,
            impact: `Increase effective capacity by 25% (${Math.ceil(hex.available_workers * 0.25)} equivalent workers)`,
            type: 'secondary',
          },
          {
            id: 'weekend',
            label: 'Weekend Work',
            description: `Schedule critical activities on Saturday/Sunday`,
            impact: `Spread workload across 7 days instead of 5, reduce peak pressure by 30%`,
            type: 'secondary',
          },
        ],
      });
    }

    // 🔵 Suggestion: Overcapacity
    if (hex.capacity_utilization < 30 && hex.available_workers > 20) {
      const idleWorkers = Math.round(hex.available_workers * 0.6);
      const costSaving = idleWorkers * 500 * 30; // ₹500/day * 30 days
      optimizations.push({
        type: 'suggestion',
        title: `${hex.id}: Excess Capacity`,
        description: `Only ${hex.capacity_utilization.toFixed(0)}% utilized with ${Math.round(hex.available_workers)} workers available.`,
        hexId: hex.id,
        metric: `${idleWorkers} workers idle`,
        impact: {
          workers_idle: idleWorkers,
          cost_saving: costSaving,
        },
        actions: [
          {
            id: 'redistribute_out',
            label: 'Redeploy to High-Demand Clusters',
            description: `Move ${Math.ceil(idleWorkers / 15)} teams to critical capacity clusters`,
            impact: `Save ₹${(costSaving / 1000).toFixed(0)}K/month in idle costs, increase revenue in target clusters`,
            type: 'primary',
          },
          {
            id: 'cross_train',
            label: 'Cross-Train for New Activities',
            description: `Train idle teams on spraying, harvesting techniques during downtime`,
            impact: `Increase service offerings, be ready for seasonal demand shifts`,
            type: 'secondary',
          },
          {
            id: 'temp_release',
            label: 'Temporary Release',
            description: `Release ${Math.ceil(idleWorkers / 15)} teams until demand increases`,
            impact: `Immediate cost saving of ₹${(costSaving / 1000).toFixed(0)}K/month, re-hire when needed`,
            type: 'secondary',
          },
        ],
      });
    }

    // 🟡 Opportunity: High margin area
    if (hex.profit_margin > 40 && hex.market_penetration < 50) {
      const potentialAcres = hex.total_cultivable_acres - hex.booked_acres;
      const potentialProfit = potentialAcres * 3000 * (hex.profit_margin / 100);
      optimizations.push({
        type: 'opportunity',
        title: `${hex.id}: High-Margin Expansion`,
        description: `${hex.profit_margin.toFixed(0)}% profit margin with room to grow to ${hex.total_cultivable_acres.toFixed(0)} acres.`,
        hexId: hex.id,
        metric: `₹${(potentialProfit / 100000).toFixed(0)}L profit potential`,
        impact: {
          revenue_potential: potentialAcres * 3000,
        },
        actions: [
          {
            id: 'premium_service',
            label: 'Launch Premium Service Tier',
            description: `Offer premium quality service at 20% higher rate in this high-margin cluster`,
            impact: `Maintain ${hex.profit_margin.toFixed(0)}% margin while growing revenue by ₹${((potentialAcres * 0.4 * 3600) / 1000).toFixed(0)}K`,
            type: 'primary',
          },
          {
            id: 'volume_discount',
            label: 'Volume Discount Campaign',
            description: `Offer 10% discount for farmers booking >5 acres`,
            impact: `Attract larger farms, book ${(potentialAcres * 0.5).toFixed(0)} more acres while maintaining profit`,
            type: 'secondary',
          },
        ],
      });
    }
  }

  // Sort by priority
  optimizations.sort((a, b) => {
    const priority = { warning: 0, opportunity: 1, suggestion: 2 };
    return priority[a.type] - priority[b.type];
  });

  const getIcon = (type: OptimizationType) => {
    switch (type) {
      case 'warning': return <AlertTriangle className="w-5 h-5" />;
      case 'opportunity': return <TrendingUp className="w-5 h-5" />;
      case 'suggestion': return <Users className="w-5 h-5" />;
    }
  };

  const getColorClasses = (type: OptimizationType) => {
    switch (type) {
      case 'warning': return 'bg-red-50 border-red-200 hover:border-red-400';
      case 'opportunity': return 'bg-emerald-50 border-emerald-200 hover:border-emerald-400';
      case 'suggestion': return 'bg-blue-50 border-blue-200 hover:border-blue-400';
    }
  };

  const getBadgeClasses = (type: OptimizationType) => {
    switch (type) {
      case 'warning': return 'bg-red-100 text-red-800 border-red-300';
      case 'opportunity': return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'suggestion': return 'bg-blue-100 text-blue-800 border-blue-300';
    }
  };

  const getIconColor = (type: OptimizationType) => {
    switch (type) {
      case 'warning': return 'text-red-600';
      case 'opportunity': return 'text-emerald-600';
      case 'suggestion': return 'text-blue-600';
    }
  };

  const handleOptimizationClick = (opt: Optimization) => {
    setSelectedOptimization(opt);
    setShowActionModal(true);
    if (onSelectHex) {
      onSelectHex(opt.hexId);
    }
  };

  const handleActionClick = (action: Action) => {
    console.log('Action clicked:', action.id, 'for', selectedOptimization?.hexId);
    // Here you would implement the actual action logic
    alert(`Executing: ${action.label}\n\n${action.impact}`);
  };

  return (
    <>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-gray-900">Optimizations</h3>
            <p className="text-xs text-gray-600">{optimizations.length} insights found</p>
          </div>
        </div>

        {optimizations.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-emerald-600" />
            </div>
            <p className="text-gray-900 font-semibold text-lg mb-2">All Clear!</p>
            <p className="text-sm text-gray-500">All clusters operating efficiently</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
            {optimizations.map((opt, index) => (
              <button
                key={index}
                onClick={() => handleOptimizationClick(opt)}
                className={`w-full text-left rounded-xl p-4 border-2 transition-all cursor-pointer ${getColorClasses(opt.type)} hover:shadow-md`}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 ${getIconColor(opt.type)}`}>
                    {getIcon(opt.type)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-bold text-gray-900">{opt.title}</h4>
                      <span className={`px-2 py-1 rounded-lg text-xs font-bold border ${getBadgeClasses(opt.type)}`}>
                        {opt.type.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-gray-700 mb-3">{opt.description}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-900">{opt.metric}</span>
                      <span className="flex items-center gap-1 text-xs font-semibold text-blue-600">
                        View Actions
                        <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Action Modal */}
      {showActionModal && selectedOptimization && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className={`p-6 border-b-2 ${
              selectedOptimization.type === 'warning' ? 'bg-red-50 border-red-200' :
              selectedOptimization.type === 'opportunity' ? 'bg-emerald-50 border-emerald-200' :
              'bg-blue-50 border-blue-200'
            }`}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-xl ${
                    selectedOptimization.type === 'warning' ? 'bg-red-100' :
                    selectedOptimization.type === 'opportunity' ? 'bg-emerald-100' :
                    'bg-blue-100'
                  }`}>
                    <div className={getIconColor(selectedOptimization.type)}>
                      {getIcon(selectedOptimization.type)}
                    </div>
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">
                      {selectedOptimization.title}
                    </h2>
                    <p className="text-gray-700">{selectedOptimization.description}</p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <span className={`px-3 py-1 rounded-lg text-sm font-bold border ${getBadgeClasses(selectedOptimization.type)}`}>
                        {selectedOptimization.metric}
                      </span>
                      {selectedOptimization.impact.workers_needed && (
                        <span className="px-3 py-1 bg-white rounded-lg text-sm font-semibold border border-gray-300">
                          Need: {selectedOptimization.impact.workers_needed} workers
                        </span>
                      )}
                      {selectedOptimization.impact.revenue_potential && (
                        <span className="px-3 py-1 bg-white rounded-lg text-sm font-semibold border border-gray-300">
                          Potential: ₹{(selectedOptimization.impact.revenue_potential / 1000).toFixed(0)}K
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setShowActionModal(false)}
                  className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  <X className="w-6 h-6 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Modal Body - Actions */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <Info className="w-5 h-5 text-blue-600" />
                Recommended Actions
              </h3>
              <div className="space-y-4">
                {selectedOptimization.actions.map((action) => (
                  <div
                    key={action.id}
                    className={`p-5 rounded-xl border-2 ${
                      action.type === 'primary'
                        ? 'bg-blue-50 border-blue-300'
                        : 'bg-gray-50 border-gray-300'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h4 className="text-base font-bold text-gray-900 mb-1">
                          {action.label}
                        </h4>
                        <p className="text-sm text-gray-700">{action.description}</p>
                      </div>
                      {action.type === 'primary' && (
                        <span className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs font-bold">
                          RECOMMENDED
                        </span>
                      )}
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-gray-200 mb-3">
                      <div className="text-xs font-semibold text-gray-600 mb-1">
                        Expected Impact:
                      </div>
                      <div className="text-sm text-gray-900">{action.impact}</div>
                    </div>
                    <button
                      onClick={() => handleActionClick(action)}
                      className={`w-full py-3 px-4 rounded-lg font-semibold transition-all ${
                        action.type === 'primary'
                          ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg'
                          : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                      }`}
                    >
                      Execute Action
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}