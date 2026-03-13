// FarmScheduler.tsx
import React, { useState, useEffect } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import JobsPanel from './components/JobsPanel';
import CalendarPanel from './components/CalendarPanel';
import MukkadamPanel from './components/MukkadamPanel';
import AllocationModal from './components/AllocationModel';
import ProductivityWarningModal from './components/ProductivityWarning';
import { Job, Mukkadam, Allocation, ValidationResult } from './types/types';
import { API_BASE_URL } from './types/config';
import './Farm.css';
import JobDetailPanel from './components/JobDetail';

import { RefreshCw } from 'lucide-react';
import MukkadamDetailPanel from './components/MukkadamDetail';
import Dialpad from './call';
import { getFileExtension, uploadFileToS3 } from './utils/s3';
// import { ClusterInsightsResponse } from './types/insights';
type PotentialStatus = 'PARTIAL' | 'NONE';

import * as XLSX from 'xlsx';
export function formatDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

interface PotentialJob {
  date: string;      
  cropName: string;
  variety: string;
  activityId: number;
  activityName: string;
  status: PotentialStatus;
  bookedArea: number;
  unbookedArea: number;
  bookedRate: number;
  clusterRate: number;
  farmerId: string;
  farmerName: string;
  plotId: number;
  plotName: string;
  potentialRevenue: number; // calculated as unbookedArea * max(clusterRate, bookedRate)
  jobId: string;
}

type PotentialByDate = Record<string, PotentialJob[]>;
// // ─── Misc Costs Section ───────────────────────────────────

interface FarmSchedulerProps {clusterId: number;onBackToClusters: () => void;
  onOpenDialpadWithNumber: (phone: string) => void;}


// ─────────────────────────────────────────────
// Types (matching backend exactly)
// ─────────────────────────────────────────────

type ClusterInsightsResponse = {
  cluster: { id: number; name: string };
  date_range: { start: string; end: string };
  summary: {
    total_jobs: number;
    total_activities: number;
    total_area_scheduled: number;          // ✅ NEW
    total_area_allocated: number;
    total_area_completed: number;
    total_allocated_workers: number;
    effective_capacity_workers: number;
    crew_utilization_percent: number;
    slot_utilization_percent: number;
    farmer_amount: number;
    mukkadam_amount: number;
    profit: number;
    profit_per_acre: number;
    loss_allocations: number;
    dispute_count: number;
    dispute_rate_percent: number;
    avg_efficiency_score: number;
  };
  by_day: ByDayRow[];
  by_mukkadam: ByMukkadamRow[];
  by_activity: ByActivityRow[];
  mukkadam_work: MukkadamWorkEntry[];
  farmer_work: FarmerWorkEntry[];
  capacity_demand: CapacityDemandRow[];
  move_suggestions: MoveSuggestion[];
};

type ByDayRow = {
  date: string;
  total_area_scheduled: number;            // ✅ NEW
  total_area_allocated: number;
  total_area_completed: number;
  allocated_workers: number;
  effective_capacity_workers: number;
  crew_utilization_percent: number;
  slot_utilization_percent: number;
  profit: number;
  jobs_scheduled: number;
  jobs_completed: number;
  disputes: number;
};

type ByMukkadamRow = {
  mukkadam_id: string;
  name: string;
  crew_size: number;
  max_crew_capacity: number;
  allocations: number;
  allocated_workers_total: number;
  effective_capacity_workers: number;
  crew_utilization_percent: number;
  total_area_scheduled: number;            // ✅ NEW
  total_area_allocated: number;
  total_area_completed: number;
  avg_efficiency_score: number;
  profit: number;
  disputes: number;
};

type ByActivityRow = {
  activity_id: number;
  activity_name: string;
  allocations: number;
  total_area_allocated: number;
  total_area_completed: number;
  avg_farmer_rate: number;
  avg_mukkadam_rate: number;
  avg_profit_per_acre: number;
  profit: number;
  loss_allocations: number;
};

type AllocationDetail = {
  allocation_id: number;
  date: string;
  job_id: string;
  farmer_id: string;
  farmer_name: string;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  allocated_area: number;
  actual_area_completed: number;
  allocated_workers: number;
  farmer_amount: number;
  mukkadam_amount: number;
  work_status: string;
  payment_status: string;
  profit: number;
  allows_second_job: boolean;
  is_carry_forward: boolean;
  is_auto_allocated: boolean;
  is_manually_moved: boolean;
  allocation_source: 'AI' | 'H';
};

type MukkadamWorkEntry = {
  mukkadam_id: string;
  name: string;
  allocations: AllocationDetail[];
};

type FarmerAllocDetail = {
  allocation_id: number;
  date: string;
  mukkadam_id: string;
  mukkadam_name: string;
  allocated_area: number;
  allocated_workers: number;
  work_status: string;
  payment_status: string;
  profit: number;
};

type FarmerActivityEntry = {
  job_id: string;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  scheduled_date: string | null;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  allocation_status: string;
  is_manually_moved: boolean;              // ✅ NEW
  allocation_source: 'AI' | 'H';          // ✅ NEW
  allocations: FarmerAllocDetail[];
};

type FarmerWorkEntry = {
  farmer_id: string;
  farmer_name: string;
  activities: FarmerActivityEntry[];
};

type CapacityDemandRow = {
  date: string;
  capacity_workers: number;
  demand_workers: number;
  shortage_workers: number;
  is_overbooked: boolean;
};

type FlexActivity = {
  job_id: string;
  farmer_id: string;
  farmer_name: string;
  activity_id: number;
  activity_name: string;
  scheduled_date: string | null;
  remaining_area: number;
  is_manually_moved: boolean;
  suggested_target_date?: string | null;  // 👈 NEW (planning hint)
};


type MoveSuggestion = {
  overbooked_date: string;
  shortage_workers: number;
  target_date: string | null;
  free_workers_on_target: number;
  can_fully_move: boolean;
  flexible_activities: FlexActivity[];
};

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const fmt = (n: number, d = 2) => (n ?? 0).toFixed(d);
const fmtINR = (n: number) =>
  (n < 0 ? '-₹' : '₹') + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });

function profitCls(p: number) {
  return p < 0 ? 'text-red-600 font-semibold' : p > 0 ? 'text-emerald-600 font-semibold' : 'text-slate-500';
}

function statusBadge(s: string) {
  const v = (s || '').toLowerCase();
  if (v === 'completed' || v === 'done') return 'bg-emerald-100 text-emerald-700';
  if (v === 'in_progress') return 'bg-blue-100 text-blue-700';
  if (v === 'fully_allocated') return 'bg-emerald-100 text-emerald-700';
  if (v === 'partially_allocated') return 'bg-amber-100 text-amber-700';
  if (v === 'dispute') return 'bg-red-100 text-red-700';
  return 'bg-slate-100 text-slate-600';
}

function allocSourceBadge(source: 'AI' | 'H') {
  return source === 'H'
    ? 'bg-sky-100 text-sky-700 border-sky-200'
    : 'bg-purple-100 text-purple-700 border-purple-200';
}

// ─────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────

function useClusterInsights(
  clusterId: number | null,
  startDate: string,
  endDate: string,
  enabled: boolean,
  refreshKey?: number,
  mode: 'actual' | 'planning' = 'actual',   // 👈 NEW
) {
  const [data, setData] = useState<ClusterInsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !clusterId) { setData(null); return; }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      mode,                               // 👈 NEW
    });

    fetch(`${API_BASE_URL}/api/clusters/${clusterId}/insights/?${params.toString()}`, {
      credentials: 'include',
      signal: ctrl.signal,
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => { if (e.name !== 'AbortError') setError(e.message || 'Failed'); })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [clusterId, startDate, endDate, enabled, refreshKey, mode]);  // 👈 include mode

  return { data, loading, error };
}


// ─────────────────────────────────────────────
// Date utils
// ─────────────────────────────────────────────

function formatISODate(d: Date) { return d.toISOString().slice(0, 10); }
function addDays(d: Date, delta: number) {
  const c = new Date(d); c.setDate(c.getDate() + delta); return c;
}

// ─────────────────────────────────────────────
// KPI Card  ✅ added 'violet' + 'sub' prop
// ─────────────────────────────────────────────

function KpiCard({ label, value, sub, accent }: {
  label: string;
  value: string;
  sub?: string;
  accent?: 'green' | 'red' | 'amber' | 'blue' | 'violet';
}) {
  const cls: Record<string, string> = {
    green:  'bg-emerald-50 border-emerald-200 text-emerald-700',
    red:    'bg-red-50 border-red-200 text-red-600',
    amber:  'bg-amber-50 border-amber-200 text-amber-700',
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    violet: 'bg-violet-50 border-violet-200 text-violet-700',
  };
  const base = accent ? cls[accent] : 'bg-white border-slate-200 text-slate-800';
  return (
    <div className={`${base} border rounded-xl p-3 flex flex-col gap-1`}>
      <span className="text-[10px] uppercase tracking-widest font-medium opacity-60">{label}</span>
      <span className="text-lg font-bold leading-none">{value}</span>
      {sub && <span className="text-[11px] opacity-50">{sub}</span>}
    </div>
  );
}

// ─────────────────────────────────────────────
// Table helpers
// ─────────────────────────────────────────────

function Thead({ cols }: { cols: { label: string; right?: boolean }[] }) {
  return (
    <thead className="bg-slate-800 text-slate-200 sticky top-0">
      <tr>
        {cols.map(c => (
          <th key={c.label} className={`px-2.5 py-2 text-[11px] font-semibold whitespace-nowrap ${c.right ? 'text-right' : 'text-left'}`}>
            {c.label}
          </th>
        ))}
      </tr>
    </thead>
  );
}

// ─────────────────────────────────────────────
// Container
// ─────────────────────────────────────────────

type RangePreset = 'day' | 'week' | 'month' | 'custom';

export function ClusterInsightsContainer({ clusterId }: { clusterId: number }) {
  const [preset, setPreset] = useState<RangePreset>('week');
  const [startDate, setStartDate] = useState(formatISODate(new Date()));
  const [endDate, setEndDate] = useState(formatISODate(new Date()));

  useEffect(() => {
    const today = new Date();
    if (preset === 'day') {
      const d = formatISODate(today);
      setStartDate(d); setEndDate(d);
    } else if (preset === 'week') {
      setStartDate(formatISODate(addDays(today, -6)));
      setEndDate(formatISODate(today));
    } else if (preset === 'month') {
      setStartDate(formatISODate(new Date(today.getFullYear(), today.getMonth(), 1)));
      setEndDate(formatISODate(new Date(today.getFullYear(), today.getMonth() + 1, 0)));
    }
  }, [preset]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {(['day', 'week', 'month', 'custom'] as RangePreset[]).map(p => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${preset === p ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:border-blue-400'}`}
            >
              {p === 'day' ? 'Day' : p === 'week' ? 'Week' : p === 'month' ? 'Month' : 'Custom'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500">From</span>
          <input type="date" className="border border-slate-200 rounded-lg px-2 py-1 text-xs" value={startDate}
            onChange={e => { setPreset('custom'); setStartDate(e.target.value); }} />
          <span className="text-slate-500">To</span>
          <input type="date" className="border border-slate-200 rounded-lg px-2 py-1 text-xs" value={endDate}
            onChange={e => { setPreset('custom'); setEndDate(e.target.value); }} />
        </div>
      </div>
      <InsightsPanel clusterId={clusterId} startDate={startDate} endDate={endDate} />
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Panel
// ─────────────────────────────────────────────

interface InsightsPanelProps { clusterId: number; startDate: string; endDate: string; }

export function InsightsPanel({ clusterId, startDate, endDate }: InsightsPanelProps) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] =
    useState<'overview' | 'mukkadam' | 'farmer' | 'capacity'>('overview');

  // ❶ Actual insights (allocations) for overview/mukkadam/farmer
  const {
    data: actualData,
    loading,
    error,
  } = useClusterInsights(clusterId, startDate, endDate, true, refreshKey, 'actual');

  // ❷ Planning insights for capacity tab
const {
  data: planningData,
} = useClusterInsights(
  clusterId,
  startDate,
  endDate,
  activeTab === 'capacity',   // 👈 only fetch when tab is active
  refreshKey,
  'planning'
);
  if (loading) return (
    <div className="flex items-center justify-center h-40 gap-3 text-slate-400">
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      <span className="text-sm">Loading insights…</span>
    </div>
  );
  if (error) return <div className="text-red-500 text-sm p-6">Error: {error}</div>;
  if (!actualData) return null;

  const data = actualData;
  const { summary } = data;

  // ── Excel Export ──────────────────────────────────────────────────────────
  const handleExport = () => {
    const wb = XLSX.utils.book_new();

    // 1. Summary  ✅ added total_area_scheduled row
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Metric', 'Value'],
      ['Total Jobs', summary.total_jobs],
      ['Total Activities', summary.total_activities],
      ['Total Area Scheduled (ac)', fmt(summary.total_area_scheduled)],   // ✅ NEW
      ['Total Area Allocated (ac)', fmt(summary.total_area_allocated)],
      ['Total Area Completed (ac)', fmt(summary.total_area_completed)],
      ['Total Workers Allocated', summary.total_allocated_workers],
      ['Effective Capacity Workers', summary.effective_capacity_workers],
      ['Crew Utilization %', fmt(summary.crew_utilization_percent, 1)],
      ['Slot Utilization %', fmt(summary.slot_utilization_percent, 1)],
      ['Farmer Amount (₹)', fmt(summary.farmer_amount)],
      ['Mukkadam Amount (₹)', fmt(summary.mukkadam_amount)],
      ['Profit (₹)', fmt(summary.profit)],
      ['Profit per Acre (₹)', fmt(summary.profit_per_acre)],
      ['Loss Allocations', summary.loss_allocations],
      ['Dispute Count', summary.dispute_count],
      ['Dispute Rate %', fmt(summary.dispute_rate_percent, 1)],
      ['Avg Efficiency Score', fmt(summary.avg_efficiency_score, 1)],
    ]), 'Summary');

    // 2. By Day — ONE ROW PER ALLOCATION  ✅ added Total Sched column
    const byDayRows: any[][] = [[
      'Date', 'Cluster', 'Village', 'Farmer', 'Activity Name',
      'Total Sched (ac)',                                                   // ✅ NEW
      'Area Alloc (ac)', 'Area Done (ac)',
      'Mukkadam/Team', 'Workers', 'Capacity',
      'Crew Util %', 'Slot Util %',
      'Farmer Amount', 'Mukkadam Amount', 'Profit',
      'Jobs Sched', 'Jobs Done', 'Disputes', 'Allocation as per',
    ]];

    const dayMap: Record<string, ByDayRow> = {};
    data.by_day.forEach(d => { dayMap[d.date] = d; });

    const allAllocs: (AllocationDetail & { mukkadam_name: string })[] = [];
    data.mukkadam_work.forEach(mw => {
      mw.allocations.forEach(a => allAllocs.push({ ...a, mukkadam_name: mw.name }));
    });
    allAllocs.sort((a, b) => a.date.localeCompare(b.date));

    allAllocs.forEach(a => {
      const day = dayMap[a.date];
      byDayRows.push([
        a.date,
        data.cluster.name,
        '',
        a.farmer_name,
        a.activity_name,
        day ? fmt(day.total_area_scheduled) : '',                           // ✅ NEW
        fmt(a.allocated_area),
        fmt(a.actual_area_completed),
        a.mukkadam_name,
        day?.allocated_workers ?? '',
        day?.effective_capacity_workers ?? '',
        day ? fmt(day.crew_utilization_percent, 1) : '',
        day ? fmt(day.slot_utilization_percent, 1) : '',
        fmt(a.farmer_amount),
        fmt(a.mukkadam_amount),
        fmt(a.profit),
        day?.jobs_scheduled ?? '',
        day?.jobs_completed ?? '',
        day?.disputes ?? '',
        a.allocation_source,
      ]);
    });

    if (allAllocs.length === 0) {
      data.by_day.forEach(d => {
        byDayRows.push([
          d.date, data.cluster.name, '', '', '',
          fmt(d.total_area_scheduled),                                       // ✅ NEW
          fmt(d.total_area_allocated), fmt(d.total_area_completed), '',
          d.allocated_workers, d.effective_capacity_workers,
          fmt(d.crew_utilization_percent, 1), fmt(d.slot_utilization_percent, 1),
          '', '', fmt(d.profit),
          d.jobs_scheduled, d.jobs_completed, d.disputes, '',
        ]);
      });
    }

    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(byDayRows), 'By Day');

    // 3. By Mukkadam  ✅ added Total Sched column
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Mukkadam ID', 'Name', 'Crew Size', 'Allocations', 'Workers Total',
       'Capacity', 'Util %', 'Total Sched', 'Area Alloc', 'Area Done',     // ✅ NEW col
       'Eff Score', 'Profit', 'Disputes'],
      ...data.by_mukkadam.map(m => [
        m.mukkadam_id, m.name, m.crew_size, m.allocations,
        m.allocated_workers_total, m.effective_capacity_workers,
        fmt(m.crew_utilization_percent, 1),
        fmt(m.total_area_scheduled),                                         // ✅ NEW
        fmt(m.total_area_allocated), fmt(m.total_area_completed),
        fmt(m.avg_efficiency_score, 1), fmt(m.profit), m.disputes,
      ]),
    ]), 'By Mukkadam');

    // 4. By Activity
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Activity', 'Allocations', 'Area Alloc', 'Area Done', 'Avg Farmer Rate', 'Avg Mukkadam Rate', 'Profit/ac', 'Profit', 'Loss Alloc'],
      ...data.by_activity.map(a => [
        a.activity_name, a.allocations,
        fmt(a.total_area_allocated), fmt(a.total_area_completed),
        fmt(a.avg_farmer_rate), fmt(a.avg_mukkadam_rate),
        fmt(a.avg_profit_per_acre), fmt(a.profit), a.loss_allocations,
      ]),
    ]), 'By Activity');

    // 5. Mukkadam Work Detail
    const mukRows: any[][] = [[
      'Mukkadam ID', 'Mukkadam Name', 'Date', 'Job ID', 'Farmer', 'Plot',
      'Activity', 'Area Alloc', 'Area Done', 'Workers', 'Farmer ₹', 'Mukkadam ₹',
      'Profit', 'Work Status', 'Payment Status', '2nd Job', 'Carry Fwd', 'Alloc As',
    ]];
    data.mukkadam_work.forEach(mw =>
      mw.allocations.forEach(a => mukRows.push([
        mw.mukkadam_id, mw.name, a.date, a.job_id, a.farmer_name, a.plot_name || '',
        a.activity_name, fmt(a.allocated_area), fmt(a.actual_area_completed),
        a.allocated_workers, fmt(a.farmer_amount), fmt(a.mukkadam_amount),
        fmt(a.profit), a.work_status, a.payment_status,
        a.allows_second_job ? 'Yes' : 'No',
        a.is_carry_forward ? 'Yes' : 'No',
        a.allocation_source,
      ])),
    );
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(mukRows), 'Mukkadam Work');

    // 6. Farmer Work Detail  ✅ added Alloc As column
    const farmerRows: any[][] = [[
      'Farmer ID', 'Farmer Name', 'Job ID', 'Plot', 'Activity', 'Sched Date',
      'Total Area', 'Alloc Area', 'Remain Area', 'Status', 'Alloc As',     // ✅ NEW col
      'Mukkadam', 'Alloc Date', 'Alloc Area', 'Workers',
    ]];
    data.farmer_work.forEach(fw =>
      fw.activities.forEach(act => {
        if (act.allocations.length === 0) {
          farmerRows.push([
            fw.farmer_id, fw.farmer_name, act.job_id, act.plot_name || '',
            act.activity_name, act.scheduled_date || '',
            fmt(act.total_area), fmt(act.allocated_area), fmt(act.remaining_area),
            act.allocation_status, act.allocation_source,                    // ✅ NEW
            'NOT ALLOCATED', '', '', '',
          ]);
        } else {
          act.allocations.forEach(al => farmerRows.push([
            fw.farmer_id, fw.farmer_name, act.job_id, act.plot_name || '',
            act.activity_name, act.scheduled_date || '',
            fmt(act.total_area), fmt(act.allocated_area), fmt(act.remaining_area),
            act.allocation_status, act.allocation_source,                    // ✅ NEW
            al.mukkadam_name, al.date, fmt(al.allocated_area), al.allocated_workers,
          ]));
        }
      }),
    );
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(farmerRows), 'Farmer Work');

    // 7. Capacity Demand
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Date', 'Capacity', 'Demand', 'Shortage', 'Overbooked'],
      ...data.capacity_demand.map(cd => [
        cd.date, cd.capacity_workers, cd.demand_workers,
        cd.shortage_workers, cd.is_overbooked ? 'YES' : 'No',
      ]),
    ]), 'Capacity Demand');

    XLSX.writeFile(wb, `Cluster_${data.cluster.name}_Insights_${data.date_range.start}_to_${data.date_range.end}.xlsx`);
  };

  const tabs = [
    { key: 'overview',  label: '📊 Overview' },
    { key: 'mukkadam', label: '👷 Teams' },
    { key: 'farmer',   label: '🧑‍🌾 Farmers' },
    { key: 'capacity', label: '⚡ Capacity & Smart Moves' },
  ];

  return (
    <div className="bg-slate-50 min-h-screen font-sans">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-5 py-4 flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">
            📊 {data.cluster.name} Insights
          </h2>
          <p className="text-xs text-slate-400">{data.date_range.start} → {data.date_range.end}</p>
        </div>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 transition-colors flex items-center gap-2"
        >
          ↓ Export to Excel
        </button>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* ── KPI Strip  ✅ 7 cards, Total Acres first in violet ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          <KpiCard label="Total Acres"  value={`${fmt(summary.total_area_scheduled, 1)} ac`} accent="violet" />
          <KpiCard label="Area Alloc"   value={`${fmt(summary.total_area_allocated, 1)} ac`} accent="blue" />
          <KpiCard label="Area Done"    value={`${fmt(summary.total_area_completed, 1)} ac`} accent="green" />
          <KpiCard
            label="Crew Util"
            value={`${fmt(summary.crew_utilization_percent, 1)}%`}
            accent={summary.crew_utilization_percent > 100 ? 'red' : summary.crew_utilization_percent > 75 ? 'amber' : 'green'}
          />
          <KpiCard label="Profit"     value={fmtINR(summary.profit)} accent={summary.profit < 0 ? 'red' : 'green'}
                   sub={`${fmtINR(summary.profit_per_acre)}/ac`} />
          <KpiCard label="Farmer ₹"  value={fmtINR(summary.farmer_amount)} />
          <KpiCard
            label="Disputes"
            value={`${summary.dispute_count} (${fmt(summary.dispute_rate_percent, 1)}%)`}
            accent={summary.dispute_rate_percent > 5 ? 'red' : 'green'}
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 bg-white rounded-t-xl px-2 pt-2 overflow-x-auto">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as any)}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg whitespace-nowrap transition-colors ${activeTab === t.key ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab Body */}
        <div className="bg-white rounded-b-xl rounded-tr-xl border border-slate-200 p-4">
          {activeTab === 'overview'  && <OverviewTab data={data} />}
          {activeTab === 'mukkadam' && <MukkadamTab data={data} />}
          {activeTab === 'farmer'   && <FarmerTab data={data} />}
          
{activeTab === 'capacity' && (
  <CapacityTab
    data={planningData || actualData}   // 👈 use planningData, fallback to actual
    clusterId={clusterId}
    onMoved={() => setRefreshKey(k => k + 1)}
  />
)}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Overview Tab
// ─────────────────────────────────────────────

function OverviewTab({ data }: { data: ClusterInsightsResponse }) {
  const [expandedDate, setExpandedDate] = useState<string | null>(null);

  const allocByDate: Record<string, (AllocationDetail & { mukkadam_name: string })[]> = {};
  data.mukkadam_work.forEach(mw => {
    mw.allocations.forEach(a => {
      if (!allocByDate[a.date]) allocByDate[a.date] = [];
      allocByDate[a.date].push({ ...a, mukkadam_name: mw.name });
    });
  });

  const dayMap: Record<string, ByDayRow> = {};
  data.by_day.forEach(d => { dayMap[d.date] = d; });

  return (
    <div className="space-y-6">
      {/* ── By Day ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-bold text-slate-700">Daily Breakdown</h3>
          <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
            Click a date row to expand all allocations for that day
          </span>
        </div>

        <div className="space-y-1.5">
          {data.by_day.map(d => {
            const allocs = allocByDate[d.date] || [];
            const isOpen = expandedDate === d.date;

            return (
              <div key={d.date} className="border border-slate-200 rounded-xl overflow-hidden">
                <button
                  className="w-full flex items-center gap-0 hover:bg-slate-50 transition-colors text-left"
                  onClick={() => setExpandedDate(prev => prev === d.date ? null : d.date)}
                >
                  <div className="w-28 shrink-0 px-3 py-3 border-r border-slate-100">
                    <div className="text-xs font-bold text-slate-700">{d.date}</div>
                    <div className="text-[10px] text-slate-400">
                      {new Date(d.date).toLocaleDateString('en-IN', { weekday: 'short' })}
                    </div>
                  </div>

                  <div className="flex flex-wrap flex-1 divide-x divide-slate-100">
                    {/* ✅ Total Acres column added first in violet */}
                    {[
                      { label: 'Total Acres', value: `${d.total_area_scheduled.toFixed(1)} ac`, cls: 'text-violet-600 font-bold' },
                      { label: 'Area Alloc',  value: `${d.total_area_allocated.toFixed(1)} ac`,  cls: 'text-blue-600' },
                      { label: 'Area Done',   value: `${d.total_area_completed.toFixed(1)} ac`,  cls: 'text-emerald-600' },
                      { label: 'Workers',     value: `${d.allocated_workers}/${d.effective_capacity_workers}`, cls: 'text-slate-700' },
                      { label: 'Crew Util',   value: `${d.crew_utilization_percent.toFixed(1)}%`, cls: d.crew_utilization_percent > 100 ? 'text-red-600 font-bold' : 'text-slate-700' },
                      { label: 'Slot Util',   value: `${d.slot_utilization_percent.toFixed(1)}%`, cls: 'text-slate-700' },
                      { label: 'Profit',      value: fmtINR(d.profit), cls: d.profit < 0 ? 'text-red-600 font-bold' : 'text-emerald-600 font-bold' },
                      { label: 'Jobs S/D',    value: `${d.jobs_scheduled}/${d.jobs_completed}`, cls: 'text-slate-600' },
                      { label: 'Disputes',    value: String(d.disputes), cls: d.disputes > 0 ? 'text-red-500 font-bold' : 'text-slate-400' },
                      { label: 'Allocs',      value: String(allocs.length), cls: 'text-indigo-600' },
                    ].map(({ label, value, cls }) => (
                      <div key={label} className="px-3 py-2 min-w-[80px]">
                        <div className="text-[9px] text-slate-400 uppercase tracking-wide">{label}</div>
                        <div className={`text-[11px] font-semibold ${cls}`}>{value}</div>
                      </div>
                    ))}
                  </div>

                  <div className="px-3 text-slate-400 text-xs">{isOpen ? '▲' : '▼'}</div>
                </button>

                {isOpen && (
                  <div className="border-t border-slate-100 overflow-x-auto">
                    {allocs.length === 0 ? (
                      <div className="px-4 py-4 text-sm text-slate-400">No allocations recorded for this date.</div>
                    ) : (
                      <table className="min-w-full text-[11px]">
                        <Thead cols={[
                          { label: 'Farmer' }, { label: 'Activity' }, { label: 'Plot' },
                          { label: 'Mukkadam / Team' },
                          { label: 'Area Alloc', right: true }, { label: 'Area Done', right: true },
                          { label: 'Workers', right: true },
                          { label: 'Farmer ₹', right: true }, { label: 'Mukkadam ₹', right: true },
                          { label: 'Profit', right: true },
                          { label: 'Work Status' }, { label: 'Payment' },
                          { label: 'Alloc As' }, { label: 'Tags' },
                        ]} />
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {allocs.map((a, i) => (
                            <tr key={i} className="hover:bg-slate-50 transition-colors">
                              <td className="px-2.5 py-2 font-medium text-slate-700">{a.farmer_name}</td>
                              <td className="px-2.5 py-2 text-slate-700">{a.activity_name}</td>
                              <td className="px-2.5 py-2 text-slate-500">{a.plot_name || '—'}</td>
                              <td className="px-2.5 py-2 text-violet-700 font-medium">{a.mukkadam_name}</td>
                              <td className="px-2.5 py-2 text-right font-medium text-blue-600">{a.allocated_area.toFixed(2)} ac</td>
                              <td className="px-2.5 py-2 text-right text-emerald-600">{a.actual_area_completed.toFixed(2)} ac</td>
                              <td className="px-2.5 py-2 text-right">{a.allocated_workers}</td>
                              <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(a.farmer_amount)}</td>
                              <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(a.mukkadam_amount)}</td>
                              <td className={`px-2.5 py-2 text-right ${profitCls(a.profit)}`}>{fmtINR(a.profit)}</td>
                              <td className="px-2.5 py-2">
                                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(a.work_status)}`}>{a.work_status}</span>
                              </td>
                              <td className="px-2.5 py-2">
                                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(a.payment_status)}`}>{a.payment_status}</span>
                              </td>
                              <td className="px-2.5 py-2">
                                <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-bold ${allocSourceBadge(a.allocation_source)}`}>
                                  {a.allocation_source}
                                </span>
                              </td>
                              <td className="px-2.5 py-2">
                                <div className="flex gap-1 flex-wrap">
                                  {a.allows_second_job && <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[9px] rounded font-medium">2nd</span>}
                                  {a.is_carry_forward   && <span className="px-1.5 py-0.5 bg-orange-100 text-orange-700 text-[9px] rounded font-medium">CF</span>}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot className="bg-slate-50 border-t-2 border-slate-300">
                          <tr>
                            <td className="px-2.5 py-2 font-bold text-slate-700" colSpan={4}>Day Total</td>
                            <td className="px-2.5 py-2 text-right font-bold text-blue-600">
                              {allocs.reduce((s, a) => s + a.allocated_area, 0).toFixed(2)} ac
                            </td>
                            <td className="px-2.5 py-2 text-right font-bold text-emerald-600">
                              {allocs.reduce((s, a) => s + a.actual_area_completed, 0).toFixed(2)} ac
                            </td>
                            <td className="px-2.5 py-2 text-right font-bold">
                              {allocs.reduce((s, a) => s + a.allocated_workers, 0)}
                            </td>
                            <td colSpan={2} />
                            <td className={`px-2.5 py-2 text-right font-bold ${profitCls(allocs.reduce((s, a) => s + a.profit, 0))}`}>
                              {fmtINR(allocs.reduce((s, a) => s + a.profit, 0))}
                            </td>
                            <td colSpan={4} />
                          </tr>
                        </tfoot>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── By Activity ── */}
      <div>
        <h3 className="text-sm font-bold text-slate-700 mb-3">By Activity</h3>
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full text-[11px]">
            <Thead cols={[
              { label: 'Activity' }, { label: 'Allocations', right: true },
              { label: 'Area Alloc', right: true }, { label: 'Area Done', right: true },
              { label: 'Farmer Rate/ac', right: true }, { label: 'Mukkadam Rate/ac', right: true },
              { label: 'Profit/ac', right: true }, { label: 'Profit', right: true },
              { label: 'Loss Allocs', right: true },
            ]} />
            <tbody className="divide-y divide-slate-100 bg-white">
              {data.by_activity.map(a => (
                <tr key={a.activity_id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 font-semibold text-slate-700">{a.activity_name}</td>
                  <td className="px-3 py-2 text-right">{a.allocations}</td>
                  <td className="px-3 py-2 text-right text-blue-600 font-medium">{a.total_area_allocated.toFixed(1)} ac</td>
                  <td className="px-3 py-2 text-right text-emerald-600">{a.total_area_completed.toFixed(1)} ac</td>
                  <td className="px-3 py-2 text-right">{fmtINR(a.avg_farmer_rate)}</td>
                  <td className="px-3 py-2 text-right">{fmtINR(a.avg_mukkadam_rate)}</td>
                  <td className={`px-3 py-2 text-right ${profitCls(a.avg_profit_per_acre)}`}>{fmtINR(a.avg_profit_per_acre)}</td>
                  <td className={`px-3 py-2 text-right ${profitCls(a.profit)}`}>{fmtINR(a.profit)}</td>
                  <td className="px-3 py-2 text-right">
                    {a.loss_allocations > 0 ? <span className="text-red-500 font-bold">{a.loss_allocations}</span> : <span className="text-slate-300">0</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Mukkadam Tab  ✅ added Total Acres column
// ─────────────────────────────────────────────

function MukkadamTab({ data }: { data: ClusterInsightsResponse }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-slate-700">Team Workload & Performance</h3>

      <div className="overflow-x-auto rounded-xl border border-slate-200 mb-4">
        <table className="min-w-full text-[11px]">
          <Thead cols={[
            { label: 'Mukkadam' }, { label: 'Crew Size', right: true },
            { label: 'Allocations', right: true },
            { label: 'Total Acres', right: true },          // ✅ NEW
            { label: 'Area Alloc', right: true }, { label: 'Area Done', right: true },
            { label: 'Workers', right: true }, { label: 'Capacity', right: true },
            { label: 'Crew Util %', right: true }, { label: 'Eff Score', right: true },
            { label: 'Profit', right: true }, { label: 'Disputes', right: true },
          ]} />
          <tbody className="divide-y divide-slate-100 bg-white">
            {data.by_mukkadam.map(m => (
              <tr key={m.mukkadam_id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-semibold text-slate-700">{m.name}</td>
                <td className="px-3 py-2 text-right">{m.crew_size}</td>
                <td className="px-3 py-2 text-right">{m.allocations}</td>
                <td className="px-3 py-2 text-right font-bold text-violet-600">{m.total_area_scheduled.toFixed(1)} ac</td>  {/* ✅ NEW */}
                <td className="px-3 py-2 text-right text-blue-600 font-medium">{m.total_area_allocated.toFixed(1)} ac</td>
                <td className="px-3 py-2 text-right text-emerald-600">{m.total_area_completed.toFixed(1)} ac</td>
                <td className="px-3 py-2 text-right">{m.allocated_workers_total}</td>
                <td className="px-3 py-2 text-right">{m.effective_capacity_workers}</td>
                <td className={`px-3 py-2 text-right font-semibold ${m.crew_utilization_percent > 100 ? 'text-red-600' : m.crew_utilization_percent > 75 ? 'text-amber-600' : 'text-emerald-600'}`}>
                  {m.crew_utilization_percent.toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right">{m.avg_efficiency_score.toFixed(1)}</td>
                <td className={`px-3 py-2 text-right ${profitCls(m.profit)}`}>{fmtINR(m.profit)}</td>
                <td className="px-3 py-2 text-right">{m.disputes > 0 ? <span className="text-red-500 font-bold">{m.disputes}</span> : <span className="text-slate-300">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="text-sm font-bold text-slate-700">Allocation Detail per Mukkadam</h3>
      <div className="space-y-2">
        {data.mukkadam_work.map(mw => (
          <div key={mw.mukkadam_id} className="border border-slate-200 rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandedId(expandedId === mw.mukkadam_id ? null : mw.mukkadam_id)}
              className="w-full px-4 py-3 flex justify-between items-center hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-bold">
                  {mw.name.charAt(0).toUpperCase()}
                </div>
                <span className="font-semibold text-slate-800 text-sm">{mw.name}</span>
                <span className="text-xs text-slate-400">{mw.allocations.length} allocations</span>
              </div>
              <span className="text-slate-400 text-xs">{expandedId === mw.mukkadam_id ? '▲' : '▼'}</span>
            </button>

            {expandedId === mw.mukkadam_id && (
              <div className="border-t border-slate-100 overflow-x-auto">
                <table className="min-w-full text-[11px]">
                  <Thead cols={[
                    { label: 'Date' }, { label: 'Farmer' }, { label: 'Plot' }, { label: 'Activity' },
                    { label: 'Area Alloc', right: true }, { label: 'Area Done', right: true },
                    { label: 'Workers', right: true },
                    { label: 'Farmer ₹', right: true }, { label: 'Mukkadam ₹', right: true },
                    { label: 'Profit', right: true },
                    { label: 'Work Status' }, { label: 'Payment' }, { label: 'Alloc As' }, { label: 'Tags' },
                  ]} />
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {mw.allocations.map(a => (
                      <tr key={a.allocation_id} className="hover:bg-slate-50">
                        <td className="px-2.5 py-2 font-medium text-slate-700 whitespace-nowrap">{a.date}</td>
                        <td className="px-2.5 py-2 text-slate-700">{a.farmer_name}</td>
                        <td className="px-2.5 py-2 text-slate-500">{a.plot_name || '—'}</td>
                        <td className="px-2.5 py-2 text-slate-700">{a.activity_name}</td>
                        <td className="px-2.5 py-2 text-right text-blue-600 font-medium">{a.allocated_area.toFixed(2)} ac</td>
                        <td className="px-2.5 py-2 text-right text-emerald-600">{a.actual_area_completed.toFixed(2)} ac</td>
                        <td className="px-2.5 py-2 text-right">{a.allocated_workers}</td>
                        <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(a.farmer_amount)}</td>
                        <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(a.mukkadam_amount)}</td>
                        <td className={`px-2.5 py-2 text-right ${profitCls(a.profit)}`}>{fmtINR(a.profit)}</td>
                        <td className="px-2.5 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(a.work_status)}`}>{a.work_status}</span>
                        </td>
                        <td className="px-2.5 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(a.payment_status)}`}>{a.payment_status}</span>
                        </td>
                        <td className="px-2.5 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-bold ${allocSourceBadge(a.allocation_source)}`}>
                            {a.allocation_source}
                          </span>
                        </td>
                        <td className="px-2.5 py-2">
                          <div className="flex gap-1">
                            {a.allows_second_job && <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[9px] rounded font-medium">2nd</span>}
                            {a.is_carry_forward   && <span className="px-1.5 py-0.5 bg-orange-100 text-orange-700 text-[9px] rounded font-medium">CF</span>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Farmer Tab  ✅ added AI/H badge + area stats in header
// ─────────────────────────────────────────────

function FarmerTab({ data }: { data: ClusterInsightsResponse }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-slate-700">Farmer Work & Allocation Status</h3>
      <div className="space-y-2">
        {data.farmer_work.map(fw => {
          const unalloc = fw.activities.filter(a => a.remaining_area > 0).length;
          const isOpen = expandedId === fw.farmer_id;

          const totalArea  = fw.activities.reduce((s, a) => s + a.total_area, 0);
          const totalAlloc = fw.activities.reduce((s, a) => s + a.allocated_area, 0);
          const totalRem   = fw.activities.reduce((s, a) => s + a.remaining_area, 0);
          const totalProfit = fw.activities.reduce((s, a) =>
            s + a.allocations.reduce((ss, al) => ss + al.profit, 0), 0);

          return (
            <div key={fw.farmer_id} className="border border-slate-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedId(isOpen ? null : fw.farmer_id)}
                className="w-full px-4 py-3 flex justify-between items-center hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="w-8 h-8 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-xs font-bold">
                    {fw.farmer_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="text-left">
                    <div className="font-semibold text-slate-800 text-sm">{fw.farmer_name}</div>
                    {/* ✅ area summary in subtitle */}
                    <div className="flex flex-wrap items-center gap-2 text-[11px] mt-0.5">
                      <span className="text-slate-400">{fw.activities.length} activities</span>
                      <span className="text-slate-300">·</span>
                      <span className="text-slate-600">{totalArea.toFixed(1)} ac total</span>
                      <span className="text-slate-300">·</span>
                      <span className="text-blue-600 font-semibold">{totalAlloc.toFixed(1)} ac alloc</span>
                      {totalRem > 0 && (
                        <>
                          <span className="text-slate-300">·</span>
                          <span className="text-amber-600 font-semibold">{totalRem.toFixed(1)} ac pending</span>
                        </>
                      )}
                    </div>
                  </div>
                  {unalloc > 0 && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 text-[10px] rounded-full font-medium">
                      {unalloc} unallocated
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <div className={`text-sm font-bold ${profitCls(totalProfit)}`}>{fmtINR(totalProfit)}</div>
                  <span className="text-slate-400 text-xs">{isOpen ? '▲' : '▼'}</span>
                </div>
              </button>

              {isOpen && (
                <div className="border-t border-slate-100 p-4 space-y-3 bg-slate-50/50">
                  {fw.activities.map(act => (
                    <div key={`${act.job_id}-${act.activity_id}`} className="border border-slate-200 rounded-lg bg-white overflow-hidden">
                      {/* Activity header */}
                      <div className="px-3 py-2.5 bg-slate-50 flex flex-wrap items-center justify-between gap-2 border-b border-slate-100">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-slate-800">{act.activity_name}</span>
                          <span className="text-[11px] text-slate-400">{act.plot_name || 'No plot'} · {act.scheduled_date || 'Not scheduled'}</span>
                          {/* ✅ AI/H badge per activity */}
                          <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-bold ${allocSourceBadge(act.allocation_source)}`}>
                            {act.allocation_source}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="text-slate-500">Total: <strong className="text-slate-700">{act.total_area.toFixed(1)} ac</strong></span>
                          <span className="text-blue-600">Alloc: <strong>{act.allocated_area.toFixed(1)} ac</strong></span>
                          <span className={act.remaining_area > 0 ? 'text-amber-600 font-bold' : 'text-emerald-600'}>
                            Rem: {act.remaining_area.toFixed(1)} ac
                          </span>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(act.allocation_status)}`}>
                            {act.allocation_status}
                          </span>
                        </div>
                      </div>

                      {act.allocations.length === 0 ? (
                        <div className="px-3 py-3 text-xs text-red-500 bg-red-50 flex items-center gap-1">
                          ⚠️ Not allocated yet
                        </div>
                      ) : (
                        <table className="min-w-full text-[11px]">
                          <Thead cols={[
                            { label: 'Alloc Date' }, { label: 'Mukkadam' },
                            { label: 'Area Alloc', right: true }, { label: 'Workers', right: true },
                            { label: 'Work Status' }, { label: 'Payment' }, { label: 'Profit', right: true },
                          ]} />
                          <tbody className="divide-y divide-slate-100">
                            {act.allocations.map(al => (
                              <tr key={al.allocation_id} className="hover:bg-slate-50">
                                <td className="px-2.5 py-2 font-medium text-slate-700">{al.date}</td>
                                <td className="px-2.5 py-2 text-violet-700 font-medium">{al.mukkadam_name}</td>
                                <td className="px-2.5 py-2 text-right text-blue-600 font-medium">{al.allocated_area.toFixed(2)} ac</td>
                                <td className="px-2.5 py-2 text-right">{al.allocated_workers}</td>
                                <td className="px-2.5 py-2">
                                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(al.work_status)}`}>{al.work_status}</span>
                                </td>
                                <td className="px-2.5 py-2">
                                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge(al.payment_status)}`}>{al.payment_status}</span>
                                </td>
                                <td className={`px-2.5 py-2 text-right ${profitCls(al.profit)}`}>{fmtINR(al.profit)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Capacity Tab  ✅ fixed handleMove (credentials), full smart moves UI
// ─────────────────────────────────────────────

function CapacityTab({ data, clusterId, onMoved }: {
  data: ClusterInsightsResponse;
  clusterId: number;
  onMoved?: () => void;
}) {
  const [view, setView] = useState<'overview' | 'moves'>('moves');
  const [expandedDate, setExpandedDate] = useState<string | null>(null);
  const [movingKey, setMovingKey] = useState<string | null>(null);
  const [movedKeys, setMovedKeys] = useState<Set<string>>(new Set());
  const [customTarget, setCustomTarget] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const overbooked = data.capacity_demand.filter(d => d.is_overbooked);
  const totalShortage = overbooked.reduce((s, d) => s + d.shortage_workers, 0);

  const freeByDate: Record<string, number> = {};
  data.capacity_demand.forEach(d => {
    const free = d.capacity_workers - d.demand_workers;
    if (free > 0) freeByDate[d.date] = free;
  });
  const freeDates = Object.keys(freeByDate).sort();

  const maxWorkers = Math.max(
    ...data.capacity_demand.map(d => Math.max(d.capacity_workers, d.demand_workers)), 1,
  );

  const bar = (val: number, max: number, color: string) => (
    <div className="w-full bg-slate-100 rounded-full h-1.5 mt-0.5">
      <div className={`h-1.5 rounded-full ${color}`}
           style={{ width: `${Math.min((val / Math.max(max, 1)) * 100, 100)}%` }} />
    </div>
  );

  const handleMove = async (act: FlexActivity, fromDate: string, toDate: string) => {
    const key = `${act.job_id}-${act.activity_id}`;
    if (!toDate) { showToast('Please select a target date first.', false); return; }
    setMovingKey(key);
    try {
      const res = await fetch(`${API_BASE_URL}/api/job-activities/${act.activity_id}/move/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',                              // ✅ FIXED: was missing
        body: JSON.stringify({
          scheduled_date: toDate,
          is_manually_moved: true,
          move_reason: `Moved via Smart Moves: capacity shortage on ${fromDate}`,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = new Set(movedKeys);
      updated.add(key);
      setMovedKeys(updated);
      showToast(`✅ Moved ${act.activity_name} (${act.farmer_name}) → ${toDate}`, true);
      onMoved?.();
    } catch (e: any) {
      showToast(`❌ Failed to move: ${e.message}`, false);
    } finally {
      setMovingKey(null);
    }
  };

  return (
    <div className="space-y-4 relative">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-semibold transition-all ${toast.ok ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <KpiCard label="Total Days"           value={String(data.capacity_demand.length)} />
        <KpiCard label="Overbooked Days"      value={String(overbooked.length)} accent={overbooked.length > 0 ? 'red' : 'green'} />
        <KpiCard label="Worker Shortage"      value={String(totalShortage)} accent={totalShortage > 0 ? 'red' : 'green'} />
        <KpiCard label="Days with Free Slots" value={String(freeDates.length)} accent="blue" />
      </div>

      {/* Sub-tab */}
      <div className="flex gap-1 border-b border-slate-200">
        {(['overview', 'moves'] as const).map(key => (
          <button key={key} onClick={() => setView(key)}
            className={`px-3 py-2 text-xs font-semibold rounded-t-lg transition-colors ${view === key ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`}>
            {key === 'overview' ? '📊 All Days' : `🔀 Smart Moves${overbooked.length > 0 ? ` (${overbooked.length})` : ''}`}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {view === 'overview' && (
        <div className="space-y-1.5">
          {data.capacity_demand.map(cd => {
            const utilPct = cd.capacity_workers > 0 ? (cd.demand_workers / cd.capacity_workers) * 100 : 0;
            const isOver  = cd.is_overbooked;
            const free    = cd.capacity_workers - cd.demand_workers;
            const dow     = new Date(cd.date).toLocaleDateString('en-IN', { weekday: 'short' });
            return (
              <div key={cd.date}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border text-[11px] ${isOver ? 'bg-red-50 border-red-200' : free > 0 ? 'bg-white border-slate-100 hover:bg-emerald-50/40' : 'bg-slate-50 border-slate-100'}`}>
                <div className="w-24 shrink-0">
                  <div className="font-bold text-slate-700">{cd.date}</div>
                  <div className="text-[10px] text-slate-400">{dow}</div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[10px] text-slate-400 w-14 shrink-0">Capacity</span>
                    <div className="flex-1">{bar(cd.capacity_workers, maxWorkers, 'bg-blue-400')}</div>
                    <span className="text-[11px] font-semibold text-blue-600 w-8 text-right">{cd.capacity_workers}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-400 w-14 shrink-0">Demand</span>
                    <div className="flex-1">{bar(cd.demand_workers, maxWorkers, isOver ? 'bg-red-500' : 'bg-emerald-400')}</div>
                    <span className={`text-[11px] font-semibold w-8 text-right ${isOver ? 'text-red-600' : 'text-emerald-600'}`}>{cd.demand_workers}</span>
                  </div>
                </div>
                <div className="w-14 text-center shrink-0">
                  <div className={`text-xs font-bold ${utilPct > 100 ? 'text-red-600' : utilPct > 80 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {utilPct.toFixed(0)}%
                  </div>
                  <div className="text-[9px] text-slate-400">util</div>
                </div>
                <div className="w-28 shrink-0 text-right">
                  {isOver
                    ? <span className="inline-block px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-[10px] font-bold">⚠ -{cd.shortage_workers} short</span>
                    : free > 0
                      ? <span className="inline-block px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-medium">+{free} free</span>
                      : <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-400 rounded-full text-[10px]">exact</span>
                  }
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── SMART MOVES ── */}
      {view === 'moves' && (
        <div className="space-y-3">
          {overbooked.length === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <div className="text-5xl mb-3">✅</div>
              <p className="text-sm font-semibold text-slate-600">All days are within capacity</p>
              <p className="text-xs mt-1">No moves needed — great planning!</p>
            </div>
          ) : (
            <>
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex flex-wrap gap-3 items-center text-xs">
                <span className="text-red-700 font-bold text-sm">⚠️ {overbooked.length} overbooked {overbooked.length === 1 ? 'day' : 'days'}</span>
                <span className="text-red-600">Total shortage: <strong>{totalShortage} workers</strong></span>
                <span className="text-slate-300">|</span>
                <span className="text-emerald-700">
                  {freeDates.length} days have free capacity:&nbsp;
                  <strong>{freeDates.slice(0, 4).join(', ')}{freeDates.length > 4 ? ` +${freeDates.length - 4} more` : ''}</strong>
                </span>
              </div>

              {freeDates.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-slate-500 mb-1.5">Available days to move into:</div>
                  <div className="flex flex-wrap gap-1.5">
                    {freeDates.map(d => (
                      <span key={d} className="px-2.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg text-[11px] font-semibold">
                        {d} <span className="text-emerald-500 font-normal">+{freeByDate[d]} free</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {data.move_suggestions.map(ms => {
                const isExpanded  = expandedDate === ms.overbooked_date;
                const dowOver     = new Date(ms.overbooked_date).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' });
                const dowTarget   = ms.target_date ? new Date(ms.target_date).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' }) : null;
                const movedCount  = ms.flexible_activities.filter(a => movedKeys.has(`${a.job_id}-${a.activity_id}`)).length;

                return (
                  <div key={ms.overbooked_date} className="border border-red-200 rounded-xl overflow-hidden shadow-sm">
                    <button
                      onClick={() => setExpandedDate(isExpanded ? null : ms.overbooked_date)}
                      className="w-full px-4 py-3 bg-red-50 hover:bg-red-100 transition-colors flex items-start justify-between text-left gap-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
                          <div>
                            <div className="text-xs font-extrabold text-red-700">{ms.overbooked_date}</div>
                            <div className="text-[10px] text-red-400">{dowOver}</div>
                          </div>
                        </div>
                        <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-[10px] font-bold border border-red-200">
                          -{ms.shortage_workers} workers short
                        </span>
                        {ms.can_fully_move && (
                          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-semibold">Can fully resolve</span>
                        )}
                        {movedCount > 0 && (
                          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-[10px] font-semibold">{movedCount} moved</span>
                        )}
                        {ms.target_date && (
                          <>
                            <span className="text-slate-400">→</span>
                            <div className="flex items-center gap-1.5">
                              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0" />
                              <div>
                                <div className="text-xs font-extrabold text-emerald-700">{ms.target_date}</div>
                                <div className="text-[10px] text-emerald-400">{dowTarget} · {ms.free_workers_on_target} free</div>
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                      <span className="text-slate-400 text-xs">{isExpanded ? '▲' : '▼'}</span>
                    </button>

                    {isExpanded && (
                      <div className="p-4 bg-white border-t border-red-100 space-y-3">
                        {ms.flexible_activities.length === 0 ? (
                          <p className="text-sm text-slate-400 text-center py-4">No flexible activities to move on this day.</p>
                        ) : (
                          <div className="overflow-x-auto rounded-lg border border-slate-200">
                            <table className="min-w-full text-[11px]">
                              <Thead cols={[
                                { label: 'Farmer' }, { label: 'Activity' }, { label: 'Job ID' },
                                { label: 'Rem. Area', right: true }, { label: 'Move To' }, { label: 'Action' },
                              ]} />
                              <tbody className="divide-y divide-slate-100 bg-white">
                                {ms.flexible_activities.map(act => {
                                  const key      = `${act.job_id}-${act.activity_id}`;
                                  const isMoved  = movedKeys.has(key);
                                  const isMoving = movingKey === key;
                                  const target =
  customTarget[key] ??
  act.suggested_target_date ??   // 👈 use planning suggestion first
  ms.target_date ??              // (actual-mode fallback)
  '';

                                  return (
                                    <tr key={key} className={isMoved ? 'bg-emerald-50 opacity-70' : 'hover:bg-slate-50'}>
                                      <td className="px-2.5 py-2.5 font-medium text-slate-700">{act.farmer_name}</td>
                                      <td className="px-2.5 py-2.5 text-slate-700">{act.activity_name}</td>
                                      <td className="px-2.5 py-2.5 font-mono text-blue-600">{act.job_id}</td>
                                      <td className="px-2.5 py-2.5 text-right text-amber-600 font-medium">{act.remaining_area.toFixed(2)} ac</td>
                                      <td className="px-2.5 py-2.5">
                                        {isMoved ? (
                                          <span className="text-emerald-600 font-semibold text-[11px]">✅ Moved → {target}</span>
                                        ) : (
                                          <select
                                            value={target}
                                            onChange={e => setCustomTarget(prev => ({ ...prev, [key]: e.target.value }))}
                                            className="border border-slate-200 rounded-lg px-2 py-1 text-[11px] text-slate-700 bg-white focus:ring-1 focus:ring-blue-400 outline-none"
                                          >
                                            <option value="">— pick date —</option>
                                            {freeDates.map(d => (
                                              <option key={d} value={d}>{d} (+{freeByDate[d]} free)</option>
                                            ))}
                                          </select>
                                        )}
                                      </td>
                                      <td className="px-2.5 py-2.5">
                                        {isMoved ? (
                                          <span className="text-emerald-600 text-[11px] font-semibold">Done</span>
                                        ) : (
                                          <button
                                            disabled={isMoving || !target}
                                            onClick={() => handleMove(act, ms.overbooked_date, target)}
                                            className={`px-3 py-1 rounded-lg text-[11px] font-semibold transition-colors ${isMoving ? 'bg-slate-200 text-slate-400 cursor-wait' : !target ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'}`}
                                          >
                                            {isMoving ? 'Moving…' : 'Move'}
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}


function PaymentDashboard({ clusterId }: { clusterId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'farmers' | 'mukkadams'>('farmers');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [expandedAlloc, setExpandedAlloc] = useState<number | null>(null);
// New state
const [billBuilder, setBillBuilder] = useState<{
  farmer: any;
  jobs: any[];
} | null>(null);


  // Farmer payment modal
  const [payModal, setPayModal] = useState<{
    farmerId: string; jobId: string;
    amount: number; farmerName: string;
    existingPayments?: any[];
  } | null>(null);


  // ── WEBHOOK CONFIG ──────────────────────────────────────────
const FARMER_BILL_WEBHOOK_URL = ''; // ← paste your URL here

// Farmer bill detail modal (replaces old payModal)
const [detailModal, setDetailModal] = useState<{
  farmerName: string;
  farmerId: string;
  phone: string;
  jobId: string;
  cropName: string;
  plotName: string;
  mukkadamName: string;
  mukkadamMobile: string;
  activities: any[];
  paymentHistory: any[];
  totalBilled: number;
  totalPaid: number;
  balanceDue: number;
} | null>(null);
const [webhookSending, setWebhookSending] = useState(false);
const [webhookSent, setWebhookSent] = useState(false);
  const [payAmount, setPayAmount] = useState('');
  const [payMode, setPayMode] = useState('CASH');
  const [payNotes, setPayNotes] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofUploading, setProofUploading] = useState(false);

  // Mukkadam pay loading
  const [mukkadamPaying, setMukkadamPaying] = useState<string | null>(null);

  // Mukkadam payment modal (settlement pay)
  const [mukkadamPayModal, setMukkadamPayModal] = useState<{
    mukkadamId: number; jobId: string; amount: number; name: string;
  } | null>(null);
  const [mukkadamPayMode, setMukkadamPayMode] = useState('CASH');
  const [mukkadamPayNotes, setMukkadamPayNotes] = useState('');
  const [mukkadamProofFile, setMukkadamProofFile] = useState<File | null>(null);
  const [mukkadamProofUploading, setMukkadamProofUploading] = useState(false);
  const [mukkadamPayLoading, setMukkadamPayLoading] = useState(false);

  // Weekly payment modal
const [weeklyModal, setWeeklyModal] = useState<{
  mukkadamId: number; assignmentId: number; amount: number; name: string;
  paymentDate?: string;  // ← ADD THIS
} | null>(null);

  const [weeklyMode, setWeeklyMode] = useState('CASH');
  const [weeklyNotes, setWeeklyNotes] = useState('');
  const [weeklyProofFile, setWeeklyProofFile] = useState<File | null>(null);
  const [weeklyProofUploading, setWeeklyProofUploading] = useState(false);
  const [weeklyPayLoading, setWeeklyPayLoading] = useState(false);

  // Farmer verify loading
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);

  // Dispute override state
  const [disputeOpen, setDisputeOpen] = useState<number | null>(null);
  const [disputeArea, setDisputeArea] = useState('');
  const [disputeReason, setDisputeReason] = useState('');
  const [disputeSaving, setDisputeSaving] = useState(false);

  // OTP resend + verify state
  const [otpSending, setOtpSending] = useState<number | null>(null);
  const [otpOpen, setOtpOpen] = useState<number | null>(null);
  const [otpCode, setOtpCode] = useState('');
  const [otpVerifying, setOtpVerifying] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${clusterId}/payment-dashboard/`);
      setData(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [clusterId],);

  const handleMukkadamPay = (mukkadamId: number, jobId: string, amount: number, name: string) => {
    setMukkadamPayModal({ mukkadamId, jobId, amount, name });
    setMukkadamPayMode('CASH'); setMukkadamPayNotes(''); setMukkadamProofFile(null);
  };

  const submitMukkadamPay = async () => {
    if (!mukkadamPayModal || !mukkadamProofFile) return;
    setMukkadamProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(mukkadamProofFile);
      const s3Name = `payments/mukkadam/${mukkadamPayModal.mukkadamId}/job_${mukkadamPayModal.jobId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(mukkadamProofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setMukkadamProofUploading(false); }

    setMukkadamPayLoading(true);
    const key = `${mukkadamPayModal.mukkadamId}-${mukkadamPayModal.jobId}`;
    setMukkadamPaying(key);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamPayModal.mukkadamId}/settlement/${mukkadamPayModal.jobId}/pay/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: mukkadamPayMode, notes: mukkadamPayNotes, proof_s3_key: proofS3Key }),
        }
      );
      const result = await res.json();
      if (res.ok) {
        alert(`✅ ${result.message}`);
        setMukkadamPayModal(null); setMukkadamProofFile(null);
        fetchData();
      } else { alert(`❌ ${result.error}`); }
    } finally { setMukkadamPayLoading(false); setMukkadamPaying(null); }
  };

  const handleAddWeeklyPayment = (mukkadamId: number, assignmentId: number, amount: number, name: string) => {
    setWeeklyModal({ mukkadamId, assignmentId, amount, name });
    setWeeklyMode('CASH'); setWeeklyNotes(''); setWeeklyProofFile(null);
  };

  const submitWeeklyPayment = async () => {
    if (!weeklyModal || !weeklyProofFile) return;
    setWeeklyProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(weeklyProofFile);
      const s3Name = `payments/weekly/${weeklyModal.mukkadamId}/assignment_${weeklyModal.assignmentId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(weeklyProofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setWeeklyProofUploading(false); }

    setWeeklyPayLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/weekly-payment/add/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
  assignment_id: weeklyModal.assignmentId,
  amount: weeklyModal.amount,
  payment_date: weeklyModal.paymentDate || new Date().toISOString().split('T')[0], // ← use missed date
  mode: weeklyMode,
  notes: weeklyNotes ? `${weeklyNotes} (late — was due ${weeklyModal.paymentDate})` : `Late payment — was due ${weeklyModal.paymentDate}`,
  proof_s3_key: proofS3Key,
}),
      });
      if (res.ok) {
        setWeeklyModal(null); setWeeklyProofFile(null);
        fetchData();
      } else {
        const d = await res.json();
        alert(`❌ ${d.error || 'Failed'}`);
      }
    } finally { setWeeklyPayLoading(false); }
  };

  const handleFarmerVerify = async (allocationId: number, farmerId: string, jobId: string, agreed: boolean, disputeReason?: string) => {
    if (!agreed && !disputeReason?.trim()) {
      const reason = window.prompt('Please enter dispute reason:');
      if (!reason?.trim()) return;
      disputeReason = reason;
    }
    setVerifyLoading(allocationId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmer/verify-work/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farmer_id: farmerId,
          allocation_id: allocationId,
          agreed,
          dispute_reason: disputeReason || '',
        }),
      });
      const result = await res.json();
      if (res.ok) {
        alert(agreed ? '✅ Work verified successfully' : '⚠️ Dispute recorded');
        fetchData();
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setVerifyLoading(null);
    }
  };

  const handleResolveDispute = async (allocationId: number) => {
    if (!disputeArea) return;
    setDisputeSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/resolve-dispute/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          allocation_id: allocationId,
          farmer_claimed_area: parseFloat(disputeArea),
          dispute_reason: disputeReason,
        }),
      });
      const result = await res.json();
      if (res.ok) {
        setDisputeOpen(null);
        setDisputeArea('');
        setDisputeReason('');
        fetchData();
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setDisputeSaving(false);
    }
  };

  const handleSendOtp = async (allocationId: number) => {
    setOtpSending(allocationId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/send-farmer-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocation_id: allocationId }),
      });
      const result = await res.json();
      if (res.ok) {
        alert('✅ OTP sent to farmer');
        setOtpOpen(allocationId);
        setOtpCode('');
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setOtpSending(null);
    }
  };

  const handleVerifyOtp = async (allocationId: number, farmerId: string) => {
    if (!otpCode.trim()) return;
    setOtpVerifying(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/attendance/verify-farmer-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocation_id: allocationId, otp: otpCode.trim(), farmer_id: farmerId }),
      });
      const result = await res.json();
      if (res.ok) {
        alert('✅ Farmer verified successfully');
        setOtpOpen(null);
        setOtpCode('');
        fetchData();
      } else {
        alert(`❌ ${result.error || 'Invalid OTP'}`);
      }
    } finally {
      setOtpVerifying(false);
    }
  };
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', color: '#9ca3af' }}>
      <RefreshCw size={24} className="animate-spin" style={{ color: '#14b8a6', marginRight: '10px' }} />
      Loading payment data...
    </div>
  // );

  if (!data) return null;

  const STATUS_META: Record<string, { bg: string; text: string; label: string }> = {
    paid:              { bg: '#dcfce7', text: '#16a34a', label: '✓ Paid' },
    calculated:        { bg: '#fef9c3', text: '#b45309', label: '⚠ Due' },
    no_payment_needed: { bg: '#dbeafe', text: '#1d4ed8', label: '✅ Credit' },
    payment_raised:    { bg: '#fce7f3', text: '#be185d', label: 'Raised' },
    pending:           { bg: '#f3f4f6', text: '#6b7280', label: 'Pending' },
  };


  
// Handler — add this near your other handlers (handleMukkadamPay etc.)
const handleUpdownComplete = async (mukkadamId: number, allocationId: number) => {
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/mukkadam/${mukkadamId}/updown-allocations/${allocationId}/complete/`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }
    );
    if (!res.ok) throw new Error('Failed');
    fetchData(); // your existing refresh function
  } catch {
    alert('Failed to mark complete. Please try again.');
  }
};


const BillBuilderModal = ({ farmer, jobs, onClose, onSent }: any) => {
  // All activities from all jobs, each toggleable
  const allActivities = jobs.flatMap((j: any) =>
    (j.activities || []).flatMap((act: any) =>
      (act.allocations || [{ ...act }]).map((alloc: any) => ({
        ...act, ...alloc,
        job_id:    j.job_id,
        plot_name: j.plot_name,
        crop_name: j.crop_name,
        _key: `${j.job_id}-${act.activity_id}-${alloc.allocation_id}`,
      }))
    )
  );

  const [selected, setSelected] = useState<Set<string>>(
    new Set(allActivities.map((a: any) => a._key))  // all selected by default
  );

  const toggle = (key: string) =>
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // Recalculate totals based on selected activities only
  const selectedActivities = allActivities.filter((a: any) => selected.has(a._key));
  
  const totalBilled = selectedActivities.reduce((sum: number, a: any) => {
    const area = a.admin_override_area ?? a.actual_area_done ?? a.allocated_area ?? 0;
    return sum + (Number(area) * Number(a.rate_per_acre || 0));
  }, 0);

  const totalPaid = jobs.reduce((sum: number, j: any) =>
    sum + (j.summary?.total_paid || 0), 0
  );

  const balanceDue = totalBilled - totalPaid;

  // All payment history across selected jobs
  const allPayments = jobs.flatMap((j: any) => j.payment_history || []);

  const handleSend = async () => {
    const token = localStorage.getItem('auth_token');
    const payload = {
      timestamp: new Date().toISOString(),
      auth_token: token,
      farmer: {
        id:    farmer.farmer_id,
        name:  farmer.farmer_name,
        phone: farmer.phone_number || farmer.mobile_number || '',
      },
      job: {
        // Use first selected job's info, or combined
        id:   selectedActivities[0]?.job_id || jobs[0]?.job_id,
        crop: jobs.map((j: any) => j.crop_name).join(', '),
        plot: jobs.map((j: any) => j.plot_name).join(', '),
      },
      mukkadam: {
        name:   jobs[0]?.mukkadam_name || '',
        mobile: jobs[0]?.mukkadam_mobile || '',
      },
      work_done: selectedActivities.map((a: any) => ({
  activity:      a.activity_name,
  plot_name:     a.plot_name || '',
  date:          a.allocated_date || a.scheduled_date || '',
  acres_done:    a.admin_override_area ?? a.actual_area_done ?? a.allocated_area ?? 0,
  actual_acres:  a.actual_area_done ?? null,
  workers:       a.actual_crew_size || a.allocated_workers || 0,
  mukkadam:      a.mukkadam_name || jobs[0]?.mukkadam_name || '',
  rate_per_acre: a.rate_per_acre || 0,
  amount:        Number(a.admin_override_area ?? a.actual_area_done ?? a.allocated_area ?? 0) * Number(a.rate_per_acre || 0),
})),
      payment_history: allPayments,
      bill_summary: {
        total_billed:       totalBilled,
        total_already_paid: totalPaid,
        balance_due_now:    balanceDue,
        why_this_bill:      `Bill for ${selectedActivities.length} activities across ${new Set(selectedActivities.map((a: any) => a.plot_name)).size} plot(s)`,
      },
    };


    await fetch(`${API_BASE_URL}/api/farmer-bill/send-webhook/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' ,'Authorization': `Token ${token}`},
      body: JSON.stringify(payload),
    });

    onSent();
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}
        style={{ maxWidth: '600px', width: '100%', borderRadius: '16px', padding: '24px', maxHeight: '85vh', overflowY: 'auto' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#111827' }}>
            📋 Build Bill — {farmer.farmer_name}
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
        </div>

        {/* Activity selection grouped by plot */}
        {jobs.map((j: any) => {
          const jobActivities = allActivities.filter((a: any) => a.job_id === j.job_id);
          if (jobActivities.length === 0) return null;
          return (
            <div key={j.job_id} style={{ marginBottom: '14px' }}>
              {/* Plot header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <span style={{ fontWeight: 700, fontSize: '0.78rem', color: '#111827' }}>{j.plot_name || j.crop_name}</span>
                <span style={{ fontSize: '0.64rem', color: '#9ca3af' }}>#{j.job_id}</span>
                <button
                  onClick={() => {
                    const allKeys = jobActivities.map((a: any) => a._key);
                    const allSelected = allKeys.every(k => selected.has(k));
                    setSelected(prev => {
                      const next = new Set(prev);
                      allKeys.forEach(k => allSelected ? next.delete(k) : next.add(k));
                      return next;
                    });
                  }}
                  style={{ fontSize: '0.6rem', padding: '1px 8px', borderRadius: '999px', border: '1px solid #e5e7eb', background: '#f9fafb', cursor: 'pointer', marginLeft: 'auto' }}
                >
                  {jobActivities.every((a: any) => selected.has(a._key)) ? 'Deselect All' : 'Select All'}
                </button>
              </div>

              {/* Activities */}
           
{jobActivities.map((a: any) => {
  // CORRECT area priority: admin_override > actual_done > allocated
  const area   = a.admin_override_area ?? a.actual_area_done ?? a.allocated_area ?? 0;
  const amount = Number(area) * Number(a.rate_per_acre || 0);
  const isSelected = selected.has(a._key);
  
  // CORRECT date: prefer actual work date
  const workDate = a.actual_start_time
    ? new Date(a.actual_start_time).toLocaleDateString('en-IN')
    : a.allocated_date || a.scheduled_date || '—';

  // Area label — show what type of area we're using
  const areaLabel = a.admin_override_area != null
    ? `${Number(a.admin_override_area).toFixed(2)} ac (admin)`
    : a.actual_area_done != null
    ? `${Number(a.actual_area_done).toFixed(2)} ac (actual)`
    : `${Number(a.allocated_area || 0).toFixed(2)} ac (allocated)`;

  return (
    <div key={a._key}
      onClick={() => toggle(a._key)}
      style={{
        display: 'flex', alignItems: 'center', gap: '10px',
        padding: '8px 10px', borderRadius: '8px', marginBottom: '4px',
        border: `1px solid ${isSelected ? '#bfdbfe' : '#e5e7eb'}`,
        background: isSelected ? '#eff6ff' : '#f9fafb',
        cursor: 'pointer', opacity: isSelected ? 1 : 0.5,
      }}>
      <input type="checkbox" checked={isSelected} onChange={() => toggle(a._key)}
        style={{ accentColor: '#3b82f6', flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Activity name + plot name */}
        <div style={{ fontSize: '0.76rem', fontWeight: 600, color: '#111827' }}>
          {a.activity_name}
          {a.plot_name && a.plot_name !== j.plot_name && (
            <span style={{ fontSize: '0.62rem', color: '#6b7280', marginLeft: '6px' }}>· {a.plot_name}</span>
          )}
        </div>
        {/* Date + area + rate */}
        <div style={{ fontSize: '0.62rem', color: '#6b7280', marginTop: '2px' }}>
          📅 {workDate} · 🌾 {areaLabel} × ₹{Number(a.rate_per_acre).toLocaleString('en-IN')}/ac
        </div>
        {/* Mukkadam */}
        {(a.mukkadam_name || j.mukkadam_name) && (
          <div style={{ fontSize: '0.6rem', color: '#9ca3af', marginTop: '1px' }}>
            👷 {a.mukkadam_name || j.mukkadam_name}
            {(a.mukkadam_mobile || j.mukkadam_mobile) && ` · ${a.mukkadam_mobile || j.mukkadam_mobile}`}
          </div>
        )}
        {/* Workers */}
        {(a.actual_crew_size || a.allocated_workers) && (
          <div style={{ fontSize: '0.6rem', color: '#9ca3af', marginTop: '1px' }}>
            👥 {a.actual_crew_size || a.allocated_workers} workers
          </div>
        )}
      </div>
      <span style={{ fontWeight: 700, fontSize: '0.82rem', color: isSelected ? '#0f766e' : '#9ca3af', flexShrink: 0 }}>
        ₹{Math.round(amount).toLocaleString('en-IN')}
      </span>
    </div>
  );
})}
            </div>
          );
        })}

        {/* Summary */}
        <div style={{ background: '#f9fafb', borderRadius: '10px', padding: '12px 14px', marginTop: '8px', border: '1px solid #e5e7eb' }}>
          {[
            { label: 'Total Billed (selected)', val: `₹${Math.round(totalBilled).toLocaleString('en-IN')}`, color: '#0f766e' },
            { label: '− Already Collected',     val: `−₹${Math.round(totalPaid).toLocaleString('en-IN')}`, color: '#16a34a' },
          ].map((row, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '6px' }}>
              <span style={{ color: '#6b7280' }}>{row.label}</span>
              <span style={{ fontWeight: 700, color: row.color }}>{row.val}</span>
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1.5px solid #e5e7eb', paddingTop: '8px', fontWeight: 800, fontSize: '0.9rem' }}>
            <span>Balance Due Now</span>
            <span style={{ color: balanceDue > 0 ? '#dc2626' : '#16a34a' }}>
              {balanceDue > 0 ? `₹${Math.round(balanceDue).toLocaleString('en-IN')}` : '✓ Clear'}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
          <button onClick={onClose}
            style={{ flex: 1, padding: '10px', borderRadius: '10px', border: '1px solid #e5e7eb', background: '#fff', fontWeight: 600, cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={handleSend} disabled={selected.size === 0 || balanceDue <= 0}
            style={{ flex: 2, padding: '10px', borderRadius: '10px', border: 'none', background: selected.size === 0 ? '#9ca3af' : '#3b82f6', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}>
            📤 Send Bill ₹{Math.round(Math.max(balanceDue, 0)).toLocaleString('en-IN')}
          </button>
        </div>
      </div>
    </div>
  );
};

  // ── Work + Payment status badges (BI team naming) ──────────────────────
  const WorkStatusBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      work_not_started: { bg: '#f3f4f6', color: '#6b7280',  label: 'Work Not Started' },
      in_progress:      { bg: '#dbeafe', color: '#1d4ed8',  label: 'In Progress' },
      completed:        { bg: '#dcfce7', color: '#16a34a',  label: 'Completed' },
    };
    const m = map[status] || map.work_not_started;
    return (
      <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
        {m.label}
      </span>
    );
  };

  const PaymentStatusBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      pending:  { bg: '#f3f4f6', color: '#6b7280',  label: 'Payment Pending' },
      dispute:  { bg: '#fef2f2', color: '#dc2626',  label: '🚨 Dispute' },
      done:     { bg: '#dcfce7', color: '#16a34a',  label: '✓ Done' },
      settled:  { bg: '#ede9fe', color: '#7c3aed',  label: 'Settled' },
    };
    const m = map[status] || map.pending;
    return (
      <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
        {m.label}
      </span>
    );
  };

  // ── Farmer verify status badge ──────────────────────────
  const VerifyBadge = ({ status }: { status: string }) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      not_submitted:         { bg: '#f3f4f6', color: '#6b7280',  label: '⏳ Not Submitted' },
      pending_your_response: { bg: '#fef9c3', color: '#b45309',  label: '👀 Awaiting Your Response' },
      agreed:                { bg: '#dcfce7', color: '#16a34a',  label: '✅ You Agreed' },
      disputed:              { bg: '#fef2f2', color: '#dc2626',  label: '❌ Disputed' },
    };
    const m = map[status] || map.not_submitted;
    return (
      <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: m.bg, color: m.color }}>
        {m.label}
      </span>
    );
  };

  // ── Allocation day-end report card ──────────────────────
  const AllocReportCard = ({ act, farmerId }: { act: any; farmerId: string }) => {
    const isExpanded = expandedAlloc === act.allocation_id;
    const hasReport = act.report_submitted;
    const verifyStatus = !hasReport
      ? 'not_submitted'
      : act.farmer_agreed === null
      ? 'pending_your_response'
      : act.farmer_agreed
      ? 'agreed'
      : 'disputed';

    const areaDiff = hasReport && act.actual_area_done != null
      ? (act.actual_area_done - act.allocated_area).toFixed(2)
      : null;
    const areaDiffNum = areaDiff ? parseFloat(areaDiff) : 0;

    const workStatus = act.work_status || 'work_not_started';
    const paymentStatus = act.payment_status || 'pending';
    const isDispute = paymentStatus === 'dispute';
    const billingLocked = isDispute && !act.use_actual_for_settlement && !act.admin_override_area;
    const mukkadamClaimed = act.mukkadam_claimed_area ?? act.actual_area_done;
    // Farmer column: OTP verified = same as mukkadam. Team override = override area. Otherwise nothing.
    const farmerArea = act.admin_override_area != null
      ? act.admin_override_area
      : (act.farmer_agreed === true && mukkadamClaimed != null)
        ? mukkadamClaimed
        : null;
    const billingArea = act.admin_override_area ?? act.actual_area_done ?? act.allocated_area;

    return (
      <div style={{
        border: `1px solid ${isDispute ? '#fecaca' : verifyStatus === 'pending_your_response' ? '#fde68a' : verifyStatus === 'agreed' ? '#bbf7d0' : '#e5e7eb'}`,
        borderRadius: '8px', overflow: 'hidden', background: '#fff',
        marginBottom: '6px',
      }}>
        {/* Row header */}
        <div
          onClick={() => setExpandedAlloc(isExpanded ? null : act.allocation_id)}
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 0.8fr 1fr 1fr 1fr auto',
            gap: '8px', padding: '8px 12px',
            cursor: 'pointer', alignItems: 'center',
            fontSize: '0.74rem',
          }}
        >
          {/* Activity name + status badges */}
          <div>
            <p style={{ margin: 0, fontWeight: 700, color: '#111827' }}>{act.activity_name}</p>
            <p style={{ margin: 0, fontSize: '0.62rem', color: '#9ca3af' }}>{act.plot_code || act.plot_name || '—'}</p>
            <div style={{ display: 'flex', gap: '4px', marginTop: '3px', flexWrap: 'wrap' }}>
              <WorkStatusBadge status={workStatus} />
              <PaymentStatusBadge status={paymentStatus} />
              {act.is_carry_forward && (
                <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>↩ Carry Fwd</span>
              )}
            </div>
          </div>

          {/* DATE */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 700, color: '#374151', fontSize: '0.72rem' }}>
              {act.allocated_date ? act.allocated_date.slice(5) : '—'}
            </p>
            <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>{act.allocated_workers}w</p>
          </div>

          {/* BI ASSIGNED */}
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 700, color: '#374151' }}>{Number(act.allocated_area).toFixed(2)} ac</p>
            <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(act.allocated_area) * Number(act.rate_per_acre || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
          </div>

          {/* MUKKADAM */}
          <div style={{ textAlign: 'center' }}>
            {mukkadamClaimed != null ? (
              <>
                <p style={{ margin: 0, fontWeight: 700, color: '#1d4ed8' }}>{Number(mukkadamClaimed).toFixed(2)} ac</p>
                <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(mukkadamClaimed) * Number(act.mukkadam_rate || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
              </>
            ) : (
              <p style={{ margin: 0, color: '#d1d5db', fontSize: '0.7rem' }}>—</p>
            )}
          </div>

          {/* FARMER */}
          <div style={{ textAlign: 'center' }}>
            {farmerArea != null ? (
              <>
                <p style={{ margin: 0, fontWeight: 700, color: act.admin_override_area != null ? '#d97706' : '#16a34a' }}>
                  {Number(farmerArea).toFixed(2)} ac
                </p>
                <p style={{ margin: 0, fontSize: '0.58rem', color: '#9ca3af' }}>₹{Number(Number(farmerArea) * Number(act.rate_per_acre || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</p>
              </>
            ) : isDispute ? (
              <p style={{ margin: 0, color: '#dc2626', fontSize: '0.62rem', fontWeight: 700 }}>🚨 Disputed</p>
            ) : verifyStatus === 'pending_your_response' ? (
              <p style={{ margin: 0, color: '#b45309', fontSize: '0.62rem', fontWeight: 600 }}>⏳ Pending</p>
            ) : (
              <p style={{ margin: 0, color: '#d1d5db', fontSize: '0.7rem' }}>—</p>
            )}
          </div>

          <span style={{ color: '#9ca3af', fontSize: '0.65rem' }}>{isExpanded ? '▲' : '▼'}</span>
        </div>

        {/* Dispute override panel — shown inline without expanding */}
        {isDispute && billingLocked && (
          <div style={{ borderTop: '1px solid #fecaca', background: '#fff5f5', padding: '10px 12px' }}>
            <p style={{ margin: '0 0 6px', fontSize: '0.68rem', fontWeight: 700, color: '#dc2626' }}>
              🚨 Dispute — Billing locked. Fill farmer's claim after call to unlock.
            </p>
            <div style={{ fontSize: '0.7rem', color: '#6b7280', marginBottom: '6px' }}>
              Mukkadam claimed: <strong style={{ color: '#1d4ed8' }}>{mukkadamClaimed != null ? `${Number(mukkadamClaimed).toFixed(2)} ac` : '—'}</strong>
            </div>
            {disputeOpen === act.allocation_id ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <input
                  type="number"
                  value={disputeArea}
                  onChange={e => setDisputeArea(e.target.value)}
                  placeholder="Farmer says (acres)"
                  style={{ width: '100%', padding: '6px 10px', border: '1px solid #fca5a5', borderRadius: '6px', fontSize: '0.78rem', boxSizing: 'border-box' }}
                />
                <textarea
                  value={disputeReason}
                  onChange={e => setDisputeReason(e.target.value)}
                  placeholder="Reason (water logging, crop damage...)"
                  rows={2}
                  style={{ width: '100%', padding: '6px 10px', border: '1px solid #fca5a5', borderRadius: '6px', fontSize: '0.72rem', resize: 'none', boxSizing: 'border-box' }}
                />
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => { setDisputeOpen(null); setDisputeArea(''); setDisputeReason(''); }}
                    style={{ flex: 1, padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleResolveDispute(act.allocation_id)}
                    disabled={disputeSaving || !disputeArea}
                    style={{ flex: 2, padding: '6px', borderRadius: '6px', border: 'none', background: disputeSaving ? '#fca5a5' : '#dc2626', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                  >
                    {disputeSaving ? 'Saving...' : 'Unlock Billing with This Area'}
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setDisputeOpen(act.allocation_id)}
                style={{ padding: '5px 12px', borderRadius: '6px', border: '1px solid #fca5a5', background: '#fff', color: '#dc2626', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
              >
                + Enter Farmer's Claim
              </button>
            )}
          </div>
        )}

        {/* Override applied indicator */}
        {isDispute && !billingLocked && act.admin_override_area != null && (
          <div style={{ borderTop: '1px solid #fed7aa', background: '#fff7ed', padding: '6px 12px', fontSize: '0.68rem', color: '#c2410c' }}>
            ⚠ Billing uses override area ({Number(act.admin_override_area).toFixed(2)} ac) — {act.dispute_reason}
          </div>
        )}

        {/* Expanded detail */}
        {isExpanded && (
          <div style={{ borderTop: '1px solid #f3f4f6', padding: '12px', background: '#fafafa' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>

              {/* Planned box */}
              <div style={{ background: '#eff6ff', borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem' }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: '#1d4ed8', textTransform: 'uppercase' }}>📋 Planned</p>
                {[
                  { label: 'Date',    val: act.allocated_date },
                  { label: 'Area',    val: `${Number(act.allocated_area).toFixed(2)} ac` },
                  { label: 'Workers', val: act.allocated_workers },
                  { label: 'Rate',    val: `₹${Number(act.mukkadam_rate).toLocaleString('en-IN')}/ac` },
                  { label: 'Amount',  val: `₹${Number(act.mukkadam_amount).toLocaleString('en-IN')}` },
                ].map((r, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                    <span style={{ color: '#6b7280' }}>{r.label}</span>
                    <span style={{ fontWeight: 600, color: '#111827' }}>{r.val}</span>
                  </div>
                ))}
              </div>

              {/* Mukkadam report box */}
              <div style={{
                background: hasReport ? '#f0fdf4' : '#f9fafb',
                borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem',
                border: hasReport ? '1px solid #bbf7d0' : '1px solid #e5e7eb',
              }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: hasReport ? '#16a34a' : '#6b7280', textTransform: 'uppercase' }}>
                  👷 Mukkadam Report {!hasReport && '(Pending)'}
                </p>
                {hasReport ? (
                  <>
                    {[
                      { label: 'Claimed Area', val: `${Number(mukkadamClaimed).toFixed(2)} ac` },
                      { label: 'Crew Showed',  val: act.actual_crew_size },
                      { label: 'Start Time',   val: act.actual_start_time ? new Date(act.actual_start_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'End Time',     val: act.actual_end_time ? new Date(act.actual_end_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—' },
                      { label: 'Submitted',    val: act.report_submitted_at ? new Date(act.report_submitted_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—' },
                    ].map((r, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                        <span style={{ color: '#6b7280' }}>{r.label}</span>
                        <span style={{ fontWeight: 600, color: '#111827' }}>{r.val}</span>
                      </div>
                    ))}
                    {mukkadamClaimed && (
                      <div style={{ borderTop: '1px solid #bbf7d0', marginTop: '5px', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                        <span style={{ color: '#6b7280' }}>Claimed Amt</span>
                        <span style={{ color: '#0f766e' }}>
                          ₹{(Number(mukkadamClaimed) * Number(act.mukkadam_rate)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    )}
                  </>
                ) : (
                  <p style={{ color: '#9ca3af', fontSize: '0.7rem', margin: 0 }}>
                    Mukkadam hasn't submitted day-end report yet
                  </p>
                )}
              </div>

              {/* Farmer response box */}
              <div style={{
                background: verifyStatus === 'agreed' ? '#f0fdf4' : verifyStatus === 'disputed' ? '#fef2f2' : '#fffbeb',
                borderRadius: '8px', padding: '10px 12px', fontSize: '0.72rem',
                border: `1px solid ${verifyStatus === 'agreed' ? '#bbf7d0' : verifyStatus === 'disputed' ? '#fecaca' : '#fde68a'}`,
              }}>
                <p style={{ margin: '0 0 6px', fontSize: '0.62rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>
                  🌾 Your Response
                </p>

                {verifyStatus === 'not_submitted' && (
                  <p style={{ color: '#9ca3af', fontSize: '0.7rem', margin: 0 }}>
                    Waiting for mukkadam to submit report first
                  </p>
                )}

                {verifyStatus === 'pending_your_response' && (
                  <>
                    <p style={{ margin: '0 0 8px', fontSize: '0.7rem', color: '#374151' }}>
                      Mukkadam claimed <strong>{Number(mukkadamClaimed).toFixed(2)} ac</strong> done.
                      {areaDiffNum !== 0 && (
                        <span style={{ color: areaDiffNum < 0 ? '#dc2626' : '#0f766e', marginLeft: '4px' }}>
                          ({areaDiffNum > 0 ? '+' : ''}{areaDiff} vs planned)
                        </span>
                      )}
                    </p>
                    <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, true)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{ flex: 1, padding: '6px', borderRadius: '6px', border: 'none', background: '#16a34a', color: '#fff', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '✅ Agree'}
                      </button>
                      <button
                        onClick={() => handleFarmerVerify(act.allocation_id, farmerId, act.job_id, false)}
                        disabled={verifyLoading === act.allocation_id}
                        style={{ flex: 1, padding: '6px', borderRadius: '6px', border: 'none', background: '#dc2626', color: '#fff', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' }}
                      >
                        {verifyLoading === act.allocation_id ? '...' : '❌ Dispute'}
                      </button>
                    </div>
                    {/* OTP resend */}
                    <div style={{ borderTop: '1px solid #fde68a', paddingTop: '8px' }}>
                      <p style={{ margin: '0 0 6px', fontSize: '0.62rem', color: '#6b7280', fontWeight: 600 }}>VERIFY VIA OTP</p>
                      {otpOpen === act.allocation_id ? (
                        <div style={{ display: 'flex', gap: '5px' }}>
                          <input
                            type="text"
                            inputMode="numeric"
                            value={otpCode}
                            onChange={e => setOtpCode(e.target.value)}
                            placeholder="Enter OTP"
                            maxLength={6}
                            style={{ flex: 1, padding: '6px 10px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.15em', textAlign: 'center' }}
                          />
                          <button
                            onClick={() => handleVerifyOtp(act.allocation_id, farmerId)}
                            disabled={otpVerifying || !otpCode.trim()}
                            style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: otpVerifying ? '#99f6e4' : '#14b8a6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            {otpVerifying ? '...' : '✓ Verify'}
                          </button>
                          <button onClick={() => { setOtpOpen(null); setOtpCode(''); }}
                            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}>✕</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleSendOtp(act.allocation_id)}
                          disabled={otpSending === act.allocation_id}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', color: '#374151', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
                        >
                          {otpSending === act.allocation_id ? 'Sending...' : '📱 Send OTP to Farmer'}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {verifyStatus === 'agreed' && (
                  <>
                    <p style={{ margin: '0 0 4px', color: '#16a34a', fontWeight: 700, fontSize: '0.78rem' }}>✅ Farmer verified via OTP</p>
                    <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280' }}>
                      Settlement uses: <strong>{Number(billingArea).toFixed(2)} ac</strong>
                    </p>
                    {act.farmer_response_at && (
                      <p style={{ margin: '3px 0 0', fontSize: '0.6rem', color: '#9ca3af' }}>
                        Verified: {new Date(act.farmer_response_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </p>
                    )}
                  </>
                )}

                {verifyStatus === 'disputed' && (
                  <>
                    <p style={{ margin: '0 0 8px', color: '#dc2626', fontWeight: 700, fontSize: '0.78rem' }}>❌ Disputed</p>

                    {/* Comparison: Mukkadam vs Farmer */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
                      <div style={{ background: '#eff6ff', borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                        <p style={{ margin: '0 0 2px', fontSize: '0.58rem', color: '#6b7280', fontWeight: 600 }}>MUKKADAM</p>
                        <p style={{ margin: 0, fontWeight: 800, color: '#1d4ed8', fontSize: '0.88rem' }}>{mukkadamClaimed != null ? `${Number(mukkadamClaimed).toFixed(2)} ac` : '—'}</p>
                      </div>
                      <div style={{ background: act.admin_override_area != null ? '#fff7ed' : '#fef2f2', borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                        <p style={{ margin: '0 0 2px', fontSize: '0.58rem', color: '#6b7280', fontWeight: 600 }}>FARMER</p>
                        <p style={{ margin: 0, fontWeight: 800, color: act.admin_override_area != null ? '#d97706' : '#dc2626', fontSize: '0.88rem' }}>
                          {act.admin_override_area != null ? `${Number(act.admin_override_area).toFixed(2)} ac` : '—'}
                        </p>
                      </div>
                    </div>

                    {act.admin_override_area != null ? (
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '5px 8px', fontSize: '0.68rem', color: '#16a34a', fontWeight: 700, marginBottom: '8px' }}>
                        ✓ Billing using farmer's claim: {Number(act.admin_override_area).toFixed(2)} ac
                        {act.dispute_reason ? <span style={{ color: '#6b7280', fontWeight: 400 }}> — {act.dispute_reason}</span> : ''}
                      </div>
                    ) : (
                      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', padding: '5px 8px', fontSize: '0.68rem', color: '#dc2626', fontWeight: 600, marginBottom: '8px' }}>
                        🔒 Billing locked — call farmer &amp; fill claim below
                      </div>
                    )}

                    {act.farmer_dispute_reason && (
                      <p style={{ margin: '0 0 8px', fontSize: '0.68rem', color: '#374151', background: '#fef2f2', padding: '5px 7px', borderRadius: '5px' }}>
                        "{act.farmer_dispute_reason}"
                      </p>
                    )}

                    {/* OTP section */}
                    <div style={{ borderTop: '1px solid #fecaca', paddingTop: '8px', marginTop: '4px' }}>
                      <p style={{ margin: '0 0 6px', fontSize: '0.62rem', color: '#6b7280', fontWeight: 600 }}>RE-VERIFY VIA OTP</p>
                      {otpOpen === act.allocation_id ? (
                        <div style={{ display: 'flex', gap: '5px' }}>
                          <input
                            type="text"
                            inputMode="numeric"
                            value={otpCode}
                            onChange={e => setOtpCode(e.target.value)}
                            placeholder="Enter OTP"
                            maxLength={6}
                            style={{ flex: 1, padding: '6px 10px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.15em', textAlign: 'center' }}
                          />
                          <button
                            onClick={() => handleVerifyOtp(act.allocation_id, farmerId)}
                            disabled={otpVerifying || !otpCode.trim()}
                            style={{ padding: '6px 12px', borderRadius: '6px', border: 'none', background: otpVerifying ? '#99f6e4' : '#14b8a6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            {otpVerifying ? '...' : '✓ Verify'}
                          </button>
                          <button
                            onClick={() => { setOtpOpen(null); setOtpCode(''); }}
                            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleSendOtp(act.allocation_id)}
                          disabled={otpSending === act.allocation_id}
                          style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', color: '#374151', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
                        >
                          {otpSending === act.allocation_id ? 'Sending...' : '📱 Send OTP to Farmer'}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Duration bar */}
            {act.actual_start_time && act.actual_end_time && (
              <div style={{ background: '#fff', borderRadius: '6px', border: '1px solid #e5e7eb', padding: '8px 12px', fontSize: '0.7rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ color: '#6b7280' }}>
                    🕐 {new Date(act.actual_start_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span style={{ fontWeight: 700, color: '#374151' }}>
                    {Math.round((new Date(act.actual_end_time).getTime() - new Date(act.actual_start_time).getTime()) / 60000)} mins worked
                  </span>
                  <span style={{ color: '#6b7280' }}>
                    🕐 {new Date(act.actual_end_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── Top Summary Bar ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '10px', padding: '14px 16px',
        borderBottom: '1px solid #e5e7eb', background: '#fff', flexShrink: 0,
      }}>
        {[
          { label: 'Farmers', value: data.farmer_count, suffix: 'in cluster', color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe' },
          { label: 'To Collect', value: `₹${data.total_farmer_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, suffix: 'from farmers', color: '#b45309', bg: '#fffbeb', border: '#fde68a' },
          { label: 'Mukkadams', value: data.mukkadam_count, suffix: 'assigned', color: '#0f766e', bg: '#f0fdfa', border: '#99f6e4' },
          {
            label: 'To Pay',
            value: `₹${Math.max(0, data.mukkadams.reduce((sum: number, m: any) => {
              // Only sum 'calculated' jobs with positive net_payable — skip paid/no_payment_needed
              const totalNet = m.settlements
                .filter((s2: any) => s2.status === 'calculated' && Number(s2.net_payable) > 0.01)
                .reduce((s: number, s2: any) => s + Number(s2.net_payable), 0);
              return sum + totalNet;
            }, 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
            suffix: 'to mukkadams', color: '#dc2626', bg: '#fef2f2', border: '#fecaca'
          },
        ].map(s => (
          <div key={s.label} style={{ background: s.bg, borderRadius: '10px', border: `1.5px solid ${s.border}`, padding: '10px 14px' }}>
            <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280', marginBottom: '3px' }}>{s.label}</p>
            <p style={{ margin: 0, fontWeight: 800, fontSize: '1.2rem', color: s.color, lineHeight: 1 }}>{s.value}</p>
            <p style={{ margin: '2px 0 0', fontSize: '0.62rem', color: '#9ca3af' }}>{s.suffix}</p>
          </div>
        ))}
      </div>

      {/* ── Tab Switch ── */}
      <div style={{ display: 'flex', borderBottom: '1.5px solid #e5e7eb', background: '#fff', flexShrink: 0 }}>
        {[
          { key: 'farmers', label: '🌾 Farmer Collections', count: data.farmers.filter((f: any) => {
    const allAllocs = (f.jobs || [f]).flatMap((j: any) =>
      (j.activities || []).flatMap((a: any) => a.allocations || [])
    );
    if (allAllocs.length === 0) return true;
    return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
  }).length, color: '#3b82f6' },
          { key: 'mukkadams', label: '👷 Mukkadam Settlements', count: data.mukkadams.filter((m: any) => {
    const allAllocs = (m.settlements || []).flatMap((s: any) => s.activities || []);
    if (allAllocs.length === 0) return true;
    return allAllocs.some((a: any) => a.work_status !== 'work_not_started');
  }).length, color: '#0f766e' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key as any); setExpandedKey(null); setExpandedAlloc(null); }}
            style={{
              padding: '10px 20px', border: 'none', background: 'none', cursor: 'pointer',
              fontSize: '0.82rem', fontWeight: 700,
              borderBottom: tab === t.key ? `2.5px solid ${t.color}` : '2.5px solid transparent',
              color: tab === t.key ? t.color : '#6b7280',
            }}
          >
            {t.label}
            <span style={{ marginLeft: '6px', fontSize: '0.65rem', padding: '1px 6px', borderRadius: '999px', background: tab === t.key ? t.color : '#f3f4f6', color: tab === t.key ? '#fff' : '#6b7280', fontWeight: 700 }}>
              {t.count}
            </span>
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', paddingRight: '12px' }}>
          <button onClick={fetchData} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 12px', borderRadius: '7px', border: 'none', background: '#f3f4f6', color: '#374151', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}>
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Scrollable Content ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>

        {/* ════ FARMERS TAB ════ */}

{tab === 'farmers' && (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
    {data.farmers.length === 0 ? (
      <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af', fontSize: '0.82rem' }}>
        No farmers in this cluster yet
      </div>
    ) : data.farmers.map((f: any) => {
      const jobs = f.jobs || [f];

      // ── Aggregated financials across ALL jobs ──
      const aggTotalJob  = jobs.reduce((s: number, j: any) => s + (j.total_job_amount || j.booking_total || 0), 0);
      const aggBilled    = jobs.reduce((s: number, j: any) => s + (j.summary?.total_billable_so_far || 0), 0);
      const aggPaid      = jobs.reduce((s: number, j: any) => s + (j.summary?.total_paid || 0), 0);
      const aggDue       = jobs.reduce((s: number, j: any) => s + (j.summary?.balance_due || 0), 0);

      const firstDate = jobs.reduce((d: string | null, j: any) => {
        const fd = j.first_activity_date || j.activities?.[0]?.scheduled_date;
        return (!d || (fd && fd < d)) ? fd : d;
      }, null as string | null);
      const lastDate = jobs.reduce((d: string | null, j: any) => {
        const ld = j.last_activity_date || j.activities?.[j.activities?.length - 1]?.scheduled_date;
        return (!d || (ld && ld > d)) ? ld : d;
      }, null as string | null);

      const hasBalance = aggDue > 0.01;

      // Pending verifications across all jobs
      const pendingVerify = jobs.reduce((n: number, j: any) =>
        n + (j.activities || []).filter((a: any) =>
          a.report_submitted && a.farmer_agreed === null
        ).length, 0);

      // Dispute count
      const disputeCount = jobs.reduce((n: number, j: any) =>
        n + (j.activities || []).flatMap((a: any) => a.allocations || []).filter((a: any) =>
          a.payment_status === 'dispute'
        ).length, 0);

      const expandKey = `farmer-${f.farmer_id}`;
      const isOpen = expandedKey === expandKey;

      return (
        <div key={expandKey} style={{
          border: `1.5px solid ${disputeCount > 0 ? '#fecaca' : pendingVerify > 0 ? '#fde68a' : hasBalance ? '#fde68a' : '#e5e7eb'}`,
          borderRadius: '12px', background: '#fff', overflow: 'hidden',
        }}>

          {/* ── COLLAPSED HEADER ── */}
          <div
            onClick={() => setExpandedKey(isOpen ? null : expandKey)}
            style={{ padding: '12px 16px', cursor: 'pointer' }}
          >
            {/* Row 1: name + badges + collect button */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#111827' }}>{f.farmer_name}</span>
                  <span style={{ fontSize: '0.65rem', color: '#9ca3af' }}>{f.farmer_id}</span>
                  <span style={{
                    fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 600,
                    background: hasBalance ? '#fef9c3' : '#dcfce7',
                    color: hasBalance ? '#b45309' : '#16a34a',
                  }}>
                    {hasBalance ? '⚠ Balance Due' : '✓ Clear'}
                  </span>
                  {disputeCount > 0 && (
                    <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>
                      🚨 {disputeCount} Dispute{disputeCount > 1 ? 's' : ''}
                    </span>
                  )}
                  {pendingVerify > 0 && (
                    <span style={{ fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>
                      👀 {pendingVerify} Verify Pending
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.68rem', color: '#6b7280', marginTop: '3px' }}>
                  📞 {f.phone_number || f.mobile_number || '—'}
                </div>
                {(firstDate || lastDate) && (
                  <div style={{ fontSize: '0.65rem', color: '#9ca3af', marginTop: '2px' }}>
                    📅 {firstDate || '—'} → {lastDate || '—'}
                  </div>
                )}
              </div>

              {/* Right: AGGREGATED financial summary + collect button */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }} onClick={e => e.stopPropagation()}>
                {/* Aggregated 4-number summary */}
                <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-end' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Total Job</div>
                    <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#374151' }}>
                      {aggTotalJob > 0 ? `₹${aggTotalJob.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Billed</div>
                    <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#0f766e' }}>
                      {aggBilled > 0 ? `₹${aggBilled.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>Collected</div>
                    <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#16a34a' }}>
                      ₹{aggPaid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>To Collect</div>
                    <div style={{ fontWeight: 800, fontSize: '0.92rem', color: aggDue > 0.01 ? '#dc2626' : '#16a34a' }}>
                      {aggDue > 0.01 ? `₹${aggDue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear'}
                    </div>
                  </div>
                </div>

                {/* Collect button — only when due */}
                {aggDue > 0.01 && jobs.map((j: any) => {
                  const s = j.summary;
                  {j.bill_sent ? (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
    <span style={{ fontSize: '0.68rem', padding: '4px 10px', borderRadius: '7px', background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#16a34a', fontWeight: 700 }}>
      ✅ Bill Sent
    </span>
    <button
      onClick={() => {
        setDetailModal({
          farmerName:     f.farmer_name,
          farmerId:       f.farmer_id,
          phone:          f.phone_number || f.mobile_number || '—',
          jobId:          j.job_id,
          cropName:       j.crop_name,
          plotName:       j.plot_name || '',
          mukkadamName:   j.mukkadam_name || '',
          mukkadamMobile: j.mukkadam_mobile || '',
          activities:     (j.activities || []).flatMap((act: any) =>
            (act.allocations || [{ ...act }]).map((alloc: any) => ({ ...act, ...alloc }))
          ),
          paymentHistory: (j.payment_history || []).filter((p: any) => p.type !== 'advance'),
          totalBilled:    s.total_billable_so_far,
          totalPaid:      s.total_paid,
          balanceDue:     s.balance_due,
        });
        setWebhookSent(false);
      }}
      style={{ padding: '3px 10px', borderRadius: '7px', border: '1px solid #d1d5db', background: '#f9fafb', color: '#6b7280', fontSize: '0.65rem', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
    >
      🔁 Send Again
    </button>
  </div>
) : (
  s.balance_due > 0.01 && (
    // <button
    //   onClick={() => {
    //     setDetailModal({
    //       farmerName:     f.farmer_name,
    //       farmerId:       f.farmer_id,
    //       phone:          f.phone_number || f.mobile_number || '—',
    //       jobId:          j.job_id,
    //       cropName:       j.crop_name,
    //       plotName:       j.plot_name || '',
    //       mukkadamName:   j.mukkadam_name || '',
    //       mukkadamMobile: j.mukkadam_mobile || '',
    //       activities:     (j.activities || []).flatMap((act: any) =>
    //         (act.allocations || [{ ...act }]).map((alloc: any) => ({ ...act, ...alloc }))
    //       ),
    //       paymentHistory: (j.payment_history || []).filter((p: any) => p.type !== 'advance'),
    //       totalBilled:    s.total_billable_so_far,
    //       totalPaid:      s.total_paid,
    //       balanceDue:     s.balance_due,
    //     });
    //     setWebhookSent(false);
    //   }}
    //   style={{ padding: '5px 14px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
    // >
    //   + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')}
    // </button>
    <button
  onClick={() => setBillBuilder({ farmer: f, jobs })}
  style={{ padding: '5px 14px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
  📋 Build & Send Bill
</button>
  )
)}
                })}
              </div>
            </div>

            {/* Row 2: per-job work status counts */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              {jobs.map((j: any) => {
                const allAllocs = (j.activities || []).flatMap((a: any) => a.allocations || []);
                const counts: Record<string, number> = {};
                allAllocs.forEach((a: any) => {
                  const ws = a.work_status || 'work_not_started';
                  counts[ws] = (counts[ws] || 0) + 1;
                });
                return (
                  <div key={j.job_id} style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.6rem', color: '#9ca3af', fontFamily: 'monospace' }}>#{j.job_id}</span>
                    {/* Plot name shown in header row too */}
                    {j.plot_name && (
                      <span style={{ fontSize: '0.6rem', color: '#374151', fontWeight: 700 }}>{j.plot_name}</span>
                    )}
                    {counts.work_not_started > 0 && (
                      <span style={{ fontSize: '0.6rem', background: '#f3f4f6', color: '#6b7280', padding: '1px 5px', borderRadius: '999px' }}>
                        {counts.work_not_started} not started
                      </span>
                    )}
                    {counts.in_progress > 0 && (
                      <span style={{ fontSize: '0.6rem', background: '#dbeafe', color: '#1d4ed8', padding: '1px 5px', borderRadius: '999px' }}>
                        {counts.in_progress} in progress
                      </span>
                    )}
                    {counts.completed > 0 && (
                      <span style={{ fontSize: '0.6rem', background: '#dcfce7', color: '#16a34a', padding: '1px 5px', borderRadius: '999px' }}>
                        {counts.completed} completed
                      </span>
                    )}
                  </div>
                );
              })}
              <span style={{ marginLeft: 'auto', color: '#9ca3af', fontSize: '0.65rem' }}>{isOpen ? '▲' : '▼'}</span>
            </div>
          </div>

          {/* ── EXPANDED ── */}
          {isOpen && jobs.map((j: any) => {
            const s = j.summary;
            const hasJobBalance = s && s.balance_due > 0.01;

            return (
              <div key={j.job_id} style={{ borderTop: '1px solid #e5e7eb', background: '#fafafa', padding: '14px 16px' }}>
                {/* Job title row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', color: '#374151' }}>{j.crop_name}</span>
                    {j.variety && <span style={{ fontSize: '0.72rem', color: '#9ca3af', marginLeft: '6px' }}>({j.variety})</span>}
                    {/* ── BOLD PLOT NAME ── */}
                    {j.plot_name && (
                      <span style={{ fontSize: '0.78rem', color: '#111827', marginLeft: '8px', fontWeight: 700 }}>
                        {j.plot_name}
                      </span>
                    )}
                  </div>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: '#9ca3af' }}>#{j.job_id}</span>
                </div>

                {/* ── PAYMENT SECTION ── */}
                {s && (
                  <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px', marginBottom: '14px' }}>
                    <p style={{ margin: '0 0 10px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>💰 Payment Summary</p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>

                      {/* Calculation */}
                      <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                        {[
                          { label: 'Total Billed So Far', val: `₹${s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                          { label: '− Total Collected',   val: `−₹${s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#16a34a' },
                        ].map((row, ri) => (
                          <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                            <span style={{ color: '#6b7280' }}>{row.label}</span>
                            <span style={{ fontWeight: 700, color: row.color }}>{row.val}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                          <span style={{ color: '#111827' }}>Balance Due</span>
                          <span style={{ color: hasJobBalance ? '#dc2626' : '#16a34a', fontSize: '0.9rem' }}>
                            {hasJobBalance ? `₹${s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear'}
                          </span>
                        </div>
                        {s.all_activities_past && s.final_gap > 0 && (
                          <div style={{ marginTop: '6px', padding: '6px 8px', borderRadius: '6px', background: '#fef2f2', border: '1px solid #fecaca', fontSize: '0.68rem', color: '#dc2626', fontWeight: 700 }}>
                            ⚠ All done — ₹{s.final_gap.toLocaleString('en-IN', { maximumFractionDigits: 0 })} vs booking total
                          </div>
                        )}
                      </div>

                      {/* Payment history */}
                      <div style={{ background: '#f9fafb', borderRadius: '8px', padding: '10px 12px', fontSize: '0.74rem' }}>
                        <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 History</p>
                        {(j.payment_history || []).length === 0 ? (
                          <p style={{ color: '#9ca3af', fontSize: '0.72rem', margin: 0 }}>No payments recorded</p>
                        ) : (
                          <>
                            {(j.payment_history || []).map((p: any, pi: number) => (
                              <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '4px', marginBottom: '4px', borderBottom: pi < j.payment_history.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
                                  <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '999px', background: p.type === 'advance' ? '#eff6ff' : '#f0fdf4', color: p.type === 'advance' ? '#1d4ed8' : '#16a34a', fontWeight: 600 }}>{p.mode}</span>
                                  <span style={{ color: '#9ca3af', fontSize: '0.64rem' }}>{p.date}</span>
                                  {p.proof_url && (
                                    <a href={p.proof_url} target="_blank" rel="noreferrer"
                                      style={{ fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0px 5px', background: '#eff6ff', cursor: 'pointer' }}
                                      title="View payment proof">
                                      📎 View
                                    </a>
                                  )}
                                </div>
                                <span style={{ fontWeight: 700, color: '#16a34a' }}>₹{Number(p.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                              </div>
                            ))}
                            <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontWeight: 800 }}>
                              <span>Total</span>
                              <span style={{ color: '#16a34a' }}>₹{s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>

                    {j.bill_sent ? (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
    <span style={{ fontSize: '0.68rem', padding: '4px 10px', borderRadius: '7px', background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#16a34a', fontWeight: 700 }}>
      ✅ Bill Sent
    </span>
    <button
      onClick={() => {
        setDetailModal({
          farmerName:     f.farmer_name,
          farmerId:       f.farmer_id,
          phone:          f.phone_number || f.mobile_number || '—',
          jobId:          j.job_id,
          cropName:       j.crop_name,
          plotName:       j.plot_name || '',
          mukkadamName:   j.mukkadam_name || '',
          mukkadamMobile: j.mukkadam_mobile || '',
          activities:     (j.activities || []).flatMap((act: any) =>
            (act.allocations || [{ ...act }]).map((alloc: any) => ({ ...act, ...alloc }))
          ),
          paymentHistory: (j.payment_history || []).filter((p: any) => p.type !== 'advance'),
          totalBilled:    s.total_billable_so_far,
          totalPaid:      s.total_paid,
          balanceDue:     s.balance_due,
        });
        setWebhookSent(false);
      }}
      style={{ padding: '3px 10px', borderRadius: '7px', border: '1px solid #d1d5db', background: '#f9fafb', color: '#6b7280', fontSize: '0.65rem', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
    >
      🔁 Send Again
    </button>
  </div>
) : (
  s.balance_due > 0.01 && (
    // <button
    //   onClick={() => {
    //     setDetailModal({
    //       farmerName:     f.farmer_name,
    //       farmerId:       f.farmer_id,
    //       phone:          f.phone_number || f.mobile_number || '—',
    //       jobId:          j.job_id,
    //       cropName:       j.crop_name,
    //       plotName:       j.plot_name || '',
    //       mukkadamName:   j.mukkadam_name || '',
    //       mukkadamMobile: j.mukkadam_mobile || '',
    //       activities:     (j.activities || []).flatMap((act: any) =>
    //         (act.allocations || [{ ...act }]).map((alloc: any) => ({ ...act, ...alloc }))
    //       ),
    //       paymentHistory: (j.payment_history || []).filter((p: any) => p.type !== 'advance'),
    //       totalBilled:    s.total_billable_so_far,
    //       totalPaid:      s.total_paid,
    //       balanceDue:     s.balance_due,
    //     });
    //     setWebhookSent(false);
    //   }}
    //   style={{ padding: '5px 14px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
    // >
    //   + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')}
    // </button>
    <button
  onClick={() => setBillBuilder({ farmer: f, jobs })}
  style={{ padding: '5px 14px', borderRadius: '7px', border: 'none', background: '#3b82f6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
  📋 Build & Send Bill
</button>
  )
)}
                  </div>
                )}

                {/* ── WORK ALLOCATIONS ── */}
                <p style={{ margin: '0 0 8px', fontSize: '0.68rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  📋 Work Allocations & Verification
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 0.8fr 1fr 1fr 1fr auto', gap: '8px', padding: '4px 12px', fontSize: '0.6rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>
                  <span>Activity / Status</span>
                  <span style={{ textAlign: 'center' }}>Date</span>
                  <span style={{ textAlign: 'center' }}>BI Assigned</span>
                  <span style={{ textAlign: 'center' }}>Mukkadam</span>
                  <span style={{ textAlign: 'center' }}>Farmer</span>
                  <span />
                </div>

                {(j.activities || []).flatMap((act: any) =>
                  (act.allocations || [{ ...act, allocation_id: act.activity_id }]).map((alloc: any) => (
                    <AllocReportCard
                      key={alloc.allocation_id}
                      act={{ ...act, ...alloc }}
                      farmerId={f.farmer_id}
                    />
                  ))
                )}
              </div>
            );
          })}
        </div>
      );
    })}
  </div>
)}


{billBuilder && (
  <BillBuilderModal
    farmer={billBuilder.farmer}
    jobs={billBuilder.jobs}
    onClose={() => setBillBuilder(null)}
    onSent={() => { fetchData(); setBillBuilder(null); }}
  />
)}

{tab === 'mukkadams' && (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
    {data.mukkadams.map((m: any) => {
      // ── SAFE DEFAULTS ─────────────────────────────────────────
      const settlements    = Array.isArray(m.settlements)         ? m.settlements         : [];
      const missedWeekly   = Array.isArray(m.missed_weekly_dates) ? m.missed_weekly_dates : [];

      const expandKey = `mukkadam-${m.mukkadam_id}`;
      const isOpen    = expandedKey === expandKey;

      // ── UPDOWN DETECTION ─────────────────────────────────────────
      const isUpdown = m.mukkadam_type === 'updown';

      const weeklyPaymentDayValue = m.weekly_payment_day_value ?? m.assignment?.weekly_payment_day_value;
      const weeklyPaymentAmount   = m.weekly_payment_amount    ?? m.assignment?.weekly_payment_amount;
      const weeklyPaymentDayLabel = m.weekly_payment_day_label ?? m.assignment?.weekly_payment_day_label;
      const alreadyPaidToday      = m.already_paid_today       ?? m.assignment?.already_paid_today;
      const assignmentId          = m.assignment_id            ?? m.assignment?.assignment_id;
      const totalWeeklyPaid       = m.total_weekly_paid        ?? 0;
      const advancePaid           = m.advance_amount           ?? 0;

      const todayJs = new Date().getDay();
      const todayPy = todayJs === 0 ? 6 : todayJs - 1;
      const weeklyDueToday = !isUpdown && weeklyPaymentDayValue === todayPy && !alreadyPaidToday;

      // ── GROSS & TRANSPORT ────────────────────────────────────────
      const totalGross = settlements.reduce(
        (acc: number, st: any) => acc + Number(st.gross_amount || 0), 0
      );
      const totalTransport = settlements.reduce(
        (acc: number, st: any) => acc + Number(st.transport_deducted || 0), 0
      );

      // ── DEPOSIT (permanent only) ─────────────────────────────────
      const isJobFullyDone = (st: any) => {
        const acts = st.activities || [];
        return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed');
      };
      const depositHeld = settlements
        .filter((st: any) => !isJobFullyDone(st))
        .reduce((acc: number, st: any) => acc + Number(st.deposit_held || 0), 0);

      const totalMisc = settlements.reduce(
        (acc: number, st: any) => acc + Number(st.total_misc || 0), 0
      );

      // ── SHOOT SELECTION CHECK (permanent only) ───────────────────
      const isShootSelectionDone = (st: any) => {
        const acts = st.activities || [];
        return acts.some((a: any) => {
          const name = (a.activity_name || '').toLowerCase();
          return ((name.includes('shoot') && name.includes('select')) ||
                 (a.activity_name || '').includes('विरळणी')) &&
                 a.work_status === 'completed';
        });
      };

      const netPayableOverall = isUpdown
        ? settlements
            .filter((st: any) => st.status === 'calculated')
            .reduce((acc: number, st: any) => acc + Number(st.net_payable || 0), 0)
        : settlements
            .filter((st: any) => st.status === 'calculated' && isShootSelectionDone(st))
            .reduce((acc: number, st: any) => acc + Number(st.net_payable || 0), 0);

      const jobsReadyToPay = isUpdown
        ? settlements.filter((st: any) => st.status === 'calculated' && Number(st.net_payable) > 0.01)
        : settlements.filter((st: any) => st.status === 'calculated' && Number(st.net_payable) > 0.01 && isShootSelectionDone(st));

      const staleSettlements = isUpdown
        ? []
        : settlements.filter((st: any) => st.status === 'calculated' && !isShootSelectionDone(st));

      const canPay = netPayableOverall > 0.01 && jobsReadyToPay.length > 0;
      const hasDue = canPay;

      return (
        <div key={expandKey} style={{ border: `1.5px solid ${hasDue ? '#fde68a' : '#e5e7eb'}`, borderRadius: '12px', background: '#fff', overflow: 'hidden' }}>

          {/* ── COLLAPSED HEADER ── */}
          <div onClick={() => setExpandedKey(isOpen ? null : expandKey)} style={{ padding: '12px 16px', cursor: 'pointer' }}>

            {/* Row 1: name + badges */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#111827' }}>{m.mukkadam_name}</span>
                  {isUpdown && (
                    <span style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px', fontWeight: 700, background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>
                      🚗 Updown
                    </span>
                  )}
                  {weeklyDueToday && (
                    <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef9c3', color: '#b45309' }}>📅 Weekly Due</span>
                  )}
                </div>
                <div style={{ fontSize: '0.66rem', color: '#6b7280', marginTop: '2px' }}>
                  📞 {m.mobile || m.mobile_numbers || '—'} · {m.crew_size} workers
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }} onClick={e => e.stopPropagation()}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.6rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Net Payable</div>
                  <div style={{ fontWeight: 800, fontSize: '1.1rem', color: canPay ? '#dc2626' : netPayableOverall < -0.01 ? '#16a34a' : '#6b7280' }}>
                    {canPay ? `₹${netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : netPayableOverall < -0.01 ? '✓ In Credit' : '—'}
                  </div>
                </div>
                {canPay && jobsReadyToPay.map((st: any) => (
                  <button key={st.job_id}
                    onClick={() => handleMukkadamPay(m.mukkadam_id, st.job_id, netPayableOverall, m.mukkadam_name)}
                    disabled={mukkadamPaying === `${m.mukkadam_id}-${st.job_id}`}
                    style={{ padding: '5px 10px', borderRadius: '7px', border: 'none', background: '#14b8a6', color: '#fff', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                    🏦 Pay ₹{netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </button>
                ))}
                {weeklyDueToday && (
                  <button onClick={() => handleAddWeeklyPayment(m.mukkadam_id, assignmentId, weeklyPaymentAmount, m.mukkadam_name)}
                    style={{ padding: '5px 10px', borderRadius: '7px', border: 'none', background: '#d97706', color: '#fff', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer' }}>
                    + Weekly ₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}
                  </button>
                )}
                {!isUpdown && missedWeekly.length > 0 && (
                  <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: '#fef2f2', color: '#dc2626' }}>
                    ⚠️ {missedWeekly.length} missed payment{missedWeekly.length > 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>

            {/* ── SUMMARY GRID ── */}
            {(() => {
              const totalPaidOut = settlements.reduce((acc: number, st: any) =>
                acc + (st.payments_made || []).reduce((s: number, p: any) => s + Number(p.amount), 0), 0);
              const totalNetPayable = settlements.reduce((acc: number, st: any) => acc + Number(st.net_payable || 0), 0);
              const remaining = totalNetPayable - totalPaidOut;

              const cells = isUpdown ? [
                { label: 'Gross Earned', val: `₹${totalGross.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,                                                         color: '#0f766e' },
                { label: '+ Transport',  val: totalTransport > 0 ? `+₹${totalTransport.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—',                         color: '#0369a1' },
                { label: 'Net Payable',  val: `₹${(totalGross + totalTransport).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,                                       color: '#dc2626' },
                { label: 'Paid Out',     val: totalPaidOut > 0 ? `−₹${totalPaidOut.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—',                             color: totalPaidOut > 0 ? '#16a34a' : '#9ca3af' },
                { label: 'Remaining',    val: remaining > 0.01 ? `₹${remaining.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '✓ Clear',                           color: remaining > 0.01 ? '#dc2626' : '#16a34a' },
              ] : [
                { label: 'Gross Earned',    val: `₹${totalGross.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,                                                      color: '#0f766e' },
                { label: '10% Deposit',     val: (() => {
                    const totalDeposit = settlements.reduce((acc: number, st: any) => acc + Number(st.deposit_held || 0), 0);
                    if (depositHeld <= 0 && totalDeposit > 0) return `✓ ₹${totalDeposit.toLocaleString('en-IN', { maximumFractionDigits: 0 })} released`;
                    if (depositHeld <= 0) return '—';
                    return `₹${depositHeld.toLocaleString('en-IN', { maximumFractionDigits: 0 })} held`;
                  })(),                                                                                                                                                        color: depositHeld > 0 ? '#b45309' : '#16a34a' },
                { label: 'Advance',         val: `−₹${Number(advancePaid).toLocaleString('en-IN')}`,                                                                         color: '#dc2626' },
                { label: 'Weekly Paid',     val: `−₹${Number(totalWeeklyPaid).toLocaleString('en-IN')}`,                                                                     color: '#dc2626' },
                { label: 'Settlement Paid', val: totalPaidOut > 0 ? `−₹${totalPaidOut.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—',                         color: totalPaidOut > 0 ? '#16a34a' : '#9ca3af' },
                { label: 'Remaining',       val: remaining > 0.01 ? `₹${remaining.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : remaining < -0.01 ? '✓ clear' : '✓ Clear', color: remaining > 0.01 ? '#dc2626' : '#16a34a' },
              ];

              return (
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cells.length}, 1fr)`, gap: '6px', marginTop: '10px', padding: '8px 10px', background: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                  {cells.map((item, i) => (
                    <div key={i} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '0.56rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginBottom: '2px' }}>{item.label}</div>
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: item.color }}>{item.val}</div>
                    </div>
                  ))}
                </div>
              );
            })()}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
              <span style={{ color: '#9ca3af', fontSize: '0.62rem' }}>{isOpen ? '▲' : '▼'} Details</span>
            </div>
          </div>

          {/* ── EXPANDED ── */}
          {isOpen && (
            <div style={{ borderTop: '1px solid #e5e7eb', padding: '14px 16px', background: '#fafafa', display: 'flex', flexDirection: 'column', gap: '12px' }}>

              {/* ── 1. OVERALL SETTLEMENT ── */}
              <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px' }}>
                <p style={{ margin: '0 0 10px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📊 Overall Settlement</p>
                <div style={{ fontSize: '0.76rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>

                  {settlements.map((st: any) => {
                    const stMeta = STATUS_META[st.status] || STATUS_META.pending;
                    const stTransport = Number(st.transport_deducted || 0);

                    const breakdownRows = isUpdown ? [
                      { label: 'Gross  (area × rate)', val: `₹${Number(st.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                      ...(stTransport > 0 ? [{ label: '+ Transport', val: `+₹${stTransport.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0369a1' }] : []),
                    ] : [
                      { label: 'Gross', val: `₹${Number(st.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' },
                      { label: (() => { const acts = st.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return allDone ? '+ 10% released ✓' : '− 10% deposit held'; })(), val: (() => { const acts = st.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return (allDone ? '+' : '−') + `₹${Number(st.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`; })(), color: (() => { const acts = st.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#16a34a' : '#b45309'; })() },
                      { label: '= 90% payable', val: `₹${Number(st.payable_90pct).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#1f2937' },
                      ...(st.deposit_carried_forward > 0  ? [{ label: '+ Deposit from prev job', val: `+₹${Number(st.deposit_carried_forward).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e' }] : []),
                      ...(st.credit_carried_forward > 0   ? [{ label: '− Credit to next job',    val: `−₹${Number(st.credit_carried_forward).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#6b7280' }] : []),
                      ...(st.advance_deducted > 0         ? [{ label: '− Advance (this job)',    val: `−₹${Number(st.advance_deducted).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,         color: '#dc2626' }] : []),
                      ...(st.weekly_payments_deducted > 0 ? [{ label: '− Weekly payments',      val: `−₹${Number(st.weekly_payments_deducted).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#dc2626' }] : []),
                      ...(st.total_misc > 0               ? [{ label: '− Misc costs',           val: `−₹${Number(st.total_misc).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,               color: '#dc2626' }] : []),
                    ];

                    return (
                      <div key={st.job_id} style={{ background: '#f9fafb', borderRadius: '6px', padding: '6px 10px', marginBottom: '2px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 700, color: '#374151', fontSize: '0.72rem' }}>#{st.job_id} {st.farmer_name}</span>
                          <span style={{ fontSize: '0.58rem', padding: '1px 6px', borderRadius: '999px', background: stMeta.bg, color: stMeta.text, fontWeight: 700 }}>{stMeta.label}</span>
                        </div>

                        {breakdownRows.map((row, ri) => (
                          <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', paddingBottom: '1px' }}>
                            <span style={{ color: '#9ca3af' }}>{row.label}</span>
                            <span style={{ fontWeight: 600, color: row.color }}>{row.val}</span>
                          </div>
                        ))}

                        <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e5e7eb', paddingTop: '3px', marginTop: '3px', fontSize: '0.72rem', fontWeight: 800 }}>
                          <span>Net</span>
                          <span style={{ color: Number(st.net_payable) > 0.01 ? '#dc2626' : '#6b7280' }}>
                            {Number(st.net_payable) > 0.01
                              ? `To Pay ₹${Number(st.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                              : st.status === 'no_payment_needed' ? 'Credit → carried forward' : '₹0'}
                          </span>
                        </div>

                        {(st.payments_made || []).length > 0 && (
                          <div style={{ marginTop: '4px', borderTop: '1px dashed #e5e7eb', paddingTop: '4px' }}>
                            {(st.payments_made || []).map((pay: any, pi: number) => (
                              <div key={pi} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.67rem', paddingBottom: '2px' }}>
                                <span style={{ color: '#6b7280' }}>
                                  ✅ Paid {pay.paid_at} · {pay.mode}
                                  {pay.notes ? ` · ${pay.notes}` : ''}
                                </span>
                                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{ fontWeight: 700, color: '#16a34a' }}>
                                    −₹{Number(pay.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                  </span>
                                  {pay.proof_url && (
                                    <a href={pay.proof_url} target="_blank" rel="noreferrer"
                                      style={{ fontSize: '0.6rem', color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 4px', background: '#eff6ff', textDecoration: 'none' }}>
                                      📎
                                    </a>
                                  )}
                                </span>
                              </div>
                            ))}
                            {Number(st.total_already_paid) > 0 && (
                              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e5e7eb', paddingTop: '3px', marginTop: '2px', fontSize: '0.72rem', fontWeight: 800 }}>
                                <span style={{ color: '#374151' }}>Remaining</span>
                                <span style={{ color: (Number(st.net_payable) - Number(st.total_already_paid)) > 0.01 ? '#dc2626' : '#16a34a' }}>
                                  {(Number(st.net_payable) - Number(st.total_already_paid)) > 0.01
                                    ? `₹${(Number(st.net_payable) - Number(st.total_already_paid)).toLocaleString('en-IN', { maximumFractionDigits: 0 })} still due`
                                    : `✓ Fully Paid`}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 10px', background: canPay ? '#fef2f2' : '#f0fdf4', borderRadius: '8px', border: `1px solid ${canPay ? '#fecaca' : '#bbf7d0'}`, fontWeight: 800, marginTop: '4px' }}>
                    <span style={{ color: '#111827', fontSize: '0.84rem' }}>Net Payable Now</span>
                    <span style={{ fontSize: '1rem', color: canPay ? '#dc2626' : '#16a34a' }}>
                      {canPay ? `₹${netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : `✓ ₹0`}
                    </span>
                  </div>

                  {!canPay && settlements.some((st: any) => st.status === 'no_payment_needed') && (
                    <p style={{ margin: '2px 0 0', fontSize: '0.64rem', color: '#16a34a' }}>✓ Credit from earlier jobs absorbed — no payment needed</p>
                  )}

                  {isUpdown && (
                    <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px' }}>
                      <p style={{ margin: '0 0 10px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>
                        🚜 All Allocations
                      </p>
                      {(m.updown_allocations || []).length === 0 ? (
                        <div style={{ fontSize: '0.74rem', color: '#9ca3af', textAlign: 'center', padding: '12px 0' }}>
                          No allocations assigned yet
                        </div>
                      ) : (m.updown_allocations || []).map((alloc: any) => {
                        const isCompleted = alloc.work_status === 'completed';
                        const isFuture    = alloc.allocated_date && alloc.allocated_date > new Date().toISOString().slice(0, 10);
                        const isPending   = !isCompleted;
                        const statusStyle =
                          isCompleted ? { bg: '#f0fdf4', border: '#bbf7d0', color: '#16a34a', label: '✓ Completed' } :
                          isFuture    ? { bg: '#eff6ff', border: '#bfdbfe', color: '#1d4ed8', label: '📅 Upcoming'  } :
                                        { bg: '#fef9c3', border: '#fde68a', color: '#b45309', label: '⏳ Pending'   };
                        const gross     = isCompleted && alloc.actual_gross     != null ? alloc.actual_gross     : alloc.gross_estimate;
                        const transport = isCompleted && alloc.actual_transport != null ? alloc.actual_transport : alloc.transport_estimate;
                        const net       = isCompleted && alloc.actual_net       != null ? alloc.actual_net       : alloc.net_estimate;
                        const isEstimate = !isCompleted;

                        return (
                          <div key={alloc.allocation_id} style={{ background: statusStyle.bg, border: `1px solid ${statusStyle.border}`, borderRadius: '8px', padding: '10px 12px', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                              <div>
                                <span style={{ fontWeight: 700, fontSize: '0.76rem', color: '#111827' }}>{alloc.activity_name}</span>
                                <span style={{ fontSize: '0.64rem', color: '#6b7280', marginLeft: '6px' }}>{alloc.plot_code} · {alloc.plot_name}</span>
                                <div style={{ fontSize: '0.62rem', color: '#6b7280', marginTop: '2px' }}>
                                  👨‍🌾 {alloc.farmer_name} · #{alloc.job_id}
                                  {alloc.allocated_date && ` · ${alloc.allocated_date}`}
                                </div>
                              </div>
                              <span style={{ fontSize: '0.58rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.border}`, whiteSpace: 'nowrap', marginLeft: '8px' }}>
                                {statusStyle.label}
                              </span>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: isPending ? '8px' : '0' }}>
                              {[
                                { label: isEstimate ? 'Gross (est.)' : 'Gross', val: `₹${Number(gross).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, sub: `${alloc.actual_area_done ?? alloc.allocated_area} ac × ₹${alloc.mukkadam_rate}`, color: '#0f766e', bg: '#f0fdf4' },
                                { label: isEstimate ? 'Transport (est.)' : 'Transport', val: Number(transport) > 0 ? `+₹${Number(transport).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—', sub: Number(transport) > 0 ? 'from assignment' : 'not applicable', color: '#0369a1', bg: '#eff6ff' },
                                { label: isEstimate ? 'Net (est.)' : 'Net Payable', val: `₹${Number(net).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, sub: isEstimate ? 'estimate' : alloc.settlement_status || '', color: isCompleted ? '#16a34a' : '#dc2626', bg: isCompleted ? '#f0fdf4' : '#fff7ed' },
                              ].map((cell, ci) => (
                                <div key={ci} style={{ background: cell.bg, borderRadius: '6px', padding: '5px 8px', textAlign: 'center' }}>
                                  <div style={{ fontSize: '0.54rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', marginBottom: '1px' }}>{cell.label}</div>
                                  <div style={{ fontSize: '0.76rem', fontWeight: 800, color: cell.color }}>{cell.val}</div>
                                  <div style={{ fontSize: '0.54rem', color: '#9ca3af', marginTop: '1px' }}>{cell.sub}</div>
                                </div>
                              ))}
                            </div>
                            {isPending && (
                              <button onClick={() => handleUpdownComplete(m.mukkadam_id, alloc.allocation_id)}
                                style={{ width: '100%', padding: '7px', borderRadius: '7px', border: 'none', background: '#14b8a6', color: '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}>
                                ✓ Mark Complete &amp; Generate Bill
                              </button>
                            )}
                            {isCompleted && (
                              <div style={{ fontSize: '0.62rem', color: '#6b7280', marginTop: '4px' }}>
                                {alloc.actual_crew_size && `👥 ${alloc.actual_crew_size} workers · `}
                                {alloc.actual_area_done != null ? `${alloc.actual_area_done} ac done` : `${alloc.allocated_area} ac (planned)`}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {!isUpdown && staleSettlements.length > 0 && (
                    <div style={{ marginTop: '6px', background: '#fef9c3', border: '1px solid #fde047', borderRadius: '7px', padding: '8px 12px' }}>
                      <p style={{ margin: '0 0 4px', fontSize: '0.64rem', fontWeight: 700, color: '#854d0e', textTransform: 'uppercase' }}>⚠️ Stale Settlement Detected</p>
                      {staleSettlements.map((st: any) => (
                        <div key={st.job_id} style={{ fontSize: '0.68rem', color: '#713f12' }}>
                          Job #{st.job_id} ({st.farmer_name}) — settlement shows ₹{Number(st.net_payable).toLocaleString('en-IN')} but shoot selection is NOT completed.
                        </div>
                      ))}
                      <p style={{ margin: '4px 0 0', fontSize: '0.64rem', color: '#854d0e' }}>
                        👉 Go to Django Admin → MukkadamJobSettlement → reset status to 'pending' for these jobs, then recalculate when shoot selection is done.
                      </p>
                    </div>
                  )}

                  {canPay && jobsReadyToPay.map((st: any) => (
                    <button key={st.job_id}
                      onClick={() => handleMukkadamPay(m.mukkadam_id, st.job_id, netPayableOverall, m.mukkadam_name)}
                      disabled={mukkadamPaying === `${m.mukkadam_id}-${st.job_id}`}
                      style={{ width: '100%', marginTop: '4px', padding: '10px', borderRadius: '8px', border: 'none', background: '#14b8a6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}>
                      🏦 Pay ₹{netPayableOverall.toLocaleString('en-IN', { maximumFractionDigits: 0 })} to {m.mukkadam_name}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── 2. WEEK-WISE LEDGER — permanent only ── */}
              {!isUpdown && (() => {
                const ledger: any[]      = m.week_ledger  || [];
                const pendingWork: any[] = m.pending_work || [];

                if (ledger.length === 0 && pendingWork.length === 0) return (
                  <div style={{ padding: '10px 14px', background: '#f9fafb', borderRadius: '8px', fontSize: '0.72rem', color: '#9ca3af', textAlign: 'center' }}>
                    No weekly payments recorded yet
                  </div>
                );

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <p style={{ margin: '0 0 4px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 Week-wise Running Ledger</p>
                    {ledger.map((row: any, ri: number) => {
                      const isAdvance  = row.type === 'advance';
                      const isPositive = row.running_balance >= 0;
                      const events: any[] = row.billing_events || [];
                      return (
                        <div key={ri} style={{ background: '#fff', borderRadius: '8px', border: `1px solid ${row.can_pay ? '#fde68a' : isAdvance ? '#fecaca' : '#e5e7eb'}`, overflow: 'hidden' }}>
                          <div style={{ background: isAdvance ? '#fef2f2' : '#f9fafb', padding: '7px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: events.length > 0 || pendingWork.length > 0 ? '1px solid #e5e7eb' : 'none' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              {isAdvance ? (
                                <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#dc2626' }}>💰 Advance Given</span>
                              ) : (
                                <>
                                  <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#374151' }}>Week {row.week_num} · {row.payment_date}</span>
                                  <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', background: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>
                                    Weekly −₹{Number(row.weekly_paid).toLocaleString('en-IN')}
                                  </span>
                                  {row.weekly_proof_url && (
                                    <a href={row.weekly_proof_url} target="_blank" rel="noreferrer"
                                      style={{ fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 4px', background: '#eff6ff' }}>📎</a>
                                  )}
                                  {row.payable_this_week > 0 && (
                                    <span style={{ fontSize: '0.6rem', padding: '1px 7px', borderRadius: '999px', background: '#f0fdf4', color: '#16a34a', fontWeight: 600 }}>
                                      +₹{Number(row.payable_this_week).toLocaleString('en-IN')} earned
                                    </span>
                                  )}
                                </>
                              )}
                            </div>
                            <div style={{ textAlign: 'right', minWidth: '80px' }}>
                              <div style={{ fontSize: '0.56rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Running</div>
                              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isAdvance ? '#dc2626' : isPositive ? '#16a34a' : '#dc2626' }}>
                                {row.running_balance >= 0 ? '+' : ''}₹{Number(row.running_balance).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </div>
                              {row.can_pay && <div style={{ fontSize: '0.58rem', color: '#b45309', fontWeight: 700 }}>⚡ PAY NOW</div>}
                            </div>
                          </div>
                          {events.length > 0 && (
                            <div style={{ padding: '6px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {events.map((ev: any, ei: number) => (
                                <div key={ei} style={{ background: ev.type === 'shoot_billing' ? '#f0fdf4' : ev.type === 'deposit_release' ? '#eff6ff' : '#f9fafb', border: `1px solid ${ev.type === 'shoot_billing' ? '#bbf7d0' : ev.type === 'deposit_release' ? '#bfdbfe' : '#e5e7eb'}`, borderRadius: '6px', padding: '6px 10px' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: ev.activities?.length > 0 ? '5px' : '0' }}>
                                    <div>
                                      <span style={{ fontSize: '0.64rem', fontWeight: 700, color: ev.type === 'shoot_billing' ? '#16a34a' : '#1d4ed8' }}>
                                        {ev.type === 'shoot_billing' ? '🌱 Shoot Selection Billed' : '✓ Deposit Released'}
                                      </span>
                                      <span style={{ fontSize: '0.62rem', color: '#6b7280', marginLeft: '6px' }}>{ev.farmer_name} · #{ev.job_id}</span>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                      <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#16a34a' }}>+₹{Number(ev.payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                                      {ev.deposit_held > 0 && <div style={{ fontSize: '0.6rem', color: '#b45309' }}>10% held ₹{Number(ev.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>}
                                      {ev.deposit_released > 0 && <div style={{ fontSize: '0.6rem', color: '#1d4ed8' }}>₹{Number(ev.deposit_released).toLocaleString('en-IN', { maximumFractionDigits: 0 })} released</div>}
                                    </div>
                                  </div>
                                  {ev.activities?.length > 0 && (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.64rem' }}>
                                      <thead>
                                        <tr>
                                          {['Activity', 'Area', 'Rate', 'Amount'].map(h => (
                                            <th key={h} style={{ padding: '2px 4px', textAlign: ['Area','Rate','Amount'].includes(h) ? 'right' : 'left', color: '#9ca3af', fontWeight: 600, borderBottom: '1px solid #f3f4f6' }}>{h}</th>
                                          ))}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {ev.activities.map((act: any, ai: number) => (
                                          <tr key={ai}>
                                            <td style={{ padding: '2px 4px', color: '#374151' }}>{act.activity_name}</td>
                                            <td style={{ padding: '2px 4px', textAlign: 'right', color: '#6b7280' }}>{Number(act.area).toFixed(2)}</td>
                                            <td style={{ padding: '2px 4px', textAlign: 'right', color: '#6b7280' }}>₹{Number(act.rate).toLocaleString('en-IN')}</td>
                                            <td style={{ padding: '2px 4px', textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>₹{Number(act.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {pendingWork.length > 0 && (
                      <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '8px 12px' }}>
                        <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#b45309', textTransform: 'uppercase' }}>⏳ Work Done — Shoot Selection Pending</p>
                        {pendingWork.map((pw: any, pi: number) => (
                          <div key={pi} style={{ marginBottom: pi < pendingWork.length - 1 ? '6px' : '0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', marginBottom: '3px' }}>
                              <span style={{ fontWeight: 700, color: '#374151' }}>{pw.farmer_name} · #{pw.job_id}</span>
                              <span style={{ color: '#9ca3af' }}>₹{Number(pw.gross_so_far).toLocaleString('en-IN', { maximumFractionDigits: 0 })} earned (not yet payable)</span>
                            </div>
                            {pw.activities?.map((act: any, ai: number) => (
                              <div key={ai} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.64rem', color: '#6b7280', paddingLeft: '8px' }}>
                                <span>{act.activity_name}</span>
                                <span>{Number(act.area).toFixed(2)} ac × ₹{Number(act.rate).toLocaleString('en-IN')} = ₹{Number(act.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* ── 3. TRANSACTION HISTORY ── */}
              {(() => {
                const txns: any[] = m.transaction_history || [];
                if (txns.length === 0) return null;
                const colorMap: any = {
                  advance:            { bg: '#fef2f2', border: '#fecaca', text: '#dc2626', icon: '💰' },
                  weekly:             { bg: '#fff7ed', border: '#fed7aa', text: '#ea580c', icon: '📅' },
                  settlement_payment: { bg: '#f0fdf4', border: '#bbf7d0', text: '#16a34a', icon: '✅' },
                  misc_deduction:     { bg: '#faf5ff', border: '#e9d5ff', text: '#7c3aed', icon: '⚠️' },
                };
                return (
                  <div style={{ marginBottom: '4px' }}>
                    <p style={{ margin: '0 0 6px', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>🧾 Transaction History</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {txns.map((txn: any, ti: number) => {
                        const c = colorMap[txn.type] || colorMap.weekly;
                        const isCredit = txn.amount > 0;
                        return (
                          <div key={ti} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: '8px', padding: '7px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ minWidth: '56px', textAlign: 'center' }}>
                              <div style={{ fontSize: '1rem' }}>{c.icon}</div>
                              <div style={{ fontSize: '0.58rem', color: '#9ca3af', fontWeight: 600 }}>{txn.date?.slice(5)}</div>
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1f2937', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{txn.label}</div>
                              {txn.mode && txn.mode !== '—' && (
                                <div style={{ fontSize: '0.6rem', color: '#6b7280' }}>{txn.mode}{txn.notes ? ` · ${txn.notes}` : ''}</div>
                              )}
                            </div>
                            <div style={{ textAlign: 'right', minWidth: '80px' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isCredit ? '#16a34a' : '#dc2626' }}>
                                {isCredit ? '+' : ''}₹{Math.abs(txn.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </div>
                              <div style={{ fontSize: '0.58rem', color: txn.running_balance >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                                Bal: {txn.running_balance >= 0 ? '+' : ''}₹{txn.running_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </div>
                            </div>
                            {txn.proof_url && (
                              <a href={txn.proof_url} target="_blank" rel="noreferrer"
                                style={{ fontSize: '0.6rem', color: '#3b82f6', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '2px 6px', background: '#eff6ff', whiteSpace: 'nowrap', textDecoration: 'none' }}>📎</a>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* ── 4. PER-JOB CARDS ── */}
              <p style={{ margin: '4px 0 0', fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>🌾 Job Details</p>
              {settlements.length === 0 ? (
                <p style={{ fontSize: '0.78rem', color: '#9ca3af', margin: 0 }}>No settlements yet</p>
              ) : settlements.map((s: any) => {
                const sm = STATUS_META[s.status] || STATUS_META.pending;
                const stTransport = Number(s.transport_deducted || 0);
                return (
                  <div key={s.job_id} style={{ background: '#fff', borderRadius: '10px', border: `1px solid ${s.status === 'calculated' ? '#fde68a' : s.status === 'paid' ? '#bbf7d0' : '#e5e7eb'}`, padding: '12px 14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                      <div>
                        <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1d4ed8', fontSize: '0.8rem' }}>#{s.job_id}</span>
                        <span style={{ marginLeft: '8px', fontSize: '0.8rem', color: '#374151', fontWeight: 700 }}>{s.farmer_name}</span>
                        <div style={{ marginTop: '3px', display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.66rem', color: '#6b7280' }}>
                          <span>{s.job_title?.split('—')[0]?.trim()}</span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '3px' }}>
                        <span style={{ fontSize: '0.64rem', padding: '2px 8px', borderRadius: '999px', fontWeight: 700, background: sm.bg, color: sm.text }}>{sm.label}</span>
                        {s.status === 'paid' && s.proof_url && (
                          <a href={s.proof_url} target="_blank" rel="noreferrer"
                            style={{ fontSize: '0.6rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0 5px', background: '#eff6ff' }}>📎 Payment proof</a>
                        )}
                      </div>
                    </div>

                    {isUpdown ? (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '10px' }}>
                        {[
                          { label: 'Gross Earned', val: `₹${Number(s.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e', bg: '#f0fdf4' },
                          { label: '+ Transport',  val: stTransport > 0 ? `+₹${stTransport.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '₹0', color: '#0369a1', bg: '#eff6ff' },
                        ].map((item, i) => (
                          <div key={i} style={{ background: item.bg, borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.58rem', color: '#6b7280', marginBottom: '2px', fontWeight: 600 }}>{item.label}</div>
                            <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.color }}>{item.val}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: '10px' }}>
                        {[
                          { label: 'Gross Earned', val: `₹${Number(s.gross_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#0f766e', bg: '#f0fdf4' },
                          { label: (() => { const acts = s.activities || []; const allDone = acts.length > 0 && acts.every((a: any) => a.work_status === 'completed'); return allDone ? '10% Released ✓' : '10% Held'; })(), val: `₹${Number(s.deposit_held).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: (() => { const acts = s.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#16a34a' : '#b45309'; })(), bg: (() => { const acts = s.activities || []; return acts.length > 0 && acts.every((a: any) => a.work_status === 'completed') ? '#f0fdf4' : '#fffbeb'; })() },
                          { label: '90% Payable', val: `₹${Number(s.payable_90pct).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`, color: '#1d4ed8', bg: '#eff6ff' },
                        ].map((item, i) => (
                          <div key={i} style={{ background: item.bg, borderRadius: '6px', padding: '6px 8px', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.58rem', color: '#6b7280', marginBottom: '2px', fontWeight: 600 }}>{item.label}</div>
                            <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.color }}>{item.val}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div style={{ border: '1px solid #e5e7eb', borderRadius: '7px', overflow: 'hidden', marginBottom: '8px' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.68rem' }}>
                        <thead>
                          <tr style={{ background: '#f9fafb' }}>
                            {['Activity', 'Plot', 'Date', 'Planned', 'Claimed', 'Crew', 'Rate', 'Earned', 'Status'].map(h => (
                              <th key={h} style={{ padding: '4px 6px', textAlign: ['Planned','Claimed','Crew','Rate','Earned'].includes(h) ? 'right' : 'left', color: '#6b7280', fontWeight: 600, fontSize: '0.6rem', borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(s.activities || []).map((act: any, idx: number) => {
                            const claimed = act.mukkadam_claimed_area ?? act.actual_area_done;
                            const billing = act.admin_override_area ?? (act.use_actual_for_settlement && claimed != null ? claimed : act.allocated_area);
                            const billAmt = act.billing_locked ? 0 : billing * act.mukkadam_rate;
                            const diff    = claimed != null ? (claimed - act.allocated_area) : 0;
                            return (
                              <tr key={idx} style={{ borderTop: idx > 0 ? '1px solid #f3f4f6' : 'none', background: act.billing_locked ? '#fff5f5' : 'transparent' }}>
                                <td style={{ padding: '5px 6px', fontWeight: 600, color: '#111827' }}>
                                  {act.activity_name}
                                  {act.is_carry_forward && <span style={{ fontSize: '0.56rem', color: '#b45309', marginLeft: '2px' }}>↩</span>}
                                </td>
                                <td style={{ padding: '5px 6px', color: '#6b7280', fontFamily: 'monospace', fontSize: '0.62rem' }}>{act.plot_code}</td>
                                <td style={{ padding: '5px 6px', color: '#6b7280', whiteSpace: 'nowrap' }}>{act.allocated_date?.slice(5) || act.scheduled_date?.slice(5) || '—'}</td>
                                <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>{Number(act.allocated_area).toFixed(2)}</td>
                                <td style={{ padding: '5px 6px', textAlign: 'right' }}>
                                  {claimed != null ? (
                                    <span style={{ fontWeight: 700, color: diff < 0 ? '#dc2626' : diff > 0 ? '#0f766e' : '#374151' }}>
                                      {Number(claimed).toFixed(2)}
                                      {diff !== 0 && <span style={{ fontSize: '0.56rem', marginLeft: '2px' }}>({diff > 0 ? '+' : ''}{diff.toFixed(2)})</span>}
                                    </span>
                                  ) : <span style={{ color: '#9ca3af' }}>—</span>}
                                </td>
                                <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>{act.actual_crew_size ?? act.allocated_workers}</td>
                                <td style={{ padding: '5px 6px', textAlign: 'right', color: '#6b7280' }}>₹{Number(act.mukkadam_rate).toLocaleString('en-IN')}</td>
                                <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: act.billing_locked ? '#9ca3af' : '#0f766e' }}>
                                  {act.billing_locked ? '🔒' : `₹${Number(billAmt).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                                </td>
                                <td style={{ padding: '5px 6px' }}>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', alignItems: 'center' }}>
                                    <WorkStatusBadge status={act.work_status || 'work_not_started'} />
                                    <PaymentStatusBadge status={act.payment_status || 'pending'} />
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                          <tr style={{ borderTop: '2px solid #e5e7eb', background: isUpdown ? '#eff6ff' : '#f0fdfa' }}>
                            <td colSpan={3} style={{ padding: '5px 6px', fontWeight: 700, fontSize: '0.68rem' }}>Total</td>
                            <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: '#6b7280' }}>
                              {(s.activities || []).reduce((t: number, a: any) => t + Number(a.allocated_area), 0).toFixed(2)}
                            </td>
                            <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700 }}>
                              {(s.activities || []).some((a: any) => (a.mukkadam_claimed_area ?? a.actual_area_done) != null)
                                ? (s.activities || []).reduce((t: number, a: any) => t + Number(a.mukkadam_claimed_area ?? a.actual_area_done ?? a.allocated_area), 0).toFixed(2)
                                : '—'}
                            </td>
                            <td colSpan={2} />
                            <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 800, color: '#0f766e' }}>
                              ₹{s.gross_amount.toLocaleString('en-IN')}
                            </td>
                            <td />
                          </tr>
                          {isUpdown && stTransport > 0 && (
                            <tr style={{ background: '#eff6ff' }}>
                              <td colSpan={7} style={{ padding: '5px 6px', fontWeight: 700, fontSize: '0.68rem', color: '#0369a1' }}>🚗 Transport</td>
                              <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 800, color: '#0369a1' }}>
                                +₹{stTransport.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </td>
                              <td />
                            </tr>
                          )}
                          {isUpdown && (
                            <tr style={{ background: '#f0fdf4', borderTop: '2px solid #e5e7eb' }}>
                              <td colSpan={7} style={{ padding: '5px 6px', fontWeight: 800, fontSize: '0.7rem', color: '#0f766e' }}>= Net Payable</td>
                              <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 800, color: '#dc2626' }}>
                                ₹{Number(s.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </td>
                              <td />
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>

                    <MiscCostsSection
                      mukkadamId={m.mukkadam_id}
                      jobId={s.job_id}
                      initialCosts={s.misc_costs || []}
                      onCostChange={fetchData}
                    />

                    {s.status === 'paid' && (
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 14px', marginTop: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '0.62rem', color: '#16a34a', fontWeight: 700, textTransform: 'uppercase', marginBottom: '2px' }}>✓ Settlement Paid</div>
                            <div style={{ fontSize: '0.72rem', color: '#374151' }}>on {s.paid_at || '—'}</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '1rem', fontWeight: 800, color: '#16a34a' }}>₹{Number(s.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                            {s.proof_url && (
                              <a href={s.proof_url} target="_blank" rel="noreferrer"
                                style={{ fontSize: '0.62rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '1px 7px', background: '#eff6ff', display: 'inline-block', marginTop: '2px' }}>
                                📎 View Proof
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {/* ── Weekly payment section — permanent only ── */}
              {!isUpdown && weeklyDueToday && (
                <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 12px' }}>
                  <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#92400e', textTransform: 'uppercase' }}>📅 Weekly Payment Due Today</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}</span>
                      <span style={{ color: '#6b7280', fontSize: '0.7rem', marginLeft: 6 }}>{m.crew_size} workers · {weeklyPaymentDayLabel}</span>
                    </div>
                    <button onClick={() => handleAddWeeklyPayment(m.mukkadam_id, assignmentId, weeklyPaymentAmount, m.mukkadam_name)}
                      style={{ background: '#d97706', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', fontWeight: 700, cursor: 'pointer', fontSize: '0.74rem' }}>
                      + Add Payment
                    </button>
                  </div>
                </div>
              )}

              {!isUpdown && alreadyPaidToday && (
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 12px', fontSize: '0.74rem', color: '#16a34a', fontWeight: 700 }}>
                  ✓ Weekly payment already added today
                </div>
              )}

              {!isUpdown && missedWeekly.length > 0 && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '10px 12px' }}>
                  <p style={{ margin: '0 0 8px', fontSize: '0.64rem', fontWeight: 700, color: '#dc2626', textTransform: 'uppercase' }}>
                    ⚠️ Missed Weekly Payments
                  </p>
                  {missedWeekly.map((missedDate: string) => (
                    <div key={missedDate} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div>
                        <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>₹{Number(weeklyPaymentAmount).toLocaleString('en-IN')}</span>
                        <span style={{ color: '#9ca3af', fontSize: '0.68rem', marginLeft: 6 }}>was due on {missedDate}</span>
                        <span style={{ marginLeft: 6, fontSize: '0.6rem', padding: '1px 6px', borderRadius: '999px', background: '#fef2f2', color: '#dc2626', fontWeight: 700 }}>Late</span>
                      </div>
                      <button
                        onClick={() => setWeeklyModal({ mukkadamId: m.mukkadam_id, assignmentId: assignmentId, amount: weeklyPaymentAmount, name: m.mukkadam_name, paymentDate: missedDate })}
                        style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: 6, padding: '5px 12px', fontWeight: 700, cursor: 'pointer', fontSize: '0.72rem' }}>
                        Pay Now (Late)
                      </button>
                    </div>
                  ))}
                </div>
              )}

            </div>
          )}
        </div>
      );
    })}
  </div>
)}
      </div>


      {/* ── Farmer Bill Detail + Webhook Modal ── */}
{detailModal && (
  <div
    style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
    onClick={() => { setDetailModal(null); setWebhookSent(false); }}
  >
    <div
      style={{ background: '#fff', borderRadius: '16px', width: '460px', maxHeight: '88vh', overflowY: 'auto', boxShadow: '0 24px 60px rgba(0,0,0,0.25)' }}
      onClick={e => e.stopPropagation()}
    >
      {/* Header */}
      <div style={{ padding: '20px 24px 14px', borderBottom: '1px solid #e5e7eb' }}>
        <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>🧾 Bill Details</h3>
        <p style={{ margin: 0, fontSize: '0.75rem', color: '#6b7280' }}>
          <strong>{detailModal.farmerName}</strong> · {detailModal.phone} · Job #{detailModal.jobId}
        </p>
      </div>

      <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>

        {/* Crop + Plot + Mukkadam */}
        <div style={{ background: '#f9fafb', borderRadius: '10px', padding: '12px 14px', fontSize: '0.76rem', display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>Crop</span>
            <span style={{ fontWeight: 700, color: '#111827' }}>{detailModal.cropName}{detailModal.plotName ? ` · ${detailModal.plotName}` : ''}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>Mukkadam</span>
            <span style={{ fontWeight: 700, color: '#1d4ed8' }}>{detailModal.mukkadamName || '—'}{detailModal.mukkadamMobile ? ` · ${detailModal.mukkadamMobile}` : ''}</span>
          </div>
        </div>

        {/* Activities breakdown */}
        <div>
          <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📋 Work Done</p>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.68rem' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  {['Activity', 'Date', 'Acres', 'Rate/ac', 'Amount'].map(h => (
                    <th key={h} style={{ padding: '5px 8px', textAlign: ['Acres','Rate/ac','Amount'].includes(h) ? 'right' : 'left', color: '#6b7280', fontWeight: 600, borderBottom: '1px solid #e5e7eb' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detailModal.activities.filter((act: any) => {
  const area = act.admin_override_area ?? act.mukkadam_claimed_area ?? act.actual_area_done ?? act.allocated_area;
  const rate = act.rate_per_acre ?? act.mukkadam_rate ?? 0;
  return Number(area) * Number(rate) > 0;
}).map((act: any, i: number) => {
                  const area = act.admin_override_area ?? act.mukkadam_claimed_area ?? act.actual_area_done ?? act.allocated_area;
                  const rate = act.rate_per_acre ?? act.mukkadam_rate ?? 0;
                  const amt  = Number(area) * Number(rate);
                  return (
                    <tr key={i} style={{ borderTop: i > 0 ? '1px solid #f3f4f6' : 'none' }}>
                      <td style={{ padding: '5px 8px', color: '#111827', fontWeight: 600 }}>{act.activity_name}</td>
                      <td style={{ padding: '5px 8px', color: '#6b7280' }}>
  {(act.allocated_date || act.scheduled_date)?.slice(5) || '—'}
</td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', color: '#374151', fontWeight: 700 }}>{Number(area).toFixed(2)}</td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', color: '#6b7280' }}>₹{Number(rate).toLocaleString('en-IN')}</td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>₹{amt.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Payment history */}
        <div>
          <p style={{ margin: '0 0 6px', fontSize: '0.64rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>📅 Payments Already Made</p>
          {detailModal.paymentHistory.length === 0 ? (
            <p style={{ fontSize: '0.74rem', color: '#9ca3af', margin: 0 }}>No payments recorded yet</p>
          ) : (
            <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
              {detailModal.paymentHistory.map((p: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 12px', borderTop: i > 0 ? '1px solid #f3f4f6' : 'none', fontSize: '0.72rem' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ background: '#eff6ff', color: '#1d4ed8', padding: '1px 7px', borderRadius: '999px', fontSize: '0.62rem', fontWeight: 600 }}>{p.mode}</span>
                    <span style={{ color: '#6b7280' }}>{p.date}</span>
                    {p.notes && <span style={{ color: '#9ca3af' }}>· {p.notes}</span>}
                  </div>
                  <span style={{ fontWeight: 700, color: '#16a34a' }}>₹{Number(p.amount).toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bill summary */}
        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '10px', padding: '12px 14px', fontSize: '0.76rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>Total Billed So Far</span>
            <span style={{ fontWeight: 700, color: '#0f766e' }}>₹{detailModal.totalBilled.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>Already Collected</span>
            <span style={{ fontWeight: 700, color: '#16a34a' }}>−₹{detailModal.totalPaid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1.5px solid #fed7aa', paddingTop: '6px', marginTop: '2px' }}>
            <span style={{ fontWeight: 800, color: '#111827', fontSize: '0.84rem' }}>Balance Due Now</span>
            <span style={{ fontWeight: 800, color: '#dc2626', fontSize: '1rem' }}>₹{detailModal.balanceDue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          </div>
        </div>

        {/* Action buttons */}
        {webhookSent ? (
          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '14px', textAlign: 'center' }}>
            <p style={{ margin: 0, fontWeight: 700, color: '#16a34a', fontSize: '0.88rem' }}>✅ Bill details sent successfully</p>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => { setDetailModal(null); setWebhookSent(false); }}
              style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              onClick={async () => {
                setWebhookSending(true);
                try {

                  const authToken = localStorage.getItem('auth_token') || localStorage.getItem('token') || '';

                  const res = await fetch(`${API_BASE_URL}/api/farmer-bill/send-webhook/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' ,'Authorization': `Token ${authToken}`,},
  body: JSON.stringify({
    event: 'farmer_bill_collect_initiated',
    timestamp: new Date().toISOString(),
    farmer: {
      id:    detailModal.farmerId,
      name:  detailModal.farmerName,
      phone: detailModal.phone,
    },
    job: {
      id:   detailModal.jobId,
      crop: detailModal.cropName,
      plot: detailModal.plotName,
    },
    mukkadam: {
      name:   detailModal.mukkadamName,
      mobile: detailModal.mukkadamMobile,
    },
    work_done: detailModal.activities.map((act: any) => {
      const area = act.admin_override_area ?? act.mukkadam_claimed_area ?? act.actual_area_done ?? act.allocated_area;
      const rate = act.rate_per_acre ?? act.mukkadam_rate ?? 0;
      return {
        activity:      act.activity_name,
        date:          act.allocated_date || act.scheduled_date,
        acres_done:    Number(area).toFixed(2),
        rate_per_acre: Number(rate),
        amount:        Number((Number(area) * Number(rate)).toFixed(0)),
      };
    }),
    payment_history: detailModal.paymentHistory.map((p: any) => ({
      date:   p.date,
      amount: Number(p.amount),
      mode:   p.mode,
      notes:  p.notes || '',
    })),
    bill_summary: {
      total_billed:       detailModal.totalBilled,
      total_already_paid: detailModal.totalPaid,
      balance_due_now:    detailModal.balanceDue,
      why_this_bill:      `Balance of ₹${detailModal.balanceDue.toLocaleString('en-IN')} remaining after ₹${detailModal.totalPaid.toLocaleString('en-IN')} collected against total billing of ₹${detailModal.totalBilled.toLocaleString('en-IN')} for ${detailModal.activities.length} activity/activities done by mukkadam ${detailModal.mukkadamName} on job #${detailModal.jobId}`,
    },
  }),
});

if (!res.ok) {
  const err = await res.json();
  throw new Error(err.error || 'Failed');
}
                  setWebhookSent(true);
                  fetchData();
                } catch (e) {
                  alert('❌ Failed to send. Check webhook URL.');
                } finally {
                  setWebhookSending(false);
                }
              }}
              disabled={webhookSending}
              style={{
                flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                background: webhookSending ? '#93c5fd' : '#3b82f6',
                color: '#fff', fontWeight: 700, fontSize: '0.85rem',
                cursor: webhookSending ? 'not-allowed' : 'pointer',
              }}
            >
              {webhookSending ? 'Sending...' : `📤 Confirm & Send Bill Details`}
            </button>
          </div>
        )}
      </div>
    </div>
  </div>
)}

      {/* {payModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setPayModal(null); setProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '420px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 60px rgba(0,0,0,0.25)' }}
            onClick={e => e.stopPropagation()}>

            
            <div style={{ padding: '20px 24px 0' }}>
              <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>💰 Collect Payment</h3>
              <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
                From <strong>{payModal.farmerName}</strong> · Job #{payModal.jobId}
              </p>
            </div>

            {(payModal.existingPayments || []).filter((p: any) => p.type !== 'advance').length > 0 && (
              <div style={{ margin: '0 24px 14px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '10px 12px' }}>
                <p style={{ margin: '0 0 8px', fontSize: '0.62rem', fontWeight: 700, color: '#16a34a', textTransform: 'uppercase' }}>✓ Already Collected</p>
                {(payModal.existingPayments || []).filter((p: any) => p.type !== 'advance').map((p: any, i: number) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '6px', marginBottom: i < (payModal.existingPayments || []).filter((x:any)=>x.type!=='advance').length - 1 ? '6px' : 0, borderBottom: i < (payModal.existingPayments || []).filter((x:any)=>x.type!=='advance').length - 1 ? '1px solid #dcfce7' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px', background: '#dcfce7', color: '#16a34a', fontWeight: 600 }}>{p.mode}</span>
                      <span style={{ fontSize: '0.68rem', color: '#6b7280' }}>{p.date}</span>
                      {p.notes && <span style={{ fontSize: '0.62rem', color: '#9ca3af' }}>· {p.notes}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontWeight: 700, color: '#16a34a', fontSize: '0.82rem' }}>₹{Number(p.amount).toLocaleString('en-IN')}</span>
                      {p.proof_url && (
                        <a href={p.proof_url} target="_blank" rel="noreferrer"
                          style={{ fontSize: '0.62rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '4px', padding: '1px 6px', background: '#eff6ff' }}>
                          📎 View
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            
            <div style={{ padding: '0 24px 20px' }}>
              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Amount (₹)</label>
              <input type="number" value={payAmount} onChange={e => setPayAmount(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '1.1rem', fontWeight: 700, marginBottom: '10px', boxSizing: 'border-box' }} />

              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
              <select value={payMode} onChange={e => setPayMode(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
                {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                  <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
                ))}
              </select>

              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
              <input value={payNotes} onChange={e => setPayNotes(e.target.value)} placeholder="e.g. UPI ref 12345"
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />

              <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
                Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
                <span style={{ color: '#9ca3af', fontWeight: 400 }}> (screenshot / receipt / photo)</span>
              </label>
              {proofFile ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                  {proofFile.type.startsWith('image/') && (
                    <img src={URL.createObjectURL(proofFile)} alt="proof"
                      style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px', border: '1px solid #e5e7eb' }} />
                  )}
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <p style={{ margin: 0, fontSize: '0.74rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {proofFile.name}</p>
                    <p style={{ margin: 0, fontSize: '0.62rem', color: '#9ca3af' }}>{(proofFile.size / 1024).toFixed(0)} KB</p>
                  </div>
                  <button onClick={() => setProofFile(null)}
                    style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700, padding: '0 4px' }}>✕</button>
                </div>
              ) : (
                <label style={{ display: 'block', padding: '14px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                  <input type="file" accept="image/*,application/pdf" onChange={e => setProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                  <p style={{ margin: '0 0 2px', fontSize: '0.8rem', color: '#374151' }}>📷 Tap to attach proof</p>
                  <p style={{ margin: 0, fontSize: '0.66rem', color: '#9ca3af' }}>UPI screenshot, cheque photo, bank receipt</p>
                </label>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => { setPayModal(null); setProofFile(null); }}
                  style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>
                  Cancel
                </button>
                <button onClick={handleFarmerPay}
                  disabled={payLoading || proofUploading || !proofFile || !payAmount}
                  style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                    background: (!proofFile || !payAmount) ? '#d1d5db' : proofUploading ? '#fbbf24' : payLoading ? '#93c5fd' : '#3b82f6',
                    color: '#fff', fontWeight: 700, fontSize: '0.85rem',
                    cursor: (!proofFile || !payAmount || payLoading || proofUploading) ? 'not-allowed' : 'pointer' }}>
                  {proofUploading ? '⬆ Uploading proof...' : payLoading ? 'Recording...' : !proofFile ? 'Attach proof first' : `Record ₹${parseFloat(payAmount || '0').toLocaleString('en-IN')}`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )} */}

      {/* ── Mukkadam Settlement Pay Modal ── */}
      {mukkadamPayModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setMukkadamPayModal(null); setMukkadamProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '380px', boxShadow: '0 24px 60px rgba(0,0,0,0.25)', padding: '22px 24px' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>🏦 Pay Mukkadam</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
              <strong>{mukkadamPayModal.name}</strong> · Job #{mukkadamPayModal.jobId} · ₹{mukkadamPayModal.amount.toLocaleString('en-IN')}
            </p>
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', color: '#6b7280', marginBottom: '2px' }}>NET PAYABLE</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f766e' }}>₹{mukkadamPayModal.amount.toLocaleString('en-IN')}</div>
            </div>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
            <select value={mukkadamPayMode} onChange={e => setMukkadamPayMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
            <input value={mukkadamPayNotes} onChange={e => setMukkadamPayNotes(e.target.value)} placeholder="e.g. UPI ref 12345"
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
              Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
            </label>
            {mukkadamProofFile ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                {mukkadamProofFile.type.startsWith('image/') && (
                  <img src={URL.createObjectURL(mukkadamProofFile)} alt="proof" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '4px' }} />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {mukkadamProofFile.name}</p>
                </div>
                <button onClick={() => setMukkadamProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700 }}>✕</button>
              </div>
            ) : (
              <label style={{ display: 'block', padding: '12px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                <input type="file" accept="image/*,application/pdf" onChange={e => setMukkadamProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                <p style={{ margin: '0 0 2px', fontSize: '0.78rem', color: '#374151' }}>📷 Attach payment proof</p>
                <p style={{ margin: 0, fontSize: '0.64rem', color: '#9ca3af' }}>Screenshot / receipt / photo</p>
              </label>
            )}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => { setMukkadamPayModal(null); setMukkadamProofFile(null); }}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>Cancel</button>
              <button onClick={submitMukkadamPay}
                disabled={mukkadamPayLoading || mukkadamProofUploading || !mukkadamProofFile}
                style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                  background: !mukkadamProofFile ? '#d1d5db' : mukkadamProofUploading ? '#fbbf24' : mukkadamPayLoading ? '#99f6e4' : '#14b8a6',
                  color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: (!mukkadamProofFile || mukkadamPayLoading || mukkadamProofUploading) ? 'not-allowed' : 'pointer' }}>
                {mukkadamProofUploading ? '⬆ Uploading...' : mukkadamPayLoading ? 'Processing...' : !mukkadamProofFile ? 'Attach proof first' : `✓ Confirm Pay ₹${mukkadamPayModal.amount.toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Weekly Payment Modal ── */}
      {weeklyModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => { setWeeklyModal(null); setWeeklyProofFile(null); }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '380px', boxShadow: '0 24px 60px rgba(0,0,0,0.25)', padding: '22px 24px' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 2px', fontSize: '1rem', fontWeight: 700 }}>📅 Weekly Payment</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.75rem', color: '#6b7280' }}>
              <strong>{weeklyModal.name}</strong> · Today {new Date().toLocaleDateString('en-IN')}
            </p>
            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', color: '#6b7280', marginBottom: '2px' }}>WEEKLY AMOUNT</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#1d4ed8' }}>₹{weeklyModal.amount.toLocaleString('en-IN')}</div>
            </div>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Payment Mode</label>
            <select value={weeklyMode} onChange={e => setWeeklyMode(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '10px', background: '#fff', boxSizing: 'border-box' }}>
              {['CASH', 'UPI', 'ZOHO_PAYMENT', 'BANK_TRANSFER', 'CHEQUE'].map(m => (
                <option key={m} value={m}>{m === 'ZOHO_PAYMENT' ? 'Zoho Payment' : m === 'BANK_TRANSFER' ? 'Bank Transfer' : m}</option>
              ))}
            </select>
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Notes (optional)</label>
            <input value={weeklyNotes} onChange={e => setWeeklyNotes(e.target.value)} placeholder="e.g. Cash given on site"
              style={{ width: '100%', padding: '8px 12px', border: '1.5px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px', boxSizing: 'border-box' }} />
            <label style={{ fontSize: '0.72rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
              Payment Proof <span style={{ color: '#dc2626', fontWeight: 700 }}>*</span>
            </label>
            {weeklyProofFile ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1.5px solid #bbf7d0', borderRadius: '8px', background: '#f0fdf4', marginBottom: '16px' }}>
                {weeklyProofFile.type.startsWith('image/') && (
                  <img src={URL.createObjectURL(weeklyProofFile)} alt="proof" style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '4px' }} />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 600, color: '#16a34a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {weeklyProofFile.name}</p>
                </div>
                <button onClick={() => setWeeklyProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '1rem', fontWeight: 700 }}>✕</button>
              </div>
            ) : (
              <label style={{ display: 'block', padding: '12px', border: '1.5px dashed #d1d5db', borderRadius: '8px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '16px' }}>
                <input type="file" accept="image/*,application/pdf" onChange={e => setWeeklyProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                <p style={{ margin: '0 0 2px', fontSize: '0.78rem', color: '#374151' }}>📷 Attach payment proof</p>
                <p style={{ margin: 0, fontSize: '0.64rem', color: '#9ca3af' }}>Screenshot / receipt / photo</p>
              </label>
            )}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => { setWeeklyModal(null); setWeeklyProofFile(null); }}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.82rem', cursor: 'pointer' }}>Cancel</button>
              <button onClick={submitWeeklyPayment}
                disabled={weeklyPayLoading || weeklyProofUploading || !weeklyProofFile}
                style={{ flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                  background: !weeklyProofFile ? '#d1d5db' : weeklyProofUploading ? '#fbbf24' : weeklyPayLoading ? '#bfdbfe' : '#1d4ed8',
                  color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: (!weeklyProofFile || weeklyPayLoading || weeklyProofUploading) ? 'not-allowed' : 'pointer' }}>
                {weeklyProofUploading ? '⬆ Uploading...' : weeklyPayLoading ? 'Saving...' : !weeklyProofFile ? 'Attach proof first' : `✓ Record ₹${weeklyModal.amount.toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── MiscCostsSection with proof upload ──────────────────────────────────────
function MiscCostsSection({
  mukkadamId, jobId, initialCosts, onCostChange,
}: {
  mukkadamId: number; jobId: string; initialCosts: any[]; onCostChange: () => void;
}) {
  const [costs, setCosts] = useState<any[]>(initialCosts);
  const [adding, setAdding] = useState(false);
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [proofUploading, setProofUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleAdd = async () => {
    if (!amount || parseFloat(amount) <= 0) { alert('Enter valid amount'); return; }
    if (!reason.trim()) { alert('Reason is required'); return; }
    if (!proofFile) { alert('Proof is required'); return; }

    setProofUploading(true);
    let proofS3Key: string | null = null;
    try {
      // const { uploadFileToS3, getFileExtension } = await import('../utils/s3Upload');
      const userToken = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
      const ext = getFileExtension(proofFile);
      const s3Name = `payments/misc/${mukkadamId}/job_${jobId}_${Date.now()}.${ext}`;
      proofS3Key = await uploadFileToS3(proofFile, s3Name, userToken);
      if (!proofS3Key) { alert('❌ Proof upload failed'); return; }
    } finally { setProofUploading(false); }

    setSaving(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: parseFloat(amount), reason, proof_s3_key: proofS3Key }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        setCosts(prev => [data, ...prev]);
        setAmount(''); setReason(''); setProofFile(null); setAdding(false);
        onCostChange();
      } else { alert(data.error); }
    } finally { setSaving(false); }
  };

  const handleDelete = async (costId: number) => {
    if (!confirm('Remove this misc cost?')) return;
    setDeletingId(costId);
    try {
      const res = await fetch(`${API_BASE_URL}/api/mukkadam/${mukkadamId}/job/${jobId}/misc/${costId}/`, { method: 'DELETE' });
      if (res.ok) { setCosts(prev => prev.filter(c => c.id !== costId)); onCostChange(); }
    } finally { setDeletingId(null); }
  };

  const total = costs.reduce((t, c) => t + Number(c.amount), 0);

  return (
    <div style={{ background: '#fafafa', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '10px 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <p style={{ margin: 0, fontSize: '0.66rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase' }}>⚠ Misc Deductions</p>
        {!adding && (
          <button onClick={() => setAdding(true)}
            style={{ fontSize: '0.68rem', padding: '3px 10px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontWeight: 600, cursor: 'pointer' }}>
            + Add
          </button>
        )}
      </div>

      {adding && (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #fde68a', padding: '10px', marginBottom: '8px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px', marginBottom: '8px' }}>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Amount (₹)</label>
              <input type="number" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0"
                style={{ width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 700, boxSizing: 'border-box' }} />
            </div>
            <div>
              <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>Reason <span style={{ color: '#ef4444' }}>*</span></label>
              <input type="text" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Tool damage, travel..."
                style={{ width: '100%', padding: '6px 8px', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '0.78rem', boxSizing: 'border-box' }} />
            </div>
          </div>
          <label style={{ fontSize: '0.65rem', color: '#6b7280', display: 'block', marginBottom: '3px' }}>
            Proof <span style={{ color: '#ef4444' }}>*</span>
          </label>
          {proofFile ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 8px', border: '1px solid #bbf7d0', borderRadius: '6px', background: '#f0fdf4', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>✓ {proofFile.name}</span>
              <button onClick={() => setProofFile(null)} style={{ border: 'none', background: 'none', color: '#dc2626', cursor: 'pointer', fontWeight: 700 }}>✕</button>
            </div>
          ) : (
            <label style={{ display: 'block', padding: '8px', border: '1px dashed #d1d5db', borderRadius: '6px', textAlign: 'center', cursor: 'pointer', background: '#f9fafb', marginBottom: '8px' }}>
              <input type="file" accept="image/*,application/pdf" onChange={e => setProofFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
              <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>📷 Attach proof</span>
            </label>
          )}
          <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
            <button onClick={() => { setAdding(false); setAmount(''); setReason(''); setProofFile(null); }}
              style={{ padding: '5px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: '0.72rem', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleAdd} disabled={saving || proofUploading || !proofFile}
              style={{ padding: '5px 12px', borderRadius: '6px', border: 'none',
                background: !proofFile ? '#d1d5db' : proofUploading ? '#fde68a' : saving ? '#fde68a' : '#f59e0b',
                color: !proofFile ? '#9ca3af' : '#fff', fontSize: '0.72rem', fontWeight: 700, cursor: (!proofFile || saving || proofUploading) ? 'not-allowed' : 'pointer' }}>
              {proofUploading ? '⬆ Uploading...' : saving ? 'Saving...' : !proofFile ? 'Attach proof' : 'Add Deduction'}
            </button>
          </div>
        </div>
      )}

      {costs.length === 0 ? (
        <p style={{ fontSize: '0.72rem', color: '#9ca3af', margin: 0, textAlign: 'center', padding: '8px 0' }}>No misc deductions</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {costs.map((c) => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderRadius: '6px', background: '#fff', border: '1px solid #f3f4f6', fontSize: '0.74rem' }}>
              <div style={{ flex: 1 }}>
                <span style={{ color: '#374151', fontWeight: 600 }}>{c.reason}</span>
                <span style={{ color: '#9ca3af', fontSize: '0.62rem', marginLeft: '6px' }}>{c.created_at?.slice(0, 10)}</span>
                {c.proof_url && (
                  <a href={c.proof_url} target="_blank" rel="noreferrer"
                    style={{ marginLeft: '6px', fontSize: '0.58rem', color: '#3b82f6', textDecoration: 'none', border: '1px solid #bfdbfe', borderRadius: '3px', padding: '0px 4px', background: '#eff6ff' }}>
                    📎
                  </a>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 800, color: '#dc2626' }}>−₹{Number(c.amount).toLocaleString('en-IN')}</span>
                <button onClick={() => handleDelete(c.id)} disabled={deletingId === c.id}
                  style={{ padding: '2px 6px', borderRadius: '4px', border: 'none', background: '#fef2f2', color: '#ef4444', fontSize: '0.65rem', cursor: 'pointer', fontWeight: 700 }}>
                  {deletingId === c.id ? '...' : '✕'}
                </button>
              </div>
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 8px', borderTop: '1.5px solid #e5e7eb', marginTop: '2px', fontSize: '0.74rem' }}>
            <span style={{ fontWeight: 700, color: '#374151' }}>Total Misc</span>
            <span style={{ fontWeight: 800, color: '#dc2626' }}>−₹{total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
      )}
    </div>
  );
}

const FarmScheduler: React.FC<FarmSchedulerProps> = ({clusterId, onBackToClusters,onOpenDialpadWithNumber}) => {
  // State
  const [dialpadOpen, setDialpadOpen] = useState(false);
const [dialpadNumber, setDialpadNumber] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [mukkadams, setMukkadams] = useState<Mukkadam[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [loading, setLoading] = useState(false);
const [potentialByDate, setPotentialByDate] = useState<PotentialByDate>({});
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedMukkadam, setSelectedMukkadam] = useState<Mukkadam | null>(null);

  // Modals
  const [showAllocationModal, setShowAllocationModal] = useState(false);
  const [showProductivityWarning, setShowProductivityWarning] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [pendingAllocation, setPendingAllocation] = useState<any>(null);

// when cluster changes → reload base data for that cluster & current month
useEffect(() => {
  const run = async () => {
    setJobs([]);
    setAllJobs([]);
    await Promise.all([
      loadJobs(filters.plotId),
      loadAllocations(currentMonth), // ✅ explicit month
      loadLeaves(currentMonth),       // ✅ explicit month
      loadMukkadams(),
      loadOverload(),
      loadPotential(),
    ]);
  };
  run();
}, [clusterId]); // only clusterId, not currentMonth
const startOfMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
const endOfMonth   = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);


const [leaves, setLeaves] = useState<any[]>([]);
// in parent, e.g. CalendarPage.tsx
const [selectedMukkadamCapacity, setSelectedMukkadamCapacity] = useState<number | null>(null);
const [overloadItems, setOverloadItems] = useState<any[]>([]);
type Filters = {
  farmerId: string | null;
  mukkadamId: number | null;
  cropName: string | null;
  variety: string | null;
  plotId: number | null;
  activityId: number | null;
  dateFrom: string | null; // "YYYY-MM-DD"
  dateTo: string | null;
};

const [filters, setFilters] = useState<Filters>({
  farmerId: null,
  mukkadamId: null,
  plotId: null,
  cropName: null,
  variety: null,
  activityId: null,
  dateFrom: null,
  dateTo: null,
});

const loadOverload = async () => {
  const res = await fetch(
    `${API_BASE_URL}/api/planning/by_activity_date/?cluster_id=${clusterId}`,
  );
  const data = await res.json();
  console.log('Loaded overload items:', data);
  setOverloadItems(data);
};
const loadPotential = async () => {
  const res = await fetch(
    `${API_BASE_URL}/api/clusters/${clusterId}/potential_jobs/`
  );
  const data = await res.json();
  console.log('Loaded potential jobs:', data);

  setPotentialByDate(data);
};

const overloadMap: Record<string, any> = {};
overloadItems.forEach((o) => {
  const key = `${o.job_id}-${o.activity_id}-${o.scheduled_date}`;
  overloadMap[key] = o;
});


useEffect(() => {
  if (!selectedMukkadam || !selectedDate) {
    setSelectedMukkadamCapacity(null);
    return;
  }
  const dateStr = formatDate(selectedDate);   // ✅

  fetch(
    `${API_BASE_URL}/api/mukkadams/${selectedMukkadam.mukkadam_id}/daily_capacity/?date=${dateStr}&cluster_id=${clusterId}`,
  )
    .then((r) => r.json())
    .then((data) => setSelectedMukkadamCapacity(data.available_crew_size))
    .catch(() => setSelectedMukkadamCapacity(null));
}, [selectedMukkadam, selectedDate]);
const [dayCapacities, setDayCapacities] = useState<Record<string, number>>({});
// key: `${mukkadam_id}-${dateString}`, value: available_crew_size
useEffect(() => {
  const fetchDayCapacities = async () => {
    const dateStr = formatDate(selectedDate);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/daily_capacity_all/?date=${dateStr}&cluster_id=${clusterId}`,
      );
      const data = await res.json();
      const map: Record<string, number> = {};
      data.forEach((item: any) => {
        map[`${item.mukkadam_id}-${dateStr}`] = item.available_crew_size;
      });
      setDayCapacities(map);
    } catch (err) {
      console.error('Failed to load day capacities', err);
      setDayCapacities({});
    }
  };

  // fetchDayCapacities();
}, [selectedDate]);

// load all mukkadams
const loadMukkadams = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/mukkadams/?cluster_id=${clusterId}`);
    const data = await response.json();

    const normalized = data.map((m: any) => ({
      ...m,
      mukkadam_id: m.mukkadam_id,
      crew_size: Number(m.crew_size) || 0,
    }));

    setMukkadams(normalized);
  } catch (error) {
    toast.error('Failed to load mukkadams');
    console.error(error);
  }
};


const [prefillData, setPrefillData] = useState<{
  jobId: string;
  activityId: number;
  activityDate?: string;
  farmerRate?: number;
  // team-click prefill
  mukkadamId?: number | null;
  allocatedArea?: number | null;
  allocatedWorkers?: number | null;
  mukkadamRate?: number | null;
} | null>(null);
const handleStartAllocationFromDay = (
  jobId: string,
  activityId: number,
  activity: any,
) => {
  const prefill = activity?.__prefill;

  if (prefill) {
    // ── Team click → direct allocation, no modal ──
    const allocationData = {
      job_id: jobId,
      job_activity_id: activityId,
      mukkadam_id: prefill.mukkadam_id,
      allocated_date: activity.scheduled_date,
      allocated_area: prefill.allocated_area,
      allocated_workers: prefill.allocated_workers,
      farmer_rate: activity.rate_per_acre,
      mukkadam_rate: prefill.mukkadam_rate,
      cluster_id: clusterId,
    };
    handleCreateAllocation([allocationData]);
    return;
  }

  // ── Regular Allocate → button → open modal ──
  setPrefillData({
    jobId,
    activityId,
    activityDate: activity.scheduled_date,
    farmerRate: activity.rate_per_acre,
  });
  setShowAllocationModal(true);
};



const handleAddDayCrew = async (mukkadam: Mukkadam, date: Date) => {
  const input = window.prompt(
    `Add extra workers for ${mukkadam.mukkadam_name} on ${formatDate(date)}:`,
    '0',
  );
  if (!input) return;
  const extra = parseInt(input, 10);
  if (Number.isNaN(extra) || extra <= 0) return;

  try {
    setLoading(true);
    await fetch(`${API_BASE_URL}/api/extra-workers/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mukkadam_id: mukkadam.mukkadam_id,
        mukkadam:mukkadam.mukkadam_id,
        date: formatDate(date),
        workers: extra,
      }),
    });
    await loadAllocations();
    await loadMukkadams();
  } finally {
    setLoading(false);
  }
};

const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);

useEffect(() => {
  if (!selectedMukkadam || !selectedDate) {
    setSelectedMukkadamCapacity(null);
    return;
  }
  const dateStr = formatDate(selectedDate);   // ✅

  fetch(
    `${API_BASE_URL}/api/mukkadams/${selectedMukkadam.mukkadam_id}/daily_capacity/?date=${dateStr}&cluster_id=${clusterId}`,
  )
    .then((r) => r.json())
    .then((data) => setSelectedMukkadamCapacity(data.available_crew_size))
    .catch(() => setSelectedMukkadamCapacity(null));
}, [selectedMukkadam, selectedDate]);

// helper for date formatting used in allocations filter

// 2. Add loadLeaves function
const loadLeaves = async (forMonth?: Date) => {
  const month = forMonth ?? currentMonth; // ✅
  try {
    const startDate = new Date(month.getFullYear(), month.getMonth(), 1);
    const endDate = new Date(month.getFullYear(), month.getMonth() + 1, 0);
    const response = await fetch(
      `${API_BASE_URL}/api/leaves/?start_date=${formatDate(startDate)}&end_date=${formatDate(endDate)}&cluster_id=${clusterId}`
    );
    const data = await response.json();
    setLeaves(data);
  } catch (error) {
    console.error('Failed to load leaves');
  }
};

// FarmScheduler.tsx

// const [jobs, setJobs] = useState<Job[]>([]);
const [allJobs, setAllJobs] = useState<Job[]>([]); // ✅ Add this

const loadJobs = async (plotId?: number | null) => {
  const activePlotId = plotId !== undefined ? plotId : filters.plotId;
  
  console.log('loadJobs called, plotId:', activePlotId, 'filters.plotId:', filters.plotId);
  
  let url = `${API_BASE_URL}/api/jobs/?status=pending,scheduled,in_progress&cluster_id=${clusterId}`;
  if (activePlotId) {
    url += `&plot=${activePlotId}`;
  }
  
  console.log('Fetching URL:', url);  // ← check this in browser
  
  try {
    setLoading(true);
    const response = await fetch(url);
    const data = await response.json();
    setAllJobs(data);
    setJobs(data);
  } catch (error) {
    toast.error('Failed to load jobs');
  } finally {
    setLoading(false);
  }
};
// ✅ Jobs reload whenever clusterId OR plotId changes
useEffect(() => {
  loadJobs(filters.plotId);
}, [clusterId, filters.plotId]);
useEffect(() => {
  loadLeaves(currentMonth);
  loadAllocations(currentMonth);
}, [currentMonth, clusterId]);
// FarmScheduler.tsx
const loadAllocations = async (forMonth?: Date) => {
  const month = forMonth ?? currentMonth; // ✅ use passed month, fallback to current
  try {
    const startDate = new Date(month.getFullYear(), month.getMonth(), 1);
    const endDate = new Date(month.getFullYear(), month.getMonth() + 1, 0);
    const token = localStorage.getItem('auth_token');
    const response = await fetch(
      `${API_BASE_URL}/api/allocations/calendar_view/?start_date=${formatDate(startDate)}&end_date=${formatDate(endDate)}&cluster_id=${clusterId}`
      ,
  {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    credentials: 'include',
  },
    );
    const data = await response.json();
    const allocationsList: Allocation[] = [];
    Object.values(data).forEach((dayAllocations: any) => {
      allocationsList.push(...dayAllocations);
    });
    setAllocations(allocationsList);
  } catch (error) {
    toast.error('Failed to load allocations');
  }
};

  //   const [jobs, setJobs] = useState<Job[]>([]);
  // const [loading, setLoading] = useState(false);
  const [selectedFarmerId, setSelectedFarmerId] = useState<string | null>(null);
  const [selectedFarmerName, setSelectedFarmerName] = useState<string | null>(null);


  // const loadJobs = async () => {
  //   setLoading(true);
  //   try {
  //     const response = await fetch(`http://localhost:8001/tender/api/jobs/?cluster=${clusterId}`);
  //     const data = await response.json();
  //     setJobs(data);
  //   } catch (error) {
  //     console.error('Failed to load jobs:', error);
  //   } finally {
  //     setLoading(false);
  //   }
  // };

  const handleFarmerSelect = (farmerId: string, farmerName: string) => {
    setSelectedFarmerId(farmerId);
    setSelectedFarmerName(farmerName);
  };
const loadData = async () => {
  await loadMukkadams();
};
const inRange = (dateStr: string | null | undefined): boolean => {
  if (!dateStr) return true; // ignore if no date
  const d = dateStr;
  if (filters.dateFrom && d < filters.dateFrom) return false;
  if (filters.dateTo && d > filters.dateTo) return false;
  return true;
};

// allocationData is now an array of allocations from the modal
const handleCreateAllocation = async (allocationData: any[]) => {
  const isMultiTeam = allocationData.length > 1;
  
  // For STRICT activities with multiple teams, validate the total first
  if (isMultiTeam) {
    const job = jobs.find(j => j.job_id === allocationData[0].job_id);
    const activity = job?.activities?.find(a => a.id === allocationData[0].job_activity_id);
    
    if (activity?.is_strict) {
      // 👇 NEW: Check all dates are the same for STRICT
      const uniqueDates = new Set(allocationData.map(a => a.allocated_date));
      if (uniqueDates.size > 1) {
        toast.error(
          `STRICT activity must be allocated on ONE date. ` +
          `You selected: ${Array.from(uniqueDates).join(', ')}`
        );
        return;
      }
      
      // 👇 Check total area matches remaining
      const totalArea = allocationData.reduce((sum, alloc) => sum + alloc.allocated_area, 0);
      
      if (Math.abs(totalArea - activity.remaining_area) > 0.01) {
        toast.error(
          `Strict activity requires full allocation. ` +
          `Remaining: ${activity.remaining_area} acres, ` +
          `You're allocating: ${totalArea} acres`
        );
        return;
      }
    }
  }
  
  // Create all allocations
  for (const alloc of allocationData) {
    setPendingAllocation(alloc);
    await validateAllocation(alloc, isMultiTeam);
  }
};
const validateAllocation = async (allocationData: any, isMultiTeam: boolean = false) => {
  try {
    setLoading(true);

    // 1️⃣ Check leave availability
    const leaveCheckResponse = await fetch(
      `${API_BASE_URL}/api/leaves/check_availability/?date=${allocationData.allocated_date}&mukkadam_id=${allocationData.mukkadam_id}&cluster_id=${clusterId}`
    );

    const leaveCheck = await leaveCheckResponse.json();

    if (!leaveCheckResponse.ok) {
      toast.error(leaveCheck.message || "Leave check failed");
      return;
    }

    if (!leaveCheck.available) {
      toast.error(leaveCheck.message);
      return;
    }

    // 2️⃣ Validate allocation
    const job = jobs.find(j => j.job_id === allocationData.job_id);
    const activity = job?.activities?.find(a => a.id === allocationData.job_activity_id);
    const isActivityStrict = activity?.is_strict || false;
    
    // Skip strict check ONLY if multi-team AND strict (already validated in handleCreateAllocation)
    const skipStrictCheck = isMultiTeam && isActivityStrict;

    const response = await fetch(
      `${API_BASE_URL}/api/allocations/validate_allocation/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_activity_id: allocationData.job_activity_id,
          mukkadam_id: allocationData.mukkadam_id,
          allocated_date: allocationData.allocated_date,
          allocated_area: allocationData.allocated_area,
          allocated_workers: allocationData.allocated_workers,
          skip_strict_check: skipStrictCheck,
          cluster_id: clusterId,
        }),
      }
    );

    const result = await response.json();

    if (!response.ok) {
      toast.error(result.error || result.message || "Validation error");
      return;
    }

    setValidationResult(result);

    if (result.can_allocate) {
      if (result.warnings && Object.keys(result.warnings).length > 0) {
        toast.success("Validation passed with warnings");
      }
      await createAllocation(allocationData, false, skipStrictCheck);
    } else {
      setShowProductivityWarning(true);
    }
  } catch (error) {
    toast.error("Validation failed");
    console.error(error);
  } finally {
    setLoading(false);
  }
};
const token = localStorage.getItem('auth_token');
const createAllocation = async (allocationData: any, force: boolean = false, skipStrictCheck: boolean = false) => {  // 👈 Add parameter
  try {
    setLoading(true);
    const response = await fetch(`${API_BASE_URL}/api/allocations/create_allocation/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${token}`,},
      body: JSON.stringify({ 
        ...allocationData, 
        force,
        skip_strict_check: skipStrictCheck,  // 👈 ADD THIS
        cluster_id: clusterId,
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      toast.success('Allocation created successfully!');
      setShowAllocationModal(false);
      setShowProductivityWarning(false);
      loadAllocations();
      loadJobs();
    } else {
      toast.error(result.error || 'Failed to create allocation');
    }
  } catch (error) {
    toast.error('Failed to create allocation');
    console.error(error);
  } finally {
    setLoading(false);
  }
};



  const handleSuggestionSelected = async (suggestion: any) => {
    switch (suggestion.option) {
      case 'reduce_area':
        setPendingAllocation({
          ...pendingAllocation,
          allocated_area: suggestion.allocation.area
        });
        await createAllocation({
          ...pendingAllocation,
          allocated_area: suggestion.allocation.area
        });
        break;
        
      case 'add_workers':
        setPendingAllocation({
          ...pendingAllocation,
          allocated_workers: suggestion.allocation.workers
        });
        await createAllocation({
          ...pendingAllocation,
          allocated_workers: suggestion.allocation.workers
        });
        break;
        
      case 'update_productivity':
        await updateProductivity(suggestion);
        await createAllocation(pendingAllocation);
        break;
        
      case 'split_days':
        await createSplitAllocations(suggestion.allocations);
        break;
    }
  };

  const updateProductivity = async (suggestion: any) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/mukkadam-rates/update_rate_and_productivity/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mukkadam_id: pendingAllocation.mukkadam_id,
          activity_id: pendingAllocation.activity_id,
          rate_per_acre: pendingAllocation.mukkadam_rate,
          productivity_per_worker: suggestion.allocation.new_productivity
        })
      });
      
      const result = await response.json();
      if (result.success) {
        toast.success('Productivity updated successfully');
      }
    } catch (error) {
      toast.error('Failed to update productivity');
      console.error(error);
    }
  };

  const createSplitAllocations = async (allocations: any[]) => {
    try {
      for (const alloc of allocations) {
        await createAllocation({
          ...pendingAllocation,
          allocated_area: alloc.area,
          allocated_date: alloc.date === 'next_day' 
            ? formatDate(new Date(new Date(pendingAllocation.allocated_date).getTime() + 86400000))
            : alloc.date
        });
      }
      toast.success('Split allocations created successfully!');
    } catch (error) {
      toast.error('Failed to create split allocations');
      console.error(error);
    }
  };

  const handleForceOverride = async () => {
    await createAllocation(pendingAllocation, true);
  };

const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

// adjusted mukkadams list for the bottom panel
const adjustedMukkadams = mukkadams.map((m) => {
  const dateStr = formatDate(selectedDate);
  const key = `${m.mukkadam_id}-${dateStr}`;
  const dayCapacity = dayCapacities[key];

  return {
    ...m,
    available_crew_size:
      dayCapacity != null
        ? dayCapacity
        : m.crew_size, // fallback if API failed
  };
});



const filteredPotentialByDate: PotentialByDate = {};
Object.entries(potentialByDate).forEach(([dateStr, list]) => {
  if (!inRange(dateStr)) return;
  const kept = list.filter(p => {
    if (filters.farmerId && p.farmerId !== filters.farmerId) return false;
    if (filters.plotId && p.plotId !== filters.plotId) return false;
    if (filters.activityId && p.activityId !== filters.activityId) return false;
    if (filters.cropName && p.cropName !== filters.cropName) return false;
    if (filters.variety && p.variety !== filters.variety) return false;
    return true;
  });
  if (kept.length) filteredPotentialByDate[dateStr] = kept;
});
const filteredJobs = jobs.filter(job => {
  // farmer filter
  if (filters.farmerId && job.farmer_id !== filters.farmerId) return false;

  // plot filter
  if (filters.plotId && job.plot !== filters.plotId) return false;

  // CROP filter - NEW
  if (filters.cropName && job.crop_name !== filters.cropName) return false;

  // VARIETY filter - NEW
  if (filters.variety && job.variety !== filters.variety) return false;

  const acts = job.activities || [];

  // activity filter
  if (filters.activityId) {
    const hasAct = acts.some(a => a.activity_id === filters.activityId);
    if (!hasAct) return false;
  }

  // date range: at least one activity in range
  if (filters.dateFrom || filters.dateTo) {
    const hasInRange = acts.some(a => inRange(a.scheduled_date));
    if (!hasInRange) return false;
  }

  return true;
});
const jobsByDate: Record<string, Job[]> = {};

filteredJobs.forEach((job) => {
  (job.activities || []).forEach((act) => {
    if (!act.scheduled_date) return;
    
    // ✅ Apply activity filter here
    if (filters.activityId && act.activity_id !== filters.activityId) return;
    
    const key = act.scheduled_date;
    if (!jobsByDate[key]) jobsByDate[key] = [];
    
    // Clone job with only matching activities for this date
    const existingJob = jobsByDate[key].find(j => j.job_id === job.job_id);
    if (!existingJob) {
      jobsByDate[key].push({
        ...job,
        activities: job.activities?.filter(a => 
          a.scheduled_date === key &&
          (!filters.activityId || a.activity_id === filters.activityId)
        )
      });
    }
  });
});
const filteredAllocations = allocations.filter(a => {
  const job = jobs.find(j => j.job_id === a.job_id);
  if (!job) return false;

  if (filters.farmerId && job.farmer_id !== filters.farmerId) return false;
  if (filters.plotId && job.plot !== filters.plotId) return false;
  
  // CROP filter - NEW
  if (filters.cropName && job.crop_name !== filters.cropName) return false;
  
  // VARIETY filter - NEW
  if (filters.variety && job.variety !== filters.variety) return false;

  if (filters.activityId) {
    const acts = job.activities || [];
    if (!acts.some(act => act.activity_id === filters.activityId)) return false;
  }

  if (filters.mukkadamId && a.mukkadam !== filters.mukkadamId) return false;
  if ((filters.dateFrom || filters.dateTo) && !inRange(a.allocated_date)) return false;

  return true;
});
// FarmScheduler.tsx
const [refreshKey, setRefreshKey] = useState(0);

// FarmScheduler.tsx
const handleRefreshAll = async () => {
  // ✅ Pass currentMonth explicitly so closure captures correct value
  await loadAllocations(currentMonth);
  await Promise.all([
    loadJobs(filters.plotId),
    
  ]);
  setRefreshKey(k => k + 1); // bumps AFTER fresh data is in state
};

// FarmScheduler.tsx — add this one useEffect
useEffect(() => {
  const handler = () => handleRefreshAll();
  window.addEventListener('farm-scheduler-refresh', handler);
  return () => window.removeEventListener('farm-scheduler-refresh', handler);
}, [currentMonth, filters.plotId]); // deps so handleRefreshAll uses fresh values

const VIEW_OPTIONS: { value: 'jobs' | 'allocations' | 'both' | 'payments' | 'insights' ; label: string }[] = [
  { value: 'both', label: 'Allocations' },
  { value: 'jobs', label: 'AI' },
  { value: 'payments', label: '💰 Payments' },
  { value: 'insights', label: '📊 Insights' },  // ✅ NEW
];
const [viewModes, setViewModes] = useState<('jobs' | 'allocations' | 'potential' | 'payments' | 'insights')[]>(['jobs', 'allocations']);


const currentMode =
  viewModes.includes('insights')
    ? 'insights'  // ✅ NEW
    : viewModes.includes('payments')
    ? 'payments'
    : viewModes.includes('jobs') && viewModes.includes('allocations')
    ? 'both'
    : viewModes.includes('allocations')
    ? 'allocations'
    : 'jobs';

const setViewMode = (mode: 'jobs' | 'allocations' | 'both' | 'payments' | 'insights') => {
  if (mode === 'both') {
    setViewModes(['jobs', 'allocations']);
  } else if (mode === 'payments') {
    setViewModes(['payments']);
  } else if (mode === 'insights') {  // ✅ NEW
    setViewModes(['insights']);
  } else {
    setViewModes([mode]);
  }
};


const selected = VIEW_OPTIONS.find(o => o.value === currentMode) ?? VIEW_OPTIONS[0];
const [modeDropdownOpen, setModeDropdownOpen] = useState(false);


const toggleViewMode = (mode: 'jobs' | 'allocations' | 'potential') => {
  setViewModes(prev => {
    if (prev.includes(mode)) {
      // Remove if already selected (but keep at least one)
      return prev.length > 1 ? prev.filter(m => m !== mode) : prev;
    } else {
      // Add if not selected
      return [...prev, mode];
    }
  });
};


const filteredMukkadams = adjustedMukkadams.filter(m => {
  // mukkadam filter
  if (filters.mukkadamId && m.mukkadam_id !== filters.mukkadamId) return false;

  // date filter: show only those who have allocations in range OR crew_size>0 if only date filter
  if (filters.dateFrom || filters.dateTo || filters.farmerId) {
    const hasAlloc = filteredAllocations.some(
      a => a.mukkadam === m.mukkadam_id
    );
    return hasAlloc;
  }

  // only date filter case with no farmer/mukkadam: show crew_size > 0
  if (!filters.farmerId && !filters.mukkadamId && (filters.dateFrom || filters.dateTo)) {
    return m.available_crew_size > 0;
  }

  return true;
});
// unique plots from jobs (for plot filter)
const plotOptions = [
  ...new Map(
    jobs
      .filter(j => !filters.farmerId || j.farmer_id === filters.farmerId)
      .map(j => [j.plot, { id: j.plot, name: j.plot_name }])  // ❌ job.plot is the MAIN plot only
  ).values(),
].filter(p => p.id);
// unique activities from jobs (for activity filter)
const activityOptions = [
  ...new Map(
    jobs.flatMap(j =>
      (j.activities || []).map(a => [
        a.activity_id,
        { id: a.activity_id, name: a.activity_name },
      ]),
    ),
  ).values(),
];
// unique crops from jobs
const cropOptions = [
  ...new Set(
    jobs
      .filter(j => {
        // apply existing filters for dependent behavior
        if (filters.farmerId && j.farmer_id !== filters.farmerId) return false;
        if (filters.plotId && j.plot !== filters.plotId) return false;
        return true;
      })
      .map(j => j.crop_name)
      .filter(Boolean) // remove null/undefined
  )
].sort();

// unique varieties from jobs - filtered by selected crop if any
const varietyOptions = [
  ...new Set(
    jobs
      .filter(j => {
        // apply existing filters
        if (filters.farmerId && j.farmer_id !== filters.farmerId) return false;
        if (filters.plotId && j.plot !== filters.plotId) return false;
        if (filters.cropName && j.crop_name !== filters.cropName) return false;
        return true;
      })
      .map(j => j.variety)
      .filter(Boolean)
  )
].sort();

  return (
    <div className="farm-scheduler">
      <Toaster position="top-right" />
      
<header className="scheduler-header">
  {/* LEFT: back + title */}
  <div className="header-content">
    <button
      className="btn-secondary back-button"
      onClick={onBackToClusters}
    >
      ← Back to clusters
    </button>

   
  </div>

  
  <div className="header-center">
<div className="filter-bar">


{/* 
  <select
    value={filters.plotId ?? ''}
    onChange={(e) =>
  setFilters(f => {
    console.log('Plot selected:', e.target.value);  // ✅ add this
    return {
      ...f,
      plotId: e.target.value ? Number(e.target.value) : null,
    };
  })
}
    className="form-select"
  >
    <option value="">All plots</option>
    {plotOptions.map(p => (
      <option key={p.id} value={p.id}>
        {p.name}
      </option>
    ))}
  </select> */}
{/* 
  <select
    value={filters.cropName || ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        cropName: e.target.value || null,
        variety: null, // reset variety when crop changes
      }))
    }
    className="form-select"
  >
    <option value="">All crops</option>
    {cropOptions.map(c => (
      <option key={c} value={c}>
        {c}
      </option>
    ))}
  </select> */}

  {/* <select
    value={filters.variety || ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        variety: e.target.value || null,
      }))
    }
    className="form-select"
  >
    <option value="">All varieties</option>
    {varietyOptions.map(v => (
      <option key={v} value={v}>
        {v}
      </option>
    ))}
  </select> */}
{/* 
  <select
    value={filters.activityId ?? ''}
    onChange={(e) =>
      setFilters(f => ({
        ...f,
        activityId: e.target.value ? Number(e.target.value) : null,
      }))
    }
    className="form-select"
  >
    <option value="">All activities</option>
    {activityOptions.map(a => (
      <option key={a.id} value={a.id}>
        {a.name}
      </option>
    ))}
  </select> */}




  {/* <input
    type="date"
    value={filters.dateFrom || ''}
    onChange={(e) =>
      setFilters(f => ({ ...f, dateFrom: e.target.value || null }))
    }
    className="form-input"
  />
  <span>to</span>
  <input
    type="date"
    value={filters.dateTo || ''}
    onChange={(e) =>
      setFilters(f => ({ ...f, dateTo: e.target.value || null }))
    }
    className="form-input"
  /> */}

  {/* <button
    className="btn-secondary"
    onClick={() =>
      setFilters({
        farmerId: null,
        mukkadamId: null,
        plotId: null,
        activityId: null,
        cropName: null,
        variety: null,
        dateFrom: null,
        dateTo: null,
      })
    }
  >
    Clear
  </button> */}
</div>
<div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
  {/* Header Row: Back Button & Title */}

  {/* Filter Controls Row */}
  <div className="flex flex-wrap items-center gap-2">
    {/* Farmer Select */}
    <select
      value={filters.farmerId || ''}
      onChange={(e) =>
        setFilters(f => ({
          ...f,
          farmerId: e.target.value || null,
          plotId: null,
        }))
      }
      className="flex-1 min-w-[140px] bg-white border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2"
    >
      <option value="">All farmers</option>
      {[...new Map(
        jobs.map(j => [j.farmer_id, { id: j.farmer_id, name: j.farmer_name }])
      ).values()].map(f => (
        <option key={f.id} value={f.id}>{f.name}</option>
      ))}
    </select>

    
{/* Activity Select */}
<select
  value={filters.activityId ?? ''}
  onChange={(e) =>
    setFilters(f => ({
      ...f,
      activityId: e.target.value ? Number(e.target.value) : null,
    }))
  }
  className="flex-1 min-w-[140px] h-[38px] bg-white border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2"
>
  <option value="">All activities</option>
  {activityOptions.map(a => (
    <option key={a.id} value={a.id}>
      {a.name}
    </option>
  ))}
</select>


    {/* Team/Mukkadam Select */}
    <select
      value={filters.mukkadamId ?? ''}
      onChange={(e) =>
        setFilters(f => ({
          ...f,
          mukkadamId: e.target.value ? Number(e.target.value) : null,
        }))
      }
      className="flex-1 min-w-[140px] bg-white border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2"
    >
      <option value="">All teams</option>
      {mukkadams.map(m => (
        <option key={m.mukkadam_id} value={m.mukkadam_id}>
          {m.mukkadam_name}
        </option>
      ))}
    </select>

    {/* Custom View Dropdown */}
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setModeDropdownOpen(o => !o)}
        className="h-[38px] border border-gray-300 rounded-lg px-3 py-1 text-sm bg-white flex items-center justify-between gap-2 hover:bg-gray-50 active:bg-gray-100 transition-colors"
      >
        <span className="text-sm font-medium text-gray-700">
          {selected.label}
        </span>
        <span className={`text-[10px] text-gray-500 transition-transform ${modeDropdownOpen ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {modeDropdownOpen && (
        <>
          {/* Invisible backdrop to close dropdown when clicking outside */}
          <div className="fixed inset-0 z-10" onClick={() => setModeDropdownOpen(false)}></div>
          
          <div className="absolute right-0 z-20 mt-2 w-48 origin-top-right bg-white border border-gray-200 rounded-xl shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none overflow-hidden">
            <div className="py-1">
              {VIEW_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    setViewMode(opt.value);
                    setModeDropdownOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-blue-50 transition-colors ${
                    currentMode === opt.value ? 'font-bold text-blue-700 bg-blue-50' : 'text-gray-700'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  </div>
</div>

  </div>

  {/* RIGHT: actions */}
  <div className="header-actions">
  
  </div>
</header>




      {/* Main Layout */}
<div className="scheduler-layout">
  <div className="panel-left-content">
    
    <JobsPanel
      jobs={jobs}
          loading={loading}
          onRefresh={loadJobs}
          onFarmerSelect={handleFarmerSelect}
          clusterId={clusterId}
    />


  {/* <div className="job-details-wrapper">
    <JobDetailPanel
    selectedFarmerId={selectedFarmerId}
          selectedFarmerName={selectedFarmerName}
          onActivityAdded={loadJobs}
          clusterId={clusterId}
    />
  </div> */}
</div>




        {/* Center Panel - Calendar */}
        <div className="center-panel">

{
  currentMode === 'payments' ? (
    <PaymentDashboard clusterId={clusterId} />
  ) : currentMode === 'insights' ? (
// ✅ use this instead
<ClusterInsightsContainer clusterId={clusterId} />

  ) : (
    <CalendarPanel
      currentMonth={currentMonth}
      selectedDate={selectedDate}
      jobs={filteredJobs}
      allJobs={jobs}
      allocations={filteredAllocations}
      mukkadams={adjustedMukkadams}
      leaves={leaves}
      jobsByDate={jobsByDate}
      viewModes={viewModes}
      filters={filters}
      setFilters={setFilters}
      onMonthChange={setCurrentMonth}
      onDateSelect={setSelectedDate}
      onAllocationClick={(allocation) => console.log('Allocation clicked:', allocation)}
      onLeavesUpdated={handleRefreshAll}
      refreshKey={refreshKey}
      clusterId={clusterId}
      overloadMap={overloadMap}
      potentialByDate={filteredPotentialByDate}
      onStartAllocation={handleStartAllocationFromDay}
    />
  )
}



        </div>

        {/* Right Panel - Mukkadams */}
{/* <div className="panel right-panel">
  <div className="right-split">
    <div className="right-top">
      <MukkadamDetailPanel
        mukkadam={
          selectedMukkadam
            ? {
                ...selectedMukkadam,
                available_crew_size:
                  selectedMukkadamCapacity ?? selectedMukkadam.crew_size,
              }
            : null
        }
        onRefresh={loadData}
      />
    </div>

    <div className="right-bottom">
      <MukkadamPanel
        mukkadams={filteredMukkadams}
        selectedDate={selectedDate}
        allocations={allocations.filter(
          (a) =>
            formatDate(new Date(a.allocated_date)) === formatDate(selectedDate),
        )}
        loading={loading}
        onRefresh={loadMukkadams}
        onAddDayCrew={handleAddDayCrew} 
        onMukkadamClick={(m) => setSelectedMukkadam(m)}
        clusterId={clusterId}  
      />
    </div>
  </div>
</div> */}

<Dialpad
  isOpen={dialpadOpen}
  number={dialpadNumber}
  onClose={() => setDialpadOpen(false)}
  onNumberChange={setDialpadNumber}
/>




      </div>
      

      {/* Modals */}
      {showAllocationModal && (
        <AllocationModal
          jobs={jobs}
    mukkadams={mukkadams}
    selectedDate={selectedDate}
    clusterId={clusterId}
    onCreate={handleCreateAllocation}
    initialJobId={prefillData?.jobId}
    initialActivityId={prefillData?.activityId}
    initialDate={prefillData?.activityDate}
    initialFarmerRate={prefillData?.farmerRate}
    onClose={() => {
      setShowAllocationModal(false);
      setPrefillData(null);
    }}
        />
      )}

      {showProductivityWarning && validationResult && (
        <ProductivityWarningModal
          validation={validationResult}
          pendingAllocation={pendingAllocation}
          onClose={() => setShowProductivityWarning(false)}
          onSuggestionSelect={handleSuggestionSelected}
          onForceOverride={handleForceOverride}
        />
      )}
    </div>
  );
};

export default FarmScheduler;
