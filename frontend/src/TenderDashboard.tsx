

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

// ─── Mukkadam Card ───────────────────────────────────────
// ─── Mukkadam Add to Cluster Trigger ────────────────────
function MukkadamAddToCluster({ mukkadam, clusters, onSuccess }: {
  mukkadam: Mukkadam;
  clusters: ClusterOption[];
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const filtered = clusters.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const alreadyInCluster = (clusterId: number) =>
    mukkadam.clusters.some(c => c.id === clusterId);

  const handleAdd = async (cluster: ClusterOption) => {
    if (saving || alreadyInCluster(cluster.id)) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/cluster/${cluster.id}/add_mukkadam/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mukkadam_id: mukkadam.id }),
      });
      if (res.ok) {
        toast.success(`${mukkadam.name} → ${cluster.name}`);
        setOpen(false);
        setSearch('');
        onSuccess();
      } else {
        toast.error('Failed to add mukkadam');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setSaving(false);
    }
  };

  return (
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
                onClick={() => handleAdd(c)}
              />
            ))}
          </div>
        </PortalDropdown>
      )}
    </div>
  );
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

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Farmer Header */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition"
        onClick={() => setExpanded(!expanded)}
      >
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

// ─── Main Page ───────────────────────────────────────────
export default function TenderDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'mukkadams' | 'farmers'>('mukkadams');
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
      <div className="p-6">
        {loading ? (
          <div className="flex justify-center items-center py-24">
            <RefreshCw size={32} className="animate-spin text-teal-400" />
          </div>
        ) : tab === 'mukkadams' ? (
          <div className="space-y-3">
            {filteredMukkadams.length === 0
              ? <div className="text-center py-16 text-gray-400">No mukkadams found</div>
              : filteredMukkadams.map(m => <MukkadamCard
    key={m.id}
    m={m}
    clusters={clusters}
    onSuccess={fetchData}
  />)
            }
          </div>
        ) : (
          <div className="space-y-3">
            {filteredFarmers.length === 0
              ? <div className="text-center py-16 text-gray-400">No farmers found</div>
              : filteredFarmers.map(f => (
                <FarmerCard
                
                    key={f.farmer_id}
                    farmer={f}
                    clusters={clusters}
                    onSuccess={fetchData}  // ← just re-fetch, no modal state needed
                />
                ))
            }
          </div>
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