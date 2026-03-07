import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE_URL } from './types/config';
import * as XLSX from 'xlsx';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type GlobalSummary = {
  total_jobs: number;
  total_activities: number;
  total_area_allocated: number;
  total_area_completed: number;
  total_allocated_workers: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
  loss_allocations: number;
  dispute_count: number;
  avg_efficiency_score: number;
};

type ClusterSummaryRow = {
  cluster_id: number;
  cluster_name: string;
  jobs: number;
  total_area_allocated: number;
  total_area_completed: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
  allocated_workers: number;
  loss_allocations: number;
  dispute_count: number;
};

type WeekSummaryRow = {
  week_start: string;
  allocations: number;
  total_area_allocated: number;
  total_area_completed: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
};

type ClusterJobRow = {
  job_id: string;
  cluster_id: number;
  cluster_name: string;
  farmer_id: string;
  farmer_name: string;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  scheduled_date: string | null;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  estimated_workers: number;
  allocation_status: string;
  allocations_count: number;
  allocated_workers: number;
  allocated_area_sum: number;
};

type ClusterJobsBlock = {
  cluster_id: number;
  cluster_name: string;
  jobs: ClusterJobRow[];
};

type MukkadamClusterRow = {
  cluster_id: number;
  cluster_name: string;
  allocations: number;
  area_alloc: number;
  area_done: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
};

type MukkadamSummaryRow = {
  mukkadam_id: string | number;
  mukkadam_name: string;
  total_area_allocated: number;
  total_farmer_amount: number;
  total_mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
  clusters: MukkadamClusterRow[];
};

type FarmerClusterRow = {
  cluster_id: number;
  cluster_name: string;
  allocations: number;
  area_alloc: number;
  area_done: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
};

type FarmerSummaryRow = {
  farmer_id: string;
  farmer_name: string;
  total_area_allocated: number;
  total_farmer_amount: number;
  total_mukkadam_amount: number;
  profit: number;
  profit_per_acre: number;
  clusters: FarmerClusterRow[];
};

type GlobalInsightsResponse = {
  date_range: { start: string; end: string };
  overall_summary: GlobalSummary;
  cluster_summary: ClusterSummaryRow[];
  week_summary: WeekSummaryRow[];
  cluster_jobs: ClusterJobsBlock[];
  mukkadam_summary: MukkadamSummaryRow[];
  farmer_summary: FarmerSummaryRow[];
};

type DayClusterRow = {
  cluster_id: number;
  cluster_name: string;
  activities: number;
  area_scheduled: number;
  area_allocated: number;
  area_remaining: number;
  allocated_workers: number;
  available_capacity_workers: number;
  farmer_amount: number;
  mukkadam_amount: number;
  profit: number;
};

type DayJobRow = {
  cluster_id: number;
  cluster_name: string;
  booking_id: string;
  job_id: string;
  farmer_id: string;
  farmer_name: string;
  farmer_price: number;
  mukkadam_id: string | number | null;
  mukkadam_name: string | null;
  mukkadam_price: number;
  profit: number;
  plot_name: string | null;
  activity_id: number;
  activity_name: string;
  scheduled_date: string | null;
  total_area: number;
  allocated_area: number;
  remaining_area: number;
  estimated_workers: number;
  allocated_workers: number;
  allocation_status: string;
};

type DayApiResponse = {
  date: string;
  filters: {
    farmer_id: string | null;
    mukkadam_id: string | null;
    activity_id: string | null;
    cluster_id: string | null;
  };
  overall: {
    date: string;
    total_clusters: number;
    total_activities: number;
    total_area_scheduled: number;
    total_area_allocated: number;
    total_area_remaining: number;
    total_allocated_workers: number;
    total_available_capacity_workers: number;
    farmer_amount: number;
    mukkadam_amount: number;
    profit: number;
  };
  clusters: DayClusterRow[];
  jobs: DayJobRow[];
};

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const fmt = (n: number, dec = 1) => n.toFixed(dec);
const fmtINR = (n: number) =>
  '₹' + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });

function statusBadge(status: string) {
  const s = (status || '').toLowerCase();
  if (s === 'completed' || s === 'done')
    return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  if (s === 'partial' || s === 'in_progress')
    return 'bg-amber-100 text-amber-700 border-amber-200';
  if (s === 'pending' || s === 'unallocated')
    return 'bg-slate-100 text-slate-600 border-slate-200';
  if (s === 'dispute')
    return 'bg-red-100 text-red-700 border-red-200';
  return 'bg-blue-100 text-blue-700 border-blue-200';
}

function profitColor(p: number) {
  if (p > 0) return 'text-emerald-600 font-semibold';
  if (p < 0) return 'text-red-500 font-semibold';
  return 'text-slate-500';
}

// ─────────────────────────────────────────────
// Mini KPI Card
// ─────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: 'green' | 'red' | 'amber' | 'blue' | 'indigo';
}) {
  const accents: Record<string, string> = {
    green: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    red: 'bg-red-50 border-red-200 text-red-600',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-700',
  };
  const cls = accent ? accents[accent] : 'bg-white border-slate-200 text-slate-800';
  return (
    <div className={`${cls} border rounded-xl p-4 flex flex-col gap-1`}>
      <span className="text-[10px] uppercase tracking-widest font-medium opacity-60">{label}</span>
      <span className="text-xl font-bold leading-none">{value}</span>
      {sub && <span className="text-[11px] opacity-50">{sub}</span>}
    </div>
  );
}

// ─────────────────────────────────────────────
// Section Header
// ─────────────────────────────────────────────

function SectionHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h3 className="text-sm font-bold text-slate-700 tracking-tight">{title}</h3>
      {count !== undefined && (
        <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">
          {count} rows
        </span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Sortable Table Head
// ─────────────────────────────────────────────

type SortDir = 'asc' | 'desc' | null;

function Th({
  label,
  right,
  sortKey,
  currentSort,
  onSort,
}: {
  label: string;
  right?: boolean;
  sortKey?: string;
  currentSort?: { key: string; dir: SortDir };
  onSort?: (k: string) => void;
}) {
  const active = currentSort?.key === sortKey;
  return (
    <th
      className={`px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 whitespace-nowrap select-none ${right ? 'text-right' : 'text-left'} ${sortKey ? 'cursor-pointer hover:text-slate-700' : ''}`}
      onClick={() => sortKey && onSort && onSort(sortKey)}
    >
      {label}
      {sortKey && (
        <span className="ml-1 text-[10px]">
          {active && currentSort?.dir === 'asc' ? '▲' : active && currentSort?.dir === 'desc' ? '▼' : '⇅'}
        </span>
      )}
    </th>
  );
}

function useSort<T>(data: T[], defaultKey: string) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir }>({ key: defaultKey, dir: 'asc' });
  const toggle = (key: string) => {
    setSort(prev =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : prev.dir === 'desc' ? null : 'asc' }
        : { key, dir: 'asc' },
    );
  };
  const sorted = [...data].sort((a: any, b: any) => {
    if (!sort.dir) return 0;
    const av = a[sort.key] ?? '';
    const bv = b[sort.key] ?? '';
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
    return sort.dir === 'asc' ? cmp : -cmp;
  });
  return { sorted, sort, toggle };
}

// ─────────────────────────────────────────────
// Calendar Day Tab — range-wide calendar with per-date stats + drill-in
// ─────────────────────────────────────────────

type DaySummaryCache = Record<string, DayApiResponse | null | 'loading' | 'empty'>;

function CalendarDayTab({
  startDate,
  endDate,
  clusterId,
  farmerFilter,
  mukkadamFilter,
  activityFilter,
}: {
  startDate: string;
  endDate: string;
  clusterId: number | null;
  farmerFilter: string;
  mukkadamFilter: string;
  activityFilter: string;
}) {
  const [cache, setCache] = useState<DaySummaryCache>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [loadingDates, setLoadingDates] = useState<Set<string>>(new Set());

  // Generate all dates in range
  const allDates: string[] = [];
  if (startDate && endDate) {
    const s = new Date(startDate);
    const e = new Date(endDate);
    for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
      allDates.push(d.toISOString().slice(0, 10));
    }
  }

  // Fetch all dates in range on mount / when range changes
  useEffect(() => {
    if (!allDates.length) return;
    const toFetch = allDates.filter(d => !(d in cache));
    if (!toFetch.length) return;

    // Mark as loading
    setLoadingDates(prev => {
      const n = new Set(prev);
      toFetch.forEach(d => n.add(d));
      return n;
    });
    setCache(prev => {
      const n = { ...prev };
      toFetch.forEach(d => { n[d] = 'loading'; });
      return n;
    });

    // Fetch in batches of 5 to avoid hammering the API
    const batches: string[][] = [];
    for (let i = 0; i < toFetch.length; i += 5) batches.push(toFetch.slice(i, i + 5));

    const fetchBatch = async (batch: string[]) => {
      await Promise.all(batch.map(async (date) => {
        try {
          const params: Record<string, string> = { date };
          if (clusterId) params.cluster_id = String(clusterId);
          const res = await axios.get(`${API_BASE_URL}/api/tender-global-day-insights/`, { params });
          const data: DayApiResponse = res.data;
          const hasData = (data.overall.total_activities > 0 || data.overall.total_area_allocated > 0);
          setCache(prev => ({ ...prev, [date]: hasData ? data : 'empty' }));
        } catch {
          setCache(prev => ({ ...prev, [date]: 'empty' }));
        } finally {
          setLoadingDates(prev => { const n = new Set(prev); n.delete(date); return n; });
        }
      }));
    };

    (async () => {
      for (const batch of batches) await fetchBatch(batch);
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate, clusterId]);

  // Group dates by month → week rows
  const months: Record<string, string[]> = {};
  allDates.forEach(d => {
    const key = d.slice(0, 7); // YYYY-MM
    if (!months[key]) months[key] = [];
    months[key].push(d);
  });

  const fmtMonth = (ym: string) => {
    const [y, m] = ym.split('-');
    return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
  };

  const dayLabel = (d: string) => {
    const dt = new Date(d);
    return { num: dt.getDate(), dow: dt.toLocaleDateString('en-IN', { weekday: 'short' }) };
  };

  const totalLoading = loadingDates.size;
  const totalDates = allDates.length;

  if (selectedDate) {
    const cached = cache[selectedDate];
    return (
      <div>
        <button
          onClick={() => setSelectedDate(null)}
          className="flex items-center gap-2 text-xs font-semibold text-blue-600 hover:text-blue-800 mb-4 transition-colors"
        >
          ← Back to Calendar
        </button>
        <div className="mb-4 flex items-center gap-3">
          <div className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm font-bold">
            {new Date(selectedDate).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </div>
        </div>
        {cached === 'loading' || cached === undefined ? (
          <div className="flex items-center justify-center h-32 text-slate-400 text-sm animate-pulse">Loading…</div>
        ) : cached === 'empty' || cached === null ? (
          <div className="text-center py-16 text-slate-400">
            <div className="text-3xl mb-2">📭</div>
            <p className="text-sm">No activities found for this date.</p>
          </div>
        ) : (
          <DayDetailView
            data={cached}
            farmerFilter={farmerFilter}
            mukkadamFilter={mukkadamFilter}
            activityFilter={activityFilter}
            clusterId={clusterId}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      {/* Loading progress bar */}
      {totalLoading > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span>Loading date data…</span>
            <span>{totalDates - totalLoading}/{totalDates} dates loaded</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${((totalDates - totalLoading) / totalDates) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Legend + stat key */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mb-4 text-[11px] text-slate-500 bg-slate-50 border border-slate-100 rounded-xl px-4 py-3">
        <span className="font-semibold text-slate-600 w-full">Each tile shows:</span>
        <span><span className="font-bold text-violet-600">Jobs ac</span> — total area of all scheduled jobs</span>
        <span><span className="font-bold text-indigo-600">Act</span> — number of activities</span>
        <span><span className="font-bold text-blue-600">Alloc</span> — area allocated (ac)</span>
        <span><span className="font-bold text-slate-600">Workers</span> — used / capacity</span>
        <span><span className="font-bold text-emerald-600">₹</span> — profit (k = thousands, L = lakhs)</span>
        <div className="w-full border-t border-slate-200 my-0.5" />
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-white border border-emerald-300 inline-block" /> Profitable day — click for detail</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-50 border border-amber-300 inline-block" /> Loss day — click for detail</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-50 border border-slate-200 inline-block opacity-40" /> No data</span>
      </div>

      <div className="space-y-6">
        {Object.entries(months).map(([ym, dates]) => (
          <div key={ym}>
            <div className="text-xs font-bold text-slate-700 uppercase tracking-widest mb-3 flex items-center gap-2">
              <span className="w-5 h-px bg-slate-300 inline-block" />
              {fmtMonth(ym)}
              <span className="w-full h-px bg-slate-100 inline-block" />
            </div>

            {/* Day-of-week header */}
            <div className="grid grid-cols-7 gap-1.5 mb-1">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                <div key={d} className="text-[10px] text-center text-slate-400 font-semibold py-1">{d}</div>
              ))}
            </div>

            {/* Calendar grid — pad start */}
            <CalendarMonthGrid
              dates={dates}
              cache={cache}
              loadingDates={loadingDates}
              onSelect={setSelectedDate}
            />
          </div>
        ))}
      </div>

      {allDates.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <div className="text-3xl mb-2">📅</div>
          <p className="text-sm">Select a date range at the top to view the calendar.</p>
        </div>
      )}
    </div>
  );
}

function CalendarMonthGrid({
  dates,
  cache,
  loadingDates,
  onSelect,
}: {
  dates: string[];
  cache: DaySummaryCache;
  loadingDates: Set<string>;
  onSelect: (d: string) => void;
}) {
  // figure out padding: day of week of first date
  const firstDow = new Date(dates[0]).getDay(); // 0=Sun
  const padCells = Array(firstDow).fill(null);
  const allCells = [...padCells, ...dates];
  // fill to complete last row
  while (allCells.length % 7 !== 0) allCells.push(null);

  const rows: (string | null)[][] = [];
  for (let i = 0; i < allCells.length; i += 7) rows.push(allCells.slice(i, i + 7));

  return (
    <div className="space-y-1.5">
      {rows.map((row, ri) => (
        <div key={ri} className="grid grid-cols-7 gap-1.5">
          {row.map((d, ci) => (
            <CalendarDayTile
              key={d ?? `pad-${ri}-${ci}`}
              date={d}
              cached={d ? cache[d] : undefined}
              isLoading={d ? loadingDates.has(d) : false}
              onSelect={onSelect}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function CalendarDayTile({
  date,
  cached,
  isLoading,
  onSelect,
}: {
  date: string | null;
  cached: DayApiResponse | null | 'loading' | 'empty' | undefined;
  isLoading: boolean;
  onSelect: (d: string) => void;
}) {
  if (!date) return <div className="rounded-xl min-h-[7.5rem]" />;

  const dayNum = new Date(date).getDate();
  const dowShort = new Date(date).toLocaleDateString('en-IN', { weekday: 'short' });
  const isToday = date === new Date().toISOString().slice(0, 10);
  const hasData = cached && cached !== 'loading' && cached !== 'empty';
  const data = hasData ? (cached as DayApiResponse) : null;
  const profit = data?.overall.profit ?? 0;
  const isLoss = hasData && profit < 0;

  // total job acres = total_area_scheduled (all jobs scheduled this day)
  const totalJobAcres = data?.overall.total_area_scheduled ?? 0;

  let tileCls = 'border rounded-xl p-2 flex flex-col gap-0.5 transition-all min-h-[7.5rem] ';
  if (isLoading || cached === 'loading') {
    tileCls += 'bg-slate-50 border-slate-100 animate-pulse cursor-wait';
  } else if (!hasData) {
    tileCls += 'bg-slate-50 border-slate-100 opacity-40 cursor-default';
  } else if (isLoss) {
    tileCls += 'bg-amber-50 border-amber-200 hover:bg-amber-100 hover:border-amber-400 cursor-pointer hover:shadow-lg active:scale-95';
  } else {
    tileCls += 'bg-white border-emerald-200 hover:bg-emerald-50 hover:border-emerald-400 cursor-pointer hover:shadow-lg active:scale-95';
  }

  if (isToday) tileCls += ' ring-2 ring-blue-400 ring-offset-1';

  const shortNum = (n: number) =>
    Math.abs(n) >= 100000
      ? `${n >= 0 ? '' : '-'}${(Math.abs(n) / 100000).toFixed(1)}L`
      : Math.abs(n) >= 1000
      ? `${n >= 0 ? '' : '-'}${(Math.abs(n) / 1000).toFixed(1)}k`
      : n.toFixed(0);

  return (
    <div className={tileCls} onClick={() => hasData && onSelect(date)}>
      {/* Date header */}
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-1">
          <span className={`text-xs font-extrabold leading-none ${isToday ? 'text-blue-600' : 'text-slate-700'}`}>{dayNum}</span>
          {isToday && <span className="text-[8px] bg-blue-600 text-white px-1 rounded font-bold leading-tight">Today</span>}
        </div>
        <span className="text-[9px] text-slate-400 font-medium">{dowShort}</span>
      </div>

      {/* Thin divider */}
      {hasData && <div className="h-px bg-slate-100 mb-0.5" />}

      {isLoading || cached === 'loading' ? (
        <div className="space-y-1.5 mt-1 flex-1">
          <div className="h-2 bg-slate-200 rounded w-4/5" />
          <div className="h-2 bg-slate-200 rounded w-3/5" />
          <div className="h-2 bg-slate-200 rounded w-4/5" />
          <div className="h-2 bg-slate-200 rounded w-2/5" />
          <div className="h-2 bg-slate-200 rounded w-3/5" />
        </div>
      ) : hasData && data ? (
        <div className="flex-1 flex flex-col justify-between space-y-0.5">
          {/* Row: label | value */}
          {[
            { label: 'Jobs ac', value: `${totalJobAcres.toFixed(1)}`, color: 'text-violet-600', labelColor: 'text-violet-400' },
            { label: 'Act', value: String(data.overall.total_activities), color: 'text-indigo-600', labelColor: 'text-indigo-400' },
            { label: 'Alloc', value: `${data.overall.total_area_allocated.toFixed(1)}ac`, color: 'text-blue-600', labelColor: 'text-blue-400' },
            { label: 'Workers', value: `${data.overall.total_allocated_workers}/${data.overall.total_available_capacity_workers}`, color: 'text-slate-600', labelColor: 'text-slate-400' },
            { label: '₹', value: shortNum(profit), color: profit >= 0 ? 'text-emerald-600' : 'text-red-500', labelColor: profit >= 0 ? 'text-emerald-400' : 'text-red-300' },
          ].map(({ label, value, color, labelColor }) => (
            <div key={label} className="flex items-center justify-between">
              <span className={`text-[9px] font-semibold ${labelColor}`}>{label}</span>
              <span className={`text-[10px] font-bold ${color} tabular-nums`}>{value}</span>
            </div>
          ))}
          {/* Click hint */}
          <div className="text-[8px] text-slate-300 text-center mt-0.5">tap for detail</div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[9px] text-slate-300">—</span>
        </div>
      )}
    </div>
  );
}

// Full day detail view (used when clicking a calendar tile)
function DayDetailView({
  data,
  farmerFilter,
  mukkadamFilter,
  activityFilter,
  clusterId,
}: {
  data: DayApiResponse;
  farmerFilter: string;
  mukkadamFilter: string;
  activityFilter: string;
  clusterId: number | null;
}) {
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);
  const o = data.overall;

  const filteredJobs = data.jobs.filter(j => {
    if (clusterId && j.cluster_id !== clusterId) return false;
    if (farmerFilter && !j.farmer_name.toLowerCase().includes(farmerFilter.toLowerCase())) return false;
    if (mukkadamFilter && !(j.mukkadam_name || '').toLowerCase().includes(mukkadamFilter.toLowerCase())) return false;
    if (activityFilter && !j.activity_name.toLowerCase().includes(activityFilter.toLowerCase())) return false;
    return true;
  });

  const byCluster: Record<number, { cluster: DayClusterRow; jobs: DayJobRow[] }> = {};
  data.clusters.forEach(c => { byCluster[c.cluster_id] = { cluster: c, jobs: [] }; });
  filteredJobs.forEach(j => { if (byCluster[j.cluster_id]) byCluster[j.cluster_id].jobs.push(j); });

  return (
    <div className="space-y-3">
      {/* Overall KPI strip */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        <KpiCard label="Activities" value={String(o.total_activities)} accent="indigo" />
        <KpiCard label="Area Sched" value={`${fmt(o.total_area_scheduled)} ac`} />
        <KpiCard label="Area Alloc" value={`${fmt(o.total_area_allocated)} ac`} accent="blue" />
        <KpiCard label="Remaining" value={`${fmt(o.total_area_remaining)} ac`} accent="amber" />
        <KpiCard label="Workers" value={`${o.total_allocated_workers}/${o.total_available_capacity_workers}`} />
        <KpiCard label="Profit" value={fmtINR(o.profit)} accent={o.profit >= 0 ? 'green' : 'red'} />
      </div>

      {/* Per-cluster accordions */}
      {Object.values(byCluster).map(({ cluster: c, jobs }) => (
        <div key={c.cluster_id} className="border border-slate-200 rounded-xl overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
            onClick={() => setExpandedCluster(prev => prev === c.cluster_id ? null : c.cluster_id)}
          >
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold text-slate-700">{c.cluster_name}</span>
              <span className="text-[11px] text-slate-500">
                {c.activities} activities · {fmt(c.area_allocated)} ac alloc · {c.allocated_workers} workers
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm font-bold ${profitColor(c.profit)}`}>{fmtINR(c.profit)}</span>
              <span className="text-slate-400 text-xs">{expandedCluster === c.cluster_id ? '▲' : '▼'}</span>
            </div>
          </button>

          {expandedCluster === c.cluster_id && (
            <div className="p-3 border-t border-slate-100">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
                <KpiCard label="Sched Area" value={`${fmt(c.area_scheduled)} ac`} />
                <KpiCard label="Alloc Area" value={`${fmt(c.area_allocated)} ac`} accent="blue" />
                <KpiCard label="Remaining" value={`${fmt(c.area_remaining)} ac`} accent="amber" />
                <KpiCard label="Workers" value={`${c.allocated_workers}/${c.available_capacity_workers}`} />
                <KpiCard label="Profit" value={fmtINR(c.profit)} accent={c.profit >= 0 ? 'green' : 'red'} />
              </div>

              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-[11px]">
                  <thead className="bg-slate-800 text-slate-200">
                    <tr>
                      {['Booking', 'Farmer', 'Plot', 'Activity', 'Mukkadam', 'Total Area', 'Alloc Area', 'Remaining', 'Workers', 'Farmer ₹', 'Mukkadam ₹', 'Profit', 'Status'].map(h => (
                        <th key={h} className="px-2.5 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {jobs.length === 0 && (
                      <tr><td colSpan={13} className="px-3 py-5 text-center text-slate-400">No jobs for this cluster.</td></tr>
                    )}
                    {jobs.map((j, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-2.5 py-2 font-mono text-blue-600">{j.booking_id}</td>
                        <td className="px-2.5 py-2 font-medium text-slate-700">{j.farmer_name}</td>
                        <td className="px-2.5 py-2 text-slate-500">{j.plot_name || '—'}</td>
                        <td className="px-2.5 py-2 text-slate-700">{j.activity_name}</td>
                        <td className="px-2.5 py-2 text-slate-600">{j.mukkadam_name || '—'}</td>
                        <td className="px-2.5 py-2 text-right font-medium">{fmt(j.total_area)} ac</td>
                        <td className="px-2.5 py-2 text-right text-blue-600 font-medium">{fmt(j.allocated_area)} ac</td>
                        <td className="px-2.5 py-2 text-right text-amber-600">{fmt(j.remaining_area)} ac</td>
                        <td className="px-2.5 py-2 text-right">{j.allocated_workers}</td>
                        <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(j.farmer_price)}</td>
                        <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(j.mukkadam_price)}</td>
                        <td className={`px-2.5 py-2 text-right ${profitColor(j.profit)}`}>{fmtINR(j.profit)}</td>
                        <td className="px-2.5 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-medium ${statusBadge(j.allocation_status)}`}>
                            {j.allocation_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Day Panel (used in weeks accordion)
// ─────────────────────────────────────────────

function DayPanel({
  date,
  clusterId,
  farmerFilter,
  mukkadamFilter,
  activityFilter,
}: {
  date: string;
  clusterId: number | null;
  farmerFilter: string;
  mukkadamFilter: string;
  activityFilter: string;
}) {
  const [data, setData] = useState<DayApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params: Record<string, string> = { date };
    if (clusterId) params.cluster_id = String(clusterId);
    axios
      .get(`${API_BASE_URL}/api/tender-global-day-insights/`, { params })
      .then(r => setData(r.data))
      .catch(e => setError(e.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [date, clusterId]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        <span className="animate-pulse">Loading day data…</span>
      </div>
    );
  if (error || !data)
    return <div className="text-red-500 text-sm p-4">{error || 'Error'}</div>;

  const o = data.overall;

  const filteredJobs = data.jobs.filter(j => {
    if (clusterId && j.cluster_id !== clusterId) return false;
    if (farmerFilter && !j.farmer_name.toLowerCase().includes(farmerFilter.toLowerCase()))
      return false;
    if (mukkadamFilter && !(j.mukkadam_name || '').toLowerCase().includes(mukkadamFilter.toLowerCase()))
      return false;
    if (activityFilter && !j.activity_name.toLowerCase().includes(activityFilter.toLowerCase()))
      return false;
    return true;
  });

  // group by cluster
  const byCluster: Record<number, { cluster: DayClusterRow; jobs: DayJobRow[] }> = {};
  data.clusters.forEach(c => {
    byCluster[c.cluster_id] = { cluster: c, jobs: [] };
  });
  filteredJobs.forEach(j => {
    if (!byCluster[j.cluster_id]) return;
    byCluster[j.cluster_id].jobs.push(j);
  });

  return (
    <div className="space-y-3">
      {/* Overall pills */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        <KpiCard label="Activities" value={String(o.total_activities)} accent="indigo" />
        <KpiCard label="Area Sched" value={`${fmt(o.total_area_scheduled)} ac`} />
        <KpiCard label="Area Alloc" value={`${fmt(o.total_area_allocated)} ac`} accent="blue" />
        <KpiCard label="Remaining" value={`${fmt(o.total_area_remaining)} ac`} accent="amber" />
        <KpiCard
          label="Workers"
          value={`${o.total_allocated_workers}/${o.total_available_capacity_workers}`}
        />
        <KpiCard
          label="Profit"
          value={fmtINR(o.profit)}
          accent={o.profit >= 0 ? 'green' : 'red'}
        />
      </div>

      {/* Per-cluster accordion */}
      {Object.values(byCluster).map(({ cluster: c, jobs }) => (
        <div key={c.cluster_id} className="border border-slate-200 rounded-xl overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
            onClick={() =>
              setExpandedCluster(prev => (prev === c.cluster_id ? null : c.cluster_id))
            }
          >
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold text-slate-700">{c.cluster_name}</span>
              <span className="text-[11px] text-slate-500">
                {c.activities} activities · {fmt(c.area_allocated)} ac alloc · {c.allocated_workers} workers
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm ${profitColor(c.profit)}`}>{fmtINR(c.profit)}</span>
              <span className="text-slate-400 text-xs">{expandedCluster === c.cluster_id ? '▲' : '▼'}</span>
            </div>
          </button>

          {expandedCluster === c.cluster_id && (
            <div className="p-3 overflow-x-auto">
              {/* Cluster day stats */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
                <KpiCard label="Sched Area" value={`${fmt(c.area_scheduled)} ac`} />
                <KpiCard label="Alloc Area" value={`${fmt(c.area_allocated)} ac`} accent="blue" />
                <KpiCard label="Remaining" value={`${fmt(c.area_remaining)} ac`} accent="amber" />
                <KpiCard label="Workers" value={`${c.allocated_workers}/${c.available_capacity_workers}`} />
                <KpiCard
                  label="Profit"
                  value={fmtINR(c.profit)}
                  accent={c.profit >= 0 ? 'green' : 'red'}
                />
              </div>

              <table className="min-w-full text-[11px] rounded-lg overflow-hidden">
                <thead className="bg-slate-800 text-slate-200">
                  <tr>
                    {['Booking', 'Farmer', 'Plot', 'Activity', 'Mukkadam', 'Total Area', 'Alloc Area', 'Remaining', 'Workers', 'Farmer ₹', 'Mukkadam ₹', 'Profit', 'Status'].map(h => (
                      <th key={h} className="px-2.5 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {jobs.length === 0 && (
                    <tr>
                      <td colSpan={13} className="px-3 py-5 text-center text-slate-400">No jobs for this cluster on this day.</td>
                    </tr>
                  )}
                  {jobs.map((j, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      <td className="px-2.5 py-2 font-mono text-blue-600">{j.booking_id}</td>
                      <td className="px-2.5 py-2 font-medium text-slate-700">{j.farmer_name}</td>
                      <td className="px-2.5 py-2 text-slate-500">{j.plot_name || '—'}</td>
                      <td className="px-2.5 py-2 text-slate-700">{j.activity_name}</td>
                      <td className="px-2.5 py-2 text-slate-600">{j.mukkadam_name || '—'}</td>
                      <td className="px-2.5 py-2 text-right font-medium">{fmt(j.total_area)} ac</td>
                      <td className="px-2.5 py-2 text-right text-blue-600 font-medium">{fmt(j.allocated_area)} ac</td>
                      <td className="px-2.5 py-2 text-right text-amber-600">{fmt(j.remaining_area)} ac</td>
                      <td className="px-2.5 py-2 text-right">{j.allocated_workers}</td>
                      <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(j.farmer_price)}</td>
                      <td className="px-2.5 py-2 text-right text-slate-600">{fmtINR(j.mukkadam_price)}</td>
                      <td className={`px-2.5 py-2 text-right ${profitColor(j.profit)}`}>{fmtINR(j.profit)}</td>
                      <td className="px-2.5 py-2">
                        <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-medium ${statusBadge(j.allocation_status)}`}>
                          {j.allocation_status}
                        </span>
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
  );
}

// ─────────────────────────────────────────────
// Cluster Jobs Tab
// ─────────────────────────────────────────────

function ClusterJobsTab({
  clusterJobs,
  selectedClusterId,
  farmerFilter,
  activityFilter,
}: {
  clusterJobs: ClusterJobsBlock[];
  selectedClusterId: number | null;
  farmerFilter: string;
  activityFilter: string;
}) {
  const [expandedClusters, setExpandedClusters] = useState<Set<number>>(new Set());

  const toggle = (id: number) => {
    setExpandedClusters(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const blocks = clusterJobs.filter(b => !selectedClusterId || b.cluster_id === selectedClusterId);

  return (
    <div className="space-y-2">
      {blocks.map(block => {
        const filtered = block.jobs.filter(j => {
          if (farmerFilter && !j.farmer_name.toLowerCase().includes(farmerFilter.toLowerCase())) return false;
          if (activityFilter && !j.activity_name.toLowerCase().includes(activityFilter.toLowerCase())) return false;
          return true;
        });
        const isOpen = expandedClusters.has(block.cluster_id);
        const totalArea = filtered.reduce((s, j) => s + j.total_area, 0);
        const allocArea = filtered.reduce((s, j) => s + j.allocated_area, 0);
        const workers = filtered.reduce((s, j) => s + j.allocated_workers, 0);

        return (
          <div key={block.cluster_id} className="border border-slate-200 rounded-xl overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors"
              onClick={() => toggle(block.cluster_id)}
            >
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-sm font-bold text-slate-800">{block.cluster_name}</span>
                <span className="text-xs text-slate-400">{filtered.length} jobs</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span>{fmt(totalArea)} ac total · {fmt(allocArea)} ac alloc · {workers} workers</span>
                <span>{isOpen ? '▲' : '▼'}</span>
              </div>
            </button>

            {isOpen && (
              <div className="overflow-x-auto border-t border-slate-100">
                <table className="min-w-full text-[11px]">
                  <thead className="bg-slate-800 text-slate-200">
                    <tr>
                      {['Job ID', 'Farmer', 'Plot', 'Activity', 'Sched Date', 'Total Area', 'Alloc Area', 'Remaining', 'Est Workers', 'Alloc Workers', 'Alloc Count', 'Status'].map(h => (
                        <th key={h} className="px-2.5 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {filtered.map((j, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-2.5 py-2 font-mono text-blue-600">{j.job_id}</td>
                        <td className="px-2.5 py-2 font-medium text-slate-700">{j.farmer_name}</td>
                        <td className="px-2.5 py-2 text-slate-500">{j.plot_name || '—'}</td>
                        <td className="px-2.5 py-2 text-slate-700">{j.activity_name}</td>
                        <td className="px-2.5 py-2 text-slate-500">{j.scheduled_date || '—'}</td>
                        <td className="px-2.5 py-2 text-right font-medium">{fmt(j.total_area)} ac</td>
                        <td className="px-2.5 py-2 text-right text-blue-600 font-medium">{fmt(j.allocated_area)} ac</td>
                        <td className="px-2.5 py-2 text-right text-amber-600">{fmt(j.remaining_area)} ac</td>
                        <td className="px-2.5 py-2 text-right">{j.estimated_workers}</td>
                        <td className="px-2.5 py-2 text-right">{j.allocated_workers}</td>
                        <td className="px-2.5 py-2 text-right">{j.allocations_count}</td>
                        <td className="px-2.5 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded-full border text-[10px] font-medium ${statusBadge(j.allocation_status)}`}>
                            {j.allocation_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={12} className="py-5 text-center text-slate-400">No jobs match filters.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────
// Mukkadams Tab
// ─────────────────────────────────────────────

function MukkadamsTab({
  data,
  mukkadamFilter,
  selectedClusterId,
}: {
  data: MukkadamSummaryRow[];
  mukkadamFilter: string;
  selectedClusterId: number | null;
}) {
  const [expanded, setExpanded] = useState<Set<string | number>>(new Set());
  const [selectedWeekDay, setSelectedWeekDay] = useState<Record<string | number, string>>({});

  const toggle = (id: string | number) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const filtered = data.filter(m =>
    !mukkadamFilter || m.mukkadam_name.toLowerCase().includes(mukkadamFilter.toLowerCase()),
  );

  return (
    <div className="space-y-2">
      {filtered.map(m => {
        const isOpen = expanded.has(m.mukkadam_id);
        const clusters = selectedClusterId
          ? m.clusters.filter(c => c.cluster_id === selectedClusterId)
          : m.clusters;

        return (
          <div key={m.mukkadam_id} className="border border-slate-200 rounded-xl overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors"
              onClick={() => toggle(m.mukkadam_id)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-bold">
                  {m.mukkadam_name.charAt(0).toUpperCase()}
                </div>
                <div className="text-left">
                  <div className="text-sm font-bold text-slate-800">{m.mukkadam_name}</div>
                  <div className="text-[11px] text-slate-400">{clusters.length} clusters · {fmt(m.total_area_allocated)} ac total</div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right hidden md:block">
                  <div className={`text-sm font-bold ${profitColor(m.profit)}`}>{fmtINR(m.profit)}</div>
                  <div className="text-[11px] text-slate-400">{fmtINR(m.profit_per_acre)}/ac</div>
                </div>
                <span className="text-slate-400 text-xs">{isOpen ? '▲' : '▼'}</span>
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-slate-100 p-4 space-y-4 bg-slate-50/50">
                {/* Summary KPIs */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <KpiCard label="Area Alloc" value={`${fmt(m.total_area_allocated)} ac`} accent="indigo" />
                  <KpiCard label="Farmer Paid" value={fmtINR(m.total_farmer_amount)} />
                  <KpiCard label="Mukkadam Paid" value={fmtINR(m.total_mukkadam_amount)} accent="amber" />
                  <KpiCard label="Profit" value={fmtINR(m.profit)} accent={m.profit >= 0 ? 'green' : 'red'} sub={`${fmtINR(m.profit_per_acre)}/ac`} />
                </div>

                {/* Cluster breakdown table */}
                <div>
                  <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Cluster-wise Breakdown</p>
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="min-w-full text-[11px]">
                      <thead className="bg-slate-800 text-slate-200">
                        <tr>
                          {['Cluster', 'Allocations', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit'].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {clusters.map(c => (
                          <tr key={c.cluster_id} className="hover:bg-slate-50">
                            <td className="px-3 py-2 font-medium text-slate-700">{c.cluster_name}</td>
                            <td className="px-3 py-2 text-right">{c.allocations}</td>
                            <td className="px-3 py-2 text-right text-blue-600">{fmt(c.area_alloc)} ac</td>
                            <td className="px-3 py-2 text-right text-emerald-600">{fmt(c.area_done)} ac</td>
                            <td className="px-3 py-2 text-right">{fmtINR(c.farmer_amount)}</td>
                            <td className="px-3 py-2 text-right">{fmtINR(c.mukkadam_amount)}</td>
                            <td className={`px-3 py-2 text-right ${profitColor(c.profit)}`}>{fmtINR(c.profit)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
      {filtered.length === 0 && (
        <div className="text-center py-12 text-slate-400 text-sm">No mukkadams found.</div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Farmers Tab
// ─────────────────────────────────────────────

function FarmersTab({
  data,
  farmerFilter,
  selectedClusterId,
}: {
  data: FarmerSummaryRow[];
  farmerFilter: string;
  selectedClusterId: number | null;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const filtered = data.filter(f =>
    !farmerFilter || f.farmer_name.toLowerCase().includes(farmerFilter.toLowerCase()),
  );

  return (
    <div className="space-y-2">
      {filtered.map(f => {
        const isOpen = expanded.has(f.farmer_id);
        const clusters = selectedClusterId
          ? f.clusters.filter(c => c.cluster_id === selectedClusterId)
          : f.clusters;

        return (
          <div key={f.farmer_id} className="border border-slate-200 rounded-xl overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors"
              onClick={() => toggle(f.farmer_id)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-green-100 text-green-700 flex items-center justify-center text-xs font-bold">
                  {f.farmer_name.charAt(0).toUpperCase()}
                </div>
                <div className="text-left">
                  <div className="text-sm font-bold text-slate-800">{f.farmer_name}</div>
                  <div className="text-[11px] text-slate-400">{clusters.length} clusters · {fmt(f.total_area_allocated)} ac total</div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right hidden md:block">
                  <div className={`text-sm font-bold ${profitColor(f.profit)}`}>{fmtINR(f.profit)}</div>
                  <div className="text-[11px] text-slate-400">{fmtINR(f.profit_per_acre)}/ac</div>
                </div>
                <span className="text-slate-400 text-xs">{isOpen ? '▲' : '▼'}</span>
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-slate-100 p-4 space-y-4 bg-slate-50/50">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <KpiCard label="Area Alloc" value={`${fmt(f.total_area_allocated)} ac`} accent="green" />
                  <KpiCard label="Farmer Paid" value={fmtINR(f.total_farmer_amount)} />
                  <KpiCard label="Mukkadam Paid" value={fmtINR(f.total_mukkadam_amount)} accent="amber" />
                  <KpiCard label="Profit" value={fmtINR(f.profit)} accent={f.profit >= 0 ? 'green' : 'red'} sub={`${fmtINR(f.profit_per_acre)}/ac`} />
                </div>

                <div>
                  <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Cluster-wise Breakdown</p>
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="min-w-full text-[11px]">
                      <thead className="bg-slate-800 text-slate-200">
                        <tr>
                          {['Cluster', 'Allocations', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit'].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {clusters.map(c => (
                          <tr key={c.cluster_id} className="hover:bg-slate-50">
                            <td className="px-3 py-2 font-medium text-slate-700">{c.cluster_name}</td>
                            <td className="px-3 py-2 text-right">{c.allocations}</td>
                            <td className="px-3 py-2 text-right text-blue-600">{fmt(c.area_alloc)} ac</td>
                            <td className="px-3 py-2 text-right text-emerald-600">{fmt(c.area_done)} ac</td>
                            <td className="px-3 py-2 text-right">{fmtINR(c.farmer_amount)}</td>
                            <td className="px-3 py-2 text-right">{fmtINR(c.mukkadam_amount)}</td>
                            <td className={`px-3 py-2 text-right ${profitColor(c.profit)}`}>{fmtINR(c.profit)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
      {filtered.length === 0 && (
        <div className="text-center py-12 text-slate-400 text-sm">No farmers found.</div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Weeks Tab with click-to-day-drill-down
// ─────────────────────────────────────────────

function WeeksTab({
  weeks,
  selectedClusterId,
  farmerFilter,
  mukkadamFilter,
  activityFilter,
}: {
  weeks: WeekSummaryRow[];
  selectedClusterId: number | null;
  farmerFilter: string;
  mukkadamFilter: string;
  activityFilter: string;
}) {
  const [expandedWeek, setExpandedWeek] = useState<string | null>(null);

  // Generate 7 days for a given week_start
  const weekDays = (weekStart: string) => {
    const days = [];
    const d = new Date(weekStart);
    for (let i = 0; i < 7; i++) {
      const n = new Date(d);
      n.setDate(d.getDate() + i);
      days.push(n.toISOString().slice(0, 10));
    }
    return days;
  };

  return (
    <div className="space-y-2">
      {weeks.map(w => {
        const isOpen = expandedWeek === w.week_start;
        const days = weekDays(w.week_start);

        return (
          <div key={w.week_start} className="border border-slate-200 rounded-xl overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors"
              onClick={() => setExpandedWeek(prev => (prev === w.week_start ? null : w.week_start))}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center text-xs font-bold">
                  W
                </div>
                <div className="text-left">
                  <div className="text-sm font-bold text-slate-800">Week of {w.week_start}</div>
                  <div className="text-[11px] text-slate-400">
                    {w.allocations} allocations · {fmt(w.total_area_allocated)} ac alloc · {fmt(w.total_area_completed)} ac done
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right hidden md:block">
                  <div className={`text-sm font-bold ${profitColor(w.profit)}`}>{fmtINR(w.profit)}</div>
                  <div className="text-[11px] text-slate-400">{fmtINR(w.profit_per_acre)}/ac</div>
                </div>
                <span className="text-slate-400 text-xs">{isOpen ? '▲' : '▼'}</span>
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-slate-100 p-4 bg-slate-50/50 space-y-4">
                {/* Week KPIs */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <KpiCard label="Allocations" value={String(w.allocations)} accent="indigo" />
                  <KpiCard label="Area Alloc" value={`${fmt(w.total_area_allocated)} ac`} accent="blue" />
                  <KpiCard label="Area Done" value={`${fmt(w.total_area_completed)} ac`} accent="green" />
                  <KpiCard label="Profit" value={fmtINR(w.profit)} accent={w.profit >= 0 ? 'green' : 'red'} sub={`${fmtINR(w.profit_per_acre)}/ac`} />
                </div>

                {/* Day-by-day */}
                <div>
                  <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Day-by-Day Detail</p>
                  <div className="space-y-2">
                    {days.map(day => (
                      <DayAccordionRow
                        key={day}
                        date={day}
                        clusterId={selectedClusterId}
                        farmerFilter={farmerFilter}
                        mukkadamFilter={mukkadamFilter}
                        activityFilter={activityFilter}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Lazy-loaded day row within weeks
function DayAccordionRow({
  date,
  clusterId,
  farmerFilter,
  mukkadamFilter,
  activityFilter,
}: {
  date: string;
  clusterId: number | null;
  farmerFilter: string;
  mukkadamFilter: string;
  activityFilter: string;
}) {
  const [open, setOpen] = useState(false);
  const dayLabel = new Date(date).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
      <button
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-50 transition-colors text-left"
        onClick={() => setOpen(o => !o)}
      >
        <span className="text-[12px] font-semibold text-slate-700">{dayLabel} <span className="text-slate-400 font-normal">({date})</span></span>
        <span className="text-slate-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="border-t border-slate-100 p-3">
          <DayPanel
            date={date}
            clusterId={clusterId}
            farmerFilter={farmerFilter}
            mukkadamFilter={mukkadamFilter}
            activityFilter={activityFilter}
          />
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Clusters Tab
// ─────────────────────────────────────────────

function ClustersTab({
  clusters,
  selectedClusterId,
  onSelectCluster,
}: {
  clusters: ClusterSummaryRow[];
  selectedClusterId: number | null;
  onSelectCluster: (id: number | null) => void;
}) {
  const { sorted, sort, toggle } = useSort(clusters, 'cluster_name');

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-800 text-slate-200">
          <tr>
            <Th label="Cluster" sortKey="cluster_name" currentSort={sort} onSort={toggle} />
            <Th label="Jobs" sortKey="jobs" right currentSort={sort} onSort={toggle} />
            <Th label="Area Alloc" sortKey="total_area_allocated" right currentSort={sort} onSort={toggle} />
            <Th label="Area Done" sortKey="total_area_completed" right currentSort={sort} onSort={toggle} />
            <Th label="Workers" sortKey="allocated_workers" right currentSort={sort} onSort={toggle} />
            <Th label="Farmer ₹" sortKey="farmer_amount" right currentSort={sort} onSort={toggle} />
            <Th label="Mukkadam ₹" sortKey="mukkadam_amount" right currentSort={sort} onSort={toggle} />
            <Th label="Profit" sortKey="profit" right currentSort={sort} onSort={toggle} />
            <Th label="₹/ac" sortKey="profit_per_acre" right currentSort={sort} onSort={toggle} />
            <Th label="Loss Alloc" sortKey="loss_allocations" right currentSort={sort} onSort={toggle} />
            <Th label="Disputes" sortKey="dispute_count" right currentSort={sort} onSort={toggle} />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map(c => (
            <tr
              key={c.cluster_id}
              className={`cursor-pointer transition-colors ${selectedClusterId === c.cluster_id ? 'bg-blue-50 border-l-4 border-l-blue-500' : 'hover:bg-slate-50'}`}
              onClick={() => onSelectCluster(selectedClusterId === c.cluster_id ? null : c.cluster_id)}
            >
              <td className="px-3 py-2.5 font-semibold text-slate-700">{c.cluster_name}</td>
              <td className="px-3 py-2.5 text-right">{c.jobs}</td>
              <td className="px-3 py-2.5 text-right text-blue-600 font-medium">{fmt(c.total_area_allocated)} ac</td>
              <td className="px-3 py-2.5 text-right text-emerald-600 font-medium">{fmt(c.total_area_completed)} ac</td>
              <td className="px-3 py-2.5 text-right">{c.allocated_workers}</td>
              <td className="px-3 py-2.5 text-right">{fmtINR(c.farmer_amount)}</td>
              <td className="px-3 py-2.5 text-right">{fmtINR(c.mukkadam_amount)}</td>
              <td className={`px-3 py-2.5 text-right ${profitColor(c.profit)}`}>{fmtINR(c.profit)}</td>
              <td className={`px-3 py-2.5 text-right ${profitColor(c.profit_per_acre)}`}>{fmtINR(c.profit_per_acre)}</td>
              <td className="px-3 py-2.5 text-right">{c.loss_allocations > 0 ? <span className="text-red-500 font-semibold">{c.loss_allocations}</span> : 0}</td>
              <td className="px-3 py-2.5 text-right">{c.dispute_count > 0 ? <span className="text-amber-500 font-semibold">{c.dispute_count}</span> : 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────

type TabKey = 'clusters' | 'jobs' | 'mukkadams' | 'farmers' | 'weeks' | 'day';

export function GlobalInsightsPanel() {
  const [data, setData] = useState<GlobalInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const today = new Date();
  const defaultEnd = today.toISOString().slice(0, 10);
  const defaultStart = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const [tab, setTab] = useState<TabKey>('clusters');
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [farmerFilter, setFarmerFilter] = useState('');
  const [mukkadamFilter, setMukkadamFilter] = useState('');
  const [activityFilter, setActivityFilter] = useState('');


  const fetchGlobal = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const res = await axios.get(`${API_BASE_URL}/api/tender-global-insights/`, { params });
      setData(res.data);
    } catch (e: any) {
      setError(e.message || 'Failed to load global insights');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => { fetchGlobal(); }, []);

  const handleExport = () => {
    if (!data) return;
    const wb = XLSX.utils.book_new();
    const s = data.overall_summary;

    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Metric', 'Value'],
      ['Total Jobs', s.total_jobs],
      ['Total Activities', s.total_activities],
      ['Total Area Allocated (ac)', s.total_area_allocated.toFixed(2)],
      ['Total Area Completed (ac)', s.total_area_completed.toFixed(2)],
      ['Total Workers Allocated', s.total_allocated_workers],
      ['Farmer Amount (₹)', s.farmer_amount.toFixed(2)],
      ['Mukkadam Amount (₹)', s.mukkadam_amount.toFixed(2)],
      ['Profit (₹)', s.profit.toFixed(2)],
      ['Profit / Acre (₹)', s.profit_per_acre.toFixed(2)],
      ['Loss Allocations', s.loss_allocations],
      ['Dispute Count', s.dispute_count],
      ['Avg Efficiency Score', s.avg_efficiency_score.toFixed(1)],
    ]), 'Global Summary');

    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Cluster', 'Jobs', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit', 'Profit/ac', 'Workers', 'Loss', 'Disputes'],
      ...data.cluster_summary.map(c => [c.cluster_name, c.jobs, c.total_area_allocated.toFixed(2), c.total_area_completed.toFixed(2), c.farmer_amount.toFixed(2), c.mukkadam_amount.toFixed(2), c.profit.toFixed(2), c.profit_per_acre.toFixed(2), c.allocated_workers, c.loss_allocations, c.dispute_count]),
    ]), 'Cluster Summary');

    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([
      ['Week Start', 'Allocations', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit', 'Profit/ac'],
      ...data.week_summary.map(w => [w.week_start, w.allocations, w.total_area_allocated.toFixed(2), w.total_area_completed.toFixed(2), w.farmer_amount.toFixed(2), w.mukkadam_amount.toFixed(2), w.profit.toFixed(2), w.profit_per_acre.toFixed(2)]),
    ]), 'Week Summary');

    const cjRows: any[][] = [['Cluster', 'Job ID', 'Farmer', 'Plot', 'Activity', 'Sched Date', 'Total Area', 'Alloc Area', 'Remaining', 'Est Workers', 'Alloc Workers', 'Alloc Count', 'Status']];
    data.cluster_jobs.forEach(b => b.jobs.forEach(j => cjRows.push([b.cluster_name, j.job_id, j.farmer_name, j.plot_name || '', j.activity_name, j.scheduled_date || '', j.total_area.toFixed(2), j.allocated_area.toFixed(2), j.remaining_area.toFixed(2), j.estimated_workers, j.allocated_workers, j.allocations_count, j.allocation_status])));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(cjRows), 'Cluster Jobs');

    const mukRows: any[][] = [['Mukkadam', 'Cluster', 'Allocations', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit']];
    data.mukkadam_summary.forEach(m => m.clusters.forEach(c => mukRows.push([m.mukkadam_name, c.cluster_name, c.allocations, c.area_alloc.toFixed(2), c.area_done.toFixed(2), c.farmer_amount.toFixed(2), c.mukkadam_amount.toFixed(2), c.profit.toFixed(2)])));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(mukRows), 'Mukkadam Summary');

    const farmerRows: any[][] = [['Farmer', 'Cluster', 'Allocations', 'Area Alloc', 'Area Done', 'Farmer ₹', 'Mukkadam ₹', 'Profit']];
    data.farmer_summary.forEach(f => f.clusters.forEach(c => farmerRows.push([f.farmer_name, c.cluster_name, c.allocations, c.area_alloc.toFixed(2), c.area_done.toFixed(2), c.farmer_amount.toFixed(2), c.mukkadam_amount.toFixed(2), c.profit.toFixed(2)])));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(farmerRows), 'Farmer Summary');

    XLSX.writeFile(wb, `Global_Insights_${data.date_range.start}_to_${data.date_range.end}.xlsx`);
  };

  if (loading)
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-400">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading global insights…</span>
      </div>
    );

  if (error || !data)
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-500 gap-2">
        <span className="text-2xl">⚠️</span>
        <span className="text-sm">{error || 'Failed to load global insights'}</span>
        <button onClick={fetchGlobal} className="text-xs bg-red-50 border border-red-200 text-red-600 px-3 py-1 rounded-lg hover:bg-red-100">
          Retry
        </button>
      </div>
    );

  const s = data.overall_summary;

  const tabs: { key: TabKey; label: string; icon: string }[] = [
    { key: 'clusters', label: 'Clusters', icon: '🏘️' },
    { key: 'jobs', label: 'Cluster Jobs', icon: '🌾' },
    { key: 'mukkadams', label: 'Mukkadams', icon: '👷' },
    { key: 'farmers', label: 'Farmers', icon: '🧑‍🌾' },
    { key: 'weeks', label: 'Weeks', icon: '📅' },
    { key: 'day', label: 'Day View', icon: '📆' },
  ];

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-extrabold text-slate-900 tracking-tight">🌍 Global Cluster Insights</h1>
            <p className="text-xs text-slate-400 mt-0.5">{data.date_range.start} → {data.date_range.end}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 bg-slate-100 rounded-lg px-3 py-1.5">
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="bg-transparent text-xs text-slate-700 outline-none"
              />
              <span className="text-slate-400 text-xs">→</span>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="bg-transparent text-xs text-slate-700 outline-none"
              />
            </div>
            <button
              onClick={fetchGlobal}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors"
            >
              Apply
            </button>
            <button
              onClick={handleExport}
              className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 transition-colors"
            >
              ↓ Export
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mt-3">
          <input
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs bg-white placeholder-slate-400 focus:ring-1 focus:ring-blue-400 outline-none"
            placeholder="🔍 Filter farmer…"
            value={farmerFilter}
            onChange={e => setFarmerFilter(e.target.value)}
          />
          <input
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs bg-white placeholder-slate-400 focus:ring-1 focus:ring-blue-400 outline-none"
            placeholder="🔍 Filter mukkadam…"
            value={mukkadamFilter}
            onChange={e => setMukkadamFilter(e.target.value)}
          />
          <input
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs bg-white placeholder-slate-400 focus:ring-1 focus:ring-blue-400 outline-none"
            placeholder="🔍 Filter activity…"
            value={activityFilter}
            onChange={e => setActivityFilter(e.target.value)}
          />
          {selectedClusterId && (
            <button
              onClick={() => setSelectedClusterId(null)}
              className="px-3 py-1.5 bg-blue-100 text-blue-700 border border-blue-200 text-xs font-medium rounded-lg hover:bg-blue-200 transition-colors flex items-center gap-1"
            >
              <span>Cluster filter active</span>
              <span>✕</span>
            </button>
          )}
        </div>
      </div>

      <div className="px-6 py-4 space-y-4">
        {/* KPIs */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          <KpiCard label="Total Jobs" value={String(s.total_jobs)} />
          <KpiCard label="Activities" value={String(s.total_activities)} />
          <KpiCard label="Area Alloc" value={`${fmt(s.total_area_allocated)} ac`} accent="blue" />
          <KpiCard label="Area Done" value={`${fmt(s.total_area_completed)} ac`} accent="green" />
          <KpiCard label="Workers" value={String(s.total_allocated_workers)} />
          <KpiCard label="Profit" value={fmtINR(s.profit)} accent={s.profit >= 0 ? 'green' : 'red'} sub={`${fmtINR(s.profit_per_acre)}/ac`} />
          <KpiCard label="Loss Allocs" value={String(s.loss_allocations)} accent={s.loss_allocations > 0 ? 'red' : undefined} />
          <KpiCard label="Disputes" value={String(s.dispute_count)} accent={s.dispute_count > 0 ? 'amber' : undefined} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 bg-white rounded-t-xl px-2 pt-2 overflow-x-auto">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold whitespace-nowrap transition-colors rounded-t-lg ${tab === t.key ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'}`}
            >
              <span>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab body */}
        <div className="bg-white rounded-b-xl rounded-tr-xl border border-slate-200 p-4">
          {tab === 'clusters' && (
            <>
              <SectionHeader title="Cluster Summary" count={data.cluster_summary.length} />
              <p className="text-[11px] text-slate-400 mb-3">Click a row to filter all tabs by that cluster.</p>
              <ClustersTab
                clusters={data.cluster_summary}
                selectedClusterId={selectedClusterId}
                onSelectCluster={setSelectedClusterId}
              />
            </>
          )}

          {tab === 'jobs' && (
            <>
              <SectionHeader title="Cluster Jobs & Allocation Status" />
              <p className="text-[11px] text-slate-400 mb-3">Each cluster is expandable. Shows job-level: plot, activity, area, allocation detail.</p>
              <ClusterJobsTab
                clusterJobs={data.cluster_jobs}
                selectedClusterId={selectedClusterId}
                farmerFilter={farmerFilter}
                activityFilter={activityFilter}
              />
            </>
          )}

          {tab === 'mukkadams' && (
            <>
              <SectionHeader title="Mukkadam Summary" count={data.mukkadam_summary.length} />
              <MukkadamsTab
                data={data.mukkadam_summary}
                mukkadamFilter={mukkadamFilter}
                selectedClusterId={selectedClusterId}
              />
            </>
          )}

          {tab === 'farmers' && (
            <>
              <SectionHeader title="Farmer Summary" count={data.farmer_summary.length} />
              <FarmersTab
                data={data.farmer_summary}
                farmerFilter={farmerFilter}
                selectedClusterId={selectedClusterId}
              />
            </>
          )}

          {tab === 'weeks' && (
            <>
              <SectionHeader title="Week Summary" count={data.week_summary.length} />
              <p className="text-[11px] text-slate-400 mb-3">Click a week to expand day-by-day detail. Click each day to see cluster and job breakdown.</p>
              <WeeksTab
                weeks={data.week_summary}
                selectedClusterId={selectedClusterId}
                farmerFilter={farmerFilter}
                mukkadamFilter={mukkadamFilter}
                activityFilter={activityFilter}
              />
            </>
          )}

          {tab === 'day' && (
            <>
              <SectionHeader title="Day View" />
              <p className="text-[11px] text-slate-400 mb-4">
                Showing all dates from <strong>{startDate}</strong> to <strong>{endDate}</strong>. Each tile shows activities, area allocated, workers and profit. Click any tile with data to see full detail.
              </p>
              <CalendarDayTab
                startDate={startDate}
                endDate={endDate}
                clusterId={selectedClusterId}
                farmerFilter={farmerFilter}
                mukkadamFilter={mukkadamFilter}
                activityFilter={activityFilter}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}