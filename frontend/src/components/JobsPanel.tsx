// components/JobsPanel.tsx
import React, { useState, useMemo, useEffect } from 'react';
import {
  MapPin,
  ChevronDown,
  ChevronUp,
  Phone,
  Users,
  Zap,
  Star,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { Job } from '../types/types';
import { API_BASE_URL } from '@/types/config';
import './job.css';
import Dialpad from '@/call';

interface JobsPanelProps {
  jobs: Job[];
  loading: boolean;
  onRefresh: () => void;
  onFarmerSelect: (farmerId: string, farmerName: string) => void;
  clusterId: number;
}

interface FarmerSummary {
  farmerId: string;
  farmerName: string;
  plotCount: number;
  totalActivities: number;
  doneCount: number;
  remainingArea: number;
  nearestDate: string | null;
  mobileNumber: string;
  poc: string;
  jobs: Job[];
  totalAcres: number;
}

type Cluster = {
  id: number;
  name: string;
  district: string;
  taluka: string;
  village: string;
  date_range: { start_date: string; end_date: string };
  state_code: string;
  district_codes: string[];
};

type MukkadamActivityRate = {
  activity_id: number;
  activity_name: string;
  rate_per_acre: number;
  productivity_per_worker: number;
  is_active: boolean;
};

type MukkadamDetail = {
  mukkadam_id: number;
  mukkadam_name: string;
  mobile_numbers: string;
  village: string;
  taluka: string;
  district: string;
  crew_size: number;
  max_crew_capacity: number;
  is_permanent: boolean;
  has_smartphone: string;
  work_mode: string;
  start_date: string | null;
  end_date: string | null;
  efficiency: string;
  activity_rates: MukkadamActivityRate[];
};

// ─────────────────────────────────────────────
// Mukkadam Card component
// ─────────────────────────────────────────────
const MukkadamCard: React.FC<{
  mukkadam: MukkadamDetail;
  onCall: (number: string) => void;
}> = ({ mukkadam, onCall }) => {
  const [expanded, setExpanded] = useState(false);

  const primaryNumber = (() => {
    const raw = String(mukkadam.mobile_numbers || '').split(',')[0].trim();
    return raw.startsWith('91') && raw.length === 12 ? raw.slice(2) : raw;
  })();

  const initials = (mukkadam.mukkadam_name || '')
    .split(' ')
    .slice(0, 2)
    .map((n: string) => n[0])
    .join('')
    .toUpperCase();

  const activeRates = mukkadam.activity_rates?.filter(r => r.is_active) || [];

  return (
    <div
      className={`rounded-xl border transition-all duration-200 overflow-hidden mb-2 ${
        expanded
          ? 'border-violet-300 bg-violet-50/40 shadow-sm shadow-violet-100'
          : 'border-stone-200 bg-white hover:border-stone-300 hover:shadow-sm'
      }`}
    >
      {/* Header row */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left p-3 bg-transparent"
      >
        <div className="flex items-start gap-2.5">
          {/* Avatar */}
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 transition-all duration-150"
            style={{
              backgroundColor: expanded ? '#7c3aed' : '#f5f5f4',
              color: expanded ? '#fff' : '#78716c',
              boxShadow: expanded ? '0 1px 4px rgba(124,58,237,0.25)' : 'none',
            }}
          >
            {initials}
          </div>

          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm text-stone-800 truncate leading-tight">
              {mukkadam.mukkadam_name}
            </p>
            <div className="flex flex-wrap items-center gap-1.5 mt-1 text-xs text-stone-400">
              {/* Crew badge */}
              <span className="inline-flex items-center gap-1">
                <Users size={9} />
                {mukkadam.crew_size} crew
                {mukkadam.max_crew_capacity > 0 && mukkadam.max_crew_capacity !== mukkadam.crew_size
                  ? ` / ${mukkadam.max_crew_capacity} max`
                  : ''}
              </span>
              {mukkadam.village && (
                <>
                  <span className="text-stone-300 text-[10px]">·</span>
                  <span>{mukkadam.village}</span>
                </>
              )}
              {mukkadam.is_permanent && (
                <>
                  <span className="text-stone-300 text-[10px]">·</span>
                  <span className="text-violet-600 font-medium">Permanent</span>
                </>
              )}
            </div>
          </div>

          <div className="mt-1.5 shrink-0">
            {expanded ? (
              <ChevronUp size={14} className="text-violet-500" />
            ) : (
              <ChevronDown size={14} className="text-stone-300" />
            )}
          </div>
        </div>

        {/* Phone + call button row */}
        <div className="flex items-center gap-3 mt-2 ml-11 flex-wrap">
          {primaryNumber && (
            <div className="flex items-center gap-1.5">
              <Phone size={10} className="text-stone-300" />
              <span className="text-xs text-stone-400 tabular-nums">{primaryNumber}</span>
            </div>
          )}
          {activeRates.length > 0 && (
            <span className="text-xs text-stone-400">
              <Zap size={9} className="inline mr-0.5 text-amber-400" />
              {activeRates.length} activity rates
            </span>
          )}
          {primaryNumber && (
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                onCall(primaryNumber);
              }}
              className="ml-auto inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-violet-600 text-white shadow-sm hover:bg-violet-700"
            >
              <Phone size={10} />
              Call
            </button>
          )}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="pt-2 px-3 pb-3 border-t border-violet-200/60 space-y-3">

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'District', value: mukkadam.district },
              { label: 'Taluka', value: mukkadam.taluka },
              { label: 'Village', value: mukkadam.village },
              { label: 'Work Mode', value: mukkadam.work_mode || '—' },
              { label: 'Smartphone', value: mukkadam.has_smartphone === 'yes' ? '✅ Yes' : '❌ No' },
              {
                label: 'Efficiency',
                value: mukkadam.efficiency
                  ? `${(Number(mukkadam.efficiency) * 100).toFixed(0)}%`
                  : '—',
              },
              {
                label: 'Start Date',
                value: mukkadam.start_date
                  ? new Date(mukkadam.start_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
                  : '—',
              },
              {
                label: 'End Date',
                value: mukkadam.end_date
                  ? new Date(mukkadam.end_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
                  : '—',
              },
            ]
              .filter(item => item.value && item.value !== '—' || item.label === 'Smartphone')
              .map(item => (
                <div key={item.label} className="bg-white rounded-lg border border-stone-100 px-2.5 py-2">
                  <p className="text-[10px] text-stone-400 mb-0.5">{item.label}</p>
                  <p className="text-[12px] font-semibold text-stone-700">{item.value}</p>
                </div>
              ))}
          </div>

          {/* Activity rates */}
          {activeRates.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-stone-500 uppercase tracking-[0.1em] mb-1.5">
                Activity Rates
              </p>
              <div className="rounded-xl overflow-hidden border border-stone-200">
                {activeRates.map((rate, idx) => (
                  <div
                    key={rate.activity_id}
                    className={`flex items-center justify-between px-3 py-2 text-xs ${
                      idx > 0 ? 'border-t border-stone-100' : ''
                    } ${idx % 2 === 0 ? 'bg-white' : 'bg-stone-50/60'}`}
                  >
                    <div className="flex items-center gap-1.5">
                      <Star size={9} className="text-amber-400 shrink-0" />
                      <span className="text-stone-700 font-medium">{rate.activity_name}</span>
                    </div>
                    <div className="flex items-center gap-3 text-right">
                      <span className="text-emerald-700 font-bold">
                        ₹{Number(rate.rate_per_acre).toLocaleString('en-IN')}/ac
                      </span>
                      {rate.productivity_per_worker > 0 && (
                        <span className="text-stone-400 text-[10px]">
                          {rate.productivity_per_worker} ac/worker
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeRates.length === 0 && (
            <p className="text-xs text-stone-400 text-center py-2">No activity rates configured</p>
          )}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
// Main JobsPanel
// ─────────────────────────────────────────────
const JobsPanel: React.FC<JobsPanelProps> = ({
  jobs,
  loading,
  onRefresh,
  onFarmerSelect,
  clusterId,
}) => {
  const [activeTab, setActiveTab] = useState<'farmers' | 'mukkadams'>('farmers');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedFarmerId, setExpandedFarmerId] = useState<string | null>(null);
  const [expandedPlotId, setExpandedPlotId] = useState<number | null>(null);

  const [farmerPlots, setFarmerPlots] = useState<Record<string, any[]>>({});
  const [plotJobs, setPlotJobs] = useState<Record<number, Job[]>>({});
  const [allActivities, setAllActivities] = useState<any[]>([]);
  const [clusterCalendar, setClusterCalendar] = useState<any[]>([]);
  const [farmers, setFarmers] = useState<any[]>([]);

  // Mukkadams state
  const [mukkadams, setMukkadams] = useState<MukkadamDetail[]>([]);
  const [mukkadamsLoading, setMukkadamsLoading] = useState(false);

  const [editingActivity, setEditingActivity] = useState<any>(null);
  const [cluster, setCluster] = useState<Cluster | null>(null);
  const [farmerAcresMap, setFarmerAcresMap] = useState<Record<string, number>>({});
  const [dialpadOpen, setDialpadOpen] = useState(false);
  const [dialpadNumber, setDialpadNumber] = useState('');

  // ── Load on mount ──────────────────────────
  useEffect(() => {
    loadClusterCalendar();
    loadAllActivities();
    loadFarmers();
  }, [clusterId]);

  useEffect(() => {
    const loadCluster = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/`);
        if (!res.ok) return;
        const data = await res.json();
        setCluster(data);
      } catch (e) {
        console.error('Failed to load cluster', e);
      }
    };
    if (clusterId) loadCluster();
  }, [clusterId]);

  useEffect(() => {
    const fetchFarmerAcres = async () => {
      const res = await fetch(`${API_BASE_URL}/api/farmers/?cluster_id=${clusterId}`);
      const data = await res.json();
      const map: Record<string, number> = {};
      data.forEach((f: any) => { map[f.farmer_id] = Number(f.total_acres) || 0; });
      setFarmerAcresMap(map);
    };
    fetchFarmerAcres();
  }, [clusterId]);

  // Load mukkadams when tab switches to mukkadams
  useEffect(() => {
    if (activeTab === 'mukkadams' && mukkadams.length === 0) {
      loadMukkadams();
    }
  }, [activeTab]);

  const loadMukkadams = async () => {
    setMukkadamsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadams/?cluster_id=${clusterId}`,
      );
      const data = await res.json();
      setMukkadams(data);
    } catch (e) {
      console.error('Failed to load mukkadams', e);
    } finally {
      setMukkadamsLoading(false);
    }
  };

  const loadClusterCalendar = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/clusters/${clusterId}/activity-calendar/`);
      const data = await res.json();
      setClusterCalendar(data.activities || []);
    } catch (e) { console.error(e); }
  };

  const loadAllActivities = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/activities/`);
      const data = await res.json();
      setAllActivities(data);
    } catch (e) { console.error(e); }
  };

  const loadFarmers = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmers/?cluster_id=${clusterId}`);
      const data = await res.json();
      setFarmers(data);
    } catch (e) { console.error(e); }
  };

  const loadFarmerPlots = async (farmerId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/plots/?farmer_id=${farmerId}&cluster_id=${clusterId}`);
      const data = await res.json();
      setFarmerPlots(prev => ({ ...prev, [farmerId]: data }));
      return data;
    } catch (e) { return []; }
  };

  const loadPlotJobs = async (plotId: number) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/jobs/?plot=${plotId}`);
      const data = await res.json();
      const filtered = data.map((job: any) => ({
        ...job,
        activities: (job.activities || []).filter(
          (a: any) => Number(a.plot) === Number(plotId) || Number(a.plot_id) === Number(plotId),
        ),
      }));
      setPlotJobs(prev => ({ ...prev, [plotId]: filtered }));
      return filtered;
    } catch (e) { return []; }
  };

  const handleFarmerClick = async (farmerId: string, farmerName: string) => {
    if (expandedFarmerId === farmerId) {
      setExpandedFarmerId(null);
      setExpandedPlotId(null);
      return;
    }
    setExpandedFarmerId(farmerId);
    setExpandedPlotId(null);
    onFarmerSelect(farmerId, farmerName);
    if (!farmerPlots[farmerId]) await loadFarmerPlots(farmerId);
  };

  const handlePlotClick = async (plotId: number, plotArea: number, farmerId: string) => {
    if (expandedPlotId === plotId) { setExpandedPlotId(null); return; }
    setExpandedPlotId(plotId);
    await loadPlotJobs(plotId);
  };

  const handleEditActivity = async () => {
    if (!editingActivity) return;
    if (editingActivity.total_area < editingActivity.allocated_area) {
      toast.error(`Cannot be less than allocated area (${editingActivity.allocated_area} ac)`);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/job-activities/${editingActivity.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_area: editingActivity.total_area,
          rate_per_acre: editingActivity.rate_per_acre,
          scheduled_date: editingActivity.scheduled_date,
          is_strict: editingActivity.is_strict,
        }),
      });
      if (res.ok) {
        toast.success('Updated!');
        setEditingActivity(null);
        await loadPlotJobs(editingActivity.plotId);
        onRefresh();
        window.location.reload();
      } else {
        const err = await res.json();
        toast.error(err.error || 'Failed');
      }
    } catch (e) { toast.error('Failed'); }
  };

  // ── Farmer summaries ───────────────────────
  const todayStr = new Date().toISOString().split('T')[0];

  const farmerSummaries = useMemo<FarmerSummary[]>(() => {
    if (!jobs || jobs.length === 0) return [];
    const filtered = jobs.filter(job =>
      job.farmer_name.toLowerCase().includes(searchTerm.toLowerCase()),
    );
    const map = new Map<string, FarmerSummary>();

    filtered.forEach(job => {
      if (!map.has(job.farmer_id)) {
        map.set(job.farmer_id, {
          farmerId: job.farmer_id,
          farmerName: job.farmer_name,
          plotCount: 0,
          totalAcres: Number(farmerAcresMap[job.farmer_id]) || 0,
          totalActivities: 0,
          remainingArea: 0,
          doneCount: 0,
          nearestDate: null,
          jobs: [],
          mobileNumber: (() => {
            const farmerData = farmers.find((f: any) => f.farmer_id === job.farmer_id);
            const raw = farmerData?.phone_number || '';
            const str = String(raw);
            return str.startsWith('91') && str.length === 12 ? str.slice(2) : str;
          })(),
          poc: (job as any).point_of_contact || '',
        });
      }
      const s = map.get(job.farmer_id)!;
      s.jobs.push(job);
      const activities = job.activities || [];

      activities.forEach((a: any) => {
        if (a.scheduled_date && a.scheduled_date >= todayStr) {
          if (!s.nearestDate || a.scheduled_date < s.nearestDate) s.nearestDate = a.scheduled_date;
        }
      });

      activities.forEach((a: any) => {
        s.totalActivities += 1;
        const isFullyAllocated = Number(a.allocated_area) >= Number(a.total_area);
        const isPast = a.scheduled_date < todayStr;
        const isNextActivity = a.scheduled_date === s.nearestDate;
        if (!isFullyAllocated && (isPast || isNextActivity || a.scheduled_date === todayStr)) {
          s.remainingArea += Number(a.total_area) - Number(a.allocated_area);
        }
        if ((isPast || a.scheduled_date === todayStr) && isFullyAllocated) s.doneCount += 1;
      });
    });

    map.forEach(s => {
      const plots = new Set<number>();
      s.jobs.forEach(j => {
        (j.activities || []).forEach((act: any) => {
          if (act.plot) plots.add(Number(act.plot));
        });
      });
      s.plotCount = plots.size;
    });

    return Array.from(map.values()).sort((a, b) => {
      if (a.nearestDate && !b.nearestDate) return -1;
      if (!a.nearestDate && b.nearestDate) return 1;
      if (a.nearestDate !== b.nearestDate) {
        return (a.nearestDate || '') < (b.nearestDate || '') ? -1 : 1;
      }
      return b.remainingArea - a.remainingArea;
    });
  }, [jobs, searchTerm, farmerAcresMap, farmers]);

  // Filtered mukkadams
  const filteredMukkadams = useMemo(
    () => mukkadams.filter(m =>
      m.mukkadam_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.village?.toLowerCase().includes(searchTerm.toLowerCase()),
    ),
    [mukkadams, searchTerm],
  );

  return (
    <div className="jobs-panel flex flex-col h-full bg-white">
      {/* ── Header ─────────────────────────────── */}
      <div className="px-4 pt-3 pb-2 border-b border-stone-200 bg-white">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center shadow-sm">
              <MapPin size={15} className="text-white" />
            </div>
            <div>
              <p className="text-[11px] text-stone-400 leading-tight">Cluster</p>
              <h1 className="text-sm font-bold text-stone-800 leading-tight">{cluster?.name || '—'}</h1>
              <p className="text-[10px] text-stone-400">
                {cluster?.village || ''}{cluster?.district ? ` · ${cluster.district}` : ''}
              </p>
            </div>
          </div>
        </div>

        {/* ── Farmers / Mukkadams toggle ────────── */}
        <div className="flex items-center gap-1.5 mb-3 bg-stone-100 rounded-xl p-1">
          <button
            onClick={() => { setActiveTab('farmers'); setSearchTerm(''); }}
            className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all ${
              activeTab === 'farmers'
                ? 'bg-white text-emerald-700 shadow-sm'
                : 'text-stone-400 hover:text-stone-600'
            }`}
          >
            🧑‍🌾 Farmers
          </button>
          <button
            onClick={() => { setActiveTab('mukkadams'); setSearchTerm(''); }}
            className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all ${
              activeTab === 'mukkadams'
                ? 'bg-white text-violet-700 shadow-sm'
                : 'text-stone-400 hover:text-stone-600'
            }`}
          >
            👷 Mukkadams
          </button>
        </div>

        {/* Search */}
        <div className="mb-2">
          <input
            type="text"
            className="w-full pl-3 pr-3 py-2 rounded-lg border border-stone-200 bg-stone-50 text-sm placeholder-stone-300 focus:bg-white focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100 outline-none"
            placeholder={activeTab === 'farmers' ? 'Search farmers...' : 'Search mukkadams...'}
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="pb-1">
          <span className="text-[11px] font-medium text-stone-400 uppercase tracking-[0.12em]">
            {activeTab === 'farmers'
              ? `${farmerSummaries.length} FARMERS`
              : `${filteredMukkadams.length} MUKKADAMS`}
          </span>
        </div>
      </div>

      {/* ── List body ───────────────────────────── */}
      <div className="panel-content flex-1 overflow-y-auto px-3 pb-3 pt-2">

        {/* ══ FARMERS TAB ════════════════════════ */}
        {activeTab === 'farmers' && (
          <>
            {loading ? (
              <div className="empty-state">
                <div className="loading-spinner" />
                <p>Loading...</p>
              </div>
            ) : farmerSummaries.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <p className="empty-state-text">No farmers found</p>
              </div>
            ) : (
              <div className="jobs-list">
                {farmerSummaries.map(s => {
                  const isExpanded = expandedFarmerId === s.farmerId;
                  const plots = farmerPlots[s.farmerId] || [];
                  const initials = (s.farmerName || '')
                    .split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase();

                  return (
                    <div
                      key={s.farmerId}
                      className={`rounded-xl border transition-all duration-200 overflow-hidden ${
                        isExpanded
                          ? 'border-emerald-400 bg-emerald-50/50 shadow-sm shadow-emerald-100'
                          : 'border-stone-200 bg-white hover:border-stone-300 hover:shadow-sm'
                      } mb-2`}
                    >
                      <button
                        onClick={() => handleFarmerClick(s.farmerId, s.farmerName)}
                        className="w-full text-left p-3 bg-transparent"
                      >
                        <div className="flex items-start gap-2.5">
                          <div
                            className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                            style={{
                              backgroundColor: isExpanded ? '#059669' : '#f5f5f4',
                              color: isExpanded ? '#fff' : '#78716c',
                              boxShadow: isExpanded ? '0 1px 4px rgba(5,150,105,0.25)' : 'none',
                              transition: 'all 0.15s',
                            }}
                          >
                            {initials}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-sm text-stone-800 truncate leading-tight">
                              {s.farmerName}
                            </p>
                            <div className="flex flex-wrap items-center gap-1.5 mt-1 text-xs text-stone-400">
                              <span>{s.plotCount} plot{s.plotCount !== 1 ? 's' : ''}</span>
                              <span className="text-stone-300 text-[10px]">·</span>
                              <span>{(farmerAcresMap?.[s.farmerId] ?? s.totalAcres ?? 0).toFixed(2)} ac</span>
                              <span className="text-stone-300 text-[10px]">·</span>
                              <span>{s.totalActivities} tasks</span>
                            </div>
                          </div>
                          <div className="mt-1.5 shrink-0">
                            {isExpanded
                              ? <ChevronUp size={14} className="text-emerald-500" />
                              : <ChevronDown size={14} className="text-stone-300" />}
                          </div>
                        </div>

                        <div className="flex items-center gap-3 mt-2 ml-11 flex-wrap">
                          {s.mobileNumber && (
                            <div className="flex items-center gap-1.5">
                              <Phone size={10} className="text-stone-300" />
                              <span className="text-xs text-stone-400 tabular-nums">{s.mobileNumber}</span>
                            </div>
                          )}
                          {s.nearestDate && (
                            <span className="text-xs text-stone-400 whitespace-nowrap">
                              Next: {new Date(s.nearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                            </span>
                          )}
                          {s.poc && (
                            <span className="text-[11px] text-stone-400">🧑‍💼 {s.poc}</span>
                          )}
                          {s.mobileNumber && (
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation();
                                setDialpadNumber(s.mobileNumber || '');
                                setDialpadOpen(true);
                              }}
                              className="ml-auto inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-600 text-white shadow-sm hover:bg-emerald-700"
                            >
                              <Phone size={10} />
                              Call
                            </button>
                          )}
                        </div>
                      </button>

                      {isExpanded && (
                        <div className="pt-2 px-3 pb-3 border-t border-emerald-200/60">
                          <div className="flex flex-col gap-2">
                            {plots.length === 0 ? (
                              <p className="text-xs text-stone-400 px-1 py-1.5">No plots yet</p>
                            ) : (
                              (() => {
                                const sortedPlots = [...plots].sort((a: any, b: any) => {
                                  const getMeta = (plotObj: any) => {
                                    const pJobs = s.jobs.filter((j: any) => Number(j.plot) === Number(plotObj.id));
                                    let nearest: string | null = null;
                                    let rem = 0;
                                    pJobs.forEach((j: any) =>
                                      (j.activities || []).forEach((act: any) => {
                                        if (act.scheduled_date && act.scheduled_date >= todayStr) {
                                          if (!nearest || act.scheduled_date < nearest) nearest = act.scheduled_date;
                                        }
                                        if (act.allocated_area < act.total_area && act.scheduled_date <= (nearest || todayStr)) {
                                          rem += Number(act.total_area) - Number(act.allocated_area);
                                        }
                                      }),
                                    );
                                    return { nearest, rem };
                                  };
                                  const dA = getMeta(a), dB = getMeta(b);
                                  if (dA.nearest !== dB.nearest) {
                                    if (!dA.nearest) return 1;
                                    if (!dB.nearest) return -1;
                                    return dA.nearest < dB.nearest ? -1 : 1;
                                  }
                                  return dB.rem - dA.rem;
                                });

                                return sortedPlots.map((plot: any) => {
                                  const isPlotExpanded = expandedPlotId === plot.id;
                                  const currentPlotJobs = isPlotExpanded
                                    ? plotJobs[plot.id] || s.jobs.filter((j: any) =>
                                        Number(j.plot) === Number(plot.id) ||
                                        (j.activities || []).some((a: any) => Number(a.plot) === Number(plot.id)),
                                      )
                                    : s.jobs.filter((j: any) => Number(j.plot) === Number(plot.id));

                                  let plotNearestDate: string | null = null;
                                  currentPlotJobs.forEach((j: any) =>
                                    (j.activities || []).forEach((a: any) => {
                                      if (a.scheduled_date >= todayStr) {
                                        if (!plotNearestDate || a.scheduled_date < plotNearestDate)
                                          plotNearestDate = a.scheduled_date;
                                      }
                                    }),
                                  );

                                  const plotRemaining = currentPlotJobs.reduce(
                                    (acc: number, job: any) =>
                                      acc + (job.activities || []).reduce((aAcc: number, act: any) => {
                                        const isUnallocated = Number(act.allocated_area) < Number(act.total_area);
                                        if (isUnallocated && (act.scheduled_date < todayStr || act.scheduled_date === plotNearestDate)) {
                                          return aAcc + (Number(act.total_area) - Number(act.allocated_area));
                                        }
                                        return aAcc;
                                      }, 0),
                                    0,
                                  );

                                  return (
                                    <div key={plot.id} className="bg-white rounded-xl border border-stone-200 overflow-hidden shadow-sm">
                                      <button
                                        onClick={() => handlePlotClick(plot.id, plot.area_acres, s.farmerId)}
                                        className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-stone-50"
                                      >
                                        <div className="flex items-center gap-2 flex-1">
                                          <div className="w-6 h-6 rounded-md bg-red-50 flex items-center justify-center">
                                            <MapPin size={13} className="text-red-400" />
                                          </div>
                                          <div>
                                            <p className="text-[13px] font-semibold text-stone-700 leading-tight">{plot.name}</p>
                                            {plot.crop_name && (
                                              <p className="text-[11px] text-stone-400 mt-[1px]">
                                                {plot.crop_name}{plot.variety ? ` · ${plot.variety}` : ''}
                                              </p>
                                            )}
                                            {plotRemaining > 0 && (
                                              <div className="mt-[2px]">
                                                <span className="text-[11px] text-blue-600 font-semibold">
                                                  {plotRemaining.toFixed(2)} ac remaining
                                                </span>
                                                {plotNearestDate && (
                                                  <span className="text-[10px] text-blue-500 ml-2">
                                                    Next: {new Date(plotNearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                                                  </span>
                                                )}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                                            {plot.area_acres} ac
                                          </span>
                                          {isPlotExpanded
                                            ? <ChevronUp size={12} className="text-stone-400" />
                                            : <ChevronDown size={12} className="text-stone-300" />}
                                        </div>
                                      </button>

                                      {isPlotExpanded && (
                                        <div className="border-t border-stone-100">
                                          {currentPlotJobs.length === 0 ? (
                                            <p className="text-xs text-stone-400 px-3 py-2.5">No jobs</p>
                                          ) : (
                                            currentPlotJobs.map((job: any) => (
                                              <div key={job.job_id}>
                                                <div className="px-3 py-1.5 bg-stone-50">
                                                  <span className="text-[11px] text-stone-600 font-semibold">
                                                    {job.crop_name}{job.variety ? ` · ${job.variety}` : ''}
                                                  </span>
                                                </div>
                                                {[...(job.activities || [])]
                                                  .sort((a: any, b: any) => {
                                                    const isAB = a.scheduled_date < todayStr && a.allocated_area < a.total_area;
                                                    const isBB = b.scheduled_date < todayStr && b.allocated_area < b.total_area;
                                                    const isAN = a.scheduled_date === plotNearestDate;
                                                    const isBN = b.scheduled_date === plotNearestDate;
                                                    if (isAB && !isBB) return -1;
                                                    if (!isAB && isBB) return 1;
                                                    if (isAN && !isBN) return -1;
                                                    if (!isAN && isBN) return 1;
                                                    return (a.scheduled_date || '').localeCompare(b.scheduled_date || '');
                                                  })
                                                  .map((act: any, ti: number) => {
                                                    const isNextJob = act.scheduled_date === plotNearestDate;
                                                    const isBacklog = act.scheduled_date < todayStr && act.allocated_area < act.total_area;
                                                    return (
                                                      <div
                                                        key={act.id}
                                                        className={`flex items-center justify-between px-3 py-2.5 text-xs ${ti > 0 ? 'border-t border-stone-100' : ''}`}
                                                        style={{
                                                          backgroundColor: isNextJob ? '#f0fdf4' : isBacklog ? '#fef2f2' : '#fff',
                                                        }}
                                                      >
                                                        <div>
                                                          <div className="flex items-center gap-1.5 mb-0.5">
                                                            <span className="text-[12px] text-stone-700" style={{ fontWeight: isNextJob ? 700 : 500 }}>
                                                              {act.activity_name}
                                                            </span>
                                                            {isNextJob && (
                                                              <span className="text-[9px] font-semibold px-1.5 py-[1px] rounded bg-emerald-600 text-white tracking-[0.06em]">NEXT</span>
                                                            )}
                                                            {isBacklog && (
                                                              <span className="text-[9px] font-semibold px-1.5 py-[1px] rounded bg-rose-100 text-rose-600 tracking-[0.06em]">BACKLOG</span>
                                                            )}
                                                          </div>
                                                          <span className="text-[11px] text-stone-400">{act.total_area} ac</span>
                                                        </div>
                                                        {act.scheduled_date && (
                                                          <span
                                                            className="text-[11px] px-1.5 py-0.5 rounded bg-stone-50 tabular-nums ml-2"
                                                            style={{
                                                              color: isNextJob ? '#059669' : isBacklog ? '#ef4444' : '#a8a29e',
                                                              fontWeight: isNextJob || isBacklog ? 600 : 400,
                                                            }}
                                                          >
                                                            {new Date(act.scheduled_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                                                          </span>
                                                        )}
                                                      </div>
                                                    );
                                                  })}
                                                {plotNearestDate && (
                                                  <div className="px-3 py-1.5 bg-stone-50 border-t border-stone-100 text-[11px] text-stone-600 font-medium">
                                                    Next job:{' '}
                                                    {new Date(plotNearestDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                                                  </div>
                                                )}
                                              </div>
                                            ))
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                });
                              })()
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ══ MUKKADAMS TAB ══════════════════════ */}
        {activeTab === 'mukkadams' && (
          <>
            {mukkadamsLoading ? (
              <div className="empty-state">
                <div className="loading-spinner" />
                <p>Loading mukkadams...</p>
              </div>
            ) : filteredMukkadams.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">👷</div>
                <p className="empty-state-text">No mukkadams found</p>
              </div>
            ) : (
              <div className="jobs-list">
                {filteredMukkadams.map(m => (
                  <MukkadamCard
                    key={m.mukkadam_id}
                    mukkadam={m}
                    onCall={num => {
                      setDialpadNumber(num);
                      setDialpadOpen(true);
                    }}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <Dialpad
        isOpen={dialpadOpen}
        number={dialpadNumber}
        onClose={() => setDialpadOpen(false)}
        onNumberChange={setDialpadNumber}
      />
    </div>
  );
};

export default JobsPanel;