

// pages/TenderDashboard.tsx
import { useEffect,useRef, useState } from "react";
import axios from "axios";
import {Pencil,Pen,Check,X,
  Users, Briefcase, ChevronDown, ChevronUp,
  MapPin, Phone, Calendar, Layers, IndianRupee,
  TrendingUp, RefreshCw, Filter, Search, CheckCircle,
  Clock, AlertCircle, Building2, User, PlusCircle
} from "lucide-react";

import { AddToClusterModal } from "./Tender";
const API_BASE = "http://localhost:8002/tender";
const API_BASE_URL = "http://localhost:8002/tender";

import toast from "react-hot-toast";
// ─── Types ───────────────────────────────────────────────
// interface Activity { name: string; price: string; }
interface Mukkadam {
  id: number;
  name: string;
  mobile: string;
  crew_size: number;
  max_crew_capacity: number;
  location: { state: string; district: string; taluka: string; village: string };
  availability: { start_date: string | null; end_date: string | null };
  activities: any[];        // old field — keep for safety
  activity_rates: any[];   
  total_price: number;
  reference_image_url: string;
  efficiency: number;
  clusters: { id: number; name: string }[];
}
interface Payment {
  payment_id: number; amount: number; mode: string;
  paid_at: string; paid_status: boolean; notes: string;
}
interface Booking {
  booking_id: number; status: string; total_amount: number;
  advance_paid: number; balance: number; payments: Payment[];
}
interface JobActivity {
  id: number; name: string; total_area: number;
  allocated_area: number; remaining_area: number;
  scheduled_date: string | null; total_price: number; allocation_status: string;
}
interface Job {
  job_id: string; status: string; priority: string;
  scheduled_date: string | null; total_activities_amount: number;
  activities: JobActivity[]; booking: Booking | null;
}
interface Plot {
  plot_id: number; plot_code: string; name: string;
  area_acres: number; crop_name: string; variety: string;
  pruning_date: string | null; jobs_count: number;
  payment_summary: { total_amount: number; advance_paid: number; balance: number; is_fully_paid: boolean };
  jobs: Job[];
}
interface PlotsByCluster { cluster_id: number | null; cluster_name: string; plots: Plot[]; }
interface Farmer {
  farmer_id: string; farmer_name: string; phone_number: string;
  location: string; clusters: { id: number; name: string }[];
  total_plots: number; total_jobs: number;
  payment_summary: { total_amount: number; advance_paid: number; balance: number };
  plots_by_cluster: PlotsByCluster[];
}
interface DashboardData {
  summary: { total_mukkadams: number; total_farmers: number; total_tender_jobs: number };
  mukkadams: Mukkadam[];
  farmers: Farmer[];
}
interface ClusterOption { id: number; name: string; }

// ─── Helpers ────────────────────────────────────────────
const fmt = (n: number) => `₹${n.toLocaleString('en-IN')}`;
const pct = (a: number, b: number) => b > 0 ? Math.round((a / b) * 100) : 0;

/** Count unique plot_ids that appear in ANY named cluster (cluster_id !== null) */
function countPlotsInCluster(plotsByCluster: PlotsByCluster[]): number {
  const seen = new Set<number>();
  plotsByCluster.forEach(group => {
    if (group.cluster_id !== null) {
      group.plots.forEach(p => seen.add(p.plot_id));
    }
  });
  return seen.size;
}

function ClusterCoverageBar({ farmer }: { farmer: Farmer }) {
  const inCluster = countPlotsInCluster(farmer.plots_by_cluster);
  const total = farmer.total_plots;
  const p = pct(inCluster, total);

  return (
    <div className="mt-3 flex items-center gap-3">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${
            p >= 100 ? 'bg-green-500' : p > 0 ? 'bg-teal-500' : 'bg-gray-300'
          }`}
          style={{ width: `${Math.min(p, 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 whitespace-nowrap">
        {inCluster}/{total} in cluster
      </span>
    </div>
  );
}

function AllocationBar({ allocated, total }: { allocated: number; total: number }) {
  const p = pct(allocated, total);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${p >= 100 ? 'bg-green-500' : p > 0 ? 'bg-yellow-500' : 'bg-gray-300'}`}
          style={{ width: `${Math.min(p, 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 w-8">{p}%</span>
    </div>
  );
}

// ─── Reusable Portal Dropdown ────────────────────────────
function PortalDropdown({ anchorRef, onClose, children }: {
  anchorRef: React.RefObject<HTMLElement>;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const [pos, setPos] = useState({ top: 0, right: 0 });
  const dropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (anchorRef.current) {
      const rect = anchorRef.current.getBoundingClientRect();
      setPos({
        top: rect.bottom + window.scrollY + 6,
        right: window.innerWidth - rect.right,
      });
    }
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropRef.current && !dropRef.current.contains(e.target as Node) &&
        anchorRef.current && !anchorRef.current.contains(e.target as Node)
      ) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    const handler = () => onClose();
    window.addEventListener('scroll', handler, true);
    return () => window.removeEventListener('scroll', handler, true);
  }, []);

  return ReactDOM.createPortal(
    <div
      ref={dropRef}
      style={{
        position: 'absolute',
        top: pos.top,
        right: pos.right,
        zIndex: 99999,
        background: '#fff',
        borderRadius: '12px',
        border: '1px solid #e5e7eb',
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
        width: '200px',
        overflow: 'hidden',
      }}
    >
      {children}
    </div>,
    document.body
  );
}

// ─── Dropdown Header ─────────────────────────────────────
function DropdownHeader({ label }: { label: string }) {
  return (
    <div style={{
      padding: '9px 12px 7px',
      borderBottom: '1px solid #f3f4f6',
      background: '#f9fafb',
    }}>
      <p style={{
        margin: 0, fontSize: '0.67rem', fontWeight: 700,
        color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em',
      }}>
        {label}
      </p>
    </div>
  );
}

// ─── Cluster List Item ───────────────────────────────────
function ClusterItem({ name, alreadyIn, saving, onClick }: {
  name: string;
  alreadyIn: boolean;
  saving: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      disabled={alreadyIn || saving}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%', textAlign: 'left',
        padding: '8px 12px',
        background: hovered && !alreadyIn ? '#f0fdfa' : 'transparent',
        border: 'none',
        borderBottom: '1px solid #f9fafb',
        cursor: alreadyIn ? 'default' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontSize: '0.82rem',
        color: alreadyIn ? '#c4c4c4' : '#1f2937',
        transition: 'background 0.1s',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{
          width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
          background: alreadyIn ? '#e5e7eb' : '#14b8a6',
          transition: 'background 0.1s',
        }} />
        {name}
      </span>
      {alreadyIn && (
        <span style={{ fontSize: '0.7rem', color: '#22c55e', fontWeight: 700 }}>✓</span>
      )}
      {saving && !alreadyIn && (
        <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>…</span>
      )}
    </button>
  );
}

const WEEKDAY_OPTIONS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

function getAdvanceAmount(crewSize: number): number {
  if (crewSize <= 25) return 20000;
  if (crewSize <= 40) return 30000;
  return 30000;
}

function getWeeklyAmount(crewSize: number): number {
  if (crewSize <= 25) return 10000;
  if (crewSize <= 40) return 15000;
  return 15000;
}


interface Activity { 
  rate_id?: number;
  activity_id?: number;
  activity_name?: string;
  name?: string;           // fallback
  price?: string;          // old field
  rate_per_acre?: number;  // actual field from API
  productivity_per_worker?: number;
  productivity?: number;   // fallback
}

function ActivityRowWithEfficiency({ activity, mukkadamEfficiency }: {
  activity: any;
  mukkadamEfficiency: number;
}) {
  const rateId: number | undefined = activity.rate_id;
  
  // Handle both old {name, price} and new {activity_name, rate_per_acre} shapes
  const displayName = activity.activity_name ?? activity.name ?? '—';
  const displayPrice = activity.rate_per_acre ?? parseFloat(activity.price || '0');
  const initialValue: number = 
    activity.productivity_per_worker ?? 
    activity.productivity ?? 
    mukkadamEfficiency;

  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<number>(initialValue);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const handleSave = async () => {
    if (!rateId) { toast.error('No rate ID'); return; }
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/mukkadam-rates/${rateId}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productivity_per_worker: value }),
      });
      if (response.ok) {
        toast.success('Efficiency saved');
        setEditing(false);
      } else {
        toast.error('Failed to update efficiency');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave();
    if (e.key === 'Escape') { setEditing(false); setValue(initialValue); }
  };

  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50 group">
      <td className="px-3 py-2 text-gray-800">{displayName}</td>
      <td className="px-3 py-2 text-right font-medium text-teal-600">
        {fmt(displayPrice)}
      </td>
      <td className="px-3 py-2 text-right">
        {editing ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
            <input
              ref={inputRef}
              type="number"
              step="0.01"
              min="0"
              value={value}
              onChange={e => setValue(parseFloat(e.target.value) || 0)}
              onKeyDown={handleKeyDown}
              style={{
                width: '64px', padding: '2px 6px',
                border: '1.5px solid #14b8a6', borderRadius: '5px',
                fontSize: '0.78rem', textAlign: 'right', outline: 'none',
              }}
            />
            <button
              type="button"
              onClick={e => { e.preventDefault(); e.stopPropagation(); handleSave(); }}
              disabled={saving}
              style={{
                width: '20px', height: '20px', borderRadius: '4px',
                background: saving ? '#99f6e4' : '#14b8a6',
                border: 'none', cursor: saving ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {saving
                ? <span style={{ fontSize: '8px', color: '#fff' }}>...</span>
                : <Check size={11} color="#fff" />
              }
            </button>
            <button
              type="button"
              onClick={e => { e.preventDefault(); e.stopPropagation(); setEditing(false); setValue(initialValue); }}
              style={{
                width: '20px', height: '20px', borderRadius: '4px',
                background: '#f3f4f6', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <X size={11} color="#6b7280" />
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '6px' }}>
            <span className="text-gray-500 text-xs">{value.toFixed(2)} ac/w</span>
            <button
              type="button"
              onClick={e => { e.preventDefault(); e.stopPropagation(); setEditing(true); }}
              className="opacity-0 group-hover:opacity-100 transition-opacity"
              style={{
                width: '18px', height: '18px', borderRadius: '4px',
                background: 'none', border: '1px solid #e5e7eb',
                cursor: 'pointer', display: 'flex',
                alignItems: 'center', justifyContent: 'center', padding: 0,
              }}
            >
              <Pencil size={10} color="#9ca3af" />
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}
// ─── Mukkadam Card ───────────────────────────────────────
function MukkadamCard({ m, clusters, onSuccess }: {
  m: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-9 h-9 bg-teal-100 rounded-full flex items-center justify-center">
                <User size={18} className="text-teal-600" />
              </div>
              <div>
                <p className="font-bold text-gray-900">{m.name}</p>
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  <Phone size={11} /> {m.mobile}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-2 items-center">
              <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                Crew: {m.crew_size}/{m.max_crew_capacity}
              </span>
              <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs font-medium">
                {m.activities.length} Activities
              </span>
              {m.clusters.length === 0 ? (
                <span className="px-2 py-0.5 bg-red-50 text-red-500 rounded text-xs">No Cluster</span>
              ) : m.clusters.map(c => (
                <span key={c.id} className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded text-xs">
                  {c.name}
                </span>
              ))}

              {/* Add to Cluster — stop card expand */}
              <div onClick={e => e.stopPropagation()}>
                <MukkadamAddToCluster
                  mukkadam={m}
                  clusters={clusters}
                  onSuccess={onSuccess}
                />
              </div>
            </div>
          </div>

          <div className="text-right ml-4">
            {/* <p className="text-xs text-gray-500">Total Price</p>
            <p className="text-xl font-bold text-teal-600">{fmt(m.total_price)}</p> */}
            {expanded
              ? <ChevronUp size={16} className="ml-auto text-gray-400 mt-1" />
              : <ChevronDown size={16} className="ml-auto text-gray-400 mt-1" />
            }
          </div>
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">

            {/* Activities table with inline efficiency edit */}
            <div>
              <p className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1">
                <Briefcase size={14} /> Activities & Rates
              </p>
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2 text-gray-600 font-semibold text-xs">Activity</th>
                      <th className="text-right px-3 py-2 text-gray-600 font-semibold text-xs">Price/ac</th>
                      <th className="text-right px-3 py-2 text-gray-600 font-semibold text-xs">Efficiency</th>
                    </tr>
                  </thead>
                  <tbody>
                   {(m.activity_rates || m.activities || []).map((a: any, i: number) => (
  <ActivityRowWithEfficiency
    key={a.rate_id ?? i}
    activity={a}
    mukkadamEfficiency={m.efficiency}
  />
))}

                    <tr className="border-t-2 border-gray-200 bg-teal-50">
                      {/* <td className="px-3 py-2 font-bold text-gray-800">Total</td>
                      <td className="px-3 py-2 text-right font-bold text-teal-700">{fmt(m.total_price)}</td> */}
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Location + reference image */}
            <div className="space-y-3">
              <div>
                <p className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-1">
                  <MapPin size={14} /> Location & Availability
                 
          {/* <MukkadamSettlementsTab mukkadamId={m.id} /> */}
        
                </p>
                <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 space-y-1">
                  <p><span className="font-medium">Village:</span> {m.location.village}, {m.location.taluka}</p>
                  <p><span className="font-medium">District:</span> {m.location.district}, {m.location.state}</p>
                  {m.availability.start_date && (
                    <p className="flex items-center gap-1 mt-1">
                      <Calendar size={11} />
                      {m.availability.start_date} → {m.availability.end_date || '?'}
                    </p>
                  )}
                </div>
              </div>
              {m.reference_image_url && (
                <div>
                  <p className="text-xs font-semibold text-gray-600 mb-1">Rate Card Reference</p>
                  <img
                    src={m.reference_image_url}
                    alt="Rate card"
                    className="rounded-lg border border-gray-200 w-full max-h-40 object-cover cursor-pointer"
                    onClick={() => window.open(m.reference_image_url, '_blank')}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

  function getNearestPruningDate(farmer: Farmer): Date | null {
  const dates: Date[] = [];
  farmer.plots_by_cluster.forEach(group => {
    group.plots.forEach(plot => {
      if (plot.pruning_date) {
        dates.push(new Date(plot.pruning_date));
      }
    });
  });
  if (dates.length === 0) return null;
  return dates.reduce((min, d) => d < min ? d : min);
}

function formatPruningBadge(date: Date | null): React.ReactNode {
  if (!date) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.ceil((date.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  const label = date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

  const color = diffDays < 0
    ? { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' }  // overdue
    : diffDays <= 7
    ? { bg: '#fff7ed', text: '#ea580c', border: '#fed7aa' }  // urgent
    : diffDays <= 15
    ? { bg: '#fefce8', text: '#ca8a04', border: '#fde68a' }  // soon
    : { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' }; // ok

  const prefix = diffDays < 0 ? '⚠ ' : '🌿 ';

  return (
    <span style={{
      padding: '2px 8px', borderRadius: '999px',
      background: color.bg, color: color.text,
      fontSize: '0.68rem', fontWeight: 600,
      border: `1px solid ${color.border}`,
      whiteSpace: 'nowrap',
    }}>
      {prefix}Pruning: {label}
    </span>
  );
}
// ─── Add to Cluster Mini Modal ────────────────────────────
// Lightweight wrapper: picks cluster then opens AddToClusterModal
interface AddToClusterTriggerProps {
  farmer: Farmer;
  clusters: ClusterOption[];
  onOpen: (clusterId: number, clusterName: string, farmerId: string) => void;
}

// ─── Farmer Level: Add ALL plots to a cluster ────────────
function AddToClusterTrigger({ farmer, clusters, onSuccess }: {
  farmer: Farmer;
  clusters: ClusterOption[];
  onSuccess: () => void;
}) {
  const [showPicker, setShowPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setShowPicker(false);
        setSearch('');
      }
    };
    if (showPicker) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPicker]);

  const filtered = clusters.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleAddToCluster = async (cluster: ClusterOption) => {
    if (saving) return;
    setSaving(true);
    try {
      // Get ALL plot IDs for this farmer
      const allPlotIds = farmer.plots_by_cluster.flatMap(g => g.plots.map(p => p.plot_id));

      const res = await fetch(`${API_BASE_URL}/api/cluster/${cluster.id}/add_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farmer_id: farmer.farmer_id,
          plot_ids: allPlotIds,
        }),
      });

      if (res.ok) {
        toast.success(`All plots added to ${cluster.name}`);
        setShowPicker(false);
        setSearch('');
        onSuccess();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err?.detail || 'Failed to add to cluster');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  // Which cluster IDs already have ALL plots of this farmer?
  const fullyInCluster = (clusterId: number) => {
    const group = farmer.plots_by_cluster.find(g => g.cluster_id === clusterId);
    const allPlotIds = new Set(farmer.plots_by_cluster.flatMap(g => g.plots.map(p => p.plot_id)));
    const inClusterIds = new Set(group?.plots.map(p => p.plot_id) || []);
    return allPlotIds.size > 0 && [...allPlotIds].every(id => inClusterIds.has(id));
  };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={e => { e.stopPropagation(); setShowPicker(v => !v); }}
        style={{
          display: 'flex', alignItems: 'center', gap: '5px',
          padding: '4px 10px', borderRadius: '999px',
          border: '1.5px solid #14b8a6', background: '#f0fdfa',
          color: '#0f766e', fontSize: '0.75rem', fontWeight: 600,
          cursor: 'pointer', whiteSpace: 'nowrap',
        }}
      >
        <PlusCircle size={13} />
        Add to Cluster
      </button>

      {showPicker && (
        <div
          onClick={e => e.stopPropagation()}
          style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0,
            zIndex: 9999, background: '#fff', borderRadius: '12px',
            border: '1px solid #e5e7eb', boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
            width: '220px', overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{ padding: '10px 12px 6px', borderBottom: '1px solid #f3f4f6' }}>
            <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Add all plots to cluster
            </p>
          </div>

          {/* Search */}
          <div style={{ padding: '8px 10px', borderBottom: '1px solid #f3f4f6' }}>
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search clusters..."
              style={{
                width: '100%', padding: '5px 8px', border: '1px solid #d1d5db',
                borderRadius: '6px', fontSize: '0.8rem', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Cluster list */}
          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <p style={{ padding: '12px', textAlign: 'center', fontSize: '0.8rem', color: '#9ca3af' }}>
                No clusters found
              </p>
            ) : filtered.map(c => {
              const allIn = fullyInCluster(c.id);
              return (
                <button
                  key={c.id}
                  disabled={allIn || saving}
                  onClick={() => handleAddToCluster(c)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '9px 12px',
                    background: 'none', border: 'none',
                    cursor: allIn ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    fontSize: '0.85rem',
                    color: allIn ? '#9ca3af' : '#111827',
                    borderBottom: '1px solid #f9fafb',
                  }}
                  onMouseEnter={e => { if (!allIn) (e.currentTarget as HTMLElement).style.background = '#f0fdfa'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'none'; }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                    <Building2 size={13} style={{ color: allIn ? '#d1d5db' : '#14b8a6', flexShrink: 0 }} />
                    {c.name}
                  </span>
                  {allIn
                    ? <span style={{ fontSize: '0.7rem', color: '#22c55e', fontWeight: 600 }}>✓ All in</span>
                    : saving
                      ? <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>...</span>
                      : null
                  }
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
// ─── Plot Cluster Tag + Add Button ───────────────────────
interface PlotClusterControlProps {
  plot: Plot;
  clusterGroups: PlotsByCluster[];
  clusters: ClusterOption[];
  farmerId: string;
  onOpen: (clusterId: number, clusterName: string, farmerId: string) => void;
}
function MukkadamSettlementsTab({ 
  mukkadamId, 
  filterJobId 
}: { 
  mukkadamId: number;
  filterJobId?: string;  // if provided, show only this job's settlement
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlements/`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [mukkadamId]);

  const handlePay = async (jobId: string, amount: number) => {
    if (!confirm(`Pay ₹${amount.toLocaleString('en-IN')} for job #${jobId}?`)) return;
    setPaying(jobId);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/pay/`,
        { method: 'POST' }
      );
      const result = await res.json();
      if (res.ok) {
        toast.success(result.message);
        setData((prev: any) => ({
          ...prev,
          settlements: prev.settlements.map((s: any) =>
            s.job_id === jobId
              ? { ...s, status: 'paid', paid_at: new Date().toISOString() }
              : s
          ),
        }));
      } else {
        toast.error(result.error);
      }
    } finally {
      setPaying(null);
    }
  };

  if (loading) return (
    <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af', fontSize: '0.82rem' }}>
      <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 8px', display: 'block', color: '#14b8a6' }} />
      Loading settlements...
    </div>
  );

  if (!data || data.settlements.length === 0) return (
    <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af', fontSize: '0.82rem' }}>
      No settlements yet. Calculated after shoot selection date passes.
    </div>
  );

  const { summary, settlements } = data;

  const STATUS_META: Record<string, { bg: string; text: string; label: string }> = {
    paid:               { bg: '#dcfce7', text: '#16a34a', label: '✓ Paid' },
    calculated:         { bg: '#fef9c3', text: '#b45309', label: '⚠ Payment Due' },
    no_payment_needed:  { bg: '#dbeafe', text: '#1d4ed8', label: '✅ In Credit' },
    payment_raised:     { bg: '#fce7f3', text: '#be185d', label: 'Raised' },
    pending:            { bg: '#f3f4f6', text: '#6b7280', label: 'Pending' },
  };

  return (
    <div style={{ marginTop: '16px' }}>

      {/* ── Summary Bar ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '10px', marginBottom: '20px',
      }}>
        {[
          { label: 'Total Jobs', value: summary.total_jobs, isCount: true, color: '#374151', bg: '#f9fafb' },
          { label: 'Total Earned', value: summary.total_gross, color: '#0f766e', bg: '#f0fdfa' },
          { label: 'Total Paid', value: summary.total_paid, color: '#16a34a', bg: '#f0fdf4' },
          { label: 'Pending', value: summary.total_pending, color: '#b45309', bg: '#fffbeb' },
        ].map(s => (
          <div key={s.label} style={{
            background: s.bg, borderRadius: '10px',
            padding: '10px 12px', textAlign: 'center',
          }}>
            <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280', marginBottom: '4px' }}>{s.label}</p>
            <p style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: s.color }}>
              {s.isCount ? s.value : `₹${Number(s.value).toLocaleString('en-IN')}`}
            </p>
          </div>
        ))}
      </div>

      {/* ── Settlement Cards ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {settlements.map((s: any) => {
          const sm = STATUS_META[s.status] || STATUS_META.pending;
          const needsPayment = s.status === 'calculated' && s.net_payable > 0;
          const isCredit = s.net_payable <= 0 && s.status !== 'pending';

          return (
            <div key={s.job_id} style={{
              border: `1.5px solid ${needsPayment ? '#fde68a' : isCredit ? '#bbf7d0' : '#e5e7eb'}`,
              borderRadius: '14px', overflow: 'hidden', background: '#fff',
              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
            }}>

              {/* ── Card Header ── */}
              <div style={{
                padding: '12px 16px',
                background: needsPayment ? '#fffbeb' : isCredit ? '#f0fdf4' : '#fafafa',
                borderBottom: '1px solid #f3f4f6',
                display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: '0.85rem', fontWeight: 800, color: '#111827',
                    fontFamily: 'monospace', letterSpacing: '0.03em',
                  }}>
                    #{s.job_id}
                  </span>
                  <div>
                    <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1f2937' }}>
                      {s.farmer_name}
                    </span>
                    <span style={{ fontSize: '0.72rem', color: '#9ca3af', marginLeft: '6px' }}>
                      {s.farmer_id}
                    </span>
                  </div>
                  {s.cluster_name !== '—' && (
                    <span style={{
                      fontSize: '0.7rem', padding: '2px 9px', borderRadius: '999px',
                      background: '#f0fdfa', color: '#0f766e',
                      border: '1px solid #99f6e4', fontWeight: 600,
                    }}>
                      {s.cluster_name}
                    </span>
                  )}
                  <span style={{
                    fontSize: '0.7rem', padding: '2px 9px', borderRadius: '999px',
                    background: sm.bg, color: sm.text, fontWeight: 700,
                  }}>
                    {sm.label}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {s.calculated_at && (
                    <span style={{ fontSize: '0.68rem', color: '#9ca3af' }}>
                      Calc: {new Date(s.calculated_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })}
                    </span>
                  )}
                  {s.paid_at && (
                    <span style={{ fontSize: '0.68rem', color: '#16a34a', fontWeight: 600 }}>
                      Paid: {new Date(s.paid_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ padding: '14px 16px' }}>

                {/* ── Activity Breakdown Table ── */}
                <p style={{
                  margin: '0 0 8px', fontSize: '0.72rem',
                  fontWeight: 700, color: '#6b7280',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                }}>
                  📋 Activity Breakdown
                </p>

                <div style={{
                  border: '1px solid #e5e7eb', borderRadius: '8px',
                  overflow: 'hidden', marginBottom: '14px',
                }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                    <thead>
                      <tr style={{ background: '#f9fafb' }}>
                        {['Activity', 'Plot', 'Date', 'Acres', 'Rate/ac', 'Amount', 'Status'].map(h => (
                          <th key={h} style={{
                            padding: '7px 10px', textAlign: h === 'Activity' || h === 'Plot' || h === 'Status' ? 'left' : 'right',
                            color: '#6b7280', fontWeight: 600, fontSize: '0.7rem',
                            borderBottom: '1px solid #e5e7eb',
                          }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {s.activity_breakdown.length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ padding: '12px', textAlign: 'center', color: '#9ca3af', fontSize: '0.75rem' }}>
                            No allocations found
                          </td>
                        </tr>
                      ) : s.activity_breakdown.map((a: any, i: number) => (
                        <tr key={i} style={{
                          borderTop: i > 0 ? '1px solid #f3f4f6' : 'none',
                          background: i % 2 === 0 ? '#fff' : '#fafafa',
                        }}>
                          <td style={{ padding: '8px 10px', color: '#111827', fontWeight: 600 }}>
                            {a.activity_name}
                          </td>
                          <td style={{ padding: '8px 10px', color: '#374151' }}>
                            <span style={{ fontFamily: 'monospace', fontSize: '0.72rem' }}>
                              {a.plot_code}
                            </span>
                            {a.plot_name !== a.plot_code && (
                              <span style={{ color: '#9ca3af', fontSize: '0.7rem', marginLeft: '4px' }}>
                                ({a.plot_name})
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#6b7280', whiteSpace: 'nowrap' }}>
                            {a.scheduled_date}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#374151', fontWeight: 600 }}>
                            {a.allocated_area} ac
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#6b7280' }}>
                            ₹{Number(a.mukkadam_rate).toLocaleString('en-IN')}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>
                            ₹{Number(a.gross_amount).toLocaleString('en-IN')}
                          </td>
                          <td style={{ padding: '8px 10px' }}>
                            <span style={{
                              fontSize: '0.65rem', padding: '2px 6px', borderRadius: '999px',
                              background: a.allocation_status === 'completed' ? '#dcfce7' : '#fef9c3',
                              color: a.allocation_status === 'completed' ? '#16a34a' : '#b45309',
                              fontWeight: 600,
                            }}>
                              {a.allocation_status}
                            </span>
                          </td>
                        </tr>
                      ))}

                      {/* Totals row */}
                      {s.activity_breakdown.length > 0 && (
                        <tr style={{ borderTop: '2px solid #e5e7eb', background: '#f0fdfa' }}>
                          <td colSpan={3} style={{ padding: '8px 10px', fontWeight: 700, color: '#374151', fontSize: '0.75rem' }}>
                            Total ({s.activity_breakdown.length} activities)
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700, color: '#374151' }}>
                            {s.activity_breakdown.reduce((t: number, a: any) => t + a.allocated_area, 0).toFixed(2)} ac
                          </td>
                          <td />
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 800, color: '#0f766e' }}>
                            ₹{s.gross_amount.toLocaleString('en-IN')}
                          </td>
                          <td />
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* ── Financial Calculation ── */}
                <p style={{
                  margin: '0 0 8px', fontSize: '0.72rem',
                  fontWeight: 700, color: '#6b7280',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                }}>
                  💰 Settlement Calculation
                </p>

                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr',
                  gap: '10px', marginBottom: '12px',
                }}>
                  {/* Left: calculation steps */}
                  <div style={{
                    background: '#f9fafb', borderRadius: '10px',
                    padding: '12px 14px',
                    display: 'flex', flexDirection: 'column', gap: '7px',
                  }}>
                    {[
                      { label: 'Gross Earned', value: s.gross_amount, sign: '', color: '#0f766e', bold: false },
                      { label: '− 10% Deposit Held', value: s.deposit_held_10pct, sign: '−', color: '#b45309', bold: false },
                      { label: '= 90% Payable', value: s.payable_90pct, sign: '', color: '#1f2937', bold: true, divider: true },
                      ...(s.deposit_carried_forward > 0 ? [{
                        label: '+ Deposit from Prev Job', value: s.deposit_carried_forward,
                        sign: '+', color: '#7c3aed', bold: false,
                      }] : []),
                      ...(s.advance_deducted > 0 ? [{
                        label: '− Advance (one-time)', value: s.advance_deducted,
                        sign: '−', color: '#dc2626', bold: false,
                      }] : []),
                      ...(s.weekly_payments_deducted > 0 ? [{
                        label: `− Weekly Payments`, value: s.weekly_payments_deducted,
                        sign: '−', color: '#dc2626', bold: false,
                      }] : []),
                    ].map((row: any, i: number) => (
                      <div key={i}>
                        {row.divider && <div style={{ borderTop: '1px dashed #e5e7eb', margin: '2px 0' }} />}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{
                            fontSize: row.bold ? '0.78rem' : '0.74rem',
                            fontWeight: row.bold ? 700 : 400,
                            color: '#6b7280',
                          }}>
                            {row.label}
                          </span>
                          <span style={{
                            fontSize: row.bold ? '0.82rem' : '0.78rem',
                            fontWeight: row.bold ? 800 : 600,
                            color: row.color,
                          }}>
                            {row.sign}₹{Number(row.value).toLocaleString('en-IN')}
                          </span>
                        </div>
                      </div>
                    ))}

                    {/* Final net */}
                    <div style={{ borderTop: '2px solid #e5e7eb', paddingTop: '7px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#111827' }}>
                          Net Payable
                        </span>
                        <span style={{
                          fontSize: '0.95rem', fontWeight: 800,
                          color: s.net_payable > 0 ? '#dc2626' : '#16a34a',
                        }}>
                          {s.net_payable > 0
                            ? `₹${s.net_payable.toLocaleString('en-IN')}`
                            : `−₹${Math.abs(s.net_payable).toLocaleString('en-IN')}`
                          }
                        </span>
                      </div>
                      {s.net_payable <= 0 && (
                        <p style={{ margin: '3px 0 0', fontSize: '0.68rem', color: '#16a34a', textAlign: 'right' }}>
                          Mukkadam is in credit — no payment needed
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Right: weekly payment breakdown */}
                  <div style={{
                    background: '#f9fafb', borderRadius: '10px',
                    padding: '12px 14px',
                  }}>
                    <p style={{ margin: '0 0 8px', fontSize: '0.72rem', fontWeight: 700, color: '#6b7280' }}>
                      📅 Weekly Payments Applied
                    </p>
                    {s.weekly_breakdown.length === 0 ? (
                      <p style={{ fontSize: '0.75rem', color: '#9ca3af', margin: 0 }}>
                        No weekly payments deducted
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                        {s.weekly_breakdown.map((w: any, i: number) => (
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between',
                            alignItems: 'center', fontSize: '0.75rem',
                            padding: '4px 0',
                            borderBottom: i < s.weekly_breakdown.length - 1 ? '1px solid #e5e7eb' : 'none',
                          }}>
                            <div>
                              <span style={{ color: '#374151', fontWeight: 600 }}>{w.payment_date}</span>
                              <span style={{ color: '#9ca3af', marginLeft: '6px', fontSize: '0.68rem' }}>
                                {w.crew_size} workers
                              </span>
                            </div>
                            <span style={{ color: '#dc2626', fontWeight: 700 }}>
                              −₹{Number(w.amount).toLocaleString('en-IN')}
                            </span>
                          </div>
                        ))}
                        <div style={{
                          borderTop: '1.5px solid #e5e7eb', paddingTop: '5px', marginTop: '2px',
                          display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem',
                        }}>
                          <span style={{ fontWeight: 700, color: '#374151' }}>Total Deducted</span>
                          <span style={{ fontWeight: 800, color: '#dc2626' }}>
                            −₹{s.weekly_payments_deducted.toLocaleString('en-IN')}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Pay Button ── */}
                {needsPayment && (
                  <button
                    onClick={() => handlePay(s.job_id, s.net_payable)}
                    disabled={paying === s.job_id}
                    style={{
                      width: '100%', padding: '11px',
                      background: paying === s.job_id ? '#99f6e4' : '#14b8a6',
                      border: 'none', borderRadius: '9px',
                      color: '#fff', fontWeight: 700, fontSize: '0.88rem',
                      cursor: paying === s.job_id ? 'not-allowed' : 'pointer',
                      letterSpacing: '0.02em',
                    }}
                  >
                    {paying === s.job_id
                      ? 'Processing...'
                      : `🏦 Raise Payment · ₹${s.net_payable.toLocaleString('en-IN')}`
                    }
                  </button>
                )}

              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";

function PlotClusterControl({ plot, clusterGroups, clusters, farmerId, onSuccess }: {
  plot: Plot;
  clusterGroups: PlotsByCluster[];
  clusters: ClusterOption[];
  farmerId: string;
  onSuccess: () => void;
}) {
  const [showPicker, setShowPicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Calculate position from button's bounding rect
  const openPicker = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + window.scrollY + 6,
        right: window.innerWidth - rect.right,
      });
    }
    setShowPicker(v => !v);
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setShowPicker(false);
      }
    };
    if (showPicker) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPicker]);

  // Close on scroll
  useEffect(() => {
    const handler = () => setShowPicker(false);
    if (showPicker) window.addEventListener('scroll', handler, true);
    return () => window.removeEventListener('scroll', handler, true);
  }, [showPicker]);

  const plotClusterIds = new Set(
    clusterGroups
      .filter(g => g.cluster_id !== null && g.plots.some(p => p.plot_id === plot.plot_id))
      .map(g => g.cluster_id!)
  );
  const plotClusters = clusterGroups
    .filter(g => g.cluster_id !== null && g.plots.some(p => p.plot_id === plot.plot_id))
    .map(g => ({ id: g.cluster_id!, name: g.cluster_name }));

  const handleAddPlot = async (cluster: ClusterOption) => {
    if (saving) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${cluster.id}/add_farmer/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ farmer_id: farmerId, plot_ids: [plot.plot_id] }),
      });
      if (res.ok) {
        toast.success(`Plot ${plot.plot_code} → ${cluster.name}`);
        setShowPicker(false);
        onSuccess();
      } else {
        toast.error('Failed to add plot');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
      {/* Cluster tags */}
      {plotClusters.length === 0 ? (
        <span style={{
          padding: '2px 8px', borderRadius: '999px',
          background: '#fef2f2', color: '#f87171',
          fontSize: '0.68rem', fontWeight: 500,
          border: '1px solid #fecaca', whiteSpace: 'nowrap',
        }}>No cluster</span>
      ) : plotClusters.map(c => (
        <span key={c.id} style={{
          padding: '2px 8px', borderRadius: '999px',
          background: '#f0fdfa', color: '#0f766e',
          fontSize: '0.68rem', fontWeight: 600,
          border: '1px solid #99f6e4', whiteSpace: 'nowrap',
        }}>{c.name}</span>
      ))}

      {/* + button */}
      <button
        ref={btnRef}
        onClick={openPicker}
        style={{
          width: '22px', height: '22px', borderRadius: '50%',
          border: '1.5px solid #d1d5db',
          background: showPicker ? '#f0fdfa' : '#fff',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 0, flexShrink: 0,
          color: showPicker ? '#14b8a6' : '#9ca3af',
        }}
        title="Add to cluster"
      >
        <PlusCircle size={13} />
      </button>

      {/* Portal dropdown — renders at body level, escapes all overflow:hidden parents */}
      {showPicker && ReactDOM.createPortal(
        <div
          ref={dropdownRef}
          style={{
            position: 'absolute',
            top: dropdownPos.top,
            right: dropdownPos.right,
            zIndex: 99999,
            background: '#fff',
            borderRadius: '10px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 8px 24px rgba(0,0,0,0.13)',
            width: '180px',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '8px 12px',
            borderBottom: '1px solid #f3f4f6',
            background: '#f9fafb',
          }}>
            <p style={{
              margin: 0, fontSize: '0.68rem', fontWeight: 700,
              color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              Add plot to cluster
            </p>
          </div>

          {/* Cluster list */}
          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {clusters.length === 0 && (
              <p style={{ padding: '10px 12px', fontSize: '0.8rem', color: '#9ca3af', margin: 0 }}>
                No clusters
              </p>
            )}
            {clusters.map(c => {
              const alreadyIn = plotClusterIds.has(c.id);
              return (
                <button
                  key={c.id}
                  disabled={alreadyIn || saving}
                  onClick={() => handleAddPlot(c)}
                  style={{
                    width: '100%', textAlign: 'left',
                    padding: '8px 12px',
                    background: 'none', border: 'none',
                    borderBottom: '1px solid #f9fafb',
                    cursor: alreadyIn ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.82rem',
                    color: alreadyIn ? '#9ca3af' : '#1f2937',
                  }}
                  onMouseEnter={e => {
                    if (!alreadyIn) (e.currentTarget as HTMLElement).style.background = '#f0fdfa';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = 'none';
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                    <span style={{
                      width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
                      background: alreadyIn ? '#d1d5db' : '#14b8a6',
                    }} />
                    {c.name}
                  </span>
                  {alreadyIn && <span style={{ fontSize: '0.7rem', color: '#22c55e', fontWeight: 700 }}>✓</span>}
                  {saving && !alreadyIn && <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>...</span>}
                </button>
              );
            })}
          </div>
        </div>,
        document.body   // ← renders outside ALL parent containers
      )}
    </div>
  );
}
// ─── Farmer Card ─────────────────────────────────────────
interface FarmerCardProps {
  farmer: Farmer;
  clusters: ClusterOption[];
  onSuccess: () => void;
}
// Remove the entire formatPruningBadge function and replace with:
function formatPruningDate(date: Date | null): React.ReactNode {
  if (!date) return null;
  const label = date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  return (
    <span className="text-xs text-gray-500 whitespace-nowrap">
      🌿 {label}
    </span>
  );
}
function FarmerCard({ farmer, clusters, onSuccess }: FarmerCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedPlot, setExpandedPlot] = useState<number | null>(null);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
const [farmerTab, setFarmerTab] = useState<'details' | 'billing'>('details');

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Farmer Header */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition"
        onClick={() => setExpanded(!expanded)}
      >

        {/* <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', marginBottom: '12px' }}>
  {[
    { key: 'details', label: '📋 Details' },
    { key: 'billing', label: '💰 Billing' },
  ].map(t => (
    <button
      key={t.key}
      onClick={() => setFarmerTab(t.key as any)}
      style={{
        padding: '8px 16px', fontSize: '0.78rem', fontWeight: 600,
        border: 'none', background: 'none', cursor: 'pointer',
        borderBottom: farmerTab === t.key ? '2px solid #3b82f6' : '2px solid transparent',
        color: farmerTab === t.key ? '#3b82f6' : '#6b7280',
      }}
    >
      {t.label}
    </button>
  ))}
</div> */}

{farmerTab === 'billing' && (
  <FarmerBillingTab farmerId={farmer.farmer_id} />
)}

{farmerTab === 'details' && (
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-9 h-9 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
                <User size={18} className="text-blue-600" />
              </div>
              <div className="min-w-0">
                <p className="font-bold text-gray-900">{farmer.farmer_name}</p>
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  <Phone size={11} /> {farmer.phone_number}
                  <span className="mx-1">•</span>
                  <MapPin size={11} /> {farmer.location}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mt-2 items-center">
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                {farmer.total_plots} Plots
              </span>
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                {farmer.total_jobs} Jobs
              </span>
              {farmer.clusters.length === 0 ? (
                <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded text-xs">No Cluster</span>
              ) : farmer.clusters.map(c => (
                <span key={c.id} className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded text-xs">
                  {c.name}
                </span>

                
              ))}

{/* ← ADD THIS */}
{(() => {
  const nearest = getNearestPruningDate(farmer);
  return formatPruningDate(nearest);
})()}
              {/* ── Add to Cluster trigger (stops card expand click) ── */}
              <div onClick={e => e.stopPropagation()}>
                <AddToClusterTrigger
                farmer={farmer}
                clusters={clusters}
                onSuccess={onSuccess}
                />
            </div>
            </div>

            {/* ── Cluster Coverage Bar (replaces payment bar) ── */}
            <ClusterCoverageBar farmer={farmer} />
          </div>

          <div className="ml-3 shrink-0 mt-1">
            {expanded
              ? <ChevronUp size={16} className="text-gray-400" />
              : <ChevronDown size={16} className="text-gray-400" />
            }
          </div>
        </div>
)}
      </div>

      {/* Expanded: plots by cluster */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 pb-4">
          {farmer.plots_by_cluster.map((clusterGroup, gi) => (
            <div key={gi} className="mt-4">
              <div className="flex items-center gap-2 mb-2">
                <Building2 size={14} className="text-teal-600" />
                <p className="text-sm font-bold text-teal-700">{clusterGroup.cluster_name}</p>
                <span className="text-xs text-gray-400">({clusterGroup.plots.length} plots)</span>
              </div>

              <div className="space-y-2 pl-4 border-l-2 border-teal-100">
                {clusterGroup.plots.map(plot => (
                  <div key={plot.plot_id} className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* Plot Header */}
                    <div
                      className="px-3 py-2.5 bg-gray-50 cursor-pointer hover:bg-gray-100 flex justify-between items-center"
                      onClick={() => setExpandedPlot(expandedPlot === plot.plot_id ? null : plot.plot_id)}
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-gray-800">
                            Plot {plot.plot_code}
                            {plot.name !== `Plot ${plot.plot_code}` && (
                              <span className="ml-1 text-gray-500 font-normal">({plot.name})</span>
                            )}
                          </p>
                          <p className="text-xs text-gray-500">
                            {plot.area_acres} ac • {plot.crop_name}
                            {plot.variety && ` • ${plot.variety}`}
                            {plot.pruning_date && ` • Pruning: ${plot.pruning_date}`}
                            {' '}· {plot.jobs?.reduce((t, j) => t + (j.activities?.length || 0), 0)} activities
                          </p>
                        </div>
                      </div>

                      {/* Plot cluster control — stop expand propagation */}
                      <div onClick={e => e.stopPropagation()} className="ml-3 shrink-0">
                            <PlotClusterControl
                            plot={plot}
                            clusterGroups={farmer.plots_by_cluster}
                            clusters={clusters}
                            farmerId={farmer.farmer_id}
                            onSuccess={onSuccess}
                            />
                        </div>
                    </div>

                    {/* Plot expanded: jobs */}
                    {expandedPlot === plot.plot_id && (
                      <div className="px-3 pb-3 pt-2 space-y-2">
                        {plot.jobs.length === 0 ? (
                          <p className="text-xs text-gray-400 italic">No tender jobs for this plot</p>
                        ) : plot.jobs.map(job => (
                          <div key={job.job_id} className="border border-blue-100 rounded-lg overflow-hidden">
                            <div
                              className="px-3 py-2 bg-blue-50 cursor-pointer hover:bg-blue-100 flex justify-between items-center"
                              onClick={() => setExpandedJob(expandedJob === job.job_id ? null : job.job_id)}
                            >
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-blue-700 font-bold">#{job.job_id}</span>
                                <span className="text-xs text-gray-500">{job.activities.length} activities</span>
                              </div>
                              <div className="flex items-center gap-3">
                                {expandedJob === job.job_id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                              </div>
                            </div>

                            {expandedJob === job.job_id && (
                              <div className="px-3 pb-3 pt-2 space-y-3">
                                <div>
                                  <p className="text-xs font-bold text-gray-600 mb-1 flex items-center gap-1">
                                    <Layers size={12} /> Activities
                                  </p>
                                  <div className="space-y-1">
                                    {job.activities.map(a => (
                                      <div key={a.id} className="flex items-center gap-2 text-xs">
                                        <span className="w-24 text-gray-700 font-medium truncate">{a.name}</span>
                                        <span className="text-gray-400">{a.total_area}ac</span>
                                        {/* <AllocationBar allocated={a.allocated_area} total={a.total_area} /> */}
                                        <span className={`px-1.5 py-0.5 rounded text-xs ${
                                          a.allocation_status === 'fully_allocated' ? 'bg-green-100 text-green-700' :
                                          a.allocation_status === 'partially_allocated' ? 'bg-yellow-100 text-yellow-700' :
                                          'bg-gray-100 text-gray-500'
                                        }`}>{a.allocation_status.replace('_', ' ')}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ─── Settlement Detail Card ───────────────────────────────
function MukkadamSettlementCard({ mukkadamId, jobId }: {
  mukkadamId: number;
  jobId: string;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [mukkadamId, jobId]);

  const handlePay = async () => {
    if (!confirm(`Pay ₹${data.breakdown.net_payable}?`)) return;
    setPaying(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/pay/`,
        { method: 'POST' }
      );
      const result = await res.json();
      if (res.ok) {
        toast.success(result.message);
        setData((prev: any) => ({
          ...prev,
          settlement_status: 'paid',
          show_raise_payment: false,
        }));
      } else {
        toast.error(result.error);
      }
    } finally {
      setPaying(false);
    }
  };

  if (loading) return <div style={{ fontSize: '0.78rem', color: '#9ca3af', padding: '8px' }}>Calculating...</div>;
  if (!data?.triggered) return null;

  const b = data.breakdown;
  const isPaid = data.settlement_status === 'paid';
  const isCredit = b.net_payable <= 0;

  return (
    <div style={{
      border: `1.5px solid ${isPaid ? '#bbf7d0' : isCredit ? '#e0f2fe' : '#fde68a'}`,
      borderRadius: '10px', padding: '14px', marginTop: '12px',
      background: isPaid ? '#f0fdf4' : isCredit ? '#f0f9ff' : '#fffbeb',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#374151' }}>
          Settlement · Job #{jobId}
        </span>
        <span style={{
          fontSize: '0.7rem', fontWeight: 600, padding: '2px 8px', borderRadius: '999px',
          background: isPaid ? '#dcfce7' : isCredit ? '#dbeafe' : '#fef9c3',
          color: isPaid ? '#16a34a' : isCredit ? '#1d4ed8' : '#b45309',
        }}>
          {isPaid ? '✓ Paid' : isCredit ? 'In Credit' : 'Payment Due'}
        </span>
      </div>

      {/* Activity Breakdown */}
      <table style={{ width: '100%', fontSize: '0.75rem', borderCollapse: 'collapse', marginBottom: '10px' }}>
        <thead>
          <tr style={{ background: '#f9fafb' }}>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280' }}>Activity</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280' }}>Plot</th>
            <th style={{ textAlign: 'left', padding: '4px 8px', color: '#6b7280' }}>Date</th>
            <th style={{ textAlign: 'right', padding: '4px 8px', color: '#6b7280' }}>Acres</th>
            <th style={{ textAlign: 'right', padding: '4px 8px', color: '#6b7280' }}>Rate</th>
            <th style={{ textAlign: 'right', padding: '4px 8px', color: '#6b7280' }}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {b.activities.map((a: any, i: number) => (
            <tr key={i} style={{ borderTop: '1px solid #f3f4f6' }}>
              <td style={{ padding: '4px 8px', color: '#1f2937' }}>{a.activity_name}</td>
              <td style={{ padding: '4px 8px', color: '#6b7280' }}>{a.plot_code}</td>
              <td style={{ padding: '4px 8px', color: '#6b7280' }}>{a.scheduled_date}</td>
              <td style={{ padding: '4px 8px', textAlign: 'right' }}>{a.allocated_area}</td>
              <td style={{ padding: '4px 8px', textAlign: 'right' }}>₹{a.mukkadam_rate}</td>
              <td style={{ padding: '4px 8px', textAlign: 'right', fontWeight: 600, color: '#0f766e' }}>
                ₹{a.gross_amount.toLocaleString('en-IN')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Calculation Summary */}
      <div style={{
        background: '#fff', borderRadius: '8px', padding: '10px 12px',
        fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '5px',
      }}>
        {[
          { label: 'Gross Earned', value: b.gross_amount, color: '#1f2937' },
          { label: '10% Deposit Held', value: -b.deposit_held_10pct, color: '#ef4444' },
          { label: '90% Payable', value: b.payable_90pct, color: '#0f766e', bold: true },
          ...(b.deposit_from_prev_job > 0 ? [{ label: '+ Deposit from Prev Job', value: b.deposit_from_prev_job, color: '#7c3aed' }] : []),
          ...(b.advance_deducted > 0 ? [{ label: '− Advance Deducted', value: -b.advance_deducted, color: '#ef4444' }] : []),
          ...(b.weekly_payments_total > 0 ? [{ label: `− Weekly Payments (${b.weekly_payments.length} weeks)`, value: -b.weekly_payments_total, color: '#ef4444' }] : []),
        ].map((row, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#6b7280' }}>{row.label}</span>
            <span style={{ fontWeight: row.bold ? 700 : 500, color: row.color }}>
              ₹{Math.abs(row.value).toLocaleString('en-IN')}
            </span>
          </div>
        ))}

        <div style={{
          borderTop: '1.5px solid #e5e7eb', marginTop: '4px', paddingTop: '6px',
          display: 'flex', justifyContent: 'space-between', fontWeight: 700,
        }}>
          <span style={{ color: '#111827' }}>Net Payable</span>
          <span style={{ color: b.net_payable > 0 ? '#dc2626' : '#16a34a', fontSize: '0.88rem' }}>
            {b.net_payable > 0 ? '' : '− '}₹{Math.abs(b.net_payable).toLocaleString('en-IN')}
            {b.net_payable <= 0 && <span style={{ fontSize: '0.68rem', color: '#16a34a', marginLeft: '4px' }}>(Credit)</span>}
          </span>
        </div>
      </div>

      {/* Pay Button */}
      {data.show_raise_payment && (
        <button
          onClick={handlePay}
          disabled={paying}
          style={{
            width: '100%', marginTop: '12px', padding: '10px',
            background: paying ? '#99f6e4' : '#14b8a6',
            border: 'none', borderRadius: '8px',
            color: '#fff', fontWeight: 700, fontSize: '0.85rem',
            cursor: paying ? 'not-allowed' : 'pointer',
          }}
        >
          {paying ? 'Processing...' : `Pay ₹${b.net_payable.toLocaleString('en-IN')}`}
        </button>
      )}
    </div>
  );
}


function PaymentsTab({ clusters }: { clusters: ClusterOption[] }) {
  const [settlements, setSettlements] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [clusterFilter, setClusterFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [paying, setPaying] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<Record<string, any>>({});
  const [detailLoading, setDetailLoading] = useState<string | null>(null);

  const fetchSettlements = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (clusterFilter) params.cluster_id = clusterFilter;
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;

      const res = await fetch(
        `${API_BASE_URL}/api/settlements/?${new URLSearchParams(params)}`
      );
      const data = await res.json();
      setSettlements(data.results || data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSettlements(); }, [clusterFilter, statusFilter, search]);

  // Fetch full detail for a row when expanded
  const toggleExpand = async (mukkadamId: number, jobId: string) => {
    const key = `${mukkadamId}-${jobId}`;
    if (expandedKey === key) {
      setExpandedKey(null);
      return;
    }
    setExpandedKey(key);

    // Already fetched
    if (detailData[key]) return;

    setDetailLoading(key);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/`
      );
      const data = await res.json();
      setDetailData(prev => ({ ...prev, [key]: data }));
    } catch (e) {
      console.error(e);
    } finally {
      setDetailLoading(null);
    }
  };

  const handlePay = async (mukkadamId: number, jobId: string, amount: number, mukkadamName: string) => {
    if (!confirm(`Pay ₹${amount.toLocaleString('en-IN')} to ${mukkadamName} for job #${jobId}?`)) return;
    const key = `${mukkadamId}-${jobId}`;
    setPaying(key);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mukkadam/${mukkadamId}/settlement/${jobId}/pay/`,
        { method: 'POST' }
      );
      const result = await res.json();
      if (res.ok) {
        toast.success(result.message);
        setSettlements(prev => prev.map(s =>
          s.mukkadam_id === mukkadamId && s.job_id === jobId
            ? { ...s, status: 'paid', paid_at: new Date().toISOString() }
            : s
        ));
        // Update detail cache too
        setDetailData(prev => prev[key]
          ? { ...prev, [key]: { ...prev[key], settlement_status: 'paid', show_raise_payment: false } }
          : prev
        );
      } else {
        toast.error(result.error || 'Payment failed');
      }
    } finally {
      setPaying(null);
    }
  };

  const summary = {
    total: settlements.length,
    due: settlements.filter(s => s.status === 'calculated' && s.net_payable > 0),
    paid: settlements.filter(s => s.status === 'paid'),
    credit: settlements.filter(s => s.net_payable <= 0 && s.status !== 'pending'),
    totalDueAmount: settlements
      .filter(s => s.status === 'calculated' && s.net_payable > 0)
      .reduce((t, s) => t + s.net_payable, 0),
    totalPaidAmount: settlements
      .filter(s => s.status === 'paid')
      .reduce((t, s) => t + s.net_payable, 0),
  };

  const STATUS_META: Record<string, { bg: string; text: string; label: string }> = {
    paid:              { bg: '#dcfce7', text: '#16a34a', label: '✓ Paid' },
    calculated:        { bg: '#fef9c3', text: '#b45309', label: '⚠ Due' },
    no_payment_needed: { bg: '#dbeafe', text: '#1d4ed8', label: '✅ Credit' },
    payment_raised:    { bg: '#fce7f3', text: '#be185d', label: 'Raised' },
    pending:           { bg: '#f3f4f6', text: '#6b7280', label: 'Pending' },
  };

  return (
    <div>
      {/* ── Summary Cards ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '12px', marginBottom: '20px',
      }}>
        {[
          { label: 'Total Settlements', value: summary.total, color: '#374151', bg: '#f9fafb', border: '#e5e7eb' },
          { label: 'Payment Due', value: summary.due.length, sub: `₹${summary.totalDueAmount.toLocaleString('en-IN')} pending`, color: '#b45309', bg: '#fffbeb', border: '#fde68a' },
          { label: 'Paid', value: summary.paid.length, sub: `₹${summary.totalPaidAmount.toLocaleString('en-IN')} paid`, color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
          { label: 'In Credit', value: summary.credit.length, sub: 'No payment needed', color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe' },
        ].map(s => (
          <div key={s.label} style={{
            background: s.bg, borderRadius: '12px',
            border: `1.5px solid ${s.border}`, padding: '14px 16px',
          }}>
            <p style={{ margin: 0, fontSize: '0.7rem', color: '#6b7280', marginBottom: '6px' }}>{s.label}</p>
            <p style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</p>
            {(s as any).sub && (
              <p style={{ margin: '4px 0 0', fontSize: '0.68rem', color: '#9ca3af' }}>{(s as any).sub}</p>
            )}
          </div>
        ))}
      </div>

      {/* ── Filters ── */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: '180px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search mukkadam or farmer..."
            style={{
              width: '100%', paddingLeft: '32px', paddingRight: '12px',
              paddingTop: '8px', paddingBottom: '8px',
              border: '1px solid #e5e7eb', borderRadius: '8px',
              fontSize: '0.82rem', outline: 'none', boxSizing: 'border-box',
            }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', outline: 'none', background: '#fff' }}
        >
          <option value="">All Status</option>
          <option value="calculated">⚠ Payment Due</option>
          <option value="paid">✓ Paid</option>
          <option value="no_payment_needed">✅ In Credit</option>
          <option value="pending">Pending</option>
        </select>
        <select
          value={clusterFilter}
          onChange={e => setClusterFilter(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '0.82rem', outline: 'none', background: '#fff' }}
        >
          <option value="">All Clusters</option>
          {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button
          onClick={fetchSettlements}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '8px 14px', borderRadius: '8px', border: 'none',
            background: '#14b8a6', color: '#fff', fontSize: '0.82rem',
            fontWeight: 600, cursor: 'pointer',
          }}
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* ── Table ── */}
      {loading ? (
        <div style={{ padding: '48px', textAlign: 'center', color: '#9ca3af' }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px', display: 'block', color: '#14b8a6' }} />
          Loading payments...
        </div>
      ) : settlements.length === 0 ? (
        <div style={{ padding: '48px', textAlign: 'center', color: '#9ca3af', fontSize: '0.85rem' }}>
          No settlements found
        </div>
      ) : (
        <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '1.5px solid #e5e7eb' }}>
                {['', 'Mukkadam', 'Job', 'Farmer', 'Cluster', 'Gross', 'Advance', 'Weekly', '10% Held', 'Net Payable', 'Status', 'Action'].map(h => (
                  <th key={h} style={{
                    padding: '10px 12px',
                    textAlign: ['Gross', 'Advance', 'Weekly', '10% Held', 'Net Payable'].includes(h) ? 'right' : 'left',
                    color: '#6b7280', fontWeight: 600,
                    fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {settlements.map((s: any, i: number) => {
                const sm = STATUS_META[s.status] || STATUS_META.pending;
                const needsPayment = s.status === 'calculated' && s.net_payable > 0;
                const payKey = `${s.mukkadam_id}-${s.job_id}`;
                const isExpanded = expandedKey === payKey;
                const detail = detailData[payKey];
                const isLoadingDetail = detailLoading === payKey;

                return (
                  <>
                    {/* ── Main Row ── */}
                    <tr
                      key={payKey}
                      onClick={() => toggleExpand(s.mukkadam_id, s.job_id)}
                      style={{
                        borderBottom: isExpanded ? 'none' : '1px solid #f3f4f6',
                        background: isExpanded ? '#f0fdfa' : i % 2 === 0 ? '#fff' : '#fafafa',
                        cursor: 'pointer',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = '#f0fdfa'; }}
                      onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#fafafa'; }}
                    >
                      {/* Expand chevron */}
                      <td style={{ padding: '10px 8px 10px 12px', width: '24px' }}>
                        <span style={{ color: '#9ca3af', fontSize: '0.7rem' }}>
                          {isExpanded ? '▲' : '▼'}
                        </span>
                      </td>

                      <td style={{ padding: '10px 12px' }}>
                        <p style={{ margin: 0, fontWeight: 700, color: '#111827' }}>{s.mukkadam_name}</p>
                        <p style={{ margin: 0, fontSize: '0.68rem', color: '#9ca3af' }}>Crew: {s.crew_size ?? '—'}</p>
                      </td>

                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1d4ed8', fontSize: '0.78rem' }}>
                          #{s.job_id}
                        </span>
                      </td>

                      <td style={{ padding: '10px 12px', color: '#374151' }}>
                        <p style={{ margin: 0, fontWeight: 600 }}>{s.farmer_name}</p>
                        <p style={{ margin: 0, fontSize: '0.68rem', color: '#9ca3af' }}>{s.farmer_id}</p>
                      </td>

                      <td style={{ padding: '10px 12px' }}>
                        {s.cluster_name !== '—' ? (
                          <span style={{
                            fontSize: '0.72rem', padding: '2px 8px', borderRadius: '999px',
                            background: '#f0fdfa', color: '#0f766e',
                            border: '1px solid #99f6e4', fontWeight: 600,
                          }}>
                            {s.cluster_name}
                          </span>
                        ) : <span style={{ color: '#d1d5db', fontSize: '0.72rem' }}>—</span>}
                      </td>

                      <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#0f766e' }}>
                        ₹{s.gross_amount.toLocaleString('en-IN')}
                      </td>

                      <td style={{ padding: '10px 12px', textAlign: 'right', color: s.advance_deducted > 0 ? '#dc2626' : '#9ca3af' }}>
                        {s.advance_deducted > 0 ? `−₹${s.advance_deducted.toLocaleString('en-IN')}` : '—'}
                      </td>

                      <td style={{ padding: '10px 12px', textAlign: 'right', color: s.weekly_payments_deducted > 0 ? '#dc2626' : '#9ca3af' }}>
                        {s.weekly_payments_deducted > 0 ? `−₹${s.weekly_payments_deducted.toLocaleString('en-IN')}` : '—'}
                      </td>

                      <td style={{ padding: '10px 12px', textAlign: 'right', color: '#b45309' }}>
                        −₹{(s.gross_amount * 0.1).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </td>

                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                        <span style={{ fontWeight: 800, fontSize: '0.88rem', color: s.net_payable > 0 ? '#dc2626' : '#16a34a' }}>
                          {s.net_payable > 0
                            ? `₹${s.net_payable.toLocaleString('en-IN')}`
                            : `−₹${Math.abs(s.net_payable).toLocaleString('en-IN')}`
                          }
                        </span>
                      </td>

                      <td style={{ padding: '10px 12px' }}>
                        <span style={{
                          fontSize: '0.68rem', padding: '3px 8px', borderRadius: '999px',
                          fontWeight: 700, background: sm.bg, color: sm.text, whiteSpace: 'nowrap',
                        }}>
                          {sm.label}
                        </span>
                        {s.paid_at && (
                          <p style={{ margin: '2px 0 0', fontSize: '0.62rem', color: '#9ca3af' }}>
                            {new Date(s.paid_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                          </p>
                        )}
                      </td>

                      <td style={{ padding: '10px 12px' }} onClick={e => e.stopPropagation()}>
                        {needsPayment ? (
                          <button
                            onClick={() => handlePay(s.mukkadam_id, s.job_id, s.net_payable, s.mukkadam_name)}
                            disabled={paying === payKey}
                            style={{
                              padding: '6px 14px', borderRadius: '7px', border: 'none',
                              background: paying === payKey ? '#99f6e4' : '#14b8a6',
                              color: '#fff', fontSize: '0.75rem', fontWeight: 700,
                              cursor: paying === payKey ? 'not-allowed' : 'pointer',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {paying === payKey ? '...' : `Pay ₹${s.net_payable.toLocaleString('en-IN')}`}
                          </button>
                        ) : s.status === 'paid' ? (
                          <span style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 600 }}>✓ Done</span>
                        ) : (
                          <span style={{ fontSize: '0.72rem', color: '#d1d5db' }}>—</span>
                        )}
                      </td>
                    </tr>

                    {/* ── Expanded Detail Row ── */}
                    {isExpanded && (
  <tr key={`${payKey}-detail`}>
    <td colSpan={12} style={{
      padding: '0 16px 16px',
      background: '#f0fdfa',
      borderBottom: '2px solid #99f6e4',
    }}>
      <MukkadamSettlementsTab 
        mukkadamId={s.mukkadam_id} 
        filterJobId={s.job_id}
      />
    </td>
  </tr>
)}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ─── Farmer Billing Tab ───────────────────────────────────
const PAYMENT_MODES = ['CASH', 'UPI', 'BANK_TRANSFER', 'CHEQUE', 'OTHER'];

function FarmerBillingTab({ farmerId }: { farmerId: string }) {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  // Payment modal state
  const [payModal, setPayModal] = useState<{
    jobId: string;
    suggestedAmount: number;
    label: string;
  } | null>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMode, setPayMode] = useState('CASH');
  const [payNotes, setPayNotes] = useState('');
  const [payLoading, setPayLoading] = useState(false);

  const fetchBilling = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/farmer/${farmerId}/billing/`);
      const data = await res.json();
      setJobs(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBilling(); }, [farmerId]);

  const openPayModal = (jobId: string, amount: number, label: string) => {
    setPayModal({ jobId, suggestedAmount: amount, label });
    setPayAmount(String(amount));
    setPayMode('CASH');
    setPayNotes('');
  };

  const handleRecordPayment = async () => {
    if (!payModal || !payAmount || parseFloat(payAmount) <= 0) return;
    setPayLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/farmer/${farmerId}/job/${payModal.jobId}/payment/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount: parseFloat(payAmount),
            mode: payMode,
            notes: payNotes,
          }),
        }
      );
      const result = await res.json();
      if (res.ok) {
        alert(`✅ ${result.message}`);
        setPayModal(null);
        fetchBilling(); // refresh
      } else {
        alert(`❌ ${result.error}`);
      }
    } finally {
      setPayLoading(false);
    }
  };

  if (loading) return (
    <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>
      <RefreshCw size={20} className="animate-spin" style={{ display: 'inline', color: '#3b82f6' }} />
      <span style={{ marginLeft: '8px', fontSize: '0.82rem' }}>Loading billing...</span>
    </div>
  );

  if (jobs.length === 0) return (
    <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af', fontSize: '0.82rem' }}>
      No jobs found for this farmer
    </div>
  );

  // Summary across all jobs
  const totalBilled = jobs.reduce((t, j) => t + j.summary.total_billable_so_far, 0);
  const totalPaid = jobs.reduce((t, j) => t + j.summary.total_paid, 0);
  const totalDue = jobs.reduce((t, j) => t + Math.max(0, j.summary.balance_due), 0);

  return (
    <div style={{ padding: '12px 0' }}>
      {/* ── Summary Bar ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '10px', marginBottom: '16px',
      }}>
        {[
          { label: 'Total Billed', value: totalBilled, color: '#0f766e', bg: '#f0fdfa', border: '#99f6e4' },
          { label: 'Total Collected', value: totalPaid, color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
          { label: 'Balance Due', value: totalDue, color: totalDue > 0 ? '#dc2626' : '#6b7280', bg: totalDue > 0 ? '#fef2f2' : '#f9fafb', border: totalDue > 0 ? '#fecaca' : '#e5e7eb' },
        ].map(s => (
          <div key={s.label} style={{
            background: s.bg, borderRadius: '10px',
            border: `1.5px solid ${s.border}`, padding: '10px 14px', textAlign: 'center',
          }}>
            <p style={{ margin: 0, fontSize: '0.65rem', color: '#6b7280', marginBottom: '4px' }}>{s.label}</p>
            <p style={{ margin: 0, fontWeight: 800, fontSize: '1.1rem', color: s.color }}>
              ₹{s.value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </p>
          </div>
        ))}
      </div>

      {/* ── Job Cards ── */}
      {jobs.map(job => {
        const isOpen = expandedJob === job.job_id;
        const s = job.summary;
        const hasBalance = s.balance_due > 0.01;
        const borderColor = hasBalance ? '#fde68a' : s.all_activities_past ? '#bbf7d0' : '#e5e7eb';
        const bgColor = hasBalance ? '#fffbeb' : '#fff';

        return (
          <div key={job.job_id} style={{
            border: `1.5px solid ${borderColor}`,
            borderRadius: '12px', marginBottom: '10px',
            background: bgColor, overflow: 'hidden',
          }}>
            {/* ── Job Header ── */}
            <div
              onClick={() => setExpandedJob(isOpen ? null : job.job_id)}
              style={{
                padding: '12px 16px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1d4ed8', fontSize: '0.85rem' }}>
                  #{job.job_id}
                </span>
                <span style={{
                  fontSize: '0.68rem', padding: '2px 8px', borderRadius: '999px',
                  background: hasBalance ? '#fef9c3' : s.all_activities_past ? '#dcfce7' : '#f3f4f6',
                  color: hasBalance ? '#b45309' : s.all_activities_past ? '#16a34a' : '#6b7280',
                  fontWeight: 600,
                }}>
                  {hasBalance ? '⚠ Balance Due' : s.all_activities_past ? '✓ Complete' : '🕐 In Progress'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                {/* Mini financials */}
                <div style={{ textAlign: 'right', fontSize: '0.72rem' }}>
                  <span style={{ color: '#6b7280' }}>Billed: </span>
                  <span style={{ fontWeight: 700, color: '#0f766e' }}>
                    ₹{s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                  <span style={{ color: '#6b7280', marginLeft: '8px' }}>Paid: </span>
                  <span style={{ fontWeight: 700, color: '#16a34a' }}>
                    ₹{s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                  {hasBalance && (
                    <>
                      <span style={{ color: '#6b7280', marginLeft: '8px' }}>Due: </span>
                      <span style={{ fontWeight: 800, color: '#dc2626' }}>
                        ₹{s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </span>
                    </>
                  )}
                </div>

                {/* Collect button — outside expand, stop propagation */}
                {hasBalance && (
                  <button
                    onClick={e => { e.stopPropagation(); openPayModal(job.job_id, Math.round(s.balance_due), 'Collect Payment'); }}
                    style={{
                      padding: '6px 14px', borderRadius: '7px', border: 'none',
                      background: '#3b82f6', color: '#fff',
                      fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    + Collect ₹{Math.round(s.balance_due).toLocaleString('en-IN')}
                  </button>
                )}

                <span style={{ color: '#9ca3af', fontSize: '0.7rem' }}>{isOpen ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* ── Expanded Detail ── */}
            {isOpen && (
              <div style={{ borderTop: '1px solid #e5e7eb', padding: '14px 16px', background: '#fafafa' }}>

                {/* Activity breakdown table */}
                <p style={{ margin: '0 0 8px', fontSize: '0.7rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  📋 Activity Breakdown
                </p>
                <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden', marginBottom: '14px', background: '#fff' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem' }}>
                    <thead>
                      <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                        {['Activity', 'Plot', 'Date', 'Total ac', 'Done ac', 'Rate/ac', 'Billable', 'Status'].map(h => (
                          <th key={h} style={{
                            padding: '7px 10px', textAlign: ['Total ac', 'Done ac', 'Rate/ac', 'Billable'].includes(h) ? 'right' : 'left',
                            color: '#6b7280', fontWeight: 600, fontSize: '0.68rem',
                          }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {job.activities.map((act: any, idx: number) => (
                        <tr key={act.activity_id} style={{
                          borderTop: idx > 0 ? '1px solid #f3f4f6' : 'none',
                          background: act.is_past
                            ? (act.billable_amount > 0 ? '#f0fdfa' : '#f9fafb')
                            : '#fff',
                          opacity: act.is_past ? 1 : 0.6,
                        }}>
                          <td style={{ padding: '8px 10px', fontWeight: 600, color: '#111827' }}>
                            {act.activity_name}
                          </td>
                          <td style={{ padding: '8px 10px', color: '#6b7280', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                            {act.plot_code !== '—' ? act.plot_code : act.plot_name}
                          </td>
                          <td style={{ padding: '8px 10px', color: act.is_past ? '#374151' : '#9ca3af', whiteSpace: 'nowrap' }}>
                            {act.scheduled_date || '—'}
                            {!act.is_past && (
                              <span style={{ marginLeft: '4px', fontSize: '0.6rem', color: '#9ca3af' }}>upcoming</span>
                            )}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#6b7280' }}>
                            {act.total_area.toFixed(2)}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>
                            {act.is_past ? act.allocated_area.toFixed(2) : '—'}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', color: '#6b7280' }}>
                            ₹{act.rate_per_acre.toLocaleString('en-IN')}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700, color: act.billable_amount > 0 ? '#0f766e' : '#9ca3af' }}>
                            {act.billable_amount > 0 ? `₹${act.billable_amount.toLocaleString('en-IN')}` : '—'}
                          </td>
                          <td style={{ padding: '8px 10px' }}>
                            <span style={{
                              fontSize: '0.62rem', padding: '2px 6px', borderRadius: '999px', fontWeight: 600,
                              background: act.is_past ? '#dcfce7' : '#f3f4f6',
                              color: act.is_past ? '#16a34a' : '#9ca3af',
                            }}>
                              {act.is_past ? 'billed' : 'upcoming'}
                            </span>
                          </td>
                        </tr>
                      ))}

                      {/* Total row */}
                      <tr style={{ borderTop: '2px solid #e5e7eb', background: '#f0fdfa' }}>
                        <td colSpan={4} style={{ padding: '8px 10px', fontWeight: 700, fontSize: '0.75rem', color: '#374151' }}>
                          Total Billed So Far ({job.activities.filter((a: any) => a.is_past).length} / {job.activities.length} activities)
                        </td>
                        <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 700 }}>
                          {job.activities.filter((a: any) => a.is_past).reduce((t: number, a: any) => t + a.allocated_area, 0).toFixed(2)}
                        </td>
                        <td />
                        <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 800, color: '#0f766e' }}>
                          ₹{s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </td>
                        <td />
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* ── Payment Calculation + History side by side ── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>

                  {/* Calculation panel */}
                  <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px' }}>
                    <p style={{ margin: '0 0 10px', fontSize: '0.7rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      💰 Payment Calculation
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '7px', fontSize: '0.78rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#6b7280' }}>Booking Total</span>
                        <span style={{ fontWeight: 700, color: '#374151' }}>₹{job.booking_total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                      </div>
                      <div style={{ borderTop: '1px dashed #e5e7eb', paddingTop: '7px', display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#6b7280' }}>Total Billed So Far</span>
                        <span style={{ fontWeight: 700, color: '#0f766e' }}>₹{s.total_billable_so_far.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#6b7280' }}>− Advance Paid</span>
                        <span style={{ fontWeight: 600, color: '#16a34a' }}>−₹{s.advance_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                      </div>
                      {s.additional_paid > 0 && (
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#6b7280' }}>− Additional Collected</span>
                          <span style={{ fontWeight: 600, color: '#16a34a' }}>−₹{s.additional_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                        </div>
                      )}
                      <div style={{ borderTop: '2px solid #e5e7eb', paddingTop: '7px', display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 700, color: '#111827' }}>Balance Due</span>
                        <span style={{ fontWeight: 800, fontSize: '1rem', color: hasBalance ? '#dc2626' : '#16a34a' }}>
                          {hasBalance
                            ? `₹${s.balance_due.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                            : '✓ Clear'}
                        </span>
                      </div>
                      {/* Final gap notice */}
                      {s.all_activities_past && s.final_gap > 0 && (
                        <div style={{
                          marginTop: '6px', padding: '8px 10px', borderRadius: '7px',
                          background: '#fef2f2', border: '1px solid #fecaca', fontSize: '0.72rem',
                        }}>
                          <span style={{ color: '#dc2626', fontWeight: 700 }}>
                            ⚠ All activities done — ₹{s.final_gap.toLocaleString('en-IN', { maximumFractionDigits: 0 })} still pending vs booking total
                          </span>
                        </div>
                      )}
                      {s.all_activities_past && !hasBalance && s.final_gap <= 0 && (
                        <div style={{
                          marginTop: '6px', padding: '8px 10px', borderRadius: '7px',
                          background: '#f0fdf4', border: '1px solid #bbf7d0', fontSize: '0.72rem',
                        }}>
                          <span style={{ color: '#16a34a', fontWeight: 700 }}>
                            ✅ All activities complete — fully collected
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Payment history panel */}
                  <div style={{ background: '#fff', borderRadius: '10px', border: '1px solid #e5e7eb', padding: '12px 14px' }}>
                    <p style={{ margin: '0 0 10px', fontSize: '0.7rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      📅 Payment History
                    </p>
                    {job.payment_history.length === 0 ? (
                      <p style={{ fontSize: '0.75rem', color: '#9ca3af', margin: 0 }}>No payments recorded</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                        {job.payment_history.map((p: any, pi: number) => (
                          <div key={pi} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            fontSize: '0.75rem', padding: '5px 0',
                            borderBottom: pi < job.payment_history.length - 1 ? '1px solid #f3f4f6' : 'none',
                          }}>
                            <div>
                              <span style={{
                                fontSize: '0.65rem', padding: '1px 6px', borderRadius: '999px', marginRight: '6px',
                                background: p.type === 'advance' ? '#eff6ff' : '#f0fdf4',
                                color: p.type === 'advance' ? '#1d4ed8' : '#16a34a',
                                fontWeight: 600,
                              }}>
                                {p.mode}
                              </span>
                              <span style={{ color: '#9ca3af', fontSize: '0.68rem' }}>{p.date}</span>
                              {p.notes && <span style={{ color: '#9ca3af', marginLeft: '4px', fontSize: '0.65rem' }}> · {p.notes}</span>}
                            </div>
                            <span style={{ fontWeight: 700, color: '#16a34a' }}>
                              ₹{Number(p.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </span>
                          </div>
                        ))}
                        <div style={{ borderTop: '1.5px solid #e5e7eb', paddingTop: '5px', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                          <span style={{ fontWeight: 700 }}>Total Collected</span>
                          <span style={{ fontWeight: 800, color: '#16a34a' }}>
                            ₹{s.total_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Collect Payment Button (inside expanded too) ── */}
                {(hasBalance || s.show_final_collection) && (
                  <button
                    onClick={() => openPayModal(
                      job.job_id,
                      Math.round(hasBalance ? s.balance_due : s.final_gap),
                      hasBalance ? 'Collect Payment' : 'Final Settlement'
                    )}
                    style={{
                      width: '100%', padding: '11px', borderRadius: '9px', border: 'none',
                      background: '#3b82f6', color: '#fff',
                      fontWeight: 700, fontSize: '0.88rem', cursor: 'pointer',
                    }}
                  >
                    + Collect ₹{Math.round(hasBalance ? s.balance_due : s.final_gap).toLocaleString('en-IN')}
                    {s.show_final_collection && !hasBalance ? ' (Final Settlement)' : ''}
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* ── Payment Modal ── */}
      {payModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
          onClick={() => setPayModal(null)}
        >
          <div style={{
            background: '#fff', borderRadius: '16px', padding: '24px',
            width: '360px', boxShadow: '0 24px 60px rgba(0,0,0,0.2)',
          }}
            onClick={e => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>
              💰 {payModal.label}
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: '0.75rem', color: '#6b7280' }}>
              Job #{payModal.jobId}
            </p>

            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
              Amount (₹)
            </label>
            <input
              type="number"
              value={payAmount}
              onChange={e => setPayAmount(e.target.value)}
              style={{
                width: '100%', padding: '10px 12px', border: '1.5px solid #e5e7eb',
                borderRadius: '8px', fontSize: '1rem', fontWeight: 700,
                marginBottom: '12px', boxSizing: 'border-box',
              }}
            />

            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
              Payment Mode
            </label>
            <select
              value={payMode}
              onChange={e => setPayMode(e.target.value)}
              style={{
                width: '100%', padding: '9px 12px', border: '1.5px solid #e5e7eb',
                borderRadius: '8px', fontSize: '0.82rem', marginBottom: '12px',
                background: '#fff', boxSizing: 'border-box',
              }}
            >
              {PAYMENT_MODES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>

            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block', marginBottom: '4px' }}>
              Notes (optional)
            </label>
            <input
              value={payNotes}
              onChange={e => setPayNotes(e.target.value)}
              placeholder="e.g. Cash received in person"
              style={{
                width: '100%', padding: '9px 12px', border: '1.5px solid #e5e7eb',
                borderRadius: '8px', fontSize: '0.82rem',
                marginBottom: '20px', boxSizing: 'border-box',
              }}
            />

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => setPayModal(null)}
                style={{
                  flex: 1, padding: '10px', borderRadius: '8px',
                  border: '1px solid #e5e7eb', background: '#f9fafb',
                  fontSize: '0.82rem', cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleRecordPayment}
                disabled={payLoading}
                style={{
                  flex: 2, padding: '10px', borderRadius: '8px', border: 'none',
                  background: payLoading ? '#93c5fd' : '#3b82f6',
                  color: '#fff', fontWeight: 700, fontSize: '0.88rem',
                  cursor: payLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {payLoading ? 'Recording...' : `Record ₹${parseFloat(payAmount || '0').toLocaleString('en-IN')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// ─── Main Page ───────────────────────────────────────────
export default function TenderDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  // Change the tab type
const [tab, setTab] = useState<'mukkadams' | 'farmers' | 'payments'>('mukkadams');
  const [search, setSearch] = useState('');
  const [clusterFilter, setClusterFilter] = useState('');
  const [clusters, setClusters] = useState<ClusterOption[]>([]);
// Add alongside clusterFilter state
const [noCluster, setNoCluster] = useState(false);


const [pruningFrom, setPruningFrom] = useState('');
const [pruningTo, setPruningTo] = useState('');
  // ── AddToClusterModal state ──
  const [clusterModal, setClusterModal] = useState<{
    clusterId: number;
    clusterName: string;
    farmerId: string; // pre-selected farmer (future: pass to modal)
  } | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (clusterFilter) params.cluster_id = clusterFilter;

      const [dashRes, clusterRes] = await Promise.all([
        axios.get(`${API_BASE}/api/tender-dashboard/`, { params }),
        axios.get(`${API_BASE}/api/clusters/`),
      ]);
      setData(dashRes.data);
      setClusters(clusterRes.data?.results || clusterRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };



  useEffect(() => { fetchData(); }, [clusterFilter]);
const filteredMukkadams = (data?.mukkadams || []).filter(m => {
  const matchesSearch = 
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.mobile.includes(search);
  if (noCluster) return matchesSearch && m.clusters.length === 0;
  return matchesSearch;
});


const filteredFarmers = (data?.farmers || []).filter(f => {
  const matchesSearch =
    f.farmer_name.toLowerCase().includes(search.toLowerCase()) ||
    f.phone_number.includes(search) ||
    f.farmer_id.includes(search);

  if (!matchesSearch) return false;

  if (noCluster) {
    const plotsInCluster = countPlotsInCluster(f.plots_by_cluster);
    if (plotsInCluster >= f.total_plots) return false;
  }

  // Pruning date range filter — match if nearest pruning falls within range
  if (pruningFrom || pruningTo) {
    const nearest = getNearestPruningDate(f);
    if (!nearest) return false;
    const nearestStr = nearest.toISOString().split('T')[0]; // "YYYY-MM-DD"
    if (pruningFrom && nearestStr < pruningFrom) return false;
    if (pruningTo && nearestStr > pruningTo) return false;
  }

  return true;
});
// const filteredFarmers = (data?.farmers || []).filter(f => {
//   const matchesSearch =
//     f.farmer_name.toLowerCase().includes(search.toLowerCase()) ||
//     f.phone_number.includes(search) ||
//     f.farmer_id.includes(search);

//   if (noCluster) {
//     // "No cluster" = has plots that are NOT in any cluster
//     const totalPlots = f.total_plots;
//     const plotsInCluster = countPlotsInCluster(f.plots_by_cluster);
//     return matchesSearch && plotsInCluster < totalPlots; // has at least 1 unassigned plot
//   }
//   return matchesSearch;
// });

  const handleOpenClusterModal = (clusterId: number, clusterName: string, farmerId: string) => {
    setClusterModal({ clusterId, clusterName, farmerId });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Tender Dashboard</h1>
            <p className="text-sm text-gray-500">Mukkadams & Farmers for tender operations</p>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 bg-teal-500 text-white rounded-lg hover:bg-teal-600 text-sm font-medium"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {data && (
            
          <div className="grid grid-cols-3 gap-4 mb-4">
            {[
              { label: 'Total Mukkadams', value: data?.summary?.total_mukkadams, color: 'text-teal-600', bg: 'bg-teal-50' },
              { label: 'Total Farmers', value: data?.summary?.total_farmers, color: 'text-blue-600', bg: 'bg-blue-50' },
              { label: 'Tender Jobs', value: data?.summary?.total_tender_jobs, color: 'text-purple-600', bg: 'bg-purple-50' },
            ].map(s => (
              <div key={s.label} className={`${s.bg} rounded-xl p-3 text-center`}>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-gray-500">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex border border-gray-200 rounded-lg overflow-hidden">
  <button
    onClick={() => { setTab('mukkadams'); setNoCluster(false); setClusterFilter(''); }}
    className={`px-5 py-2 text-sm font-medium transition ${tab === 'mukkadams' ? 'bg-teal-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
  >
    <Users size={15} className="inline mr-1" />
    Mukkadams ({data?.mukkadams?.length || 0})
  </button>
  <button
    onClick={() => { setTab('farmers'); setNoCluster(false); setClusterFilter(''); }}
    className={`px-5 py-2 text-sm font-medium transition ${tab === 'farmers' ? 'bg-blue-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
  >
    <User size={15} className="inline mr-1" />
    Farmers ({data?.farmers?.length || 0})
  </button>
  {/* <button
    onClick={() => { setTab('payments'); setNoCluster(false); setClusterFilter(''); }}
    className={`px-5 py-2 text-sm font-medium transition ${tab === 'payments' ? 'bg-orange-500 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
  >
    <IndianRupee size={15} className="inline mr-1" />
    Payments
  </button> */}
</div>

<div className="flex items-center gap-2 flex-wrap flex-1">
  {/* Search */}
  <div className="relative" style={{ minWidth: '160px', flex: 1 }}>
    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
    <input
      value={search}
      onChange={e => setSearch(e.target.value)}
      placeholder={tab === 'mukkadams' ? 'Search mukkadams...' : 'Search farmers...'}
      className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
    />
  </div>

  {/* Pruning date range — farmers only */}
  {tab === 'farmers' && (
    <div className="flex items-center gap-1 shrink-0">
      <span className="text-xs text-gray-400 whitespace-nowrap">🌿</span>
      <input
        type="date"
        value={pruningFrom}
        onChange={e => setPruningFrom(e.target.value)}
        style={{ width: '130px' }}
        className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
      />
      <span className="text-xs text-gray-400">–</span>
      <input
        type="date"
        value={pruningTo}
        onChange={e => setPruningTo(e.target.value)}
        style={{ width: '130px' }}
        className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300"
      />
      {(pruningFrom || pruningTo) && (
        <button
          onClick={() => { setPruningFrom(''); setPruningTo(''); }}
          className="text-gray-400 hover:text-gray-600 text-xs px-1"
        >✕</button>
      )}
    </div>
  )}

  {/* Mukkadam cluster filter */}
  {tab === 'mukkadams' && (
    <select
      key="mukkadam-filter"
      value={noCluster ? 'NO_CLUSTER' : ''}
      onChange={e => setNoCluster(e.target.value === 'NO_CLUSTER')}
      className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300 shrink-0"
    >
      <option value="">All Mukkadams</option>
      <option value="NO_CLUSTER">⚠ No Cluster</option>
    </select>
  )}

  {/* Farmer cluster filter */}
  {tab === 'farmers' && (
    <select
      key="farmer-filter"
      value={noCluster ? 'NO_CLUSTER' : clusterFilter}
      onChange={e => {
        if (e.target.value === 'NO_CLUSTER') {
          setNoCluster(true);
          setClusterFilter('');
        } else {
          setNoCluster(false);
          setClusterFilter(e.target.value);
        }
      }}
      className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-300 shrink-0"
    >
      <option value="">All Clusters</option>
      <option value="NO_CLUSTER">⚠ No Cluster</option>
      {clusters.map(c => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  )}
</div>
        </div>
      </div>

      {/* Content */}
{/* Content */}
<div className="p-6">
  {loading ? (
    <div className="flex justify-center items-center py-24">
      <RefreshCw size={32} className="animate-spin text-teal-400" />
    </div>
  ) : tab === 'mukkadams' ? (
    <div className="space-y-3">
      {filteredMukkadams.length === 0
        ? <div className="text-center py-16 text-gray-400">No mukkadams found</div>
        : filteredMukkadams.map(m => (
          <MukkadamCard key={m.id} m={m} clusters={clusters} onSuccess={fetchData} />
        ))
      }
    </div>
  ) : tab === 'farmers' ? (
    <div className="space-y-3">
      {filteredFarmers.length === 0
        ? <div className="text-center py-16 text-gray-400">No farmers found</div>
        : filteredFarmers.map(f => (
          <FarmerCard key={f.farmer_id} farmer={f} clusters={clusters} onSuccess={fetchData} />
        ))
      }
    </div>
  ) : (
    <PaymentsTab clusters={clusters} />
  )}
</div>

      {/* AddToClusterModal — rendered at root level to avoid z-index issues */}
      {clusterModal && (
        // Import your AddToClusterModal here and pass props:
        // <AddToClusterModal
        //   clusterId={clusterModal.clusterId}
        //   clusterName={clusterModal.clusterName}
        //   mode="farmer"
        //   onClose={() => { setClusterModal(null); fetchData(); }}
        // />
        //
        // Replace the div below with the real modal once imported:
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
            zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setClusterModal(null)}
        >
          <div
            style={{
              background: '#fff', borderRadius: '14px', padding: '2rem',
              boxShadow: '0 24px 60px rgba(0,0,0,0.25)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <p className="font-bold text-lg mb-2">
              Add to: {clusterModal.clusterName}
            </p>
            <p className="text-sm text-gray-500 mb-4">
              Farmer ID: {clusterModal.farmerId}
            </p>
            <p className="text-xs text-gray-400 italic">
             {clusterModal && (
  <AddToClusterModal
    clusterId={clusterModal.clusterId}
    clusterName={clusterModal.clusterName}
    mode="farmer"
    onClose={() => {
      setClusterModal(null);
      fetchData(); // refresh so coverage bar updates
    }}
  />
)}
            </p>
            <button
              onClick={() => setClusterModal(null)}
              className="mt-4 px-4 py-2 bg-gray-100 rounded-lg text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
function AddToClusterModalM({
  mukkadam,
  cluster,
  onConfirm,
  onCancel,
  saving,
}: {
  mukkadam: Mukkadam;
  cluster: ClusterOption;
  onConfirm: (transportPrice: number, weeklyPaymentDay: number, advanceAmount: number, weeklyAmount: number) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [transportPrice, setTransportPrice] = useState('');
  const [weeklyPaymentDay, setWeeklyPaymentDay] = useState<number>(0);

  // Now editable, pre-filled with calculated defaults
  const [advanceAmount, setAdvanceAmount] = useState(String(getAdvanceAmount(mukkadam.crew_size ?? 0)));
  const [weeklyAmount, setWeeklyAmount] = useState(String(getWeeklyAmount(mukkadam.crew_size ?? 0)));

  const handleSubmit = () => {
    const price = parseFloat(transportPrice);
    const advance = parseFloat(advanceAmount);
    const weekly = parseFloat(weeklyAmount);

    if (isNaN(price) || price < 0) { toast.error('Enter a valid transport price'); return; }
    if (isNaN(advance) || advance < 0) { toast.error('Enter a valid advance amount'); return; }
    if (isNaN(weekly) || weekly < 0) { toast.error('Enter a valid weekly payment'); return; }

    onConfirm(price, weeklyPaymentDay, advance, weekly);
  };

  const inputStyle = {
    width: '100%', padding: '8px 10px', borderRadius: '7px',
    border: '1.5px solid #e5e7eb', fontSize: '0.88rem',
    outline: 'none', boxSizing: 'border-box' as const,
  };

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
        zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#fff', borderRadius: '12px', padding: '24px',
          width: '380px', boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: '18px' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#111827' }}>
            Add to {cluster.name}
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#6b7280' }}>
            {mukkadam.name} · Crew size: {mukkadam.crew_size ?? '—'}
          </p>
        </div>

        {/* Advance + Weekly — now editable, side by side */}
        <div style={{
          background: '#f0fdfa', border: '1px solid #99f6e4',
          borderRadius: '8px', padding: '12px 14px', marginBottom: '18px',
        }}>
          <p style={{ margin: '0 0 10px', fontSize: '0.72rem', fontWeight: 700, color: '#0f766e', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Payment Configuration
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '4px' }}>
                Advance Amount (₹)
              </label>
              <input
                type="number"
                min="0"
                value={advanceAmount}
                onChange={e => setAdvanceAmount(e.target.value)}
                style={inputStyle}
                onFocus={e => (e.currentTarget.style.borderColor = '#14b8a6')}
                onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
              />
              <p style={{ margin: '3px 0 0', fontSize: '0.62rem', color: '#6b7280' }}>
                Default: ₹{getAdvanceAmount(mukkadam.crew_size ?? 0).toLocaleString()}
              </p>
            </div>
            <div>
              <label style={{ fontSize: '0.72rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '4px' }}>
                Weekly Payment (₹)
              </label>
              <input
                type="number"
                min="0"
                value={weeklyAmount}
                onChange={e => setWeeklyAmount(e.target.value)}
                style={inputStyle}
                onFocus={e => (e.currentTarget.style.borderColor = '#14b8a6')}
                onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
              />
              <p style={{ margin: '3px 0 0', fontSize: '0.62rem', color: '#6b7280' }}>
                Default: ₹{getWeeklyAmount(mukkadam.crew_size ?? 0).toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        {/* Transport Price */}
        <div style={{ marginBottom: '14px' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '6px' }}>
            Transport Price (₹) <span style={{ color: '#ef4444' }}>*</span>
          </label>
          <input
            autoFocus
            type="number"
            min="0"
            value={transportPrice}
            onChange={e => setTransportPrice(e.target.value)}
            placeholder="e.g. 5000"
            style={inputStyle}
            onFocus={e => (e.currentTarget.style.borderColor = '#14b8a6')}
            onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
          />
        </div>

        {/* Weekly Payment Day */}
        <div style={{ marginBottom: '22px' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '6px' }}>
            Weekly Payment Day
          </label>
          <select
            value={weeklyPaymentDay}
            onChange={e => setWeeklyPaymentDay(Number(e.target.value))}
            style={{ ...inputStyle, background: '#fff', cursor: 'pointer' }}
          >
            {WEEKDAY_OPTIONS.map(d => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={onCancel} disabled={saving} style={{
            flex: 1, padding: '9px', borderRadius: '7px',
            border: '1.5px solid #e5e7eb', background: '#fff',
            color: '#6b7280', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
          }}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !transportPrice}
            style={{
              flex: 1, padding: '9px', borderRadius: '7px', border: 'none',
              background: saving ? '#99f6e4' : '#14b8a6',
              color: '#fff', fontSize: '0.85rem', fontWeight: 600,
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? 'Adding...' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Mukkadam Add to Cluster Trigger ────────────────────
function MukkadamAddToCluster({ mukkadam, clusters, onSuccess }: {
  mukkadam: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<ClusterOption | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const filtered = clusters.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const alreadyInCluster = (clusterId: number) =>
    mukkadam.clusters.some(c => c.id === clusterId);

  const handleClusterSelect = (cluster: ClusterOption) => {
    if (saving || alreadyInCluster(cluster.id)) return;
    setOpen(false);
    setSearch('');
    setSelectedCluster(cluster); // opens modal
  };

  const handleConfirm = async (transportPrice: number, weeklyPaymentDay: number,advanceAmount:number, weeklyAmount:number) => {
    if (!selectedCluster) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${selectedCluster.id}/add_mukkadam/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mukkadam_id: mukkadam.id,
          transport_price: transportPrice,
          weekly_payment_day: weeklyPaymentDay,
          advance_amount: advanceAmount,   // ← new
          weekly_amount: weeklyAmount,    
        }),
      });

      const data = await res.json();

      if (res.ok) {
        toast.success(data.message ?? `${mukkadam.name} → ${selectedCluster.name}`);
        setSelectedCluster(null);
        onSuccess();
      } else {
        toast.error(data.error ?? 'Failed to add mukkadam');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <button
          ref={btnRef}
          onClick={e => { e.stopPropagation(); setOpen(v => !v); }}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            padding: '3px 10px 3px 8px', borderRadius: '999px',
            border: `1.5px solid ${open ? '#14b8a6' : '#d1d5db'}`,
            background: open ? '#f0fdfa' : '#fff',
            color: open ? '#0f766e' : '#6b7280',
            fontSize: '0.72rem', fontWeight: 600,
            cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.15s',
          }}
        >
          <PlusCircle size={12} />
          Add to Cluster
        </button>

        {open && (
          <PortalDropdown
            anchorRef={btnRef as React.RefObject<HTMLElement>}
            onClose={() => { setOpen(false); setSearch(''); }}
          >
            <DropdownHeader label="Add mukkadam to" />
            <div style={{ padding: '8px 10px', borderBottom: '1px solid #f3f4f6' }}>
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search clusters..."
                style={{
                  width: '100%', padding: '5px 9px',
                  border: '1px solid #e5e7eb', borderRadius: '6px',
                  fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box',
                }}
                onFocus={e => (e.currentTarget.style.borderColor = '#14b8a6')}
                onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
              />
            </div>
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              {filtered.length === 0 ? (
                <p style={{ padding: '12px', textAlign: 'center', fontSize: '0.8rem', color: '#9ca3af', margin: 0 }}>
                  No clusters found
                </p>
              ) : filtered.map(c => (
                <ClusterItem
                  key={c.id}
                  name={c.name}
                  alreadyIn={alreadyInCluster(c.id)}
                  saving={saving}
                  onClick={() => handleClusterSelect(c)}
                />
              ))}
            </div>
          </PortalDropdown>
        )}
      </div>

      {/* Step 2 — Modal */}
      {selectedCluster && (
        <AddToClusterModalM
          mukkadam={mukkadam}
          cluster={selectedCluster}
          onConfirm={handleConfirm}
          onCancel={() => setSelectedCluster(null)}
          saving={saving}
        />
      )}
    </>
  );
}
